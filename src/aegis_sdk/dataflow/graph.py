"""Data-lineage GRAPH surface — the `/api/v1/data-governance/lineage` routes.

A distinct surface from ``lineage.py`` despite the shared word. That module
records what an external agent DID (invocations, cost, tokens, errors); this one
records how DATA MOVES — typed nodes joined by typed edges, traversable upstream
and downstream. A partner wiring a pipeline registers its nodes and edges here
and then asks what breaks if a source changes.

Two of this router's seven lineage routes were already reachable through
``modules/governance.py`` (``/lineage/graph`` and ``/lineage/nodes/{id}/impact``);
the five WRITE and TRAVERSAL routes below were not, so a partner could read an
impact analysis of a graph they had no way to build. This module closes that,
and deliberately does NOT re-declare the two covered routes — a second client
for one endpoint is two contracts to keep in agreement.

Every route below is derived from the platform's data-governance router:

    POST /api/v1/data-governance/lineage/nodes                  -> create_node()
    GET  /api/v1/data-governance/lineage/nodes/{id}             -> get_node()
    GET  /api/v1/data-governance/lineage/nodes/{id}/upstream    -> upstream()
    GET  /api/v1/data-governance/lineage/nodes/{id}/downstream  -> downstream()
    POST /api/v1/data-governance/lineage/edges                  -> create_edge()

⚠ THIS ROUTER SPEAKS camelCase ON THE WIRE, both directions. The request models
alias every field (``nodeType``, ``sourceNodeId``) and the responses are emitted
in camelCase. The models below therefore serialise ``by_alias=True`` and parse
``populate_by_name=True``, so the Python caller writes snake_case and the wire
stays exactly what the server declares. Sending snake_case here does not error —
the server's aliased fields simply do not bind, and a required field arrives
missing as a 422 that names a key the caller never typed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


class LineageNode(TolerantModel):
    """A node in the data-lineage graph (``LineageNodeResponse``).

    ``schema_def`` carries the server's ``schema`` field, renamed because
    ``schema`` shadows a Pydantic ``BaseModel`` member. The alias keeps the wire
    name correct in both directions; only the Python attribute differs.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    organization_id: str | None = Field(None, alias="organizationId")
    node_type: str | None = Field(None, alias="nodeType")
    name: str | None = None
    description: str | None = None
    source_system: str | None = Field(None, alias="sourceSystem")
    source_identifier: str | None = Field(None, alias="sourceIdentifier")
    agent_id: str | None = Field(None, alias="agentId")
    workflow_id: str | None = Field(None, alias="workflowId")
    work_unit_id: str | None = Field(None, alias="workUnitId")
    classification_id: str | None = Field(None, alias="classificationId")
    schema_def: Any = Field(None, alias="schema")
    attributes: Any = None
    created_at: str | None = Field(None, alias="createdAt")
    updated_at: str | None = Field(None, alias="updatedAt")


