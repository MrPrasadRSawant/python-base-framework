import uuid
from collections.abc import Iterable

from sqlalchemy import select

from app.core.service_tracking import track_service
from app.models import ApiClientPermission, Permission, Role, RolePermission, UserRole
from app.schemas.search import SortDirection
from app.services.base import AUDIT_FIELDS, BaseService


class PermissionService(BaseService):
    """Read-only in practice: rows come from migrations (see core/security/permissions.py)."""

    model = Permission
    filter_fields = ("code", *AUDIT_FIELDS)
    sort_fields = ("code", "created_on")
    search_fields = ("code", "description")
    default_sort = (("code", SortDirection.ASC),)

    @track_service
    async def get_by_codes(self, codes: Iterable[str]) -> list[Permission]:
        query = select(Permission).where(
            Permission.code.in_(set(codes)), Permission.is_deleted.is_(False)
        )
        return list((await self.db.scalars(query)).all())

    @track_service
    async def codes_for_roles(self, role_ids: Iterable[uuid.UUID]) -> list[str]:
        query = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id.in_(set(role_ids)), Permission.is_deleted.is_(False))
            .distinct()
            .order_by(Permission.code)
        )
        return list((await self.db.scalars(query)).all())

    @track_service
    async def codes_for_api_client(self, api_client_id: uuid.UUID) -> list[str]:
        """The client's scopes: what goes into its service access token."""
        query = (
            select(Permission.code)
            .join(ApiClientPermission, ApiClientPermission.permission_id == Permission.id)
            .where(
                ApiClientPermission.api_client_id == api_client_id,
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.code)
        )
        return list((await self.db.scalars(query)).all())

    @track_service
    async def codes_for_user(self, user_id: uuid.UUID) -> list[str]:
        """Every permission the user holds through their (non-deleted) roles.
        This is what goes into the user's access token."""
        query = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.is_deleted.is_(False),
                Permission.is_deleted.is_(False),
            )
            .distinct()
            .order_by(Permission.code)
        )
        return list((await self.db.scalars(query)).all())
