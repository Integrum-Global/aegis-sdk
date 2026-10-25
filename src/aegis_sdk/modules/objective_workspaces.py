"""HTTP client for objective workspaces, rosters, topics and private agent sessions.

This is separate from the general workspace API. Response JSON fields retain
their documented wire shape; actor identity is supplied by the credential.
Collection writes include their trailing slash to avoid redirects.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel, tolerant_null

if TYPE_CHECKING:
    from .._http import HTTPClient

__all__ = [
    "ObjectiveWorkspace",
    "ObjectiveWorkspacesModule",
    "WorkspaceAgentSession",
    "WorkspaceAuditTrail",
    "WorkspaceCondensePreview",
    "WorkspaceHierarchy",
    "WorkspaceProgress",
    "WorkspaceReply",
    "WorkspaceThread",
    "WorkspaceThreadList",
    "WorkspaceThreadMessage",
    "WorkspaceThreadMessageList",
]

_BASE = "/api/v1/objective-workspaces"

#: The collection path, trailing slash INCLUDED. ``POST`` without it answers
#: 307; see the module docstring.
_COLLECTION = f"{_BASE}/"


# ============================================================================
# Response models
# ============================================================================


class ObjectiveWorkspace(TolerantModel):
    """An objective workspace — the raw ``Workspace`` row.

    Returned by every create/attach/update route on this surface as well as the
    two reads, so it is the shape most callers will hold.

    The ``*_json`` fields are JSON-encoded **strings** (``"[]"``), not lists —
    decode before iterating::

        json.loads(workspace.assigned_agent_ids_json or "[]")
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    objective_id: str
    organization_id: str
    workspace_type: str
    classification: str
    contains_classification: str
    environment_type: str
    is_objective_workspace: bool
    is_archived: bool
    inherit_constraints_from_parent: bool
    inherit_knowledge_from_parent: bool
    created_at: str
    updated_at: str
    description: str | None = None
    archived_at: str | None = None
    artifacts_root_path: str | None = None
    parent_workspace_id: str | None = None
    memory_context_json: str | None = None
    # An absent roster is a fresh workspace, and the server's own value for it
    # is "[]" — so the default IS what the server would have sent, which is the
    # condition `tolerant_null` documents for marking a field.
    assigned_agent_ids_json: str = tolerant_null("[]")
    assigned_user_ids_json: str = tolerant_null("[]")
    accessible_knowledge_paths_json: str = tolerant_null("[]")


class WorkspaceProgress(TolerantModel):
    """The rollup from ``GET /{workspace_id}/progress``.

    Counts every objective in the workspace SUBTREE, so a parent reports its
    descendants' work as well as its own. ``progress_percent`` is an integer
    derived server-side from ``completed / total_objectives`` and is ``0`` when
    there are no objectives at all.
    """

    total_objectives: int
    completed: int
    in_progress: int
    failed: int
    progress_percent: int
    total_cost_usd_cents: int = tolerant_null(0)
    total_tokens: int = tolerant_null(0)


class WorkspaceHierarchy(ObjectiveWorkspace):
    """A workspace plus its descendants.

    ``sub_workspaces`` nests recursively, so a caller walking a deep tree should
    walk it iteratively rather than recursing without a bound.
    """

    sub_workspaces: builtins.list[WorkspaceHierarchy] = Field(default_factory=list)


class WorkspaceThread(TolerantModel):
    """A discussion topic on the workspace's rail.

    ``status`` is ``"open"`` until :meth:`ObjectiveWorkspacesModule.resolve_thread`
    closes it. ``outcome`` is deliberately allowed to stay unset through a
    resolve — "nothing follows from this" is a real decision, and the server does
    not substitute a placeholder for it.
    """

    id: str
    organization_id: str
    workspace_id: str | None = None
    title: str
    status: str
    created_by_user_id: str
    created_at: str
    updated_at: str
    outcome: str | None = None
    resolved_at: str | None = None
    resolved_by_user_id: str | None = None


class WorkspaceThreadList(TolerantModel):
    """The ``records``/``total`` envelope from ``GET /{workspace_id}/threads``."""

    records: builtins.list[WorkspaceThread] = Field(default_factory=list)
    total: int = tolerant_null(0)


