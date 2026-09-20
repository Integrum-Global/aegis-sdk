"""
Unit tests for SDK usage module.

Tests UsageModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.exceptions import NotFoundError, UnsupportedOperationError
from aegis_sdk.revenue.usage import UsageModule
from aegis_sdk.types import (
    Usage,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def usage_module(mock_http):
    """Create UsageModule with mock HTTP client."""
    return UsageModule(mock_http)


MOCK_USAGE_RESPONSE = {
    "agent_execution": {"limit": 10000, "current": 5000, "unit": "count"},
    "token": {"limit": 1000000, "current": 250000, "unit": "1000 tokens"},
    "storage": {"limit": 100, "current": 25, "unit": "GB"},
    "api_call": {"limit": 100000, "current": 10000, "unit": "count"},
}


@pytest.mark.unit
@pytest.mark.asyncio
class TestUsageModule:
    """Test UsageModule methods."""

    async def test_get_current_usage(self, mock_http, usage_module):
        """get_current() should return usage for all resource types."""
        mock_http.request = AsyncMock(return_value=MOCK_USAGE_RESPONSE)

        result = await usage_module.get_current()

        assert isinstance(result, Usage)
        assert result.agent_execution.limit == 10000
        assert result.agent_execution.current == 5000
        assert result.token.limit == 1000000
        assert result.storage.unit == "GB"
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/subscriptions/usage",
        )

    async def test_get_current_calculates_remaining(self, mock_http, usage_module):
        """get_current() should calculate remaining capacity."""
        mock_http.request = AsyncMock(return_value=MOCK_USAGE_RESPONSE)

        result = await usage_module.get_current()

        assert result.agent_execution.remaining == 5000  # 10000 - 5000
        assert result.api_call.remaining == 90000  # 100000 - 10000

    async def test_get_current_detects_unlimited(self, mock_http, usage_module):
        """get_current() should detect unlimited resources."""
        unlimited_response = {
            "agent_execution": {"limit": -1, "current": 5000, "unit": "count"},
            "token": {"limit": 0, "current": 0, "unit": "1000 tokens"},
            "storage": {"limit": 100, "current": 25, "unit": "GB"},
            "api_call": {"limit": 100000, "current": 10000, "unit": "count"},
        }
        mock_http.request = AsyncMock(return_value=unlimited_response)

        result = await usage_module.get_current()

        assert result.agent_execution.unlimited is True
        assert result.storage.unlimited is False

    async def test_get_history_raises_because_there_is_no_route(self, mock_http, usage_module):
        """get_history() ALWAYS raises — the route has never existed.

        This replaces `test_get_history_returns_empty_without_analytics`, which
        asserted `result == []`. That assertion was the defect stated as a
        contract: the method swallowed the 404 and returned an empty list, so a
        caller could not distinguish "no usage in this period" from "this
        endpoint does not exist". Both answers were `[]`.

        The old test described the 404 as "analytics endpoint not deployed" — a
        DEPLOYMENT state. It is not; the API exposes no `/analytics/usage/*`
        routes at all, so there is no version of the world in which this method
        returns data.
        """
        mock_http.request = AsyncMock(side_effect=NotFoundError("Not Found"))

        with pytest.raises(UnsupportedOperationError) as excinfo:
            await usage_module.get_history(
                start_date="2024-01-01",
                end_date="2024-01-31",
            )

        # The message must NAME the gap, not merely fail.
        assert "/analytics/usage/history" in str(excinfo.value)
        # And nothing was requested: the raise precedes any HTTP call, so the
        # mock is never invoked. This is the property that distinguishes
        # "retired" from "down" — retrying would be meaningless.
        mock_http.request.assert_not_called()

    async def test_get_history_raises_even_when_the_transport_would_succeed(
        self, mock_http, usage_module
    ):
        """A transport that would return data does not make the method work.

        This replaces `test_get_history_with_analytics`, which asserted
        `len(result) == 2` against a mocked success. That test described an
        endpoint that does not exist — a green assertion about a route the
        server has never mounted.
        """
        mock_http.request = AsyncMock(return_value={"history": [{"date": "2024-01-01"}]})

        with pytest.raises(UnsupportedOperationError):
            await usage_module.get_history(
                start_date="2024-01-01",
                end_date="2024-01-31",
                resource_type="agent_execution",
            )

        mock_http.request.assert_not_called()

    async def test_get_breakdown_raises_because_there_is_no_route(self, mock_http, usage_module):
        """get_breakdown() ALWAYS raises — see get_history above.

        Replaces `test_get_breakdown_returns_empty_without_analytics`, which
        asserted an empty-but-valid `UsageBreakdown`. That is the silent
        false-negative this change removes.
        """
        mock_http.request = AsyncMock(side_effect=NotFoundError("Not Found"))

        with pytest.raises(UnsupportedOperationError) as excinfo:
            await usage_module.get_breakdown(
                resource_type="agent_execution",
                dimension="agent",
            )

        assert "/analytics/usage/breakdown" in str(excinfo.value)
        mock_http.request.assert_not_called()

    async def test_get_breakdown_raises_even_when_the_transport_would_succeed(
        self, mock_http, usage_module
    ):
        """A transport that would return data does not make the method work.

        Replaces `test_get_breakdown_with_analytics`.
        """
        mock_http.request = AsyncMock(return_value={"by_agent": {"agent_1": 500}})

        with pytest.raises(UnsupportedOperationError):
            await usage_module.get_breakdown(
                resource_type="agent_execution",
                dimension="agent",
            )

        mock_http.request.assert_not_called()
