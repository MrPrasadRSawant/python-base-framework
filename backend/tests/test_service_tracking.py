"""@track_service -> service_call_logs rows."""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.core.service_tracking import suppress_service_tracking, track_service
from app.main import app

HEADER = settings.REQUEST_ID_HEADER
RID = "0192f5f0-3333-7000-8000-000000000001"


class FakeRunningSink:
    running = True

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def enqueue(self, row) -> None:
        self.rows.append(row.model_dump())


@pytest.fixture
def calls(monkeypatch):
    import app.core.logging.db_sink as db_sink

    sink = FakeRunningSink()
    monkeypatch.setattr(db_sink, "service_call_log_sink", sink)
    return sink.rows


# ---- demo services used by the tests ----
class DemoBase:
    @track_service
    async def ping(self):
        return "pong"


class DemoService(DemoBase):
    @track_service
    async def load(self, n):
        return n * 2

    @track_service
    def compute(self):
        return 42

    @track_service
    async def explode(self):
        raise ValueError("secret detail: password=hunter2")

    @track_service
    async def outer(self):
        return await self.load(1)  # nested tracked call


@track_service(name="pricing.calculate")
def calculate_price():
    return 10


@app.get("/_test/tracked")
async def tracked_route():
    service = DemoService()
    await service.load(1)
    service.compute()
    await service.load(2)
    return {"ok": True}


# ---- tests ----
def test_calls_in_a_request_are_numbered_in_order(client, calls):
    r = client.get("/_test/tracked", headers={HEADER: RID})
    assert r.status_code == 200
    assert [(c["call_order"], c["service_name"]) for c in calls] == [
        (1, "DemoService.load"),
        (2, "DemoService.compute"),
        (3, "DemoService.load"),
    ]
    assert {c["request_id"] for c in calls} == {uuid.UUID(RID)}
    assert all(c["status"] == "success" and c["error_type"] is None for c in calls)
    assert all(c["duration_ms"] >= 0 and c["started_on"].tzinfo for c in calls)


def test_each_request_restarts_the_order(client, calls):
    client.get("/_test/tracked")
    client.get("/_test/tracked")
    assert [c["call_order"] for c in calls] == [1, 2, 3, 1, 2, 3]


@pytest.mark.anyio
async def test_failure_is_recorded_and_reraised_unchanged(calls):
    with pytest.raises(ValueError, match="hunter2"):
        await DemoService().explode()
    (row,) = calls
    assert row["status"] == "failed" and row["error_type"] == "ValueError"
    assert "hunter2" not in str(row)  # no error message stored


@pytest.mark.anyio
async def test_names_sync_and_outside_request(calls):
    assert await DemoService().ping() == "pong"  # inherited method -> runtime class
    assert DemoService().compute() == 42
    assert calculate_price() == 10
    assert [c["service_name"] for c in calls] == [
        "DemoService.ping",
        "DemoService.compute",
        "pricing.calculate",
    ]
    assert all(c["request_id"] is None and c["call_order"] is None for c in calls)


@pytest.mark.anyio
async def test_nested_calls_are_each_recorded(calls):
    assert await DemoService().outer() == 2
    # outer starts first, load finishes first; rows arrive in finish order
    names = {c["service_name"] for c in calls}
    assert names == {"DemoService.outer", "DemoService.load"}


@pytest.mark.anyio
async def test_suppressed_calls_are_not_recorded(calls):
    with suppress_service_tracking():
        await DemoService().load(1)
    assert calls == []


@pytest.mark.anyio
async def test_no_tracking_when_sink_not_running():
    # Default sink is not started in tests: the call just runs.
    assert await DemoService().load(3) == 6


@pytest.mark.anyio
async def test_tracking_errors_never_break_the_call(monkeypatch):
    import app.core.logging.db_sink as db_sink

    class BrokenSink:
        running = True

        def enqueue(self, row):
            raise RuntimeError("queue exploded")

    monkeypatch.setattr(db_sink, "service_call_log_sink", BrokenSink())
    assert await DemoService().load(5) == 10


@pytest.mark.anyio
async def test_base_service_methods_are_tracked(calls, db_session_factory):
    from app.schemas.search import SearchRequest
    from app.services.request_log import RequestLogService

    async with db_session_factory() as session:
        service = RequestLogService(session)
        await service.search(SearchRequest(limit=1))
        await service.get(uuid.uuid4())
    assert [c["service_name"] for c in calls] == [
        "RequestLogService.search",
        "RequestLogService.get",
    ]


@pytest.mark.anyio
async def test_log_writers_do_not_track_themselves(calls, db_session_factory, monkeypatch):
    """Saving log rows goes through services; it must not create tracking rows."""
    import app.core.logging.db_sink as db_sink
    import app.db.session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", db_session_factory)
    from app.schemas.request_log import RequestLogCreate

    await db_sink._write_request_logs(
        [
            RequestLogCreate(
                started_on=datetime.now(UTC),
                id=uuid.uuid4(),
                method="GET",
                status_code=200,
                duration_ms=1.0,
            )
        ]
    )
    assert calls == []


# ---- API ----
URL = "/api/v1/service-call-logs"


@pytest.mark.anyio
async def test_api_search_a_requests_calls_in_order(api, db_session_factory):
    from app.schemas.service_call_log import ServiceCallLogCreate
    from app.services.service_call_log import ServiceCallLogService

    rid = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with db_session_factory() as session:
        await ServiceCallLogService(session).create_many(
            [
                ServiceCallLogCreate(
                    request_id=rid,
                    call_order=order,
                    service_name=name,
                    started_on=now,
                    duration_ms=ms,
                    status=status,
                    error_type=error,
                )
                for order, name, ms, status, error in [
                    (2, "OrderService.update", 30.0, "failed", "IntegrityError"),
                    (1, "OrderService.get", 4.0, "success", None),
                ]
            ]
        )

    r = await api.post(
        f"{URL}/search",
        json={
            "filters": [{"field": "request_id", "op": "eq", "value": rid}],
            "sort": [{"field": "call_order", "direction": "asc"}],
        },
    )
    assert r.status_code == 200
    records = r.json()["records"]
    assert [(x["call_order"], x["service_name"], x["status"]) for x in records] == [
        (1, "OrderService.get", "success"),
        (2, "OrderService.update", "failed"),
    ]
    detail = await api.get(f"{URL}/{records[1]['id']}")
    assert detail.json()["record"]["error_type"] == "IntegrityError"
    assert (await api.get(f"{URL}/{uuid.uuid4()}")).status_code == 404
