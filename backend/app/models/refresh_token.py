import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class RefreshToken(AuditMixin, Base):
    """One refresh token issued to a user. Only the SHA-256 of the token is stored.

    Every login starts a *family* (``family_id``); each refresh revokes the
    current token and issues the next one in the same family
    (``replaced_by_id`` links them). If a revoked token is presented again it
    was stolen or replayed, so the whole family is revoked (reuse detection).
    """

    __tablename__ = "refresh_tokens"
    # Rotated on every refresh: far too noisy to audit. Sign-in, sign-out and token
    # reuse are recorded as explicit events instead (app/api/v1/endpoints/auth.py).
    __activity_log__ = False

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    expires_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )

    def is_usable(self, now: datetime) -> bool:
        return self.revoked_on is None and self.expires_on > now and not self.is_deleted
