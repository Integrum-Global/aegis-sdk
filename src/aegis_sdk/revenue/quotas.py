"""
Quotas Module for Agentic OS SDK.

Provides quota management operations for checking and updating resource limits.

3 methods:
- get() - Get all quotas for the organization
- update() - Update quota for a resource (admin only)
- check_limit() - Check if an action would exceed quota
"""

from ..types import (
    Quota,
    QuotaCheck,
    QuotaUpdate,
    ResourceType,
)


class QuotasModule:
    """
    Quota management module.

    Provides methods for checking and managing resource quotas.

    Examples:
        # Get all quotas
        >>> quotas = await client.revenue.quotas.get()
        >>> for quota in quotas:
        ...     print(f"{quota.resource_type}: {quota.current}/{quota.limit}")

        # Check if action would exceed quota
        >>> check = await client.revenue.quotas.check_limit("agents", amount=1)
        >>> if check.allowed:
        ...     # Proceed with agent creation
        ...     pass
        ... else:
        ...     print(f"Would exceed limit: {check.current}/{check.limit}")

        # Update quota (admin only)
        >>> await client.revenue.quotas.update("agents", new_limit=20)
    """

    def __init__(self, http_client):
        """
        Initialize quotas module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client
        # Cache for quotas to enable client-side limit checking
        self._quotas_cache: list[Quota] | None = None

    async def get(self) -> list[Quota]:
        """
        Get all quotas for the organization.

        Returns quota information for all tracked resource types.

        Returns:
            List[Quota]: All quotas for the organization

        Raises:
            AuthenticationError: If not authenticated

        Example:
            >>> quotas = await client.revenue.quotas.get()
            >>> for quota in quotas:
            ...     if quota.unlimited:
            ...         print(f"{quota.resource_type}: Unlimited")
            ...     else:
            ...         pct = (quota.current / quota.limit) * 100
            ...         print(f"{quota.resource_type}: {quota.current}/{quota.limit} ({pct:.1f}%)")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/features/limits",
        )

        # Convert response to Quota models
        quotas = []
        limits_data = response.get("limits", response)

        if isinstance(limits_data, dict):
            for resource_type, data in limits_data.items():
                # Try to map resource_type to enum
                try:
                    rt = ResourceType(resource_type)
                except ValueError:
                    # Skip unknown resource types
                    continue

                if isinstance(data, dict):
                    limit = data.get("limit", 0)
                    current = data.get("current", 0)
                    quotas.append(
                        Quota(
                            resource_type=rt,
                            limit=limit,
                            current=current,
                            remaining=max(0, limit - current) if limit > 0 else 0,
                            unlimited=limit <= 0 or limit == -1,
                        )
                    )
                elif isinstance(data, int):
                    # Simple limit value
                    quotas.append(
                        Quota(
                            resource_type=rt,
                            limit=data,
                            current=0,
                            remaining=data,
                            unlimited=data <= 0 or data == -1,
                        )
                    )

        # Cache for client-side operations
        self._quotas_cache = quotas
        return quotas

    async def update(
        self,
        resource_type: str,
        new_limit: int,
    ) -> Quota:
        """
        Update quota for a resource type.

        This is an admin-only operation typically used for custom
        quota adjustments outside normal plan limits.

        Args:
            resource_type: Resource type to update
            new_limit: New limit value (-1 for unlimited)

        Returns:
            Quota: Updated quota

        Raises:
            AuthorizationError: If not admin
            ValidationError: If resource_type invalid

        Example:
            >>> # Grant additional agent capacity
            >>> quota = await client.revenue.quotas.update(
            ...     resource_type="agents",
            ...     new_limit=20
            ... )
            >>> print(f"New limit: {quota.limit}")
        """
        rt = ResourceType(resource_type)
        request_data = QuotaUpdate(
            resource_type=rt,
            new_limit=new_limit,
        )
        response = await self._http.request(
            "POST",
            "/api/v1/billing/quotas/adjust",
            json_data=request_data.model_dump(),
        )

        # Invalidate cache after update
        self._quotas_cache = None

        return Quota(
            resource_type=rt,
            limit=response.get("limit", new_limit),
            current=response.get("current", 0),
            remaining=response.get("remaining", new_limit),
            unlimited=new_limit <= 0 or new_limit == -1,
        )

    async def check_limit(
        self,
        resource_type: str,
        amount: int = 1,
    ) -> QuotaCheck:
        """
        Check if an action would exceed quota.

        Client-side helper that checks if performing an action with the
        specified amount would exceed the current quota limit.

        Args:
            resource_type: Resource type to check
            amount: Amount of resource to consume (default 1)

        Returns:
            QuotaCheck: Check result indicating if action is allowed

        Example:
            >>> # Before creating an agent
            >>> check = await client.revenue.quotas.check_limit("agents", amount=1)
            >>> if check.allowed:
            ...     agent = await client.agents.create(name="My Agent")
            ... else:
            ...     print(f"Cannot create agent: at limit ({check.current}/{check.limit})")

            >>> # Check if batch operation is possible
            >>> check = await client.revenue.quotas.check_limit("api_call", amount=100)
            >>> if not check.allowed:
            ...     print(f"Need {amount} but only {check.remaining} remaining")
        """
        # Ensure quotas are loaded
        if self._quotas_cache is None:
            await self.get()

        rt = ResourceType(resource_type)

        # Find the quota
        quota = None
        for q in self._quotas_cache or []:
            if q.resource_type == rt:
                quota = q
                break

        if quota is None:
            # If quota not found, assume allowed (unknown resource type)
            return QuotaCheck(
                resource_type=rt,
                allowed=True,
                current=0,
                limit=0,
                remaining=0,
                amount_requested=amount,
            )

        # Check if action is allowed
        if quota.unlimited:
            allowed = True
            remaining = -1  # Unlimited
        else:
            remaining = quota.remaining
            allowed = remaining >= amount

        return QuotaCheck(
            resource_type=rt,
            allowed=allowed,
            current=quota.current,
            limit=quota.limit,
            remaining=remaining,
            amount_requested=amount,
        )
