"""The API docs (Swagger) stay true to the code.

Every /api/v1 endpoint must have a summary and a description that starts with an
**Access:** line, and that line must name exactly what the code enforces:
each required permission, or "Signed-in user" for user-only routes.
"""

import pytest
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts

from app.core.config import settings
from app.core.security import require_user
from app.main import app


def _calls(dependant):
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from _calls(dep)


def _api_routes() -> list[RouteContext]:
    """Every /api/v1 route as mounted (router prefixes and dependencies applied)."""
    return [
        r
        for r in iter_route_contexts(app.routes)
        if isinstance(r.original_route, APIRoute)
        and r.include_in_schema
        and r.path_format.startswith(settings.API_V1_PREFIX)
    ]


ROUTES = _api_routes()


def _id(route: RouteContext) -> str:
    return f"{','.join(sorted(route.methods))} {route.path_format}"


def test_routes_found():
    assert len(ROUTES) > 30


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_route_has_summary_and_access_line(route):
    assert route.summary, "add summary= to the route decorator"
    assert (route.description or "").startswith("**Access:**"), (
        "start the docstring with an **Access:** line"
    )


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_access_line_matches_the_code(route):
    access = route.description.split("\n\n", 1)[0]
    calls = list(_calls(route.dependant))
    perms = {p for call in calls for p in getattr(call, "required_permissions", ())}
    user_only = require_user in calls

    for perm in perms:
        assert f"`{perm}`" in access, f"Access line must name permission {perm}"
    if user_only:
        assert "Signed-in user" in access
    if not perms and not user_only:
        assert "Public" in access or "Refresh cookie" in access, "unprotected route"
    if perms or user_only:
        assert "Public" not in access, "protected route documented as public"


def test_every_tag_is_described(client):
    spec = client.get("/openapi.json").json()
    described = {t["name"] for t in spec["tags"]}
    api_ops = [
        op
        for path, ops in spec["paths"].items()
        if path.startswith(settings.API_V1_PREFIX)
        for op in ops.values()
    ]
    assert all(op.get("tags") for op in api_ops), "every endpoint needs a tag"
    used = {tag for op in api_ops for tag in op["tags"]}
    assert used <= described


def test_protected_routes_document_401_and_403(client):
    spec = client.get("/openapi.json").json()
    for route in ROUTES:
        if any(getattr(c, "required_permissions", None) for c in _calls(route.dependant)):
            for method in route.methods:
                responses = spec["paths"][route.path_format][method.lower()]["responses"]
                assert {"401", "403"} <= responses.keys(), _id(route)
