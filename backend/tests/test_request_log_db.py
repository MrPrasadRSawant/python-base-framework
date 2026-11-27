"""request_logs: one row per request, built from the access log line."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.models import RequestLog

HEADER = settings.REQUEST_ID_HEADER
USER_DATA_COLUMNS = {
    "path",
    "client_ip",
    "user_agent",
    "query_params",
    "request_headers",
    "request_body",
}


def test_one_row_per_request(client, request_rows):
    r = client.get("/_test/missing/9", headers={HEADER: "trace-req-0001"})
    assert len(request_rows) == 1
    row = request_rows[0]
    assert row["request_id"] == "trace-req-0001" == r.headers[HEADER]
    assert row["method"] == "GET"
    assert row["route"] == "/_test/missing/{thing_id}"
    assert row["endpoint"].endswith(".missing")
    assert row["status_code"] == 404
    assert row["duration_ms"] >= 0
    assert row["created_by"] == "system"
    assert row["started_on"] <= datetime.now(UTC)


def test_route_includes_router_prefix(client, request_rows):
    client.post("/api/v1/exception-logs/search", json={"limit": 0})  # 422, no DB needed
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
    import logging

    logging.getLogger("app.access").info(
        "x", extra={"method": "GET", "path": "/x", "status_code": 200, "duration_ms": 1500.0}
    )
    row = request_rows[0]
    assert datetime.now(UTC) - row["started_on"] >= timedelta(milliseconds=1500)


# ----------------------------------------------------------- real database
@pytest.mark.anyio
async def test_service_writes_and_searches(db_session_factory):
    from app.schemas.request_log import RequestLogCreate
    from app.schemas.search import SearchRequest
    from app.services.request_log import RequestLogService

    rid = f"t{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    async with db_session_factory() as session:
        service = RequestLogService(session)
        await service.create_many(
            [
                RequestLogCreate(
                    started_on=now,
                    request_id=f"{rid}-{i}",
                    method="GET",
                    route="/api/v1/orders/{order_id}",
                    status_code=200 if i < 3 else 500,
                    duration_ms=float(i * 100),
                )
                for i in range(5)
            ]
        )
        slow_failures = await service.search(
            SearchRequest(
                filters=[
                    {"field": "request_id", "op": "starts_with", "value": rid},
                    {"field": "status_code", "op": "gte", "value": 500},
                ],
                sort=[{"field": "duration_ms", "direction": "desc"}],
            )
        )
        assert [r.duration_ms for r in slow_failures.records] == [400.0, 300.0]
        assert slow_failures.records[0].route == "/api/v1/orders/{order_id}"


# ------------------------------------------------------------ API endpoints
URL = "/api/v1/request-logs"


def test_search_rejects_unknown_and_removed_fields(client):
    for field in ("path", "client_ip"):
        r = client.post(f"{URL}/search", json={"filters": [{"field": field, "value": "x"}]})
        assert r.status_code == 422, field
        assert r.json()["error"]["code"] == "invalid_filter"
    assert client.get(f"{URL}?limit=1000").status_code == 422


@pytest.fixture
def seed_requests(db_session_factory):
    async def _seed(prefix: str, *rows: dict):
        from app.schemas.request_log import RequestLogCreate
        from app.services.request_log import RequestLogService

        now = datetime.now(UTC)
        async with db_session_factory() as session:
            await RequestLogService(session).create_many(
                [
                    RequestLogCreate(
                        started_on=now,
                        request_id=f"{prefix}{row['rid']}",
                        method=row.get("method", "GET"),
                        route=row.get("route", "/api/v1/orders/{order_id}"),
                        status_code=row.get("status", 200),
                        duration_ms=row.get("ms", 10.0),
                    )
                    for row in rows
                ]
            )

    return _seed


@pytest.mark.anyio
async def test_api_list_search_and_detail(api, seed_requests):
    prefix = f"t{uuid.uuid4().hex[:8]}-"
    await seed_requests(
        prefix,
        {"rid": "fast", "ms": 5.0},
        {"rid": "slow", "ms": 900.0, "status": 500},
        {"rid": "post", "method": "POST", "route": "/api/v1/orders", "status": 201},
    )
    mine = {"field": "request_id", "op": "starts_with", "value": prefix}

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
    assert [x["request_id"] for x in body["records"]] == [f"{prefix}slow"]
    assert body["metadata"]["total_count"] == 1
    assert body["metadata"]["request_id"] == r.headers[HEADER]
    assert "path" not in body["records"][0]

    # text search on route
    r = await api.post(f"{URL}/search", json={"filters": [mine], "search": "orders/{order_id}"})
    assert sorted(x["request_id"] for x in r.json()["records"]) == [
        f"{prefix}fast",
        f"{prefix}slow",
    ]

    # simple list + detail envelopes
    r = await api.get(URL, params={"limit": 1})
    assert set(r.json()) == {"metadata", "records"} and r.json()["metadata"]["limit"] == 1
    log_id = body["records"][0]["id"]
    r = await api.get(f"{URL}/{log_id}")
    assert r.status_code == 200 and r.json()["record"]["duration_ms"] == 900.0
    r = await api.get(f"{URL}/{uuid.uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
