"""Auth routes — login, me, token refresh."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    TokenData,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
)
from app.db.models import Tenant, User
from app.db.session import get_db
from app.domain.schemas import TokenResponse, UserResponse

router = APIRouter()


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # Tenant-specific login uses "tenant-slug/username". A bare username is
    # accepted only when it identifies one active user across all tenants.
    tenant_slug = None
    username = form.username
    if "/" in username:
        tenant_slug, username = username.split("/", maxsplit=1)
        if not tenant_slug or not username:
            raise HTTPException(status_code=401, detail="Incorrect username or password")

    query = select(User).where(User.username == username, User.is_active.is_(True))
    if tenant_slug:
        query = query.join(Tenant, User.tenant_id == Tenant.id).where(Tenant.slug == tenant_slug)
    result = await db.execute(query)
    users = result.scalars().all()

    if len(users) == 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username exists in multiple tenants. Use tenant-slug/username.",
        )

    user = users[0]
    if not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access = create_access_token(str(user.id), str(user.tenant_id), user.role.value)
    refresh = create_refresh_token(str(user.id), str(user.tenant_id), user.role.value)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Issue new access token from a valid refresh token."""
    payload = decode_token(body.refresh_token)
    # Only accept refresh tokens
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: expected refresh token",
        )
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    if not user_id or not tenant_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    try:
        user_uuid = uuid.UUID(user_id)
        tenant_uuid = uuid.UUID(tenant_id)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims"
        ) from error

    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == user_uuid, User.tenant_id == tenant_uuid)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled"
        )

    access = create_access_token(str(user.id), str(user.tenant_id), user.role.value)
    new_refresh = create_refresh_token(str(user.id), str(user.tenant_id), user.role.value)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(current_user.user_id),
            User.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
