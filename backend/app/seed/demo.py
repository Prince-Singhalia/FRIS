"""Idempotent demo tenant/user/faculty seed."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.settings import get_settings
from app.db.models import (
    Faculty,
    FacultyAffiliation,
    FacultyIdentifier,
    FacultyNameVariant,
    IdentifierType,
    ResearchInterest,
    Tenant,
    User,
    UserRole,
    VerificationStatus,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

DEMO_TENANT_NAME = "FRIS Demo Tenant"
DEMO_TENANT_SLUG = "fris-demo"


async def seed_demo_data(db: AsyncSession) -> None:
    """Create demo tenant, admin user, and pilot researcher. Idempotent."""

    settings = get_settings()

    # --- Tenant ---
    result = await db.execute(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            name=DEMO_TENANT_NAME,
            slug=DEMO_TENANT_SLUG,
            is_demo=True,
        )
        db.add(tenant)
        await db.flush()
        logger.info("seed_tenant_created", tenant=DEMO_TENANT_NAME)
    else:
        logger.info("seed_tenant_exists", tenant=DEMO_TENANT_NAME)

    # --- Admin user ---
    result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.username == "admin")
    )
    admin = result.scalar_one_or_none()
    if not admin:
        admin = User(
            tenant_id=tenant.id,
            email="admin@fris-demo.local",
            username="admin",
            hashed_password=hash_password(settings.admin_default_password),
            full_name="FRIS Demo Admin",
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        await db.flush()
        logger.info("seed_admin_created", username="admin")
    else:
        logger.info("seed_admin_exists", username="admin")

    # --- Pilot researcher ---
    result = await db.execute(
        select(Faculty).where(
            Faculty.tenant_id == tenant.id,
            Faculty.full_name == "Fei-Fei Li",
        )
    )
    pilot = result.scalar_one_or_none()
    if not pilot:
        pilot = Faculty(
            tenant_id=tenant.id,
            full_name="Fei-Fei Li",
            reported_institution="Stanford University",
            department="Computer Science",
            profile_url="https://profiles.stanford.edu/fei-fei-li",
            research_interests_text="computer vision; deep learning; robotics",
            is_demo=True,
            demo_label="DEMO — external researcher; not a member of the customer's university",
        )
        db.add(pilot)
        await db.flush()

        # ORCID
        db.add(FacultyIdentifier(
            faculty_id=pilot.id,
            identifier_type=IdentifierType.orcid,
            value="0000-0002-7481-0810",
            is_verified=False,
            verification_status=VerificationStatus.self_reported,
            verification_source="pilot_seed",
        ))

        # Name variants
        for variant in ["L. Fei-Fei", "Feifei Li"]:
            db.add(FacultyNameVariant(
                faculty_id=pilot.id,
                variant_name=variant,
                source="pilot_seed",
            ))

        # Affiliation
        db.add(FacultyAffiliation(
            faculty_id=pilot.id,
            organization="Stanford University",
            department="Computer Science",
            is_current=True,
            source="pilot_seed",
        ))

        # Research interests
        for topic in ["computer vision", "deep learning", "robotics"]:
            db.add(ResearchInterest(
                faculty_id=pilot.id,
                topic=topic,
                source="pilot_seed",
            ))

        await db.flush()
        logger.info("seed_pilot_created", name="Fei-Fei Li")
    else:
        logger.info("seed_pilot_exists", name="Fei-Fei Li")

    await db.commit()
    logger.info("seed_complete")
