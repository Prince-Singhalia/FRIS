"""Faculty CRUD and CSV import routes."""

from __future__ import annotations

import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user, require_roles
from app.db.models import (
    Faculty,
    FacultyAffiliation,
    FacultyIdentifier,
    FacultyNameVariant,
    IdentifierType,
    ResearchInterest,
    VerificationStatus,
    AuditEvent,
    AuditAction,
)
from app.db.session import get_db
from app.domain.schemas import (
    CSVImportPreview,
    CSVImportResult,
    CSVRowPreview,
    FacultyCreate,
    FacultyResponse,
    FacultyUpdate,
    PaginatedResponse,
    validate_orcid,
)

router = APIRouter()

# CSV header aliases
HEADER_MAP = {
    "faculty_name": "full_name",
    "full_name": "full_name",
    "name": "full_name",
    "institution": "reported_institution",
    "reported_institution": "reported_institution",
    "affiliation": "reported_institution",
    "department": "department",
    "dept": "department",
    "institutional_email": "institutional_email",
    "email": "institutional_email",
    "orcid": "orcid",
    "orcid_id": "orcid",
    "profile_url": "profile_url",
    "url": "profile_url",
    "name_variants": "name_variants",
    "aliases": "name_variants",
    "previous_affiliations": "previous_affiliations",
    "research_interests": "research_interests",
}


