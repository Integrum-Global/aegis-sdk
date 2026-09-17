"""
Analytics Module for Agentic OS SDK.

Provides analytics operations for metrics, costs, performance tracking, and export.

Analytics are served under ``/api/v1/analytics``. Every response model
below is defined locally in this module rather than imported from
``aegis_sdk.types``, and matches the wire shape directly — no normalization
step is needed here.

15 methods:
- :meth:`~AnalyticsModule.overview` — dashboard overview metrics
- :meth:`~AnalyticsModule.tasks` — task metrics with time-series data
- :meth:`~AnalyticsModule.agent_performance` — agent performance analysis
- :meth:`~AnalyticsModule.pool_utilization` — pool utilization metrics
- :meth:`~AnalyticsModule.costs` — cost summary
- :meth:`~AnalyticsModule.cost_breakdown` — cost breakdown by dimension
- :meth:`~AnalyticsModule.export_costs` — export cost data (JSON, CSV or XLSX)
- :meth:`~AnalyticsModule.export_metrics` — export metrics data (JSON, CSV or XLSX)
- :meth:`~AnalyticsModule.list_agents` — analytics-tracked agents list
- :meth:`~AnalyticsModule.trends` — completion-rate trends

Five further methods — :meth:`~AnalyticsModule.workspace_metrics`,
:meth:`~AnalyticsModule.team_metrics`, :meth:`~AnalyticsModule.usage_history`,
:meth:`~AnalyticsModule.usage_breakdown` and
:meth:`~AnalyticsModule.top_agents` — address routes the API does not
currently serve and return 404. Each carries a warning in its own docstring.
"""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


# Response Models
class OverviewMetrics(TolerantModel):
    """Dashboard overview metrics.

    Verified against ``OverviewResponse``.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_requests: int = Field(alias="totalRequests")
    completed_requests: int = Field(alias="completedRequests")
    in_progress_requests: int = Field(alias="inProgressRequests")
    pending_requests: int = Field(alias="pendingRequests")
    escalated_requests: int = Field(alias="escalatedRequests")
    active_sessions: int = Field(alias="activeSessions")
    active_pools: int = Field(alias="activePools")
    completion_rate: float = Field(alias="completionRate")
    escalation_rate: float = Field(alias="escalationRate")
    total_cost_cents: int = Field(alias="totalCostCents")
    total_cost_usd: float = Field(alias="totalCostUsd")
    total_tokens: int = Field(alias="totalTokens")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")


class TaskMetricsItem(TolerantModel):
    """Time-series task metrics item.

    Verified against ``TaskMetricsItem``.
    """

    model_config = ConfigDict(populate_by_name=True)

    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    period_type: str = Field(alias="periodType")
    total_tasks: int = Field(alias="totalTasks")
    completed_tasks: int = Field(alias="completedTasks")
    cancelled_tasks: int = Field(alias="cancelledTasks")
    escalated_tasks: int = Field(alias="escalatedTasks")
    avg_completion_time_seconds: float = Field(alias="avgCompletionTimeSeconds")
    median_completion_time_seconds: float = Field(alias="medianCompletionTimeSeconds")


class AgentPerformance(TolerantModel):
    """Agent performance metrics.

    Verified against ``AgentPerformanceResponse`` — there is no ``agentName`` field on the wire
    (``agent_name`` is Optional here for backward compatibility, always
    ``None`` in practice); cost is two separate fields
    (``total_cost_cents``/``total_cost_usd``), not a unified ``cost``.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    agent_name: str | None = Field(default=None, alias="agentName")
    organization_id: str = Field(alias="organizationId")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    tasks_completed: int = Field(alias="tasksCompleted")
    tasks_failed: int = Field(alias="tasksFailed")
    total_tasks: int = Field(alias="totalTasks")
    avg_task_duration_seconds: float | None = Field(None, alias="avgTaskDurationSeconds")
    total_sessions: int = Field(alias="totalSessions")
    avg_session_duration_seconds: float | None = Field(None, alias="avgSessionDurationSeconds")
    total_cost_cents: int = Field(alias="totalCostCents")
    total_cost_usd: float = Field(alias="totalCostUsd")
    total_tokens: int = Field(alias="totalTokens")
    success_rate: float = Field(alias="successRate")


