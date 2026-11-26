import logging
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import list_response, record_response
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.search import AUDIT_FIELDS, SearchConfig, run_search
from app.db.session import get_db
from app.models import Item
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.schemas.responses import ListResponse, RecordResponse

router = APIRouter(prefix="/items", tags=["items"])
logger = logging.getLogger(__name__)

ITEM_SEARCH = SearchConfig(
    model=Item,
    filterable=("name", "description", *AUDIT_FIELDS),
    sortable=("name", "created_on", "updated_on"),
    searchable=("name", "description"),
)
ItemSearchRequest = ITEM_SEARCH.request_model


async def _get_active_item(db: AsyncSession, item_id: uuid.UUID) -> Item:
    item = await db.get(Item, item_id)
    if item is None or item.is_deleted:
        raise NotFoundError("Item not found", details={"item_id": str(item_id)})
    return item


@router.get("", response_model=ListResponse[ItemRead])
async def list_items(
    limit: int = Query(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Simple paginated list (newest first). Use POST /items/search for filtering."""
    result = await run_search(db, ITEM_SEARCH, ItemSearchRequest(limit=limit, offset=offset))
    return list_response(result)


@router.post("/search", response_model=ListResponse[ItemRead])
async def search_items(payload: ItemSearchRequest, db: AsyncSession = Depends(get_db)):  # type: ignore[valid-type]
    """Filter, text-search, sort and paginate items."""
    return list_response(await run_search(db, ITEM_SEARCH, payload))


@router.post("", response_model=RecordResponse[ItemRead], status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    item = Item(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    logger.info("Item created", extra={"item_id": str(item.id)})
    return record_response(item)


@router.get("/{item_id}", response_model=RecordResponse[ItemRead])
async def get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return record_response(await _get_active_item(db, item_id))


@router.patch("/{item_id}", response_model=RecordResponse[ItemRead])
async def update_item(item_id: uuid.UUID, payload: ItemUpdate, db: AsyncSession = Depends(get_db)):
    item = await _get_active_item(db, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return record_response(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await _get_active_item(db, item_id)
    item.soft_delete()
    await db.commit()
    logger.info("Item soft-deleted", extra={"item_id": str(item_id)})
