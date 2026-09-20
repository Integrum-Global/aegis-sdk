"""Tier 1: a deployment may legitimately omit ``workspace_id`` from a reply.

The SDK is a client. It talks to deployments that are not all at the same
version, so a response model that *requires* a non-null ``workspace_id``
turns an otherwise-successful call into a ``ValidationError`` after the
server has already acted. For a create that is the expensive shape: the
resource exists, the caller sees a failure, and a retry leaves a duplicate.

Widening the field costs nothing against a deployment that populates it.

Two halves, deliberately:

* the DERIVED half walks the whole package and holds *every* model that
  declares ``workspace_id`` — including one nobody has written yet;
* the CONTROL half pins that the widening was targeted, not blanket.
  ``id`` and ``organization_id`` still refuse null.

A null must also stay ``None`` through normalisation. Coercing it to ``""``
hands the caller an empty string that reads as a real workspace id and can
be sent back as a filter.
"""

from __future__ import annotations

import enum
import importlib
import pkgutil
import sys
import types
from datetime import UTC, datetime
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import aegis_sdk
from aegis_sdk.execution.objectives import _normalize_objective

FIELD = "workspace_id"
CONTROL_FIELDS = ("id", "organization_id")


def _import_every_submodule() -> None:
    """Import the whole package so the model walk sees every declaration.

    A model in an unimported module is invisible to the walk, and an
    invisible model is indistinguishable from one that does not exist.
    """
    for module in pkgutil.walk_packages(aegis_sdk.__path__, f"{aegis_sdk.__name__}."):
        importlib.import_module(module.name)


def _models_declaring(field: str) -> dict[str, type[BaseModel]]:
    """Every pydantic model in the package that declares ``field``.

    Derived from the tree, never hand-listed: a hand-written list is the
    defect, because it stays green on the day a new model is added.
    """
    _import_every_submodule()
    found: dict[str, type[BaseModel]] = {}
    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith(aegis_sdk.__name__):
            continue
        for attribute in dir(module):
            candidate = getattr(module, attribute, None)
            if not isinstance(candidate, type) or not issubclass(candidate, BaseModel):
                continue
            if candidate is BaseModel or field not in candidate.model_fields:
                continue
            found[f"{candidate.__module__}.{candidate.__qualname__}"] = candidate
    return found


MODELS = _models_declaring(FIELD)


