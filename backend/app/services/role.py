import uuid
from collections.abc import Iterable

from sqlalchemy import delete, select

from app.core.service_tracking import track_service
from app.models import Role, RolePermission, UserRole
from app.services.base import AUDIT_FIELDS, BaseService


class RoleService(BaseService):
    model = Role
    filter_fields = ("code", "name", "is_system", *AUDIT_FIELDS)
    sort_fields = ("code", "name", "created_on")
    search_fields = ("code", "name", "description")

    @track_service
    async def get_by_code(self, code: str) -> Role | None:
        return await self.db.scalar(
            select(Role).where(Role.code == code, Role.is_deleted.is_(False))
        )

    @track_service
    async def get_by_codes(self, codes: Iterable[str]) -> list[Role]:
        query = select(Role).where(Role.code.in_(set(codes)), Role.is_deleted.is_(False))
        return list((await self.db.scalars(query)).all())

    @track_service
    async def delete(self, record_id: uuid.UUID) -> bool:
        """Soft-delete the role and hard-delete its grants, in one transaction, so
        nobody keeps its permissions (from their next token on)."""
        role = await self.get(record_id)
        if role is None:
            return False
        await self.db.execute(delete(UserRole).where(UserRole.role_id == role.id))
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        role.soft_delete()
        await self.db.commit()
        return True
