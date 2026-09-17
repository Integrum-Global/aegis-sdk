"""
Work-Objectives Module for Agentic OS SDK.

Provides objective execution-lifecycle actions (confirm-implementation,
decide, progress, clarify, task-graph, recent), work-unit CRUD + execution,
work-session creation/initialization, leadership directives, change
requests, pool-based escalation config, and mid-execution interventions.

Self-contained module: local Pydantic models, no shared
imports from client.py / modules/__init__.py / types.py. Every route below is
verified against the deployed API:

⛔ AUTHENTICATION IS MIXED ACROSS THIS MODULE, prefix by prefix. An API-key
principal is synthesised with no role and an empty persona list -- the
platform's deliberate fail-closed default -- so a route gated on an operator
PERSONA denies it. The gates compose as a CONJUNCTION, so a route carrying
both a key-aware scope check and a plain persona check still denies the key.

    /api/v1/objectives/**       reachable with an API key holding an `agents` scope
    /api/v1/sessions/**         PERSONA ONLY -- 403 for an API key
    /api/v1/interventions/**    PERSONA ONLY -- 403 for an API key
    /api/v1/work-units/**       reachable with an API key
    /api/v1/directives/**       reachable with an API key
    /api/v1/change-requests/**  reachable with an API key

So on this module the objective, work-unit, directive and change-request methods
work for a client built with ``api_key=``, and the session and intervention
methods do not. For those, authenticate with a session token instead --
``await client.auth.login(...)`` then ``client.set_auth_token(...)``.

The objective prefix admits a key holding ANY ``agents`` scope. That gate is a
COARSE router-level pre-filter, and the read-versus-write boundary is enforced by
the per-route check behind it. A key holding no ``agents`` scope is refused with
403, and the refusal names the scopes that would have admitted it. THREE objective
routes are the exception and stay human-only -- ``GET /objectives``,
``/objectives/{id}/admin-status`` and ``/objectives/{id}/admin-tasks`` -- because
their persona gates ("executive or admin", "admin or architect") have no API-key
scope analogue. The list route is the one to watch: it is the only read on this
prefix a key cannot reach.

This is a platform-side gap rather than a client limitation, and it is
reported as such. It is written down here because a method that always 403s
for the credential most consumers hold is worse than an absent one unless it
says why.

Objectives (prefix ``/api/v1``):

    POST /api/v1/objectives/{id}/confirm-implementation -> confirm_implementation()
    POST /api/v1/objectives/{id}/decide                 -> decide()
    GET  /api/v1/objectives/{id}/progress               -> get_progress()
    GET  /api/v1/objectives/{id}/progress/stream (SSE)  -> stream_progress()
    GET  /api/v1/objectives/recent                      -> get_recent_objectives()
    POST /api/v1/objectives/{id}/clarify                -> clarify()
    GET  /api/v1/objectives/{id}/task-graph             -> get_task_graph()

Work units (prefix ``/api/v1/work-units``):

    GET    /api/v1/work-units                        -> list_work_units()
    POST   /api/v1/work-units                        -> create_work_unit()
    GET    /api/v1/work-units/{id}                   -> get_work_unit()
    PUT    /api/v1/work-units/{id}                   -> update_work_unit()
    DELETE /api/v1/work-units/{id}                   -> delete_work_unit()
    POST   /api/v1/work-units/{id}/run                -> run_work_unit()
    POST   /api/v1/work-units/{id}/execute            -> execute_work_unit()
    POST   /api/v1/work-units/{id}/execute/cancel     -> cancel_work_unit_execution()
    GET    /api/v1/work-units/{id}/execution-config   -> get_execution_config()
    PATCH  /api/v1/work-units/{id}/execution-config   -> update_execution_config()

Sessions (prefix ``/api/v1``):

    POST /api/v1/sessions/from-task        -> create_session_from_task()
    POST /api/v1/sessions/initialize-agent -> initialize_agent()
    GET  /api/v1/sessions/my               -> get_my_sessions()
    GET  /api/v1/sessions                  -> list_sessions()

Directives (prefix ``/api/v1/directives``):

    GET    /api/v1/directives                        -> list_directives()
    POST   /api/v1/directives                        -> create_directive()
    GET    /api/v1/directives/{id}                   -> get_directive()
    PUT    /api/v1/directives/{id}                   -> update_directive()
    DELETE /api/v1/directives/{id}                   -> delete_directive()
    POST   /api/v1/directives/{id}/publish           -> publish_directive()
    POST   /api/v1/directives/{id}/acknowledge       -> acknowledge_directive()
    GET    /api/v1/directives/{id}/acknowledgments   -> get_acknowledgment_status()
    POST   /api/v1/directives/{id}/expire            -> expire_directive()
    POST   /api/v1/directives/{id}/supersede         -> supersede_directive()
    POST   /api/v1/directives/{id}/revoke            -> revoke_directive()
    POST   /api/v1/directives/{id}/batch-acknowledge -> batch_acknowledge_directive()

Change requests (prefix
``/api/v1/change-requests``):

    GET   /api/v1/change-requests                        -> list_change_requests()
    POST  /api/v1/change-requests                        -> create_change_request()
    GET   /api/v1/change-requests/{id}                    -> get_change_request()
    PATCH /api/v1/change-requests/{id}/submit             -> submit_change_request()
    PATCH /api/v1/change-requests/{id}/approve            -> approve_change_request()
    PATCH /api/v1/change-requests/{id}/deny               -> deny_change_request()
    PATCH /api/v1/change-requests/{id}/counter-propose    -> counter_propose_change_request()
    PATCH /api/v1/change-requests/{id}/accept-counter     -> accept_counter_change_request()
    PATCH /api/v1/change-requests/{id}/apply              -> apply_change_request()

Escalation (prefix ``/api/v1/escalation``
— served through ``nexus_bridge.build_escalation_bridge`` since the
Nexus cutover deleted the FastAPI router; the wire paths are unchanged):

    GET  /api/v1/escalation/config/{pool_id} -> get_escalation_config()
    PUT  /api/v1/escalation/config/{pool_id} -> update_escalation_config()
    GET  /api/v1/escalation/pending          -> list_pending_escalations()
    POST /api/v1/escalation/tasks/{id}/escalate    -> manual_escalate_task()
    POST /api/v1/escalation/tasks/{id}/acknowledge -> acknowledge_escalation()
    GET  /api/v1/escalation/stats            -> get_escalation_stats()

Interventions (prefix
``/api/v1/interventions``):

    POST /api/v1/interventions/{session_id}/pause               -> pause_session()
    POST /api/v1/interventions/{session_id}/resume               -> resume_session()
    POST /api/v1/interventions/{session_id}/tighten-constraints -> tighten_constraints()
    POST /api/v1/interventions/{session_id}/fence               -> fence_session()
    GET  /api/v1/interventions/sessions                         -> list_intervention_sessions()
    GET  /api/v1/interventions/{session_id}                     -> get_intervention_session_state()
    GET  /api/v1/interventions/{session_id}/history             -> get_intervention_history()

Agent escalations (prefix
``/api/v1/agent-escalations`` — smart escalation queue,):

    GET  /api/v1/agent-escalations/pending             -> list_agent_escalations()
    GET  /api/v1/agent-escalations/stream (SSE)        -> stream_agent_escalations()
    GET  /api/v1/agent-escalations/{id}                -> get_agent_escalation()
    POST /api/v1/agent-escalations/{id}/resolve        -> resolve_agent_escalation()
    POST /api/v1/agent-escalations/{id}/cancel         -> cancel_agent_escalation()

NOT implemented here (grep-verified as absent or out of the P0/P1 scope for
this module):

- Leadership inbox / review queue — P2 rows in the manifest, out of scope.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


# ===========================================================================
# Objectives
# ===========================================================================


class ObjectiveRecentItem(BaseModel):
    """One row of ``GET /objectives/recent``.

    Built inline by the handler as a plain dict (no server-side
    ``BaseModel`` pins the per-record shape) — ``extra="allow"`` keeps this
    forward-compatible
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None
    title: str | None = None
    description: str | None = None
    priority: str = "medium"
    status: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    progress_percent: int = 0
    total_cost_usd_cents: int = 0
    total_tokens_used: int = 0
    started_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ObjectiveRecentList(BaseModel):
    """Response for ``GET /objectives/recent`` (``ObjectiveListResponse``)."""

    records: list[ObjectiveRecentItem]


