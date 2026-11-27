"""Sign-in for web users and API clients.

    POST /auth/register   create an account (only if AUTH_SELF_REGISTRATION_ENABLED)
    POST /auth/login      username/email + password -> access token + refresh cookie
    POST /auth/refresh    refresh cookie -> new access token + new refresh cookie
    POST /auth/logout     revoke the refresh cookie's session
    POST /auth/token      OAuth2 (form): password grant (Swagger / tools) or
                          client_credentials grant (API clients) -> access token
    GET  /auth/me         the signed-in user, with roles and permissions

Every login failure (unknown account, wrong password, inactive, locked) gets the
same 401 and message, so the response never reveals whether an account exists.

login, token, register and refresh are rate limited per client IP
(RATE_LIMIT_*), and client_credentials also per client_id: 429 + Retry-After.

Refresh tokens rotate: each one works once. Presenting a used one again means
it was stolen or replayed, so the whole session (token family) is revoked.
"""

import base64
import binascii
import ipaddress
import logging
import uuid
from datetime import timedelta
from typing import Annotated, Literal
from urllib.parse import unquote

from fastapi import APIRouter, Cookie, Depends, Form, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import error_responses, record_response
from app.api.v1.access import user_detail
from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.rate_limit import client_ip, limiter, rate_limit
from app.core.security import (
    CurrentUser,
    create_access_token,
    hash_password,
    verify_dummy,
    verify_password,
)
from app.core.security.cookies import clear_refresh_cookie, set_refresh_cookie
from app.db.mixins import utc_now
from app.db.session import get_db
from app.models import ApiClient, User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.responses import RecordResponse
from app.schemas.user import (
    PASSWORD_MAX_LENGTH,
    UserCreate,
    UserDetailResponse,
    UserRegister,
    UserResponse,
    normalize_email,
)
from app.services.api_client import ApiClientService
from app.services.permission import PermissionService
from app.services.refresh_token import RefreshTokenService
from app.services.user import UserService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

RefreshCookie = Cookie(None, alias=settings.REFRESH_COOKIE_NAME, include_in_schema=False)


