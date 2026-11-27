"""Route protection. AuthenticationMiddleware has already checked the token;
these dependencies only decide whether the caller may use the route.

    @router.get("/me")
    async def me(principal: CurrentUser): ...

    @router.get("", dependencies=[Depends(require_permission("request_logs:read"))])
    async def list_request_logs(...): ...

No token / bad token -> 401 (with WWW-Authenticate: Bearer).
Wrong caller type or missing permission -> 403.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.openapi.models import OAuthFlowClientCredentials, OAuthFlowPassword, OAuthFlows
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security.principal import (
    AUTH_ERROR_STATE_KEY,
    PRINCIPAL_STATE_KEY,
    Principal,
)

_AUTH_ERRORS = {
    None: ("not_authenticated", "Authentication is required."),
    "token_expired": ("token_expired", "The access token has expired."),
    "invalid_token": ("invalid_token", "The access token is invalid."),
}


# Security schemes: only document the auth in OpenAPI, which gives Swagger its
# Authorize button and lock icons. They never reject (auto_error=False); the
# token was already checked by AuthenticationMiddleware.
_TOKEN_URL = f"{settings.API_V1_PREFIX}/auth/token"
oauth2 = OAuth2(
    flows=OAuthFlows(
        password=OAuthFlowPassword(tokenUrl=_TOKEN_URL),
        clientCredentials=OAuthFlowClientCredentials(tokenUrl=_TOKEN_URL),
    ),
    scheme_name="OAuth2",
    description=(
        "**password**: username or email + password (client_id/secret empty). "
        "**clientCredentials**: an API client's client_id + client_secret."
    ),
    auto_error=False,
)
bearer_token = HTTPBearer(
    scheme_name="BearerToken",
    description="Paste an access token (from /auth/login or /auth/token).",
    auto_error=False,
)


async def get_principal(
    request: Request,
    _oauth2: Annotated[str | None, Security(oauth2)] = None,
    _bearer: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_token)] = None,
) -> Principal:
    principal = getattr(request.state, PRINCIPAL_STATE_KEY, None)
    if principal is not None:
        return principal
    reason = getattr(request.state, AUTH_ERROR_STATE_KEY, None)
    code, message = _AUTH_ERRORS.get(reason, _AUTH_ERRORS["invalid_token"])
    header = "Bearer" if reason is None else 'Bearer error="invalid_token"'
    raise UnauthorizedError(message, error_code=code, headers={"WWW-Authenticate": header})


async def require_user(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if principal.type != "user":
        raise ForbiddenError("This endpoint is for signed-in users only.")
    return principal


async def require_service(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if principal.type != "service":
        raise ForbiddenError("This endpoint is for API clients only.")
    return principal


def require_permission(*codes: str) -> Callable[..., Awaitable[Principal]]:
    """Caller (user or service) must hold every listed permission."""

    async def check(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        missing = sorted(set(codes) - principal.permissions)
        if missing:
            raise ForbiddenError(details={"missing_permissions": missing})
        return principal

    # Read by tests/test_api_docs.py to check each route documents what it requires.
    check.required_permissions = tuple(str(code) for code in codes)  # type: ignore[attr-defined]
    return check


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
CurrentUser = Annotated[Principal, Depends(require_user)]
CurrentService = Annotated[Principal, Depends(require_service)]
