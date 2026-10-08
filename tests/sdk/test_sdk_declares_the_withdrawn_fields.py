"""The SDK's posture-approval models cover every field the SERVER emits.

WHY THIS EXISTS. A ``POST `` to withdraw a pending posture request closes the row
as ``withdrawn`` and records who retracted it. The server has emitted the four
``withdrawn*`` fields since
``Integrum-Global/aegis`` #1349 landed, and until this change the SDK declared
none of them.

That is not a cosmetic gap. Both SDK models are pydantic models, and pydantic
DROPS an undeclared key by default — so a caller reading a withdrawn row saw a
record with no retraction on it at all. Worse, it is invisible: the parse
succeeds, the row type is right, and the four fields simply are not there. The
earlier revision of this work recorded the gap in the CHANGELOG rather than
declaring the fields, which is honest but leaves every consumer of a withdrawn
row unable to tell a RETRACTION from a row nobody has decided yet.

THE CONTRACT IS VENDORED, NOT REFERENCED. ``posture_approval_response_golden.json``
beside this file is a faithful copy of the server's golden at
``Integrum-Global/aegis`` ``tests/deployment/posture_approval_response_golden.json``,
taken at the commit recorded in its ``_vendored_from`` block. aegis-sdk is a
separate repository and cannot read the server's test tree at test time, so the
contract has to travel with the SDK. **Nothing detects drift between the two
copies** — re-sync manually when the server model changes. The server-side test
is the one that reddens on a server change; this one reds when the SDK stops
covering what the server already sends.

EVERY ASSERTION HERE IS BIPOLAR, because the defect this file guards against is
a SILENT one. ``test_the_control_fails_when_a_declared_field_is_removed`` drives
the comparison with a field removed and requires it to fail — without it, a
subset assertion over an accidentally-empty set passes over nothing
(``instrument-discipline.md`` MUST-1).
"""

from __future__ import annotations

import json
from pathlib import Path

from aegis_sdk.modules.trust_posture import PostureApproval
from aegis_sdk.trust.postures import PostureApprovalRecord

GOLDEN = Path(__file__).resolve().parent / "posture_approval_response_golden.json"

#: The four fields the retraction writer populates. Named individually because
#: they are the ones that were missing, and a future removal should red with a
#: message about THEM rather than as an anonymous set difference.
WITHDRAWN_FIELDS = ("withdrawnBy", "withdrawnByName", "withdrawnAt", "withdrawalNotes")


def _golden_fields() -> dict[str, str]:
    return dict(json.loads(GOLDEN.read_text(encoding="utf-8"))["fields"])


def _wire_keys(model: type) -> set[str]:
    """The wire names a pydantic model accepts: its ``alias`` if it has one."""
    return {f.alias or name for name, f in model.model_fields.items()}


def _missing(model: type) -> list[str]:
    return sorted(set(_golden_fields()) - _wire_keys(model))


# ───────────────────────── the contract, both models ─────────────────────────


def test_the_sdk_trust_surface_declares_every_field_the_server_emits() -> None:
    """``PostureApprovalRecord`` drops nothing the server sends."""
    assert not _missing(PostureApprovalRecord), (
        f"aegis_sdk.trust.postures.PostureApprovalRecord does not declare "
        f"{_missing(PostureApprovalRecord)}, which the server emits on "
        f"PostureApprovalResponse. Pydantic DROPS an undeclared key silently, so "
        f"a caller reading such a row gets a record that simply does not have "
        f"the field — no error, no warning."
    )


def test_the_sdk_module_surface_declares_every_field_the_server_emits() -> None:
    """``PostureApproval`` (the module surface's record) drops nothing either.

    BOTH surfaces are checked because they are separate classes and the gap
    this file closes existed on both: the trust surface and the module surface
    each parse the same response.
    """
    assert not _missing(PostureApproval), (
        f"aegis_sdk.modules.trust_posture.PostureApproval does not declare "
        f"{_missing(PostureApproval)} from the server's PostureApprovalResponse."
    )


def test_the_four_withdrawn_fields_are_declared_on_both_models() -> None:
    """Named individually, so a regression names THEM rather than a set."""
    for model in (PostureApprovalRecord, PostureApproval):
        keys = _wire_keys(model)
        missing = [f for f in WITHDRAWN_FIELDS if f not in keys]
        assert not missing, (
            f"{model.__module__}.{model.__name__} does not declare {missing}. "
            f"These four are written by the retraction path; without them a "
            f"withdrawn row is indistinguishable from one nobody has decided."
        )


