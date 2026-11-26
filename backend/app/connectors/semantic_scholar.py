"""Semantic Scholar connector — secondary author/work discovery.

Official docs: https://api.semanticscholar.org/api-docs/
Date checked: 2026-11-19

Endpoints used:
  - GET https://api.semanticscholar.org/graph/v1/author/search — author search
  - GET https://api.semanticscholar.org/graph/v1/author/{id}/papers — author papers
Pagination: offset-based
Rate limits: 1 req/sec without key, 10 req/sec with key
Auth: Optional API key via x-api-key header
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx

from app.connectors.base import BaseConnector, ConnectorResult
from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
MAX_LIMIT = 100


class SemanticScholarConnector(BaseConnector):
    @property
    def provider_name(self) -> str:
        return "semantic_scholar"

    @property
    def display_name(self) -> str:
        return "Semantic Scholar"

    @property
    def terms_url(self) -> str:
        return "https://api.semanticscholar.org/api-docs/"

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "author_search": True,
            "works_fetch": True,
            "doi_lookup": False,
        }

    def _get_headers(self) -> dict:
        settings = get_settings()
        headers = {}
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        return headers

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(
                    f"{S2_API_BASE}/author/search",
                    params={"query": "test", "limit": "1"},
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return {"status": "healthy"}
                return {"status": "unhealthy", "status_code": resp.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def search_author_candidates(
        self,
        faculty_name: str,
        orcid: str | None = None,
        institution: str | None = None,
        name_variants: list[str] | None = None,
    ) -> ConnectorResult:
        records = []
        request_count = 0
        warnings = []

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                fields = "authorId,externalIds,name,affiliations,paperCount,citationCount,url"
                params = {
                    "query": faculty_name,
                    "limit": "10",
                    "fields": fields,
                }
                request_count += 1
                resp = await client.get(
                    f"{S2_API_BASE}/author/search",
                    params=params,
                    headers=self._get_headers(),
                )

                if resp.status_code == 200:
                    data = resp.json()
                    for author in data.get("data", []):
                        records.append(self._normalize_author(author))
                elif resp.status_code == 429:
                    return ConnectorResult(
                        status="rate_limited",
                        request_count=request_count,
                        rate_limit_info={"retry_after": resp.headers.get("Retry-After")},
                        errors=["Rate limited by Semantic Scholar"],
                    )
                else:
                    return ConnectorResult(
                        status="failed",
                        request_count=request_count,
                        errors=[f"Author search returned {resp.status_code}"],
                    )

            return ConnectorResult(
                status="succeeded",
                records=records,
                request_count=request_count,
                warnings=warnings,
                retrieved_at=datetime.now(UTC),
            )
        except httpx.TimeoutException as e:
            return ConnectorResult(
                status="failed", request_count=request_count, errors=[f"Timeout: {e}"]
            )
        except Exception as e:
            return ConnectorResult(
                status="failed", request_count=request_count, errors=[f"Error: {e}"]
            )

    async def fetch_author_works(
        self,
        provider_author_id: str,
        cursor: str | None = None,
        per_page: int = MAX_LIMIT,
    ) -> ConnectorResult:
        records = []
        request_count = 0

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                fields = (
                    "paperId,externalIds,title,year,venue,publicationDate,"
                    "citationCount,isOpenAccess,openAccessPdf,authors,abstract,url"
                )
                offset = int(cursor) if cursor else 0
                params = {
                    "fields": fields,
                    "limit": str(min(per_page, MAX_LIMIT)),
                    "offset": str(offset),
                }
                request_count += 1
                resp = await client.get(
                    f"{S2_API_BASE}/author/{provider_author_id}/papers",
                    params=params,
                    headers=self._get_headers(),
                )

                if resp.status_code == 200:
                    data = resp.json()
                    for paper in data.get("data", []):
                        records.append(self._normalize_work(paper))

                    next_offset = offset + len(records)
                    total = data.get("total", len(records))
                    pagination = None
                    if next_offset < total:
                        pagination = {"next_cursor": str(next_offset), "has_more": True}

                    return ConnectorResult(
                        status="succeeded",
                        records=records,
                        pagination=pagination,
                        request_count=request_count,
                        retrieved_at=datetime.now(UTC),
                    )
                elif resp.status_code == 429:
                    return ConnectorResult(
                        status="rate_limited",
                        request_count=request_count,
                        errors=["Rate limited"],
                    )
                else:
                    return ConnectorResult(
                        status="failed",
                        request_count=request_count,
                        errors=[f"Papers fetch returned {resp.status_code}"],
                    )
        except Exception as e:
            return ConnectorResult(
                status="failed", request_count=request_count, errors=[f"Error: {e}"]
            )

    def _normalize_author(self, raw: dict) -> dict:
        external_ids = raw.get("externalIds") or {}
        orcid = external_ids.get("ORCID")
        affiliations = raw.get("affiliations", []) or []
        aff_text = (
            "; ".join(a.get("name", "") if isinstance(a, dict) else str(a) for a in affiliations)
            if affiliations
            else None
        )

        return {
            "provider": "semantic_scholar",
            "provider_author_id": raw.get("authorId", ""),
            "display_name": raw.get("name"),
            "provider_orcid": orcid,
            "provider_affiliation": aff_text,
            "works_count": raw.get("paperCount"),
            "source_url": raw.get("url"),
            "raw_data": raw,
        }

    def _normalize_work(self, raw: dict) -> dict:
        external_ids = raw.get("externalIds") or {}
        doi = external_ids.get("DOI")

        authors = []
        for i, author in enumerate(raw.get("authors", [])):
            authors.append(
                {
                    "position": i,
                    "name": author.get("name", ""),
                    "provider_author_id": author.get("authorId", ""),
                }
            )

        payload_hash = hashlib.sha256(str(raw).encode()).hexdigest()[:16]

        return {
            "provider": "semantic_scholar",
            "provider_work_id": f"s2:{raw.get('paperId', '')}",
            "title": raw.get("title"),
            "doi": doi,
            "publication_year": raw.get("year"),
            "publication_date": raw.get("publicationDate"),
            "venue": raw.get("venue"),
            "publication_type": raw.get("publicationTypes", [None])[0]
            if raw.get("publicationTypes")
            else None,
            "abstract": raw.get("abstract"),
            "landing_url": raw.get("url"),
            "is_open_access": raw.get("isOpenAccess"),
            "citation_count": raw.get("citationCount"),
            "authors": authors,
            "source_url": raw.get("url"),
            "payload_hash": payload_hash,
            "raw_data": raw,
        }
