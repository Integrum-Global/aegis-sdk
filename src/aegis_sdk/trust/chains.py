"""
Agentic OS SDK Trust Chains Module.

Provides operations for managing trust chains following EATP (Enterprise Agent Trust Protocol).
Trust chains establish the foundation of trust from human origins to agent actions.
"""

import builtins
import warnings
from typing import Any

from pydantic import BaseModel, ConfigDict

from .._http import encode_path_param
from ..exceptions import UnsupportedOperationError
from ..types import (
    AgentTrustContext,
    CascadeRevocationResult,
    DelegationPath,
    EstablishedTrustChain,
    PaginatedResponse,
    RevocationImpact,
    TrustChain,
    TrustChainStatus,
    TrustVerification,
    TrustVerificationResult,
)


class TrustChainSummary(BaseModel):
    """Public projection of a trust chain.

    Warning:
        ``status`` does not distinguish a SUSPENDED chain from a chain
        suspended as part of a bridge revocation -- a revoked bridge-origin
        chain is recorded as ``suspended``. A status-only test for "is this
        revoked?" therefore admits it. Read the revocation surface when that
        distinction is load-bearing.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    trustor_agent_id: str | None = None
    trustee_agent_id: str | None = None
    delegation_type: str | None = None
    source_bridge_id: str | None = None
    status: str
    created_at: str


class ChainsModule:
    """
    Trust chain management operations.

    Trust chains provide the cryptographic foundation connecting agent actions
    to human authorization. They enable:
    - Traceable authorization from human origin
    - Capability-based access control
    - Constraint propagation through delegations
    - Revocation with cascade support

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # Establish a trust chain
        ...     chain = await client.trust.chains.establish(
        ...         agent_id="agent_abc123",
        ...         human_origin_data={"user_id": "user_123", "auth_method": "oauth2"},
        ...         capabilities=["read:data", "write:reports"]
        ...     )
        ...
        ...     # Verify an action
        ...     result = await client.trust.chains.verify(
        ...         agent_id="agent_abc123",
        ...         action="write",
        ...         resource="report_123"
        ...     )
        ...     if result.allowed:
        ...         print("Action authorized")
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def list(
        self,
        agent_id: str | None = None,
        human_origin_id: str | None = None,
        status: TrustChainStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse:
        """
        List trust chains with optional filters.

        Args:
            agent_id: Filter by agent
            human_origin_id: Filter by human origin
            status: Filter by chain status
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Paginated list of trust chains

        Example:
            >>> chains = await client.trust.chains.list(status="active")
            >>> print(f"Found {chains.total} active trust chains")
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if agent_id:
            params["agent_id"] = agent_id
        if human_origin_id:
            params["human_origin_id"] = human_origin_id
        if status:
            params["status"] = status.value if isinstance(status, TrustChainStatus) else status

        response = await self._http.request("GET", "/api/v1/trust/chains", params=params)
        return PaginatedResponse(
            items=[TrustChain(**item) for item in response.get("items", [])],
            total=response.get("total", 0),
            page=response.get("page", page),
            page_size=response.get("page_size", page_size),
            has_next=response.get("has_next", False),
        )

    async def establish(
        self,
        agent_id: str,
        authority_id: str,
        capabilities: builtins.list[str] | None = None,
        constraints: builtins.list[str] | None = None,
        expires_in_days: int | None = 365,
        human_origin_data: dict[str, Any] | None = None,
    ) -> EstablishedTrustChain:
        """
        Establish a new trust chain for an agent.

        Calls ``POST /api/v1/trust/establish`` with an
        ``EstablishTrustRequest`` body. Human origin is derived by the API
        from the AUTHENTICATED CALLER and is never client-supplied, which is
        why ``human_origin_data`` is accepted but ignored.

        Args:
            agent_id: Agent to establish trust for. Must belong to the
                caller's organization (server-side IDOR check).
            authority_id: The organizational authority establishing this
                trust chain. Required by the server — there is no default.
            capabilities: List of capabilities granted (default: none)
            constraints: List of constraint labels (server-side this is a
                ``list[str]``, NOT a dict — see ``GenesisRecord.constraints``)
            expires_in_days: Days until the trust chain expires (server
                default: 365)
            human_origin_data: Deprecated, ignored. The server derives human
                origin from the authenticated caller.

        Returns:
            The established trust chain (genesis + delegations + status).

        Raises:
            ValidationError: If trust chain cannot be established
            AuthorizationError: If caller cannot establish trust

        Example:
            >>> chain = await client.trust.chains.establish(
            ...     agent_id="agent_abc123",
            ...     authority_id="authority_xyz",
            ...     capabilities=["read:data", "write:reports"],
            ...     constraints=["max_cost:1000"],
            ... )
            >>> print(f"Trust chain established: {chain.agent_id}")
        """
        if human_origin_data is not None:
            warnings.warn(
                "establish(human_origin_data=...) is deprecated and ignored — "
                "the server derives human_origin from the authenticated caller "
                "(POST /api/v1/trust/establish). This "
                "parameter will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
        body = {
            "agent_id": agent_id,
            "authority_id": authority_id,
            "capabilities": capabilities or [],
            "constraints": constraints or [],
            "expires_in_days": expires_in_days if expires_in_days is not None else 365,
        }
        response = await self._http.request(
            "POST",
            "/api/v1/trust/establish",
            json_data=body,
        )
        return EstablishedTrustChain(**response)

    async def get(self, chain_id: str) -> TrustChain:
        """
        Get trust chain by ID.

        Args:
            chain_id: Trust chain ID (an agent id -- the route is keyed by
                agent, one chain per agent)

        Returns:
            Trust chain details

        Raises:
            NotFoundError: If chain doesn't exist

        .. warning::
            **Known limitation -- this method does not currently work.**
            ``GET /api/v1/trust/chains/{agent_id}`` returns the full EATP
            trust-lineage document (``genesis``, ``capabilities``,
            ``delegations``, ``constraint_envelope``, ``audit_anchors``,
            ``chain_hash``, ``verification``). That is a richer shape than
            the :class:`TrustChain` model this method constructs, and it
            carries no top-level ``agent_id``, ``status`` or ``human_origin``,
            so every call raises a Pydantic ``ValidationError`` client-side.
            A dedicated lineage model is a tracked follow-up. Use
            :meth:`list` for the summary shape in the meantime.

        Example:
            >>> chain = await client.trust.chains.get("chain_abc123")
            >>> print(f"Chain status: {chain.status}")
        """
        response = await self._http.request(
            "GET", f"/api/v1/trust/chains/{encode_path_param(chain_id)}"
        )
        return TrustChain(**response)

    async def verify(
        self,
        agent_id: str,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> TrustVerificationResult:
        """
        Verify if an agent action is authorized by the trust chain.

        Args:
            agent_id: Agent requesting the action
            action: Action to verify (e.g., "read", "write", "execute")
            resource: Resource the action targets
            context: Additional context for verification

        Returns:
            Verification result with authorization decision

        Example:
            >>> result = await client.trust.chains.verify(
            ...     agent_id="agent_abc123",
            ...     action="write",
            ...     resource="report_q4_2024",
            ...     context={"cost": 50}
            ... )
            >>> if result.allowed:
            ...     print(f"Authorized via chain: {result.chain_id}")
            ... else:
            ...     print(f"Denied: {result.reason}")
        """
        verify_data = TrustVerification(
            agent_id=agent_id,
            action=action,
            resource=resource,
            context=context or {},
        )
        response = await self._http.request(
            "POST",
            "/api/v1/trust/verify",
            json_data=verify_data.model_dump(),
        )
        return TrustVerificationResult(**response)

    async def revoke(
        self,
        agent_id: str,
        reason: str,
        cascade: bool | None = None,
    ) -> CascadeRevocationResult:
        """
        Revoke trust for an agent, cascading to all delegated agents.

        Calls ``POST /api/v1/trust/revoke/{agent_id}/cascade`` with a
        ``CascadeRevocationRequest`` body — just ``{"reason": ...}``.

        Revocation ALWAYS cascades to delegated agents. Both revoke routes
        behave this way, so there is no non-cascading revoke available; the
        ``cascade`` parameter is deprecated and ignored.

        Args:
            agent_id: Agent whose trust chain to revoke. Trust chains in
                this API are keyed by agent, not by a separate chain ID.
            reason: Reason for revocation
            cascade: Deprecated, ignored — the server always cascades.

        Returns:
            The cascade revocation result (revoked agent IDs, counts).

        Example:
            >>> result = await client.trust.chains.revoke(
            ...     "agent_abc123",
            ...     reason="Security incident",
            ... )
            >>> print(f"Revoked {result.total_revoked} agents")
        """
        if cascade is not None:
            warnings.warn(
                "revoke(cascade=...) is deprecated and ignored — the server "
                "always cascades revocation; there is no non-cascading "
                "revoke endpoint. This "
                "parameter will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
        response = await self._http.request(
            "POST",
            f"/api/v1/trust/revoke/{encode_path_param(agent_id)}/cascade",
            json_data={"reason": reason},
        )
        return CascadeRevocationResult(**response)

    async def suspend(self, agent_id: str, reason: str) -> None:
        """
        DEPRECATED — no backing server capability.

        The API exposes no route for suspending a trust chain directly.
        ``SUSPENDED`` exists as a trust-chain lifecycle state and is reached
        automatically during cascade revocation of bridge-sourced chains, but
        it is not a directly-invokable operation. This method is retained as
        a deprecation shim and will be removed in a future release.

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "ChainsModule.suspend() is deprecated and non-functional — no "
            "server route exists for suspending a trust chain directly. "
            "This method will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            "suspend() has no backing server route; direct trust-chain "
            "suspension is not currently supported by the Aegis API."
        )

    async def reinstate(self, agent_id: str) -> None:
        """
        DEPRECATED — no backing server capability.

        Mirror of :meth:`suspend` — the API exposes no route for reinstating
        a suspended trust chain. This method is retained as a deprecation
        shim and will be removed in a future release.

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "ChainsModule.reinstate() is deprecated and non-functional — no "
            "server route exists for reinstating a trust chain directly. "
            "This method will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            "reinstate() has no backing server route; direct trust-chain "
            "reinstatement is not currently supported by the Aegis API."
        )

    async def get_delegation_path(self, chain_id: str) -> DelegationPath:
        """
        Get the delegation path for a trust chain.

        Args:
            chain_id: Trust chain ID

        Returns:
            Delegation path from human origin to current agent

        Example:
            >>> path = await client.trust.chains.get_delegation_path("chain_abc123")
            >>> print(f"Delegation depth: {path.depth}")
            >>> for step in path.path:
            ...     print(f"  {step['from']} -> {step['to']}")
        """
        # GET /api/v1/trust/chains/{agent_id}/delegation-path. The delegation
        # path is keyed by agent id; pass the agent id for this chain.
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/chains/{encode_path_param(chain_id)}/delegation-path",
        )
        return DelegationPath(**response)

    async def get_agent_context(self, agent_id: str) -> AgentTrustContext:
        """
        Get the current trust context for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Agent's current trust context

        Example:
            >>> context = await client.trust.chains.get_agent_context("agent_abc123")
            >>> print(f"Posture: {context.posture}")
            >>> print(f"Capabilities: {context.capabilities}")
        """
        # GET /api/v1/trust/agents/{agent_id}/trust-context.
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/trust-context",
        )
        return AgentTrustContext(**response)

    async def analyze_revocation_impact(self, agent_id: str) -> RevocationImpact:
        """
        Preview the impact of cascade-revoking an agent's trust.

        Calls ``GET /api/v1/trust/revoke/{agent_id}/impact``, which returns a
        ``RevocationImpactPreview``. Trust chains in this API are keyed by
        agent, not by a separate chain ID.

        Args:
            agent_id: Agent whose trust would be revoked.

        Returns:
            Revocation impact preview (affected agents, active workloads).

        Example:
            >>> impact = await client.trust.chains.analyze_revocation_impact("agent_abc123")
            >>> print(f"Would affect {impact.total_affected} agents")
            >>> print(f"Active workloads at risk: {impact.has_active_workloads}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/revoke/{encode_path_param(agent_id)}/impact",
        )
        return RevocationImpact(**response)

    async def get_summary(self, agent_id: str) -> TrustChainSummary:
        """
        Get a lightweight projection of an agent's trust chain.

        This is the narrow public projection of a chain: identity, the two
        parties, how the delegation arose, and its lifecycle state. Use
        :meth:`get` for the full record.

        Args:
            agent_id: Agent whose chain is summarised. Chains are keyed by
                agent, not by a separate chain ID.

        Returns:
            The summary.

        Raises:
            NotFoundError: If the agent is unknown, belongs to another
                organization, or has no trust chain.

        Note:
            Fields may be ABSENT rather than null when selective-disclosure
            redaction is enabled and the caller's clearance does not reach
            them: ``trustor_agent_id``, ``trustee_agent_id`` and
            ``source_bridge_id`` are clearance-gated, while ``id``,
            ``status``, ``created_at`` and ``delegation_type`` are always
            visible. A ``None`` on a gated field therefore means "not
            disclosed to you" OR "genuinely absent", and this response cannot
            tell you which.

            ``source_bridge_id`` -- not ``delegation_type`` -- is what marks a
            chain as bridge-originated.

        Example:
            >>> summary = await client.trust.chains.get_summary("agent_abc123")
            >>> print(summary.status, summary.source_bridge_id)
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/chains/{encode_path_param(agent_id)}/summary",
        )
        return TrustChainSummary(**response)