class PoolUtilization(TolerantModel):
    """Pool utilization metrics.

    Verified against ``PoolUtilizationResponse``.
    """

    model_config = ConfigDict(populate_by_name=True)

    pool_id: str = Field(alias="poolId")
    pool_name: str = Field(alias="poolName")
    organization_id: str | None = Field(default=None, alias="organizationId")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    total_tasks: int = Field(alias="totalTasks")
    avg_wait_time_seconds: float = Field(alias="avgWaitTimeSeconds")
    avg_claim_time_seconds: float = Field(alias="avgClaimTimeSeconds")
    escalation_count: int = Field(alias="escalationCount")
    escalation_rate: float = Field(alias="escalationRate")


class CostBreakdownItem(TolerantModel):
    """Single cost breakdown item.

    Verified against ``CostBreakdownItem`` — each item carries its own ``groupBy`` (the dimension it was
    grouped by), distinct from the response envelope's ``groupBy``.
    """

    model_config = ConfigDict(populate_by_name=True)

    group_id: str = Field(alias="groupId")
    group_name: str = Field(alias="groupName")
    group_by: str = Field(alias="groupBy")
    total_cost_cents: int = Field(alias="totalCostCents")
    total_cost_usd: float = Field(alias="totalCostUsd")
    total_tokens: int = Field(alias="totalTokens")
    total_sessions: int = Field(alias="totalSessions")


class CostBreakdown(TolerantModel):
    """Cost breakdown response.

    Verified against ``CostBreakdownResponse`` — the envelope key is ``records`` (the prior
    model declared ``breakdown``, which is absent on the wire and raised a
    missing-required-field error on every real response). There is no
    top-level ``totalCostCents``/``totalCostUsd`` on the wire; use
    :meth:`total_cost_cents` / :meth:`total_cost_usd` to sum the records.
    """

    model_config = ConfigDict(populate_by_name=True)

    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    group_by: str = Field(alias="groupBy")
    records: list[CostBreakdownItem]

    def total_cost_cents(self) -> int:
        """Sum ``total_cost_cents`` across all records (client-side —
        the server does not return a pre-computed grand total)."""
        return sum(item.total_cost_cents for item in self.records)

    def total_cost_usd(self) -> float:
        """Sum ``total_cost_usd`` across all records (client-side —
        the server does not return a pre-computed grand total)."""
        return sum(item.total_cost_usd for item in self.records)


class TrendItem(TolerantModel):
    """Completion rate trend item.

    Verified against ``CompletionRateTrendItem`` — fields already matched the wire shape.
    """

    model_config = ConfigDict(populate_by_name=True)

    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    total_tasks: int = Field(alias="totalTasks")
    completed_tasks: int = Field(alias="completedTasks")
    completion_rate: float = Field(alias="completionRate")


class UsageHistoryItem(TolerantModel):
    """Usage history item.

    Retained for typing only: no route currently backs
    :meth:`AnalyticsModule.usage_history` — see that method's docstring.
    """

    model_config = ConfigDict(populate_by_name=True)

    date: str
    resource_type: str = Field(alias="resourceType")
    usage: int
    limit: int


class UsageBreakdownItem(TolerantModel):
    """Usage breakdown by dimension.

    Retained for typing only: no route currently backs
    :meth:`AnalyticsModule.usage_breakdown` — see that method's docstring.
    """

    model_config = ConfigDict(populate_by_name=True)

    resource_type: str = Field(alias="resourceType")
    by_agent: dict[str, int] | None = Field(None, alias="byAgent")
    by_user: dict[str, int] | None = Field(None, alias="byUser")
    by_date: dict[str, int] | None = Field(None, alias="byDate")


