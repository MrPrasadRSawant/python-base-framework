"""Authentication step 1: access tokens, middleware, route dependencies, login."""

from datetime import timedelta

import jwt
import pytest
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.request_context import get_current_actor
from app.core.security import (
    CurrentPrincipal,
    create_access_token,
    hash_password,
    principal_from_token,
    require_permission,
    verify_password,
)
from app.main import app

# ---- test-only routes ------------------------------------------------------
router = APIRouter(prefix="/_test_auth")


@router.get("/whoami")
async def whoami(principal: CurrentPrincipal):
    return {"id": principal.id, "type": principal.type, "actor": get_current_actor()}


@router.get("/needs-perm", dependencies=[Depends(require_permission("orders:read"))])
async def needs_perm():
    return {"ok": True}


@router.get("/public")
async def public():
    return {"actor": get_current_actor()}


app.include_router(router)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def user_token(user_id: str = "u-1", perms=()) -> str:
    return create_access_token(subject=user_id, token_type="user", permissions=perms)[0]


# ---- passwords / tokens ----------------------------------------------------
def test_password_hash_roundtrip():
    h = hash_password("correct horse battery")
    assert h.startswith("$argon2id$")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "not-a-hash")


def test_token_roundtrip():
    token, expires_in = create_access_token(
        subject="c-1", token_type="service", permissions={"b:read", "a:write"}
    )
    assert expires_in == settings.ACCESS_TOKEN_TTL_MINUTES * 60
    p = principal_from_token(token)
    assert (p.id, p.type, p.permissions) == ("c-1", "service", {"a:write", "b:read"})
    assert p.actor == "service:c-1"


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode({"sub": "x", "type": "user"}, "other-secret-key-that-is-long-enough!!", "HS256"),
        jwt.encode({"sub": "x", "type": "user"}, None, algorithm="none"),
        "not.a.jwt",
    ],
)
def test_bad_tokens_rejected(token):
    with pytest.raises(jwt.InvalidTokenError):
        principal_from_token(token)


# ---- middleware + dependencies --------------------------------------------
def test_no_token_is_401(client):
    r = client.get("/_test_auth/whoami")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_and_expired_tokens_are_401(client):
    r = client.get("/_test_auth/whoami", headers=bearer("garbage"))
    assert r.json()["error"]["code"] == "invalid_token"
    expired, _ = create_access_token(subject="u", token_type="user", ttl=timedelta(seconds=-1))
    r = client.get("/_test_auth/whoami", headers=bearer(expired))
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_expired"


def test_valid_token_sets_principal_and_actor(client):
    r = client.get("/_test_auth/whoami", headers=bearer(user_token("u-42")))
    assert r.json() == {"id": "u-42", "type": "user", "actor": "user:u-42"}


def test_public_route_works_with_bad_token(client):
    r = client.get("/_test_auth/public", headers=bearer("garbage"))
    assert r.status_code == 200 and r.json() == {"actor": "system"}


def test_require_permission(client):
    r = client.get("/_test_auth/needs-perm", headers=bearer(user_token()))
    assert r.status_code == 403
    assert r.json()["error"]["details"] == {"missing_permissions": ["orders:read"]}
    r = client.get("/_test_auth/needs-perm", headers=bearer(user_token(perms={"orders:read"})))
    assert r.status_code == 200


def test_service_token_cannot_use_user_routes(client):
    token, _ = create_access_token(subject="c-1", token_type="service")
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 403


def test_request_row_records_the_caller(client, request_rows):
    client.get("/_test_auth/public", headers=bearer(user_token("u-7")))
    assert request_rows[-1]["created_by"] == "user:u-7"


# ---- register / login / me (real DB) --------------------------------------
REGISTER = {"email": "Alice@Example.com", "full_name": "Alice", "password": "a-long-password-1"}


@pytest.mark.anyio
async def test_register_login_me(api):
    r = await api.post("/api/v1/auth/register", json=REGISTER)
    assert r.status_code == 201
    user = r.json()["record"]
    assert user["email"] == "alice@example.com" and "password_hash" not in user

    r = await api.post(
        "/api/v1/auth/login", json={"email": "ALICE@example.com", "password": REGISTER["password"]}
    )
    assert r.status_code == 200
    token = r.json()["record"]["access_token"]
    assert principal_from_token(token).id == user["id"]

    r = await api.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 200
    assert r.json()["record"]["last_login_on"] is not None


