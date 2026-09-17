"""
Agentic OS SDK Agents Module.

Provides agent management operations including:
- CRUD: Create, Read, Update, Delete
- Execution: Sync and streaming execution
- Sub-resources: Versions, Contexts, Tools
"""

import builtins
import warnings
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel
from ..exceptions import ValidationError
from .models import (
    Agent,
    AgentCreate,
    AgentExecution,
    AgentUpdate,
    ExecutionStatus,
    PaginatedResponse,
)

if TYPE_CHECKING:
    from .._http import HTTPClient


# ---------------------------------------------------------------------------
# Local response models.
#
# These pin the wire shapes of the routes wired onto AgentsModule below, so a
# serializer change that drops a field is caught by the paired contract test
# rather than silently producing None.
# ---------------------------------------------------------------------------


class TestDraftResult(TolerantModel):
    """Result of a non-persisted draft test execution.

    Mirrors the API's ``TestDraftResponse`` (snake_case emit).
    """

    content: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    finish_reason: str
    thread_id: str
    timestamp: str
    is_test: bool = True


class AccessibleAgent(TolerantModel):
    """An agent the current user can assign objectives to.

    Mirrors the per-record transform the endpoint applies (snake_case emit;
    the endpoint
    returns ``{"records": [...]}`` with no ``total``). Every field is
    optional because the transform reads them off heterogeneous access
    records via ``.get(...)``.
    """

    id: str | None = None
    name: str | None = None
    description: str | None = None
    type: str | None = None
    agent_subtype: str | None = None
    capabilities: Any | None = None
    capabilities_json: str | None = None
    tools_json: str | None = None
    system_prompt: str | None = None
    is_shadow_agent: bool = False
    human_role_id: str | None = None
    organization_unit_id: str | None = None
    status: str | None = None
    workspace_id: str | None = None


class DelegateAgent(TolerantModel):
    """A delegate (shadow) agent summary.

    Mirrors the API's ``DelegateAgentSummary`` (snake_case emit).
    """

    id: str
    name: str
    description: str | None = None
    status: str
    model_id: str
    provider: str = "openai"
    agent_subtype: str = "specialist"
    is_shadow_agent: bool = True
    human_role_id: str | None = None
    shadow_for_user_id: str | None = None
    organization_unit_id: str | None = None
    health_status: str = "healthy"
    created_at: str
    updated_at: str


class DelegateAgentList(TolerantModel):
    """Paginated delegate-agent roster.

    Mirrors the API's ``DelegateAgentListResponse`` (``{records, total}``).
    """

    records: list[DelegateAgent]
    total: int


class DelegateDashboardSummary(TolerantModel):
    """Delegate-agent dashboard rollup.

    Mirrors the summary dict the endpoint returns. The canonical
    ``*_delegate_agents`` keys are typed; the legacy ``*_shadow_agents``
    aliases emitted for one deprecation release pass through via
    ``extra="allow"``.
    """

    model_config = ConfigDict(extra="allow")

    total_delegate_agents: int = 0
    active_delegate_agents: int = 0
    draft_delegate_agents: int = 0
    roles_with_agents: int = 0
    roles_without_agents: int = 0
    healthy_delegate_agents: int = 0
    degraded_delegate_agents: int = 0
    unhealthy_delegate_agents: int = 0


class DelegateAgentCreateResult(TolerantModel):
    """Envelope returned when creating a delegate agent from a role.

    Mirrors the ``{ agent, role, trust_chain }`` envelope the endpoint
    returns. ``trust_chain`` is ``None`` when
    trust establishment fails non-fatally (the agent still exists in
    ``draft`` state).
    """

    agent: dict[str, Any]
    role: dict[str, Any]
    trust_chain: dict[str, Any] | None = None


class DelegateAgentActivityItem(TolerantModel):
    """One entry in a delegate agent's activity log."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    agent_id: str = Field(alias="agentId")
    activity_type: str = Field(alias="activityType")
    description: str
    timestamp: str
    metadata: dict[str, Any] | None = None


class DelegateAgentHealth(TolerantModel):
    """
    A delegate agent's health rollup.

    ``trust_chain_valid`` and ``constraints_violations`` are governance
    signals, not throughput ones: an agent can be healthy by task counts and
    still have an invalid trust chain, so check them separately from
    ``status``.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    status: str
    last_active_at: str | None = Field(None, alias="lastActiveAt")
    tasks_completed: int = Field(0, alias="tasksCompleted")
    tasks_in_progress: int = Field(0, alias="tasksInProgress")
    tasks_failed: int = Field(0, alias="tasksFailed")
    success_rate: float = Field(0.0, alias="successRate")
    avg_response_time_ms: int = Field(0, alias="avgResponseTimeMs")
    trust_chain_valid: bool = Field(True, alias="trustChainValid")
    constraints_violations: int = Field(0, alias="constraintsViolations")
    trust_posture: str = Field("", alias="trustPosture")
    trust_progress_percent: int = Field(0, alias="trustProgressPercent")


class ObjectiveAnalysis(TolerantModel):
    """
    What the platform makes of a stated objective.

    ``recommended_preset`` names a preset from
    :meth:`AgentsModule.list_presets` when the analysis produced one, and is
    None when it did not — an absent recommendation is a normal outcome, not
    an error.
    """

    model_config = ConfigDict(populate_by_name=True)

    objective: str
    domain: str
    complexity: str
    suggestions: builtins.list[Any] = Field(default_factory=list)
    recommended_preset: str | None = None


class AgentStatusItem(TolerantModel):
    """
    One agent's status.

    ``is_stale`` is the field to branch on for liveness: an agent can report a
    healthy ``status`` while ``last_active_at`` is old, and ``is_stale`` is
    the platform's own verdict on that gap.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    status: str
    agent_type: str
    updated_at: str
    is_stale: bool = False
    last_active_at: str | None = None


class AgentStatusList(TolerantModel):
    """A page of agent statuses."""

    model_config = ConfigDict(populate_by_name=True)

    records: builtins.list[AgentStatusItem] = Field(default_factory=list)
    total: int = 0


class SubagentItem(TolerantModel):
    """One subagent belonging to a manager agent."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    type: str
    status: str
    description: str | None = None


class SubagentList(TolerantModel):
    """A manager agent's subagents."""

    model_config = ConfigDict(populate_by_name=True)

    subagents: builtins.list[SubagentItem] = Field(default_factory=list)
    total: int = 0


class DataSourceList(TolerantModel):
    """
    An agent's data sources.

    ``records`` holds the backend-shaped data-source payloads; the platform
    declares the envelope but the entries vary by source type.
    """

    model_config = ConfigDict(populate_by_name=True)

    records: builtins.list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ManifestGovernance(TolerantModel):
    """
    The governance envelope a manifest registration establishes.

    ``budget_monthly_usd`` is a STRING on the wire, not a number — it is a
    decimal amount and is carried as text to avoid float rounding. Parse it
    with ``decimal.Decimal``, never ``float``.
    """

    model_config = ConfigDict(populate_by_name=True)

    posture_ceiling: str
    budget_monthly_usd: str
    constraints: dict[str, Any] | None = None


