"""
Agentic OS SDK Trust Delegations Module.

Provides operations for managing trust delegations between agents.
Delegations allow agents to grant subsets of their capabilities to other agents.
"""

import builtins
import warnings
from typing import Any

from .._http import encode_path_param
from ..exceptions import NotFoundError, UnsupportedOperationError, ValidationError
from ..types import (
    DelegationStatus,
    PaginatedResponse,
    TrustDelegation,
)


class DelegationsModule:
    """
    Trust delegation management operations.

    Delegations enable agents to grant capabilities to other agents,
    creating a delegation chain that maintains traceability to the
    human origin. All delegations must be subsets of the delegator's
    capabilities.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # Create a delegation
        ...     delegation = await client.trust.delegations.create(
        ...         chain_id="chain_abc123",
        ...         delegator_id="agent_parent",
        ...         delegatee_id="agent_child",
        ...         capabilities=["read:data"]  # Subset of parent's capabilities
        ...     )
        ...
        ...     # Revoke when done
        ...     await client.trust.delegations.revoke(
        ...         delegation.id,
        ...         reason="Task completed"
        ...     )
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def list(
        self,
        chain_id: str | None = None,
        delegator_id: str | None = None,
        delegatee_id: str | None = None,
        status: DelegationStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse:
        """
        DEPRECATED — no backing server capability.

        No server route exists for listing delegations as first-class
        resources. This backend has no separate delegation entity at all —
        searched the published API for a ``/delegations`` route on
        2026-07-13, none found. Delegations exist only as inline
        ``DelegationRecord`` entries embedded in a trust chain's
        ``delegations`` list (``TrustChain.delegations``), retrievable per-agent via
        ``GET /trust/chains/{agent_id}`` or ``GET
        /trust/chains/{agent_id}/delegation-path`` — not as a flat,
        filterable collection. Kept as a deprecation shim per
        zero-tolerance Rule 6a; will be removed in a future release.

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "DelegationsModule.list() is deprecated and non-functional — no "
            "server route exists for listing delegations as first-class "
            "resources (the API serves no matching "
            "/delegations endpoint; delegations only exist inline within "
            "a trust chain's `delegations` list, see GET "
            "/trust/chains/{agent_id}). This method will be removed in a "
            "future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            "list() has no backing server route; there is no first-class "
            "delegation-listing endpoint on the Aegis API. Fetch a trust "
            "chain via client.trust.chains.get(agent_id) and read its "
            "`delegations` field instead."
        )

    async def create(
        self,
        chain_id: str,
        delegator_id: str,
        delegatee_id: str,
        capabilities: builtins.list[str],
        constraints: dict[str, Any] | None = None,
    ) -> TrustDelegation:
        """
        Create a new delegation.

        Server route: POST /trust/delegate (DelegateTrustRequest at :192-199). There is no
        "/chains/{chain_id}/delegations" sub-resource on the real
        backend — trust chains are addressed by agent_id, not a separate
        chain_id, and the delegator's existing chain is resolved
        server-side. ``chain_id`` is retained on this SDK's stored
        :class:`TrustDelegation` result (it is NOT sent over the wire —
        the server has no field for it) so callers keep a stable
        reference to which chain this delegation extends.

        The real ``DelegateTrustRequest.constraints`` field is
        ``list[str]``, not a dict — dict constraints are serialized to
        ``"key=value"`` wire strings; this SDK's ``TrustDelegation``
        result still carries the original dict for API-shape stability.

        The real ``DelegationRecord`` response has no ``id`` / ``status``
        fields — this backend has no
        first-class delegation entity. A stable composite id
        (``"{delegator_id}:{delegatee_id}"``) is synthesized so
        :meth:`revoke` can address this delegation later.

        Args:
            chain_id: Trust chain to delegate from (the delegator's own
                agent_id in this backend — see GET /trust/chains/{agent_id})
            delegator_id: Agent granting the delegation
            delegatee_id: Agent receiving the delegation
            capabilities: Capabilities to delegate (must be subset of delegator's)
            constraints: Additional constraints on the delegation

        Returns:
            Created delegation

        Raises:
            ValidationError: If capabilities exceed delegator's capabilities
            AuthorizationError: If delegator cannot delegate

        Example:
            >>> delegation = await client.trust.delegations.create(
            ...     chain_id="agent_coordinator",
            ...     delegator_id="agent_coordinator",
            ...     delegatee_id="agent_worker",
            ...     capabilities=["read:data", "execute:analysis"],
            ...     constraints={"max_runtime": "3600", "sandbox": "True"}
            ... )
        """
        constraints = constraints or {}
        wire_constraints = [f"{key}={value}" for key, value in constraints.items()]
        response = await self._http.request(
            "POST",
            "/api/v1/trust/delegate",
            json_data={
                "delegator_id": delegator_id,
                "delegatee_id": delegatee_id,
                "capabilities": capabilities,
                "constraints": wire_constraints,
            },
        )
        return TrustDelegation(
            id=f"{response['delegator_id']}:{response['delegatee_id']}",
            chain_id=chain_id,
            delegator_id=response["delegator_id"],
            delegatee_id=response["delegatee_id"],
            capabilities=response["capabilities"],
            constraints=constraints,
            status=DelegationStatus.ACTIVE,
            created_at=response.get("created_at"),
            revoked_at=None,
        )

    async def get(self, delegation_id: str) -> TrustDelegation:
        """
        DEPRECATED — no backing server capability.

        No server route exists for fetching a single delegation by ID —
        searched the published API for a ``/delegations/{id}``
        route on 2026-07-13, none found. This backend has no first-class
        delegation entity to address by ID (see :meth:`list`). Kept as a
        deprecation shim per zero-tolerance Rule 6a; will be removed in a
        future release.

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "DelegationsModule.get() is deprecated and non-functional — no "
            "server route exists for fetching a single delegation by ID "
            "(the API serves no matching /delegations/{id} "
            "endpoint). This method will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            f"get({delegation_id!r}) has no backing server route; there is "
            "no first-class delegation-by-ID endpoint on the Aegis API."
        )

    async def revoke(
        self,
        delegation_id: str,
        reason: str,
        cascade: bool = True,
    ) -> TrustDelegation:
        """
        Revoke a delegation.

        Server route: POST /trust/revoke-delegation — query params ``delegatee_id``,
        ``delegator_id``, ``reason`` (NOT a JSON body, and NOT addressed
        by a delegation ID). This backend has no delegation-ID concept,
        so ``delegation_id`` MUST be the composite
        ``"{delegator_id}:{delegatee_id}"`` key returned by :meth:`create`.

        Revocation ALWAYS cascades server-side — ``revoke_cascade`` runs
        unconditionally; there is no
        non-cascading revoke on this backend. ``cascade=False`` is
        deprecated and ignored (a cascading revoke still runs); this
        mirrors ``ChainsModule.revoke(cascade=...)``'s deprecation shape
        (src/aegis_sdk/trust/).

        The revoke-delegation response carries no delegation detail (only
        a cascade-revocation summary), so this method fetches the
        delegatee's trust chain FIRST to (a) verify the delegation
        actually exists — raising NotFoundError, not a bare 404, if it
        does not — and (b) recover its real creation timestamp /
        capabilities rather than fabricating them
        ( MUST-NOT-1 "No Fabricated Data in Production").
        ``GET /trust/chains/{agent_id}`` emits the rich EATP lineage shape,
        whose delegation entries use ``capabilities_delegated`` /
        ``delegated_at`` — NOT the plain ``capabilities`` / ``created_at``
        names the ``POST /trust/delegate`` response uses.

        Args:
            delegation_id: Delegation ID — the "{delegator_id}:{delegatee_id}"
                composite key returned by create()
            reason: Reason for revocation
            cascade: Deprecated, ignored — the server always cascades.

        Returns:
            Revoked delegation

        Raises:
            NotFoundError: If the delegation does not exist
            ValidationError: If delegation_id is not a valid composite key

        Example:
            >>> delegation = await client.trust.delegations.revoke(
            ...     "agent_coordinator:agent_worker",
            ...     reason="Task completed",
            ... )
        """
        if not cascade:
            warnings.warn(
                "revoke(cascade=False) is deprecated and ignored — the "
                "server always cascades revocation "
                "; there is no "
                "non-cascading revoke endpoint. A cascading revoke will "
                "still be performed. This parameter will be removed in a "
                "future release.",
                DeprecationWarning,
                stacklevel=2,
            )

        try:
            delegator_id, delegatee_id = delegation_id.split(":", 1)
        except ValueError as e:
            raise ValidationError(
                "delegation_id must be the '{delegator_id}:{delegatee_id}' "
                f"composite key returned by create(); got {delegation_id!r}"
            ) from e

        # Verify the delegation exists and recover its real created_at /
        # capabilities before revoking (see docstring above).
        chain = await self._http.request(
            "GET", f"/api/v1/trust/chains/{encode_path_param(delegatee_id)}"
        )
        record = next(
            (
                d
                for d in chain.get("delegations", [])
                if d.get("delegator_id") == delegator_id and d.get("delegatee_id") == delegatee_id
            ),
            None,
        )
        if record is None:
            raise NotFoundError(f"Delegation {delegation_id!r} not found")

        response = await self._http.request(
            "POST",
            "/api/v1/trust/revoke-delegation",
            params={
                "delegatee_id": delegatee_id,
                "delegator_id": delegator_id,
                "reason": reason,
            },
        )
        return TrustDelegation(
            id=delegation_id,
            chain_id=delegator_id,
            delegator_id=delegator_id,
            delegatee_id=delegatee_id,
            capabilities=record.get("capabilities_delegated", []),
            constraints={},
            status=DelegationStatus.REVOKED,
            created_at=record["delegated_at"],
            revoked_at=response.get("completed_at"),
        )

    async def get_for_agent(
        self,
        agent_id: str,
        include_granted: bool = True,
        include_received: bool = True,
    ) -> builtins.list[TrustDelegation]:
        """
        DEPRECATED — no backing server capability.

        No server route exists for listing an agent's delegations —
        searched the published API for a
        ``/agents/{agent_id}/delegations`` route on 2026-07-13, none
        found. A PARTIAL substitute exists for ``include_received`` only:
        ``GET /trust/chains/{agent_id}``
        returns the agent's full chain lineage, whose ``delegations``
        list contains every delegation RECEIVED along the path from
        genesis to this agent. There is no equivalent for delegations
        GRANTED by this agent (that data lives in the chains of whichever
        agents it delegated to, which are not enumerable from here).
        Because this method's contract promises both directions and only
        one is servable, it is kept as a deprecation shim per
        zero-tolerance Rule 6a rather than silently returning a partial
        result; will be removed in a future release.

        Args:
            agent_id: Agent ID
            include_granted: Include delegations granted by this agent
            include_received: Include delegations received by this agent

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.

        Example:
            >>> # Partial substitute for received-only:
            >>> chain = await client.trust.chains.get("agent_abc123")
            >>> received = [d for d in chain.delegations if d.delegatee_id == "agent_abc123"]
        """
        warnings.warn(
            "DelegationsModule.get_for_agent() is deprecated and "
            "non-functional — no server route exists for listing an "
            "agent's delegations (the API serves no matching "
            "/agents/{agent_id}/delegations endpoint). For received "
            "delegations only, use client.trust.chains.get(agent_id) and "
            "filter its `delegations` field. This method will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            f"get_for_agent({agent_id!r}) has no backing server route; "
            "there is no delegation-listing-by-agent endpoint on the "
            "Aegis API. Use client.trust.chains.get(agent_id) for "
            "received delegations."
        )