class WorkObjectivesModule:
    """
    Work-objective execution lifecycle, work units, sessions, directives,
    change requests, escalation, and interventions.

    Example:
        >>> result = await client.work_objectives.confirm_implementation("obj_123")
        >>> print(result["status"])  # "executing"
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    async def confirm_implementation(self, objective_id: str) -> dict[str, Any]:
        """
        Confirm an objective's implementation plan and launch agent execution.

        Verified route: ``POST /api/v1/objectives/{objective_id}/confirm-implementation``. No request body. Transitions
        ``plan_review``/``confirmed`` -> ``executing`` and launches execution
        as a background task.

        Returns:
            ``{"success": bool, "objective_id": str, "status": "executing"}``
        """
        result: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/objectives/{encode_path_param(objective_id)}/confirm-implementation"
        )
        return result

    async def decide(
        self,
        objective_id: str,
        decision_id: str,
        selected_option_id: str,
        justification: str | None = None,
        additional_notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Submit the human decision at an objective's decision phase.

        Verified route: ``POST /api/v1/objectives/{objective_id}/decide``
        with ``DecisionBody``.
        The objective must be in ``"decision"`` status; the resolved action
        (proceed/reject/revise/more_analysis) determines the response shape,
        so this returns the raw dict.

        Returns:
            Raw dict — always ``status``, ``objective_id``, ``decision_id``,
            ``action_type``; ``"proceed"`` additionally includes
            ``completion_summary``.
        """
        json_data: dict[str, Any] = {
            "decision_id": decision_id,
            "selected_option_id": selected_option_id,
        }
        if justification is not None:
            json_data["justification"] = justification
        if additional_notes is not None:
            json_data["additional_notes"] = additional_notes

        result: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/decide",
            json_data=json_data,
        )
        return result

    async def get_progress(self, objective_id: str) -> dict[str, Any]:
        """
        Get the current execution progress for an objective.

        Verified route: ``GET /api/v1/objectives/{objective_id}/progress``. Rich, task-graph-derived
        progress report with no fixed ``response_model`` server-side, so
        this returns the raw dict.

        Returns:
            Raw dict — keys include ``status``, ``overall_progress``,
            ``steps``, ``graph_nodes``, ``elapsed_ms``,
            ``estimated_remaining_ms``, ``cost``, ``constraint_dimensions``.
        """
        result: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/objectives/{encode_path_param(objective_id)}/progress"
        )
        return result

    async def stream_progress(
        self, objective_id: str, token: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        SSE stream of execution progress events for an objective.

        Verified route: ``GET /api/v1/objectives/{objective_id}/progress/stream``
        (mounted on ``sse_router``).
        EventSource cannot send Authorization headers, so this route
        authenticates via a ``?token=`` query parameter only
        (``_get_user_from_token_param``) — it does NOT
        fall back to the bearer header the rest of the SDK uses. Defaults to
        the HTTP client's configured API key when ``token`` is omitted.

        Yields:
            Event dicts: ``execution_started``, ``step_started``,
            ``step_completed``, ``progress_update``, ``execution_completed``,
            ``execution_error``, ``heartbeat``.
        """
        auth_token = token if token is not None else getattr(self._http, "_api_key", None)
        params = {"token": auth_token} if auth_token else None
        async for event in self._http.stream(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/progress/stream",
            params=params,
        ):
            yield event

    async def get_recent_objectives(self, limit: int = 10) -> ObjectiveRecentList:
        """
        Get recent objectives for the current user (Work Home landing feed).

        Verified route: ``GET /api/v1/objectives/recent``.

        Args:
            limit: Maximum results (1-100)

        Returns:
            ObjectiveRecentList: records ordered most-recent-first
        """
        response = await self._http.request(
            "GET", "/api/v1/objectives/recent", params={"limit": limit}
        )
        return ObjectiveRecentList(**response)

    async def clarify(
        self,
        objective_id: str,
        clarification_session_id: str,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        """
        Submit answers to AI clarification questions during objective intake.

        Verified route: ``POST /api/v1/objectives/{objective_id}/clarify``
        with ``ClarificationResponseBody``. Triggers task decomposition as a background task.

        Args:
            objective_id: Objective ID
            clarification_session_id: The clarification session being answered
            answers: ``{question_id: answer_text}``

        Returns:
            ``{"status": "processing", "message": str}``
        """
        result: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/clarify",
            json_data={
                "clarification_session_id": clarification_session_id,
                "answers": answers,
            },
        )
        return result

    async def trigger_clarification(
        self,
        objective_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Ask the platform to generate clarification questions for an objective.

        Generation is ASYNCHRONOUS. This returns as soon as the work is
        queued, so the questions are not in the response -- poll
        :meth:`get_clarification_status` or watch the progress stream.

        Args:
            objective_id: Objective ID
            request_id: Optional request to scope the questions to

        Returns:
            ``{"status": "triggered", "message": str, "request_id": ...}``.
            ``"triggered"`` means QUEUED, not generated.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/clarify/trigger",
            json_data={"request_id": request_id},
        )
        return response

    async def get_clarification_status(self, objective_id: str) -> dict[str, Any]:
        """
        Get the state of an objective's clarification session.

        Args:
            objective_id: Objective ID

        Returns:
            ``objective_id``, ``status``, ``questions``, ``responses``,
            ``understanding``, ``started_at`` and ``completed_at``.

            ``status`` is the field to branch on. ``"generating"`` means
            questions are still being produced and ``questions`` is
            legitimately empty. ``"failed"`` means generation did not finish;
            an explanatory ``message`` is present only in that case, and
            ``questions`` is empty for a reason that is NOT "no clarification
            needed". ``completed_at`` is populated only once the session has
            completed.

        Example:
            >>> state = await client.work_objectives.get_clarification_status("obj_abc")
            >>> if state["status"] == "generating":
            ...     pass  # not ready; empty questions here mean "not yet"
        """
        response: dict[str, Any] = await self._http.request(
            "GET",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/clarification-status",
        )
        return response

    async def respond_to_clarification(
        self,
        objective_id: str,
        responses: dict[str, str],
    ) -> dict[str, Any]:
        """
        Answer clarification questions by question ID.

        Distinct from :meth:`clarify`, which addresses the intake route and
        takes an explicit clarification-session ID. This one is keyed on the
        objective and takes a plain question-to-answer map.

        Args:
            objective_id: Objective ID
            responses: ``{question_id: answer_text}``

        Returns:
            The refreshed clarification state, in the same shape
            :meth:`get_clarification_status` returns.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/clarify/respond",
            json_data={"responses": responses},
        )
        return response

    async def respond_to_clarification_freeform(
        self,
        objective_id: str,
        response: str,
    ) -> dict[str, Any]:
        """
        Answer clarification conversationally, in one block of free text.

        Args:
            objective_id: Objective ID
            response: The free-form answer. Must be non-empty.

        Returns:
            ``{"success": True, "objective_id": ..., "status": "completed",
            "message": ...}``.

        Note:
            Accepting a freeform response TRIGGERS DECOMPOSITION. It is not
            merely recording an answer -- it closes clarification and starts
            the next stage of work.
        """
        # Bound to `result`, NOT `response`: `response` is this method's own
        # public keyword argument. Rebinding it worked only because Python
        # evaluates the call's arguments before the assignment lands, so the
        # free-text answer reached the wire by a hair's breadth -- and every
        # reader after the assignment saw a name whose declared type was `str`
        # and whose value was a dict. The parameter name is API surface and is
        # deliberately unchanged; the local is what moves.
        result: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/clarify/respond-freeform",
            json_data={"response": response},
        )
        return result

    async def get_task_graph(self, objective_id: str) -> dict[str, Any]:
        """
        Get the task decomposition graph for an objective.

        Verified route: ``GET /api/v1/objectives/{objective_id}/task-graph``. No fixed
        ``response_model`` server-side, so this returns the raw dict.

        Returns:
            Raw dict — ``objective_id``, ``nodes``, ``edges``, ``progress``,
            ``estimated_total_minutes``, ``estimated_total_cost``.
        """
        result: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/objectives/{encode_path_param(objective_id)}/task-graph"
        )
        return result

    # =======================================================================
    # Work Units
    # =======================================================================

    async def list_work_units(
        self,
        search: str | None = None,
        work_unit_type: Literal["atomic", "composite", "all"] | None = None,
        trust_status: str | None = None,
        workspace_id: str | None = None,
        tags: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> WorkUnitListResponse:
        """
        List work units (unified agent/pipeline registry).

        Verified route: ``GET /api/v1/work-units``. Combines agents (atomic) and pipelines
        (composite) into one paginated list.

        Args:
            search: Name substring search (case-insensitive, Python-side)
            work_unit_type: "atomic", "composite", or "all"
            trust_status: Filter by trust status
            workspace_id: Filter by workspace
            tags: Comma-separated tag filter
            page: 1-based page number
            page_size: Items per page (1-100)

        Returns:
            WorkUnitListResponse: items + total + page + pageSize + hasMore
        """
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if search:
            params["search"] = search
        if work_unit_type:
            params["type"] = work_unit_type
        if trust_status:
            params["trustStatus"] = trust_status
        if workspace_id:
            params["workspaceId"] = workspace_id
        if tags:
            params["tags"] = tags

        response = await self._http.request("GET", "/api/v1/work-units", params=params)
        return WorkUnitListResponse(**response)

    async def create_work_unit(
        self,
        name: str,
        work_unit_type: Literal["atomic", "composite"],
        description: str = "",
        capabilities: list[dict[str, Any]] | None = None,
        workspace_id: str | None = None,
        workspace_ids: list[str] | None = None,
        new_workspace: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        sub_unit_ids: list[str] | None = None,
        agent_config: dict[str, Any] | None = None,
        trust_setup: dict[str, Any] | None = None,
    ) -> WorkUnit:
        """
        Create a work unit (agent if ``work_unit_type="atomic"``, pipeline
        if ``"composite"``).

        Verified route: ``POST /api/v1/work-units`` with
        ``CreateWorkUnitRequest``. Nested request shapes (``agent_config`` ->
        ``AgentConfigRequest``, ``new_workspace`` -> ``NewWorkspaceInput``,
        ``trust_setup`` -> ``TrustSetupInput``) are passed through as plain
        dicts using the server's exact camelCase field names.

        Args:
            name: Work unit name (1-100 chars)
            work_unit_type: "atomic" or "composite"
            description: Description (max 2000 chars)
            capabilities: List of ``{name, description, keywords}`` dicts
            workspace_id: Legacy single workspace ID
            workspace_ids: Multiple workspace IDs
            new_workspace: Inline workspace creation —
                ``{"name": str, "color": str}``
            tags: Tag list
            sub_unit_ids: Composite sub-unit IDs
            agent_config: Atomic agent config — see ``AgentConfigRequest``
                camelCase fields (provider, agentType, modelId, systemPrompt,
                temperature, maxTokens, unitType, agentSubtype, a2aEnabled,
                capabilities, tools, orchestrationConfig)
            trust_setup: ``{"mode": "skip"|"establish"|"delegate",
                "delegateeId": str, "expirationDays": int}``

        Returns:
            WorkUnit: Created work unit
        """
        json_data: dict[str, Any] = {
            "name": name,
            "type": work_unit_type,
            "description": description,
            "capabilities": capabilities or [],
            "workspaceIds": workspace_ids or [],
            "tags": tags or [],
            "subUnitIds": sub_unit_ids or [],
        }
        if workspace_id is not None:
            json_data["workspaceId"] = workspace_id
        if new_workspace is not None:
            json_data["newWorkspace"] = new_workspace
        if agent_config is not None:
            json_data["agentConfig"] = agent_config
        if trust_setup is not None:
            json_data["trustSetup"] = trust_setup

        response = await self._http.request("POST", "/api/v1/work-units", json_data=json_data)
        return WorkUnit(**response)

    async def get_work_unit(self, work_unit_id: str) -> WorkUnit:
        """
        Get a work unit by ID.

        Verified route: ``GET /api/v1/work-units/{work_unit_id}``.
        """
        response = await self._http.request(
            "GET", f"/api/v1/work-units/{encode_path_param(work_unit_id)}"
        )
        return WorkUnit(**response)

    async def update_work_unit(self, work_unit_id: str, **fields: Any) -> WorkUnit:
        """
        Update a work unit.

        Verified route: ``PUT /api/v1/work-units/{work_unit_id}`` with
        ``UpdateWorkUnitRequest``.

        Args:
            work_unit_id: Work unit ID
            **fields: Any of ``name``, ``description``, ``capabilities``,
                ``workspaceId``, ``tags``

        Returns:
            WorkUnit: Updated work unit
        """
        response = await self._http.request(
            "PUT", f"/api/v1/work-units/{encode_path_param(work_unit_id)}", json_data=fields
        )
        return WorkUnit(**response)

    async def delete_work_unit(self, work_unit_id: str) -> dict[str, Any]:
        """
        Archive (soft-delete) a work unit.

        Verified route: ``DELETE /api/v1/work-units/{work_unit_id}``.

        Returns:
            ``{"message": str}``
        """
        result: dict[str, Any] = await self._http.request(
            "DELETE", f"/api/v1/work-units/{encode_path_param(work_unit_id)}"
        )
        return result

    async def run_work_unit(
        self, work_unit_id: str, inputs: dict[str, Any] | None = None
    ) -> RunResult:
        """
        Execute a work unit synchronously and return the run result.

        Verified route: ``POST /api/v1/work-units/{work_unit_id}/run`` with
        ``RunWorkUnitRequest``.

        Args:
            work_unit_id: Work unit ID
            inputs: Input parameters for the run

        Returns:
            RunResult: id, status, startedAt, completedAt, input, output, error
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/run",
            json_data={"inputs": inputs or {}},
        )
        return RunResult(**response)

    async def execute_work_unit(
        self,
        work_unit_id: str,
        message: str,
        session_id: str | None = None,
        override_config: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        Execute a work unit using the Kaizen v1.0.0 Unified Agent API.

        Verified route: ``POST /api/v1/work-units/{work_unit_id}/execute``
        with ``ExecuteWithAgentRequest`` (1599-1665``). Note: unlike most other work-unit request
        bodies, this endpoint uses snake_case field names.

        Args:
            work_unit_id: Work unit ID
            message: Input message for the agent
            session_id: Optional session ID for multi-turn continuity
            override_config: Optional per-call config overrides

        Returns:
            ExecutionResult: run_id, output, status, cost_usd, cycles_used,
            tokens_used
        """
        json_data: dict[str, Any] = {"message": message}
        if session_id is not None:
            json_data["session_id"] = session_id
        if override_config is not None:
            json_data["override_config"] = override_config

        response = await self._http.request(
            "POST",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/execute",
            json_data=json_data,
        )
        return ExecutionResult(**response)

    async def cancel_work_unit_execution(self, work_unit_id: str, run_id: str) -> dict[str, Any]:
        """
        Cancel an in-progress work-unit execution.

        Verified route: ``POST /api/v1/work-units/{work_unit_id}/execute/cancel``
        with ``run_id`` as a QUERY PARAMETER. Only works for autonomous executions still running.

        Returns:
            ``{"message": str}``
        """
        result: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/execute/cancel",
            params={"run_id": run_id},
        )
        return result

    async def get_execution_config(self, work_unit_id: str) -> ExecutionConfig:
        """
        Get the Kaizen agent execution configuration for a work unit.

        Verified route: ``GET /api/v1/work-units/{work_unit_id}/execution-config``.
        """
        response = await self._http.request(
            "GET", f"/api/v1/work-units/{encode_path_param(work_unit_id)}/execution-config"
        )
        return ExecutionConfig(**response)

    async def update_execution_config(self, work_unit_id: str, **fields: Any) -> ExecutionConfig:
        """
        Update the Kaizen agent execution configuration for a work unit.

        Verified route: ``PATCH /api/v1/work-units/{work_unit_id}/execution-config``
        with ``AgentExecutionConfigRequest`` (1515-1592``).

        Args:
            work_unit_id: Work unit ID
            **fields: Any of ``runtime``, ``model``, ``execution_mode``,
                ``temperature``, ``max_tokens``, ``max_cycles``,
                ``budget_limit_usd``, ``timeout_seconds``, ``memory_depth``,
                ``tool_access``, ``allowed_tools``, ``llm_routing``,
                ``checkpoint_frequency``, ``enable_checkpointing``

        Returns:
            ExecutionConfig: Updated configuration
        """
        response = await self._http.request(
            "PATCH",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/execution-config",
            json_data=fields,
        )
        return ExecutionConfig(**response)

    # =======================================================================
    # Sessions
    # =======================================================================

    # =======================================================================
    # Work unit availability, run history, and configuration versions
    # =======================================================================

    async def list_available_work_units(self) -> list[WorkUnit]:
        """
        List work units the caller may actually run.

        Distinct from :meth:`list_work_units`, which enumerates what EXISTS.
        This returns the runnable view: active agents and active pipelines the
        caller has been delegated access to, projected into the work-unit
        shape.

        Returns:
            Runnable work units.

        Note:
            The platform composes this from a bounded page of agents and a
            bounded page of pipelines, so a large organization may see a
            partial list with no marker saying so. It takes no pagination
            arguments, so there is no way to ask for the rest.
        """
        response = await self._http.request("GET", "/api/v1/work-units/available")
        return [WorkUnit(**item) for item in response or []]

    async def list_work_unit_runs(self, work_unit_id: str, limit: int = 10) -> list[RunResult]:
        """
        List recent runs of a work unit.

        Args:
            work_unit_id: Work unit ID
            limit: Maximum runs to return, 1-100

        Returns:
            Run records, each with status, timings, input, output and error.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/runs",
            params={"limit": limit},
        )
        return [RunResult(**item) for item in response or []]

    async def list_work_unit_versions(
        self,
        work_unit_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> VersionList:
        """
        List a work unit's configuration versions.

        Args:
            work_unit_id: Work unit ID
            limit: Maximum versions to return, 1-1000
            offset: Pagination offset

        Returns:
            The versions, the total count, and ``currentVersion`` -- the
            version number currently in force.
        """
        params: dict[str, Any] = {"offset": offset}
        if limit is not None:
            params["limit"] = limit
        response = await self._http.request(
            "GET",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/versions",
            params=params,
        )
        return VersionList(**response)

    async def create_work_unit_version(
        self,
        work_unit_id: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> ConfigVersion:
        """
        Snapshot a work unit's CURRENT configuration as a new version.

        Args:
            work_unit_id: Work unit ID
            description: Why this snapshot was taken
            tags: Free-form tags

        Returns:
            The new version.

        Note:
            This captures the configuration as it stands now; it does not
            accept a configuration to store. Change the work unit first, then
            snapshot it.
        """
        body: dict[str, Any] = {}
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        response = await self._http.request(
            "POST",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/versions",
            json_data=body,
        )
        return ConfigVersion(**response)

    async def get_work_unit_version(self, work_unit_id: str, version_id: str) -> ConfigVersion:
        """
        Get one configuration version.

        Args:
            work_unit_id: Work unit ID
            version_id: Version ID

        Returns:
            The version snapshot, including the full stored config.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/versions/{encode_path_param(version_id)}",
        )
        return ConfigVersion(**response)

    async def compare_work_unit_versions(
        self,
        work_unit_id: str,
        from_version: str,
        to_version: str,
    ) -> VersionComparison:
        """
        Diff two configuration versions field by field.

        Args:
            work_unit_id: Work unit ID
            from_version: The baseline version
            to_version: The version compared against it

        Returns:
            Both snapshots and the list of field-level changes.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/versions/compare",
            params={"from": from_version, "to": to_version},
        )
        return VersionComparison(**response)

    async def restore_work_unit_version(
        self,
        work_unit_id: str,
        version_id: str,
        create_backup: bool | None = None,
        description: str | None = None,
    ) -> ConfigVersion:
        """
        Restore a work unit to an earlier configuration version.

        Args:
            work_unit_id: Work unit ID
            version_id: The version to restore
            create_backup: Whether to snapshot the CURRENT configuration
                before overwriting it. Leaving this unset takes the platform's
                default rather than asserting one -- pass ``True`` explicitly
                when the pre-restore state must be recoverable.
            description: Description for the restore

        Returns:
            The configuration now in force.
        """
        body: dict[str, Any] = {}
        if create_backup is not None:
            body["createBackup"] = create_backup
        if description is not None:
            body["description"] = description
        response = await self._http.request(
            "POST",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/versions/{encode_path_param(version_id)}/restore",
            json_data=body or None,
        )
        return ConfigVersion(**response)

    async def delete_work_unit_version(self, work_unit_id: str, version_id: str) -> None:
        """
        Delete a configuration version.

        Args:
            work_unit_id: Work unit ID
            version_id: Version ID

        Returns:
            ``None``. The platform answers with no content.
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/work-units/{encode_path_param(work_unit_id)}/versions/{encode_path_param(version_id)}",
        )

    async def create_session_from_task(self, request_id: str) -> dict[str, Any]:
        """
        Create (or return an existing) work session linked to a task/request.

        Verified route: ``POST /api/v1/sessions/from-task`` — ``request_id``
        is a QUERY PARAMETER. The
        "Work on Task" flow: pre-loads the session with task context.

        Returns:
            ``{"session_id": str, "task_context": {request_id, task_title,
            task_description, objective_id, objective_title,
            parent_request_id, parent_chain}}``
        """
        result: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/sessions/from-task", params={"request_id": request_id}
        )
        return result

    async def initialize_agent(
        self,
        session_id: str,
        agent_id: str | None = None,
        trust_chain_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Initialize an agent instance for a work session.

        Verified route: ``POST /api/v1/sessions/initialize-agent`` with
        ``InitializeAgentBody``. The response wire shape is camelCase
        (``InitializeAgentResponse``, locked by an automated envelope-shape
        check on the platform side), so this returns the raw dict rather
        than inventing a parallel local model.

        Args:
            session_id: Session to initialize the agent instance for
            agent_id: Optional agent ID (server resolves from session/request
                context when omitted)
            trust_chain_id: Optional trust chain ID to bind

        Returns:
            Raw dict — ``instanceId``, ``state``, ``agentId``,
            ``systemPrompt``, ``subagents``, ``context``, ``metrics``.
        """
        json_data: dict[str, Any] = {"session_id": session_id}
        if agent_id is not None:
            json_data["agent_id"] = agent_id
        if trust_chain_id is not None:
            json_data["trust_chain_id"] = trust_chain_id

        result: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/sessions/initialize-agent", json_data=json_data
        )
        return result

    async def get_my_sessions(
        self, page_size: int = 10, sort: str = "-created_at"
    ) -> dict[str, Any]:
        """
        Get the current user's recent work sessions.

        Verified route: ``GET /api/v1/sessions/my``.

        Returns:
            ``{"records": [...], "total": int}``
        """
        result: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/sessions/my", params={"page_size": page_size, "sort": sort}
        )
        return result

    async def list_sessions(
        self,
        status: str | None = None,
        workspace_id: str | None = None,
        objective_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        List sessions with optional filters (caller sees only their own).

        Verified route: ``GET /api/v1/sessions``.

        Returns:
            ``{"records": [...], "total": int, "page": int, "page_size": int}``
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if workspace_id:
            params["workspace_id"] = workspace_id
        if objective_id:
            params["objective_id"] = objective_id
        if search:
            params["search"] = search

        result: dict[str, Any] = await self._http.request("GET", "/api/v1/sessions", params=params)
        return result

    # =======================================================================
    # Directives
    # =======================================================================

    async def list_directives(
        self,
        target_unit_id: str | None = None,
        directive_type: str | None = None,
        priority: str | None = None,
        issuing_unit_id: str | None = None,
        status: str | None = None,
        include_expired: bool = False,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DirectiveList:
        """
        List leadership directives in the current org.

        Verified route: ``GET /api/v1/directives``.

        Returns:
            DirectiveList: records + total
        """
        params: dict[str, Any] = {
            "include_expired": include_expired,
            "limit": limit,
            "offset": offset,
        }
        if target_unit_id:
            params["target_unit_id"] = target_unit_id
        if directive_type:
            params["directive_type"] = directive_type
        if priority:
            params["priority"] = priority
        if issuing_unit_id:
            params["issuing_unit_id"] = issuing_unit_id
        if status:
            params["status"] = status
        if search:
            params["search"] = search

        response = await self._http.request("GET", "/api/v1/directives", params=params)
        return DirectiveList(**response)

    async def create_directive(
        self,
        title: str,
        content_markdown: str,
        directive_type: Literal["strategic", "operational", "policy_update", "announcement"],
        issuing_unit_id: str,
        effective_from: str,
        issuing_role_id: str | None = None,
        reference_number: str | None = None,
        summary: str | None = None,
        priority: Literal["critical", "high", "normal", "low"] = "normal",
        target_units: list[str] | None = None,
        target_all_units: bool = False,
        effective_until: str | None = None,
        acknowledgment_required: bool = True,
        acknowledgment_deadline: str | None = None,
        related_knowledge_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Directive:
        """
        Create a new leadership directive.

        Verified route: ``POST /api/v1/directives`` with
        ``CreateDirectiveRequest``. Only org_owner/org_admin may create.

        Returns:
            Directive: Created directive
        """
        json_data: dict[str, Any] = {
            "title": title,
            "content_markdown": content_markdown,
            "directive_type": directive_type,
            "issuing_unit_id": issuing_unit_id,
            "effective_from": effective_from,
            "priority": priority,
            "target_all_units": target_all_units,
            "acknowledgment_required": acknowledgment_required,
        }
        if issuing_role_id is not None:
            json_data["issuing_role_id"] = issuing_role_id
        if reference_number is not None:
            json_data["reference_number"] = reference_number
        if summary is not None:
            json_data["summary"] = summary
        if target_units is not None:
            json_data["target_units"] = target_units
        if effective_until is not None:
            json_data["effective_until"] = effective_until
        if acknowledgment_deadline is not None:
            json_data["acknowledgment_deadline"] = acknowledgment_deadline
        if related_knowledge_ids is not None:
            json_data["related_knowledge_ids"] = related_knowledge_ids
        if metadata is not None:
            json_data["metadata"] = metadata
        if tags is not None:
            json_data["tags"] = tags

        response = await self._http.request("POST", "/api/v1/directives", json_data=json_data)
        return Directive(**response)

    async def get_directive(self, directive_id: str) -> Directive:
        """
        Get a directive by ID.

        Verified route: ``GET /api/v1/directives/{directive_id}``.
        """
        response = await self._http.request(
            "GET", f"/api/v1/directives/{encode_path_param(directive_id)}"
        )
        return Directive(**response)

    async def update_directive(self, directive_id: str, **fields: Any) -> Directive:
        """
        Update a directive. Only org_owner/org_admin may update.

        Verified route: ``PUT /api/v1/directives/{directive_id}`` with
        ``UpdateDirectiveRequest``.

        Args:
            directive_id: Directive ID
            **fields: Any of ``title``, ``content_markdown``,
                ``directive_type``, ``reference_number``, ``summary``,
                ``priority``, ``target_units``, ``target_all_units``,
                ``effective_from``, ``effective_until``,
                ``acknowledgment_required``, ``acknowledgment_deadline``,
                ``related_knowledge_ids``, ``metadata``, ``tags``, ``status``
        """
        response = await self._http.request(
            "PUT", f"/api/v1/directives/{encode_path_param(directive_id)}", json_data=fields
        )
        return Directive(**response)

    async def delete_directive(self, directive_id: str, hard: bool = False) -> dict[str, Any]:
        """
        Delete a directive. Default is soft-delete (revoke).

        Verified route: ``DELETE /api/v1/directives/{directive_id}``.

        Returns:
            ``{"message": str}``
        """
        result: dict[str, Any] = await self._http.request(
            "DELETE", f"/api/v1/directives/{encode_path_param(directive_id)}", params={"hard": hard}
        )
        return result

    async def publish_directive(self, directive_id: str) -> Directive:
        """
        Publish a directive (draft -> active).

        Verified route: ``POST /api/v1/directives/{directive_id}/publish``.
        """
        response = await self._http.request(
            "POST", f"/api/v1/directives/{encode_path_param(directive_id)}/publish"
        )
        return Directive(**response)

    async def acknowledge_directive(self, directive_id: str, notes: str | None = None) -> Directive:
        """
        Acknowledge a directive (any org user).

        Verified route: ``POST /api/v1/directives/{directive_id}/acknowledge``
        with ``AcknowledgeRequest``.
        """
        json_data = {"notes": notes} if notes is not None else None
        response = await self._http.request(
            "POST",
            f"/api/v1/directives/{encode_path_param(directive_id)}/acknowledge",
            json_data=json_data,
        )
        return Directive(**response)

    async def get_acknowledgment_status(self, directive_id: str) -> AcknowledgmentStatus:
        """
        Get acknowledgment status for a directive.

        Verified route: ``GET /api/v1/directives/{directive_id}/acknowledgments``.
        """
        response = await self._http.request(
            "GET", f"/api/v1/directives/{encode_path_param(directive_id)}/acknowledgments"
        )
        return AcknowledgmentStatus(**response)

    async def expire_directive(self, directive_id: str) -> Directive:
        """
        Mark a directive as expired. Only org_owner/org_admin may expire.

        Verified route: ``POST /api/v1/directives/{directive_id}/expire``.
        """
        response = await self._http.request(
            "POST", f"/api/v1/directives/{encode_path_param(directive_id)}/expire"
        )
        return Directive(**response)

    async def supersede_directive(self, directive_id: str, new_directive_id: str) -> Directive:
        """
        Mark a directive as superseded by another. Only org_owner/org_admin.

        Verified route: ``POST /api/v1/directives/{directive_id}/supersede``
        with ``SupersedeRequest``.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/directives/{encode_path_param(directive_id)}/supersede",
            json_data={"new_directive_id": new_directive_id},
        )
        return Directive(**response)

    async def revoke_directive(self, directive_id: str) -> Directive:
        """
        Revoke a directive. Only org_owner/org_admin may revoke.

        Verified route: ``POST /api/v1/directives/{directive_id}/revoke``.
        """
        response = await self._http.request(
            "POST", f"/api/v1/directives/{encode_path_param(directive_id)}/revoke"
        )
        return Directive(**response)

    async def batch_acknowledge_directive(
        self,
        directive_id: str,
        agent_ids: list[str] | None = None,
        user_ids: list[str] | None = None,
        notes: str | None = None,
    ) -> BatchAcknowledgeResult:
        """
        Batch-acknowledge a directive for multiple agents and/or users.

        Verified route: ``POST /api/v1/directives/{directive_id}/batch-acknowledge``
        with ``BatchAcknowledgeRequest`` (676-753``). At least one agent_id or user_id required.
        Only org_owner/org_admin may batch-acknowledge on behalf of others.
        """
        json_data: dict[str, Any] = {
            "agent_ids": agent_ids or [],
            "user_ids": user_ids or [],
        }
        if notes is not None:
            json_data["notes"] = notes

        response = await self._http.request(
            "POST",
            f"/api/v1/directives/{encode_path_param(directive_id)}/batch-acknowledge",
            json_data=json_data,
        )
        return BatchAcknowledgeResult(**response)

    # =======================================================================
    # Change Requests
    # =======================================================================

    async def list_change_requests(
        self,
        application_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List change requests, optionally filtered by application/status.

        Verified route: ``GET /api/v1/change-requests``. No fixed
        ``response_model`` server-side, so this returns the raw dict.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if application_id:
            params["application_id"] = application_id
        if status:
            params["status"] = status

        result: dict[str, Any] = await self._http.request("GET", "/api/v1/change-requests", params=params)
        return result

    async def create_change_request(
        self,
        application_id: str,
        agent_id: str,
        parameter_name: str,
        current_value: str,
        requested_value: str,
        justification: str,
    ) -> dict[str, Any]:
        """
        Create a change request (draft status) for an application/agent
        parameter requiring admin approval.

        Verified route: ``POST /api/v1/change-requests`` with
        ``CreateChangeRequestBody`` (121-147``).
        """
        result: dict[str, Any] = await self._http.request(
            "POST",
            "/api/v1/change-requests",
            json_data={
                "application_id": application_id,
                "agent_id": agent_id,
                "parameter_name": parameter_name,
                "current_value": current_value,
                "requested_value": requested_value,
                "justification": justification,
            },
        )
        return result

    async def get_change_request(self, request_id: str) -> dict[str, Any]:
        """
        Get a change request by ID.

        Verified route: ``GET /api/v1/change-requests/{request_id}``.
        """
        result: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/change-requests/{encode_path_param(request_id)}"
        )
        return result

    async def submit_change_request(self, request_id: str) -> dict[str, Any]:
        """
        Submit a change request (draft -> pending). Requester only.

        Verified route: ``PATCH /api/v1/change-requests/{request_id}/submit``.
        """
        result: dict[str, Any] = await self._http.request(
            "PATCH", f"/api/v1/change-requests/{encode_path_param(request_id)}/submit"
        )
        return result

    async def approve_change_request(self, request_id: str) -> dict[str, Any]:
        """
        Approve a change request (pending -> approved). Self-approval by the
        original requester is rejected server-side.

        Verified route: ``PATCH /api/v1/change-requests/{request_id}/approve``.
        """
        result: dict[str, Any] = await self._http.request(
            "PATCH", f"/api/v1/change-requests/{encode_path_param(request_id)}/approve"
        )
        return result

    async def deny_change_request(self, request_id: str, reason: str = "") -> dict[str, Any]:
        """
        Deny a change request (pending/counter_proposed -> denied).

        Verified route: ``PATCH /api/v1/change-requests/{request_id}/deny``
        with ``DenyChangeRequestBody`` (234-258``).
        """
        result: dict[str, Any] = await self._http.request(
            "PATCH",
            f"/api/v1/change-requests/{encode_path_param(request_id)}/deny",
            json_data={"reason": reason},
        )
        return result

    async def counter_propose_change_request(
        self, request_id: str, counter_value: str, counter_note: str
    ) -> dict[str, Any]:
        """
        Counter-propose on a change request (pending -> counter_proposed).

        Verified route: ``PATCH /api/v1/change-requests/{request_id}/counter-propose``
        with ``CounterProposeBody`` (261-285``).
        """
        result: dict[str, Any] = await self._http.request(
            "PATCH",
            f"/api/v1/change-requests/{encode_path_param(request_id)}/counter-propose",
            json_data={"counter_value": counter_value, "counter_note": counter_note},
        )
        return result

    async def accept_counter_change_request(self, request_id: str) -> dict[str, Any]:
        """
        Accept a counter-proposal (counter_proposed -> accepted). Requester only.

        Verified route: ``PATCH /api/v1/change-requests/{request_id}/accept-counter``.
        """
        result: dict[str, Any] = await self._http.request(
            "PATCH", f"/api/v1/change-requests/{encode_path_param(request_id)}/accept-counter"
        )
        return result

    async def apply_change_request(self, request_id: str) -> dict[str, Any]:
        """
        Apply an approved/accepted change request (-> applied). Materializes
        the change via ``InvocationPolicyService.update()``.

        Verified route: ``PATCH /api/v1/change-requests/{request_id}/apply``.
        """
        result: dict[str, Any] = await self._http.request(
            "PATCH", f"/api/v1/change-requests/{encode_path_param(request_id)}/apply"
        )
        return result

    # =======================================================================
    # Escalation (pool-based configuration + manual escalation)
    # =======================================================================

    async def get_escalation_config(self, pool_id: str) -> dict[str, Any]:
        """
        Get escalation configuration for a pool (timeouts + escalation chain).

        Verified route: ``GET /api/v1/escalation/config/{pool_id}``
        (``nexus_escalation_get_config``). Returns a plain camelCase
        dict (default config synthesized when none is configured yet), so
        this returns the raw dict.
        """
        result: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/escalation/config/{encode_path_param(pool_id)}"
        )
        return result

    async def update_escalation_config(self, pool_id: str, **fields: Any) -> dict[str, Any]:
        """
        Update (or create) escalation configuration for a pool.

        Verified route: ``PUT /api/v1/escalation/config/{pool_id}`` with
        ``UpdateEscalationConfigRequest``
        (543-594``). Field names
        are the server's camelCase aliases.

        Args:
            pool_id: Pool ID
            **fields: Any of ``enabled``, ``claimTimeoutMinutes``,
                ``poolTimeoutMinutes``, ``escalationChain`` (list of
                ``{targetType, targetId, targetName, timeoutMinutes}``)
        """
        result: dict[str, Any] = await self._http.request(
            "PUT", f"/api/v1/escalation/config/{encode_path_param(pool_id)}", json_data=fields
        )
        return result

    async def list_pending_escalations(
        self,
        pool_id: str | None = None,
        urgency: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List pending task escalations with timeout countdowns.

        Verified route: ``GET /api/v1/escalation/pending``
        (``nexus_escalation_list_pending``).

        Args:
            pool_id: Filter by pool
            urgency: Comma-separated urgency levels
            priority: Comma-separated priority levels
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            ``{"records": [...], "total": int, "hasMore": bool}``
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if pool_id:
            params["poolId"] = pool_id
        if urgency:
            params["urgency"] = urgency
        if priority:
            params["priority"] = priority

        result: dict[str, Any] = await self._http.request("GET", "/api/v1/escalation/pending", params=params)
        return result

    async def manual_escalate_task(
        self,
        task_id: str,
        reason: str,
        target_id: str | None = None,
        target_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Manually escalate a task to the next chain target, or an explicit one.

        Verified route: ``POST /api/v1/escalation/tasks/{task_id}/escalate``
        with ``ManualEscalateRequest``
        (756-796``).
        """
        json_data: dict[str, Any] = {"reason": reason}
        if target_id is not None:
            json_data["targetId"] = target_id
        if target_type is not None:
            json_data["targetType"] = target_type

        result: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/escalate",
            json_data=json_data,
        )
        return result

    async def acknowledge_escalation(self, task_id: str) -> dict[str, Any]:
        """
        Acknowledge a pending task escalation.

        Verified route: ``POST /api/v1/escalation/tasks/{task_id}/acknowledge``
        (``nexus_escalation_acknowledge``).

        Returns:
            ``{"success": true}``
        """
        result: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/escalation/tasks/{encode_path_param(task_id)}/acknowledge"
        )
        return result

    async def get_escalation_stats(
        self,
        pool_id: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated escalation statistics (counts, rates, pending).

        Verified route: ``GET /api/v1/escalation/stats``
        (``nexus_escalation_get_stats``). Camelcase wire shape, no
        fixed local model — returns the raw dict.
        """
        params: dict[str, Any] = {}
        if pool_id:
            params["poolId"] = pool_id
        if period_start:
            params["periodStart"] = period_start
        if period_end:
            params["periodEnd"] = period_end

        result: dict[str, Any] = await self._http.request("GET", "/api/v1/escalation/stats", params=params)
        return result

    # =======================================================================
    # Interventions (mid-execution session control)
    # =======================================================================

    async def pause_session(self, session_id: str, reason: str) -> Intervention:
        """
        Pause execution for a session (agent stops taking new actions).

        Verified route: ``POST /api/v1/interventions/{session_id}/pause``
        with ``PauseRequest``.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/interventions/{encode_path_param(session_id)}/pause",
            json_data={"reason": reason},
        )
        return Intervention(**response)

    async def resume_session(
        self, session_id: str, modifications: dict[str, Any] | None = None
    ) -> Intervention:
        """
        Resume a paused session, with optional constraint modifications.

        Verified route: ``POST /api/v1/interventions/{session_id}/resume``
        with ``ResumeRequest``.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/interventions/{encode_path_param(session_id)}/resume",
            json_data={"modifications": modifications},
        )
        return Intervention(**response)

    async def tighten_constraints(
        self, session_id: str, dimension: str, new_limit: float, reason: str
    ) -> Intervention:
        """
        Tighten a constraint dimension (e.g. budget, time) during execution.

        Verified route: ``POST /api/v1/interventions/{session_id}/tighten-constraints``
        with ``TightenConstraintsRequest`` (251-304``).
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/interventions/{encode_path_param(session_id)}/tighten-constraints",
            json_data={"dimension": dimension, "new_limit": new_limit, "reason": reason},
        )
        return Intervention(**response)

    async def fence_session(self, session_id: str, reason: str) -> Intervention:
        """
        Fence (best-effort cancel) in-flight actions for a session.

        Verified route: ``POST /api/v1/interventions/{session_id}/fence``
        with ``FenceRequest``.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/interventions/{encode_path_param(session_id)}/fence",
            json_data={"reason": reason},
        )
        return Intervention(**response)

    async def list_intervention_sessions(
        self, agent_id: str | None = None, organization_id: str | None = None
    ) -> SessionInterventionList:
        """
        List active (running or paused) sessions eligible for intervention.

        Verified route: ``GET /api/v1/interventions/sessions``. Note: the caller's own
        org context is always applied server-side; ``organization_id`` is
        accepted-and-ignored for API compatibility.
        """
        params: dict[str, Any] = {}
        if agent_id:
            params["agentId"] = agent_id
        if organization_id:
            params["organizationId"] = organization_id

        response = await self._http.request("GET", "/api/v1/interventions/sessions", params=params)
        return SessionInterventionList(**response)

    async def get_intervention_session_state(self, session_id: str) -> SessionInterventionState:
        """
        Get a session's current intervention state (status, pause metadata).

        Verified route: ``GET /api/v1/interventions/{session_id}``.
        """
        response = await self._http.request(
            "GET", f"/api/v1/interventions/{encode_path_param(session_id)}"
        )
        return SessionInterventionState(**response)

    async def get_intervention_history(self, session_id: str) -> list[Intervention]:
        """
        Get the full intervention history for a session, most recent first.

        Verified route: ``GET /api/v1/interventions/{session_id}/history``.
        """
        response = await self._http.request(
            "GET", f"/api/v1/interventions/{encode_path_param(session_id)}/history"
        )
        return [Intervention(**item) for item in response]

    # =======================================================================
    # Agent Escalations (smart escalation queue — SmartEscalationContext)
    # =======================================================================

    async def list_agent_escalations(
        self,
        agent_id: str | None = None,
        urgency: str | None = None,
        limit: int = 50,
    ) -> AgentEscalationList:
        """
        List pending agent escalations (smart escalation queue).

        Verified route: ``GET /api/v1/agent-escalations/pending`` with
        ``EscalationListResponse``. The caller's own org context is always applied
        server-side; the ``organization_id`` query param is
        accepted-and-ignored, so it is not exposed here.

        Args:
            agent_id: Filter by agent (server alias ``agentId``)
            urgency: Filter by urgency level
            limit: Maximum results (1-100)

        Returns:
            AgentEscalationList: escalations + total
        """
        params: dict[str, Any] = {"limit": limit}
        if agent_id:
            params["agentId"] = agent_id
        if urgency:
            params["urgency"] = urgency

        response = await self._http.request(
            "GET", "/api/v1/agent-escalations/pending", params=params
        )
        return AgentEscalationList(**response)

    async def stream_agent_escalations(
        self, agent_id: str | None = None, organization_id: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        SSE stream of new agent-escalation notifications.

        Verified route: ``GET /api/v1/agent-escalations/stream``. Unlike the
        objectives progress stream, this route authenticates via the normal
        bearer header (``Depends(get_current_user)``), NOT a ``?token=``
        query param — so no token plumbing is needed. Emits an initial
        ``escalation_pending`` event per already-pending escalation, then
        real-time ``escalation_resolved`` / ``escalation_update`` events with
        ``heartbeat`` keepalives.

        Args:
            agent_id: Stream escalations for this agent (server alias ``agentId``)
            organization_id: Accepted-and-ignored server-side (caller org is
                always applied); exposed for API compatibility.

        Yields:
            Event dicts.
        """
        params: dict[str, Any] = {}
        if agent_id:
            params["agentId"] = agent_id
        if organization_id:
            params["organizationId"] = organization_id

        async for event in self._http.stream(
            "GET", "/api/v1/agent-escalations/stream", params=params or None
        ):
            yield event

    async def get_agent_escalation(self, escalation_id: str) -> AgentEscalation:
        """
        Get a specific agent escalation by ID.

        Verified route: ``GET /api/v1/agent-escalations/{escalation_id}``
        with ``EscalationContextResponse``. Returns 404 both when the escalation
        does not exist AND when it belongs to another org (tenant-safe).
        """
        response = await self._http.request(
            "GET", f"/api/v1/agent-escalations/{encode_path_param(escalation_id)}"
        )
        return AgentEscalation(**response)

    async def resolve_agent_escalation(
        self,
        escalation_id: str,
        decision: Literal["approve", "reject", "modify", "escalate_further"],
        resolved_by: str,
        reasoning: str,
        modifications: dict[str, Any] | None = None,
    ) -> AgentEscalationResolveResult:
        """
        Resolve an agent escalation with a human decision.

        Verified route: ``POST /api/v1/agent-escalations/{escalation_id}/resolve``
        with ``ResolveEscalationRequest`` (465-537``). ``decision`` must be one of ``approve`` /
        ``reject`` / ``modify`` / ``escalate_further``; ``reasoning`` is
        required server-side for ``reject`` / ``modify``. Request body field
        names are the server's camelCase aliases.

        Args:
            escalation_id: Escalation to resolve
            decision: The resolution decision
            resolved_by: Actor id recorded on the resolution (alias ``resolvedBy``)
            reasoning: Rationale for the decision
            modifications: Optional modification payload for ``modify``

        Returns:
            AgentEscalationResolveResult: success, escalationId, decision, resolvedAt
        """
        json_data: dict[str, Any] = {
            "decision": decision,
            "resolvedBy": resolved_by,
            "reasoning": reasoning,
        }
        if modifications is not None:
            json_data["modifications"] = modifications

        response = await self._http.request(
            "POST",
            f"/api/v1/agent-escalations/{encode_path_param(escalation_id)}/resolve",
            json_data=json_data,
        )
        return AgentEscalationResolveResult(**response)

    async def cancel_agent_escalation(self, escalation_id: str) -> AgentEscalationCancelResult:
        """
        Cancel a pending agent escalation.

        Verified route: ``POST /api/v1/agent-escalations/{escalation_id}/cancel``. Returns 400 when the
        escalation is not pending / already processed.

        Returns:
            AgentEscalationCancelResult: success, escalationId, status
        """
        response = await self._http.request(
            "POST", f"/api/v1/agent-escalations/{encode_path_param(escalation_id)}/cancel"
        )
        return AgentEscalationCancelResult(**response)


# ===========================================================================
# Work Unit models (67-197 — camelCase wire shape)
# ===========================================================================


class WorkUnitTrustInfo(BaseModel):
    """Trust information nested on a work unit."""

    status: str = "valid"
    establishedAt: str | None = None
    expiresAt: str | None = None
    delegatedBy: dict[str, Any] | None = None
    trustChainId: str | None = None


class WorkUnitWorkspaceRef(BaseModel):
    """Workspace reference nested on a work unit."""

    id: str
    name: str
    color: str | None = None


class WorkUnit(BaseModel):
    """Work unit record (``WorkUnitResponse``, camelCase)."""

    id: str
    name: str
    description: str = ""
    type: str
    capabilities: list[str] = Field(default_factory=list)
    trustInfo: WorkUnitTrustInfo
    workspaceId: str | None = None
    workspace: WorkUnitWorkspaceRef | None = None
    createdBy: str
    createdByName: str | None = None
    createdAt: str
    updatedAt: str
    lastRunAt: str | None = None
    tags: list[str] = Field(default_factory=list)
    subUnits: list[dict[str, Any]] | None = None
    subUnitCount: int | None = None


class WorkUnitListResponse(BaseModel):
    """Response for ``GET /work-units`` (``WorkUnitListResponse``)."""

    items: list[WorkUnit]
    total: int
    page: int
    pageSize: int
    hasMore: bool


class RunResult(BaseModel):
    """Response for ``POST /work-units/{id}/run`` (``RunResultResponse``, camelCase)."""

    id: str
    status: str
    startedAt: str
    completedAt: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None


class ExecutionResult(BaseModel):
    """Response for ``POST /work-units/{id}/execute`` (``ExecutionResultResponse``, snake_case)."""

    run_id: str
    output: str
    status: str
    cost_usd: float = 0.0
    cycles_used: int = 1
    tokens_used: int = 0


class ConfigVersion(BaseModel):
    """A snapshot of a work unit's configuration."""

    id: str
    workUnitId: str
    version: int
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    createdBy: str
    createdByName: str
    createdAt: str
    isCurrent: bool
    tags: list[str] | None = None


class VersionList(BaseModel):
    """A page of config versions, plus which one is live."""

    versions: list[ConfigVersion] = Field(default_factory=list)
    total: int
    currentVersion: int


class VersionChange(BaseModel):
    """One field-level difference between two versions."""

    field: str
    path: list[str] = Field(default_factory=list)
    changeType: str
    oldValue: Any | None = None
    newValue: Any | None = None


class VersionComparison(BaseModel):
    """A field-level diff between two config versions."""

    fromVersion: ConfigVersion
    toVersion: ConfigVersion
    changes: list[VersionChange] = Field(default_factory=list)


class ExecutionConfig(BaseModel):
    """Response for the execution-config get/patch endpoints (snake_case)."""

    id: str | None = None
    work_unit_id: str
    runtime: str
    model: str
    execution_mode: str
    temperature: float
    max_tokens: int
    max_cycles: int
    budget_limit_usd: float
    timeout_seconds: float
    memory_depth: str
    tool_access: str
    allowed_tools: list[str] = Field(default_factory=list)
    llm_routing: dict[str, str] = Field(default_factory=dict)
    checkpoint_frequency: int
    enable_checkpointing: bool
    created_at: str | None = None
    updated_at: str | None = None


# ===========================================================================
# Directive models (123-231 — snake_case)
# ===========================================================================


class Directive(BaseModel):
    """Directive record (``DirectiveResponse``)."""

    model_config = ConfigDict(extra="allow")

    id: str
    organization_id: str
    title: str
    reference_number: str | None = None
    content_markdown: str
    summary: str | None = None
    directive_type: str
    priority: str
    issuing_unit_id: str
    issuing_role_id: str | None = None
    issued_by_user_id: str | None = None
    target_units_json: str = "[]"
    target_all_units: bool
    effective_from: str
    effective_until: str | None = None
    acknowledgment_required: bool
    acknowledgment_deadline: str | None = None
    acknowledgments_json: str = "[]"
    acknowledgment_count: int
    status: str
    # Read-back, server-side: without this field a
    # RESTRICTED directive and a PUBLIC one parsed into byte-identical
    # ``Directive`` objects -- ``extra="allow"`` above kept the value reachable
    # via ``model_extra``, but nothing on the typed surface said it existed,
    # so a caller could not tell a directive apart from one it should not
    # have been able to read the content of. Declared explicitly rather than
    # left to the extras bag, matching the server's own default.
    classification: str = "public"
    superseded_by_id: str | None = None
    supersedes_id: str | None = None
    related_knowledge_ids_json: str = "[]"
    metadata_json: str = "{}"
    tags_json: str = "[]"
    created_by: str | None = None
    published_at: str | None = None
    published_by: str | None = None
    created_at: str
    updated_at: str


class DirectiveList(BaseModel):
    """Response for ``GET /directives`` (``DirectiveListResponse``)."""

    records: list[Directive]
    total: int


class AcknowledgmentStatus(BaseModel):
    """Response for ``GET /directives/{id}/acknowledgments``."""

    directive_id: str
    found: bool
    acknowledgment_required: bool | None = None
    acknowledgment_deadline: str | None = None
    acknowledgment_count: int = 0
    acknowledgments: list[dict[str, Any]] = Field(default_factory=list)
    target_units_count: int | str | None = None
    target_all_units: bool = False


class BatchAcknowledgeResult(BaseModel):
    """Response for ``POST /directives/{id}/batch-acknowledge``."""

    directive_id: str
    acknowledged: int
    already_acknowledged: int
    total_requested: int


# ===========================================================================
# Intervention models (97-136 — camelCase)
# ===========================================================================


class Intervention(BaseModel):
    """Response for a pause/resume/tighten-constraints/fence intervention
    (``InterventionResponse``, also each row of ``get_intervention_history``)."""

    id: str
    sessionId: str
    agentId: str
    organizationId: str
    interventionType: str
    initiatedBy: str
    reason: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    completedAt: str | None = None


class SessionInterventionState(BaseModel):
    """Response for a session's intervention state (``SessionStateResponse``)."""

    sessionId: str
    agentId: str
    organizationId: str
    status: str
    pausedBy: str | None = None
    pausedAt: str | None = None
    pauseReason: str | None = None
    constraintChanges: list[dict[str, Any]] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)


