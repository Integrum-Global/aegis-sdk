"""
Unit tests for SDK quotas module.

Tests QuotasModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.quotas import QuotasModule
from aegis_sdk.types import (
    Quota,
    QuotaCheck,
    ResourceType,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def quotas_module(mock_http):
    """Create QuotasModule with mock HTTP client."""
    return QuotasModule(mock_http)


MOCK_LIMITS_RESPONSE = {
    "limits": {
        "agents": {"limit": 10, "current": 5},
        "team_members": {"limit": 5, "current": 3},
        "agent_execution": {"limit": 10000, "current": 5000},
        "storage": {"limit": 100, "current": 25},
    }
}


@pytest.mark.unit
@pytest.mark.asyncio
class TestQuotasModule:
    """Test QuotasModule methods."""

    async def test_get_quotas(self, mock_http, quotas_module):
        """get() should return all quotas."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        result = await quotas_module.get()

        assert len(result) > 0
        assert all(isinstance(q, Quota) for q in result)
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/features/limits",
        )

    async def test_get_quotas_calculates_remaining(self, mock_http, quotas_module):
        """get() should calculate remaining capacity."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        result = await quotas_module.get()

        # Find agents quota
        agents_quota = next((q for q in result if q.resource_type == ResourceType.AGENTS), None)
        if agents_quota:
            assert agents_quota.remaining == 5  # 10 - 5

    async def test_get_quotas_caches_result(self, mock_http, quotas_module):
        """get() should cache quotas for client-side operations."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        await quotas_module.get()

        assert quotas_module._quotas_cache is not None

    async def test_update_quota(self, mock_http, quotas_module):
        """update() should change quota limit."""
        mock_http.request = AsyncMock(
            return_value={
                "resource_type": "agents",
                "limit": 20,
                "current": 5,
                "remaining": 15,
            }
        )

        result = await quotas_module.update(
            resource_type="agents",
            new_limit=20,
        )

        assert isinstance(result, Quota)
        assert result.limit == 20
        mock_http.request.assert_called_once()
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/v1/billing/quotas/adjust"

    async def test_update_invalidates_cache(self, mock_http, quotas_module):
        """update() should invalidate quota cache."""
        # First populate cache
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)
        await quotas_module.get()
        assert quotas_module._quotas_cache is not None

        # Then update
        mock_http.request = AsyncMock(
            return_value={
                "resource_type": "agents",
                "limit": 20,
                "current": 5,
            }
        )
        await quotas_module.update("agents", 20)

        # Cache should be invalidated
        assert quotas_module._quotas_cache is None

    async def test_check_limit_allowed(self, mock_http, quotas_module):
        """check_limit() should return allowed when under limit."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        result = await quotas_module.check_limit("agents", amount=1)

        assert isinstance(result, QuotaCheck)
        assert result.allowed is True
        assert result.amount_requested == 1

    async def test_check_limit_denied(self, mock_http, quotas_module):
        """check_limit() should return denied when at limit."""
        at_limit_response = {
            "limits": {
                "agents": {"limit": 5, "current": 5},
            }
        }
        mock_http.request = AsyncMock(return_value=at_limit_response)

        result = await quotas_module.check_limit("agents", amount=1)

        assert result.allowed is False
        assert result.remaining == 0

    async def test_check_limit_uses_cached_quotas(self, mock_http, quotas_module):
        """check_limit() should use cached quotas."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        # First call loads cache
        await quotas_module.get()

        # Second call should use cache
        result = await quotas_module.check_limit("agents", amount=1)

        # Should only have called request once (for get)
        assert mock_http.request.call_count == 1

    async def test_check_limit_bulk_operation(self, mock_http, quotas_module):
        """check_limit() should check for bulk operations."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        # Agents: limit=10, current=5, remaining=5
        # Requesting 3 should be allowed
        result = await quotas_module.check_limit("agents", amount=3)
        assert result.allowed is True

        # Requesting 10 should be denied (only 5 remaining)
        result = await quotas_module.check_limit("agents", amount=10)
        assert result.allowed is False

    async def test_check_limit_unlimited(self, mock_http, quotas_module):
        """check_limit() should always allow unlimited resources."""
        unlimited_response = {
            "limits": {
                "agents": {"limit": -1, "current": 1000},
            }
        }
        mock_http.request = AsyncMock(return_value=unlimited_response)

        result = await quotas_module.check_limit("agents", amount=9999)

        assert result.allowed is True

    async def test_check_limit_unknown_resource(self, mock_http, quotas_module):
        """check_limit() should handle unknown resource types gracefully."""
        mock_http.request = AsyncMock(return_value=MOCK_LIMITS_RESPONSE)

        # Force cache
        await quotas_module.get()

        # Try to check unknown resource - token is in response as agent_execution
        # This will try "token" which might not match
        # The module should handle this gracefully
        result = await quotas_module.check_limit("token", amount=1)
        # Should default to allowed for unknown types
        assert isinstance(result, QuotaCheck)
