"""User activity log: data changes are captured on commit (never on rollback), with
before/after values and sensitive values redacted; security events are recorded;
the read API is protected by user_activity_logs:read.

Capture tests run against the real database inside a rolled-back transaction;
activity rows go to the in-memory sink from conftest (``activity_rows``).
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.activity_log import Activity, record_activity
from app.core.redaction import REDACTED
from app.core.security import create_access_token, hash_password
from app.core.security.permissions import ADMIN_ROLE, Perm
from app.models import (
    ExceptionLog,
    RefreshToken,
    RequestLog,
    Role,
    ServiceCallLog,
    User,
    UserActivityLog,
    UserRole,
)
from app.schemas.user import UserCreate
from app.schemas.user_activity_log import UserActivityLogCreate
from app.services.role import RoleService
from app.services.user import UserService
from app.services.user_activity_log import UserActivityLogService
from app.services.user_role import UserRoleService

pytestmark = pytest.mark.anyio
PASSWORD = "a-long-password-1"
API = "/api/v1/user-activity-logs"


def _token(subject: str, *perms: str) -> dict[str, str]:
    token, _ = create_access_token(subject=subject, token_type="user", permissions=list(perms))
    return {"Authorization": f"Bearer {token}"}


def _of(rows, action, entity_type=None):
    return [
        r
        for r in rows
        if r["action"] == action and (entity_type is None or r["entity_type"] == entity_type)
    ]


async def _make_user(factory, email: str, *roles: str) -> User:
    async with factory() as db:
        user = await UserService(db).create(
            UserCreate(
                username=email.split("@", 1)[0],
                email=email,
                full_name=email,
                password_hash=hash_password(PASSWORD),
            )
        )
        found = await RoleService(db).get_by_codes(roles)
        await UserRoleService(db).replace_for_user(user.id, [r.id for r in found])
        return user


@pytest.fixture
async def admin(db_session_factory, activity_rows):
    """A real admin user + their bearer header; setup rows are cleared."""
    user = await _make_user(db_session_factory, "auditor@example.com", ADMIN_ROLE)
    headers = _token(str(user.id), *Perm)
    activity_rows.clear()
    return user, headers


# ---- configuration -----------------------------------------------------------
def test_log_tables_and_tokens_are_not_audited():
    for model in (UserActivityLog, ExceptionLog, RequestLog, ServiceCallLog, RefreshToken):
        assert model.__activity_log__ is False, model.__name__
    assert getattr(User, "__activity_log__", True) is True
    assert {"last_login_on", "failed_login_count"} <= User.__activity_log_ignore__


def test_permission_is_in_the_catalog():
    assert Perm.USER_ACTIVITY_LOGS_READ == "user_activity_logs:read"


# ---- data changes ------------------------------------------------------------
async def test_create_update_soft_delete_through_the_api(api, admin, activity_rows):
    admin_user, headers = admin
    actor = f"user:{admin_user.id}"

    r = await api.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "dana",
            "email": "dana@example.com",
            "full_name": "Dana",
            "password": PASSWORD,
            "roles": [ADMIN_ROLE],
        },
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["record"]["id"]

    [created] = _of(activity_rows, "create", "users")
    assert created["entity_id"] == user_id
    assert created["actor"] == actor and created["actor_type"] == "user"
    assert created["actor_id"] == str(admin_user.id)
    assert created["status"] == "success"
    assert created["changes"]["username"] == {"old": None, "new": "dana"}
    assert created["changes"]["password_hash"] == {"old": None, "new": REDACTED}
    assert "created_by" not in created["changes"]  # audit columns are not repeated
    assert created["method"] == "POST" and created["route"] == "/api/v1/users"
    assert created["request_id"] == uuid.UUID(r.headers["X-Request-ID"])
    assert created["ip_address"] == "127.0.0.1"
    [grant] = _of(activity_rows, "create", "user_roles")
    assert grant["changes"]["user_id"]["new"] == user_id

    activity_rows.clear()
    r = await api.patch(f"/api/v1/users/{user_id}", headers=headers, json={"full_name": "Dana S"})
    assert r.status_code == 200, r.text
    [updated] = activity_rows
    assert updated["action"] == "update" and updated["entity_id"] == user_id
    assert updated["changes"] == {"full_name": {"old": "Dana", "new": "Dana S"}}
    assert updated["route"] == "/api/v1/users/{user_id}"

    activity_rows.clear()
    r = await api.delete(f"/api/v1/users/{user_id}", headers=headers)
    assert r.status_code == 204
    [deleted] = _of(activity_rows, "delete", "users")
    assert deleted["changes"] == {"is_deleted": {"old": False, "new": True}}


async def test_replacing_roles_records_only_the_difference(
    api, admin, db_session_factory, activity_rows
):
    _, headers = admin
    async with db_session_factory() as db:
        db.add(Role(code="auditor", name="Auditor"))
        await db.commit()
    user = await _make_user(db_session_factory, "eve@example.com", ADMIN_ROLE)
    activity_rows.clear()

    url = f"/api/v1/users/{user.id}/roles"
    r = await api.put(url, headers=headers, json={"roles": [ADMIN_ROLE]})  # unchanged
    assert r.status_code == 200, r.text
    assert _of(activity_rows, "create", "user_roles") == []
    assert _of(activity_rows, "delete", "user_roles") == []

    r = await api.put(url, headers=headers, json={"roles": ["auditor"]})
    assert r.status_code == 200, r.text
    assert len(_of(activity_rows, "create", "user_roles")) == 1
    [revoked] = _of(activity_rows, "delete", "user_roles")
    assert revoked["changes"]["user_id"] == {"old": str(user.id), "new": None}


async def test_rolled_back_changes_are_never_recorded(db_session_factory, activity_rows):
    async with db_session_factory() as db:
        db.add(Role(code="ghost", name="Ghost"))
        await db.flush()  # captured as pending...
        await db.rollback()  # ...and dropped
    assert activity_rows == []

    async with db_session_factory() as db:
        db.add(Role(code="kept", name="Kept"))
        await db.commit()
    [row] = activity_rows
    assert row["action"] == "create" and row["entity_type"] == "roles"
    assert row["actor"] == "system" and row["request_id"] is None  # outside a request


async def test_bulk_delete_statements_are_captured(db_session_factory, activity_rows):
    """RoleService.delete removes grants with a bulk DELETE, which skips the ORM flush."""
    async with db_session_factory() as db:
        role = Role(code="temp_role", name="Temp")
        db.add(role)
        await db.commit()
    user = await _make_user(db_session_factory, "frank@example.com", "temp_role")
    activity_rows.clear()

    async with db_session_factory() as db:
        assert await RoleService(db).delete(role.id)
    [grant] = _of(activity_rows, "delete", "user_roles")
    assert grant["changes"]["user_id"]["old"] == str(user.id)
    [soft] = _of(activity_rows, "delete", "roles")
    assert soft["entity_id"] == str(role.id)
    async with db_session_factory() as db:
        left = await db.scalars(select(UserRole).where(UserRole.role_id == role.id))
        assert left.all() == []


async def test_bulk_update_statements_record_before_and_after(db_session_factory, activity_rows):
    from sqlalchemy import update

    user = await _make_user(db_session_factory, "gina@example.com")
    activity_rows.clear()
    async with db_session_factory() as db:
        await db.execute(update(User).where(User.id == user.id).values(full_name="Gina B"))
        await db.commit()
    [row] = activity_rows
    assert row["action"] == "update" and row["entity_id"] == str(user.id)
    assert row["changes"]["full_name"] == {"old": "gina@example.com", "new": "Gina B"}


async def test_nothing_is_recorded_while_the_feature_is_off(
    db_session_factory, activity_rows, monkeypatch
):
    from app.core.logging import db_sink

    monkeypatch.setattr(db_sink.user_activity_log_sink, "running", False)
    async with db_session_factory() as db:
        db.add(Role(code="quiet", name="Quiet"))
        await db.commit()
    record_activity(Activity.LOGIN)
    assert activity_rows == []


# ---- security events ---------------------------------------------------------
async def test_sign_in_events(api, db_session_factory, activity_rows):
    user = await _make_user(db_session_factory, "hank@example.com")
    activity_rows.clear()
    login = "/api/v1/auth/login"

    r = await api.post(login, json={"identifier": "hank", "password": "wrong-password-1"})
    assert r.status_code == 401
    r = await api.post(login, json={"identifier": "nobody", "password": PASSWORD})
    assert r.status_code == 401
    r = await api.post(login, json={"identifier": "hank", "password": PASSWORD})
    assert r.status_code == 200, r.text

    wrong, unknown = _of(activity_rows, "login_failed")
    assert wrong["status"] == "failed" and wrong["entity_id"] == str(user.id)
    assert wrong["details"] == {"reason": "wrong_password", "locked_out": False}
    assert wrong["actor"] == "anonymous" and wrong["route"] == login
    assert unknown["details"] == {"reason": "unknown_account"}
    assert "nobody" not in str(unknown)  # the typed identifier is never stored
    [ok] = _of(activity_rows, "login")
    assert ok["actor"] == f"user:{user.id}" and ok["entity_id"] == str(user.id)
    # Sign-in bookkeeping (failed_login_count, last_login_on) is not a "users" update.
    assert _of(activity_rows, "update", "users") == []

    activity_rows.clear()
    r = await api.post("/api/v1/auth/logout")
    assert r.status_code == 204
    [out] = _of(activity_rows, "logout")
    assert out["actor"] == f"user:{user.id}"


async def test_lockout_is_flagged(api, db_session_factory, activity_rows, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "LOGIN_MAX_FAILED", 2)
    await _make_user(db_session_factory, "ivy@example.com")
    activity_rows.clear()
    for _ in range(3):
        await api.post(
            "/api/v1/auth/login", json={"identifier": "ivy", "password": "wrong-password-1"}
        )
    reasons = [(r["details"]["reason"], r["details"].get("locked_out")) for r in activity_rows]
    assert reasons == [
        ("wrong_password", False),
        ("wrong_password", True),
        ("account_locked", None),
    ]


async def test_access_denied_is_recorded(client, activity_rows):
    headers = _token(str(uuid.uuid4()))  # signed in, no permissions
    r = client.get("/api/v1/users", headers=headers)
    assert r.status_code == 403
    [row] = activity_rows
    assert row["action"] == "access_denied" and row["status"] == "failed"
    assert row["actor_type"] == "user" and row["route"] == "/api/v1/users"
    assert row["details"] == {"error_code": "forbidden", "missing_permissions": ["users:read"]}


def test_record_activity_never_raises(activity_rows, monkeypatch):
    from app.core import activity_log

    def broken(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(activity_log, "_build_row", broken)
    record_activity(Activity.LOGIN)  # no exception
    assert activity_rows == []


# ---- read API ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", API),
        ("POST", f"{API}/search"),
        ("GET", f"{API}/{uuid.uuid4()}"),
        ("GET", f"{API}/entities/users/{uuid.uuid4()}"),
    ],
)
def test_api_needs_the_permission(client, method, path):
    assert client.request(method, path, json={}).status_code == 401
    headers = _token(str(uuid.uuid4()), Perm.USERS_READ)
    r = client.request(method, path, json={}, headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["details"]["missing_permissions"] == ["user_activity_logs:read"]


async def _seed(factory, **overrides) -> None:
    base = {
        "occurred_on": datetime.now(UTC),
        "actor": "user:alice",
        "actor_type": "user",
        "actor_id": "alice",
        "action": "update",
        "entity_type": "orders",
        "entity_id": "42",
        "changes": {"total": {"old": 1, "new": 2}},
    }
    async with factory() as db:
        await UserActivityLogService(db).create_many([UserActivityLogCreate(**base | overrides)])


async def test_search_history_and_detail(api, db_session_factory, admin_headers):
    await _seed(db_session_factory)
    await _seed(db_session_factory, actor="user:bob", actor_id="bob", entity_id="43")
    await _seed(db_session_factory, action="login_failed", status="failed", entity_id="44")

    body = {
        "filters": [
            {"field": "actor_id", "value": "alice"},
            {"field": "action", "value": "update"},
        ]
    }
    r = await api.post(f"{API}/search", json=body, headers=admin_headers)
    assert r.status_code == 200, r.text
    records = [x for x in r.json()["records"] if x["entity_type"] == "orders"]
    assert [x["entity_id"] for x in records] == ["42"]
    assert records[0]["changes"] == {"total": {"old": 1, "new": 2}}

    # Scoped to the seeded "orders" rows: the shared dev database may hold real ones.
    failed = {
        "filters": [
            {"field": "status", "value": "failed"},
            {"field": "entity_type", "value": "orders"},
        ]
    }
    r = await api.post(f"{API}/search", json=failed, headers=admin_headers)
    assert [(x["action"], x["entity_id"]) for x in r.json()["records"]] == [("login_failed", "44")]

    r = await api.get(f"{API}/entities/orders/43", headers=admin_headers)
    assert r.status_code == 200
    [history] = r.json()["records"]
    assert history["actor"] == "user:bob"

    r = await api.get(f"{API}/{history['id']}", headers=admin_headers)
    assert r.status_code == 200 and r.json()["record"]["entity_id"] == "43"
    r = await api.get(f"{API}/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404


async def test_bad_filter_field_is_rejected(api, admin_headers):
    body = {"filters": [{"field": "user_agent", "value": "x"}]}
    r = await api.post(f"{API}/search", json=body, headers=admin_headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_filter"


async def test_sink_writer_persists_rows(db_session_factory):
    """The background writer saves through UserActivityLogService.create_many."""
    await _seed(db_session_factory, entity_id="written")
    async with db_session_factory() as db:
        row = await db.scalar(
            select(UserActivityLog).where(UserActivityLog.entity_id == "written")
        )
    assert row is not None and row.changes == {"total": {"old": 1, "new": 2}}
