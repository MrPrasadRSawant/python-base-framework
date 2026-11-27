"""List/search endpoints against real PostgreSQL (rolled back after each test).

Uses exception_log as the sample table; the search engine is the same for all tables.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.models import ExceptionLog

pytestmark = pytest.mark.anyio
HEADER = settings.REQUEST_ID_HEADER
URL = "/api/v1/exception-logs"


@pytest.fixture
def prefix() -> str:
    return f"t{uuid.uuid4().hex[:8]}-"


@pytest.fixture
def seed(db_session_factory, prefix):
    """Insert exception_log rows whose request_id starts with the test prefix."""

    async def _seed(*rows: dict) -> list[ExceptionLog]:
        now = datetime.now(UTC)
        objs = [
            ExceptionLog(
                occurred_on=row.pop("occurred_on", now),
                level=row.pop("level", "ERROR"),
                logger="app.exceptions",
                request_id=f"{prefix}{row.pop('rid')}",
                message=row.pop("message", "boom"),
                **row,
            )
            for row in rows
        ]
        async with db_session_factory() as s:
            s.add_all(objs)
            await s.commit()
        return objs

    return _seed


async def _search(api, payload):
    r = await api.post(f"{URL}/search", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _mine(prefix, **extra):
    return {"filters": [{"field": "request_id", "op": "starts_with", "value": prefix}], **extra}


async def test_pagination_metadata_and_pages(api, seed, prefix):
    await seed(*({"rid": f"{i:02d}"} for i in range(25)))
    sort = [{"field": "occurred_on", "direction": "asc"}]

    first = await _search(api, _mine(prefix, limit=10, offset=0, sort=sort))
    meta = first["metadata"]
    assert (meta["limit"], meta["offset"], meta["count"], meta["total_count"]) == (10, 0, 10, 25)
    assert meta["has_more"] is True and meta["next_offset"] == 10
    assert meta["previous_offset"] is None
    assert meta["sort"] == [
        {"field": "occurred_on", "direction": "asc"},
        {"field": "id", "direction": "asc"},
    ]
    assert meta["request_id"] and meta["timestamp"]

    last = await _search(api, _mine(prefix, limit=10, offset=20, sort=sort))
    assert last["metadata"]["count"] == 5
    assert last["metadata"]["has_more"] is False and last["metadata"]["next_offset"] is None
    assert last["metadata"]["previous_offset"] == 10

    # All rows share occurred_on, so only the id tie-breaker keeps pages stable:
    # walking every page must yield each row exactly once.
    seen, offset = [], 0
    while offset is not None:
        page = await _search(api, _mine(prefix, limit=7, offset=offset, sort=sort))
        seen += [r["id"] for r in page["records"]]
        offset = page["metadata"]["next_offset"]
    assert len(seen) == len(set(seen)) == 25


async def test_include_total_false_skips_count_but_keeps_has_more(api, seed, prefix):
    await seed({"rid": "a"}, {"rid": "b"}, {"rid": "c"})
    page = await _search(api, _mine(prefix, limit=2, include_total=False))
    assert page["metadata"]["total_count"] is None
    assert page["metadata"]["has_more"] is True


async def test_free_text_search_is_case_insensitive_across_fields(api, seed, prefix):
    await seed(
        {"rid": "a", "message": "Contains the MAGIC word"},
        {"rid": "b", "message": "nothing here"},
        {"rid": "c", "exception_type": "MagicError"},
    )
    page = await _search(api, _mine(prefix, search="magic"))
    assert sorted(r["request_id"].removeprefix(prefix) for r in page["records"]) == ["a", "c"]


async def test_wildcards_in_search_match_literally(api, seed, prefix):
    await seed({"rid": "a", "message": "100%_off"}, {"rid": "b", "message": "100 percent"})
    page = await _search(api, _mine(prefix, search="%_"))
    assert [r["request_id"].removeprefix(prefix) for r in page["records"]] == ["a"]


async def test_filter_operators(api, seed, prefix):
    now = datetime.now(UTC)
    a, _, _ = await seed(
        {"rid": "a", "status_code": 404, "error_code": "not_found"},
        {"rid": "b", "status_code": 500, "occurred_on": now - timedelta(days=2)},
        {"rid": "c", "status_code": 422, "error_code": "validation_error"},
    )

    async def rids(*filters):
        page = await _search(api, {"filters": [*_mine(prefix)["filters"], *filters]})
        return sorted(r["request_id"].removeprefix(prefix) for r in page["records"])

    assert await rids({"field": "id", "op": "eq", "value": str(a.id)}) == ["a"]
    assert await rids({"field": "status_code", "op": "in", "value": [404, 422]}) == ["a", "c"]
    assert await rids({"field": "status_code", "op": "not_in", "value": [404]}) == ["b", "c"]
    assert await rids({"field": "status_code", "op": "gte", "value": "422"}) == ["b", "c"]
    assert await rids({"field": "error_code", "op": "is_null", "value": True}) == ["b"]
    assert await rids({"field": "error_code", "op": "ends_with", "value": "FOUND"}) == ["a"]

    window = [(now - timedelta(days=1)).isoformat(), (now + timedelta(minutes=5)).isoformat()]
    assert await rids({"field": "occurred_on", "op": "between", "value": window}) == ["a", "c"]


async def test_soft_deleted_hidden_unless_requested(api, seed, prefix):
    await seed({"rid": "keep"}, {"rid": "gone", "is_deleted": True})
    visible = await _search(api, _mine(prefix))
    assert [r["request_id"].removeprefix(prefix) for r in visible["records"]] == ["keep"]
    everything = await _search(api, _mine(prefix, include_deleted=True))
    assert everything["metadata"]["total_count"] == 2


async def test_get_list_and_record_envelopes(api, seed):
    (row,) = await seed({"rid": "one", "traceback": "Traceback ..."})

    r = await api.get(URL, params={"limit": 1, "offset": 0})
    body = r.json()
    assert set(body) == {"metadata", "records"}
    assert body["metadata"]["limit"] == 1
    assert body["metadata"]["request_id"] == r.headers[HEADER]
    assert body["records"][0]["traceback"] == "Traceback ..."

    r = await api.get(f"{URL}/{row.id}")
    body = r.json()
    assert set(body) == {"metadata", "record"}
    assert body["record"]["traceback"] == "Traceback ..."
    assert body["metadata"]["request_id"] == r.headers[HEADER]


async def test_missing_record_returns_404_envelope(api):
    r = await api.get(f"{URL}/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_base_service_crud(db_session_factory, prefix):
    from app.schemas.base import UpdateSchema
    from app.schemas.exception_log import ExceptionLogCreate
    from app.schemas.search import SearchRequest
    from app.services.exception_log import ExceptionLogService

    class MessageUpdate(UpdateSchema):  # exception_log has no Update schema; test-only
        message: str | None = None
        error_code: str | None = None

    async with db_session_factory() as session:
        service = ExceptionLogService(session)
        created = await service.create(
            ExceptionLogCreate(
                occurred_on=datetime.now(UTC),
                level="ERROR",
                logger="app.exceptions",
                request_id=f"{prefix}svc",
                message="  boom  ",  # CreateSchema trims whitespace
            )
        )
        assert created.message == "boom"
        await service.create_many(
            [
                ExceptionLogCreate(
                    occurred_on=datetime.now(UTC),
                    level="ERROR",
                    logger="app.jobs",
                    request_id="other-request",
                    message="not mine",
                )
            ]
        )
        result = await service.search(SearchRequest(**_mine(prefix)))
        assert result.total_count == 1
        row = result.records[0]
        assert row.created_by == "system" and row.is_deleted is False
        assert (await service.get(row.id)).request_id == f"{prefix}svc"

        # update: only fields that were sent change
        updated = await service.update(row.id, MessageUpdate(message="edited"))
        assert updated.message == "edited" and updated.level == "ERROR"
        assert updated.updated_by == "system" and updated.updated_on is not None
        assert await service.update(uuid.uuid4(), MessageUpdate(message="x")) is None

        # delete: soft delete, then hidden from get
        assert await service.delete(row.id) is True
        assert await service.get(row.id) is None
        assert await service.get(row.id, include_deleted=True) is not None
        assert await service.delete(row.id) is False  # already deleted
