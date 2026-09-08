"""
Unit tests for SDK billing module.

Tests BillingModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.billing import BillingModule, PaymentMethodSetup


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def billing_module(mock_http):
    """Create BillingModule with mock HTTP client."""
    return BillingModule(mock_http)


@pytest.mark.unit
@pytest.mark.asyncio
class TestBillingModule:
    """Test BillingModule methods."""

    async def test_setup_payment_method_returns_checkout_url(self, mock_http, billing_module):
        """setup_payment_method() should return the Stripe Checkout URL and hit the real route."""
        mock_http.request = AsyncMock(
            return_value={"url": "https://checkout.stripe.com/c/pay/cs_test_123"}
        )

        result = await billing_module.setup_payment_method()

        assert isinstance(result, PaymentMethodSetup)
        assert result.url == "https://checkout.stripe.com/c/pay/cs_test_123"
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/billing/setup-payment-method",
        )
