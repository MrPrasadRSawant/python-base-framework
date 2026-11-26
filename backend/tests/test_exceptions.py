from app.core.config import settings

HEADER = settings.REQUEST_ID_HEADER


def _exception_logs(json_logs):
    return [r for r in json_logs() if r["logger"] == "app.exceptions"]


def test_unhandled_exception_returns_500_envelope(client):
    response = client.get("/_test/boom", headers={HEADER: "trace-boom-0001"})
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_server_error"
    assert response.json()["metadata"]["request_id"] == "trace-boom-0001"
    assert "timestamp" in response.json()["metadata"]
    assert response.headers[HEADER] == "trace-boom-0001"
    assert "hunter2" not in response.text  # internals never reach the client


def test_unhandled_exception_logged_once_with_request_id_and_traceback(client, json_logs):
    client.get("/_test/boom", headers={HEADER: "trace-boom-0002"})
    logs = _exception_logs(json_logs)
    assert len(logs) == 1
    log = logs[0]
    assert log["level"] == "ERROR"
    assert log["request_id"] == "trace-boom-0002"
    assert log["exception"]["type"] == "RuntimeError"
    assert "Traceback" in log["exception"]["traceback"]
    assert log["context"]["request"]["route"] == "/_test/boom"
    assert log["context"]["request"]["endpoint"].endswith(".boom")


def test_secrets_in_exception_are_redacted_in_logs(client, json_logs):
    client.get("/_test/boom")
    raw = json_logs.raw()
    assert "hunter2" not in raw
    assert "[REDACTED]" in raw


def test_app_exception_maps_to_status_and_logs_warning(client, json_logs):
    response = client.get("/_test/missing/7")
    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "not_found"
    assert body["details"] == {"thing_id": 7}
    assert response.json()["metadata"]["request_id"] == response.headers[HEADER]

    log = _exception_logs(json_logs)[-1]
    assert log["level"] == "WARNING"
    assert "exception" not in log  # no traceback for client errors
    assert log["request_id"] == response.headers[HEADER]


def test_unknown_route_and_method_use_envelope(client):
    assert client.get("/nope").json()["error"]["code"] == "not_found"
    response = client.delete("/")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_validation_error_masks_password_in_response_and_logs(client, json_logs):
    response = client.post(
        "/_test/login", json={"username": "alice", "password": "short-pw"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["body", "password"]
    assert error["details"][0]["input"] == "[REDACTED]"
    assert "short-pw" not in response.text

    raw = json_logs.raw()
    assert "short-pw" not in raw
    log = _exception_logs(json_logs)[-1]
    assert log["context"]["request"]["body"]["content"]["password"] == "[REDACTED]"
    assert log["context"]["request"]["body"]["content"]["username"] == "alice"


def test_500_log_includes_redacted_body_and_headers(client, json_logs):
    client.post(
        "/_test/login",
        json={"username": "bob", "password": "a-very-long-password"},
        headers={"Authorization": "Bearer abc.def.ghi", "X-Api-Key": "k-123"},
        params={"token": "qs-secret", "page": "2"},
    )
    raw = json_logs.raw()
    for secret in ("a-very-long-password", "abc.def.ghi", "k-123", "qs-secret"):
        assert secret not in raw

    request = _exception_logs(json_logs)[-1]["context"]["request"]
    assert request["headers"]["authorization"] == "[REDACTED]"
    assert request["headers"]["x-api-key"] == "[REDACTED]"
    assert request["query_params"] == {"token": "[REDACTED]", "page": "2"}
    assert request["body"]["content"]["password"] == "[REDACTED]"


def test_cors_headers_present_on_500(client):
    origin = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else None
    if origin is None:
        return
    response = client.get("/_test/boom", headers={"Origin": origin})
    assert response.headers.get("access-control-allow-origin") == origin
