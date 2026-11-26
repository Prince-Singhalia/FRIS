from __future__ import annotations

import pytest

from app.connectors.openalex import OpenAlexConnector


class MockResponse:
    status_code = 200
    headers: dict[str, str] = {}
    text = ""

    def __init__(self, page: int):
        self.page = page

    def json(self):
        return {
            "meta": {"count": 3, "next_cursor": "cursor-ignored-in-page-mode"},
            "results": [{"id": f"https://openalex.org/W{self.page}"}],
        }


class MockClient:
    calls: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params):
        self.calls.append({"url": url, "params": params.copy()})
        return MockResponse(int(params["page"]))


class EmptyOrcidResponse:
    status_code = 200
    headers: dict[str, str] = {}
    text = ""

    def json(self):
        return {"results": []}


class ProviderFailureResponse:
    status_code = 503
    headers: dict[str, str] = {}
    text = "Provider unavailable"


class OrcidMockClient(MockClient):
    async def get(self, url, params):
        self.calls.append({"url": url, "params": params.copy()})
        return EmptyOrcidResponse()


class ProviderFailureMockClient(MockClient):
    async def get(self, url, params):
        self.calls.append({"url": url, "params": params.copy()})
        return ProviderFailureResponse()


@pytest.mark.asyncio
async def test_numbered_pages_keep_author_filter_and_advance(monkeypatch):
    MockClient.calls = []
    monkeypatch.setattr("app.connectors.openalex.httpx.AsyncClient", MockClient)
    connector = OpenAlexConnector()

    first = await connector.fetch_author_works("https://openalex.org/A123", per_page=1, page=1)
    second = await connector.fetch_author_works("https://openalex.org/A123", per_page=1, page=2)
    third = await connector.fetch_author_works("https://openalex.org/A123", per_page=1, page=3)

    assert MockClient.calls[0]["params"]["filter"] == "authorships.author.id:A123"
    assert MockClient.calls[0]["params"]["page"] == "1"
    assert MockClient.calls[1]["params"]["page"] == "2"
    assert MockClient.calls[2]["params"]["page"] == "3"
    assert first.records[0]["provider_work_id"] != second.records[0]["provider_work_id"]
    assert first.pagination == {"page": 1, "next_page": 2, "has_more": True, "limit_reached": False}
    assert second.pagination["has_more"] is True
    assert third.pagination["has_more"] is False


@pytest.mark.asyncio
async def test_page_is_capped_at_openalex_basic_result_limit(monkeypatch):
    MockClient.calls = []
    monkeypatch.setattr("app.connectors.openalex.httpx.AsyncClient", MockClient)
    await OpenAlexConnector().fetch_author_works("A123", per_page=50, page=999)
    assert MockClient.calls[0]["params"]["page"] == "200"


def test_configured_cors_default_includes_port_5174():
    from app.core.settings import Settings

    settings = Settings(_env_file=None)
    assert "http://127.0.0.1:5174" in settings.cors_origins
    assert "http://localhost:5174" in settings.cors_origins


def test_author_source_url_points_to_the_openalex_profile():
    author = OpenAlexConnector()._normalize_author(
        {"id": "https://openalex.org/A123", "display_name": "Example Researcher"}
    )

    assert author["source_url"] == "https://openalex.org/authors/A123"


@pytest.mark.asyncio
async def test_orcid_lookup_does_not_fall_back_to_name_search(monkeypatch):
    OrcidMockClient.calls = []
    monkeypatch.setattr("app.connectors.openalex.httpx.AsyncClient", OrcidMockClient)

    result = await OpenAlexConnector().search_author_candidates(
        "", orcid="0000-0002-7481-0810"
    )

    assert result.status == "succeeded"
    assert result.records == []
    assert len(OrcidMockClient.calls) == 1
    assert OrcidMockClient.calls[0]["params"]["filter"] == "orcid:0000-0002-7481-0810"


@pytest.mark.asyncio
async def test_provider_http_failure_is_reported_as_failure(monkeypatch):
    ProviderFailureMockClient.calls = []
    monkeypatch.setattr(
        "app.connectors.openalex.httpx.AsyncClient", ProviderFailureMockClient
    )

    result = await OpenAlexConnector().search_author_candidates("Example Researcher")

    assert result.status == "failed"
    assert result.records == []
    assert result.errors == ["Name search for 'Example Researcher' returned 503"]
