"""SQLAlchemy ORM models for all FRIS entities."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    research_officer = "research_officer"
    reviewer = "reviewer"
    viewer = "viewer"


class IdentifierType(str, enum.Enum):
    orcid = "orcid"
    openalex = "openalex"
    semantic_scholar = "semantic_scholar"
    scopus = "scopus"
    wos = "wos"
    dblp = "dblp"
    crossref = "crossref"


class VerificationStatus(str, enum.Enum):
    unverified = "unverified"
    self_reported = "self_reported"
    system_verified = "system_verified"
    admin_verified = "admin_verified"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class ConnectorRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"
    auth_failed = "auth_failed"
    rate_limited = "rate_limited"


class MatchStatus(str, enum.Enum):
    verified = "verified"
    probable = "probable"
    review_required = "review_required"
    rejected = "rejected"
    pending = "pending"


class ParseStatus(str, enum.Enum):
    valid = "valid"
    invalid = "invalid"
    quarantined = "quarantined"
    partial = "partial"


class ReviewAction(str, enum.Enum):
    accept = "accept"
    reject = "reject"
    defer = "defer"
    link_identifier = "link_identifier"
    correct_affiliation = "correct_affiliation"
    request_rediscovery = "request_rediscovery"


class AuditAction(str, enum.Enum):
    login = "login"
    faculty_created = "faculty_created"
    faculty_updated = "faculty_updated"
    faculty_deleted = "faculty_deleted"
    faculty_imported = "faculty_imported"
    discovery_triggered = "discovery_triggered"
    review_decision = "review_decision"
    identifier_changed = "identifier_changed"
    publication_merged = "publication_merged"
    publication_unmerged = "publication_unmerged"
    connector_configured = "connector_configured"


class PublicationRelationType(str, enum.Enum):
    preprint_final = "preprint_final"
    version = "version"
    correction = "correction"
    translation = "translation"
    extension = "extension"
    related = "related"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # relationships
    users: Mapped[list[User]] = relationship(back_populates="tenant", lazy="selectin")
    faculty_members: Mapped[list[Faculty]] = relationship(back_populates="tenant", lazy="selectin")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
        UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Faculty(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "faculty"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(500), nullable=False)
    reported_institution: Mapped[str | None] = mapped_column(String(500), nullable=True)
    department: Mapped[str | None] = mapped_column(String(500), nullable=True)
    institutional_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    research_interests_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    demo_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_faculty_tenant_name", "tenant_id", "full_name"),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="faculty_members")
    identifiers: Mapped[list[FacultyIdentifier]] = relationship(
        back_populates="faculty", lazy="selectin", cascade="all, delete-orphan"
    )
    name_variants: Mapped[list[FacultyNameVariant]] = relationship(
        back_populates="faculty", lazy="selectin", cascade="all, delete-orphan"
    )
    affiliations: Mapped[list[FacultyAffiliation]] = relationship(
        back_populates="faculty", lazy="selectin", cascade="all, delete-orphan"
    )
    research_interests: Mapped[list[ResearchInterest]] = relationship(
        back_populates="faculty", lazy="selectin", cascade="all, delete-orphan"
    )


class FacultyIdentifier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "faculty_identifiers"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[IdentifierType] = mapped_column(SAEnum(IdentifierType), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus), default=VerificationStatus.unverified, nullable=False
    )
    verification_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("faculty_id", "identifier_type", "value", name="uq_faculty_identifier"),
    )

    faculty: Mapped[Faculty] = relationship(back_populates="identifiers")


class FacultyNameVariant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "faculty_name_variants"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint("faculty_id", "variant_name", name="uq_faculty_name_variant"),
    )

    faculty: Mapped[Faculty] = relationship(back_populates="name_variants")


class FacultyAffiliation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "faculty_affiliations"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization: Mapped[str] = mapped_column(String(500), nullable=False)
    department: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    faculty: Mapped[Faculty] = relationship(back_populates="affiliations")


class ResearchInterest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_interests"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    faculty: Mapped[Faculty] = relationship(back_populates="research_interests")


class ConnectorConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connector_configs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    terms_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # never store secrets here
    health_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_connector_tenant_provider"),
    )


class DiscoveryJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.pending, nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)  # manual, scheduled, faculty_created, retry
    triggered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    selected_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_discovery_job_tenant_status", "tenant_id", "status"),
        Index("ix_discovery_job_faculty", "faculty_id"),
    )

    connector_runs: Mapped[list[ConnectorRun]] = relationship(
        back_populates="job", lazy="selectin", cascade="all, delete-orphan"
    )


class ConnectorRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connector_runs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ConnectorRunStatus] = mapped_column(
        SAEnum(ConnectorRunStatus), default=ConnectorRunStatus.pending, nullable=False
    )
    records_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_valid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_quarantined: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)

    job: Mapped[DiscoveryJob] = relationship(back_populates="connector_runs")


class SyncCheckpoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sync_checkpoints"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    cursor_value: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "faculty_id", "provider", name="uq_sync_checkpoint"),
    )


class SourceRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_records"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_record_id: Mapped[str] = mapped_column(String(500), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    normalized_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    parse_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), default=ParseStatus.valid, nullable=False
    )
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    connector_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connector_runs.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_record_id", name="uq_source_record_provider_id"),
        Index("ix_source_record_tenant_provider", "tenant_id", "provider"),
    )


class AuthorCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "author_candidates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_author_id: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_orcid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_affiliation: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    works_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discovery_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_jobs.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("faculty_id", "provider", "provider_author_id", name="uq_author_candidate"),
        Index("ix_author_candidate_faculty", "faculty_id"),
    )

    match_decisions: Mapped[list[MatchDecision]] = relationship(
        back_populates="author_candidate", lazy="selectin", cascade="all, delete-orphan"
    )


class MatchDecision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "match_decisions"

    author_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("author_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    status: Mapped[MatchStatus] = mapped_column(SAEnum(MatchStatus), nullable=False, index=True)
    positive_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    negative_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewer_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reviewer_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    author_candidate: Mapped[AuthorCandidate] = relationship(back_populates="match_decisions")


class Publication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "publications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    doi: Mapped[str | None] = mapped_column(String(500), nullable=True)
    normalized_doi: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    publication_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    venue_issn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publication_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    landing_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_open_access: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    merge_history: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_publication_tenant_doi", "tenant_id", "normalized_doi"),
        Index("ix_publication_tenant_year", "tenant_id", "publication_year"),
    )

    sources: Mapped[list[PublicationSource]] = relationship(
        back_populates="publication", lazy="selectin", cascade="all, delete-orphan"
    )
    authorships: Mapped[list[Authorship]] = relationship(
        back_populates="publication", lazy="selectin", cascade="all, delete-orphan"
    )
    faculty_matches: Mapped[list[FacultyPublicationMatch]] = relationship(
        back_populates="publication", lazy="selectin", cascade="all, delete-orphan"
    )


class PublicationSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "publication_sources"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_records.id"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_work_id: Mapped[str] = mapped_column(String(500), nullable=False)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doi: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_venue: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("publication_id", "provider", "provider_work_id", name="uq_pub_source"),
    )

    publication: Mapped[Publication] = relationship(back_populates="sources")


class FacultyPublicationMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "faculty_publication_matches"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    status: Mapped[MatchStatus] = mapped_column(SAEnum(MatchStatus), nullable=False, index=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("faculty_id", "publication_id", name="uq_faculty_pub_match"),
    )

    publication: Mapped[Publication] = relationship(back_populates="faculty_matches")


class Authorship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "authorships"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_spelling: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    orcid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_author_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_affiliation: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    publication: Mapped[Publication] = relationship(back_populates="authorships")


class PublicationRelation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "publication_relations"

    publication_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id"), nullable=False, index=True
    )
    publication_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publications.id"), nullable=False, index=True
    )
    relation_type: Mapped[PublicationRelationType] = mapped_column(
        SAEnum(PublicationRelationType), nullable=False
    )
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("publication_a_id", "publication_b_id", "relation_type", name="uq_pub_relation"),
    )


class ReviewItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    review_type: Mapped[str] = mapped_column(String(50), nullable=False)  # match, dedup, identifier
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action"),
        Index("ix_audit_created", "created_at"),
    )
