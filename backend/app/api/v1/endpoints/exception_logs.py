"""Read-only access to the exception_log table.

Enabled only with EXCEPTION_LOG_API_ENABLED=true. It exposes request
metadata (redacted, but still internal), so put it behind admin auth before
enabling it anywhere but local development.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import list_response, record_response
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.search import AUDIT_FIELDS, SearchConfig, run_search
from app.db.session import get_db
from app.models import ExceptionLog
from app.schemas.exception_log import ExceptionLogRead, ExceptionLogSummary
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SortDirection

router = APIRouter(prefix="/exception-logs", tags=["exception logs"])

EXCEPTION_LOG_SEARCH = SearchConfig(
    model=ExceptionLog,
    filterable=(
        "request_id", "status_code", "error_code", "exception_type", "level", "logger",
        "method", "path", "route", "endpoint", "client_ip", "environment", "hostname",
        "occurred_on", *AUDIT_FIELDS,
    ),  # fmt: skip
    sortable=("occurred_on", "created_on", "status_code", "error_code", "exception_type"),
    searchable=("message", "path", "exception_type", "error_code", "request_id"),
    default_sort=(("occurred_on", SortDirection.DESC),),
)
ExceptionLogSearchRequest = EXCEPTION_LOG_SEARCH.request_model


@router.get("", response_model=ListResponse[ExceptionLogSummary])
async def list_exception_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    request = ExceptionLogSearchRequest(limit=limit, offset=offset)
    return list_response(await run_search(db, EXCEPTION_LOG_SEARCH, request))


@router.post("/search", response_model=ListResponse[ExceptionLogSummary])
async def search_exception_logs(
    payload: ExceptionLogSearchRequest,  # type: ignore[valid-type]
    db: AsyncSession = Depends(get_db),
):
    return list_response(await run_search(db, EXCEPTION_LOG_SEARCH, payload))


@router.get("/{log_id}", response_model=RecordResponse[ExceptionLogRead])
async def get_exception_log(log_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(ExceptionLog, log_id)
    if row is None or row.is_deleted:
        raise NotFoundError("Exception log not found", details={"log_id": str(log_id)})
    return record_response(row)