def test_a_withdrawn_row_round_trips_with_its_retraction_intact() -> None:
    """The behavioural half: the values actually LAND, on both models.

    The set assertions above would pass on a model that declared the aliases and
    then dropped the values; this parses a realistic withdrawn envelope and reads
    them back.
    """
    row = {
        "id": "apr_1",
        "agentId": "agent_1",
        "requestedPosture": "shared_planning",
        "currentPosture": "supervised",
        "reason": "needs approval",
        "requestedBy": "user-requester",
        "requestedByName": "Wendy Requester",
        "requestedAt": "2026-10-02T00:00:00+00:00",
        "status": "withdrawn",
        "reviewedBy": None,
        "reviewedByName": None,
        "reviewedAt": None,
        "reviewNotes": None,
        "withdrawnBy": "user-retractor",
        "withdrawnByName": "Wendy Retractor",
        "withdrawnAt": "2026-10-03T09:30:00+00:00",
        "withdrawalNotes": "the requester retracted this",
        "expiresAt": None,
        "config": {},
    }

    for model in (PostureApprovalRecord, PostureApproval):
        parsed = model(**row)
        where = f"{model.__module__}.{model.__name__}"
        assert parsed.withdrawn_by == "user-retractor", where
        assert parsed.withdrawn_by_name == "Wendy Retractor", where
        assert parsed.withdrawal_notes == "the requester retracted this", where
        assert parsed.withdrawn_at is not None, where
        assert parsed.reviewed_by is None and parsed.reviewed_at is None, (
            f"{where}: a withdrawn row must keep the reviewed* group None. A "
            f"retraction is not a decision, and a populated reviewed_by would "
            f"assert a review that never happened."
        )


def test_the_withdrawn_fields_are_nullable_so_a_pending_row_still_parses() -> None:
    """The other direction, and the one a drift would break first.

    The server marks all four ``str | None``. Most rows are NOT withdrawn, so a
    field declared non-nullable here would reject every pending row — a total
    outage of the surface, not a missing column.
    """
    pending = {
        "id": "apr_2",
        "agentId": "agent_1",
        "requestedPosture": "shared_planning",
        "currentPosture": "supervised",
        "reason": "needs approval",
        "requestedBy": "user-requester",
        "requestedByName": "Wendy Requester",
        "requestedAt": "2026-10-02T00:00:00+00:00",
        "status": "pending",
        "config": {},
    }
    for model in (PostureApprovalRecord, PostureApproval):
        parsed = model(**pending)
        assert parsed.withdrawn_by is None
        assert parsed.withdrawn_at is None
        assert parsed.withdrawal_notes is None


# ───────────────────────── controls, both directions ─────────────────────────


def test_the_vendored_golden_is_non_empty_and_typed() -> None:
    """CONTROL — an empty golden makes every set assertion above vacuous."""
    fields = _golden_fields()
    assert fields, f"{GOLDEN.name} carries no fields"
    assert all(isinstance(v, str) and v for v in fields.values()), (
        f"{GOLDEN.name} carries a field with no TYPE; the server's golden pins "
        f"types and this copy must too, or the two disagree about the contract"
    )
    assert set(WITHDRAWN_FIELDS) <= set(fields), (
        f"{GOLDEN.name} does not carry all four withdrawn fields, so the tests "
        f"above are asserting nothing about the fields this change is about"
    )


def test_the_control_fails_when_a_declared_field_is_removed() -> None:
    """BIPOLAR CONTROL — the comparison must be able to return the OTHER answer.

    Driven against a stand-in whose only difference from the real model is a
    REMOVED field. If ``_missing`` returned ``[]`` unconditionally — a renamed
    key, an empty extraction — every assertion in this file would pass over
    nothing, which is exactly the failure mode the withdrawn fields arrived
    through in the first place.
    """

    class _WithoutWithdrawnBy(PostureApprovalRecord):
        pass

    del _WithoutWithdrawnBy.model_fields["withdrawn_by"]

    assert _missing(PostureApprovalRecord) == []
    assert _missing(_WithoutWithdrawnBy) == ["withdrawnBy"], (
        "removing a declared field did not make the comparison fail, so the "
        "comparison is not measuring the model's field set"
    )
