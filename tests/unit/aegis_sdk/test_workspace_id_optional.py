"""``workspace_id`` is OPTIONAL on every response model the server stopped populating.

The server removed the Workspace entity. From that release on, six response
shapes carry ``workspace_id`` as ``null`` -- the key is kept so older clients
keep receiving it, but the value is never populated -- and the SDK declared it
``str`` (required, non-null) on all six. The consequence was not a degraded
field but a failed call: ``client.agents.create()`` raised ``ValidationError``
AFTER the server had already created the agent, so every retry created another
one, and ``agents.get()`` / ``agents.list()`` failed outright on every agent the
deployment held.

A null here is a faithful reading of "this record has no workspace". It grants
nothing, so declaring it optional is safe in the sense ``_tolerant.py`` requires:
the field KEEPS the null rather than substituting a default.

These tests pin both polarities. Every affected model must accept null, an
absent key, AND a real value (so older servers keep working); an unrelated
required field must still reject null -- that control is what stops the fix
from being read as "the model became forgiving".
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from aegis_sdk.core.agents import AgentsModule
from aegis_sdk.modules.bridges import ScopedBridge
from aegis_sdk.modules.integrations import ExternalAgent
from aegis_sdk.modules.tool_agents import ToolAgent
from aegis_sdk.types import (
    Agent,
    Objective,
    ObjectiveStatus,
    Pipeline,
    PipelinePattern,
)

_TS = "2026-09-18T00:00:00Z"

# A minimal valid payload per model, shaped as the server emits it. Every value
# other than workspace_id is irrelevant to the property under test.
_PAYLOADS: dict[type[BaseModel], dict[str, Any]] = {
    Agent: {
        "id": "agent-1",
        "name": "n",
        "agent_type": "chat",
        "unit_type": "atomic",
        "status": "draft",
        "organization_id": "org-1",
        "created_at": _TS,
        "updated_at": _TS,
    },
    ToolAgent: {
        "id": "ta-1",
        "organization_id": "org-1",
        "name": "n",
        "description": "d",
        "agent_type": "tool",
        "status": "active",
        "model_id": "m",
        "temperature": 0.2,
        "max_tokens": 100,
        "created_by": "u-1",
        "capabilities_json": "[]",
        "tools_json": "[]",
        "created_at": _TS,
        "updated_at": _TS,
    },
    Pipeline: {
        "id": "p-1",
        "name": "n",
        "pattern": list(PipelinePattern)[0].value,
        "organization_id": "org-1",
        "created_at": _TS,
        "updated_at": _TS,
    },
    Objective: {
        "id": "o-1",
        "title": "t",
        "description": "d",
        "agent_id": "agent-1",
        "status": list(ObjectiveStatus)[0].value,
        "organization_id": "org-1",
        "created_by": "u-1",
        "created_at": _TS,
        "updated_at": _TS,
    },
    ScopedBridge: {
        "id": "b-1",
        "organization_id": "org-1",
        "name": "n",
        "objective": "o",
        "participants_json": "[]",
        "owner_unit_id": "unit-1",
        "purpose": "p",
        "scope_description": "s",
        "active_from": _TS,
        "active_until": _TS,
        "starts_at": _TS,
        "auto_expire_on_objective_completion": False,
        "status": "active",
        "created_at": _TS,
        "updated_at": _TS,
    },
    ExternalAgent: {
        "id": "ea-1",
        "organization_id": "org-1",
        "name": "n",
        "platform": "custom",
        "webhook_url": "https://example.invalid/hook",
        "auth_type": "none",
        "platform_config": "{}",
        "capabilities": "[]",
        "config": "{}",
        "budget_limit_daily": 1.0,
        "budget_limit_monthly": 10.0,
        "rate_limit_per_minute": 1,
        "rate_limit_per_hour": 10,
        "status": "active",
        "created_by": "u-1",
        "created_at": _TS,
        "updated_at": _TS,
    },
}

_MODELS = list(_PAYLOADS)


@pytest.mark.parametrize("model", _MODELS, ids=lambda m: m.__name__)
def test_null_workspace_id_parses_and_stays_null(model: type[BaseModel]) -> None:
    obj = model(**_PAYLOADS[model], workspace_id=None)
    assert obj.workspace_id is None


@pytest.mark.parametrize("model", _MODELS, ids=lambda m: m.__name__)
def test_absent_workspace_id_parses_as_none(model: type[BaseModel]) -> None:
    assert model(**_PAYLOADS[model]).workspace_id is None


@pytest.mark.parametrize("model", _MODELS, ids=lambda m: m.__name__)
def test_populated_workspace_id_is_preserved(model: type[BaseModel]) -> None:
    # An older server still populates it; that value must survive untouched.
    assert model(**_PAYLOADS[model], workspace_id="ws-1").workspace_id == "ws-1"


@pytest.mark.parametrize("model", _MODELS, ids=lambda m: m.__name__)
def test_unrelated_required_field_still_rejects_null(model: type[BaseModel]) -> None:
    # Control: the fix is scoped to workspace_id. A genuinely required field
    # arriving null is still a server fault and must still raise.
    with pytest.raises(ValidationError):
        model(**{**_PAYLOADS[model], "organization_id": None})


class _FakeHTTP:
    """Returns the live server's reply shape: workspace_id always null."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def request(self, method: str, path: str, **_: Any) -> dict[str, Any]:
        self.calls.append((method, path))
        row = {**_PAYLOADS[Agent], "workspace_id": None}
        if method == "GET" and path == "/api/v1/agents":
            return {"records": [row, {**row, "id": "agent-2"}], "total": 2}
        return row


