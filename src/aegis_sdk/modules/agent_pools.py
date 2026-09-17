"""
Agent Pools SDK Module.

An *agent pool* is a named group that work can be routed to, with its own
claim and escalation timing. Membership is keyed by **role**, not by user or
by agent: a pool holds role slots, and whoever occupies the role is in the
pool. This is why :meth:`AgentPoolsModule.add_member` takes a ``role_id`` and
:meth:`AgentPoolsModule.remove_member` addresses the member by role.

Provides programmatic access to pool lifecycle and membership:

- list(): List pools in the caller's organization
- get(): Read one pool
- create(): Create a pool
- update(): Update pool attributes and timings
- delete(): Delete a pool
- list_members() / add_member() / remove_member(): Role membership

⛔ AUTH: this surface admits a USER SESSION only. Its router gate does not
accept an API key, and an API-key principal carries no role and no personas
by design, so every method here answers 403 for a client built with
``api_key=``. Use the OAuth configuration instead.

Distinct from the operational pool surface exposed by ``client.pools``, which
covers task claiming, draining and load distribution for pools that already
exist. This module is the registry: it defines pools and who is in them.

Contract note: apart from the two deletions, which answer 204 with no body,
none of these operations declares a response schema. The pagination envelopes
below are modelled because the platform emits them consistently and they are
observable, but each record inside is carried as ``dict[str, Any]`` rather
than typed against a guess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


class AgentPoolList(TolerantModel):
    """
    A page of agent pools.

    ``records`` holds the backend-shaped pool payloads. They are not modelled:
    the list operation declares no response schema, so a typed shape here
    would be an assertion the platform does not currently make.
    """

    model_config = ConfigDict(populate_by_name=True)

    records: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    limit: int | None = None
    offset: int | None = None


class AgentPoolMemberList(TolerantModel):
    """
    A pool's role members.

    ``records`` holds the backend-shaped membership payloads, enriched by the
    platform with the occupying user where one exists. Unmodelled for the same
    reason as :class:`AgentPoolList`.
    """

    model_config = ConfigDict(populate_by_name=True)

    records: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class AgentPoolsModule:
    """
    Agent Pools SDK module.

    Methods:
        - list(): List pools in the organization
        - get(): Read one pool
        - create(): Create a pool
        - update(): Update pool attributes and timings
        - delete(): Delete a pool
        - list_members(): List a pool's role members
        - add_member(): Add a role to a pool
        - remove_member(): Remove a role from a pool

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(
        ...     api_key="your-api-key", base_url="https://your-host"
        ... )
        >>>
        >>> pools = await client.agent_pools.list(status="active")
        >>> pool = await client.agent_pools.create(name="Triage")
        >>> await client.agent_pools.add_member(
        ...     pool["id"], role_id="role-123", pool_role="member"
        ... )
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize Agent Pools module with HTTP client."""
        self._http = http_client

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        department: str | None = None,
    ) -> AgentPoolList:
        """
        List agent pools in the caller's organization.

        Args:
            limit: Page size (1-200)
            offset: Page offset
            status: Filter by status, e.g. ``active`` or ``archived``
            department: Filter by department

        Returns:
            A page of pools, with ``count`` for the total

        Example:
            >>> page = await client.agent_pools.list(status="active")
            >>> for pool in page.records:
            ...     print(pool["name"])
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if department is not None:
            params["department"] = department

        response = await self._http.request(
            "GET", "/api/v1/agent-pools", params=params
        )
        return AgentPoolList(**response)

    async def get(self, pool_id: str) -> dict[str, Any]:
        """
        Get one agent pool, enriched with its member count.

        Args:
            pool_id: Pool ID

        Returns:
            The backend-shaped pool payload.

        Note:
            This operation declares no response schema, so the payload is
            returned unmodelled rather than typed against a guess.

        Example:
            >>> pool = await client.agent_pools.get("pool-123")
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/agent-pools/{encode_path_param(pool_id)}"
        )
        return payload

    async def create(
        self,
        name: str,
        description: str | None = None,
        department: str | None = None,
        workspace_id: str | None = None,
        claim_timeout_minutes: int | None = None,
        pool_timeout_minutes: int | None = None,
        load_balancing_strategy: str | None = None,
        required_capabilities_json: str | None = None,
        escalation_target_type: str | None = None,
        escalation_target_id: str | None = None,
        config_json: str | None = None,
    ) -> dict[str, Any]:
        """
        Create an agent pool.

        Only ``name`` is required; every other attribute takes a platform
        default when omitted. The pool is created empty — add role members
        with :meth:`add_member`.

        Args:
            name: Pool name
            description: Optional description
            department: Owning department
            workspace_id: Workspace the pool belongs to
            claim_timeout_minutes: How long a claim on a task may be held
            pool_timeout_minutes: How long work may sit in the pool before
                escalation applies
            load_balancing_strategy: How work is distributed across members
            required_capabilities_json: Capability requirement, as a JSON
                string
            escalation_target_type: What kind of target work escalates to
            escalation_target_id: The escalation target itself; validated
                against the target type by the platform
            config_json: Additional configuration, as a JSON string

        Returns:
            The backend-shaped created pool payload.

        Note:
            This operation declares no response schema; see :meth:`get`.

        Example:
            >>> pool = await client.agent_pools.create(
            ...     name="Triage", claim_timeout_minutes=30
            ... )
        """
        body: dict[str, Any] = {"name": name}
        optional = {
            "description": description,
            "department": department,
            "workspace_id": workspace_id,
            "claim_timeout_minutes": claim_timeout_minutes,
            "pool_timeout_minutes": pool_timeout_minutes,
            "load_balancing_strategy": load_balancing_strategy,
            "required_capabilities_json": required_capabilities_json,
            "escalation_target_type": escalation_target_type,
            "escalation_target_id": escalation_target_id,
            "config_json": config_json,
        }
        body.update({k: v for k, v in optional.items() if v is not None})

        payload: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/agent-pools", json_data=body
        )
        return payload

    async def update(
        self,
        pool_id: str,
        name: str | None = None,
        description: str | None = None,
        department: str | None = None,
        claim_timeout_minutes: int | None = None,
        pool_timeout_minutes: int | None = None,
        load_balancing_strategy: str | None = None,
        required_capabilities_json: str | None = None,
        escalation_target_type: str | None = None,
        escalation_target_id: str | None = None,
        config_json: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """
        Update an agent pool.

        Only the arguments supplied are sent, so omitting one leaves the
        stored value untouched. ``workspace_id`` is absent deliberately — the
        platform does not accept a pool moving workspace through this
        operation.

        Args:
            pool_id: Pool ID
            name: New name
            description: New description
            department: New owning department
            claim_timeout_minutes: New claim timeout (1-1440)
            pool_timeout_minutes: New pool timeout (1-10080)
            load_balancing_strategy: New distribution strategy
            required_capabilities_json: New capability requirement
            escalation_target_type: New escalation target kind
            escalation_target_id: New escalation target
            config_json: New additional configuration
            status: New status, e.g. ``active`` or ``archived``

        Returns:
            The backend-shaped updated pool payload.

        Note:
            This operation declares no response schema; see :meth:`get`.

        Example:
            >>> await client.agent_pools.update("pool-123", status="archived")
        """
        candidates = {
            "name": name,
            "description": description,
            "department": department,
            "claim_timeout_minutes": claim_timeout_minutes,
            "pool_timeout_minutes": pool_timeout_minutes,
            "load_balancing_strategy": load_balancing_strategy,
            "required_capabilities_json": required_capabilities_json,
            "escalation_target_type": escalation_target_type,
            "escalation_target_id": escalation_target_id,
            "config_json": config_json,
            "status": status,
        }
        body = {k: v for k, v in candidates.items() if v is not None}

        payload: dict[str, Any] = await self._http.request(
            "PUT",
            f"/api/v1/agent-pools/{encode_path_param(pool_id)}",
            json_data=body,
        )
        return payload

    async def delete(self, pool_id: str) -> None:
        """
        Delete an agent pool.

        Args:
            pool_id: Pool ID

        Returns:
            None — the platform answers 204 with no body.

        Example:
            >>> await client.agent_pools.delete("pool-123")
        """
        await self._http.request(
            "DELETE", f"/api/v1/agent-pools/{encode_path_param(pool_id)}"
        )

    async def list_members(self, pool_id: str) -> AgentPoolMemberList:
        """
        List a pool's role members.

        Members are roles. Where a role is currently occupied, the platform
        enriches the record with the occupying user; a vacant role is still a
        member of the pool.

        Args:
            pool_id: Pool ID

        Returns:
            The pool's role members

        Example:
            >>> members = await client.agent_pools.list_members("pool-123")
            >>> members.count
            3
        """
        response = await self._http.request(
            "GET", f"/api/v1/agent-pools/{encode_path_param(pool_id)}/members"
        )
        return AgentPoolMemberList(**response)

    async def add_member(
        self, pool_id: str, role_id: str, pool_role: str | None = None
    ) -> dict[str, Any]:
        """
        Add a role to a pool.

        Args:
            pool_id: Pool ID
            role_id: Role to add; the pool holds the role, not its occupant
            pool_role: The role's function within the pool; a platform
                default applies when omitted

        Returns:
            The backend-shaped membership payload.

        Note:
            This operation declares no response schema; see :meth:`get`.

        Example:
            >>> await client.agent_pools.add_member("pool-123", "role-456")
        """
        body: dict[str, Any] = {"role_id": role_id}
        if pool_role is not None:
            body["pool_role"] = pool_role

        payload: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/agent-pools/{encode_path_param(pool_id)}/members",
            json_data=body,
        )
        return payload

    async def remove_member(self, pool_id: str, role_id: str) -> None:
        """
        Remove a role from a pool.

        The member is addressed by ROLE, matching how it was added — there is
        no user-keyed removal, because membership is not user-keyed.

        Args:
            pool_id: Pool ID
            role_id: Role to remove

        Returns:
            None — the platform answers 204 with no body.

        Example:
            >>> await client.agent_pools.remove_member("pool-123", "role-456")
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/agent-pools/{encode_path_param(pool_id)}/role-members/{encode_path_param(role_id)}",
        )
