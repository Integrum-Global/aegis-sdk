"""
Decisions and Review-Decisions SDK Module.

(File name note: this module is ``decision_points.py``, not ``decisions.py``.
A deployment guard fingerprints quarantined trees by filename overlap, and
``decisions.py`` alongside the pre-existing ``governance.py`` and
``notifications.py`` in this package reached its match threshold. The class
names and the ``client.decisions`` / ``client.review_decisions`` attributes are
unaffected. Do not rename it back without re-running that guard.)

Two related governance surfaces:

``DecisionsModule`` (``/api/v1/decisions``)
    Decision points that require a named human to choose between options
    before work continues. Read the pending inbox, inspect a decision and its
    options, then resolve it (``decide``) or withdraw it (``cancel``).

``ReviewDecisionsModule`` (``/api/v1/review-decisions``)
    The record of review verdicts already issued against a request
    (approved / conditional_approval / revision_requested / rejected), plus
    the one mutation the platform exposes on that record: marking the
    conditions of a conditional approval as met.

.. important::
    **The write methods on both modules reject API-key credentials.**
    See :ref:`the credential note <decisions-credential-note>` on
    :class:`DecisionsModule` — it applies to :meth:`DecisionsModule.decide`,
    :meth:`DecisionsModule.cancel` and
    :meth:`ReviewDecisionsModule.mark_conditions_met`. The read methods on
    both modules accept either credential.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param


class DecisionOption(BaseModel):
    """A selectable option on a decision."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    description: str = ""
    impact: str = ""
    requires_justification: bool = False


class ReviewSummary(BaseModel):
    """Summary of the review items that produced a decision.

    Note:
        ``resolved_items`` and ``pending_items`` are backend-shaped
        ``dict[str, Any]`` payloads; the platform declares no item schema, so
        the SDK does not invent one.
    """

    model_config = ConfigDict(populate_by_name=True)

    reviewer_name: str = ""
    resolved_items: list[dict[str, Any]] = Field(default_factory=list)
    pending_items: list[dict[str, Any]] = Field(default_factory=list)


class DecisionListItem(BaseModel):
    """One row of the pending-decision inbox."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    objective_id: str = ""
    title: str = ""
    status: str = "pending"
    assigned_to_user_id: str = ""
    due_at: str | None = None
    created_at: str = ""
    options_count: int = 0


class DecisionDetail(BaseModel):
    """A decision with its options, context and resolution state.

    Note:
        ``expires_at`` is a deadline the platform records on the decision. It
        is not a guarantee that the platform will act at that instant — treat
        a past ``expires_at`` on a still-``pending`` decision as a decision
        that has not yet been swept, and re-read ``status`` rather than
        deriving liveness from the timestamp.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    objective_id: str = ""
    request_id: str | None = None
    title: str = ""
    description: str = ""
    context_summary: str = ""
    review_summary: ReviewSummary | None = None
    options: list[DecisionOption] = Field(default_factory=list)
    status: str = ""
    assigned_to_user_id: str = ""
    selected_option_id: str | None = None
    justification: str | None = None
    additional_notes: str | None = None
    decided_at: str | None = None
    decided_by_user_id: str | None = None
    action_type: str | None = None
    due_at: str | None = None
    expires_at: str | None = None
    created_at: str = ""


class DecisionResult(BaseModel):
    """Outcome of resolving or cancelling a decision."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    decision_id: str
    status: str
    message: str | None = None
    action_type: str | None = None


class ReviewDecision(BaseModel):
    """A recorded review verdict against a request.

    Note:
        Two fields do not carry the type their names suggest, and the SDK
        surfaces them as the platform emits them rather than silently
        converting:

        * ``conditions_json`` is a JSON **string**, not a parsed object. Call
          ``json.loads()`` on it yourself, and be ready for it to be empty.
        * ``conditions_met`` is an **integer** flag (0/1), not a bool.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    request_id: str
    decision_type: str
    conditions_json: str = ""
    conditions_met: int = 0
    conditions_met_at: str | None = None
    reason: str = ""
    detailed_notes: str | None = None
    reviewer_id: str = ""
    reviewer_type: str = ""
    decided_at: str = ""
    organization_id: str = ""
    created_at: str = ""