async def test_agents_create_get_list_against_server_that_nulls_workspace() -> None:
    http = _FakeHTTP()
    agents = AgentsModule(http)

    created = await agents.create(name="n", agent_type="chat", workspace_id="ws-1", model_id="m")
    fetched = await agents.get(created.id)
    listed = await agents.list()

    # Reached-the-subject check: each call went through the production module
    # to the transport, rather than being short-circuited somewhere upstream.
    assert http.calls == [
        ("POST", "/api/v1/agents"),
        ("GET", "/api/v1/agents/agent-1"),
        ("GET", "/api/v1/agents"),
    ]
    assert created.workspace_id is None
    assert fetched.workspace_id is None
    assert [a.id for a in listed.items] == ["agent-1", "agent-2"]


@pytest.mark.parametrize("model", _MODELS, ids=lambda m: m.__name__)
def test_required_id_still_rejects_null(model: type[BaseModel]) -> None:
    # Second control, on the identity field: the fix did not relax the model.
    with pytest.raises(ValidationError):
        model(**{**_PAYLOADS[model], "workspace_id": None, "id": None})


def test_objectives_normalizer_keeps_null_workspace_id() -> None:
    # client.objectives builds Objective through this normalizer, not directly.
    # It used to coerce a null to "" because the field was a required str; that
    # hid "no workspace" behind an empty string the caller could send back.
    from aegis_sdk.execution.objectives import _normalize_objective

    raw = {
        "id": "o-1",
        "title": "t",
        "description": "d",
        "agent_id": "agent-1",
        "status": "draft",
        "organization_id": "org-1",
        "workspace_id": None,
        "created_by_user_id": "u-1",
        "created_at": _TS,
        "updated_at": _TS,
    }
    assert Objective(**_normalize_objective(raw)).workspace_id is None
    assert Objective(**_normalize_objective({**raw, "workspace_id": "ws-1"})).workspace_id == "ws-1"


# The one response model allowed to keep a required workspace_id: it is the
# payload of the Workspaces endpoint itself, where the id is the subject, not a
# nullable back-reference.
_REQUIRED_WORKSPACE_ALLOWLIST = {"WorkspaceDocumentAttachment"}


def test_no_other_model_requires_workspace_id() -> None:
    # Completeness: a hand-listed parametrization cannot notice a seventh model.
    import importlib
    import pkgutil

    import aegis_sdk

    seen: dict[str, type[BaseModel]] = {}
    for pkg in ("aegis_sdk.core", "aegis_sdk.modules", "aegis_sdk.execution"):
        root = importlib.import_module(pkg)
        for info in pkgutil.walk_packages(root.__path__, prefix=f"{pkg}."):
            mod = importlib.import_module(info.name)
            for obj in vars(mod).values():
                if isinstance(obj, type) and issubclass(obj, BaseModel):
                    seen[f"{obj.__module__}.{obj.__qualname__}"] = obj
    for obj in vars(importlib.import_module("aegis_sdk.types")).values():
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            seen[f"{obj.__module__}.{obj.__qualname__}"] = obj

    assert len(seen) > 50, "positive control: the walk must actually find models"
    offenders = sorted(
        name
        for name, m in seen.items()
        if name.startswith(aegis_sdk.__name__)
        and "workspace_id" in m.model_fields
        and m.model_fields["workspace_id"].is_required()
        and m.__name__ not in _REQUIRED_WORKSPACE_ALLOWLIST
    )
    assert offenders == []
