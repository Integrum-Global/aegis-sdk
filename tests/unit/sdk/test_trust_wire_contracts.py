"""Tier 1: trust-client request and response shapes, pinned against the server.

Four contracts, each verified against the real server route rather than against
what the client happened to send:

* posture progression returns HTTP 202 with an approval-pending body when the
  transition needs a manager. The client used to raise on that body — AFTER the
  server had accepted the request — so a caller's natural retry filed a SECOND
  pending request. Not raising is the whole fix; reaching the approval id is
  what makes the non-raise useful.
* approving a transition returns the transition record, not posture info.
* the verification route takes a resource TYPE (and an optional resource id),
  so a body carrying only ``resource`` is rejected before it reaches any logic.
* the trust-context and trust-chain routes return documents whose shape the
  client must actually accept; identity fields must come back POPULATED.

Assertions are written against OBSERVABLE outcomes (does it raise, is the value
reachable, is the emitted request body the shape the server model accepts)
rather than against a particular return class, because the typed models for
several of these documents are landing alongside these tests.
"""

import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.exceptions import ValidationError
from aegis_sdk.trust.chains import ChainsModule
from aegis_sdk.trust.postures import PosturesModule

# --------------------------------------------------------------------------
# Tolerant readers.
#
# These locate a value without pinning a field name that is still being
# chosen. They stay DISCRIMINATING: when the value is absent, dropped, or
# None, every lookup misses and the assertion fails. They can only ever be
# too generous about WHERE a value lives, never about WHETHER it is there.
# --------------------------------------------------------------------------


def _as_container(obj: Any) -> Any:
    """Normalise a pydantic model to a plain dict; leave everything else."""
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump()
        except Exception:  # pragma: no cover - defensive, model_dump is total
            return obj
    return obj


def _reachable(obj: Any, needle: Any, _depth: int = 0) -> bool:
    """True when ``needle`` appears anywhere in the returned document."""
    if _depth > 8:
        return False
    obj = _as_container(obj)
    if obj == needle:
        return True
    if isinstance(obj, dict):
        return any(_reachable(v, needle, _depth + 1) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_reachable(v, needle, _depth + 1) for v in obj)
    return False


def _first_populated(obj: Any, *names: str) -> Any:
    """First non-empty value among ``names``, read as attribute or key.

    Returns ``None`` when every candidate is absent, ``None``, or empty — which
    is exactly the condition the identity-population tests exist to catch.
    """
    container = _as_container(obj)
    for name in names:
        value = None
        if isinstance(container, dict) and name in container:
            value = container[name]
        elif hasattr(obj, name):
            value = getattr(obj, name)
        if value not in (None, "", [], {}):
            return value
    return None


@pytest.fixture
def mock_http():
    http = MagicMock()
    http.request = AsyncMock()
    return http


# A request-SHAPE test asks what the client put on the wire. That question has
# an answer even when the reply cannot be parsed, and the two are different
# defects with different owners — so a request-shape test wraps the call in
# ``contextlib.suppress`` and asserts on the captured call instead. Those are
# the only tests here that suppress anything; every response test lets the
# error surface, which is how the response defects are detected at all.


# ==========================================================================
# Posture progression — the approval-pending reply
# ==========================================================================

APPROVAL_PENDING_BODY = {
    "approvalPending": True,
    "approvalId": "approval_abc123",
    "approval": {
        "id": "approval_abc123",
        "agentId": "agent_1",
        "requestedPosture": "shared_planning",
        "currentPosture": "supervised",
        "reason": "50 tasks without incident",
        "status": "pending",
        "reviewedBy": None,
    },
}

