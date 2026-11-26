"""Standard response envelopes used by every resource endpoint.

    single record  {"metadata": {...}, "record": {...}}
    list / search  {"metadata": {...pagination...}, "records": [...]}
    error          {"metadata": {...}, "error": {...}}   (see schemas/error.py)

Every response, error or not, carries ``metadata.request_id``, the same id
as the ``X-Request-ID`` header and the ``exception_log`` table.
"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.schemas.search import SortDirection

T = TypeVar("T")


class ResponseMetadata(BaseModel):
    request_id: str | None = Field(None, description="Same as the X-Request-ID response header")
    timestamp: datetime = Field(description="When the response was generated (UTC)")


class AppliedSort(BaseModel):
    field: str
    direction: SortDirection


class ListMetadata(ResponseMetadata):
    limit: int = Field(description="Max records requested")
    offset: int = Field(description="Records skipped")
    count: int = Field(description="Records in this response")
    total_count: int | None = Field(
        description="Total matching records (null when include_total=false)"
    )
    has_more: bool = Field(description="True if more records exist after this page")
    next_offset: int | None = Field(description="Offset for the next page, null on the last")
    previous_offset: int | None = Field(
        description="Offset of the previous page, null on the first"
    )
    sort: list[AppliedSort] = Field(description="Ordering actually applied, tie-breaker included")


class RecordResponse(BaseModel, Generic[T]):
    metadata: ResponseMetadata
    record: T


class ListResponse(BaseModel, Generic[T]):
    metadata: ListMetadata
    records: list[T]
