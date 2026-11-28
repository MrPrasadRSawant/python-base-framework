import io
import json
import logging
import os

# Must be set before the app (and its settings) are imported.
os.environ["LOG_TO_FILE"] = "false"
os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "test"
# Tests never touch the real DB; the exception_log handler is tested with a fake sink.
os.environ["EXCEPTION_LOG_DB_ENABLED"] = "false"
os.environ["REQUEST_LOG_DB_ENABLED"] = "false"
os.environ["SERVICE_CALL_LOG_DB_ENABLED"] = "false"
os.environ["EXCEPTION_LOG_API_ENABLED"] = "true"  # so their endpoints can be tested
os.environ["REQUEST_LOG_API_ENABLED"] = "true"
os.environ["SERVICE_CALL_LOG_API_ENABLED"] = "true"
# Capture + API on; rows go to the in-memory sink below (autouse), never the real DB.
os.environ["ENABLE_USER_ACTIVITY_LOG"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters"
os.environ["AUTH_SELF_REGISTRATION_ENABLED"] = "true"
os.environ["REFRESH_COOKIE_SECURE"] = "false"  # test client talks plain http
os.environ["RATE_LIMIT_ENABLED"] = "false"  # tests share one IP; test_rate_limit.py turns it on

import pytest  # noqa: E402
from fastapi import APIRouter  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app.core.exceptions import NotFoundError  # noqa: E402
from app.core.logging.filters import RequestIdFilter  # noqa: E402
from app.core.logging.formatters import JsonFormatter  # noqa: E402
from app.main import app  # noqa: E402

# ---- test-only routes that exercise each error path -----------------------
test_router = APIRouter(prefix="/_test")


class LoginIn(BaseModel):
    username: str
    password: str = Field(min_length=12)


@test_router.get("/boom")
async def boom():
    raise RuntimeError("connection failed for postgresql://app:hunter2@db/app")


@test_router.get("/missing/{thing_id}")
async def missing(thing_id: int):
    raise NotFoundError("Thing not found", details={"thing_id": thing_id})


@test_router.post("/login")
async def login(payload: LoginIn):
    raise RuntimeError(f"login exploded for {payload.username}")


app.include_router(test_router)


@pytest.fixture
def client():
    # Run the app's lifespan so its shutdown disposes the DB pool on the same
    # event loop that opened the connections (avoids asyncpg cross-loop warnings).
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def json_logs():
    """Capture logs exactly as the real JSON formatter writes them."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)

    def read() -> list[dict]:
        return [json.loads(line) for line in stream.getvalue().splitlines() if line]

    read.raw = stream.getvalue  # type: ignore[attr-defined]
    yield read
    root.removeHandler(handler)


class FakeSink:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def enqueue(self, row: dict) -> None:
        self.rows.append(row.model_dump())


class FakeActivitySink(FakeSink):
    """Stands in for user_activity_log_sink: always "running", keeps rows in memory."""

    name = "user_activity_logs"
    running = True

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


@pytest.fixture(autouse=True)
def activity_rows(monkeypatch):
    """Every test: activity tracking on, rows collected here instead of the database."""
    from app.core import activity_log
    from app.core.logging import db_sink

    activity_log.install_activity_tracking()
    sink = FakeActivitySink()
    monkeypatch.setattr(db_sink, "user_activity_log_sink", sink)
    return sink.rows


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session_factory():
    """Real-Postgres session factory inside one transaction that is rolled back.

    Endpoint commits become SAVEPOINT releases, so tests see their own writes
    but nothing survives the test. Skips when the database isn't reachable
    or migrations haven't been applied.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        conn = await engine.connect()
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"database not reachable: {exc}")
    has_tables = (
        await conn.execute(text("select to_regclass('exception_log') is not null"))
    ).scalar_one()
    if not has_tables:
        await conn.close()
        await engine.dispose()
        pytest.skip("tables missing; run `alembic upgrade head`")
    await conn.rollback()  # end the autobegun check transaction

    trans = await conn.begin()
    factory = async_sessionmaker(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield factory
    finally:
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
async def api(db_session_factory):
    """Async HTTP client for the app, with get_db bound to the rolled-back transaction."""
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_rows():
    """Attach the real ExceptionLogDBHandler with an in-memory sink."""
    from app.core.logging.db_handler import ExceptionLogDBHandler
    from app.core.redaction import get_redactor

    sink = FakeSink()
    handler = ExceptionLogDBHandler(sink, get_redactor(), min_status=400, environment="test")
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    yield sink.rows
    root.removeHandler(handler)


@pytest.fixture
def request_rows():
    """Attach the real RequestLogDBHandler with an in-memory sink."""
    from app.core.logging.db_handler import RequestLogDBHandler

    sink = FakeSink()
    handler = RequestLogDBHandler(sink, exclude_paths=["/api/v1/health"])
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.addHandler(handler)
    yield sink.rows
    root.removeHandler(handler)


# ---- authentication ---------------------------------------------------------
ADMIN_TEST_USER_ID = "00000000-0000-7000-8000-00000000a0a0"


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Bearer header for a user holding every permission in the catalog."""
    from app.core.security import create_access_token
    from app.core.security.permissions import Perm

    token, _ = create_access_token(
        subject=ADMIN_TEST_USER_ID, token_type="user", permissions=list(Perm)
    )
    return {"Authorization": f"Bearer {token}"}
