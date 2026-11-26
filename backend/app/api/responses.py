"""Build the standard envelopes (see app/schemas/responses.py).

Endpoints return these dicts; FastAPI validates them against the declared
``response_model`` (ORM objects in ``record``/``records`` are read from attributes).
"""

from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id
from app.db.search import SearchResult


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
            "has_more": result.has_more,
            "next_offset": result.offset + count if result.has_more else None,
            "previous_offset": (
                max(result.offset - result.limit, 0) if result.offset > 0 else None
            ),
            "sort": [{"field": f, "direction": d} for f, d in result.sort],
        },
        "records": result.records,
    }