class WorkspaceThreadMessage(TolerantModel):
    """One post in a topic.

    ``origin`` records whether the prose was written by a person (``"user"``) or
    produced by the platform (an agent/condensed origin). It is validated
    server-side against a closed set, so an unrecognized value is refused at the
    point of posting rather than rendered later as an unknown badge.
    """

    id: str
    organization_id: str
    thread_id: str
    author_user_id: str
    origin: str
    body: str
    created_at: str


class WorkspaceThreadMessageList(TolerantModel):
    """The envelope from ``GET /{workspace_id}/threads/{thread_id}/messages``.

    Ordered oldest-first, which is the opposite of the thread rail's order and is
    deliberate: a rail is scanned for what is NEW, a conversation for what was
    SAID.
    """

    records: builtins.list[WorkspaceThreadMessage] = Field(default_factory=list)
    total: int = tolerant_null(0)


class WorkspaceAuditTrail(TolerantModel):
    """The envelope from ``GET /{workspace_id}/audit-trail``.

    Records are returned **unmodelled**: the audit entry schema is owned by the
    audit subsystem rather than this surface, and the server envelopes them
    precisely so that schema can grow without a breaking change. Modelling them
    here would reintroduce the fragility the envelope avoids.
    """

    records: builtins.list[dict[str, Any]] = Field(default_factory=list)
    total: int = tolerant_null(0)


class WorkspaceAgentSession(TolerantModel):
    """The CALLER'S OWN private session in a workspace.

    There is no session id in any route path and none is accepted: the server
    resolves the session from the verified principal, so there is no id to guess
    and none a caller could substitute for a colleague's. The ``id`` is still
    carried here.

    ``messages_json`` is a JSON-encoded string, not a list.
    """

    id: str
    organization_id: str
    workspace_id: str | None = None
    user_id: str
    status: str
    created_at: str
    updated_at: str
    agent_id: str | None = None
    last_activity_at: str | None = None
    messages_json: str = tolerant_null("[]")


class WorkspaceCondensePreview(TolerantModel):
    """The W8 preview from ``POST /{workspace_id}/agent-session/condense``.

    ⛔ Condensing **writes nothing** — this is a preview for the user to read
    before deciding to post it. An empty ``summary`` means nothing could be
    condensed and ``note`` says why; the client MUST NOT offer to post an empty
    summary, and no placeholder text is ever substituted.
    """

    session_id: str
    summary: str
    note: str | None = None


class WorkspaceReply(TolerantModel):
    """The result of ``POST /{workspace_id}/agent-session/reply``.

    ⛔ This call **runs an agent and spends its budget**. The reply is produced
    through the platform's execution path, so it carries a trust chain, an
    envelope, cost attribution and an audit record — a reply that bypassed that
    path would look identical on screen and carry none of them.

    ``session`` is the updated private session, including the two turns this
    call stored: the caller's (as ``user``) and the agent's (as ``assistant``).
    The agent's turn is the SERVER's record of what execution produced, which is
    why no route here lets a caller address a message as the assistant.
    """

    session: WorkspaceAgentSession
    reply: str
    run_id: str | None = None
    agent_id: str | None = None
    cost_usd: float | None = None


# ============================================================================
# Module
# ============================================================================


