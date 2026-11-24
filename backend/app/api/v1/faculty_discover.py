"""Faculty discovery trigger endpoint — POST /api/v1/faculty/{faculty_id}/discover"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, require_roles
from app.core.settings import get_settings
from app.db.models import AuditAction, AuditEvent, DiscoveryJob, Faculty, JobStatus
from app.db.session import get_db
from app.domain.schemas import DiscoveryJobResponse
from app.services.discovery_submission import submit_discovery_run

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

    correlation_id = f"disc-{faculty_id}-{uuid.uuid4().hex}"
    selected_sources = ["openalex", "crossref", "semantic_scholar"]
    deployment_name = get_settings().prefect_deployment_name
    job = DiscoveryJob(
        tenant_id=tid,
        faculty_id=faculty_id,
        status=JobStatus.pending,
        trigger_type="manual",
        triggered_by=current_user.user_id,
        correlation_id=correlation_id,
        idempotency_key=correlation_id,
        prefect_deployment_name=deployment_name,
        selected_sources=selected_sources,
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
    job_id = str(job.id)
    await db.commit()

    try:
        flow_run = await submit_discovery_run(
            deployment_name=deployment_name,
            job_id=job_id,
            faculty_id=str(faculty_id),
            tenant_id=str(tid),
            selected_sources=selected_sources,
            idempotency_key=correlation_id,
        )
    except Exception as error:
        job.status = JobStatus.failed
        job.completed_at = datetime.now(timezone.utc)
        job.error_detail = f"Prefect submission failed ({type(error).__name__})"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Discovery could not be submitted to the configured Prefect deployment",
                "job_id": job_id,
            },
        ) from error

    job.prefect_flow_run_id = str(flow_run.id)
    await db.commit()
    await db.refresh(job, attribute_names=["connector_runs"])

    return job
