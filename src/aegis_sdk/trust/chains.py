"""
Agentic OS SDK Trust Chains Module.

Provides operations for managing trust chains following EATP (Enterprise Agent Trust Protocol).
Trust chains establish the foundation of trust from human origins to agent actions.
"""

import builtins
import warnings
from typing import Any

from pydantic import ConfigDict, Field

from .._http import HTTPClient, encode_path_param
from .._tolerant import TolerantModel
from ..exceptions import UnsupportedOperationError, ValidationError
from ..types import (
    CascadeRevocationResult,
    DelegationPath,
    EstablishedTrustChain,
    PaginatedResponse,
    RevocationImpact,
    TrustChain,
    TrustChainStatus,
    TrustVerificationResult,
)


class TrustLineageGenesis(TolerantModel):
    """The genesis record at the root of a trust lineage.

    This is where a lineage document carries ``id``, ``agent_id`` and
    ``authority_id``. The lineage document has NO top-level fields of those
    names -- a reader looking for them one level too high finds nothing and,
    on a permissive model, reads three nulls beside fully-populated
    capability rows.

    Note:
        ``authority_id`` and ``created_at`` are ``None`` ONLY for a chain
        established before lineage signing existed, where the platform has no
        such record to report. On any chain established since, both are
        populated -- so a ``None`` here means "this chain predates the signed
        lineage", never "the value was lost in transit".
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    agent_id: str
    authority_type: str
    authority_id: str | None = None
    created_at: str | None = None
    agent_name: str | None = None
    expires_at: str | None = None
    signature: str = ""
    # Opaque signing metadata, carried through verbatim and never interpreted
    # here. Deliberately untyped: the platform owns this vocabulary, and
    # refusing a whole lineage document because a field the SDK does not read
    # arrived in an unexpected form would turn a cosmetic platform change into
    # an outage. The fields that carry MEANING -- id, agent_id, authority_id --
    # stay strictly required above.
    signature_algorithm: Any = None
    alg_id: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrustLineageCapability(TolerantModel):
    """One signed capability attestation within a lineage."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    capability: str
    capability_type: str
    attester_id: str
    attested_at: str
    constraints: builtins.list[str] = Field(default_factory=list)
    expires_at: str | None = None
    signature: str = ""
    # Opaque signing metadata -- see TrustLineageGenesis.alg_id.
    alg_id: Any = None
    scope: dict[str, Any] | None = None


class TrustChainLineage(TolerantModel):
    """The full signed EATP lineage document for one agent.

    Returned by :meth:`ChainsModule.get`. This is a RICHER shape than the
    summary projection :meth:`ChainsModule.list` yields, and it is nested:
    identity lives on :attr:`genesis`, not at the top level.

    Warning:
        ``verification`` carries the per-record trusted-key verdict. A chain
        established before lineage signing existed is returned with unsigned
        records and an ALL-FALSE verification block. That is an honest
        "unverified", never a claim of tampering -- do not read
        ``verified=False`` as a security finding without checking whether the
        record carries a signature at all.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    genesis: TrustLineageGenesis
    capabilities: builtins.list[TrustLineageCapability] = Field(default_factory=list)
    delegations: builtins.list[dict[str, Any]] = Field(default_factory=list)
    constraint_envelope: dict[str, Any] | None = None
    audit_anchors: builtins.list[dict[str, Any]] = Field(default_factory=list)
    chain_hash: str | None = None
    verification: dict[str, Any] = Field(default_factory=dict)

    @property
    def agent_id(self) -> str:
        """The agent this lineage belongs to, read from the genesis record."""
        return self.genesis.agent_id

    @property
    def authority_id(self) -> str | None:
        """The authority that established this lineage, or ``None``.

        ``None`` has ONE meaning here: this chain was established before
        lineage signing existed, so the platform holds no authority record to
        report for it. It never means the value was lost in transit -- see
        :class:`TrustLineageGenesis`. A caller that requires an authority must
        branch on this rather than assume a string; the platform populates it
        on every chain established since signing landed.
        """
        return self.genesis.authority_id


class AgentDelegationPath(DelegationPath):
    """Delegation path from the human root down to one agent.

    Extends :class:`~aegis_sdk.types.DelegationPath` with the depth ceiling the
    base model does not carry, and populates ``chain_id`` / ``depth`` from the
    platform's ``trust_chain_id`` / ``total_depth``.

    Note:
        ``chain_id`` is ``None`` for an agent with no established chain -- the
        platform answers that case with an empty path rather than an error, so
        ``None`` here means "no chain", not "failed to load".

        Each entry in ``path`` is keyed ``delegator_id`` / ``delegator_name`` /
        ``delegator_type`` / ``delegatee_id`` / ``delegatee_name`` /
        ``delegatee_type`` / ``delegated_at`` / ``capabilities`` /
        ``constraints_added``. There are no ``from`` / ``to`` keys.
    """

    chain_id: str | None = None  # type: ignore[assignment]
    path: builtins.list[dict[str, Any]] = Field(default_factory=list)
    depth: int = 0
    max_depth_allowed: int = 10


class TrustWarning(TolerantModel):
    """A computed advisory about an agent's trust standing."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str
    message: str
    severity: str


