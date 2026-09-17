"""
Pools Module for Agentic OS SDK.

Provides agent pool management, task claiming, and escalation features.

20 methods:
- list() - List pools
- create() - Create pool
- get() - Get pool details
- update() - Update pool
- delete() - Delete pool
- add_member() - Add member to pool
- remove_member() - Remove member from pool
- list_members() - List pool members
- get_utilization() - Get pool utilization metrics
- get_escalation_config() - Get escalation configuration
- update_escalation_config() - Update escalation configuration
- list_pending_escalations() - List pending escalations
- escalate_task() - Manually escalate task
- acknowledge_escalation() - Acknowledge escalation
- get_escalation_history() - Get escalation history
- get_escalation_stats() - Get escalation statistics
- list_requests() - List pending requests
- claim_request() - Claim a request
- respond_request() - Respond to request
- reassign_request() - Reassign request
"""

import builtins
from typing import Any, Literal

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class PoolConfig(TolerantModel):
    """Pool configuration."""

    model_config = ConfigDict(populate_by_name=True)

    max_concurrent_claims: int = Field(5, alias="maxConcurrentClaims")
    priority_rules: dict[str, Any] | None = Field(None, alias="priorityRules")
    capability_requirements: list[str] | None = Field(None, alias="capabilityRequirements")


class Pool(TolerantModel):
    """Agent pool model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    workspace_id: str | None = Field(None, alias="workspaceId")
    name: str
    description: str | None = None
    department: str | None = None
    config: PoolConfig | None = None
    claim_timeout_minutes: int = Field(30, alias="claimTimeoutMinutes")
    pool_timeout_minutes: int = Field(60, alias="poolTimeoutMinutes")
    load_balancing_strategy: str = Field(
        "round_robin", alias="loadBalancingStrategy"
    )  # round_robin, least_loaded, capability_match, priority
    escalation_target_type: str | None = Field(None, alias="escalationTargetType")
    escalation_target_id: str | None = Field(None, alias="escalationTargetId")
    status: str = "active"
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class PoolMember(TolerantModel):
    """Pool membership model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    pool_id: str = Field(alias="poolId")
    user_id: str = Field(alias="userId")
    capabilities: list[str] | None = None
    pool_role: str = Field("member", alias="poolRole")  # member, lead, admin
    status: str = "active"
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class PoolUtilization(TolerantModel):
    """Pool utilization metrics."""

    model_config = ConfigDict(populate_by_name=True)

    pool_id: str = Field(alias="poolId")
    pool_name: str = Field(alias="poolName")
    total_tasks: int = Field(alias="totalTasks")
    avg_wait_time_seconds: float = Field(alias="avgWaitTimeSeconds")
    avg_claim_time_seconds: float = Field(alias="avgClaimTimeSeconds")
    escalation_count: int = Field(alias="escalationCount")
    escalation_rate: float = Field(alias="escalationRate")


class PoolTaskResult(TolerantModel):
    """
    Outcome of a task claim, release, or claim-timeout change.

    ⛔ ``success`` is the load-bearing field. These operations answer HTTP 200
    even when they REFUSE — an already-claimed task or a non-member caller
    comes back with ``success`` false and a populated ``error``, not an
    exception. A caller that only checks for a raised error will read a
    refusal as a success.
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    task: dict[str, Any] | None = None
    error: str | None = None


class PoolTaskList(TolerantModel):
    """
    A page of pending pool tasks.

    ``tasks`` holds the backend-shaped task payloads, unmodelled because the
    operation declares no response schema.
    """

    model_config = ConfigDict(populate_by_name=True)

    tasks: builtins.list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class PoolSummaryList(TolerantModel):
    """A page of pool summaries; records are backend-shaped and unmodelled."""

    model_config = ConfigDict(populate_by_name=True)

    records: builtins.list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class PoolRosterEnvelope(TolerantModel):
    """The pools a user belongs to; entries are backend-shaped and unmodelled."""

    model_config = ConfigDict(populate_by_name=True)

    pools: builtins.list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class EscalationChainItem(TolerantModel):
    """Escalation chain step."""

    model_config = ConfigDict(populate_by_name=True)

    target_type: str = Field(alias="targetType")  # pool, user, team
    target_id: str = Field(alias="targetId")
    target_name: str | None = Field(None, alias="targetName")
    timeout_minutes: int = Field(alias="timeoutMinutes")


class EscalationConfig(TolerantModel):
    """Escalation configuration for a pool."""

    model_config = ConfigDict(populate_by_name=True)

    pool_id: str = Field(alias="poolId")
    enabled: bool = True
    claim_timeout_minutes: int = Field(30, alias="claimTimeoutMinutes")
    pool_timeout_minutes: int = Field(60, alias="poolTimeoutMinutes")
    escalation_chain: list[EscalationChainItem] = Field(
        default_factory=list, alias="escalationChain"
    )


class PendingEscalation(TolerantModel):
    """Pending escalation record."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    task_title: str = Field(alias="taskTitle")
    pool_id: str = Field(alias="poolId")
    pool_name: str = Field(alias="poolName")
    urgency: str
    priority: str
    created_at: str = Field(alias="createdAt")
    timeout_at: str = Field(alias="timeoutAt")
    current_step: int = Field(alias="currentStep")


