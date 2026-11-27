"""Authentication step 4: API clients (OAuth2 client credentials)."""

import base64
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token, principal_from_token
from app.core.security.permissions import Perm

pytestmark = pytest.mark.anyio
URL = "/api/v1/api-clients"
TOKEN_URL = "/api/v1/auth/token"


@pytest.fixture
def admin(api, admin_headers):
    return admin_headers


async def _create(api, headers, **body) -> dict:
    r = await api.post(URL, json={"name": "billing", **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["record"]


async def _service_token(api, client_id, secret):
    form = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret}
    return await api.post(TOKEN_URL, data=form)


def _bearer(r) -> dict[str, str]:
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_create_then_get_token_and_call_apis(api, admin):
    client = await _create(api, admin, permissions=[Perm.EXCEPTION_LOGS_READ])
    assert client["client_id"].startswith("cli_") and client["client_secret"]
    assert client["permissions"] == [Perm.EXCEPTION_LOGS_READ]

    detail = (await api.get(f"{URL}/{client['id']}", headers=admin)).json()["record"]
    assert "client_secret" not in detail and "secret_hash" not in detail

    r = await _service_token(api, client["client_id"], client["client_secret"])
    assert r.status_code == 200
    p = principal_from_token(r.json()["access_token"])
    assert (p.type, p.id, p.permissions) == ("service", client["client_id"], {"exception_logs:read"})

    api.headers.clear()
    assert (await api.get("/api/v1/exception-logs", headers=_bearer(r))).status_code == 200
    assert (await api.get("/api/v1/users", headers=_bearer(r))).status_code == 403
    assert (await api.get("/api/v1/auth/me", headers=_bearer(r))).status_code == 403  # users only

    detail = (await api.get(f"{URL}/{client['id']}", headers=admin)).json()["record"]
    assert detail["last_used_on"] is not None


async def test_http_basic_credentials(api, admin):
    client = await _create(api, admin)
    basic = base64.b64encode(f"{client['client_id']}:{client['client_secret']}".encode()).decode()
    r = await api.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {basic}"},
    )
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


async def test_bad_credentials_look_the_same(api, admin):
    client = await _create(api, admin)
    wrong = await _service_token(api, client["client_id"], "wrong-secret")
    unknown = await _service_token(api, "cli_unknown", "whatever")
    missing = await api.post(TOKEN_URL, data={"grant_type": "client_credentials"})
    for r in (wrong, unknown, missing):
        assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_client"


async def test_rotate_secret(api, admin):
    client = await _create(api, admin)
    r = await api.post(f"{URL}/{client['id']}/rotate-secret", headers=admin)
    new_secret = r.json()["record"]["client_secret"]
    assert new_secret != client["client_secret"]
    assert (await _service_token(api, client["client_id"], client["client_secret"])).status_code == 401
    assert (await _service_token(api, client["client_id"], new_secret)).status_code == 200


async def test_disabled_expired_or_deleted_clients_get_no_token(api, admin):
    client = await _create(api, admin)
    cid, secret = client["client_id"], client["client_secret"]

    await api.patch(f"{URL}/{client['id']}", json={"is_active": False}, headers=admin)
    assert (await _service_token(api, cid, secret)).status_code == 401

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    await api.patch(f"{URL}/{client['id']}", json={"is_active": True, "expires_on": past}, headers=admin)
    assert (await _service_token(api, cid, secret)).status_code == 401

    await api.patch(f"{URL}/{client['id']}", json={"expires_on": None}, headers=admin)
    assert (await _service_token(api, cid, secret)).status_code == 200
    assert (await api.delete(f"{URL}/{client['id']}", headers=admin)).status_code == 204
    assert (await _service_token(api, cid, secret)).status_code == 401


async def test_ip_allowlist(api, admin):
    # The test transport connects from 127.0.0.1.
    blocked = await _create(api, admin, allowed_ips=["10.0.0.0/8"])
    allowed = await _create(api, admin, allowed_ips=["127.0.0.1"])
    assert allowed["allowed_ips"] == ["127.0.0.1/32"]  # normalized
    assert (await _service_token(api, blocked["client_id"], blocked["client_secret"])).status_code == 401
    assert (await _service_token(api, allowed["client_id"], allowed["client_secret"])).status_code == 200

    r = await api.post(URL, json={"name": "x", "allowed_ips": ["not-an-ip"]}, headers=admin)
    assert r.status_code == 422


async def test_can_only_grant_own_permissions(api, admin):
    token, _ = create_access_token(
        subject="00000000-0000-7000-8000-0000000000b1",
        token_type="user",
        permissions=[Perm.API_CLIENTS_MANAGE],
    )
    manager = {"Authorization": f"Bearer {token}"}
    r = await api.post(
        URL, json={"name": "x", "permissions": [Perm.USERS_MANAGE]}, headers=manager
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "cannot_grant"

    client = await _create(api, admin)
    r = await api.put(
        f"{URL}/{client['id']}/permissions",
        json={"permissions": [Perm.REQUEST_LOGS_READ]},
        headers=admin,
    )
    assert r.json()["record"]["permissions"] == [Perm.REQUEST_LOGS_READ]
    r = await api.put(f"{URL}/{client['id']}/permissions", json={"permissions": []}, headers=manager)
    assert r.status_code == 403  # removing a permission you don't hold
