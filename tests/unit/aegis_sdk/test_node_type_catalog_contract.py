"""Contract tests for ``PipelinesModule.list_node_types``.

WHY THIS FILE EXISTS
--------------------
The method shipped broken and nothing could say so. It asserted that
``GET /api/v1/pipelines/node-types`` answers ``{"data": [<node type>, ...]}``
— a flat list — while the route answers ``{"data": {categories, total_types,
executable, unavailable_reason, node_types}}``. Every call therefore raised
``ServiceError``, and the error reported only ``{"response_type": "dict"}``.

Two things kept that invisible for the life of the method: **nothing called
it** — no caller anywhere in ``src/`` or ``tests/`` — and **nothing tested
it**. A method that always raises looks exactly like a method nobody uses,
until a customer is the first to find out. This file closes the second half.

WHAT THESE TESTS PIN, AND HOW A GREEN COULD BE WRONG
----------------------------------------------------
``CATALOG_PAYLOAD`` is the shape a live deployment actually returns,
transcribed. The suite is bipolar on the exact axis that broke:

* the real object parses, and every field survives to the caller;
* a flat list — the shape the old code DEMANDED — is now the shape that must
  RAISE. Revert the parser to its old assertion and that test goes red.

The second case is the falsifying result, and it is why a green here means
something. These tests say nothing about whether the server honours the
route; ``handbook/check.py`` is explicit that existence is not behaviour.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.core.pipelines import PipelinesModule
from aegis_sdk.exceptions import ServiceError
from aegis_sdk.types import NodeTypeCatalog

# Transcribed from a live deployment's answer, structure intact: category
# buckets holding palette nodes, a palette count that is NOT the vocabulary
# count, a catalogue-wide executability flag, and a per-type verdict map that
# covers types the palette does not offer.
CATALOG_PAYLOAD = {
    "categories": [
        {
            "id": "ai_llm",
            "label": "AI & LLM",
            "nodes": [
                {
                    "type": "TextSplitterNode",
                    "label": "Text Splitter",
                    "description": "Splits text into chunks.",
                }
            ],
        },
        {
            "id": "control_flow",
            "label": "Control Flow",
            "nodes": [
                {
                    "type": "ConditionalNode",
                    "label": "Conditional",
                    "description": "Branches on a predicate.",
                },
                {
                    "type": "MergeNode",
                    "label": "Merge",
                    "description": "Joins branches.",
                },
            ],
        },
    ],
    "total_types": 3,
    "executable": False,
    "unavailable_reason": (
        "These run only in legacy execution mode. The default compiled "
        "executor has no SDK binding for connector nodes."
    ),
    "node_types": {
        "agent": {"executable": True, "reason": None, "fabricates": False},
        "connector": {
            "executable": False,
            "reason": "'connector' has no SDK binding, so the compiler refuses it.",
            "fabricates": False,
        },
        # A silent failure: "does not run" by emitting a diagnostic string AS
        # its output. Rendering this identically to a loud refusal is how a
        # fabricated result reaches a client.
        "quiet_fabricator": {
            "executable": False,
            "reason": "emits a diagnostic string as its output",
            "fabricates": True,
        },
    },
}


@pytest.fixture
def http():
    stub = MagicMock()
    stub.request = AsyncMock(return_value={"data": CATALOG_PAYLOAD})
    return stub


@pytest.fixture
def pipelines(http):
    return PipelinesModule(http)


async def test_returns_the_catalog_without_discarding_executability(pipelines):
    """The whole point: a caller can see what is here AND what will run.

    Flattening this to a bare list of nodes is the tempting simplification and
    it is the defect — it drops the fields that answer "will my pipeline
    actually execute?", which is the question the catalogue exists to answer.
    """
    catalog = await pipelines.list_node_types()

    assert isinstance(catalog, NodeTypeCatalog)
    assert catalog.total_types == 3
    assert catalog.executable is False
    assert "legacy execution mode" in catalog.unavailable_reason


async def test_flat_preserves_server_order_across_categories(pipelines):
    catalog = await pipelines.list_node_types()

    assert [node.type for node in catalog.flat] == [
        "TextSplitterNode",
        "ConditionalNode",
        "MergeNode",
    ]
    assert catalog.flat[0].label == "Text Splitter"


async def test_vocabulary_covers_types_the_palette_does_not_offer(pipelines):
    """``node_types`` is not a second view of ``categories``.

    It carries a verdict for the whole pipeline vocabulary, including types
    the palette withholds. A caller reading only ``flat`` would miss that
    ``connector`` exists and refuses.
    """
    catalog = await pipelines.list_node_types()

    assert "connector" in catalog.node_types
    assert "connector" not in {node.type for node in catalog.flat}
    assert catalog.node_types["connector"].executable is False


async def test_fabricates_survives_the_round_trip(pipelines):
    """A silent failure must not arrive looking like a loud one."""
    catalog = await pipelines.list_node_types()

    assert catalog.node_types["agent"].fabricates is False
    assert catalog.node_types["quiet_fabricator"].fabricates is True
    assert catalog.node_types["agent"].reason is None


async def test_a_flat_list_raises_because_that_is_the_shape_that_broke(pipelines):
    """THE FALSIFYING CASE — the old contract is now the rejected one.

    The previous implementation accepted exactly this payload and returned it;
    it is what the method was written against. If a revert reintroduces that
    assertion, this test is the one that reds.
    """
    pipelines._http.request = AsyncMock(
        return_value={"data": [{"type": "agent", "name": "Agent"}]}
    )

    with pytest.raises(ServiceError) as excinfo:
        await pipelines.list_node_types()

    assert "list" in str(excinfo.value)


async def test_a_missing_key_names_what_actually_arrived(pipelines):
    """The error must be usable without a re-investigation.

    The shipped version reported only the payload's TYPE, which was true and
    told a reader nothing about which side had moved. Naming the received keys
    is the difference between a one-line diagnosis and this whole file.
    """
    pipelines._http.request = AsyncMock(
        return_value={"data": {"categories": [], "node_types": {"agent": {}}}}
    )

    with pytest.raises(ServiceError) as excinfo:
        await pipelines.list_node_types()

    assert "total_types" in str(excinfo.value)
    details = excinfo.value.details
    assert "total_types" in details["missing_keys"]
    assert "categories" in details["received_keys"]


async def test_a_catalogue_with_neither_palette_nor_vocabulary_raises(pipelines):
    """An empty answer and a wrong route are indistinguishable to a caller.

    Returning empty would be a confident wrong answer to "what can I build
    with?"; raising is not.
    """
    pipelines._http.request = AsyncMock(
        return_value={"data": {"categories": [], "total_types": 0, "node_types": {}}}
    )

    with pytest.raises(ServiceError):
        await pipelines.list_node_types()


async def test_the_route_is_the_one_the_server_declares(pipelines, http):
    await pipelines.list_node_types()

    assert http.request.call_args[0] == ("GET", "/api/v1/pipelines/node-types")
