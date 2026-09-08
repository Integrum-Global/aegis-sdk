"""
Usage Module for Agentic OS SDK.

Provides usage tracking operations for monitoring resource consumption
against quotas.

3 methods:
- get_current() - Get current usage against quotas
- get_history() - Get historical usage (requires Analytics module)
- get_breakdown() - Get usage breakdown by dimension (requires Analytics module)
"""

from ..exceptions import NotFoundError
from ..types import (
    ResourceType,
    ResourceUsage,
    Usage,
    UsageBreakdown,
    UsageHistory,
)


class UsageModule:
    """
    Usage tracking module.

    Provides methods for monitoring resource consumption against quotas.

    Examples:
        # Get current usage
        >>> usage = await client.revenue.usage.get_current()
        >>> print(f"Agent executions: {usage.agent_execution.current}/{usage.agent_execution.limit}")
        >>> print(f"Tokens used: {usage.token.current}/{usage.token.limit}")

        # Check if approaching limits
        >>> if usage.agent_execution.current > usage.agent_execution.limit * 0.8:
        ...     print("Warning: Approaching agent execution limit")
    """

    def __init__(self, http_client):
        """
        Initialize usage module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def get_current(self) -> Usage:
        """
        Get current usage against quotas.

        Returns usage for all resource types tracked by the billing system.

        Returns:
            Usage: Current usage for all resource types

        Raises:
            AuthenticationError: If not authenticated

        Example:
            >>> usage = await client.revenue.usage.get_current()
            >>> print(f"Agent executions: {usage.agent_execution.current}/{usage.agent_execution.limit}")
            >>> print(f"Tokens: {usage.token.current}/{usage.token.limit}")
            >>> print(f"Storage: {usage.storage.current}/{usage.storage.limit} GB")
            >>> print(f"API calls: {usage.api_call.current}/{usage.api_call.limit}")

            >>> # Check remaining capacity
            >>> remaining = usage.agent_execution.limit - usage.agent_execution.current
            >>> print(f"Remaining executions: {remaining}")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/subscriptions/usage",
        )

        # Convert response to Usage model with ResourceUsage for each type
        def make_resource_usage(data: dict, unit: str) -> ResourceUsage:
            limit = data.get("limit", 0)
            current = data.get("current", 0)
            return ResourceUsage(
                limit=limit,
                current=current,
                unit=unit,
                remaining=max(0, limit - current) if limit > 0 else None,
                unlimited=limit <= 0 or limit == -1,
            )

        return Usage(
            agent_execution=make_resource_usage(response.get("agent_execution", {}), "count"),
            token=make_resource_usage(response.get("token", {}), "1000 tokens"),
            storage=make_resource_usage(response.get("storage", {}), "GB"),
            api_call=make_resource_usage(response.get("api_call", {}), "count"),
        )

    async def get_history(
        self,
        start_date: str,
        end_date: str,
        resource_type: str | None = None,
    ) -> list[UsageHistory]:
        """
        Get historical usage data.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            resource_type: Filter by resource type (optional)

        Returns:
            List[UsageHistory]: Historical usage records

        Example:
            >>> history = await client.revenue.usage.get_history(
            ...     start_date="2024-01-01",
            ...     end_date="2024-01-31",
            ...     resource_type="agent_execution"
            ... )
            >>> for record in history:
            ...     print(f"{record.date}: {record.usage}/{record.limit}")
        """
        params = {
            "start_date": start_date,
            "end_date": end_date,
        }
        if resource_type:
            params["resource_type"] = resource_type

        try:
            response = await self._http.request(
                "GET",
                "/api/v1/analytics/usage/history",
                params=params,
            )
            return [UsageHistory(**h) for h in response.get("history", [])]
        except NotFoundError:
            # Analytics endpoint not yet deployed — return empty history
            return []

    async def get_breakdown(
        self,
        resource_type: str,
        dimension: str = "agent",
    ) -> UsageBreakdown:
        """
        Get usage breakdown by dimension.

        Args:
            resource_type: Resource type to analyze
            dimension: Breakdown dimension ("agent", "user", "date")

        Returns:
            UsageBreakdown: Usage breakdown by dimension

        Example:
            >>> breakdown = await client.revenue.usage.get_breakdown(
            ...     resource_type="agent_execution",
            ...     dimension="agent"
            ... )
            >>> for agent_id, count in breakdown.by_agent.items():
            ...     print(f"Agent {agent_id}: {count} executions")
        """
        try:
            response = await self._http.request(
                "GET",
                "/api/v1/analytics/usage/breakdown",
                params={
                    "resource_type": resource_type,
                    "dimension": dimension,
                },
            )
            return UsageBreakdown(
                resource_type=ResourceType(resource_type),
                by_agent=response.get("by_agent"),
                by_user=response.get("by_user"),
                by_date=response.get("by_date"),
            )
        except NotFoundError:
            # Analytics endpoint not yet deployed — return empty breakdown
            return UsageBreakdown(
                resource_type=ResourceType(resource_type),
            )
