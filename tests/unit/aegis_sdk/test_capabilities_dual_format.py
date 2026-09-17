"""``capabilities_json`` is DUAL-FORMAT, and the SDK read model must accept both.

An element of an agent's ``capabilities_json`` is EITHER a bare string (the
capability name) OR an object ``{name, description, keywords}``. Both shapes are
live on the server simultaneously:

* ``services/pseudo_agent_service.py`` persists the STRING form at agent
  creation, ``api/task_agents.py``'s validator documents the string form, and
  the SDK itself writes strings via ``AgentCreate.to_request_body``;
* ``models/agent.py`` documents the OBJECT form, and both
  ``services/objective_router.py`` and ``services/shadow_agent_factory.py``
  implement BOTH shapes.

Before this fix ``Agent.capabilities`` was ``list[str]`` and the parser assigned
the raw decoded list, so the SDK raised ``ValidationError`` on the object form.
The partner-visible consequence is a read that crashes on an agent somebody else
wrote -- the mirror of the server-side ``AttributeError`` that made
``GET /a2a/agent/{id}/card`` a 500 for string-capability agents.

These tests pin BOTH polarities: every live shape must PARSE, malformed elements
must DROP rather than raise, and unrelated validation must still FAIL -- that
last one is what keeps the forgiveness from becoming vacuous.
"""

import json
import logging

import pytest
from pydantic import ValidationError

from aegis_sdk.types import Agent

_BASE = {
    "id": "agent-1",
    "name": "n",
    "agent_type": "tool_agent",
    "unit_type": "atomic",
    "status": "active",
    "organization_id": "org-1",
    "workspace_id": "ws-1",
    "created_at": "2026-09-14T00:00:00Z",
    "updated_at": "2026-09-14T00:00:00Z",
}


def _agent(capabilities: list) -> Agent:
    return Agent(**_BASE, capabilities_json=json.dumps(capabilities))


@pytest.mark.parametrize(
    ("label", "raw"),
    [
        ("string form", ["ordering", "billing"]),
        (
            "object form",
            [
                {"name": "ordering", "description": "d", "keywords": ["o"]},
                {"name": "billing"},
            ],
        ),
        ("mixed form", ["ordering", {"name": "billing"}]),
    ],
)
def test_every_live_capability_shape_parses_to_names(label: str, raw: list) -> None:
    """Both persisted shapes -- and a column holding both -- yield the names.

    The object arm is the one that regressed: it raised
    ``('capabilities', 0): string_type`` before the normalizer existed.
    """
    assert _agent(raw).capabilities == ["ordering", "billing"], label


def test_malformed_elements_are_dropped_with_a_warning_not_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One unparseable capability degrades that entry, never the whole page.

    Same forgiving-read-model principle ``_coerce_unknown_agent_type`` records:
    a read model must survive forward drift rather than fail an entire
    ``agents.list()`` response on a single bad row.
    """
    malformed = [{"description": "no name"}, 42, None, {"name": ""}, {"name": 123}]
    with caplog.at_level(logging.WARNING, logger="aegis_sdk.types"):
        agent = _agent(["ordering", *malformed])

    assert agent.capabilities == ["ordering"]
    # One WARN per dropped element -- a silent drop would be the dead-feature
    # class this SDK has already shipped once.
    assert len(caplog.records) == len(malformed)


def test_forgiveness_is_scoped_and_validation_is_not_vacuous() -> None:
    """The control: an unrelated invalid field MUST still raise.

    Without this, a normalizer that quietly accepted everything would pass the
    tests above for the wrong reason.
    """
    with pytest.raises(ValidationError) as excinfo:
        Agent(**{**_BASE, "status": "not_a_real_status"}, capabilities_json='["x"]')

    # Pin WHICH field rejected it: a ValidationError raised for some unrelated
    # reason would satisfy a bare `raises` and prove nothing about `status`.
    assert [e["loc"] for e in excinfo.value.errors()] == [("status",)]


def test_absent_and_empty_capabilities_json_stay_empty() -> None:
    """Absence is not a parse failure, and must not warn."""
    assert Agent(**_BASE).capabilities == []
    assert Agent(**_BASE, capabilities_json="").capabilities == []
    assert Agent(**_BASE, capabilities_json="not json").capabilities == []
