"""Faculty CRUD and CSV import routes."""

from __future__ import annotations

import csv
import io
import re
import uuid
from urllib.parse import urlsplit

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
    Tenant,
    VerificationStatus,
    AuditAction,
    AuditEvent,
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
MAX_IMPORT_BYTES = 10 * 1024 * 1024
DEMO_LABEL = "DEMO — external researcher; not a member of the customer's university"

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


def _split_semicolon_list(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def _validate_import_fields(data: dict) -> list[str]:
    errors: list[str] = []
    if not data.get("full_name", "").strip():
        errors.append("full_name is required")
    if data.get("profile_url"):
        try:
            parsed = urlsplit(data["profile_url"])
            valid_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except ValueError:
            valid_url = False
        if not valid_url:
            errors.append("profile_url must be an absolute HTTP or HTTPS URL")
    email = data.get("institutional_email")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        errors.append("institutional_email must be a valid email address")
    if data.get("orcid"):
        try:
            data["orcid"] = validate_orcid(data["orcid"])
        except ValueError as error:
            errors.append(str(error))
    return errors


def _mapped_row(raw_row: dict, headers_mapped: dict[str, str]) -> dict:
    data: dict[str, str] = {}
    for original, mapped in headers_mapped.items():
        value = raw_row.get(original)
        if value is not None and value.strip():
            data[mapped] = value.strip()
    return data


async def _read_csv_upload(file: UploadFile) -> tuple[list[str], list[dict[str, str | None]]]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only CSV files are accepted")
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise HTTPException(status_code=422, detail="CSV has no headers")
        return list(reader.fieldnames), list(reader)
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="CSV must use UTF-8 encoding") from error
    except csv.Error as error:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {error}") from error


