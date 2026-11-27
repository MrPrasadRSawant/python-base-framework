"""Developer report: request -> outcome -> failure reason -> per-service timing."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as Row

import pytest

from app.core.service_tracking import track_service
from app.services.request_report import build_report, summarize

T0 = datetime(2026, 11, 27, 10, 0, 0, tzinfo=UTC)


def _request(status=200, ms=100.0):
    return Row(
        id=uuid.uuid4(),
        started_on=T0,
        method="PATCH",
        route="/api/v1/orders/{order_id}",
        endpoint="orders.update_order",
        status_code=status,
        duration_ms=ms,
    )


def _call(order, name, ms, parent=None, start_ms=0.0, status="success", error=None):
    return Row(
        call_order=order,
        parent_call_order=parent,
        service_name=name,
        started_on=T0 + timedelta(milliseconds=start_ms),
        duration_ms=ms,
        status=status,
        error_type=error,
    )


def _exception(logger="app.exceptions", code="conflict", message="duplicate key"):
    return Row(
        id=uuid.uuid4(),
        logger=logger,
        error_code=code,
        exception_type="IntegrityError",
        message=message,
    )


# ---------------------------------------------------------------- pure maths
def test_nested_calls_get_depth_and_own_time():
    # update (60 ms) calls get (15 ms) and save (35 ms): update's own time is 10 ms
    report = build_report(
        _request(ms=100.0),
        [
            _call(1, "OrderService.update", 60.0, start_ms=5),
            _call(2, "OrderService.get", 15.0, parent=1, start_ms=6),
            _call(3, "OrderService.save", 35.0, parent=1, start_ms=22),
            _call(4, "AuditService.record", 20.0, start_ms=70),
        ],
        [],
    )
    steps = {s.service_name: s for s in report.services}
    assert [s.call_order for s in report.services] == [1, 2, 3, 4]
    assert steps["OrderService.update"].depth == 0 and steps["OrderService.get"].depth == 1
    assert steps["OrderService.update"].self_ms == 10.0
    assert steps["OrderService.save"].self_ms == 35.0
    assert steps["OrderService.update"].percent_of_request == 60.0
    assert steps["OrderService.save"].offset_ms == 22.0

    # slowest = highest OWN time, not the parent that contains it
    assert steps["OrderService.save"].is_slowest
    assert sum(s.is_slowest for s in report.services) == 1
    t = report.timing
    assert (t.slowest_service, t.slowest_service_ms) == ("OrderService.save", 35.0)
    # only top-level calls count toward time in services (no double counting)
    assert (t.in_services_ms, t.outside_services_ms) == (80.0, 20.0)
    assert (t.service_calls, t.failed_service_calls) == (4, 0)
    assert report.outcome == "succeeded" and report.failure is None


def test_failed_request_gets_reason_from_exception_log():
    report = build_report(
        _request(status=409, ms=40.0),
        [_call(1, "OrderService.update", 30.0, status="failed", error="IntegrityError")],
        [_exception(logger="app.jobs", code=None, message="other"), _exception()],
    )
    assert report.outcome == "failed"
    f = report.failure
    assert f.kind == "client_error" and f.error_code == "conflict"  # app.exceptions row preferred
    assert f.message == "duplicate key" and f.exception_type == "IntegrityError"
    assert report.timing.failed_service_calls == 1
    assert report.services[0].error_type == "IntegrityError"

    summary = summarize(report)
    assert summary.failure_reason == "conflict: duplicate key"
    assert summary.slowest_service == "OrderService.update"


def test_server_error_kind_and_request_without_services():
    report = build_report(
        _request(status=500, ms=12.0), [], [_exception(code="internal_server_error")]
    )
    assert report.failure.kind == "server_error"
    assert report.services == [] and report.timing.slowest_service is None
    assert report.timing.outside_services_ms == 12.0


def test_concurrent_calls_never_give_negative_outside_time():
    report = build_report(
        _request(ms=50.0), [_call(1, "A.x", 45.0), _call(2, "B.y", 45.0, start_ms=1)], []
    )
    assert report.timing.outside_services_ms == 0.0


# ------------------------------------------------------- parent tracking
class FakeRunningSink:
    running = True

    def __init__(self):
        self.rows = []

    def enqueue(self, row):
        self.rows.append(row.model_dump())


@pytest.fixture
def calls(monkeypatch):
    import app.core.logging.db_sink as db_sink

    sink = FakeRunningSink()
    monkeypatch.setattr(db_sink, "service_call_log_sink", sink)
    return sink.rows


class Demo:
    @track_service
    async def leaf(self):
        await asyncio.sleep(0)

    @track_service
    async def middle(self):
        await self.leaf()

    @track_service
    async def top(self):
        await self.middle()
        await asyncio.gather(self.leaf(), self.leaf())  # concurrent children


@pytest.mark.anyio
async def test_parent_call_order_is_recorded(calls):
    from app.core.request_context import reset_call_counter, start_call_counter

    token = start_call_counter()
    try:
        await Demo().top()
    finally:
        reset_call_counter(token)
    by_order = {c["call_order"]: c for c in calls}
    assert by_order[1]["service_name"] == "Demo.top" and by_order[1]["parent_call_order"] is None
    assert by_order[2]["service_name"] == "Demo.middle" and by_order[2]["parent_call_order"] == 1
    assert by_order[3]["service_name"] == "Demo.leaf" and by_order[3]["parent_call_order"] == 2
    # both concurrent leaves belong to top
    assert {by_order[4]["parent_call_order"], by_order[5]["parent_call_order"]} == {1}


# ------------------------------------------------------------- API (real DB)
URL = "/api/v1/requests"


@pytest.fixture
def seed_report(db_session_factory):
    async def _seed(tag: str, status: int, with_failure: bool) -> uuid.UUID:
        from app.models import ExceptionLog, RequestLog, ServiceCallLog

        rid = uuid.uuid4()
        now = datetime.now(UTC)
        rows = [
            RequestLog(
                id=rid,
                started_on=now,
                method="PATCH",
                route="/api/v1/orders/{order_id}",
                endpoint=tag,
                status_code=status,
                duration_ms=100.0,
            ),
            ServiceCallLog(
                request_id=rid, call_order=1, service_name="OrderService.update",
                started_on=now, duration_ms=60.0,
                status="failed" if with_failure else "success",
                error_type="IntegrityError" if with_failure else None,
            ),
            ServiceCallLog(
                request_id=rid, call_order=2, parent_call_order=1, service_name="OrderService.get",
                started_on=now + timedelta(milliseconds=2), duration_ms=50.0, status="success",
            ),
        ]  # fmt: skip
        if with_failure:
            rows.append(
                ExceptionLog(
                    occurred_on=now, level="WARNING", logger="app.exceptions",
                    request_id=rid, status_code=status, error_code="conflict",
                    exception_type="IntegrityError", message="duplicate key",
                )
            )  # fmt: skip
        async with db_session_factory() as session:
            session.add_all(rows)
            await session.commit()
        return rid

    return _seed


@pytest.mark.anyio
async def test_api_drill_down_report(api, seed_report):
    rid = await seed_report(f"t{uuid.uuid4().hex[:8]}", 409, with_failure=True)
    r = await api.get(f"{URL}/{rid}/report")
    assert r.status_code == 200
    report = r.json()["record"]
    assert report["request_id"] == str(rid)
    assert report["outcome"] == "failed"
    assert report["failure"]["error_code"] == "conflict"
    assert report["failure"]["message"] == "duplicate key"
    assert [(s["call_order"], s["depth"], s["self_ms"]) for s in report["services"]] == [
        (1, 0, 10.0),
        (2, 1, 50.0),
    ]
    assert report["timing"]["slowest_service"] == "OrderService.get"
    assert report["timing"]["outside_services_ms"] == 40.0
    assert r.json()["metadata"]["request_id"]  # the report call's own id

    missing = await api.get(f"{URL}/{uuid.uuid4()}/report")
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_api_report_list_with_filters(api, seed_report):
    tag = f"t{uuid.uuid4().hex[:8]}"
    ok = await seed_report(tag, 200, with_failure=False)
    failed = await seed_report(tag, 409, with_failure=True)
    mine = {"field": "endpoint", "op": "eq", "value": tag}

    r = await api.post(f"{URL}/report", json={"filters": [mine]})
    assert r.status_code == 200
    rows = {x["request_id"]: x for x in r.json()["records"]}
    assert set(rows) == {str(ok), str(failed)}
    assert rows[str(ok)]["outcome"] == "succeeded" and rows[str(ok)]["failure_reason"] is None
    assert rows[str(failed)]["failure_reason"] == "conflict: duplicate key"
    assert rows[str(failed)]["slowest_service"] == "OrderService.get"
    assert r.json()["metadata"]["total_count"] == 2

    only_failures = await api.post(
        f"{URL}/report",
        json={"filters": [mine, {"field": "status_code", "op": "gte", "value": 400}]},
    )
    assert [x["request_id"] for x in only_failures.json()["records"]] == [str(failed)]
