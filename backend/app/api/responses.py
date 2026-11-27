"""Build the standard envelopes (see app/schemas/responses.py).

Endpoints return these dicts; FastAPI validates them against the declared
``response_model`` (ORM objects in ``record``/``records`` are read from attributes).
"""

from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id
from app.db.search import SearchResult
from app.schemas.error import ErrorResponse


def response_metadata() -> dict[str, Any]:
    return {"request_id": get_request_id(), "timestamp": datetime.now(UTC)}


def record_response(record: Any) -> dict[str, Any]:
    return {"metadata": response_metadata(), "record": record}


def list_response(result: SearchResult) -> dict[str, Any]:
    count = len(result.records)
    return {
        "metadata": {
            **response_metadata(),
            "limit": result.limit,
            "offset": result.offset,
            "count": count,
            "total_count": result.total_count,
            "average_duration_ms": result.average_duration_ms,
            "has_more": result.has_more,
            "next_offset": result.offset + count if result.has_more else None,
            "previous_offset": (
                max(result.offset - result.limit, 0) if result.offset > 0 else None
            ),
            "sort": [{"field": f, "direction": d} for f, d in result.sort],
        },
        "records": result.records,
    }


# ------------------------------------------------------------ docs (OpenAPI)
_ERROR_TEXT = {
    400: "Bad request",
    401: "Not authenticated: missing, invalid or expired access token "
    "(`not_authenticated`, `invalid_token`, `token_expired`)",
    403: "Forbidden: the token lacks the required permission (`forbidden`, "
    "`details.missing_permissions`) or is the wrong token type",
    404: "Not found (`not_found`)",
    409: "Conflict",
    422: "Validation error (`validation_error`; field errors in `details`)",
    429: "Too many attempts (`rate_limited`); retry after the `Retry-After` header",
    500: "Unexpected server error (`internal_error`); report the `request_id`",
}

# Common sets for route decorators.
PROTECTED = (401, 403)


def error_responses(*items: int | tuple[int, str]) -> dict[int | str, dict[str, Any]]:
    """Document a route's error responses, all in the standard error envelope.

        @router.post("", responses=error_responses(*PROTECTED, (409, "`email_taken`")))
    """
    out: dict[int | str, dict[str, Any]] = {}
    for item in items:
        status, text = item if isinstance(item, tuple) else (item, _ERROR_TEXT[item])
        out[status] = {"model": ErrorResponse, "description": text}
    return out
