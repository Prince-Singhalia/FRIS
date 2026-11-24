"""Prefect Research Data Pipeline — discovery workflow.

This is the core research data automation. It discovers publications
for a faculty member from configured providers, scores identity matches,
deduplicates, and persists canonical records.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from prefect import flow, task, get_run_logger

from app.connectors.base import ConnectorResult
from app.connectors.openalex import OpenAlexConnector
from app.connectors.crossref import CrossrefConnector
from app.connectors.semantic_scholar import SemanticScholarConnector
from app.connectors.orcid import ORCIDConnector
from app.services.matching import evaluate_author_candidate
from app.services.normalization import normalize_doi, normalize_title
from app.services.deduplication import should_merge_by_doi, should_consider_no_doi_merge


# ── Prefect tasks ────────────────────────────────────────────────────────


@task(name="load_faculty_identity", retries=1)
async def load_faculty_identity(faculty_id: str, tenant_id: str) -> dict:
    """Load faculty identity, aliases, identifiers from DB."""
    from app.db.session import get_session_factory
    from app.db.models import Faculty, FacultyIdentifier, FacultyNameVariant, FacultyAffiliation
    from sqlalchemy import select

    logger = get_run_logger()
    factory = get_session_factory()

    async with factory() as session:
        result = await session.execute(
            select(Faculty).where(
                Faculty.id == faculty_id,
                Faculty.tenant_id == tenant_id,
            )
        )
        faculty = result.scalar_one_or_none()
        if not faculty:
            raise ValueError(f"Faculty {faculty_id} not found in tenant {tenant_id}")

        # Load identifiers
        ids_result = await session.execute(
            select(FacultyIdentifier).where(FacultyIdentifier.faculty_id == faculty.id)
        )
        identifiers = ids_result.scalars().all()

        # Load name variants
        vars_result = await session.execute(
            select(FacultyNameVariant).where(FacultyNameVariant.faculty_id == faculty.id)
        )
        variants = vars_result.scalars().all()

        # Load affiliations
        affs_result = await session.execute(
            select(FacultyAffiliation).where(FacultyAffiliation.faculty_id == faculty.id)
        )
        affiliations = affs_result.scalars().all()

    orcid = None
    verified_ids = []
    for ident in identifiers:
        if ident.identifier_type.value == "orcid":
            orcid = ident.value
        if ident.is_verified:
            verified_ids.append({
                "provider": ident.identifier_type.value,
                "value": ident.value,
            })

    profile = {
        "faculty_id": str(faculty.id),
        "tenant_id": str(faculty.tenant_id),
        "full_name": faculty.full_name,
        "reported_institution": faculty.reported_institution,
        "department": faculty.department,
        "orcid": orcid,
        "name_variants": [v.variant_name for v in variants],
        "affiliations": [
            {"organization": a.organization, "department": a.department, "is_current": a.is_current}
            for a in affiliations
        ],
        "verified_ids": verified_ids,
    }
    logger.info(f"Loaded faculty: {faculty.full_name} (ORCID: {orcid})")
    return profile


@task(name="search_provider_authors", retries=2, retry_delay_seconds=10)
async def search_provider_authors(
    provider_name: str,
    faculty_profile: dict,
) -> dict:
    """Search a single provider for author candidates."""
    logger = get_run_logger()
    logger.info(f"Searching {provider_name} for author candidates...")

    connector = _get_connector(provider_name)
    if connector is None:
        return {"provider": provider_name, "status": "not_configured", "candidates": [], "errors": [f"No connector for {provider_name}"]}

    result: ConnectorResult = await connector.search_author_candidates(
        faculty_name=faculty_profile["full_name"],
        orcid=faculty_profile.get("orcid"),
        institution=faculty_profile.get("reported_institution"),
        name_variants=faculty_profile.get("name_variants"),
    )

    logger.info(f"{provider_name}: status={result.status}, candidates={len(result.records)}")
    return {
        "provider": provider_name,
        "status": result.status,
        "candidates": result.records,
        "request_count": result.request_count,
        "warnings": result.warnings,
        "errors": result.errors,
    }


@task(name="score_candidates")
async def score_candidates(
    provider_results: list[dict],
    faculty_profile: dict,
) -> list[dict]:
    """Score all author candidates from all providers against the faculty profile."""
    logger = get_run_logger()
    scored = []

    for provider_result in provider_results:
        if provider_result["status"] not in ("succeeded",):
            continue

        for candidate in provider_result["candidates"]:
            score_result = evaluate_author_candidate(
                faculty_name=faculty_profile["full_name"],
                faculty_orcid=faculty_profile.get("orcid"),
                faculty_institution=faculty_profile.get("reported_institution"),
                candidate_name=candidate.get("display_name"),
                candidate_orcid=candidate.get("provider_orcid"),
                candidate_institution=candidate.get("provider_affiliation"),
                candidate_provider_id=candidate.get("provider_author_id"),
                verified_provider_ids=faculty_profile.get("verified_ids"),
            )

            scored.append({
                **candidate,
                "score": score_result["score"],
                "band": score_result["band"],
                "positive_evidence": score_result["positive_evidence"],
                "negative_evidence": score_result["negative_evidence"],
                "explanation": score_result["explanation"],
                "score_version": score_result["score_version"],
                "has_contradiction": score_result["has_contradiction"],
            })
            logger.info(
                f"  Candidate {candidate.get('display_name')} ({candidate.get('provider')}): "
                f"score={score_result['score']}, band={score_result['band']}"
            )

    return scored


@task(name="fetch_works_for_accepted", retries=2, retry_delay_seconds=15)
async def fetch_works_for_accepted(
    scored_candidates: list[dict],
    min_score_for_works: int = 50,
) -> list[dict]:
    """Fetch works only from candidates that meet the policy threshold."""
    logger = get_run_logger()
    all_works = []

    for candidate in scored_candidates:
        if candidate["score"] < min_score_for_works:
            logger.info(f"  Skipping works for {candidate.get('display_name')} (score {candidate['score']} < {min_score_for_works})")
            continue

        provider = candidate.get("provider")
        author_id = candidate.get("provider_author_id")
        if not provider or not author_id:
            continue

        connector = _get_connector(provider)
        if connector is None:
            continue

        logger.info(f"  Fetching works for {candidate.get('display_name')} from {provider}...")

        # Fetch first page of works
        result = await connector.fetch_author_works(author_id)
        if result.status == "succeeded":
            for work in result.records:
                work["_candidate_score"] = candidate["score"]
                work["_candidate_band"] = candidate["band"]
                work["_candidate_id"] = author_id
                all_works.append(work)
            logger.info(f"    Got {len(result.records)} works")

            # Fetch more pages if available (up to 3 pages for MVP)
            pages_fetched = 1
            while result.pagination and result.pagination.get("has_more") and pages_fetched < 3:
                cursor = result.pagination.get("next_cursor")
                if not cursor:
                    break
                result = await connector.fetch_author_works(author_id, cursor=cursor)
                if result.status == "succeeded":
                    for work in result.records:
                        work["_candidate_score"] = candidate["score"]
                        work["_candidate_band"] = candidate["band"]
                        work["_candidate_id"] = author_id
                        all_works.append(work)
                    pages_fetched += 1
                else:
                    break
        else:
            logger.warning(f"    Works fetch failed: {result.errors}")

    logger.info(f"Total raw works fetched: {len(all_works)}")
    return all_works


@task(name="deduplicate_works")
async def deduplicate_works(raw_works: list[dict]) -> dict:
    """Deduplicate works using DOI-first strategy.

    Returns dict with canonical_works, review_items, and source_mapping.
    """
    logger = get_run_logger()

    canonical: dict[str, dict] = {}  # normalized_doi or temp_id -> canonical work
    sources: dict[str, list[dict]] = {}  # canonical_key -> [source records]
    review_items: list[dict] = []

    for work in raw_works:
        doi = work.get("doi")
        norm_doi = normalize_doi(doi) if doi else None
        title = work.get("title", "")
        norm_title = normalize_title(title) if title else None
        year = work.get("publication_year")

        matched_key = None

        # Strategy 1: DOI match
        if norm_doi:
            for key, canonical_work in canonical.items():
                if canonical_work.get("normalized_doi") == norm_doi:
                    matched_key = key
                    break

        # Strategy 2: Title similarity (no DOI)
        if matched_key is None and norm_title:
            for key, canonical_work in canonical.items():
                canon_title = canonical_work.get("normalized_title")
                if not canon_title:
                    continue
                merge_decision = should_consider_no_doi_merge(
                    title, canonical_work.get("title", ""),
                    year, canonical_work.get("publication_year"),
                )
                if merge_decision == "merge":
                    matched_key = key
                    break
                elif merge_decision == "review":
                    review_items.append({
                        "type": "dedup_ambiguous",
                        "work_a_title": canonical_work.get("title"),
                        "work_b_title": title,
                        "work_a_provider": canonical_work.get("provider"),
                        "work_b_provider": work.get("provider"),
                        "similarity": "high_but_below_threshold",
                    })

        if matched_key:
            # Merge: add this as a source
            sources.setdefault(matched_key, []).append(work)
        else:
            # New canonical work
            key = norm_doi or f"noid-{uuid.uuid4().hex[:12]}"
            canonical[key] = {
                "title": title,
                "normalized_title": norm_title,
                "doi": doi,
                "normalized_doi": norm_doi,
                "publication_year": year,
                "publication_date": work.get("publication_date"),
                "venue": work.get("venue"),
                "venue_issn": work.get("venue_issn"),
                "publication_type": work.get("publication_type"),
                "abstract": work.get("abstract"),
                "landing_url": work.get("landing_url"),
                "is_open_access": work.get("is_open_access"),
                "citation_count": work.get("citation_count"),
                "authors": work.get("authors", []),
                "provider": work.get("provider"),
                "_candidate_score": work.get("_candidate_score"),
                "_candidate_band": work.get("_candidate_band"),
            }
            sources[key] = [work]

    logger.info(
        f"Dedup: {len(raw_works)} raw -> {len(canonical)} canonical, "
        f"{len(review_items)} review items"
    )
    return {
        "canonical_works": canonical,
        "sources": sources,
        "review_items": review_items,
    }


@task(name="persist_results")
async def persist_results(
    job_id: str,
    tenant_id: str,
    faculty_id: str,
    dedup_result: dict,
    scored_candidates: list[dict],
    provider_statuses: list[dict],
) -> dict:
    """Persist canonical publications, sources, matches, and job status."""
    from app.db.session import get_session_factory
    from app.db.models import (
        DiscoveryJob, ConnectorRun, ConnectorRunStatus,
        SourceRecord, AuthorCandidate, MatchDecision, MatchStatus,
        Publication, PublicationSource, Authorship,
        FacultyPublicationMatch, ReviewItem, JobStatus,
    )
    from sqlalchemy import select

    logger = get_run_logger()
    factory = get_session_factory()

    canonical_works = dedup_result["canonical_works"]
    sources_map = dedup_result["sources"]
    review_items_data = dedup_result["review_items"]

    pubs_created = 0
    pubs_existing = 0
    sources_created = 0
    matches_created = 0

    async with factory() as session:
        # Update job status to running
        job_result = await session.execute(
            select(DiscoveryJob).where(DiscoveryJob.id == job_id)
        )
        job = job_result.scalar_one_or_none()
        if job:
            job.status = JobStatus.running
            job.started_at = datetime.now(timezone.utc)

        # Save connector runs
        for ps in provider_statuses:
            cr = ConnectorRun(
                job_id=uuid.UUID(job_id),
                provider=ps["provider"],
                status=_map_connector_status(ps["status"]),
                records_fetched=len(ps.get("candidates", [])),
                records_valid=len(ps.get("candidates", [])),
                request_count=ps.get("request_count", 0),
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                error_message="; ".join(ps.get("errors", [])) or None,
                warnings=ps.get("warnings"),
            )
            session.add(cr)

        # Save author candidates and match decisions
        for candidate in scored_candidates:
            # Idempotent: check if candidate already exists
            existing = await session.execute(
                select(AuthorCandidate).where(
                    AuthorCandidate.faculty_id == faculty_id,
                    AuthorCandidate.provider == candidate["provider"],
                    AuthorCandidate.provider_author_id == candidate["provider_author_id"],
                )
            )
            ac = existing.scalar_one_or_none()
            if not ac:
                ac = AuthorCandidate(
                    tenant_id=uuid.UUID(tenant_id),
                    faculty_id=uuid.UUID(faculty_id),
                    provider=candidate["provider"],
                    provider_author_id=candidate["provider_author_id"],
                    display_name=candidate.get("display_name"),
                    provider_orcid=candidate.get("provider_orcid"),
                    provider_affiliation=candidate.get("provider_affiliation"),
                    works_count=candidate.get("works_count"),
                    source_url=candidate.get("source_url"),
                    discovery_job_id=uuid.UUID(job_id),
                )
                session.add(ac)
                await session.flush()

            # Save match decision
            band = candidate.get("band", "pending")
            status_map = {
                "verified": MatchStatus.verified,
                "probable": MatchStatus.probable,
                "review_required": MatchStatus.review_required,
                "rejected": MatchStatus.rejected,
            }
            match_status = status_map.get(band, MatchStatus.pending)

            md = MatchDecision(
                author_candidate_id=ac.id,
                faculty_id=uuid.UUID(faculty_id),
                score=candidate.get("score", 0),
                score_version=candidate.get("score_version", "1.0"),
                status=match_status,
                positive_evidence=candidate.get("positive_evidence"),
                negative_evidence=candidate.get("negative_evidence"),
                explanation=candidate.get("explanation"),
            )
            session.add(md)

        # Save canonical publications
        tid = uuid.UUID(tenant_id)
        fid = uuid.UUID(faculty_id)

        for key, canon in canonical_works.items():
            norm_doi = canon.get("normalized_doi")

            # Idempotent: check if publication with same DOI exists
            existing_pub = None
            if norm_doi:
                ep_result = await session.execute(
                    select(Publication).where(
                        Publication.tenant_id == tid,
                        Publication.normalized_doi == norm_doi,
                    )
                )
                existing_pub = ep_result.scalar_one_or_none()

            if existing_pub:
                pub = existing_pub
                pubs_existing += 1
            else:
                pub = Publication(
                    tenant_id=tid,
                    title=canon.get("title", "Untitled"),
                    normalized_title=canon.get("normalized_title"),
                    doi=canon.get("doi"),
                    normalized_doi=norm_doi,
                    publication_year=canon.get("publication_year"),
                    publication_date=canon.get("publication_date"),
                    venue=canon.get("venue"),
                    venue_issn=canon.get("venue_issn"),
                    publication_type=canon.get("publication_type"),
                    original_type=canon.get("publication_type"),
                    abstract=canon.get("abstract"),
                    landing_url=canon.get("landing_url"),
                    is_open_access=canon.get("is_open_access"),
                    citation_count=canon.get("citation_count"),
                )
                session.add(pub)
                await session.flush()
                pubs_created += 1

                # Add authorships
                for author in canon.get("authors", []):
                    session.add(Authorship(
                        publication_id=pub.id,
                        author_position=author.get("position"),
                        author_name=author.get("name", "Unknown"),
                        source_spelling=author.get("name"),
                        provider=canon.get("provider"),
                        orcid=author.get("orcid"),
                        provider_author_id=author.get("provider_author_id"),
                        raw_affiliation=author.get("affiliation"),
                    ))

            # Add source records for this publication
            for source_work in sources_map.get(key, []):
                provider = source_work.get("provider", "unknown")
                pwid = source_work.get("provider_work_id", "")

                # Idempotent source check
                existing_src = await session.execute(
                    select(PublicationSource).where(
                        PublicationSource.publication_id == pub.id,
                        PublicationSource.provider == provider,
                        PublicationSource.provider_work_id == pwid,
                    )
                )
                if not existing_src.scalar_one_or_none():
                    session.add(PublicationSource(
                        publication_id=pub.id,
                        provider=provider,
                        provider_work_id=pwid,
                        source_title=source_work.get("title"),
                        source_doi=source_work.get("doi"),
                        source_year=source_work.get("publication_year"),
                        source_venue=source_work.get("venue"),
                        source_type=source_work.get("publication_type"),
                        source_authors=source_work.get("authors"),
                        source_url=source_work.get("source_url"),
                        retrieved_at=datetime.now(timezone.utc),
                    ))
                    sources_created += 1

            # Faculty-publication match (idempotent)
            existing_match = await session.execute(
                select(FacultyPublicationMatch).where(
                    FacultyPublicationMatch.faculty_id == fid,
                    FacultyPublicationMatch.publication_id == pub.id,
                )
            )
            if not existing_match.scalar_one_or_none():
                candidate_band = canon.get("_candidate_band", "review_required")
                match_status = {
                    "verified": MatchStatus.verified,
                    "probable": MatchStatus.probable,
                    "review_required": MatchStatus.review_required,
                    "rejected": MatchStatus.rejected,
                }.get(candidate_band, MatchStatus.review_required)

                session.add(FacultyPublicationMatch(
                    faculty_id=fid,
                    publication_id=pub.id,
                    tenant_id=tid,
                    status=match_status,
                    confidence_score=canon.get("_candidate_score"),
                ))
                matches_created += 1

        # Save review items
        for ri_data in review_items_data:
            session.add(ReviewItem(
                tenant_id=tid,
                review_type="dedup_ambiguous",
                entity_type="publication",
                entity_id=uuid.uuid4(),  # placeholder
                status="pending",
                evidence=ri_data,
                explanation=f"Ambiguous duplicate: {ri_data.get('work_a_title', '')[:80]} vs {ri_data.get('work_b_title', '')[:80]}",
            ))

        # Finalize job
        if job:
            any_failed = any(ps["status"] == "failed" for ps in provider_statuses)
            any_succeeded = any(ps["status"] == "succeeded" for ps in provider_statuses)
            all_failed = all(ps["status"] in ("failed", "auth_failed", "not_configured") for ps in provider_statuses)

            if all_failed:
                job.status = JobStatus.failed
            elif any_failed and any_succeeded:
                job.status = JobStatus.partial
            else:
                job.status = JobStatus.succeeded

            job.completed_at = datetime.now(timezone.utc)
            job.summary = (
                f"Publications: {pubs_created} new, {pubs_existing} existing. "
                f"Sources: {sources_created}. Matches: {matches_created}. "
                f"Reviews: {len(review_items_data)}."
            )

        await session.commit()

    logger.info(
        f"Persisted: {pubs_created} new pubs, {pubs_existing} existing, "
        f"{sources_created} sources, {matches_created} matches"
    )
    return {
        "pubs_created": pubs_created,
        "pubs_existing": pubs_existing,
        "sources_created": sources_created,
        "matches_created": matches_created,
        "review_items": len(review_items_data),
    }


# ── Main Prefect flow ───────────────────────────────────────────────────


@flow(name="fris-discovery", log_prints=True)
async def discovery_flow(
    job_id: str,
    faculty_id: str,
    tenant_id: str,
    selected_sources: list[str] | None = None,
) -> dict:
    """Execute the full research data discovery pipeline for one faculty member.

    Flow stages (per spec Section 6):
    1. Load faculty identity
    2. Search providers for author candidates
    3. Score candidates
    4. Fetch works from accepted candidates
    5. Deduplicate
    6. Persist results
    """
    logger = get_run_logger()
    logger.info(f"Starting discovery for faculty {faculty_id}, job {job_id}")

    if selected_sources is None:
        selected_sources = ["openalex", "crossref", "semantic_scholar"]

    # 1. Load faculty identity
    faculty_profile = await load_faculty_identity(faculty_id, tenant_id)

    # 2. Search providers in parallel
    provider_futures = []
    for provider in selected_sources:
        provider_futures.append(
            search_provider_authors.submit(provider, faculty_profile)
        )

    provider_results = [await f.result() for f in provider_futures]

    # 3. Score candidates
    scored_candidates = await score_candidates(provider_results, faculty_profile)

    # 4. Fetch works from accepted candidates
    all_works = await fetch_works_for_accepted(scored_candidates)

    # 5. Deduplicate
    dedup_result = await deduplicate_works(all_works)

    # 6. Persist
    persist_summary = await persist_results(
        job_id=job_id,
        tenant_id=tenant_id,
        faculty_id=faculty_id,
        dedup_result=dedup_result,
        scored_candidates=scored_candidates,
        provider_statuses=provider_results,
    )

    summary = {
        "job_id": job_id,
        "faculty_id": faculty_id,
        "providers_queried": len(provider_results),
        "candidates_found": len(scored_candidates),
        "works_fetched": len(all_works),
        "canonical_publications": len(dedup_result["canonical_works"]),
        **persist_summary,
    }

    logger.info(f"Discovery complete: {summary}")
    return summary


# ── Helpers ──────────────────────────────────────────────────────────────

def _get_connector(provider_name: str):
    """Get connector instance by provider name."""
    connectors = {
        "openalex": OpenAlexConnector,
        "crossref": CrossrefConnector,
        "semantic_scholar": SemanticScholarConnector,
        "orcid": ORCIDConnector,
    }
    cls = connectors.get(provider_name)
    return cls() if cls else None


def _map_connector_status(status_str: str):
    """Map string status to ConnectorRunStatus enum."""
    from app.db.models import ConnectorRunStatus
    mapping = {
        "succeeded": ConnectorRunStatus.succeeded,
        "failed": ConnectorRunStatus.failed,
        "rate_limited": ConnectorRunStatus.rate_limited,
        "auth_failed": ConnectorRunStatus.auth_failed,
        "skipped": ConnectorRunStatus.skipped,
        "not_configured": ConnectorRunStatus.skipped,
    }
    return mapping.get(status_str, ConnectorRunStatus.failed)
