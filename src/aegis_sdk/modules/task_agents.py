"""
Task Agents Module for Agentic OS SDK.

Provides CRUD + test operations for the Task Agent Library — non-delegate
agents used for agent-to-agent (A2A) delegation in the Two-Path Architecture.

Self-contained module: local Pydantic models, no shared
imports from client.py / modules/__init__.py / types.py. Every route below is
verified against the deployed API at
(prefix ``/api/v1/task-agents``):

    GET    /api/v1/task-agents           -> list()
    GET    /api/v1/task-agents/{id}      -> get()
    POST   /api/v1/task-agents           -> create()
    PUT    /api/v1/task-agents/{id}      -> update()
    DELETE /api/v1/task-agents/{id}      -> delete()
    POST   /api/v1/task-agents/{id}/test -> test()
"""

# NOTE: deferred annotation evaluation. The class defines an `async def
# list(...)` method; without `from __future__ import annotations`, any
# subsequent method signature in the class body using a bare `list[...]` type
# hint would resolve `list` to that method object instead of the builtin
# (class-body name resolution) — see tool_agents.py for the concrete failure
# this guards against.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


# Mirrors TaskAgentCreate/TaskAgentUpdate posture_ceiling allowlist in
# (CARE posture ladder, lowercase per
# /).
ALLOWED_POSTURE_CEILINGS: frozenset[str] = frozenset(
    {"pseudo", "supervised", "shared_planning", "continuous_insight", "delegated"}
)

PostureCeiling = Literal[
    "pseudo", "supervised", "shared_planning", "continuous_insight", "delegated"
]


class TaskAgent(TolerantModel):
    """
    Task agent record.

    The backend router returns the raw ``AgentService``/enrichment dict with
    no ``response_model`` pin (verified at), so this model declares the
    known task-agent fields and allows any additional backend fields to pass
    through rather than raising on drift (
    — a producer-shape mismatch here would silently drop fields, not crash;
    ``extra="allow"`` keeps the SDK forward-compatible while still typing the
    contract fields the create/update/list/get flows are known to carry).
    """

    model_config = ConfigDict(extra="allow")

    id: str
    organization_id: str | None = None
    name: str
    description: str | None = None
    agent_type: str | None = None
    status: str | None = None
    model_id: str | None = None
    system_prompt: str | None = None
    instructions_json: str | None = None
    capabilities_json: str | None = None
    tools_json: str | None = None
    unit_type: str | None = None
    agent_subtype: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    authority_level: int | None = None
    organization_unit_id: str | None = None
    human_role_id: str | None = None
    # Derived server-side from instructions_json (never a stored column) —
    # every list + get response enriches this field.
    posture_ceiling: str | None = None
    # get() only — enrichment fields. None on
    # list()'s per-record shape.
    unit_name: str | None = None
    reporting_chain: list[dict[str, Any]] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TaskAgentList(TolerantModel):
    """Paginated task-agent library roster (``{records, count, limit, offset}``)."""

    records: list[TaskAgent]
    count: int
    limit: int
    offset: int


class TaskAgentTestResult(TolerantModel):
    """Result of testing a task agent with a sample prompt (direct LLM call)."""

    agent_id: str
    prompt: str
    result: str


