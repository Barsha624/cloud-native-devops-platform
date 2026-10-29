import pytest

from taskapi.app import MAX_TITLE_LENGTH, create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def secured_client(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-not-a-real-secret")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def create_task(client, title="write tests"):
    return client.post("/tasks", json={"title": title})


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_version_reads_environment(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    app = create_app()
    response = app.test_client().get("/version")
    assert response.get_json() == {"version": "1.2.3"}


def test_create_task_returns_201_and_task(client):
    response = create_task(client, "  learn docker  ")
    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "title": "learn docker", "done": False}


def test_ids_increase_per_task(client):
    create_task(client)
    second = create_task(client)
    assert second.get_json()["id"] == 2


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"title": 123},
        {"title": "x" * (MAX_TITLE_LENGTH + 1)},
        ["not", "an", "object"],
    ],
)
def test_create_task_rejects_invalid_body(client, body):
    response = client.post("/tasks", json=body)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_task_rejects_non_json_body(client):
    response = client.post("/tasks", data="plain text")
    assert response.status_code == 400


def test_list_tasks(client):
    assert client.get("/tasks").get_json() == []
    create_task(client)
    assert len(client.get("/tasks").get_json()) == 1


def test_get_task_and_missing_task(client):
    create_task(client)
    assert client.get("/tasks/1").status_code == 200
    missing = client.get("/tasks/99")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_update_task(client):
    create_task(client)
    response = client.patch("/tasks/1", json={"done": True, "title": "renamed"})
    assert response.status_code == 200
    assert response.get_json() == {"id": 1, "title": "renamed", "done": True}


def test_update_task_validation(client):
    create_task(client)
    assert client.patch("/tasks/1", json={"done": "yes"}).status_code == 400
    assert client.patch("/tasks/1", json={"title": ""}).status_code == 400
    assert client.patch("/tasks/1", json={}).status_code == 400
    assert client.patch("/tasks/99", json={"done": True}).status_code == 404


def test_delete_task(client):
    create_task(client)
    assert client.delete("/tasks/1").status_code == 204
    assert client.get("/tasks/1").status_code == 404
    assert client.delete("/tasks/1").status_code == 404


def test_unknown_route_returns_json_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_wrong_method_returns_json_405(client):
    response = client.put("/tasks")
    assert response.status_code == 405
    assert "error" in response.get_json()


def test_api_key_required_when_configured(secured_client):
    assert secured_client.get("/tasks").status_code == 401
    wrong = secured_client.get("/tasks", headers={"X-API-Key": "wrong"})
    assert wrong.status_code == 401
    right = secured_client.get("/tasks", headers={"X-API-Key": "test-key-not-a-real-secret"})
    assert right.status_code == 200


def test_public_endpoints_skip_api_key(secured_client):
    for path in ("/health", "/version", "/metrics"):
        assert secured_client.get(path).status_code == 200


def test_metrics_count_requests(client):
    client.get("/health")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'http_requests_total{endpoint="/health",method="GET",status="200"} 1.0' in body


def test_unexpected_error_returns_generic_500(monkeypatch):
    app = create_app()
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert response.get_json() == {"error": "internal server error"}