class ManifestRegistration(TolerantModel):
    """
    The result of registering an agent from a manifest.

    ``governance`` is the enforced envelope the agent is created under — the
    posture ceiling and monthly budget come from the manifest, so a manifest
    that omits them takes the platform's defaults rather than being
    unconstrained.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str
    name: str
    status: str
    agent_card: dict[str, Any] = Field(default_factory=dict)
    governance: ManifestGovernance


class PipelineExecutionStart(TolerantModel):
    """Result of starting a pipeline execution.

    Mirrors the API's ``StartExecutionResponse`` (camelCase emit —
    ``executionId``).
    """

    model_config = ConfigDict(populate_by_name=True)

    execution_id: str = Field(alias="executionId")


class PipelineNodeExecution(TolerantModel):
    """A single node's execution status within a pipeline run.

    Mirrors the API's ``NodeExecution`` (camelCase emit).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    node_id: str = Field(alias="nodeId")
    status: str
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    error: str | None = None
    output: Any | None = None


class PipelineExecutionLog(TolerantModel):
    """A single log entry from a pipeline run.

    Mirrors the API's ``ExecutionLog`` (camelCase ``nodeId``).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    timestamp: str
    level: str
    message: str
    node_id: str | None = Field(default=None, alias="nodeId")
    data: dict[str, Any] | None = None


class PipelineExecutionStatus(TolerantModel):
    """Full status of a pipeline execution run.

    Mirrors the API's ``ExecutionStatusResponse`` and the
    structurally-identical
    ``ExecutionHistoryItem`` (``:97-111``) — both camelCase emit.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    pipeline_id: str = Field(alias="pipelineId")
    status: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    logs: list[PipelineExecutionLog] = Field(default_factory=list)
    node_executions: list[PipelineNodeExecution] = Field(
        default_factory=list, alias="nodeExecutions"
    )
    start_time: str = Field(alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    error: str | None = None


class PipelineExecutionHistory(TolerantModel):
    """Paginated pipeline-execution history for one pipeline.

    Mirrors the API's ``ExecutionHistoryResponse``. NOTE: the envelope keys
    ``total`` / ``page`` / ``page_size`` are snake_case (the response model
    declares no aliases on them), while each per-execution item is camelCase.
    """

    model_config = ConfigDict(populate_by_name=True)

    executions: list[PipelineExecutionStatus]
    total: int
    page: int
    page_size: int


class AgentVersionsModule:
    """
    Agent version management.

    SDK-only feature for version history and rollback.
    """

    def __init__(self, http_client: "HTTPClient"):
        self._http = http_client

    async def list(self, agent_id: str) -> list[dict[str, Any]]:
        """
        List version history for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of version records
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/versions"
        )
        return response

    async def get(self, agent_id: str, version: int) -> dict[str, Any]:
        """
        Get specific version of an agent.

        Args:
            agent_id: Agent ID
            version: Version number

        Returns:
            Version record with agent state at that version
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/versions/{encode_path_param(version)}",
        )
        return response

    async def create(self, agent_id: str, changelog: str | None = None) -> dict[str, Any]:
        """
        Create a version snapshot of the current agent configuration.

        Args:
            agent_id: Agent ID
            changelog: Optional description of what changed in this version

        Returns:
            Created version record with version number and snapshot
        """
        # Always a JSON object, never an absent body: ``CreateVersionRequest``
        # is a REQUIRED body parameter on the route even though every field in
        # it is optional, so sending no body at all is refused with 422.
        json_data: dict[str, Any] = {}
        if changelog:
            json_data["changelog"] = changelog

        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/versions",
            json_data=json_data,
        )
        return response

    async def rollback(self, agent_id: str, version: int) -> Agent:
        """
        Rollback agent to a previous version.

        Args:
            agent_id: Agent ID
            version: Target version number

        Returns:
            Updated Agent at the specified version
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/versions/{encode_path_param(version)}/rollback",
        )
        return Agent(**response)


class AgentContextsModule:
    """
    Agent context management.

    SDK-only feature for managing agent execution contexts.
    """

    def __init__(self, http_client: "HTTPClient"):
        self._http = http_client

    async def list(self, agent_id: str) -> list[dict[str, Any]]:
        """
        List contexts for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of context objects
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/contexts"
        )
        return response

    async def create(
        self,
        agent_id: str,
        name: str,
        config: dict[str, Any] | None = None,
        *,
        content_type: Literal["text", "file", "url"] | None = None,
        content: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        """
        Create new context for agent.

        Verified against ``AddContextRequest``
        (``POST /api/v1/agents/{agent_id}/contexts``), which requires ``name``,
        ``content_type`` and ``content``.

        Args:
            agent_id: Agent ID
            name: Context name (1-100 characters)
            config: DEPRECATED. Never a field the server reads: every call that
                sent it was refused with 422. Passing it emits
                ``DeprecationWarning``; it will be removed in the next minor
                release. Use ``content_type`` and ``content``.
            content_type: One of ``text``, ``file``, ``url`` (required)
            content: The context content (required, non-empty)
            is_active: Whether the context is active (default True)

        Returns:
            Created context object

        Raises:
            ValueError: If ``content_type`` or ``content`` is missing -- raised
                before any request
        """
        if config is not None:
            warnings.warn(
                "AgentContextsModule.create(config=...) is deprecated: the server has "
                "no `config` field for a context and refused every such call with "
                "422. Pass content_type= and content= instead; `config` will be "
                "removed in the next minor release.",
                DeprecationWarning,
                stacklevel=2,
            )
        if content_type is None or not content:
            raise ValueError(
                "contexts.create() requires content_type ('text', 'file' or 'url') and "
                "a non-empty content -- the server's AddContextRequest requires both"
            )
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/contexts",
            json_data={
                "name": name,
                "content_type": content_type,
                "content": content,
                "is_active": is_active,
            },
        )
        return response

    async def get(self, agent_id: str, context_id: str) -> dict[str, Any]:
        """
        Get specific context.

        Args:
            agent_id: Agent ID
            context_id: Context ID

        Returns:
            Context object
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/contexts/{encode_path_param(context_id)}",
        )
        return response

    async def update(
        self,
        agent_id: str,
        context_id: str,
        name: str | None = None,
        content_type: str | None = None,
        content: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """
        Update context.

        Args:
            agent_id: Agent ID
            context_id: Context ID
            name: Optional new context name
            content_type: Optional new content type (text/file/url)
            content: Optional new content
            is_active: Optional active flag

        Returns:
            Updated context object

        Raises:
            ValueError: If no field is supplied -- raised before any request
        """
        json_data: dict[str, Any] = {}
        if name is not None:
            json_data["name"] = name
        if content_type is not None:
            json_data["content_type"] = content_type
        if content is not None:
            json_data["content"] = content
        if is_active is not None:
            json_data["is_active"] = is_active

        # Never a bodiless PUT. ``UpdateContextRequest`` is a REQUIRED body
        # parameter on the route, so omitting the body is refused by FastAPI
        # with 422 before the handler runs -- the same defect
        # ``versions.create()`` carried, in this same file, and fixed one cycle
        # earlier. An EMPTY object is a different and correct refusal (the
        # handler answers 400 "No fields to update"), so there is nothing to
        # gain from a round trip: refuse here, and say which fields would work.
        if not json_data:
            raise ValueError(
                "contexts.update() requires at least one field to change "
                "(name, content_type, content or is_active) -- the server's "
                "UpdateContextRequest body is required"
            )

        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}/contexts/{encode_path_param(context_id)}",
            json_data=json_data,
        )
        return response

    async def delete(self, agent_id: str, context_id: str) -> None:
        """
        Delete context.

        Args:
            agent_id: Agent ID
            context_id: Context ID
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/agents/{encode_path_param(agent_id)}/contexts/{encode_path_param(context_id)}",
        )


