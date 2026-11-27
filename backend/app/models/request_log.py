from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class RequestLog(AuditMixin, Base):
    """One row per HTTP request (table ``requests``), for endpoint monitoring and reports.

    ``id`` IS the request id: the same UUID as the X-Request-ID header, and the
    value in ``exception_log.request_id`` / ``service_call_logs.request_id``.
    Those are logical links (indexed, used in JOINs) rather than enforced foreign
    keys: the log tables are written by separate background writers, in any order.

        SELECT r.route, s.service_name, s.duration_ms
        FROM requests r JOIN service_call_logs s ON s.request_id = r.id;

    No user data: no actual URL path (it carries ids and search terms), IP address,
    user agent, query string, headers or body. ``route`` is the template only.
    ``created_by`` holds the acting user once authentication is added.
    """

    __tablename__ = "requests"

    started_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    method: Mapped[str] = mapped_column(String(16))
    # Route template, e.g. /api/v1/orders/{order_id}: group by this for per-endpoint stats.
    # NULL when no route matched (404 on an unknown URL).
    route: Mapped[str | None] = mapped_column(String(512), index=True)
    endpoint: Mapped[str | None] = mapped_column(String(512))  # handler function
    status_code: Mapped[int] = mapped_column(Integer, index=True)
    duration_ms: Mapped[float] = mapped_column(Float)
