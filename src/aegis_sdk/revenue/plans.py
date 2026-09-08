"""
Plans Module for Agentic OS SDK.

Provides plan information including listing available plans, getting
features for specific tiers, and comparing plans.

3 methods:
- list() - List all available plans
- get_features() - Get features for a specific tier
- compare_tiers() - Compare two plan tiers
"""

from ..exceptions import NotFoundError, ValidationError
from ..types import (
    Plan,
    PlanFeatures,
    PlanTier,
    TierComparison,
)


class PlansModule:
    """
    Plan information module.

    Provides methods for listing available subscription plans and
    comparing features across tiers.

    Examples:
        # List all plans
        >>> plans = await client.revenue.plans.list()
        >>> for plan in plans:
        ...     print(f"{plan.name}: ${plan.monthly_price / 100}/month")

        # Get features for a tier
        >>> features = await client.revenue.plans.get_features("professional")
        >>> print(features.features)

        # Compare tiers
        >>> comparison = await client.revenue.plans.compare_tiers("starter", "professional")
        >>> print(f"Additional features: {comparison.additional_in_tier2}")
    """

    def __init__(self, http_client):
        """
        Initialize plans module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client
        # Cache for plans to enable client-side operations
        self._plans_cache: list[Plan] | None = None

    async def list(self) -> list[Plan]:
        """
        List all available subscription plans.

        Returns all available subscription tiers with pricing and features.
        This endpoint does not require authentication.

        Returns:
            List[Plan]: Available subscription plans

        Example:
            >>> plans = await client.revenue.plans.list()
            >>> for plan in plans:
            ...     if not plan.contact_sales:
            ...         print(f"{plan.name}: ${plan.monthly_price / 100}/month")
            ...     else:
            ...         print(f"{plan.name}: Contact sales")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/subscriptions/plans",
        )
        plans = [Plan(**p) for p in response.get("plans", [])]
        # Cache for client-side operations
        self._plans_cache = plans
        return plans

    async def get_features(self, tier: str) -> PlanFeatures:
        """
        Get features for a specific plan tier.

        Args:
            tier: Plan tier ("free", "starter", "professional", "enterprise")

        Returns:
            PlanFeatures: Features included in the tier

        Raises:
            ValidationError: If tier is invalid
            NotFoundError: If tier not found

        Example:
            >>> features = await client.revenue.plans.get_features("professional")
            >>> for feature in features.features:
            ...     print(f"- {feature}")
        """
        # Ensure plans are loaded
        if self._plans_cache is None:
            await self.list()

        # Find the tier in cached plans
        try:
            tier_enum = PlanTier(tier)
        except ValueError:
            raise ValidationError(f"Invalid plan tier: {tier}")
        for plan in self._plans_cache or []:
            if plan.tier == tier_enum:
                return PlanFeatures(features=plan.features)

        # Fallback: Make API request for features
        response = await self._http.request(
            "GET",
            "/api/v1/features/tiers",
            params={"tier": tier},
        )
        return PlanFeatures(**response)

    async def compare_tiers(self, tier1: str, tier2: str) -> TierComparison:
        """
        Compare two plan tiers.

        Returns a comparison showing features in each tier and the
        additional features gained by upgrading.

        Args:
            tier1: First tier to compare
            tier2: Second tier to compare

        Returns:
            TierComparison: Comparison of the two tiers

        Example:
            >>> comparison = await client.revenue.plans.compare_tiers(
            ...     "starter", "professional"
            ... )
            >>> print(f"Upgrading from {comparison.tier1} to {comparison.tier2}")
            >>> print(f"Additional features: {comparison.additional_in_tier2}")
            >>> print(f"Price increase: ${comparison.price_difference_monthly / 100}/month")
        """
        # Ensure plans are loaded
        if self._plans_cache is None:
            await self.list()

        try:
            tier1_enum = PlanTier(tier1)
        except ValueError:
            raise ValidationError(f"Invalid plan tier: {tier1}")
        try:
            tier2_enum = PlanTier(tier2)
        except ValueError:
            raise ValidationError(f"Invalid plan tier: {tier2}")

        plan1 = None
        plan2 = None

        for plan in self._plans_cache or []:
            if plan.tier == tier1_enum:
                plan1 = plan
            if plan.tier == tier2_enum:
                plan2 = plan

        if plan1 is None or plan2 is None:
            # Fallback: reload plans
            await self.list()
            for plan in self._plans_cache or []:
                if plan.tier == tier1_enum:
                    plan1 = plan
                if plan.tier == tier2_enum:
                    plan2 = plan

        # Raise error if plans not found after reload
        if plan1 is None:
            raise NotFoundError(f"Plan tier not found: {tier1}")
        if plan2 is None:
            raise NotFoundError(f"Plan tier not found: {tier2}")

        tier1_features = plan1.features
        tier1_price = plan1.monthly_price
        tier2_features = plan2.features
        tier2_price = plan2.monthly_price

        # Calculate additional features in tier2
        additional = [f for f in tier2_features if f not in tier1_features]

        return TierComparison(
            tier1=tier1_enum,
            tier2=tier2_enum,
            tier1_features=tier1_features,
            tier2_features=tier2_features,
            additional_in_tier2=additional,
            tier1_price_monthly=tier1_price,
            tier2_price_monthly=tier2_price,
            price_difference_monthly=tier2_price - tier1_price,
        )
