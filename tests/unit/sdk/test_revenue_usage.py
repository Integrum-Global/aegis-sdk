"""
Unit tests for SDK usage module.

Tests UsageModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.exceptions import NotFoundError
from aegis_sdk.revenue.usage import UsageModule
from aegis_sdk.types import (
    ResourceType,
    Usage,
    UsageBreakdown,
    UsageHistory,
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

    async def test_get_history_returns_empty_without_analytics(self, mock_http, usage_module):
        """get_history() should return empty list when analytics not available."""
        # Simulate analytics endpoint not deployed (404)
        mock_http.request = AsyncMock(side_effect=NotFoundError("Not Found"))

        result = await usage_module.get_history(
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        # Should return empty list, not raise exception
        assert result == []

    async def test_get_history_with_analytics(self, mock_http, usage_module):
        """get_history() should return historical data when available."""
        mock_http.request = AsyncMock(
            return_value={
                "history": [
                    {
                        "date": "2024-01-01",
                        "resource_type": "agent_execution",
                        "usage": 100,
                        "limit": 10000,
                    },
                    {
                        "date": "2024-01-02",
                        "resource_type": "agent_execution",
                        "usage": 150,
                        "limit": 10000,
                    },
                ]
            }
        )

        result = await usage_module.get_history(
            start_date="2024-01-01",
            end_date="2024-01-31",
            resource_type="agent_execution",
        )

        assert len(result) == 2
        assert all(isinstance(h, UsageHistory) for h in result)

    async def test_get_breakdown_returns_empty_without_analytics(self, mock_http, usage_module):
        """get_breakdown() should return empty breakdown when analytics not available."""
        mock_http.request = AsyncMock(side_effect=NotFoundError("Not Found"))

        result = await usage_module.get_breakdown(
            resource_type="agent_execution",
            dimension="agent",
        )

        assert isinstance(result, UsageBreakdown)
        assert result.resource_type == ResourceType.AGENT_EXECUTION
        # Breakdown data should be empty/None
        assert result.by_agent is None or result.by_agent == {}

    async def test_get_breakdown_with_analytics(self, mock_http, usage_module):
        """get_breakdown() should return breakdown when available."""
        mock_http.request = AsyncMock(
            return_value={
                "by_agent": {
                    "agent_1": 500,
                    "agent_2": 300,
                    "agent_3": 200,
                }
            }
        )

        result = await usage_module.get_breakdown(
            resource_type="agent_execution",
            dimension="agent",
        )

        assert isinstance(result, UsageBreakdown)
        assert result.by_agent is not None
        assert result.by_agent["agent_1"] == 500
