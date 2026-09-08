"""
Unit tests for SDK revenue exception handling.

Tests PaymentError and proper exception handling in revenue modules.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.exceptions import (
    NotFoundError,
    PaymentError,
    ValidationError,
)
from aegis_sdk.revenue.plans import PlansModule


def make_plan(tier="starter"):
    """Create a complete plan response dict."""
    return {
        "id": tier,
        "tier": tier,
        "name": tier.title(),
        "description": f"{tier.title()} plan",
        "monthly_price": 19900,
        "annual_price": 199900,
        "features": ["Feature A"],
        "contact_sales": False,
    }


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def plans_module(mock_http):
    """Create PlansModule with mock HTTP client."""
    return PlansModule(mock_http)


@pytest.mark.unit
class TestPaymentError:
    """Test PaymentError exception."""

    def test_payment_error_basic(self):
        """PaymentError should be instantiable with message."""
        error = PaymentError("Payment declined")
        assert str(error) == "Payment declined"
        assert error.message == "Payment declined"
        assert error.decline_code is None

    def test_payment_error_with_decline_code(self):
        """PaymentError should accept decline_code."""
        error = PaymentError(
            "Card declined",
            decline_code="insufficient_funds",
        )
        assert error.decline_code == "insufficient_funds"

    def test_payment_error_with_details(self):
        """PaymentError should accept details dict."""
        error = PaymentError(
            "Payment failed",
            decline_code="card_declined",
            details={"card_last4": "4242"},
        )
        assert error.details == {"card_last4": "4242"}


@pytest.mark.unit
@pytest.mark.asyncio
class TestPlansModuleErrorHandling:
    """Test error handling in PlansModule."""

    async def test_get_features_invalid_tier_raises_validation_error(self, mock_http, plans_module):
        """get_features() should raise ValidationError for invalid tier."""
        mock_http.request = AsyncMock(return_value={"plans": [make_plan("starter")]})

        with pytest.raises(ValidationError) as exc_info:
            await plans_module.get_features("invalid_tier")

        assert "Invalid plan tier" in str(exc_info.value)

    async def test_compare_tiers_invalid_tier1_raises_validation_error(
        self, mock_http, plans_module
    ):
        """compare_tiers() should raise ValidationError for invalid tier1."""
        mock_http.request = AsyncMock(return_value={"plans": [make_plan("starter")]})

        with pytest.raises(ValidationError) as exc_info:
            await plans_module.compare_tiers("invalid", "starter")

        assert "Invalid plan tier: invalid" in str(exc_info.value)

    async def test_compare_tiers_invalid_tier2_raises_validation_error(
        self, mock_http, plans_module
    ):
        """compare_tiers() should raise ValidationError for invalid tier2."""
        mock_http.request = AsyncMock(return_value={"plans": [make_plan("starter")]})

        with pytest.raises(ValidationError) as exc_info:
            await plans_module.compare_tiers("starter", "invalid")

        assert "Invalid plan tier: invalid" in str(exc_info.value)

    async def test_compare_tiers_not_found_raises_not_found_error(self, mock_http, plans_module):
        """compare_tiers() should raise NotFoundError when tier not in API response."""
        # Only starter exists in response, but we request professional
        mock_http.request = AsyncMock(return_value={"plans": [make_plan("starter")]})

        with pytest.raises(NotFoundError) as exc_info:
            await plans_module.compare_tiers("starter", "professional")

        assert "professional" in str(exc_info.value)
