"""Idempotent demo tenant/user/faculty seed."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.logging import get_logger
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
from app.domain.schemas import validate_orcid

logger = get_logger(__name__)

DEMO_TENANT_NAME = "FRIS Demo Tenant"
DEMO_TENANT_SLUG = "fris-demo"
PILOT_SEED_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "pilot_faculty_seed.csv"


async def seed_demo_data(db: AsyncSession) -> None:
    """Create demo tenant, admin user, and pilot researcher. Idempotent."""

    settings = get_settings()
    if not settings.fris_seed_demo:
        raise RuntimeError("Demo seeding is disabled; set FRIS_SEED_DEMO=true explicitly")
    if settings.app_env.lower() == "production":
        raise RuntimeError("Demo seeding is forbidden when APP_ENV=production")
    if len(settings.admin_default_password) < 12 or settings.admin_default_password.startswith(
        "CHANGE"
    ):
        raise RuntimeError("Set a unique ADMIN_DEFAULT_PASSWORD of at least 12 characters")

    with PILOT_SEED_PATH.open(encoding="utf-8-sig", newline="") as seed_file:
        pilot_data = next(csv.DictReader(seed_file), None)
    if not pilot_data or not pilot_data.get("faculty_name"):
        raise RuntimeError(f"Pilot seed file is missing a faculty row: {PILOT_SEED_PATH}")

    # --- Tenant ---
    tenant_result = await db.execute(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
    tenant: Tenant | None = tenant_result.scalar_one_or_none()
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
    admin_result = await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.username == "admin")
    )
    admin: User | None = admin_result.scalar_one_or_none()
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
    pilot_result = await db.execute(
        select(Faculty).where(
            Faculty.tenant_id == tenant.id,
            Faculty.full_name == pilot_data["faculty_name"].strip(),
        )
    )
    pilot: Faculty | None = pilot_result.scalar_one_or_none()
    if not pilot:
        pilot = Faculty(
            tenant_id=tenant.id,
            full_name=pilot_data["faculty_name"].strip(),
            reported_institution=pilot_data.get("institution", "").strip() or None,
            department=pilot_data.get("department", "").strip() or None,
            profile_url=pilot_data.get("profile_url", "").strip() or None,
            research_interests_text=pilot_data.get("research_interests", "").strip() or None,
            is_demo=True,
            demo_label="DEMO — external researcher; not a member of the customer's university",
        )
        db.add(pilot)
        await db.flush()

        # ORCID
        orcid = pilot_data.get("orcid", "").strip()
        if orcid:
            orcid = validate_orcid(orcid)
            db.add(
                FacultyIdentifier(
                    faculty_id=pilot.id,
                    identifier_type=IdentifierType.orcid,
                    value=orcid,
                    is_verified=False,
                    verification_status=VerificationStatus.self_reported,
                    verification_source="pilot_seed_csv",
                )
            )

        # Name variants
        for variant in [
            v.strip() for v in pilot_data.get("name_variants", "").split(";") if v.strip()
        ]:
            db.add(
                FacultyNameVariant(
                    faculty_id=pilot.id,
                    variant_name=variant,
                    source="pilot_seed",
                )
            )

        # Affiliation
        if pilot_data.get("institution", "").strip():
            db.add(
                FacultyAffiliation(
                    faculty_id=pilot.id,
                    organization=pilot_data["institution"].strip(),
                    department=pilot_data.get("department", "").strip() or None,
                    is_current=True,
                    source="pilot_seed_csv",
                )
            )

        # Research interests
        topics = [
            v.strip() for v in pilot_data.get("research_interests", "").split(";") if v.strip()
        ]
        for topic in topics:
            db.add(
                ResearchInterest(
                    faculty_id=pilot.id,
                    topic=topic,
                    source="pilot_seed",
                )
            )

        await db.flush()
        logger.info("seed_pilot_created", name=pilot.full_name)
    else:
        logger.info("seed_pilot_exists", name=pilot.full_name)

    await db.commit()
    logger.info("seed_complete")