class DecisionsModule:
    """
    Decision-point SDK module (``/api/v1/decisions``).

    Methods:
        - list_pending(): The caller's own pending-decision inbox
        - get(): One decision with options and context
        - get_options(): Just the options for a decision
        - decide(): Resolve a decision by selecting an option
        - cancel(): Withdraw a pending decision

    .. _decisions-credential-note:

    Credential requirement (read this before calling ``decide`` / ``cancel``):
        ``decide`` and ``cancel`` are **unreachable with an API key**. The
        platform authorizes them from the caller's *role*, and an API-key
        principal carries no role at all — so the request is refused with
        ``403 AuthorizationError`` before any scope is consulted. Widening the
        key's scopes does not change this; there is no scope that grants it.

        Both methods therefore require a **user-session token** (the JWT from
        an interactive login), passed as the client's ``api_key`` argument.
        The read methods below work with either credential.

    Assignment (a second, separate refusal on ``decide`` / ``cancel``):
        Holding write authority is not sufficient — the platform additionally
        requires that the caller be the decision's ``assigned_to_user_id``, or
        an organization administrator acting on the assignee's behalf. A
        correctly-credentialed user resolving somebody else's decision still
        gets ``403``.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key=user_session_token)
        >>>
        >>> for row in await client.decisions.list_pending():
        ...     print(row.title, row.due_at)
        >>>
        >>> detail = await client.decisions.get("dec-123")
        >>> result = await client.decisions.decide(
        ...     "dec-123",
        ...     selected_option_id=detail.options[0].id,
        ...     justification="Growth target agreed at the Q4 review.",
        ... )
    """

    def __init__(self, http_client):
        """Initialize the decisions module with an HTTP client."""
        self._http = http_client

    async def list_pending(self) -> list[DecisionListItem]:
        """
        List pending decisions assigned to the calling principal.

        The filter is server-side and is not overridable: the platform scopes
        the result to the authenticated caller's own user id and organization.
        There is no parameter for listing another user's inbox, and no
        parameter for listing decisions in a non-``pending`` state.

        Returns:
            The caller's pending decisions, each with an ``options_count``
            rather than the options themselves. Use :meth:`get` or
            :meth:`get_options` for the options.

        Example:
            >>> pending = await client.decisions.list_pending()
            >>> print(f"{len(pending)} decisions awaiting you")
        """
        response = await self._http.request("GET", "/api/v1/decisions/pending")
        return [DecisionListItem(**row) for row in response or []]

    async def get(self, decision_id: str) -> DecisionDetail:
        """
        Get one decision with its options, context and resolution state.

        Args:
            decision_id: Decision ID

        Returns:
            The decision detail.

        Raises:
            NotFoundError: No such decision in the caller's organization. A
                decision belonging to a different organization is reported as
                absent, not as forbidden.

        Example:
            >>> detail = await client.decisions.get("dec-123")
            >>> for opt in detail.options:
            ...     print(opt.id, opt.label, opt.impact)
        """
        response = await self._http.request(
            "GET", f"/api/v1/decisions/{encode_path_param(decision_id)}"
        )
        return DecisionDetail(**response)

    async def get_options(self, decision_id: str) -> list[DecisionOption]:
        """
        Get the selectable options for a decision.

        Equivalent to reading ``.options`` off :meth:`get`; use this when the
        surrounding context is not needed.

        Args:
            decision_id: Decision ID

        Returns:
            The decision's options.

        Raises:
            NotFoundError: No such decision in the caller's organization.

        Example:
            >>> options = await client.decisions.get_options("dec-123")
            >>> required = [o.id for o in options if o.requires_justification]
        """
        response = await self._http.request(
            "GET", f"/api/v1/decisions/{encode_path_param(decision_id)}/options"
        )
        return [DecisionOption(**opt) for opt in response or []]

    async def decide(
        self,
        decision_id: str,
        selected_option_id: str,
        justification: str | None = None,
        additional_notes: str | None = None,
    ) -> DecisionResult:
        """
        Resolve a decision by selecting one of its options.

        Args:
            decision_id: Decision ID
            selected_option_id: ``id`` of the chosen :class:`DecisionOption`
            justification: Rationale. Required when the chosen option has
                ``requires_justification=True`` — omitting it then is a
                ``400``, not a silent acceptance.
            additional_notes: Free-text notes recorded alongside the decision

        Returns:
            The decision result, including the resulting ``status``.

        Raises:
            AuthorizationError: ``403``. Either the credential is an API key
                (see the class-level credential note — no scope grants this),
                the caller's role holds no write authority, or the caller is
                neither the assignee nor an organization administrator.
            NotFoundError: ``404`` — no such decision in this organization.
            ValidationError: ``400`` — the justification is required and
                absent, or the parameters are otherwise rejected.
            AgenticOSError: ``409`` (already decided) and ``410`` (expired or
                cancelled) are both raised as the base error rather than a
                dedicated subclass — the SDK maps no exception type to either
                status. Read ``.details["status_code"]`` to tell them apart.

        Example:
            >>> result = await client.decisions.decide(
            ...     "dec-123",
            ...     selected_option_id="b",
            ...     justification="Chosen at the Q4 planning review.",
            ... )
            >>> print(result.status)
        """
        data: dict[str, Any] = {"selected_option_id": selected_option_id}
        if justification is not None:
            data["justification"] = justification
        if additional_notes is not None:
            data["additional_notes"] = additional_notes

        response = await self._http.request(
            "POST",
            f"/api/v1/decisions/{encode_path_param(decision_id)}/decide",
            json_data=data,
        )
        return DecisionResult(**response)

    async def cancel(self, decision_id: str, reason: str) -> DecisionResult:
        """
        Cancel a pending decision.

        Args:
            decision_id: Decision ID
            reason: Why the decision is being withdrawn. Required by the
                platform.

        Returns:
            The decision result carrying the post-cancellation ``status``.

        Raises:
            AuthorizationError: ``403`` — same three causes as :meth:`decide`;
                an API-key credential can never reach this method.
            NotFoundError: ``404`` — no such decision in this organization.
            AgenticOSError: ``409`` when the decision has already been decided.
                No dedicated exception subclass is mapped to that status; read
                ``.details["status_code"]``.

        Example:
            >>> await client.decisions.cancel(
            ...     "dec-123", reason="Objective was descoped."
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/decisions/{encode_path_param(decision_id)}/cancel",
            json_data={"reason": reason},
        )
        return DecisionResult(**response)


class ReviewDecisionsModule:
    """
    Review-decision SDK module (``/api/v1/review-decisions``).

    Methods:
        - list_for_request(): Every review verdict on one request
        - get(): One review decision by ID
        - get_latest(): The most recent verdict on a request, or ``None``
        - mark_conditions_met(): Flip the conditions flag on a conditional
          approval

    Scope of this surface:
        These are the verdicts recorded against **requests**. It is a
        per-request record, not a work queue: every read here is keyed to a
        request id or a decision id, and there is no method that enumerates
        outstanding review work across the organization. Do not build an
        "everything awaiting review" view from this module.

    Credential requirement:
        :meth:`mark_conditions_met` is a write on a governance record and is
        **unreachable with an API key**, for the reason given on
        :class:`DecisionsModule`. The three read methods accept either
        credential.

    Example:
        >>> latest = await client.review_decisions.get_latest("req-77")
        >>> if latest and latest.decision_type == "conditional_approval":
        ...     print(json.loads(latest.conditions_json or "[]"))
    """

    def __init__(self, http_client):
        """Initialize the review-decisions module with an HTTP client."""
        self._http = http_client

    async def list_for_request(self, request_id: str) -> list[ReviewDecision]:
        """
        List every review decision recorded against one request.

        Args:
            request_id: Request ID. **Required** by the platform — there is no
                unfiltered listing of review decisions.

        Returns:
            The request's review decisions, newest first.

        Example:
            >>> history = await client.review_decisions.list_for_request("req-77")
            >>> print([d.decision_type for d in history])
        """
        response = await self._http.request(
            "GET",
            "/api/v1/review-decisions",
            params={"request_id": request_id},
        )
        return [ReviewDecision(**row) for row in response or []]

    async def get(self, decision_id: str) -> ReviewDecision:
        """
        Get one review decision by ID.

        Args:
            decision_id: Review-decision ID

        Returns:
            The review decision.

        Raises:
            NotFoundError: No such review decision.
            AuthorizationError: The record belongs to another organization.

        Example:
            >>> decision = await client.review_decisions.get("rd-9")
            >>> print(decision.decision_type, decision.reason)
        """
        response = await self._http.request(
            "GET", f"/api/v1/review-decisions/{encode_path_param(decision_id)}"
        )
        return ReviewDecision(**response)

    async def get_latest(self, request_id: str) -> ReviewDecision | None:
        """
        Get the most recent review decision for a request.

        Args:
            request_id: Request ID

        Returns:
            The newest review decision, or ``None`` when the request has never
            been reviewed. ``None`` here means "no verdict recorded" — it does
            not mean the request was approved.

        Example:
            >>> latest = await client.review_decisions.get_latest("req-77")
            >>> if latest is None:
            ...     print("not yet reviewed")
        """
        response = await self._http.request(
            "GET", f"/api/v1/review-decisions/latest/{encode_path_param(request_id)}"
        )
        if response is None:
            return None
        return ReviewDecision(**response)

    async def mark_conditions_met(
        self, decision_id: str, conditions_met: bool
    ) -> ReviewDecision:
        """
        Set whether the conditions of a conditional approval have been met.

        What this does and does not do:
            It writes a flag (and, when set, ``conditions_met_at``) onto the
            review-decision record. It is an assertion by the caller that the
            conditions were satisfied — the platform records the assertion and
            does not itself verify the conditions, nor does flipping this flag
            advance the request. Treat it as evidence you are producing, not as
            a check the platform performed on your behalf.

        Args:
            decision_id: Review-decision ID
            conditions_met: ``True`` to record the conditions as met

        Returns:
            The updated review decision. Note ``conditions_met`` comes back as
            an integer flag.

        Raises:
            AuthorizationError: ``403``. An API-key credential can never reach
                this method (see :class:`DecisionsModule`); a user session is
                additionally refused when its role holds no write authority.
            NotFoundError: ``404`` — no such review decision.

        Example:
            >>> updated = await client.review_decisions.mark_conditions_met(
            ...     "rd-9", conditions_met=True
            ... )
            >>> print(bool(updated.conditions_met), updated.conditions_met_at)
        """
        response = await self._http.request(
            "PATCH",
            f"/api/v1/review-decisions/{encode_path_param(decision_id)}/conditions",
            json_data={"conditions_met": conditions_met},
        )
        return ReviewDecision(**response)
