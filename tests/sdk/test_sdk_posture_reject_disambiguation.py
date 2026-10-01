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
from pydantic import BaseModel

from aegis_sdk.modules.trust_posture import TrustPostureModule
from aegis_sdk.trust.postures import PosturesModule


class _DecisionBody(BaseModel):
    """The route's decision body AS THE ROUTE DECLARES IT.

    `request_id` and nothing else addresses the request; the route has no
    alias generator (`model_config` is empty), so every other spelling —
    `requestId`, `approvalId` — is dropped by pydantic's default
    `extra='ignore'` and arrives as `None`.
    """

    notes: str | None = None
    request_id: str | None = None


def _bound_identifier(sent: dict) -> str | None:
    """Parse an outgoing body the way the route does, and return what binds.

    THE POINT IS TO ASSERT THE EFFECT, NOT THE SPELLING. The test this
    replaces pinned the literal key `approvalId` and passed for the whole
    life of the defect, because a literal assertion pins what THIS SDK sends
    and says nothing about what the route reads. Two callers can agree with
    each other and both be wrong.

    What this cannot do: notice the ROUTE changing. It encodes the contract
    as measured on 2026-10-01 against the platform's
    `ApproveTransitionRequest` / `RejectTransitionRequest`. If the route
    stops reading `request_id`, this stays green. It fails when this SDK
    sends something else, which is the regression it exists to catch.
    """
    return _DecisionBody(**sent).request_id

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
    async def test_the_identifier_binds_through_the_route_own_field(self, mock_http):
        mock_http.request.return_value = REJECTED_BODY

        record = await PosturesModule(mock_http).reject_transition(
            "agent_1", "insufficient evidence", approval_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == REJECT_URL

        # The effect assertion. This is the one that would have caught the
        # defect: an identifier that does not bind is an identifier the
        # caller supplied for nothing.
        bound = _bound_identifier(kwargs["json_data"])
        assert bound == "approval_b", (
            "the supplied identifier did not bind to the route's field. The "
            "route declares `request_id` and has no alias, so any other "
            "spelling is dropped on arrival: the caller named their target "
            f"and the route still sees none. sent={kwargs['json_data']!r}"
        )

        # The shape assertion, kept because it catches churn the binding
        # check cannot see (a stray extra key, a reordered body).
        assert kwargs["json_data"] == {
            "notes": "insufficient evidence",
            "request_id": "approval_b",
        }
        assert record["id"] == "approval_b"

    async def test_omitted_approval_id_is_absent_not_null(self, mock_http):
        """The single-pending wire body is byte-identical to before."""
        mock_http.request.return_value = REJECTED_BODY

        await PosturesModule(mock_http).reject_transition("agent_1", notes="insufficient evidence")

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "insufficient evidence"}
        assert _bound_identifier(kwargs["json_data"]) is None
        assert "approvalId" not in kwargs["json_data"]
        assert "requestId" not in kwargs["json_data"]

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


# ---------------------------------------------------------------------------
# The SAME wire-key defect existed on the other posture surface, and nothing
# covered those two methods at all — `TrustPostureModule` had no test in this
# repository. Fixing one surface and leaving the other untested is how the
# omission survived the first time (security.md § Enforcement-Surface Parity),
# so the binding assertion is repeated here rather than assumed.
# ---------------------------------------------------------------------------


TRANSITION_BODY = {
    "id": "transition_1",
    "agentId": "agent_1",
    "fromPosture": "supervised",
    "toPosture": "shared_planning",
    "reason": "evidence reviewed",
    "trigger": "approval",
    "transitionedAt": "2026-09-15T02:00:00+00:00",
}


@pytest.mark.asyncio
class TestTheModuleSurfaceSendsTheKeyTheRouteReads:
    async def test_approve_posture_transition(self, mock_http):
        mock_http.request.return_value = TRANSITION_BODY

        await TrustPostureModule(mock_http).approve_posture_transition(
            "agent_1", notes="reviewed", approval_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/api/v1/agents/agent_1/trust-posture/approve"
        assert _bound_identifier(kwargs["json_data"]) == "approval_b", (
            f"identifier did not bind. sent={kwargs['json_data']!r}"
        )

    async def test_reject_posture_transition(self, mock_http):
        mock_http.request.return_value = REJECTED_BODY

        await TrustPostureModule(mock_http).reject_posture_transition(
            "agent_1", "insufficient evidence", approval_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == REJECT_URL
        assert _bound_identifier(kwargs["json_data"]) == "approval_b", (
            f"identifier did not bind. sent={kwargs['json_data']!r}"
        )

    async def test_omitted_identifier_is_absent_not_null(self, mock_http):
        mock_http.request.return_value = TRANSITION_BODY

        await TrustPostureModule(mock_http).approve_posture_transition("agent_1", notes="reviewed")

        _args, kwargs = mock_http.request.call_args
        assert kwargs["json_data"] == {"notes": "reviewed"}
        assert _bound_identifier(kwargs["json_data"]) is None

    async def test_approve_transition_on_the_trust_surface(self, mock_http):
        """The fourth site. Its identifier path had no wire pin either — the
        existing approve test passes no identifier, so it asserted only that
        the body was `{"notes": ...}`."""
        mock_http.request.return_value = _pending_body(already_pending=None)

        await PosturesModule(mock_http).approve_transition(
            "agent_1", notes="reviewed", approval_id="approval_b"
        )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/api/v1/agents/agent_1/trust-posture/approve"
        assert _bound_identifier(kwargs["json_data"]) == "approval_b", (
            f"identifier did not bind. sent={kwargs['json_data']!r}"
        )