class AgentToolsModule:
    """
    Agent tools management.

    SDK-only feature for managing agent tool configurations.
    """

    def __init__(self, http_client: "HTTPClient"):
        self._http = http_client

    async def list(self, agent_id: str) -> list[dict[str, Any]]:
        """
        List tools assigned to an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of tool configurations
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/tools"
        )
        return response

    async def add(
        self,
        agent_id: str,
        tool_type: Literal["function", "mcp", "api"],
        config: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        is_enabled: bool = True,
    ) -> dict[str, Any]:
        """
        Add tool to agent.

        Verified against ``AddToolRequest``
        (``POST /api/v1/agents/{agent_id}/tools``), which requires ``tool_type``,
        ``name`` and ``description``. An MCP binding that references a shared
        server registration (``config["mcpServerId"]``) must not also carry
        inline ``url``/``headers``/``command``; the server refuses that with 422.

        Args:
            agent_id: Agent ID
            tool_type: One of ``function``, ``mcp``, ``api``
            config: Tool configuration (default ``{}``)
            name: Tool name, 1-100 characters (required)
            description: Tool description, 1-500 characters (required)
            is_enabled: Whether the tool is enabled (default True)

        Returns:
            Created tool assignment

        Raises:
            ValueError: If ``name`` or ``description`` is missing -- raised
                before any request
        """
        if not name or not description:
            raise ValueError(
                "tools.add() requires name and description -- the server's "
                "AddToolRequest requires both (name 1-100 characters, "
                "description 1-500)"
            )
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/tools",
            json_data={
                "tool_type": tool_type,
                "name": name,
                "description": description,
                "config": config if config is not None else {},
                "is_enabled": is_enabled,
            },
        )
        return response

    async def remove(self, agent_id: str, tool_id: str) -> None:
        """
        Remove tool from agent.

        Args:
            agent_id: Agent ID
            tool_id: Tool assignment ID
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/agents/{encode_path_param(agent_id)}/tools/{encode_path_param(tool_id)}",
        )

    async def update(
        self,
        agent_id: str,
        tool_id: str,
        config: dict[str, Any] | None = None,
        *,
        tool_type: Literal["function", "mcp", "api"] | None = None,
        name: str | None = None,
        description: str | None = None,
        is_enabled: bool | None = None,
    ) -> dict[str, Any]:
        """
        Update tool configuration.

        Verified against ``UpdateToolRequest``
        (``PUT /api/v1/agents/{agent_id}/tools/{tool_id}``), every field of
        which is optional -- but the BODY is required, and the handler answers
        400 ``No fields to update`` for an empty one. Until now this method
        sent ``{"config": ...}`` and nothing else, so the other four fields the
        route accepts were unreachable from the SDK: a partner could not rename
        a tool, re-describe it, change its type, or disable it.

        An MCP binding that references a shared server registration
        (``config["mcpServerId"]``) must not also carry inline
        ``url``/``headers``/``command``; the server refuses that with 422.

        Args:
            agent_id: Agent ID
            tool_id: Tool assignment ID
            config: Updated configuration
            tool_type: New tool type (``function``, ``mcp``, ``api``)
            name: New tool name, 1-100 characters
            description: New tool description, 1-500 characters
            is_enabled: Whether the tool is enabled

        Returns:
            Updated tool assignment

        Raises:
            ValueError: If no field is supplied -- raised before any request
        """
        json_data: dict[str, Any] = {}
        if config is not None:
            json_data["config"] = config
        if tool_type is not None:
            json_data["tool_type"] = tool_type
        if name is not None:
            json_data["name"] = name
        if description is not None:
            json_data["description"] = description
        if is_enabled is not None:
            json_data["is_enabled"] = is_enabled

        if not json_data:
            raise ValueError(
                "tools.update() requires at least one field to change "
                "(config, tool_type, name, description or is_enabled) -- the "
                "server's UpdateToolRequest body is required"
            )

        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}/tools/{encode_path_param(tool_id)}",
            json_data=json_data,
        )
        return response


