import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.request_context import SYSTEM_ACTOR
from app.schemas.base import CreateSchema, ResponseSchema

CallStatus = Literal["success", "failed"]


class ServiceCallLogCreate(CreateSchema):
    """One service call, built by @track_service. No Update schema: append-only."""

    request_id: uuid.UUID | None = None
    call_order: int | None = None
    parent_call_order: int | None = None
    service_name: str = Field(max_length=255)
    started_on: datetime
    duration_ms: float = Field(ge=0)
    status: CallStatus
    error_type: str | None = Field(None, max_length=255)
    # Captured during the call: the background writer runs outside the request.
    created_by: str = Field(SYSTEM_ACTOR, max_length=255)


class ServiceCallLogResponse(ResponseSchema):
    request_id: uuid.UUID | None
    call_order: int | None
    parent_call_order: int | None
    service_name: str
    started_on: datetime
    duration_ms: float
    status: str
    error_type: str | None
