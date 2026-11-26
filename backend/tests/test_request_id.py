from app.core.config import settings

HEADER = settings.REQUEST_ID_HEADER


def test_request_id_is_generated(client):
    response = client.get("/")
    assert len(response.headers[HEADER]) == 32


def test_valid_incoming_request_id_is_reused(client):
    response = client.get("/", headers={HEADER: "trace-abc-12345"})
    assert response.headers[HEADER] == "trace-abc-12345"


def test_unsafe_incoming_request_id_is_replaced(client):
    for bad in ["short", "has spaces in it", "x" * 200, "evil;injection=1", '{"json":1}']:
        response = client.get("/", headers={HEADER: bad})
        assert response.headers[HEADER] != bad


def test_access_log_carries_request_id(client, json_logs):
    response = client.get("/", headers={HEADER: "trace-access-0001"})
    access = [r for r in json_logs() if r["logger"] == "app.access"]
    assert access and access[-1]["request_id"] == "trace-access-0001"
    assert access[-1]["context"]["status_code"] == response.status_code
    assert "duration_ms" in access[-1]["context"]


def test_each_request_gets_its_own_id(client):
    ids = {client.get("/").headers[HEADER] for _ in range(5)}
    assert len(ids) == 5
