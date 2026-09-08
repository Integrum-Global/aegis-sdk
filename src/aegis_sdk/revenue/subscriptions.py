"""
Subscriptions Module for Agentic OS SDK.

Provides subscription management operations including create, upgrade,
cancel, reactivate, and Stripe portal access.

6 methods:
- get() - Get current subscription
- subscribe() - Create new subscription
- upgrade() - Upgrade/downgrade subscription
- cancel() - Cancel subscription
- reactivate() - Reactivate cancelled subscription
- create_portal_session() - Get Stripe customer portal URL
"""

from ..types import (
    BillingCycle,
    CancelRequest,
    PortalSession,
    SubscribeRequest,
    Subscription,
    UpgradeRequest,
)


class SubscriptionsModule:
    """
    Subscription management module.

    Provides methods for managing organization subscriptions including
    creation, upgrades, cancellation, and Stripe portal access.

    Examples:
        # Get current subscription
        >>> subscription = await client.revenue.subscriptions.get()
        >>> print(f"Plan: {subscription.plan_tier}")

        # Subscribe to a plan
        >>> subscription = await client.revenue.subscriptions.subscribe(
        ...     plan_id="professional",
        ...     billing_cycle="monthly",
        ...     payment_method_id="pm_card_visa"
        ... )

        # Upgrade to a higher tier
        >>> upgraded = await client.revenue.subscriptions.upgrade(
        ...     new_plan_id="enterprise",
        ...     prorate=True
        ... )

        # Cancel subscription
        >>> cancelled = await client.revenue.subscriptions.cancel(at_period_end=True)

        # Access Stripe portal
        >>> portal = await client.revenue.subscriptions.create_portal_session()
        >>> print(f"Manage billing at: {portal.url}")
    """

    def __init__(self, http_client):
        """
        Initialize subscriptions module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def get(self) -> Subscription:
        """
        Get the organization's current subscription.

        Returns the active subscription for the authenticated user's organization.
        Raises NotFoundError if no active subscription exists.

        Returns:
            Subscription: Current subscription details

        Raises:
            NotFoundError: If no active subscription found
            AuthenticationError: If not authenticated

        Example:
            >>> subscription = await client.revenue.subscriptions.get()
            >>> print(f"Plan: {subscription.plan_tier}")
            >>> print(f"Status: {subscription.status}")
            >>> print(f"Renews: {subscription.current_period_end}")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/subscriptions/current",
        )
        return Subscription(**response)

    async def subscribe(
        self,
        plan_id: str,
        billing_cycle: str,
        payment_method_id: str | None = None,
    ) -> Subscription:
        """
        Create a new subscription.

        Creates a Stripe subscription for the organization. Requires a valid
        payment method from Stripe.

        Args:
            plan_id: Plan tier ("starter", "professional", "enterprise")
            billing_cycle: Billing frequency ("monthly", "annual")
            payment_method_id: Stripe payment method ID (optional if default set)

        Returns:
            Subscription: Created subscription details

        Raises:
            ValidationError: If plan_id or billing_cycle invalid
            PaymentError: If payment method fails
            AuthenticationError: If not authenticated

        Example:
            >>> subscription = await client.revenue.subscriptions.subscribe(
            ...     plan_id="starter",
            ...     billing_cycle="monthly",
            ...     payment_method_id="pm_card_visa"
            ... )
            >>> assert subscription.status == "active"
            >>> print(f"Subscribed to {subscription.plan_tier}")
        """
        request_data = SubscribeRequest(
            plan_id=plan_id,
            billing_cycle=BillingCycle(billing_cycle),
            payment_method_id=payment_method_id,
        )
        response = await self._http.request(
            "POST",
            "/api/v1/subscriptions/subscribe",
            json_data=request_data.model_dump(exclude_none=True),
        )
        return Subscription(**response)

    async def upgrade(
        self,
        new_plan_id: str,
        prorate: bool = True,
    ) -> Subscription:
        """
        Upgrade or downgrade the subscription.

        Changes the subscription plan tier. By default, charges are prorated.

        Args:
            new_plan_id: New plan tier ("starter", "professional", "enterprise")
            prorate: Whether to prorate charges (default True)

        Returns:
            Subscription: Updated subscription details

        Raises:
            ValidationError: If new_plan_id invalid
            NotFoundError: If no active subscription
            PaymentError: If payment fails
            AuthenticationError: If not authenticated

        Example:
            >>> upgraded = await client.revenue.subscriptions.upgrade(
            ...     new_plan_id="professional",
            ...     prorate=True
            ... )
            >>> assert upgraded.plan_tier == "professional"
        """
        request_data = UpgradeRequest(
            new_plan_id=new_plan_id,
            prorate=prorate,
        )
        response = await self._http.request(
            "PUT",
            "/api/v1/subscriptions/upgrade",
            json_data=request_data.model_dump(),
        )
        return Subscription(**response)

    async def cancel(
        self,
        at_period_end: bool = True,
    ) -> Subscription:
        """
        Cancel the subscription.

        Cancels the active subscription. By default, cancellation takes effect
        at the end of the current billing period to allow continued access.

        Args:
            at_period_end: Cancel at period end (True) or immediately (False)

        Returns:
            Subscription: Updated subscription with cancellation status

        Raises:
            NotFoundError: If no active subscription
            AuthenticationError: If not authenticated

        Example:
            >>> # Cancel at end of billing period (recommended)
            >>> cancelled = await client.revenue.subscriptions.cancel(at_period_end=True)
            >>> assert cancelled.cancel_at_period_end == True

            >>> # Cancel immediately (no refund)
            >>> cancelled = await client.revenue.subscriptions.cancel(at_period_end=False)
            >>> assert cancelled.status == "canceled"
        """
        request_data = CancelRequest(at_period_end=at_period_end)
        response = await self._http.request(
            "POST",
            "/api/v1/subscriptions/cancel",
            json_data=request_data.model_dump(),
        )
        return Subscription(**response)

    async def reactivate(self) -> Subscription:
        """
        Reactivate a cancelled subscription.

        Removes the scheduled cancellation, allowing the subscription to continue.
        Only works if subscription is scheduled for cancellation (not already canceled).

        Returns:
            Subscription: Reactivated subscription details

        Raises:
            NotFoundError: If no subscription found
            ValidationError: If subscription not scheduled for cancellation
            AuthenticationError: If not authenticated

        Example:
            >>> # Reactivate before cancellation takes effect
            >>> reactivated = await client.revenue.subscriptions.reactivate()
            >>> assert reactivated.cancel_at_period_end == False
            >>> assert reactivated.status == "active"
        """
        response = await self._http.request(
            "POST",
            "/api/v1/subscriptions/reactivate",
        )
        return Subscription(**response)

    async def create_portal_session(self) -> PortalSession:
        """
        Create a Stripe customer portal session.

        Returns a URL to the Stripe customer portal where users can manage
        their subscription, payment methods, and view billing history.

        Returns:
            PortalSession: Portal session with URL

        Raises:
            NotFoundError: If no Stripe customer exists
            AuthenticationError: If not authenticated

        Example:
            >>> portal = await client.revenue.subscriptions.create_portal_session()
            >>> print(f"Manage billing at: {portal.url}")
            >>> # Redirect user to portal.url
        """
        response = await self._http.request(
            "POST",
            "/api/v1/subscriptions/portal",
        )
        return PortalSession(**response)