class ObjectiveWorkspacesModule:
    """Objective-workspaces SDK module.

    Methods:
        - create(): Create the container for an objective
        - get_by_objective(): Resolve a workspace by its objective
        - create_sub_workspace(): Create a child workspace, sealed on creation
        - add_agents() / remove_agents(): Agent roster
        - add_users(): User roster
        - get_progress(): Progress rollup over the subtree
        - get_hierarchy(): The workspace tree
        - get_audit_trail(): Audit records for the workspace
        - update_memory_context() / set_artifacts_path(): Workspace state
        - list_threads() / create_thread(): The topic rail (W7)
        - list_thread_messages() / post_thread_message(): Posts (W7 + W8)
        - resolve_thread(): Close a topic with its outcome
        - get_agent_session() / append_agent_session_message(): Private session (W6)
        - condense_agent_session(): W8 preview — writes nothing
        - reply_in_agent_session(): Ask the agent (RUNS AN AGENT)

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(api_key="...", base_url="https://your-host")
        >>>
        >>> workspace = await client.objective_workspaces.create(
        ...     objective_id="obj-123", name="Q3 planning"
        ... )
        >>> await client.objective_workspaces.add_users(workspace.id, ["user-456"])
        >>> progress = await client.objective_workspaces.get_progress(workspace.id)
        >>> progress.progress_percent
        0
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize the module with an HTTP client."""
        self._http = http_client

    # -- lifecycle ---------------------------------------------------------

    async def create(
        self,
        objective_id: str,
        name: str | None = None,
        parent_workspace_id: str | None = None,
    ) -> ObjectiveWorkspace:
        """Create the workspace that containers an objective.

        The caller is seeded as the workspace's owner at creation, which is what
        makes the membership fence on every other method reachable: without an
        owner row the workspace is born unsealed and every subsequent write is
        refused.

        Args:
            objective_id: Objective this workspace is for
            name: Optional display name; the server derives one when omitted
            parent_workspace_id: Optional parent, to create a nested workspace

        Returns:
            The created workspace

        Example:
            >>> workspace = await client.objective_workspaces.create(
            ...     objective_id="obj-123", name="Q3 planning"
            ... )
        """
        body: dict[str, Any] = {"objective_id": objective_id}
        if name is not None:
            body["name"] = name
        if parent_workspace_id is not None:
            body["parent_workspace_id"] = parent_workspace_id

        response = await self._http.request("POST", _COLLECTION, json_data=body)
        return ObjectiveWorkspace(**response)

    async def get_by_objective(self, objective_id: str) -> ObjectiveWorkspace:
        """Resolve a workspace by the objective it containers.

        This is the read to use when the objective is known and the workspace id
        is not — the common case after an objective is created elsewhere.

        A non-member receives the **same 404** as an absent objective, so this is
        not an existence oracle either.

        Args:
            objective_id: Objective whose workspace should be read

        Returns:
            The workspace for that objective

        Example:
            >>> workspace = await client.objective_workspaces.get_by_objective("obj-123")
        """
        response = await self._http.request(
            "GET", f"{_BASE}/by-objective/{encode_path_param(objective_id)}"
        )
        return ObjectiveWorkspace(**response)

    async def create_sub_workspace(
        self,
        parent_workspace_id: str,
        objective_id: str,
        assigned_agent_ids: builtins.list[str] | None = None,
        name: str | None = None,
    ) -> ObjectiveWorkspace:
        """Create a child workspace beneath a parent.

        Requires ``admin`` on the PARENT rather than ``viewer``: this extends the
        hierarchy rather than reading it. The child is sealed on creation, and
        any ``assigned_agent_ids`` are inherited as the child's own roster.

        Args:
            parent_workspace_id: Parent workspace
            objective_id: Objective the child is for
            assigned_agent_ids: Optional agents to seed the child's roster with
            name: Optional display name

        Returns:
            The created child workspace

        Example:
            >>> child = await client.objective_workspaces.create_sub_workspace(
            ...     parent_workspace_id="ws-1", objective_id="obj-456"
            ... )
        """
        body: dict[str, Any] = {"objective_id": objective_id}
        if assigned_agent_ids is not None:
            body["assigned_agent_ids"] = assigned_agent_ids
        if name is not None:
            body["name"] = name

        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(parent_workspace_id)}/sub",
            json_data=body,
        )
        return ObjectiveWorkspace(**response)

    # -- rosters -----------------------------------------------------------

    async def add_agents(
        self, workspace_id: str, agent_ids: builtins.list[str]
    ) -> ObjectiveWorkspace:
        """Assign agents to a workspace.

        Args:
            workspace_id: Workspace to write
            agent_ids: Agents to assign; must be non-empty

        Returns:
            The updated workspace

        Example:
            >>> await client.objective_workspaces.add_agents("ws-1", ["agent-1"])
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/agents",
            json_data={"agent_ids": agent_ids},
        )
        return ObjectiveWorkspace(**response)

    async def remove_agents(
        self, workspace_id: str, agent_ids: builtins.list[str]
    ) -> ObjectiveWorkspace:
        """Unassign agents from a workspace.

        ⛔ This is a **POST to a ``/remove`` path, not a DELETE**. A DELETE
        carrying a request body is stripped end-to-end — proxies drop it and so
        does this repository's own web client — so the roster could grow and
        never shrink. The id list travels in a body, as it must.

        Removal is a de-escalation and is deliberately **not** gated on the
        caller still being able to reach the agent: that is precisely the case
        where removing it is most likely to be wanted.

        Args:
            workspace_id: Workspace to write
            agent_ids: Agents to unassign; must be non-empty

        Returns:
            The updated workspace

        Example:
            >>> await client.objective_workspaces.remove_agents("ws-1", ["agent-1"])
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/agents/remove",
            json_data={"agent_ids": agent_ids},
        )
        return ObjectiveWorkspace(**response)

    async def add_users(self, workspace_id: str, user_ids: builtins.list[str]) -> ObjectiveWorkspace:
        """Add users to a workspace's roster.

        Args:
            workspace_id: Workspace to write
            user_ids: Users to add; must be non-empty

        Returns:
            The updated workspace

        Example:
            >>> await client.objective_workspaces.add_users("ws-1", ["user-1"])
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/users",
            json_data={"user_ids": user_ids},
        )
        return ObjectiveWorkspace(**response)

    # -- reads -------------------------------------------------------------

    async def get_progress(self, workspace_id: str) -> WorkspaceProgress:
        """Read the progress rollup for a workspace and its descendants.

        Args:
            workspace_id: Workspace to report on

        Returns:
            Counts and a percentage over the whole subtree

        Example:
            >>> progress = await client.objective_workspaces.get_progress("ws-1")
            >>> progress.completed, progress.total_objectives
            (0, 1)
        """
        response = await self._http.request(
            "GET", f"{_BASE}/{encode_path_param(workspace_id)}/progress"
        )
        return WorkspaceProgress(**response)

    async def get_hierarchy(self, workspace_id: str) -> WorkspaceHierarchy:
        """Read a workspace and everything nested beneath it.

        Args:
            workspace_id: Root of the subtree to read

        Returns:
            The workspace with ``sub_workspaces`` nested recursively

        Example:
            >>> tree = await client.objective_workspaces.get_hierarchy("ws-1")
            >>> len(tree.sub_workspaces)
            0
        """
        response = await self._http.request(
            "GET", f"{_BASE}/{encode_path_param(workspace_id)}/hierarchy"
        )
        return WorkspaceHierarchy(**response)

    async def get_audit_trail(
        self, workspace_id: str, include_descendants: bool | None = None
    ) -> WorkspaceAuditTrail:
        """Read the workspace audit records and server-reported total.

        include_descendants is omitted by default for compatibility with
        deployments that do not accept that query parameter. Pass True/False
        only when the deployment documents support. Totals depend on the
        deployment's filtering and visible records; compare the same explicit
        workspace id when checking changes over time.
        """
        params: dict[str, Any] | None = None
        if include_descendants is not None:
            params = {"include_descendants": include_descendants}

        response = await self._http.request(
            "GET",
            f"{_BASE}/{encode_path_param(workspace_id)}/audit-trail",
            params=params,
        )
        return WorkspaceAuditTrail(**response)

    # -- workspace state ---------------------------------------------------

    async def update_memory_context(
        self, workspace_id: str, memory_data: dict[str, Any]
    ) -> ObjectiveWorkspace:
        """Replace the workspace's memory context.

        The value is stored as JSON and is returned by later reads as the
        ``memory_context_json`` string.

        Args:
            workspace_id: Workspace to write
            memory_data: Memory context object to store

        Returns:
            The updated workspace

        Example:
            >>> await client.objective_workspaces.update_memory_context(
            ...     "ws-1", {"notes": "kickoff done"}
            ... )
        """
        response = await self._http.request(
            "PATCH",
            f"{_BASE}/{encode_path_param(workspace_id)}/memory",
            json_data={"memory_data": memory_data},
        )
        return ObjectiveWorkspace(**response)

    async def set_artifacts_path(
        self, workspace_id: str, artifacts_path: str
    ) -> ObjectiveWorkspace:
        """Set the workspace's artifact root path.

        Args:
            workspace_id: Workspace to write
            artifacts_path: Path the workspace's artifacts live under

        Returns:
            The updated workspace

        Example:
            >>> await client.objective_workspaces.set_artifacts_path("ws-1", "/data/ws-1")
        """
        response = await self._http.request(
            "PATCH",
            f"{_BASE}/{encode_path_param(workspace_id)}/artifacts-path",
            json_data={"artifacts_path": artifacts_path},
        )
        return ObjectiveWorkspace(**response)

    # -- discussion: topics (W7) -------------------------------------------

    async def list_threads(self, workspace_id: str) -> WorkspaceThreadList:
        """List the workspace's discussion topics — the rail.

        Args:
            workspace_id: Workspace to read

        Returns:
            The topic envelope, newest activity first

        Example:
            >>> threads = await client.objective_workspaces.list_threads("ws-1")
            >>> [t.title for t in threads.records]
            []
        """
        response = await self._http.request(
            "GET", f"{_BASE}/{encode_path_param(workspace_id)}/threads"
        )
        return WorkspaceThreadList(**response)

    async def create_thread(self, workspace_id: str, title: str) -> WorkspaceThread:
        """Open a discussion topic.

        Args:
            workspace_id: Workspace to write
            title: Topic title; must be non-empty

        Returns:
            The created topic

        Example:
            >>> thread = await client.objective_workspaces.create_thread("ws-1", "Sequencing")
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/threads",
            json_data={"title": title},
        )
        return WorkspaceThread(**response)

    async def list_thread_messages(
        self, workspace_id: str, thread_id: str
    ) -> WorkspaceThreadMessageList:
        """List the posts in a topic, oldest first.

        Args:
            workspace_id: Workspace owning the topic
            thread_id: Topic to read

        Returns:
            The post envelope

        Example:
            >>> posts = await client.objective_workspaces.list_thread_messages("ws-1", "wsthr-1")
            >>> posts.records[0].origin
            'user'
        """
        response = await self._http.request(
            "GET",
            f"{_BASE}/{encode_path_param(workspace_id)}/threads/"
            f"{encode_path_param(thread_id)}/messages",
        )
        return WorkspaceThreadMessageList(**response)

    async def post_thread_message(
        self, workspace_id: str, thread_id: str, body: str, origin: str = "user"
    ) -> WorkspaceThreadMessage:
        """Post a message to a topic.

        This is also the route the W8 condensed summary posts through, carrying
        ``origin="agent_condensed"``. The server enforces the closed set of
        origin values; this SDK forwards the string without validating it.
        There is deliberately no separate publish
        route — the thing published is a message in a topic, and a second write
        path would let attribution drift from this one.

        Args:
            workspace_id: Workspace owning the topic
            thread_id: Topic to post into
            body: The post body; must be non-empty
            origin: Whether the prose is the caller's (``"user"``) or platform-
                produced. Validated server-side against a closed set.

        Returns:
            The created post

        Example:
            >>> await client.objective_workspaces.post_thread_message(
            ...     "ws-1", "wsthr-1", "Proceeding with option B"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/threads/"
            f"{encode_path_param(thread_id)}/messages",
            json_data={"body": body, "origin": origin},
        )
        return WorkspaceThreadMessage(**response)

    async def resolve_thread(
        self, workspace_id: str, thread_id: str, outcome: str | None = None
    ) -> WorkspaceThread:
        """Close a topic, optionally recording its outcome.

        ``outcome`` is genuinely optional and stays unset when omitted — "we
        decided nothing follows from this" is a real decision, and a placeholder
        default would record one nobody made.

        Args:
            workspace_id: Workspace owning the topic
            thread_id: Topic to close
            outcome: Optional recorded outcome

        Returns:
            The resolved topic

        Example:
            >>> await client.objective_workspaces.resolve_thread(
            ...     "ws-1", "wsthr-1", outcome="Shipped option B"
            ... )
        """
        body: dict[str, Any] = {}
        if outcome is not None:
            body["outcome"] = outcome

        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/threads/"
            f"{encode_path_param(thread_id)}/resolve",
            json_data=body,
        )
        return WorkspaceThread(**response)

    # -- private agent session (W6/W8) -------------------------------------

    async def get_agent_session(self, workspace_id: str) -> WorkspaceAgentSession:
        """Read the CALLER'S OWN private agent session.

        No session id is accepted, by design: the server resolves the session
        from the verified principal, so there is no id to guess and none a caller
        could substitute for a colleague's. A caller who somehow learned another's
        session id still receives the same 404 as an absent session — the refusal
        never distinguishes "absent" from "not yours", because that distinction
        would confirm a named colleague had been active in the workspace.

        ⚠ This is a ``GET`` that can WRITE: the server creates the session row if
        the caller has none. It is therefore refused on an unsealed workspace
        like any other write.

        Args:
            workspace_id: Workspace whose session should be resolved

        Returns:
            The caller's session, created if it did not exist

        Example:
            >>> session = await client.objective_workspaces.get_agent_session("ws-1")
            >>> session.user_id
            'user-1'
        """
        response = await self._http.request(
            "GET", f"{_BASE}/{encode_path_param(workspace_id)}/agent-session"
        )
        return WorkspaceAgentSession(**response)

    async def append_agent_session_message(
        self, workspace_id: str, role: str, content: str
    ) -> WorkspaceAgentSession:
        """Append one turn to the caller's own private session.

        The server enforces the closed set of role values; the SDK forwards
        the string without validating it. ``role`` is accepted here because
        the caller is declaring a turn. That is
        exactly why the reply route does NOT accept one — see
        :meth:`reply_in_agent_session`.

        Args:
            workspace_id: Workspace owning the session
            role: Role to record this turn as (e.g. ``"user"``)
            content: Turn content; must be non-empty

        Returns:
            The updated session

        Example:
            >>> await client.objective_workspaces.append_agent_session_message(
            ...     "ws-1", "user", "Draft the outline"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/agent-session/messages",
            json_data={"role": role, "content": content},
        )
        return WorkspaceAgentSession(**response)

    async def condense_agent_session(self, workspace_id: str) -> WorkspaceCondensePreview:
        """Preview a condensed summary of the caller's session — W8.

        ⛔ **Writes no summary.** The user reads this, then posts it themselves
        through :meth:`post_thread_message` with ``origin="agent_condensed"`` and
        their own id as author. An empty ``summary`` means nothing could be
        condensed; ``note`` says why, and nothing else is substituted.

        ⚠ The call is still conditionally MUTATING — it creates the session row
        if the caller has none — so it is refused on an unsealed workspace.

        Args:
            workspace_id: Workspace whose session should be condensed

        Returns:
            The preview; check ``summary`` before offering to post it

        Example:
            >>> preview = await client.objective_workspaces.condense_agent_session("ws-1")
            >>> if preview.summary:
            ...     print(preview.summary)
        """
        response = await self._http.request(
            "POST", f"{_BASE}/{encode_path_param(workspace_id)}/agent-session/condense"
        )
        return WorkspaceCondensePreview(**response)

    async def reply_in_agent_session(self, workspace_id: str, content: str) -> WorkspaceReply:
        """Ask the workspace's agent for a reply — W6.

        ⛔ **THIS RUNS AN AGENT AND SPENDS ITS BUDGET.** It is gated on the
        platform's ``agents:execute`` permission in addition to the persona and
        membership gates every other method here shares — a reply is an
        execution, not a read, and this surface must not become a way to spend an
        agent's budget without the permission that governs spending it.

        ⚠ Consequence worth knowing before you debug a refusal: ``agents:execute``
        is held by ``developer``, ``user``, ``operator`` and ``manager``, and NOT
        by ``architect`` or ``admin``. A caller whose ONLY role is architect or
        admin passes the persona gate and is then refused here by RBAC. That is
        the intended governance outcome — those roles may read a workspace
        without spending an agent in it — but it presents as a failure unless you
        know it is a refusal.

        The reply is produced through the platform's execution path, so it
        carries a trust chain, an envelope, cost attribution and an audit record.

        Args:
            workspace_id: Workspace to run in
            content: The message to the agent; must be non-empty

        Returns:
            The reply, the updated session, and the run's cost/identity

        Example:
            >>> result = await client.objective_workspaces.reply_in_agent_session(
            ...     "ws-1", "Summarise where we are"
            ... )
            >>> result.reply
            '...'
        """
        response = await self._http.request(
            "POST",
            f"{_BASE}/{encode_path_param(workspace_id)}/agent-session/reply",
            json_data={"content": content},
        )
        return WorkspaceReply(**response)
