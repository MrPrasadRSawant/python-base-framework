"""Generic CRUD + search for one table.

Subclass it, point it at a model and list which fields may be used:

    class OrderService(BaseService):
        model = Order
        filter_fields = ("reference", "total", *AUDIT_FIELDS)
        sort_fields = ("total", "created_on")
        search_fields = ("reference",)

    service = OrderService(db)
    order = await service.create(OrderCreate(...))
    order = await service.get(order_id)
    order = await service.update(order_id, OrderUpdate(...))
    deleted = await service.delete(order_id)
    result = await service.search(SearchRequest(...))
"""

import uuid
from typing import Any

from sqlalchemy import Select, String, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.service_tracking import track_service
from app.db.search import SearchResult, escape_like, filter_condition, invalid_search
from app.schemas.base import CreateSchema, UpdateSchema
from app.schemas.search import SearchRequest, SortDirection

# Common columns every table can filter on.
AUDIT_FIELDS = ("id", "created_by", "created_on", "updated_by", "updated_on")


class BaseService:
    model: Any
    filter_fields: tuple[str, ...] = AUDIT_FIELDS
    sort_fields: tuple[str, ...] = ("created_on",)
    search_fields: tuple[str, ...] = ()
    default_sort: tuple[tuple[str, SortDirection], ...] = (("created_on", SortDirection.DESC),)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Catch typos in the field lists when the app starts, not on first request.
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "model"):
            return  # an intermediate base without a table
        names = {*cls.filter_fields, *cls.sort_fields, *cls.search_fields}
        names |= {name for name, _ in cls.default_sort}
        missing = sorted(name for name in names if not hasattr(cls.model, name))
        if missing:
            raise TypeError(f"{cls.__name__}: {cls.model.__name__} has no field(s) {missing}")
        not_text = [
            f for f in cls.search_fields if not isinstance(getattr(cls.model, f).type, String)
        ]
        if not_text:
            raise TypeError(f"{cls.__name__}: search_fields must be text columns, not {not_text}")

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ CRUD
    @track_service
    async def get(self, record_id: uuid.UUID, *, include_deleted: bool = False) -> Any | None:
        record = await self.db.get(self.model, record_id)
        if record is None or (record.is_deleted and not include_deleted):
            return None
        return record

    @track_service
    async def create(self, data: CreateSchema) -> Any:
        record = self.model(**data.model_dump())
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    @track_service
    async def create_many(self, items: list[CreateSchema]) -> None:
        self.db.add_all([self.model(**item.model_dump()) for item in items])
        await self.db.commit()

    @track_service
    async def update(self, record_id: uuid.UUID, data: UpdateSchema) -> Any | None:
        """Apply only the fields the client sent. Returns None if not found."""
        record = await self.get(record_id)
        if record is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    @track_service
    async def delete(self, record_id: uuid.UUID) -> bool:
        """Soft delete. Returns False if not found."""
        record = await self.get(record_id)
        if record is None:
            return False
        record.soft_delete()
        await self.db.commit()
        return True

    # ---------------------------------------------------------------- search
    @track_service
    async def search(self, request: SearchRequest) -> SearchResult:
        query, sort = self.build_query(request)

        total = None
        if request.include_total:
            count_query = select(func.count()).select_from(query.subquery())
            total = (await self.db.execute(count_query)).scalar_one()

        order_by = [
            getattr(self.model, f).desc() if d == SortDirection.DESC else getattr(self.model, f)
            for f, d in sort
        ]
        # Fetch one extra row to know whether another page exists.
        page = query.order_by(*order_by).limit(request.limit + 1).offset(request.offset)
        rows = list((await self.db.scalars(page)).all())

        return SearchResult(
            records=rows[: request.limit],
            total_count=total,
            limit=request.limit,
            offset=request.offset,
            has_more=len(rows) > request.limit,
            sort=sort,
        )

    def build_query(self, request: SearchRequest) -> tuple[Select, list[tuple[str, SortDirection]]]:
        """Filtered SELECT (no ordering/paging) plus the sort to apply."""
        conditions = []
        for i, flt in enumerate(request.filters):
            if flt.field not in self.filter_fields:
                raise invalid_search(
                    f"Cannot filter on '{flt.field}'.", ["body", "filters", i, "field"]
                )
            conditions.append(filter_condition(getattr(self.model, flt.field), flt, i))

        if not request.include_deleted:
            conditions.append(self.model.is_deleted.is_(False))

        text = (request.search or "").strip()
        if text and self.search_fields:
            pattern = f"%{escape_like(text)}%"
            conditions.append(
                or_(
                    *(
                        getattr(self.model, f).ilike(pattern, escape="\\")
                        for f in self.search_fields
                    )
                )
            )

        query = select(self.model)
        if conditions:
            query = query.where(and_(*conditions))

        for i, s in enumerate(request.sort):
            if s.field not in self.sort_fields:
                raise invalid_search(f"Cannot sort on '{s.field}'.", ["body", "sort", i, "field"])
        sort = [(s.field, s.direction) for s in request.sort] or list(self.default_sort)
        # Always end with id so rows never repeat or go missing between pages.
        if all(field != "id" for field, _ in sort):
            sort.append(("id", SortDirection.ASC))
        return query, sort