@router.post("", response_model=FacultyResponse, status_code=201)
async def create_faculty(
    body: FacultyCreate,
    current_user: TokenData = Depends(require_roles("admin", "research_officer")),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = uuid.UUID(current_user.tenant_id)
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Tenant not found")
    if body.is_demo and not tenant.is_demo:
        raise HTTPException(status_code=422, detail="Demo records can only be created in a demo tenant")
    is_demo = tenant.is_demo or body.is_demo

    # Check for duplicate name in tenant
    existing = await db.execute(
        select(Faculty).where(
            Faculty.tenant_id == tenant_id,
            func.lower(Faculty.full_name) == body.full_name.casefold(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Faculty '{body.full_name}' already exists in tenant")

    faculty = Faculty(
        tenant_id=tenant_id,
        full_name=body.full_name,
        reported_institution=body.reported_institution,
        department=body.department,
        institutional_email=body.institutional_email,
        profile_url=body.profile_url,
        research_interests_text=body.research_interests_text,
        is_demo=is_demo,
        demo_label=(body.demo_label or DEMO_LABEL) if is_demo else None,
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
            verification_source="manual_entry",
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
        tenant_id=tenant_id,
        user_id=uuid.UUID(current_user.user_id),
        action=AuditAction.faculty_created,
        entity_type="faculty",
        entity_id=faculty.id,
        detail={"full_name": body.full_name, "is_demo": is_demo},
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
    tenant_id = uuid.UUID(current_user.tenant_id)
    base_q = select(Faculty).where(Faculty.tenant_id == tenant_id)
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
    tenant_id = uuid.UUID(current_user.tenant_id)
    result = await db.execute(
        select(Faculty).where(
            Faculty.id == faculty_id,
            Faculty.tenant_id == tenant_id,
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
    tenant_id = uuid.UUID(current_user.tenant_id)
    result = await db.execute(
        select(Faculty).where(
            Faculty.id == faculty_id,
            Faculty.tenant_id == tenant_id,
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
    headers_found, raw_rows = await _read_csv_upload(file)
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
    seen_names: set[str] = set()

    for i, raw_row in enumerate(raw_rows, start=2):
        data = _mapped_row(raw_row, headers_mapped)
        errors = _validate_import_fields(data)

        # Check duplicates within tenant
        dup_id = None
        duplicate_in_upload = False
        if data.get("full_name"):
            normalized_name = data["full_name"].casefold()
            duplicate_in_upload = normalized_name in seen_names
            seen_names.add(normalized_name)
            existing = await db.execute(
                select(Faculty.id).where(
                    Faculty.tenant_id == tenant_id,
                    func.lower(Faculty.full_name) == normalized_name,
                )
            )
            dup = existing.scalar_one_or_none()
            if dup:
                dup_id = dup
            if dup_id or duplicate_in_upload:
                errors.append("duplicate faculty name in this tenant or upload")

        rows.append(CSVRowPreview(
            row_number=i,
            data=data,
            is_valid=len(errors) == 0,
            errors=errors,
            duplicate_of=dup_id,
            duplicate_in_upload=duplicate_in_upload,
        ))

    return CSVImportPreview(
        total_rows=len(rows),
        valid_rows=sum(1 for r in rows if r.is_valid),
        invalid_rows=sum(1 for r in rows if not r.is_valid),
        duplicate_rows=sum(1 for r in rows if r.duplicate_of or r.duplicate_in_upload),
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
    headers_found, raw_rows = await _read_csv_upload(file)
    headers_mapped = {}
    for h in headers_found:
        mapped = HEADER_MAP.get(h.lower().strip())
        if mapped:
            headers_mapped[h] = mapped
    if "full_name" not in headers_mapped.values():
        raise HTTPException(status_code=422, detail="CSV must contain a faculty_name, full_name, or name column")

    batch_id = uuid.uuid4()
    tenant_id = uuid.UUID(current_user.tenant_id)
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Tenant not found")

    imported = 0
    skipped = 0
    errors_list: list[dict] = []
    seen_names: set[str] = set()

    for i, raw_row in enumerate(raw_rows, start=2):
        data = _mapped_row(raw_row, headers_mapped)
        row_errors = _validate_import_fields(data)
        if row_errors:
            errors_list.extend({"row": i, "error": error} for error in row_errors)
            continue

        normalized_name = data["full_name"].casefold()
        if normalized_name in seen_names:
            skipped += 1
            errors_list.append({"row": i, "error": "duplicate faculty name in this upload; row skipped"})
            continue
        seen_names.add(normalized_name)
        existing = await db.execute(
            select(Faculty.id).where(
                Faculty.tenant_id == tenant_id,
                func.lower(Faculty.full_name) == normalized_name,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            errors_list.append({"row": i, "error": "faculty already exists in this tenant; row skipped"})
            continue

        faculty = Faculty(
            tenant_id=tenant_id,
            full_name=data["full_name"],
            reported_institution=data.get("reported_institution"),
            department=data.get("department"),
            institutional_email=data.get("institutional_email"),
            profile_url=data.get("profile_url"),
            research_interests_text=data.get("research_interests"),
            is_demo=tenant.is_demo,
            demo_label=DEMO_LABEL if tenant.is_demo else None,
            import_batch_id=batch_id,
        )
        db.add(faculty)
        await db.flush()

        if data.get("orcid"):
            db.add(FacultyIdentifier(
                faculty_id=faculty.id,
                identifier_type=IdentifierType.orcid,
                value=data["orcid"],
                is_verified=False,
                verification_status=VerificationStatus.self_reported,
                verification_source="csv_import",
            ))

        for v in _split_semicolon_list(data.get("name_variants")):
            db.add(FacultyNameVariant(faculty_id=faculty.id, variant_name=v, source="csv_import"))

        if data.get("reported_institution"):
            db.add(FacultyAffiliation(
                faculty_id=faculty.id,
                organization=data["reported_institution"],
                department=data.get("department"),
                is_current=True,
                source="csv_import",
            ))

        for previous_affiliation in _split_semicolon_list(data.get("previous_affiliations")):
            db.add(FacultyAffiliation(
                faculty_id=faculty.id,
                organization=previous_affiliation,
                is_current=False,
                source="csv_import_previous_affiliation",
            ))

        for t in _split_semicolon_list(data.get("research_interests")):
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

    tenant_id = uuid.UUID(current_user.tenant_id)
    # Verify faculty belongs to tenant
    fac = await db.execute(
        select(Faculty).where(Faculty.id == faculty_id, Faculty.tenant_id == tenant_id)
    )
    if not fac.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Faculty not found")

    base_q = (
        select(Publication)
        .join(FacultyPublicationMatch, FacultyPublicationMatch.publication_id == Publication.id)
        .where(
            FacultyPublicationMatch.faculty_id == faculty_id,
            FacultyPublicationMatch.tenant_id == tenant_id,
        )
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
