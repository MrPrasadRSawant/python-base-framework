"""List/search endpoints against real PostgreSQL (rolled back after each test)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.models import ExceptionLog

pytestmark = pytest.mark.anyio
HEADER = settings.REQUEST_ID_HEADER


@pytest.fixture
def prefix() -> str:
    return f"t{uuid.uuid4().hex[:8]}-"


async def _create(api, name, description=None):
    r = await api.post("/api/v1/items", json={"name": name, "description": description})
    assert r.status_code == 201, r.text
    return r.json()["record"]


async def _search(api, payload):
    r = await api.post("/api/v1/items/search", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _mine(prefix, **extra):
    return {"filters": [{"field": "name", "op": "starts_with", "value": prefix}], **extra}


async def test_pagination_metadata_and_pages(api, prefix):
    for i in range(25):
        await _create(api, f"{prefix}{i:02d}")
    sort = [{"field": "name", "direction": "asc"}]

    first = await _search(api, _mine(prefix, limit=10, offset=0, sort=sort))
    meta = first["metadata"]
    assert (meta["limit"], meta["offset"], meta["count"], meta["total_count"]) == (10, 0, 10, 25)
    assert meta["has_more"] is True and meta["next_offset"] == 10
    assert meta["previous_offset"] is None
    assert meta["sort"] == [
        {"field": "name", "direction": "asc"},
        {"field": "id", "direction": "asc"},
    ]
    assert meta["request_id"] and meta["timestamp"]

    last = await _search(api, _mine(prefix, limit=10, offset=20, sort=sort))
    assert last["metadata"]["count"] == 5
    assert last["metadata"]["has_more"] is False and last["metadata"]["next_offset"] is None
    assert last["metadata"]["previous_offset"] == 10

    # Walking all pages yields every row exactly once, in order.
    names, offset = [], 0
    while offset is not None:
        page = await _search(api, _mine(prefix, limit=7, offset=offset, sort=sort))
        names += [r["name"] for r in page["records"]]
        offset = page["metadata"]["next_offset"]
    assert names == [f"{prefix}{i:02d}" for i in range(25)]


async def test_include_total_false_skips_count_but_keeps_has_more(api, prefix):
    for i in range(3):
        await _create(api, f"{prefix}{i}")
    page = await _search(api, _mine(prefix, limit=2, include_total=False))
    assert page["metadata"]["total_count"] is None
    assert page["metadata"]["has_more"] is True


async def test_free_text_search_is_case_insensitive_across_fields(api, prefix):
    await _create(api, f"{prefix}alpha", "Contains the MAGIC word")
    await _create(api, f"{prefix}beta", "nothing here")
    await _create(api, f"{prefix}Magic-gamma")
    page = await _search(api, _mine(prefix, search="magic"))
    assert sorted(r["name"] for r in page["records"]) == [f"{prefix}Magic-gamma", f"{prefix}alpha"]


async def test_wildcards_in_search_match_literally(api, prefix):
    await _create(api, f"{prefix}100%_off")
    await _create(api, f"{prefix}100 percent")
    page = await _search(api, _mine(prefix, search="%_"))
    assert [r["name"] for r in page["records"]] == [f"{prefix}100%_off"]


async def test_filter_operators(api, prefix):
    a = await _create(api, f"{prefix}a")
    b = await _create(api, f"{prefix}b", "desc")
    await _create(api, f"{prefix}c")
    await api.patch(f"/api/v1/items/{b['id']}", json={"description": "edited"})

    async def names(*filters):
        page = await _search(api, {"filters": [*_mine(prefix)["filters"], *filters]})
        return sorted(r["name"].removeprefix(prefix) for r in page["records"])

    assert await names({"field": "id", "op": "eq", "value": a["id"]}) == ["a"]
    assert await names({"field": "name", "op": "in", "value": [f"{prefix}a", f"{prefix}c"]}) == [
        "a",
        "c",
    ]
    assert await names({"field": "name", "op": "not_in", "value": [f"{prefix}a"]}) == ["b", "c"]
    assert await names({"field": "updated_on", "op": "is_null", "value": False}) == ["b"]
    assert await names({"field": "description", "op": "is_null", "value": True}) == ["a", "c"]
    assert await names({"field": "name", "op": "ends_with", "value": "C"}) == ["c"]

    now = datetime.now(UTC)
    window = [(now - timedelta(minutes=5)).isoformat(), (now + timedelta(minutes=5)).isoformat()]
    assert await names({"field": "created_on", "op": "between", "value": window}) == [
        "a",
        "b",
        "c",
    ]
    future = (now + timedelta(days=1)).isoformat()
    assert await names({"field": "created_on", "op": "gte", "value": future}) == []


async def test_soft_deleted_hidden_unless_requested(api, prefix):
    keep = await _create(api, f"{prefix}keep")
    gone = await _create(api, f"{prefix}gone")
    assert (await api.delete(f"/api/v1/items/{gone['id']}")).status_code == 204

    visible = await _search(api, _mine(prefix))
    assert [r["id"] for r in visible["records"]] == [keep["id"]]
    everything = await _search(api, _mine(prefix, include_deleted=True))
    assert everything["metadata"]["total_count"] == 2


async def test_get_list_and_record_envelopes(api, prefix):
    created = await _create(api, f"{prefix}one")
    r = await api.get("/api/v1/items", params={"limit": 1, "offset": 0})
    body = r.json()
    assert set(body) == {"metadata", "records"}
    assert body["metadata"]["limit"] == 1
    assert body["metadata"]["request_id"] == r.headers[HEADER]

    r = await api.get(f"/api/v1/items/{created['id']}")
    body = r.json()
    assert set(body) == {"metadata", "record"}
    assert body["record"]["id"] == created["id"]
    assert body["metadata"]["request_id"] == r.headers[HEADER]


async def test_exception_log_search(api, db_session_factory):
    rid = f"trace-{uuid.uuid4().hex}"
    async with db_session_factory() as s:
        s.add(
            ExceptionLog(
                occurred_on=datetime.now(UTC),
                level="ERROR",
                logger="app.exceptions",
                request_id=rid,
                status_code=500,
                error_code="internal_server_error",
                exception_type="RuntimeError",
                message="boom",
                traceback="Traceback ...",
            )
        )
        await s.commit()

    r = await api.post(
        "/api/v1/exception-logs/search",
        json={"filters": [{"field": "request_id", "op": "eq", "value": rid}]},
    )
    page = r.json()
    assert page["metadata"]["total_count"] == 1
    row = page["records"][0]
    assert row["status_code"] == 500 and "traceback" not in row  # summary in lists

    detail = (await api.get(f"/api/v1/exception-logs/{row['id']}")).json()
    assert detail["record"]["traceback"] == "Traceback ..."
