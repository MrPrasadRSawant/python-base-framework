"""Build a redacted, log-safe snapshot of the current HTTP request."""

import json
from typing import Any
from urllib.parse import parse_qsl

from app.core.config import settings
from app.core.redaction import get_redactor
from app.core.request_context import (
    REQUEST_BODY_STATE_KEY,
    REQUEST_BODY_TRUNCATED_STATE_KEY,
    request_id_from_scope,
)


def _headers(scope: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (k.decode("latin-1"), v.decode("latin-1")) for k, v in scope.get("headers") or []
    ]


def client_ip(scope: dict[str, Any]) -> str | None:
    for key, value in _headers(scope):
        if key.lower() == "x-forwarded-for":
            return value.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else None


def route_info(scope: dict[str, Any]) -> dict[str, str | None]:
    """Matched route template and endpoint function (set by the router)."""
    route = scope.get("route")
    endpoint = scope.get("endpoint")
    return {
        "route": getattr(route, "path", None),
        "endpoint": (
            f"{endpoint.__module__}.{endpoint.__qualname__}"
            if endpoint is not None and hasattr(endpoint, "__qualname__")
            else None
        ),
    }


def _parse_body(raw: bytes, content_type: str) -> Any:
    redactor = get_redactor()
    text = raw.decode("utf-8", errors="replace")
    if "application/json" in content_type:
        try:
            return redactor.redact(json.loads(text))
        except ValueError:
            pass  # truncated or invalid JSON: fall back to text masking
    if "application/x-www-form-urlencoded" in content_type:
        return redactor.redact_pairs(parse_qsl(text, keep_blank_values=True))
    return redactor.redact_text(text)


def request_body(scope: dict[str, Any]) -> dict[str, Any] | None:
    state = scope.get("state") or {}
    raw: bytes | None = state.get(REQUEST_BODY_STATE_KEY)
    if not raw:
        return None
    content_type = dict((k.lower(), v) for k, v in _headers(scope)).get("content-type", "")
    return {
        "content": _parse_body(raw, content_type.lower()),
        "truncated": bool(state.get(REQUEST_BODY_TRUNCATED_STATE_KEY)),
    }


def build_request_context(
    scope: dict[str, Any], *, include_headers: bool = False, include_body: bool = False
) -> dict[str, Any]:
    redactor = get_redactor()
    query_string = scope.get("query_string", b"").decode("latin-1")
    context: dict[str, Any] = {
        "request_id": request_id_from_scope(scope),
        "method": scope.get("method"),
        "path": scope.get("path"),
        **route_info(scope),
        "client_ip": client_ip(scope),
        "user_agent": next(
            (v for k, v in _headers(scope) if k.lower() == "user-agent"), None
        ),
    }
    if query_string:
        context["query_params"] = redactor.redact_pairs(
            parse_qsl(query_string, keep_blank_values=True)
        )
    if include_headers:
        context["headers"] = redactor.redact_pairs(_headers(scope))
    if include_body and settings.LOG_REQUEST_BODY_ON_ERROR:
        body = request_body(scope)
        if body is not None:
            context["body"] = body
    return context
