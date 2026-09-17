"""
Aegis SDK Trust Registry Module.

The trust registry is the discovery surface over agents and their genesis
grants: register an agent, discover agents by capability, read an agent's
registry metadata, and record a heartbeat.

Operations:
- register(): register an agent in the trust registry
- discover(): find agents by capability, tag, or status
- get_metadata(): read one agent's registry entry
- heartbeat(): record agent liveness
"""

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class RegisteredAgent(TolerantModel):
    """An agent as returned by registration."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    agent_id: str
    name: str
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str
    registered_at: str
    last_heartbeat: str | None = None


class DiscoveredTrustAgent(TolerantModel):
    """An agent discovered through the trust registry.

    Discovery reads TRUST CHAINS, not the agent table: an agent with no chain
    is invisible here even if it exists and is running.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    status: str | None = None
    human_origin: dict[str, Any] | None = None


class AgentRegistryMetadata(TolerantModel):
    """Registry metadata for one agent, projected from its trust chain."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    status: str | None = None
    established_at: str | None = None
    human_origin: dict[str, Any] | None = None


class HeartbeatResult(TolerantModel):
    """Acknowledgement of a recorded heartbeat."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool
    timestamp: str


class TrustRegistryModule:
    """
    Trust registry operations.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     agents = await client.trust.registry.discover(
        ...         capabilities=["read:data"],
        ...     )
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def register(
        self,
        agent_id: str,
        name: str,
        capabilities: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> RegisteredAgent:
        """
        Register an agent in the trust registry.

        Args:
            agent_id: Caller-chosen agent ID. This becomes the agent's primary
                key -- it is not generated for you.
            name: Agent display name
            capabilities: Capabilities to record on the agent
            tags: Free-form tags

        Returns:
            The registered agent.

        Note:
            This call CREATES a durable agent record, not merely an index
            entry. It is a write, and requires a trust write scope.

        Example:
            >>> agent = await client.trust.registry.register(
            ...     agent_id="agent_abc123",
            ...     name="Reporting Agent",
            ...     capabilities=["read:data"],
            ... )
        """
        body: dict[str, Any] = {}
        if capabilities is not None:
            body["capabilities"] = capabilities
        if tags is not None:
            body["tags"] = tags

        response = await self._http.request(
            "POST",
            "/api/v1/trust/registry/agents",
            params={"agent_id": agent_id, "name": name},
            json_data=body or None,
        )
        return RegisteredAgent(**response)

    async def discover(
        self,
        capabilities: list[str] | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
    ) -> list[DiscoveredTrustAgent]:
        """
        Discover agents through their trust chains.

        Args:
            capabilities: Require ALL of these capabilities. Matching is a
                subset test, not a scoring or ranking function.
            tags: Tags to match
            status: Filter by chain status

        Returns:
            Matching agents.

        Note:
            The platform scans a bounded page of trust chains, so a very large
            organization may see a partial result set with no marker saying so.
        """
        body: dict[str, Any] = {}
        if capabilities is not None:
            body["capabilities"] = capabilities
        if tags is not None:
            body["tags"] = tags

        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status

        response = await self._http.request(
            "POST",
            "/api/v1/trust/registry/discover",
            params=params or None,
            json_data=body or None,
        )
        return [DiscoveredTrustAgent(**item) for item in response or []]

    async def get_metadata(self, agent_id: str) -> AgentRegistryMetadata:
        """
        Get an agent's registry metadata.

        Args:
            agent_id: Agent ID

        Returns:
            The registry entry, projected from the agent's trust chain.

        Raises:
            NotFoundError: If the agent does not exist, belongs to another
                organization, or has no trust chain.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/registry/agents/{encode_path_param(agent_id)}",
        )
        return AgentRegistryMetadata(**response)

    async def heartbeat(self, agent_id: str) -> HeartbeatResult:
        """
        Record a liveness heartbeat for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Acknowledgement carrying the server timestamp.

        Warning:
            This is a WRITE, and it is not purely a timestamp update. If
            ``agent_id`` names no existing agent in the caller's organization,
            the platform CREATES an active agent record under that ID rather
            than rejecting the call. Heartbeating an id you have not registered
            therefore mints an agent. It requires a trust write scope for that
            reason, and it can never write into another organization -- the new
            record is stamped with the caller's own organization.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/trust/registry/agents/{encode_path_param(agent_id)}/heartbeat",
        )
        return HeartbeatResult(**response)
