"""
Emergency-Bypass and Kill-Switch SDK Module.

The two break-glass surfaces. One widens an envelope under an incident; the
other stops agents.

``EmergencyBypassModule`` (``/api/v1/emergency-bypass``)
    Request a temporary widening of a role's operating envelope, have it
    approved or rejected by someone with the required authority, and withdraw
    it early.

``KillSwitchModule`` (``/api/v1/kill-switch``)
    Stop agents at a chosen blast radius, list open activations, and lift a
    terminal activation's admission gate.

.. important::
    **Neither surface is reachable with an API key.** Emergency-bypass admits
    only the ``admin`` or ``architect`` persona, and an API-key principal
    carries no persona — so all seven routes, the three reads included, return
    ``403`` regardless of the key's scopes. Kill-switch is stricter still: it
    requires a verified user token outright and fails with ``401`` without one.
    Both need a user-session token.

.. note::
    The emergency-bypass methods return ``dict[str, Any]``, not typed models,
    because at the time they were written the platform declared no response
    model for those seven operations and the SDK will not invent a contract the
    API does not make. The keys named on each method are therefore **observed,
    not guaranteed** — read them as a description of what came back, not as a
    schema.

    That is a statement about the SDK's rule, not a standing claim about the
    server: if the platform declares models for these operations, the return
    type can be narrowed to them without any signature here changing, and the
    per-method key lists become redundant rather than wrong. Kill-switch is
    already typed, because its handler carries an explicit, exhaustive wire
    mapper — a real contract the generated spec simply cannot see.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class KillActivation(TolerantModel):
    """One kill-switch activation.

    Note:
        ``targetsStopped`` and ``targetsUncompensated`` **overlap by design**:
        a force-stopped target counts in both — it was stopped, and it may
        have left a partial behind. Do not add them.

    Note:
        Absent fields are emitted as empty strings and zeros rather than
        ``null``, so ``settled_at == ""`` means "not settled", not "unknown".

    Note:
        The per-target ledger is not exposed. A whole-estate stop can name
        thousands of targets; the counters answer the operational question and
        the full list stays in the audit trail.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    organization_id: str = Field("", alias="organizationId")
    scope: str = ""
    scope_selector: str = Field("", alias="scopeSelector")
    mode: str = ""
    status: str = ""
    compensation_window_seconds: int = Field(0, alias="compensationWindowSeconds")
    window_expires_at: str = Field("", alias="windowExpiresAt")
    activated_by_user_id: str = Field("", alias="activatedByUserId")
    activated_by_role_id: str = Field("", alias="activatedByRoleId")
    activated_by_authority_level: int = Field(0, alias="activatedByAuthorityLevel")
    reason: str = ""
    incident_id: str = Field("", alias="incidentId")
    targets_total: int = Field(0, alias="targetsTotal")
    targets_stopped: int = Field(0, alias="targetsStopped")
    targets_uncompensated: int = Field(0, alias="targetsUncompensated")
    targets_truncated: bool = Field(False, alias="targetsTruncated")
    failure_type: str = Field("", alias="failureType")
    created_at: str = Field("", alias="createdAt")
    updated_at: str = Field("", alias="updatedAt")
    settled_at: str = Field("", alias="settledAt")
    cleared_at: str = Field("", alias="clearedAt")
    cleared_by_user_id: str = Field("", alias="clearedByUserId")
    clearance_reason: str = Field("", alias="clearanceReason")


