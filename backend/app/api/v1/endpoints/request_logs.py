"""Read-only access to the request_logs table (endpoint monitoring).

Enabled only with REQUEST_LOG_API_ENABLED=true. It exposes internal traffic
data, so put it behind admin auth before enabling it anywhere but local
development.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import list_response, record_response
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.request_log import RequestLogResponse
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.services.request_log import RequestLogService

router = APIRouter(prefix="/request-logs", tags=["request logs"])


@router.get("", response_model=ListResponse[RequestLogResponse])
async def list_request_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await RequestLogService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post("/search", response_model=ListResponse[RequestLogResponse])
async def search_request_logs(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    return list_response(await RequestLogService(db).search(payload))


@router.get("/{log_id}", response_model=RecordResponse[RequestLogResponse])
async def get_request_log(log_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await RequestLogService(db).get(log_id)
    if row is None:
        raise NotFoundError("Request log not found", details={"log_id": str(log_id)})
    return record_response(row)
