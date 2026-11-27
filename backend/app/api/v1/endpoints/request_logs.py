"""Read-only access to the requests table (endpoint monitoring, reports).

Enabled only with REQUEST_LOG_API_ENABLED=true. It exposes internal traffic
data, so put it behind admin auth before enabling it anywhere but local
development.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import error_responses, list_response, record_response
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


NOT_FOUND = (404, "`not_found`: no request with this id (or not written yet, ~1 s after it ends)")


@router.get("", summary="List requests", response_model=ListResponse[RequestLogResponse])
async def list_request_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `request_logs:read`.

    One row per HTTP request, most recent first: method, route template, handler,
    status, duration and the caller (`created_by`: `user:<id>`, `service:<client_id>` or
    `system`). No URLs, bodies, headers or IPs are stored.
    """
    result = await RequestLogService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post("/search", summary="Search requests", response_model=ListResponse[RequestLogResponse])
async def search_request_logs(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `request_logs:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `method`, `route`, `endpoint`, `status_code`, `duration_ms`, `started_on`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `started_on`, `duration_ms`, `status_code`, `route` (default: `started_on` desc) |
    | `search` (text) | `route`, `endpoint` |

    Example, slow requests: `{"filters": [{"field": "duration_ms", "op": "gte", "value": 1000}]}`
    """
    return list_response(await RequestLogService(db).search(payload))


@router.get(
    "/{request_id}",
    summary="Get a request",
    response_model=RecordResponse[RequestLogResponse],
    responses=error_responses(NOT_FOUND),
)
async def get_request_log(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `request_logs:read`.

    One request by its id: the `X-Request-ID` header / `metadata.request_id` the client
    received.
    """
    row = await RequestLogService(db).get(request_id)
    if row is None:
        raise NotFoundError("Request not found", details={"request_id": str(request_id)})
    return record_response(row)


# ------------------------------------------------------------- developer report
@router.post(
    "/report",
    summary="Report: requests with outcome",
    response_model=ListResponse[RequestReportSummary],
)
async def report_requests(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `request_logs:read`.

    Requests with their outcome (`success` / `failed`), failure reason (from the
    exception log) and slowest service call. Same filters, sort and paging as
    `POST /requests/search`. Example, failures only:
    `{"filters": [{"field": "status_code", "op": "gte", "value": 400}]}`
    """
    return list_response(await RequestReportService(db).list_reports(payload))


@router.get(
    "/{request_id}/report",
    summary="Report: one request drill-down",
    response_model=RecordResponse[RequestReport],
    responses=error_responses(NOT_FOUND),
)
async def report_request(request_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `request_logs:read`.

    Everything about one request: outcome and failure reason, every service call nested
    under its caller with total time, own time and % of the request, the slowest step,
    and time spent outside services. Log rows arrive about 1 second after a request
    ends, so a report fetched immediately may be incomplete.
    """
    report = await RequestReportService(db).get_report(request_id)
    if report is None:
        raise NotFoundError("Request not found", details={"request_id": str(request_id)})
    return record_response(report)
