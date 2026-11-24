"""Submit persisted discovery jobs to the configured Prefect deployment."""

from __future__ import annotations

from typing import Any

from app.core.settings import get_settings


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

    return await run_deployment(
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
