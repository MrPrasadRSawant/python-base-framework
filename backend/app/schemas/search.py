"""Search request payload, shared by every POST /<resource>/search endpoint.

    {
      "search": "timeout",
      "filters": [
        {"field": "status_code", "op": "gte", "value": 500},
        {"field": "occurred_on", "op": "between", "value": ["2026-11-01", "2026-11-30"]}
      ],
      "sort": [{"field": "occurred_on", "direction": "desc"}],
      "limit": 20,
      "offset": 0
    }

Filters are combined with AND; ``search`` is a case-insensitive OR across the
table's ``search_fields``. Which fields can be filtered/sorted is decided by
each service (``filter_fields`` / ``sort_fields``); others get a 422.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings


class FilterOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"  # inclusive, value = [low, high]
    CONTAINS = "contains"  # case-insensitive, text fields only
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"  # value = true / false


TEXT_OPERATORS = {FilterOperator.CONTAINS, FilterOperator.STARTS_WITH, FilterOperator.ENDS_WITH}


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class FilterCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    op: FilterOperator = FilterOperator.EQ
    value: Any = None

    @model_validator(mode="after")
    def check_value_shape(self) -> "FilterCondition":
        op, value = self.op, self.value
        if op in (FilterOperator.IN, FilterOperator.NOT_IN):
            if not isinstance(value, list) or not value:
                raise ValueError(f"'{op}' needs a non-empty list value")
            if len(value) > settings.SEARCH_MAX_IN_VALUES:
                raise ValueError(f"'{op}' accepts at most {settings.SEARCH_MAX_IN_VALUES} values")
        elif op == FilterOperator.BETWEEN:
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError("'between' needs a [low, high] list value")
        elif op == FilterOperator.IS_NULL:
            if not isinstance(value, bool):
                raise ValueError("'is_null' needs a true/false value")
        elif value is None or isinstance(value, (list, dict)):
            raise ValueError(f"'{op}' needs a single non-null value (use is_null for nulls)")
        if op in TEXT_OPERATORS and not isinstance(value, str):
            raise ValueError(f"'{op}' needs a string value")
        return self


class SortField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    direction: SortDirection = SortDirection.ASC


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(
        None, max_length=200, description="Case-insensitive text across searchable fields"
    )
    filters: list[FilterCondition] = Field(
        default_factory=list, max_length=settings.SEARCH_MAX_FILTERS
    )
    sort: list[SortField] = Field(default_factory=list, max_length=5)
    limit: int = Field(settings.PAGINATION_DEFAULT_LIMIT, ge=1, le=settings.PAGINATION_MAX_LIMIT)
    offset: int = Field(0, ge=0)
    include_total: bool = Field(True, description="Run COUNT(*); disable for speed on big tables")
    include_deleted: bool = Field(False, description="Include soft-deleted records")
