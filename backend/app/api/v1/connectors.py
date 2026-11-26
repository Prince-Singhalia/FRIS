"""Connector status routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.settings import Settings, get_settings
from app.db.session import get_db
from app.domain.schemas import ConnectorStatusResponse

router = APIRouter()


class ConnectorDefinition(TypedDict):
    provider: str
    display_name: str
    terms_url: str
    capabilities: dict[str, bool]
    credential_check: Callable[[Settings], bool]


# Default connectors and their credential requirements
DEFAULT_CONNECTORS: list[ConnectorDefinition] = [
    {
        "provider": "openalex",
        "display_name": "OpenAlex",
        "terms_url": "https://docs.openalex.org/",
        "capabilities": {"author_search": True, "works_fetch": True, "doi_lookup": True},
        "credential_check": lambda s: True,  # No key required for basic use
    },
    {
        "provider": "crossref",
        "display_name": "Crossref",
        "terms_url": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
        "capabilities": {"author_search": True, "doi_lookup": True, "works_fetch": False},
        "credential_check": lambda s: True,  # No key required, mailto recommended
    },
    {
        "provider": "orcid",
        "display_name": "ORCID Public API",
        "terms_url": "https://info.orcid.org/documentation/api-tutorials/",
        "capabilities": {"record_lookup": True, "works_read": True},
        "credential_check": lambda s: bool(s.orcid_client_id and s.orcid_client_secret),
    },
    {
        "provider": "semantic_scholar",
        "display_name": "Semantic Scholar",
        "terms_url": "https://api.semanticscholar.org/api-docs/",
        "capabilities": {"author_search": True, "works_fetch": True},
        "credential_check": lambda s: True,  # API key optional, rate limits differ
    },
    {
        "provider": "ieee",
        "display_name": "IEEE Xplore",
        "terms_url": "https://developer.ieee.org/",
        "capabilities": {"search": True},
        "credential_check": lambda s: bool(s.ieee_api_key),
    },
]


@router.get("/status", response_model=list[ConnectorStatusResponse])
async def get_connector_status(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    statuses = []

    for conn in DEFAULT_CONNECTORS:
        is_configured = conn["credential_check"](settings)
        is_enabled = conn["provider"] != "ieee"  # IEEE disabled by default

        statuses.append(
            ConnectorStatusResponse(
                provider=conn["provider"],
                display_name=conn["display_name"],
                is_enabled=is_enabled,
                is_configured=is_configured,
                health_status="not_checked" if is_configured else "not_configured",
                capabilities=conn["capabilities"],
                terms_url=conn["terms_url"],
            )
        )

    return statuses
