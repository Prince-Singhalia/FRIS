"""ORCID Public API connector — read ORCID records and public works.

Official docs: https://info.orcid.org/documentation/api-tutorials/
Date checked: 2026-11-19

Endpoints used:
  - GET https://pub.orcid.org/v3.0/{orcid}/record — read ORCID record
  - GET https://pub.orcid.org/v3.0/{orcid}/works — read works
Auth: Requires registered client credentials (client_id/client_secret) and
      a read-public access token obtained via client credentials grant.
      Without credentials, this connector reports not_configured.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.connectors.base import BaseConnector, ConnectorResult
from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

ORCID_API_BASE = "https://pub.orcid.org/v3.0"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"  # noqa: S105  # nosec B105
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)


class ORCIDConnector(BaseConnector):
    def __init__(self):
        self._access_token: str | None = None

    @property
    def provider_name(self) -> str:
        return "orcid"

    @property
    def display_name(self) -> str:
        return "ORCID Public API"

    @property
    def terms_url(self) -> str:
        return "https://info.orcid.org/documentation/api-tutorials/"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def capabilities(self) -> dict[str, bool]:
        return {
            "record_lookup": True,
            "works_read": True,
            "author_search": False,
            "doi_lookup": False,
        }

    def _is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.orcid_client_id and settings.orcid_client_secret)

    async def _get_token(self) -> str | None:
        """Get access token via client credentials grant."""
        if self._access_token:
            return self._access_token

        settings = get_settings()
        if not self._is_configured():
            return None

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(
                    ORCID_TOKEN_URL,
                    data={
                        "client_id": settings.orcid_client_id,
                        "client_secret": settings.orcid_client_secret,
                        "grant_type": "client_credentials",
                        "scope": "/read-public",
                    },
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._access_token = data.get("access_token")
                    return self._access_token
                else:
                    logger.warning("orcid_token_failed", status=resp.status_code)
                    return None
        except Exception as e:
            logger.warning("orcid_token_error", error=str(e))
            return None

    async def health_check(self) -> dict:
        if not self._is_configured():
            return {"status": "not_configured", "detail": "ORCID client credentials not set"}
        token = await self._get_token()
        if not token:
            return {"status": "auth_failed", "detail": "Could not obtain access token"}
        return {"status": "healthy"}

    async def search_author_candidates(
        self,
        faculty_name: str,
        orcid: str | None = None,
        institution: str | None = None,
        name_variants: list[str] | None = None,
    ) -> ConnectorResult:
        """ORCID connector reads records by ORCID, not search by name."""
        if not orcid:
            return ConnectorResult(
                status="skipped",
                warnings=["ORCID connector requires a known ORCID iD; no ORCID provided"],
            )

        if not self._is_configured():
            return ConnectorResult(
                status="auth_failed",
                errors=[
                    "ORCID client credentials not configured "
                    "(ORCID_CLIENT_ID / ORCID_CLIENT_SECRET)"
                ],
            )

        token = await self._get_token()
        if not token:
            return ConnectorResult(
                status="auth_failed", errors=["Could not obtain ORCID access token"]
            )

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
                resp = await client.get(f"{ORCID_API_BASE}/{orcid}/record", headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    record = self._normalize_record(data, orcid)
                    return ConnectorResult(
                        status="succeeded",
                        records=[record],
                        request_count=1,
                        retrieved_at=datetime.now(UTC),
                    )
                elif resp.status_code == 404:
                    return ConnectorResult(
                        status="succeeded",
                        records=[],
                        request_count=1,
                        warnings=[f"ORCID {orcid} not found"],
                    )
                elif resp.status_code in (401, 403):
                    return ConnectorResult(
                        status="auth_failed",
                        request_count=1,
                        errors=[f"ORCID auth failed: {resp.status_code}"],
                    )
                else:
                    return ConnectorResult(
                        status="failed",
                        request_count=1,
                        errors=[f"ORCID record fetch returned {resp.status_code}"],
                    )
        except Exception as e:
            return ConnectorResult(status="failed", request_count=1, errors=[str(e)])

    def _normalize_record(self, raw: dict, orcid: str) -> dict:
        person = raw.get("person", {})
        name_data = person.get("name", {})
        given = name_data.get("given-names", {}).get("value", "")
        family = name_data.get("family-name", {}).get("value", "")
        display_name = f"{given} {family}".strip()

        # Affiliations
        activities = raw.get("activities-summary", {})
        employments = activities.get("employments", {}).get("affiliation-group", [])
        affiliations = []
        for group in employments:
            for summary in group.get("summaries", []):
                emp = summary.get("employment-summary", {})
                org = emp.get("organization", {})
                affiliations.append(org.get("name", ""))

        return {
            "provider": "orcid",
            "provider_author_id": orcid,
            "display_name": display_name,
            "provider_orcid": orcid,
            "provider_affiliation": "; ".join(affiliations) if affiliations else None,
            "source_url": f"https://orcid.org/{orcid}",
            "raw_data": raw,
        }