class TopAgent(TolerantModel):
    """Top performing agent.

    Retained for typing only: no route currently backs
    :meth:`AnalyticsModule.top_agents` — see that method's docstring.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    executions: int
    success_rate: float = Field(alias="successRate")
    avg_latency_ms: float = Field(alias="avgLatencyMs")
    total_cost: float = Field(alias="totalCost")


class PoolMetricsItem(TolerantModel):
    """Aggregate pool-utilization list item.

    Verified against ``PoolMetricsListItem`` — the aggregate ``/pools`` list, distinct from the
    single-pool ``PoolUtilization`` (``/pools/{id}/utilization``).
    """

    model_config = ConfigDict(populate_by_name=True)

    pool_id: str = Field(alias="poolId")
    pool_name: str = Field(alias="poolName")
    utilization_rate: float = Field(alias="utilizationRate")
    avg_queue_depth: float = Field(alias="avgQueueDepth")
    avg_wait_time_minutes: float = Field(alias="avgWaitTimeMinutes")
    active_tasks: int = Field(alias="activeTasks")
    completed_tasks: int = Field(alias="completedTasks")
    member_count: int = Field(alias="memberCount")
    organization_id: str = Field(alias="organizationId")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    total_tasks: int = Field(alias="totalTasks")
    avg_wait_time_seconds: float = Field(alias="avgWaitTimeSeconds")
    escalation_count: int = Field(alias="escalationCount")
    escalation_rate: float = Field(alias="escalationRate")


class SLAMetrics(TolerantModel):
    """SLA compliance metrics.

    Verified against ``SLAMetricsResponse`` — all keys camelCase on the wire.
    """

    model_config = ConfigDict(populate_by_name=True)

    # None + measured=False when the period had zero terminal requests --
    # there is nothing to score.
    compliance_rate: float | None = Field(alias="complianceRate")
    compliance_rate_change: float = Field(alias="complianceRateChange")
    measured: bool = Field(default=True, alias="measured")
    total_tasks: int = Field(alias="totalTasks")
    on_time_tasks: int = Field(alias="onTimeTasks")
    late_tasks: int = Field(alias="lateTasks")
    avg_time_to_breach_minutes: float = Field(alias="avgTimeToBreachMinutes")
    by_pool: list[dict[str, Any]] = Field(alias="byPool")
    by_priority: list[dict[str, Any]] = Field(alias="byPriority")
    timeline: list[dict[str, Any]]
    threshold_percentage: float = Field(alias="thresholdPercentage")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")


class ReviewDecisions(TolerantModel):
    """Review-decision counts for HITL metrics.

    Verified against ``ReviewDecisions``.
    """

    model_config = ConfigDict(populate_by_name=True)

    approved: int
    rejected: int
    revision_requested: int = Field(alias="revisionRequested")


class HITLMetrics(TolerantModel):
    """Human-in-the-loop (escalation / review) metrics.

    Verified against ``HITLMetricsResponse`` — all keys camelCase on the wire; ``review_decisions`` is a
    nested object.
    """

    model_config = ConfigDict(populate_by_name=True)

    escalation_rate: float = Field(alias="escalationRate")
    escalation_rate_change: float = Field(alias="escalationRateChange")
    total_escalations: int = Field(alias="totalEscalations")
    auto_escalations: int = Field(alias="autoEscalations")
    manual_escalations: int = Field(alias="manualEscalations")
    avg_review_time_minutes: float = Field(alias="avgReviewTimeMinutes")
    avg_review_time_change: float = Field(alias="avgReviewTimeChange")
    review_decisions: ReviewDecisions = Field(alias="reviewDecisions")
    intervention_rate: float = Field(alias="interventionRate")
    intervention_rate_change: float = Field(alias="interventionRateChange")
    timeline: list[dict[str, Any]]
    decisions_timeline: list[dict[str, Any]] = Field(alias="decisionsTimeline")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")


class SummaryTasksSection(TolerantModel):
    """Tasks section of the combined analytics summary.

    Verified against ``SummaryTasksSection``.
    """

    model_config = ConfigDict(populate_by_name=True)

    total: int
    completion_rate: float = Field(alias="completionRate")
    completion_rate_change: float = Field(alias="completionRateChange")
    avg_completion_time_minutes: float = Field(alias="avgCompletionTimeMinutes")
    avg_completion_time_change: float = Field(alias="avgCompletionTimeChange")


class SummarySLASection(TolerantModel):
    """SLA section of the combined analytics summary.

    Verified against ``SummarySLASection``.
    """

    model_config = ConfigDict(populate_by_name=True)

    # See SLAMetrics.compliance_rate.
    compliance_rate: float | None = Field(alias="complianceRate")
    compliance_rate_change: float = Field(alias="complianceRateChange")
    measured: bool = Field(default=True, alias="measured")
    on_time_tasks: int = Field(alias="onTimeTasks")
    late_tasks: int = Field(alias="lateTasks")


class SummaryHITLSection(TolerantModel):
    """HITL section of the combined analytics summary.

    Verified against ``SummaryHITLSection``.
    """

    model_config = ConfigDict(populate_by_name=True)

    escalation_rate: float = Field(alias="escalationRate")
    escalation_rate_change: float = Field(alias="escalationRateChange")
    avg_review_time_minutes: float = Field(alias="avgReviewTimeMinutes")
    avg_review_time_change: float = Field(alias="avgReviewTimeChange")


class SummaryTopPerformer(TolerantModel):
    """Top-performer entry in the summary agents section.

    Verified against ``TopPerformerItem``.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    success_rate: float = Field(alias="successRate")