# The 200 branch of the same PUT: the route is declared
# ``PostureTransitionResponse | ApprovalPendingResponse``, so the
# applied-immediately reply is a transition RECORD, not posture info.
APPLIED_IMMEDIATELY_BODY = {
    "id": "transition_9",
    "agentId": "agent_1",
    "fromPosture": "supervised",
    "toPosture": "shared_planning",
    "reason": "50 tasks without incident",
    "trigger": "manual",
    "triggeredBy": "user_1",
    "triggeredByName": "Operator",
    "approvedBy": None,
    "approvedByName": None,
    "approvedAt": None,
    "transitionedAt": "2026-01-01T00:00:00Z",
    "metadata": {},
}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestRequestProgressionApprovalPending:
    async def test_approval_pending_body_does_not_raise(self, mock_http):
        """The server ACCEPTED the request (202). Raising here tells the caller
        it failed, and the retry that follows files a duplicate."""
        mock_http.request.return_value = APPROVAL_PENDING_BODY

        result = await PosturesModule(mock_http).request_progression(
            "agent_1", "shared_planning", "50 tasks without incident"
        )

        assert result is not None

    async def test_caller_can_reach_the_approval_id(self, mock_http):
        """Not raising is not enough — swallowing the body would also not
        raise. The approval id is what lets the caller track or cancel the
        request instead of re-submitting it."""
        mock_http.request.return_value = APPROVAL_PENDING_BODY

        result = await PosturesModule(mock_http).request_progression(
            "agent_1", "shared_planning", "50 tasks without incident"
        )

        assert _reachable(result, "approval_abc123"), (
            "approval id is not reachable from the returned object — a caller "
            "cannot distinguish 'queued for approval' from 'applied'"
        )

    async def test_pending_state_is_distinguishable_from_applied(self, mock_http):
        """The caller must be able to tell the two 200/202 outcomes apart."""
        module = PosturesModule(mock_http)

        mock_http.request.return_value = APPROVAL_PENDING_BODY
        pending = await module.request_progression("agent_1", "shared_planning", "x" * 12)

        mock_http.request.return_value = APPLIED_IMMEDIATELY_BODY
        applied = await module.request_progression("agent_1", "shared_planning", "x" * 12)

        assert _as_container(pending) != _as_container(applied)

    async def test_applied_immediately_body_still_parses(self, mock_http):
        """Over-application guard: the normal reply must not regress."""
        mock_http.request.return_value = APPLIED_IMMEDIATELY_BODY

        result = await PosturesModule(mock_http).request_progression(
            "agent_1", "shared_planning", "50 tasks without incident"
        )

        assert _first_populated(result, "agent_id", "agentId") == "agent_1"
        assert _reachable(result, "shared_planning")

    async def test_request_body_is_the_server_field_names(self, mock_http):
        """PUT body is {posture, config, reason} — not the SDK-side names."""
        mock_http.request.return_value = APPLIED_IMMEDIATELY_BODY

        with contextlib.suppress(Exception):
            await PosturesModule(mock_http).request_progression(
                "agent_1", "shared_planning", "50 tasks without incident"
            )

        args, kwargs = mock_http.request.call_args
        assert args[0] == "PUT"
        assert args[1] == "/api/v1/agents/agent_1/trust-posture"
        body = kwargs["json_data"]
        assert body["posture"] == "shared_planning"
        assert body["reason"] == "50 tasks without incident"
        assert "target_posture" not in body
        assert "justification" not in body


# ==========================================================================
# Approving a pending transition
# ==========================================================================

