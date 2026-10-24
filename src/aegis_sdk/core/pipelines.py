"""
Agentic OS SDK Pipelines Module.

Provides pipeline management operations including:
- CRUD: Create, Read, Update, Delete, List
- Execution: Sync pipeline execution
"""

import asyncio
import builtins
import warnings
import weakref
from typing import TYPE_CHECKING, Any

from .._http import encode_path_param, unwrap_envelope
from ..exceptions import ServiceError
from .models import (
    ExecutionStatus,
    PaginatedResponse,
    Pipeline,
    PipelineConnection,
    PipelineCreate,
    PipelineExecution,
    PipelineNode,
    PipelineUpdate,
)

if TYPE_CHECKING:
    from .._http import HTTPClient


# ``GET /api/v1/pipelines/{id}/executions`` caps ``page_size`` at 100
# (``Query(50, ge=1, le=100)``). A status-filtered listing reads every page at
# that size, so this is the fewest requests the route allows.
_EXECUTION_SCAN_PAGE_SIZE = 100



def _execution_from_status_response(payload: Any) -> dict[str, Any]:
    """Normalize the public execution response without inventing a run state."""
    if not isinstance(payload, dict):
        raise ServiceError("Execution response must be an object")
    execution_id = payload.get("id")
    pipeline_id = payload.get("pipelineId", payload.get("pipeline_id"))
    if not isinstance(execution_id, str) or not execution_id:
        raise ServiceError("Execution response has no execution id")
    if not isinstance(pipeline_id, str) or not pipeline_id:
        raise ServiceError("Execution response has no pipeline id")
    nodes = payload.get("nodeExecutions", payload.get("node_results")) or []
    return {
        "id": execution_id,
        "pipeline_id": pipeline_id,
        "status": payload.get("status") or ExecutionStatus.UNKNOWN,
        "inputs": payload.get("inputs") or {},
        "outputs": payload.get("outputs"),
        "error": payload.get("error"),
        "node_results": [
            {
                "node_id": node.get("nodeId", node.get("node_id", "")),
                "status": node.get("status") or ExecutionStatus.UNKNOWN.value,
                "start_time": node.get("startTime", node.get("start_time")),
                "end_time": node.get("endTime", node.get("end_time")),
                "error": node.get("error"),
                "output": node.get("output"),
            }
            for node in nodes if isinstance(node, dict)
        ],
        "started_at": payload.get("startTime", payload.get("started_at")),
        "completed_at": payload.get("endTime", payload.get("completed_at")),
    }


