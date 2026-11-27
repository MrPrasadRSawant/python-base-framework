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
from app.db.session import get_db
from app.schemas.exception_log import ExceptionLogResponse
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.services.exception_log import ExceptionLogService

router = APIRouter(prefix="/exception-logs", tags=["exception logs"])


@router.get("", response_model=ListResponse[ExceptionLogResponse])
async def list_exception_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await ExceptionLogService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post("/search", response_model=ListResponse[ExceptionLogResponse])
async def search_exception_logs(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    return list_response(await ExceptionLogService(db).search(payload))


@router.get("/{log_id}", response_model=RecordResponse[ExceptionLogResponse])
async def get_exception_log(log_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await ExceptionLogService(db).get(log_id)
    if row is None:
        raise NotFoundError("Exception log not found", details={"log_id": str(log_id)})
    return record_response(row)
