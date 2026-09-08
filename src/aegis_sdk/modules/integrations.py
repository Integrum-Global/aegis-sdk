"""
Integrations SDK Module for Agentic OS SDK.

Covers three backend domains under one module (
integrations-a2a P0/P1 fill — see §
"Domain: integrations-a2a"):

- External Agents — governance-wrapped third-party agents (Teams/Slack/
  Discord/Telegram/Notion/custom webhook), registered against budget and
  rate-limit envelopes.
- Deployments — agent-to-gateway deployment lifecycle (create, list,
  detail, start, stop, redeploy).
- Gateways — Nexus gateway registration (create, list) that deployments
  target.
- Notifications — real-time SSE notification stream.

Self-contained module: local Pydantic models, no shared imports from
client.py / modules/__init__.py / types.py. Every route below is verified
against the real backend routers:

    POST   /api/v1/external-agents                       -> create_external_agent()
    GET    /api/v1/external-agents                       -> list_external_agents()
    GET    /api/v1/external-agents/{agent_id}             -> get_external_agent()
    PATCH  /api/v1/external-agents/{agent_id}             -> update_external_agent()
    DELETE /api/v1/external-agents/{agent_id}             -> delete_external_agent()
    POST   /api/v1/external-agents/{agent_id}/invoke      -> invoke_external_agent()
    GET    /api/v1/external-agents/{agent_id}/invocations -> list_external_agent_invocations()

    POST   /api/v1/gateways                               -> create_gateway()
    GET    /api/v1/gateways                               -> list_gateways()

    POST   /api/v1/deployments                            -> create_deployment()
    GET    /api/v1/deployments                            -> list_deployments()
    GET    /api/v1/deployments/{deployment_id}            -> get_deployment()
    POST   /api/v1/deployments/{deployment_id}/start       -> start_deployment()
    POST   /api/v1/deployments/{deployment_id}/stop        -> stop_deployment()
    POST   /api/v1/deployments/{deployment_id}/redeploy    -> redeploy_deployment()

    GET    /api/v1/notifications/stream/sse               -> stream_notifications()

Source routes verified against the published API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


# ===================
# External Agents
# ===================


class ExternalAgent(BaseModel):
    """
    External agent record (``ExternalAgentResponse``, snake_case).

    ``platform_config`` / ``capabilities`` / ``config`` are JSON-encoded
    strings on the wire ( stores them
    as JSON string columns) -- NOT parsed dict/list. ``tags`` is normalized
    server-side from the DB column ``agent_tags`` (see
    ``ExternalAgentService._normalize_response``).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str
    workspace_id: str
    name: str
    description: str | None = None
    platform: str
    platform_agent_id: str | None = None
    webhook_url: str
    auth_type: str
    platform_config: str
    capabilities: str
    config: str
    budget_limit_daily: float
    budget_limit_monthly: float
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    tags: str | None = None
    status: str
    created_by: str
    created_at: str
    updated_at: str


class ExternalAgentList(BaseModel):
    """Paginated external-agent roster (``ExternalAgentListResponse``)."""

    agents: list[ExternalAgent]
    total: int
    limit: int
    offset: int


class ExternalAgentInvokeResult(BaseModel):
    """Result of invoking an external agent (``InvokeExternalAgentResponse``)."""

    invocation_id: str
    trace_id: str
    status: str
    output: str | None = None
    metadata: dict[str, Any] | None = None


class ExternalAgentInvocation(BaseModel):
    """
    External-agent invocation history record
    (``ExternalAgentInvocationResponse``).

    ``request_payload`` / ``response_payload`` are objects (parsed from the
    persisted JSON strings server-side); ``cost`` / ``response_code`` /
    ``execution_time_ms`` / ``error_message`` are nullable.
    """

    id: str
    agent_id: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None = None
    status: str
    execution_time_ms: int | None = None
    response_code: int | None = None
    error_message: str | None = None
    cost: float | None = None
    created_at: str


# ===================
# Gateways
# ===================


class Gateway(BaseModel):
    """
    Nexus gateway record (encrypted API key never returned on the wire --
    ``GatewayService`` pops ``api_key_encrypted`` before every response).
    """

    id: str
    organization_id: str
    name: str
    description: str | None = None
    api_url: str
    environment: str
    status: str
    health_check_url: str | None = None
    last_health_check: str | None = None
    last_health_status: str | None = None
    created_at: str
    updated_at: str


