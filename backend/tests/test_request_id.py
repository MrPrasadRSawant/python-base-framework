import uuid

from app.core.config import settings

HEADER = settings.REQUEST_ID_HEADER
INCOMING = "0192f5f0-1111-7000-8000-00000000abcd"


def test_request_id_is_generated_as_uuid(client):
    value = client.get("/").headers[HEADER]
    parsed = uuid.UUID(value)
    assert str(parsed) == value  # canonical form
    if hasattr(uuid, "uuid7"):
        assert parsed.version == 7  # time-ordered


def test_incoming_uuid_is_reused(client):
    assert client.get("/", headers={HEADER: INCOMING}).headers[HEADER] == INCOMING


def test_incoming_uuid_is_normalized(client):
    for spelling in (INCOMING.upper(), INCOMING.replace("-", ""), "{" + INCOMING + "}"):
        assert client.get("/", headers={HEADER: spelling}).headers[HEADER] == INCOMING


def test_non_uuid_incoming_id_is_replaced(client):
    for bad in ["trace-abc-12345", "short", "x" * 200, "evil;injection=1", '{"json":1}']:
        value = client.get("/", headers={HEADER: bad}).headers[HEADER]
        assert value != bad
        uuid.UUID(value)  # always a valid UUID


def test_access_log_carries_request_id(client, json_logs):
    response = client.get("/", headers={HEADER: INCOMING})
    access = [r for r in json_logs() if r["logger"] == "app.access"]
    assert access and access[-1]["request_id"] == INCOMING
    assert access[-1]["context"]["status_code"] == response.status_code
    assert "duration_ms" in access[-1]["context"]


def test_each_request_gets_its_own_id(client):
    ids = {client.get("/").headers[HEADER] for _ in range(5)}
    assert len(ids) == 5
