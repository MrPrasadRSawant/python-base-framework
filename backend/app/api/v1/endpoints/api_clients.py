"""API clients: server-side integrations using OAuth2 client credentials.
Reading needs api_clients:read; changes need api_clients:manage.

The client secret is returned only by create and rotate-secret; only its hash
is stored. You can only grant a client permissions you hold yourself.

Disabling, deleting or rotating stops new tokens immediately; a token already
issued stays valid until it expires (SERVICE_TOKEN_TTL_MINUTES).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import PROTECTED, error_responses, list_response, record_response
from app.api.v1.access import ensure_can_grant, resolve_permissions
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.security import Principal, require_permission
from app.core.security.permissions import Perm
from app.db.session import get_db
from app.models import ApiClient
from app.schemas.api_client import (
    ApiClientCreate,
    ApiClientDetailResponse,
    ApiClientResponse,
    ApiClientUpdate,
    ApiClientWithSecretResponse,
)
from app.schemas.rbac import AssignPermissions
from app.schemas.responses import ListResponse, RecordResponse
from app.schemas.search import SearchRequest
from app.services.api_client import ApiClientService
from app.services.api_client_permission import ApiClientPermissionService
from app.services.permission import PermissionService

router = APIRouter(prefix="/api-clients", tags=["api clients"])

can_read = require_permission(Perm.API_CLIENTS_READ)
can_manage = require_permission(Perm.API_CLIENTS_MANAGE)


async def _get_client(db: AsyncSession, record_id: uuid.UUID) -> ApiClient:
    client = await ApiClientService(db).get(record_id)
    if client is None:
        raise NotFoundError("API client not found", details={"api_client_id": str(record_id)})
    return client


async def _detail(db: AsyncSession, client: ApiClient, **extra) -> dict:
    return {
        **ApiClientResponse.model_validate(client).model_dump(),
        "permissions": await PermissionService(db).codes_for_api_client(client.id),
        **extra,
    }


NOT_FOUND = (404, "`not_found`: no API client with this id (or deleted)")
CANNOT_GRANT = (403, "`forbidden` or `cannot_grant` (granting a permission you don't hold)")
UNKNOWN_PERMS = (422, "`unknown_permissions`: a permission code does not exist")


@router.get(
    "",
    summary="List API clients",
    response_model=ListResponse[ApiClientResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def list_api_clients(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `api_clients:read`.

    Registered integrations, newest first. Secrets are never returned.
    `last_used_on` shows when the client last got a token.
    """
    result = await ApiClientService(db).search(SearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post(
    "/search",
    summary="Search API clients",
    response_model=ListResponse[ApiClientResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED),
)
async def search_api_clients(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `api_clients:read`.

    | Option | Fields |
    |---|---|
    | `filters` | `client_id`, `name`, `is_active`, `expires_on`, `last_used_on`, `id`, `created_by`, `created_on`, `updated_by`, `updated_on` |
    | `sort` | `name`, `created_on`, `last_used_on`, `expires_on` (default: `created_on` desc) |
    | `search` (text) | `client_id`, `name`, `description` |
    """
    return list_response(await ApiClientService(db).search(payload))


@router.get(
    "/{api_client_id}",
    summary="Get an API client",
    response_model=RecordResponse[ApiClientDetailResponse],
    dependencies=[Depends(can_read)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def get_api_client(api_client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `api_clients:read`.

    One client with its `permissions` (the scopes put into its tokens).
    """
    return record_response(await _detail(db, await _get_client(db, api_client_id)))


@router.post(
    "",
    summary="Register an API client",
    response_model=RecordResponse[ApiClientWithSecretResponse],
    status_code=201,
    responses=error_responses(401, CANNOT_GRANT, UNKNOWN_PERMS),
)
async def create_api_client(
    payload: ApiClientCreate,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `api_clients:manage`.

    Registers a server-side integration and returns its credentials:
    - `client_id`: public identifier (`cli_...`).
    - `client_secret`: **shown only in this response**; store it in the integration's
      secret store. It cannot be read again; use rotate-secret if it is lost.

    Options: `permissions` (codes the client's tokens will carry; you can only grant
    permissions you hold), `allowed_ips` (IPs / CIDRs allowed to request tokens;
    `null` = any), `expires_on` (`null` = never).

    The integration then calls `POST /auth/token` with `grant_type=client_credentials`.
    """
    perms = await resolve_permissions(db, payload.permissions)
    ensure_can_grant(principal, (p.code for p in perms))
    client, secret = await ApiClientService(db).register(
        name=payload.name,
        description=payload.description,
        allowed_ips=payload.allowed_ips,
        expires_on=payload.expires_on,
    )
    if perms:
        await ApiClientPermissionService(db).replace_for_client(client.id, (p.id for p in perms))
    return record_response(await _detail(db, client, client_secret=secret))


@router.patch(
    "/{api_client_id}",
    summary="Update an API client",
    response_model=RecordResponse[ApiClientDetailResponse],
    dependencies=[Depends(can_manage)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def update_api_client(
    api_client_id: uuid.UUID, payload: ApiClientUpdate, db: AsyncSession = Depends(get_db)
):
    """**Access:** Permission `api_clients:manage`.

    Partial update: `name`, `description`, `is_active`, `allowed_ips`, `expires_on`
    (send `null` to clear the last two). `is_active: false` blocks new tokens at once;
    tokens already issued expire within `SERVICE_TOKEN_TTL_MINUTES`.
    """
    client = await ApiClientService(db).update(api_client_id, payload)
    if client is None:
        raise NotFoundError("API client not found", details={"api_client_id": str(api_client_id)})
    return record_response(await _detail(db, client))


@router.put(
    "/{api_client_id}/permissions",
    summary="Set an API client's permissions",
    response_model=RecordResponse[ApiClientDetailResponse],
    responses=error_responses(401, CANNOT_GRANT, NOT_FOUND, UNKNOWN_PERMS),
)
async def set_api_client_permissions(
    api_client_id: uuid.UUID,
    payload: AssignPermissions,
    principal: Principal = Depends(can_manage),
    db: AsyncSession = Depends(get_db),
):
    """**Access:** Permission `api_clients:manage`.

    **Replaces** the client's permissions with exactly this list (`[]` removes all).
    Adding or removing a permission requires holding it yourself. Applies from the
    client's next token.
    """
    client = await _get_client(db, api_client_id)
    perms = await resolve_permissions(db, payload.permissions)
    current = await PermissionService(db).codes_for_api_client(client.id)
    ensure_can_grant(principal, set(current) ^ {p.code for p in perms})
    await ApiClientPermissionService(db).replace_for_client(client.id, (p.id for p in perms))
    return record_response(await _detail(db, client))


@router.post(
    "/{api_client_id}/rotate-secret",
    summary="Rotate an API client's secret",
    response_model=RecordResponse[ApiClientWithSecretResponse],
    dependencies=[Depends(can_manage)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def rotate_api_client_secret(api_client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `api_clients:manage`.

    Issues a new `client_secret`, **shown only in this response**. The old secret stops
    working immediately, so update the integration right away. Tokens already issued
    stay valid until they expire.
    """
    client = await _get_client(db, api_client_id)
    secret = await ApiClientService(db).rotate_secret(client)
    return record_response(await _detail(db, client, client_secret=secret))


@router.delete(
    "/{api_client_id}",
    summary="Delete an API client",
    status_code=204,
    dependencies=[Depends(can_manage)],
    responses=error_responses(*PROTECTED, NOT_FOUND),
)
async def delete_api_client(api_client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """**Access:** Permission `api_clients:manage`.

    Removes the client: it can no longer get tokens. Tokens already issued expire within
    `SERVICE_TOKEN_TTL_MINUTES`.
    """
    if not await ApiClientService(db).delete(api_client_id):
        raise NotFoundError("API client not found", details={"api_client_id": str(api_client_id)})
