"""Tests for collecting results from submitted Prefect tasks."""

import asyncio
from concurrent.futures import Future

import pytest

from app.workflows.discovery import _collect_provider_results


def test_collect_provider_results_waits_for_completed_futures():
    first = Future()
    second = Future()
    first.set_result({"provider": "openalex"})
    second.set_result({"provider": "crossref"})

    results = asyncio.run(_collect_provider_results([first.result, second.result]))

    assert results == [{"provider": "openalex"}, {"provider": "crossref"}]


def test_collect_provider_results_rejects_non_dictionary_results():
    result = Future()
    result.set_result(None)

    with pytest.raises(TypeError, match="non-dictionary result"):
        asyncio.run(_collect_provider_results([result.result]))
