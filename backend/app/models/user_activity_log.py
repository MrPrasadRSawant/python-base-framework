import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class UserActivityLog(AuditMixin, Base):
    """Audit trail (table ``user_activity_logs``): who did what, to which record, when.

    Two kinds of rows:

    * **Data changes**, captured automatically from every ORM flush that is
      committed: ``create`` / ``update`` / ``delete`` / ``restore`` of a row in any
      table, with before/after values in ``changes``. Rolled-back changes are
      never recorded. Bulk ``UPDATE`` / ``DELETE`` statements are captured too.
    * **Security events**, recorded explicitly: ``login``, ``login_failed``,
      ``logout``, ``token_issued`` / ``client_auth_failed`` (API clients),
      ``session_revoked`` (refresh-token reuse) and ``access_denied`` (any 403).

    Unlike the other log tables this one is *about* people, so it stores the
    client IP and user agent: they are what tells a stolen session apart from
    its owner. Values of sensitive columns (password / secret / token hashes)
    are redacted; only the fact that they changed is kept.

    ``request_id`` links to ``requests.id``, ``exception_log.request_id`` and
    ``service_call_logs.request_id`` (logical link, not an enforced foreign key).
    """

    __tablename__ = "user_activity_logs"
    __table_args__ = (
        # "History of this record" and "what did this user do" are the main questions.
        Index("ix_user_activity_logs_entity", "entity_type", "entity_id", "occurred_on"),
        Index("ix_user_activity_logs_actor_occurred", "actor_id", "occurred_on"),
    )
    # Never audit the audit table itself (and its writer's own inserts).
    __activity_log__ = False

    occurred_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Who: "user:<id>", "service:<client_id>", "system" or "anonymous".
    actor: Mapped[str] = mapped_column(String(255))
    actor_type: Mapped[str] = mapped_column(String(16), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64))  # users.id / client_id
    # What: create, update, delete, restore, login, login_failed, access_denied, ...
    action: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # success | failed
    # Which record: table name + primary key (NULL for events about no record).
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    # {"field": {"old": ..., "new": ...}}; sensitive values are "[REDACTED]".
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # reason, codes, ...
    # Where from
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    method: Mapped[str | None] = mapped_column(String(16))
    route: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512))
