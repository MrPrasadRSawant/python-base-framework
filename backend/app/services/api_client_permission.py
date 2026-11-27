import uuid
from collections.abc import Iterable

from sqlalchemy import delete

from app.core.service_tracking import track_service
from app.models import ApiClientPermission
from app.services.base import AUDIT_FIELDS, BaseService


class ApiClientPermissionService(BaseService):
    model = ApiClientPermission
    filter_fields = ("api_client_id", "permission_id", *AUDIT_FIELDS)

    @track_service
    async def replace_for_client(
        self, api_client_id: uuid.UUID, permission_ids: Iterable[uuid.UUID]
    ) -> None:
        """Make ``permission_ids`` the client's complete set (old rows hard-deleted)."""
        await self.db.execute(
            delete(ApiClientPermission).where(ApiClientPermission.api_client_id == api_client_id)
        )
        self.db.add_all(
            ApiClientPermission(api_client_id=api_client_id, permission_id=pid)
            for pid in set(permission_ids)
        )
        await self.db.commit()
