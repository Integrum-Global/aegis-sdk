"""Contract tests for the `aegis_sdk.dataflow` lineage surface.

Pins route + method + request shape + response parsing against a stubbed
HTTPClient, in the idiom of ``tests/unit/sdk/test_modules_knowledge_govern.py``.

Route coverage — the thing the parity ratchet measures — is asserted separately
in ``test_lineage_route_coverage.py``. These tests answer the other half: that
the request actually sent is the one the server declares.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.dataflow.graph import (
    LineageEdge,
    LineageGraphModule,
    LineageNode,
    LineageTraversal,
)
from aegis_sdk.dataflow.lineage import (
    InvocationLineageModule,
    LineageGraph,
    LineagePage,
    LineageRecord,
)


@pytest.fixture
def mock_http():
    return MagicMock()


@pytest.fixture
def lineage(mock_http):
    return InvocationLineageModule(mock_http)


@pytest.fixture
def graph(mock_http):
    return LineageGraphModule(mock_http)


def make_record(**overrides):
    base = {
        "id": "inv-1",
        "external_user_email": "a@example.test",
        "external_agent_id": "ext-9",
        "status": "success",
        "duration_ms": 120,
        "cost_usd": 0.0121,
    }
    base.update(overrides)
    return base


def make_node(**overrides):
    base = {
        "id": "node-1",
        "organizationId": "org-1",
        "nodeType": "source",
        "name": "orders_raw",
        "sourceSystem": "postgres",
        "schema": {"cols": ["id"]},
        "createdAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def make_edge(**overrides):
    base = {
        "id": "edge-1",
        "sourceNodeId": "node-1",
        "targetNodeId": "node-2",
        "edgeType": "derives_from",
        "isActive": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Invocation lineage — /api/v1/lineage
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestInvocationLineage:
    async def test_list_route_and_defaults(self, mock_http, lineage):
        """list() GETs /api/v1/lineage and parses the envelope."""
        mock_http.request = AsyncMock(
            return_value={
                "lineages": [make_record()],
                "total": 1,
                "page": 1,
                "limit": 100,
            }
        )

        result = await lineage.list()

        assert mock_http.request.call_args[0] == ("GET", "/api/v1/lineage")
        params = mock_http.request.call_args[1]["params"]
        assert params == {"page": 1, "limit": 100}
        assert isinstance(result, LineagePage)
        assert result.total == 1
        assert isinstance(result.lineages[0], LineageRecord)
        assert result.lineages[0].cost_usd == 0.0121

    async def test_list_omits_unset_filters_rather_than_sending_null(
        self, mock_http, lineage
    ):
        """An unset filter is ABSENT, not `None`.

        Sending `status=None` serialises to an empty query value, which the
        server reads as a filter on the empty string — zero rows, and
        indistinguishable from a genuine empty result.
        """
        mock_http.request = AsyncMock(
            return_value={"lineages": [], "total": 0, "page": 2, "limit": 5}
        )

        await lineage.list(status="error", external_system="zapier", page=2, limit=5)

        params = mock_http.request.call_args[1]["params"]
        assert params == {
            "page": 2,
            "limit": 5,
            "external_system": "zapier",
            "status": "error",
        }
        assert "external_user_id" not in params
        assert None not in params.values()

    async def test_graph_route(self, mock_http, lineage):
        """graph() GETs the literal /graph route, not /{invocation_id}."""
        mock_http.request = AsyncMock(
            return_value={"nodes": [{"id": "n1"}], "edges": [{"from": "n1"}]}
        )

        result = await lineage.graph(workflow_id="wf-1")

        assert mock_http.request.call_args[0] == ("GET", "/api/v1/lineage/graph")
        assert mock_http.request.call_args[1]["params"] == {"workflow_id": "wf-1"}
        assert isinstance(result, LineageGraph)
        assert result.nodes == [{"id": "n1"}]

    async def test_export_requests_raw_bytes(self, mock_http, lineage):
        """export() must set raw_response — the CSV branch is not JSON.

        Without it the client parses the body as JSON and a CSV export raises
        a decode error instead of returning the caller's file.
        """
        mock_http.request = AsyncMock(return_value=b"id,cost\ninv-1,0.01\n")

        body = await lineage.export(format="csv", status="error")

        assert mock_http.request.call_args[0] == ("GET", "/api/v1/lineage/export")
        assert mock_http.request.call_args[1]["raw_response"] is True
        assert mock_http.request.call_args[1]["params"] == {
            "format": "csv",
            "status": "error",
        }
        assert body == b"id,cost\ninv-1,0.01\n"

    async def test_get_route_and_encoding(self, mock_http, lineage):
        """get() addresses /api/v1/lineage/{id} with the id percent-encoded."""
        mock_http.request = AsyncMock(return_value=make_record(id="inv/../admin"))

        await lineage.get("inv/../admin")

        method, path = mock_http.request.call_args[0]
        assert method == "GET"
        assert path.startswith("/api/v1/lineage/")
        assert "/../" not in path, "an id must not be able to shift path segments"
        assert path == "/api/v1/lineage/inv%2F..%2Fadmin"

    @pytest.mark.parametrize("reserved", ["graph", "export", "user"])
    async def test_get_refuses_sibling_route_names(self, mock_http, lineage, reserved):
        """A sibling route name as an id would 200 with the WRONG document."""
        mock_http.request = AsyncMock()

        with pytest.raises(ValueError, match="not an invocation id"):
            await lineage.get(reserved)

        mock_http.request.assert_not_called()

    async def test_get_refuses_empty_id(self, mock_http, lineage):
        mock_http.request = AsyncMock()

        with pytest.raises(ValueError, match="must not be empty"):
            await lineage.get("")

        mock_http.request.assert_not_called()

    async def test_redact_user_route_and_body(self, mock_http, lineage):
        """redact_user() DELETEs /user/{email} carrying the step-up receipt."""
        mock_http.request = AsyncMock(return_value=None)

        result = await lineage.redact_user(
            "a@example.test", {"receipt_id": "r-1", "sig": "abc"}
        )

        method, path = mock_http.request.call_args[0]
        assert method == "DELETE"
        assert path == "/api/v1/lineage/user/a%40example.test"
        assert mock_http.request.call_args[1]["json_data"] == {
            "approval_receipt": {"receipt_id": "r-1", "sig": "abc"}
        }
        assert result is None

    async def test_redact_user_refuses_an_empty_receipt_locally(
        self, mock_http, lineage
    ):
        """Refused HERE, because the server's answer would be ambiguous.

        A missing receipt, an expired one and a replayed one all come back as
        401. Refusing the empty case client-side keeps 'you sent nothing' from
        arriving as 'your receipt was rejected'.
        """
        mock_http.request = AsyncMock()

        with pytest.raises(ValueError, match="approval_receipt is required"):
            await lineage.redact_user("a@example.test", {})

        mock_http.request.assert_not_called()


# ---------------------------------------------------------------------------
# Data-lineage graph — /api/v1/data-governance/lineage
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestLineageGraphModule:
    async def test_create_node_sends_camel_case(self, mock_http, graph):
        """This router aliases every field; snake_case would not bind."""
        mock_http.request = AsyncMock(return_value=make_node())

        result = await graph.create_node(
            node_type="source",
            name="orders_raw",
            source_system="postgres",
            schema_def={"cols": ["id"]},
        )

        assert mock_http.request.call_args[0] == (
            "POST",
            "/api/v1/data-governance/lineage/nodes",
        )
        body = mock_http.request.call_args[1]["json_data"]
        assert body == {
            "nodeType": "source",
            "name": "orders_raw",
            "sourceSystem": "postgres",
            "schema": {"cols": ["id"]},
        }
        assert "node_type" not in body
        assert "schema_def" not in body, "the wire field is `schema`, not `schema_def`"
        assert isinstance(result, LineageNode)
        assert result.node_type == "source"
        assert result.schema_def == {"cols": ["id"]}

    async def test_create_edge_sends_camel_case(self, mock_http, graph):
        mock_http.request = AsyncMock(return_value=make_edge())

        result = await graph.create_edge(
            source_node_id="node-1",
            target_node_id="node-2",
            edge_type="derives_from",
            data_fields=["id", "total"],
        )

        assert mock_http.request.call_args[0] == (
            "POST",
            "/api/v1/data-governance/lineage/edges",
        )
        assert mock_http.request.call_args[1]["json_data"] == {
            "sourceNodeId": "node-1",
            "targetNodeId": "node-2",
            "edgeType": "derives_from",
            "isActive": True,
            "dataFields": ["id", "total"],
        }
        assert isinstance(result, LineageEdge)
        assert result.source_node_id == "node-1"

    async def test_get_node_route(self, mock_http, graph):
        mock_http.request = AsyncMock(return_value=make_node())

        await graph.get_node("node-1")

        assert mock_http.request.call_args[0] == (
            "GET",
            "/api/v1/data-governance/lineage/nodes/node-1",
        )

    @pytest.mark.parametrize(
        ("direction", "suffix"),
        [("upstream", "upstream"), ("downstream", "downstream")],
    )
    async def test_traversal_routes_are_distinct_literals(
        self, mock_http, graph, direction, suffix
    ):
        """Each direction addresses its OWN route.

        Pinned as two distinct literal paths rather than one parameterised
        one: `sdk_parity_gap.py` derives coverage from the literal path
        argument, so an interpolated direction emits `.../nodes/{}/{}` and
        both routes read as uncovered while behaving correctly.
        """
        mock_http.request = AsyncMock(
            return_value={
                "nodes": [make_node()],
                "edges": [make_edge()],
                "path": ["node-1", "node-2"],
            }
        )

        result = await getattr(graph, direction)("node-1", max_depth=5)

        assert mock_http.request.call_args[0] == (
            "GET",
            f"/api/v1/data-governance/lineage/nodes/node-1/{suffix}",
        )
        assert mock_http.request.call_args[1]["params"] == {"maxDepth": 5}
        assert isinstance(result, LineageTraversal)
        assert result.path == ["node-1", "node-2"]
        assert isinstance(result.nodes[0], LineageNode)
        assert isinstance(result.edges[0], LineageEdge)

    @pytest.mark.parametrize("method", ["get_node", "upstream", "downstream"])
    async def test_node_routes_refuse_an_empty_id(self, mock_http, graph, method):
        """An empty id collapses onto the collection route."""
        mock_http.request = AsyncMock()

        with pytest.raises(ValueError, match="must not be empty"):
            await getattr(graph, method)("")

        mock_http.request.assert_not_called()

    async def test_node_id_is_percent_encoded(self, mock_http, graph):
        mock_http.request = AsyncMock(return_value=make_node())

        await graph.get_node("../../admin")

        path = mock_http.request.call_args[0][1]
        assert "/../" not in path
        assert path == "/api/v1/data-governance/lineage/nodes/..%2F..%2Fadmin"
