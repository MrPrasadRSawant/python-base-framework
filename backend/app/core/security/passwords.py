"""Password (and later client secret) hashing with argon2.

    password_hash = hash_password("s3cret-pass")
    verify_password("s3cret-pass", password_hash)   # True

Only hashes are ever stored. ``verify_dummy`` spends the same time as a real
check, so a login for an unknown email takes as long as one with a wrong
password (no way to probe which emails exist).
"""

from functools import lru_cache

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_hasher = PasswordHash.recommended()  # argon2id


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except UnknownHashError:
        return False


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("dummy-password-for-timing")


def verify_dummy(password: str) -> None:
    _hasher.verify(password, _dummy_hash())
