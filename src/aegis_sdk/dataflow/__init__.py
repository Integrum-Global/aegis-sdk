"""Data-plane surfaces for the Aegis SDK.

A delivery architect holding only the published SDK builds against a running
Aegis over HTTP. This subpackage carries the DATA-plane half of that reach: what
produced a record, where data came from, and what breaks downstream if it
changes.

Two surfaces, deliberately separate despite sharing the word *lineage*:

``lineage`` — :class:`~aegis_sdk.dataflow.lineage.InvocationLineageModule`
    INVOCATION lineage. What an external agent DID: calls, cost, tokens,
    errors, budget, approval state. Backed by ``/api/v1/lineage``.

``graph`` — :class:`~aegis_sdk.dataflow.graph.LineageGraphModule`
    DATA lineage. How data MOVES: typed nodes joined by typed edges, walkable
    upstream and downstream. Backed by ``/api/v1/data-governance/lineage``.

⛔ A NOTE FOR ANYONE EXTENDING THIS SUBPACKAGE, because getting it wrong is
silent. ``scripts/audit/sdk_parity_gap.py`` measures partner reach by AST-walking
the literal path handed to ``request()``/``stream()``. Two consequences bind
every module added here:

1. ``EXCLUDED_SUBTREES`` skips ``src/aegis_sdk/kaizen/`` entirely, so an
   identical client written there scores ZERO coverage and closes nothing.
2. Every interpolated segment becomes ``{}``. Parameterising a path segment to
   avoid repeating a route makes the derived path match no live route, so the
   coverage disappears while the client keeps working. Keep each route a
   literal at its own call site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .graph import (
    LineageEdge,
    LineageGraphModule,
    LineageNode,
    LineageTraversal,
)
from .lineage import (
    InvocationLineageModule,
    LineageGraph,
    LineagePage,
    LineageRecord,
)

if TYPE_CHECKING:
    from .._http import HTTPClient


class DataFlowModules:
    """Container mounted on the client as ``client.dataflow``.

    Declared HERE rather than in ``client.py`` deliberately. The client is a
    high-traffic merge surface — several lanes append to its constructor at
    once — so this subpackage costs it exactly one import and one attribute.
    Everything this surface grows later lands in this file instead.

    Attributes:
        lineage: INVOCATION lineage (``/api/v1/lineage``) — what an agent did.
        graph: DATA lineage (``/api/v1/data-governance/lineage``) — how data
            moves, and what breaks downstream if a node changes.
    """

    def __init__(self, http_client: HTTPClient):
        self.lineage = InvocationLineageModule(http_client)
        self.graph = LineageGraphModule(http_client)


__all__ = [
    "DataFlowModules",
    "InvocationLineageModule",
    "LineageEdge",
    "LineageGraph",
    "LineageGraphModule",
    "LineageNode",
    "LineagePage",
    "LineageRecord",
    "LineageTraversal",
]
