"""Search payload validation and SQL generation. No database needed:
everything here is rejected (or built) before a query runs."""

from sqlalchemy.dialects import postgresql

from app.api.v1.endpoints.items import ITEM_SEARCH, ItemSearchRequest
from app.core.config import settings
from app.db.search import build_statement


def _post(client, payload):
    return client.post("/api/v1/items/search", json=payload)


def test_unknown_filter_field_rejected(client):
    r = _post(client, {"filters": [{"field": "password_hash", "op": "eq", "value": "x"}]})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"][0]["loc"][:4] == ["body", "filters", 0, "field"]
    assert body["metadata"]["request_id"] == r.headers[settings.REQUEST_ID_HEADER]


def test_unknown_sort_field_and_extra_keys_rejected(client):
    assert _post(client, {"sort": [{"field": "secret"}]}).status_code == 422
    assert _post(client, {"page": 2}).status_code == 422  # extra="forbid"


def test_limit_and_offset_bounds(client):
    assert _post(client, {"limit": 0}).status_code == 422
    assert _post(client, {"limit": settings.PAGINATION_MAX_LIMIT + 1}).status_code == 422
    assert _post(client, {"offset": -1}).status_code == 422
    assert client.get("/api/v1/items?limit=1000").status_code == 422


def test_operator_value_shapes(client):
    bad = [
        {"field": "name", "op": "in", "value": "not-a-list"},
        {"field": "name", "op": "in", "value": []},
        {"field": "created_on", "op": "between", "value": ["2026-01-01"]},
        {"field": "updated_on", "op": "is_null", "value": "yes"},
        {"field": "name", "op": "eq", "value": None},
        {"field": "name", "op": "contains", "value": 5},
        {"field": "name", "op": "regex", "value": ".*"},
    ]
    for flt in bad:
        assert _post(client, {"filters": [flt]}).status_code == 422, flt


def test_value_coerced_to_column_type(client):
    r = _post(client, {"filters": [{"field": "id", "op": "eq", "value": "not-a-uuid"}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_filter"
    assert r.json()["error"]["details"][0]["loc"] == ["body", "filters", 0, "value"]


def test_text_operator_on_non_text_column_rejected(client):
    r = _post(client, {"filters": [{"field": "created_on", "op": "contains", "value": "2026"}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_filter"


def _sql(payload) -> str:
    stmt, sort = build_statement(ITEM_SEARCH, ItemSearchRequest(**payload))
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    return str(compiled), sort


def test_soft_deleted_excluded_by_default():
    sql, _ = _sql({})
    assert "items.is_deleted IS false" in sql
    sql, _ = _sql({"include_deleted": True})
    assert "WHERE" not in sql


def test_like_wildcards_are_escaped():
    sql, _ = _sql({"search": "100%_off"})
    # compiled SQL doubles % for the driver: \%% is an escaped literal %
    assert "100\\%%\\_off" in sql
    assert "ESCAPE '\\'" in sql


def test_sort_always_ends_with_id_tie_breaker():
    _, sort = _sql({"sort": [{"field": "name", "direction": "desc"}]})
    assert [f for f, _ in sort] == ["name", "id"]
    _, sort = _sql({})
    assert [f for f, _ in sort] == ["created_on", "id"]


def test_search_request_schema_lists_allowed_fields(client):
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    field_enum = schema["ItemFilter"]["properties"]["field"]["enum"]
    assert "name" in field_enum and "is_deleted" not in field_enum