class LineageEdge(TolerantModel):
    """An edge in the data-lineage graph (``LineageEdgeResponse``)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    organization_id: str | None = Field(None, alias="organizationId")
    source_node_id: str | None = Field(None, alias="sourceNodeId")
    target_node_id: str | None = Field(None, alias="targetNodeId")
    edge_type: str | None = Field(None, alias="edgeType")
    transformation_description: str | None = Field(
        None, alias="transformationDescription"
    )
    transformation_logic: str | None = Field(None, alias="transformationLogic")
    data_fields: Any = Field(None, alias="dataFields")
    frequency: str | None = None
    last_data_flow_at: str | None = Field(None, alias="lastDataFlowAt")
    volume_estimate: str | None = Field(None, alias="volumeEstimate")
    is_active: bool = Field(True, alias="isActive")
    created_at: str | None = Field(None, alias="createdAt")
    updated_at: str | None = Field(None, alias="updatedAt")


class LineageTraversal(TolerantModel):
    """The result of walking one direction from a node.

    ``path`` is the ordered node-id walk the server took, which is what makes a
    traversal auditable — the same node set can be reached by different routes
    and only the path distinguishes them.
    """

    model_config = ConfigDict(populate_by_name=True)

    nodes: list[LineageNode]
    edges: list[LineageEdge]
    path: list[str]


class LineageGraphModule:
    """Register and traverse the data-lineage graph.

    Example:
        >>> src = await client.dataflow.graph.create_node(
        ...     node_type="source", name="orders_raw", source_system="postgres"
        ... )
        >>> dst = await client.dataflow.graph.create_node(
        ...     node_type="dataset", name="orders_clean"
        ... )
        >>> await client.dataflow.graph.create_edge(
        ...     source_node_id=src.id, target_node_id=dst.id, edge_type="derives_from"
        ... )
        >>> walk = await client.dataflow.graph.upstream(dst.id, max_depth=5)
        >>> [n.name for n in walk.nodes]
        ['orders_raw']
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    async def create_node(
        self,
        node_type: str,
        name: str,
        description: str | None = None,
        source_system: str | None = None,
        source_identifier: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        work_unit_id: str | None = None,
        classification_id: str | None = None,
        schema_def: dict[str, Any] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> LineageNode:
        """Register a node in the lineage graph.

        Server: ``POST /api/v1/data-governance/lineage/nodes`` -> 201.

        Args:
            node_type: What the node IS (source/dataset/transform/destination)
            name: Human-readable node name
            description: Free-text description
            source_system: System the node lives in
            source_identifier: The node's id WITHIN that system
            agent_id: Agent that owns or produces the node
            workflow_id: Workflow that produces the node
            work_unit_id: Owning work unit
            classification_id: EATP data classification to attach
            schema_def: The node's schema; sent on the wire as ``schema``
            attributes: Free-form attributes

        Returns:
            LineageNode: the created node, including its server-assigned id.
        """
        body: dict[str, Any] = {"nodeType": node_type, "name": name}
        for key, value in (
            ("description", description),
            ("sourceSystem", source_system),
            ("sourceIdentifier", source_identifier),
            ("agentId", agent_id),
            ("workflowId", workflow_id),
            ("workUnitId", work_unit_id),
            ("classificationId", classification_id),
            ("schema", schema_def),
            ("attributes", attributes),
        ):
            if value is not None:
                body[key] = value

        response = await self._http.request(
            "POST", "/api/v1/data-governance/lineage/nodes", json_data=body
        )
        return LineageNode(**response)

    async def create_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        edge_type: str,
        transformation_description: str | None = None,
        transformation_logic: str | None = None,
        data_fields: list[str] | None = None,
        frequency: str | None = None,
        volume_estimate: str | None = None,
        is_active: bool = True,
    ) -> LineageEdge:
        """Join two nodes with a typed, directed edge.

        Server: ``POST /api/v1/data-governance/lineage/edges`` -> 201.

        Args:
            source_node_id: Where the data comes FROM
            target_node_id: Where the data goes TO
            edge_type: Relationship (derives_from/feeds_into/copies_to)
            transformation_description: What the transformation does
            transformation_logic: How it does it
            data_fields: Field names carried along this edge
            frequency: How often data flows
            volume_estimate: Rough volume moved
            is_active: Whether the flow is live

        Returns:
            LineageEdge: the created edge.
        """
        body: dict[str, Any] = {
            "sourceNodeId": source_node_id,
            "targetNodeId": target_node_id,
            "edgeType": edge_type,
            "isActive": is_active,
        }
        for key, value in (
            ("transformationDescription", transformation_description),
            ("transformationLogic", transformation_logic),
            ("dataFields", data_fields),
            ("frequency", frequency),
            ("volumeEstimate", volume_estimate),
        ):
            if value is not None:
                body[key] = value

        response = await self._http.request(
            "POST", "/api/v1/data-governance/lineage/edges", json_data=body
        )
        return LineageEdge(**response)

    async def get_node(self, node_id: str) -> LineageNode:
        """Get one lineage node.

        Server: ``GET /api/v1/data-governance/lineage/nodes/{node_id}``.

        Args:
            node_id: The node's id

        Returns:
            LineageNode: the node.

        Raises:
            ValueError: if ``node_id`` is empty. An empty id collapses the path
                onto the collection route, which answers 201/405 rather than
                the 404 the caller would expect.
        """
        if not node_id:
            raise ValueError("node_id must not be empty")
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/lineage/nodes/{encode_path_param(node_id)}",
        )
        return LineageNode(**response)

    async def upstream(self, node_id: str, max_depth: int = 10) -> LineageTraversal:
        """Walk UPSTREAM from a node — everything it derives from.

        Server: ``GET /api/v1/data-governance/lineage/nodes/{id}/upstream``.

        Args:
            node_id: The node to walk from
            max_depth: Hops to follow; the server bounds this to 1-20

        Returns:
            LineageTraversal: nodes, edges, and the ordered path walked.
        """
        if not node_id:
            raise ValueError("node_id must not be empty")
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/lineage/nodes/{encode_path_param(node_id)}/upstream",
            params={"maxDepth": max_depth},
        )
        return self._as_traversal(response)

    async def downstream(self, node_id: str, max_depth: int = 10) -> LineageTraversal:
        """Walk DOWNSTREAM from a node — everything derived from it.

        Server: ``GET /api/v1/data-governance/lineage/nodes/{id}/downstream``.

        This is the blast-radius question: change this node, and these are the
        things that change with it.

        Args:
            node_id: The node to walk from
            max_depth: Hops to follow; the server bounds this to 1-20

        Returns:
            LineageTraversal: nodes, edges, and the ordered path walked.
        """
        if not node_id:
            raise ValueError("node_id must not be empty")
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/lineage/nodes/{encode_path_param(node_id)}/downstream",
            params={"maxDepth": max_depth},
        )
        return self._as_traversal(response)

    @staticmethod
    def _as_traversal(response: dict[str, Any]) -> LineageTraversal:
        """Parse a traversal envelope. Shared by both directions.

        ⛔ ONLY the PARSING is shared, never the request. The two routes differ
        by one path segment and the DRY move is to interpolate it — which is
        precisely what must not happen here. ``scripts/audit/sdk_parity_gap.py``
        derives SDK coverage by AST over the LITERAL path argument, turning
        every interpolated segment into ``{}``; a parameterised direction emits
        ``/api/v1/data-governance/lineage/nodes/{}/{}``, which matches no live
        route, so BOTH paths would silently read as uncovered while the client
        kept working perfectly. Behaviour and measured coverage come apart, and
        only the coverage moves. Keep each path a literal at its own call site.
        """
        return LineageTraversal(
            nodes=[LineageNode(**n) for n in response.get("nodes", [])],
            edges=[LineageEdge(**e) for e in response.get("edges", [])],
            path=response.get("path", []),
        )