class AgentsModule:
    """
    Agent management operations.

    Provides full lifecycle management for agents including:
    - CRUD operations (create, read, update, delete, list)
    - Execution (sync and streaming)
    - Duplication
    - Sub-resource management (versions, contexts, tools)

    Example:
        >>> import os
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # List agents
        ...     agents = await client.agents.list()
        ...
        ...     # Create agent (agent_type: chat/task/pipeline/custom;
        ...     # model_id read from your own env — never hardcode a model)
        ...     agent = await client.agents.create(
        ...         name="Research Assistant",
        ...         agent_type="chat",
        ...         model_id=os.environ["AGENTIC_OS_MODEL"],
        ...     )
        ...
        ...     # Execute agent
        ...     result = await client.agents.execute(
        ...         agent.id,
        ...         objective="Research quantum computing"
        ...     )
    """

    def __init__(self, http_client: "HTTPClient"):
        """
        Initialize agents module.

        Args:
            http_client: Internal HTTP client instance
        """
        self._http = http_client

        # Initialize sub-modules
        self.versions = AgentVersionsModule(http_client)
        self.contexts = AgentContextsModule(http_client)
        self.tools = AgentToolsModule(http_client)

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    async def list(
        self,
        workspace_id: str | None = None,
        status: str | None = None,
        agent_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[Agent]:
        """
        List agents with optional filters.

        Args:
            workspace_id: Filter by workspace
            status: Filter by status (draft, active, archived, deprecated,
                suspended, revoked)
            agent_type: Filter by type (chat, task, pipeline, custom)
            page: Page number (1-indexed)
            page_size: Items per page (max 100)

        Returns:
            PaginatedResponse containing Agent objects

        Example:
            >>> result = await client.agents.list(status="active", page_size=20)
            >>> print(f"Found {result.total} active agents")
            >>> for agent in result.items:
            ...     print(f"  - {agent.name}")
        """
        # Server pagination is limit/offset,
        # NOT page/page_size -- sending page/page_size (the prior behavior)
        # was silently ignored by FastAPI's declared-params matching, so
        # every call returned the server's default first page regardless of
        # the caller's requested page.
        offset = (page - 1) * page_size
        params: dict[str, Any] = {"limit": page_size, "offset": offset}
        if workspace_id:
            params["workspace_id"] = workspace_id
        if status:
            params["status"] = status
        if agent_type:
            params["agent_type"] = agent_type

        response = await self._http.request("GET", "/api/v1/agents", params=params)

        # Server response is {"records": [...], "total": N}
        # (AgentListResponse) -- NOT
        # {"items": [...], "page": ..., "page_size": ..., "has_next": ...}.
        # Reading "items" from that envelope always returned [] regardless
        # of how many agents existed.
        records = response.get("records", [])
        total = response.get("total", len(records))
        return PaginatedResponse[Agent](
            items=[Agent(**item) for item in records],
            total=total,
            page=page,
            page_size=page_size,
            has_next=(offset + len(records)) < total,
        )

    async def create(
        self,
        name: str,
        agent_type: str = "chat",
        **kwargs: Any,
    ) -> Agent:
        """
        Create a new agent.

        Args:
            name: Agent name
            agent_type: Behavioral type — one of ``chat``, ``task``,
                ``pipeline``, ``custom`` (server pattern; default ``chat``, the
                conversational assistant a vertical's first agent usually is).
                This is DISTINCT from ``unit_type`` (atomic/composite).
            **kwargs: Additional fields accepted by the server
                ``CreateAgentRequest`` — ``workspace_id``, ``model_id``,
                ``description``, ``system_prompt``, ``temperature``,
                ``max_tokens``, ``instructions``, ``unit_type``,
                ``agent_subtype``, ``provider``, ``capabilities`` (list, →
                ``capabilities_json``), ``capabilities_json``, ``tools_json``,
                ``a2a_enabled``, ``orchestration_config``, ``is_shadow_agent``,
                ``shadow_for_user_id``, ``human_role_id``,
                ``organization_unit_id``, ``id``.

        Returns:
            Created Agent object

        Raises:
            ValidationError: If required fields missing or invalid — including
                client-side pre-flight validation of ``model_id`` /
                ``workspace_id``, which the server's ``CreateAgentRequest``
                requires even though
                :class:`~aegis_sdk.types.AgentCreate` declares them
                ``Optional`` for wire-shape flexibility. Sending either as
                ``None``/omitted previously round-tripped to the server and
                came back as an opaque 422; failing fast client-side turns
                that into an actionable message.
            AuthorizationError: If not allowed to create agents

        Example:
            >>> import os
            >>> # Stand up a vertical's first (delegate) agent
            >>> agent = await client.agents.create(
            ...     name="My Assistant",
            ...     agent_type="chat",
            ...     workspace_id="ws_123",
            ...     model_id=os.environ["AGENTIC_OS_MODEL"],  # never hardcode a model
            ...     system_prompt="You are a helpful assistant.",
            ...     capabilities=["research", "summarization"],
            ...     is_shadow_agent=True,
            ...     shadow_for_user_id="user_42",
            ...     human_role_id="role_7",
            ...     organization_unit_id="unit_3",
            ... )
        """
        # Server-required (CreateAgentRequest):
        # model_id: str = Field(..., min_length=1) and workspace_id: str
        # (no default). aegis_sdk.types.AgentCreate declares both Optional
        # for wire-shape flexibility, so pydantic can't catch the omission —
        # validate here to fail fast with an actionable message instead of
        # an opaque 422 round-trip.
        if not kwargs.get("model_id"):
            raise ValidationError(
                "agents.create() requires 'model_id' — the server's "
                "CreateAgentRequest.model_id is required (never hardcode a "
                "model string; read it from your own env, e.g. "
                "os.environ['AGENTIC_OS_MODEL'])."
            )
        if not kwargs.get("workspace_id"):
            raise ValidationError(
                "agents.create() requires 'workspace_id' — the server's "
                "CreateAgentRequest.workspace_id is required."
            )
        create_data = AgentCreate(name=name, agent_type=agent_type, **kwargs)
        response = await self._http.request(
            "POST",
            "/api/v1/agents",
            json_data=create_data.to_request_body(),
        )
        return Agent(**response)

    async def get(self, agent_id: str) -> Agent:
        """
        Get agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent object

        Raises:
            NotFoundError: If agent doesn't exist

        Example:
            >>> agent = await client.agents.get("agent_abc123")
            >>> print(f"Agent: {agent.name} ({agent.status})")
        """
        response = await self._http.request("GET", f"/api/v1/agents/{encode_path_param(agent_id)}")
        return Agent(**response)

    async def update(self, agent_id: str, **kwargs: Any) -> Agent:
        """
        Update agent fields.

        Args:
            agent_id: Agent ID
            **kwargs: Fields to update (name, status, model_id,
                     system_prompt, capabilities, a2a_enabled, description)

        Returns:
            Updated Agent object

        Raises:
            NotFoundError: If agent doesn't exist
            ValidationError: If update data is invalid

        Example:
            >>> agent = await client.agents.update(
            ...     "agent_abc123",
            ...     name="Updated Name",
            ...     status="active"
            ... )
        """
        update_data = AgentUpdate(**kwargs)
        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}",
            json_data=update_data.to_request_body(),
        )
        return Agent(**response)

    async def delete(self, agent_id: str) -> None:
        """
        Delete agent.

        Args:
            agent_id: Agent ID

        Raises:
            NotFoundError: If agent doesn't exist
            AuthorizationError: If not allowed to delete

        Example:
            >>> await client.agents.delete("agent_abc123")
        """
        await self._http.request("DELETE", f"/api/v1/agents/{encode_path_param(agent_id)}")

    async def duplicate(self, agent_id: str, name: str) -> Agent:
        """
        Duplicate an existing agent.

        Creates a copy of the agent with a new name and ID.
        All configurations are copied except execution history.

        Args:
            agent_id: Source agent ID
            name: Name for the duplicated agent

        Returns:
            New Agent object (copy)

        Raises:
            NotFoundError: If source agent doesn't exist

        Example:
            >>> copy = await client.agents.duplicate(
            ...     "agent_abc123",
            ...     name="My Assistant (Copy)"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/duplicate",
            json_data={"name": name},
        )
        return Agent(**response)

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    async def execute(
        self,
        agent_id: str,
        message: str,
        context: dict[str, Any] | None = None,
        conversation_history: builtins.list[dict[str, Any]] | None = None,
        thread_id: str | None = None,
    ) -> AgentExecution:
        """
        Execute agent with a message.

        Verified against ``ExecuteAgentRequest``
        / ``ExecuteAgentResponse`` (``POST /api/v1/agents/{agent_id}/execute``).
        This is a synchronous chat-completion call. The request body key is
        ``message`` (not ``objective``), and there is no ``wait`` concept —
        the call either completes synchronously or raises.

        Args:
            agent_id: Agent ID
            message: User message to send to the agent
            context: Optional caller-supplied context injected into the
                agent's system prompt
            conversation_history: Optional previous conversation messages
            thread_id: Optional client-owned conversation thread ID, echoed
                back for correlation (server generates one when unset)

        Returns:
            AgentExecution — adapted from the server's flat
            ``{content, model, usage, finish_reason, thread_id, timestamp}``
            response. Because the call is synchronous, ``status`` is always
            ``ExecutionStatus.COMPLETED`` on success; ``id`` is populated
            from the response ``thread_id``. Executions are not persisted as
            separate, individually-addressable records, so there is nothing to
            poll, list or cancel afterwards — see :meth:`get_execution`,
            :meth:`list_executions` and :meth:`cancel_execution`.

        Raises:
            NotFoundError: If agent doesn't exist
            GovernanceViolationError: If execution blocked by governance

        Example:
            >>> result = await client.agents.execute(
            ...     "agent_abc123",
            ...     message="Research quantum computing and summarize findings",
            ...     context={"focus_area": "algorithms"}
            ... )
            >>> print(f"Status: {result.status}")
            >>> print(f"Result: {result.result['content']}")
        """
        json_data: dict[str, Any] = {"message": message}
        if context is not None:
            json_data["context"] = context
        if conversation_history is not None:
            json_data["conversation_history"] = conversation_history
        if thread_id is not None:
            json_data["thread_id"] = thread_id

        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/execute",
            json_data=json_data,
        )
        return AgentExecution(
            id=response.get("thread_id", ""),
            agent_id=agent_id,
            status=ExecutionStatus.COMPLETED,
            objective=message,
            context=context or {},
            result={
                "content": response.get("content"),
                "model": response.get("model"),
                "usage": response.get("usage", {}),
                "finish_reason": response.get("finish_reason"),
            },
            completed_at=response.get("timestamp"),
        )

    async def stream(
        self,
        agent_id: str,
        message: str,
        context: dict[str, Any] | None = None,
        conversation_history: builtins.list[dict[str, Any]] | None = None,
        thread_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream agent execution with real-time events.

        Uses Server-Sent Events (SSE) to stream execution progress. Verified
        against ``execute_agent_stream``
        (``POST /api/v1/agents/{agent_id}/execute/stream``) — the request
        body is the same ``ExecuteAgentRequest`` shape as :meth:`execute`
        (``message``, NOT ``objective``), and each emitted SSE event carries
        its kind under the key ``type`` (NOT ``event_type``).

        Args:
            agent_id: Agent ID
            message: User message to send to the agent
            context: Optional caller-supplied context injected into the
                agent's system prompt
            conversation_history: Optional previous conversation messages
            thread_id: Optional client-owned conversation thread ID

        Yields:
            Execution events, each a dict with a ``type`` key.

        Event Types (server-emitted):
            - ``start``: Stream started (``thread_id``, ``model``, ``timestamp``)
            - ``content``: A streamed content chunk (``content``, ``thread_id``)
            - ``done``: Execution completed (``thread_id``, ``timestamp``)
            - ``error``: Execution failed (``error``, ``thread_id``)

        Example:
            >>> async for event in client.agents.stream(
            ...     "agent_abc123",
            ...     message="Write a poem about AI"
            ... ):
            ...     if event["type"] == "content":
            ...         print(event["content"], end="", flush=True)
            ...     elif event["type"] == "done":
            ...         print("\\nDone!")
        """
        json_data: dict[str, Any] = {"message": message}
        if context is not None:
            json_data["context"] = context
        if conversation_history is not None:
            json_data["conversation_history"] = conversation_history
        if thread_id is not None:
            json_data["thread_id"] = thread_id

        async for event in self._http.stream(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/execute/stream",
            json_data=json_data,
        ):
            yield event

    async def get_execution(self, agent_id: str, execution_id: str) -> AgentExecution:
        """
        Get execution status/result by ID.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/agents/{agent_id}/executions/{execution_id}`` is not
            served. Agent execution is a synchronous request/response and is
            not persisted as an individually-addressable record, so there is
            nothing to retrieve by id. Use :meth:`execute`, whose return value
            carries the result directly.

        Args:
            agent_id: Agent ID
            execution_id: Execution ID

        Returns:
            AgentExecution with status and result

        Raises:
            NotFoundError: If execution doesn't exist
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/executions/{encode_path_param(execution_id)}",
        )
        return AgentExecution(**response)

    async def list_executions(
        self,
        agent_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[AgentExecution]:
        """
        List executions for an agent.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/agents/{agent_id}/executions`` is not served; agent
            executions are not persisted as listable records. See
            :meth:`get_execution`.

        Args:
            agent_id: Agent ID
            status: Filter by status
            page: Page number
            page_size: Items per page

        Returns:
            PaginatedResponse of AgentExecution objects
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/executions",
            params=params,
        )

        return PaginatedResponse[AgentExecution](
            items=[AgentExecution(**item) for item in response.get("items", [])],
            total=response.get("total", 0),
            page=response.get("page", page),
            page_size=response.get("page_size", page_size),
            has_next=response.get("has_next", False),
        )

    async def cancel_execution(self, agent_id: str, execution_id: str) -> None:
        """
        Cancel a running execution.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``POST /api/v1/agents/{agent_id}/executions/{execution_id}/cancel``
            is not served. Agent execution is synchronous, so there is no
            in-flight execution to cancel. See :meth:`get_execution`.

        Args:
            agent_id: Agent ID
            execution_id: Execution ID to cancel

        Raises:
            NotFoundError: If execution doesn't exist
            ValidationError: If execution already completed
        """
        await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/executions/{encode_path_param(execution_id)}/cancel",
        )

    # -------------------------------------------------------------------------
    # Draft testing
    # -------------------------------------------------------------------------

    async def test_draft(
        self,
        agent_id: str,
        message: str,
        draft_instructions_json: dict[str, Any] | None = None,
        draft_system_prompt: str | None = None,
        conversation_history: builtins.list[dict[str, Any]] | None = None,
    ) -> TestDraftResult:
        """
        Test an agent with draft prompt/instructions WITHOUT persisting changes.

        Lets a PM try configuration changes before saving. Runs against a
        separate, per-request test budget (capped server-side); nothing is
        written. Verified against
        ``TestDraftRequest`` /
        ``TestDraftResponse`` (``POST /api/v1/agents/{agent_id}/test-draft``).

        Args:
            agent_id: Agent ID
            message: Test input message
            draft_instructions_json: Draft structured instructions to use
                instead of the saved ones (merged into the system prompt)
            draft_system_prompt: Draft system prompt to use instead of the
                saved one
            conversation_history: Previous conversation messages
                (``role`` must be ``user`` or ``assistant`` — ``system`` is
                rejected server-side)

        Returns:
            TestDraftResult: content + model + usage + finish_reason +
            thread_id + timestamp (``is_test`` always ``True``)

        Raises:
            NotFoundError: If the agent doesn't exist / belongs to another org
            ValidationError: If the agent is archived (cannot be tested)
        """
        json_data: dict[str, Any] = {"message": message}
        if draft_instructions_json is not None:
            json_data["draft_instructions_json"] = draft_instructions_json
        if draft_system_prompt is not None:
            json_data["draft_system_prompt"] = draft_system_prompt
        if conversation_history is not None:
            json_data["conversation_history"] = conversation_history

        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/test-draft",
            json_data=json_data,
        )
        return TestDraftResult(**response)

    async def list_accessible(self, search: str = "") -> builtins.list[AccessibleAgent]:
        """
        List agents the current user can assign objectives to.

        Drives the objective-assignment agent picker — returns the agents
        within the caller's authority scope, optionally name/description
        filtered. Verified against
        ``get_accessible_agents``
        (``GET /api/v1/agents/accessible``). The envelope is
        ``{"records": [...]}`` with NO ``total``.

        Args:
            search: Optional case-insensitive filter over name + description

        Returns:
            list[AccessibleAgent]
        """
        params: dict[str, Any] = {}
        if search:
            params["search"] = search

        response = await self._http.request(
            "GET", "/api/v1/agents/accessible", params=params or None
        )
        return [AccessibleAgent(**r) for r in response.get("records", [])]

    # -------------------------------------------------------------------------
    # Delegate (shadow) agents
    # -------------------------------------------------------------------------

    async def list_delegate_agents(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> DelegateAgentList:
        """
        List delegate (shadow) agents for the current user's organization.

        Filtered by role-hierarchy visibility (fail-closed — an empty list is
        returned if the visibility check fails). Verified against
        ``list_shadow_agents``
        (``GET /api/v1/delegate-agents``).

        Args:
            limit: Maximum results (1-200)
            offset: Pagination offset
            status: Optional lifecycle filter — one of ``draft``/``active``/
                ``archived``/``deprecated``/``suspended``/``revoked``. All six
                are accepted; an earlier revision of this docstring named only
                the first three, which under-reported the filter by half.

        Returns:
            DelegateAgentList: records + total

        Note:
            The server also accepts an ``include_archived`` flag on this route
            and this method does not expose it, so archived delegate agents
            cannot be listed here. ``list_delegate_agents_for_unit`` does wire
            it. Until that gap closes, filter with ``status="archived"``.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/delegate-agents", params=params)
        return DelegateAgentList(
            records=[DelegateAgent(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def get_delegate_dashboard_summary(
        self, organization_id: str
    ) -> DelegateDashboardSummary:
        """
        Get the delegate-agent dashboard rollup for an organization.

        Verified against
        ``get_shadow_agents_dashboard_summary``
        (``GET /api/v1/delegate-agents/dashboard-summary``). The
        ``organization_id`` query param is validated server-side against the
        caller's tenant (IDOR guard — a mismatch returns 404).

        Args:
            organization_id: The caller's organization ID

        Returns:
            DelegateDashboardSummary: counts by status + health + role coverage
        """
        response = await self._http.request(
            "GET",
            "/api/v1/delegate-agents/dashboard-summary",
            params={"organization_id": organization_id},
        )
        return DelegateDashboardSummary(**response)

    async def create_delegate_agent(
        self,
        role_id: str,
        name: str | None = None,
        description: str | None = None,
        provider: str | None = None,
        model_id: str | None = None,
        system_prompt: str | None = None,
        instructions: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> DelegateAgentCreateResult:
        """
        Create a delegate agent from an organization role (Deploy Organization).

        Establishes a trust chain and links the role → agent. Verified against
        ``create_shadow_agent`` /
        ``CreateDelegateAgentRequest`` (``POST /api/v1/delegate-agents``).

        PACT constraints (enforced server-side): the target role must
        RESOLVE and belong to the caller's tenant (Rule 21); external/BOD roles
        receive governance-only agents (Rule 5). An earlier revision of this
        docstring also required the role to be non-vacant — that requirement is
        retracted and the server no longer refuses a vacant role, so an SDK
        caller that pre-checks occupancy is blocking a call the API now accepts.

        Args:
            role_id: OrganizationRole ID to attach the delegate agent to
            name: Optional agent name (defaults to ``Delegate: <role title>``)
            description: Optional description
            provider: Optional LLM provider — one of ``openai``/``anthropic``/
                ``google``/``azure``/``custom``
            model_id: Optional LLM model identifier (read from your own env;
                never hardcode a model string)
            system_prompt: Optional system prompt
            instructions: Optional structured instructions object
            temperature: Optional sampling temperature (0.0-2.0)
            max_tokens: Optional max completion tokens

        Returns:
            DelegateAgentCreateResult: ``{ agent, role, trust_chain }``

        Raises:
            NotFoundError: If the role doesn't exist / belongs to another org
            ValidationError: If the role cannot be RESOLVED (422). Not vacancy —
                a vacant role is accepted; see the retraction noted above.
        """
        data: dict[str, Any] = {"role_id": role_id}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if provider is not None:
            data["provider"] = provider
        if model_id is not None:
            data["model_id"] = model_id
        if system_prompt is not None:
            data["system_prompt"] = system_prompt
        if instructions is not None:
            data["instructions"] = instructions
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens

        response = await self._http.request("POST", "/api/v1/delegate-agents", json_data=data)
        return DelegateAgentCreateResult(**response)

    async def activate_delegate_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Activate a delegate agent (draft/suspended → active).

        Fails closed (422) unless an established trust chain exists. Verified
        against ``activate_shadow_agent``
        (``POST /api/v1/delegate-agents/{agent_id}/activate``).

        Args:
            agent_id: Delegate agent ID

        Returns:
            dict: The updated agent record (raw service shape)

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
            ValidationError: If no trust chain is established (422) or the FSM
                transition is illegal
        """
        return await self._http.request(
            "POST", f"/api/v1/delegate-agents/{encode_path_param(agent_id)}/activate"
        )

    async def deactivate_delegate_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Deactivate a delegate agent (→ archived).

        ``archived`` is the canonical inactive status for delegate agents.
        Verified against ``deactivate_shadow_agent``
        (``POST /api/v1/delegate-agents/{agent_id}/deactivate``).

        Args:
            agent_id: Delegate agent ID

        Returns:
            dict: The updated agent record (raw service shape)

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
            ValidationError: If the FSM transition is illegal
        """
        return await self._http.request(
            "POST", f"/api/v1/delegate-agents/{encode_path_param(agent_id)}/deactivate"
        )


    async def list_delegate_agents_for_unit(
        self, unit_id: str, include_archived: bool = False
    ) -> dict[str, Any]:
        """
        List the delegate agents attached to one organization unit.

        Archived agents are excluded unless ``include_archived`` is set.

        Args:
            unit_id: OrganizationUnit ID
            include_archived: Include archived delegate agents

        Returns:
            dict: The roster payload (raw service shape)

        Raises:
            NotFoundError: If the unit doesn't exist / belongs to another org
        """
        payload: dict[str, Any] = await self._http.request(
            "GET",
            f"/api/v1/delegate-agents/for-unit/{encode_path_param(unit_id)}",
            params={"include_archived": include_archived},
        )
        return payload

    async def get_delegate_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Get one delegate agent.

        Args:
            agent_id: Delegate agent ID

        Returns:
            dict: The agent record (raw service shape)

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/delegate-agents/{encode_path_param(agent_id)}"
        )
        return payload

    async def update_delegate_agent(
        self,
        agent_id: str,
        name: str | None = None,
        description: str | None = None,
        provider: str | None = None,
        model_id: str | None = None,
        system_prompt: str | None = None,
        instructions: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools_json: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a delegate agent's configuration.

        Only the arguments supplied are sent, so omitting one leaves the
        stored value untouched rather than clearing it. The bound role is not
        updatable here — the role→agent link is established at creation.

        Args:
            agent_id: Delegate agent ID
            name: New name
            description: New description
            provider: New LLM provider
            model_id: New model identifier (read from your own env; never
                hardcode a model string)
            system_prompt: New system prompt
            instructions: New structured instructions
            temperature: New sampling temperature (0.0-2.0)
            max_tokens: New response token ceiling
            tools_json: New tool configuration, as a JSON string

        Returns:
            dict: The updated agent record (raw service shape)

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
            ValidationError: If a field fails server-side validation
        """
        candidates = {
            "name": name,
            "description": description,
            "provider": provider,
            "model_id": model_id,
            "system_prompt": system_prompt,
            "instructions": instructions,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools_json": tools_json,
        }
        data = {k: v for k, v in candidates.items() if v is not None}
        payload: dict[str, Any] = await self._http.request(
            "PATCH",
            f"/api/v1/delegate-agents/{encode_path_param(agent_id)}",
            json_data=data,
        )
        return payload

    async def delete_delegate_agent(self, agent_id: str) -> str:
        """
        Soft-retire a delegate agent (status -> ``archived``).

        ⛔ **This does NOT remove the agent, and it is NOT recoverable.** An
        earlier revision of this docstring said it "removes" the agent, in
        contrast to ``deactivate_delegate_agent``. Both statements were wrong:
        the two calls reach the SAME end state, ``archived``, and the platform
        deliberately does not expose a hard delete — the agent participates in
        audit-trail and trust-chain records that must survive for forensic
        queries.

        ``archived`` is TERMINAL and the server enforces it: there is no
        transition out, so ``activate_delegate_agent`` on an archived agent
        fails with 422. Recovering the capability means provisioning a NEW
        delegate agent, not reviving this one.

        Args:
            agent_id: Delegate agent ID

        Returns:
            str: The platform's confirmation message

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
        """
        response: dict[str, Any] = await self._http.request(
            "DELETE", f"/api/v1/delegate-agents/{encode_path_param(agent_id)}"
        )
        message: str = response.get("message", "")
        return message

    async def get_delegate_agent_activity(
        self, agent_id: str, limit: int = 50, offset: int = 0
    ) -> builtins.list[DelegateAgentActivityItem]:
        """
        Get a delegate agent's activity log.

        Args:
            agent_id: Delegate agent ID
            limit: Page size
            offset: Page offset

        Returns:
            list[DelegateAgentActivityItem]: Activity entries, most recent first

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/delegate-agents/{encode_path_param(agent_id)}/activity",
            params={"limit": limit, "offset": offset},
        )
        return [DelegateAgentActivityItem(**item) for item in response]

    async def get_delegate_agent_health(self, agent_id: str) -> DelegateAgentHealth:
        """
        Get a delegate agent's health rollup.

        Args:
            agent_id: Delegate agent ID

        Returns:
            DelegateAgentHealth: Throughput counters plus the governance
            signals ``trust_chain_valid`` and ``constraints_violations``

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
        """
        response = await self._http.request(
            "GET", f"/api/v1/delegate-agents/{encode_path_param(agent_id)}/health"
        )
        return DelegateAgentHealth(**response)

    async def get_delegate_agent_trust_chain(self, agent_id: str) -> dict[str, Any]:
        """
        Get the trust chain backing a delegate agent.

        The chain is what authorizes the agent to act for its bound role.
        ``get_delegate_agent_health`` reports whether it is currently valid;
        this returns the chain itself.

        Args:
            agent_id: Delegate agent ID

        Returns:
            dict: The trust-chain payload (raw service shape)

        Raises:
            NotFoundError: If the agent doesn't exist / isn't a delegate agent
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/delegate-agents/{encode_path_param(agent_id)}/trust-chain"
        )
        return payload


    async def analyze_objective(self, objective: str) -> ObjectiveAnalysis:
        """
        Analyze a stated objective and get a suggested agent shape for it.

        Args:
            objective: The objective, in plain language

        Returns:
            ObjectiveAnalysis: domain, complexity, suggestions, and a
            recommended preset when the analysis produced one

        Example:
            >>> analysis = await client.agents.analyze_objective(
            ...     "summarise inbound support tickets each morning"
            ... )
            >>> analysis.recommended_preset
        """
        response = await self._http.request(
            "POST",
            "/api/v1/agents/analyze-objective",
            json_data={"objective": objective},
        )
        return ObjectiveAnalysis(**response)

    async def list_presets(self) -> dict[str, Any]:
        """
        List the available agent presets.

        Returns:
            dict: The backend-shaped preset catalogue. This operation declares
            no response schema, so it is returned unmodelled rather than typed
            against a guess.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/agents/presets"
        )
        return payload

    async def list_status(self) -> AgentStatusList:
        """
        List every agent's status for the caller's organization.

        Returns:
            AgentStatusList: status records plus their total

        Example:
            >>> statuses = await client.agents.list_status()
            >>> stale = [r for r in statuses.records if r.is_stale]
        """
        response = await self._http.request("GET", "/api/v1/agents/status")
        return AgentStatusList(**response)

    async def get_summary(self, agent_id: str) -> dict[str, Any]:
        """
        Get one agent's summary view.

        Args:
            agent_id: Agent ID

        Returns:
            dict: The agent summary payload. The platform declares a response
            model for this route, but it is the shared agent shape rather than
            a summary-specific one, so it is returned unmodelled here to avoid
            implying a narrower contract than exists.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/summary"
        )
        return payload

    async def list_subagents(self, agent_id: str) -> SubagentList:
        """
        List a manager agent's subagents.

        Args:
            agent_id: Manager agent ID

        Returns:
            SubagentList: subagents plus their total
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/subagents"
        )
        return SubagentList(**response)

    async def list_data_sources(self, agent_id: str) -> DataSourceList:
        """
        List an agent's data sources.

        Args:
            agent_id: Agent ID

        Returns:
            DataSourceList: data-source records plus their total
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/data-sources"
        )
        return DataSourceList(**response)

    async def list_connectors(self, agent_id: str) -> dict[str, Any]:
        """
        List the connectors attached to an agent.

        Args:
            agent_id: Agent ID

        Returns:
            dict: The backend-shaped connector payload; this operation
            declares no response schema. See :meth:`list_data_sources` for the
            typed sibling.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/connectors"
        )
        return payload

    async def get_execution_status(self, agent_id: str) -> dict[str, Any]:
        """
        Get an agent's current execution status.

        This is a point-in-time read. To follow an execution as it happens,
        use :meth:`stream`, which consumes the same execution over SSE.

        Args:
            agent_id: Agent ID

        Returns:
            dict: The backend-shaped status payload; this operation declares
            no response schema.
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/execute/status"
        )
        return payload

    async def register_from_manifest(
        self,
        toml_content: str,
        registered_to_role_id: str,
        workspace_id: str | None = None,
    ) -> ManifestRegistration:
        """
        Register an agent from a manifest supplied as TOML text.

        The manifest carries the agent's governance envelope, so the returned
        ``governance`` is enforced from creation rather than applied later.

        Args:
            toml_content: The manifest, as TOML text
            registered_to_role_id: Role the agent is registered against
            workspace_id: Optional workspace to place the agent in

        Returns:
            ManifestRegistration: the new agent and its governance envelope

        Example:
            >>> reg = await client.agents.register_from_manifest(
            ...     toml_content=manifest_text, registered_to_role_id="role-1"
            ... )
            >>> reg.governance.posture_ceiling
        """
        data: dict[str, Any] = {
            "toml_content": toml_content,
            "registered_to_role_id": registered_to_role_id,
        }
        if workspace_id is not None:
            data["workspace_id"] = workspace_id
        response = await self._http.request(
            "POST", "/api/v1/agents/register-from-manifest", json_data=data
        )
        return ManifestRegistration(**response)

    async def register_from_manifest_upload(
        self,
        content: bytes,
        registered_to_role_id: str,
        filename: str = "manifest.toml",
        workspace_id: str | None = None,
    ) -> ManifestRegistration:
        """
        Register an agent by uploading a manifest FILE.

        Same outcome as :meth:`register_from_manifest`, which takes the
        manifest as text and is the simpler call. Prefer this one only when
        the manifest is already a file you would otherwise have to decode --
        it is sent as multipart, and the routing arguments travel as query
        parameters rather than in the body.

        Args:
            content: The manifest file's bytes
            registered_to_role_id: Role the agent is registered against
            filename: Name to send with the upload
            workspace_id: Optional workspace to place the agent in

        Returns:
            ManifestRegistration: the new agent and its governance envelope

        Example:
            >>> reg = await client.agents.register_from_manifest_upload(
            ...     content=Path("agent.toml").read_bytes(),
            ...     registered_to_role_id="role-1",
            ... )
        """
        params: dict[str, Any] = {"registered_to_role_id": registered_to_role_id}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        response = await self._http.request(
            "POST",
            "/api/v1/agents/register-from-manifest/upload",
            params=params,
            files={"file": (filename, content, "application/toml")},
        )
        return ManifestRegistration(**response)

    # -------------------------------------------------------------------------
    # Pipeline executions
    #
    # Distinct from the agent-execution methods above (execute / get_execution
    # / list_executions): these drive the /api/v1/executions router, which runs
    # a PIPELINE (not a single agent) and persists a listable run record.
    # -------------------------------------------------------------------------

    async def start_pipeline_execution(
        self,
        pipeline_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> PipelineExecutionStart:
        """
        Start a pipeline execution run.

        Verified against ``start_execution`` /
        ``StartExecutionRequest`` (``POST /api/v1/executions/start``). The
        request body is camelCase (``pipelineId``); the response returns
        ``executionId``.

        Args:
            pipeline_id: Pipeline ID to run
            inputs: Optional input payload for the run

        Returns:
            PipelineExecutionStart: the new ``execution_id``

        Raises:
            NotFoundError: If the pipeline doesn't exist / belongs to another org
        """
        data: dict[str, Any] = {"pipelineId": pipeline_id, "inputs": inputs or {}}
        response = await self._http.request("POST", "/api/v1/executions/start", json_data=data)
        return PipelineExecutionStart(**response)

    async def get_pipeline_execution(self, execution_id: str) -> PipelineExecutionStatus:
        """
        Get a pipeline execution run's status by ID.

        Verified against ``get_execution_status``
        (``GET /api/v1/executions/{execution_id}``).

        Args:
            execution_id: Execution run ID

        Returns:
            PipelineExecutionStatus: status + inputs/outputs + logs + node runs

        Raises:
            NotFoundError: If the execution doesn't exist / belongs to another org
        """
        response = await self._http.request(
            "GET", f"/api/v1/executions/{encode_path_param(execution_id)}"
        )
        return PipelineExecutionStatus(**response)

    async def stop_pipeline_execution(self, execution_id: str) -> None:
        """
        Stop a running pipeline execution.

        Verified against ``stop_execution``
        (``POST /api/v1/executions/{execution_id}/stop`` — returns 204).

        Args:
            execution_id: Execution run ID

        Raises:
            NotFoundError: If the execution doesn't exist / belongs to another org
            ValidationError: If the execution is not running/pending (400)
        """
        await self._http.request(
            "POST", f"/api/v1/executions/{encode_path_param(execution_id)}/stop"
        )

    async def list_pipeline_execution_history(
        self,
        pipeline_id: str,
        page: int = 1,
        page_size: int = 10,
    ) -> PipelineExecutionHistory:
        """
        List execution-run history for a pipeline.

        Verified against ``get_execution_history``
        (``GET /api/v1/executions/history/{pipeline_id}``).

        Args:
            pipeline_id: Pipeline ID
            page: Page number (1-indexed)
            page_size: Items per page (1-100)

        Returns:
            PipelineExecutionHistory: executions + total + page + page_size

        Raises:
            NotFoundError: If the pipeline doesn't exist / belongs to another org
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/executions/history/{encode_path_param(pipeline_id)}",
            params={"page": page, "page_size": page_size},
        )
        return PipelineExecutionHistory(**response)
