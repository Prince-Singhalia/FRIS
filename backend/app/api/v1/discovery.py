"""Discovery job routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user, require_roles
from app.db.models import DiscoveryJob, Faculty
from app.db.session import get_db
from app.domain.schemas import DiscoveryJobResponse, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(DiscoveryJob).where(DiscoveryJob.tenant_id == current_user.tenant_id)
    if status:
        base_q = base_q.where(DiscoveryJob.status == status)

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    items_q = base_q.order_by(DiscoveryJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(items_q)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[DiscoveryJobResponse.model_validate(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{job_id}", response_model=DiscoveryJobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DiscoveryJob).where(
            DiscoveryJob.id == job_id,
            DiscoveryJob.tenant_id == current_user.tenant_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Discovery job not found")
    return job