def _dummy(annotation: Any) -> Any:
    """A type-appropriate placeholder, so a model can be built from its own
    declared requirements rather than from a payload written out by hand."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        for arg in get_args(annotation):
            if arg is not type(None):
                return _dummy(arg)
        return None
    if origin in (list, set, tuple):
        return []
    if origin is dict:
        return {}
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return next(iter(annotation))
        if issubclass(annotation, bool):
            return False
        if issubclass(annotation, int):
            return 1
        if issubclass(annotation, float):
            return 1.0
        if issubclass(annotation, datetime):
            return datetime(2026, 1, 1, tzinfo=UTC)
        if issubclass(annotation, str):
            return "x"
    return "x"


def _payload(model: type[BaseModel]) -> dict[str, Any]:
    """Minimal payload satisfying every required field except ``workspace_id``."""
    return {
        name: _dummy(field.annotation)
        for name, field in model.model_fields.items()
        if field.is_required() and name != FIELD
    }


def _constructible() -> list[tuple[str, type[BaseModel]]]:
    """Models that accept a generically-built payload.

    A model this harness cannot build is reported rather than silently
    skipped -- see ``test_behavioural_harness_is_not_vacuous``.
    """
    ok = []
    for name, model in sorted(MODELS.items()):
        try:
            model(**{**_payload(model), FIELD: "ws-real"})
        except ValidationError:
            continue
        ok.append((name, model))
    return ok


CONSTRUCTIBLE = _constructible()


# --- the walk: complete over the package, no model exempt -------------------


def test_the_walk_actually_found_models() -> None:
    """Positive control. An empty walk and a clean walk print the same thing."""
    assert MODELS, "the model walk found nothing -- the walk is broken, not the tree"
    assert len(MODELS) >= 7, f"expected the known declarations, walk saw {len(MODELS)}"


@pytest.mark.parametrize("name", sorted(MODELS))
def test_every_model_declaring_workspace_id_admits_none(name: str) -> None:
    """The completeness assertion: this fails for a model nobody listed here.

    Checked against the field's own annotation rather than a constructed
    instance, so it holds even for a model this file cannot build.
    """
    field = MODELS[name].model_fields[FIELD]
    TypeAdapter(field.annotation).validate_python(None)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_every_model_declaring_workspace_id_allows_it_absent(name: str) -> None:
    """A deployment that omits the key entirely is the same case as null."""
    assert not MODELS[name].model_fields[FIELD].is_required()


# --- behaviour: real instances, all three cases -----------------------------


def test_behavioural_harness_is_not_vacuous() -> None:
    """Without this, an all-skipped behavioural suite reads as a pass."""
    assert CONSTRUCTIBLE, "no model could be built -- the behavioural cases prove nothing"


@pytest.mark.parametrize("name,model", CONSTRUCTIBLE, ids=[n for n, _ in CONSTRUCTIBLE])
def test_null_workspace_id_parses(name: str, model: type[BaseModel]) -> None:
    assert model(**{**_payload(model), FIELD: None}).workspace_id is None


@pytest.mark.parametrize("name,model", CONSTRUCTIBLE, ids=[n for n, _ in CONSTRUCTIBLE])
def test_absent_workspace_id_parses(name: str, model: type[BaseModel]) -> None:
    assert model(**_payload(model)).workspace_id is None


@pytest.mark.parametrize("name,model", CONSTRUCTIBLE, ids=[n for n, _ in CONSTRUCTIBLE])
def test_real_workspace_id_is_preserved(name: str, model: type[BaseModel]) -> None:
    """The widening must not quietly discard a value the server did send."""
    assert model(**{**_payload(model), FIELD: "ws-real"}).workspace_id == "ws-real"


# --- control: the widening was targeted, not blanket ------------------------


@pytest.mark.parametrize("control", CONTROL_FIELDS)
def test_identity_fields_still_reject_null(control: str) -> None:
    """If these ever accept null, the widening has gone further than intended.

    Asserted across every constructible model that declares the field, so
    the control cannot pass on a single lucky example.
    """
    checked = 0
    for _name, model in CONSTRUCTIBLE:
        field = model.model_fields.get(control)
        if field is None or not field.is_required():
            continue
        checked += 1
        with pytest.raises(ValidationError):
            model(**{**_payload(model), FIELD: "ws-real", control: None})
    assert checked, f"no constructible model requires {control!r} -- control is vacuous"


# --- normalisation: a null stays a null -------------------------------------


def test_normalizer_returns_none_for_a_null_workspace_id() -> None:
    assert _normalize_objective({"workspace_id": None})["workspace_id"] is None


def test_normalizer_returns_none_when_the_key_is_absent() -> None:
    assert _normalize_objective({})["workspace_id"] is None


def test_normalizer_preserves_a_real_workspace_id() -> None:
    assert _normalize_objective({"workspace_id": "ws-real"})["workspace_id"] == "ws-real"


def test_normalizer_output_is_accepted_by_the_objective_model() -> None:
    """The normaliser feeds ``Objective``; a null it emits must parse there.

    This is the round trip the two halves above cannot see on their own.
    """
    from aegis_sdk.types import Objective

    normalized = _normalize_objective({})
    built = Objective(
        **{
            **{
                name: _dummy(field.annotation)
                for name, field in Objective.model_fields.items()
                if field.is_required() and name not in normalized
            },
            **normalized,
        }
    )
    assert built.workspace_id is None
