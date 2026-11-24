"""Crossref connector — DOI metadata registry and supplementary discovery.

Official docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
Date checked: 2026-11-19

Endpoints used:
  - GET https://api.crossref.org/works?query.author={name} — author work search
  - GET https://api.crossref.org/works/{doi} — DOI lookup
Pagination: offset-based (offset + rows)
Rate limits: 50 req/sec polite pool (with mailto), lower without
Auth: No key required; mailto recommended for polite pool
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from app.connectors.base import BaseConnector, ConnectorResult
from app.core.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org"
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
MAX_ROWS = 50


class CrossrefConnector(BaseConnector):

    @property
    def provider_name(self) -> str:
        return "crossref"

    @property
    def display_name(self) -> str:
        return "Crossref"

    @property
    def terms_url(self) -> str:
        return "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"

    @property
    def requires_auth(self) -> bool:
        return False

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "author_search": True,
            "works_fetch": False,
            "doi_lookup": True,
            "record_lookup": False,
        }

    def _get_headers(self) -> dict:
        """Headers including polite pool mailto."""
        settings = get_settings()
        headers = {"User-Agent": f"FRIS/0.1 (mailto:{settings.crossref_mailto})" if settings.crossref_mailto else "FRIS/0.1"}
        return headers

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(
                    f"{CROSSREF_API_BASE}/works",
                    params={"query": "test", "rows": "1"},
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return {"status": "healthy", "response_time_ms": resp.elapsed.total_seconds() * 1000}
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
        """Search Crossref for works by author name.

        Note: Crossref is a DOI registry, not an author identity service.
        query.author searches are supplementary, not authoritative for identity.
        """
        records = []
        warnings = []
        request_count = 0

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                # Crossref works search with author filter
                params = {
                    "query.author": faculty_name,
                    "rows": str(MAX_ROWS),
                    "sort": "relevance",
                    "order": "desc",
                }

                # ORCID filter if available
                if orcid:
                    params["filter"] = f"orcid:{orcid}"

                request_count += 1
                resp = await client.get(
                    f"{CROSSREF_API_BASE}/works",
                    params=params,
                    headers=self._get_headers(),
                )

                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("message", {}).get("items", [])
                    for work in items:
                        records.append(self._normalize_work(work))

                    total = data.get("message", {}).get("total-results", 0)
                    if total > MAX_ROWS:
                        warnings.append(f"Crossref returned {total} total results; only first {MAX_ROWS} fetched")
                elif resp.status_code == 429:
                    return ConnectorResult(
                        status="rate_limited",
                        request_count=request_count,
                        rate_limit_info={"retry_after": resp.headers.get("Retry-After")},
                        errors=["Rate limited by Crossref"],
                    )
                else:
                    return ConnectorResult(
                        status="failed",
                        request_count=request_count,
                        errors=[f"Crossref search returned {resp.status_code}"],
                    )

            return ConnectorResult(
                status="succeeded",
                records=records,
                request_count=request_count,
                warnings=warnings,
                retrieved_at=datetime.now(timezone.utc),
            )
        except httpx.TimeoutException as e:
            return ConnectorResult(status="failed", request_count=request_count, errors=[f"Timeout: {e}"])
        except Exception as e:
            return ConnectorResult(status="failed", request_count=request_count, errors=[f"Error: {e}"])

    async def lookup_work_by_doi(self, doi: str) -> ConnectorResult:
        """Look up work metadata by DOI."""
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(
                    f"{CROSSREF_API_BASE}/works/{doi}",
                    headers=self._get_headers(),
                )

                if resp.status_code == 200:
                    data = resp.json()
                    work = data.get("message", {})
                    return ConnectorResult(
                        status="succeeded",
                        records=[self._normalize_work(work)],
                        request_count=1,
                        retrieved_at=datetime.now(timezone.utc),
                    )
                elif resp.status_code == 404:
                    return ConnectorResult(status="succeeded", records=[], request_count=1)
                else:
                    return ConnectorResult(
                        status="failed",
                        request_count=1,
                        errors=[f"DOI lookup returned {resp.status_code}"],
                    )
        except Exception as e:
            return ConnectorResult(status="failed", request_count=1, errors=[str(e)])

    def _normalize_work(self, raw: dict) -> dict:
        """Normalize Crossref work to FRIS schema."""
        # DOI
        doi = raw.get("DOI")

        # Title
        titles = raw.get("title", [])
        title = titles[0] if titles else None

        # Year/date
        date_parts = raw.get("published-print", raw.get("published-online", raw.get("created", {})))
        pub_year = None
        pub_date = None
        if date_parts:
            parts = date_parts.get("date-parts", [[]])
            if parts and parts[0]:
                pub_year = parts[0][0] if len(parts[0]) >= 1 else None
                if len(parts[0]) >= 3:
                    pub_date = f"{parts[0][0]}-{parts[0][1]:02d}-{parts[0][2]:02d}"
                elif len(parts[0]) >= 2:
                    pub_date = f"{parts[0][0]}-{parts[0][1]:02d}"

        # Authors
        authors = []
        for i, author in enumerate(raw.get("author", [])):
            name_parts = []
            if author.get("given"):
                name_parts.append(author["given"])
            if author.get("family"):
                name_parts.append(author["family"])
            full_name = " ".join(name_parts) if name_parts else "Unknown"

            orcid_raw = author.get("ORCID", "")
            orcid = orcid_raw.replace("http://orcid.org/", "").replace("https://orcid.org/", "").strip() or None

            authors.append({
                "position": i,
                "name": full_name,
                "orcid": orcid,
                "affiliation": "; ".join(
                    aff.get("name", "") for aff in author.get("affiliation", [])
                ) or None,
            })

        # Venue
        containers = raw.get("container-title", [])
        venue = containers[0] if containers else None
        issn_list = raw.get("ISSN", [])
        issn = issn_list[0] if issn_list else None

        # Type
        pub_type = raw.get("type")

        payload_str = str(raw).encode("utf-8")
        payload_hash = hashlib.sha256(payload_str).hexdigest()[:16]

        return {
            "provider": "crossref",
            "provider_work_id": f"crossref:{doi}" if doi else f"crossref:{raw.get('URL', '')}",
            "title": title,
            "doi": doi,
            "publication_year": pub_year,
            "publication_date": pub_date,
            "venue": venue,
            "venue_issn": issn,
            "publication_type": pub_type,
            "abstract": raw.get("abstract"),  # May contain HTML
            "landing_url": raw.get("URL"),
            "is_open_access": None,  # Crossref doesn't directly provide this in basic metadata
            "citation_count": raw.get("is-referenced-by-count"),
            "authors": authors,
            "source_url": raw.get("URL"),
            "payload_hash": payload_hash,
            "raw_data": raw,
        }
