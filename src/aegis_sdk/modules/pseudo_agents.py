"""
Pseudo Agents Module for Aegis SDK.

A pseudo agent is a HUMAN-IN-THE-LOOP work unit. It presents the same
interface as an autonomous agent, and behind it a request is routed to human
operators over configurable channels. Use one wherever a step in an
orchestration must be decided by a person.

This module covers the pseudo agent DEFINITION -- creating one, configuring
its operators, channels and escalation, and routing a task to it. The
resulting human REQUESTS (claiming, responding, reassigning) are handled by
the pools module.

Operations:
- create() / get() / update() / delete(): pseudo agent lifecycle
- list(): enumerate pseudo agents
- test_channel(): probe a routing channel before committing to it
- route_task(): hand a task to the pseudo agent's operators

⛔ AUTHENTICATION — none of this module's routes accept an API key.

Every route here is gated on an operator PERSONA. An API-key principal is
synthesised with no role and an empty persona list, which is the platform's
deliberate fail-closed default, and these routes were never wired with the
key-aware variant of the persona gate. The gates are applied as a
CONJUNCTION, so a route carrying both a key-aware scope check and a plain
persona check still denies the key.

The consequence is concrete: a client built as ``AgenticOSClient(api_key=...)``
receives 403 from every method below, on reads as well as writes. Authenticate
with a session token instead -- ``await client.auth.login(...)`` followed by
``client.set_auth_token(token.access_token)``.

This is a platform-side gap, not a client limitation, and it is reported as
such. It is documented here rather than left for a caller to discover at
runtime, because a method that always 403s for the credential most consumers
hold is worse than an absent one unless it says so.

The same gate covers the human-request routes the pools module wraps, so the
whole human-in-the-loop surface -- definition and requests alike -- is
session-token-only today.
"""

import builtins
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param


class ChannelConfig(BaseModel):
    """A routing channel that carries requests to operators."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str
    enabled: bool = True
    primary: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class OperatorAvailability(BaseModel):
    """When an operator is available to take requests."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    schedule: str | None = None
    timezone: str | None = None
    exclude_dates: builtins.list[str] | None = Field(default=None, alias="excludeDates")


class PseudoOperator(BaseModel):
    """A person who can handle this pseudo agent's requests."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user_id: str = Field(alias="userId")
    user_name: str = Field(alias="userName")
    email: str
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    role: str
    availability: OperatorAvailability | None = None


class EscalationConfig(BaseModel):
    """What happens when nobody responds in time.

    ``final_action`` decides the outcome once ``max_escalations`` is exhausted:
    ``fail`` stops the run, ``skip`` continues past the step, and
    ``default_response`` continues using ``default_response``. The default is
    ``fail`` -- an unanswered human step stops the work rather than being
    quietly assumed.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    timeout_minutes: int = Field(default=60, alias="timeoutMinutes")
    escalation_path: builtins.list[str] = Field(default_factory=list, alias="escalationPath")
    notify_on_escalation: bool = Field(default=True, alias="notifyOnEscalation")
    max_escalations: int = Field(default=3, alias="maxEscalations")
    final_action: str = Field(default="fail", alias="finalAction")
    default_response: dict[str, Any] | None = Field(default=None, alias="defaultResponse")


class ResponseSchemaField(BaseModel):
    """One field of the form an operator fills in."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str
    type: str
    label: str
    description: str | None = None
    required: bool | None = None
    default_value: Any | None = Field(default=None, alias="defaultValue")
    validation: dict[str, Any] | None = None


class ResponseSchema(BaseModel):
    """The shape of the answer an operator is asked for."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    fields: builtins.list[ResponseSchemaField] = Field(default_factory=list)
    default_values: dict[str, Any] | None = Field(default=None, alias="defaultValues")


class PseudoAgentConfig(BaseModel):
    """How a pseudo agent routes work to people."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    routing_channels: builtins.list[ChannelConfig] = Field(
        default_factory=list, alias="routingChannels"
    )
    operators: builtins.list[PseudoOperator] = Field(default_factory=list)
    escalation: EscalationConfig = Field(default_factory=lambda: EscalationConfig())
    response_schema: ResponseSchema | None = Field(default=None, alias="responseSchema")
    instructions: str | None = None
    auto_assign: bool = Field(default=False, alias="autoAssign")
    require_claim: bool = Field(default=True, alias="requireClaim")
    allow_reassign: bool = Field(default=True, alias="allowReassign")


class TrustSetup(BaseModel):
    """Trust arrangement to establish alongside the pseudo agent.

    ``mode`` is one of ``establish``, ``delegate`` or ``skip``; it defaults to
    ``skip``, so a pseudo agent created without this block has NO trust chain.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    mode: str = "skip"
    delegatee_id: str | None = Field(default=None, alias="delegateeId")
    expiration_days: int | None = Field(default=None, alias="expirationDays")


