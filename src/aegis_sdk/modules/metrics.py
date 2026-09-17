"""
Metrics Module for Agentic OS SDK.

Thin HTTP-wrapper over the backend's Metrics API
(prefix ``/api/v1/metrics``) — execution
metrics summary, time-series, raw execution list, top errors, and the
dashboard rollup.

Every route below was verified against the deployed API AND its service before implementation — path,
method, and response shape (all snake_case, no camelCase aliasing on this
router) match exactly. This module is self-contained (no imports from
client.py / modules/__init__.py / types.py); it is registered on
``AgenticOSClient`` by the client itself.

8 methods:
- dashboard()           - GET  /api/v1/metrics/dashboard              (P0)
- summary()             - GET  /api/v1/metrics/summary                (P1)
- timeseries()          - GET  /api/v1/metrics/timeseries             (P1)
- list_executions()     - GET  /api/v1/metrics/executions
- top_errors()          - GET  /api/v1/metrics/errors
- deployment_metrics()  - GET  /api/v1/metrics/deployments/{id}
- agent_metrics()       - GET  /api/v1/metrics/agents/{id}
- record_metric()       - POST /api/v1/metrics/record
"""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

# ============================================================================
# Response Models (local — mirror the server response shape )
# ============================================================================


class MetricsSummary(TolerantModel):
    """Aggregated metrics summary — avg latency, tokens, error rate, cost."""

    model_config = ConfigDict(populate_by_name=True)

    total_executions: int
    avg_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    error_rate: float
    success_count: int
    failure_count: int


class TimeseriesPoint(TolerantModel):
    """Single time-bucketed data point."""

    model_config = ConfigDict(populate_by_name=True)

    timestamp: str
    value: float
    count: int


class ExecutionListResponse(TolerantModel):
    """Raw execution metrics list."""

    model_config = ConfigDict(populate_by_name=True)

    executions: list[dict[str, Any]]
    count: int


class TopErrorItem(TolerantModel):
    """Top error by frequency."""

    model_config = ConfigDict(populate_by_name=True)

    error_type: str
    count: int
    last_message: str | None = None
    last_occurred: str | None = None


class TopAgentUsage(TolerantModel):
    """Per-agent usage aggregate (top_agents entry on the dashboard rollup)."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str
    execution_count: int
    total_tokens: int
    total_cost: float


class DashboardMetrics(TolerantModel):
    """
    Dashboard metrics rollup for the last 24h/30d window.

    Mirrors ``MetricsService.get_dashboard`` return shape: ``period`` + a nested
    ``summary`` + ``top_errors`` (currently always empty — see service
    docstring) + ``top_agents``.
    """

    model_config = ConfigDict(populate_by_name=True)

    period: str
    summary: MetricsSummary
    top_errors: list[TopErrorItem] = Field(default_factory=list)
    top_agents: list[TopAgentUsage] = Field(default_factory=list)


class AgentMetrics(TolerantModel):
    """
    Per-agent metrics, frontend-expected field names.

    Mirrors ``MetricsService.get_agent_metrics`` return shape — distinct field names
    from ``MetricsSummary`` (``successful_executions`` vs ``success_count``,
    ``total_cost`` vs ``total_cost_usd``) because the service intentionally
    remaps for this one endpoint; do NOT collapse into MetricsSummary.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_latency_ms: float
    total_tokens: int
    total_cost: float
    error_rate: float
    last_execution_at: str | None = None


class SdkMetricsOverview(TolerantModel):
    """Developer SDK API-usage headline counters + prior-window trends.

    Mirrors ``SdkMetricsOverviewResponse`` — DISTINCT surface from the agent-execution metrics above:
    ``/api/v1/sdk-metrics/*`` is the developer API-usage lens (calls, error
    rate, latency, active users). All keys camelCase on the wire.
    """

    model_config = ConfigDict(populate_by_name=True)

    total_calls: int = Field(alias="totalCalls")
    total_calls_trend: float = Field(alias="totalCallsTrend")
    active_users: int = Field(alias="activeUsers")
    active_users_trend: float = Field(alias="activeUsersTrend")
    error_rate: float = Field(alias="errorRate")
    error_rate_trend: float = Field(alias="errorRateTrend")
    avg_latency_ms: float = Field(alias="avgLatencyMs")
    avg_latency_trend: float = Field(alias="avgLatencyTrend")


