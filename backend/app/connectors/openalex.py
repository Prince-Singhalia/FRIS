"""OpenAlex connector — primary broad author/work discovery source.

Official docs: https://docs.openalex.org/
Date checked: 2026-11-19

Endpoints used:
  - GET https://api.openalex.org/authors — search/filter authors
  - GET https://api.openalex.org/authors/{id} — author details
  - GET https://api.openalex.org/works — filter works by author
Pagination: cursor-based (?cursor=*)
Rate limits: 10 req/sec unauthenticated, 100 req/sec with API key (polite pool via mailto)
Auth: No key required; email recommended for polite pool
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx

from app.connectors.base import BaseConnector, ConnectorResult
from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

OPENALEX_API_BASE = "https://api.openalex.org"
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
MAX_PER_PAGE = 50
MAX_BASIC_RESULTS = 10_000


class OpenAlexConnector(BaseConnector):
    @property
    def provider_name(self) -> str:
        return "openalex"

    @property
    def display_name(self) -> str:
        return "OpenAlex"

    @property
    def terms_url(self) -> str:
        return "https://docs.openalex.org/"

    @property
    def requires_auth(self) -> bool:
        return False

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "author_search": True,
            "works_fetch": True,
            "doi_lookup": True,
            "record_lookup": True,
        }

    def _get_params(self) -> dict:
        """Common query params (polite pool email)."""
        settings = get_settings()
        params = {}
        if settings.openalex_email:
            params["mailto"] = settings.openalex_email
        return params

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                params = self._get_params()
                resp = await client.get(
                    f"{OPENALEX_API_BASE}/authors",
                    params={**params, "search": "test", "per_page": "1"},
                )
                if resp.status_code == 200:
                    return {
                        "status": "healthy",
                        "response_time_ms": resp.elapsed.total_seconds() * 1000,
                    }
                return {"status": "unhealthy", "status_code": resp.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def search_author_candidates(
        self,
        faculty_name: str,
        orcid: str | None = None,
        institution: str | None = None,
        name_variants: list[str] | None = None,
        cursor: str | None = None,
    ) -> ConnectorResult:
        """Search OpenAlex for author candidates.

        Strategy:
        1. If ORCID is provided, filter by ORCID first (most reliable).
        2. Otherwise, search by name with optional institution filter.
        """
        records = []
        warnings = []
        errors: list[str] = []
        request_count = 0
        rate_limited = False
        next_cursor = None

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                base_params = self._get_params()

                # Strategy 1: ORCID-based lookup
                if orcid:
                    params = {**base_params, "filter": f"orcid:{orcid}"}
                    request_count += 1
                    resp = await client.get(f"{OPENALEX_API_BASE}/authors", params=params)

                    if resp.status_code == 200:
                        data = resp.json()
                        for author in data.get("results", []):
                            normalized = self._normalize_author(author)
                            provider_orcid = normalized.get("provider_orcid")
                            if provider_orcid and provider_orcid.upper() == orcid.upper():
                                records.append(normalized)
                    elif resp.status_code == 429:
                        return ConnectorResult(
                            status="rate_limited",
                            request_count=request_count,
                            rate_limit_info={"retry_after": resp.headers.get("Retry-After")},
                            errors=["Rate limited by OpenAlex"],
                        )
                    else:
                        error = f"ORCID search returned {resp.status_code}"
                        warnings.append(error)
                        errors.append(error)

                # Strategy 2: Name search
                # ORCID is an exact identity lookup. Never broaden a failed or
                # empty identifier lookup into a name search for an unrelated person.
                if not orcid and not records:
                    names_to_search = [faculty_name]
                    if name_variants:
                        names_to_search.extend(name_variants[:3])  # Limit variant searches

                    for name in names_to_search:
                        # OpenAlex returns only 10 authors by default. Use its
                        # maximum page size so common names expose a useful
                        # candidate set instead of silently stopping at ten.
                        params = {
                            **base_params,
                            "search": name,
                            "per_page": "200",
                            "cursor": cursor or "*",
                        }
                        if institution:
                            params["filter"] = (
                                f"last_known_institutions.display_name.search:{institution}"
                            )

                        request_count += 1
                        resp = await client.get(f"{OPENALEX_API_BASE}/authors", params=params)

                        if resp.status_code == 200:
                            data = resp.json()
                            next_cursor = data.get("meta", {}).get("next_cursor")
                            for author in data.get("results", []):
                                # Avoid duplicate candidates
                                author_id = author.get("id", "")
                                if not any(
                                    r.get("provider_author_id") == author_id for r in records
                                ):
                                    records.append(self._normalize_author(author))
                        elif resp.status_code == 429:
                            warnings.append(f"Rate limited during name search for '{name}'")
                            rate_limited = True
                            break
                        else:
                            error = f"Name search for '{name}' returned {resp.status_code}"
                            warnings.append(error)
                            errors.append(error)

            status = (
                "failed"
                if errors and not records
                else "rate_limited"
                if rate_limited and not records
                else "succeeded"
            )
            return ConnectorResult(
                status=status,
                records=records,
                pagination=(
                    {"next_cursor": next_cursor, "has_more": True} if next_cursor else None
                ),
                request_count=request_count,
                warnings=warnings,
                errors=errors,
                retrieved_at=datetime.now(UTC),
            )

        except httpx.TimeoutException as e:
            return ConnectorResult(
                status="failed",
                request_count=request_count,
                errors=[f"Timeout: {e}"],
            )
        except Exception as e:
            return ConnectorResult(
                status="failed",
                request_count=request_count,
                errors=[f"Error: {e}"],
            )

    async def fetch_author_works(
        self,
        provider_author_id: str,
        cursor: str | None = None,
        per_page: int = MAX_PER_PAGE,
        page: int = 1,
    ) -> ConnectorResult:
        """Fetch author works using numbered paging for the public demo.

        Cursor remains available for existing workflow callers. Numbered paging
        does not require an OpenAlex API key, but is limited to 10,000 results.
        """
        records = []
        errors = []
        request_count = 0
        next_cursor = None
        count = 0

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                base_params = self._get_params()
                # Extract short ID from full URL if needed
                short_id = provider_author_id.replace("https://openalex.org/", "")

                params = {
                    **base_params,
                    "filter": f"authorships.author.id:{short_id}",
                    "per_page": str(min(per_page, MAX_PER_PAGE)),
                    "sort": "publication_date:desc",
                }
                if cursor:
                    params["cursor"] = cursor
                else:
                    safe_page_size = min(max(per_page, 1), MAX_PER_PAGE)
                    safe_page = min(max(page, 1), MAX_BASIC_RESULTS // safe_page_size)
                    params["per_page"] = str(safe_page_size)
                    params["page"] = str(safe_page)

                request_count += 1
                resp = await client.get(f"{OPENALEX_API_BASE}/works", params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    meta = data.get("meta", {})
                    next_cursor = meta.get("next_cursor") if cursor else None
                    count = meta.get("count")

                    for work in data.get("results", []):
                        records.append(self._normalize_work(work))

                elif resp.status_code == 429:
                    return ConnectorResult(
                        status="rate_limited",
                        request_count=request_count,
                        rate_limit_info={"retry_after": resp.headers.get("Retry-After")},
                        errors=["Rate limited by OpenAlex"],
                    )
                else:
                    errors.append(f"Works fetch returned {resp.status_code}: {resp.text[:200]}")

            pagination = None
            if next_cursor:
                pagination = {"next_cursor": next_cursor, "has_more": True}
            elif (
                not cursor
                and count
                and page * min(per_page, MAX_PER_PAGE) < min(count, MAX_BASIC_RESULTS)
            ):
                pagination = {
                    "page": page,
                    "next_page": page + 1,
                    "has_more": True,
                    "limit_reached": False,
                }
            elif not cursor and count and count > MAX_BASIC_RESULTS:
                pagination = {"page": page, "has_more": False, "limit_reached": True}
            else:
                pagination = (
                    {"page": page, "has_more": False, "limit_reached": False}
                    if not cursor
                    else None
                )

            return ConnectorResult(
                status="succeeded" if not errors else "failed",
                records=records,
                pagination=pagination,
                request_count=request_count,
                errors=errors,
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

    async def lookup_work_by_doi(self, doi: str) -> ConnectorResult:
        """Look up a work by DOI."""
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                params = self._get_params()
                resp = await client.get(
                    f"{OPENALEX_API_BASE}/works/https://doi.org/{doi}", params=params
                )

                if resp.status_code == 200:
                    work = resp.json()
                    return ConnectorResult(
                        status="succeeded",
                        records=[self._normalize_work(work)],
                        request_count=1,
                        retrieved_at=datetime.now(UTC),
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

    def _normalize_author(self, raw: dict) -> dict:
        """Normalize OpenAlex author entity to FRIS schema."""
        author_id = raw.get("id", "").removeprefix("https://openalex.org/")
        orcid_raw = raw.get("orcid") or ""
        orcid = orcid_raw.replace("https://orcid.org/", "").strip() or None

        affiliations = []
        for inst in raw.get("last_known_institutions", []) or []:
            affiliations.append(inst.get("display_name", ""))

        return {
            "provider": "openalex",
            "provider_author_id": raw.get("id", ""),
            "display_name": raw.get("display_name"),
            "provider_orcid": orcid,
            "provider_affiliation": "; ".join(affiliations) if affiliations else None,
            "works_count": raw.get("works_count"),
            "cited_by_count": raw.get("cited_by_count"),
            "source_url": f"https://openalex.org/authors/{author_id}",
            "raw_data": raw,
        }

    def _normalize_work(self, raw: dict) -> dict:
        """Normalize OpenAlex work to FRIS schema."""
        # DOI
        doi_raw = raw.get("doi") or ""
        doi = doi_raw.replace("https://doi.org/", "").strip() or None

        # Authors
        authors = []
        for i, authorship in enumerate(raw.get("authorships", [])):
            author = authorship.get("author", {})
            orcid_raw = author.get("orcid") or ""
            authors.append(
                {
                    "position": i,
                    "name": author.get("display_name", ""),
                    "orcid": orcid_raw.replace("https://orcid.org/", "").strip() or None,
                    "provider_author_id": author.get("id", ""),
                    "affiliation": "; ".join(
                        inst.get("display_name", "") for inst in authorship.get("institutions", [])
                    ),
                }
            )

        # Venue/source
        primary_location = raw.get("primary_location") or {}
        source = primary_location.get("source") or {}

        payload_str = str(raw).encode("utf-8")
        payload_hash = hashlib.sha256(payload_str).hexdigest()[:16]

        return {
            "provider": "openalex",
            "provider_work_id": raw.get("id", ""),
            "title": raw.get("title") or raw.get("display_name", ""),
            "doi": doi,
            "publication_year": raw.get("publication_year"),
            "publication_date": raw.get("publication_date"),
            "venue": source.get("display_name"),
            "venue_issn": source.get("issn_l"),
            "publication_type": raw.get("type"),
            "abstract": raw.get("abstract"),
            "landing_url": primary_location.get("landing_page_url"),
            "is_open_access": raw.get("open_access", {}).get("is_oa"),
            "license": raw.get("open_access", {}).get("oa_url"),
            "citation_count": raw.get("cited_by_count"),
            "authors": authors,
            "source_url": raw.get("id", ""),
            "payload_hash": payload_hash,
            "raw_data": raw,
        }
