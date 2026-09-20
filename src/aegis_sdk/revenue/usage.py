"""
Usage Module for Agentic OS SDK.

Provides usage tracking operations for monitoring resource consumption
against quotas.

3 methods:
- get_current() - Get current usage against quotas (WORKS — has a server route)
- get_history() - DEPRECATED, RETIRED — no server route. Previously swallowed the
  404 and returned an empty list, which a caller could not distinguish from a
  period with genuinely no usage. Now raises ``UnsupportedOperationError``.
- get_breakdown() - DEPRECATED, RETIRED — no server route. Previously swallowed
  the 404 and returned an empty ``UsageBreakdown``. Now raises
  ``UnsupportedOperationError``.

⛔ WHEN YOU CHANGE A METHOD'S BEHAVIOUR, SIX SURFACES DESCRIBE IT — DERIVE THE
LIST, DO NOT RECALL IT. This file is the worked case for why, and the failure
was measured on 2026-09-18 while retiring these two methods:

    body · method docstring · module docstring · tests · partner docs · handbook

Four of those six were updated by memory, and two were missed — the METHOD
docstrings (left carrying live `Example:` blocks on methods that now raise;
`help()` and every IDE tooltip render those) and the TESTS (six of them, which
kept asserting the removed behaviour and were reported green for one commit
because the summary line quoted a DIFFERENT instrument's exit code).

The list is FINITE and ENUMERABLE. Deriving it costs one pass; recalling it
costs whatever you happen not to think of, and the omission is invisible from
inside the change. Two of the six — `tests/` and the partner `handbook/` — are
in other directories from the code, which is exactly why they are the ones
recalled last.

⚠ This note lives here because this file is the example. **The durable home for
this rule is a COC artifact under `.claude/rules/`, which is a `/codify` action
and outside this lane's scope** — recorded here so it is not silently lost.

⛔ THE TWO RETIRED METHODS ARE THE ONLY PLACE IN THIS SDK WHERE AN HTTP FAILURE
WAS CONVERTED INTO A PLAUSIBLE SUCCESS. Measured 2026-09-18 across all 121 SDK
modules: of 117 ``ast.Try`` nodes, exactly TWO wrap an ``_http.request`` call —
both were here — and both returned empty on ``NotFoundError`` with no log and no
warning. Everywhere else in the SDK a route failure propagates honestly. The
sweep that established this is recorded in ``sdk_route_parity.py``'s header
under "THREE WAYS TO MISREAD A SHRINK", finding 1: the ratchet reports
"the SDK calls a missing route LOUDLY" and "the SDK calls a missing route and
HIDES the failure" in the SAME bucket, and the loud one is the harmless one.
"""

import warnings

from ..exceptions import UnsupportedOperationError
from ..types import (
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
        DEPRECATED, RETIRED — no backing server capability. Always raises.

        There is no ``/analytics/usage/history`` route on the Aegis API; the
        API exposes no ``/analytics/usage/*`` routes at all.

        ⛔ **Until 2026-09-18 this method did not fail — it LIED.** It caught
        the 404 and returned an EMPTY LIST, with no log and no warning, so a
        caller could not distinguish "this period had no usage" from "this
        endpoint does not exist". Both answers were the same ``[]``. It now
        raises, which is the only honest answer available.

        For cost-shaped usage over a period use
        :meth:`AnalyticsModule.costs` or :meth:`AnalyticsModule.cost_breakdown`.
        ⚠ Those return **cost** shapes, NOT the ``UsageHistory`` records this
        method declared — reachable, but not equivalent.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            resource_type: Filter by resource type (optional)

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "UsageModule.get_history() is deprecated and non-functional — "
            "no server route exists for historical usage (the API serves no "
            "/analytics/usage/* endpoint). This method previously swallowed "
            "the 404 and returned an EMPTY LIST, which a caller could not "
            "distinguish from a period that genuinely had no usage. For "
            "cost-shaped usage over a period, use client.analytics.costs() "
            "or client.analytics.cost_breakdown() — those return cost "
            "shapes, not the UsageHistory records this method declared. This "
            "method will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            f"get_history({start_date!r}, {end_date!r}, "
            f"resource_type={resource_type!r}) has no backing server route; "
            "there is no /analytics/usage/history endpoint on the Aegis API. "
            "For cost-shaped usage over a period, use "
            "client.analytics.costs() or client.analytics.cost_breakdown() — "
            "those return cost shapes, not the UsageHistory records this "
            "method declared."
        )

    async def get_breakdown(
        self,
        resource_type: str,
        dimension: str = "agent",
    ) -> UsageBreakdown:
        """
        DEPRECATED, RETIRED — no backing server capability. Always raises.

        There is no ``/analytics/usage/breakdown`` route on the Aegis API; the
        API exposes no ``/analytics/usage/*`` routes at all.

        ⛔ **Until 2026-09-18 this method did not fail — it LIED.** It caught
        the 404 and returned an EMPTY ``UsageBreakdown``, with no log and no
        warning, so a caller could not distinguish "no usage in this period"
        from "this endpoint does not exist". It now raises.

        For a dimensioned view of spend use
        :meth:`AnalyticsModule.cost_breakdown`. ⚠ That returns a **cost**
        shape, NOT the ``UsageBreakdown`` this method declared — reachable,
        but not equivalent.

        Args:
            resource_type: Resource type to analyze
            dimension: Breakdown dimension ("agent", "user", "date")

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "UsageModule.get_breakdown() is deprecated and non-functional — "
            "no server route exists for usage breakdown (the API serves no "
            "/analytics/usage/* endpoint). This method previously swallowed "
            "the 404 and returned an EMPTY UsageBreakdown, which a caller "
            "could not distinguish from a period with genuinely no usage. "
            "For a dimensioned view of spend, use "
            "client.analytics.cost_breakdown() — note it returns a cost "
            "shape, not the UsageBreakdown this method declared. This method "
            "will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            f"get_breakdown({resource_type!r}, dimension={dimension!r}) has "
            "no backing server route; there is no "
            "/analytics/usage/breakdown endpoint on the Aegis API. For a "
            "dimensioned view of spend, use "
            "client.analytics.cost_breakdown() — it returns a cost shape, not "
            "the UsageBreakdown this method declared."
        )
