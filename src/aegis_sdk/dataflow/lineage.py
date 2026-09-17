"""Invocation-lineage surface — the `/api/v1/lineage` router.

A delivery architect building a data pipeline against Aegis has to answer two
questions the platform already records and the SDK could not previously ask:
*which external invocation produced this record*, and *what did it cost, touch
and return*. That is the invocation-lineage router, and every one of its five
routes sat outside the SDK's reach.

Self-contained module: local Pydantic models, no shared imports from
``client.py`` / ``modules/__init__.py`` / ``types.py``, matching the convention
``modules/knowledge_govern.py`` records.

Every route below is derived from the platform's invocation-lineage router:

    GET    /api/v1/lineage                  -> list()
    GET    /api/v1/lineage/graph            -> graph()
    GET    /api/v1/lineage/export           -> export()
    GET    /api/v1/lineage/{invocation_id}  -> get()
    DELETE /api/v1/lineage/user/{email}     -> redact_user()

⚠ ``/graph`` and ``/export`` are LITERAL routes that must stay distinguishable
from ``/{invocation_id}``. The server pins that ordering with a comment; the
client side of the same hazard is that ``get("graph")`` would address the graph
route rather than an invocation. :func:`get` therefore percent-encodes its id
like every other interpolated segment, and the reserved literals are refused
outright rather than silently addressing a different endpoint.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient

# Path segments that are ROUTES on this router, not invocation ids. Passing one
# as an id would produce a well-formed request against the wrong endpoint —
# a 200 carrying the wrong document, which is worse than an error.
_RESERVED_SEGMENTS = frozenset({"graph", "export", "user"})


class LineageRecord(TolerantModel):
    """A single external-agent invocation record (``LineageRecordResponse``).

    Extra keys are tolerated rather than rejected: this record grows on the
    server as new telemetry is captured, and a client that raises on an
    unrecognised field turns an additive server change into a client outage.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    external_user_id: str | None = None
    external_user_email: str | None = None
    external_system: str | None = None
    external_agent_id: str | None = None
    external_agent_name: str | None = None
    organization_id: str | None = None
    team_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_trace_id: str | None = None
    status: str | None = None
    request_timestamp: str | None = None
    response_timestamp: str | None = None
    duration_ms: int | None = None
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    api_calls_count: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    response_status_code: int | None = None
    budget_checked: bool = False
    budget_remaining_before: float | None = None
    budget_remaining_after: float | None = None
    # None = NOT EVALUATED, and that is a third state, not a falsy False. No
    # approval gate is wired into the external-agent invocation path, so the
    # platform cannot honestly assert either boolean. Rendering
    # this as "not required" would report an absent control as a passed one.
    approval_required: bool | None = None
    approval_status: str | None = None
    approval_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LineagePage(TolerantModel):
    """One page of invocation lineages (``LineageListResponse``)."""

    model_config = ConfigDict(populate_by_name=True)

    lineages: builtins.list[LineageRecord]
    total: int
    page: int
    limit: int


class LineageGraph(TolerantModel):
    """Invocation graph (``LineageGraphResponse``).

    Nodes and edges stay untyped dicts because the server declares them as
    ``list[dict]``. Inventing a schema the API does not declare would give the
    caller a type that the wire can contradict at any time.
    """

    model_config = ConfigDict(populate_by_name=True)

    nodes: builtins.list[dict[str, Any]]
    edges: builtins.list[dict[str, Any]]


