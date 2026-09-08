"""
Unit tests for SDK plans module.

Tests PlansModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.plans import PlansModule
from aegis_sdk.types import (
    Plan,
    PlanFeatures,
    PlanTier,
    TierComparison,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def plans_module(mock_http):
    """Create PlansModule with mock HTTP client."""
    return PlansModule(mock_http)


MOCK_PLANS_RESPONSE = {
    "plans": [
        {
            "id": "starter",
            "name": "Starter",
            "tier": "starter",
            "description": "Perfect for small teams",
            "monthly_price": 19900,
            "annual_price": 199900,
            "features": [
                "Up to 10,000 agent executions/month",
                "1M tokens/month",
                "10GB storage",
            ],
            "contact_sales": False,
        },
        {
            "id": "professional",
            "name": "Professional",
            "tier": "professional",
            "description": "For growing teams",
            "monthly_price": 59900,
            "annual_price": 599900,
            "features": [
                "Up to 10,000 agent executions/month",
                "1M tokens/month",
                "10GB storage",
                "Up to 100,000 agent executions/month",
                "10M tokens/month",
                "100GB storage",
            ],
            "contact_sales": False,
        },
        {
            "id": "enterprise",
            "name": "Enterprise",
            "tier": "enterprise",
            "description": "Unlimited scale",
            "monthly_price": 0,
            "annual_price": 0,
            "features": [
                "Unlimited agent executions",
                "Unlimited tokens",
                "Unlimited storage",
                "Dedicated support",
            ],
            "contact_sales": True,
        },
    ]
}


@pytest.mark.unit
@pytest.mark.asyncio
class TestPlansModule:
    """Test PlansModule methods."""

    async def test_list_plans(self, mock_http, plans_module):
        """list() should return all available plans."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        result = await plans_module.list()

        assert len(result) == 3
        assert all(isinstance(p, Plan) for p in result)
        assert result[0].tier == PlanTier.STARTER
        assert result[1].tier == PlanTier.PROFESSIONAL
        assert result[2].tier == PlanTier.ENTERPRISE
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/subscriptions/plans",
        )

    async def test_list_plans_caches_result(self, mock_http, plans_module):
        """list() should cache plans for client-side operations."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        await plans_module.list()

        # Plans should be cached
        assert plans_module._plans_cache is not None
        assert len(plans_module._plans_cache) == 3

    async def test_get_features_from_cache(self, mock_http, plans_module):
        """get_features() should use cached plans."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        # First call loads plans
        await plans_module.list()

        # Second call uses cache
        features = await plans_module.get_features("starter")

        assert isinstance(features, PlanFeatures)
        assert len(features.features) == 3
        # Should only have called request once (for list)
        assert mock_http.request.call_count == 1

    async def test_get_features_loads_plans_if_not_cached(self, mock_http, plans_module):
        """get_features() should load plans if not cached."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        features = await plans_module.get_features("professional")

        assert isinstance(features, PlanFeatures)
        # Should have loaded plans
        assert mock_http.request.call_count == 1

    async def test_compare_tiers(self, mock_http, plans_module):
        """compare_tiers() should show differences between tiers."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        comparison = await plans_module.compare_tiers("starter", "professional")

        assert isinstance(comparison, TierComparison)
        assert comparison.tier1 == PlanTier.STARTER
        assert comparison.tier2 == PlanTier.PROFESSIONAL
        assert comparison.tier1_price_monthly == 19900
        assert comparison.tier2_price_monthly == 59900
        assert comparison.price_difference_monthly == 40000

    async def test_compare_tiers_additional_features(self, mock_http, plans_module):
        """compare_tiers() should list features only in higher tier."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        comparison = await plans_module.compare_tiers("starter", "professional")

        # Professional has more features than starter
        assert len(comparison.additional_in_tier2) > 0

    async def test_compare_tiers_enterprise(self, mock_http, plans_module):
        """compare_tiers() should handle enterprise pricing."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        comparison = await plans_module.compare_tiers("professional", "enterprise")

        assert comparison.tier2 == PlanTier.ENTERPRISE
        assert comparison.tier2_price_monthly == 0  # Contact sales

    async def test_plan_contact_sales_flag(self, mock_http, plans_module):
        """list() should include contact_sales flag."""
        mock_http.request = AsyncMock(return_value=MOCK_PLANS_RESPONSE)

        plans = await plans_module.list()

        # Enterprise requires contacting sales
        enterprise = next(p for p in plans if p.tier == PlanTier.ENTERPRISE)
        assert enterprise.contact_sales is True

        # Other tiers don't
        starter = next(p for p in plans if p.tier == PlanTier.STARTER)
        assert starter.contact_sales is False
