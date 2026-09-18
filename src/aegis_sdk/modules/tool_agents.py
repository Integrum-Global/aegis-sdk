"""
Tool Agents Module for Agentic OS SDK.

Provides CRUD, status lifecycle, dependency graph, analytics, and
governance-gated invocation for the Tool Agent Registry — singleton shared
capabilities that multiple applications can invoke.

Self-contained module: local Pydantic models, no shared
imports from client.py / modules/__init__.py / types.py. Every route below is
verified against the deployed API at
(13 routes, prefix ``/api/v1/tool-agents``):

    GET    /api/v1/tool-agents                            -> list()
    POST   /api/v1/tool-agents                             -> create()
    GET    /api/v1/tool-agents/{agent_id}                   -> get()
    GET    /api/v1/tool-agents/{agent_id}/envelope-summary  -> get_envelope_summary()
    PUT    /api/v1/tool-agents/{agent_id}                   -> update()
    PATCH  /api/v1/tool-agents/{agent_id}/status            -> change_status()
    POST   /api/v1/tool-agents/{agent_id}/invoke            -> invoke()
    GET    /api/v1/tool-agents/{agent_id}/consumers         -> list_consumers()
    GET    /api/v1/tool-agents/{agent_id}/invocations       -> list_invocations()
    GET    /api/v1/tool-agents/{agent_id}/components        -> list_components()
    POST   /api/v1/tool-agents/{agent_id}/components        -> add_component()
    DELETE /api/v1/tool-agents/{agent_id}/components/{dependency_id} -> remove_component()
    GET    /api/v1/tool-agents/{agent_id}/impact            -> get_impact()
"""

# NOTE: deferred annotation evaluation is required here. The class defines an
# `async def list(...)` method; without `from __future__ import annotations`,
# every subsequent method signature evaluating a bare `list[...]` type hint in
# the class body resolves `list` to that method object (class-body name
# resolution), not the builtin, raising `TypeError: 'function' object is not
# subscriptable` at import time.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


# Mirrors ALLOWED_TOOL_AGENT_STATUS_TARGETS.
# `draft` is initial-only and is never a valid transition target.
ALLOWED_TOOL_AGENT_STATUS_TARGETS: frozenset[str] = frozenset(
    {"active", "suspended", "deprecated", "revoked", "archived"}
)


class ToolAgent(TolerantModel):
    """Tool agent record (registry.ToolAgentResponse, snake_case)."""

    id: str
    organization_id: str
    # Optional: servers that removed the Workspace entity emit null here (the
    # key is kept for older clients). Null means "no workspace"; it grants nothing.
    workspace_id: str | None = None
    name: str
    description: str
    agent_type: str
    status: str
    model_id: str
    temperature: float
    max_tokens: int
    created_by: str
    capabilities_json: str
    tools_json: str
    registered_to_role_id: str | None = None
    composition_role: str | None = None
    parent_composite_id: str | None = None
    human_role_id: str | None = None
    created_at: str
    updated_at: str
    system_prompt: str | None = None
    instructions_json: str | None = None
    safety_constraints_json: str | None = None
    a2a_enabled: bool | None = None
    orchestration_config: str | None = None
    provider: str | None = None
    unit_type: str | None = None
    agent_subtype: str | None = None
    consumer_count: int = 0


class ToolAgentList(TolerantModel):
    """Paginated tool-agent registry roster (``{records, total}``)."""

    records: list[ToolAgent]
    total: int


class ToolAgentInvocationResult(TolerantModel):
    """Result of a governance-gated tool-agent invocation."""

    content: str
    model: str
    usage: dict[str, Any] = Field(default_factory=dict)
    # Which path produced the result. Mirrors the server's
    # ``InvokeToolAgentResponse.dispatch_path`` AND its default, so a server that
    # predates the field reads as the LLM path it was. ``"builtin_tool"`` means a
    # named built-in tool ran with no model call: ``model``/``usage`` are empty
    # and ``cost`` is "0" by construction, not because a model call was free.
    dispatch_path: Literal["llm", "builtin_tool"] = "llm"
    trust_chain_id: str
    constraint_status: str
    cost: str
    audit_anchor_id: str
    verification_zone: Literal["auto_approved", "flagged", "held", "blocked"]


