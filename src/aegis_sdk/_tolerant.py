"""The null-tolerant model base every SDK response model inherits.

A CLONED SDK TALKS TO MANY DEPLOYMENTS AT DIFFERENT VERSIONS — THAT IS THE
DELIVERY MODEL, NOT AN EDGE CASE. Partners clone this repository and point it at
whichever Aegis they run, and those servers do not move in lockstep with this
source. So a response model correct only against one server's exact contract is
not correct.

Concretely, and measured in the field: the same ``UserResponse`` field is
declared ``auth_type: str = "user"`` in one deployment's core and
``auth_type: str | None = None`` in another. The first can never emit null; the
second routinely does. ``client.auth.login()`` — the first call any integrator
makes — raised on an HTTP 200 because the SDK's own ``User`` model declared the
field non-optional WITH A DEFAULT, and a pydantic default applies only when a key
is ABSENT, never when it is present and null.

⛔ TOLERANCE IS OPT-IN, AND THAT DIRECTION IS THE POINT — IT WAS NOT ALWAYS
--------------------------------------------------------------------------------
The first version of this base tolerated null on EVERY defaulted field. That was
a FAIL-OPEN DEFAULT and it was reverted (see "the regression" below), because a
substituted default is only safe when it is a faithful reading of "absent" — and
this base cannot know that. So it asks. A field tolerates null **only** when
someone declared it with :func:`tolerant_null`, and every other defaulted field
raises exactly as it did before this base existed.

WHY NOT THE OTHER WAY ROUND: an opt-OUT list of dangerous fields would mean
enumerating the DANGEROUS set, which is unbounded and unknowable — any permissive
default nobody thought of stays silently fail-open forever. Declaring the SAFE
set is bounded, reviewable, and every member is a decision someone made on
purpose. When you cannot enumerate the dangerous set, invert and enumerate the
safe one.

Do not flip this default to tolerant-on. A field whose default GRANTS something —
``classification = "public"``, ``allows_export = True``, ``status = "active"``,
``email_verified = True`` — turns "the server told us nothing" into "the server
told us yes" under a tolerant default. That is not a hypothetical: it is
measured, and one instance re-opened a hazard whose own comment, seven lines
above the field, explained why it had been closed.

WHAT IT DOES, AND DELIBERATELY DOES NOT DO
------------------------------------------
For an incoming key whose value is ``None``, the key is DROPPED — so pydantic
applies the field's default — if and only if ALL hold:

  * the field is declared with :func:`tolerant_null`, and
  * the field has a DEFAULT (``is_required()`` is False).

Everything else is left exactly as it arrived:

  * a REQUIRED field receiving null still RAISES. A missing required value is a
    real defect and silently defaulting it would hide a server fault.
  * an OPTIONAL field receiving null KEEPS the null. There ``None`` is a
    meaningful value the server chose to send, and overwriting it with a default
    would destroy information — the failure mode this class exists to prevent,
    pointed the other way.
  * a defaulted field NOT marked tolerant still RAISES. Unmarked is the
    fail-closed default.

Scope: ONE dict level, and the DICT path only. Nested models validate through
their own base. ``model_config = ConfigDict(from_attributes=True)`` receives an
OBJECT with no keys to drop, so a null defaulted attribute still raises there —
behaviour byte-identical to plain ``BaseModel``, a LIMIT of this fix and not a
regression it introduced. ``model_construct`` bypasses validation entirely, by
design. Both are pinned by the SDK's own unit suite.

⚠ The base covers REQUEST models too, not only response models. ``types.py``
re-points ``SubscribeRequest`` / ``UpgradeRequest`` / ``CancelRequest`` /
``LicenseValidationRequest`` and they are built for outbound payloads. For an
unmarked field a caller-supplied ``None`` raises exactly as before, so the write
path is unchanged; but a MARKED request field would take its default and, under
``model_dump(exclude_none=True)``, send that default on the wire. Mark a request
model field only if you mean that.
"""

from __future__ import annotations

import types as _pytypes
import typing
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticUndefined

__all__ = ["TolerantModel", "tolerant_null", "annotation_admits_none", "TOLERANT_NULL_KEY"]

TOLERANT_NULL_KEY = "tolerant_null"