@router.post("", response_model=FacultyResponse, status_code=201)
async def create_faculty(
    body: FacultyCreate,
    current_user: TokenData = Depends(require_roles("admin", "research_officer")),
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate name in tenant
    existing = await db.execute(
        select(Faculty).where(
            Faculty.tenant_id == current_user.tenant_id,
            Faculty.full_name == body.full_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Faculty '{body.full_name}' already exists in tenant")

    faculty = Faculty(
        tenant_id=uuid.UUID(current_user.tenant_id),
        full_name=body.full_name,
        reported_institution=body.reported_institution,
        department=body.department,
        institutional_email=body.institutional_email,
        profile_url=body.profile_url,
        research_interests_text=body.research_interests_text,
        is_demo=body.is_demo,
        demo_label=body.demo_label,
    )
    db.add(faculty)
    await db.flush()

    # Add ORCID identifier if provided
    if body.orcid:
        orcid_id = FacultyIdentifier(
            faculty_id=faculty.id,
            identifier_type=IdentifierType.orcid,
            value=body.orcid,
            is_verified=False,
            verification_status=VerificationStatus.self_reported,
            verification_source="csv_import" if body.import_batch_id else "manual_entry" if not hasattr(body, 'import_batch_id') else "manual_entry",
        )
        db.add(orcid_id)

    # Add name variants
    for variant in body.name_variants:
        v = variant.strip()
        if v:
            db.add(FacultyNameVariant(faculty_id=faculty.id, variant_name=v, source="user_input"))

    # Add reported institution as affiliation
    if body.reported_institution:
        db.add(FacultyAffiliation(
            faculty_id=faculty.id,
            organization=body.reported_institution,
            department=body.department,
            is_current=True,
            source="user_input",
        ))

    # Add research interests
    if body.research_interests_text:
        for topic in body.research_interests_text.split(";"):
            t = topic.strip()
            if t:
                db.add(ResearchInterest(faculty_id=faculty.id, topic=t, source="user_input"))

    # Audit
    db.add(AuditEvent(
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_id=uuid.UUID(current_user.user_id),
        action=AuditAction.faculty_created,
        entity_type="faculty",
        entity_id=faculty.id,
        detail={"full_name": body.full_name, "is_demo": body.is_demo},
    ))

    await db.flush()
    # Reload with relationships
    await db.refresh(faculty, attribute_names=["identifiers", "name_variants", "affiliations"])
    return faculty


@router.get("", response_model=PaginatedResponse)
async def list_faculty(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(Faculty).where(Faculty.tenant_id == current_user.tenant_id)
    if search:
        base_q = base_q.where(Faculty.full_name.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    items_q = base_q.order_by(Faculty.full_name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(items_q)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[FacultyResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{faculty_id}", response_model=FacultyResponse)
async def get_faculty(
    faculty_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Faculty).where(
            Faculty.id == faculty_id,
            Faculty.tenant_id == current_user.tenant_id,
        )
    )
    faculty = result.scalar_one_or_none()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")
    return faculty


@router.patch("/{faculty_id}", response_model=FacultyResponse)
async def update_faculty(
    faculty_id: uuid.UUID,
    body: FacultyUpdate,
    current_user: TokenData = Depends(require_roles("admin", "research_officer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Faculty).where(
            Faculty.id == faculty_id,
            Faculty.tenant_id == current_user.tenant_id,
        )
    )
    faculty = result.scalar_one_or_none()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(faculty, field, value)

    db.add(AuditEvent(
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_id=uuid.UUID(current_user.user_id),
        action=AuditAction.faculty_updated,
        entity_type="faculty",
        entity_id=faculty.id,
        detail={"updated_fields": list(update_data.keys())},
    ))

    await db.flush()
    await db.refresh(faculty, attribute_names=["identifiers", "name_variants", "affiliations"])
    return faculty


@router.post("/import/preview", response_model=CSVImportPreview)
async def import_preview(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_roles("admin", "research_officer")),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only CSV files are accepted")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    text = content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV has no headers")

    # Map headers
    headers_found = list(reader.fieldnames)
    headers_mapped = {}
    for h in headers_found:
        mapped = HEADER_MAP.get(h.lower().strip())
        if mapped:
            headers_mapped[h] = mapped

    if "full_name" not in headers_mapped.values():
        raise HTTPException(
            status_code=422,
            detail=f"CSV must contain a name column. Found: {headers_found}. Expected one of: faculty_name, full_name, name",
        )

    rows: list[CSVRowPreview] = []
    tenant_id = uuid.UUID(current_user.tenant_id)

    for i, raw_row in enumerate(reader, start=2):  # row 1 is header
        errors: list[str] = []
        data: dict = {}

        for orig_col, mapped_col in headers_mapped.items():
            val = raw_row.get(orig_col, "").strip()
            if val:
                data[mapped_col] = val

        if not data.get("full_name"):
            errors.append("full_name is required")

        # Validate ORCID if present
        if data.get("orcid"):
            try:
                data["orcid"] = validate_orcid(data["orcid"])
            except ValueError as e:
                errors.append(str(e))

        # Check duplicates within tenant
        dup_id = None
        if data.get("full_name"):
            existing = await db.execute(
                select(Faculty.id).where(
                    Faculty.tenant_id == tenant_id,
                    Faculty.full_name == data["full_name"],
                )
            )
            dup = existing.scalar_one_or_none()
            if dup:
                dup_id = dup

        rows.append(CSVRowPreview(
            row_number=i,
            data=data,
            is_valid=len(errors) == 0,
            errors=errors,
            duplicate_of=dup_id,
        ))

    return CSVImportPreview(
        total_rows=len(rows),
        valid_rows=sum(1 for r in rows if r.is_valid),
        invalid_rows=sum(1 for r in rows if not r.is_valid),
        duplicate_rows=sum(1 for r in rows if r.duplicate_of),
        rows=rows,
        headers_found=headers_found,
        headers_mapped=headers_mapped,
    )


@router.post("/import/commit", response_model=CSVImportResult)
async def import_commit(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_roles("admin", "research_officer")),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV has no headers")

    headers_mapped = {}
    for h in reader.fieldnames:
        mapped = HEADER_MAP.get(h.lower().strip())
        if mapped:
            headers_mapped[h] = mapped

    batch_id = uuid.uuid4()
    tenant_id = uuid.UUID(current_user.tenant_id)
    imported = 0
    skipped = 0
    errors_list: list[dict] = []

    for i, raw_row in enumerate(reader, start=2):
        data: dict = {}
        for orig_col, mapped_col in headers_mapped.items():
            val = raw_row.get(orig_col, "").strip()
            if val:
                data[mapped_col] = val

        if not data.get("full_name"):
            errors_list.append({"row": i, "error": "full_name is required"})
            continue

        # Validate ORCID
        orcid_val = None
        if data.get("orcid"):
            try:
                orcid_val = validate_orcid(data["orcid"])
            except ValueError as e:
                errors_list.append({"row": i, "error": str(e)})
                continue

        # Skip duplicates
        existing = await db.execute(
            select(Faculty.id).where(
                Faculty.tenant_id == tenant_id,
                Faculty.full_name == data["full_name"],
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Parse name variants
        name_variants_raw = data.get("name_variants", "")
        variants = [v.strip() for v in name_variants_raw.split(";") if v.strip()]

        # Parse research interests
        interests_raw = data.get("research_interests", "")
        interests = [t.strip() for t in interests_raw.split(";") if t.strip()]

        faculty = Faculty(
            tenant_id=tenant_id,
            full_name=data["full_name"],
            reported_institution=data.get("reported_institution"),
            department=data.get("department"),
            institutional_email=data.get("institutional_email"),
            profile_url=data.get("profile_url"),
            research_interests_text=data.get("research_interests"),
            is_demo=True,  # CSV imports into demo tenant are demo data
            demo_label="DEMO — external researcher; not a member of the customer's university",
            import_batch_id=batch_id,
        )
        db.add(faculty)
        await db.flush()

        if orcid_val:
            db.add(FacultyIdentifier(
                faculty_id=faculty.id,
                identifier_type=IdentifierType.orcid,
                value=orcid_val,
                is_verified=False,
                verification_status=VerificationStatus.self_reported,
                verification_source="csv_import",
            ))

        for v in variants:
            db.add(FacultyNameVariant(faculty_id=faculty.id, variant_name=v, source="csv_import"))

        if data.get("reported_institution"):
            db.add(FacultyAffiliation(
                faculty_id=faculty.id,
                organization=data["reported_institution"],
                department=data.get("department"),
                is_current=True,
                source="csv_import",
            ))

        for t in interests:
            db.add(ResearchInterest(faculty_id=faculty.id, topic=t, source="csv_import"))

        imported += 1

    # Audit
    db.add(AuditEvent(
        tenant_id=tenant_id,
        user_id=uuid.UUID(current_user.user_id),
        action=AuditAction.faculty_imported,
        entity_type="faculty",
        detail={"batch_id": str(batch_id), "imported": imported, "skipped": skipped, "errors": len(errors_list)},
    ))

    return CSVImportResult(
        batch_id=batch_id,
        imported_count=imported,
        skipped_count=skipped,
        error_count=len(errors_list),
        errors=errors_list,
    )


@router.get("/{faculty_id}/publications")
async def get_faculty_publications(
    faculty_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models import FacultyPublicationMatch, Publication

    # Verify faculty belongs to tenant
    fac = await db.execute(
        select(Faculty).where(Faculty.id == faculty_id, Faculty.tenant_id == current_user.tenant_id)
    )
    if not fac.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Faculty not found")

    base_q = (
        select(Publication)
        .join(FacultyPublicationMatch, FacultyPublicationMatch.publication_id == Publication.id)
        .where(FacultyPublicationMatch.faculty_id == faculty_id)
    )
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    items_q = base_q.order_by(Publication.publication_year.desc().nullslast()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(items_q)
    items = result.scalars().all()

    from app.domain.schemas import PublicationResponse
    return PaginatedResponse(
        items=[PublicationResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )
