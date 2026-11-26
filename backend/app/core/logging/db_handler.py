"""Logging handler that copies exception records into the exception_log table.

It is one more handler next to the console and file handlers, so the file
logs stay exactly as they are. Which records get stored:

* everything from ``report_exception`` (logger ``app.exceptions``) whose
  status code is >= ``EXCEPTION_LOG_DB_MIN_STATUS``: all API errors.
* any other ERROR-or-worse record carrying a traceback, e.g.
  ``logger.exception(...)`` in a service, background job or startup code.

Rows are fully redacted here and handed to the non-blocking sink.
"""

import json
import logging
import os
import socket
import traceback
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.redaction import Redactor
from app.core.request_context import get_current_actor
from app.services.exception_log_sink import SINK_LOGGER_NAME

EXCEPTIONS_LOGGER_NAME = "app.exceptions"
_HOSTNAME = socket.gethostname()


class RowSink(Protocol):
    def enqueue(self, row: dict[str, Any]) -> None: ...


def _cut(value: Any, length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= length else text[: length - 3] + "..."


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

    def build_row(self, record: logging.LogRecord) -> dict[str, Any]:
        r = self.redactor
        request: dict[str, Any] = r.redact(getattr(record, "request", None) or {})

        exc_type_name = getattr(record, "exception_type", None)
        tb_text = None
        if record.exc_info and record.exc_info[0] is not None:
            exc_type_name = exc_type_name or record.exc_info[0].__name__
            tb_text = r.redact_text("".join(traceback.format_exception(*record.exc_info)))

        body = request.get("body")
        return {
            "created_by": _cut(get_current_actor(), 255),  # captured in the request's context
            "occurred_on": datetime.fromtimestamp(record.created, UTC),
            "level": record.levelname,
            "logger": _cut(record.name, 255),
            "source": _cut(f"{record.module}:{record.funcName}:{record.lineno}", 512),
            "request_id": _cut(getattr(record, "request_id", None) or None, 128),
            "status_code": getattr(record, "status_code", None),
            "error_code": _cut(getattr(record, "error_code", None), 100),
            "exception_type": _cut(exc_type_name, 255),
            "message": r.redact_text(record.getMessage()),
            "traceback": tb_text,
            "method": _cut(request.get("method"), 16),
            "path": _cut(request.get("path"), 2048),
            "route": _cut(request.get("route"), 512),
            "endpoint": _cut(request.get("endpoint"), 512),
            "client_ip": _cut(request.get("client_ip"), 64),
            "user_agent": _cut(request.get("user_agent"), 512),
            "query_params": _json_safe(request.get("query_params")),
            "request_headers": _json_safe(request.get("headers")),
            "request_body": _json_safe(body if isinstance(body, dict) else None),
            "details": _json_safe(r.redact(getattr(record, "details", None))),
            "environment": _cut(self.environment, 50),
            "hostname": _cut(_HOSTNAME, 255),
            "process_id": record.process or os.getpid(),
        }
