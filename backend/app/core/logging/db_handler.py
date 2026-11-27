"""Logging handlers that copy log records into the log tables.

They are extra handlers next to the console and file handlers, so the file
logs stay exactly as they are.

ExceptionLogDBHandler -> exception_log
* everything from ``report_exception`` (logger ``app.exceptions``) whose
  status code is >= ``EXCEPTION_LOG_DB_MIN_STATUS``: all API errors.
* any other ERROR-or-worse record carrying a traceback, e.g.
  ``logger.exception(...)`` in a service, background job or startup code.

RequestLogDBHandler -> request_logs
* the one access-log line per request (logger ``app.access``), except
  excluded paths such as the health check.

Only technical data is stored: no request body, query string, headers, IP
address or user agent, and user ``input`` is stripped from ``details``.
Text fields are redacted before the row is handed to the non-blocking sink.
"""

import json
import logging
import os
import socket
import traceback
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.core.logging.db_sink import SINK_LOGGER_NAME
from app.core.redaction import Redactor
from app.core.request_context import get_current_actor, request_id_as_uuid
from app.schemas.exception_log import ExceptionLogCreate
from app.schemas.request_log import RequestLogCreate

EXCEPTIONS_LOGGER_NAME = "app.exceptions"
ACCESS_LOGGER_NAME = "app.access"
_HOSTNAME = socket.gethostname()

# Keys inside ``details`` that carry what the user sent (e.g. validation errors).
_USER_INPUT_KEYS = frozenset({"input"})


class RowSink(Protocol):
    def enqueue(self, row: Any) -> None: ...


def _cut(value: Any, length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= length else text[: length - 3] + "..."


def _strip_user_input(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_user_input(v) for k, v in value.items() if k not in _USER_INPUT_KEYS}
    if isinstance(value, list):
        return [_strip_user_input(v) for v in value]
    return value


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    return json.loads(json.dumps(value, default=str))


class ExceptionLogDBHandler(logging.Handler):
    def __init__(
        self,
        sink: RowSink,
        redactor: Redactor,
        *,
        min_status: int = 400,
        environment: str | None = None,
    ) -> None:
        super().__init__(level=logging.WARNING)
        self.sink = sink
        self.redactor = redactor
        self.min_status = min_status
        self.environment = environment

    def should_store(self, record: logging.LogRecord) -> bool:
        if record.name.startswith(SINK_LOGGER_NAME):
            return False  # never persist the sink's own failures (loop guard)
        if record.name == EXCEPTIONS_LOGGER_NAME:
            status = getattr(record, "status_code", None)
            return status is None or status >= self.min_status
        return record.levelno >= logging.ERROR and bool(record.exc_info)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.should_store(record):
                self.sink.enqueue(self.build_row(record))
        except Exception:
            self.handleError(record)

    def build_row(self, record: logging.LogRecord) -> ExceptionLogCreate:
        r = self.redactor
        request: dict[str, Any] = getattr(record, "request", None) or {}

        exc_type_name = getattr(record, "exception_type", None)
        tb_text = None
        if record.exc_info and record.exc_info[0] is not None:
            exc_type_name = exc_type_name or record.exc_info[0].__name__
            tb_text = r.redact_text("".join(traceback.format_exception(*record.exc_info)))

        details = _strip_user_input(getattr(record, "details", None))
        # Values are truncated to the column sizes first, so validation can't drop the row.
        return ExceptionLogCreate(
            created_by=_cut(get_current_actor(), 255),  # captured in the request's context
            occurred_on=datetime.fromtimestamp(record.created, UTC),
            level=record.levelname,
            logger=_cut(record.name, 255),
            source=_cut(f"{record.module}:{record.funcName}:{record.lineno}", 512),
            request_id=request_id_as_uuid(getattr(record, "request_id", None)),
            status_code=getattr(record, "status_code", None),
            error_code=_cut(getattr(record, "error_code", None), 100),
            exception_type=_cut(exc_type_name, 255),
            # API errors: the bare reason; other records (jobs, startup): the log message.
            message=r.redact_text(getattr(record, "reason", None) or record.getMessage()),
            traceback=tb_text,
            method=_cut(request.get("method"), 16),
            path=_cut(request.get("path"), 2048),
            route=_cut(request.get("route"), 512),
            endpoint=_cut(request.get("endpoint"), 512),
            details=_json_safe(r.redact(details)),
            environment=_cut(self.environment, 50),
            hostname=_cut(_HOSTNAME, 255),
            process_id=record.process or os.getpid(),
        )


class RequestLogDBHandler(logging.Handler):
    """Turns each access-log line into a request_logs row (no user data)."""

    def __init__(self, sink: RowSink, *, exclude_paths: Iterable[str] = ()) -> None:
        super().__init__(level=logging.INFO)
        self.sink = sink
        self.exclude_paths = frozenset(exclude_paths)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name != ACCESS_LOGGER_NAME:
                return
            # The path is only read for this check, never stored.
            if getattr(record, "path", None) in self.exclude_paths:
                return
            row = self.build_row(record)
            if row is not None:
                self.sink.enqueue(row)
        except Exception:
            self.handleError(record)

    def build_row(self, record: logging.LogRecord) -> RequestLogCreate | None:
        request_id = request_id_as_uuid(getattr(record, "request_id", None))
        if request_id is None:
            return None  # not an HTTP request handled by RequestContextMiddleware
        duration_ms = float(getattr(record, "duration_ms", 0.0))
        # The access line is written when the request ends; derive the start time.
        finished = datetime.fromtimestamp(record.created, UTC)
        return RequestLogCreate(
            created_by=_cut(get_current_actor(), 255),  # captured in the request's context
            id=request_id,  # the request id is the row's primary key
            started_on=finished - timedelta(milliseconds=duration_ms),
            method=_cut(getattr(record, "method", None) or "-", 16),
            route=_cut(getattr(record, "route", None), 512),
            endpoint=_cut(getattr(record, "endpoint", None), 512),
            status_code=int(getattr(record, "status_code", 0)),
            duration_ms=duration_ms,
        )
