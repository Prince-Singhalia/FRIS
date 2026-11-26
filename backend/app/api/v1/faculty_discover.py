"""Faculty discovery trigger endpoint — POST /api/v1/faculty/{faculty_id}/discover"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, require_roles
from app.db.models import DiscoveryJob, Faculty, JobStatus
from app.db.session import get_db
from app.domain.schemas import DiscoveryJobResponse
from app.services.discovery_submission import enqueue_faculty_discovery

router = APIRouter()


@router.post("/{faculty_id}/discover", response_model=DiscoveryJobResponse, status_code=201)
async def trigger_discovery(
    faculty_id: uuid.UUID,
    current_user: TokenData = Depends(require_roles("admin", "research_officer")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a discovery job for a faculty member."""
    tid = uuid.UUID(current_user.tenant_id)

    # Verify faculty exists in tenant
    result = await db.execute(
        select(Faculty).where(Faculty.id == faculty_id, Faculty.tenant_id == tid)
    )
    faculty = result.scalar_one_or_none()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    # Idempotency: check for pending/running job
    existing = await db.execute(
        select(DiscoveryJob).where(
            DiscoveryJob.faculty_id == faculty_id,
            DiscoveryJob.tenant_id == tid,
            DiscoveryJob.status.in_([JobStatus.pending, JobStatus.running]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="A discovery job is already pending or running for this faculty member",
        )

    job = await enqueue_faculty_discovery(
        db,
        faculty=faculty,
        tenant_id=tid,
        user_id=uuid.UUID(current_user.user_id),
        trigger_type="manual",
    )
    if job.status == JobStatus.failed:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Discovery could not be submitted to the configured Prefect deployment",
                "job_id": str(job.id),
                "error": job.error_detail,
            },
        )

    return job
