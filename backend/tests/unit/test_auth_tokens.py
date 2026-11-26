"""Tests for access and refresh token encoding and validation."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import auth


@pytest.fixture
def test_settings(monkeypatch):
    settings = SimpleNamespace(
        secret_key="x" * 40,
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    return settings


def test_access_token_round_trip(test_settings):
    token = auth.create_access_token("user-id", "tenant-id", "admin")

    payload = auth.decode_token(token)

    assert payload["sub"] == "user-id"
    assert payload["tenant_id"] == "tenant-id"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_invalid_token_returns_unauthorized(test_settings):
    with pytest.raises(HTTPException) as error:
        auth.decode_token("not-a-jwt")

    assert error.value.status_code == 401
