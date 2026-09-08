"""
Agentic Dashboard Module for Agentic OS SDK.

Thin HTTP-wrapper over the backend's Agentic OS dashboard surface
(prefix ``/api/v1/agentic``) — the
primary OBSERVE landing surface: dashboard stats, the task inbox, claim,
and validate (the core human-in-the-loop flows).

Every route below was verified against the deployed API before implementation — path,
method, and response shape match exactly. This module is self-contained
(no imports from client.py / modules/__init__.py / types.py); it is registered
on ``AgenticOSClient``.

8 methods:
- dashboard_stats()   - GET  /api/v1/agentic/dashboard/stats        (P0)
- inbox()             - GET  /api/v1/agentic/inbox                 (P0)
- claim()             - POST /api/v1/agentic/requests/{id}/claim   (P0)
- validate()          - POST /api/v1/agentic/requests/{id}/validate (P0)
- activity_feed()     - GET  /api/v1/agentic/dashboard/activity-feed (P1)
- get_request()       - GET  /api/v1/agentic/requests/{id}          (P1)
- list_pools()        - GET  /api/v1/agentic/pools                  (P1)
- get_pool()          - GET  /api/v1/agentic/pools/{id}             (bonus)
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param

# ============================================================================
# Response Models (local — mirror the server response shape exactly)
# ============================================================================


class AgentContext(BaseModel):
    """User's shadow agent context (already snake_case on the wire)."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str | None = None
    agent_name: str | None = None
    agent_status: str | None = None
    access_type: str | None = None
    permission_level: str | None = None


class LastAgentAction(BaseModel):
    """Most recent agent activity event (already snake_case on the wire)."""

    model_config = ConfigDict(populate_by_name=True)

    timestamp: str
    description: str
    agent_name: str | None = None
    objective_id: str | None = None


class DashboardStats(BaseModel):
    """
    Dashboard statistics for the Agentic OS home page.

    Backend emits camelCase (``DashboardStatsResponse`` in uses literal camelCase field
    names, not aliased snake_case) — this SDK model maps those wire keys to
    Pythonic snake_case attributes via ``Field(alias=...)``.
    """

    model_config = ConfigDict(populate_by_name=True)

    pending_objectives: int = Field(alias="pendingObjectives")
    active_objectives: int = Field(alias="activeObjectives")
    completed_today: int = Field(alias="completedToday")
    active_sessions: int = Field(alias="activeSessions")
    pending_escalations: int = Field(alias="pendingEscalations")
    active_agents: int = Field(alias="activeAgents")
    pending_inbox_count: int = Field(0, alias="pendingInboxCount")
    agent_context: AgentContext | None = Field(None, alias="agentContext")
    posture_distribution: dict[str, int] | None = Field(None, alias="postureDistribution")
    active_delegations: int = Field(0, alias="activeDelegations")
    active_objectives_today: int = Field(0, alias="activeObjectivesToday")
    completed_this_week: int = Field(0, alias="completedThisWeek")
    executing_agents_count: int = Field(0, alias="executingAgentsCount")
    last_agent_action: LastAgentAction | None = Field(None, alias="lastAgentAction")


class InboxResponse(BaseModel):
    """
    Task inbox response.

    ``records`` are raw ``AgenticRequest`` rows (backend returns
    ``list[dict]`` verbatim, no strict per-record model — see); kept as ``dict`` here to
    avoid inventing a fake schema for a shape the backend itself doesn't pin.
    """

    model_config = ConfigDict(populate_by_name=True)

    records: list[dict[str, Any]]
    total: int


class ActivityFeedItem(BaseModel):
    """Single activity feed item (already snake_case on the wire)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    title: str
    description: str | None = None
    status: str | None = None
    objective_id: str | None = None
    agent_name: str | None = None
    selected_posture: str | None = None
    timestamp: str


class ActivityFeedResponse(BaseModel):
    """Activity feed response."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ActivityFeedItem]
    total: int


class ClaimResult(BaseModel):
    """Result of claiming a task from the inbox."""

    model_config = ConfigDict(populate_by_name=True)

    status: str
    request: dict[str, Any]


class ValidateResult(BaseModel):
    """
    Result of validating (approve/reject/revise) a completed request.

    Shape varies by action — ``notification`` is present only on approve;
    ``reason`` is present on reject/revise (see). Both are optional here.
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str
    request_id: str
    reason: str | None = None
    notification: dict[str, Any] | None = None


class PoolSummary(BaseModel):
    """Task pool summary (list view)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    member_count: int
    active_tasks: int


class PoolListResponse(BaseModel):
    """List of task pools."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[PoolSummary]
    total: int


class PoolDetail(BaseModel):
    """Single task pool detail (includes claim/pool timeout fields)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    member_count: int
    active_tasks: int
    task_count: int
    available_count: int
    timeout: str
    claim_timeout: str