class SessionInterventionList(BaseModel):
    """Response for ``GET /interventions/sessions`` (``SessionListResponse``)."""

    sessions: list[SessionInterventionState]
    total: int


# ===========================================================================
# Agent-escalation models (85-216 —
# camelCase wire shape; response_model serializes by alias, so attribute
# names here match the camelCase wire keys directly). ``extra="allow"`` on
# the nested shapes keeps the rich SmartEscalationContext forward-compatible.
# ===========================================================================


class AgentEscalationTriggerEvent(BaseModel):
    """Trigger event that caused an escalation (``TriggerEventResponse``)."""

    model_config = ConfigDict(extra="allow")

    eventType: str
    description: str
    timestamp: str
    severity: str


class AgentEscalationOption(BaseModel):
    """One resolution option (``EscalationOptionResponse``)."""

    model_config = ConfigDict(extra="allow")

    optionId: str
    label: str
    description: str
    impact: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)


class AgentEscalationRecommendation(BaseModel):
    """AI recommendation for resolution (``AIRecommendationResponse``)."""

    model_config = ConfigDict(extra="allow")

    recommendedOptionId: str
    confidence: float
    reasoning: str
    supportingEvidence: list[str] = Field(default_factory=list)


class AgentEscalationConstraintViolation(BaseModel):
    """One constraint violation (``ConstraintViolationResponse``)."""

    model_config = ConfigDict(extra="allow")

    constraintId: str
    constraintType: str
    violatedAt: str
    threshold: dict[str, Any] | None = None
    actualValue: dict[str, Any] | None = None


