"""
Admin Module for Agentic OS SDK.

Thin HTTP-wrapper for the admin-settings domain's most-blocked P0/P1 admin
surface: task-pool management, agent-role assignments, org role hierarchy,
and the Admin Access Visualization endpoints (tree/matrix/audit/export).

Self-contained module: request/response models are
defined LOCALLY in this file. Do not import from ``aegis_sdk.types`` or
edit ``modules/__init__.py`` / ``client.py`` -- a separate orchestrator
wiring pass registers this module on the client.

Backend routers (verified against the real source, cited per-method below):
  (FastAPI prefix ``/admin``)
  (FastAPI prefix ``/admin/access``)
Both mount under the app-wide ``settings.api_prefix`` (``/api/v1`` --
verified), so
every path below is ``/api/v1/admin/...``.

18 methods:
  Pools:
    - list_pools()          GET    /api/v1/admin/pools
    - get_pool()             GET    /api/v1/admin/pools/{pool_id}
    - create_pool()          POST   /api/v1/admin/pools
    - update_pool()          PUT    /api/v1/admin/pools/{pool_id}
    - delete_pool()          DELETE /api/v1/admin/pools/{pool_id}
    - archive_pool()         POST   /api/v1/admin/pools/{pool_id}/archive
    - get_pool_stats()       GET    /api/v1/admin/pools/{pool_id}/stats
  Agent assignments:
    - list_assignments()     GET    /api/v1/admin/agent-assignments
    - get_assignment()       GET    /api/v1/admin/agent-assignments/{id}
    - create_assignment()    POST   /api/v1/admin/agent-assignments
    - delete_assignment()    DELETE /api/v1/admin/agent-assignments/{id}
    - bulk_delete_assignments() POST /api/v1/admin/agent-assignments/bulk-delete
  Role hierarchy:
    - get_role_hierarchy()   GET    /api/v1/admin/roles/hierarchy
  Admin Access Visualization:
    - get_access_tree()      GET    /api/v1/admin/access/tree
    - get_access_matrix()    GET    /api/v1/admin/access/matrix
    - get_access_audit()     GET    /api/v1/admin/access/audit
    - export_access()        POST   /api/v1/admin/access/export

Known limitation (documented, not a phantom route): ``POST
/admin/access/export`` supports ``format="csv"`` server-side, but the shared ``HTTPClient.request()``
always calls ``response.json()`` for a 200 -- that raises on CSV bytes. This module always requests
``format="json"`` (verified valid JSON)
and does not expose a ``format`` parameter; a raw-bytes export requires a
transport-layer addition out of this module's self-contained scope.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param

# ---------------------------------------------------------------------------
# Response models -- Pools (verified `_pool_to_response`)
# ---------------------------------------------------------------------------


class PoolConfig(BaseModel):
    """Pool configuration (response shape)."""

    model_config = ConfigDict(populate_by_name=True)

    claim_timeout_minutes: int = Field(30, alias="claimTimeoutMinutes")
    completion_timeout_minutes: int = Field(120, alias="completionTimeoutMinutes")
    max_concurrent_tasks: int = Field(5, alias="maxConcurrentTasks")
    priority_rules: list[dict[str, Any]] = Field(default_factory=list, alias="priorityRules")
    required_capabilities: list[str] = Field(default_factory=list, alias="requiredCapabilities")


class EscalationChainItem(BaseModel):
    """A single escalation-chain step (response shape)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    type: str = "user"  # "user" | "pool"
    target_id: str = Field("", alias="targetId")
    target_name: str = Field("", alias="targetName")
    delay_minutes: int = Field(30, alias="delayMinutes")
    order: int = 0