class SummaryAgentsSection(TolerantModel):
    """Agents section of the combined analytics summary.

    Verified against ``SummaryAgentsSection``.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_active: int = Field(alias="totalActive")
    avg_success_rate: float = Field(alias="avgSuccessRate")
    top_performer: SummaryTopPerformer | None = Field(default=None, alias="topPerformer")


class SummaryPoolsSection(TolerantModel):
    """Pools section of the combined analytics summary.

    Verified against ``SummaryPoolsSection``.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_pools: int = Field(alias="totalPools")
    avg_utilization: float = Field(alias="avgUtilization")
    avg_queue_depth: float = Field(alias="avgQueueDepth")


class AnalyticsSummary(TolerantModel):
    """Combined analytics summary for dashboard overview panels.

    Verified against ``AnalyticsSummaryResponse`` — five nested sections, no top-level scalars.
    """

    model_config = ConfigDict(populate_by_name=True)

    tasks: SummaryTasksSection
    sla: SummarySLASection
    hitl: SummaryHITLSection
    agents: SummaryAgentsSection
    pools: SummaryPoolsSection


class VerificationDistributionItem(TolerantModel):
    """Single verification-level distribution entry.

    Verified against ``VerificationDistributionItem`` — plain snake_case (no aliasing on this route).
    """

    model_config = ConfigDict(populate_by_name=True)

    level: str
    count: int
    percent: float


class VerificationGradient(TolerantModel):
    """EATP verification-level distribution statistics.

    Verified against ``VerificationGradientStatsResponse`` — ``period_start``/``period_end`` are snake_case
    on the wire (this route does NOT camelCase, unlike its siblings).
    """

    model_config = ConfigDict(populate_by_name=True)

    total: int
    distribution: list[VerificationDistributionItem]
    period_start: str
    period_end: str