class AgentTrustContextDetail(TolerantModel):
    """Everything the platform knows about one agent's current trust standing.

    Composes the agent's chain, its delegation path, its position in that
    path, and any computed warnings.

    Note:
        ``trust_chain`` is ``None`` for an agent that exists but has no chain
        established yet. That is a normal state answered with a 200, not a
        404: the platform 404s only when the agent itself is unknown or
        belongs to another organization, so ``trust_chain is None`` tells you
        the agent is real and its chain is the thing still missing.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    trust_chain: TrustChain | None = None
    delegation_path: AgentDelegationPath = Field(default_factory=AgentDelegationPath)
    position: int = 0
    expires_in_days: int | None = None
    has_warnings: bool = False
    warnings: builtins.list[TrustWarning] = Field(default_factory=list)


class TrustVerificationOutcome(TrustVerificationResult):
    """Result of a trust verification, including the platform's reasoning.

    Extends :class:`~aegis_sdk.types.TrustVerificationResult` with the two
    lists the platform actually returns, which the base model does not carry:
    which capabilities matched, and which constraints were violated.

    Warning:
        ``chain_id`` and ``constraints_applied`` are inherited from the base
        model and are ALWAYS ``None`` / empty -- the verification route emits
        neither. Read :attr:`constraints_violated` for the constraints that
        decided a denial; ``constraints_applied`` is not its synonym and is
        not populated.
    """

    capabilities_matched: builtins.list[str] = Field(default_factory=list)
    constraints_violated: builtins.list[str] = Field(default_factory=list)


class TrustChainSummary(TolerantModel):
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

    def __init__(self, http_client: HTTPClient) -> None:
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

    async def get(self, chain_id: str) -> TrustChainLineage:
        """
        Get the full signed trust lineage for an agent.

        Args:
            chain_id: The agent whose lineage is read. Chains are keyed by
                agent -- one chain per agent -- so this is an agent id.

        Returns:
            The lineage document: genesis, capability attestations,
            delegations, the constraint envelope, audit anchors, the chain
            hash, and the per-record verification block.

        Raises:
            NotFoundError: If the agent has no trust chain.

        Note:
            Identity is NESTED on this route. ``id``, ``agent_id`` and
            ``authority_id`` live on :attr:`TrustChainLineage.genesis`, not at
            the top level; :attr:`TrustChainLineage.agent_id` and
            :attr:`TrustChainLineage.authority_id` are conveniences that read
            through to it. A consumer that looks for those three names at the
            top level of the raw response finds none of them.

            Use :meth:`list` or :meth:`get_summary` for the flat summary
            projection; they are a different, narrower shape.

        Example:
            >>> lineage = await client.trust.chains.get("agent_abc123")
            >>> print(lineage.genesis.authority_id, lineage.chain_hash)
            >>> for capability in lineage.capabilities:
            ...     print(capability.capability, capability.attester_id)
        """
        response = await self._http.request(
            "GET", f"/api/v1/trust/chains/{encode_path_param(chain_id)}"
        )
        return TrustChainLineage(**response)

    async def verify(
        self,
        agent_id: str,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> TrustVerificationOutcome:
        """
        Verify whether an agent's action is authorized by its trust chain.

        The target of an action is addressed as a KIND plus an optional
        INSTANCE -- ``resource_type`` says what sort of thing is being acted
        on, ``resource_id`` says which one. ``resource_type`` is required;
        omit ``resource_id`` to ask about the kind as a whole.

        Args:
            agent_id: Agent requesting the action.
            action: Action to verify (e.g. ``"read"``, ``"write"``,
                ``"execute"``).
            resource: Deprecated. A single undifferentiated string cannot
                express the kind/instance pair, so it is forwarded AS the kind
                when ``resource_type`` is absent, and read as the instance when
                ``resource_type`` is supplied alongside it. Pass the two
                explicitly instead.
            context: Deprecated, ignored. The verification route accepts no
                caller-supplied context and evaluates against the chain's own
                recorded constraints.
            resource_type: The kind of resource the action targets.
            resource_id: The specific resource instance, when the check is
                about one.

        Returns:
            The authorization decision, the capabilities that matched, and any
            constraints violated.

        Raises:
            ValidationError: If neither ``resource_type`` nor ``resource`` is
                supplied. The route requires a target and the SDK will not
                invent one: a fabricated resource kind would be written into
                the platform's audit record as though the caller had named it.

        Example:
            >>> result = await client.trust.chains.verify(
            ...     agent_id="agent_abc123",
            ...     action="write",
            ...     resource_type="report",
            ...     resource_id="report_q4_2024",
            ... )
            >>> if result.allowed:
            ...     print("Authorized:", result.capabilities_matched)
            ... else:
            ...     print("Denied:", result.reason, result.constraints_violated)
        """
        if context is not None:
            warnings.warn(
                "verify(context=...) is deprecated and ignored — the "
                "verification route accepts no caller-supplied context and "
                "evaluates against the trust chain's own recorded "
                "constraints. This parameter will be removed in a future "
                "release.",
                DeprecationWarning,
                stacklevel=2,
            )
        if resource is not None:
            warnings.warn(
                "verify(resource=...) is deprecated — the verification route "
                "addresses a target as resource_type (the kind) plus an "
                "optional resource_id (the instance). Pass resource_type, and "
                "resource_id where a specific instance is meant. This "
                "parameter will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
        # A caller who supplied only the legacy single string gets that string
        # forwarded AS the kind. This invents nothing -- it carries the
        # caller's own word into the one required target field -- and it cannot
        # change a verdict: the platform matches capabilities on `action`, and
        # reads resource_type only as an audit label.
        #
        # The "neither was supplied" refusal is the LAST arm of this same
        # dispatch rather than a separate guard above it. Written as a separate
        # guard the two forms stay in sync only by inspection, and the fact
        # that `kind` can never be None is something a reader has to
        # reconstruct from a condition several lines away. Here the arm that
        # binds `kind` from `resource` is reached only when `resource` is not
        # None, so `kind: str` is enforced by the control flow itself.
        kind: str
        instance: str | None
        if resource_type is not None:
            kind, instance = resource_type, (resource_id if resource_id is not None else resource)
        elif resource is not None:
            kind, instance = resource, resource_id
        else:
            raise ValidationError(
                "verify() requires resource_type — the kind of resource the "
                'action targets (for example "report" or "dataset"). The SDK '
                "will not substitute a placeholder: the platform records this "
                "value in its audit trail, so an invented kind would read as "
                "one the caller had named."
            )
        body: dict[str, Any] = {
            "agent_id": agent_id,
            "action": action,
            "resource_type": kind,
        }
        if instance is not None:
            body["resource_id"] = instance
        response = await self._http.request(
            "POST",
            "/api/v1/trust/verify",
            json_data=body,
        )
        return TrustVerificationOutcome(**response)

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

    async def get_delegation_path(self, chain_id: str) -> AgentDelegationPath:
        """
        Get the delegation path for an agent's trust chain.

        Args:
            chain_id: The agent whose path is read. Delegation paths are keyed
                by agent id.

        Returns:
            The ordered path from the human root down to this agent, its
            depth, and the depth ceiling in force.

        Note:
            The platform names these fields ``trust_chain_id`` and
            ``total_depth``; they are surfaced here as
            :attr:`~AgentDelegationPath.chain_id` and
            :attr:`~AgentDelegationPath.depth` to match the rest of this SDK.

            Path entries are keyed ``delegator_id`` / ``delegatee_id`` (plus
            ``*_name``, ``*_type``, ``delegated_at``, ``capabilities``,
            ``constraints_added``) -- there are no ``from`` / ``to`` keys.

        Example:
            >>> path = await client.trust.chains.get_delegation_path("agent_abc123")
            >>> print(f"Depth {path.depth} of {path.max_depth_allowed}")
            >>> for step in path.path:
            ...     print(f"  {step['delegator_id']} -> {step['delegatee_id']}")
        """
        # GET /api/v1/trust/chains/{agent_id}/delegation-path. The delegation
        # path is keyed by agent id; pass the agent id for this chain.
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/chains/{encode_path_param(chain_id)}/delegation-path",
        )
        return AgentDelegationPath(
            chain_id=response.get("trust_chain_id"),
            path=list(response.get("path") or []),
            depth=response.get("total_depth", 0),
            max_depth_allowed=response.get("max_depth_allowed", 10),
        )

    async def get_agent_context(self, agent_id: str) -> AgentTrustContextDetail:
        """
        Get the current trust context for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            The agent's chain, its delegation path, its position in that path,
            how long its authorization has left, and any computed warnings.

        Raises:
            NotFoundError: If the agent is unknown or belongs to another
                organization.

        Note:
            An agent that exists but has no chain established yet is answered
            with a normal result carrying ``trust_chain=None`` and an empty
            delegation path -- NOT a 404. The two cases are deliberately kept
            distinct: a 404 means the agent is not yours to see, while
            ``trust_chain is None`` means the agent is real and establishing
            its chain is the action that unblocks you.

        Example:
            >>> context = await client.trust.chains.get_agent_context("agent_abc123")
            >>> if context.trust_chain is None:
            ...     print("No trust chain established yet")
            ... else:
            ...     print("Status:", context.trust_chain.status)
            ...     print("Depth:", context.delegation_path.depth)
            >>> for warning in context.warnings:
            ...     print(warning.severity, warning.message)
        """
        # GET /api/v1/trust/agents/{agent_id}/trust-context.
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/trust-context",
        )
        path_data = response.get("delegation_path") or {}
        return AgentTrustContextDetail(
            trust_chain=response.get("trust_chain"),
            delegation_path=AgentDelegationPath(
                chain_id=path_data.get("trust_chain_id"),
                path=list(path_data.get("path") or []),
                depth=path_data.get("total_depth", 0),
                max_depth_allowed=path_data.get("max_depth_allowed", 10),
            ),
            position=response.get("position", 0),
            expires_in_days=response.get("expires_in_days"),
            has_warnings=response.get("has_warnings", False),
            warnings=[TrustWarning(**w) for w in response.get("warnings") or []],
        )

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
