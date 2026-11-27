from typing import Any

from fastapi import APIRouter

from app.api.v1.endpoints import exception_logs, health, request_logs
from app.core.config import settings
from app.schemas.error import ErrorResponse

# Documents the standard error envelope on every route in /docs.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in {
        400: "Bad request",
        404: "Not found",
        409: "Conflict",
        422: "Validation error",
        500: "Internal server error",
    }.items()
}

api_router = APIRouter(responses=ERROR_RESPONSES)
api_router.include_router(health.router, tags=["health"])
if settings.EXCEPTION_LOG_API_ENABLED:
    api_router.include_router(exception_logs.router)
if settings.REQUEST_LOG_API_ENABLED:
    api_router.include_router(request_logs.router)
