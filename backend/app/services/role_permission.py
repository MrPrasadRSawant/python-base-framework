import uuid
from collections.abc import Iterable

from sqlalchemy import delete

from app.core.service_tracking import track_service
from app.models import RolePermission
from app.services.base import AUDIT_FIELDS, BaseService


class RolePermissionService(BaseService):
    model = RolePermission
    filter_fields = ("role_id", "permission_id", *AUDIT_FIELDS)

    @track_service
    async def replace_for_role(
        self, role_id: uuid.UUID, permission_ids: Iterable[uuid.UUID]
    ) -> None:
        """Make ``permission_ids`` the role's complete set (old rows hard-deleted)."""
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        self.db.add_all(
            RolePermission(role_id=role_id, permission_id=pid) for pid in set(permission_ids)
        )
        await self.db.commit()