TRANSITION_RECORD_BODY = {
    "id": "transition_1",
    "agentId": "agent_1",
    "fromPosture": "supervised",
    "toPosture": "shared_planning",
    "reason": "approved after review",
    "trigger": "approval",
    "triggeredBy": "user_1",
    "approvedBy": "user_2",
    "approvedAt": "2026-01-02T00:00:00Z",
    "transitionedAt": "2026-01-02T00:00:00Z",
}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestApproveTransition:
    async def test_posts_to_the_agent_scoped_approve_route(self, mock_http):
        """The pending approval is resolved server-side from the agent in the
        path — the approve request model carries notes and nothing else, so the
        agent id in the path IS the request identifier. A body field naming a
        different agent or a client-invented id would not be read."""
        mock_http.request.return_value = TRANSITION_RECORD_BODY

        with contextlib.suppress(Exception):
            await PosturesModule(mock_http).approve_transition("agent_1", notes="reviewed")

        args, kwargs = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/api/v1/agents/agent_1/trust-posture/approve"
        assert set(kwargs["json_data"]) <= {"notes"}
        assert kwargs["json_data"]["notes"] == "reviewed"

    async def test_transition_record_reply_does_not_raise(self, mock_http):
        """The route replies with the transition record. Raising on a
        successful approval leaves the caller unable to confirm the approval
        landed, which invites a second approve call."""
        mock_http.request.return_value = TRANSITION_RECORD_BODY

        result = await PosturesModule(mock_http).approve_transition("agent_1", notes="reviewed")

        assert result is not None

    async def test_approved_posture_is_reachable_from_the_reply(self, mock_http):
        mock_http.request.return_value = TRANSITION_RECORD_BODY

        result = await PosturesModule(mock_http).approve_transition("agent_1", notes="reviewed")

        assert _reachable(result, "shared_planning"), (
            "the posture the approval moved the agent to is not reachable"
        )
        assert _first_populated(result, "agent_id", "agentId") == "agent_1"

    async def test_notes_are_optional(self, mock_http):
        mock_http.request.return_value = TRANSITION_RECORD_BODY

        with contextlib.suppress(Exception):
            await PosturesModule(mock_http).approve_transition("agent_1")

        assert mock_http.request.call_args[1]["json_data"].get("notes") is None


# ==========================================================================
# Trust verification — POST /api/v1/trust/verify
# ==========================================================================

VERIFY_RESULT_BODY = {
    "allowed": True,
    "reason": None,
    "capabilities_matched": ["read"],
    "constraints_violated": [],
}


async def _verify(module, **overrides):
    """Call verify() with the kind/instance pair the route declares."""
    kwargs = {
        "agent_id": "agent_1",
        "action": "write",
        "resource_type": "report",
        "resource_id": "report_q4",
    }
    kwargs.update(overrides)
    return await module.verify(**kwargs)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestVerifyRequestShape:
    """The server's request model is {agent_id, action, resource_type,
    resource_id?}. ``resource_type`` is REQUIRED and has no default, so a body
    without it is rejected at validation — before any trust logic runs."""

    async def test_body_carries_resource_type(self, mock_http):
        mock_http.request.return_value = VERIFY_RESULT_BODY

        await _verify(ChainsModule(mock_http))

        body = mock_http.request.call_args[1]["json_data"]
        assert "resource_type" in body, (
            "request omits the required resource_type field — the route rejects "
            "this body at validation"
        )
        assert body["resource_type"] == "report"

    async def test_body_carries_the_resource_identifier(self, mock_http):
        mock_http.request.return_value = VERIFY_RESULT_BODY

        await _verify(ChainsModule(mock_http))

        body = mock_http.request.call_args[1]["json_data"]
        assert _reachable(body, "report_q4"), (
            "the resource the caller named is not present in the emitted body"
        )

    async def test_body_carries_agent_and_action(self, mock_http):
        mock_http.request.return_value = VERIFY_RESULT_BODY

        await _verify(ChainsModule(mock_http))

        body = mock_http.request.call_args[1]["json_data"]
        assert body["agent_id"] == "agent_1"
        assert body["action"] == "write"

    async def test_body_has_no_fields_the_route_does_not_declare(self, mock_http):
        """Kept separate from the required-field test so the two failures stay
        distinguishable: a missing required field is fatal, a surplus field is
        dead weight the route silently drops."""
        mock_http.request.return_value = VERIFY_RESULT_BODY

        await _verify(ChainsModule(mock_http))

        body = mock_http.request.call_args[1]["json_data"]
        assert set(body) <= {"agent_id", "action", "resource_type", "resource_id"}, (
            f"body carries fields the route does not declare: "
            f"{set(body) - {'agent_id', 'action', 'resource_type', 'resource_id'}}"
        )

    async def test_kind_only_check_omits_the_instance(self, mock_http):
        """Asking about a kind as a whole is a legitimate question: the body
        carries resource_type and no invented resource_id."""
        mock_http.request.return_value = VERIFY_RESULT_BODY

        await ChainsModule(mock_http).verify(
            agent_id="agent_1", action="write", resource_type="report"
        )

        body = mock_http.request.call_args[1]["json_data"]
        assert body["resource_type"] == "report"
        assert body.get("resource_id") is None

    async def test_a_missing_resource_kind_is_refused_before_the_call(self, mock_http):
        """No target, no request. Inventing a resource kind would write a
        caller-shaped claim into the platform's audit record that the caller
        never made, so the refusal must happen client-side — and nothing may
        reach the transport."""
        mock_http.request.return_value = VERIFY_RESULT_BODY

        with pytest.raises(ValidationError):
            await ChainsModule(mock_http).verify(agent_id="agent_1", action="write")

        mock_http.request.assert_not_called()

    async def test_posts_to_the_verify_route(self, mock_http):
        mock_http.request.return_value = VERIFY_RESULT_BODY

        await _verify(ChainsModule(mock_http))

        args, _ = mock_http.request.call_args
        assert args[0] == "POST"
        assert args[1] == "/api/v1/trust/verify"

    async def test_result_reports_the_decision(self, mock_http):
        mock_http.request.return_value = VERIFY_RESULT_BODY

        result = await _verify(ChainsModule(mock_http))

        assert _first_populated(result, "allowed") is True
        assert _reachable(result, "read"), "matched capabilities were dropped"

    async def test_denial_is_not_read_as_permission(self, mock_http):
        """Both polarities of the decision itself: a deny must stay a deny."""
        mock_http.request.return_value = {
            "allowed": False,
            "reason": "capability not attested",
            "capabilities_matched": [],
            "constraints_violated": ["budget"],
        }

        result = await _verify(ChainsModule(mock_http))

        container = _as_container(result)
        assert container["allowed"] is False
        assert _reachable(result, "capability not attested")
        assert _reachable(result, "budget"), "violated constraints were dropped"


