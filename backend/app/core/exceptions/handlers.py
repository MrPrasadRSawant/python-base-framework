"""Exception handlers for *expected* error types.

Every handler does the same two things through ``_handle``:
  1. log the exception via ``report_exception`` (request id + redaction),
  2. return the standard error envelope via ``error_response``.

Truly unhandled exceptions are caught by ``UnhandledExceptionMiddleware``
instead (see app/middleware/unhandled_exception.py for why).
"""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions.errors import AppException
from app.core.exceptions.reporting import report_exception
from app.core.exceptions.responses import error_response
from app.core.redaction import REDACTED, get_redactor
from app.core.request_context import request_id_from_scope


def _handle(
    request: Request,
    exc: Exception,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
    log_summary: str | None = None,
) -> JSONResponse:
    report_exception(
        request.scope,
        exc,
        status_code=status_code,
        error_code=code,
        details=details,
        summary=log_summary,
    )
    return error_response(
        status_code=status_code,
        code=code,
        message=message,
        request_id=request_id_from_scope(request.scope),
        details=details,
        headers=headers,
    )


def _status_to_code(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "http_error"


def _sanitize_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep loc/msg/type and mask raw user ``input`` (it may contain passwords)."""
    redactor = get_redactor()
    cleaned = []
    for err in errors:
        loc = list(err.get("loc", ()))
        item: dict[str, Any] = {"loc": loc, "msg": err.get("msg"), "type": err.get("type")}
        if "input" in err:
            field = loc[-1] if loc else None
            item["input"] = (
                REDACTED if redactor.is_sensitive_key(field) else redactor.redact(err["input"])
            )
        cleaned.append(item)
    return jsonable_encoder(cleaned, custom_encoder={Exception: str})


# --------------------------------------------------------------------- handlers
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _handle(
        request,
        exc,
        status_code=exc.status_code,
        code=exc.error_code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    is_text = isinstance(exc.detail, str)
    return _handle(
        request,
        exc,
        status_code=exc.status_code,
        code=_status_to_code(exc.status_code),
        message=exc.detail if is_text else HTTPStatus(exc.status_code).phrase,
        details=None if is_text else exc.detail,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = _sanitize_validation_errors(exc.errors())
    return _handle(
        request,
        exc,
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details=details,
        # str(exc) embeds the raw rejected input, so never log it directly
        log_summary=f"{len(details)} validation error(s)",
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Never expose SQL / driver messages to clients; the full detail goes to the log.
    if isinstance(exc, IntegrityError):
        status_code, code, message = 409, "conflict", "The request conflicts with existing data."
    elif isinstance(exc, DBAPIError) and exc.connection_invalidated:
        status_code, code, message = (
            503,
            "database_unavailable",
            "The database is temporarily unavailable.",
        )
    else:
        status_code, code, message = 500, "database_error", "A database error occurred."
    return _handle(request, exc, status_code=status_code, code=code, message=message)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
