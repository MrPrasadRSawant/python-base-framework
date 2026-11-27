from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class RequestLog(AuditMixin, Base):
    """One row per HTTP request, for endpoint monitoring (traffic, errors, latency).

    No user data: no actual URL path (it carries ids and search terms), IP address,
    user agent, query string, headers or body. ``route`` is the template only.
    ``created_by`` holds the acting user once authentication is added.
    """

    __tablename__ = "request_logs"

    started_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    request_id: Mapped[str] = mapped_column(String(128), index=True)
    method: Mapped[str] = mapped_column(String(16))
    # Route template, e.g. /api/v1/orders/{order_id}: group by this for per-endpoint stats.
    # NULL when no route matched (404 on an unknown URL).
    route: Mapped[str | None] = mapped_column(String(512), index=True)
    endpoint: Mapped[str | None] = mapped_column(String(512))  # handler function
    status_code: Mapped[int] = mapped_column(Integer, index=True)
    duration_ms: Mapped[float] = mapped_column(Float)
