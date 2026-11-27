"""Unauthenticated, read-only endpoints for the faculty demonstration UI."""

from __future__ import annotations

import re
from asyncio import gather
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.connectors.crossref import CrossrefConnector
from app.connectors.openalex import OpenAlexConnector
from app.connectors.semantic_scholar import SemanticScholarConnector
from app.domain.schemas import validate_orcid

router = APIRouter()

INSTITUTION_DIRECTORY = {
    "priyanka goel": {
        "provider": "institution",
        "provider_author_id": "institution:upes:priyanka-goel",
        "display_name": "Priyanka Goel",
        "provider_affiliation": "University of Petroleum and Energy Studies (UPES)",
        "source_url": "https://www.upes.ac.in/faculty/school-of-computer-science/priyanka-goel",
        "linkedin_url": "https://in.linkedin.com/in/priyanka-goel-124a7722",
        "works_count": None,
        "cited_by_count": None,
        "provider_orcid": None,
    },
}


def _author_view(record: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "id": record.get("provider_author_id"),
        "provider": record.get("provider", "openalex"),
        "name": record.get("display_name"),
        "orcid": record.get("provider_orcid"),
        "affiliation": record.get("provider_affiliation"),
        "works_count": record.get("works_count"),
        "cited_by_count": record.get("cited_by_count"),
        "source_url": record.get("source_url"),
        "linkedin_url": record.get("linkedin_url"),
        "identity_status": status,
    }


@router.get("/search/authors")
async def search_authors(
    name: str = Query(min_length=2, max_length=160),
    cursor: str | None = Query(default=None, max_length=500),
):
    normalized_name = name.strip()
    if cursor:
        available = [("OpenAlex", await OpenAlexConnector().search_author_candidates(normalized_name, cursor=cursor))]
    else:
        openalex_result, semantic_result = await gather(
            OpenAlexConnector().search_author_candidates(normalized_name),
            SemanticScholarConnector().search_author_candidates(normalized_name),
        )
        available = [("OpenAlex", openalex_result), ("Semantic Scholar", semantic_result)]
    results = []
    warnings = []
    sources = []
    for source, result in available:
        if result.status == "succeeded":
            sources.append(source)
            results.extend(_author_view(row, "possible_name_match") for row in result.records)
        else:
            warnings.extend(result.errors or [f"{source} search {result.status}"])
        warnings.extend(result.warnings)

    directory_record = INSTITUTION_DIRECTORY.get(normalized_name.casefold())
    if directory_record and not any(
        row.get("display_name", "").casefold() == normalized_name.casefold() for row in results
    ):
        results.insert(0, _author_view(directory_record, "institution_profile_match"))
        sources.append("UPES faculty directory")

    if not results:
        raise HTTPException(
            502,
            detail={"message": "All author search providers failed", "warnings": warnings},
        )
    return {
        "results": results,
        "count": len(results),
        "source": ", ".join(sources),
        "sources": sources,
        "pagination": openalex_result.pagination if cursor is None else available[0][1].pagination,
        "retrieved_at": datetime.now(UTC),
        "warnings": warnings,
    }


@router.get("/search/orcid/{orcid_id}")
async def search_orcid(orcid_id: str):
    try:
        normalized = validate_orcid(orcid_id)
    except ValueError as exc:
        raise HTTPException(422, detail="Invalid ORCID format or checksum") from exc
    result = await OpenAlexConnector().search_author_candidates("", orcid=normalized)
    if result.status != "succeeded":
        raise HTTPException(
            502,
            detail={"message": "OpenAlex ORCID lookup failed", "status": result.status},
        )
    return {
        "orcid": normalized,
        "results": [_author_view(row, "provider_identifier_matched") for row in result.records],
        "count": len(result.records),
        "source": "OpenAlex",
        "retrieved_at": result.retrieved_at or datetime.now(UTC),
        "warnings": result.warnings,
    }


@router.get("/authors/{author_id:path}/works")
async def author_works(
    author_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=50),
):
    if not re.fullmatch(r"(?:https://openalex\.org/)?A\d+", author_id):
        raise HTTPException(422, detail="Invalid OpenAlex author identifier")
    result = await OpenAlexConnector().fetch_author_works(author_id, per_page=per_page, page=page)
    if result.status != "succeeded":
        raise HTTPException(
            502,
            detail={"message": "OpenAlex works retrieval failed", "status": result.status},
        )
    return {
        "results": result.records,
        "count": len(result.records),
        "pagination": result.pagination,
        "page": page,
        "source": "OpenAlex",
        "retrieved_at": result.retrieved_at or datetime.now(UTC),
    }


@router.get("/search/semantic-scholar/authors/{author_id}/works")
async def semantic_scholar_author_works(
    author_id: str,
    cursor: str | None = None,
    per_page: int = Query(default=25, ge=1, le=100),
):
    if not re.fullmatch(r"\d+", author_id):
        raise HTTPException(422, detail="Invalid Semantic Scholar author identifier")
    result = await SemanticScholarConnector().fetch_author_works(
        author_id, cursor=cursor, per_page=per_page
    )
    if result.status != "succeeded":
        raise HTTPException(
            502,
            detail={"message": "Semantic Scholar works retrieval failed", "status": result.status},
        )
    return {
        "results": result.records,
        "count": len(result.records),
        "pagination": result.pagination,
        "source": "Semantic Scholar",
        "retrieved_at": result.retrieved_at or datetime.now(UTC),
    }


@router.get("/search/crossref/works")
async def crossref_author_works(name: str = Query(min_length=2, max_length=160)):
    result = await CrossrefConnector().search_author_candidates(name.strip())
    if result.status != "succeeded":
        raise HTTPException(
            502,
            detail={"message": "Crossref publication search failed", "status": result.status},
        )
    return {
        "results": result.records,
        "count": len(result.records),
        "source": "Crossref",
        "warnings": result.warnings,
        "retrieved_at": result.retrieved_at or datetime.now(UTC),
    }