# ==========================================================================
# Agent trust context — GET /api/v1/trust/agents/{id}/trust-context
# ==========================================================================

TRUST_CONTEXT_BODY = {
    "trust_chain": {
        "agent_id": "agent_1",
        "genesis": {
            "agent_id": "agent_1",
            "authority_id": "authority_1",
            "established_at": "2026-01-01T00:00:00Z",
            "capabilities": ["read"],
            "constraints": [],
        },
        "delegations": [],
        "status": "active",
        "human_origin": None,
    },
    "delegation_path": {
        "trust_chain_id": "chain_1",
        "path": [{"agent_id": "agent_1", "agent_name": "Researcher", "depth": 0}],
        "total_depth": 1,
        "max_depth_allowed": 10,
    },
    "position": 0,
    "expires_in_days": 30,
    "has_warnings": False,
    "warnings": [],
}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestAgentTrustContext:
    async def test_gets_the_agent_scoped_trust_context_route(self, mock_http):
        mock_http.request.return_value = TRUST_CONTEXT_BODY

        with contextlib.suppress(Exception):
            await ChainsModule(mock_http).get_agent_context("agent_1")

        args, kwargs = mock_http.request.call_args
        assert args[0] == "GET"
        assert args[1] == "/api/v1/trust/agents/agent_1/trust-context"
        # A GET to this route takes no body and no query parameters.
        assert kwargs.get("json_data") is None
        assert not kwargs.get("params")

    async def test_server_response_parses(self, mock_http):
        mock_http.request.return_value = TRUST_CONTEXT_BODY

        result = await ChainsModule(mock_http).get_agent_context("agent_1")

        assert result is not None

    async def test_identity_and_depth_are_populated(self, mock_http):
        mock_http.request.return_value = TRUST_CONTEXT_BODY

        result = await ChainsModule(mock_http).get_agent_context("agent_1")

        assert _reachable(result, "agent_1"), "the agent this context describes is not reachable"
        assert _reachable(result, "chain_1"), "the trust chain id is not reachable"
        assert _first_populated(result, "expires_in_days", "expiresInDays") == 30

    async def test_chainless_agent_is_an_empty_context_not_an_error(self, mock_http):
        """The route deliberately returns 200 with a null chain for an agent
        whose chain has not been established. The client must render that, not
        raise — otherwise a normal state reads as a failure."""
        mock_http.request.return_value = {
            "trust_chain": None,
            "delegation_path": {
                "trust_chain_id": None,
                "path": [],
                "total_depth": 0,
                "max_depth_allowed": 10,
            },
            "position": 0,
            "expires_in_days": None,
            "has_warnings": False,
            "warnings": [],
        }

        result = await ChainsModule(mock_http).get_agent_context("agent_1")

        assert result is not None
        assert _first_populated(result, "trust_chain", "trustChain") is None


