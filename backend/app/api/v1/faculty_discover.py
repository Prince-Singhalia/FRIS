"""Faculty discovery trigger endpoint — POST /api/v1/faculty/{faculty_id}/discover"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, require_roles
from app.db.models import AuditAction, AuditEvent, DiscoveryJob, Faculty, JobStatus
from app.db.session import get_db
from app.domain.schemas import DiscoveryJobResponse

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

    correlation_id = f"disc-{faculty_id}-{uuid.uuid4().hex[:8]}"
    job = DiscoveryJob(
        tenant_id=tid,
        faculty_id=faculty_id,
        status=JobStatus.pending,
        trigger_type="manual",
        triggered_by=current_user.user_id,
        correlation_id=correlation_id,
        idempotency_key=f"manual-{faculty_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
        selected_sources=["openalex", "crossref", "semantic_scholar"],
    )
    db.add(job)

    # Audit
    db.add(AuditEvent(
        tenant_id=tid,
        user_id=uuid.UUID(current_user.user_id),
        action=AuditAction.discovery_triggered,
        entity_type="faculty",
        entity_id=faculty_id,
        detail={"job_correlation_id": correlation_id, "trigger": "manual"},
    ))

    await db.flush()
    await db.refresh(job, attribute_names=["connector_runs"])

    # In production, this would submit to Prefect.
    # For now, the job is created in pending state for the Prefect worker to pick up.

    return job
