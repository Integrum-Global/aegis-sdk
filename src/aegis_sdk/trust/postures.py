"""
Agentic OS SDK Trust Postures Module.

Provides operations for managing agent trust postures.
Postures define the level of autonomy and trust granted to an agent.

Response models
---------------
The models in this module mirror the shapes the posture endpoints actually
put on the wire. They are declared here, beside the only calls that produce
them, rather than being force-fitted onto an unrelated model.

A posture change is NOT always applied when the call returns. Raising an
agent above ``supervised`` is held for a human approver, and the server
answers that case with an approval record instead of a transition record.
:class:`PostureChangeResult` represents both outcomes and tells them apart
through :attr:`PostureChangeResult.approval_pending`, so a caller can branch
on the outcome instead of inferring it.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param
from ..exceptions import AgenticOSError
from ..types import TrustPosture


class _WireModel(BaseModel):
    """Base for models parsed directly from a posture endpoint's JSON body.

    The posture endpoints emit camelCase keys. Each field below therefore
    carries the wire key as its alias while exposing the SDK's usual
    snake_case attribute name, and ``populate_by_name`` keeps construction
    by attribute name working for callers building these in tests.

    Every field except an identity or posture field is optional. A client
    that hard-requires a presentational field it does not use turns an
    additive server change into a crash on an otherwise-successful call,
    which is the failure mode this module was rebuilt to remove.
    """

    model_config = ConfigDict(populate_by_name=True)


class PostureOverrideRecord(_WireModel):
    """An active posture override sitting on top of an agent's base posture."""

    id: str
    original_posture: TrustPosture | None = Field(default=None, alias="originalPosture")
    override_posture: TrustPosture | None = Field(default=None, alias="overridePosture")
    reason: str | None = None
    override_type: str | None = Field(default=None, alias="overrideType")
    initiated_by: str | None = Field(default=None, alias="initiatedBy")
    initiated_by_name: str | None = Field(default=None, alias="initiatedByName")
    initiated_at: datetime | None = Field(default=None, alias="initiatedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    is_active: bool = Field(default=True, alias="isActive")


class PostureState(_WireModel):
    """An agent's current posture configuration.

    ``posture`` is the EFFECTIVE posture — if an override is active this is
    the override's posture, and ``base_posture`` is what the agent reverts to
    when the override lapses.

    ``agent_id`` is the id the caller asked about. The endpoint answers with
    the configuration only and does not echo the agent id, so it is carried
    through from the request rather than read off the response.
    """

    agent_id: str
    posture: TrustPosture
    base_posture: TrustPosture | None = Field(default=None, alias="basePosture")
    config: dict[str, Any] = Field(default_factory=dict)
    current_since: datetime | None = Field(default=None, alias="currentSince")
    configured_by: str | None = Field(default=None, alias="configuredBy")
    configured_by_name: str | None = Field(default=None, alias="configuredByName")
    configured_at: datetime | None = Field(default=None, alias="configuredAt")
    approved_by: str | None = Field(default=None, alias="approvedBy")
    approved_by_name: str | None = Field(default=None, alias="approvedByName")
    approved_at: datetime | None = Field(default=None, alias="approvedAt")
    review_due_at: datetime | None = Field(default=None, alias="reviewDueAt")
    override_active: bool = Field(default=False, alias="overrideActive")
    override_info: PostureOverrideRecord | None = Field(default=None, alias="overrideInfo")


class PostureApprovalRecord(_WireModel):
    """A posture change that is waiting on, or has been decided by, a human.

    ``status`` is one of ``pending``, ``approved``, ``rejected`` or
    ``expired``. While it is ``pending`` the agent is still running at
    ``current_posture`` — ``requested_posture`` has NOT taken effect.
    """

    id: str
    agent_id: str = Field(alias="agentId")
    requested_posture: TrustPosture = Field(alias="requestedPosture")
    current_posture: TrustPosture = Field(alias="currentPosture")
    reason: str | None = None
    requested_by: str | None = Field(default=None, alias="requestedBy")
    requested_by_name: str | None = Field(default=None, alias="requestedByName")
    requested_at: datetime | None = Field(default=None, alias="requestedAt")
    status: str | None = None
    reviewed_by: str | None = Field(default=None, alias="reviewedBy")
    reviewed_by_name: str | None = Field(default=None, alias="reviewedByName")
    reviewed_at: datetime | None = Field(default=None, alias="reviewedAt")
    review_notes: str | None = Field(default=None, alias="reviewNotes")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    config: dict[str, Any] = Field(default_factory=dict)


class PostureTransitionRecord(_WireModel):
    """A posture change that has been applied.

    ``to_posture`` is in force from ``transitioned_at`` onwards.
    """

    id: str
    agent_id: str = Field(alias="agentId")
    from_posture: TrustPosture | None = Field(default=None, alias="fromPosture")
    to_posture: TrustPosture = Field(alias="toPosture")
    reason: str | None = None
    trigger: str | None = None
    triggered_by: str | None = Field(default=None, alias="triggeredBy")
    triggered_by_name: str | None = Field(default=None, alias="triggeredByName")
    approved_by: str | None = Field(default=None, alias="approvedBy")
    approved_by_name: str | None = Field(default=None, alias="approvedByName")
    approved_at: datetime | None = Field(default=None, alias="approvedAt")
    transitioned_at: datetime | None = Field(default=None, alias="transitionedAt")
    metadata: dict[str, Any] | None = None


class PostureChangeResult(BaseModel):
    """The outcome of a posture-change call.

    A posture change has two possible outcomes and they demand OPPOSITE next
    actions, so the outcome is reported rather than left to be inferred:

    ``approval_pending is False``
        The change is applied. :attr:`posture` is the agent's new posture and
        :attr:`transition` carries the transition record.

    ``approval_pending is True``
        The change is recorded and awaiting a human decision. :attr:`posture`
        is the posture the agent is STILL running at — the requested posture
        has not taken effect. :attr:`approval_id` addresses the request, and
        :attr:`approval` carries it in full, including
        ``approval.requested_posture`` and ``approval.expires_at``.

    Do not re-issue the change to "make it take". The request has already
    been accepted; re-issuing creates a SECOND pending request against the
    same agent (see :meth:`PosturesModule.request_progression`).

    ``progression_eligible`` is deliberately absent: no posture-change
    response carries an eligibility verdict. Read one from
    :meth:`PosturesModule.evaluate_progression` instead.
    """

    approval_pending: bool
    agent_id: str
    posture: TrustPosture
    approval_id: str | None = None
    approval: PostureApprovalRecord | None = None
    transition: PostureTransitionRecord | None = None


class ProgressionEvaluation(_WireModel):
    """Whether an agent currently qualifies to move up a posture."""

    agent_id: str
    can_progress: bool = Field(alias="canProgress")
    current_posture: TrustPosture = Field(alias="currentPosture")
    next_posture: TrustPosture | None = Field(default=None, alias="nextPosture")
    metrics_status: list[dict[str, Any]] = Field(default_factory=list, alias="metricsStatus")
    estimated_time_to_progression: str | None = Field(
        default=None, alias="estimatedTimeToProgression"
    )
    blockers: list[str] | None = None


class PostureProgressionMetrics(_WireModel):
    """Behavioural metrics the progression evaluation is computed from.

    ``agent_id`` is carried through from the request — the endpoint answers
    with the metric values only and does not echo the agent id.
    """

    agent_id: str
    interaction_count: int = Field(default=0, alias="interactionCount")
    approval_rate: float = Field(default=0.0, alias="approvalRate")
    override_rate: float = Field(default=0.0, alias="overrideRate")
    error_rate: float = Field(default=0.0, alias="errorRate")
    plan_acceptance_rate: float | None = Field(default=None, alias="planAcceptanceRate")
    alert_accuracy: float | None = Field(default=None, alias="alertAccuracy")
    autonomous_success_rate: float | None = Field(default=None, alias="autonomousSuccessRate")
    last_evaluated_at: datetime | None = Field(default=None, alias="lastEvaluatedAt")


def _require_mapping(response: Any, *, operation: str) -> dict[str, Any]:
    """Return ``response`` as a JSON object, or raise naming what arrived."""
    if isinstance(response, dict):
        return response
    raise AgenticOSError(
        f"{operation} expected a JSON object from the server but received "
        f"{type(response).__name__}.",
        details={"operation": operation, "received_type": type(response).__name__},
    )


def _parse_model(
    model: type[BaseModel],
    payload: Any,
    *,
    operation: str,
    extra_details: dict[str, Any] | None = None,
) -> Any:
    """Validate ``payload`` into ``model``, reporting a shape mismatch usefully.

    A shape mismatch is surfaced as an :class:`AgenticOSError` carrying the
    keys that actually arrived, rather than as a raw ``pydantic``
    ``ValidationError`` — that type is in no documented SDK exception list,
    so no caller can reasonably be expected to catch it. The original error
    is preserved as the cause.
    """
    try:
        return model.model_validate(payload)
    except Exception as exc:
        details: dict[str, Any] = {
            "operation": operation,
            "expected_model": model.__name__,
            "received_keys": sorted(payload) if isinstance(payload, dict) else None,
        }
        if extra_details:
            details.update(extra_details)
        raise AgenticOSError(
            f"{operation} could not interpret the server's response as "
            f"{model.__name__}: {exc}",
            details=details,
        ) from exc


def _parse_posture_change(
    response: Any, *, agent_id: str, operation: str
) -> PostureChangeResult:
    """Build a :class:`PostureChangeResult` from a posture-change response.

    The two outcomes are told apart by the ``approvalPending`` flag, which is
    present only on the approval-pending body. The HTTP status also
    distinguishes them (202 vs 200) but the transport surfaces the parsed
    body only, so the flag is the discriminator available here.
    """
    body = _require_mapping(response, operation=operation)

    if body.get("approvalPending"):
        approval_id = body.get("approvalId")
        approval_payload = body.get("approval")
        if not isinstance(approval_payload, dict):
            # The change WAS accepted and is pending. Surface the id even in
            # this degraded case: without it the caller cannot poll, cannot
            # approve, and cannot avoid filing the request a second time.
            raise AgenticOSError(
                f"{operation}: the change is pending approval but the server's "
                f"response carried no approval record. The request was accepted "
                f"— do not re-issue it; resolve it by its approval id instead.",
                details={
                    "operation": operation,
                    "agent_id": agent_id,
                    "approval_id": approval_id,
                    "approval_pending": True,
                },
            )
        approval: PostureApprovalRecord = _parse_model(
            PostureApprovalRecord,
            approval_payload,
            operation=operation,
            extra_details={"agent_id": agent_id, "approval_id": approval_id},
        )
        return PostureChangeResult(
            approval_pending=True,
            agent_id=approval.agent_id or agent_id,
            # The agent is STILL at this posture. The requested one has not
            # taken effect and is on `approval.requested_posture`.
            posture=approval.current_posture,
            approval_id=approval_id or approval.id,
            approval=approval,
        )

    transition: PostureTransitionRecord = _parse_model(
        PostureTransitionRecord,
        body,
        operation=operation,
        extra_details={"agent_id": agent_id},
    )
    return PostureChangeResult(
        approval_pending=False,
        agent_id=transition.agent_id or agent_id,
        posture=transition.to_posture,
        transition=transition,
    )


class PosturesModule:
    """
    Trust posture management operations.

    Postures define progressive levels of autonomy (CARE-aligned; these are
    the exact lowercase values the backend accepts):
    - pseudo: Human approval required for all actions
    - supervised: Human approval for high-impact actions
    - shared_planning: Autonomous low-risk actions, approval for medium/high
    - continuous_insight: Autonomous medium-risk actions, approval for high
    - delegated: Fully autonomous (rarely granted)

    Agents progress through postures based on track record.

    Raising an agent above ``supervised`` is held for a human approver, so a
    posture-change call has two possible outcomes — applied, or pending
    approval. Both are returned as a :class:`PostureChangeResult`; read
    ``approval_pending`` to tell them apart.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # Check current posture
        ...     state = await client.trust.postures.get("agent_abc123")
        ...     print(f"Current posture: {state.posture}")
        ...
        ...     # Request progression
        ...     evaluation = await client.trust.postures.evaluate_progression(
        ...         "agent_abc123"
        ...     )
        ...     if evaluation.can_progress:
        ...         result = await client.trust.postures.request_progression(
        ...             "agent_abc123",
        ...             target_posture="shared_planning",
        ...             justification="50 successful tasks without issues",
        ...         )
        ...         if result.approval_pending:
        ...             print(f"Awaiting approval: {result.approval_id}")
        ...         else:
        ...             print(f"Applied: now {result.posture}")
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def get(self, agent_id: str) -> PostureState:
        """
        Get current posture configuration for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            The agent's posture configuration. ``posture`` is the EFFECTIVE
            posture; when ``override_active`` is set it is the override's
            posture and ``base_posture`` is what the agent reverts to.

        Note:
            This does NOT report progression eligibility — the endpoint
            carries no eligibility verdict. Use :meth:`evaluate_progression`.

        Example:
            >>> state = await client.trust.postures.get("agent_abc123")
            >>> print(f"Posture: {state.posture}")
            >>> if state.override_active:
            ...     print(f"Override in force until {state.override_info.expires_at}")
        """
        # Server route: GET /agents/{agent_id}/trust-posture — the posture
        # router mounts at /api/v1 WITHOUT the /trust prefix.
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture",
        )
        body = _require_mapping(response, operation="postures.get")
        # The endpoint answers with the configuration only; the agent id is
        # carried through from the request rather than read off the response.
        state: PostureState = _parse_model(
            PostureState,
            {**body, "agent_id": agent_id},
            operation="postures.get",
            extra_details={"agent_id": agent_id},
        )
        return state

    async def request_progression(
        self,
        agent_id: str,
        target_posture: TrustPosture,
        justification: str,
    ) -> PostureChangeResult:
        """
        Request posture progression for an agent.

        Server route: PUT /agents/{agent_id}/trust-posture. There is no
        dedicated "/posture/progression" endpoint — a posture-change request
        (whether self-initiated progression or an admin override, see
        :meth:`override`) goes through this single PUT, which decides
        internally whether the transition applies immediately or is held for
        a human approver. The wire body is ``{posture, config, reason}`` —
        NOT ``target_posture`` / ``justification`` (those SDK-side names are
        kept for API stability; they map onto the real field names below).

        THE CHANGE IS NOT ALWAYS APPLIED WHEN THIS RETURNS. Raising an agent
        above ``supervised`` is held for approval. Branch on
        ``result.approval_pending`` before reporting the agent progressed:
        while a request is pending, the agent is still running at the
        posture it had, which ``result.posture`` reports.

        Warning:
            Re-issuing a pending request does NOT resolve it — it files a
            SECOND request against the same agent, and the two then compete
            (see :meth:`approve_transition`). The endpoint offers no
            idempotency key, so a retry cannot be de-duplicated server-side.
            Before retrying after an ambiguous failure — a timeout, a dropped
            connection — call :meth:`get_pending_approval` to find out
            whether the first attempt was in fact recorded.

        Args:
            agent_id: Agent ID
            target_posture: Target posture level
            justification: Justification for progression. The endpoint
                requires at least 10 characters.

        Returns:
            The outcome of the request — applied, or pending approval with
            the approval id needed to poll or resolve it.

        Raises:
            ValidationError: If the progression is refused — a skipped
                posture level, a justification under 10 characters, or
                evidence that does not support the upgrade.
            AuthorizationError: If the caller may not change postures.

        Example:
            >>> result = await client.trust.postures.request_progression(
            ...     "agent_abc123",
            ...     target_posture="shared_planning",
            ...     justification="Completed 100 tasks with 99% success rate",
            ... )
            >>> if result.approval_pending:
            ...     print(f"Held for approval: {result.approval_id}")
            ...     print(f"Still running at: {result.posture}")
            ... else:
            ...     print(f"Applied: now {result.posture}")
        """
        posture_value = (
            target_posture.value
            if isinstance(target_posture, TrustPosture)
            else TrustPosture(target_posture).value
        )
        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture",
            json_data={"posture": posture_value, "config": {}, "reason": justification},
        )
        return _parse_posture_change(
            response, agent_id=agent_id, operation="postures.request_progression"
        )

    async def override(
        self,
        agent_id: str,
        new_posture: TrustPosture,
        reason: str,
    ) -> PostureChangeResult:
        """
        Override an agent's posture (admin action).

        Server route: PUT /agents/{agent_id}/trust-posture — the SAME endpoint
        as :meth:`request_progression`. There is no separate
        ``/posture/override`` endpoint; the PUT handler is the single
        posture-change surface, and it gates on the same delegate permission
        regardless of whether the caller's intent is a self-requested
        progression or an admin override.

        Because it is the same endpoint, it has the same two outcomes.
        LOWERING a posture — the emergency-restriction case — applies
        immediately, but RAISING one above ``supervised`` is held for
        approval exactly as :meth:`request_progression` is, so an override
        upward can return pending. Branch on ``result.approval_pending``
        rather than assuming an override took effect.

        Warning:
            The endpoint offers no idempotency key. If an upward override
            returns pending and the call is retried, the retry files a SECOND
            request. Check :meth:`get_pending_approval` before retrying after
            an ambiguous failure.

        Args:
            agent_id: Agent ID
            new_posture: New posture to set
            reason: Reason for override. The endpoint requires at least 10
                characters.

        Returns:
            The outcome — applied, or pending approval with the approval id.

        Raises:
            AuthorizationError: If caller cannot override postures
            ValidationError: If the posture change is refused

        Example:
            >>> # Emergency restriction — a downward change applies at once
            >>> result = await client.trust.postures.override(
            ...     "agent_abc123",
            ...     new_posture="pseudo",
            ...     reason="Security review pending",
            ... )
            >>> assert not result.approval_pending
            >>> print(f"Now restricted to {result.posture}")
        """
        posture_value = (
            new_posture.value
            if isinstance(new_posture, TrustPosture)
            else TrustPosture(new_posture).value
        )
        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture",
            json_data={"posture": posture_value, "config": {}, "reason": reason},
        )
        return _parse_posture_change(
            response, agent_id=agent_id, operation="postures.override"
        )

    async def approve_transition(
        self,
        agent_id: str,
        notes: str | None = None,
        approval_id: str | None = None,
    ) -> PostureChangeResult:
        """
        Approve a pending posture transition for an agent.

        Server route: POST /agents/{agent_id}/trust-posture/approve.

        ledger ``ewl-20260913-4137c62903``: this used to resolve the agent's
        pending request itself with no way for the caller to say which one,
        so with two pending requests which one this call approved was
        undefined (row order, not caller intent). ``approval_id`` closes
        that — pass the ``id`` from :meth:`get_pending_approval` (or from
        :meth:`get_my_pending_approvals`, filtered to this agent) to say
        exactly which request to decide.

        Args:
            agent_id: Agent ID
            notes: Optional approval notes
            approval_id: Which pending approval to act on. Optional while the
                agent has exactly one pending request (kept for backward
                compatibility); REQUIRED in effect once it has more than
                one — the server refuses (``ValidationError``) rather than
                picking one when this is omitted and more than one request is
                pending.

        Returns:
            The applied transition. ``approval_pending`` is False and
            ``transition`` carries the change that took effect.

        Raises:
            NotFoundError: If no pending approval matches (none pending, or
                ``approval_id`` does not match a pending row for this agent).
            ValidationError: If ``approval_id`` was omitted and more than one
                approval is pending for this agent.
            AuthorizationError: If the caller may not approve transitions

        Example:
            >>> pending = await client.trust.postures.get_pending_approval("agent_abc123")
            >>> assert pending is not None and pending.id == expected_approval_id
            >>> result = await client.trust.postures.approve_transition(
            ...     "agent_abc123",
            ...     notes="Reviewed evidence, approved",
            ...     approval_id=pending.id,
            ... )
            >>> print(f"Applied: now {result.posture}")
        """
        # `approvalId` is omitted entirely (not sent as null) when the caller
        # does not pass one — preserves the exact `{"notes": ...}` wire body
        # for the single-pending-request case, which is the common path and
        # what the server's own field default already treats identically to
        # omission.
        json_body: dict[str, Any] = {"notes": notes}
        if approval_id is not None:
            json_body["approvalId"] = approval_id
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/approve",
            json_data=json_body,
        )
        return _parse_posture_change(
            response, agent_id=agent_id, operation="postures.approve_transition"
        )

    async def get_pending_approval(self, agent_id: str) -> PostureApprovalRecord | None:
        """
        Get the posture change currently awaiting approval for an agent.

        Server route: GET /agents/{agent_id}/trust-posture/pending.

        This is the read that makes a posture change safe to retry. The
        posture-change endpoint has no idempotency key, so a client cannot
        tell an accepted-but-unacknowledged request from one that never
        arrived. Reading the pending request answers that directly: if one is
        already recorded, the earlier attempt landed and re-issuing it would
        file a duplicate.

        Note:
            The endpoint returns at most ONE request. While at most one is
            pending this is unambiguous; if MORE than one is pending for the
            agent, the server now refuses (``ValidationError``) instead of
            picking one arbitrarily (ledger ``ewl-20260913-4137c62903``) —
            resolve the ambiguity via :meth:`get_my_pending_approvals`
            filtered to this agent, then pass the chosen ``id`` as
            ``approval_id`` to :meth:`approve_transition`.

        Args:
            agent_id: Agent ID

        Returns:
            The pending approval record, or ``None`` if nothing is pending.

        Raises:
            ValidationError: If more than one approval is pending for the
                agent (ambiguous — this read carries no id to disambiguate
                with).

        Example:
            >>> pending = await client.trust.postures.get_pending_approval("agent_abc123")
            >>> if pending is None:
            ...     result = await client.trust.postures.request_progression(
            ...         "agent_abc123",
            ...         target_posture="shared_planning",
            ...         justification="Completed 100 tasks with 99% success rate",
            ...     )
            ... else:
            ...     print(f"Already awaiting approval: {pending.id}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/pending",
        )
        if response is None:
            return None
        record: PostureApprovalRecord = _parse_model(
            PostureApprovalRecord,
            response,
            operation="postures.get_pending_approval",
            extra_details={"agent_id": agent_id},
        )
        return record

    async def evaluate_progression(self, agent_id: str) -> ProgressionEvaluation:
        """
        Evaluate whether an agent currently qualifies to move up a posture.

        Server route: GET /agents/{agent_id}/trust-posture/evaluate.

        This is the eligibility verdict. No posture read and no
        posture-change response carries one, so this is the only call that
        answers "may this agent progress?".

        Args:
            agent_id: Agent ID

        Returns:
            The evaluation — ``can_progress``, the ``next_posture`` in line,
            per-metric status, and any ``blockers``.

        Example:
            >>> evaluation = await client.trust.postures.evaluate_progression("agent_abc123")
            >>> if evaluation.can_progress:
            ...     print(f"Ready for {evaluation.next_posture}")
            ... else:
            ...     print(f"Blocked by: {evaluation.blockers}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/evaluate",
        )
        body = _require_mapping(response, operation="postures.evaluate_progression")
        evaluation: ProgressionEvaluation = _parse_model(
            ProgressionEvaluation,
            {**body, "agent_id": agent_id},
            operation="postures.evaluate_progression",
            extra_details={"agent_id": agent_id},
        )
        return evaluation

    async def reject_transition(
        self,
        agent_id: str,
        notes: str,
    ) -> dict[str, Any]:
        """
        Reject a pending posture transition for an agent.

        Server route: POST /agents/{agent_id}/trust-posture/reject
        (RejectTransitionRequest at
        ``notes`` requires >= 10 characters server-side). Returns the
        rejected approval record as the raw response dict.

        The dict is returned as-is for compatibility with callers that
        already index it. Its shape is the one :class:`PostureApprovalRecord`
        models, so a caller wanting typed access can parse it with
        ``PostureApprovalRecord.model_validate(record)``.

        Args:
            agent_id: Agent ID
            notes: Rejection reason (server requires >= 10 characters)

        Returns:
            Raw rejected-approval record from the server

        Raises:
            NotFoundError: If no pending approval exists for the agent
            ValidationError: If notes is too short

        Example:
            >>> record = await client.trust.postures.reject_transition(
            ...     "agent_abc123",
            ...     notes="Insufficient evidence for this posture level"
            ... )
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/reject",
            json_data={"notes": notes},
        )
        return response

    async def get_metrics(self, agent_id: str) -> PostureProgressionMetrics:
        """
        Get posture progression metrics for an agent.

        These are the behavioural rates the progression evaluation is
        computed from. They are inputs, not a verdict — for the verdict, use
        :meth:`evaluate_progression`.

        Args:
            agent_id: Agent ID

        Returns:
            Interaction volume and the approval / override / error rates,
            plus the posture-specific rates where they apply.

        Example:
            >>> metrics = await client.trust.postures.get_metrics("agent_abc123")
            >>> print(f"Interactions: {metrics.interaction_count}")
            >>> print(f"Approval rate: {metrics.approval_rate:.1%}")
            >>> print(f"Error rate: {metrics.error_rate:.1%}")
        """
        # Server route: GET /agents/{agent_id}/trust-posture/metrics
        # (posture router mounts at /api/v1).
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/metrics",
        )
        body = _require_mapping(response, operation="postures.get_metrics")
        # The endpoint answers with the metric values only; the agent id is
        # carried through from the request rather than read off the response.
        metrics: PostureProgressionMetrics = _parse_model(
            PostureProgressionMetrics,
            {**body, "agent_id": agent_id},
            operation="postures.get_metrics",
            extra_details={"agent_id": agent_id},
        )
        return metrics