class GatewayList(BaseModel):
    """Gateway roster envelope (``{"gateways": [...]}``)."""

    gateways: list[Gateway]


# ===================
# Deployments
# ===================


class Deployment(BaseModel):
    """Agent-to-gateway deployment record."""

    id: str
    organization_id: str
    agent_id: str
    agent_version_id: str | None = None
    gateway_id: str
    registration_id: str | None = None
    status: str
    endpoint_url: str | None = None
    error_message: str | None = None
    deployed_by: str
    deployed_at: str | None = None
    stopped_at: str | None = None
    # created_at is OPTIONAL: the POST /deployments create + /start paths build
    # their response from DeploymentService.deploy() (deployment_service.py
    # ~103-117), which emits updated_at but NOT created_at. Only the DB-backed
    # read paths (get/list) include it. A required created_at raised
    # ValidationError on every real create_deployment()/start_deployment()
    # (holistic-redteam MEDIUM finding). Backend emit-gap flagged for a
    # follow-up consistency fix (add created_at to deployment_data).
    created_at: str | None = None
    updated_at: str


class DeploymentList(BaseModel):
    """Deployment roster envelope (``{"deployments": [...]}``)."""

    deployments: list[Deployment]


class IntegrationsModule:
    """
    Integrations module -- external agents, gateways, deployments,
    notifications.

    Example:
        >>> from aegis_sdk import AgenticOS
        >>> client = AgenticOS(api_key="your-api-key")
        >>>
        >>> agent = await client.integrations.create_external_agent(
        ...     workspace_id="ws-123",
        ...     name="Support Bot",
        ...     platform="slack",
        ...     webhook_url="https://hooks.slack.com/services/...",
        ...     auth_type="bearer_token",
        ... )
        >>>
        >>> gateway = await client.integrations.create_gateway(
        ...     name="prod-gateway",
        ...     api_url="https://nexus.example.com",
        ...     api_key="nx-key-...",
        ... )
        >>>
        >>> deployment = await client.integrations.create_deployment(
        ...     agent_id="agent-123",
        ...     gateway_id=gateway.id,
        ... )
    """

    def __init__(self, http_client: HTTPClient):
        """Initialize Integrations module with HTTP client."""
        self._http = http_client

    # -------------------
    # External Agents
    # -------------------

    async def create_external_agent(
        self,
        workspace_id: str,
        name: str,
        platform: str,
        webhook_url: str,
        auth_type: str = "none",
        description: str | None = None,
        platform_agent_id: str | None = None,
        auth_config: dict[str, Any] | None = None,
        platform_config: dict[str, Any] | None = None,
        capabilities: list[Any] | None = None,
        config: dict[str, Any] | None = None,
        budget_limit_daily: float = -1.0,
        budget_limit_monthly: float = -1.0,
        rate_limit_per_minute: int = -1,
        rate_limit_per_hour: int = -1,
        tags: list[str] | None = None,
    ) -> ExternalAgent:
        """
        Register a new external agent for governance wrapping.

        Args:
            workspace_id: Workspace this agent belongs to
            name: Agent name
            platform: One of teams/discord/slack/telegram/notion/custom_http
            webhook_url: Target webhook/endpoint URL (SSRF-validated server-side)
            auth_type: One of oauth2/api_key/bearer_token/basic/custom/none
            description: Optional description
            platform_agent_id: Optional platform-specific agent identifier
            auth_config: Optional auth configuration (shape depends on auth_type)
            platform_config: Optional platform-specific settings
            capabilities: Optional list of capability identifiers
            config: Optional free-form config
            budget_limit_daily: Daily cost limit in USD (-1 = unlimited)
            budget_limit_monthly: Monthly cost limit in USD (-1 = unlimited)
            rate_limit_per_minute: Requests/minute limit (-1 = unlimited)
            rate_limit_per_hour: Requests/hour limit (-1 = unlimited)
            tags: Optional tag list

        Returns:
            ExternalAgent: Created agent record
        """
        data: dict[str, Any] = {
            "workspace_id": workspace_id,
            "name": name,
            "platform": platform,
            "webhook_url": webhook_url,
            "auth_type": auth_type,
            "budget_limit_daily": budget_limit_daily,
            "budget_limit_monthly": budget_limit_monthly,
            "rate_limit_per_minute": rate_limit_per_minute,
            "rate_limit_per_hour": rate_limit_per_hour,
        }
        if description is not None:
            data["description"] = description
        if platform_agent_id is not None:
            data["platform_agent_id"] = platform_agent_id
        if auth_config is not None:
            data["auth_config"] = auth_config
        if platform_config is not None:
            data["platform_config"] = platform_config
        if capabilities is not None:
            data["capabilities"] = capabilities
        if config is not None:
            data["config"] = config
        if tags is not None:
            data["tags"] = tags

        response = await self._http.request("POST", "/api/v1/external-agents", json_data=data)
        return ExternalAgent(**response)

    async def list_external_agents(
        self,
        workspace_id: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ExternalAgentList:
        """
        List external agents for the current organization.

        Args:
            workspace_id: Optional workspace filter
            platform: Optional platform filter
            status: Optional status filter (active/inactive/deleted)
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            ExternalAgentList: agents + total + limit + offset
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if workspace_id:
            params["workspace_id"] = workspace_id
        if platform:
            params["platform"] = platform
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/external-agents", params=params)
        return ExternalAgentList(**response)

    async def get_external_agent(self, agent_id: str) -> ExternalAgent:
        """
        Get an external agent by ID.

        Args:
            agent_id: External agent ID

        Returns:
            ExternalAgent: Agent detail
        """
        response = await self._http.request(
            "GET", f"/api/v1/external-agents/{encode_path_param(agent_id)}"
        )
        return ExternalAgent(**response)

    async def update_external_agent(self, agent_id: str, **fields: Any) -> ExternalAgent:
        """
        Update an external agent's config.

        Args:
            agent_id: External agent ID
            **fields: Any of name, description, webhook_url, auth_type,
                auth_config, platform_config, config, budget_limit_daily,
                budget_limit_monthly, rate_limit_per_minute,
                rate_limit_per_hour, status, tags

        Returns:
            ExternalAgent: Updated agent
        """
        response = await self._http.request(
            "PATCH", f"/api/v1/external-agents/{encode_path_param(agent_id)}", json_data=fields
        )
        return ExternalAgent(**response)

    async def delete_external_agent(self, agent_id: str) -> None:
        """
        Soft-delete an external agent (sets status="deleted").

        Args:
            agent_id: External agent ID
        """
        await self._http.request("DELETE", f"/api/v1/external-agents/{encode_path_param(agent_id)}")

    async def invoke_external_agent(
        self,
        agent_id: str,
        input: str,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalAgentInvokeResult:
        """
        Invoke an external agent through Aegis governance.

        Args:
            agent_id: External agent ID
            input: Input text/payload for the agent
            context: Optional context data
            metadata: Optional request metadata

        Returns:
            ExternalAgentInvokeResult: invocation_id, trace_id, status, output
        """
        data: dict[str, Any] = {"input": input}
        if context is not None:
            data["context"] = context
        if metadata is not None:
            data["metadata"] = metadata

        response = await self._http.request(
            "POST", f"/api/v1/external-agents/{encode_path_param(agent_id)}/invoke", json_data=data
        )
        return ExternalAgentInvokeResult(**response)

    async def list_external_agent_invocations(
        self, agent_id: str, limit: int = 50, offset: int = 0
    ) -> list[ExternalAgentInvocation]:
        """
        List invocation history for an external agent.

        Args:
            agent_id: External agent ID
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            list[ExternalAgentInvocation]: Bare array (route returns no envelope)
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/external-agents/{encode_path_param(agent_id)}/invocations",
            params={"limit": limit, "offset": offset},
        )
        return [ExternalAgentInvocation(**item) for item in response]

    # -------------------
    # Gateways
    # -------------------

    async def create_gateway(
        self,
        name: str,
        api_url: str,
        api_key: str,
        description: str | None = None,
        environment: str = "development",
        health_check_url: str | None = None,
    ) -> Gateway:
        """
        Register a new Nexus gateway.

        Args:
            name: Gateway name
            api_url: Nexus gateway URL (SSRF-validated server-side)
            api_key: API key for gateway authentication (encrypted at rest)
            description: Optional description
            environment: development/staging/production
            health_check_url: Optional custom health-check endpoint

        Returns:
            Gateway: Created gateway record (encrypted key never returned)
        """
        data: dict[str, Any] = {
            "name": name,
            "api_url": api_url,
            "api_key": api_key,
            "environment": environment,
        }
        if description is not None:
            data["description"] = description
        if health_check_url is not None:
            data["health_check_url"] = health_check_url

        response = await self._http.request("POST", "/api/v1/gateways", json_data=data)
        return Gateway(**response)

    async def list_gateways(self, environment: str | None = None) -> GatewayList:
        """
        List gateways for the current organization.

        Args:
            environment: Optional environment filter

        Returns:
            GatewayList: gateways
        """
        params: dict[str, Any] | None = {"environment": environment} if environment else None
        response = await self._http.request("GET", "/api/v1/gateways", params=params)
        return GatewayList(**response)

    # -------------------
    # Deployments
    # -------------------

    async def create_deployment(
        self,
        agent_id: str,
        gateway_id: str,
        agent_version_id: str | None = None,
    ) -> Deployment:
        """
        Create and start a new deployment (deploys an agent to a gateway).

        Args:
            agent_id: Agent to deploy
            gateway_id: Target gateway
            agent_version_id: Optional specific agent version

        Returns:
            Deployment: Created deployment (status reflects actual outcome --
                "active" on success, "failed" with error_message on failure)
        """
        data: dict[str, Any] = {"agent_id": agent_id, "gateway_id": gateway_id}
        if agent_version_id is not None:
            data["agent_version_id"] = agent_version_id

        response = await self._http.request("POST", "/api/v1/deployments", json_data=data)
        return Deployment(**response)

    async def list_deployments(
        self,
        agent_id: str | None = None,
        gateway_id: str | None = None,
        status: str | None = None,
    ) -> DeploymentList:
        """
        List deployments for the organization.

        Args:
            agent_id: Optional agent filter
            gateway_id: Optional gateway filter
            status: Optional status filter

        Returns:
            DeploymentList: deployments
        """
        params: dict[str, Any] = {}
        if agent_id:
            params["agent_id"] = agent_id
        if gateway_id:
            params["gateway_id"] = gateway_id
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/deployments", params=params or None)
        return DeploymentList(**response)

    async def get_deployment(self, deployment_id: str) -> Deployment:
        """
        Get a deployment by ID.

        Args:
            deployment_id: Deployment ID

        Returns:
            Deployment: Deployment detail
        """
        response = await self._http.request(
            "GET", f"/api/v1/deployments/{encode_path_param(deployment_id)}"
        )
        return Deployment(**response)

    async def start_deployment(self, deployment_id: str) -> Deployment:
        """
        Resume a stopped or failed deployment.

        Re-registers the agent on the gateway and flips the existing record
        back to active. Distinct from redeploy(), which stops the deployment
        and recreates it as a new record.

        Args:
            deployment_id: Deployment ID

        Returns:
            Deployment: Updated deployment
        """
        response = await self._http.request(
            "POST", f"/api/v1/deployments/{encode_path_param(deployment_id)}/start"
        )
        return Deployment(**response)

    async def stop_deployment(self, deployment_id: str) -> Deployment:
        """
        Stop a deployment.

        Unregisters the agent from the gateway and updates status.

        Args:
            deployment_id: Deployment ID

        Returns:
            Deployment: Updated deployment
        """
        response = await self._http.request(
            "POST", f"/api/v1/deployments/{encode_path_param(deployment_id)}/stop"
        )
        return Deployment(**response)

    async def redeploy_deployment(self, deployment_id: str) -> Deployment:
        """
        Redeploy an existing deployment.

        Stops the current deployment and creates a new one with the same
        parameters.

        Args:
            deployment_id: Deployment ID

        Returns:
            Deployment: New deployment record
        """
        response = await self._http.request(
            "POST", f"/api/v1/deployments/{encode_path_param(deployment_id)}/redeploy"
        )
        return Deployment(**response)

    # -------------------
    # Notifications
    # -------------------

    async def stream_notifications(self) -> AsyncIterator[dict[str, Any]]:
        """
        Stream real-time notifications via Server-Sent Events (SSE).

        Fallback transport for environments where WebSocket is blocked
        (corporate proxies, etc.). Yields parsed SSE data payloads --
        connection/heartbeat/notification/error events as emitted by.

        Yields:
            dict: Parsed SSE event payload

        Example:
            >>> async for event in client.integrations.stream_notifications():
            ...     print(event)
        """
        async for event in self._http.stream("GET", "/api/v1/notifications/stream/sse"):
            yield event
