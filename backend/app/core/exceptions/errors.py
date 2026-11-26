"""Application exception hierarchy.

Raise these from endpoints/services instead of ``HTTPException``: each one
carries an HTTP status, a stable machine-readable ``error_code`` and optional
``details``, and is logged + rendered consistently by the exception handlers.

    raise NotFoundError("Item not found", details={"item_id": item_id})
"""

from typing import Any


class AppException(Exception):
    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppException):
    status_code = 400
    error_code = "bad_request"
    message = "The request is invalid."


class UnauthorizedError(AppException):
    status_code = 401
    error_code = "unauthorized"
    message = "Authentication is required."


class ForbiddenError(AppException):
    status_code = 403
    error_code = "forbidden"
    message = "You do not have permission to perform this action."


class NotFoundError(AppException):
    status_code = 404
    error_code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppException):
    status_code = 409
    error_code = "conflict"
    message = "The request conflicts with the current state of the resource."


class UnprocessableEntityError(AppException):
    status_code = 422
    error_code = "unprocessable_entity"
    message = "The request could not be processed."


class TooManyRequestsError(AppException):
    status_code = 429
    error_code = "too_many_requests"
    message = "Too many requests. Please retry later."


class ServiceUnavailableError(AppException):
    status_code = 503
    error_code = "service_unavailable"
    message = "The service is temporarily unavailable."
