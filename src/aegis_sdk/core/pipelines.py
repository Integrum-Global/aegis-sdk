"""
Agentic OS SDK Pipelines Module.

Provides pipeline management operations including:
- CRUD: Create, Read, Update, Delete, List
- Execution: Sync pipeline execution
"""

import builtins
import warnings
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
        (``ValidationError``), not an opaque 500.

        Args:
            pipeline_id: Pipeline whose graph to replace
            nodes: Node definitions (dicts with node_type + label required)
            connections: Connection definitions (dicts with
                source_node_id + target_node_id required)

        Returns:
            The saved graph result dict

        Raises:
            NotFoundError: If the pipeline doesn't exist or is out of tenant scope
            ValidationError: On a cross-pipeline node/connection id collision (409)

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
        """
        Run a pipeline with inputs and return the finished run record.

        Two requests, both to routes the platform serves:
        ``POST /api/v1/executions/start`` (``{pipelineId, inputs}`` ->
        ``{executionId}``), which answers only once the run has completed or
        failed, then ``GET /api/v1/pipelines/{pipeline_id}/executions/{execution_id}``
        for the run record. Starting a run requires write authority on agents
        (``agents:execute`` for a person, the ``agents:write`` scope for an API
        key).

        This method previously POSTed ``/api/v1/pipelines/{id}/execute``, which no
        router declares, so every call raised ``NotFoundError``.

        Args:
            pipeline_id: Pipeline ID
            inputs: Input values for the pipeline
            wait: DEPRECATED, and has no effect. The server has no asynchronous
                start, so the run has always finished by the time this returns.
                Passing any value emits ``DeprecationWarning``; it will be
                removed in the next minor release.

        Returns:
            PipelineExecution: the run record. ``status`` is ``completed`` or
            ``failed``; a failed run carries ``error``.

        Raises:
            NotFoundError: If the pipeline doesn't exist or belongs to another org
            ValidationError: If the pipeline graph is invalid (the server
                validates before it starts the run)
            AuthorizationError: If the caller lacks write authority on agents
            ServiceError: If the start response carries no ``executionId``

        Example:
            >>> result = await client.pipelines.execute(
            ...     "pipeline_abc123",
            ...     inputs={"topic": "AI Safety", "depth": "detailed"}
            ... )
            >>> print(f"Status: {result.status}")
            >>> print(f"Outputs: {result.outputs}")
        """
        if wait is not None:
            warnings.warn(
                "PipelinesModule.execute(wait=...) is deprecated and has no effect: "
                "the server has no asynchronous start, so the run has already "
                "finished when execute() returns. Omit `wait`; it will be removed "
                "in the next minor release.",
                DeprecationWarning,
                stacklevel=2,
            )
        started = await self._http.request(
            "POST",
            "/api/v1/executions/start",
            json_data={"pipelineId": pipeline_id, "inputs": inputs or {}},
        )
        execution_id = started.get("executionId") if isinstance(started, dict) else None
        if not execution_id:
            raise ServiceError(
                "POST /api/v1/executions/start answered without an executionId, "
                "so the run record cannot be read back",
                details={"response": started},
            )
        return await self.get_execution(pipeline_id, execution_id)

    async def get_execution(self, pipeline_id: str, execution_id: str) -> PipelineExecution:
        """
        Get execution status/result by ID.

        Args:
            pipeline_id: Pipeline ID
            execution_id: Execution ID

        Returns:
            PipelineExecution with status and result

        Raises:
            NotFoundError: If execution doesn't exist
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/executions/{encode_path_param(execution_id)}",
        )
        return PipelineExecution(**response)

    async def list_executions(
        self,
        pipeline_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse[PipelineExecution]:
        """
        List executions for a pipeline.

        ``status`` is applied by the SDK, not by the server: the route refuses a
        ``status`` parameter with 400. Filtering one server page would report a
        ``total`` that disagrees with its items, so when ``status`` is given the
        SDK reads EVERY page of the pipeline's runs, filters them, and pages the
        filtered set -- ``total`` and ``has_next`` then describe the filtered
        runs. That costs one request per 100 runs; omit ``status`` for a single
        request.

        Args:
            pipeline_id: Pipeline ID
            status: Filter by status -- one of ``pending``, ``running``,
                ``completed``, ``failed``, ``cancelled`` (a string or an
                ``ExecutionStatus``)
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            PaginatedResponse of PipelineExecution objects

        Raises:
            ValueError: If ``status`` is not a known execution status, or
                ``page``/``page_size`` is below 1 -- raised before any request
        """
        if page < 1 or page_size < 1:
            raise ValueError(f"page and page_size must be >= 1; got {page}, {page_size}")
        if status is not None:
            return await self._list_executions_with_status(pipeline_id, status, page, page_size)

        params: dict[str, Any] = {"page": page, "page_size": page_size}
        response = await self._http.request(
            "GET",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/executions",
            params=params,
        )

        return PaginatedResponse[PipelineExecution](
            items=[PipelineExecution(**item) for item in response.get("items", [])],
            total=response.get("total", 0),
            page=response.get("page", page),
            page_size=response.get("page_size", page_size),
            has_next=response.get("has_next", False),
        )

    async def _list_executions_with_status(
        self,
        pipeline_id: str,
        status: str,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[PipelineExecution]:
        """Filter a pipeline's runs by status across every server page."""
        # ``ExecutionStatus`` is a str-Enum whose hash is its NAME, not its
        # value, so a member is normalised to its value before any comparison.
        wanted = status.value if isinstance(status, ExecutionStatus) else status
        known = {s.value for s in ExecutionStatus}
        if wanted not in known:
            raise ValueError(f"status must be one of {sorted(known)}; got {status!r}")

        matching = []
        server_page = 1
        while True:
            response = await self._http.request(
                "GET",
                f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/executions",
                params={"page": server_page, "page_size": _EXECUTION_SCAN_PAGE_SIZE},
            )
            items = response.get("items", [])
            matching.extend(item for item in items if item.get("status") == wanted)
            read_so_far = server_page * _EXECUTION_SCAN_PAGE_SIZE
            if (
                not items
                or not response.get("has_next", False)
                or read_so_far >= response.get("total", 0)
            ):
                break
            server_page += 1

        start = (page - 1) * page_size
        window = matching[start : start + page_size]
        return PaginatedResponse[PipelineExecution](
            items=[PipelineExecution(**item) for item in window],
            total=len(matching),
            page=page,
            page_size=page_size,
            has_next=start + len(window) < len(matching),
        )

    async def cancel_execution(self, pipeline_id: str, execution_id: str) -> None:
        """
        Cancel a running execution.

        Args:
            pipeline_id: Pipeline ID
            execution_id: Execution ID to cancel

        Raises:
            NotFoundError: If execution doesn't exist
            ValidationError: If execution already completed
        """
        await self._http.request(
            "POST",
            f"/api/v1/pipelines/{encode_path_param(pipeline_id)}/executions/{encode_path_param(execution_id)}/cancel",
        )

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