class AdminPool(BaseModel):
    """Task pool (response shape)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str = ""
    description: str = ""
    status: str = "active"
    config: PoolConfig = Field(default_factory=PoolConfig)
    escalation_chain: list[EscalationChainItem] = Field(
        default_factory=list, alias="escalationChain"
    )
    member_count: int = Field(0, alias="memberCount")
    pending_task_count: int = Field(0, alias="pendingTaskCount")
    avg_completion_time_ms: int = Field(0, alias="avgCompletionTimeMs")
    created_at: str = Field("", alias="createdAt")
    updated_at: str = Field("", alias="updatedAt")


class PoolListResult(BaseModel):
    """Paginated pool-list envelope."""

    records: list[AdminPool] = Field(default_factory=list)
    total: int = 0


class PoolStats(BaseModel):
    """Live pool statistics."""

    model_config = ConfigDict(populate_by_name=True)

    pending_tasks: int = Field(0, alias="pendingTasks")
    active_tasks: int = Field(0, alias="activeTasks")
    completed_tasks: int = Field(0, alias="completedTasks")
    avg_completion_time_ms: int = Field(0, alias="avgCompletionTimeMs")
    total_members: int = Field(0, alias="totalMembers")
    active_members: int = Field(0, alias="activeMembers")


# ---------------------------------------------------------------------------
# Response models -- Agent assignments
# ---------------------------------------------------------------------------


class AgentAssignment(BaseModel):
    """Agent-role assignment (response shape)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    agent_id: str = Field("", alias="agentId")
    agent_name: str = Field("", alias="agentName")
    role_id: str = Field("", alias="roleId")
    role_name: str = Field("", alias="roleName")
    permission_level: str = Field("read_only", alias="permissionLevel")
    expires_at: str | None = Field(None, alias="expiresAt")
    created_at: str = Field("", alias="createdAt")
    created_by: str = Field("", alias="createdBy")


class AssignmentListResult(BaseModel):
    """Paginated assignment-list envelope."""

    records: list[AgentAssignment] = Field(default_factory=list)
    total: int = 0


class BulkDeleteError(BaseModel):
    """A single failed id in a bulk-delete response."""

    id: str
    error: str


class BulkDeleteResult(BaseModel):
    """Bulk agent-assignment delete result."""

    deleted: int = 0
    errors: list[BulkDeleteError] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response models -- Role hierarchy
# ---------------------------------------------------------------------------


class RoleHierarchyNode(BaseModel):
    """A node in the role hierarchy tree."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str = ""
    description: str | None = None
    parent_id: str | None = Field(None, alias="parentId")
    children: list[RoleHierarchyNode] = Field(default_factory=list)
    agent_count: int = Field(0, alias="agentCount")
    user_count: int = Field(0, alias="userCount")


RoleHierarchyNode.model_rebuild()


class RoleHierarchyResult(BaseModel):
    """Role hierarchy envelope."""

    roots: list[RoleHierarchyNode] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response models -- Admin Access Visualization
# (verified against the platform's own admin-access route; wire-shape
#  locked at Tier 1 by an automated envelope-shape check on the platform side)
# ---------------------------------------------------------------------------


class AccessAgent(BaseModel):
    """Agent visible at a role, with its access classification."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str = ""
    access_type: str = Field("none", alias="accessType")
    permission_level: str = Field("read_only", alias="permissionLevel")


