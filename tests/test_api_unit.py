import logging

from fastapi.testclient import TestClient

from api_service.auth import get_current_username
from api_service.main import app


client = TestClient(app)
API_V1_PREFIX = "/api/v1"


def test_health_check_unit():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_login_unit_success_with_mocked_database(monkeypatch):
    monkeypatch.setattr("api_service.main.authenticate_user", lambda username, password: True)

    response = client.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": "lelalomos", "password": "password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_unit_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setattr("api_service.main.authenticate_user", lambda username, password: False)

    response = client.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": "lelalomos", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_register_unit_creates_user(monkeypatch):
    monkeypatch.setattr(
        "api_service.main.create_user_account",
        lambda username, password: {"user_id": 123, "username": username},
    )

    response = client.post(
        f"{API_V1_PREFIX}/auth/register",
        json={"username": "new-user", "password": "secret"},
    )

    assert response.status_code == 201
    assert response.json() == {"user_id": 123, "username": "new-user"}


def test_register_unit_rejects_duplicate_username(monkeypatch):
    monkeypatch.setattr(
        "api_service.main.create_user_account",
        lambda username, password: (_ for _ in ()).throw(ValueError("Username 'new-user' already exists.")),
    )

    response = client.post(
        f"{API_V1_PREFIX}/auth/register",
        json={"username": "new-user", "password": "secret"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username 'new-user' already exists."


def test_recommendations_unit_rejects_mismatched_username(monkeypatch):
    app.dependency_overrides[get_current_username] = lambda: "lelalomos"

    try:
        response = client.post(
            f"{API_V1_PREFIX}/recommendations",
            json={"username": "another-user", "title": "Wednesday"},
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Authenticated user does not match request username"


def test_recommendations_unit_returns_worker_rpc_result(monkeypatch):
    app.dependency_overrides[get_current_username] = lambda: "lelalomos"

    try:
        monkeypatch.setattr(
            "api_service.main.request_recommendations",
            lambda username, title: [
                {
                    "show_id": "s1",
                    "title": "Interstellar",
                    "content_type": "movie",
                    "language": "en",
                    "score": 0.98,
                },
                {
                    "show_id": "s2",
                    "title": "Dark",
                    "content_type": "tv_show",
                    "language": "de",
                    "score": 0.91,
                },
            ],
        )

        response = client.post(
            f"{API_V1_PREFIX}/recommendations",
            json={"username": "lelalomos", "title": "Inception"},
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Inception"
    assert body["recommendations"][0]["show_id"] == "s1"
    assert body["recommendations"][0]["language"] == "en"


def test_recommendations_unit_returns_gateway_timeout(monkeypatch):
    app.dependency_overrides[get_current_username] = lambda: "lelalomos"

    try:
        from api_service.rpc import RpcTimeoutError

        monkeypatch.setattr(
            "api_service.main.request_recommendations",
            lambda username, title: (_ for _ in ()).throw(
                RpcTimeoutError("Worker did not respond within 30 seconds.")
            ),
        )

        response = client.post(
            f"{API_V1_PREFIX}/recommendations",
            json={"username": "lelalomos", "title": "Inception"},
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504


def test_unversioned_routes_are_not_exposed():
    assert client.post("/auth/register", json={"username": "lelalomos", "password": "password"}).status_code == 404
    assert client.post("/auth/token", data={"username": "lelalomos", "password": "password"}).status_code == 404
    assert client.post(
        "/recommendations",
        json={"username": "lelalomos", "title": "Inception"},
        headers={"Authorization": "Bearer fake-token"},
    ).status_code == 404


def test_recommendations_unit_logs_completion(monkeypatch, caplog):
    app.dependency_overrides[get_current_username] = lambda: "lelalomos"

    try:
        monkeypatch.setattr(
            "api_service.main.request_recommendations",
            lambda username, title: [
                {
                    "show_id": "s1",
                    "title": "Interstellar",
                    "content_type": "movie",
                    "language": "en",
                    "score": 0.98,
                }
            ],
        )
        with caplog.at_level(logging.INFO):
            response = client.post(
                f"{API_V1_PREFIX}/recommendations",
                json={"username": "lelalomos", "title": "Inception"},
                headers={"Authorization": "Bearer fake-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "recommendations_request_completed username=lelalomos title=Inception result_count=1" in caplog.text
