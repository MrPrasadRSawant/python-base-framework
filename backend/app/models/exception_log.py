import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class ExceptionLog(AuditMixin, Base):
    """One row per exception.

    Stores only technical data about the failure. Nothing the user sent
    (body, query string, headers) and nothing identifying the user's device
    (IP address, user agent). Use ``request_id`` to correlate with the log files.
    """

    __tablename__ = "exception_log"
    # Log table: not audited by the user activity log (see app/core/activity_log.py).
    __activity_log__ = False

    occurred_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    level: Mapped[str] = mapped_column(String(20))
    logger: Mapped[str] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(512))  # module:function:line

    # Logical link to requests.id (same UUID, indexed; not an enforced foreign key).
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), index=True)

    exception_type: Mapped[str | None] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)

    method: Mapped[str | None] = mapped_column(String(16))
    path: Mapped[str | None] = mapped_column(String(2048))
    route: Mapped[str | None] = mapped_column(String(512))
    endpoint: Mapped[str | None] = mapped_column(String(512))

    # Error context, e.g. {"order_id": ...} or validation errors (loc/msg/type, no input).
    details: Mapped[Any | None] = mapped_column(JSONB)

    environment: Mapped[str | None] = mapped_column(String(50))
    hostname: Mapped[str | None] = mapped_column(String(255))
    process_id: Mapped[int | None] = mapped_column(Integer)
