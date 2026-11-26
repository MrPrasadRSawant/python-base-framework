import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import AuditRead


class ExceptionLogSummary(BaseModel):
    """Lightweight row for lists (no traceback / request payloads)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_on: datetime
    level: str
    request_id: str | None
    status_code: int | None
    error_code: str | None
    exception_type: str | None
    message: str
    method: str | None
    path: str | None
    route: str | None
    environment: str | None


class ExceptionLogRead(AuditRead, ExceptionLogSummary):
    """Full row for the detail endpoint."""

    logger: str
    source: str | None
    traceback: str | None
    endpoint: str | None
    client_ip: str | None
    user_agent: str | None
    query_params: dict[str, Any] | None
    request_headers: dict[str, Any] | None
    request_body: dict[str, Any] | None
    details: Any = None
    hostname: str | None
    process_id: int | None
