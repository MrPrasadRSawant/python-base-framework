import asyncio
import logging

from app.core.config import settings
from app.models import ExceptionLog
from app.services.exception_log_sink import ExceptionLogSink

HEADER = settings.REQUEST_ID_HEADER


# ------------------------------------------------------------ handler -> row
def test_unhandled_exception_becomes_one_row(client, db_rows):
    client.get("/_test/boom", headers={HEADER: "trace-db-0001", "User-Agent": "pytest-ua"})
    assert len(db_rows) == 1
    row = db_rows[0]
    assert row["request_id"] == "trace-db-0001"
    assert row["status_code"] == 500
    assert row["error_code"] == "internal_server_error"
    assert row["exception_type"] == "RuntimeError"
    assert row["level"] == "ERROR"
    assert row["route"] == "/_test/boom"
    assert row["endpoint"].endswith(".boom")
    assert row["user_agent"] == "pytest-ua"
    assert row["created_by"] == "system"
    assert row["occurred_on"].tzinfo is not None
    assert "Traceback" in row["traceback"]
    assert "hunter2" not in row["traceback"] and "hunter2" not in row["message"]


def test_row_keys_match_table_columns(client, db_rows):
    client.get("/_test/boom")
    columns = set(ExceptionLog.__table__.columns.keys())
    assert set(db_rows[0]) <= columns


def test_client_errors_are_stored_without_traceback(client, db_rows):
    response = client.get("/_test/missing/9")
    row = db_rows[-1]
    assert row["status_code"] == 404
    assert row["error_code"] == "not_found"
    assert row["exception_type"] == "NotFoundError"
    assert row["traceback"] is None
    assert row["details"] == {"thing_id": 9}
    assert row["request_id"] == response.headers[HEADER]


def test_stored_request_data_is_redacted(client, db_rows):
    client.post(
        "/_test/login",
        json={"username": "bob", "password": "a-very-long-password"},
        headers={"Authorization": "Bearer abc.def.ghi"},
        params={"token": "qs-secret"},
    )
    row = db_rows[-1]
    assert row["request_body"]["content"]["password"] == "[REDACTED]"
    assert row["request_headers"]["authorization"] == "[REDACTED]"
    assert row["query_params"]["token"] == "[REDACTED]"
    assert "a-very-long-password" not in str(row)


def test_min_status_filters_client_errors(client, db_rows):
    from app.core.logging.db_handler import ExceptionLogDBHandler

    handler = next(h for h in logging.getLogger().handlers if isinstance(h, ExceptionLogDBHandler))
    handler.min_status = 500
    client.get("/_test/missing/1")
    client.get("/_test/boom")
    assert [r["status_code"] for r in db_rows] == [500]


def test_logger_exception_outside_handlers_is_stored(db_rows):
    log = logging.getLogger("app.jobs.nightly")
    try:
        raise ValueError("token=abc123 failed")
    except ValueError:
        log.exception("Nightly job failed")
    log.warning("just a warning")  # no traceback -> not stored
    assert len(db_rows) == 1
    assert db_rows[0]["logger"] == "app.jobs.nightly"
    assert db_rows[0]["status_code"] is None
    assert "abc123" not in db_rows[0]["traceback"]


def test_sink_failures_are_never_persisted(db_rows):
    logging.getLogger("app.exception_log_sink").error("db down", exc_info=RuntimeError("x"))
    assert db_rows == []


# -------------------------------------------------------------------- sink
def test_sink_batches_writes_and_flushes_on_stop():
    written: list[list[dict]] = []

    async def writer(rows):
        written.append(list(rows))

    async def scenario():
        sink = ExceptionLogSink(writer, batch_size=3, flush_interval=0.05)
        await sink.start()
        for i in range(7):
            sink.enqueue({"n": i})
        await sink.stop()
        return sink

    sink = asyncio.run(scenario())
    assert [r["n"] for batch in written for r in batch] == list(range(7))
    assert max(len(b) for b in written) <= 3
    assert sink.written == 7 and sink.dropped == 0


def test_sink_retries_rows_individually_and_never_raises():
    stored: list[dict] = []

    async def writer(rows):
        if any(r.get("bad") for r in rows):
            raise RuntimeError("insert failed")
        stored.extend(rows)

    async def scenario():
        sink = ExceptionLogSink(writer, batch_size=10, flush_interval=0.05)
        await sink.start()
        sink.enqueue({"n": 1})
        sink.enqueue({"n": 2, "bad": True})
        sink.enqueue({"n": 3})
        await sink.stop()
        return sink

    sink = asyncio.run(scenario())
    assert [r["n"] for r in stored] == [1, 3]
    assert sink.failed == 1 and sink.written == 2


def test_sink_drops_when_full_or_not_started():
    sink = ExceptionLogSink()
    sink.enqueue({"n": 1})  # not started
    assert sink.dropped == 1

    async def scenario():
        gate = asyncio.Event()

        async def slow_writer(rows):
            await gate.wait()

        s = ExceptionLogSink(slow_writer, max_queue=2, batch_size=1, flush_interval=0.01)
        await s.start()
        for i in range(10):
            s.enqueue({"n": i})
        gate.set()
        await s.stop()
        return s

    s = asyncio.run(scenario())
    assert s.dropped > 0


# ------------------------------------------------------------ common columns
def test_every_table_has_the_common_columns():
    from app.db.base import Base

    common = ["id", "created_by", "created_on", "updated_by", "updated_on", "is_deleted"]
    for table in Base.metadata.sorted_tables:
        cols = table.columns
        assert list(cols.keys())[0] == "id", table.name
        for name in common:
            assert name in cols, f"{table.name}.{name}"
        assert cols["id"].primary_key
        assert cols["created_on"].type.timezone and not cols["created_on"].nullable
        assert cols["updated_on"].nullable
        assert not cols["is_deleted"].nullable
