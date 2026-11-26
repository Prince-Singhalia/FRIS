"""PostgreSQL-backed tenant authentication and authorization tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.auth import create_access_token
from app.db.models import UserRole

pytestmark = pytest.mark.integration


async def test_tenant_scoped_login_and_me(
    api_client: AsyncClient,
    auth_test_data: dict[str, str],
) -> None:
    password = auth_test_data["password"]
    tenant_a_id = auth_test_data["tenant_a_id"]
    tenant_a_slug = auth_test_data["tenant_a_slug"]
    tenant_b_id = auth_test_data["tenant_b_id"]
    user_a_id = auth_test_data["user_a_id"]

    ambiguous_login = await api_client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": password},
    )
    assert ambiguous_login.status_code == 409

    scoped_login = await api_client.post(
        "/api/v1/auth/login",
        data={"username": f"{tenant_a_slug}/admin", "password": password},
    )
    assert scoped_login.status_code == 200
    access_token = scoped_login.json()["access_token"]

    me_response = await api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["tenant_id"] == tenant_a_id

    cross_tenant_token = create_access_token(user_a_id, tenant_b_id, UserRole.admin.value)
    cross_tenant_response = await api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {cross_tenant_token}"},
    )
    assert cross_tenant_response.status_code == 404
