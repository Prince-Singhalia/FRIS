"""Review queue routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user, require_roles
from app.db.models import AuditAction, AuditEvent, ReviewItem
from app.db.session import get_db
from app.domain.schemas import PaginatedResponse, ReviewDecisionRequest, ReviewItemResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str = Query("pending"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = uuid.UUID(current_user.tenant_id)
    base_q = select(ReviewItem).where(
        ReviewItem.tenant_id == tenant_id,
        ReviewItem.status == status,
    )
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    items_q = base_q.order_by(ReviewItem.priority.desc(), ReviewItem.created_at.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(items_q)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[ReviewItemResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("/{review_id}/decision", response_model=ReviewItemResponse)
async def submit_decision(
    review_id: uuid.UUID,
    body: ReviewDecisionRequest,
    current_user: TokenData = Depends(require_roles("admin", "research_officer", "reviewer")),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = uuid.UUID(current_user.tenant_id)
    result = await db.execute(
        select(ReviewItem).where(
            ReviewItem.id == review_id,
            ReviewItem.tenant_id == tenant_id,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if body.decision not in ("accept", "reject", "defer"):
        raise HTTPException(status_code=422, detail="Decision must be accept, reject, or defer")

    review.decision = body.decision
    review.decision_rationale = body.rationale
    review.reviewer_id = uuid.UUID(current_user.user_id)
    review.decided_at = datetime.now(timezone.utc)
    review.status = "decided" if body.decision != "defer" else "deferred"

    # Audit
    db.add(AuditEvent(
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_id=uuid.UUID(current_user.user_id),
        action=AuditAction.review_decision,
        entity_type=review.entity_type,
        entity_id=review.entity_id,
        detail={
            "review_id": str(review.id),
            "decision": body.decision,
            "rationale": body.rationale,
        },
    ))

    await db.flush()
    await db.refresh(review)
    return review
