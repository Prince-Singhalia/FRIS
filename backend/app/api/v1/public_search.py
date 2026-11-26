"""Unauthenticated, read-only endpoints for the faculty demonstration UI."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.connectors.openalex import OpenAlexConnector
from app.domain.schemas import validate_orcid

router = APIRouter()


def _author_view(record: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "id": record.get("provider_author_id"),
        "name": record.get("display_name"),
        "orcid": record.get("provider_orcid"),
        "affiliation": record.get("provider_affiliation"),
        "works_count": record.get("works_count"),
        "cited_by_count": record.get("cited_by_count"),
        "source_url": record.get("source_url"),
        "identity_status": status,
    }


@router.get("/search/authors")
async def search_authors(name: str = Query(min_length=2, max_length=160)):
    result = await OpenAlexConnector().search_author_candidates(name.strip())
    if result.status != "succeeded":
        raise HTTPException(
            502,
            detail={"message": "OpenAlex author search failed", "status": result.status},
        )
    return {
        "results": [_author_view(row, "possible_name_match") for row in result.records],
        "count": len(result.records),
        "source": "OpenAlex",
        "retrieved_at": result.retrieved_at or datetime.now(UTC),
        "warnings": result.warnings,
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
