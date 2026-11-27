"""Authentication step 5: rate limiting (no database needed)."""

import pytest

from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimiter, limiter, parse_rule


@pytest.fixture
def limits(monkeypatch):
    """Turn rate limiting on with small limits; fresh counters per test."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "2/minute")
    monkeypatch.setattr(settings, "RATE_LIMIT_TOKEN_PER_CLIENT", "2/minute")
    limiter.reset()
    yield
    limiter.reset()


def test_parse_rule():
    assert parse_rule("10/minute") == (10, 60)
    assert parse_rule(" 3 / hour ") == (3, 3600)
    for bad in ("10", "0/minute", "5/day", "x/second"):
        with pytest.raises(ValueError):
            parse_rule(bad)


def test_fixed_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: now[0])
    rl = InMemoryRateLimiter()
    assert rl.hit("k", 2, 60) is None
    assert rl.hit("k", 2, 60) is None
    assert rl.hit("k", 2, 60) == 60  # wait a full window
    assert rl.hit("other", 2, 60) is None  # keys are independent
    now[0] += 60
    assert rl.hit("k", 2, 60) is None  # new window


def test_login_is_limited_per_ip(client, limits):
    codes = [client.post("/api/v1/auth/login", json={}).status_code for _ in range(3)]
    assert codes == [422, 422, 429]
    r = client.post("/api/v1/auth/login", json={})
    assert r.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(r.headers["Retry-After"]) <= 60


def test_password_grant_shares_the_login_limit(client, limits):
    client.post("/api/v1/auth/login", json={})
    client.post("/api/v1/auth/login", json={})
    r = client.post("/api/v1/auth/token", data={"grant_type": "password"})
    assert r.status_code == 429


def test_client_credentials_limited_per_client_id(client, limits):
    form = {"grant_type": "client_credentials", "client_id": "cli_x"}  # no secret: 401, no DB
    codes = [client.post("/api/v1/auth/token", data=form).status_code for _ in range(3)]
    assert codes == [401, 401, 429]
    other = {**form, "client_id": "cli_y"}
    assert client.post("/api/v1/auth/token", data=other).status_code == 401


def test_disabled_means_unlimited(client):
    assert not settings.RATE_LIMIT_ENABLED
    assert all(client.post("/api/v1/auth/login", json={}).status_code == 422 for _ in range(15))
