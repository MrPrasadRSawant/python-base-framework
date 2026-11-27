"""Read-only access to the service_call_logs table (service load monitoring).

Enabled only with SERVICE_CALL_LOG_API_ENABLED=true. Internal data: put it
behind admin auth before enabling it anywhere but local development.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import error_responses, list_response, record_response
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.schemas.service_call_log import ServiceCallLogResponse
from app.services.service_call_log import ServiceCallLogService

router = APIRouter(prefix="/service-call-logs", tags=["service call logs"])


@router.get(
    "", summary="List service call logs", response_model=ListResponse[ServiceCallLogResponse]
)
async def list_service_call_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `service_call_logs:read`.

    One row per tracked service call (name, order within the request, duration,
    success / failure), most recent first. Arguments and results are never stored.
    """
    result = await ServiceCallLogService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post(
    "/search",
    summary="Search service call logs",
    response_model=ListResponse[ServiceCallLogResponse],
)
async def search_service_call_logs(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `service_call_logs:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `request_id`, `call_order`, `parent_call_order`, `service_name`, `started_on`, `duration_ms`, `status`, `error_type`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `started_on`, `call_order`, `duration_ms`, `service_name` (default: `started_on` desc) |
    | `search` (text) | `service_name`, `error_type` |

    Example, the calls of one request in order:
    `{"filters": [{"field": "request_id", "value": "<uuid>"}], "sort": [{"field": "call_order"}]}`
    """
    return list_response(await ServiceCallLogService(db).search(payload))


@router.get(
    "/{log_id}",
    summary="Get a service call log",
    response_model=RecordResponse[ServiceCallLogResponse],
    responses=error_responses((404, "`not_found`: no service call log with this id")),
)
async def get_service_call_log(log_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `service_call_logs:read`.

    One tracked service call.
    """
    row = await ServiceCallLogService(db).get(log_id)
    if row is None:
        raise NotFoundError("Service call log not found", details={"log_id": str(log_id)})
    return record_response(row)
