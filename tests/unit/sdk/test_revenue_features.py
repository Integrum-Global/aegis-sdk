"""
Unit tests for SDK features module.

Tests FeaturesModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.features import FeatureCheck, FeaturesModule


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def features_module(mock_http):
    """Create FeaturesModule with mock HTTP client."""
    return FeaturesModule(mock_http)


@pytest.mark.unit
@pytest.mark.asyncio
class TestFeaturesModule:
    """Test FeaturesModule methods."""

    async def test_check_allowed(self, mock_http, features_module):
        """check() should report an allowed feature and target the real route."""
        mock_http.request = AsyncMock(return_value={"allowed": True, "tier": "professional"})

        result = await features_module.check("sso")

        assert isinstance(result, FeatureCheck)
        assert result.allowed is True
        assert result.tier == "professional"
        assert result.reason is None
        assert result.required_tier is None
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/features/check",
            params={"feature": "sso"},
        )

    async def test_check_denied_surfaces_required_tier(self, mock_http, features_module):
        """check() should surface reason + required_tier when denied."""
        mock_http.request = AsyncMock(
            return_value={
                "allowed": False,
                "tier": "starter",
                "reason": "Feature 'sso' requires upgrade",
                "required_tier": "professional",
            }
        )

        result = await features_module.check("sso")

        assert result.allowed is False
        assert result.tier == "starter"
        assert result.required_tier == "professional"
        assert "requires upgrade" in result.reason
