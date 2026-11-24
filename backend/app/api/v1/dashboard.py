"""Dashboard routes — overview and per-faculty stats."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.settings import get_settings
from app.db.models import (
    DiscoveryJob,
    Faculty,
    FacultyPublicationMatch,
    Publication,
    ReviewItem,
)
from app.db.session import get_db
from app.domain.schemas import (
    ConnectorStatusResponse,
    DashboardOverview,
    DiscoveryJobResponse,
)

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(current_user.tenant_id)

    # Counts
    total_faculty = (
        await db.execute(select(func.count(Faculty.id)).where(Faculty.tenant_id == tid))
    ).scalar() or 0

    total_pubs = (
        await db.execute(select(func.count(Publication.id)).where(Publication.tenant_id == tid))
    ).scalar() or 0

    pending_reviews = (
        await db.execute(
            select(func.count(ReviewItem.id)).where(
                ReviewItem.tenant_id == tid, ReviewItem.status == "pending"
            )
        )
    ).scalar() or 0

    # Recent jobs
    jobs_q = (
        select(DiscoveryJob)
        .where(DiscoveryJob.tenant_id == tid)
        .order_by(DiscoveryJob.created_at.desc())
        .limit(10)
    )
    jobs = (await db.execute(jobs_q)).scalars().all()

    # Publication years
    year_q = (
        select(Publication.publication_year, func.count(Publication.id))
        .where(Publication.tenant_id == tid, Publication.publication_year.isnot(None))
        .group_by(Publication.publication_year)
        .order_by(Publication.publication_year)
    )
    year_rows = (await db.execute(year_q)).all()
    pub_years = {row[0]: row[1] for row in year_rows}

    # Connector statuses from connectors module
    from app.api.v1.connectors import DEFAULT_CONNECTORS
    settings = get_settings()
    conn_statuses = []
    for conn in DEFAULT_CONNECTORS:
        is_configured = conn["credential_check"](settings)
        conn_statuses.append(ConnectorStatusResponse(
            provider=conn["provider"],
            display_name=conn["display_name"],
            is_enabled=conn["provider"] != "ieee",
            is_configured=is_configured,
            health_status="not_checked" if is_configured else "not_configured",
            capabilities=conn["capabilities"],
            terms_url=conn["terms_url"],
        ))

    return DashboardOverview(
        tenant_id=tid,
        total_faculty=total_faculty,
        total_publications=total_pubs,
        pending_reviews=pending_reviews,
        recent_jobs=[DiscoveryJobResponse.model_validate(j) for j in jobs],
        connector_statuses=conn_statuses,
        publication_years=pub_years,
    )


@router.get("/faculty/{faculty_id}")
async def faculty_dashboard(
    faculty_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(current_user.tenant_id)
    result = await db.execute(
        select(Faculty).where(Faculty.id == faculty_id, Faculty.tenant_id == tid)
    )
    faculty = result.scalar_one_or_none()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    pub_count = (
        await db.execute(
            select(func.count(FacultyPublicationMatch.id)).where(
                FacultyPublicationMatch.faculty_id == faculty_id,
                FacultyPublicationMatch.tenant_id == tid,
            )
        )
    ).scalar() or 0

    latest_job = (
        await db.execute(
            select(DiscoveryJob)
            .where(DiscoveryJob.faculty_id == faculty_id, DiscoveryJob.tenant_id == tid)
            .order_by(DiscoveryJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    from app.domain.schemas import FacultyResponse
    return {
        "faculty": FacultyResponse.model_validate(faculty),
        "publication_count": pub_count,
        "latest_job": DiscoveryJobResponse.model_validate(latest_job) if latest_job else None,
    }
