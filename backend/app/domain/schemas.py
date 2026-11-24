"""Domain Pydantic schemas for API request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    items: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    pages: int = 0


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------

class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_demo: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Faculty
# ---------------------------------------------------------------------------

class FacultyCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=500)
    reported_institution: str | None = Field(default=None, max_length=500)
    department: str | None = Field(default=None, max_length=500)
    institutional_email: str | None = Field(default=None, max_length=320)
    profile_url: str | None = Field(default=None, max_length=2048)
    research_interests_text: str | None = None
    orcid: str | None = Field(default=None, max_length=50)
    name_variants: list[str] = Field(default_factory=list)
    is_demo: bool = False
    demo_label: str | None = None

    @field_validator("orcid")
    @classmethod
    def validate_orcid_format(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return validate_orcid(v)


class FacultyUpdate(BaseModel):
    full_name: str | None = None
    reported_institution: str | None = None
    department: str | None = None
    institutional_email: str | None = None
    profile_url: str | None = None
    research_interests_text: str | None = None


class FacultyIdentifierResponse(BaseModel):
    id: uuid.UUID
    identifier_type: str
    value: str
    is_verified: bool
    verification_status: str
    verification_source: str | None = None
    verified_at: datetime | None = None

    model_config = {"from_attributes": True}


class FacultyNameVariantResponse(BaseModel):
    id: uuid.UUID
    variant_name: str
    source: str | None = None

    model_config = {"from_attributes": True}


class FacultyAffiliationResponse(BaseModel):
    id: uuid.UUID
    organization: str
    department: str | None = None
    is_current: bool
    start_date: datetime | None = None
    end_date: datetime | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class FacultyResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    full_name: str
    reported_institution: str | None = None
    department: str | None = None
    profile_url: str | None = None
    research_interests_text: str | None = None
    is_demo: bool = False
    demo_label: str | None = None
    created_at: datetime
    updated_at: datetime
    identifiers: list[FacultyIdentifierResponse] = Field(default_factory=list)
    name_variants: list[FacultyNameVariantResponse] = Field(default_factory=list)
    affiliations: list[FacultyAffiliationResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

class CSVRowPreview(BaseModel):
    row_number: int
    data: dict
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    duplicate_of: uuid.UUID | None = None


class CSVImportPreview(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    rows: list[CSVRowPreview]
    headers_found: list[str]
    headers_mapped: dict[str, str]


class CSVImportResult(BaseModel):
    batch_id: uuid.UUID
    imported_count: int
    skipped_count: int
    error_count: int
    errors: list[dict]


# ---------------------------------------------------------------------------
# Discovery Jobs
# ---------------------------------------------------------------------------

class DiscoveryJobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    faculty_id: uuid.UUID
    status: str
    trigger_type: str
    triggered_by: str | None = None
    correlation_id: str
    summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_detail: str | None = None
    created_at: datetime
    connector_runs: list[ConnectorRunResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConnectorRunResponse(BaseModel):
    id: uuid.UUID
    provider: str
    status: str
    records_fetched: int = 0
    records_valid: int = 0
    records_quarantined: int = 0
    request_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    warnings: list | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Connector Status
# ---------------------------------------------------------------------------

class ConnectorStatusResponse(BaseModel):
    provider: str
    display_name: str
    is_enabled: bool
    is_configured: bool
    health_status: str | None = None
    last_health_check: datetime | None = None
    capabilities: dict | None = None
    terms_url: str | None = None


# ---------------------------------------------------------------------------
# Review Queue
# ---------------------------------------------------------------------------

class ReviewItemResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    review_type: str
    entity_type: str
    entity_id: uuid.UUID
    related_entity_id: uuid.UUID | None = None
    status: str
    priority: int = 0
    evidence: dict | None = None
    explanation: str | None = None
    reviewer_id: uuid.UUID | None = None
    decision: str | None = None
    decided_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(description="accept, reject, defer")
    rationale: str | None = None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardOverview(BaseModel):
    tenant_id: uuid.UUID
    total_faculty: int = 0
    total_publications: int = 0
    pending_reviews: int = 0
    recent_jobs: list[DiscoveryJobResponse] = Field(default_factory=list)
    connector_statuses: list[ConnectorStatusResponse] = Field(default_factory=list)
    publication_years: dict[int, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

class PublicationSourceResponse(BaseModel):
    id: uuid.UUID
    provider: str
    provider_work_id: str
    source_title: str | None = None
    source_doi: str | None = None
    source_year: int | None = None
    source_venue: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    retrieved_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthorshipResponse(BaseModel):
    id: uuid.UUID
    author_position: int | None = None
    author_name: str
    orcid: str | None = None
    provider: str | None = None
    raw_affiliation: str | None = None

    model_config = {"from_attributes": True}


class PublicationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    doi: str | None = None
    publication_year: int | None = None
    publication_date: str | None = None
    venue: str | None = None
    publication_type: str | None = None
    abstract: str | None = None
    landing_url: str | None = None
    is_open_access: bool | None = None
    citation_count: int | None = None
    created_at: datetime
    sources: list[PublicationSourceResponse] = Field(default_factory=list)
    authorships: list[AuthorshipResponse] = Field(default_factory=list)
    match_status: str | None = None
    confidence_score: float | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ORCID validation utility
# ---------------------------------------------------------------------------

def validate_orcid(value: str) -> str:
    """Validate ORCID format and checksum. Returns cleaned ORCID or raises ValueError."""
    cleaned = value.strip().upper()
    # Strip common prefixes
    for prefix in ["HTTPS://ORCID.ORG/", "HTTP://ORCID.ORG/", "ORCID.ORG/", "ORCID:"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]

    # Must be XXXX-XXXX-XXXX-XXXX where X is 0-9 and last can be X
    cleaned = cleaned.replace(" ", "")
    parts = cleaned.split("-")
    if len(parts) != 4 or not all(len(p) == 4 for p in parts):
        raise ValueError(f"Invalid ORCID format: {value}")

    digits_str = cleaned.replace("-", "")
    if len(digits_str) != 16:
        raise ValueError(f"Invalid ORCID length: {value}")

    # Validate characters (last can be X for checksum=10)
    for i, c in enumerate(digits_str):
        if i < 15:
            if not c.isdigit():
                raise ValueError(f"Invalid ORCID character at position {i}: {c}")
        else:
            if not (c.isdigit() or c == "X"):
                raise ValueError(f"Invalid ORCID check digit: {c}")

    # Verify checksum (ISO 7064 Mod 11,2)
    total = 0
    for c in digits_str[:-1]:
        total = (total + int(c)) * 2
    remainder = total % 11
    check = (12 - remainder) % 11
    expected = "X" if check == 10 else str(check)
    if digits_str[-1] != expected:
        raise ValueError(f"ORCID checksum failed: expected {expected}, got {digits_str[-1]}")

    return cleaned  # e.g. "0000-0002-7481-0810"