class DriftMetrics(BaseModel):
    """Drift metrics rollup.

    Mirrors ``DriftMetrics`` — camelCase
    on the wire.
    """

    model_config = ConfigDict(populate_by_name=True)

    alerts_last_24h: int = Field(0, alias="alertsLast24h")
    avg_escalation_duration: int = Field(0, alias="avgEscalationDuration")
    recovery_rate: float = Field(0.0, alias="recoveryRate")


class DriftStatus(BaseModel):
    """Complete drift status for an agent.

    Mirrors ``DriftStatusResponse`` —
    camelCase on the wire. The route wraps this under a ``status`` envelope
    key; :meth:`AgenticDashboardModule.get_agent_drift`
    unwraps it.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    current_level: str = Field(alias="currentLevel")
    last_evaluated_at: str = Field(alias="lastEvaluatedAt")
    active_alerts: list[dict[str, Any]] = Field(default_factory=list, alias="activeAlerts")
    recent_triggers: list[dict[str, Any]] = Field(default_factory=list, alias="recentTriggers")
    pending_recovery: dict[str, Any] | None = Field(None, alias="pendingRecovery")
    metrics: DriftMetrics


class DriftRecoveryRequest(BaseModel):
    """Drift recovery request record.

    Mirrors ``DriftRecoveryRequestResponse`` — camelCase on the wire. The route wraps this under a
    ``recovery`` envelope key;
    :meth:`AgenticDashboardModule.recover_drift` unwraps it.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    agent_id: str = Field(alias="agentId")
    requested_level: str = Field(alias="requestedLevel")
    current_level: str = Field(alias="currentLevel")
    reason: str
    requested_by: str = Field(alias="requestedBy")
    requested_at: str = Field(alias="requestedAt")
    status: str
    reviewed_by: str | None = Field(None, alias="reviewedBy")
    reviewed_at: str | None = Field(None, alias="reviewedAt")
    review_notes: str | None = Field(None, alias="reviewNotes")


class DriftTrigger(BaseModel):
    """Drift trigger detail on an alert.

    Mirrors ``DriftTriggerResponse``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    type: str | None = None
    description: str | None = None
    severity: str | None = None
    detected_at: str | None = Field(None, alias="detectedAt")
    metrics: dict[str, Any] | None = None


class DriftAlert(BaseModel):
    """Active drift alert across agents.

    Mirrors ``DriftAlertResponse`` —
    camelCase on the wire. The route wraps a list under an ``alerts``
    envelope key;
    :meth:`AgenticDashboardModule.list_drift_alerts` unwraps it.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    trigger: DriftTrigger | None = None
    previous_level: str = Field(alias="previousLevel")
    current_level: str = Field(alias="currentLevel")
    escalated_at: str = Field(alias="escalatedAt")
    escalated_by: str = Field(alias="escalatedBy")
    acknowledged_at: str | None = Field(None, alias="acknowledgedAt")
    acknowledged_by: str | None = Field(None, alias="acknowledgedBy")
    resolved_at: str | None = Field(None, alias="resolvedAt")
    resolved_by: str | None = Field(None, alias="resolvedBy")
    notes: str | None = None


class ReasoningTraceRecord(BaseModel):
    """Single redacted reasoning trace (governance decision review).

    Mirrors ``ReasoningTraceRecord`` — all field names camelCase on the wire. Content is redacted
    server-side per the caller's effective clearance.
    """

    model_config = ConfigDict(populate_by_name=True)

    trace_id: str = Field(alias="traceId")
    decision: str
    rationale: str
    reasoning: str
    confidentiality: str
    timestamp: str
    methodology: str | None = None
    confidence: float | None = None
    parent_record_type: str | None = Field(None, alias="parentRecordType")
    parent_record_id: str | None = Field(None, alias="parentRecordId")
    genesis_binding_hash: str | None = Field(None, alias="genesisBindingHash")
    trace_hash: str = Field(alias="traceHash")
    alternatives_considered: list[str] = Field(alias="alternativesConsidered")
    evidence: list[dict[str, Any]]
    anchor_id: str = Field(alias="anchorId")
    organization_id: str = Field(alias="organizationId")


class ReasoningTraceListResponse(BaseModel):
    """Paginated reasoning-trace list.

    Mirrors ``ReasoningTraceListResponse`` — ``{records, total}``.
    """

    model_config = ConfigDict(populate_by_name=True)

    records: list[ReasoningTraceRecord]
    total: int


# ============================================================================
# Module
# ============================================================================


