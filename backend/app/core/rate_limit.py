"""Rate limiting for sensitive endpoints (login, token, register, refresh).

    @router.post("/login", dependencies=[Depends(rate_limit("login", lambda: settings.RATE_LIMIT_LOGIN))])

    limiter.check("token:client:cli_abc", "60/minute")   # inside an endpoint

Rules are "<count>/<second|minute|hour>". Over the limit -> 429 with
``Retry-After``. Fixed window counter per key.

Storage is in memory, per process: limits apply per worker. With several
workers or servers, swap ``limiter`` for a shared backend (e.g. Redis) with
the same ``hit`` method.
"""

import logging
import math
import re
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import TooManyRequestsError

logger = logging.getLogger(__name__)

_PERIODS = {"second": 1, "minute": 60, "hour": 3600}
_RULE = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour)\s*$")


@lru_cache
def parse_rule(rule: str) -> tuple[int, int]:
    """ "10/minute" -> (10, 60)."""
    match = _RULE.match(rule)
    if not match or int(match.group(1)) < 1:
        raise ValueError(f"Invalid rate limit rule {rule!r}; use e.g. '10/minute'")
    return int(match.group(1)), _PERIODS[match.group(2)]


class InMemoryRateLimiter:
    def __init__(self, max_keys: int = 100_000) -> None:
        self._windows: dict[str, tuple[float, int]] = {}  # key -> (window start, count)
        self._max_keys = max_keys

    def hit(self, key: str, limit: int, window: int) -> float | None:
        """Count one hit. Returns seconds to wait if over the limit, else None."""
        now = time.monotonic()
        start, count = self._windows.get(key, (now, 0))
        if now - start >= window:
            start, count = now, 0
        if count >= limit:
            return window - (now - start)
        if len(self._windows) >= self._max_keys:
            self._prune(now, window)
        self._windows[key] = (start, count + 1)
        return None

    def _prune(self, now: float, window: int) -> None:
        expired = [k for k, (s, _) in self._windows.items() if now - s >= window]
        for k in expired:
            del self._windows[k]
        if len(self._windows) >= self._max_keys:  # still full: start over rather than grow
            self._windows.clear()

    def reset(self) -> None:
        self._windows.clear()

    def check(self, key: str, rule: str) -> None:
        """Raise 429 if ``key`` is over ``rule``. No-op when rate limiting is disabled."""
        if not settings.RATE_LIMIT_ENABLED:
            return
        retry_after = self.hit(key, *parse_rule(rule))
        if retry_after is not None:
            logger.warning("Rate limit exceeded", extra={"rate_limit_key": key, "rule": rule})
            raise TooManyRequestsError(
                error_code="rate_limited",
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )


limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, rule: Callable[[], str]) -> Callable[..., Awaitable[None]]:
    """Dependency: limit each client IP to ``rule()`` requests on this route.
    ``rule`` is a callable so the setting is read per request (tests can change it)."""

    async def dependency(request: Request) -> None:
        limiter.check(f"{scope}:ip:{client_ip(request)}", rule())

    return dependency
