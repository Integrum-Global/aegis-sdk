"""
Unit tests for SDK licenses module.

Tests LicensesModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.revenue.licenses import LicensesModule
from aegis_sdk.types import (
    Edition,
    License,
    LicenseEdition,
    LicenseStatus,
    LicenseUsage,
    LicenseValidation,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def licenses_module(mock_http):
    """Create LicensesModule with mock HTTP client."""
    return LicensesModule(mock_http)


def make_license_response(edition="enterprise", revoked=False):
    """Create a license response dict."""
    return {
        "license_id": "lic_123",
        "customer_id": "cust_456",
        "customer_name": "Acme Corp",
        "customer_email": "admin@acme.com",
        "edition": edition,
        "max_agents": -1,
        "max_users": -1,
        "max_runs_per_month": -1,
        "features": ["All features"],
        "expires_at": "2025-01-01T00:00:00Z",
        "phone_home_required": True,
        "phone_home_interval_days": 7,
        "grace_period_days": 30,
        "revoked": revoked,
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestLicensesModule:
    """Test LicensesModule methods."""

    async def test_generate_license(self, mock_http, licenses_module):
        """generate() should create a signed license."""
        mock_http.request = AsyncMock(
            return_value={
                "license_id": "lic_123",
                "license_data": make_license_response(),
                "message": "License generated successfully",
            }
        )

        result = await licenses_module.generate(
            customer_id="cust_456",
            customer_name="Acme Corp",
            customer_email="admin@acme.com",
            edition="enterprise",
            max_agents=-1,
            validity_days=365,
        )

        assert isinstance(result, License)
        assert result.license_id == "lic_123"
        assert result.edition == LicenseEdition.ENTERPRISE
        mock_http.request.assert_called_once()
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/v1/licenses/generate"

    async def test_generate_license_with_defaults(self, mock_http, licenses_module):
        """generate() should use sensible defaults."""
        mock_http.request = AsyncMock(
            return_value={
                "license_id": "lic_456",
                "license_data": make_license_response(edition="professional"),
                "message": "License generated",
            }
        )

        result = await licenses_module.generate(
            customer_id="cust_123",
            customer_name="Test Corp",
            customer_email="test@example.com",
            edition="professional",
        )

        call_args = mock_http.request.call_args
        request_data = call_args[1]["json_data"]
        assert request_data["validity_days"] == 365
        assert request_data["phone_home_required"] is True
        assert request_data["grace_period_days"] == 30

    async def test_validate_license_valid(self, mock_http, licenses_module):
        """validate() should return valid result."""
        mock_http.request = AsyncMock(
            return_value={
                "valid": True,
                "message": "License is valid",
                "expires_at": "2025-01-01T00:00:00Z",
                "entitlements": {"agents": -1, "users": -1},
                "next_check_days": 7,
            }
        )

        result = await licenses_module.validate(
            license_id="lic_123",
            machine_id="machine-001",
            timestamp="2024-06-01T12:00:00Z",
            app_version="1.0.0",
        )

        assert isinstance(result, LicenseValidation)
        assert result.valid is True
        assert result.next_check_days == 7
        mock_http.request.assert_called_once()
        call_args = mock_http.request.call_args
        assert call_args[0][1] == "/api/v1/licenses/validate"

    async def test_validate_license_with_usage(self, mock_http, licenses_module):
        """validate() should send usage telemetry."""
        mock_http.request = AsyncMock(
            return_value={
                "valid": True,
                "message": "License is valid",
                "next_check_days": 7,
            }
        )

        await licenses_module.validate(
            license_id="lic_123",
            machine_id="machine-001",
            timestamp="2024-06-01T12:00:00Z",
            app_version="1.0.0",
            usage={"agents_created": 5, "runs_this_month": 100},
        )

        call_args = mock_http.request.call_args
        request_data = call_args[1]["json_data"]
        assert request_data["usage"] == {"agents_created": 5, "runs_this_month": 100}

    async def test_validate_license_revoked(self, mock_http, licenses_module):
        """validate() should return invalid for revoked license."""
        mock_http.request = AsyncMock(
            return_value={
                "valid": False,
                "message": "License has been revoked",
                "next_check_days": 1,
            }
        )

        result = await licenses_module.validate(
            license_id="lic_123",
            machine_id="machine-001",
            timestamp="2024-06-01T12:00:00Z",
            app_version="1.0.0",
        )

        assert result.valid is False
        assert "revoked" in result.message.lower()

    async def test_revoke_license(self, mock_http, licenses_module):
        """revoke() should mark license as revoked."""
        mock_http.request = AsyncMock(
            return_value={
                "license_id": "lic_123",
                "revoked": True,
                "message": "License revoked: Customer churned",
            }
        )

        result = await licenses_module.revoke(
            license_id="lic_123",
            reason="Customer churned",
        )

        assert result is True
        mock_http.request.assert_called_once()
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/v1/licenses/lic_123/revoke"
        assert call_args[1]["json_data"]["reason"] == "Customer churned"

    async def test_get_usage(self, mock_http, licenses_module):
        """get_usage() should return telemetry data."""
        mock_http.request = AsyncMock(
            return_value={
                "license_id": "lic_123",
                "validations": [
                    {"timestamp": "2024-06-01T12:00:00Z", "machine_id": "m1"},
                    {"timestamp": "2024-06-02T12:00:00Z", "machine_id": "m1"},
                ],
                "total_validations": 2,
            }
        )

        result = await licenses_module.get_usage("lic_123")

        assert isinstance(result, LicenseUsage)
        assert result.license_id == "lic_123"
        assert result.total_validations == 2
        assert len(result.validations) == 2
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/licenses/lic_123/usage",
        )

    async def test_get_status(self, mock_http, licenses_module):
        """get_status() should return current license status."""
        mock_http.request = AsyncMock(
            return_value={
                "valid": True,
                "license_id": "lic_123",
                "customer_name": "Acme Corp",
                "edition": "enterprise",
                "expires_at": "2025-01-01T00:00:00Z",
                "days_remaining": 180,
                "grace_period_active": False,
                "entitlements": {"agents": -1},
            }
        )

        result = await licenses_module.get_status()

        assert isinstance(result, LicenseStatus)
        assert result.valid is True
        assert result.license_id == "lic_123"
        assert result.days_remaining == 180
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/licenses/status",
        )

    async def test_get_status_grace_period(self, mock_http, licenses_module):
        """get_status() should show grace period info."""
        mock_http.request = AsyncMock(
            return_value={
                "valid": False,
                "license_id": "lic_123",
                "grace_period_active": True,
                "grace_period_days_remaining": 20,
            }
        )

        result = await licenses_module.get_status()

        assert result.grace_period_active is True
        assert result.grace_period_days_remaining == 20

    async def test_list_editions(self, mock_http, licenses_module):
        """list_editions() should return edition info."""
        mock_http.request = AsyncMock(
            return_value={
                "editions": {
                    "starter": {
                        "features": ["Feature A", "Feature B"],
                        "limits": {"agents": 5, "users": 5},
                    },
                    "professional": {
                        "features": ["Feature A", "Feature B", "Feature C"],
                        "limits": {"agents": 50, "users": 25},
                    },
                    "enterprise": {
                        "features": ["All features"],
                        "limits": {"agents": -1, "users": -1},
                    },
                }
            }
        )

        result = await licenses_module.list_editions()

        assert len(result) == 3
        assert "starter" in result
        assert "enterprise" in result
        assert isinstance(result["starter"], Edition)
        assert result["enterprise"].limits["agents"] == -1
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/licenses/editions",
        )