class EscalationEvent(TolerantModel):
    """Escalation history event."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    task_id: str = Field(alias="taskId")
    event_type: str = Field(alias="eventType")  # created, escalated, acknowledged
    from_target: str | None = Field(None, alias="fromTarget")
    to_target: str | None = Field(None, alias="toTarget")
    reason: str | None = None
    created_at: str = Field(alias="createdAt")
    created_by: str | None = Field(None, alias="createdBy")


class EscalationStats(TolerantModel):
    """Escalation statistics."""

    model_config = ConfigDict(populate_by_name=True)

    pool_id: str | None = Field(None, alias="poolId")
    total_escalations: int = Field(alias="totalEscalations")
    pending_escalations: int = Field(alias="pendingEscalations")
    acknowledged_escalations: int = Field(alias="acknowledgedEscalations")
    avg_time_to_claim_seconds: float = Field(alias="avgTimeToClaimSeconds")
    escalation_rate: float = Field(alias="escalationRate")
    period_start: str | None = Field(None, alias="periodStart")
    period_end: str | None = Field(None, alias="periodEnd")


class PseudoRequest(TolerantModel):
    """Human-in-the-loop request."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    workspace_id: str | None = Field(None, alias="workspaceId")
    pseudo_agent_id: str = Field(alias="pseudoAgentId")
    title: str
    description: str | None = None
    priority: str = "medium"
    status: str  # pending, assigned, completed, cancelled
    assigned_to: str | None = Field(None, alias="assignedTo")
    assigned_at: str | None = Field(None, alias="assignedAt")
    due_at: str | None = Field(None, alias="dueAt")
    response: dict[str, Any] | None = None
    version: int = 1
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RequestStats(TolerantModel):
    """Request statistics."""

    model_config = ConfigDict(populate_by_name=True)

    pending: int
    assigned: int
    due_within_1_hour: int = Field(alias="dueWithin1Hour")
    overdue: int
    my_pending: int = Field(alias="myPending")
    unassigned: int
    escalated: int


