"""Read-only access to the user activity log (audit trail).

Mounted only with ENABLE_USER_ACTIVITY_LOG=true; every route needs
user_activity_logs:read (applied in api/v1/router.py). Rows are written by
app/core/activity_log.py, never through this API.
"""

import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import error_responses, list_response, record_response
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import FilterCondition, SearchRequest, SortDirection, SortField
from app.schemas.user_activity_log import UserActivityLogResponse
from app.services.user_activity_log import UserActivityLogService

router = APIRouter(prefix="/user-activity-logs", tags=["user activity logs"])


@router.get(
    "", summary="List user activity", response_model=ListResponse[UserActivityLogResponse]
)
async def list_user_activity_logs(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `user_activity_logs:read`.

    Every recorded action, most recent first: data changes (`create`, `update`,
    `delete`, `restore` of any record, with before/after values) and security events
    (`login`, `login_failed`, `logout`, `token_issued`, `client_auth_failed`,
    `session_revoked`, `access_denied`). Use `POST /user-activity-logs/search` to filter.
    """
    result = await UserActivityLogService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post(
    "/search", summary="Search user activity", response_model=ListResponse[UserActivityLogResponse]
)
async def search_user_activity_logs(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `user_activity_logs:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `occurred_on`, `actor`, `actor_type`, `actor_id`, `action`, `status`, `entity_type`, `entity_id`, `request_id`, `method`, `route`, `ip_address`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `occurred_on`, `action`, `actor`, `entity_type`, `status` (default: `occurred_on` desc) |
    | `search` (text) | `actor`, `action`, `entity_type`, `entity_id`, `route`, `ip_address`, request ID (partial match) |

    Examples:
    - Who changed anything on a day: `{"filters": [{"field": "occurred_on", "op": "between",
      "value": ["2026-11-27T00:00:00Z", "2026-11-28T00:00:00Z"]}, {"field": "action", "op": "in",
      "value": ["create", "update", "delete", "restore"]}]}`
    - Everything one user did: `{"filters": [{"field": "actor_id", "value": "<user id>"}]}`
    - Refused attempts: `{"filters": [{"field": "status", "value": "failed"}]}`
    """
    return list_response(await UserActivityLogService(db).search(payload))


@router.get(
    "/entities/{entity_type}/{entity_id}",
    summary="History of one record",
    response_model=ListResponse[UserActivityLogResponse],
)
async def record_history(
    entity_type: str = Path(max_length=64, description="Table name, e.g. `users`"),
    entity_id: str = Path(max_length=64, description="The record's id"),
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `user_activity_logs:read`.

    Every change ever made to one record, newest first, with who made it, from where,
    and the before/after values: e.g. `/user-activity-logs/entities/users/<user id>`.
    Includes security events about the record (a user's sign-ins, failed sign-ins).
    """
    request = SearchRequest(
        filters=[
            FilterCondition(field="entity_type", value=entity_type),
            FilterCondition(field="entity_id", value=entity_id),
        ],
        sort=[SortField(field="occurred_on", direction=SortDirection.DESC)],
        limit=limit,
        offset=offset,
    )
    return list_response(await UserActivityLogService(db).search(request))


@router.get(
    "/{log_id}",
    summary="Get one activity",
    response_model=RecordResponse[UserActivityLogResponse],
    responses=error_responses((404, "`not_found`: no activity with this id")),
)
async def get_user_activity_log(log_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `user_activity_logs:read`.

    One activity with its full `changes` and `details`. Join on `request_id` with
    `GET /requests/{request_id}/report` to see everything that request did.
    """
    row = await UserActivityLogService(db).get(log_id)
    if row is None:
        raise NotFoundError("Activity not found", details={"log_id": str(log_id)})
    return record_response(row)
