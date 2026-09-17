"""
Agentic OS SDK Objectives Module.

Provides operations for managing objectives (top-level work units).

Objectives are served under ``/api/v1/objectives``. The API's
``ObjectiveResponse`` does not match :class:`~aegis_sdk.types.Objective`
field-for-field (``priority`` is a string tier on the wire, not an int; the
lifecycle has more states than :class:`~aegis_sdk.types.ObjectiveStatus`
declares; ``created_by``/``workspace_id``/``agent_id`` are optional on the
wire but required here), so responses are normalized before construction —
see ``_normalize_objective`` / ``_priority_to_wire`` / ``_priority_from_wire``
for the mapping.

Known limitation: the SDK's ``Objective``/``ObjectiveStatus`` types still
carry a narrower status vocabulary and a stricter optional-field shape than
the API returns. Aligning them is a tracked follow-up. Several methods on
this module address routes the API does not serve and are marked with a
warning in their own docstrings.

Progress STREAMING is deliberately not duplicated here: the platform's
progress SSE stream is consumed by ``client.work_objectives.stream_progress``
and a second client method for the same server handler would be a rival, not
coverage.

⚠ AUTHENTICATION — MIXED. This module's routes now admit an API key, with three
exceptions that stay human-only (named below). The persona allowlists are
unchanged.

Both router-level gates were swapped for the key-aware variant, so a key
holding ANY ``agents`` scope (``agents:read`` or ``agents:write``) passes router
admission. A key holding none is refused with 403, and that refusal names the
scopes which would have admitted it — a key is never admitted merely by
existing.

Two things that does NOT say:

  * The router gate is COARSE by design. It decides only whether a key has any
    business in this router, mirroring what the persona check does for a human.
    The read-versus-write and exact-action boundary is still enforced by the
    per-route permission/scope dependency behind it.
  * Three routes stay human-only, and one of them is the LIST endpoint:
    ``GET /objectives``, ``POST /objectives/{id}/admin-status`` and
    ``POST /objectives/{id}/admin-tasks``. They keep plain persona gates
    (``executive``/``admin`` and ``admin``/``architect``), neither of which has
    an API-key scope analogue. The list route is the one to watch: every other
    read on this prefix admits a key, so a key that works everywhere else on
    this module is still refused when it ENUMERATES.

So for a client built as ``AgenticOSClient(api_key=...)`` the split is no longer
credential type but SCOPE. Session tokens keep working exactly as before: the
key-aware gate's JWT branch *is* the persona check, so no session gains or loses
anything.

Not established: that a write completes end to end for a real key against a live
database. Admission is proven at the gate; the full round trip is not.
"""

import builtins
from datetime import UTC, datetime
from typing import Any

from .._http import encode_path_param
from ..types import (
    Objective,
    ObjectiveStatus,
    PaginatedResponse,
    Request,
)

# The API's priority tiers are a string enum, NOT an int. Mapped to and from
# the SDK's legacy int-priority field band-wise.
_PRIORITY_TO_WIRE_BANDS: tuple[tuple[int, str], ...] = (
    (2, "low"),
    (6, "medium"),
    (8, "high"),
)
_PRIORITY_FROM_WIRE: dict[str, int] = {"low": 2, "medium": 5, "high": 8, "urgent": 10}

# The API's status vocabulary, collapsed onto the SDK's 6-value
# ObjectiveStatus enum. "plan_review"/"confirmed" are pre-
# execution holds (closest SDK analog: PENDING); "decision" is a still-active
# post-execution hold awaiting a human decision (closest analog: IN_PROGRESS).
_STATUS_FROM_WIRE: dict[str, ObjectiveStatus] = {
    "draft": ObjectiveStatus.DRAFT,
    "pending": ObjectiveStatus.PENDING,
    "plan_review": ObjectiveStatus.PENDING,
    "confirmed": ObjectiveStatus.PENDING,
    "executing": ObjectiveStatus.IN_PROGRESS,
    "decision": ObjectiveStatus.IN_PROGRESS,
    "completed": ObjectiveStatus.COMPLETED,
    "cancelled": ObjectiveStatus.CANCELLED,
    "failed": ObjectiveStatus.FAILED,
}


