"""Small helpers used by BaseService.search: one filter -> one SQL condition."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Boolean, ColumnElement, String, not_
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exceptions import UnprocessableEntityError
from app.schemas.search import TEXT_OPERATORS, FilterCondition, FilterOperator, SortDirection


@dataclass
class SearchResult:
    records: list[Any]
    total_count: int | None
    limit: int
    offset: int
    has_more: bool
    sort: list[tuple[str, SortDirection]]
    average_duration_ms: float | None = None


def invalid_search(message: str, loc: list[Any]) -> UnprocessableEntityError:
    return UnprocessableEntityError(
        message, error_code="invalid_filter", details=[{"loc": loc, "msg": message}]
    )


def escape_like(text: str) -> str:
    """Make % and _ in user input match literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@lru_cache(maxsize=64)
def _adapter(python_type: type) -> TypeAdapter:
    return TypeAdapter(python_type)


def _coerce(column: InstrumentedAttribute, value: Any, index: int) -> Any:
    """Convert a JSON value to the column's type (UUID, datetime, int, ...)."""
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        return value  # e.g. JSONB: compare as-is
    try:
        return _adapter(python_type).validate_python(value)
    except ValidationError:
        raise invalid_search(
            f"Expected a {python_type.__name__} value.", ["body", "filters", index, "value"]
        ) from None


def filter_condition(
    column: InstrumentedAttribute, flt: FilterCondition, index: int
) -> ColumnElement[bool]:
    op = flt.op

    if op == FilterOperator.IS_NULL:
        return column.is_(None) if flt.value else column.is_not(None)

    if op in TEXT_OPERATORS:
        if not isinstance(column.type, String):
            raise invalid_search(
                f"'{op}' only works on text fields.", ["body", "filters", index, "op"]
            )
        text = escape_like(flt.value)
        pattern = {
            FilterOperator.CONTAINS: f"%{text}%",
            FilterOperator.STARTS_WITH: f"{text}%",
            FilterOperator.ENDS_WITH: f"%{text}",
        }[op]
        return column.ilike(pattern, escape="\\")

    if op in (FilterOperator.IN, FilterOperator.NOT_IN):
        values = [_coerce(column, v, index) for v in flt.value]
        return column.in_(values) if op == FilterOperator.IN else not_(column.in_(values))

    if op == FilterOperator.BETWEEN:
        low, high = (_coerce(column, v, index) for v in flt.value)
        return column.between(low, high)

    value = _coerce(column, flt.value, index)
    if op == FilterOperator.EQ:
        return column == value
    if op == FilterOperator.NE:
        return column != value
    if isinstance(column.type, Boolean):
        raise invalid_search(
            f"'{op}' does not work on boolean fields.", ["body", "filters", index, "op"]
        )
    if op == FilterOperator.GT:
        return column > value
    if op == FilterOperator.GTE:
        return column >= value
    if op == FilterOperator.LT:
        return column < value
    if op == FilterOperator.LTE:
        return column <= value
    raise invalid_search(f"Unsupported filter operator '{op}'.", ["body", "filters", index, "op"])
