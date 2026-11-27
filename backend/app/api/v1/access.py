"""Shared RBAC logic for the auth, users and roles endpoints.

Grant rule (stops privilege escalation): a caller can only hand out
permissions they hold themselves, directly (role permissions) or through a
role (assigning a role whose permissions they don't all hold is refused).
"""

from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnprocessableEntityError
from app.core.security import Principal
from app.models import Permission, Role, User
from app.schemas.user import UserDetailResponse, UserResponse
from app.services.permission import PermissionService
from app.services.role import RoleService
from app.services.user_role import UserRoleService


async def resolve_roles(db: AsyncSession, codes: Iterable[str]) -> list[Role]:
    codes = set(codes)
    roles = await RoleService(db).get_by_codes(codes) if codes else []
    unknown = sorted(codes - {r.code for r in roles})
    if unknown:
        raise UnprocessableEntityError(
            "Unknown role(s).", error_code="unknown_roles", details={"unknown_roles": unknown}
        )
    return roles


async def resolve_permissions(db: AsyncSession, codes: Iterable[str]) -> list[Permission]:
    codes = set(codes)
    perms = await PermissionService(db).get_by_codes(codes) if codes else []
    unknown = sorted(codes - {p.code for p in perms})
    if unknown:
        raise UnprocessableEntityError(
            "Unknown permission(s).",
            error_code="unknown_permissions",
            details={"unknown_permissions": unknown},
        )
    return perms


def ensure_can_grant(principal: Principal, permission_codes: Iterable[str]) -> None:
    missing = sorted(set(permission_codes) - principal.permissions)
    if missing:
        raise ForbiddenError(
            "You can only grant permissions you hold yourself.",
            error_code="cannot_grant",
            details={"missing_permissions": missing},
        )


async def ensure_can_assign_roles(db: AsyncSession, principal: Principal, roles: list[Role]) -> None:
    if roles:
        codes = await PermissionService(db).codes_for_roles(r.id for r in roles)
        ensure_can_grant(principal, codes)


async def ensure_can_manage_user(db: AsyncSession, principal: Principal, user: User) -> None:
    """Changing another user's status or roles needs every permission they hold,
    so e.g. a support manager cannot disable or demote an admin."""
    ensure_can_grant(principal, await PermissionService(db).codes_for_user(user.id))


async def user_detail(db: AsyncSession, user: User) -> UserDetailResponse:
    return UserDetailResponse(
        **UserResponse.model_validate(user).model_dump(),
        roles=await UserRoleService(db).role_codes_for_user(user.id),
        permissions=await PermissionService(db).codes_for_user(user.id),
    )