class KillActivationList(TolerantModel):
    """Envelope for the open-activations read."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[KillActivation] = Field(default_factory=list)
    total: int = 0


class EmergencyBypassModule:
    """
    Emergency-bypass SDK module (``/api/v1/emergency-bypass``).

    Methods:
        - create(): Request a bypass (lands ``pending``)
        - approve() / reject(): The approver's two verdicts
        - revoke(): Withdraw an already-active bypass early
        - list(): Bypasses in this organization, optionally by status
        - list_active(): Only the active ones
        - get(): One bypass

    **The clock starts when the bypass is REQUESTED, not when it is approved.**
        ``expires_at`` is computed at create time as ``created_at +
        duration_hours`` and is never recomputed. Approval sets the status to
        ``active`` and carries that same timestamp forward untouched. Two
        consequences a caller has to plan around:

        * A bypass approved late grants a **shortened** window — request at
          09:00 for four hours, approve at 11:00, and the widening ends at
          13:00, not 15:00.
        * Approval is **not** blocked by a passed ``expires_at``. The only gate
          is the ``pending -> active`` state transition, so approving a stale
          request yields a record that reads ``active`` with an expiry already
          behind it.

        Never present ``expires_at`` to a user as a window measured from
        approval. Compute the remaining time from ``expires_at`` and the
        current clock, and check it after approving.

    Duration must match the approval tier — the platform rejects a mismatch:
        ============  ===================  ================================
        duration      required tier        approver authority
        ============  ===================  ================================
        0 < h <= 4    ``supervisor``       level 2 and above
        4 < h <= 24   ``two_levels_up``    level 3 and above
        24 < h <= 72  ``c_suite``          level 4 and above
        ============  ===================  ================================

        Above 72 hours is refused as not an emergency (``422``).

    Identity is server-bound, and both role ids you pass are checked:
        You supply ``requesting_role_id`` on create and ``approver_role_id`` on
        approve/reject — but the platform verifies that the authenticated
        caller actually occupies the role named, and refuses with ``403``
        otherwise. These fields select which of *your own* roles is acting;
        they cannot be used to act as somebody else.

    Self-approval is refused unconditionally:
        The requester's identity is captured immutably at create time and is
        never re-derived from who currently holds the requesting role. An
        approver resolving to the same person — via any role — is a ``403``
        with no tier or posture exception. A pre-existing record carrying no
        captured requester identity also fails closed rather than approving.

    ``post_incident_review_at`` is a reminder, not an enforced control:
        Every bypass is stamped with a review date seven days out and
        ``post_incident_review_completed: false``. **No platform surface sets
        that flag true** — there is no endpoint to complete the review and no
        process that chases it. Treat the field as a marker your own process
        must act on; it is not evidence that a review happened, and the
        platform does not withhold anything until it does.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key=user_session_token)
        >>>
        >>> bypass = await client.emergency_bypass.create(
        ...     bypassed_role_id="role-1", requesting_role_id="role-me",
        ...     duration_hours=4, approval_tier="supervisor",
        ...     reason=incident_narrative,   # at least 100 characters
        ...     original_envelope=current, widened_envelope=needed,
        ... )
        >>> pending = await client.emergency_bypass.list(status="pending")
    """

    def __init__(self, http_client):
        """Initialize the emergency-bypass module with an HTTP client."""
        self._http = http_client

    async def create(
        self,
        bypassed_role_id: str,
        requesting_role_id: str,
        duration_hours: int,
        approval_tier: str,
        reason: str,
        original_envelope: dict[str, Any],
        widened_envelope: dict[str, Any],
        superior_envelope: dict[str, Any] | None = None,
        incident_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Request an emergency bypass. Responds ``201``; the bypass is ``pending``.

        Args:
            bypassed_role_id: The role whose envelope would be widened
            requesting_role_id: One of the caller's **own** roles, making the
                request. A role the caller does not occupy is a ``403``.
            duration_hours: 1-72. Must fall in the band matching
                ``approval_tier`` — see the class docstring table. **The
                countdown starts now, not at approval.**
            approval_tier: ``supervisor``, ``two_levels_up`` or ``c_suite``
            reason: Justification. Minimum 100 characters, maximum 4000 — a
                short reason is rejected, not truncated.
            original_envelope: The role's current envelope
            widened_envelope: The envelope being requested. If
                ``superior_envelope`` is given, the stored widening is the
                **intersection** of the two — you cannot widen past the
                superior, and the platform narrows it silently rather than
                refusing. Re-read the record to see what was actually granted.
            superior_envelope: The superior's envelope, used as the ceiling
            incident_id: Correlating incident identifier

            Each envelope is capped at 16 top-level keys.

        Returns:
            The created bypass record as an untyped dict. Observed keys:
            ``id``, ``organization_id``, ``bypassed_role_id``,
            ``requesting_role_id``, ``requested_by_user_id``,
            ``approver_role_id``, ``original_envelope_json``,
            ``widened_envelope_json``, ``approval_tier``, ``duration_hours``,
            ``reason``, ``incident_id``, ``status``, ``created_at``,
            ``updated_at``, ``expires_at``, ``revoked_at``,
            ``post_incident_review_at``, ``post_incident_review_completed``,
            ``post_incident_review_notes``. The two envelope fields are JSON
            **strings**.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, a session
                without the ``admin``/``architect`` persona, or
                ``requesting_role_id`` naming a role the caller does not hold.
            ValidationError: ``400`` — tier/duration band mismatch, unknown
                tier, reason under 100 characters, or an envelope over the key
                cap. ``422`` — duration above 72 hours.

        Example:
            >>> bypass = await client.emergency_bypass.create(
            ...     bypassed_role_id="role-1",
            ...     requesting_role_id="role-me",
            ...     duration_hours=4,
            ...     approval_tier="supervisor",
            ...     reason=incident_narrative,
            ...     original_envelope={"max_spend": 100},
            ...     widened_envelope={"max_spend": 5000},
            ... )
        """
        body: dict[str, Any] = {
            "bypassed_role_id": bypassed_role_id,
            "requesting_role_id": requesting_role_id,
            "duration_hours": duration_hours,
            "approval_tier": approval_tier,
            "reason": reason,
            "original_envelope": original_envelope,
            "widened_envelope": widened_envelope,
        }
        if superior_envelope is not None:
            body["superior_envelope"] = superior_envelope
        if incident_id is not None:
            body["incident_id"] = incident_id

        response = await self._http.request(
            "POST", "/api/v1/emergency-bypass/create", json_data=body
        )
        return response

    async def approve(self, bypass_id: str, approver_role_id: str) -> dict[str, Any]:
        """
        Approve a pending bypass, putting the widening into effect.

        Check the returned ``expires_at`` before telling anyone how long they
        have. It was fixed when the bypass was requested, so the window you are
        granting is shorter than ``duration_hours`` by however long the request
        waited — and may already have passed, which this call does not refuse.

        Args:
            bypass_id: Bypass ID
            approver_role_id: One of the caller's **own** roles, holding at
                least the authority the bypass's tier requires

        Returns:
            The updated bypass record (untyped dict; keys as in :meth:`create`)
            with ``status`` now ``active`` and ``approver_role_id`` set.

        Raises:
            AuthorizationError: ``403`` — self-approval (unconditional), a role
                the caller does not occupy, authority below the tier's minimum,
                a bypass whose captured requester identity is missing, an
                API-key credential, or a missing persona.
            NotFoundError: ``404`` — no such bypass in this organization.
            AgenticOSError: ``409`` — the bypass is not ``pending``.

        Example:
            >>> record = await client.emergency_bypass.approve(
            ...     "bypass-1", approver_role_id="role-director"
            ... )
            >>> print(record["expires_at"])  # measured from the REQUEST
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/emergency-bypass/{encode_path_param(bypass_id)}/approve",
            json_data={"approver_role_id": approver_role_id},
        )
        return response

    async def reject(
        self, bypass_id: str, approver_role_id: str, rejection_reason: str
    ) -> dict[str, Any]:
        """
        Reject a pending bypass — the approver's denial path.

        Distinct from :meth:`revoke`: reject acts on a ``pending`` bypass and
        records a denial. Revoke acts on one already ``active``.

        Args:
            bypass_id: Bypass ID
            approver_role_id: One of the caller's own roles
            rejection_reason: Why the request is refused. Recorded on the audit
                trail so a reviewer can reconstruct the denial.

        Returns:
            The updated bypass record (untyped dict).

        Raises:
            AuthorizationError: ``403`` — a role the caller does not occupy, an
                API-key credential, or a missing persona.
            NotFoundError: ``404`` — no such bypass in this organization.
            AgenticOSError: ``409`` — the bypass is not ``pending``.

        Example:
            >>> await client.emergency_bypass.reject(
            ...     "bypass-1", "role-director", "Use the standard change path."
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/emergency-bypass/{encode_path_param(bypass_id)}/reject",
            json_data={
                "approver_role_id": approver_role_id,
                "rejection_reason": rejection_reason,
            },
        )
        return response

    async def revoke(self, bypass_id: str, revoked_by_role_id: str) -> dict[str, Any]:
        """
        Withdraw an active bypass before its ``expires_at``.

        Active-only. To deny a bypass that has not been approved yet, use
        :meth:`reject`.

        Args:
            bypass_id: Bypass ID
            revoked_by_role_id: One of the caller's own roles

        Returns:
            The updated bypass record (untyped dict).

        Raises:
            AuthorizationError: ``403`` — a role the caller does not occupy, an
                API-key credential, or a missing persona.
            NotFoundError: ``404`` — no such bypass in this organization.
            AgenticOSError: ``409`` — the bypass is not ``active``.

        Example:
            >>> await client.emergency_bypass.revoke("bypass-1", "role-director")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/emergency-bypass/{encode_path_param(bypass_id)}/revoke",
            json_data={"revoked_by_role_id": revoked_by_role_id},
        )
        return response

    async def list(
        self,
        status: str | None = None,
        bypassed_role_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        List bypasses in the caller's organization.

        This is the approver's discovery route: self-approval is refused
        unconditionally, so the person who may approve a request is never the
        person who made it, and needs ``status="pending"`` here to find it.

        Args:
            status: One of ``pending``, ``active``, ``expired``, ``revoked``,
                ``rejected``. An unrecognized value is rejected with ``400``
                rather than returning an empty page — a typo will not read as a
                clean queue.
            bypassed_role_id: Restrict to bypasses against one role
            limit: 1-500, default 100

        Returns:
            ``{"records": [...], "total": int}`` as an untyped dict. Tenant
            scope is server-derived; there is no organization parameter.

        Example:
            >>> queue = await client.emergency_bypass.list(status="pending")
            >>> print(queue["total"])
        """
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        if bypassed_role_id is not None:
            params["bypassedRoleId"] = bypassed_role_id

        response = await self._http.request(
            "GET", "/api/v1/emergency-bypass", params=params
        )
        return response

    async def list_active(
        self, bypassed_role_id: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """
        List currently-active bypasses.

        Args:
            bypassed_role_id: Restrict to bypasses against one role
            limit: 1-500, default 100

        Returns:
            ``{"records": [...], "total": int}`` as an untyped dict.

        Note:
            A record here reports the status the store holds. Expiry is swept
            on an interval by a background scheduler rather than at read time,
            so a bypass can appear in this list for a short period after its
            ``expires_at`` has passed. Compare ``expires_at`` to the clock if
            the distinction matters.

        Example:
            >>> active = await client.emergency_bypass.list_active()
        """
        params: dict[str, Any] = {"limit": limit}
        if bypassed_role_id is not None:
            params["bypassedRoleId"] = bypassed_role_id

        response = await self._http.request(
            "GET", "/api/v1/emergency-bypass/active", params=params
        )
        return response

    async def get(self, bypass_id: str) -> dict[str, Any]:
        """
        Get one bypass by ID.

        Args:
            bypass_id: Bypass ID

        Returns:
            The bypass record as an untyped dict (keys as in :meth:`create`).

        Raises:
            NotFoundError: ``404`` — no such bypass in this organization. A
                bypass in another organization reports the same way, so this
                cannot be used to probe for existence elsewhere.

        Example:
            >>> record = await client.emergency_bypass.get("bypass-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/emergency-bypass/{encode_path_param(bypass_id)}"
        )
        return response


class KillSwitchModule:
    """
    Estate kill-switch SDK module (``/api/v1/kill-switch``).

    Methods:
        - activate(): Stop agents at a chosen blast radius
        - list_open(): Non-terminal activations, newest first
        - get(): One activation
        - clear(): Lift a terminal activation's admission gate

    Credential:
        Requires a verified user token. An API key fails with ``401`` (no
        verified identity) rather than ``403``, and the caller must additionally
        hold the ``admin`` or ``architect`` persona.

    Authority scales with blast radius, and it is server-derived:
        ==================  ==========================  ==================
        scope               selector                    minimum authority
        ==================  ==========================  ==================
        ``single_agent``    agent id                    level 2
        ``per_human``       user id                     level 3
        ``workflow_class``  class value                 level 4
        ``whole_estate``    must be empty               level 5
        ==================  ==========================  ==================

        You cannot supply your own actor, authority level, or organization —
        all three are read from the verified token and your own active roles,
        and the request model **rejects** those fields outright rather than
        ignoring them, so you can never believe you set an actor you did not.

    Activation is one-way:
        The lifecycle has no ``cancelled``, ``resumed`` or ``reverted`` state.
        :meth:`clear` is not an undo — see its docstring.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key=user_session_token)
        >>>
        >>> activation = await client.kill_switch.activate(
        ...     scope="single_agent", mode="drain",
        ...     scope_selector="agent-42",
        ...     reason="Runaway spend on the invoice-reconciliation loop.",
        ... )
        >>> open_now = await client.kill_switch.list_open()
    """

    def __init__(self, http_client):
        """Initialize the kill-switch module with an HTTP client."""
        self._http = http_client

    async def activate(
        self,
        scope: str,
        mode: str,
        reason: str,
        scope_selector: str = "",
        compensation_window_seconds: int | None = None,
        incident_id: str | None = None,
    ) -> KillActivation:
        """
        Stop agents at the requested blast radius. Responds ``201``.

        Args:
            scope: ``single_agent``, ``per_human``, ``workflow_class`` or
                ``whole_estate``. Determines both the target set and the
                authority you must hold — see the class docstring.
            mode: ``drain`` refuses new work, lets in-flight work settle inside
                the bounded window, then force-stops whatever is left.
                ``hard_stop`` terminates immediately.
            reason: Justification. Minimum 40 characters, maximum 2000. It is
                recorded on the activation and on every audit row it produces.
            scope_selector: The agent id, user id, or class value the scope
                names. **Must be empty for ``whole_estate``**, and must be
                non-empty for every other scope.
            compensation_window_seconds: Settle window for ``drain``, 1-3600.
                Omit for the tenant default. **Must be absent for
                ``hard_stop``** — supplying it there is rejected.
            incident_id: Correlating incident identifier

        Returns:
            The activation, including the counters. Note that
            ``targets_stopped`` and ``targets_uncompensated`` overlap.

        Raises:
            AuthenticationError: ``401`` — no verified user identity (an API
                key lands here).
            AuthorizationError: ``403`` — missing persona, no organization
                scope on the token, or authority below what the scope requires.
            ValidationError: ``400``/``422`` — unknown scope or mode, a reason
                under 40 characters, a selector that is present when it must be
                absent (or absent when required), an out-of-range compensation
                window, or a selector that resolves to no target.
            AgenticOSError: ``409`` — an overlapping activation already covers
                this scope.

        Example:
            >>> activation = await client.kill_switch.activate(
            ...     scope="whole_estate", mode="hard_stop",
            ...     reason="Confirmed credential compromise, stopping everything.",
            ... )
        """
        body: dict[str, Any] = {"scope": scope, "mode": mode, "reason": reason}
        if scope_selector:
            body["scopeSelector"] = scope_selector
        if compensation_window_seconds is not None:
            body["compensationWindowSeconds"] = compensation_window_seconds
        if incident_id is not None:
            body["incidentId"] = incident_id

        response = await self._http.request(
            "POST", "/api/v1/kill-switch/activate", json_data=body
        )
        return KillActivation(**response)

    async def list_open(self) -> KillActivationList:
        """
        List non-terminal activations, newest first.

        Returns:
            The open activations and their count. Scoped to the caller's
            organization from the verified token; there is no organization
            parameter.

        Example:
            >>> open_now = await client.kill_switch.list_open()
            >>> for a in open_now.records:
            ...     print(a.scope, a.mode, a.status, a.targets_stopped)
        """
        response = await self._http.request("GET", "/api/v1/kill-switch/open")
        return KillActivationList(**response)

    async def get(self, activation_id: str) -> KillActivation:
        """
        Get one activation by ID.

        Args:
            activation_id: Activation ID

        Returns:
            The activation.

        Raises:
            NotFoundError: ``404`` — no such activation in this organization.
            ServiceError: ``500`` — a store failure. Deliberately **not**
                reported as ``404``: mid-incident, "your kill does not exist"
                would be the worst possible answer to a database blip. Retry
                rather than concluding the activation is gone.

        Example:
            >>> activation = await client.kill_switch.get("act-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/kill-switch/{encode_path_param(activation_id)}"
        )
        return KillActivation(**response)

    async def clear(self, activation_id: str, reason: str) -> KillActivation:
        """
        Lift a terminal activation's admission gate.

        What this is: a separate, audited record that the admission check
        additionally consults, so an operator can end a permanent gate without
        editing the database by hand.

        What it is **not**: an undo. It does not resume any agent, does not
        restart any stopped work, and does not change the activation's
        ``status`` — the lifecycle has no reverted state. ``cleared_at``,
        ``cleared_by_user_id`` and ``clearance_reason`` are populated; nothing
        else moves.

        Clearing needs the same minimum authority that creating an activation
        of that scope would need, resolved from your own roles rather than the
        request.

        Args:
            activation_id: Activation ID
            reason: Justification for lifting the gate. Minimum 40 characters,
                maximum 2000.

        Returns:
            The updated activation.

        Raises:
            AuthenticationError: ``401`` — no verified user identity.
            AuthorizationError: ``403`` — missing persona, or authority below
                what this activation's scope requires.
            NotFoundError: ``404`` — no such activation in this organization.
            AgenticOSError: ``409`` — the activation is not in a clearable
                state.
            ValidationError: ``400`` — reason under 40 characters.

        Example:
            >>> await client.kill_switch.clear(
            ...     "act-1", reason="Incident closed; the affected agent is repaired."
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/kill-switch/{encode_path_param(activation_id)}/clear",
            json_data={"reason": reason},
        )
        return KillActivation(**response)