class TaskAgentsModule:
    """
    Task Agent Library module.

    Task agents are non-delegate A2A-delegation targets (distinct from
    delegate/shadow agents, which stand in for a human role).

    Example:
        >>> agent = await client.task_agents.create(
        ...     name="Data Extraction Specialist",
        ...     posture_ceiling="supervised",
        ... )
        >>> result = await client.task_agents.test(agent.id, prompt="Extract totals from this invoice")
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> TaskAgentList:
        """
        List task agents for the current organization.

        Args:
            limit: Maximum results (1-200)
            offset: Pagination offset
            status: Optional lifecycle-status filter

        Returns:
            TaskAgentList: records + count (backend pagination envelope key
                is ``count``, NOT ``total`` — verified at
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/task-agents", params=params)
        return TaskAgentList(
            records=[TaskAgent(**r) for r in response.get("records", [])],
            count=response.get("count", 0),
            limit=response.get("limit", limit),
            offset=response.get("offset", offset),
        )

    async def get(self, agent_id: str) -> TaskAgent:
        """
        Get a task agent by ID, enriched with ``unit_name`` and ``reporting_chain``.

        Args:
            agent_id: Task agent ID

        Returns:
            TaskAgent: Agent detail

        Raises:
            NotFoundError: If the agent doesn't exist or belongs to another org
        """
        response = await self._http.request(
            "GET", f"/api/v1/task-agents/{encode_path_param(agent_id)}"
        )
        return TaskAgent(**response)

    async def create(
        self,
        name: str,
        description: str = "",
        agent_type: str = "task",
        model_id: str = "",
        system_prompt: str = "",
        instructions_json: str = "{}",
        capabilities_json: str = "[]",
        tools_json: str = "[]",
        unit_type: str = "atomic",
        agent_subtype: str = "specialist",
        temperature: float = 0.7,
        max_tokens: int = 0,
        authority_level: int = 3,
        organization_unit_id: str = "",
        posture_ceiling: PostureCeiling = "delegated",
    ) -> TaskAgent:
        """
        Create a task agent for agent-to-agent delegation.

        Args:
            name: Task agent name
            description: Human-readable description
            agent_type: Behavioral type (default "task")
            model_id: LLM model identifier
            system_prompt: System prompt
            instructions_json: JSON-encoded instructions object
            capabilities_json: JSON-encoded capabilities array
            tools_json: JSON-encoded tools array
            unit_type: "atomic" or "composite"
            agent_subtype: Agent subtype (e.g. "specialist")
            temperature: Sampling temperature
            max_tokens: Max completion tokens
            authority_level: L1-L5 authority (informational; does not gate access)
            organization_unit_id: Optional org unit anchor
            posture_ceiling: CARE posture ceiling — one of pseudo/supervised/
                shared_planning/continuous_insight/delegated (server-side
                allowlist mirrored client-side per ALLOWED_POSTURE_CEILINGS)

        Returns:
            TaskAgent: Created agent
        """
        if posture_ceiling not in ALLOWED_POSTURE_CEILINGS:
            raise ValueError(
                f"posture_ceiling must be one of {sorted(ALLOWED_POSTURE_CEILINGS)}; "
                f"got {posture_ceiling!r}"
            )
        data: dict[str, Any] = {
            "name": name,
            "description": description,
            "agent_type": agent_type,
            "model_id": model_id,
            "system_prompt": system_prompt,
            "instructions_json": instructions_json,
            "capabilities_json": capabilities_json,
            "tools_json": tools_json,
            "unit_type": unit_type,
            "agent_subtype": agent_subtype,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "authority_level": authority_level,
            "organization_unit_id": organization_unit_id,
            "posture_ceiling": posture_ceiling,
        }
        response = await self._http.request("POST", "/api/v1/task-agents", json_data=data)
        return TaskAgent(**response)

    async def update(self, agent_id: str, **fields: Any) -> TaskAgent:
        """
        Update a task agent's config.

        Args:
            agent_id: Task agent ID
            **fields: Any of name, description, model_id, system_prompt,
                instructions_json, capabilities_json, tools_json, unit_type,
                agent_subtype, temperature, max_tokens, status,
                authority_level, organization_unit_id, posture_ceiling

        Returns:
            TaskAgent: Updated agent
        """
        if "posture_ceiling" in fields and fields["posture_ceiling"] is not None:
            if fields["posture_ceiling"] not in ALLOWED_POSTURE_CEILINGS:
                raise ValueError(
                    f"posture_ceiling must be one of {sorted(ALLOWED_POSTURE_CEILINGS)}; "
                    f"got {fields['posture_ceiling']!r}"
                )
        response = await self._http.request(
            "PUT", f"/api/v1/task-agents/{encode_path_param(agent_id)}", json_data=fields
        )
        return TaskAgent(**response)

    async def delete(self, agent_id: str) -> None:
        """
        Delete a task agent.

        Args:
            agent_id: Task agent ID
        """
        await self._http.request("DELETE", f"/api/v1/task-agents/{encode_path_param(agent_id)}")

    async def test(self, agent_id: str, prompt: str, max_turns: int = 1) -> TaskAgentTestResult:
        """
        Test a task agent with a sample prompt (direct LLM call, not governance-gated).

        Args:
            agent_id: Task agent ID
            prompt: Sample prompt to send
            max_turns: Reserved for future multi-turn testing (1-5)

        Returns:
            TaskAgentTestResult: agent_id, prompt, and the LLM's result text
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/task-agents/{encode_path_param(agent_id)}/test",
            json_data={"prompt": prompt, "max_turns": max_turns},
        )
        return TaskAgentTestResult(**response)
