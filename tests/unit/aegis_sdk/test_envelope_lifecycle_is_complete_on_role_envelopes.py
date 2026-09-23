"""An envelope created on ``client.role_envelopes`` can be made effective there.

WHY THIS FILE EXISTS

``create`` exists only on ``client.role_envelopes``, and an envelope is born
``status="draft"``. ``activate`` used to exist only on ``client.trust_posture``,
so the two halves of one lifecycle lived on two modules: the module a standup
caller reaches first could produce a draft and nothing else. A draft constrains
nothing, which is what made the gap silent — the create succeeded, the envelope
existed, and no constraint was ever enforced.

WHAT THESE TESTS PIN, AND HOW A GREEN COULD BE WRONG

Each verb issues the route the server serves. The control is the route itself: a
method that merely exists, posting to a path nobody serves, passes "the
attribute is there" and fails here. The clearance check is pinned the same way —
it must refuse BEFORE any request is sent, so a rejection that still reached the
server would be caught.
"""

from __future__ import annotations

from typing import Any

import pytest

from aegis_sdk.standup.envelopes import RoleEnvelopesModule

_ENVELOPE = "env-1"
_BASE = f"/api/v1/role-envelopes/{_ENVELOPE}"


class _RecordingHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, path, kwargs.get("json_data")))
        return {"id": _ENVELOPE}


def _module() -> tuple[RoleEnvelopesModule, _RecordingHTTP]:
    http = _RecordingHTTP()
    return RoleEnvelopesModule(http), http  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("verb", "method", "path"),
    [
        ("activate", "POST", f"{_BASE}/activate"),
        ("suspend", "POST", f"{_BASE}/suspend"),
    ],
)
async def test_lifecycle_verbs_issue_their_route(verb: str, method: str, path: str) -> None:
    module, http = _module()
    await getattr(module, verb)(_ENVELOPE)
    assert http.calls[0][:2] == (method, path)


async def test_update_sends_only_the_fields_you_named() -> None:
    module, http = _module()
    await module.update(_ENVELOPE, clearance_ceiling="confidential")
    method, path, body = http.calls[0]
    assert (method, path) == ("PUT", _BASE)
    assert body == {"clearance_ceiling": "confidential"}


async def test_update_never_carries_status_so_the_fsm_cannot_be_bypassed() -> None:
    """Status moves through activate/suspend/delete, never through an edit."""
    module, http = _module()
    await module.update(_ENVELOPE, review_at="2026-10-01T00:00:00Z")
    assert "status" not in (http.calls[0][2] or {})


async def test_update_refuses_an_unknown_clearance_before_sending() -> None:
    """Control: a local refusal that still reached the server would pass a
    naive 'it raised' test."""
    module, http = _module()
    with pytest.raises(ValueError):
        await module.update(_ENVELOPE, clearance_ceiling="ultra")
    assert http.calls == []


async def test_delete_issues_its_route() -> None:
    module, http = _module()
    await module.delete(_ENVELOPE)
    assert http.calls[0][:2] == ("DELETE", _BASE)