class AgentEscalationConstraintState(BaseModel):
    """Current constraint state (``ConstraintStateResponse``)."""

    model_config = ConfigDict(extra="allow")

    activeConstraints: list[dict[str, Any]] = Field(default_factory=list)
    violatedConstraints: list[AgentEscalationConstraintViolation] = Field(default_factory=list)
    remainingBudget: dict[str, Any] | None = None


class AgentEscalationGatheredContext(BaseModel):
    """Context gathered for the escalation (``GatheredContextResponse``)."""

    model_config = ConfigDict(extra="allow")

    relevantHistory: list[dict[str, Any]] = Field(default_factory=list)
    userPreferences: dict[str, Any] = Field(default_factory=dict)
    similarPastDecisions: list[dict[str, Any]] = Field(default_factory=list)
    stakeholderContext: dict[str, Any] = Field(default_factory=dict)


class AgentEscalation(BaseModel):
    """A single agent escalation in SmartEscalationContext format
    (``EscalationContextResponse``, also each row of the pending list)."""

    model_config = ConfigDict(extra="allow")

    escalationId: str
    urgency: str
    escalationType: str
    agentId: str
    sessionId: str
    triggerEvent: AgentEscalationTriggerEvent
    contextSnapshot: dict[str, Any] = Field(default_factory=dict)
    options: list[AgentEscalationOption] = Field(default_factory=list)
    recommendation: AgentEscalationRecommendation | None = None
    constraintState: AgentEscalationConstraintState
    gatheredContext: AgentEscalationGatheredContext
    status: str
    createdAt: str
    expiresAt: str | None = None
    resolvedAt: str | None = None
    resolvedBy: str | None = None
    decision: str | None = None
    resolutionReasoning: str | None = None


class AgentEscalationList(BaseModel):
    """Response for ``GET /agent-escalations/pending`` (``EscalationListResponse``)."""

    escalations: list[AgentEscalation]
    total: int


class AgentEscalationResolveResult(BaseModel):
    """Response for ``POST /agent-escalations/{id}/resolve``
    (``ResolveEscalationResponse``, serialized by alias → camelCase)."""

    model_config = ConfigDict(extra="allow")

    success: bool
    escalationId: str
    decision: str
    resolvedAt: str


class AgentEscalationCancelResult(BaseModel):
    """Response for ``POST /agent-escalations/{id}/cancel``
    (``CancelEscalationResponse``, serialized by alias → camelCase)."""

    model_config = ConfigDict(extra="allow")

    success: bool
    escalationId: str
    status: str