class InvocationLineageModule:
    """Invocation lineage for external-agent traffic.

    Example:
        >>> page = await client.dataflow.lineage.list(status="error", limit=20)
        >>> page.total
        3
        >>> record = await client.dataflow.lineage.get(page.lineages[0].id)
        >>> record.cost_usd
        0.0121
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    async def list(
        self,
        external_user_id: str | None = None,
        external_user_email: str | None = None,
        external_system: str | None = None,
        external_agent_id: str | None = None,
        organization_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> LineagePage:
        """List invocation lineages.

        Server: ``GET /api/v1/lineage`` (requires ``lineage:read``).

        Args:
            external_user_id: Filter by the calling external user's id
            external_user_email: Filter by the calling external user's email
            external_system: Filter by originating system
            external_agent_id: Filter by external agent
            organization_id: Filter by organization
            status: Filter by invocation status
            page: 1-based page number
            limit: Page size (server bounds this to 1-200)

        Returns:
            LineagePage: records plus the server's total/page/limit.
        """
        params: dict[str, Any] = {"page": page, "limit": limit}
        for key, value in (
            ("external_user_id", external_user_id),
            ("external_user_email", external_user_email),
            ("external_system", external_system),
            ("external_agent_id", external_agent_id),
            ("organization_id", organization_id),
            ("status", status),
        ):
            if value is not None:
                params[key] = value

        response = await self._http.request("GET", "/api/v1/lineage", params=params)
        return LineagePage(
            lineages=[LineageRecord(**r) for r in response.get("lineages", [])],
            total=response.get("total", 0),
            page=response.get("page", page),
            limit=response.get("limit", limit),
        )

    async def graph(
        self,
        workflow_id: str | None = None,
        external_agent_id: str | None = None,
    ) -> LineageGraph:
        """Get the invocation graph for a workflow or an external agent.

        Server: ``GET /api/v1/lineage/graph`` (requires ``lineage:read``).

        Args:
            workflow_id: Root the graph at a workflow
            external_agent_id: Root the graph at an external agent

        Returns:
            LineageGraph: nodes and edges of the invocation chain.
        """
        params: dict[str, Any] = {}
        if workflow_id is not None:
            params["workflow_id"] = workflow_id
        if external_agent_id is not None:
            params["external_agent_id"] = external_agent_id

        response = await self._http.request(
            "GET", "/api/v1/lineage/graph", params=params
        )
        return LineageGraph(
            nodes=response.get("nodes", []), edges=response.get("edges", [])
        )

    async def export(
        self,
        format: Literal["json", "csv"] = "json",
        external_user_id: str | None = None,
        external_user_email: str | None = None,
        external_system: str | None = None,
        external_agent_id: str | None = None,
        status: str | None = None,
    ) -> bytes:
        """Export lineage records as a downloadable document.

        Server: ``GET /api/v1/lineage/export`` (requires ``lineage:export``).

        Returns the response BODY AS BYTES. This endpoint emits a file with a
        ``Content-Disposition`` — ``application/json`` or ``text/csv`` — not a
        JSON document to be parsed, so ``raw_response=True`` is load-bearing:
        without it the CSV branch raises inside the client's own ``.json()``
        and the caller sees a parse error rather than their export.

        Args:
            format: ``"json"`` or ``"csv"``; the server rejects anything else
            external_user_id: Filter by the calling external user's id
            external_user_email: Filter by the calling external user's email
            external_system: Filter by originating system
            external_agent_id: Filter by external agent
            status: Filter by invocation status

        Returns:
            bytes: the raw export body, to write to a file or stream onward.
        """
        params: dict[str, Any] = {"format": format}
        for key, value in (
            ("external_user_id", external_user_id),
            ("external_user_email", external_user_email),
            ("external_system", external_system),
            ("external_agent_id", external_agent_id),
            ("status", status),
        ):
            if value is not None:
                params[key] = value

        # Narrowed explicitly rather than returned straight through: the
        # transport is typed `Any`, so a bare return would hand the caller an
        # unchecked value under a `bytes` annotation and mypy would flag the
        # lie rather than the shape.
        body: bytes = await self._http.request(
            "GET", "/api/v1/lineage/export", params=params, raw_response=True
        )
        return body

    async def get(self, invocation_id: str) -> LineageRecord:
        """Get one invocation lineage record.

        Server: ``GET /api/v1/lineage/{invocation_id}`` (``lineage:read``).

        Args:
            invocation_id: The invocation's id

        Returns:
            LineageRecord: the full record.

        Raises:
            ValueError: if ``invocation_id`` is empty or names a sibling route
                on this router (``graph``/``export``/``user``). Those would
                otherwise produce a 200 carrying a different document — a
                wrong answer is worse than a refusal.
        """
        if not invocation_id:
            raise ValueError("invocation_id must not be empty")
        if invocation_id in _RESERVED_SEGMENTS:
            raise ValueError(
                f"{invocation_id!r} is a route on /api/v1/lineage, not an "
                f"invocation id; use the matching method instead"
            )
        response = await self._http.request(
            "GET", f"/api/v1/lineage/{encode_path_param(invocation_id)}"
        )
        return LineageRecord(**response)

    async def redact_user(self, email: str, approval_receipt: dict[str, Any]) -> None:
        """Redact one subject's PII across lineage records (GDPR erasure).

        Server: ``DELETE /api/v1/lineage/user/{email}`` -> 204 No Content.

        ⛔ IRREVERSIBLE, and org-wide in blast radius — the server sweeps up to
        10,000 lineage records. It requires BOTH the ``gdpr:redact`` permission
        and a signed, single-use ``gdpr_redact`` step-up receipt minted by the
        caller via approve/begin + approve/finish with
        ``action_ref=<this email>``. The permission bounds who may ask; the
        receipt proves a live re-authentication for THIS subject.

        The target is taken from the ROUTE PATH and re-derived server-side at
        consume time, never from the body, so a receipt minted for one subject
        cannot redact another.

        Args:
            email: The subject whose PII is erased
            approval_receipt: The signed ``gdpr_redact`` receipt

        Returns:
            None: the server answers 204 with no body.

        Raises:
            ValueError: if ``email`` is empty or ``approval_receipt`` is empty.
                An empty receipt is refused HERE rather than sent, because the
                server's fail-closed answer is a 401 that reads identically to
                an expired or replayed receipt — three very different problems
                arriving as one message.
        """
        if not email:
            raise ValueError("email must not be empty")
        if not approval_receipt:
            raise ValueError(
                "approval_receipt is required: this route consumes a signed, "
                "single-use gdpr_redact step-up receipt"
            )
        await self._http.request(
            "DELETE",
            f"/api/v1/lineage/user/{encode_path_param(email)}",
            json_data={"approval_receipt": approval_receipt},
        )
