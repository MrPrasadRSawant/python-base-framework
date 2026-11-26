from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class ExceptionLog(AuditMixin, Base):
    """One row per exception. Every value is redacted before insert."""

    __tablename__ = "exception_log"

    occurred_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    level: Mapped[str] = mapped_column(String(20))
    logger: Mapped[str] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(512))  # module:function:line

    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), index=True)

    exception_type: Mapped[str | None] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)

    method: Mapped[str | None] = mapped_column(String(16))
    path: Mapped[str | None] = mapped_column(String(2048))
    route: Mapped[str | None] = mapped_column(String(512))
    endpoint: Mapped[str | None] = mapped_column(String(512))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))

    query_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    details: Mapped[Any | None] = mapped_column(JSONB)

    environment: Mapped[str | None] = mapped_column(String(50))
    hostname: Mapped[str | None] = mapped_column(String(255))
    process_id: Mapped[int | None] = mapped_column(Integer)
