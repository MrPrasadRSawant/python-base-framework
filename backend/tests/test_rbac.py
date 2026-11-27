"""Authentication step 3: roles, permissions, tokens with permissions, admin APIs."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password, principal_from_token
from app.core.security.permissions import ADMIN_ROLE, DESCRIPTIONS, Perm
from app.db.mixins import utc_now
from app.models import Permission
from app.schemas.user import UserCreate
from app.services.permission import PermissionService
from app.services.role import RoleService
from app.services.user import UserService
from app.services.user_role import UserRoleService

pytestmark = pytest.mark.anyio
PASSWORD = "a-long-password-1"


def test_every_permission_has_a_description():
    assert set(DESCRIPTIONS) == set(Perm)


async def _make_user(factory, email: str, *roles: str) -> None:
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


async def _token(api, email: str) -> dict[str, str]:
    r = await api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['record']['access_token']}"}


@pytest.fixture
async def admin(api, db_session_factory):
    await _make_user(db_session_factory, "root@example.com", ADMIN_ROLE)
    return await _token(api, "root@example.com")


# ---- catalog ---------------------------------------------------------------
async def test_db_catalog_matches_code_and_admin_has_everything(db_session_factory):
    async with db_session_factory() as db:
        codes = set((await db.scalars(select(Permission.code))).all())
        admin = await RoleService(db).get_by_code(ADMIN_ROLE)
        admin_codes = set(await PermissionService(db).codes_for_roles([admin.id]))
        developer = await RoleService(db).get_by_code("developer")
        developer_codes = set(await PermissionService(db).codes_for_roles([developer.id]))
    assert codes == set(Perm), "add a migration for new/removed permissions"
    assert admin.is_system and admin_codes == set(Perm)
    assert developer_codes == {
        Perm.EXCEPTION_LOGS_READ,
        Perm.REQUEST_LOGS_READ,
        Perm.SERVICE_CALL_LOGS_READ,
        Perm.ROLES_READ,
        Perm.ROLES_MANAGE,
    }


# ---- tokens + protection ---------------------------------------------------
async def test_login_token_carries_role_permissions(api, admin):
    token = admin["Authorization"].split()[1]
    assert principal_from_token(token).permissions == set(Perm)
    me = (await api.get("/api/v1/auth/me", headers=admin)).json()["record"]
    assert me["roles"] == [ADMIN_ROLE] and set(me["permissions"]) == set(Perm)


async def test_log_and_admin_apis_need_permissions(api, db_session_factory):
    assert (await api.get("/api/v1/exception-logs")).status_code == 401
    await _make_user(db_session_factory, "plain@example.com")
    plain = await _token(api, "plain@example.com")
    for url in ("/api/v1/exception-logs", "/api/v1/requests", "/api/v1/users", "/api/v1/roles"):
        assert (await api.get(url, headers=plain)).status_code == 403, url


# ---- users -----------------------------------------------------------------
async def test_admin_creates_user_with_roles_and_changes_them(api, admin):
    body = {"username": "bob", "email": "bob@example.com", "full_name": "Bob", "password": PASSWORD, "roles": []}
    r = await api.post("/api/v1/users", json=body, headers=admin)
    assert r.status_code == 201
    user_id = r.json()["record"]["id"]

    r = await api.put(f"/api/v1/users/{user_id}/roles", json={"roles": ["nope"]}, headers=admin)
    assert r.status_code == 422 and r.json()["error"]["details"] == {"unknown_roles": ["nope"]}

    r = await api.put(
        f"/api/v1/users/{user_id}/roles", json={"roles": [ADMIN_ROLE]}, headers=admin
    )
    assert r.status_code == 200 and r.json()["record"]["roles"] == [ADMIN_ROLE]
    bob = await _token(api, "bob@example.com")
    assert (await api.get("/api/v1/users", headers=bob)).status_code == 200


async def test_admin_usernames_are_unique_and_can_be_changed(api, admin):
    body = {
        "username": "Sam",
        "email": "sam-one@example.com",
        "full_name": "Sam One",
        "password": PASSWORD,
    }
    first = await api.post("/api/v1/users", json=body, headers=admin)
    assert first.status_code == 201
    second = await api.post(
        "/api/v1/users",
        json={**body, "username": "SamTwo", "email": "sam-two@example.com"},
        headers=admin,
    )
    assert second.status_code == 201
    duplicate = await api.patch(
        f"/api/v1/users/{second.json()['record']['id']}",
        json={"username": "sAM"},
        headers=admin,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "username_taken"
    renamed = await api.patch(
        f"/api/v1/users/{first.json()['record']['id']}",
        json={"username": "SamRenamed"},
        headers=admin,
    )
    assert renamed.status_code == 200
    assert renamed.json()["record"]["username"] == "SamRenamed"


async def test_cannot_change_own_account(api, admin):
    me = (await api.get("/api/v1/auth/me", headers=admin)).json()["record"]
    r = await api.put(f"/api/v1/users/{me['id']}/roles", json={"roles": []}, headers=admin)
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_change"
    assert (await api.delete(f"/api/v1/users/{me['id']}", headers=admin)).status_code == 403
    r = await api.put(
        f"/api/v1/users/{me['id']}/lock", json={"locked": True}, headers=admin
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_change"


async def test_disabling_a_user_ends_their_session(api, admin, db_session_factory):
    await _make_user(db_session_factory, "carol@example.com")
    r = await api.post("/api/v1/auth/login", json={"email": "carol@example.com", "password": PASSWORD})
    refresh_cookie = r.cookies[settings.REFRESH_COOKIE_NAME]
    user_id = principal_from_token(r.json()["record"]["access_token"]).id

    r = await api.patch(f"/api/v1/users/{user_id}", json={"is_active": False}, headers=admin)
    assert r.status_code == 200 and r.json()["record"]["is_active"] is False
    listed = await api.post(
        "/api/v1/users/search",
        json={"filters": [{"field": "is_active", "value": False}]},
        headers=admin,
    )
    assert user_id in {row["id"] for row in listed.json()["records"]}
    api.cookies.clear()
    r = await api.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{settings.REFRESH_COOKIE_NAME}={refresh_cookie}"},
    )
    assert r.status_code == 401


async def test_admin_lock_is_distinct_from_disable_and_unlock_restores_login(
    api, admin, db_session_factory
):
    await _make_user(db_session_factory, "locked@example.com")
    r = await api.post(
        "/api/v1/auth/login", json={"email": "locked@example.com", "password": PASSWORD}
    )
    refresh_cookie = r.cookies[settings.REFRESH_COOKIE_NAME]
    user_id = principal_from_token(r.json()["record"]["access_token"]).id

    r = await api.put(
        f"/api/v1/users/{user_id}/lock", json={"locked": True}, headers=admin
    )
    assert r.status_code == 200
    assert r.json()["record"]["is_locked"] is True
    assert r.json()["record"]["is_active"] is True
    listed = await api.post(
        "/api/v1/users/search",
        json={"filters": [{"field": "is_locked", "value": True}]},
        headers=admin,
    )
    assert user_id in {row["id"] for row in listed.json()["records"]}
    api.cookies.clear()
    r = await api.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{settings.REFRESH_COOKIE_NAME}={refresh_cookie}"},
    )
    assert r.status_code == 401
    r = await api.post(
        "/api/v1/auth/login", json={"email": "locked@example.com", "password": PASSWORD}
    )
    assert r.status_code == 401

    async with db_session_factory() as db:
        user = await UserService(db).get(user_id)
        user.locked_until = utc_now() + timedelta(minutes=5)
        user.failed_login_count = 2
        await db.commit()

    r = await api.put(
        f"/api/v1/users/{user_id}/lock", json={"locked": False}, headers=admin
    )
    assert r.status_code == 200
    assert r.json()["record"]["is_locked"] is False
    assert r.json()["record"]["locked_until"] is None
    r = await api.post(
        "/api/v1/auth/login", json={"email": "locked@example.com", "password": PASSWORD}
    )
    assert r.status_code == 200


async def test_no_privilege_escalation(api, admin, db_session_factory):
    # A user manager (users:read + users:manage) ...
    r = await api.post(
        "/api/v1/roles", json={"code": "user_manager", "name": "User manager"}, headers=admin
    )
    role_id = r.json()["record"]["id"]
    r = await api.put(
        f"/api/v1/roles/{role_id}/permissions",
        json={"permissions": [Perm.USERS_READ, Perm.USERS_MANAGE]},
        headers=admin,
    )
    assert r.status_code == 200
    await _make_user(db_session_factory, "mgr@example.com", "user_manager")
    mgr = await _token(api, "mgr@example.com")

    # ... cannot hand out admin,
    body = {"username": "x_user", "email": "x@example.com", "full_name": "X", "password": PASSWORD, "roles": ["admin"]}
    r = await api.post("/api/v1/users", json=body, headers=mgr)
    assert r.status_code == 403 and r.json()["error"]["code"] == "cannot_grant"
    # ... and cannot disable an admin.
    root_id = (await api.get("/api/v1/auth/me", headers=admin)).json()["record"]["id"]
    r = await api.patch(f"/api/v1/users/{root_id}", json={"is_active": False}, headers=mgr)
    assert r.status_code == 403
    r = await api.put(
        f"/api/v1/users/{root_id}/lock", json={"locked": True}, headers=mgr
    )
    assert r.status_code == 403


# ---- roles -----------------------------------------------------------------
async def test_system_role_is_protected(api, admin):
    roles = (await api.post("/api/v1/roles/search", json={}, headers=admin)).json()["records"]
    admin_id = next(r["id"] for r in roles if r["code"] == ADMIN_ROLE)
    assert (await api.delete(f"/api/v1/roles/{admin_id}", headers=admin)).status_code == 403
    r = await api.put(
        f"/api/v1/roles/{admin_id}/permissions", json={"permissions": []}, headers=admin
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "system_role"


async def test_deleted_role_no_longer_grants_permissions(api, admin, db_session_factory):
    r = await api.post("/api/v1/roles", json={"code": "auditor", "name": "Auditor"}, headers=admin)
    role_id = r.json()["record"]["id"]
    await api.put(
        f"/api/v1/roles/{role_id}/permissions",
        json={"permissions": [Perm.EXCEPTION_LOGS_READ]},
        headers=admin,
    )
    await _make_user(db_session_factory, "aud@example.com", "auditor")
    aud = await _token(api, "aud@example.com")
    assert principal_from_token(aud["Authorization"].split()[1]).permissions == {
        Perm.EXCEPTION_LOGS_READ
    }

    assert (await api.delete(f"/api/v1/roles/{role_id}", headers=admin)).status_code == 204
    aud = await _token(api, "aud@example.com")
    assert principal_from_token(aud["Authorization"].split()[1]).permissions == set()


async def test_permission_catalog_endpoint(api, admin):
    r = await api.get("/api/v1/permissions", headers=admin)
    assert [p["code"] for p in r.json()["records"]] == sorted(Perm)
