"""
Features Module for Agentic OS SDK.

Provides feature-gate / entitlement checks: whether the current organization's
plan tier grants access to a named feature (SSO, custom_agents, etc.).

1 method:
- check() - Check if the organization has access to a feature
"""


from .._tolerant import TolerantModel


class FeatureCheck(TolerantModel):
    """Result of a feature-gate check.

    Mirrors the wire shape emitted by ``GET /api/v1/features/check``
    (53-69 → FeatureGateService.check_feature). All fields snake_case.

    ``reason`` and ``required_tier`` are only present when ``allowed`` is False.
    """

    allowed: bool
    tier: str
    reason: str | None = None
    required_tier: str | None = None


class FeaturesModule:
    """
    Feature-gate / entitlement module.

    Provides a method to check whether the organization's plan tier grants
    access to a named feature before rendering gated UI or invoking a
    tier-restricted capability.

    Examples:
        # Gate an SSO settings page
        >>> check = await client.revenue.features.check("sso")
        >>> if check.allowed:
        ...     # render SSO configuration
        ...     pass
        ... else:
        ...     print(f"SSO requires the {check.required_tier} plan")
    """

    def __init__(self, http_client):
        """
        Initialize features module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def check(self, feature: str) -> FeatureCheck:
        """
        Check if the current organization has access to a feature.

        Backend: ``GET /api/v1/features/check?feature=<feature>``.

        Args:
            feature: Feature name to check (e.g. "sso", "custom_agents")

        Returns:
            FeatureCheck: allowed flag, current tier, and — when denied —
            the reason and the required tier.

        Raises:
            ValidationError: If the feature name is unknown (backend 400)
            AuthenticationError: If not authenticated

        Example:
            >>> check = await client.revenue.features.check("custom_agents")
            >>> if not check.allowed:
            ...     print(f"Upgrade to {check.required_tier}: {check.reason}")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/features/check",
            params={"feature": feature},
        )

        return FeatureCheck(
            allowed=response.get("allowed", False),
            tier=response.get("tier", ""),
            reason=response.get("reason"),
            required_tier=response.get("required_tier"),
        )
