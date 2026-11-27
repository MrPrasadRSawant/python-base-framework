from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.request_context import SYSTEM_ACTOR
from app.schemas.base import CreateSchema, ResponseSchema


class ExceptionLogCreate(CreateSchema):
    """One exception row, built by the logging handler and validated before insert.

    No ExceptionLogUpdate: the table is append-only.
    """

    occurred_on: datetime
    level: str = Field(max_length=20)
    logger: str = Field(max_length=255)
    source: str | None = Field(None, max_length=512)
    request_id: str | None = Field(None, max_length=128)
    status_code: int | None = None
    error_code: str | None = Field(None, max_length=100)
    exception_type: str | None = Field(None, max_length=255)
    message: str
    traceback: str | None = None
    method: str | None = Field(None, max_length=16)
    path: str | None = Field(None, max_length=2048)
    route: str | None = Field(None, max_length=512)
    endpoint: str | None = Field(None, max_length=512)
    details: Any = None
    environment: str | None = Field(None, max_length=50)
    hostname: str | None = Field(None, max_length=255)
    process_id: int | None = None
    # Captured when the error happens: the background writer runs outside the request.
    created_by: str = Field(SYSTEM_ACTOR, max_length=255)


class ExceptionLogResponse(ResponseSchema):
    occurred_on: datetime
    level: str
    logger: str
    source: str | None
    request_id: str | None
    status_code: int | None
    error_code: str | None
    exception_type: str | None
    message: str
    traceback: str | None
    method: str | None
    path: str | None
    route: str | None
    endpoint: str | None
    details: Any = None
    environment: str | None
    hostname: str | None
    process_id: int | None
