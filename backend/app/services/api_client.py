import secrets

from sqlalchemy import select

from app.core.security.passwords import hash_password
from app.core.service_tracking import track_service
from app.db.mixins import utc_now
from app.models import ApiClient
from app.schemas.api_client import ApiClientInsert
from app.services.base import AUDIT_FIELDS, BaseService

CLIENT_ID_PREFIX = "cli_"


def new_client_secret() -> tuple[str, str]:
    """Return (secret for the caller, argon2 hash to store)."""
    secret = secrets.token_urlsafe(32)
    return secret, hash_password(secret)


class ApiClientService(BaseService):
    model = ApiClient
    filter_fields = ("client_id", "name", "is_active", "expires_on", "last_used_on", *AUDIT_FIELDS)
    sort_fields = ("name", "created_on", "last_used_on", "expires_on")
    search_fields = ("client_id", "name", "description")

    @track_service
    async def register(
        self, *, name: str, description: str | None, allowed_ips, expires_on
    ) -> tuple[ApiClient, str]:
        """Create a client with a generated client_id and secret. Returns (row, secret)."""
        secret, secret_hash = new_client_secret()
        client = await self.create(
            ApiClientInsert(
                client_id=CLIENT_ID_PREFIX + secrets.token_urlsafe(16),
                secret_hash=secret_hash,
                name=name,
                description=description,
                allowed_ips=allowed_ips,
                expires_on=expires_on,
            )
        )
        return client, secret

    @track_service
    async def get_by_client_id(self, client_id: str) -> ApiClient | None:
        return await self.db.scalar(
            select(ApiClient).where(
                ApiClient.client_id == client_id, ApiClient.is_deleted.is_(False)
            )
        )

    @track_service
    async def rotate_secret(self, client: ApiClient) -> str:
        """New secret; the old one stops working immediately."""
        secret, client.secret_hash = new_client_secret()
        await self.db.commit()
        return secret

    @track_service
    async def record_use(self, client: ApiClient) -> None:
        client.last_used_on = utc_now()
        await self.db.commit()