class PipelinesModule:
    """
    Pipeline management operations.

    Provides full lifecycle management for pipelines including:
    - CRUD operations (create, read, update, delete, list)
    - Execution with inputs

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # List pipelines
        ...     pipelines = await client.pipelines.list()
        ...
        ...     # Create pipeline
        ...     pipeline = await client.pipelines.create(
        ...         name="Research Pipeline",
        ...         pattern="sequential",
        ...         nodes=[...]
        ...     )
        ...
        ...     # Execute pipeline
        ...     result = await client.pipelines.execute(
        ...         pipeline.id,
        ...         inputs={"topic": "AI Safety"}
        ...     )
    """

    def __init__(self, http_client: "HTTPClient"):
        """
        Initialize pipelines module.

        Args:
            http_client: Internal HTTP client instance
        """
        self._http = http_client
        # Created on first sync call only; see ``list_node_types_sync``.
        self._sync_loop: asyncio.AbstractEventLoop | None = None

    async def list(
        self,
        workspace_id: str | None = None,
        pattern: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[Pipeline]:
        """
        List pipelines with optional filters.

        Args:
            workspace_id: Filter by workspace
            pattern: Filter by pipeline pattern (sequential, parallel, etc.)
            page: Page number (1-indexed)
            page_size: Items per page (max 100)

        Returns:
            PaginatedResponse containing Pipeline objects

        Example:
            >>> result = await client.pipelines.list(workspace_id="ws_abc123")
            >>> print(f"Found {result.total} pipelines")
            >>> for pipeline in result.items:
            ...     print(f"  - {pipeline.name}: {pipeline.pattern}")
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if workspace_id:
            params["workspace_id"] = workspace_id
        if pattern:
            params["pattern"] = pattern

        response = await self._http.request("GET", "/api/v1/pipelines", params=params)

        # Bare array — no pagination metadata to read from. Retained for any
        # endpoint or older build that answers this way.
        if isinstance(response, list):
            return PaginatedResponse[Pipeline](
                items=[Pipeline(**item) for item in response],
                total=len(response),
                page=1,
                page_size=len(response),
                has_next=False,
            )

        # The endpoint answers ``{"data": [...], "total": N}``: the pipelines
        # are under ``data`` and the count is its sibling. This method read
        # ``items`` only, which that shape never carries — so it returned an
        # EMPTY page for every caller, indistinguishable from an account with
        # no pipelines. ``items`` is still honoured below so a build serving
        # the older shape does not regress.
        payload = unwrap_envelope(response)
        items = payload if isinstance(payload, list) else response.get("items", [])

        return PaginatedResponse[Pipeline](
            items=[Pipeline(**item) for item in items],
            # Defaulting to the number of items received, rather than to zero:
            # a page reporting total=0 while carrying rows is never right.
            total=response.get("total", len(items)),
            page=response.get("page", page),
            page_size=response.get("page_size", page_size),
            has_next=response.get("has_next", False),
        )

    async def create(
        self,
        name: str,
        pattern: str = "sequential",
        description: str | None = None,
        nodes: builtins.list[dict[str, Any]] | None = None,
        connections: builtins.list[dict[str, Any]] | None = None,
        workspace_id: str | None = None,
    ) -> Pipeline:
        """
        Create a new pipeline.

        Args:
            name: Pipeline name
            pattern: Execution pattern (sequential, parallel, conditional, etc.)
            description: Optional description
            nodes: Pipeline node definitions
            connections: Connections between nodes
            workspace_id: Target workspace

        Returns:
            Created Pipeline object

        Raises:
            ValidationError: If required fields missing or invalid
            AuthorizationError: If not allowed to create pipelines

        Example:
            >>> pipeline = await client.pipelines.create(
            ...     name="Research Pipeline",
            ...     pattern="sequential",
            ...     nodes=[
            ...         {"id": "n1", "name": "Research", "node_type": "agent", "agent_id": "agent_1"},
            ...         {"id": "n2", "name": "Summarize", "node_type": "agent", "agent_id": "agent_2"}
            ...     ],
            ...     connections=[
            ...         {"source_node_id": "n1", "target_node_id": "n2"}
            ...     ]
            ... )
        """
        # Convert dict nodes to proper format
        node_list = []
        if nodes:
            for node in nodes:
                if isinstance(node, dict):
                    node_list.append(PipelineNode(**node))
                else:
                    node_list.append(node)

        connection_list = []
        if connections:
            for conn in connections:
                if isinstance(conn, dict):
                    connection_list.append(PipelineConnection(**conn))
                else:
                    connection_list.append(conn)

        create_data = PipelineCreate(
            name=name,
            pattern=pattern,
            description=description,
            nodes=node_list,
            connections=connection_list,
            workspace_id=workspace_id,
        )
        response = await self._http.request(
            "POST",
            "/api/v1/pipelines",
            json_data=create_data.model_dump(exclude_none=True, mode="json"),
        )
        return Pipeline(**unwrap_envelope(response))

    async def get(self, pipeline_id: str) -> Pipeline:
        """
        Get pipeline by ID.

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Pipeline object

        Raises:
            NotFoundError: If pipeline doesn't exist

        Example:
            >>> pipeline = await client.pipelines.get("pipeline_abc123")
            >>> print(f"Pipeline: {pipeline.name} ({pipeline.pattern})")
            >>> print(f"Nodes: {len(pipeline.nodes)}")
        """
        response = await self._http.request(
            "GET", f"/api/v1/pipelines/{encode_path_param(pipeline_id)}"
        )
        return Pipeline(**unwrap_envelope(response))

    async def update(self, pipeline_id: str, **kwargs: Any) -> Pipeline:
        """
        Update pipeline fields.

        Args:
            pipeline_id: Pipeline ID
            **kwargs: Fields to update (name, description, pattern, nodes, connections)

        Returns:
            Updated Pipeline object

        Raises:
            NotFoundError: If pipeline doesn't exist
            ValidationError: If update data is invalid

        Example:
            >>> pipeline = await client.pipelines.update(
            ...     "pipeline_abc123",
            ...     name="Updated Pipeline",
            ...     description="New description"
            ... )
        """
        update_data = PipelineUpdate(**kwargs)
        response = await self._http.request(
            "PUT",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}",
            json_data=update_data.model_dump(exclude_none=True, mode="json"),
        )
        return Pipeline(**unwrap_envelope(response))

    async def delete(self, pipeline_id: str) -> None:
        """
        Delete pipeline.

        Args:
            pipeline_id: Pipeline ID

        Raises:
            NotFoundError: If pipeline doesn't exist
            AuthorizationError: If not allowed to delete

        Example:
            >>> await client.pipelines.delete("pipeline_abc123")
        """
        await self._http.request("DELETE", f"/api/v1/pipelines/{encode_path_param(pipeline_id)}")

    async def duplicate(self, pipeline_id: str, name: str) -> Pipeline:
        """
        Duplicate an existing pipeline.

        Creates a copy of the pipeline with a new name and ID.

        Args:
            pipeline_id: Source pipeline ID
            name: Name for the duplicated pipeline

        Returns:
            New Pipeline object (copy)

        Raises:
            NotFoundError: If source pipeline doesn't exist

        Example:
            >>> copy = await client.pipelines.duplicate(
            ...     "pipeline_abc123",
            ...     name="Research Pipeline (Copy)"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/duplicate",
            json_data={"name": name},
        )
        return Pipeline(**unwrap_envelope(response))

    async def save_graph(
        self,
        pipeline_id: str,
        nodes: builtins.list[dict[str, Any]],
        connections: builtins.list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Persist the complete node/connection graph a user builds in the editor.

        Replaces the pipeline's existing nodes and connections wholesale.

        Verified route: ``PUT /api/v1/pipelines/{pipeline_id}/graph`` with the ``GraphSave`` body: ``{"nodes": [...],
        "connections": [...]}``. Each node is a ``NodeCreate``: required ``node_type`` + ``label``,
        optional ``id``/``agent_id``/``position_x``/``position_y``/``config``.
        Each connection is a ``ConnectionCreate``: ``source_node_id`` +
        ``target_node_id`` (required), optional ``source_handle`` (default
        ``"output"``) / ``target_handle`` (default ``"input"``) / ``condition``.
        The backend wraps the saved graph as ``{"data": result}``; this method
        unwraps ``data``. A cross-pipeline id collision surfaces as HTTP 409
        (``ConflictError``), not an opaque 500.

        Args:
            pipeline_id: Pipeline whose graph to replace
            nodes: Node definitions (dicts with node_type + label required)
            connections: Connection definitions (dicts with
                source_node_id + target_node_id required)

        Returns:
            The saved graph result dict

        Raises:
            NotFoundError: If the pipeline doesn't exist or is out of tenant scope
            ConflictError: On a cross-pipeline node/connection id collision (409)

        Example:
            >>> await client.pipelines.save_graph(
            ...     "pipeline_abc123",
            ...     nodes=[
            ...         {"id": "n1", "node_type": "agent", "label": "Research",
            ...          "agent_id": "agent_1", "position_x": 100, "position_y": 50},
            ...         {"id": "n2", "node_type": "agent", "label": "Summarize",
            ...          "agent_id": "agent_2", "position_x": 400, "position_y": 50},
            ...     ],
            ...     connections=[
            ...         {"source_node_id": "n1", "target_node_id": "n2"},
            ...     ],
            ... )
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/graph",
            json_data={"nodes": nodes, "connections": connections},
        )
        return unwrap_envelope(response)

    # -------------------------------------------------------------------------
    # Workflows (execution-graph views)
    #
    # The backend ``/api/v1/workflows`` routes are a read-only projection of
    # pipeline EXECUTIONS into the execution-graph viewer shape (see
    # — "Read-only projection of pipeline
    # executions"). They are hosted on this already-wired module because
    # ``client.py`` is out of scope for this module and workflows are, by the
    # backend's own framing, a view over pipeline executions.
    # -------------------------------------------------------------------------

    async def list_workflows(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[dict[str, Any]]:
        """
        List pipeline executions as execution-graph summaries.

        Verified route: ``GET /api/v1/workflows`` — query params are ``status``,
        ``limit`` (1..100), ``offset`` (>=0). Response envelope is
        ``WorkflowListResponse``:
        ``{"data": [WorkflowExecutionResponse...], "total": int}`` in
        snake_case (``id``, ``name``, ``status``, ``nodes``, ``edges``,
        ``session_id``, ``created_at`` per). There is no SDK model for a
        workflow-execution graph, so items are returned as raw dicts inside a
        :class:`PaginatedResponse`.

        Args:
            status: Filter by projected execution status
            limit: Items per page (1..100)
            offset: Pagination offset

        Returns:
            PaginatedResponse whose items are workflow-execution graph dicts

        Example:
            >>> result = await client.pipelines.list_workflows(status="running")
            >>> print(f"{result.total} executions")
            >>> for wf in result.items:
            ...     print(f"  - {wf['name']}: {wf['status']}")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/workflows", params=params)

        items = response.get("data", [])
        total = response.get("total", len(items))
        return PaginatedResponse[dict[str, Any]](
            items=items,
            total=total,
            page=(offset // limit) + 1 if limit else 1,
            page_size=limit,
            has_next=(offset + len(items)) < total,
        )

    async def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """
        Get one pipeline execution's node/edge graph + live status.

        Verified route: ``GET /api/v1/workflows/{workflow_id}`` — ``workflow_id`` is a
        pipeline-execution id. Returns ``WorkflowExecutionResponse``: ``{"id", "name", "status",
        "nodes": [...], "edges": [...], "session_id", "created_at"}`` in
        snake_case. Fail-closed 404 on missing OR cross-tenant. Returned as a
        raw dict (no SDK model for the execution-graph shape).

        Args:
            workflow_id: Pipeline-execution id to project

        Returns:
            The execution-graph projection dict

        Raises:
            NotFoundError: If the execution doesn't exist or is out of tenant scope

        Example:
            >>> wf = await client.pipelines.get_workflow("exec_abc123")
            >>> print(f"{wf['name']}: {wf['status']}")
            >>> print(f"Nodes: {len(wf['nodes'])}, Edges: {len(wf['edges'])}")
        """
        return await self._http.request(
            "GET", f"/api/v1/workflows/{encode_path_param(workflow_id)}"
        )

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    async def execute(
        self,
        pipeline_id: str,
        inputs: dict[str, Any] | None = None,
        wait: bool | None = None,
    ) -> PipelineExecution:
        """Start a pipeline; optionally read its reported result.

        POST /api/v1/executions/start is synchronous and returns an execution id.
        Omit ``wait`` (or pass True) to fetch status and outputs afterwards.
        False skips only that read: the returned status is UNKNOWN, because the
        start response reports no status. False does not make the server async.
        Passing wait explicitly remains deprecated and emits DeprecationWarning.
        """
        if wait is not None:
            warnings.warn(
                "PipelinesModule.execute(wait=...) is deprecated. The start is synchronous; "
                "False only skips result retrieval. Omit wait to read the reported result.",
                DeprecationWarning,
                stacklevel=2,
            )
        started = await self._http.request(
            "POST", "/api/v1/executions/start",
            json_data={"pipelineId": pipeline_id, "inputs": inputs or {}},
        )
        execution_id = started.get("executionId") if isinstance(started, dict) else None
        if not isinstance(execution_id, str) or not execution_id:
            raise ServiceError("Start response has no executionId", details={"response": started})
        if wait is False:
            return PipelineExecution(
                id=execution_id, pipeline_id=pipeline_id,
                status=ExecutionStatus.UNKNOWN, inputs=inputs or {},
            )
        return await self.get_execution(pipeline_id, execution_id)

    async def get_execution(self, pipeline_id: str, execution_id: str) -> PipelineExecution:
        """Read a public execution record and verify its requested pipeline/id pair."""
        response = await self._http.request(
            "GET", f"/api/v1/executions/{encode_path_param(execution_id)}",
        )
        execution = _execution_from_status_response(response)
        if execution["id"] != execution_id or execution["pipeline_id"] != pipeline_id:
            raise ValueError("Execution response does not match the requested pipeline/id pair")
        return PipelineExecution(**execution)

    async def list_executions(
        self, pipeline_id: str, status: str | None = None,
        page: int = 1, page_size: int = 50,
    ) -> PaginatedResponse[PipelineExecution]:
        """List execution history, retaining SDK-wide status filtering and totals.

        The server history endpoint accepts page/page_size. A status filter is
        applied across every page by the SDK, never sent as an ignored parameter.
        """
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("page must be >= 1 and page_size must be between 1 and 100")
        if status is not None:
            return await self._list_executions_with_status(pipeline_id, status, page, page_size)
        response = await self._http.request(
            "GET", f"/api/v1/executions/history/{encode_path_param(pipeline_id)}",
            params={"page": page, "page_size": page_size},
        )
        items = [PipelineExecution(**_execution_from_status_response(item))
                 for item in response.get("executions", response.get("items", []))]
        if any(item.pipeline_id != pipeline_id for item in items):
            raise ValueError("Execution history contains a different pipeline")
        total = response.get("total", 0)
        return PaginatedResponse[PipelineExecution](
            items=items, total=total, page=response.get("page", page),
            page_size=response.get("page_size", page_size), has_next=page * page_size < total,
        )

    async def _list_executions_with_status(
        self, pipeline_id: str, status: str, page: int, page_size: int,
    ) -> PaginatedResponse[PipelineExecution]:
        """Filter all public history pages before computing the caller's page."""
        wanted = status.value if isinstance(status, ExecutionStatus) else status
        known = {s.value for s in ExecutionStatus}
        if wanted not in known:
            raise ValueError(f"status must be one of {sorted(known)}; got {status!r}")
        matching: list[PipelineExecution] = []
        server_page = 1
        while True:
            result = await self.list_executions(
                pipeline_id, page=server_page, page_size=_EXECUTION_SCAN_PAGE_SIZE,
            )
            matching.extend(item for item in result.items if getattr(item.status, "value", item.status) == wanted)
            if not result.items or not result.has_next:
                break
            server_page += 1
        start = (page - 1) * page_size
        window = matching[start:start + page_size]
        return PaginatedResponse[PipelineExecution](
            items=window, total=len(matching), page=page, page_size=page_size,
            has_next=start + len(window) < len(matching),
        )

    async def cancel_execution(self, pipeline_id: str, execution_id: str) -> None:
        """Verify the pipeline/id pair before asking the public execution endpoint to stop."""
        await self.get_execution(pipeline_id, execution_id)
        await self._http.request(
            "POST", f"/api/v1/executions/{encode_path_param(execution_id)}/stop",
        )

    # -------------------------------------------------------------------------
    # Node-type catalogue
    # -------------------------------------------------------------------------

    async def list_node_types(self) -> builtins.list[dict[str, Any]]:
        """
        List every pipeline node type the deployment has registered.

        Covers the built-in types and every node a deployment pack added. Each
        entry is a dict with ``type``, ``name``, ``description``, ``origin``
        (``"builtin"`` or ``"pack:<pack_id>"``), ``citation``, ``binding``
        (``None`` for built-ins), ``params`` (each with ``key``, ``label``,
        ``type``, ``default``, ``required``, ``min``, ``max``, ``choices``),
        ``inputs`` and ``outputs`` (each with ``name``, ``type``,
        ``description``).

        Verified route: ``GET /api/v1/pipelines/node-types``, which answers
        ``{"data": [...]}``; this method returns the unwrapped list. Requires
        the same authorization as reading pipelines (``agents:read``).

        Returns:
            The registered node types, in the server's order (built-ins
            first).

        Raises:
            ServiceError: The server answered with something other than a
                list of node types. Raised rather than returning an empty list,
                because an empty catalogue is indistinguishable from a
                deployment with no node types at all.

        Example:
            >>> for node_type in await client.pipelines.list_node_types():
            ...     print(node_type["type"], node_type["origin"])
        """
        response = await self._http.request("GET", "/api/v1/pipelines/node-types")
        payload = unwrap_envelope(response)
        if not isinstance(payload, builtins.list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise ServiceError(
                "Unexpected response from GET /api/v1/pipelines/node-types: "
                "expected {'data': [<node type>, ...]}",
                details={"response_type": type(response).__name__},
            )
        return payload

    def list_node_types_sync(self) -> builtins.list[dict[str, Any]]:
        """
        Blocking form of :meth:`list_node_types`, for scripts without an event loop.

        Runs on an event loop owned by this module and reused across sync
        calls. It is deliberately NOT ``asyncio.run``: that closes its loop on
        return, and the client's pooled connections belong to the loop that
        opened them, so a second sync call would reuse a connection bound to a
        closed loop.

        Use ONE mode per client. Connections opened here belong to this
        module's private loop, and connections opened under your own loop
        belong to that one; mixing the two on one client can hand a request a
        connection from the other loop.

        Raises:
            RuntimeError: Called from a thread that is already running an event
                loop. Blocking there would stall that loop; ``await
                list_node_types()`` instead.
            ServiceError: As :meth:`list_node_types`.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "list_node_types_sync() cannot run inside a running event loop; "
                "use 'await client.pipelines.list_node_types()' instead"
            )
        if self._sync_loop is None or self._sync_loop.is_closed():
            loop = asyncio.new_event_loop()
            # Close the loop when this module is garbage-collected, so a
            # short-lived client does not leak it.
            weakref.finalize(self, loop.close)
            self._sync_loop = loop
        return self._sync_loop.run_until_complete(self.list_node_types())

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    async def validate(self, pipeline_id: str) -> dict[str, Any]:
        """
        Validate pipeline configuration.

        Checks for:
        - Node connectivity
        - Missing required configurations
        - Circular dependencies
        - Agent availability

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Validation result with any warnings or errors

        Example:
            >>> validation = await client.pipelines.validate("pipeline_abc123")
            >>> if validation["valid"]:
            ...     print("Pipeline is valid!")
            >>> else:
            ...     for error in validation["errors"]:
            ...         print(f"Error: {error}")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/validate",
        )
        # The endpoint answers ``{"data": {"valid": ..., "errors": [...]}}``.
        # The documented contract above — and the example in it — has always
        # been the INNER result, so unwrapping brings the behaviour into line
        # with the documentation rather than changing the contract: before
        # this, ``validation["valid"]`` raised KeyError on every call.
        return unwrap_envelope(response)
