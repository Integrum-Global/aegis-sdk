"""
Aegis SDK Trust Authorities Module.

An organizational authority is the signing root a trust chain is established
under: agents are attested *by* an authority, and deactivating one is a
security transition that every chain established under it inherits.

Operations:
- list() / list_for_display(): enumerate authorities
- get() / get_for_display(): read one authority
- create(): register a new authority
- update(): rename / re-describe
- deactivate(): retire an authority (requires a reason)
- list_agents(): agents established under an authority
"""

import builtins
from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class OrganizationalAuthority(TolerantModel):
    """An organizational signing authority.

    Mirrors the platform's ``OrganizationalAuthority`` response model.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    organization_id: str
    public_key: str | None = None
    status: str = "active"
    created_at: str


class AuthorityDisplay(TolerantModel):
    """An authority enriched for display, with its established-agent count.

    The display routes return the authority fields above plus a merged agent
    count. The count is computed server-side by scanning trust chains; it is
    absent when the platform did not emit it, and is never defaulted to ``0``
    (an unknown count and a genuine zero are different facts).

    ``extra`` carries any additional keys the platform returns: these routes
    declare no response model, so their shape is authoritative only at
    runtime.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    name: str
    organization_id: str
    public_key: str | None = None
    status: str = "active"
    created_at: str
    agent_count: int | None = Field(None, alias="agentCount")


class AuthorityAgent(TolerantModel):
    """An agent whose genesis was established under an authority."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str | None = None
    established_at: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    status: str | None = None


class AuthoritiesModule:
    """
    Organizational trust authority operations.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     authorities = await client.trust.authorities.list()
        ...     for authority in authorities:
        ...         print(authority.name, authority.status)
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def list(self) -> list[OrganizationalAuthority]:
        """
        List authorities for the caller's organization.

        Returns:
            Every authority visible to the caller.

        Example:
            >>> authorities = await client.trust.authorities.list()
        """
        response = await self._http.request(
            "GET",
            "/api/v1/trust/authorities",
        )
        return [OrganizationalAuthority(**item) for item in response or []]

    async def get(self, authority_id: str) -> OrganizationalAuthority:
        """
        Get a single authority.

        Args:
            authority_id: Authority ID

        Returns:
            The authority.

        Raises:
            NotFoundError: If the authority does not exist, or belongs to
                another organization (cross-organization reads are answered
                as not-found, never as forbidden).
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/authorities/{encode_path_param(authority_id)}",
        )
        return OrganizationalAuthority(**response)

    async def create(
        self,
        name: str,
        description: str = "",
        authority_type: str = "organizational",
        public_key: str | None = None,
    ) -> OrganizationalAuthority:
        """
        Create an organizational authority.

        Args:
            name: Authority display name (1-200 characters)
            description: Free-text description (up to 2000 characters)
            authority_type: Authority type; defaults to ``organizational``
            public_key: Optional signing public key (up to 8192 characters)

        Returns:
            The created authority.

        Example:
            >>> authority = await client.trust.authorities.create(
            ...     name="Platform Engineering",
            ...     description="Root authority for platform agents",
            ... )
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": authority_type,
        }
        if public_key is not None:
            body["public_key"] = public_key

        response = await self._http.request(
            "POST",
            "/api/v1/trust/authorities",
            json_data=body,
        )
        return OrganizationalAuthority(**response)

    async def update(
        self,
        authority_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> OrganizationalAuthority:
        """
        Rename or re-describe an authority.

        Both fields are optional and absent fields are left unchanged. Supplying
        neither is a no-op the platform accepts.

        Args:
            authority_id: Authority ID
            name: New display name
            description: New description

        Returns:
            The updated authority.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description

        response = await self._http.request(
            "PATCH",
            f"/api/v1/trust/authorities/{encode_path_param(authority_id)}",
            json_data=body,
        )
        return OrganizationalAuthority(**response)

    async def deactivate(self, authority_id: str, reason: str) -> OrganizationalAuthority:
        """
        Deactivate an authority.

        Args:
            authority_id: Authority ID
            reason: Required justification, recorded on the deactivation audit
                entry. The platform rejects an empty reason.

        Returns:
            The deactivated authority.
        Raises:
            AgenticOSError: On a 409 conflict -- the authority is already inactive. The SDK maps NO
                exception subclass to 409, so this arrives as the BASE error
                rather than a conflict-specific type; discriminate on
                ``exc.details["status_code"] == 409``.

        Example:
            >>> await client.trust.authorities.deactivate(
            ...     "auth_abc123",
            ...     reason="Signing key rotated out of service",
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/trust/authorities/{encode_path_param(authority_id)}/deactivate",
            json_data={"reason": reason},
        )
        return OrganizationalAuthority(**response)

    async def list_agents(self, authority_id: str) -> builtins.list[AuthorityAgent]:
        """
        List agents whose trust chain genesis names this authority.

        Args:
            authority_id: Authority ID

        Returns:
            Agents established under the authority.

        Note:
            The platform scans a bounded page of trust chains to answer this,
            so an organization with a very large number of chains may see a
            partial list. The response carries no marker distinguishing a
            complete answer from a truncated one.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/authorities/{encode_path_param(authority_id)}/agents",
        )
        return [AuthorityAgent(**item) for item in response or []]

    async def list_for_display(
        self,
        status: str | None = None,
        search: str | None = None,
    ) -> builtins.list[AuthorityDisplay]:
        """
        List authorities enriched with their established-agent counts.

        Args:
            status: Filter by authority status
            search: Case-insensitive substring match on the authority name

        Returns:
            Authorities with display enrichment.
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if search is not None:
            params["search"] = search

        response = await self._http.request(
            "GET",
            "/api/v1/trust/authorities/ui",
            params=params or None,
        )
        return [AuthorityDisplay(**item) for item in response or []]

    async def get_for_display(self, authority_id: str) -> AuthorityDisplay:
        """
        Get one authority enriched with its established-agent count.

        Args:
            authority_id: Authority ID

        Returns:
            The authority with display enrichment.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/authorities/ui/{encode_path_param(authority_id)}",
        )
        return AuthorityDisplay(**response)
