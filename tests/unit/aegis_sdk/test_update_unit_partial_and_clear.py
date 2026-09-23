"""``update_unit`` sends only what you named — except where nulling IS the point.

WHY THIS FILE EXISTS

``client.units`` gained an update route so a unit can be renamed. Units cannot be
merged, so before it the only remedy for a name typo was archive-and-rebuild.

The route takes a partial body where an ABSENT key means "leave unchanged". One
field breaks that rule on purpose: ``isolation_domain`` must be able to mean
UNASSIGN, which is an explicit ``null``, and only a key that is PRESENT with a
null value says so. A body built with the usual "drop every ``None``" idiom
therefore cannot clear the plane label at all — the call reports success, the
label stays, and nothing errors.

WHAT THESE TESTS PIN, AND HOW A GREEN COULD BE WRONG

1. A named field is sent alone: the body is exactly ``{"name": ...}``, so no
   unnamed field is accidentally sent as null. Without this, "the rename worked"
   would also describe a client that nulls every other column on every call.
2. Omitting ``isolation_domain`` leaves its key OUT of the body.
3. Passing ``isolation_domain=None`` puts the key IN, with a null. Claims 2 and 3
   are each other's control: a body that always omits passes 2, a body that
   always includes passes 3, and only a sentinel passes both.
4. A body with nothing to change raises rather than issuing a request that
   cannot alter anything.
"""

from __future__ import annotations

from typing import Any

import pytest

from aegis_sdk.standup.units import OrganizationUnitsModule

_UNIT = "unit-1"
_PATH = f"/api/v1/organization-units/{_UNIT}"


class _RecordingHTTP:
    """Records the method, the path and the JSON body of every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, path, kwargs.get("json_data")))
        return {"id": _UNIT}


def _module() -> tuple[OrganizationUnitsModule, _RecordingHTTP]:
    http = _RecordingHTTP()
    return OrganizationUnitsModule(http), http  # type: ignore[arg-type]


async def test_a_named_field_is_sent_alone() -> None:
    """No unnamed field may ride along as null."""
    module, http = _module()
    await module.update_unit(_UNIT, name="Accounts Payable")
    method, path, body = http.calls[0]
    assert (method, path) == ("PUT", _PATH)
    assert body == {"name": "Accounts Payable"}


async def test_omitting_isolation_domain_leaves_the_key_out() -> None:
    module, http = _module()
    await module.update_unit(_UNIT, name="Accounts Payable")
    assert "isolation_domain" not in (http.calls[0][2] or {})


async def test_passing_isolation_domain_none_sends_the_clear() -> None:
    """The control for the test above: unassign must be REACHABLE."""
    module, http = _module()
    await module.update_unit(_UNIT, isolation_domain=None)
    assert http.calls[0][2] == {"isolation_domain": None}


async def test_a_plane_label_can_also_be_assigned() -> None:
    module, http = _module()
    await module.update_unit(_UNIT, isolation_domain="plane-a")
    assert http.calls[0][2] == {"isolation_domain": "plane-a"}


async def test_status_is_reachable_so_a_unit_can_be_retired() -> None:
    module, http = _module()
    await module.update_unit(_UNIT, status="archived")
    assert http.calls[0][2] == {"status": "archived"}


async def test_an_empty_update_raises_and_sends_nothing() -> None:
    module, http = _module()
    with pytest.raises(ValueError):
        await module.update_unit(_UNIT)
    assert http.calls == [], "an unchangeable request must not reach the server"
