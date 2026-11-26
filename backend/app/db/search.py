"""Generic filter / search / sort / paginate for any model.

Each resource declares a ``SearchConfig`` (which columns may be filtered,
sorted, text-searched) and calls ``run_search``. Guarantees:

* Only allow-listed columns are reachable (no arbitrary column access).
* Filter values are coerced to the column's Python type (UUID, datetime, int...).
  A bad value -> 422 with the failing filter's position.
* LIKE wildcards in user input are escaped (``%`` / ``_`` match literally).
* Ordering is always deterministic: ``id`` is appended as a tie-breaker, so
  rows never repeat or go missing between pages.
* ``has_more`` comes from fetching ``limit + 1`` rows, so it's correct even
  with ``include_total=false`` (no COUNT query).
* Soft-deleted rows are excluded unless ``include_deleted`` is set.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import ColumnElement, Select, String, and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exceptions import UnprocessableEntityError
from app.schemas.search import (
    LIST_OPERATORS,
    FilterCondition,
    FilterOperator,
    SearchRequest,
    SortDirection,
    build_search_request,
)

# Audit columns every AuditMixin table can filter/sort on.
AUDIT_FIELDS: tuple[str, ...] = (
    "id",
    "created_by",
    "created_on",
    "updated_by",
    "updated_on",
)


@dataclass(frozen=True)
class SearchConfig:
    model: type
    filterable: tuple[str, ...]
    sortable: tuple[str, ...]
    searchable: tuple[str, ...] = ()
    default_sort: tuple[tuple[str, SortDirection], ...] = (("created_on", SortDirection.DESC),)
    tie_breaker: str = "id"
    request_model: type[SearchRequest] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Fail fast at import time on typos in the allow-lists.
        names = {*self.filterable, *self.sortable, *self.searchable, self.tie_breaker}
        names |= {name for name, _ in self.default_sort}
        missing = sorted(n for n in names if not hasattr(self.model, n))
        if missing:
            raise ValueError(f"{self.model.__name__} has no column(s): {missing}")
        for name in self.searchable:
            if not isinstance(self.column(name).type, String):
                raise ValueError(f"searchable field {name!r} must be a text column")
        object.__setattr__(
            self,
            "request_model",
            build_search_request(
                self.model.__name__, filterable=self.filterable, sortable=self.sortable
            ),
        )

    def column(self, name: str) -> InstrumentedAttribute:
        return getattr(self.model, name)

    @property
    def soft_deletable(self) -> bool:
        return hasattr(self.model, "is_deleted")


@dataclass
class SearchResult:
    records: list[Any]
    total_count: int | None
    limit: int
    offset: int
    has_more: bool
    sort: list[tuple[str, SortDirection]]


# ------------------------------------------------------------------ helpers
@lru_cache(maxsize=64)
def _adapter(python_type: type) -> TypeAdapter:
    return TypeAdapter(python_type)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _coerce(column: InstrumentedAttribute, value: Any, index: int) -> Any:
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        return value  # e.g. JSONB: compare as-is
    try:
        return _adapter(python_type).validate_python(value)
    except ValidationError as exc:
        raise UnprocessableEntityError(
            "Invalid filter value.",
            error_code="invalid_filter",
            details=[
                {
                    "loc": ["body", "filters", index, "value"],
                    "msg": f"Expected {python_type.__name__}: {exc.errors()[0]['msg']}",
                }
            ],
        ) from None


def _condition(config: SearchConfig, flt: FilterCondition, index: int) -> ColumnElement[bool]:
    column = config.column(flt.field)
    op = flt.op

    if op == FilterOperator.IS_NULL:
        return column.is_(None) if flt.value else column.is_not(None)

    if op in (FilterOperator.CONTAINS, FilterOperator.STARTS_WITH, FilterOperator.ENDS_WITH):
        if not isinstance(column.type, String):
            raise UnprocessableEntityError(
                f"'{op}' only works on text fields.",
                error_code="invalid_filter",
                details=[{"loc": ["body", "filters", index, "op"], "msg": "text fields only"}],
            )
        text = _escape_like(flt.value)
        pattern = {
            FilterOperator.CONTAINS: f"%{text}%",
            FilterOperator.STARTS_WITH: f"{text}%",
            FilterOperator.ENDS_WITH: f"%{text}",
        }[op]
        return column.ilike(pattern, escape="\\")

    if op in LIST_OPERATORS:
        values = [_coerce(column, v, index) for v in flt.value]
        return column.in_(values) if op == FilterOperator.IN else not_(column.in_(values))

    if op == FilterOperator.BETWEEN:
        low, high = (_coerce(column, v, index) for v in flt.value)
        return column.between(low, high)

    value = _coerce(column, flt.value, index)
    return {
        FilterOperator.EQ: column == value,
        FilterOperator.NE: column != value,
        FilterOperator.GT: column > value,
        FilterOperator.GTE: column >= value,
        FilterOperator.LT: column < value,
        FilterOperator.LTE: column <= value,
    }[op]


def _resolve_sort(config: SearchConfig, request: SearchRequest) -> list[tuple[str, SortDirection]]:
    sort = [(s.field, s.direction) for s in request.sort] or list(config.default_sort)
    seen: set[str] = set()
    unique = [(f, d) for f, d in sort if not (f in seen or seen.add(f))]
    if config.tie_breaker not in seen:
        unique.append((config.tie_breaker, SortDirection.ASC))
    return unique


def build_statement(
    config: SearchConfig, request: SearchRequest, base: Select | None = None
) -> tuple[Select, list[tuple[str, SortDirection]]]:
    """Filtered, unpaginated, unordered SELECT plus the sort to apply."""
    stmt = base if base is not None else select(config.model)
    conditions = [_condition(config, f, i) for i, f in enumerate(request.filters)]

    if config.soft_deletable and not request.include_deleted:
        conditions.append(config.model.is_deleted.is_(False))

    if request.search and request.search.strip() and config.searchable:
        pattern = f"%{_escape_like(request.search.strip())}%"
        conditions.append(
            or_(*(config.column(n).ilike(pattern, escape="\\") for n in config.searchable))
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt, _resolve_sort(config, request)


async def run_search(
    db: AsyncSession, config: SearchConfig, request: SearchRequest, base: Select | None = None
) -> SearchResult:
    stmt, sort = build_statement(config, request, base)

    total = None
    if request.include_total:
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await db.execute(count_stmt)).scalar_one()

    order_by = [
        config.column(f).desc() if d == SortDirection.DESC else config.column(f).asc()
        for f, d in sort
    ]
    page_stmt = stmt.order_by(*order_by).limit(request.limit + 1).offset(request.offset)
    rows = list((await db.scalars(page_stmt)).all())

    has_more = len(rows) > request.limit
    return SearchResult(
        records=rows[: request.limit],
        total_count=total,
        limit=request.limit,
        offset=request.offset,
        has_more=has_more,
        sort=sort,
    )
