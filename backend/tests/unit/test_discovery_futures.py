"""Tests for collecting results from submitted Prefect tasks."""

import asyncio
from concurrent.futures import Future

from app.workflows.discovery import _collect_provider_results


def test_collect_provider_results_waits_for_completed_futures():
    first = Future()
    second = Future()
    first.set_result({"provider": "openalex"})
    second.set_result({"provider": "crossref"})

    results = asyncio.run(_collect_provider_results([first.result, second.result]))

    assert results == [{"provider": "openalex"}, {"provider": "crossref"}]