class AnalyticsModule:
    """
    Analytics module for metrics and performance tracking.

    Provides methods for accessing platform analytics including metrics,
    costs, performance data, and export functionality.

    Examples:
        # Get dashboard overview
        >>> overview = await client.analytics.overview()
        >>> print(f"Completion rate: {overview.completion_rate}%")

        # Get cost breakdown by agent
        >>> costs = await client.analytics.cost_breakdown(group_by="agent")
        >>> for item in costs.records:
        ...     print(f"{item.group_name}: ${item.total_cost_usd}")

        # Export metrics (JSON, CSV or XLSX — see export_metrics docstring)
        >>> data = await client.analytics.export_metrics(format="json")
    """

    def __init__(self, http_client):
        """
        Initialize analytics module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def overview(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> OverviewMetrics:
        """
        Get dashboard overview metrics.

        Args:
            start_date: Start date (ISO format, default: 30 days ago)
            end_date: End date (ISO format, default: now)

        Returns:
            OverviewMetrics: Aggregated dashboard metrics

        Example:
            >>> overview = await client.analytics.overview(
            ...     start_date="2026-01-01",
            ...     end_date="2026-01-31"
            ... )
            >>> print(f"Total requests: {overview.total_requests}")
            >>> print(f"Completion rate: {overview.completion_rate}%")
        """
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/overview",
            params=params if params else None,
        )
        return OverviewMetrics(**response)

    async def tasks(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: Literal["hourly", "daily", "weekly", "monthly"] = "daily",
    ) -> list[TaskMetricsItem]:
        """
        Get task metrics with time-series data.

        Fixed envelope: the real ``TaskMetricsResponse`` wraps items under
        ``records``, not ``metrics``
        — the prior implementation read ``response.get("metrics", [])``,
        which always returned an empty list against the real response.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            granularity: Time granularity (hourly, daily, weekly, monthly)

        Returns:
            List[TaskMetricsItem]: Time-series task metrics

        Example:
            >>> metrics = await client.analytics.tasks(
            ...     start_date="2026-01-01",
            ...     end_date="2026-01-31",
            ...     granularity="daily"
            ... )
            >>> for m in metrics:
            ...     print(f"{m.period_start}: {m.completed_tasks}/{m.total_tasks}")
        """
        params: dict[str, Any] = {"granularity": granularity}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/tasks",
            params=params,
        )
        return [TaskMetricsItem(**item) for item in response.get("records", [])]

    async def agent_performance(
        self,
        agent_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> AgentPerformance:
        """
        Get agent performance analysis.

        Args:
            agent_id: Agent ID to analyze
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            AgentPerformance: Agent performance metrics

        Example:
            >>> perf = await client.analytics.agent_performance(
            ...     "agent-123",
            ...     start_date="2026-01-01"
            ... )
            >>> print(f"Success rate: {perf.success_rate}%")
            >>> print(f"Total cost: ${perf.total_cost_usd}")
        """
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            f"/api/v1/analytics/agents/{encode_path_param(agent_id)}/performance",
            params=params if params else None,
        )
        return AgentPerformance(**response)

    async def pool_utilization(
        self,
        pool_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> PoolUtilization:
        """
        Get pool utilization metrics.

        Args:
            pool_id: Pool ID to analyze
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            PoolUtilization: Pool utilization metrics

        Example:
            >>> util = await client.analytics.pool_utilization("pool-123")
            >>> print(f"Total tasks: {util.total_tasks}")
            >>> print(f"Escalation rate: {util.escalation_rate}%")
        """
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            f"/api/v1/analytics/pools/{encode_path_param(pool_id)}/utilization",
            params=params if params else None,
        )
        return PoolUtilization(**response)

    async def costs(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        group_by: Literal["agent", "pool", "department", "user"] = "agent",
    ) -> dict[str, Any]:
        """
        Get cost summary (raw dict — same endpoint as :meth:`cost_breakdown`,
        provided for callers who want the untyped response).

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            group_by: Grouping dimension (agent, pool, department, user)

        Returns:
            Dict with cost summary data (``{"records", "periodStart",
            "periodEnd", "groupBy"}``)
        """
        params: dict[str, Any] = {"groupBy": group_by}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self._http.request(
            "GET",
            "/api/v1/analytics/costs",
            params=params,
        )

    async def cost_breakdown(
        self,
        group_by: Literal["agent", "pool", "department", "user"] = "agent",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> CostBreakdown:
        """
        Get cost breakdown by dimension.

        Wire route: ``GET /api/v1/analytics/costs``, the SAME route :meth:`costs`
        uses. An earlier implementation hit ``/analytics/costs/breakdown``; that
        path now exists on the server but serves a DIFFERENT shape (a token-type
        cost breakdown with budget), not this grouped breakdown.

        ``group_by`` is exactly the server's ``COST_GROUP_BY_OPTIONS``; any other
        value is refused with 400. For ``pool`` and ``department`` the server
        currently places every session in a single ``unknown`` group.

        Args:
            group_by: Grouping dimension (agent, pool, department, user)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            CostBreakdown: Cost breakdown by selected dimension

        Example:
            >>> costs = await client.analytics.cost_breakdown(group_by="agent")
            >>> for item in costs.records:
            ...     print(f"{item.group_name}: ${item.total_cost_usd}")
        """
        params: dict[str, Any] = {"groupBy": group_by}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/costs",
            params=params,
        )
        return CostBreakdown(**response)

    async def export_costs(
        self,
        format: Literal["json", "csv", "xlsx"] = "json",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any] | bytes:
        """
        Export cost-only analytics data.

        Fixed wire route: the prior implementation hit
        ``/analytics/costs/export``, which does not exist — the real (and
        only) export endpoint is the unified ``GET /api/v1/analytics/export``, which this maps to a
        cost-only export via ``includeCosts=true`` and the other
        ``include*`` flags set to false.

        A binary ``format`` (``csv``/``xlsx``) is fetched with
        ``raw_response=True``, which short-circuits the transport's
        ``.json()`` before it is attempted. That parameter is the SDK's
        shipped raw-bytes path and is already used by
        ``compliance.export_report``, ``export_audit`` and
        ``export_soc2_evidence``; this method now uses it too.

        ⛔ This method previously raised ``UnsupportedOperationError`` for
        ``csv``/``xlsx`` on the stated ground that ``_handle_response``
        "unconditionally calls ``response.json()`` ... it has no raw-bytes
        return path". **That premise is false** and the guard is removed
        rather than re-documented: ``_http.py`` returns ``response.content``
        for any 200/201/202 fetched with ``raw_response=True`` (line 515) AND
        for any 200/201/202 whose body fails to parse (line 519-521), and the
        ``raw_response`` parameter's own docstring records that it exists
        precisely because two shipped methods were passing it. The guard was
        a written claim that outlived its mechanism, and it blocked a
        capability the transport could already serve. Adding a format to this
        surface MUST NOT be re-gated on that sentence.

        Args:
            format: ``"json"`` returns the parsed export document; ``"csv"``
                and ``"xlsx"`` return the raw export bytes (the xlsx body is
                a real OOXML workbook, not text).
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            The exported cost data — a parsed ``dict`` for ``format="json"``,
            raw ``bytes`` for ``csv``/``xlsx``.
        """
        params: dict[str, Any] = {
            "format": format,
            "includeCosts": True,
            "includeTasks": False,
            "includeAgents": False,
            "includePools": False,
        }
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self._http.request(
            "GET",
            "/api/v1/analytics/export",
            params=params,
            raw_response=format != "json",
        )

    async def export_metrics(
        self,
        format: Literal["json", "csv", "xlsx"] = "json",
        metrics: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any] | bytes:
        """
        Export metrics data.

        Fixed wire route: the prior implementation hit
        ``/analytics/metrics/export``, which does not exist — the real (and
        only) export endpoint is the unified ``GET /api/v1/analytics/export``. ``metrics`` (a list of
        ``executions``/``costs``/``agents``/``pools``) is translated into
        the server's ``include*`` boolean flags; when omitted, everything is
        included (matching the server's own defaults).

        ``format`` accepts the same three values as :meth:`export_costs`, and
        for the same reason — the transport has a raw-bytes path, so the
        former ``UnsupportedOperationError`` guard rested on a false premise.
        See that method for the full account.

        Args:
            format: ``"json"`` returns the parsed export document; ``"csv"``
                and ``"xlsx"`` return the raw export bytes.
            metrics: Categories to include — any of ``executions``
                (maps to ``includeTasks``), ``costs`` (``includeCosts``),
                ``agents`` (``includeAgents``), ``pools`` (``includePools``).
                All are included when omitted.
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            The exported metrics data — a parsed ``dict`` for
            ``format="json"``, raw ``bytes`` for ``csv``/``xlsx``.

        Example:
            >>> data = await client.analytics.export_metrics(
            ...     format="json",
            ...     metrics=["executions", "costs"]
            ... )
            >>> workbook: bytes = await client.analytics.export_metrics(
            ...     format="xlsx"
            ... )
        """
        include_all = metrics is None
        metrics_set = set(metrics or [])
        params: dict[str, Any] = {
            "format": format,
            "includeTasks": include_all or "executions" in metrics_set,
            "includeCosts": include_all or "costs" in metrics_set,
            "includeAgents": include_all or "agents" in metrics_set,
            "includePools": include_all or "pools" in metrics_set,
        }
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self._http.request(
            "GET",
            "/api/v1/analytics/export",
            params=params,
            raw_response=format != "json",
        )

    async def list_agents(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List agents with analytics data.

        Fixed wire route + envelope: the prior implementation sent
        ``limit``/``offset`` params (not accepted by the real endpoint) and
        read ``response.get("agents", [])`` — the real ``GET
        /api/v1/analytics/agents``
        takes only ``startDate``/``endDate`` and returns a BARE JSON array
        (``list[AgentPerformanceListItem]``), so ``.get()`` on the response
        would raise ``AttributeError`` (a list has no ``.get``).

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            List of agents with analytics summary (camelCase dicts, e.g.
            ``agentId``, ``agentName``, ``tasksDelegated``, ``successRate``)
        """
        params: dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/agents",
            params=params if params else None,
        )
        return response

    async def workspace_metrics(
        self,
        workspace_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get workspace analytics.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/analytics/workspaces/{workspace_id}`` is not
            served; analytics are not scoped by workspace today.

        Args:
            workspace_id: Workspace ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Dict with workspace metrics
        """
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self._http.request(
            "GET",
            f"/api/v1/analytics/workspaces/{encode_path_param(workspace_id)}",
            params=params if params else None,
        )

    async def team_metrics(
        self,
        team_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get team analytics.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/analytics/teams/{team_id}`` is not served;
            analytics are not scoped by team today.

        Args:
            team_id: Team ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Dict with team metrics
        """
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        return await self._http.request(
            "GET",
            f"/api/v1/analytics/teams/{encode_path_param(team_id)}",
            params=params if params else None,
        )

    async def trends(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: Literal["hourly", "daily", "weekly", "monthly"] = "daily",
    ) -> list[TrendItem]:
        """
        Get completion rate trends.

        Fixed envelope: the real ``CompletionRateTrendResponse`` wraps items
        under ``records``, not
        ``trends`` — the prior implementation read
        ``response.get("trends", [])``, which always returned an empty list.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            granularity: Time granularity

        Returns:
            List[TrendItem]: Trend data points

        Example:
            >>> trends = await client.analytics.trends(granularity="weekly")
            >>> for t in trends:
            ...     print(f"{t.period_start}: {t.completion_rate}%")
        """
        params: dict[str, Any] = {"granularity": granularity}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/trends/completion-rate",
            params=params,
        )
        return [TrendItem(**item) for item in response.get("records", [])]

    async def usage_history(
        self,
        start_date: str,
        end_date: str,
        resource_type: str | None = None,
    ) -> list[UsageHistoryItem]:
        """
        Get historical usage data.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/analytics/usage/history`` is not served; there are
            no ``/usage/*`` routes. For cost-shaped usage over a period, use
            :meth:`costs` or :meth:`cost_breakdown`.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            resource_type: Filter by resource type (optional)

        Returns:
            List[UsageHistoryItem]: Historical usage records
        """
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
        }
        if resource_type:
            params["resource_type"] = resource_type

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/usage/history",
            params=params,
        )
        return [UsageHistoryItem(**item) for item in response.get("history", [])]

    async def usage_breakdown(
        self,
        resource_type: str,
        dimension: Literal["agent", "user", "date"] = "agent",
    ) -> UsageBreakdownItem:
        """
        Get usage breakdown by dimension.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/analytics/usage/breakdown`` is not served — see
            :meth:`usage_history`. Use :meth:`cost_breakdown` for a
            dimensioned view of spend.

        Args:
            resource_type: Resource type to analyze
            dimension: Breakdown dimension (agent, user, date)

        Returns:
            UsageBreakdownItem: Usage breakdown data
        """
        response = await self._http.request(
            "GET",
            "/api/v1/analytics/usage/breakdown",
            params={
                "resource_type": resource_type,
                "dimension": dimension,
            },
        )
        return UsageBreakdownItem(**response)

    async def top_agents(
        self,
        limit: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[TopAgent]:
        """
        Get top performing agents.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/analytics/top-agents`` is not served.
            :meth:`list_agents` returns every agent's performance data
            unsorted and with a different field set (no ``executions``,
            ``avg_latency_ms`` or unified ``total_cost``), so it is not a
            drop-in substitute — but it plus client-side sorting gives an
            equivalent view today.

        Args:
            limit: Number of agents to return (default: 10)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            List[TopAgent]: Top performing agents
        """
        params: dict[str, Any] = {"limit": limit}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/top-agents",
            params=params,
        )
        return [TopAgent(**agent) for agent in response.get("agents", [])]

    async def pools(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[PoolMetricsItem]:
        """
        Get utilization metrics aggregated across all pools (AI operations page).

        GET /api/v1/analytics/pools —
        returns a BARE JSON array (``list[PoolMetricsListItem]``), distinct
        from :meth:`pool_utilization` which is single-pool.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            list[PoolMetricsItem]: Per-pool utilization records
        """
        params: dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/pools",
            params=params if params else None,
        )
        return [PoolMetricsItem(**item) for item in response]

    async def sla(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> SLAMetrics:
        """
        Get SLA compliance metrics for the analytics dashboard.

        GET /api/v1/analytics/sla.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            SLAMetrics: Compliance rate, on-time/late counts, breakdowns,
            timeline
        """
        params: dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/sla",
            params=params if params else None,
        )
        return SLAMetrics(**response)

    async def hitl(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> HITLMetrics:
        """
        Get human-in-the-loop (escalation / review) metrics.

        GET /api/v1/analytics/hitl.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            HITLMetrics: Escalation rate, review times, review-decision
            distribution, timelines
        """
        params: dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/hitl",
            params=params if params else None,
        )
        return HITLMetrics(**response)

    async def summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> AnalyticsSummary:
        """
        Get a combined analytics summary for dashboard overview panels.

        GET /api/v1/analytics/summary — aggregates tasks / SLA / HITL / agents / pools into one
        response to minimise round-trips.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            AnalyticsSummary: Five nested summary sections
        """
        params: dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/summary",
            params=params if params else None,
        )
        return AnalyticsSummary(**response)

    async def verification_gradient(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> VerificationGradient:
        """
        Get EATP verification-level distribution (trust VerificationGradientPage).

        GET /api/v1/analytics/verification-gradient — distribution across the four EATP levels
        (auto_approved / flagged / held / blocked). Returns zeroed
        distribution (not 404) for new organizations.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            VerificationGradient: total + per-level distribution
        """
        params: dict[str, Any] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/analytics/verification-gradient",
            params=params if params else None,
        )
        return VerificationGradient(**response)
