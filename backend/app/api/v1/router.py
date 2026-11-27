from fastapi import APIRouter, Depends

from app.api.responses import PROTECTED, error_responses
from app.api.v1.endpoints import (
    api_clients,
    auth,
    exception_logs,
    health,
    request_logs,
    roles,
    service_call_logs,
    users,
)
from app.core.config import settings
from app.core.security import require_permission
from app.core.security.permissions import Perm

# Errors any route can return. Routes add their own (401, 403, 404, ...) with
# error_responses() from app/api/responses.py.
ERROR_RESPONSES = error_responses(422, 500)

api_router = APIRouter(responses=ERROR_RESPONSES)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(api_clients.router)


def _protected(router: APIRouter, perm: Perm) -> None:
    """Every route of ``router`` needs ``perm`` (documented in each route's docstring)."""
    api_router.include_router(
        router,
        dependencies=[Depends(require_permission(perm))],
        responses=error_responses(*PROTECTED),
    )


# Log APIs: every route needs the matching *_logs:read permission.
if settings.EXCEPTION_LOG_API_ENABLED:
    _protected(exception_logs.router, Perm.EXCEPTION_LOGS_READ)
if settings.REQUEST_LOG_API_ENABLED:
    _protected(request_logs.router, Perm.REQUEST_LOGS_READ)
if settings.SERVICE_CALL_LOG_API_ENABLED:
    _protected(service_call_logs.router, Perm.SERVICE_CALL_LOGS_READ)
