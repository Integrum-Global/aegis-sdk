"""
Bridges SDK Module.

Bridges connect ROLES across organizational boundaries, and the operating
envelope of any interaction over one is the INTERSECTION of the two sides —
never the union. Nothing in this module widens an envelope: every method here
addresses a server route that performs its own authorization, and the client is
a typed caller of that route, not a second opinion about it.

Three bridge kinds, three server routers, three namespaces here:

- ``standing``  — permanent, role-anchored collaboration channels. Dual
  authorization (one call per side) then activation; suspend/revoke/review.
- ``scoped``    — temporary channels bounded by a workspace or objective, with
  a participant set that can be added to and removed from.
- ``ad_hoc``    — request/approve channels raised against a unit, carrying an
  urgency and an expiry.

The three are DISTINCT records in distinct tables. A scoped-bridge id handed to
an ad-hoc method addresses a different record type and answers 404; the
namespaces exist so that mismatch is visible at the call site rather than
discovered from an error message.

Example:
    >>> bridges = await client.bridges.standing.list(status="active")
    >>> for b in bridges.records:
    ...     if not b.trust_consistent:
    ...         print(f"{b.name} is active with no trust chains behind it")
"""

from __future__ import annotations

import builtins
from typing import Any

from pydantic import ConfigDict, Field

from .._http import HTTPClient, encode_path_param
from .._tolerant import TolerantModel

# ===================
# Models
# ===================


class StandingBridge(TolerantModel):
    """A permanent, role-anchored collaboration channel between two units."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str
    name: str
    unit_a_id: str
    unit_b_id: str
    bridge_type: str
    interaction_mode: str
    purpose: str
    description: str | None = None
    role_a_id: str | None = None
    role_b_id: str | None = None
    bridge_topology: str | None = "role_to_role"
    is_bidirectional: bool
    allowed_interactions_json: str = "[]"
    prohibited_interactions_json: str = "[]"
    shared_knowledge_paths_json: str = "[]"
    knowledge_sharing_level: str
    requires_approval_above_json: str = "{}"
    escalation_triggers_json: str = "[]"
    authorization_required: bool
    authorized_by_a_user_id: str | None = None
    authorized_by_b_user_id: str | None = None
    authorization_date: str | None = None
    status: str
    review_at: str | None = None
    expires_at: str | None = None
    metadata_json: str = "{}"
    created_at: str
    updated_at: str
    bridge_trust_chain_id: str | None = None
    # COMPUTED SERVER-SIDE, never accepted from a caller. A bridge with
    # status="active" and no trust delegations behind it reads False here
    # instead of presenting as healthy — read it before treating an active
    # bridge as one that actually carries trust.
    trust_consistent: bool = True


class StandingBridgeList(TolerantModel):
    """A page of standing bridges."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[StandingBridge] = Field(default_factory=list)
    total: int = 0


class OverdueBridge(TolerantModel):
    """A standing bridge past its periodic-review date."""

    model_config = ConfigDict(populate_by_name=True)

    bridge_id: str
    name: str
    organization_id: str
    last_reviewed_at: str | None = None
    review_interval_days: int | None = None
    days_overdue: int | None = None


class InteractionCheck(TolerantModel):
    """Whether one interaction type is permitted over a standing bridge."""

    model_config = ConfigDict(populate_by_name=True)

    allowed: bool
    bridge_id: str
    interaction_type: str
    # A denial with no reason is unactionable; the server populates this.
    reason: str | None = None


class BridgeReview(TolerantModel):
    """The recorded outcome of a periodic bridge review."""

    model_config = ConfigDict(populate_by_name=True)

    bridge_id: str
    reviewer_role_id: str
    approved: bool
    notes: str
    reviewed_at: str


