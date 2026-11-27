"""Read-only access to the requests table (endpoint monitoring, reports).

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
from app.schemas.request_report import RequestReport, RequestReportSummary
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.services.request_log import RequestLogService
from app.services.request_report import RequestReportService

router = APIRouter(prefix="/requests", tags=["requests"])


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


@router.get("/{request_id}", response_model=RecordResponse[RequestLogResponse])
async def get_request_log(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """One request by its id (the X-Request-ID / metadata.request_id value)."""
    row = await RequestLogService(db).get(request_id)
    if row is None:
        raise NotFoundError("Request not found", details={"request_id": str(request_id)})
    return record_response(row)


# ------------------------------------------------------------- developer report
@router.post("/report", response_model=ListResponse[RequestReportSummary])
async def report_requests(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Requests with outcome, failure reason and slowest service.

    Same filters / sort / paging as POST /requests/search, e.g. only failures:
    ``{"filters": [{"field": "status_code", "op": "gte", "value": 400}]}``
    """
    return list_response(await RequestReportService(db).list_reports(payload))


@router.get("/{request_id}/report", response_model=RecordResponse[RequestReport])
async def report_request(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Drill-down for one request: outcome, failure reason, every service call with
    its own time and share of the request, the slowest step, and time spent
    outside services. Rows arrive ~1 s after a request ends."""
    report = await RequestReportService(db).get_report(request_id)
    if report is None:
        raise NotFoundError("Request not found", details={"request_id": str(request_id)})
    return record_response(report)
