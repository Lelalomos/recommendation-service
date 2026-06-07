from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from api_service.auth import (
    ALGORITHM,
    authenticate_user,
    create_user_account,
    create_access_token,
    decode_access_token,
    get_secret_key,
    hash_password,
    get_user_account_by_username,
    verify_password,
)


def test_password_hash_verification():
    stored_hash = hash_password("demo-password", salt=b"1234567890abcdef")

    assert verify_password("demo-password", stored_hash)
    assert not verify_password("wrong-password", stored_hash)


def test_sha256_hex_password_verification():
    stored_hash = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"

    assert verify_password("password", stored_hash)
    assert not verify_password("wrong-password", stored_hash)


def test_authenticate_user_uses_database_row(monkeypatch):
    monkeypatch.setattr(
        "api_service.auth.get_user_account_by_username",
        lambda username: {
            "user_id": 99,
            "username": username,
            "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        },
    )

    assert authenticate_user("lelalomos", "password")
    assert not authenticate_user("lelalomos", "wrong-password")


def test_get_user_account_by_username_returns_none_when_missing(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchone(self):
            return None

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr("api_service.auth.psycopg.connect", lambda **kwargs: FakeConnection())

    assert get_user_account_by_username("missing-user") is None


def test_create_user_account_rejects_duplicate_username(monkeypatch):
    monkeypatch.setattr(
        "api_service.auth.get_user_account_by_username",
        lambda username: {"user_id": 7, "username": username, "password": "stored"},
    )

    with pytest.raises(ValueError, match="already exists"):
        create_user_account("lelalomos", "password")


def test_create_access_token_contains_subject_and_expiry():
    token, expires_at = create_access_token("demo_user")
    payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

    assert payload["sub"] == "demo_user"
    assert expires_at > datetime.now(timezone.utc)


def test_decode_access_token_rejects_expired_token():
    expired_token = jwt.encode(
        {"sub": "demo_user", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        get_secret_key(),
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException):
        decode_access_token(expired_token)
