"""A requester can retract their OWN pending posture request, on both surfaces.

Before this existed, a pending request had two exits -- approve and reject --
and both are somebody else's decision. A requester who changed their mind had
to reject their own request, which closed the row as ``rejected`` and recorded
``reviewed_by`` for a decision nobody made. Withdrawing closes it as
``withdrawn`` and records the withdrawer instead.

TWO THINGS HERE ARE PINNED BECAUSE THEY ARE EASY TO GET WRONG IN OPPOSITE
DIRECTIONS, and both were.

1. THE PATH IS NOT ITS SIBLINGS' SHAPE. The approve and reject routes are
   addressed by agent (``/agents/{agent_id}/trust-posture/...``). Withdraw is
   served under its own ``/trust-posture`` prefix. A reader who assumes the
   sibling shape is wrong, and the failure is a 404 that reads like a missing
   deployment rather than a wrong URL.

2. THE IDENTIFIER MUST BIND. The route declares ``request_id``; a camelCase
   spelling is dropped by pydantic's default ``extra='ignore'`` and arrives as
   ``None``. That is not a visible error -- with more than one request pending
   the server refuses as AMBIGUOUS, so a caller who named their target is told
   they did not. Every wire assertion here parses the outgoing body through a
   model declaring the route's own field and asserts the value BINDS, rather
   than pinning the literal key this SDK happens to send. A literal assertion
   pins what we send and says nothing about what the route reads; that is
   exactly how the sibling defect survived its own test suite.

Tier 1: the HTTP layer is mocked, as in
``test_sdk_posture_reject_disambiguation.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from aegis_sdk.modules.trust_posture import TrustPostureModule
from aegis_sdk.trust.postures import PosturesModule

#: The route the platform SERVES. Not the siblings' shape.
WITHDRAW_URL = "/api/v1/trust-posture/agent_1/withdraw"

#: The shape a sibling-shaped guess would produce, asserted AGAINST below.
SIBLING_SHAPED_URL = "/api/v1/agents/agent_1/trust-posture/withdraw"


class _WithdrawBody(BaseModel):
    """The route's withdraw body AS THE ROUTE DECLARES IT.

    ``request_id`` addresses the request; the route declares no alias, so
    ``requestId`` and ``approvalId`` alike are dropped on arrival and bind as
    ``None``. Parsing through this model is what makes the assertion about the
    ROUTE rather than about this SDK's spelling.
    """

    notes: str = Field(..., min_length=10)
    request_id: str | None = None


def _bound_identifier(sent: dict) -> str | None:
    """Parse an outgoing body the way the route does, and return what binds."""
    return _WithdrawBody(**sent).request_id


# A withdrawn record. ``status`` is where the difference from a rejection
# shows, and the reviewer fields stay null: nobody reviewed it.
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
    http.request = AsyncMock(return_value=WITHDRAWN_BODY)
    return http


@pytest.mark.asyncio
class TestWithdrawOnTheTrustSurface:
    async def test_posts_to_the_route_the_platform_serves(self, mock_http):
        """The falsifying case: the sibling-shaped path must fail this."""
        await PosturesModule(mock_http).withdraw_transition("agent_1", "no longer needed")

        args, _kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == WITHDRAW_URL
        assert args[1] != SIBLING_SHAPED_URL, (
            "withdraw was re-pointed at the siblings' agent-scoped shape. The "
            "platform serves this route under its own /trust-posture prefix; "
            "the sibling-shaped path is a 404 that reads like a missing "
            "deployment rather than a wrong URL."
        )

    async def test_the_identifier_binds_under_the_key_the_route_declares(self, mock_http):
        await PosturesModule(mock_http).withdraw_transition(
            "agent_1", "superseded by the revised request", approval_id="approval_b"
        )

        _args, kwargs = mock_http.request.call_args
        assert _bound_identifier(kwargs["json_data"]) == "approval_b", (
            "the identifier did not bind when parsed as the route declares it. "
            "A camelCase key is dropped by pydantic's extra='ignore', so "
            "request_id arrives None and a caller who named their target is "
            "refused as ambiguous."
        )

    async def test_body_carries_no_identifier_key_beside_the_one_that_binds(self, mock_http):
        """Stated separately because this is the defect the sibling decision
        calls had. A future edit that 'harmonises' withdraw with them must
        fail here, loudly."""
        await PosturesModule(mock_http).withdraw_transition(
            "agent_1", "superseded by the revised request", approval_id="approval_b"
        )

        _args, kwargs = mock_http.request.call_args
        body = kwargs["json_data"]
        assert "approvalId" not in body
        assert "requestId" not in body
        assert set(body) == {"notes", "request_id"}

    async def test_omitted_identifier_is_absent_not_null(self, mock_http):
        """The single-pending wire body stays minimal -- no null, no empty
        string. ``notes`` is a required field of the route's model, so sending
        null for the identifier would be a different body, not a smaller one."""
        await PosturesModule(mock_http).withdraw_transition("agent_1", "no longer needed")

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "no longer needed"}

    async def test_the_withdrawn_record_is_returned(self, mock_http):
        record = await PosturesModule(mock_http).withdraw_transition("agent_1", "no longer needed")

        assert record["id"] == "approval_b"
        assert record["status"] == "withdrawn"
        assert record["reviewedBy"] is None

    async def test_notes_is_required(self, mock_http):
        """The route applies a >= 10 character floor. The SDK makes the
        argument mandatory so a missing reason is refused locally rather than
        by a round trip."""
        with pytest.raises(TypeError):
            await PosturesModule(mock_http).withdraw_transition("agent_1")


@pytest.mark.asyncio
class TestWithdrawOnTheModuleSurface:
    """Enforcement-surface parity: this SDK has two posture surfaces and both
    need the operation, or fixing one ships the defect on the other."""

    async def test_posts_to_the_route_the_platform_serves(self, mock_http):
        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        args, _kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == WITHDRAW_URL

    async def test_the_identifier_binds_under_the_key_the_route_declares(self, mock_http):
        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "superseded by the revised request", approval_id="approval_b"
        )

        _args, kwargs = mock_http.request.call_args
        assert _bound_identifier(kwargs["json_data"]) == "approval_b"

    async def test_omitted_identifier_is_absent_not_null(self, mock_http):
        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "no longer needed"}

    async def test_the_withdrawn_record_is_typed(self, mock_http):
        record = await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        assert record.id == "approval_b"
        assert record.status == "withdrawn"
        assert record.reviewed_by is None

    async def test_a_server_that_adds_withdrawal_fields_does_not_break_the_caller(self, mock_http):
        """Forward-compatibility, and the reason the typed model declares no
        withdrawal-specific fields.

        A deployment MAY add ``withdrawnBy`` / ``withdrawnAt`` to this response
        (this SDK cannot see the platform's source, and the route's design is
        not a promise about its future). Declaring them here would make them
        read ``None`` for every call against a server that does not send them,
        which is indistinguishable from the server having sent null. Not
        declaring them must still not CRASH when a server does send them.
        """
        mock_http.request.return_value = {
            **WITHDRAWN_BODY,
            "withdrawnBy": "user_2",
            "withdrawnAt": "2026-09-15T02:00:00+00:00",
            "withdrawalNotes": "changed my mind",
        }

        record = await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        assert record.status == "withdrawn"
        assert record.id == "approval_b"
