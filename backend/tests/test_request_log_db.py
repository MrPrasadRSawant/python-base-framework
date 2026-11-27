"""requests table: one row per request, id = the request id, built from the access log."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.models import RequestLog

HEADER = settings.REQUEST_ID_HEADER
RID = "0192f5f0-2222-7000-8000-000000000001"
USER_DATA_COLUMNS = {
    "path",
    "client_ip",
    "user_agent",
    "query_params",
    "request_headers",
    "request_body",
}


def test_table_is_requests_keyed_by_request_id():
    assert RequestLog.__tablename__ == "requests"
    columns = RequestLog.__table__.columns
    assert columns["id"].primary_key and "request_id" not in columns


def test_one_row_per_request_with_id_equal_to_request_id(client, request_rows):
    r = client.get("/_test/missing/9", headers={HEADER: RID})
    assert len(request_rows) == 1
    row = request_rows[0]
    assert row["id"] == uuid.UUID(RID) == uuid.UUID(r.headers[HEADER])
    assert row["method"] == "GET"
    assert row["route"] == "/_test/missing/{thing_id}"
    assert row["endpoint"].endswith(".missing")
    assert row["status_code"] == 404
    assert row["duration_ms"] >= 0
    assert row["created_by"] == "system"
    assert row["started_on"] <= datetime.now(UTC)


def test_generated_request_id_becomes_the_row_id(client, request_rows):
    r = client.get("/")
    assert request_rows[0]["id"] == uuid.UUID(r.headers[HEADER])


def test_route_includes_router_prefix(client, request_rows, admin_headers):
    client.post(  # 422, no DB needed
        "/api/v1/exception-logs/search", json={"limit": 0}, headers=admin_headers
    )
    assert request_rows[-1]["route"] == "/api/v1/exception-logs/search"
    assert request_rows[-1]["status_code"] == 422


def test_server_errors_and_unknown_urls_are_recorded(client, request_rows):
    client.get("/_test/boom")
    client.get("/no/such/url")
    boom, unknown = request_rows
    assert boom["status_code"] == 500 and boom["route"] == "/_test/boom"
    assert unknown["status_code"] == 404 and unknown["route"] is None


def test_health_checks_are_excluded(client, request_rows):
    client.get("/api/v1/health")
    assert request_rows == []


def test_no_user_data_stored(client, request_rows):
    client.get(
        "/_test/missing/987654",  # an id inside the URL path
        params={"email": "bob@example.com"},
        headers={"User-Agent": "pytest-ua", "X-Forwarded-For": "203.0.113.7"},
    )
    row = request_rows[-1]
    assert row["route"] == "/_test/missing/{thing_id}"  # template only
    assert not USER_DATA_COLUMNS & set(row)
    assert not USER_DATA_COLUMNS & set(RequestLog.__table__.columns.keys())
    for value in ("987654", "bob@example.com", "pytest-ua", "203.0.113.7"):
        assert value not in str(row)


def test_row_keys_match_table_columns(client, request_rows):
    client.get("/")
    assert set(request_rows[0]) <= set(RequestLog.__table__.columns.keys())


def test_started_on_is_end_minus_duration(request_rows):
    logging.getLogger("app.access").info(
        "x",
        extra={
            "request_id": RID,
            "method": "GET",
            "path": "/x",
            "status_code": 200,
            "duration_ms": 1500.0,
        },
    )
    row = request_rows[0]
    assert datetime.now(UTC) - row["started_on"] >= timedelta(milliseconds=1500)


def test_access_lines_without_a_request_id_are_skipped(request_rows):
    logging.getLogger("app.access").info("x", extra={"path": "/x", "status_code": 200})
    assert request_rows == []


# ----------------------------------------------------------- real database
@pytest.fixture
def seed_requests(db_session_factory):
    """Insert requests rows tagged via `endpoint`; returns {rid: request id}."""

    async def _seed(prefix: str, *rows: dict) -> dict[str, uuid.UUID]:
        from app.schemas.request_log import RequestLogCreate
        from app.services.request_log import RequestLogService

        now = datetime.now(UTC)
        ids = {row["rid"]: uuid.uuid4() for row in rows}
        async with db_session_factory() as session:
            await RequestLogService(session).create_many(
                [
                    RequestLogCreate(
                        id=ids[row["rid"]],
                        started_on=now,
                        method=row.get("method", "GET"),
                        route=row.get("route", "/api/v1/orders/{order_id}"),
                        endpoint=f"{prefix}{row['rid']}",
                        status_code=row.get("status", 200),
                        duration_ms=row.get("ms", 10.0),
                    )
                    for row in rows
                ]
            )
        return ids

    return _seed


@pytest.mark.anyio
async def test_service_search(seed_requests, db_session_factory):
    from app.schemas.search import SearchRequest
    from app.services.request_log import RequestLogService

    prefix = f"t{uuid.uuid4().hex[:8]}-"
    await seed_requests(
        prefix, *({"rid": str(i), "ms": float(i * 100), "status": 200 if i < 3 else 500}
                  for i in range(5))
    )  # fmt: skip
    async with db_session_factory() as session:
        slow_failures = await RequestLogService(session).search(
            SearchRequest(
                filters=[
                    {"field": "endpoint", "op": "starts_with", "value": prefix},
                    {"field": "status_code", "op": "gte", "value": 500},
                ],
                sort=[{"field": "duration_ms", "direction": "desc"}],
            )
        )
    assert [r.duration_ms for r in slow_failures.records] == [400.0, 300.0]


@pytest.mark.anyio
async def test_report_join_requests_with_service_calls(seed_requests, db_session_factory):
    """The point of id = request id: JOIN the log tables for reports."""
    from sqlalchemy import text

    from app.schemas.service_call_log import ServiceCallLogCreate
    from app.services.service_call_log import ServiceCallLogService

    prefix = f"t{uuid.uuid4().hex[:8]}-"
    ids = await seed_requests(prefix, {"rid": "a", "ms": 50.0})
    now = datetime.now(UTC)
    async with db_session_factory() as session:
        await ServiceCallLogService(session).create_many(
            [
                ServiceCallLogCreate(
                    request_id=ids["a"],
                    call_order=order,
                    service_name=name,
                    started_on=now,
                    duration_ms=ms,
                    status="success",
                )
                for order, name, ms in [
                    (1, "OrderService.get", 4.0),
                    (2, "OrderService.update", 30.0),
                ]
            ]
        )
        rows = (
            await session.execute(
                text(
                    "SELECT r.route, r.duration_ms AS request_ms, s.call_order, s.service_name "
                    "FROM requests r JOIN service_call_logs s ON s.request_id = r.id "
                    "WHERE r.id = :id ORDER BY s.call_order"
                ),
                {"id": ids["a"]},
            )
        ).all()
    assert [(r.call_order, r.service_name) for r in rows] == [
        (1, "OrderService.get"),
        (2, "OrderService.update"),
    ]
    assert rows[0].route == "/api/v1/orders/{order_id}" and rows[0].request_ms == 50.0


# ------------------------------------------------------------ API endpoints
URL = "/api/v1/requests"


def test_search_rejects_unknown_and_removed_fields(client, admin_headers):
    client.headers.update(admin_headers)
    for field in ("path", "client_ip", "request_id"):
        r = client.post(f"{URL}/search", json={"filters": [{"field": field, "value": "x"}]})
        assert r.status_code == 422, field
        assert r.json()["error"]["code"] == "invalid_filter"
    assert client.get(f"{URL}?limit=1000").status_code == 422


@pytest.mark.anyio
async def test_api_list_search_and_detail_by_request_id(api, seed_requests):
    prefix = f"t{uuid.uuid4().hex[:8]}-"
    ids = await seed_requests(
        prefix,
        {"rid": "fast", "ms": 5.0},
        {"rid": "slow", "ms": 900.0, "status": 500},
        {"rid": "post", "method": "POST", "route": "/api/v1/orders", "status": 201},
    )
    mine = {"field": "endpoint", "op": "starts_with", "value": prefix}

    # slowest failing requests first
    r = await api.post(
        f"{URL}/search",
        json={
            "filters": [mine, {"field": "status_code", "op": "gte", "value": 500}],
            "sort": [{"field": "duration_ms", "direction": "desc"}],
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert [x["id"] for x in body["records"]] == [str(ids["slow"])]
    assert body["metadata"]["total_count"] == 1
    assert "path" not in body["records"][0]

    # filter by request id = id
    r = await api.post(
        f"{URL}/search", json={"filters": [{"field": "id", "op": "eq", "value": str(ids["post"])}]}
    )
    assert [x["method"] for x in r.json()["records"]] == ["POST"]

    # text search on route
    r = await api.post(f"{URL}/search", json={"filters": [mine], "search": "orders/{order_id}"})
    assert sorted(x["endpoint"] for x in r.json()["records"]) == [f"{prefix}fast", f"{prefix}slow"]

    # simple list + detail by request id
    r = await api.get(URL, params={"limit": 1})
    assert set(r.json()) == {"metadata", "records"} and r.json()["metadata"]["limit"] == 1
    r = await api.get(f"{URL}/{ids['slow']}")
    assert r.status_code == 200 and r.json()["record"]["duration_ms"] == 900.0
    r = await api.get(f"{URL}/{uuid.uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


@pytest.fixture
def api(api, admin_headers):
    """The log APIs need *_logs:read: call them as an admin."""
    api.headers.update(admin_headers)
    return api