# ==========================================================================
# Trust chain lineage — GET /api/v1/trust/chains/{agent_id}
# ==========================================================================

LINEAGE_BODY = {
    "genesis": {
        "id": "genesis_1",
        "agent_id": "agent_1",
        "agent_name": "Researcher",
        "authority_id": "authority_1",
        "authority_type": "organizational",
        "created_at": "2026-01-01T00:00:00+00:00",
        "expires_at": None,
        "signature": "sig_genesis",
        "signature_algorithm": "ed25519",
        "alg_id": "eatp-v1",
        "metadata": {},
    },
    "capabilities": [
        {
            "id": "capability_1",
            "capability": "documents:read",
            "capability_type": "data_access",
            "constraints": [],
            "attester_id": "authority_1",
            "attested_at": "2026-01-01T00:00:00+00:00",
            "expires_at": None,
            "signature": "sig_capability",
            "alg_id": "eatp-v1",
            "scope": None,
        }
    ],
    "delegations": [],
    "constraint_envelope": None,
    "audit_anchors": [],
    "chain_hash": "0123456789abcdef",
    "verification": {"genesis": True, "capabilities": [True], "delegations": []},
}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestTrustChainLineage:
    async def test_gets_the_agent_keyed_chain_route(self, mock_http):
        mock_http.request.return_value = LINEAGE_BODY

        with contextlib.suppress(Exception):
            await ChainsModule(mock_http).get("agent_1")

        args, _ = mock_http.request.call_args
        assert args[0] == "GET"
        assert args[1] == "/api/v1/trust/chains/agent_1"

    async def test_lineage_document_parses(self, mock_http):
        mock_http.request.return_value = LINEAGE_BODY

        result = await ChainsModule(mock_http).get("agent_1")

        assert result is not None

    async def test_identity_fields_are_populated_not_none(self, mock_http):
        """The polarity that matters. Capability rows carrying data while the
        record identities come back None is the signature of a shape the client
        reads through the wrong key names — a document that looks half-loaded
        rather than one that failed."""
        mock_http.request.return_value = LINEAGE_BODY

        result = await ChainsModule(mock_http).get("agent_1")

        # ledger ewl-20260913-9850011aa1: read identity through the TYPED
        # accessors a partner uses. `_reachable` alone walks nested dicts, so a
        # permissive model with `agent_id=None` at the top level beside a
        # populated `genesis` (the filed symptom, exactly) still found
        # "agent_1" inside `genesis` and stayed green.
        assert result.agent_id == "agent_1", "agent identity is not populated"
        assert result.authority_id == "authority_1", "authority identity is not populated"
        assert result.genesis.id == "genesis_1", "genesis record id is not populated"
        assert _reachable(result, "agent_1"), "agent identity is not populated"
        assert _reachable(result, "authority_1"), "authority identity is not populated"
        assert _reachable(result, "genesis_1"), "genesis record id is not populated"

    async def test_capability_rows_survive(self, mock_http):
        """The other half: the fix must not drop the rows that already worked."""
        mock_http.request.return_value = LINEAGE_BODY

        result = await ChainsModule(mock_http).get("agent_1")

        assert _reachable(result, "documents:read"), "capability rows were dropped"
        assert _reachable(result, "capability_1")

    async def test_chain_hash_survives(self, mock_http):
        mock_http.request.return_value = LINEAGE_BODY

        result = await ChainsModule(mock_http).get("agent_1")

        assert _reachable(result, "0123456789abcdef"), (
            "chain_hash is the integrity anchor of the document and must survive"
        )
