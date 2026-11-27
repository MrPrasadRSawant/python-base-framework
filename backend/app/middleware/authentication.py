"""Reads the Bearer token on every request and records who is calling.

* Valid token  -> ``request.state.principal`` and the current actor
  (``user:<id>`` / ``service:<client_id>``), so created_by / updated_by,
  the requests table and service_call_logs all show the caller.
* No token     -> anonymous (actor stays "system").
* Bad token    -> anonymous + ``request.state.auth_error`` (token_expired /
  invalid_token), so a protected route can explain its 401.

It never rejects a request itself: public routes keep working, and protected
routes reject through the dependencies in core/security/dependencies.py.
Verifying a JWT needs no DB access, so this is cheap.

Pure ASGI, like the other middleware: the actor ContextVar set here is visible
to everything inside the request, including the access log written after it.
"""

import jwt
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.request_context import reset_current_actor, set_current_actor
from app.core.security.principal import AUTH_ERROR_STATE_KEY, PRINCIPAL_STATE_KEY, Principal
from app.core.security.tokens import principal_from_token


def _authenticate(authorization: str | None) -> tuple[Principal | None, str | None]:
    if not authorization:
        return None, None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None, "invalid_token"
    try:
        return principal_from_token(token.strip()), None
    except jwt.ExpiredSignatureError:
        return None, "token_expired"
    except jwt.InvalidTokenError:
        return None, "invalid_token"


class AuthenticationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        principal, error = _authenticate(Headers(scope=scope).get("authorization"))
        state = scope.setdefault("state", {})
        state[PRINCIPAL_STATE_KEY] = principal
        state[AUTH_ERROR_STATE_KEY] = error

        if principal is None:
            await self.app(scope, receive, send)
            return
        token = set_current_actor(principal.actor)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_actor(token)
