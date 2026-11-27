"""Read-only access to the exception_log table.

Enabled only with EXCEPTION_LOG_API_ENABLED=true. It exposes request
metadata (redacted, but still internal), so put it behind admin auth before
enabling it anywhere but local development.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import error_responses, list_response, record_response
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.exception_log import ExceptionLogResponse
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.services.exception_log import ExceptionLogService

router = APIRouter(prefix="/exception-logs", tags=["exception logs"])


@router.get("", summary="List exception logs", response_model=ListResponse[ExceptionLogResponse])
async def list_exception_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `exception_logs:read`.

    Stored errors, most recent first: every API error response (status ≥
    `EXCEPTION_LOG_DB_MIN_STATUS`) and server exceptions. Messages and tracebacks are
    redacted; no request bodies or user data are stored.
    """
    result = await ExceptionLogService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post(
    "/search", summary="Search exception logs", response_model=ListResponse[ExceptionLogResponse]
)
async def search_exception_logs(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `exception_logs:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `request_id`, `status_code`, `error_code`, `exception_type`, `level`, `logger`, `method`, `path`, `route`, `endpoint`, `environment`, `hostname`, `occurred_on`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `occurred_on`, `created_on`, `status_code`, `error_code`, `exception_type` (default: `occurred_on` desc) |
    | `search` (text) | `message`, `path`, `exception_type`, `error_code` |

    Example, server errors only:
    `{"filters": [{"field": "status_code", "op": "gte", "value": 500}]}`
    """
    return list_response(await ExceptionLogService(db).search(payload))


@router.get(
    "/{log_id}",
    summary="Get an exception log",
    response_model=RecordResponse[ExceptionLogResponse],
    responses=error_responses((404, "`not_found`: no exception log with this id")),
)
async def get_exception_log(log_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `exception_logs:read`.

    One stored error, including the redacted traceback. To find the errors of a request,
    search with a `request_id` filter (the `X-Request-ID` the client received).
    """
    row = await ExceptionLogService(db).get(log_id)
    if row is None:
        raise NotFoundError("Exception log not found", details={"log_id": str(log_id)})
    return record_response(row)
