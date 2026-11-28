import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.core.request_context import SYSTEM_ACTOR
from app.schemas.base import CreateSchema, ResponseSchema

ActivityStatus = Literal["success", "failed"]


class UserActivityLogCreate(CreateSchema):
    """One activity row, built by app/core/activity_log.py. Append-only: no Update schema."""

    occurred_on: datetime
    actor: str = Field(max_length=255)
    actor_type: str = Field(max_length=16)
    actor_id: str | None = Field(None, max_length=64)
    action: str = Field(max_length=32)
    status: ActivityStatus = "success"
    entity_type: str | None = Field(None, max_length=64)
    entity_id: str | None = Field(None, max_length=64)
    changes: dict[str, Any] | None = None
    details: dict[str, Any] | None = None
    request_id: uuid.UUID | None = None
    method: str | None = Field(None, max_length=16)
    route: str | None = Field(None, max_length=512)
    ip_address: str | None = Field(None, max_length=64)
    user_agent: str | None = Field(None, max_length=512)
    # Captured during the request: the background writer runs outside it.
    created_by: str = Field(SYSTEM_ACTOR, max_length=255)


class UserActivityLogResponse(ResponseSchema):
    occurred_on: datetime = Field(description="When it happened (UTC)")
    actor: str = Field(
        description="Who: `user:<id>`, `service:<client_id>`, `system` or `anonymous`"
    )
    actor_type: str = Field(description="`user`, `service`, `system` or `anonymous`")
    actor_id: str | None = Field(description="User id or API client id; null for system")
    action: str = Field(
        description="`create`, `update`, `delete`, `restore`, `login`, `login_failed`, "
        "`logout`, `token_issued`, `client_auth_failed`, `session_revoked`, `access_denied`"
    )
    status: ActivityStatus = Field(description="`success`, or `failed` (refused attempts)")
    entity_type: str | None = Field(description="Table of the affected record, e.g. `users`")
    entity_id: str | None = Field(description="Id of the affected record")
    changes: dict[str, Any] | None = Field(
        description='Changed fields: `{"field": {"old": ..., "new": ...}}`. Sensitive '
        "values (password / secret / token hashes) are `[REDACTED]`."
    )
    details: dict[str, Any] | None = Field(description="Extra context, e.g. failure reason")
    request_id: uuid.UUID | None = Field(description="Request that did it (`requests.id`)")
    method: str | None
    route: str | None = Field(description="Route template, e.g. `/api/v1/users/{user_id}`")
    ip_address: str | None = Field(description="Client IP (first `X-Forwarded-For` hop)")
    user_agent: str | None