class AccessTreeNode(BaseModel):
    """Role node in the access tree, with nested children."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    role_id: str = Field("", alias="roleId")
    role_name: str = Field("", alias="roleName")
    role_description: str | None = Field(None, alias="roleDescription")
    access_type: str = Field("none", alias="accessType")
    agents: list[AccessAgent] = Field(default_factory=list)
    user_count: int = Field(0, alias="userCount")
    children: list[AccessTreeNode] = Field(default_factory=list)


AccessTreeNode.model_rebuild()


class AccessTreeResult(BaseModel):
    """Envelope for GET /admin/access/tree."""

    roots: list[AccessTreeNode] = Field(default_factory=list)


class AccessMatrixCell(BaseModel):
    """Single cell of the role x agent access matrix."""

    model_config = ConfigDict(populate_by_name=True)

    role_id: str = Field("", alias="roleId")
    agent_id: str = Field("", alias="agentId")
    access_type: str = Field("none", alias="accessType")
    permission_level: str | None = Field(None, alias="permissionLevel")


class AccessMatrixRow(BaseModel):
    """A single row of the access matrix (one per role)."""

    model_config = ConfigDict(populate_by_name=True)

    role_id: str = Field("", alias="roleId")
    role_name: str = Field("", alias="roleName")
    cells: list[AccessMatrixCell] = Field(default_factory=list)


class AccessMatrixAgent(BaseModel):
    """Compact agent descriptor for matrix column headers."""

    id: str
    name: str = ""


class AccessMatrixResult(BaseModel):
    """Envelope for GET /admin/access/matrix."""

    roles: list[AccessMatrixRow] = Field(default_factory=list)
    agents: list[AccessMatrixAgent] = Field(default_factory=list)


class AccessAuditEntry(BaseModel):
    """A single access grant/revoke/modify audit record."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    action: str = "modify"  # "grant" | "revoke" | "modify"
    target_type: str = Field("user", alias="targetType")  # "agent" | "role" | "user"
    target_id: str = Field("", alias="targetId")
    target_name: str = Field("", alias="targetName")
    role_id: str | None = Field(None, alias="roleId")
    role_name: str | None = Field(None, alias="roleName")
    performed_by: str = Field("", alias="performedBy")
    performed_by_name: str = Field("", alias="performedByName")
    details: str | None = None
    timestamp: str = ""


class AccessAuditResult(BaseModel):
    """Envelope for GET /admin/access/audit."""

    records: list[AccessAuditEntry] = Field(default_factory=list)
    total: int = 0


class AccessExportResult(BaseModel):
    """JSON-format envelope for POST /admin/access/export
    ( -- the ``format="json"`` branch this module
    always requests; see module docstring's Known limitation)."""

    organization_id: str = ""
    generated_at: str = ""
    include_inherited: bool = True
    rows: list[dict[str, Any]] = Field(default_factory=list)


