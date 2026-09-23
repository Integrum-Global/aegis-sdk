"""``skills.duplicate()`` fails loudly and locally, and never reaches the wire.

WHY THIS FILE EXISTS

``POST /api/v1/skills/{id}/duplicate`` is not served, so every call this method
made answered 404 — while three handbook chapters described it as *"the honest
way to fork a skill"*. Skills are the one configurable object the client reaches
with no fork operation; agents and pipelines both have one, and the method
generalised their convention to a resource the platform never implemented.

It is now a named, throwing stub, kept rather than deleted so a caller gets a
message naming the gap instead of an ``AttributeError``.

WHAT THESE TESTS PIN, AND HOW A GREEN COULD BE WRONG

The exception type and the deprecation warning are the easy half. The control is
the third test: **no request may be issued**. A stub that still sent the request
would raise the same exception and pass a naive test, while continuing to put a
doomed call on the wire — and, on a future server that does serve the route,
would silently start working in a method documented as non-functional.
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from aegis_sdk.core.skills import SkillsModule
from aegis_sdk.exceptions import UnsupportedOperationError


class _RecordingHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, path))
        return {}


def _module() -> tuple[SkillsModule, _RecordingHTTP]:
    http = _RecordingHTTP()
    return SkillsModule(http), http  # type: ignore[arg-type]


async def test_it_raises_unsupported_operation_error() -> None:
    module, _ = _module()
    with pytest.raises(UnsupportedOperationError):
        await module.duplicate("skill-1", name="Copy")


async def test_it_warns_before_it_raises() -> None:
    module, _ = _module()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(UnsupportedOperationError):
            await module.duplicate("skill-1", name="Copy")
    assert [w.category for w in caught] == [DeprecationWarning]


async def test_it_never_reaches_the_wire() -> None:
    """Control: the route is unserved, so a stub that still sent would 404."""
    module, http = _module()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(UnsupportedOperationError):
            await module.duplicate("skill-1", name="Copy")
    assert http.calls == [], "no request may be issued for an unserved route"


async def test_the_message_names_the_alternative() -> None:
    module, _ = _module()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(UnsupportedOperationError) as caught:
            await module.duplicate("skill-1", name="Copy")
    assert "create" in str(caught.value)
