"""Roles and the permission catalog. Reading needs roles:read; changes need roles:manage.

System roles (``is_system``, e.g. admin) can be renamed but not deleted, and
their permissions cannot be changed (admin always holds everything, through
migrations). You can only grant permissions you hold yourself.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import PROTECTED, error_responses, list_response, record_response
from app.api.v1.access import ensure_can_grant, resolve_permissions
from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import Principal, require_permission
from app.core.security.permissions import Perm
from app.db.session import get_db
from app.models import Role
from app.schemas.rbac import (
    AssignPermissions,
    PermissionResponse,
    RoleCreate,
    RoleDetailResponse,
    RoleResponse,
    RoleUpdate,
)
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.services.permission import PermissionService
from app.services.role import RoleService
from app.services.role_permission import RolePermissionService

router = APIRouter(tags=["roles"])

can_read = require_permission(Perm.ROLES_READ)
can_manage = require_permission(Perm.ROLES_MANAGE)


async def _get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await RoleService(db).get(role_id)
    if role is None:
        raise NotFoundError("Role not found", details={"role_id": str(role_id)})
    return role


def _not_system(role: Role, action: str) -> None:
    if role.is_system:
        raise ForbiddenError(f"System roles cannot be {action}.", error_code="system_role")


async def _detail(db: AsyncSession, role: Role) -> RoleDetailResponse:
    return RoleDetailResponse(
        **RoleResponse.model_validate(role).model_dump(),
        permissions=await PermissionService(db).codes_for_roles([role.id]),
    )


NOT_FOUND = (404, "`not_found`: no role with this id (or deleted)")


# ------------------------------------------------------------------ roles
@router.get(
    "/roles",
    summary="List roles",
    response_model=ListResponse[RoleResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def list_roles(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `roles:read`.

    Roles, newest first. `is_system: true` marks built-in roles (e.g. `admin`).
    Use `GET /roles/{role_id}` to see a role's permissions.
    """
    return list_response(await RoleService(db).search(SearchRequest(limit=limit, offset=offset)))


@router.post(
    "/roles/search",
    summary="Search roles",
    response_model=ListResponse[RoleResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def search_roles(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `roles:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `code`, `name`, `is_system`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `code`, `name`, `created_on` (default: `created_on` desc) |
    | `search` (text) | `code`, `name`, `description` |
    """
    return list_response(await RoleService(db).search(payload))


@router.get(
    "/roles/{role_id}",
    summary="Get a role",
    response_model=RecordResponse[RoleDetailResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def get_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `roles:read`.

    One role with its `permissions` (permission codes).
    """
    return record_response(await _detail(db, await _get_role(db, role_id)))


@router.post(
    "/roles",
    summary="Create a role",
    response_model=RecordResponse[RoleDetailResponse],
    status_code=201,
    dependencies=[Depends(can_manage)],
    responses=error_responses(
        *PROTECTED, (409, "`role_code_taken`: a role with this code already exists")
    ),
)
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `roles:manage`.

    Creates an empty role (no permissions). `code` is the stable identifier used in
    role assignments: lower case, starting with a letter, e.g. `support_agent`. It cannot
    be changed later. Add permissions with `PUT /roles/{role_id}/permissions`.
    """
    roles = RoleService(db)
    if await roles.get_by_code(payload.code) is not None:
        raise ConflictError("A role with this code already exists.", error_code="role_code_taken")
    return record_response(await _detail(db, await roles.create(payload)))


@router.patch(
    "/roles/{role_id}",
    summary="Rename or describe a role",
    response_model=RecordResponse[RoleDetailResponse],
    dependencies=[Depends(can_manage)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def update_role(role_id: uuid.UUID, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `roles:manage`.

    Partial update of `name` and `description`. Allowed on system roles too.
    """
    role = await RoleService(db).update(role_id, payload)
    if role is None:
        raise NotFoundError("Role not found", details={"role_id": str(role_id)})
    return record_response(await _detail(db, role))


@router.delete(
    "/roles/{role_id}",
    summary="Delete a role",
    status_code=204,
    responses=error_responses(
        401,
        (403, "`forbidden`, `system_role` (built-in roles cannot be deleted) or "
         "`cannot_grant` (the role holds permissions you don't)"),
        NOT_FOUND,
    ),
)
async def delete_role(
    role_id: uuid.UUID,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `roles:manage`.

    Deletes the role and **removes it from every user**; they lose its permissions
    from their next token (within 15 minutes).
    """
    role = await _get_role(db, role_id)
    _not_system(role, "deleted")
    ensure_can_grant(principal, await PermissionService(db).codes_for_roles([role.id]))
    await RoleService(db).delete(role.id)


@router.put(
    "/roles/{role_id}/permissions",
    summary="Set a role's permissions",
    response_model=RecordResponse[RoleDetailResponse],
    responses=error_responses(
        401,
        (403, "`forbidden`, `system_role` (built-in roles cannot be changed) or "
         "`cannot_grant` (adding or removing a permission you don't hold)"),
        NOT_FOUND,
        (422, "`unknown_permissions`: a permission code does not exist"),
    ),
)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: AssignPermissions,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `roles:manage`.

    **Replaces** the role's permissions with exactly this list of codes (`[]` removes
    all). Valid codes come from `GET /permissions`. Users with this role get the change
    from their next token (within 15 minutes).
    """
    role = await _get_role(db, role_id)
    _not_system(role, "changed")
    perms = await resolve_permissions(db, payload.permissions)
    current = await PermissionService(db).codes_for_roles([role.id])
    # Adding or removing a permission both need it: no editing what you don't hold.
    ensure_can_grant(principal, set(current) ^ {p.code for p in perms})
    await RolePermissionService(db).replace_for_role(role.id, (p.id for p in perms))
    return record_response(await _detail(db, role))


# ------------------------------------------------------------ permissions
@router.get(
    "/permissions",
    summary="List the permission catalog",
    response_model=ListResponse[PermissionResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def list_permissions(
    limit: int = Query(settings.PAGINATION_MAX_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `roles:read`.

    Every permission the API checks, sorted by `code` (`resource:action`). Read-only:
    the catalog is defined in code and changes only with a release.
    """
    result = await PermissionService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)
