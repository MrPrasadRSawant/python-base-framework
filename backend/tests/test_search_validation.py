"""Search payload validation and SQL generation. No database needed:
everything here is rejected (or built) before a query runs."""

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.schemas.search import SearchRequest
from app.services.exception_log import ExceptionLogService

URL = "/api/v1/exception-logs"


def _post(client, payload):
    return client.post(f"{URL}/search", json=payload)


def test_unknown_filter_field_rejected(client):
    r = _post(client, {"filters": [{"field": "password_hash", "op": "eq", "value": "x"}]})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "invalid_filter"
    assert body["error"]["details"][0]["loc"] == ["body", "filters", 0, "field"]
    assert body["metadata"]["request_id"] == r.headers[settings.REQUEST_ID_HEADER]


def test_column_not_in_filter_fields_rejected(client):
    # traceback is a real column, but not in ExceptionLogService.filter_fields
    r = _post(client, {"filters": [{"field": "traceback", "op": "eq", "value": "x"}]})
    assert r.status_code == 422


def test_unknown_sort_field_and_extra_keys_rejected(client):
    r = _post(client, {"sort": [{"field": "secret"}]})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["loc"] == ["body", "sort", 0, "field"]
    assert _post(client, {"page": 2}).status_code == 422  # extra="forbid"


def test_limit_and_offset_bounds(client):
    assert _post(client, {"limit": 0}).status_code == 422
    assert _post(client, {"limit": settings.PAGINATION_MAX_LIMIT + 1}).status_code == 422
    assert _post(client, {"offset": -1}).status_code == 422
    assert client.get(f"{URL}?limit=1000").status_code == 422


def test_operator_value_shapes(client):
    bad = [
        {"field": "request_id", "op": "in", "value": "not-a-list"},
        {"field": "request_id", "op": "in", "value": []},
        {"field": "occurred_on", "op": "between", "value": ["2026-01-01"]},
        {"field": "error_code", "op": "is_null", "value": "yes"},
        {"field": "request_id", "op": "eq", "value": None},
        {"field": "request_id", "op": "contains", "value": 5},
        {"field": "request_id", "op": "regex", "value": ".*"},
    ]
    for flt in bad:
        assert _post(client, {"filters": [flt]}).status_code == 422, flt


def test_value_coerced_to_column_type(client):
    r = _post(client, {"filters": [{"field": "id", "op": "eq", "value": "not-a-uuid"}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_filter"
    assert r.json()["error"]["details"][0]["loc"] == ["body", "filters", 0, "value"]


def test_text_operator_on_non_text_column_rejected(client):
    r = _post(client, {"filters": [{"field": "occurred_on", "op": "contains", "value": "2026"}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_filter"


def _sql(payload):
    stmt, sort = ExceptionLogService(db=None).build_query(SearchRequest(**payload))
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    return str(compiled), sort


def test_soft_deleted_excluded_by_default():
    sql, _ = _sql({})
    assert "exception_log.is_deleted IS false" in sql
    sql, _ = _sql({"include_deleted": True})
    assert "WHERE" not in sql


def test_like_wildcards_are_escaped():
    sql, _ = _sql({"search": "100%_off"})
    # compiled SQL doubles % for the driver: \%% is an escaped literal %
    assert "100\\%%\\_off" in sql
    assert "ESCAPE '\\'" in sql


def test_sort_always_ends_with_id_tie_breaker():
    _, sort = _sql({"sort": [{"field": "status_code", "direction": "desc"}]})
    assert [f for f, _ in sort] == ["status_code", "id"]
    _, sort = _sql({})
    assert [f for f, _ in sort] == ["occurred_on", "id"]


def test_typo_in_service_field_lists_fails_at_definition():
    import pytest

    from app.services.base import BaseService

    with pytest.raises(TypeError, match="no field"):

        class BrokenService(BaseService):
            model = ExceptionLogService.model
            filter_fields = ("status_cod",)


@pytest.fixture
def client(client, admin_headers):
    """The log APIs need *_logs:read: call them as an admin."""
    client.headers.update(admin_headers)
    return client
