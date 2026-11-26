"""Log formatters. Both redact the final output, so nothing leaves unmasked:
messages, ``extra`` context, exception messages and tracebacks."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.redaction import Redactor, get_redactor

# Attributes every LogRecord has; anything else came from ``extra=...``.
_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "request_id",
    "color_message",  # added by uvicorn
}


def extract_context(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _STANDARD_ATTRS and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """One JSON object per line, suitable for log shippers (ELK, Loki, Datadog...)."""

    def __init__(self, redactor: Redactor | None = None) -> None:
        super().__init__()
        self.redactor = redactor or get_redactor()

    def format(self, record: logging.LogRecord) -> str:
        r = self.redactor
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": r.redact_text(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
        }
        context = extract_context(record)
        if context:
            payload["context"] = r.redact(context)
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, _ = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__,
                "message": r.redact_text(str(exc_value)),
                "traceback": r.redact_text(self.formatException(record.exc_info)),
            }
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable single line (+ traceback) for local development."""

    DEFAULT_FORMAT = (
        "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s:%(lineno)d | %(message)s"
    )

    def __init__(self, redactor: Redactor | None = None, fmt: str | None = None) -> None:
        super().__init__(fmt or self.DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        self.redactor = redactor or get_redactor()

    def formatMessage(self, record: logging.LogRecord) -> str:
        # Context goes on the message line, before any traceback.
        line = super().formatMessage(record)
        context = extract_context(record)
        if context:
            line += " | " + json.dumps(self.redactor.redact(context), default=str)
        return line

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return self.redactor.redact_text(super().format(record))