class ScopedBridge(TolerantModel):
    """A temporary channel bounded by a workspace or an objective."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str
    # Optional: servers that removed the Workspace entity emit null here (the
    # key is kept for older clients). Null means "no workspace"; it grants nothing.
    workspace_id: str | None = None
    name: str
    objective_id: str | None = None
    objective: str
    participants_json: str
    owner_unit_id: str
    purpose: str
    scope_description: str
    active_from: str
    active_until: str
    starts_at: str
    expires_at: str | None = None
    created_by_user_id: str | None = None
    allowed_interactions_json: str = "[]"
    shared_knowledge_paths_json: str = "[]"
    auto_expire_on_objective_completion: bool
    status: str
    metadata_json: str = "{}"
    created_at: str
    updated_at: str


class Participant(TolerantModel):
    """One participating unit of a scoped bridge.

    ``unit_id`` is the only field the server guarantees: it is the key every
    read path uses. ``roles``, ``constraints`` and ``added_at`` are filled in
    when a participant is added through the add-participant endpoint, but a
    participant supplied at bridge-creation time is persisted exactly as the
    caller wrote it and may carry none of them. Unknown keys are preserved
    rather than dropped, for the same reason.
    """

    model_config = ConfigDict(extra="allow")

    unit_id: str
    roles: builtins.list[str] | None = None
    constraints: dict[str, Any] | None = None
    added_at: str | None = None


class ScopedBridgeList(TolerantModel):
    """A page of scoped bridges."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[ScopedBridge] = Field(default_factory=list)
    total: int = 0