class PoolsModule:
    """
    Pools module for agent pool management and task claiming.

    Provides human-in-the-loop task management with escalation support.

    Examples:
        # Get pool utilization
        >>> util = await client.pools.get_utilization("pool-123")
        >>> print(f"Avg wait: {util.avg_wait_time_seconds}s")
        >>> print(f"Escalation rate: {util.escalation_rate}%")

        # Claim a request
        >>> request = await client.pools.claim_request("req-456")
        >>> print(f"Claimed: {request.title}")
    """

    def __init__(self, http_client):
        """Initialize pools module."""
        self._http = http_client

    # Pool CRUD
    async def list(
        self,
        workspace_id: str | None = None,
        status: Literal["active", "archived"] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Pool]:
        """
        List pools.

        Args:
            workspace_id: Filter by workspace
            status: Filter by status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Pool]: List of pools
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if workspace_id:
            params["workspace_id"] = workspace_id
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            "/api/v1/pools",
            params=params,
        )
        return [Pool(**p) for p in response.get("pools", [])]

    async def create(
        self,
        name: str,
        description: str | None = None,
        workspace_id: str | None = None,
        department: str | None = None,
        load_balancing_strategy: Literal[
            "round_robin", "least_loaded", "capability_match", "priority"
        ] = "round_robin",
        claim_timeout_minutes: int = 30,
        pool_timeout_minutes: int = 60,
    ) -> Pool:
        """
        Create a new pool.

        Args:
            name: Pool name
            description: Pool description
            workspace_id: Workspace ID (optional)
            department: Department name
            load_balancing_strategy: How to distribute tasks
            claim_timeout_minutes: Timeout for claiming tasks
            pool_timeout_minutes: Timeout before escalation

        Returns:
            Pool: Created pool
        """
        data: dict[str, Any] = {
            "name": name,
            "loadBalancingStrategy": load_balancing_strategy,
            "claimTimeoutMinutes": claim_timeout_minutes,
            "poolTimeoutMinutes": pool_timeout_minutes,
        }
        if description:
            data["description"] = description
        if workspace_id:
            data["workspaceId"] = workspace_id
        if department:
            data["department"] = department

        response = await self._http.request(
            "POST",
            "/api/v1/pools",
            json_data=data,
        )
        return Pool(**response)

    async def get(self, pool_id: str) -> Pool:
        """
        Get pool details.

        Args:
            pool_id: Pool ID

        Returns:
            Pool: Pool details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/pools/{encode_path_param(pool_id)}",
        )
        return Pool(**response)

    async def update(
        self,
        pool_id: str,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        load_balancing_strategy: str | None = None,
    ) -> Pool:
        """
        Update pool.

        Args:
            pool_id: Pool ID
            name: New name
            description: New description
            status: New status
            load_balancing_strategy: New strategy

        Returns:
            Pool: Updated pool
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if status:
            data["status"] = status
        if load_balancing_strategy:
            data["loadBalancingStrategy"] = load_balancing_strategy

        response = await self._http.request(
            "PUT",
            f"/api/v1/pools/{encode_path_param(pool_id)}",
            json_data=data,
        )
        return Pool(**response)

    async def delete(self, pool_id: str) -> bool:
        """
        Delete pool.

        Args:
            pool_id: Pool ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/pools/{encode_path_param(pool_id)}",
        )
        return True

    # Membership
    async def list_members(
        self,
        pool_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> builtins.list[PoolMember]:
        """
        List pool members.

        Args:
            pool_id: Pool ID
            status: Filter by status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[PoolMember]: Pool members
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            f"/api/v1/pools/{encode_path_param(pool_id)}/members",
            params=params,
        )
        return [PoolMember(**m) for m in response.get("members", [])]

    async def add_member(
        self,
        pool_id: str,
        user_id: str,
        pool_role: Literal["member", "lead", "admin"] = "member",
        capabilities: builtins.list[str] | None = None,
    ) -> PoolMember:
        """
        Add member to pool.

        Args:
            pool_id: Pool ID
            user_id: User ID
            pool_role: Member role
            capabilities: Member capabilities

        Returns:
            PoolMember: Created membership
        """
        data: dict[str, Any] = {
            "userId": user_id,
            "poolRole": pool_role,
        }
        if capabilities:
            data["capabilities"] = capabilities

        response = await self._http.request(
            "POST",
            f"/api/v1/pools/{encode_path_param(pool_id)}/members",
            json_data=data,
        )
        return PoolMember(**response)

    async def remove_member(self, pool_id: str, member_id: str) -> bool:
        """
        Remove member from pool.

        Args:
            pool_id: Pool ID
            member_id: Membership ID

        Returns:
            bool: True if removed
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/pools/{encode_path_param(pool_id)}/members/{encode_path_param(member_id)}",
        )
        return True

    # Utilization
    async def get_utilization(
        self,
        pool_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> PoolUtilization:
        """
        Get pool utilization metrics.

        Args:
            pool_id: Pool ID
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)

        Returns:
            PoolUtilization: Utilization metrics

        Example:
            >>> util = await client.pools.get_utilization("pool-123")
            >>> print(f"Tasks: {util.total_tasks}")
            >>> print(f"Escalation rate: {util.escalation_rate}%")
        """
        params: dict[str, Any] = {}
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

    # Escalation Configuration
    async def get_escalation_config(self, pool_id: str) -> EscalationConfig:
        """
        Get escalation configuration for pool.

        Args:
            pool_id: Pool ID

        Returns:
            EscalationConfig: Escalation configuration
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/escalation/config/{encode_path_param(pool_id)}",
        )
        return EscalationConfig(**response)

    async def update_escalation_config(
        self,
        pool_id: str,
        enabled: bool | None = None,
        claim_timeout_minutes: int | None = None,
        pool_timeout_minutes: int | None = None,
        escalation_chain: builtins.list[dict[str, Any]] | None = None,
    ) -> EscalationConfig:
        """
        Update escalation configuration.

        Args:
            pool_id: Pool ID
            enabled: Enable/disable escalation
            claim_timeout_minutes: Timeout for claiming
            pool_timeout_minutes: Pool-level timeout
            escalation_chain: Escalation chain steps

        Returns:
            EscalationConfig: Updated configuration

        Example:
            >>> config = await client.pools.update_escalation_config(
            ...     pool_id="pool-123",
            ...     enabled=True,
            ...     claim_timeout_minutes=15,
            ...     escalation_chain=[
            ...         {"targetType": "user", "targetId": "user-1", "timeoutMinutes": 30},
            ...         {"targetType": "team", "targetId": "team-1", "timeoutMinutes": 60}
            ...     ]
            ... )
        """
        data: dict[str, Any] = {}
        if enabled is not None:
            data["enabled"] = enabled
        if claim_timeout_minutes is not None:
            data["claimTimeoutMinutes"] = claim_timeout_minutes
        if pool_timeout_minutes is not None:
            data["poolTimeoutMinutes"] = pool_timeout_minutes
        if escalation_chain is not None:
            data["escalationChain"] = escalation_chain

        response = await self._http.request(
            "PUT",
            f"/api/v1/escalation/config/{encode_path_param(pool_id)}",
            json_data=data,
        )
        return EscalationConfig(**response)

    # Escalation Management
    async def list_pending_escalations(
        self,
        pool_id: str | None = None,
        urgency: builtins.list[str] | None = None,
        priority: builtins.list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> builtins.list[PendingEscalation]:
        """
        List pending escalations.

        Args:
            pool_id: Filter by pool
            urgency: Filter by urgency levels
            priority: Filter by priority levels
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[PendingEscalation]: Pending escalations
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if pool_id:
            params["poolId"] = pool_id
        if urgency:
            params["urgency"] = ",".join(urgency)
        if priority:
            params["priority"] = ",".join(priority)

        response = await self._http.request(
            "GET",
            "/api/v1/escalation/pending",
            params=params,
        )
        return [PendingEscalation(**e) for e in response.get("escalations", [])]

    async def escalate_task(
        self,
        task_id: str,
        reason: str,
        target_id: str | None = None,
        target_type: Literal["pool", "user", "team"] | None = None,
    ) -> PendingEscalation:
        """
        Manually escalate a task.

        Args:
            task_id: Task ID
            reason: Escalation reason
            target_id: Specific target ID (optional)
            target_type: Target type (optional)

        Returns:
            PendingEscalation: Escalation record
        """
        data: dict[str, Any] = {"reason": reason}
        if target_id:
            data["targetId"] = target_id
        if target_type:
            data["targetType"] = target_type

        response = await self._http.request(
            "POST",
            f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/escalate",
            json_data=data,
        )
        return PendingEscalation(**response)

    async def acknowledge_escalation(self, task_id: str) -> bool:
        """
        Acknowledge a pending escalation.

        Args:
            task_id: Task ID

        Returns:
            bool: True if acknowledged
        """
        await self._http.request(
            "POST",
            f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/acknowledge",
        )
        return True

    async def get_escalation_history(
        self,
        task_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> builtins.list[EscalationEvent]:
        """
        Get escalation history for a task.

        Args:
            task_id: Task ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[EscalationEvent]: Escalation events
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/history",
            params={"limit": limit, "offset": offset},
        )
        return [EscalationEvent(**e) for e in response.get("events", [])]

    async def get_escalation_stats(
        self,
        pool_id: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> EscalationStats:
        """
        Get escalation statistics.

        Args:
            pool_id: Filter by pool
            period_start: Start date (ISO 8601)
            period_end: End date (ISO 8601)

        Returns:
            EscalationStats: Escalation metrics
        """
        params: dict[str, Any] = {}
        if pool_id:
            params["poolId"] = pool_id
        if period_start:
            params["periodStart"] = period_start
        if period_end:
            params["periodEnd"] = period_end

        response = await self._http.request(
            "GET",
            "/api/v1/escalation/stats",
            params=params if params else None,
        )
        return EscalationStats(**response)

    # Request Management (Human-in-the-Loop)
    async def list_requests(
        self,
        status: builtins.list[str] | None = None,
        assigned_to: str | None = None,
        pseudo_agent_id: str | None = None,
        priority: builtins.list[str] | None = None,
        workspace_id: str | None = None,
        search: str | None = None,
        due_before: str | None = None,
        due_after: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> builtins.list[PseudoRequest]:
        """
        List pending requests.

        Args:
            status: Filter by status (pending, assigned, completed)
            assigned_to: Filter by assignee ("me" for current user)
            pseudo_agent_id: Filter by pseudo agent pool
            priority: Filter by priority levels
            workspace_id: Filter by workspace
            search: Search in title/description
            due_before: Filter by due date
            due_after: Filter by due date
            page: Page number
            page_size: Page size

        Returns:
            List[PseudoRequest]: Requests
        """
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = ",".join(status)
        if assigned_to:
            params["assignedTo"] = assigned_to
        if pseudo_agent_id:
            params["pseudoAgentId"] = pseudo_agent_id
        if priority:
            params["priority"] = ",".join(priority)
        if workspace_id:
            params["workspaceId"] = workspace_id
        if search:
            params["search"] = search
        if due_before:
            params["dueBefore"] = due_before
        if due_after:
            params["dueAfter"] = due_after

        response = await self._http.request(
            "GET",
            "/api/v1/pseudo-requests",
            params=params,
        )
        return [PseudoRequest(**r) for r in response.get("requests", [])]

    async def get_request_stats(self) -> RequestStats:
        """
        Get request statistics.

        Returns:
            RequestStats: Request counts by status
        """
        response = await self._http.request(
            "GET",
            "/api/v1/pseudo-requests/stats",
        )
        return RequestStats(**response)

    async def claim_request(
        self,
        request_id: str,
        version: int | None = None,
    ) -> PseudoRequest:
        """
        Claim a request for handling.

        Args:
            request_id: Request ID
            version: Version for optimistic locking

        Returns:
            PseudoRequest: Claimed request

        Example:
            >>> request = await client.pools.claim_request("req-123")
            >>> print(f"Claimed: {request.title}")
        """
        data = {}
        if version is not None:
            data["version"] = version

        response = await self._http.request(
            "POST",
            f"/api/v1/pseudo-requests/{encode_path_param(request_id)}/claim",
            json_data=data if data else None,
        )
        return PseudoRequest(**response)

    async def respond_request(
        self,
        request_id: str,
        response_data: dict[str, Any],
        comment: str | None = None,
    ) -> PseudoRequest:
        """
        Respond to a claimed request.

        Args:
            request_id: Request ID
            response_data: Response data
            comment: Optional comment

        Returns:
            PseudoRequest: Updated request
        """
        data: dict[str, Any] = {"response": response_data}
        if comment:
            data["comment"] = comment

        response = await self._http.request(
            "POST",
            f"/api/v1/pseudo-requests/{encode_path_param(request_id)}/respond",
            json_data=data,
        )
        return PseudoRequest(**response)

    async def reassign_request(
        self,
        request_id: str,
        to_user_id: str,
        reason: str | None = None,
    ) -> PseudoRequest:
        """
        Reassign request to another operator.

        Args:
            request_id: Request ID
            to_user_id: New assignee user ID
            reason: Reason for reassignment

        Returns:
            PseudoRequest: Updated request
        """
        data: dict[str, Any] = {"toUserId": to_user_id}
        if reason:
            data["reason"] = reason

        response = await self._http.request(
            "POST",
            f"/api/v1/pseudo-requests/{encode_path_param(request_id)}/reassign",
            json_data=data,
        )
        return PseudoRequest(**response)

    # -------------------------------------------------------------------------
    # Timer Operations (SDK-only)
    # -------------------------------------------------------------------------

    async def extend_timeout(
        self,
        task_id: str,
        timeout_minutes: int,
    ) -> dict[str, Any]:
        """
        Extend/reset the escalation timer for a task.

        This is an SDK-only operation to extend the escalation timeout
        for a task that is taking longer than expected.

        Args:
            task_id: Task ID
            timeout_minutes: New timeout value in minutes

        Returns:
            Timer reset result with new expiry time

        Example:
            >>> # Task needs more time
            >>> result = await client.pools.extend_timeout(
            ...     task_id="task-123",
            ...     timeout_minutes=60,  # Extend to 60 minutes
            ... )
            >>> print(f"New timeout expires at: {result['expires_at']}")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/reset-timer",
            params={"timeout_minutes": timeout_minutes},
        )
        return response

    async def cancel_timeout(self, task_id: str) -> bool:
        """
        Cancel the escalation timer for a task.

        This is an SDK-only operation to prevent a task from escalating.
        Use with caution as it may leave tasks indefinitely unescalated.

        Args:
            task_id: Task ID

        Returns:
            True if timer was cancelled successfully

        Example:
            >>> # Task will be handled manually, cancel escalation
            >>> success = await client.pools.cancel_timeout("task-123")
            >>> if success:
            ...     print("Escalation timer cancelled")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/cancel-timer",
        )
        return response.get("success", False)

    # -------------------------------------------------------------------------
    # Pool operations — task claiming, lifecycle and routing telemetry
    #
    # These address the live operational surface under /api/v1/pools. None of
    # them declares a response schema, so envelopes that the platform emits
    # consistently are modelled and each record inside stays unmodelled.
    #
    # ⛔ AUTH: this surface admits a USER SESSION only. Its router gate does not
    # accept an API key, and an API-key principal carries no role and no
    # personas by design, so every method below answers 403 for a client built
    # with `api_key=`. Use the OAuth configuration instead.
    # -------------------------------------------------------------------------

    async def list_pool_summaries(
        self, status: str | None = None, limit: int = 50
    ) -> PoolSummaryList:
        """
        List pool summaries for the caller's organization.

        Args:
            status: Filter by pool status
            limit: Page size

        Returns:
            PoolSummaryList: summaries plus their count

        Example:
            >>> summaries = await client.pools.list_pool_summaries(status="active")
        """
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        response = await self._http.request(
            "GET", "/api/v1/pools/summaries", params=params
        )
        return PoolSummaryList(**response)

    async def get_user_pools(self, user_id: str) -> PoolRosterEnvelope:
        """
        List the pools a user belongs to.

        Args:
            user_id: User ID

        Returns:
            PoolRosterEnvelope: pools plus their total
        """
        response = await self._http.request(
            "GET", f"/api/v1/pools/user/{encode_path_param(user_id)}"
        )
        return PoolRosterEnvelope(**response)

    async def list_pending_tasks(self, limit: int = 50) -> PoolTaskList:
        """
        List pending tasks across every pool the caller can see.

        Args:
            limit: Page size

        Returns:
            PoolTaskList: tasks plus their total
        """
        response = await self._http.request(
            "GET", "/api/v1/pools/tasks/pending", params={"limit": limit}
        )
        return PoolTaskList(**response)

    async def list_pool_pending_tasks(
        self, pool_id: str, limit: int = 50
    ) -> PoolTaskList:
        """
        List pending tasks in one pool.

        Args:
            pool_id: Pool ID
            limit: Page size

        Returns:
            PoolTaskList: tasks plus their total
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/pools/{encode_path_param(pool_id)}/tasks/pending",
            params={"limit": limit},
        )
        return PoolTaskList(**response)

    async def claim_task(self, task_id: str) -> PoolTaskResult:
        """
        Claim a pending task for the authenticated caller.

        ⛔ CHECK ``result.success`` — this call does NOT raise on a refused
        claim. A task already claimed by someone else, or a caller who is not
        a member of the pool, both answer HTTP 200 with ``success`` false and
        a populated ``error``. Only a task that does not exist raises (404).
        Treating "no exception" as "claimed" will silently hand two callers
        the same task.

        The claiming identity is derived from the authenticated session, so
        this method takes no user argument.

        Args:
            task_id: Task ID

        Returns:
            PoolTaskResult: ``success``, the claimed ``task`` when it
            succeeded, and ``error`` when it did not

        Example:
            >>> result = await client.pools.claim_task("task-123")
            >>> if not result.success:
            ...     print(f"not claimed: {result.error}")
        """
        response = await self._http.request(
            "POST", f"/api/v1/pools/tasks/{encode_path_param(task_id)}/claim"
        )
        return PoolTaskResult(**response)

    async def release_task(self, task_id: str) -> PoolTaskResult:
        """
        Release a task the caller has claimed, returning it to its pool.

        ⛔ CHECK ``result.success`` — like :meth:`claim_task`, a refused
        release answers HTTP 200 with ``success`` false rather than raising.

        Args:
            task_id: Task ID

        Returns:
            PoolTaskResult: ``success``, ``task``, and ``error``
        """
        response = await self._http.request(
            "POST", f"/api/v1/pools/tasks/{encode_path_param(task_id)}/release"
        )
        return PoolTaskResult(**response)

    async def extend_claim_timeout(self, task_id: str) -> PoolTaskResult:
        """
        Extend the claim timeout on a task.

        ⚠ Takes a TASK id, despite sitting under the ``/pools/`` prefix where
        every sibling operation takes a pool id. Passing a pool id here will
        not work.

        ⛔ CHECK ``result.success`` — a refused extension answers HTTP 200
        with ``success`` false rather than raising.

        Args:
            task_id: Task ID whose claim timeout is extended

        Returns:
            PoolTaskResult: ``success``, ``task``, and ``error``
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/pools/{encode_path_param(task_id)}/operations/extend_timeout",
        )
        return PoolTaskResult(**response)

    async def cancel_claim_timeout(self, task_id: str) -> PoolTaskResult:
        """
        Cancel the claim timeout on a task, so the claim does not expire.

        ⚠ Takes a TASK id, not a pool id — see :meth:`extend_claim_timeout`.

        ⛔ CHECK ``result.success`` — a refused cancellation answers HTTP 200
        with ``success`` false rather than raising.

        Args:
            task_id: Task ID whose claim timeout is cancelled

        Returns:
            PoolTaskResult: ``success``, ``task``, and ``error``
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/pools/{encode_path_param(task_id)}/operations/cancel_timeout",
        )
        return PoolTaskResult(**response)

    async def pause_pool(self, pool_id: str) -> dict[str, Any]:
        """
        Pause a pool, so it stops accepting new work.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped status payload. This operation declares no
            response schema, so it is returned unmodelled.
        """
        payload: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/pools/{encode_path_param(pool_id)}/pause"
        )
        return payload

    async def resume_pool(self, pool_id: str) -> dict[str, Any]:
        """
        Resume a paused pool.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped status payload; see :meth:`pause_pool`.
        """
        payload: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/pools/{encode_path_param(pool_id)}/resume"
        )
        return payload

    async def drain_pool(self, pool_id: str) -> dict[str, Any]:
        """
        Drain a pool — stop accepting new work while letting claimed work
        finish.

        Distinct from :meth:`pause_pool` in intent: drain is the graceful
        wind-down.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped status payload; see :meth:`pause_pool`.
        """
        payload: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/pools/{encode_path_param(pool_id)}/drain"
        )
        return payload

    async def get_pool_health(self, pool_id: str) -> dict[str, Any]:
        """
        Get a pool's health rollup.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped health payload; see :meth:`pause_pool`.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/pools/{encode_path_param(pool_id)}/health"
        )
        return payload

    async def get_pool_statistics(self, pool_id: str) -> dict[str, Any]:
        """
        Get a pool's statistics.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped statistics payload; see :meth:`pause_pool`.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/pools/{encode_path_param(pool_id)}/statistics"
        )
        return payload

    async def get_pool_metrics(self, pool_id: str) -> dict[str, Any]:
        """
        Get a pool's routing metrics.

        Distinct from :meth:`get_utilization`, which reads the analytics
        surface rather than this operational one.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped metrics payload; see :meth:`pause_pool`.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/pools/{encode_path_param(pool_id)}/metrics"
        )
        return payload

    async def get_load_distribution(self, pool_id: str) -> dict[str, Any]:
        """
        Compute a pool's current per-member task load distribution.

        This is a point-in-time snapshot, not a history. The platform
        registers the same read under both GET and POST; this method uses GET,
        because the operation does not modify anything.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped distribution payload; see :meth:`pause_pool`.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET",
            f"/api/v1/pools/{encode_path_param(pool_id)}/operations/load_distribution",
        )
        return payload

    async def rebalance_pool(
        self, pool_id: str, workspace_id: str | None = None
    ) -> dict[str, Any]:
        """
        Rebalance a pool's task assignments across its members.

        Args:
            pool_id: Pool ID
            workspace_id: Restrict the rebalance to one workspace; the pool's
                own workspace is used when omitted

        Returns:
            The backend-shaped rebalance summary; see :meth:`pause_pool`.
        """
        body: dict[str, Any] = {}
        if workspace_id is not None:
            body["workspace_id"] = workspace_id
        payload: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/pools/{encode_path_param(pool_id)}/operations/rebalance",
            json_data=body,
        )
        return payload
