"""
Licenses Module for Agentic OS SDK.

Provides license management operations for self-hosted deployments including
generation, validation (phone-home), revocation, and usage tracking.

6 methods:
- generate() - Generate a new license (admin only)
- validate() - Validate license via phone-home
- revoke() - Revoke a license
- get_usage() - Get license usage telemetry
- get_status() - Get current license status
- list_editions() - List available license editions
"""

from typing import Any

from .._http import encode_path_param
from ..types import (
    Edition,
    License,
    LicenseEdition,
    LicenseGenerate,
    LicenseStatus,
    LicenseUsage,
    LicenseValidation,
    LicenseValidationRequest,
)


class LicensesModule:
    """
    License management module.

    Provides methods for managing licenses in self-hosted deployments,
    including generation, phone-home validation, and revocation.

    Examples:
        # Generate a license (admin only)
        >>> license = await client.revenue.licenses.generate(
        ...     customer_id="cust_123",
        ...     customer_name="Acme Corp",
        ...     customer_email="admin@acme.com",
        ...     edition="enterprise",
        ...     validity_days=365
        ... )

        # Validate license (phone-home)
        >>> validation = await client.revenue.licenses.validate(
        ...     license_id="lic_123",
        ...     machine_id="machine-001",
        ...     timestamp=datetime.now(UTC).isoformat(),
        ...     app_version="1.0.0"
        ... )
        >>> if validation.valid:
        ...     print(f"License valid until {validation.expires_at}")

        # Get current license status
        >>> status = await client.revenue.licenses.get_status()
        >>> if status.grace_period_active:
        ...     print(f"Grace period: {status.grace_period_days_remaining} days left")

        # Revoke a license
        >>> await client.revenue.licenses.revoke("lic_123", reason="Customer churned")
    """

    def __init__(self, http_client):
        """
        Initialize licenses module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def generate(
        self,
        customer_id: str,
        customer_name: str,
        customer_email: str,
        edition: str,
        max_agents: int = -1,
        max_users: int = -1,
        max_runs_per_month: int = -1,
        features: list[str] | None = None,
        validity_days: int = 365,
        machine_binding: bool = False,
        machine_id: str | None = None,
        domain_restriction: list[str] | None = None,
        phone_home_required: bool = True,
        phone_home_interval_days: int = 7,
        grace_period_days: int = 30,
    ) -> License:
        """
        Generate a new signed license file.

        This endpoint is only available on the license server and requires
        admin authentication.

        Args:
            customer_id: Customer identifier
            customer_name: Customer display name
            customer_email: Customer email address
            edition: License edition ("starter", "professional", "enterprise")
            max_agents: Maximum agents allowed (-1 for unlimited)
            max_users: Maximum users allowed (-1 for unlimited)
            max_runs_per_month: Maximum runs per month (-1 for unlimited)
            features: Custom features list (defaults to edition features)
            validity_days: License validity in days
            machine_binding: Whether to bind license to machine
            machine_id: Machine fingerprint to bind to. REQUIRED when
                machine_binding is True — the server rejects the combination
                with a 400 because a license that declares binding but names no
                machine is unenforceable and fails verification.
            domain_restriction: List of allowed domains
            phone_home_required: Whether phone-home validation is required
            phone_home_interval_days: Days between phone-home checks
            grace_period_days: Grace period for offline operation

        Returns:
            License: Generated license with signature

        Raises:
            ValidationError: If parameters invalid
            AuthorizationError: If not admin
            ServiceUnavailableError: If not in license server mode

        Example:
            >>> license = await client.revenue.licenses.generate(
            ...     customer_id="cust_123",
            ...     customer_name="Acme Corp",
            ...     customer_email="admin@acme.com",
            ...     edition="enterprise",
            ...     max_agents=-1,  # unlimited
            ...     validity_days=365
            ... )
            >>> print(f"License ID: {license.license_id}")
        """
        request_data = LicenseGenerate(
            customer_id=customer_id,
            customer_name=customer_name,
            customer_email=customer_email,
            edition=LicenseEdition(edition),
            max_agents=max_agents,
            max_users=max_users,
            max_runs_per_month=max_runs_per_month,
            features=features,
            validity_days=validity_days,
            machine_binding=machine_binding,
            machine_id=machine_id,
            domain_restriction=domain_restriction,
            phone_home_required=phone_home_required,
            phone_home_interval_days=phone_home_interval_days,
            grace_period_days=grace_period_days,
        )
        response = await self._http.request(
            "POST",
            "/licenses/generate",
            json_data=request_data.model_dump(exclude_none=True),
        )
        # Response includes license_id, license_data, message
        license_data = response.get("license_data", {})
        license_data["license_id"] = response.get("license_id")
        return License(**license_data)

    async def validate(
        self,
        license_id: str,
        machine_id: str,
        timestamp: str,
        app_version: str,
        usage: dict[str, Any] | None = None,
    ) -> LicenseValidation:
        """
        Validate license via phone-home.

        Called by self-hosted installations to validate their license.
        Records usage telemetry and checks for revocation.

        Args:
            license_id: License identifier
            machine_id: Machine fingerprint
            timestamp: Request timestamp (ISO format)
            app_version: Application version
            usage: Current usage telemetry (optional)

        Returns:
            LicenseValidation: Validation result with entitlements

        Example:
            >>> from datetime import datetime, UTC
            >>> validation = await client.revenue.licenses.validate(
            ...     license_id="lic_123",
            ...     machine_id="machine-001",
            ...     timestamp=datetime.now(UTC).isoformat(),
            ...     app_version="1.0.0",
            ...     usage={"agents_created": 5, "runs_this_month": 100}
            ... )
            >>> if validation.valid:
            ...     print(f"Valid until: {validation.expires_at}")
            ...     print(f"Next check in: {validation.next_check_days} days")
            ... else:
            ...     print(f"Invalid: {validation.message}")
        """
        request_data = LicenseValidationRequest(
            license_id=license_id,
            machine_id=machine_id,
            timestamp=timestamp,
            app_version=app_version,
            usage=usage,
        )
        response = await self._http.request(
            "POST",
            "/licenses/validate",
            json_data=request_data.model_dump(exclude_none=True),
        )
        return LicenseValidation(**response)

    async def revoke(
        self,
        license_id: str,
        reason: str,
    ) -> bool:
        """
        Revoke a license.

        Marks the license as revoked. The revocation takes effect on the next
        phone-home validation from the self-hosted installation.

        Args:
            license_id: License identifier
            reason: Reason for revocation

        Returns:
            bool: True if revocation successful

        Raises:
            NotFoundError: If license not found

        Example:
            >>> revoked = await client.revenue.licenses.revoke(
            ...     license_id="lic_123",
            ...     reason="Customer churned"
            ... )
            >>> if revoked:
            ...     print("License revoked successfully")
        """
        response = await self._http.request(
            "POST",
            f"/licenses/{encode_path_param(license_id)}/revoke",
            json_data={"reason": reason},
        )
        return response.get("revoked", False)

    async def get_usage(self, license_id: str) -> LicenseUsage:
        """
        Get usage telemetry for a license.

        Returns historical validation records and usage data.

        Args:
            license_id: License identifier

        Returns:
            LicenseUsage: Usage telemetry data

        Example:
            >>> usage = await client.revenue.licenses.get_usage("lic_123")
            >>> print(f"Total validations: {usage.total_validations}")
            >>> for v in usage.validations[-5:]:
            ...     print(f"  {v['timestamp']}: {v['machine_id']}")
        """
        response = await self._http.request(
            "GET",
            f"/licenses/{encode_path_param(license_id)}/usage",
        )
        return LicenseUsage(**response)

    async def get_status(self) -> LicenseStatus:
        """
        Get the current license status for this installation.

        Performs a local validation (optionally with phone-home).

        Returns:
            LicenseStatus: Current license status and entitlements

        Example:
            >>> status = await client.revenue.licenses.get_status()
            >>> if status.valid:
            ...     print(f"License: {status.license_id}")
            ...     print(f"Edition: {status.edition}")
            ...     print(f"Days remaining: {status.days_remaining}")
            ... elif status.grace_period_active:
            ...     print(f"Grace period active: {status.grace_period_days_remaining} days left")
            ... else:
            ...     print(f"License invalid: {status.error}")
        """
        response = await self._http.request(
            "GET",
            "/licenses/status",
        )
        return LicenseStatus(**response)

    async def list_editions(self) -> dict[str, Edition]:
        """
        Get available license editions and their features.

        Returns:
            Dict[str, Edition]: Edition information with features and limits

        Example:
            >>> editions = await client.revenue.licenses.list_editions()
            >>> for name, edition in editions.items():
            ...     print(f"{name}:")
            ...     for feature in edition.features:
            ...         print(f"  - {feature}")
        """
        response = await self._http.request(
            "GET",
            "/licenses/editions",
        )
        editions_data = response.get("editions", {})
        return {name: Edition(name=name, **data) for name, data in editions_data.items()}
