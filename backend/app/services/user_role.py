import uuid
from collections.abc import Iterable

from sqlalchemy import delete, select

from app.core.service_tracking import track_service
from app.models import Role, UserRole
from app.services.base import AUDIT_FIELDS, BaseService


class UserRoleService(BaseService):
    model = UserRole
    filter_fields = ("user_id", "role_id", *AUDIT_FIELDS)

    @track_service
    async def role_codes_for_user(self, user_id: uuid.UUID) -> list[str]:
        query = (
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.is_deleted.is_(False))
            .order_by(Role.code)
        )
        return list((await self.db.scalars(query)).all())

    @track_service
    async def replace_for_user(self, user_id: uuid.UUID, role_ids: Iterable[uuid.UUID]) -> None:
        """Make ``role_ids`` the user's complete set of roles (old rows hard-deleted)."""
        await self.db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        self.db.add_all(UserRole(user_id=user_id, role_id=rid) for rid in set(role_ids))
        await self.db.commit()
