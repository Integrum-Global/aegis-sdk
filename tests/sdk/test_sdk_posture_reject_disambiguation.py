"""A partner can say WHICH pending posture request to reject, and can tell a
duplicate request from a new one — through ``aegis_sdk`` alone.

ledger ``ewl-20260913-4137c62903``. ``approve_transition`` gained
``approval_id`` so two pending requests could be told apart; ``reject_transition``
did not, so with two pending requests a partner could approve either one but
reject neither (the server refuses an unqualified decision as ambiguous, and
the SDK had no way to qualify it).

The second half: the server no longer files a second pending request for a
transition that is already pending — it returns the existing one with
``alreadyPending: true``. A partner that retried after a timeout needs to see
that their own reason and config were NOT recorded, so the flag is surfaced as
``PostureChangeResult.already_pending``.

Tier 1: the HTTP layer is mocked, as in ``test_sdk_posture_approval_disambiguation.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.trust.postures import PosturesModule

REJECT_URL = "/api/v1/agents/agent_1/trust-posture/reject"

REJECTED_BODY = {
    "id": "approval_b",
    "agentId": "agent_1",
    "requestedPosture": "continuous_insight",
    "currentPosture": "shared_planning",
    "reason": "second request",
    "requestedBy": "user_2",
    "requestedByName": "Operator Two",
    "requestedAt": "2026-09-15T00:00:00+00:00",
    "status": "rejected",
    "reviewedBy": "user_3",
    "reviewedByName": "Reviewer",
    "reviewedAt": "2026-09-15T01:00:00+00:00",
    "reviewNotes": "insufficient evidence",
    "expiresAt": None,
    "config": {},
}


def _pending_body(*, already_pending: bool | None) -> dict:
    body: dict = {
        "approvalPending": True,
        "approvalId": "approval_existing",
        "approval": {
            "id": "approval_existing",
            "agentId": "agent_1",
            "requestedPosture": "shared_planning",
            "currentPosture": "supervised",
            "reason": "the request that was filed first",
            "requestedBy": "user_1",
            "status": "pending",
        },
    }
    if already_pending is not None:
        body["alreadyPending"] = already_pending
    return body


@pytest.fixture
def mock_http():
    http = MagicMock()
    http.request = AsyncMock()
    return http


@pytest.mark.asyncio
class TestRejectCanNameThePendingRequest:
    async def test_approval_id_goes_on_the_wire_as_approvalId(self, mock_http):
        mock_http.request.return_value = REJECTED_BODY

        record = await PosturesModule(mock_http).reject_transition(
            "agent_1", "insufficient evidence", approval_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == REJECT_URL
        assert kwargs["json_data"] == {"notes": "insufficient evidence", "approvalId": "approval_b"}
        assert record["id"] == "approval_b"

    async def test_omitted_approval_id_is_absent_not_null(self, mock_http):
        """The single-pending wire body is byte-identical to before."""
        mock_http.request.return_value = REJECTED_BODY

        await PosturesModule(mock_http).reject_transition("agent_1", notes="insufficient evidence")

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "insufficient evidence"}
        assert "approvalId" not in kwargs["json_data"]

    async def test_existing_positional_call_shape_still_works(self, mock_http):
        mock_http.request.return_value = REJECTED_BODY

        await PosturesModule(mock_http).reject_transition("agent_1", "insufficient evidence")

        args, kwargs = mock_http.request.call_args
        assert args[1] == REJECT_URL
        assert kwargs["json_data"] == {"notes": "insufficient evidence"}


@pytest.mark.asyncio
class TestDuplicateRequestIsReported:
    async def test_already_pending_is_true_when_the_server_returned_the_existing_request(
        self, mock_http
    ):
        mock_http.request.return_value = _pending_body(already_pending=True)

        result = await PosturesModule(mock_http).request_progression(
            "agent_1", "shared_planning", "retry after a client timeout"
        )

        assert result.approval_pending is True
        assert result.already_pending is True
        assert result.approval_id == "approval_existing"
        assert result.approval is not None
        assert result.approval.reason == "the request that was filed first"

    async def test_already_pending_is_false_for_a_newly_filed_request(self, mock_http):
        mock_http.request.return_value = _pending_body(already_pending=False)

        result = await PosturesModule(mock_http).request_progression(
            "agent_1", "shared_planning", "first request for this promotion"
        )

        assert result.already_pending is False

    async def test_already_pending_defaults_false_when_the_server_does_not_say(self, mock_http):
        """An older server omits the key; absence must not read as a duplicate."""
        mock_http.request.return_value = _pending_body(already_pending=None)

        result = await PosturesModule(mock_http).request_progression(
            "agent_1", "shared_planning", "first request for this promotion"
        )

        assert result.already_pending is False
