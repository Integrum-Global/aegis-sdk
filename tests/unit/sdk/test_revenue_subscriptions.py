"""
Unit tests for SDK subscriptions module.

Tests SubscriptionsModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.subscriptions import SubscriptionsModule
from aegis_sdk.types import (
    PlanTier,
    PortalSession,
    Subscription,
    SubscriptionStatus,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def subscriptions_module(mock_http):
    """Create SubscriptionsModule with mock HTTP client."""
    return SubscriptionsModule(mock_http)


def make_subscription_response(
    plan_tier="professional",
    status="active",
    cancel_at_period_end=False,
):
    """Create a subscription response dict."""
    return {
        "id": "sub_123",
        "organization_id": "org_456",
        "plan_tier": plan_tier,
        "billing_cycle": "monthly",
        "status": status,
        "current_period_start": "2024-01-01T00:00:00Z",
        "current_period_end": "2024-02-01T00:00:00Z",
        "cancel_at_period_end": cancel_at_period_end,
        "stripe_customer_id": "cus_abc",
        "stripe_subscription_id": "sub_xyz",
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestSubscriptionsModule:
    """Test SubscriptionsModule methods."""

    async def test_get_current_subscription(self, mock_http, subscriptions_module):
        """get() should return current subscription."""
        mock_http.request = AsyncMock(return_value=make_subscription_response())

        result = await subscriptions_module.get()

        assert isinstance(result, Subscription)
        assert result.id == "sub_123"
        assert result.plan_tier == PlanTier.PROFESSIONAL
        assert result.status == SubscriptionStatus.ACTIVE
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/subscriptions/current",
        )

    async def test_subscribe_with_payment_method(self, mock_http, subscriptions_module):
        """subscribe() should create subscription with payment method."""
        mock_http.request = AsyncMock(return_value=make_subscription_response(plan_tier="starter"))

        result = await subscriptions_module.subscribe(
            plan_id="starter",
            billing_cycle="monthly",
            payment_method_id="pm_card_visa",
        )

        assert isinstance(result, Subscription)
        assert result.plan_tier == PlanTier.STARTER
        mock_http.request.assert_called_once()
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/v1/subscriptions/subscribe"
        assert call_args[1]["json_data"]["plan_id"] == "starter"
        assert call_args[1]["json_data"]["billing_cycle"] == "monthly"
        assert call_args[1]["json_data"]["payment_method_id"] == "pm_card_visa"

    async def test_subscribe_without_payment_method(self, mock_http, subscriptions_module):
        """subscribe() should work without payment method if default exists."""
        mock_http.request = AsyncMock(
            return_value=make_subscription_response(plan_tier="professional")
        )

        result = await subscriptions_module.subscribe(
            plan_id="professional",
            billing_cycle="annual",
        )

        assert isinstance(result, Subscription)
        call_args = mock_http.request.call_args
        # payment_method_id should not be in request if None
        assert (
            "payment_method_id" not in call_args[1]["json_data"]
            or call_args[1]["json_data"]["payment_method_id"] is None
        )

    async def test_upgrade_with_proration(self, mock_http, subscriptions_module):
        """upgrade() should change plan with proration."""
        mock_http.request = AsyncMock(
            return_value=make_subscription_response(plan_tier="enterprise")
        )

        result = await subscriptions_module.upgrade(
            new_plan_id="enterprise",
            prorate=True,
        )

        assert isinstance(result, Subscription)
        assert result.plan_tier == PlanTier.ENTERPRISE
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "PUT"
        assert call_args[0][1] == "/api/v1/subscriptions/upgrade"
        assert call_args[1]["json_data"]["new_plan_id"] == "enterprise"
        assert call_args[1]["json_data"]["prorate"] is True

    async def test_upgrade_without_proration(self, mock_http, subscriptions_module):
        """upgrade() can skip proration."""
        mock_http.request = AsyncMock(return_value=make_subscription_response(plan_tier="starter"))

        result = await subscriptions_module.upgrade(
            new_plan_id="starter",
            prorate=False,
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["prorate"] is False

    async def test_cancel_at_period_end(self, mock_http, subscriptions_module):
        """cancel() should set cancel_at_period_end flag."""
        mock_http.request = AsyncMock(
            return_value=make_subscription_response(cancel_at_period_end=True)
        )

        result = await subscriptions_module.cancel(at_period_end=True)

        assert isinstance(result, Subscription)
        assert result.cancel_at_period_end is True
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/v1/subscriptions/cancel"
        assert call_args[1]["json_data"]["at_period_end"] is True

    async def test_cancel_immediately(self, mock_http, subscriptions_module):
        """cancel() can cancel immediately."""
        mock_http.request = AsyncMock(return_value=make_subscription_response(status="canceled"))

        result = await subscriptions_module.cancel(at_period_end=False)

        assert result.status == SubscriptionStatus.CANCELED
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["at_period_end"] is False

    async def test_reactivate(self, mock_http, subscriptions_module):
        """reactivate() should remove cancel flag."""
        mock_http.request = AsyncMock(
            return_value=make_subscription_response(cancel_at_period_end=False)
        )

        result = await subscriptions_module.reactivate()

        assert isinstance(result, Subscription)
        assert result.cancel_at_period_end is False
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/subscriptions/reactivate",
        )

    async def test_create_portal_session(self, mock_http, subscriptions_module):
        """create_portal_session() should return portal URL."""
        mock_http.request = AsyncMock(
            return_value={"url": "https://billing.stripe.com/session/abc123"}
        )

        result = await subscriptions_module.create_portal_session()

        assert isinstance(result, PortalSession)
        assert "stripe.com" in result.url
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/subscriptions/portal",
        )

    async def test_subscription_with_trial(self, mock_http, subscriptions_module):
        """get() should handle subscription with trial."""
        response = make_subscription_response(status="trialing")
        response["trial_start"] = "2024-01-01T00:00:00Z"
        response["trial_end"] = "2024-01-15T00:00:00Z"
        mock_http.request = AsyncMock(return_value=response)

        result = await subscriptions_module.get()

        assert result.status == SubscriptionStatus.TRIALING
        assert result.trial_start is not None
        assert result.trial_end is not None