def _priority_to_wire(priority: int) -> str:
    """Map the SDK's legacy int priority (higher = more urgent) to the real
    backend's string tier."""
    for threshold, label in _PRIORITY_TO_WIRE_BANDS:
        if priority <= threshold:
            return label
    return "urgent"


def _priority_from_wire(priority: Any) -> int:
    """Map the real backend's string priority tier back to the SDK's int
    field. Already-int values (defensive) pass through unchanged."""
    if isinstance(priority, str):
        return _PRIORITY_FROM_WIRE.get(priority, 5)
    return int(priority or 0)


def _normalize_objective(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt the real ``ObjectiveResponse`` wire shape into the fields
    :class:`~aegis_sdk.types.Objective` requires. See the module docstring
    for the vocabulary difference this bridges."""
    return {
        "id": raw.get("id", ""),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "agent_id": raw.get("agent_id") or "",
        "status": _STATUS_FROM_WIRE.get(raw.get("status", "draft"), ObjectiveStatus.PENDING),
        "priority": _priority_from_wire(raw.get("priority")),
        "organization_id": raw.get("organization_id", ""),
        "workspace_id": raw.get("workspace_id") or "",
        "created_by": raw.get("created_by_user_id") or raw.get("requester_user_id") or "",
        "assigned_to": None,
        "metadata": {
            "agent_name": raw.get("agent_name"),
            "trust_chain_id": raw.get("trust_chain_id"),
            "due_at": raw.get("due_at"),
        },
        "created_at": raw.get("created_at") or datetime.now(UTC),
        "updated_at": raw.get("updated_at") or raw.get("created_at") or datetime.now(UTC),
        "completed_at": raw.get("completed_at"),
    }


class ObjectivesModule:
    """
    Objectives management operations.

    Objectives are top-level work units that contain one or more requests.
    They represent high-level goals that agents work towards.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     objective = await client.objectives.create(
        ...         title="Research quantum computing",
        ...         description="Analyze recent advances in quantum computing",
        ...     )
        ...     print(f"Created objective: {objective.id}")
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def list(
        self,
        status: ObjectiveStatus | str | None = None,
        page_size: int = 50,
    ) -> PaginatedResponse[Objective]:
        """
        List objectives across the organization.

        ``GET /api/v1/objectives`` is an executive/admin-only management
        endpoint, and it is the ONE read on this prefix an API key cannot reach.
        Callers without that persona -- and every API-key principal -- should
        use ``GET /api/v1/objectives/recent`` instead: it admits a key holding
        ``agents:read``, and this SDK wraps it as
        ``client.work_objectives.get_recent_objectives(limit=...)`` in the
        ``work_objectives`` module.

        It is not a drop-in substitute for the envelope below. ``recent`` takes
        ``limit`` (1-100) rather than ``page_size``, returns records ordered
        most-recent-first, and carries no ``total`` at all. Whether that is
        sufficient to ENUMERATE an organization's objectives is not established
        here -- it is the Work Home landing feed, and it is documented as one.

        Supported params are ``status``, ``page_size`` and ``sort``. There is
        no ``page``, ``agent_id`` or ``workspace_id`` filter — the endpoint
        always returns the first ``page_size`` records. Its envelope is
        ``{"records": [...], "total": N}`` where ``total`` is the length of
        the returned page, not an organization-wide count.

        Args:
            status: Filter by objective status (e.g. "executing")
            page_size: Items per page (max 200)

        Returns:
            Paginated list of objectives. ``page`` is always 1 and
            ``has_next`` is a heuristic (``len(records) >= page_size``),
            because this endpoint does not paginate.

        Example:
            >>> objectives = await client.objectives.list(status="executing")
            >>> print(f"Found {len(objectives.items)} executing objectives")
        """
        params: dict[str, Any] = {"page_size": page_size}
        if status:
            params["status"] = status.value if isinstance(status, ObjectiveStatus) else status

        response = await self._http.request("GET", "/api/v1/objectives", params=params)
        records = response.get("records", [])
        total = response.get("total", len(records))
        return PaginatedResponse[Objective](
            items=[Objective(**_normalize_objective(item)) for item in records],
            total=total,
            page=1,
            page_size=page_size,
            has_next=len(records) >= page_size,
        )

    async def create(
        self,
        title: str,
        description: str,
        agent_id: str | None = None,
        priority: int = 5,
        workspace_id: str | None = None,
        due_at: str | None = None,
        selected_posture: str | None = None,
    ) -> Objective:
        """
        Create a new objective.

        Verified route: ``POST /api/v1/objectives`` with ``ObjectiveCreate`` — the real body fields are
        ``title``, ``description``, ``agent_id`` (optional — the server
        auto-assigns the caller's delegate agent when omitted), ``priority``
        (a STRING tier, not an int — see ``_priority_to_wire``), ``due_at``,
        ``workspace_id``, ``selected_posture``. There is NO ``metadata``
        field on the wire (the prior implementation sent one; the server
        silently dropped it — objectives have no persisted metadata bag).

        Args:
            title: Objective title
            description: Detailed description of the objective
            agent_id: ID of the agent to work on this objective (auto-
                assigned to the caller's delegate agent if omitted)
            priority: Priority level, 0-10 (higher = more urgent); mapped to
                the server's low/medium/high/urgent string tiers
            workspace_id: Workspace ID (uses default if not specified)
            due_at: Optional ISO due date/time
            selected_posture: Optional originator-determined trust posture
                (one of pseudo/supervised/shared_planning/continuous_insight/
                delegated)

        Returns:
            Created objective

        Example:
            >>> objective = await client.objectives.create(
            ...     title="Analyze sales data",
            ...     description="Process Q4 sales data and generate insights",
            ...     priority=8,
            ... )
        """
        json_data: dict[str, Any] = {
            "title": title,
            "description": description,
            "priority": _priority_to_wire(priority),
        }
        if agent_id is not None:
            json_data["agent_id"] = agent_id
        if workspace_id is not None:
            json_data["workspace_id"] = workspace_id
        if due_at is not None:
            json_data["due_at"] = due_at
        if selected_posture is not None:
            json_data["selected_posture"] = selected_posture

        response = await self._http.request(
            "POST",
            "/api/v1/objectives",
            json_data=json_data,
        )
        return Objective(**_normalize_objective(response))

    async def get(self, objective_id: str) -> Objective:
        """
        Get objective by ID.

        Args:
            objective_id: Objective ID

        Returns:
            Objective details

        Raises:
            NotFoundError: If objective doesn't exist

        Example:
            >>> objective = await client.objectives.get("obj_abc123")
            >>> print(f"Objective: {objective.title} ({objective.status})")
        """
        response = await self._http.request(
            "GET", f"/api/v1/objectives/{encode_path_param(objective_id)}"
        )
        return Objective(**_normalize_objective(response))

    async def update(
        self,
        objective_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        assigned_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Objective:
        """
        Update an objective.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``PUT /api/v1/objectives/{objective_id}`` is not served, and
            there is no PATCH equivalent. The nearest available surface is
            ``POST /api/v1/objectives/{objective_id}/admin-status``, which
            updates ``status`` only and requires an admin or architect
            persona.

        Args:
            objective_id: Objective ID
            title: New title
            description: New description
            priority: New priority
            assigned_to: New assignee
            metadata: New metadata (merged with existing)

        Returns:
            Updated objective

        Example:
            >>> objective = await client.objectives.update(
            ...     "obj_abc123",
            ...     priority=10,
            ... )
        """
        from ..types import ObjectiveUpdate

        update_data = ObjectiveUpdate(
            title=title,
            description=description,
            priority=priority,
            assigned_to=assigned_to,
            metadata=metadata,
        )
        response = await self._http.request(
            "PUT",
            f"/api/v1/objectives/{encode_path_param(objective_id)}",
            json_data=update_data.model_dump(exclude_none=True),
        )
        return Objective(**_normalize_objective(response))

    async def cancel(self, objective_id: str, reason: str | None = None) -> dict[str, Any]:
        """
        Cancel (stop) an objective's execution.

        Calls ``POST /api/v1/objectives/{objective_id}/stop`` with a
        ``StopExecutionBody = {reason}``. Stopping is terminal — a stopped
        objective cannot be resumed. The response is a small status dict
        (``{"success", "objective_id", "status", "reason"}``), not a full
        ``Objective``.

        Args:
            objective_id: Objective ID
            reason: Optional reason for cancellation

        Returns:
            ``{"success": bool, "objective_id": str, "status": "cancelled", "reason": str}``

        Example:
            >>> result = await client.objectives.cancel(
            ...     "obj_abc123",
            ...     reason="Requirements changed"
            ... )
        """
        return await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/stop",
            json_data={"reason": reason},
        )

    async def confirm_implementation(self, objective_id: str) -> dict[str, Any]:
        """
        Confirm an objective's implementation plan and launch execution.

        Verified route: ``POST /api/v1/objectives/{objective_id}/confirm-implementation`` — transitions the
        objective from ``plan_review``/``confirmed`` to ``executing`` and
        launches agent execution as a background task. Takes no request
        body.

        Args:
            objective_id: Objective ID

        Returns:
            ``{"success": bool, "objective_id": str, "status": "executing"}``

        Raises:
            NotFoundError: If objective doesn't exist
            ValidationError: If the objective is not in a confirmable state

        Example:
            >>> result = await client.objectives.confirm_implementation("obj_abc123")
            >>> print(result["status"])
        """
        return await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/confirm-implementation",
        )

    async def decide(
        self,
        objective_id: str,
        decision_id: str,
        selected_option_id: str,
        justification: str | None = None,
        additional_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Submit a decision for an objective in the decision phase.

        Verified route: ``POST /api/v1/objectives/{objective_id}/decide``
        with ``DecisionBody``.
        The objective must be in ``"decision"`` status. Depending on
        ``selected_option_id``'s resolved action type, the objective is
        completed (``action_type == "proceed"``), cancelled
        (``"reject"``), or returned to executing (``"revise"`` /
        ``"more_analysis"``) — the response shape varies accordingly, so
        this returns the raw dict rather than a typed ``Objective``.

        Args:
            objective_id: Objective ID
            decision_id: ID of the decision record being answered
            selected_option_id: The chosen option's ID
            justification: Optional justification for the decision
            additional_notes: Optional additional notes

        Returns:
            Raw response dict — always includes ``status``, ``objective_id``,
            ``decision_id``, ``action_type``; ``"proceed"`` additionally
            includes ``completion_summary``.

        Raises:
            NotFoundError: If the decision doesn't exist
            ValidationError: If the decision was already made or has expired

        Example:
            >>> result = await client.objectives.decide(
            ...     "obj_abc123",
            ...     decision_id="dec_1",
            ...     selected_option_id="proceed",
            ... )
        """
        json_data: dict[str, Any] = {
            "decision_id": decision_id,
            "selected_option_id": selected_option_id,
        }
        if justification is not None:
            json_data["justification"] = justification
        if additional_notes is not None:
            json_data["additional_notes"] = additional_notes

        return await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/decide",
            json_data=json_data,
        )

    async def get_progress(self, objective_id: str) -> dict[str, Any]:
        """
        Get the current execution progress for an objective.

        Verified route: ``GET /api/v1/objectives/{objective_id}/progress``. Returns a rich progress
        report (task-graph-derived steps, graph nodes, elapsed/estimated
        time, cost, and constraint-envelope dimensions) that has no
        corresponding typed model in this SDK yet, so this returns the raw
        dict. Use :meth:`get` for the objective's own lifecycle status.

        Args:
            objective_id: Objective ID

        Returns:
            Raw progress dict — keys include ``status``, ``overall_progress``,
            ``steps``, ``graph_nodes``, ``elapsed_ms``,
            ``estimated_remaining_ms``, ``cost``, ``constraint_dimensions``.

        Example:
            >>> progress = await client.objectives.get_progress("obj_abc123")
            >>> print(f"{progress['overall_progress']}% complete")
        """
        return await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/progress",
        )

    async def submit(
        self,
        objective_id: str,
        summary: str,
        artifacts: builtins.list[str] | None = None,
    ) -> Objective:
        """
        Submit a completed objective.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``POST /api/v1/objectives/{objective_id}/submit`` is not served.
            Objectives are completed through :meth:`decide` with
            ``action_type == "proceed"``, which runs completion server-side.

        Args:
            objective_id: Objective ID
            summary: Summary of work completed
            artifacts: List of artifact IDs

        Returns:
            Submitted objective

        Example:
            >>> objective = await client.objectives.submit(
            ...     "obj_abc123",
            ...     summary="Analysis complete with 5 key insights",
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/submit",
            json_data={"summary": summary, "artifacts": artifacts or []},
        )
        return Objective(**_normalize_objective(response))

    async def get_requests(
        self,
        objective_id: str,
        status: str | None = None,
    ) -> builtins.list[Request]:
        """
        Get all requests (tasks) for an objective.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/objectives/{objective_id}/requests`` is not served
            as a top-level list; only per-request sub-actions
            (``/requests/{request_id}/decompose|complete|submit-deliverable``)
            exist. The task graph is available from :meth:`get_progress`, as
            ``steps`` / ``graph_nodes``.

        Args:
            objective_id: Objective ID
            status: Filter by request status

        Returns:
            List of requests

        Example:
            >>> requests = await client.objectives.get_requests("obj_abc123")
            >>> print(f"Found {len(requests)} requests")
        """
        params = {}
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/requests",
            params=params,
        )
        return [Request(**item) for item in response]

    async def get_decisions(self, objective_id: str) -> builtins.list[dict[str, Any]]:
        """
        Get all decisions for an objective.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/objectives/{objective_id}/decisions`` is not
            served. Decisions can be submitted with :meth:`decide` but are
            not readable back through a list endpoint.

        Args:
            objective_id: Objective ID

        Returns:
            List of decisions made during objective execution

        Example:
            >>> decisions = await client.objectives.get_decisions("obj_abc123")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/decisions",
        )
        return response

    async def get_artifacts(self, objective_id: str) -> builtins.list[dict[str, Any]]:
        """
        Get all artifacts for an objective.

        Verified route: ``GET /api/v1/objectives/{objective_id}/artifacts`` — returns a bare list of
        artifact dicts directly (not wrapped in an envelope), matching this
        method's existing (unchanged) return handling.

        Args:
            objective_id: Objective ID

        Returns:
            List of artifacts produced during objective execution

        Example:
            >>> artifacts = await client.objectives.get_artifacts("obj_abc123")
            >>> for a in artifacts:
            ...     print(f"Artifact: {a['name']} ({a['type']})")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/artifacts",
        )
        return response

    # ------------------------------------------------------------------
    # Lifecycle control
    # ------------------------------------------------------------------

    async def pause(self, objective_id: str) -> dict[str, Any]:
        """
        Pause a running objective.

        Args:
            objective_id: Objective ID

        Returns:
            ``{"success": True, "objective_id": ..., "status": "paused"}``

        Example:
            >>> await client.objectives.pause("obj_abc123")
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/pause",
        )
        return response

    async def resume(self, objective_id: str) -> dict[str, Any]:
        """
        Resume a paused objective.

        Args:
            objective_id: Objective ID

        Returns:
            ``{"success": True, "objective_id": ..., "status": "executing"}``
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/resume",
        )
        return response

    async def trigger_execution(self, objective_id: str) -> dict[str, Any]:
        """
        Ask the platform to decompose an objective into tasks.

        Args:
            objective_id: Objective ID

        Returns:
            ``{"status": "processing", ...}`` when decomposition was started,
            or ``{"status": "already_decomposed", "task_count": N, ...}`` when
            the objective already has a task graph. Branch on ``status`` --
            this call is not idempotent in its effect but is safe to repeat.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/trigger-execution",
        )
        return response

    async def implement(
        self,
        objective_id: str,
        confirmed: bool = False,
        additional_instructions: str | None = None,
    ) -> dict[str, Any]:
        """
        Confirm an objective's plan and trigger implementation.

        Args:
            objective_id: Objective ID
            confirmed: Whether the human has confirmed the plan
            additional_instructions: Extra guidance to fold into decomposition

        Returns:
            ``{"success": True, "status": ..., "task_count": N,
            "task_graph_id": ...}``
        """
        body: dict[str, Any] = {"confirmed": confirmed}
        if additional_instructions is not None:
            body["additional_instructions"] = additional_instructions

        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/implement",
            json_data=body,
        )
        return response

    async def retry_node(self, objective_id: str, node_id: str) -> dict[str, Any]:
        """
        Retry one failed node of an objective's task graph.

        Args:
            objective_id: Objective ID
            node_id: Task-graph node ID

        Returns:
            ``{"success": True, "objective_id": ..., "node_id": ...,
            "status": "PENDING"}`` -- the node is reset to pending, not
            re-executed synchronously.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/nodes/{encode_path_param(node_id)}/retry",
        )
        return response

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    async def get_completion_status(self, objective_id: str) -> dict[str, Any]:
        """
        Check whether an objective is ready to be completed.

        Args:
            objective_id: Objective ID

        Returns:
            ``{"success": True, "ready": bool, "blockers": [...],
            "pending_requests": [...], "pending_decisions": [...]}``. Read
            ``ready`` -- ``success`` reports that the CHECK ran, not that the
            objective is completable.
        """
        response: dict[str, Any] = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/completion-status",
        )
        return response

    async def check_completion(self, objective_id: str) -> dict[str, Any]:
        """
        Evaluate completion readiness and complete the objective if it is met.

        Unlike :meth:`get_completion_status`, this is a WRITE: when every
        blocker is clear it transitions the objective.

        Args:
            objective_id: Objective ID

        Returns:
            The outcome. An objective already in a terminal state returns
            ``{"action": "already_complete", ...}`` rather than raising.

        Raises:
            AgenticOSError: On a 409 conflict when the objective is not ready.
                The blockers travel in the ERROR body, not in a success
                response. The SDK maps NO exception subclass to 409, so this
                arrives as the BASE error rather than a conflict-specific
                type; discriminate on ``exc.details["status_code"] == 409``
                and read the blockers from ``exc.details``.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/check-completion",
        )
        return response

    async def complete(
        self,
        objective_id: str,
        final_deliverable_ids: builtins.list[str] | None = None,
        completion_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Complete an objective, naming its final deliverables.

        Args:
            objective_id: Objective ID
            final_deliverable_ids: Deliverables that constitute the result
            completion_notes: Free-text closing notes

        Returns:
            ``success``, ``new_status``, ``final_deliverable_ids``,
            ``notification_ids``, ``audit_anchor_id``, and an
            ``execution_summary`` that is ``None`` when the platform had no
            summary to compute. ``error_message`` is present only on an
            unsuccessful completion.

            Note that ``success`` can be ``False`` in a 200 response -- a
            failed completion is reported in the body, not raised.

        Raises:
            AgenticOSError: On a 409 conflict -- the objective is in a state from which it cannot be completed. The SDK maps NO
                exception subclass to 409, so this arrives as the BASE error
                rather than a conflict-specific type; discriminate on
                ``exc.details["status_code"] == 409``.
        """
        body: dict[str, Any] = {}
        if final_deliverable_ids is not None:
            body["final_deliverable_ids"] = final_deliverable_ids
        if completion_notes is not None:
            body["completion_notes"] = completion_notes

        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/complete",
            json_data=body,
        )
        return response

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    async def get_summary(self, objective_id: str) -> dict[str, Any]:
        """
        Get the execution summary for an objective.

        Args:
            objective_id: Objective ID

        Returns:
            Task counts split by AI and human, elapsed and human time as
            preformatted strings, agent cost as a preformatted currency
            string, critical-issue counts, and the trust verdicts
            ``trust_chain_verified`` / ``within_constraints``.

        Note:
            ``total_time``, ``human_time`` and ``agent_cost`` are rendered
            STRINGS ("2 hours 5 minutes", "$1.40"), not numbers. Do not parse
            them for arithmetic; they are display values and their format is
            not a stable contract.
        """
        response: dict[str, Any] = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/summary",
        )
        return response

    async def get_participants(self, objective_id: str) -> builtins.list[dict[str, Any]]:
        """
        List everyone who contributed to an objective.

        Args:
            objective_id: Objective ID

        Returns:
            One entry per participant with ``id``, ``type`` (owner, agent or
            contributor), ``name``, ``role`` and ``contribution_summary``.

        Note:
            ``contribution_summary`` is backfilled with a generic sentence
            when the platform holds none, so a summary is always present and
            its presence does not indicate a recorded contribution.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/participants",
        )
        return list((response or {}).get("participants", []))

    async def get_templates(self, category: str | None = None) -> builtins.list[dict[str, Any]]:
        """
        List objective templates.

        Args:
            category: Restrict to one template category

        Returns:
            Template records.
        """
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category

        response = await self._http.request(
            "GET",
            "/api/v1/objectives/templates",
            params=params or None,
        )
        return list((response or {}).get("records", []))

    async def download_artifacts(self, objective_id: str) -> bytes:
        """
        Download every artifact attached to an objective, as a zip archive.

        Args:
            objective_id: Objective ID

        Returns:
            The raw bytes of a zip archive. This route answers with binary
            content, not JSON, so the return value is ``bytes`` -- write it to
            a file or open it with :mod:`zipfile`.

        Example:
            >>> archive = await client.objectives.download_artifacts("obj_abc123")
            >>> import io, zipfile
            >>> with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            ...     names = bundle.namelist()
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/download",
        )
        return response if isinstance(response, bytes) else bytes(response or b"")

    # ------------------------------------------------------------------
    # Administrative
    # ------------------------------------------------------------------

    async def set_status(
        self,
        objective_id: str,
        status: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Set an objective's status directly.

        This is an ADMINISTRATIVE override: it moves the objective without
        running the lifecycle transition the ordinary routes run. Prefer
        :meth:`pause`, :meth:`resume`, :meth:`complete` or :meth:`cancel`
        where one of them expresses the intent.

        Args:
            objective_id: Objective ID
            status: New status
            reason: Why the override was made

        Returns:
            ``{"success": True, "objective_id": ..., "previous_status": ...,
            "status": ...}``
        """
        body: dict[str, Any] = {"status": status}
        if reason is not None:
            body["reason"] = reason

        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/admin-status",
            json_data=body,
        )
        return response

    async def create_tasks(
        self,
        objective_id: str,
        tasks: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Create task-graph nodes on an objective in bulk.

        This is an ADMINISTRATIVE route: it writes nodes directly rather than
        letting decomposition produce them.

        Args:
            objective_id: Objective ID
            tasks: Task definitions to create

        Returns:
            ``{"success": True, "objective_id": ..., "tasks_created": N,
            "graph_nodes": [...]}``. ``tasks_created`` counts what was
            actually written and may be smaller than ``len(tasks)``.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/admin-tasks",
            json_data={"tasks": tasks},
        )
        return response
