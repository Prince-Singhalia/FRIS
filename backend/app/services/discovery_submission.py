"""Submit persisted discovery jobs to the configured Prefect deployment."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import AuditAction, AuditEvent, DiscoveryJob, Faculty, JobStatus


async def submit_discovery_run(
    *,
    deployment_name: str,
    job_id: str,
    faculty_id: str,
    tenant_id: str,
    selected_sources: list[str],
    idempotency_key: str,
) -> Any:
    """Create a Prefect run and return immediately with its server run record.

    The work pool worker executes the flow separately. A missing deployment or
    unavailable Prefect API is allowed to raise so the caller can mark the DB
    job failed instead of leaving it falsely pending.
    """
    from prefect.deployments import run_deployment

    flow_run = run_deployment(
        name=deployment_name,
        parameters={
            "job_id": job_id,
            "faculty_id": faculty_id,
            "tenant_id": tenant_id,
            "selected_sources": selected_sources,
        },
        timeout=0,
        idempotency_key=idempotency_key,
        as_subflow=False,
    )
    return await flow_run if isawaitable(flow_run) else flow_run


async def enqueue_faculty_discoveries(
    db: AsyncSession,
    *,
    faculties: Sequence[Faculty],
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trigger_type: str,
) -> list[DiscoveryJob]:
    """Persist discovery jobs before submitting each run to Prefect."""
    if not faculties:
        return []

    selected_sources = ["openalex", "crossref", "semantic_scholar"]
    deployment_name = get_settings().prefect_deployment_name
    jobs: list[DiscoveryJob] = []
    for faculty in faculties:
        correlation_id = f"disc-{faculty.id}-{uuid.uuid4().hex}"
        job = DiscoveryJob(
            tenant_id=tenant_id,
            faculty_id=faculty.id,
            status=JobStatus.pending,
            trigger_type=trigger_type,
            triggered_by=str(user_id),
            correlation_id=correlation_id,
            idempotency_key=correlation_id,
            prefect_deployment_name=deployment_name,
            selected_sources=selected_sources,
        )
        jobs.append(job)
        db.add(job)
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action=AuditAction.discovery_triggered,
                entity_type="faculty",
                entity_id=faculty.id,
                detail={"job_correlation_id": correlation_id, "trigger": trigger_type},
            )
        )

    await db.flush()
    await db.commit()

    for job in jobs:
        try:
            flow_run = await submit_discovery_run(
                deployment_name=deployment_name,
                job_id=str(job.id),
                faculty_id=str(job.faculty_id),
                tenant_id=str(tenant_id),
                selected_sources=selected_sources,
                idempotency_key=job.correlation_id,
            )
        except Exception as error:
            job.status = JobStatus.failed
            job.completed_at = datetime.now(UTC)
            job.error_detail = f"Prefect submission failed ({type(error).__name__})"
        else:
            job.prefect_flow_run_id = str(flow_run.id)

        await db.commit()

    for job in jobs:
        await db.refresh(job, attribute_names=["connector_runs"])
    return jobs


async def enqueue_faculty_discovery(
    db: AsyncSession,
    *,
    faculty: Faculty,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trigger_type: str,
) -> DiscoveryJob:
    """Create one discovery job and submit it after it has been persisted."""
    jobs = await enqueue_faculty_discoveries(
        db,
        faculties=[faculty],
        tenant_id=tenant_id,
        user_id=user_id,
        trigger_type=trigger_type,
    )
    return jobs[0]
