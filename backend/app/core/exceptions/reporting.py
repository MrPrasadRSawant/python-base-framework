"""Single place where exceptions are written to the log.

* 5xx -> ERROR with traceback, request headers and body (all redacted)
* 4xx -> WARNING without traceback (client errors are expected), with body
"""

import logging
from typing import Any

from app.core.logging.request_info import build_request_context

logger = logging.getLogger("app.exceptions")


def report_exception(
    scope: dict[str, Any],
    exc: BaseException,
    *,
    status_code: int,
    error_code: str,
    details: Any = None,
    summary: str | None = None,
) -> None:
    """Log ``exc`` with the redacted request context.

    ``summary`` replaces ``str(exc)`` in the message for exceptions whose text
    embeds raw user input (e.g. RequestValidationError).
    """
    is_server_error = status_code >= 500
    context = build_request_context(
        scope, include_headers=is_server_error, include_body=True
    )
    request_id = context.pop("request_id")

    extra: dict[str, Any] = {
        "request_id": request_id,  # explicit: survives outside the ContextVar
        "status_code": status_code,
        "error_code": error_code,
        "exception_type": type(exc).__name__,
        "request": context,
    }
    if details is not None:
        extra["details"] = details
    # The bare reason ("Item not found"): stored as exception_log.message. The full
    # log line below also carries the URL path, which belongs in the log files only.
    reason = summary if summary is not None else str(exc) or type(exc).__name__
    extra["reason"] = reason

    message = (
        f"{type(exc).__name__} on {context.get('method')} {context.get('path')} "
        f"-> {status_code} {error_code}: {reason}"
    )
    if is_server_error:
        logger.error(message, exc_info=exc, extra=extra)
    else:
        logger.warning(message, extra=extra)
