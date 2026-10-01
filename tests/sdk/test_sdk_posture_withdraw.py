"""A requester can retract their OWN pending posture request, on both surfaces.

Before this existed, a pending request had two exits — approve and reject —
and both are somebody else's decision. A requester who changed their mind had
to reject their own request, which closes the row as ``rejected`` and records
a reviewer for a decision nobody made. Withdrawing closes it as ``withdrawn``
with no reviewer recorded.

THE WIRE KEY IS THE POINT OF MOST OF THIS FILE. The withdraw route declares
``request_id``; its model carries no camelCase alias, so ``requestId`` and
``approvalId`` are both dropped on arrival. A dropped key is not a visible
error — the server just sees "no target named", and with more than one
request pending it refuses as ambiguous. So a caller who DID name their
target is told their request was ambiguous, which reads as a server quirk
rather than as the client sending the wrong key. The sibling decision calls
in this module send ``approvalId`` today; these tests pin withdraw to the key
that actually arrives.

Every wire assertion here is EXACT (``==`` on the whole body), so a change to
a camelCase key fails them rather than passing on a substring.

Tier 1: the HTTP layer is mocked, as in ``test_sdk_posture_reject_disambiguation.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from aegis_sdk.modules.trust_posture import TrustPostureModule
from aegis_sdk.trust.postures import PosturesModule


class _DecisionBody(BaseModel):
    """The withdraw route's request body AS THE ROUTE DECLARES IT.

    `request_id` and nothing else addresses the request. The route has no
    alias generator, so pydantic's default `extra='ignore'` drops every
    other spelling -- `requestId` and `approvalId` alike -- and the field
    arrives as `None`.
    """

    notes: str | None = None
    request_id: str | None = None


def _bound_identifier(sent: dict) -> str | None:
    """Parse an outgoing body the way the route does, and return what binds.

    Asserting the EFFECT rather than the spelling. A literal assertion pins
    what this SDK sends and says nothing about what the route reads, which is
    how the sibling calls shipped `approvalId` for the life of the defect
    while a test pinned it and passed.

    Cannot see the ROUTE changing: this encodes the contract measured on
    2026-10-01. It fails when this SDK sends something else.
    """
    return _DecisionBody(**sent).request_id

WITHDRAW_URL = "/api/v1/agents/agent_1/trust-posture/withdraw"

# A withdrawn record. ``status`` is where the difference from a rejection
# shows: there is no reviewer, because nobody reviewed it.
WITHDRAWN_BODY = {
    "id": "approval_b",
    "agentId": "agent_1",
    "requestedPosture": "continuous_insight",
    "currentPosture": "shared_planning",
    "reason": "second request",
    "requestedBy": "user_2",
    "requestedByName": "Operator Two",
    "requestedAt": "2026-09-15T00:00:00+00:00",
    "status": "withdrawn",
    "reviewedBy": None,
    "reviewedByName": None,
    "reviewedAt": None,
    "reviewNotes": None,
    "expiresAt": None,
    "config": {},
}


@pytest.fixture
def mock_http():
    http = MagicMock()
    http.request = AsyncMock()
    return http


@pytest.mark.asyncio
class TestWithdrawOnTheTrustSurface:
    async def test_request_id_goes_on_the_wire_under_that_exact_key(self, mock_http):
        """The falsifying case: a camelCase key must fail this, not pass it."""
        mock_http.request.return_value = WITHDRAWN_BODY

        await PosturesModule(mock_http).withdraw_transition(
            "agent_1", "superseded by the revised request", request_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == WITHDRAW_URL
        assert _bound_identifier(kwargs["json_data"]) == "approval_b", (
            "the supplied identifier did not bind to the route's field -- the "
            f"caller named a target the route cannot see. sent={kwargs['json_data']!r}"
        )
        assert kwargs["json_data"] == {
            "notes": "superseded by the revised request",
            "request_id": "approval_b",
        }

    async def test_camelcase_key_is_not_what_is_sent(self, mock_http):
        """Stated separately because this is the defect the module already has
        on its four decision calls. A future edit that "harmonises" withdraw
        with those siblings must fail here, loudly, with the reason."""
        mock_http.request.return_value = WITHDRAWN_BODY

        await PosturesModule(mock_http).withdraw_transition(
            "agent_1", "superseded by the revised request", request_id="approval_b"
        )

        _args, kwargs = mock_http.request.call_args
        body = kwargs["json_data"]
        assert "approvalId" not in body, (
            "withdraw sends `approvalId`. That key is dropped by the server, so "
            "`request_id` arrives None and a caller who named their target is "
            "refused as ambiguous."
        )
        assert "requestId" not in body, (
            "withdraw sends `requestId`. The route declares `request_id` with no "
            "camelCase alias, so this is dropped exactly as `approvalId` is."
        )

    async def test_omitted_request_id_is_absent_not_null(self, mock_http):
        """The single-pending wire body stays minimal — no null, no empty string."""
        mock_http.request.return_value = WITHDRAWN_BODY

        await PosturesModule(mock_http).withdraw_transition("agent_1", "no longer needed")

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "no longer needed"}
        assert _bound_identifier(kwargs["json_data"]) is None

    async def test_the_withdrawn_record_is_returned(self, mock_http):
        mock_http.request.return_value = WITHDRAWN_BODY

        record = await PosturesModule(mock_http).withdraw_transition("agent_1", "no longer needed")

        assert record["id"] == "approval_b"
        assert record["status"] == "withdrawn"
        assert record["reviewedBy"] is None

    async def test_notes_is_required(self, mock_http):
        """The route applies a >= 10 character floor. The SDK makes the
        argument mandatory so the refusal is local rather than a round trip."""
        with pytest.raises(TypeError):
            await PosturesModule(mock_http).withdraw_transition("agent_1")


@pytest.mark.asyncio
class TestWithdrawOnTheModuleSurface:
    """Enforcement-surface parity: this SDK has two posture surfaces and both
    need the operation, or fixing one ships the defect on the other."""

    async def test_request_id_goes_on_the_wire_under_that_exact_key(self, mock_http):
        mock_http.request.return_value = WITHDRAWN_BODY

        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "superseded by the revised request", request_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == WITHDRAW_URL
        assert _bound_identifier(kwargs["json_data"]) == "approval_b", (
            "the supplied identifier did not bind to the route's field -- the "
            f"caller named a target the route cannot see. sent={kwargs['json_data']!r}"
        )
        assert kwargs["json_data"] == {
            "notes": "superseded by the revised request",
            "request_id": "approval_b",
        }

    async def test_omitted_request_id_is_absent_not_null(self, mock_http):
        mock_http.request.return_value = WITHDRAWN_BODY

        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "no longer needed"}
        assert _bound_identifier(kwargs["json_data"]) is None

    async def test_the_withdrawn_record_is_typed(self, mock_http):
        mock_http.request.return_value = WITHDRAWN_BODY

        record = await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        assert record.id == "approval_b"
        assert record.status == "withdrawn"
        assert record.reviewed_by is None
