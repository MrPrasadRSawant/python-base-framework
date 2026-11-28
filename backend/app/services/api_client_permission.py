import uuid
from collections.abc import Iterable

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
        """Make ``permission_ids`` the client's complete set (only differences change)."""
        await self.replace_links("api_client_id", api_client_id, "permission_id", permission_ids)
