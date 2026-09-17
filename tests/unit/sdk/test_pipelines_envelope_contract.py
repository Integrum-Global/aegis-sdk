"""Tier 1: PipelinesModule against the envelope the server actually returns.

Every pipelines route returns ``{"data": ...}``; the list route returns
``{"data": [...], "total": N}``. Reading ``items`` off that envelope yields an
EMPTY list and a CORRECT total — a result that looks like "no pipelines yet"
and is indistinguishable, from the caller's side, from a real empty account.

The assertion that matters in every list test below is that ``items`` is
NON-EMPTY and carries the right ids. Asserting only the type of ``items``, or
only ``total``, would have passed for the entire life of the bug: ``total``
came through correctly the whole time.

Mocked at the HTTP-transport boundary, which is the correct seam for a
client-side contract test — no infrastructure is stood up.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.core.pipelines import PipelinesModule

PIPELINE_A = {
    "id": "pipeline_a",
    "name": "Research",
    "pattern": "sequential",
    "organization_id": "org_1",
    "workspace_id": "ws_1",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}
PIPELINE_B = {**PIPELINE_A, "id": "pipeline_b", "name": "Summarize"}


@pytest.fixture
def mock_http():
    http = MagicMock()
    http.request = AsyncMock()
    return http


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPipelinesListUnwrapsEnvelope:
    """GET /api/v1/pipelines -> {"data": [...], "total": N}."""

    async def test_list_returns_the_records_the_server_sent(self, mock_http):
        mock_http.request.return_value = {"data": [PIPELINE_A, PIPELINE_B], "total": 2}

        result = await PipelinesModule(mock_http).list()

        # THE assertion. An empty list here IS the bug, and it arrives with a
        # correct total attached, which is what made it look like real data.
        assert len(result.items) == 2, (
            "list() returned an empty page while the server sent 2 records — "
            "the {'data': [...]} envelope was not unwrapped"
        )
        assert [p.id for p in result.items] == ["pipeline_a", "pipeline_b"]
        assert result.items[0].name == "Research"
        assert result.total == 2

    async def test_list_total_alone_is_not_evidence(self, mock_http):
        """Pins the asymmetry explicitly: total is correct even when the page
        is empty, so a total-only assertion cannot detect the defect."""
        mock_http.request.return_value = {"data": [PIPELINE_A], "total": 1}

        result = await PipelinesModule(mock_http).list()

        assert result.total == 1
        assert result.items != [], "total was right and the page was empty"

    async def test_list_passes_pagination_params_through(self, mock_http):
        mock_http.request.return_value = {"data": [], "total": 0}

        await PipelinesModule(mock_http).list(workspace_id="ws_1", pattern="parallel")

        args, kwargs = mock_http.request.call_args
        assert args[0] == "GET"
        assert args[1] == "/api/v1/pipelines"
        assert kwargs["params"]["workspace_id"] == "ws_1"
        assert kwargs["params"]["pattern"] == "parallel"

    async def test_list_empty_envelope_is_genuinely_empty(self, mock_http):
        """The fix must not invent rows: an empty server page stays empty."""
        mock_http.request.return_value = {"data": [], "total": 0}

        result = await PipelinesModule(mock_http).list()

        assert result.items == []
        assert result.total == 0


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPipelinesListLegacyShapes:
    """The fix must not over-apply — older/plain shapes still work."""

    async def test_bare_array_response(self, mock_http):
        mock_http.request.return_value = [PIPELINE_A, PIPELINE_B]

        result = await PipelinesModule(mock_http).list()

        assert [p.id for p in result.items] == ["pipeline_a", "pipeline_b"]
        assert result.total == 2

    async def test_items_keyed_paginated_response(self, mock_http):
        mock_http.request.return_value = {
            "items": [PIPELINE_A],
            "total": 1,
            "page": 1,
            "page_size": 50,
            "has_next": False,
        }

        result = await PipelinesModule(mock_http).list()

        assert [p.id for p in result.items] == ["pipeline_a"]
        assert result.total == 1


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPipelinesSingleRecordRoutes:
    """GET/POST/PUT single-record routes all return {"data": {...}}."""

    async def test_get_returns_a_populated_pipeline(self, mock_http):
        mock_http.request.return_value = {"data": PIPELINE_A}

        pipeline = await PipelinesModule(mock_http).get("pipeline_a")

        assert pipeline.id == "pipeline_a"
        assert pipeline.name == "Research"
        assert pipeline.workspace_id == "ws_1"
        mock_http.request.assert_called_once_with("GET", "/api/v1/pipelines/pipeline_a")

    async def test_get_accepts_an_unwrapped_record(self, mock_http):
        """Over-application guard: a bare record must still parse."""
        mock_http.request.return_value = PIPELINE_A

        pipeline = await PipelinesModule(mock_http).get("pipeline_a")

        assert pipeline.id == "pipeline_a"

    async def test_create_returns_a_populated_pipeline(self, mock_http):
        mock_http.request.return_value = {"data": PIPELINE_A}

        pipeline = await PipelinesModule(mock_http).create(name="Research")

        assert pipeline.id == "pipeline_a"
        assert pipeline.name == "Research"

    async def test_update_returns_a_populated_pipeline(self, mock_http):
        mock_http.request.return_value = {"data": {**PIPELINE_A, "name": "Renamed"}}

        pipeline = await PipelinesModule(mock_http).update("pipeline_a", name="Renamed")

        assert pipeline.name == "Renamed"

    async def test_duplicate_returns_a_populated_pipeline(self, mock_http):
        mock_http.request.return_value = {"data": {**PIPELINE_A, "id": "pipeline_copy"}}

        pipeline = await PipelinesModule(mock_http).duplicate("pipeline_a", name="Copy")

        assert pipeline.id == "pipeline_copy"
