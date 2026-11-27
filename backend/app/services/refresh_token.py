import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.security.tokens import hash_opaque_token, new_opaque_token
from app.core.service_tracking import track_service
from app.db.mixins import new_uuid, utc_now
from app.models import RefreshToken
from app.services.base import AUDIT_FIELDS, BaseService


class RefreshTokenService(BaseService):
    model = RefreshToken
    filter_fields = ("user_id", "family_id", "expires_on", "revoked_on", *AUDIT_FIELDS)
    sort_fields = ("created_on", "expires_on")

    def _new_row(self, user_id: uuid.UUID, family_id: uuid.UUID) -> tuple[str, RefreshToken]:
        token, token_hash = new_opaque_token()
        row = RefreshToken(
            id=new_uuid(),
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_on=utc_now() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        )
        self.db.add(row)
        return token, row

    @track_service
    async def issue(self, user_id: uuid.UUID) -> str:
        """Start a new family (a login). Returns the plain token for the cookie."""
        token, _ = self._new_row(user_id, new_uuid())
        await self.db.commit()
        return token

    @track_service
    async def get_by_token(self, token: str, *, for_update: bool = False) -> RefreshToken | None:
        """Look a token up by its hash. ``for_update`` locks the row, so two refreshes
        with the same token cannot both succeed."""
        query = select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(token))
        if for_update:
            query = query.with_for_update()
        return await self.db.scalar(query)

    @track_service
    async def rotate(self, current: RefreshToken) -> str:
        """Revoke ``current`` and issue its successor in the same family."""
        token, successor = self._new_row(current.user_id, current.family_id)
        await self.db.flush()  # successor row must exist before it is referenced
        current.revoked_on = utc_now()
        current.replaced_by_id = successor.id
        await self.db.commit()
        return token

    @track_service
    async def revoke_family(self, family_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_on.is_(None))
            .values(revoked_on=utc_now())
        )
        await self.db.commit()

    @track_service
    async def revoke_for_user(self, user_id: uuid.UUID) -> None:
        """Sign the user out everywhere (used when an account is disabled or deleted)."""
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_on.is_(None))
            .values(revoked_on=utc_now())
        )
        await self.db.commit()

    @track_service
    async def delete_expired(self, before: datetime) -> int:
        """Housekeeping: hard-delete tokens that expired before ``before``."""
        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.expires_on < before)
        )
        await self.db.commit()
        return result.rowcount
