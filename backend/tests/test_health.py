def test_root(client):
    response = client.get("/")
    assert response.status_code == 200


def test_health_responds_even_without_db(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
