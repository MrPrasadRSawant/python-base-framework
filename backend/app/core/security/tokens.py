"""Access tokens: signed JWTs, the same format for users and services.

    token, expires_in = create_access_token(subject=str(user.id), token_type="user",
                                            permissions={"request_logs:read"})
    principal = principal_from_token(token)     # raises jwt.InvalidTokenError

Claims: sub, type (user | service), perms, iss, iat, exp, jti.
Permissions are inside the token, so checking a request needs no DB lookup.

Refresh tokens are opaque random strings instead (see new_opaque_token).
"""

import hashlib
import secrets
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.security.principal import Principal, PrincipalType

_REQUIRED_CLAIMS = ["sub", "type", "exp", "iat", "iss"]


def create_access_token(
    *,
    subject: str,
    token_type: PrincipalType,
    permissions: Iterable[str] = (),
    ttl: timedelta | None = None,
) -> tuple[str, int]:
    """Return the signed token and its lifetime in seconds."""
    ttl = ttl or timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "type": token_type,
        "perms": sorted(set(permissions)),
        "iss": settings.JWT_ISSUER,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(
        claims, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM
    )
    return token, int(ttl.total_seconds())


def principal_from_token(token: str) -> Principal:
    """Verify signature, expiry and issuer, then build the Principal.

    Raises ``jwt.ExpiredSignatureError`` or another ``jwt.InvalidTokenError``.
    """
    claims = jwt.decode(
        token,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],  # never trust the token's own "alg"
        issuer=settings.JWT_ISSUER,
        options={"require": _REQUIRED_CLAIMS},
    )
    token_type = claims["type"]
    perms = claims.get("perms", [])
    if token_type not in ("user", "service") or not isinstance(perms, list):
        raise jwt.InvalidTokenError("Unexpected token claims")
    return Principal(id=str(claims["sub"]), type=token_type, permissions=frozenset(perms))


# ---- opaque tokens (refresh tokens) ----------------------------------------
# Random, not JWTs: they are looked up in the DB anyway, and only their SHA-256
# is stored, so a database leak does not leak usable tokens.
def new_opaque_token() -> tuple[str, str]:
    """Return (token for the client, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_opaque_token(token)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
