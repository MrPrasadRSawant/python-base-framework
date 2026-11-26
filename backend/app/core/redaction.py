"""Masking of sensitive data before it reaches any log sink.

Two strategies are combined:

* key-based     - values stored under sensitive keys (dicts, headers, query
                  params, request bodies) are replaced with ``[REDACTED]``.
* pattern-based - free text (log messages, exception messages, tracebacks) is
                  scanned for auth tokens, JWTs, credentials in URLs,
                  ``key=value`` secrets, card numbers and email addresses.
"""

import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any

REDACTED = "[REDACTED]"
_MAX_DEPTH = 10

# Exact (normalized) key names that are always sensitive.
DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password", "passwd", "pwd", "pass", "new_password", "old_password",
        "secret", "client_secret", "token", "access_token", "refresh_token",
        "id_token", "api_key", "apikey", "x_api_key", "authorization",
        "proxy_authorization", "cookie", "set_cookie", "session", "sessionid",
        "csrf", "csrf_token", "x_csrf_token", "private_key", "credit_card",
        "card_number", "cvv", "cvc", "ssn", "pin", "otp",
    }
)  # fmt: skip

# Any key *containing* one of these fragments is also sensitive.
DEFAULT_SENSITIVE_FRAGMENTS: tuple[str, ...] = (
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "credential", "private_key",
)  # fmt: skip

_KV_KEY_FRAGMENT = r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|credential)"


def _normalize(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _luhn_valid(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_card(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if 13 <= len(digits) <= 19 and _luhn_valid(digits):
        return f"{REDACTED}-{digits[-4:]}"
    return raw  # not a real card number (e.g. an id or timestamp)


class Redactor:
    def __init__(self, extra_keys: Iterable[str] = (), redact_emails: bool = True) -> None:
        extra = {_normalize(k) for k in extra_keys}
        self.sensitive_keys = DEFAULT_SENSITIVE_KEYS | extra
        self.sensitive_fragments = DEFAULT_SENSITIVE_FRAGMENTS + tuple(sorted(extra))
        self.redact_emails = redact_emails

        self._patterns: list[tuple[re.Pattern[str], Any]] = [
            # scheme://user:password@host -> keep user, hide password
            (
                re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^:/\s@]+:)([^@\s/]+)(@)"),
                rf"\1{REDACTED}\3",
            ),
            # Authorization header schemes
            (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9\-._~+/]+=*"), rf"\1 {REDACTED}"),
            # JWTs anywhere in text
            (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), REDACTED),
            # password=..., "api_key": "...", 'token': '...'
            (
                re.compile(
                    rf"(?i)([\"']?[\w-]*{_KV_KEY_FRAGMENT}[\w-]*[\"']?\s*[:=]\s*)"
                    rf"([\"']?)([^\"'\s,&;}}\]]+)"
                ),
                rf"\1\2{REDACTED}",
            ),
            # Card-like numbers, Luhn-validated
            (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), _mask_card),
        ]
        if redact_emails:
            self._patterns.append(
                (
                    re.compile(
                        r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
                    ),
                    r"\1***@\2",
                )
            )

    def is_sensitive_key(self, key: Any) -> bool:
        if not isinstance(key, str):
            return False
        norm = _normalize(key)
        return norm in self.sensitive_keys or any(f in norm for f in self.sensitive_fragments)

    def redact_text(self, text: str) -> str:
        if not text:
            return text
        for pattern, replacement in self._patterns:
            text = pattern.sub(replacement, text)
        return text

    def redact(self, value: Any, _depth: int = 0) -> Any:
        """Return a redacted deep copy of ``value``."""
        if _depth > _MAX_DEPTH:
            return "[MAX_DEPTH]"
        if isinstance(value, Mapping):
            return {
                k: REDACTED if self.is_sensitive_key(k) else self.redact(v, _depth + 1)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self.redact(v, _depth + 1) for v in value]
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, bytes):
            return self.redact_text(value.decode("utf-8", errors="replace"))
        return value

    def redact_pairs(self, pairs: Iterable[tuple[str, str]]) -> dict[str, Any]:
        """Redact header / query-string style (key, value) pairs into a dict."""
        return {
            key: REDACTED if self.is_sensitive_key(key) else self.redact_text(val)
            for key, val in pairs
        }


@lru_cache
def get_redactor() -> Redactor:
    from app.core.config import settings

    return Redactor(extra_keys=settings.REDACT_EXTRA_KEYS, redact_emails=settings.REDACT_EMAILS)
