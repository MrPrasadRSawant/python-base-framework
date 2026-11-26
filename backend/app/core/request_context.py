"""Per-request context shared by middleware, exception handlers and log records.

The request id is kept in a ContextVar, so anything running inside a request
(endpoints, services, the DB layer) is tagged automatically when it logs.
It is also stored in ``scope["state"]``, so code that runs outside the
ContextVar's lifetime can still find it.
"""

import re
import uuid
from contextvars import ContextVar, Token
from typing import Any

REQUEST_ID_STATE_KEY = "request_id"
REQUEST_BODY_STATE_KEY = "request_body"
REQUEST_BODY_TRUNCATED_STATE_KEY = "request_body_truncated"

# Only accept safe client-supplied ids (prevents log injection and huge values).
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{8,128}$")

SYSTEM_ACTOR = "system"

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
# Who is acting (fills created_by / updated_by). Auth middleware should call
# set_current_actor(user_id) once authentication exists.
_actor_ctx: ContextVar[str] = ContextVar("actor", default=SYSTEM_ACTOR)


def get_current_actor() -> str:
    return _actor_ctx.get()


def set_current_actor(actor: str) -> Token:
    return _actor_ctx.set(actor)


def reset_current_actor(token: Token) -> None:
    _actor_ctx.reset(token)


def generate_request_id() -> str:
    return uuid.uuid4().hex


def is_valid_request_id(value: str | None) -> bool:
    return bool(value and _VALID_REQUEST_ID.match(value))


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> Token:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id_ctx.reset(token)


def request_id_from_scope(scope: dict[str, Any]) -> str | None:
    """Request id stored on the ASGI scope, falling back to the ContextVar."""
    state = scope.get("state") or {}
    return state.get(REQUEST_ID_STATE_KEY) or get_request_id()
