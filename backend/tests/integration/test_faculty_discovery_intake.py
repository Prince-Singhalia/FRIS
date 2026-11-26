"""Faculty intake automatically queues tenant-scoped discovery jobs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.auth import create_access_token
from app.db.models import UserRole

pytestmark = pytest.mark.integration


def _headers(user_id: str, tenant_id: str) -> dict[str, str]:
    token = create_access_token(user_id, tenant_id, UserRole.admin.value)
    return {"Authorization": f"Bearer {token}"}


async def test_create_faculty_queues_discovery_and_is_tenant_scoped(
    api_client: AsyncClient,
    auth_test_data: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: dict = {}

    async def submit_run(**kwargs):
        submitted.update(kwargs)
        return SimpleNamespace(id="prefect-run-integration")

    monkeypatch.setattr("app.services.discovery_submission.submit_discovery_run", submit_run)
    tenant_a_headers = _headers(
        auth_test_data["user_a_id"],
        auth_test_data["tenant_a_id"],
    )
    created = await api_client.post(
        "/api/v1/faculty",
        headers=tenant_a_headers,
        json={
            "full_name": "Ada Researcher",
            "reported_institution": "Example University",
            "institutional_email": "ada@example.test",
        },
    )

    assert created.status_code == 201
    profile = created.json()
    job = profile["discovery_job"]
    assert profile["full_name"] == "Ada Researcher"
    assert "institutional_email" not in profile
    assert job["status"] == "pending"
    assert job["trigger_type"] == "faculty_created"
    assert job["prefect_flow_run_id"] == "prefect-run-integration"
    assert submitted["faculty_id"] == profile["id"]
    assert submitted["tenant_id"] == auth_test_data["tenant_a_id"]
    assert submitted["job_id"] == job["id"]
    assert "institutional_email" not in submitted

    tenant_b_headers = _headers(
        auth_test_data["user_b_id"],
        auth_test_data["tenant_b_id"],
    )
    faculty_id = profile["id"]
    paths = (
        f"/api/v1/faculty/{faculty_id}",
        f"/api/v1/faculty/{faculty_id}/publications",
        f"/api/v1/dashboard/faculty/{faculty_id}",
        f"/api/v1/faculty/{faculty_id}/discover",
    )
    for path in paths:
        if path.endswith("/discover"):
            response = await api_client.post(path, headers=tenant_b_headers)
        else:
            response = await api_client.get(path, headers=tenant_b_headers)
        assert response.status_code == 404, path


async def test_faculty_is_saved_and_failed_submission_is_visible(
    api_client: AsyncClient,
    auth_test_data: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_submission(**_kwargs):
        raise RuntimeError("Prefect is unavailable")

    monkeypatch.setattr("app.services.discovery_submission.submit_discovery_run", fail_submission)
    headers = _headers(auth_test_data["user_a_id"], auth_test_data["tenant_a_id"])
    created = await api_client.post(
        "/api/v1/faculty",
        headers=headers,
        json={"full_name": "Grace Researcher"},
    )

    assert created.status_code == 201
    job = created.json()["discovery_job"]
    assert job["status"] == "failed"
    assert job["error_detail"] == "Prefect submission failed (RuntimeError)"
    assert job["completed_at"] is not None

    retried = await api_client.post(
        f"/api/v1/faculty/{job['faculty_id']}/discover",
        headers=headers,
    )
    assert retried.status_code == 503
    retried_job_id = retried.json()["detail"]["job_id"]
    assert retried_job_id != job["id"]

    jobs = await api_client.get("/api/v1/discovery-jobs", headers=headers)
    assert jobs.status_code == 200
    persisted_jobs = jobs.json()["items"]
    assert {item["status"] for item in persisted_jobs} == {"failed"}
    assert {job["id"] for job in persisted_jobs} == {
        created.json()["discovery_job"]["id"],
        retried_job_id,
    }


async def test_csv_import_enqueues_only_valid_unique_faculty(
    api_client: AsyncClient,
    auth_test_data: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[dict] = []

    async def submit_run(**kwargs):
        submitted.append(kwargs)
        return SimpleNamespace(id=f"prefect-run-csv-{len(submitted)}")

    monkeypatch.setattr("app.services.discovery_submission.submit_discovery_run", submit_run)
    headers = _headers(auth_test_data["user_a_id"], auth_test_data["tenant_a_id"])
    csv_content = (
        "full_name,reported_institution,name_variants,previous_affiliations,"
        "research_interests,orcid\n"
        '"Lin Q",Example University,"L Q;L. Qing","Old University;Earlier Institute",'
        'NLP;Vision,0000-0002-1825-0097\n'
        '"Lin Q",Example University,,,,\n'
        '"Invalid Person",Example University,,,AI,0000-0000-0000-0000\n'
    )
    imported = await api_client.post(
        "/api/v1/faculty/import/commit",
        headers=headers,
        files={"file": ("faculty.csv", csv_content, "text/csv")},
    )

    assert imported.status_code == 200
    result = imported.json()
    assert result["imported_count"] == 1
    assert result["skipped_count"] == 1
    assert result["error_count"] == 2
    assert len(result["discovery_jobs"]) == 1
    assert result["discovery_jobs"][0]["trigger_type"] == "faculty_imported"
    assert result["discovery_jobs"][0]["prefect_flow_run_id"] == "prefect-run-csv-1"
    assert len(submitted) == 1

    faculty_id = result["discovery_jobs"][0]["faculty_id"]
    profile = await api_client.get(f"/api/v1/faculty/{faculty_id}", headers=headers)
    assert profile.status_code == 200
    profile_data = profile.json()
    assert {variant["variant_name"] for variant in profile_data["name_variants"]} == {
        "L Q",
        "L. Qing",
    }
    assert {
        affiliation["organization"]: affiliation["is_current"]
        for affiliation in profile_data["affiliations"]
    } == {
        "Example University": True,
        "Old University": False,
        "Earlier Institute": False,
    }
