"""
Agentic OS SDK Sessions Module.

Provides operations for managing work sessions (agent execution contexts).

Sessions are served under ``/api/v1/sessions``. There is no plain
``POST /api/v1/sessions`` create route: a session is created either via
``POST /sessions/from-task`` (query-param ``request_id``) or lazily via
``GET /sessions/{id}`` when the id resolves to an objective.

The API's ``Session`` shape (``objective_id``, ``created_at``/``updated_at``/
``paused_at``/``completed_at``, ``messages_json``/``artifacts_json``/
``cost_json``) does not match :class:`~aegis_sdk.types.Session`
(``request_id``, ``start_time``/``end_time``/``pause_time``,
``message_count``/``artifact_count``), so responses are normalized before
construction — see ``_normalize_session`` for the field mapping.

Known limitation: the SDK's ``Session``/``SessionArtifact`` types still carry
the older vocabulary rather than the wire's. Aligning them is a tracked
follow-up. Several methods on this module address routes the API does not
serve and are marked with a warning in their own docstrings.
"""

import uuid
import warnings
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from .._http import encode_path_param
from ..types import (
    Session,
    SessionArtifact,
    SessionContext,
    SessionMessage,
    Subagent,
)


def _normalize_session(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt the real session wire shape (``_session_to_response`` in
    into the fields :class:`~aegis_sdk.types.Session` requires.

    ``request_id`` holds the parent objective/task id (the wire's
    ``objective_id``) since that is the closest SDK-vocabulary analog to
    "the work item this session is tied to". ``message_count`` /
    ``artifact_count`` are derived by parsing the wire's JSON-string fields
    since the server does not return pre-computed counts.
    """
    import json

    try:
        messages = json.loads(raw.get("messages_json") or "[]")
    except (TypeError, ValueError):
        messages = []
    try:
        artifacts = json.loads(raw.get("artifacts_json") or "[]")
    except (TypeError, ValueError):
        artifacts = []

    return {
        "id": raw.get("id", ""),
        "request_id": raw.get("objective_id", ""),
        "agent_id": raw.get("agent_id") or "",
        "status": raw.get("status", "active"),
        "start_time": raw.get("created_at") or datetime.now(UTC),
        "end_time": raw.get("completed_at"),
        "pause_time": raw.get("paused_at"),
        "message_count": len(messages),
        "artifact_count": len(artifacts),
        "metadata": {
            "organization_id": raw.get("organization_id"),
            "workspace_id": raw.get("workspace_id"),
            "user_id": raw.get("user_id"),
            "user_name": raw.get("user_name"),
            "agent_name": raw.get("agent_name"),
            "title": raw.get("title"),
            "description": raw.get("description"),
            "cost_json": raw.get("cost_json"),
        },
    }


def _normalize_session_artifact(raw: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Adapt a real ``AgenticArtifact`` DB row (as returned by
    ``GET /sessions/{id}/artifacts`` / ``POST /sessions/{id}/artifacts``)
    into the fields :class:`~aegis_sdk.types.SessionArtifact` requires.

    The wire row has no ``session_id`` field (it links via ``request_id``)
    and no unified ``data`` dict — the descriptive fields are bagged into
    ``data`` so no information is lost.
    """
    return {
        "id": raw.get("id", ""),
        "session_id": session_id,
        "artifact_type": raw.get("artifact_type", "file"),
        "name": raw.get("name", ""),
        "data": {
            "request_id": raw.get("request_id"),
            "mime_type": raw.get("mime_type"),
            "size_bytes": raw.get("size_bytes"),
            "storage_path": raw.get("storage_path"),
            "created_by_id": raw.get("created_by_id"),
            "created_by_type": raw.get("created_by_type"),
            "artifact_version": raw.get("artifact_version"),
        },
        "created_at": raw.get("created_at") or datetime.now(UTC),
    }


class SessionsModule:
    """
    Sessions management operations.

    Sessions are execution contexts where agents perform work on requests.
    They track messages, artifacts, and spawned subagents.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # Start a session for a task/request
        ...     session = await client.sessions.start(request_id="req_abc123")
        ...
        ...     # Send messages during work
        ...     await client.sessions.send_message(
        ...         session.id,
        ...         content="Starting analysis..."
        ...     )
        ...
        ...     # End the session
        ...     await client.sessions.end(session.id)
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def create_from_task(self, request_id: str) -> dict[str, Any]:
        """
        Create (or return an existing) work session linked to a task/request.

        Verified route: ``POST /api/v1/sessions/from-task`` — ``request_id``
        is a QUERY PARAMETER, not a JSON body field. This is the real explicit
        session-creation endpoint (there is no plain ``POST /sessions``).

        Args:
            request_id: ID of the AgenticRequest (task) to work on

        Returns:
            Raw dict: ``{"session_id": str, "task_context": {...}}`` — the
            API's ``SessionFromTaskResponse`` shape, which does not map onto
            :class:`~aegis_sdk.types.Session` (no status/timestamps).
            Call :meth:`get` with the returned ``session_id`` for the full
            typed :class:`Session`.

        Example:
            >>> created = await client.sessions.create_from_task("req_abc123")
            >>> session = await client.sessions.get(created["session_id"])
        """
        return await self._http.request(
            "POST",
            "/api/v1/sessions/from-task",
            params={"request_id": request_id},
        )

    async def start(self, request_id: str) -> Session:
        """
        Start (or resume) a work session for a request/task.

        Sessions are created with ``POST /api/v1/sessions/from-task``, taking
        ``request_id`` as a query parameter only: the executing agent is
        resolved from the task server-side, and there is no per-session
        metadata bag, so this method takes neither ``agent_id`` nor
        ``metadata``. A ``GET`` for the full session follows.

        Args:
            request_id: Request/task this session is working on

        Returns:
            Started (or existing) session

        Example:
            >>> session = await client.sessions.start(request_id="req_abc123")
            >>> print(f"Session started: {session.id}")
        """
        created = await self.create_from_task(request_id)
        return await self.get(created["session_id"])

    async def get(self, session_id: str) -> Session:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session details

        Raises:
            NotFoundError: If session doesn't exist

        Example:
            >>> session = await client.sessions.get("ses_abc123")
            >>> print(f"Session status: {session.status}")
        """
        response = await self._http.request(
            "GET", f"/api/v1/sessions/{encode_path_param(session_id)}"
        )
        return Session(**_normalize_session(response))

    async def end(self, session_id: str) -> Session:
        """
        End a work session.

        ``POST /api/v1/sessions/{session_id}/end`` takes NO request body, so
        this method takes no ``summary`` or ``metadata``.

        Args:
            session_id: Session ID

        Returns:
            Ended session

        Example:
            >>> session = await client.sessions.end("ses_abc123")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/sessions/{encode_path_param(session_id)}/end",
        )
        return Session(**_normalize_session(response))

    async def pause(self, session_id: str) -> Session:
        """
        Pause a work session.

        ``POST /api/v1/sessions/{session_id}/pause`` takes NO request body,
        so this method takes no ``reason``.

        Args:
            session_id: Session ID

        Returns:
            Paused session

        Example:
            >>> session = await client.sessions.pause("ses_abc123")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/sessions/{encode_path_param(session_id)}/pause",
        )
        return Session(**_normalize_session(response))

    async def resume(self, session_id: str) -> Session:
        """
        Resume a paused session.

        Args:
            session_id: Session ID

        Returns:
            Resumed session

        Example:
            >>> session = await client.sessions.resume("ses_abc123")
            >>> print(f"Session resumed, status: {session.status}")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/sessions/{encode_path_param(session_id)}/resume",
        )
        return Session(**_normalize_session(response))

    async def send_message(
        self,
        session_id: str,
        content: str,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Send a message within a session, triggering agent response.

        ``POST /api/v1/sessions/{session_id}/messages`` takes
        ``SendMessageBody = {content, artifact_ids}``. There is no ``role``
        field (messages are always stored as ``role="user"``) and no
        ``metadata`` field, so this method accepts neither.
        The response is ``{"message_id": str, "status": "processing"}``
        (agent execution is launched as a background task and its response
        is published on :meth:`stream_events` / :meth:`stream_messages`) —
        NOT a full message record, so this returns the raw dict rather than
        a :class:`~aegis_sdk.types.SessionMessage`.

        Args:
            session_id: Session ID
            content: Message content
            artifact_ids: Optional list of artifact IDs referenced by the
                message

        Returns:
            ``{"message_id": str, "status": "processing"}``

        Example:
            >>> result = await client.sessions.send_message(
            ...     "ses_abc123",
            ...     content="Please continue the analysis.",
            ... )
            >>> print(result["message_id"])
        """
        json_data: dict[str, Any] = {"content": content}
        if artifact_ids is not None:
            json_data["artifact_ids"] = artifact_ids

        return await self._http.request(
            "POST",
            f"/api/v1/sessions/{encode_path_param(session_id)}/messages",
            json_data=json_data,
        )

    async def get_messages(
        self,
        session_id: str,
        role: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SessionMessage]:
        """
        Get messages from a session.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/sessions/{session_id}/messages`` is not served;
            only the POST-to-send endpoint exists, and messages are delivered
            over the event stream rather than a listable GET. Use
            :meth:`stream_messages` to observe messages as they arrive.

        Args:
            session_id: Session ID
            role: Filter by message role
            limit: Maximum messages to return
            offset: Offset for pagination

        Returns:
            List of messages

        Example:
            >>> messages = await client.sessions.get_messages("ses_abc123")
            >>> for msg in messages:
            ...     print(f"[{msg.role}] {msg.content}")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if role:
            params["role"] = role

        response = await self._http.request(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/messages",
            params=params,
        )
        return [SessionMessage(**item) for item in response]

    async def add_artifact(
        self,
        session_id: str,
        name: str,
        artifact_type: str,
        file_content: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> SessionArtifact:
        """
        Upload or create an artifact attached to a session.

        ``POST /api/v1/sessions/{session_id}/artifacts`` accepts
        ``multipart/form-data`` — ``file`` (optional upload), ``name`` (form
        field) and ``type`` (form field) — not a JSON body. Artifact content
        travels as raw file bytes; there is no ``data`` field.

        Args:
            session_id: Session ID
            name: Artifact name
            artifact_type: Type of artifact (used as the server's ``type``
                form field, e.g. "file", "code", "image", "json")
            file_content: Optional raw file bytes to upload
            filename: Optional filename for the uploaded file (defaults to
                ``name``)
            content_type: Optional MIME type for the uploaded file

        Returns:
            Created artifact

        Example:
            >>> artifact = await client.sessions.add_artifact(
            ...     "ses_abc123",
            ...     name="analysis_results.json",
            ...     artifact_type="json",
            ...     file_content=b'{"findings": [], "score": 85}',
            ...     content_type="application/json",
            ... )
        """
        request_kwargs: dict[str, Any] = {"data": {"name": name, "type": artifact_type}}
        if file_content is not None:
            request_kwargs["files"] = {
                "file": (
                    filename or name,
                    file_content,
                    content_type or "application/octet-stream",
                )
            }

        response = await self._http.request(
            "POST",
            f"/api/v1/sessions/{encode_path_param(session_id)}/artifacts",
            **request_kwargs,
        )
        return SessionArtifact(**_normalize_session_artifact(response, session_id))

    async def get_artifacts(self, session_id: str) -> list[SessionArtifact]:
        """
        Get all artifacts from a session.

        Fixed wire route: ``GET /api/v1/sessions/{session_id}/artifacts``
        returns ``{"records": [...]}`` (NOT a bare array; the prior
        implementation iterated the raw response, which would iterate over
        the dict's KEYS). Each record is a raw ``AgenticArtifact`` DB row
        (``id``, ``request_id``, ``mime_type``, ``size_bytes``, ...) — NOT
        the ``SessionArtifact`` shape (no ``session_id`` / ``data`` fields);
        normalized via ``_normalize_session_artifact``.

        Args:
            session_id: Session ID

        Returns:
            List of artifacts

        Example:
            >>> artifacts = await client.sessions.get_artifacts("ses_abc123")
            >>> for artifact in artifacts:
            ...     print(f"Artifact: {artifact.name} ({artifact.artifact_type})")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/artifacts",
        )
        records = response.get("records", [])
        return [
            SessionArtifact(**_normalize_session_artifact(item, session_id)) for item in records
        ]

    async def get_context(self, session_id: str) -> Any:
        """
        Get session context information.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``GET /api/v1/sessions/{session_id}/context`` is not served.

        Args:
            session_id: Session ID

        Returns:
            Session context including agent context and memory
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/context",
        )
        return SessionContext(**response)

    async def get_memory_context(
        self,
        session_id: str,
        memory_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Get a session's tiered memory.

        ``GET /api/v1/sessions/{session_id}/memory`` returns
        ``{"data": [{key, value, tier, size, last_access}, ...]}``, where
        ``tier`` is ``hot`` / ``warm`` / ``cold``. The envelope is returned
        as-is.

        Args:
            session_id: Session ID
            memory_type: Deprecated, ignored. The endpoint takes no filter
                parameter, and its ``tier`` vocabulary does not correspond to
                the ``short_term``/``long_term``/``episodic`` values this
                argument was documented with. Filter the returned entries on
                ``tier`` instead.

        Returns:
            ``{"data": [...]}`` — the memory entries for this session.
        """
        if memory_type is not None:
            warnings.warn(
                "get_memory_context(memory_type=...) is deprecated and "
                "ignored — the endpoint accepts no filter parameter. Filter "
                "the returned entries on their `tier` field instead. This "
                "parameter will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )

        # aegis-wire-exempt: DELIBERATE envelope passthrough. The endpoint wraps
        # its payload as {"data": [...]}, and this method returns that envelope
        # UNCHANGED, on purpose -- the docstring above, the `-> dict[str, Any]`
        # annotation and the behaviour all say the same thing, and callers read
        # `["data"]` themselves. Unwrapping it here would be a breaking change
        # to a documented return shape, not a fix. Delete this method and this
        # exemption goes with it.
        return await self._http.request(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/memory",
        )

    async def spawn_subagent(
        self,
        session_id: str,
        subagent_id: str,
        task: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Spawn a subagent within a session.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``POST /api/v1/sessions/{session_id}/subagents`` is not served.
            Subagent spawn events (``type: "subagent_spawn"``) DO appear on
            :meth:`stream_events`, but there is no request-side endpoint to
            trigger a spawn directly.

        Args:
            session_id: Session ID
            subagent_id: ID of the agent to spawn
            task: Task description for the subagent
            metadata: Additional metadata

        Returns:
            Spawned subagent reference
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/sessions/{encode_path_param(session_id)}/subagents",
            json_data={
                "subagent_id": subagent_id,
                "task": task,
                "metadata": metadata or {},
            },
        )
        return Subagent(**response)

    async def list_subagents(self, session_id: str) -> list[Any]:
        """
        List all subagents spawned in a session.

        ``GET /api/v1/sessions/{session_id}/subagents`` returns
        ``{"data": [{id, name, type, status, spawned_at, task, parent_id},
        ...]}``. Those rows are returned as-is rather than as
        :class:`~aegis_sdk.types.Subagent`, whose fields
        (``session_id``/``subagent_id``/``created_at``) the endpoint does not
        emit; aligning that type is a tracked follow-up.

        Args:
            session_id: Session ID

        Returns:
            The subagent rows for this session.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/subagents",
        )
        return response.get("data", [])

    async def stream_messages(self, session_id: str) -> AsyncIterator[SessionMessage]:
        """
        Stream messages from a session using Server-Sent Events (SSE).

        Messages arrive on the unified event stream,
        ``GET /api/v1/sessions/{session_id}/stream``; this method filters it
        for ``type == "message"`` events. Message events are FLAT
        (``{"type": "message", "role": ..., "content": ...}``) with no nested
        ``data`` key, and carry no message id or timestamp, so both are
        synthesized client-side.

        Args:
            session_id: Session ID

        Yields:
            SessionMessage objects as they arrive

        Example:
            >>> async for message in client.sessions.stream_messages("ses_abc123"):
            ...     print(f"[{message.role}] {message.content}")
        """
        async for event in self._http.stream(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/stream",
        ):
            if event.get("type") == "message":
                yield SessionMessage(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role=event.get("role", "assistant"),
                    content=event.get("content", ""),
                    metadata={},
                    created_at=datetime.now(UTC),
                )

    async def stream_events(
        self,
        session_id: str,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream all session events using Server-Sent Events (SSE).

        Events arrive on the unified event stream,
        ``GET /api/v1/sessions/{session_id}/stream``. It has no server-side
        event-type filter, so ``event_types`` is applied client-side.

        Each yielded event is the parsed frame, unchanged::

            {"type": str, "timestamp": str, "data": {...}}

        The event-specific payload is NESTED under ``data``, so read
        ``event["data"][...]`` — the frame itself carries only ``type``,
        ``timestamp`` and a top-level id.

        **Per-agent model.** ``data["model"]`` carries the model the emitting
        agent is actually running, as a ``str``. This is what lets a consumer of
        a multi-agent session show *which model each agent is using* — agents in
        one session do not share a model, so it must be read per event rather
        than resolved once for the session.

        It is ``""`` when the platform could not resolve one, and an empty
        string means UNRESOLVED — never "the default model". The platform
        reports no model rather than naming one it did not resolve, so a consumer
        that fills the blank with a default is inventing an attribution.

        Presence is not uniform across the vocabulary: the key is set on **every
        event the agent-execution bridge maps** (``progress_update``,
        ``subagent_spawned``, ``cost_update``, ``objective_completed``,
        ``objective_failed``, ``escalation_created`` and the rest) and on the two
        auto-claim events, but NOT on ``cancelled`` or ``error``, which the
        session API publishes directly. Read it with ``data.get("model", "")``
        rather than indexing.

        Args:
            session_id: Session ID
            event_types: Filter by event types. The wire types are
                ``progress_update``, ``subagent_spawned``, ``cost_update``,
                ``objective_completed``, ``objective_failed``,
                ``escalation_created``, ``agent_auto_claimed``,
                ``agent_auto_executing``, ``cancelled`` and ``error``.

                The two that carry agent activity are ``progress_update`` — the
                agent's step-by-step work (start, reasoning, messages, tool use,
                posture and human-approval events all map onto this one type) —
                and ``subagent_spawned``, which marks a subagent appearing, with
                its identity in ``data["nodeName"]``. The two auto-claim events
                mark an agent picking up work, and carry ``data["agent_name"]``
                alongside the model.

        Yields:
            Event dictionaries with a ``type`` key, a nested ``data`` payload,
            and event-specific fields

        Example:
            >>> async for event in client.sessions.stream_events(
            ...     "ses_abc123",
            ...     event_types=["progress_update", "subagent_spawned"],
            ... ):
            ...     data = event["data"]
            ...     if event["type"] == "subagent_spawned":
            ...         print(f"{data['nodeName']} started on {data.get('model') or 'unresolved'}")
        """
        async for event in self._http.stream(
            "GET",
            f"/api/v1/sessions/{encode_path_param(session_id)}/stream",
        ):
            if event_types and event.get("type") not in event_types:
                continue
            yield event
