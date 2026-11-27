from datetime import datetime

from pydantic import Field

from app.core.request_context import SYSTEM_ACTOR
from app.schemas.base import CreateSchema, ResponseSchema


class RequestLogCreate(CreateSchema):
    """One request row, built from the access log line. No RequestLogUpdate: append-only."""

    started_on: datetime
    request_id: str = Field(max_length=128)
    method: str = Field(max_length=16)
    route: str | None = Field(None, max_length=512)
    endpoint: str | None = Field(None, max_length=512)
    status_code: int
    duration_ms: float = Field(ge=0)
    # Captured during the request: the background writer runs outside it.
    created_by: str = Field(SYSTEM_ACTOR, max_length=255)


class RequestLogResponse(ResponseSchema):
    started_on: datetime
    request_id: str
    method: str
    route: str | None
    endpoint: str | None
    status_code: int
    duration_ms: float
