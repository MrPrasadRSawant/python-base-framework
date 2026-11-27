"""Common columns required on every table.

    class Order(AuditMixin, Base):
        __tablename__ = "orders"
        ...

Columns:
    id          UUID primary key (time-ordered UUIDv7 when available)
    created_by  who created the row (from the current actor; "system" by default)
    created_on  UTC timestamp, set on insert
    updated_by  who last updated the row (set automatically on UPDATE)
    updated_on  UTC timestamp of the last update (NULL until first update)
    is_deleted  soft-delete flag
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.request_context import SYSTEM_ACTOR, get_current_actor

ACTOR_LENGTH = 255


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> uuid.UUID:
    # UUIDv7 (Python 3.14+) is time-ordered, which keeps the PK index compact.
    return uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4()


class AuditMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
        sort_order=-1000,  # first column
    )

    # sort_order >= 1000 keeps the audit columns at the end of every table.
    created_by: Mapped[str] = mapped_column(
        String(ACTOR_LENGTH),
        default=get_current_actor,
        server_default=SYSTEM_ACTOR,
        sort_order=1001,
    )
    created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        index=True,
        sort_order=1002,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(ACTOR_LENGTH), onupdate=get_current_actor, sort_order=1003
    )
    updated_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=utc_now, sort_order=1004
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), index=True, sort_order=1005
    )

    def soft_delete(self) -> None:
        self.is_deleted = True

    def restore(self) -> None:
        self.is_deleted = False
