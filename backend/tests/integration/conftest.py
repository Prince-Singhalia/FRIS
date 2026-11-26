"""Fixtures for PostgreSQL-backed API integration tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.auth import hash_password
from app.db.models import Tenant, User, UserRole
from app.db.session import get_db
from app.main import app


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.getenv("FRIS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set FRIS_TEST_DATABASE_URL to run PostgreSQL integration tests")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(test_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def auth_test_data(test_engine: AsyncEngine) -> AsyncIterator[dict[str, str]]:
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    suffix = uuid.uuid4().hex
    tenant_a = Tenant(name=f"Integration tenant A {suffix}", slug=f"it-a-{suffix}")
    tenant_b = Tenant(name=f"Integration tenant B {suffix}", slug=f"it-b-{suffix}")
    password = f"test-password-{suffix}"

    async with session_factory() as session:
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        user_a = User(
            tenant_id=tenant_a.id,
            email=f"admin-a-{suffix}@integration.test",
            username="admin",
            hashed_password=hash_password(password),
            full_name="Integration Admin A",
            role=UserRole.admin,
        )
        user_b = User(
            tenant_id=tenant_b.id,
            email=f"admin-b-{suffix}@integration.test",
            username="admin",
            hashed_password=hash_password(password),
            full_name="Integration Admin B",
            role=UserRole.admin,
        )
        session.add_all([user_a, user_b])
        await session.commit()
        data = {
            "tenant_a_id": str(tenant_a.id),
            "tenant_a_slug": tenant_a.slug,
            "tenant_b_id": str(tenant_b.id),
            "user_a_id": str(user_a.id),
            "password": password,
        }

    try:
        yield data
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(User).where(User.tenant_id.in_([tenant_a.id, tenant_b.id]))
            )
            await session.execute(delete(Tenant).where(Tenant.id.in_([tenant_a.id, tenant_b.id])))
            await session.commit()