class PseudoAgent(BaseModel):
    """A human-in-the-loop work unit."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    name: str
    description: str
    type: str = "atomic"
    agent_subtype: str = Field(default="pseudo", alias="agentSubtype")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    workspace_ids: builtins.list[str] = Field(default_factory=list, alias="workspaceIds")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    tags: builtins.list[str] = Field(default_factory=list)
    trust_info: dict[str, Any] = Field(default_factory=dict, alias="trustInfo")
    pseudo_config: PseudoAgentConfig | None = Field(default=None, alias="pseudoConfig")
    capabilities: builtins.list[str] = Field(default_factory=list)


class PseudoAgentPage(BaseModel):
    """One page of pseudo agents."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    items: builtins.list[PseudoAgent] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=50, alias="pageSize")
    has_more: bool = Field(default=False, alias="hasMore")


class ChannelTestResult(BaseModel):
    """Outcome of probing a routing channel."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool
    latency_ms: int | None = Field(default=None, alias="latencyMs")
    error: str | None = None
    details: str | None = None
    tested_at: str = Field(alias="testedAt")


class PseudoRequest(BaseModel):
    """A request routed to human operators."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    pseudo_agent_id: str = Field(alias="pseudoAgentId")
    pseudo_agent_name: str = Field(alias="pseudoAgentName")
    workflow_run_id: str = Field(alias="workflowRunId")
    node_id: str = Field(alias="nodeId")
    title: str
    description: str | None = None
    work_unit_id: str = Field(alias="workUnitId")
    work_unit_name: str | None = Field(default=None, alias="workUnitName")
    request_data: dict[str, Any] = Field(default_factory=dict, alias="requestData")
    status: str
    priority: str
    assigned_to: str | None = Field(default=None, alias="assignedTo")
    assigned_to_name: str | None = Field(default=None, alias="assignedToName")
    created_by_agent_name: str | None = Field(default=None, alias="createdByAgentName")
    created_at: str = Field(alias="createdAt")
    due_at: str = Field(alias="dueAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    response: dict[str, Any] | None = None
    escalation_level: int = Field(default=0, alias="escalationLevel")
    context: dict[str, Any] = Field(default_factory=dict)
    history: builtins.list[dict[str, Any]] = Field(default_factory=list)
    instructions: str | None = None
    response_schema: dict[str, Any] | None = Field(default=None, alias="responseSchema")
    comments: builtins.list[dict[str, Any]] = Field(default_factory=list)


class PseudoAgentsModule:
    """
    Pseudo agent (human-in-the-loop work unit) management.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     agent = await client.pseudo_agents.create(
        ...         name="Legal sign-off",
        ...         description="Routes contract approvals to counsel",
        ...         config={
        ...             "operators": [
        ...                 {
        ...                     "userId": "user_1",
        ...                     "userName": "Counsel",
        ...                     "email": "counsel@example.com",
        ...                     "role": "primary",
        ...                 }
        ...             ]
        ...         },
        ...     )
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def create(
        self,
        name: str,
        description: str,
        config: dict[str, Any],
        workspace_ids: builtins.list[str] | None = None,
        tags: builtins.list[str] | None = None,
        trust_setup: dict[str, Any] | None = None,
    ) -> PseudoAgent:
        """
        Create a pseudo agent.

        Args:
            name: Display name
            description: What this human step is for. Required, not optional.
            config: Routing configuration in the platform's camelCase wire
                shape -- ``routingChannels``, ``operators``, ``escalation``,
                ``responseSchema``, ``instructions``, ``autoAssign``,
                ``requireClaim``, ``allowReassign``. See
                :class:`PseudoAgentConfig` for the field meanings.
            workspace_ids: Workspaces this agent belongs to
            tags: Free-form tags
            trust_setup: Optional trust arrangement -- ``mode``
                (``establish`` / ``delegate`` / ``skip``), ``delegateeId``,
                ``expirationDays``.

        Returns:
            The created pseudo agent.

        Note:
            Omitting ``trust_setup`` means ``mode="skip"``: the agent is
            created with NO trust chain. That is the platform's default, not
            an oversight, but it does mean an agent created this way will not
            appear in trust-chain-derived views such as registry discovery.
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "pseudoConfig": config,
        }
        if workspace_ids is not None:
            body["workspaceIds"] = workspace_ids
        if tags is not None:
            body["tags"] = tags
        if trust_setup is not None:
            body["trustSetup"] = trust_setup

        response = await self._http.request(
            "POST",
            "/api/v1/work-units/pseudo",
            json_data=body,
        )
        return PseudoAgent(**response)

    async def list(
        self,
        workspace_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PseudoAgentPage:
        """
        List pseudo agents.

        Args:
            workspace_id: Restrict to one workspace
            limit: Maximum results, 1-100
            offset: Pagination offset

        Returns:
            One page, with ``has_more`` saying whether to fetch another.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if workspace_id is not None:
            params["workspace_id"] = workspace_id

        response = await self._http.request(
            "GET",
            "/api/v1/work-units/pseudo",
            params=params,
        )
        return PseudoAgentPage(**response)

    async def get(self, agent_id: str) -> PseudoAgent:
        """
        Get one pseudo agent.

        Args:
            agent_id: Pseudo agent ID

        Returns:
            The pseudo agent, including its routing configuration.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/work-units/pseudo/{encode_path_param(agent_id)}",
        )
        return PseudoAgent(**response)

    async def update(
        self,
        agent_id: str,
        name: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
        tags: builtins.list[str] | None = None,
    ) -> PseudoAgent:
        """
        Update a pseudo agent.

        Args:
            agent_id: Pseudo agent ID
            name: New display name
            description: New description
            config: Replacement routing configuration. This REPLACES the
                configuration block rather than merging into it -- send the
                whole thing, including the operators and channels you want to
                keep.
            tags: Replacement tags

        Returns:
            The updated pseudo agent.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if config is not None:
            body["pseudoConfig"] = config
        if tags is not None:
            body["tags"] = tags

        response = await self._http.request(
            "PATCH",
            f"/api/v1/work-units/pseudo/{encode_path_param(agent_id)}",
            json_data=body,
        )
        return PseudoAgent(**response)

    async def delete(self, agent_id: str) -> None:
        """
        Delete a pseudo agent.

        Args:
            agent_id: Pseudo agent ID

        Returns:
            ``None``. The platform answers with no content.
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/work-units/pseudo/{encode_path_param(agent_id)}",
        )

    async def test_channel(
        self,
        channel_type: str,
        config: dict[str, Any] | None = None,
        enabled: bool = True,
        primary: bool = False,
    ) -> ChannelTestResult:
        """
        Probe a routing channel before committing to it.

        Args:
            channel_type: Channel type -- ``internal``, ``email``, ``slack``,
                ``teams`` or ``webhook``
            config: Channel-specific settings
            enabled: Whether the channel would be enabled
            primary: Whether it would be the primary channel

        Returns:
            ``success`` plus ``latency_ms`` and, on failure, ``error`` /
            ``details``.

        Note:
            This probes a CANDIDATE channel supplied in the call -- it does
            not read a saved pseudo agent's configuration -- so it is usable
            before the agent exists.
        """
        body: dict[str, Any] = {
            "type": channel_type,
            "enabled": enabled,
            "primary": primary,
            "config": config or {},
        }
        response = await self._http.request(
            "POST",
            "/api/v1/work-units/pseudo/test-channel",
            json_data=body,
        )
        return ChannelTestResult(**response)

    async def route_task(
        self,
        agent_id: str,
        workflow_run_id: str,
        node_id: str,
        title: str,
        request_data: dict[str, Any] | None = None,
        description: str | None = None,
        priority: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> PseudoRequest:
        """
        Hand a task to a pseudo agent's human operators.

        Args:
            agent_id: Pseudo agent ID
            workflow_run_id: The run this task belongs to
            node_id: The node within that run
            title: What the operator sees first
            request_data: The payload the operator is deciding on
            description: Longer explanation for the operator
            priority: Request priority; defaults to ``medium``
            context: Extra context to show alongside the request

        Returns:
            The created request, including ``due_at`` and the response schema
            the operator will be asked to fill in.

        Note:
            This CREATES a request and returns immediately -- it does not wait
            for a human. Track the outcome through the pools module's request
            operations, or through the request's ``status``.
        """
        body: dict[str, Any] = {
            "workflowRunId": workflow_run_id,
            "nodeId": node_id,
            "title": title,
            "requestData": request_data or {},
            "priority": priority,
        }
        if description is not None:
            body["description"] = description
        if context is not None:
            body["context"] = context

        response = await self._http.request(
            "POST",
            f"/api/v1/work-units/pseudo/{encode_path_param(agent_id)}/route",
            json_data=body,
        )
        return PseudoRequest(**response)
