"""Unit tests for durable Prefect discovery submission."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.db.models import AuditEvent, DiscoveryJob, Faculty, JobStatus
from app.services import discovery_submission


async def test_batch_jobs_are_persisted_before_submission_and_fail_independently(
    monkeypatch,
) -> None:
    added: list[object] = []

    async def assign_job_ids() -> None:
        for entity in added:
            if isinstance(entity, DiscoveryJob) and entity.id is None:
                entity.id = uuid.uuid4()

    db = SimpleNamespace(
        add=added.append,
        flush=AsyncMock(side_effect=assign_job_ids),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    monkeypatch.setattr(
        discovery_submission,
        "get_settings",
        lambda: SimpleNamespace(prefect_deployment_name="test/discovery"),
    )
    submitted: list[str] = []

    async def submit_run(**kwargs):
        assert db.commit.await_count >= 1
        submitted.append(kwargs["faculty_id"])
        if kwargs["faculty_id"] == str(faculties[1].id):
            raise RuntimeError("Prefect unavailable")
        return SimpleNamespace(id="prefect-run-1")

    monkeypatch.setattr(discovery_submission, "submit_discovery_run", submit_run)
    tenant_id = uuid.uuid4()
    faculties = [
        Faculty(id=uuid.uuid4(), tenant_id=tenant_id, full_name="Researcher One"),
        Faculty(id=uuid.uuid4(), tenant_id=tenant_id, full_name="Researcher Two"),
    ]

    jobs = await discovery_submission.enqueue_faculty_discoveries(
        db,
        faculties=faculties,
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        trigger_type="faculty_imported",
    )

    assert len(jobs) == 2
    assert [job.status for job in jobs] == [JobStatus.pending, JobStatus.failed]
    assert jobs[0].prefect_flow_run_id == "prefect-run-1"
    assert jobs[1].error_detail == "Prefect submission failed (RuntimeError)"
    assert len(submitted) == 2
    assert db.commit.await_count == 3
    assert sum(isinstance(entity, AuditEvent) for entity in added) == 2