class ConstraintSource(TolerantModel):
    """A single inheritance level contributing constraints to an agent."""

    label: str
    count: int
    level: str


class ToolAgentEnvelopeSummary(TolerantModel):
    """Operating-envelope summary for the agent-configuration side panel."""

    agent_id: str
    trust_posture: str | None = None
    posture_source: str | None = None
    unit_ceiling: str | None = None
    unit_ceiling_source: str | None = None
    budget_used_usd: float | None = None
    budget_allocated_usd: float | None = None
    active_capabilities: int = 0
    total_capabilities: int = 0
    must_rules: int = 0
    must_not_rules: int = 0
    should_rules: int = 0
    active_workflows: int = 0
    constraint_sources: list[ConstraintSource] = Field(default_factory=list)


class ToolAgentsModule:
    """
    Tool Agent Registry module.

    Governs singleton, shared capabilities registered against an
    accountable role and invoked by applications through Aegis governance
    (trust chain, posture, budget).

    Example:
        >>> agent = await client.tool_agents.create(
        ...     name="PDF Summarizer",
        ...     registered_to_role_id="role_123",
        ...     capabilities=["summarize", "extract_text"],
        ... )
        >>> result = await client.tool_agents.invoke(agent.id, message="Summarize this doc")
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    async def list(
        self,
        status: str | None = None,
        composition_role: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ToolAgentList:
        """
        List tool agents for the current organization.

        Args:
            status: Filter by lifecycle status
            composition_role: Filter by composition role (e.g. "standalone")
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            ToolAgentList: records + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if composition_role:
            params["composition_role"] = composition_role

        response = await self._http.request("GET", "/api/v1/tool-agents", params=params)
        return ToolAgentList(
            records=[ToolAgent(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def create(
        self,
        name: str,
        registered_to_role_id: str,
        capabilities: list[Any] | str,
        description: str = "",
        composition_role: str = "standalone",
        tools_json: str = "[]",
        model_id: str = "",
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        id: str | None = None,
    ) -> ToolAgent:
        """
        Register a new tool agent (draft status).

        Args:
            name: Tool agent name
            registered_to_role_id: Accountable role this agent registers to
                (required — anchors grant approvals + capability matching, orphan-registration enforcement)
            capabilities: Non-empty list of capability strings, OR a
                pre-serialized JSON array string. The backend rejects an
                empty array (a zero-capability agent cannot be matched by
                the grant-approval flow).
            description: Human-readable description
            composition_role: "standalone" or a composite role
            tools_json: JSON-encoded tool configuration array
            model_id: LLM model identifier
            system_prompt: System prompt for invocations
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Max completion tokens (1-200000)
            id: Optional explicit UUID

        Returns:
            ToolAgent: Created agent (status="draft")
        """
        capabilities_json = (
            capabilities if isinstance(capabilities, str) else json.dumps(capabilities)
        )
        data: dict[str, Any] = {
            "name": name,
            "registered_to_role_id": registered_to_role_id,
            "capabilities_json": capabilities_json,
            "description": description,
            "composition_role": composition_role,
            "tools_json": tools_json,
            "model_id": model_id,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if id:
            data["id"] = id

        response = await self._http.request("POST", "/api/v1/tool-agents", json_data=data)
        return ToolAgent(**response)

    async def get(self, agent_id: str) -> ToolAgent:
        """
        Get a tool agent by ID.

        Args:
            agent_id: Tool agent ID

        Returns:
            ToolAgent: Agent detail (includes consumer_count)
        """
        response = await self._http.request(
            "GET", f"/api/v1/tool-agents/{encode_path_param(agent_id)}"
        )
        return ToolAgent(**response)

    async def get_envelope_summary(self, agent_id: str) -> ToolAgentEnvelopeSummary:
        """
        Get the operating-envelope summary for the agent configuration side panel.

        Args:
            agent_id: Tool agent ID

        Returns:
            ToolAgentEnvelopeSummary: posture, budget, and capability rollups
        """
        response = await self._http.request(
            "GET", f"/api/v1/tool-agents/{encode_path_param(agent_id)}/envelope-summary"
        )
        return ToolAgentEnvelopeSummary(**response)

    async def update(self, agent_id: str, **fields: Any) -> ToolAgent:
        """
        Update a tool agent's config.

        Args:
            agent_id: Tool agent ID
            **fields: Any of name, description, composition_role,
                capabilities_json, tools_json, model_id, system_prompt,
                temperature, max_tokens

        Returns:
            ToolAgent: Updated agent
        """
        response = await self._http.request(
            "PUT", f"/api/v1/tool-agents/{encode_path_param(agent_id)}", json_data=fields
        )
        return ToolAgent(**response)

    async def change_status(
        self,
        agent_id: str,
        status: Literal["active", "suspended", "deprecated", "revoked", "archived"],
    ) -> ToolAgent:
        """
        Change a tool agent's lifecycle status. Enforces state-machine transitions.

        Args:
            agent_id: Tool agent ID
            status: Target status — one of active/suspended/deprecated/revoked/archived
                (server-side allowlist mirrored client-side per
                ``ALLOWED_TOOL_AGENT_STATUS_TARGETS``)

        Returns:
            ToolAgent: Agent with updated status

        Raises:
            ValidationError: If the (status, target) transition is invalid
        """
        if status not in ALLOWED_TOOL_AGENT_STATUS_TARGETS:
            raise ValueError(
                f"status must be one of {sorted(ALLOWED_TOOL_AGENT_STATUS_TARGETS)}; got {status!r}"
            )
        response = await self._http.request(
            "PATCH",
            f"/api/v1/tool-agents/{encode_path_param(agent_id)}/status",
            json_data={"status": status},
        )
        return ToolAgent(**response)

    async def invoke(
        self,
        agent_id: str,
        message: str,
        application_id: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        *,
        tool_name: str | None = None,
        tool_arguments: dict[str, Any] | None = None,
        action_type: str | None = None,
    ) -> ToolAgentInvocationResult:
        """
        Invoke a tool agent through Aegis governance (trust + posture + budget gated).

        Args:
            agent_id: Tool agent ID
            message: User message
            application_id: Application context — when provided, the
                application must be active and hold an active grant for
                this agent; the application budget is consumed on success.
            conversation_history: Previous conversation messages for
                multi-turn context
            tool_name: Name of a BUILT-IN tool to execute directly, with no
                model round-trip. The result's ``dispatch_path`` is then
                ``"builtin_tool"``, ``model``/``usage`` are empty and ``cost`` is
                ``"0"``. Every governance gate applies exactly as on the LLM
                path. An unregistered name is refused with 400
                (``ValidationError``) -- it is never answered by the model.
                Must be a non-empty string when given.
            tool_arguments: Arguments for ``tool_name``, per that tool's own
                input schema. Only valid together with ``tool_name``. Tenant
                and identity scope are always server-derived, so a key of the
                same name here cannot widen scope.
            action_type: Caller-declared coarse governance CATEGORY -- not a
                tool name. Declaring a never-delegated category (for example
                ``financial_decisions``) is refused with 403 regardless of the
                agent's posture; any other value does not change the outcome.

        Returns:
            ToolAgentInvocationResult: output + governance metadata, including
            ``dispatch_path``

        Raises:
            ValueError: If ``tool_name`` is empty, or ``tool_arguments`` is given
                without ``tool_name`` -- raised before any request, because the
                server would silently answer from the model instead.
            ValidationError: If the server does not recognise ``tool_name`` (400)
            GovernanceViolationError: If governance denies the invocation
            ServiceError: On fail-closed governance-service unavailability (503)
        """
        # The server branches on ``if body.tool_name:`` and ignores
        # ``tool_arguments`` without a name, so both of these would otherwise be
        # a silent fall-through to the LLM that reads as success.
        if tool_name is not None and not tool_name.strip():
            raise ValueError(
                "tool_name must be a non-empty tool name; omit it to use the LLM path"
            )
        if tool_arguments is not None and tool_name is None:
            raise ValueError(
                "tool_arguments requires tool_name: without a tool name the server "
                "ignores the arguments and answers from the model"
            )

        data: dict[str, Any] = {"message": message}
        if application_id:
            data["application_id"] = application_id
        if conversation_history is not None:
            data["conversation_history"] = conversation_history
        if action_type is not None:
            data["action_type"] = action_type
        if tool_name is not None:
            data["tool_name"] = tool_name
        if tool_arguments is not None:
            data["tool_arguments"] = tool_arguments

        response = await self._http.request(
            "POST", f"/api/v1/tool-agents/{encode_path_param(agent_id)}/invoke", json_data=data
        )
        return ToolAgentInvocationResult(**response)

    async def list_consumers(self, agent_id: str, status: str = "active") -> dict[str, Any]:
        """
        List applications granted access to this tool agent.

        Args:
            agent_id: Tool agent ID
            status: "active" (default), "revoked", or "all"

        Returns:
            dict: {"records": [...], "total": N}
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/tool-agents/{encode_path_param(agent_id)}/consumers",
            params={"status": status},
        )
        return response

    async def list_invocations(
        self, agent_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """
        List invocation history for a tool agent.

        Args:
            agent_id: Tool agent ID
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            dict: Invocation history payload
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/tool-agents/{encode_path_param(agent_id)}/invocations",
            params={"limit": limit, "offset": offset},
        )
        return response

    async def list_components(self, agent_id: str) -> dict[str, Any]:
        """
        List dependency components of a composite tool agent.

        Args:
            agent_id: Tool agent ID

        Returns:
            dict: {"records": [...], "total": N}
        """
        response = await self._http.request(
            "GET", f"/api/v1/tool-agents/{encode_path_param(agent_id)}/components"
        )
        return response

    async def add_component(
        self,
        agent_id: str,
        component_agent_id: str,
        role: str,
        is_inline: bool = False,
        version_constraint: str | None = None,
    ) -> dict[str, Any]:
        """
        Add a dependency component to a composite tool agent. Cycle detection is enforced.

        Args:
            agent_id: Composite (parent) tool agent ID
            component_agent_id: Component tool agent ID
            role: Role of the component within the composite
            is_inline: Whether the component is inlined
            version_constraint: Optional version constraint string

        Returns:
            dict: Created dependency record
        """
        data: dict[str, Any] = {
            "component_agent_id": component_agent_id,
            "role": role,
            "is_inline": is_inline,
        }
        if version_constraint:
            data["version_constraint"] = version_constraint

        response = await self._http.request(
            "POST", f"/api/v1/tool-agents/{encode_path_param(agent_id)}/components", json_data=data
        )
        return response

    async def remove_component(self, agent_id: str, dependency_id: str) -> None:
        """
        Remove a dependency component from a composite tool agent.

        Args:
            agent_id: Composite (parent) tool agent ID
            dependency_id: Dependency record ID to remove
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/tool-agents/{encode_path_param(agent_id)}/components/{encode_path_param(dependency_id)}",
        )

    async def get_impact(self, agent_id: str) -> dict[str, Any]:
        """
        Get impact analysis for a tool agent (use before deprecating/revoking).

        Args:
            agent_id: Tool agent ID

        Returns:
            dict: Direct composites, transitive composites, affected applications
        """
        response = await self._http.request(
            "GET", f"/api/v1/tool-agents/{encode_path_param(agent_id)}/impact"
        )
        return response
