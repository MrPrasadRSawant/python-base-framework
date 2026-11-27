import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class ServiceCallLog(AuditMixin, Base):
    """One row per tracked service call (functions decorated with @track_service).

    Answers: which services did a request call, in what order, how long did
    each take, and did it succeed. No arguments or return values are stored.
    """

    __tablename__ = "service_call_logs"

    # Logical link to requests.id (same UUID, indexed; not an enforced foreign key).
    # NULL for calls made outside a request (startup, background jobs).
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True)
    call_order: Mapped[int | None] = mapped_column(Integer)  # 1, 2, 3... within the request
    # call_order of the tracked call that made this one; NULL for top-level calls.
    parent_call_order: Mapped[int | None] = mapped_column(Integer)
    service_name: Mapped[str] = mapped_column(String(255), index=True)
    started_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), index=True)  # success / failed
    error_type: Mapped[str | None] = mapped_column(String(255))  # exception class only
