import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class ApiClient(AuditMixin, Base):
    """A server-side integration that signs in with client_id + client_secret
    (OAuth2 client credentials) and gets a short-lived ``service`` access token.

    Only the argon2 hash of the secret is stored; the secret is shown once,
    when the client is created or its secret rotated.
    """

    __tablename__ = "api_clients"

    # Updated on every token request; recorded as token_issued events instead.
    __activity_log_ignore__ = frozenset({"last_used_on"})

    client_id: Mapped[str] = mapped_column(String(64), unique=True)  # public, random
    secret_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    expires_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL = never
    # IPs / CIDRs allowed to request tokens, e.g. ["10.0.0.0/8"]. NULL = any.
    allowed_ips: Mapped[list[str] | None] = mapped_column(JSONB)
    last_used_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiClientPermission(AuditMixin, Base):
    """The client's scopes: permissions granted directly (no roles). Hard-deleted on revoke."""

    __tablename__ = "api_client_permissions"
    __table_args__ = (UniqueConstraint("api_client_id", "permission_id"),)

    api_client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("api_clients.id", ondelete="CASCADE"), index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )
