"""Base connector interface and registry."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectorResult:
    """Structured result from a connector operation."""

    status: str  # succeeded, failed, rate_limited, auth_failed, partial
    records: list[dict] = field(default_factory=list)
    pagination: dict | None = None
    request_count: int = 0
    rate_limit_info: dict | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    retrieved_at: datetime | None = None


class BaseConnector(abc.ABC):
    """Base contract for all provider connectors.

    Each adapter declares supported operations, auth requirements,
    rate limits, terms URL, and optional capabilities.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g., 'openalex', 'crossref')."""
        ...

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abc.abstractmethod
    def terms_url(self) -> str:
        """URL to provider terms of service / API docs."""
        ...

    @property
    def requires_auth(self) -> bool:
        """Whether this connector requires credentials to function."""
        return False

    @property
    def capabilities(self) -> dict[str, bool]:
        """Declare what this connector can do."""
        return {
            "author_search": False,
            "works_fetch": False,
            "doi_lookup": False,
            "record_lookup": False,
        }

    @abc.abstractmethod
    async def health_check(self) -> dict:
        """Check if the provider API is reachable and credentials valid."""
        ...

    async def search_author_candidates(
        self,
        faculty_name: str,
        orcid: str | None = None,
        institution: str | None = None,
        name_variants: list[str] | None = None,
    ) -> ConnectorResult:
        """Search for author candidates matching faculty profile."""
        return ConnectorResult(
            status="not_implemented",
            errors=[f"{self.provider_name} does not support author search"],
        )

    async def fetch_author_works(
        self,
        provider_author_id: str,
        cursor: str | None = None,
        per_page: int = 50,
    ) -> ConnectorResult:
        """Fetch works for a provider author ID."""
        return ConnectorResult(
            status="not_implemented",
            errors=[f"{self.provider_name} does not support works fetch"],
        )

    async def lookup_work_by_doi(self, doi: str) -> ConnectorResult:
        """Look up a work by DOI."""
        return ConnectorResult(
            status="not_implemented",
            errors=[f"{self.provider_name} does not support DOI lookup"],
        )


class ConnectorRegistry:
    """Registry of all available connectors."""

    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        self._connectors[connector.provider_name] = connector

    def get(self, provider_name: str) -> BaseConnector | None:
        return self._connectors.get(provider_name)

    def get_all(self) -> dict[str, BaseConnector]:
        return dict(self._connectors)

    def get_enabled(self, enabled_providers: list[str] | None = None) -> dict[str, BaseConnector]:
        if enabled_providers is None:
            return dict(self._connectors)
        return {
            name: conn
            for name, conn in self._connectors.items()
            if name in enabled_providers
        }


# Global registry instance
registry = ConnectorRegistry()