class AdHocBridge(TolerantModel):
    """A request/approve channel raised against a unit, with an expiry."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str
    name: str
    initiator_unit_id: str
    target_unit_id: str
    requested_by_user_id: str
    approved_by_user_id: str | None = None
    urgency: str
    reason: str
    requested_capabilities_json: str = "[]"
    status: str
    expires_at: str
    max_duration_minutes: int
    activated_at: str | None = None
    completed_at: str | None = None
    completion_notes: str | None = None
    metadata_json: str = "{}"
    created_at: str
    updated_at: str


class DeleteResult(TolerantModel):
    """Server acknowledgement of a delete."""

    model_config = ConfigDict(populate_by_name=True)

    message: str


# ===================
# Standing bridges
# ===================


class StandingBridgesModule:
    """Permanent, role-anchored collaboration channels."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize the standing-bridges module with an HTTP client."""
        self._http = http_client

    async def create(
        self,
        name: str,
        role_a_id: str,
        role_b_id: str,
        bridge_type: str,
        interaction_mode: str,
        purpose: str,
        description: str | None = None,
        allowed_interactions: builtins.list[str] | None = None,
        prohibited_interactions: builtins.list[str] | None = None,
        shared_knowledge_paths: builtins.list[str] | None = None,
        knowledge_sharing_level: str = "restricted",
        requires_approval_above: dict[str, Any] | None = None,
        escalation_triggers: builtins.list[str] | None = None,
        authorization_required: bool = True,
        bridge_topology: str = "role_to_role",
        review_at: str | None = None,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StandingBridge:
        """
        Create a standing bridge between two roles.

        The bridge anchors to ROLES, not units: a role already knows its unit,
        so the server derives both unit ids. The bridge is created unauthorized
        — call :meth:`authorize` once for each side, then :meth:`activate`.

        Args:
            name: Human-readable bridge name
            role_a_id: Role on side A (primary anchor)
            role_b_id: Role on side B (primary anchor)
            bridge_type: One of collaboration, escalation, advisory, approval
            interaction_mode: One of bidirectional, a_to_b_only, b_to_a_only
            purpose: Why this bridge exists
            description: Longer free-text description
            allowed_interactions: Interaction types explicitly permitted
            prohibited_interactions: Interaction types explicitly refused
            shared_knowledge_paths: Knowledge paths shared across the bridge
            knowledge_sharing_level: One of restricted, partial, full
            requires_approval_above: Thresholds above which approval is needed
            escalation_triggers: Conditions that escalate over this bridge
            authorization_required: Whether both sides must authorize
            bridge_topology: One of role_to_role, role_to_unit
            review_at: ISO 8601 date of the next periodic review
            expires_at: ISO 8601 expiry, if the bridge is time-bounded
            metadata: Free-form metadata

        Returns:
            The created bridge, in status "pending"

        Example:
            >>> bridge = await client.bridges.standing.create(
            ...     name="Engineering <-> Compliance",
            ...     role_a_id="role-eng-lead",
            ...     role_b_id="role-compliance-lead",
            ...     bridge_type="advisory",
            ...     interaction_mode="bidirectional",
            ...     purpose="Pre-release compliance review",
            ... )
        """
        data: dict[str, Any] = {
            "name": name,
            "role_a_id": role_a_id,
            "role_b_id": role_b_id,
            "bridge_type": bridge_type,
            "interaction_mode": interaction_mode,
            "purpose": purpose,
            "knowledge_sharing_level": knowledge_sharing_level,
            "authorization_required": authorization_required,
            "bridge_topology": bridge_topology,
        }
        optional: dict[str, Any] = {
            "description": description,
            "allowed_interactions": allowed_interactions,
            "prohibited_interactions": prohibited_interactions,
            "shared_knowledge_paths": shared_knowledge_paths,
            "requires_approval_above": requires_approval_above,
            "escalation_triggers": escalation_triggers,
            "review_at": review_at,
            "expires_at": expires_at,
            "metadata": metadata,
        }
        data.update({k: v for k, v in optional.items() if v is not None})

        response = await self._http.request("POST", "/api/v1/standing-bridges", json_data=data)
        return StandingBridge(**response)

    async def list(
        self,
        unit_id: str | None = None,
        status: str | None = None,
        bridge_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> StandingBridgeList:
        """
        List standing bridges in the caller's organization.

        With no ``status`` filter the server excludes archived and deleted
        bridges — pass one explicitly to see them.

        Args:
            unit_id: Restrict to bridges with this unit on EITHER side
            status: One of pending, active, suspended, revoked, archived
            bridge_type: One of collaboration, escalation, advisory, approval
            limit: Maximum results (1-200)
            offset: Result offset

        Returns:
            A page of standing bridges

        Example:
            >>> page = await client.bridges.standing.list(status="active")
            >>> print(page.total)
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for key, value in (
            ("unit_id", unit_id),
            ("status", status),
            ("bridge_type", bridge_type),
        ):
            if value is not None:
                params[key] = value

        response = await self._http.request("GET", "/api/v1/standing-bridges", params=params)
        return StandingBridgeList(**response)

    async def get(self, bridge_id: str) -> StandingBridge:
        """
        Get one standing bridge.

        Args:
            bridge_id: Bridge ID

        Returns:
            The bridge

        Example:
            >>> bridge = await client.bridges.standing.get("bridge-123")
        """
        response = await self._http.request(
            "GET", f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}"
        )
        return StandingBridge(**response)

    async def update(
        self,
        bridge_id: str,
        name: str | None = None,
        purpose: str | None = None,
        description: str | None = None,
        allowed_interactions: builtins.list[str] | None = None,
        prohibited_interactions: builtins.list[str] | None = None,
        shared_knowledge_paths: builtins.list[str] | None = None,
        knowledge_sharing_level: str | None = None,
        requires_approval_above: dict[str, Any] | None = None,
        escalation_triggers: builtins.list[str] | None = None,
        review_at: str | None = None,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> StandingBridge:
        """
        Update a standing bridge.

        Only the fields supplied are sent; the role anchors are NOT updatable
        here, because re-anchoring a bridge changes which envelopes intersect.

        Args:
            bridge_id: Bridge ID
            name: New name
            purpose: New purpose
            description: New description
            allowed_interactions: Replacement allowed-interaction list
            prohibited_interactions: Replacement prohibited-interaction list
            shared_knowledge_paths: Replacement shared-knowledge paths
            knowledge_sharing_level: One of restricted, partial, full
            requires_approval_above: Replacement approval thresholds
            escalation_triggers: Replacement escalation triggers
            review_at: New periodic-review date
            expires_at: New expiry
            metadata: Replacement metadata
            status: One of pending, active, suspended, revoked, archived

        Returns:
            The updated bridge

        Example:
            >>> bridge = await client.bridges.standing.update(
            ...     "bridge-123", purpose="Quarterly compliance review"
            ... )
        """
        data: dict[str, Any] = {
            k: v
            for k, v in {
                "name": name,
                "purpose": purpose,
                "description": description,
                "allowed_interactions": allowed_interactions,
                "prohibited_interactions": prohibited_interactions,
                "shared_knowledge_paths": shared_knowledge_paths,
                "knowledge_sharing_level": knowledge_sharing_level,
                "requires_approval_above": requires_approval_above,
                "escalation_triggers": escalation_triggers,
                "review_at": review_at,
                "expires_at": expires_at,
                "metadata": metadata,
                "status": status,
            }.items()
            if v is not None
        }

        response = await self._http.request(
            "PUT", f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}", json_data=data
        )
        return StandingBridge(**response)

    async def delete(self, bridge_id: str, hard: bool = False) -> DeleteResult:
        """
        Delete a standing bridge.

        Args:
            bridge_id: Bridge ID
            hard: If True, permanently delete rather than archive

        Returns:
            The server's acknowledgement

        Example:
            >>> await client.bridges.standing.delete("bridge-123")
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}",
            params={"hard": hard},
        )
        return DeleteResult(**response)

    async def authorize(self, bridge_id: str, user_id: str, side: str) -> StandingBridge:
        """
        Authorize a standing bridge from ONE side.

        Both sides must authorize before :meth:`activate` will succeed — that
        is the point of the dual gate, and calling this twice for the same side
        does not satisfy the other.

        Args:
            bridge_id: Bridge ID
            user_id: The user authorizing this side
            side: Which side to authorize, "a" or "b"

        Returns:
            The bridge with this side's authorization recorded

        Example:
            >>> await client.bridges.standing.authorize("b-1", "user-7", "a")
            >>> await client.bridges.standing.authorize("b-1", "user-9", "b")
            >>> await client.bridges.standing.activate("b-1")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}/authorize",
            json_data={"user_id": user_id, "side": side},
        )
        return StandingBridge(**response)

    async def activate(self, bridge_id: str) -> StandingBridge:
        """
        Activate a standing bridge after dual authorization.

        Args:
            bridge_id: Bridge ID

        Returns:
            The activated bridge

        Example:
            >>> bridge = await client.bridges.standing.activate("bridge-123")
            >>> assert bridge.status == "active"
        """
        response = await self._http.request(
            "POST", f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}/activate"
        )
        return StandingBridge(**response)

    async def suspend(self, bridge_id: str, reason: str | None = None) -> StandingBridge:
        """
        Suspend an active standing bridge.

        Suspension is reversible; :meth:`revoke` is not.

        Args:
            bridge_id: Bridge ID
            reason: Why the bridge is being suspended (max 500 chars)

        Returns:
            The suspended bridge

        Example:
            >>> await client.bridges.standing.suspend("b-1", reason="Under review")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}/suspend",
            json_data={"reason": reason} if reason is not None else None,
        )
        return StandingBridge(**response)

    async def revoke(self, bridge_id: str, reason: str | None = None) -> StandingBridge:
        """
        Permanently revoke a standing bridge.

        ⚠ A revoked bridge's trust chains are recorded with status
        ``suspended``, not ``revoked`` — so a status-only check against the
        chain cannot tell a revocation from a suspension. Read the BRIDGE's
        status, which this returns, rather than inferring it from the chain.

        Args:
            bridge_id: Bridge ID
            reason: Why the bridge is being revoked (max 500 chars)

        Returns:
            The revoked bridge

        Example:
            >>> await client.bridges.standing.revoke("b-1", reason="Unit dissolved")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}/revoke",
            json_data={"reason": reason} if reason is not None else None,
        )
        return StandingBridge(**response)

    async def for_unit(self, unit_id: str) -> builtins.list[StandingBridge]:
        """
        Get every standing bridge with this unit on either side.

        Args:
            unit_id: Unit ID

        Returns:
            The unit's standing bridges

        Example:
            >>> bridges = await client.bridges.standing.for_unit("unit-42")
        """
        response = await self._http.request(
            "GET", f"/api/v1/standing-bridges/for-unit/{encode_path_param(unit_id)}"
        )
        return [StandingBridge(**item) for item in response]

    async def check_interaction(self, bridge_id: str, interaction_type: str) -> InteractionCheck:
        """
        Ask whether one interaction type is permitted over a bridge.

        This is the SERVER's answer, and it is the authoritative one. Read
        ``reason`` on a denial rather than inferring the cause from the
        bridge's configuration.

        Args:
            bridge_id: Bridge ID
            interaction_type: The interaction type to test

        Returns:
            The allow/deny verdict and, on a denial, its reason

        Example:
            >>> check = await client.bridges.standing.check_interaction(
            ...     "b-1", "share_document"
            ... )
            >>> if not check.allowed:
            ...     print(check.reason)
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}/check-interaction",
            json_data={"interaction_type": interaction_type},
        )
        return InteractionCheck(**response)

    async def submit_review(
        self, bridge_id: str, approved: bool, notes: str = ""
    ) -> BridgeReview:
        """
        Submit a completed periodic review for a standing bridge.

        Records the outcome, resets the review clock, and SUSPENDS the bridge
        when ``approved`` is False. The reviewer identity comes from the
        authenticated principal, never from this call — an approval that could
        name its own reviewer would not be attributable.

        Args:
            bridge_id: Bridge ID
            approved: Whether the bridge passed the review
            notes: Reviewer notes (max 2000 chars)

        Returns:
            The recorded review

        Example:
            >>> review = await client.bridges.standing.submit_review(
            ...     "b-1", approved=True, notes="Still required for Q3"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/standing-bridges/{encode_path_param(bridge_id)}/review",
            json_data={"approved": approved, "notes": notes},
        )
        return BridgeReview(**response)

    async def overdue(self) -> builtins.list[OverdueBridge]:
        """
        List standing bridges overdue for a periodic review.

        Args:
            None

        Returns:
            The overdue bridges, each with how many days it is overdue

        Example:
            >>> for b in await client.bridges.standing.overdue():
            ...     print(f"{b.name}: {b.days_overdue} days")
        """
        response = await self._http.request("GET", "/api/v1/standing-bridges/overdue")
        return [OverdueBridge(**item) for item in response]


# ===================
# Scoped bridges
# ===================


class ScopedBridgesModule:
    """Temporary channels bounded by a workspace or an objective."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize the scoped-bridges module with an HTTP client."""
        self._http = http_client

    async def create(
        self,
        workspace_id: str,
        name: str,
        objective: str,
        participants: builtins.list[dict[str, Any]],
        owner_unit_id: str,
        purpose: str,
        scope_description: str,
        starts_at: str,
        objective_id: str | None = None,
        expires_at: str | None = None,
        allowed_interactions: builtins.list[str] | None = None,
        shared_knowledge_paths: builtins.list[str] | None = None,
        auto_expire_on_objective_completion: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ScopedBridge:
        """
        Create a scoped bridge.

        Args:
            workspace_id: Workspace this bridge belongs to
            name: Human-readable bridge name
            objective: What the bridge exists to achieve
            participants: Participant dicts, each with unit_id and optional
                roles / constraints
            owner_unit_id: Unit that owns the bridge
            purpose: Why this bridge exists
            scope_description: What the bridge's scope covers
            starts_at: ISO 8601 date the bridge becomes active
            objective_id: Objective this bridge is linked to, if any
            expires_at: ISO 8601 expiry
            allowed_interactions: Interaction types explicitly permitted
            shared_knowledge_paths: Knowledge paths shared across the bridge
            auto_expire_on_objective_completion: Expire when the objective closes
            metadata: Free-form metadata

        Returns:
            The created bridge

        Example:
            >>> bridge = await client.bridges.scoped.create(
            ...     workspace_id="ws-1",
            ...     name="Launch readiness",
            ...     objective="Ship the Q3 release",
            ...     participants=[{"unit_id": "unit-1"}, {"unit_id": "unit-2"}],
            ...     owner_unit_id="unit-1",
            ...     purpose="Cross-unit launch coordination",
            ...     scope_description="Release scope only",
            ...     starts_at="2026-09-01",
            ... )
        """
        data: dict[str, Any] = {
            "workspace_id": workspace_id,
            "name": name,
            "objective": objective,
            "participants": participants,
            "owner_unit_id": owner_unit_id,
            "purpose": purpose,
            "scope_description": scope_description,
            "starts_at": starts_at,
            "auto_expire_on_objective_completion": auto_expire_on_objective_completion,
        }
        optional: dict[str, Any] = {
            "objective_id": objective_id,
            "expires_at": expires_at,
            "allowed_interactions": allowed_interactions,
            "shared_knowledge_paths": shared_knowledge_paths,
            "metadata": metadata,
        }
        data.update({k: v for k, v in optional.items() if v is not None})

        response = await self._http.request("POST", "/api/v1/scoped-bridges", json_data=data)
        return ScopedBridge(**response)

    async def list(
        self,
        workspace_id: str | None = None,
        objective_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ScopedBridgeList:
        """
        List scoped bridges in the caller's organization.

        Args:
            workspace_id: Restrict to one workspace
            objective_id: Restrict to one objective
            status: One of pending, active, expired, completed, cancelled
            limit: Maximum results (1-200)
            offset: Result offset

        Returns:
            A page of scoped bridges

        Example:
            >>> page = await client.bridges.scoped.list(workspace_id="ws-1")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for key, value in (
            ("workspace_id", workspace_id),
            ("objective_id", objective_id),
            ("status", status),
        ):
            if value is not None:
                params[key] = value

        response = await self._http.request("GET", "/api/v1/scoped-bridges", params=params)
        return ScopedBridgeList(**response)

    async def get(self, bridge_id: str) -> ScopedBridge:
        """
        Get one scoped bridge.

        Args:
            bridge_id: Bridge ID

        Returns:
            The bridge

        Example:
            >>> bridge = await client.bridges.scoped.get("scoped-123")
        """
        response = await self._http.request(
            "GET", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}"
        )
        return ScopedBridge(**response)

    async def update(
        self,
        bridge_id: str,
        name: str | None = None,
        objective: str | None = None,
        purpose: str | None = None,
        scope_description: str | None = None,
        allowed_interactions: builtins.list[str] | None = None,
        shared_knowledge_paths: builtins.list[str] | None = None,
        auto_expire_on_objective_completion: bool | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> ScopedBridge:
        """
        Update a scoped bridge.

        Args:
            bridge_id: Bridge ID
            name: New name
            objective: New objective
            purpose: New purpose
            scope_description: New scope description
            allowed_interactions: Replacement allowed-interaction list
            shared_knowledge_paths: Replacement shared-knowledge paths
            auto_expire_on_objective_completion: Replacement auto-expire flag
            metadata: Replacement metadata
            status: One of pending, active, expired, completed, cancelled

        Returns:
            The updated bridge

        Example:
            >>> await client.bridges.scoped.update("s-1", purpose="Narrowed scope")
        """
        data: dict[str, Any] = {
            k: v
            for k, v in {
                "name": name,
                "objective": objective,
                "purpose": purpose,
                "scope_description": scope_description,
                "allowed_interactions": allowed_interactions,
                "shared_knowledge_paths": shared_knowledge_paths,
                "auto_expire_on_objective_completion": auto_expire_on_objective_completion,
                "metadata": metadata,
                "status": status,
            }.items()
            if v is not None
        }

        response = await self._http.request(
            "PUT", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}", json_data=data
        )
        return ScopedBridge(**response)

    async def delete(self, bridge_id: str) -> DeleteResult:
        """
        Delete a scoped bridge.

        Args:
            bridge_id: Bridge ID

        Returns:
            The server's acknowledgement

        Example:
            >>> await client.bridges.scoped.delete("scoped-123")
        """
        response = await self._http.request(
            "DELETE", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}"
        )
        return DeleteResult(**response)

    async def approve(self, bridge_id: str) -> ScopedBridge:
        """
        Approve a pending scoped bridge, promoting it to active.

        The approver is the authenticated principal and must be DISTINCT from
        the bridge's creator — the server refuses a self-approval, so a caller
        holding both identities cannot satisfy the gate by calling twice.

        Args:
            bridge_id: Bridge ID

        Returns:
            The approved bridge

        Example:
            >>> bridge = await client.bridges.scoped.approve("scoped-123")
        """
        response = await self._http.request(
            "POST", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/approve"
        )
        return ScopedBridge(**response)

    async def reject(self, bridge_id: str, reason: str | None = None) -> ScopedBridge:
        """
        Reject a pending scoped bridge before it goes active.

        Args:
            bridge_id: Bridge ID
            reason: Why the bridge is being rejected (max 500 chars)

        Returns:
            The rejected bridge

        Example:
            >>> await client.bridges.scoped.reject("s-1", reason="Scope too broad")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/reject",
            json_data={"reason": reason} if reason is not None else None,
        )
        return ScopedBridge(**response)

    async def add_unit(
        self,
        bridge_id: str,
        unit_id: str,
        roles: builtins.list[str] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> ScopedBridge:
        """
        Add a participating unit to a scoped bridge.

        Adding a unit widens who the bridge reaches, so ``constraints`` narrows
        what that unit may do over it — it does not widen anything.

        Args:
            bridge_id: Bridge ID
            unit_id: Unit to add
            roles: Roles the unit participates as
            constraints: Constraints on this participant

        Returns:
            The bridge with the participant added

        Example:
            >>> await client.bridges.scoped.add_unit("s-1", "unit-9", roles=["reviewer"])
        """
        data: dict[str, Any] = {"unit_id": unit_id}
        if roles is not None:
            data["roles"] = roles
        if constraints is not None:
            data["constraints"] = constraints

        response = await self._http.request(
            "POST",
            f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/add-unit",
            json_data=data,
        )
        return ScopedBridge(**response)

    async def remove_unit(self, bridge_id: str, unit_id: str) -> ScopedBridge:
        """
        Remove a participating unit from a scoped bridge.

        Args:
            bridge_id: Bridge ID
            unit_id: Unit to remove

        Returns:
            The bridge with the participant removed

        Example:
            >>> await client.bridges.scoped.remove_unit("s-1", "unit-9")
        """
        # TWO constraints act on this one line, and the obvious way to satisfy
        # either one breaks the other. Both are satisfied by inlining, so do
        # not "tidy" this into locals or a wrapped string:
        #
        #   * encode_path_param() must appear LITERALLY inside the f-string.
        #     The encoding guard is an AST check for that call, so binding the
        #     encoded value to a local (`bid = encode_path_param(...)`) reds it
        #     even though the value IS encoded -- the guard is name-keyed and
        #     cannot see a value arriving through a variable.
        #   * the path must be ONE literal. Adjacent literals concatenate at
        #     parse time, but a wrapped path is easy to reintroduce and the
        #     older regex-based deriver read only the first half.
        #
        # It looks like these force a choice only because the line gets long.
        # They do not: E501 is in this repo's ruff ignore list, so length is
        # not a constraint here at all.
        response = await self._http.request(
            "DELETE",
            f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/participants/{encode_path_param(unit_id)}",
        )
        return ScopedBridge(**response)

    async def participants(self, bridge_id: str) -> builtins.list[Participant]:
        """
        Get the participating units of a scoped bridge.

        Args:
            bridge_id: Bridge ID

        Returns:
            The bridge's participating units

        Example:
            >>> for p in await client.bridges.scoped.participants("s-1"):
            ...     print(p.unit_id)
        """
        response = await self._http.request(
            "GET", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/participants"
        )
        return [Participant(**item) for item in response]

    async def expire(self, bridge_id: str) -> ScopedBridge:
        """
        Mark a scoped bridge as expired.

        Args:
            bridge_id: Bridge ID

        Returns:
            The expired bridge

        Example:
            >>> await client.bridges.scoped.expire("scoped-123")
        """
        response = await self._http.request(
            "POST", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/expire"
        )
        return ScopedBridge(**response)

    async def complete(self, bridge_id: str) -> ScopedBridge:
        """
        Mark a scoped bridge as completed, its objective achieved.

        Args:
            bridge_id: Bridge ID

        Returns:
            The completed bridge

        Example:
            >>> await client.bridges.scoped.complete("scoped-123")
        """
        response = await self._http.request(
            "POST", f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/complete"
        )
        return ScopedBridge(**response)

    async def cancel(self, bridge_id: str, reason: str | None = None) -> ScopedBridge:
        """
        Cancel a scoped bridge before completion.

        Args:
            bridge_id: Bridge ID
            reason: Why the bridge is being cancelled (max 500 chars)

        Returns:
            The cancelled bridge

        Example:
            >>> await client.bridges.scoped.cancel("s-1", reason="Objective dropped")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/cancel",
            json_data={"reason": reason} if reason is not None else None,
        )
        return ScopedBridge(**response)

    async def extend(self, bridge_id: str, expires_at: str) -> ScopedBridge:
        """
        Extend an active scoped bridge's expiry.

        Use :meth:`renew` for a bridge that has already expired — extending is
        for one still running.

        Args:
            bridge_id: Bridge ID
            expires_at: New expiry (ISO 8601)

        Returns:
            The extended bridge

        Example:
            >>> await client.bridges.scoped.extend("s-1", "2026-12-31")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/extend",
            json_data={"expires_at": expires_at},
        )
        return ScopedBridge(**response)

    async def renew(self, bridge_id: str, expires_at: str) -> ScopedBridge:
        """
        Renew an EXPIRED scoped bridge, reactivating it with a new expiry.

        Args:
            bridge_id: Bridge ID
            expires_at: New expiry (ISO 8601)

        Returns:
            The reactivated bridge

        Example:
            >>> await client.bridges.scoped.renew("s-1", "2026-12-31")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/scoped-bridges/{encode_path_param(bridge_id)}/renew",
            json_data={"expires_at": expires_at},
        )
        return ScopedBridge(**response)

    async def for_workspace(self, workspace_id: str) -> builtins.list[ScopedBridge]:
        """
        Get every scoped bridge in a workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            The workspace's scoped bridges

        Example:
            >>> bridges = await client.bridges.scoped.for_workspace("ws-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/scoped-bridges/for-workspace/{encode_path_param(workspace_id)}"
        )
        return [ScopedBridge(**item) for item in response]

    async def for_objective(self, objective_id: str) -> builtins.list[ScopedBridge]:
        """
        Get every scoped bridge linked to an objective.

        Args:
            objective_id: Objective ID

        Returns:
            The objective's scoped bridges

        Example:
            >>> bridges = await client.bridges.scoped.for_objective("obj-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/scoped-bridges/for-objective/{encode_path_param(objective_id)}"
        )
        return [ScopedBridge(**item) for item in response]


# ===================
# Ad-hoc bridges
# ===================


class AdHocBridgesModule:
    """Request/approve channels raised against a unit, carrying an expiry."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize the ad-hoc-bridges module with an HTTP client."""
        self._http = http_client

    async def for_unit(self, unit_id: str) -> list[AdHocBridge]:
        """
        Get every ad-hoc bridge with this unit as initiator or target.

        Args:
            unit_id: Unit ID

        Returns:
            The unit's ad-hoc bridges, in either direction

        Example:
            >>> bridges = await client.bridges.ad_hoc.for_unit("unit-42")
        """
        response = await self._http.request(
            "GET", f"/api/v1/ad-hoc-bridges/for-unit/{encode_path_param(unit_id)}"
        )
        return [AdHocBridge(**item) for item in response]

    async def pending_for(self, unit_id: str) -> list[AdHocBridge]:
        """
        Get ad-hoc bridges awaiting this unit's approval.

        Only bridges where the unit is the TARGET (and therefore the approver)
        are returned — a unit's own outbound requests are not pending on it.

        Args:
            unit_id: Unit ID acting as approver

        Returns:
            The bridges awaiting approval

        Example:
            >>> for b in await client.bridges.ad_hoc.pending_for("unit-42"):
            ...     print(f"{b.name} ({b.urgency}) expires {b.expires_at}")
        """
        response = await self._http.request(
            "GET", f"/api/v1/ad-hoc-bridges/pending-for/{encode_path_param(unit_id)}"
        )
        return [AdHocBridge(**item) for item in response]

    async def approve(self, bridge_id: str) -> AdHocBridge:
        """
        Approve a requested ad-hoc bridge.

        The approver is the authenticated principal; approval does not itself
        open the channel — call :meth:`activate` after.

        Args:
            bridge_id: Bridge ID

        Returns:
            The approved bridge

        Example:
            >>> bridge = await client.bridges.ad_hoc.approve("adhoc-123")
        """
        response = await self._http.request(
            "POST", f"/api/v1/ad-hoc-bridges/{encode_path_param(bridge_id)}/approve"
        )
        return AdHocBridge(**response)

    async def reject(self, bridge_id: str, reason: str | None = None) -> AdHocBridge:
        """
        Reject a requested ad-hoc bridge.

        Args:
            bridge_id: Bridge ID
            reason: Why the request is refused (max 500 chars)

        Returns:
            The rejected bridge

        Example:
            >>> await client.bridges.ad_hoc.reject("a-1", reason="Use the standing bridge")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/ad-hoc-bridges/{encode_path_param(bridge_id)}/reject",
            json_data={"reason": reason} if reason is not None else None,
        )
        return AdHocBridge(**response)

    async def activate(self, bridge_id: str) -> AdHocBridge:
        """
        Activate an approved ad-hoc bridge, opening the channel.

        An ad-hoc bridge carries ``max_duration_minutes`` and ``expires_at``;
        activation starts the clock, and the server refuses activation of a
        bridge whose expiry has already passed.

        Args:
            bridge_id: Bridge ID

        Returns:
            The activated bridge, with ``activated_at`` set

        Example:
            >>> bridge = await client.bridges.ad_hoc.activate("adhoc-123")
            >>> print(bridge.activated_at)
        """
        response = await self._http.request(
            "POST", f"/api/v1/ad-hoc-bridges/{encode_path_param(bridge_id)}/activate"
        )
        return AdHocBridge(**response)


# ===================
# Facade
# ===================


class BridgesModule:
    """
    Bridges container.

    Attributes:
        standing: Permanent role-anchored collaboration channels
        scoped: Temporary workspace- or objective-bounded channels
        ad_hoc: Request/approve channels raised against a unit
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize the three bridge modules."""
        self.standing = StandingBridgesModule(http_client)
        self.scoped = ScopedBridgesModule(http_client)
        self.ad_hoc = AdHocBridgesModule(http_client)
