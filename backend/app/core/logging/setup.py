"""Central logging configuration. Call ``setup_logging()`` once at startup."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import Settings
from app.core.logging.filters import RequestIdFilter
from app.core.logging.formatters import JsonFormatter, TextFormatter
from app.core.redaction import get_redactor

APP_LOG_FILE = "app.log"
ERROR_LOG_FILE = "error.log"

# Third-party loggers re-routed through our handlers (so they get request ids + redaction).
_ROUTED_LOGGERS = ("uvicorn", "uvicorn.error", "fastapi", "sqlalchemy", "asyncpg")


def _file_handler(settings: Settings, filename: str, level: int) -> logging.Handler:
    handler = RotatingFileHandler(
        settings.LOG_DIR / filename,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter(get_redactor()))
    return handler


def setup_logging(settings: Settings) -> None:
    level = logging.getLevelNamesMapping().get(settings.LOG_LEVEL.upper(), logging.INFO)
    redactor = get_redactor()
    request_id_filter = RequestIdFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        JsonFormatter(redactor) if settings.LOG_FORMAT == "json" else TextFormatter(redactor)
    )
    handlers: list[logging.Handler] = [console]

    if settings.LOG_TO_FILE:
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(_file_handler(settings, APP_LOG_FILE, level))
        handlers.append(_file_handler(settings, ERROR_LOG_FILE, logging.ERROR))

    if settings.EXCEPTION_LOG_DB_ENABLED:
        from app.core.logging.db_handler import ExceptionLogDBHandler
        from app.services.exception_log_sink import exception_log_sink

        exception_log_sink.max_queue = settings.EXCEPTION_LOG_QUEUE_SIZE
        exception_log_sink.batch_size = settings.EXCEPTION_LOG_BATCH_SIZE
        exception_log_sink.flush_interval = settings.EXCEPTION_LOG_FLUSH_INTERVAL
        handlers.append(
            ExceptionLogDBHandler(
                exception_log_sink,
                redactor,
                min_status=settings.EXCEPTION_LOG_DB_MIN_STATUS,
                environment=settings.ENVIRONMENT,
            )
        )

    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)
        existing.close()
    for handler in handlers:
        handler.addFilter(request_id_filter)
        root.addHandler(handler)
    root.setLevel(level)

    for name in _ROUTED_LOGGERS:
        lib_logger = logging.getLogger(name)
        lib_logger.handlers.clear()
        lib_logger.propagate = True

    # Our AccessLogMiddleware replaces uvicorn's access log (it adds request ids).
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    # SQL statements only when explicitly enabled (bound params may hold PII).
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.LOG_SQL else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
