import os
import hashlib

import httpx
import psycopg


API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
API_V1_PREFIX = f"{API_BASE_URL}/api/v1"
DEFAULT_LIKED_SHOW_ID = 27205


def seed_login_user(username: str, password: str, with_liked_content: bool = True) -> None:
    user_id = 900000 + (sum(username.encode("utf-8")) % 10000)
    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    with psycopg.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {os.environ['POSTGRES_USER_ACCOUNT_TABLE']} (user_id, username, password)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET username = EXCLUDED.username,
                    password = EXCLUDED.password
                """,
                (user_id, username, password_hash),
            )
            if with_liked_content:
                cursor.execute(
                    f"""
                    INSERT INTO {os.environ['POSTGRES_USER_CONTENT_TABLE']} (user_id, show_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, show_id) DO NOTHING
                    """,
                    (user_id, DEFAULT_LIKED_SHOW_ID),
                )
        connection.commit()


def test_health_check():
    response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api-service"}


def test_register_and_login_flow():
    username = "api_registered_user"
    password = "registered-password"

    register_response = httpx.post(
        f"{API_V1_PREFIX}/auth/register",
        json={"username": username, "password": password},
        timeout=5.0,
    )

    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["username"] == username
    assert isinstance(register_body["user_id"], int)

    login_response = httpx.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": username, "password": password},
        timeout=5.0,
    )

    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_register_rejects_duplicate_username():
    username = "api_duplicate_user"
    password = "duplicate-password"

    first_response = httpx.post(
        f"{API_V1_PREFIX}/auth/register",
        json={"username": username, "password": password},
        timeout=5.0,
    )
    second_response = httpx.post(
        f"{API_V1_PREFIX}/auth/register",
        json={"username": username, "password": password},
        timeout=5.0,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == f"Username '{username}' already exists."


def test_login_and_recommendations_flow():
    seed_login_user("api_test_user", "test-password")

    login_response = httpx.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": "api_test_user", "password": "test-password"},
        timeout=5.0,
    )

    assert login_response.status_code == 200
    token_payload = login_response.json()
    assert token_payload["token_type"] == "bearer"
    assert token_payload["access_token"]

    recommendations_response = httpx.post(
        f"{API_V1_PREFIX}/recommendations",
        headers={"Authorization": f"Bearer {token_payload['access_token']}"},
        json={"username": "api_test_user", "title": "Wednesday"},
        timeout=5.0,
    )

    assert recommendations_response.status_code == 200
    body = recommendations_response.json()
    assert body["username"] == "api_test_user"
    assert body["title"] == "Wednesday"
    assert isinstance(body["recommendations"], list)


def test_login_rejects_wrong_password():
    seed_login_user("api_test_user_wrong_password", "test-password")

    response = httpx.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": "api_test_user_wrong_password", "password": "wrong-password"},
        timeout=5.0,
    )

    assert response.status_code == 401


def test_recommendations_requires_token():
    response = httpx.post(
        f"{API_V1_PREFIX}/recommendations",
        json={"username": "api_test_user", "title": "Wednesday"},
        timeout=5.0,
    )

    assert response.status_code == 401


def test_recommendations_rejects_username_mismatch():
    seed_login_user("api_test_user_mismatch", "test-password")

    login_response = httpx.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": "api_test_user_mismatch", "password": "test-password"},
        timeout=5.0,
    )

    assert login_response.status_code == 200
    token_payload = login_response.json()

    response = httpx.post(
        f"{API_V1_PREFIX}/recommendations",
        headers={"Authorization": f"Bearer {token_payload['access_token']}"},
        json={"username": "another-user", "title": "Wednesday"},
        timeout=5.0,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authenticated user does not match request username"


def test_recommendations_for_new_user_insert_input_title_into_user_content():
    username = "api_test_user_no_likes"
    expected_user_id = 900000 + (sum(username.encode("utf-8")) % 10000)
    seed_login_user(username, "test-password", with_liked_content=False)

    login_response = httpx.post(
        f"{API_V1_PREFIX}/auth/token",
        data={"username": username, "password": "test-password"},
        timeout=5.0,
    )

    assert login_response.status_code == 200
    token_payload = login_response.json()

    recommendations_response = httpx.post(
        f"{API_V1_PREFIX}/recommendations",
        headers={"Authorization": f"Bearer {token_payload['access_token']}"},
        json={"username": username, "title": "Iron Man"},
        timeout=5.0,
    )

    assert recommendations_response.status_code == 200

    with psycopg.connect(
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT ua.user_id, uc.show_id
                FROM {os.environ['POSTGRES_USER_ACCOUNT_TABLE']} AS ua
                JOIN {os.environ['POSTGRES_USER_CONTENT_TABLE']} AS uc ON uc.user_id = ua.user_id
                WHERE LOWER(ua.username) = LOWER(%s)
                ORDER BY uc.show_id
                """,
                (username,),
            )
            rows = cursor.fetchall()

    assert rows == [(expected_user_id, 45418)]