@pytest.mark.anyio
async def test_duplicate_email_is_409(api):
    await api.post("/api/v1/auth/register", json=REGISTER)
    r = await api.post("/api/v1/auth/register", json={**REGISTER, "email": "alice@EXAMPLE.com"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


@pytest.mark.anyio
async def test_login_failures_look_the_same_and_lock_the_account(api):
    await api.post("/api/v1/auth/register", json=REGISTER)
    wrong = {"email": REGISTER["email"], "password": "wrong-password"}
    unknown = await api.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"}
    )
    bad = await api.post("/api/v1/auth/login", json=wrong)
    assert unknown.status_code == bad.status_code == 401
    assert unknown.json()["error"] == bad.json()["error"]

    for _ in range(settings.LOGIN_MAX_FAILED - 1):
        await api.post("/api/v1/auth/login", json=wrong)
    # Locked now: even the right password fails.
    right = {"email": REGISTER["email"], "password": REGISTER["password"]}
    assert (await api.post("/api/v1/auth/login", json=right)).status_code == 401


# ---- refresh / logout (real DB) -------------------------------------------
COOKIE = settings.REFRESH_COOKIE_NAME
LOGIN = {"email": REGISTER["email"], "password": REGISTER["password"]}


async def _login(api) -> str:
    await api.post("/api/v1/auth/register", json=REGISTER)
    r = await api.post("/api/v1/auth/login", json=LOGIN)
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "path=/api/v1/auth" in set_cookie
    return r.cookies[COOKIE]


async def _refresh(api, token: str):
    api.cookies.clear()  # send exactly this token
    return await api.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={token}"})


@pytest.mark.anyio
async def test_refresh_rotates_the_token(api):
    first = await _login(api)
    r = await _refresh(api, first)
    assert r.status_code == 200
    second = r.cookies[COOKIE]
    assert second != first
    assert principal_from_token(r.json()["record"]["access_token"]).type == "user"
    assert (await _refresh(api, second)).status_code == 200


@pytest.mark.anyio
async def test_reusing_a_rotated_token_revokes_the_session(api):
    first = await _login(api)
    second = (await _refresh(api, first)).cookies[COOKIE]
    r = await _refresh(api, first)  # replay of a used token
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_refresh_token"
    assert (await _refresh(api, second)).status_code == 401  # whole family revoked


@pytest.mark.anyio
async def test_refresh_without_or_with_unknown_cookie(api):
    api.cookies.clear()
    assert (await api.post("/api/v1/auth/refresh")).status_code == 401
    assert (await _refresh(api, "unknown-token")).status_code == 401


@pytest.mark.anyio
async def test_logout_revokes_and_clears_cookie(api):
    token = await _login(api)
    api.cookies.clear()
    r = await api.post("/api/v1/auth/logout", headers={"Cookie": f"{COOKIE}={token}"})
    assert r.status_code == 204
    assert f'{COOKIE}=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()
    assert (await _refresh(api, token)).status_code == 401


# ---- Swagger / OAuth2 -------------------------------------------------------
def test_openapi_has_authorize_schemes(client):
    spec = client.get("/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    flows = schemes["OAuth2"]["flows"]
    assert flows["password"]["tokenUrl"] == flows["clientCredentials"]["tokenUrl"]
    assert flows["password"]["tokenUrl"] == "/api/v1/auth/token"
    assert schemes["BearerToken"]["scheme"] == "bearer"
    assert spec["paths"]["/api/v1/users"]["get"]["security"]  # lock icon
    assert "security" not in spec["paths"]["/api/v1/auth/login"]["post"]  # public


@pytest.mark.anyio
async def test_oauth2_password_grant(api):
    await api.post("/api/v1/auth/register", json=REGISTER)
    form = {"grant_type": "password", "username": "ALICE@example.com", "password": REGISTER["password"]}
    r = await api.post("/api/v1/auth/token", data=form)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and "metadata" not in body  # plain OAuth2 shape
    assert (await api.get("/api/v1/auth/me", headers=bearer(body["access_token"]))).status_code == 200

    r = await api.post("/api/v1/auth/token", data={**form, "password": "wrong"})
    assert r.status_code == 401