class InvocationSummary(TolerantModel):
    """Tool-agent invocation KPIs (/observe/invocations tiles).

    Mirrors ``InvocationSummaryResponse`` — plain snake_case on the wire.
    ``total_cost`` is a Decimal STRING (never a float — monetary values are
    serialised as strings server-side).
    """

    model_config = ConfigDict(populate_by_name=True)

    total_invocations: int
    total_cost: str
    success_rate: float
    outcomes_breakdown: dict[str, Any]
    top_agents: list[dict[str, Any]]


# ============================================================================
# Module
# ============================================================================


class MetricsModule:
    """
    Metrics module for execution metrics summary, time-series, and export.

    Examples:
        >>> dash = await client.metrics.dashboard()
        >>> print(f"30d executions: {dash.summary.total_executions}")

        >>> summary = await client.metrics.summary(agent_id="agent-123")
        >>> print(f"Error rate: {summary.error_rate}%")

        >>> points = await client.metrics.timeseries(
        ...     metric="latency", start_date="2026-01-01", end_date="2026-01-31"
        ... )
    """

    def __init__(self, http_client):
        """
        Initialize the metrics module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def dashboard(self) -> DashboardMetrics:
        """
        Get dashboard metrics for the last 24 hours / 30-day window.

        GET /api/v1/metrics/dashboard

        Returns:
            DashboardMetrics: period + summary + top_errors + top_agents
        """
        response = await self._http.request("GET", "/api/v1/metrics/dashboard")
        return DashboardMetrics(**response)

    async def summary(
        self,
        deployment_id: str | None = None,
        agent_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> MetricsSummary:
        """
        Get aggregated metrics summary.

        GET /api/v1/metrics/summary

        Args:
            deployment_id: Filter by deployment
            agent_id: Filter by agent
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            MetricsSummary: avg latency, total tokens, error rate, cost
        """
        params: dict[str, Any] = {}
        if deployment_id:
            params["deployment_id"] = deployment_id
        if agent_id:
            params["agent_id"] = agent_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/metrics/summary",
            params=params if params else None,
        )
        return MetricsSummary(**response)

    async def timeseries(
        self,
        metric: Literal["latency", "tokens", "errors", "cost"],
        start_date: str,
        end_date: str,
        interval: Literal["hour", "day", "week"] = "day",
    ) -> list[TimeseriesPoint]:
        """
        Get time-bucketed metric data (analytics feature latency/tokens/errors/cost charts).

        GET /api/v1/metrics/timeseries

        Args:
            metric: Metric type — latency, tokens, errors, or cost
            start_date: Start date (ISO format) — required by the backend
            end_date: End date (ISO format) — required by the backend
            interval: Time interval — hour, day, or week (default: day)

        Returns:
            list[TimeseriesPoint]: Data points for charting
        """
        response = await self._http.request(
            "GET",
            "/api/v1/metrics/timeseries",
            params={
                "metric": metric,
                "interval": interval,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return [TimeseriesPoint(**item) for item in response.get("data", [])]

    async def list_executions(
        self,
        deployment_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> ExecutionListResponse:
        """
        List raw execution metrics.

        GET /api/v1/metrics/executions

        Args:
            deployment_id: Filter by deployment
            agent_id: Filter by agent
            status: Filter by status
            limit: Maximum results (1-200, default 100)

        Returns:
            ExecutionListResponse: executions + count
        """
        params: dict[str, Any] = {"limit": limit}
        if deployment_id:
            params["deployment_id"] = deployment_id
        if agent_id:
            params["agent_id"] = agent_id
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            "/api/v1/metrics/executions",
            params=params,
        )
        return ExecutionListResponse(**response)

    async def top_errors(self, limit: int = 10) -> list[TopErrorItem]:
        """
        Get top errors by frequency.

        GET /api/v1/metrics/errors

        Args:
            limit: Maximum results (1-100, default 10)

        Returns:
            list[TopErrorItem]: Error types with counts
        """
        response = await self._http.request(
            "GET",
            "/api/v1/metrics/errors",
            params={"limit": limit},
        )
        return [TopErrorItem(**item) for item in response.get("errors", [])]

    async def deployment_metrics(self, deployment_id: str) -> MetricsSummary:
        """
        Get metrics for a specific deployment.

        GET /api/v1/metrics/deployments/{deployment_id}

        Args:
            deployment_id: Deployment id

        Returns:
            MetricsSummary: Aggregated metrics for the deployment
        """
        response = await self._http.request(
            "GET", f"/api/v1/metrics/deployments/{encode_path_param(deployment_id)}"
        )
        return MetricsSummary(**response)

    async def agent_metrics(self, agent_id: str) -> AgentMetrics:
        """
        Get metrics for a specific agent.

        GET /api/v1/metrics/agents/{agent_id}

        Args:
            agent_id: Agent id

        Returns:
            AgentMetrics: Aggregated metrics for the agent (distinct field
            names from MetricsSummary — see AgentMetrics docstring)
        """
        response = await self._http.request(
            "GET", f"/api/v1/metrics/agents/{encode_path_param(agent_id)}"
        )
        return AgentMetrics(**response)

    async def record_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        """
        Record an execution metric (used by gateways to report executions).

        POST /api/v1/metrics/record

        ⛔ REQUIRES A WRITE CREDENTIAL — changed 2026-09-14.

        This endpoint persists a row. It previously accepted a READ credential,
        which was an authorization defect and has been fixed.

        * **API key** (the usual caller here — a gateway reporting executions):
          the key MUST carry the ``metrics:write`` scope. A key scoped only
          ``metrics:read`` now receives **403**. ``metrics:write`` implies read,
          so one scope is enough for both this and the read methods below.
        * **User token**: requires the ``metrics:create`` permission.

        The 403 body is self-describing — it carries ``required_permission``
        and ``required_api_key_scope`` keys naming exactly what to grant, so a
        broken integration can be diagnosed from the response alone.

        Every READ method on this class is unaffected.

        Args:
            metric: Metric data — MUST include deployment_id, agent_id, status

        Returns:
            dict: The created metric record

        Raises:
            Forbidden: 403 when the credential lacks ``metrics:write`` scope
                (API key) or the ``metrics:create`` permission (user token).
        """
        return await self._http.request(
            "POST",
            "/api/v1/metrics/record",
            json_data=metric,
        )

    async def sdk_metrics_overview(
        self,
        range: str = "24h",
    ) -> SdkMetricsOverview:
        """
        Get developer SDK API-usage headline counters (features/sdk dashboard).

        GET /api/v1/sdk-metrics/overview. This is the DEVELOPER API-usage lens — distinct from the
        agent-execution metrics served by the other methods on this module.
        Empty state returns zeros (never 404).

        Args:
            range: Time range — one of "1h", "24h", "7d", "30d" (default 24h;
                any other value is normalised to "24h" server-side)

        Returns:
            SdkMetricsOverview: Call/user/error/latency counters + trends
        """
        return SdkMetricsOverview(
            **await self._http.request(
                "GET",
                "/api/v1/sdk-metrics/overview",
                params={"range": range},
            )
        )

    async def invocation_summary(self) -> InvocationSummary:
        """
        Get tool-agent invocation KPIs (/observe/invocations tiles).

        GET /api/v1/invocation-analytics/summary. Returns zeroed values (not 404)
        when no invocations exist. Monetary values are Decimal strings.

        Returns:
            InvocationSummary: total invocations, cost, success rate,
            outcome breakdown, top agents
        """
        return InvocationSummary(
            **await self._http.request(
                "GET",
                "/api/v1/invocation-analytics/summary",
            )
        )

    async def invocations_by_application(self) -> list[dict[str, Any]]:
        """
        Get per-application invocation metrics.

        GET /api/v1/invocation-analytics/by-application — returns a BARE JSON array
        (``list[dict]``, service ``get_by_application`` return type); the
        route declares no strict response_model, so the raw records are
        returned unmodelled. Monetary values are Decimal strings.

        Returns:
            list[dict]: Per-application invocation records
        """
        return await self._http.request(
            "GET",
            "/api/v1/invocation-analytics/by-application",
        )

    async def invocations_by_agent(self) -> list[dict[str, Any]]:
        """
        Get per-agent invocation metrics grouped by tool agent.

        GET /api/v1/invocation-analytics/by-agent — returns a BARE JSON array
        (``list[dict]``, service ``get_by_agent`` return type); no strict
        response_model, so raw records are returned unmodelled. Monetary
        values are Decimal strings.

        Returns:
            list[dict]: Per-agent invocation records
        """
        return await self._http.request(
            "GET",
            "/api/v1/invocation-analytics/by-agent",
        )