class AgenticDashboardModule:
    """
    Agentic Dashboard module — the primary OBSERVE landing surface.

    Provides dashboard statistics, the task inbox, and the claim/validate
    human-in-the-loop flows for the Agentic OS home page.

    Examples:
        >>> stats = await client.agentic_dashboard.dashboard_stats()
        >>> print(f"Pending objectives: {stats.pending_objectives}")

        >>> inbox = await client.agentic_dashboard.inbox()
        >>> for task in inbox.records:
        ...     print(task["id"], task.get("title"))

        >>> claimed = await client.agentic_dashboard.claim("req-123")
        >>> result = await client.agentic_dashboard.validate("req-123", action="approve")
    """

    def __init__(self, http_client):
        """
        Initialize the agentic dashboard module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def dashboard_stats(self) -> DashboardStats:
        """
        Get dashboard statistics for the Agentic OS home page.

        GET /api/v1/agentic/dashboard/stats

        Returns:
            DashboardStats: Aggregated dashboard metrics
        """
        response = await self._http.request("GET", "/api/v1/agentic/dashboard/stats")
        return DashboardStats(**response)

    async def inbox(self) -> InboxResponse:
        """
        Get tasks delegated to the current user's pools and direct assignments.

        GET /api/v1/agentic/inbox

        Returns:
            InboxResponse: Combined pool + direct-assigned tasks
        """
        response = await self._http.request("GET", "/api/v1/agentic/inbox")
        return InboxResponse(**response)

    async def claim(self, request_id: str) -> ClaimResult:
        """
        Claim a task from the user's inbox (core work flow).

        POST /api/v1/agentic/requests/{request_id}/claim

        Uses an atomic conditional update server-side to prevent race
        conditions. If the task was already claimed by another user the
        platform answers 409, which reaches you as the BASE ``AgenticOSError``
        -- the SDK defines no conflict-specific subclass and 409 falls through
        the status mapping unmapped. Discriminate on
        ``exc.details["status_code"] == 409``.

        Args:
            request_id: The AgenticRequest id to claim

        Returns:
            ClaimResult: status + the claimed request record
        """
        response = await self._http.request(
            "POST", f"/api/v1/agentic/requests/{encode_path_param(request_id)}/claim"
        )
        return ClaimResult(**response)

    async def validate(
        self,
        request_id: str,
        action: Literal["approve", "reject", "revise"],
        summary: str | None = None,
        reason: str | None = None,
        deliverable_ids: list[str] | None = None,
    ) -> ValidateResult:
        """
        Validate (approve/reject/revise) a completed request — the core HITL flow.

        POST /api/v1/agentic/requests/{request_id}/validate

        Args:
            request_id: The AgenticRequest id to validate
            action: One of "approve", "reject", "revise"
            summary: Optional summary (used on approve)
            reason: Optional reason (used on reject/revise)
            deliverable_ids: Optional deliverable ids (used on approve)

        Returns:
            ValidateResult: status + request_id + (reason | notification)
        """
        body: dict[str, Any] = {"action": action}
        if summary is not None:
            body["summary"] = summary
        if reason is not None:
            body["reason"] = reason
        if deliverable_ids is not None:
            body["deliverable_ids"] = deliverable_ids

        response = await self._http.request(
            "POST",
            f"/api/v1/agentic/requests/{encode_path_param(request_id)}/validate",
            json_data=body,
        )
        return ValidateResult(**response)

    async def activity_feed(self, limit: int = 20) -> ActivityFeedResponse:
        """
        Get recent agent activity feed for the dashboard.

        GET /api/v1/agentic/dashboard/activity-feed

        Args:
            limit: Max items to return (1-100, default 20)

        Returns:
            ActivityFeedResponse: Recent activity, most recent first
        """
        response = await self._http.request(
            "GET",
            "/api/v1/agentic/dashboard/activity-feed",
            params={"limit": limit},
        )
        return ActivityFeedResponse(**response)

    async def get_request(self, request_id: str) -> dict[str, Any]:
        """
        Get a single agentic request (pool/objective task) by id.

        GET /api/v1/agentic/requests/{request_id}

        Returns the raw record — the backend returns the ``AgenticRequest``
        row verbatim, no
        strict response_model is declared, so no field-level schema is
        invented here.

        Args:
            request_id: The AgenticRequest id

        Returns:
            dict: The raw AgenticRequest record
        """
        return await self._http.request(
            "GET", f"/api/v1/agentic/requests/{encode_path_param(request_id)}"
        )

    async def list_pools(self) -> PoolListResponse:
        """
        List available task pools for the current user's organization.

        GET /api/v1/agentic/pools

        Returns:
            PoolListResponse: Pools with member/active-task counts
        """
        response = await self._http.request("GET", "/api/v1/agentic/pools")
        return PoolListResponse(**response)

    async def get_pool(self, pool_id: str) -> PoolDetail:
        """
        Get a single task pool by id (pool/objective task detail page).

        GET /api/v1/agentic/pools/{pool_id}

        Args:
            pool_id: The AgenticPool id

        Returns:
            PoolDetail: Pool config + escalation-chain-adjacent detail fields
        """
        response = await self._http.request(
            "GET", f"/api/v1/agentic/pools/{encode_path_param(pool_id)}"
        )
        return PoolDetail(**response)

    async def get_agent_drift(self, agent_id: str) -> DriftStatus:
        """
        Get the current drift status for an agent (drift-escalation dashboard).

        GET /api/v1/agentic/agents/{agent_id}/drift. The backend wraps the status under a ``status``
        envelope key; this unwraps it.

        Args:
            agent_id: The agent id

        Returns:
            DriftStatus: Current level, active alerts, recent triggers,
            pending recovery, metrics
        """
        response = await self._http.request(
            "GET", f"/api/v1/agentic/agents/{encode_path_param(agent_id)}/drift"
        )
        return DriftStatus(**response["status"])

    async def escalate_drift(
        self,
        agent_id: str,
        target_level: str,
        reason: str,
    ) -> DriftStatus:
        """
        Manually escalate an agent to a higher drift level.

        POST /api/v1/agentic/agents/{agent_id}/drift/escalate. Returns the updated drift status (unwrapped
        from the ``status`` envelope key).

        Args:
            agent_id: The agent id
            target_level: Target drift level — one of warning, hard_block,
                sandbox, restrict, isolate
            reason: Reason for the escalation (required)

        Returns:
            DriftStatus: The updated drift status
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/agentic/agents/{encode_path_param(agent_id)}/drift/escalate",
            json_data={"targetLevel": target_level, "reason": reason},
        )
        return DriftStatus(**response["status"])

    async def recover_drift(
        self,
        agent_id: str,
        target_level: str,
        reason: str,
    ) -> DriftRecoveryRequest:
        """
        Request recovery to a lower drift level (may require approval).

        POST /api/v1/agentic/agents/{agent_id}/drift/recover. Returns the recovery request record
        (unwrapped from the ``recovery`` envelope key).

        Args:
            agent_id: The agent id
            target_level: Target drift level — one of none, warning,
                hard_block, sandbox, restrict
            reason: Reason for the recovery request (required)

        Returns:
            DriftRecoveryRequest: The recovery request (pending / approved /
            rejected)
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/agentic/agents/{encode_path_param(agent_id)}/drift/recover",
            json_data={"targetLevel": target_level, "reason": reason},
        )
        return DriftRecoveryRequest(**response["recovery"])

    async def list_drift_alerts(
        self,
        status: str = "active",
        agent_id: str | None = None,
        severity: str | None = None,
        limit: int = 20,
    ) -> list[DriftAlert]:
        """
        List active drift alerts across all agents.

        GET /api/v1/agentic/drift/alerts.
        Returns the list unwrapped from the ``alerts`` envelope key.

        Args:
            status: Alert status filter — active, acknowledged, or resolved
                (default active)
            agent_id: Filter to a specific agent
            severity: Filter by severity — low, medium, high, critical
            limit: Maximum results (1-100, default 20)

        Returns:
            list[DriftAlert]: Drift alerts, most recent first
        """
        params: dict[str, Any] = {"status": status, "limit": limit}
        if agent_id:
            params["agent_id"] = agent_id
        if severity:
            params["severity"] = severity

        response = await self._http.request(
            "GET",
            "/api/v1/agentic/drift/alerts",
            params=params,
        )
        return [DriftAlert(**alert) for alert in response.get("alerts", [])]

    async def list_reasoning_traces(
        self,
        agent_id: str | None = None,
        parent_record_type: str | None = None,
        parent_record_id: str | None = None,
        methodology: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ReasoningTraceListResponse:
        """
        List redacted reasoning traces (governance decision review).

        GET /api/v1/reasoning-traces. Traces are redacted server-side per the caller's
        effective clearance (admin/executive/architect see CONFIDENTIAL, all
        others RESTRICTED) and scoped to the caller's organization.

        Args:
            agent_id: Filter by agent id
            parent_record_type: Filter by parent record type
            parent_record_id: Filter by parent record id
            methodology: Filter by methodology
            limit: Maximum results (1-200, default 50)
            offset: Pagination offset (default 0)

        Returns:
            ReasoningTraceListResponse: records + total (org-wide post-filter
            count)
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if agent_id:
            params["agent_id"] = agent_id
        if parent_record_type:
            params["parent_record_type"] = parent_record_type
        if parent_record_id:
            params["parent_record_id"] = parent_record_id
        if methodology:
            params["methodology"] = methodology

        response = await self._http.request(
            "GET",
            "/api/v1/reasoning-traces",
            params=params,
        )
        return ReasoningTraceListResponse(**response)