class AdminModule:
    """
    Admin module for task-pool management, agent-role assignments, role
    hierarchy, and admin access visualization.

    Examples:
        # List pools
        >>> page = await client.admin.list_pools()
        >>> print(f"{page.total} pools")

        # Grant an agent-role assignment
        >>> assignment = await client.admin.create_assignment(
        ...     agent_id="agent-1", role_id="role-1", permission_level="limited"
        ... )
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize admin module.

        Args:
            http_client: HTTPClient instance for API requests.
        """
        self._http = http_client

    # -------------------------------------------------------------------
    # Pools
    # -------------------------------------------------------------------

    async def list_pools(
        self,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PoolListResult:
        """List task pools (GET /admin/pools).

        Args:
            status: Filter by pool status.
            search: Text search on name/description.
            page: Page number (1-indexed).
            page_size: Results per page (max 100).

        Returns:
            PoolListResult: Paginated pool records.
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if search:
            params["search"] = search

        response = await self._http.request(
            "GET",
            "/api/v1/admin/pools",
            params=params,
        )
        return PoolListResult(**response)

    async def get_pool(self, pool_id: str) -> AdminPool:
        """Get a single pool by ID (GET /admin/pools/{id})."""
        response = await self._http.request(
            "GET",
            f"/api/v1/admin/pools/{encode_path_param(pool_id)}",
        )
        return AdminPool(**response)

    async def create_pool(
        self,
        name: str,
        description: str | None = None,
        claim_timeout_minutes: int = 30,
        completion_timeout_minutes: int = 120,
        max_concurrent_tasks: int = 5,
        priority_rules: list[dict[str, Any]] | None = None,
        required_capabilities: list[str] | None = None,
        escalation_chain: list[dict[str, Any]] | None = None,
    ) -> AdminPool:
        """Create a new pool (POST /admin/pools).

        Request body is snake_case (``CreatePoolRequest`` /
        ``PoolConfigRequest`` declare no Pydantic
        alias), unlike the camelCase response.

        Args:
            name: Pool name.
            description: Pool description.
            claim_timeout_minutes: Timeout for claiming tasks.
            completion_timeout_minutes: Timeout before escalation.
            max_concurrent_tasks: Max concurrent tasks per pool.
            priority_rules: List of {condition, priority, description}.
            required_capabilities: Capability tags required to join the pool.
            escalation_chain: List of
                {type, target_id, target_name, delay_minutes, order}.

        Returns:
            AdminPool: Created pool.
        """
        data: dict[str, Any] = {
            "name": name,
            "config": {
                "claim_timeout_minutes": claim_timeout_minutes,
                "completion_timeout_minutes": completion_timeout_minutes,
                "max_concurrent_tasks": max_concurrent_tasks,
                "priority_rules": priority_rules or [],
                "required_capabilities": required_capabilities or [],
            },
            "escalation_chain": escalation_chain or [],
        }
        if description is not None:
            data["description"] = description

        response = await self._http.request(
            "POST",
            "/api/v1/admin/pools",
            json_data=data,
        )
        return AdminPool(**response)

    async def update_pool(
        self,
        pool_id: str,
        name: str | None = None,
        description: str | None = None,
        status: Literal["active", "inactive", "archived"] | None = None,
        claim_timeout_minutes: int | None = None,
        completion_timeout_minutes: int | None = None,
        max_concurrent_tasks: int | None = None,
        priority_rules: list[dict[str, Any]] | None = None,
        required_capabilities: list[str] | None = None,
        escalation_chain: list[dict[str, Any]] | None = None,
    ) -> AdminPool:
        """Update a pool (PUT /admin/pools/{id}).

        ``config`` and its nested fields are only sent when at least one
        config-shaped kwarg is provided (mirrors ``UpdatePoolRequest``'s
        optional ``config: PoolConfigRequest | None``).
        """
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if status is not None:
            data["status"] = status

        config_fields = {
            k: v
            for k, v in {
                "claim_timeout_minutes": claim_timeout_minutes,
                "completion_timeout_minutes": completion_timeout_minutes,
                "max_concurrent_tasks": max_concurrent_tasks,
                "priority_rules": priority_rules,
                "required_capabilities": required_capabilities,
            }.items()
            if v is not None
        }
        if config_fields:
            data["config"] = config_fields
        if escalation_chain is not None:
            data["escalation_chain"] = escalation_chain

        response = await self._http.request(
            "PUT",
            f"/api/v1/admin/pools/{encode_path_param(pool_id)}",
            json_data=data,
        )
        return AdminPool(**response)

    async def delete_pool(self, pool_id: str) -> bool:
        """Soft-delete a pool (DELETE /admin/pools/{id},
        returns 204 -- ``HTTPClient._handle_response`` maps 204 to
        ``None``)."""
        await self._http.request(
            "DELETE",
            f"/api/v1/admin/pools/{encode_path_param(pool_id)}",
        )
        return True

    async def archive_pool(self, pool_id: str) -> AdminPool:
        """Archive a pool (POST /admin/pools/{id}/archive)."""
        response = await self._http.request(
            "POST",
            f"/api/v1/admin/pools/{encode_path_param(pool_id)}/archive",
        )
        return AdminPool(**response)

    async def get_pool_stats(self, pool_id: str) -> PoolStats:
        """Get live pool statistics (GET /admin/pools/{id}/stats)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/admin/pools/{encode_path_param(pool_id)}/stats",
        )
        return PoolStats(**response)

    # -------------------------------------------------------------------
    # Agent assignments
    # -------------------------------------------------------------------

    async def list_assignments(
        self,
        agent_id: str | None = None,
        role_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AssignmentListResult:
        """List agent-role assignments (GET
        /admin/agent-assignments)."""
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if agent_id:
            params["agent_id"] = agent_id
        if role_id:
            params["role_id"] = role_id
        if search:
            params["search"] = search

        response = await self._http.request(
            "GET",
            "/api/v1/admin/agent-assignments",
            params=params,
        )
        return AssignmentListResult(**response)

    async def get_assignment(self, assignment_id: str) -> AgentAssignment:
        """Get a single agent-role assignment (GET
        /admin/agent-assignments/{id})."""
        response = await self._http.request(
            "GET",
            f"/api/v1/admin/agent-assignments/{encode_path_param(assignment_id)}",
        )
        return AgentAssignment(**response)

    async def create_assignment(
        self,
        agent_id: str,
        role_id: str,
        permission_level: Literal["full", "limited", "read_only"],
        expires_at: str | None = None,
    ) -> AgentAssignment:
        """Create an agent-role assignment (POST
        /admin/agent-assignments)."""
        data: dict[str, Any] = {
            "agent_id": agent_id,
            "role_id": role_id,
            "permission_level": permission_level,
        }
        if expires_at is not None:
            data["expires_at"] = expires_at

        response = await self._http.request(
            "POST",
            "/api/v1/admin/agent-assignments",
            json_data=data,
        )
        return AgentAssignment(**response)

    async def delete_assignment(self, assignment_id: str) -> bool:
        """Revoke an agent-role assignment (DELETE
        /admin/agent-assignments/{id}, returns 204)."""
        await self._http.request(
            "DELETE",
            f"/api/v1/admin/agent-assignments/{encode_path_param(assignment_id)}",
        )
        return True

    async def bulk_delete_assignments(self, ids: list[str]) -> BulkDeleteResult:
        """Bulk-revoke agent-role assignments (POST
        /admin/agent-assignments/bulk-delete)."""
        response = await self._http.request(
            "POST",
            "/api/v1/admin/agent-assignments/bulk-delete",
            json_data={"ids": ids},
        )
        return BulkDeleteResult(**response)

    # -------------------------------------------------------------------
    # Role hierarchy
    # -------------------------------------------------------------------

    async def get_role_hierarchy(self) -> RoleHierarchyResult:
        """Get the organization's role tree (GET
        /admin/roles/hierarchy)."""
        response = await self._http.request(
            "GET",
            "/api/v1/admin/roles/hierarchy",
        )
        return RoleHierarchyResult(**response)

    # -------------------------------------------------------------------
    # Admin Access Visualization
    # -------------------------------------------------------------------

    async def get_access_tree(self) -> AccessTreeResult:
        """Get the role hierarchy with per-agent access flags
        (GET /admin/access/tree)."""
        response = await self._http.request(
            "GET",
            "/api/v1/admin/access/tree",
        )
        return AccessTreeResult(**response)

    async def get_access_matrix(self) -> AccessMatrixResult:
        """Get the role x agent access matrix (GET /admin/access/matrix)."""
        response = await self._http.request(
            "GET",
            "/api/v1/admin/access/matrix",
        )
        return AccessMatrixResult(**response)

    async def get_access_audit(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> AccessAuditResult:
        """Get the access grant/revoke/modify audit trail
        (GET /admin/access/audit).

        Args:
            start_date: Filter to entries at/after this ISO date.
            end_date: Filter to entries at/before this ISO date.
            action: Filter by normalized action ("grant"/"revoke"/"modify").
            target_type: Filter by target type ("agent"/"role"/"user").
            page: Page number (1-indexed).
            page_size: Results per page (max 200).
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if action:
            params["action"] = action
        if target_type:
            params["target_type"] = target_type

        response = await self._http.request(
            "GET",
            "/api/v1/admin/access/audit",
            params=params,
        )
        return AccessAuditResult(**response)

    async def export_access(
        self,
        include_inherited: bool = True,
        date_range: dict[str, str] | None = None,
    ) -> AccessExportResult:
        """Export the current access state as JSON
        (POST /admin/access/export).

        Always requests ``format="json"`` server-side -- see this
        module's docstring "Known limitation" for why ``format="csv"``
        is not exposed here (the shared HTTP transport JSON-decodes
        every 200 response; CSV bytes would raise).

        Args:
            include_inherited: Include role-inherited access rows.
            date_range: Optional {"start": iso_date, "end": iso_date}.
        """
        data: dict[str, Any] = {
            "format": "json",
            "include_inherited": include_inherited,
        }
        if date_range is not None:
            data["date_range"] = date_range

        response = await self._http.request(
            "POST",
            "/api/v1/admin/access/export",
            json_data=data,
        )
        return AccessExportResult(**response)
