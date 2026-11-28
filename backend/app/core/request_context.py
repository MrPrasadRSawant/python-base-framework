"""Per-request context shared by middleware, exception handlers and log records.

The request id is kept in a ContextVar, so anything running inside a request
(endpoints, services, the DB layer) is tagged automatically when it logs.
It is also stored in ``scope["state"]``, so code that runs outside the
ContextVar's lifetime can still find it.
"""

import itertools
import uuid
from contextvars import ContextVar, Token
from typing import Any

REQUEST_ID_STATE_KEY = "request_id"
REQUEST_BODY_STATE_KEY = "request_body"
REQUEST_BODY_TRUNCATED_STATE_KEY = "request_body_truncated"

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
    """A new request id. It is also the primary key of the request's row in ``requests``,
    so it is a UUID: v7 (time-ordered) on Python 3.14+, else v4."""
    return str(uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4())


def parse_request_id(value: str | None) -> str | None:
    """Normalize a client-sent X-Request-ID, or None if it isn't a UUID.

    Only UUIDs are accepted (any common spelling: upper case, no hyphens, braces),
    which also rules out log injection and oversized values.
    """
    if not value or len(value) > 64:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def request_id_as_uuid(value: str | None) -> uuid.UUID | None:
    """For DB columns: the request id as a UUID, or None if absent/invalid."""
    normalized = parse_request_id(value)
    return uuid.UUID(normalized) if normalized else None


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> Token:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id_ctx.reset(token)


# Numbers tracked service calls 1, 2, 3... within one request. One counter object
# per request, shared by every task/thread the request spawns.
_call_counter_ctx: ContextVar[Any] = ContextVar("call_counter", default=None)


def start_call_counter() -> Token:
    return _call_counter_ctx.set(itertools.count(1))


def reset_call_counter(token: Token) -> None:
    _call_counter_ctx.reset(token)


def next_call_order() -> int | None:
    """Next service-call number in this request, or None outside a request."""
    counter = _call_counter_ctx.get()
    return next(counter) if counter is not None else None


# The current request's ASGI scope, for code deep inside a request that needs to
# know where it came from (route, client IP), e.g. the user activity log.
# Read-only: never mutate it. Reading the route only works once routing is done.
_scope_ctx: ContextVar[dict[str, Any] | None] = ContextVar("request_scope", default=None)


def get_request_scope() -> dict[str, Any] | None:
    return _scope_ctx.get()


def set_request_scope(scope: dict[str, Any]) -> Token:
    return _scope_ctx.set(scope)


def reset_request_scope(token: Token) -> None:
    _scope_ctx.reset(token)


def request_id_from_scope(scope: dict[str, Any]) -> str | None:
    """Request id stored on the ASGI scope, falling back to the ContextVar."""
    state = scope.get("state") or {}
    return state.get(REQUEST_ID_STATE_KEY) or get_request_id()