def tolerant_null(default: Any = PydanticUndefined, **kwargs: Any) -> Any:
    """Declare a field whose DEFAULT may stand in for an explicit server ``null``.

    Use this instead of ``Field(...)`` on the specific fields where a null is a
    faithful reading of "absent" — i.e. where the default IS what the server
    would have sent. ``User.auth_type`` is the canonical case: canon's server
    declares ``auth_type: str = "user"`` itself, so "user" is the server's own
    default rather than this SDK's guess.

    Do NOT reach for it to silence a validation error. Ask first whether the
    default GRANTS something; if it does, an unmarked field that raises loudly is
    the correct behaviour, because "the server sent something we do not
    understand" must not read as approval.

    Args:
        default: The field's default, or omit and pass ``default_factory=``.
        **kwargs: Passed through to :func:`pydantic.Field` unchanged, so
            ``alias=``, ``repr=False`` and ``default_factory=`` all work.
    """
    extra = dict(kwargs.pop("json_schema_extra", None) or {})
    extra[TOLERANT_NULL_KEY] = True
    if default is PydanticUndefined:
        return Field(**kwargs, json_schema_extra=extra)
    return Field(default, **kwargs, json_schema_extra=extra)


def _declared_tolerant(field: Any) -> bool:
    """True when a field was declared through :func:`tolerant_null`."""
    extra = field.json_schema_extra
    return isinstance(extra, dict) and extra.get(TOLERANT_NULL_KEY) is True



def _inbound_names(alias: Any) -> set[str]:
    """Every wire name pydantic would accept for a field as INPUT.

    Handles a plain string, an ``AliasPath`` (ignored — it addresses a nested
    location, not a top-level key this validator sees) and ``AliasChoices``,
    which carries several accepted names and would otherwise leave a marked
    field unable to recognise its own inbound keys.
    """
    if isinstance(alias, str):
        return {alias}
    choices = getattr(alias, "choices", None)
    if choices is None:
        return set()
    out: set[str] = set()
    for choice in choices:
        if isinstance(choice, str):
            out.add(choice)
    return out

def annotation_admits_none(annotation: Any) -> bool:
    """True when ``annotation`` accepts ``None`` as a legitimate value.

    Covers ``X | None``, ``Optional[X]``, ``Union[..., None]``, bare ``None`` and
    ``Any``. Anything unrecognised is treated as NOT admitting None, which here
    means "do not touch it" — the conservative direction, since the field will
    then simply keep raising as it did before.
    """
    if annotation is None or annotation is type(None):
        return True
    if annotation is Any:
        return True
    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is _pytypes.UnionType:
        return any(annotation_admits_none(arg) for arg in typing.get_args(annotation))
    return False


class TolerantModel(BaseModel):
    """Base for every SDK model parsed from a server response.

    See the module docstring for why this exists and why tolerance is opt-in. The
    drop-set is computed ONCE per subclass and cached on that subclass, so
    validation stays O(incoming keys) rather than O(declared fields) per instance.
    """

    # Populated lazily per subclass. Declared ClassVar so pydantic does not
    # mistake it for a field.
    _null_droppable_keys: ClassVar[frozenset[str] | None] = None

    @classmethod
    def _droppable_keys(cls) -> frozenset[str]:
        cached = cls.__dict__.get("_null_droppable_keys")
        if cached is not None:
            return cached
        keys: set[str] = set()
        for name, field in cls.model_fields.items():
            if not _declared_tolerant(field):
                continue
            if field.is_required():
                continue
            if annotation_admits_none(field.annotation):
                continue
            keys.add(name)
            # Only INPUT names belong in an input-matching set. ``alias`` is what
            # the server sends when one is set; ``validation_alias`` may override
            # it. ``serialization_alias`` is an OUTPUT name, which pydantic does
            # not accept as input — including it would let a null-valued key
            # carrying an output-only name be swallowed instead of rejected.
            keys.update(_inbound_names(field.alias))
            keys.update(_inbound_names(field.validation_alias))
        frozen = frozenset(keys)
        cls._null_droppable_keys = frozen
        return frozen

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls_for_declared_tolerant_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        droppable = cls._droppable_keys()
        if not droppable:
            return data
        offending = [k for k, v in data.items() if v is None and k in droppable]
        if not offending:
            return data
        # Copy only when there is something to remove — the common path must not
        # pay for an allocation it does not need.
        cleaned = dict(data)
        for k in offending:
            del cleaned[k]
        return cleaned
