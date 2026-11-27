"""User administration. Reading needs users:read; changes need users:manage.

You cannot disable, delete or change the roles of your own account (so an
admin cannot lock themselves out). You can only assign roles whose permissions
you hold, and only disable / delete / re-role users whose permissions you all
hold (see app/api/v1/access.py).

Permission changes reach a user's access token on their next refresh
(at most ACCESS_TOKEN_TTL_MINUTES). Disabling or deleting a user also
revokes their refresh tokens, so they are signed out at the next refresh.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import PROTECTED, error_responses, list_response, record_response
from app.api.v1.access import (
    ensure_can_assign_roles,
    ensure_can_manage_user,
    resolve_roles,
    user_detail,
)
from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import Principal, hash_password, require_permission
from app.core.security.permissions import Perm
from app.db.session import get_db
from app.models import User
from app.schemas.rbac import AssignRoles
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.schemas.user import (
    UserAdminCreate,
    UserCreate,
    UserDetailResponse,
    UserResponse,
    UserUpdate,
)
from app.services.refresh_token import RefreshTokenService
from app.services.user import UserService
from app.services.user_role import UserRoleService

router = APIRouter(prefix="/users", tags=["users"])

can_read = require_permission(Perm.USERS_READ)
can_manage = require_permission(Perm.USERS_MANAGE)


async def _get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await UserService(db).get(user_id)
    if user is None:
        raise NotFoundError("User not found", details={"user_id": str(user_id)})
    return user


def _not_self(principal: Principal, user_id: uuid.UUID, action: str) -> None:
    if principal.id == str(user_id):
        raise ForbiddenError(f"You cannot {action} your own account.", error_code="self_change")


NOT_FOUND = (404, "`not_found`: no user with this id (or deleted)")
CANNOT_GRANT = (
    403,
    "`forbidden` (missing permission), `cannot_grant` (roles or target user hold "
    "permissions you don't), or `self_change` (your own account)",
)


@router.get(
    "",
    summary="List users",
    response_model=ListResponse[UserResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def list_users(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `users:read`.

    Users, newest first, paged with `limit` / `offset`. Deleted users are hidden.
    Use `POST /users/search` to filter, search or sort.
    """
    return list_response(await UserService(db).search(SearchRequest(limit=limit, offset=offset)))


@router.post(
    "/search",
    summary="Search users",
    response_model=ListResponse[UserResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def search_users(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `users:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `email`, `full_name`, `is_active`, `last_login_on`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `email`, `full_name`, `created_on`, `last_login_on` (default: `created_on` desc) |
    | `search` (text) | `email`, `full_name` |

    Example, active users matching "ali":
    `{"search": "ali", "filters": [{"field": "is_active", "value": true}]}`
    """
    return list_response(await UserService(db).search(payload))


@router.get(
    "/{user_id}",
    summary="Get a user",
    response_model=RecordResponse[UserDetailResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `users:read`.

    One user with their `roles` and effective `permissions`.
    """
    return record_response(await user_detail(db, await _get_user(db, user_id)))


@router.post(
    "",
    summary="Create a user",
    response_model=RecordResponse[UserDetailResponse],
    status_code=201,
    responses=error_responses(
        401,
        CANNOT_GRANT,
        (409, "`email_taken`: an account with this email already exists"),
        (422, "`unknown_roles`: a role code does not exist (or other validation errors)"),
    ),
)
async def create_user(
    payload: UserAdminCreate,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `users:manage`.

    Creates an active account with the given password and optional `roles` (role codes).
    You can only assign roles whose permissions you hold yourself.
    The email is stored lower-cased; the password must be 12 to 128 characters.
    """
    users = UserService(db)
    if await users.get_by_email(payload.email) is not None:
        raise ConflictError("An account with this email already exists.", error_code="email_taken")
    roles = await resolve_roles(db, payload.roles)
    await ensure_can_assign_roles(db, principal, roles)
    user = await users.create(
        UserCreate(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
    )
    if roles:
        await UserRoleService(db).replace_for_user(user.id, (r.id for r in roles))
    return record_response(await user_detail(db, user))


@router.patch(
    "/{user_id}",
    summary="Update a user",
    response_model=RecordResponse[UserDetailResponse],
    responses=error_responses(401, CANNOT_GRANT, NOT_FOUND),
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `users:manage`.

    Partial update: only the fields sent change (`full_name`, `is_active`).

    Setting `is_active: false` disables the account: the user cannot sign in, and their
    sessions end at the next refresh (current access tokens expire within 15 minutes).
    Changing `is_active` is refused for your own account, and for users holding
    permissions you don't have.
    """
    if payload.is_active is not None:
        _not_self(principal, user_id, "disable or enable")
        await ensure_can_manage_user(db, principal, await _get_user(db, user_id))
    user = await UserService(db).update(user_id, payload)
    if user is None:
        raise NotFoundError("User not found", details={"user_id": str(user_id)})
    if payload.is_active is False:
        await RefreshTokenService(db).revoke_for_user(user.id)
    return record_response(await user_detail(db, user))


@router.delete(
    "/{user_id}",
    summary="Delete a user",
    status_code=204,
    responses=error_responses(401, CANNOT_GRANT, NOT_FOUND),
)
async def delete_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `users:manage`.

    Soft delete: the user disappears from lists and cannot sign in, and their sessions
    end. The email can be registered again. Refused for your own account and for users
    holding permissions you don't have.
    """
    _not_self(principal, user_id, "delete")
    await ensure_can_manage_user(db, principal, await _get_user(db, user_id))
    await UserService(db).delete(user_id)
    await RefreshTokenService(db).revoke_for_user(user_id)


@router.put(
    "/{user_id}/roles",
    summary="Set a user's roles",
    response_model=RecordResponse[UserDetailResponse],
    responses=error_responses(
        401,
        CANNOT_GRANT,
        NOT_FOUND,
        (422, "`unknown_roles`: a role code does not exist"),
    ),
)
async def set_user_roles(
    user_id: uuid.UUID,
    payload: AssignRoles,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `users:manage`.

    **Replaces** the user's roles with exactly this list of role codes (`[]` removes all).
    The new permissions apply from the user's next token (within 15 minutes).

    Refused for your own account, for users holding permissions you don't have, and
    for roles granting permissions you don't have.
    """
    _not_self(principal, user_id, "change the roles of")
    user = await _get_user(db, user_id)
    await ensure_can_manage_user(db, principal, user)
    roles = await resolve_roles(db, payload.roles)
    await ensure_can_assign_roles(db, principal, roles)
    await UserRoleService(db).replace_for_user(user.id, (r.id for r in roles))
    return record_response(await user_detail(db, user))