def _invalid_credentials() -> UnauthorizedError:
    return UnauthorizedError(
        "Invalid username, email or password.",
        error_code="invalid_credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _invalid_refresh() -> UnauthorizedError:
    return UnauthorizedError(
        "The session has expired. Please sign in again.", error_code="invalid_refresh_token"
    )


def _invalid_client() -> UnauthorizedError:
    return UnauthorizedError(
        "Invalid client credentials.",
        error_code="invalid_client",
        headers={"WWW-Authenticate": 'Basic realm="api"'},
    )


def _basic_credentials(request: Request) -> tuple[str, str] | None:
    """client_id / client_secret from an ``Authorization: Basic`` header."""
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic" or not value:
        return None
    try:
        decoded = base64.b64decode(value, validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None
    cid, sep, secret = decoded.partition(":")
    return (unquote(cid), unquote(secret)) if sep else None


def _ip_allowed(client: ApiClient, ip: str | None) -> bool:
    if client.allowed_ips is None:
        return True
    if ip is None:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(net, strict=False) for net in client.allowed_ips)


async def _authenticate_client(
    db: AsyncSession, client_id: str | None, secret: str | None, ip: str | None
) -> ApiClient:
    """Check client credentials. Raises the same 401 for every failure."""
    if not client_id or not secret:
        raise _invalid_client()
    clients = ApiClientService(db)
    client = await clients.get_by_client_id(client_id)
    if client is None:
        verify_dummy(secret)  # same time as a real check
        raise _invalid_client()
    usable = (
        client.is_active
        and (client.expires_on is None or client.expires_on > utc_now())
        and _ip_allowed(client, ip)
    )
    if not verify_password(secret, client.secret_hash) or not usable:
        logger.warning(
            "API client authentication failed",
            extra={"client_id": client.client_id, "client_ip": ip},
        )
        raise _invalid_client()
    await clients.record_use(client)
    return client


async def _user_token(db: AsyncSession, user: User) -> TokenResponse:
    """Access token carrying the user's current permissions (from their roles)."""
    permissions = await PermissionService(db).codes_for_user(user.id)
    token, expires_in = create_access_token(
        subject=str(user.id), token_type="user", permissions=permissions
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


async def _token_record(db: AsyncSession, user: User) -> dict:
    return record_response(await _user_token(db, user))


async def _authenticate_user(db: AsyncSession, identifier: str, password: str) -> User:
    """Check username or email + password with the same failure response."""
    users = UserService(db)
    identifier = identifier.strip()
    user = (
        await users.get_by_email(normalize_email(identifier))
        if "@" in identifier
        else await users.get_by_username(identifier)
    )
    if user is None:
        verify_dummy(password)  # same time as a real check
        raise _invalid_credentials()
    if user.is_locked or (user.locked_until is not None and user.locked_until > utc_now()):
        raise _invalid_credentials()
    if not verify_password(password, user.password_hash):
        await users.record_login_failure(
            user, max_failed=settings.LOGIN_MAX_FAILED, lock_minutes=settings.LOGIN_LOCK_MINUTES
        )
        raise _invalid_credentials()
    if not user.is_active:
        raise _invalid_credentials()
    await users.record_login_success(user)
    return user


@router.post(
    "/register",
    summary="Register a new account",
    response_model=RecordResponse[UserResponse],
    status_code=201,
    dependencies=[Depends(rate_limit("register", lambda: settings.RATE_LIMIT_REGISTER))],
    responses=error_responses(
        (403, "`registration_disabled`: self-registration is switched off"),
        (409, "`email_taken` or `username_taken`: email or username already exists"),
        429,
    ),
)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """**Access:** Public. Only available when `AUTH_SELF_REGISTRATION_ENABLED` is on.
    **Rate limit:** `RATE_LIMIT_REGISTER` per IP.

    Creates an active account with **no roles**: the user can sign in but has no
    permissions until an admin assigns a role. Email is stored lower-cased;
    username is separate and unique without regard to case.
    Password: 12 to 128 characters.

    This does not sign the user in; call `POST /auth/login` next.
    """
    if not settings.AUTH_SELF_REGISTRATION_ENABLED:
        raise ForbiddenError("Self-registration is disabled.", error_code="registration_disabled")
    users = UserService(db)
    if await users.get_by_email(payload.email) is not None:
        raise ConflictError("An account with this email already exists.", error_code="email_taken")
    if await users.get_by_username(payload.username) is not None:
        raise ConflictError("This username is already taken.", error_code="username_taken")
    user = await users.create(
        UserCreate(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
    )
    return record_response(user)


@router.post(
    "/login",
    summary="Sign in (web app)",
    response_model=RecordResponse[TokenResponse],
    dependencies=[Depends(rate_limit("login", lambda: settings.RATE_LIMIT_LOGIN))],
    responses=error_responses(
        (401, "`invalid_credentials`: wrong username/email or password, disabled or locked account"),
        429,
    ),
)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """**Access:** Public. **Rate limit:** `RATE_LIMIT_LOGIN` per IP (shared with `/auth/token`).

    Checks username or email + password and returns:
    - `record.access_token`: send as `Authorization: Bearer <token>`; valid for `expires_in`
      seconds. It carries the user's permissions.
    - A **refresh cookie** (`Set-Cookie`, HttpOnly, path `/api/v1/auth`), used by
      `POST /auth/refresh`. JavaScript cannot read it; send requests with credentials.

    Every failure returns the same `401 invalid_credentials`, so the response never
    reveals whether an account exists. After `LOGIN_MAX_FAILED` wrong passwords in a row
    the account is locked for `LOGIN_LOCK_MINUTES`.
    """
    user = await _authenticate_user(db, payload.identifier, payload.password)
    set_refresh_cookie(response, await RefreshTokenService(db).issue(user.id))
    return await _token_record(db, user)


@router.post(
    "/token",
    summary="Get an access token (OAuth2)",
    response_model=TokenResponse,
    responses=error_responses(
        (401, "`invalid_credentials` (password grant) or `invalid_client` (client credentials)"),
        429,
    ),
)
async def token(
    request: Request,
    grant_type: Annotated[
        Literal["password", "client_credentials"],
        Form(description="`client_credentials` for API clients, `password` for users"),
    ],
    username: Annotated[
        str | None, Form(max_length=255, description="password grant: username or email")
    ] = None,
    password: Annotated[
        str | None, Form(max_length=PASSWORD_MAX_LENGTH, description="password grant")
    ] = None,
    client_id: Annotated[
        str | None, Form(max_length=64, description="client_credentials grant (or HTTP Basic)")
    ] = None,
    client_secret: Annotated[
        str | None, Form(max_length=256, description="client_credentials grant (or HTTP Basic)")
    ] = None,
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Public. **Rate limit:** per IP, and per `client_id` for client credentials.

    Standard OAuth2 token endpoint: **form-encoded** request
    (`application/x-www-form-urlencoded`) and a plain OAuth2 response
    (`{"access_token", "token_type", "expires_in"}`, no envelope).

    **`client_credentials`** (server integrations): send `client_id` + `client_secret` as
    form fields, or as `Authorization: Basic base64(client_id:client_secret)`. Returns a
    `service` token carrying the client's permissions, valid `SERVICE_TOKEN_TTL_MINUTES`.
    There is no refresh token: request a new token when it expires. Fails with
    `401 invalid_client` if the client is unknown, disabled, expired, calling from an IP
    outside its allowlist, or the secret is wrong.

    **`password`** (Swagger / tools): send `username` (username or email) + `password`. Same checks as
    `POST /auth/login`, but no refresh cookie is set. The web app should use `/auth/login`.

    ```
    curl -X POST https://<host>/api/v1/auth/token \\
      -d grant_type=client_credentials -d client_id=cli_... -d client_secret=...
    ```
    """
    ip = client_ip(request)
    if grant_type == "password":
        limiter.check(f"login:ip:{ip}", settings.RATE_LIMIT_LOGIN)  # shared with /auth/login
        if not username or not password:
            raise _invalid_credentials()
        user = await _authenticate_user(db, username, password)
        return await _user_token(db, user)

    limiter.check(f"token:ip:{ip}", settings.RATE_LIMIT_TOKEN)
    if not client_id and not client_secret:  # not in the form: try HTTP Basic
        client_id, client_secret = _basic_credentials(request) or (None, None)
    if client_id:
        limiter.check(f"token:client:{client_id}", settings.RATE_LIMIT_TOKEN_PER_CLIENT)
    client = await _authenticate_client(db, client_id, client_secret, ip)
    permissions = await PermissionService(db).codes_for_api_client(client.id)
    access_token, expires_in = create_access_token(
        subject=client.client_id,
        token_type="service",
        permissions=permissions,
        ttl=timedelta(minutes=settings.SERVICE_TOKEN_TTL_MINUTES),
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post(
    "/refresh",
    summary="Renew the access token (web app)",
    response_model=RecordResponse[TokenResponse],
    dependencies=[Depends(rate_limit("refresh", lambda: settings.RATE_LIMIT_REFRESH))],
    responses=error_responses(
        (401, "`invalid_refresh_token`: missing, unknown, expired or reused cookie"), 429
    ),
)
async def refresh(
    response: Response,
    refresh_token: str | None = RefreshCookie,
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Refresh cookie (set by `POST /auth/login`); no access token needed.
    **Rate limit:** `RATE_LIMIT_REFRESH` per IP.

    No request body. Returns a new access token (same shape as login) and replaces the
    refresh cookie with a new one; the old cookie value stops working.

    - Call it when an API call returns `401 token_expired`, or shortly before `expires_in`.
    - Run **one refresh at a time**: two parallel refreshes with the same cookie look like a
      stolen token, and the whole session is ended.
    - `401 invalid_refresh_token` means the session is over: send the user to sign in.
    """
    if not refresh_token:
        raise _invalid_refresh()
    tokens = RefreshTokenService(db)
    current = await tokens.get_by_token(refresh_token, for_update=True)
    if current is None or current.is_deleted or current.expires_on <= utc_now():
        raise _invalid_refresh()
    if current.revoked_on is not None:
        await tokens.revoke_family(current.family_id)
        logger.warning(
            "Refresh token reuse detected; session revoked",
            extra={"user_id": str(current.user_id), "family_id": str(current.family_id)},
        )
        raise _invalid_refresh()

    user = await UserService(db).get(current.user_id)
    if user is None or not user.is_active or user.is_locked:
        await tokens.revoke_family(current.family_id)
        raise _invalid_refresh()

    set_refresh_cookie(response, await tokens.rotate(current))
    return await _token_record(db, user)


@router.post("/logout", summary="Sign out (web app)", status_code=204, response_class=Response)
async def logout(refresh_token: str | None = RefreshCookie, db: AsyncSession = Depends(get_db)):
    """**Access:** Refresh cookie (optional); no access token needed.

    Ends the session: the refresh cookie is revoked and cleared. Always returns `204`,
    even without a cookie. The current access token stays valid until it expires
    (at most 15 minutes), so the client should discard it.
    """
    if refresh_token:
        tokens = RefreshTokenService(db)
        current = await tokens.get_by_token(refresh_token)
        if current is not None:
            await tokens.revoke_family(current.family_id)
    response = Response(status_code=204)
    clear_refresh_cookie(response)
    return response


@router.get(
    "/me",
    summary="Current user, roles and permissions",
    response_model=RecordResponse[UserDetailResponse],
    responses=error_responses(
        401,
        (403, "`forbidden`: called with an API-client token"),
        (404, "`not_found`: the account was deleted or disabled after the token was issued"),
    ),
)
async def me(principal: CurrentUser, db: AsyncSession = Depends(get_db)):
    """**Access:** Signed-in user (user token only).

    The signed-in user's profile, with `roles` (role codes) and `permissions` (effective
    permission codes from all roles). Use `permissions` to show or hide UI features.
    Values are read from the database, so they can be newer than the access token.
    """
    user = await UserService(db).get(uuid.UUID(principal.id))
    if user is None or not user.is_active:
        # Token is still valid but the account was deleted or disabled meanwhile.
        raise NotFoundError("User not found", details={"user_id": principal.id})
    return record_response(await user_detail(db, user))
