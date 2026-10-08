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

2. THE IDENTIFIER MUST BIND. The route accepts ``request_id`` and
   ``approvalId`` (a compatibility alias); ``requestId`` is dropped by
   pydantic's default ``extra='ignore'`` and arrives as ``None``. That is not
   a visible error -- with more than one request pending the server refuses as
   AMBIGUOUS, so a caller who named their target is told they did not. Every
   wire assertion here parses the outgoing body through a model declaring the
   route's own field and asserts the value BINDS, rather than pinning the
   literal key this SDK happens to send. A literal assertion pins what we send
   and says nothing about what the route reads; that is exactly how the
   sibling defect survived its own test suite.

Tier 1: the HTTP layer is mocked, as in
``test_sdk_posture_reject_disambiguation.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from aegis_sdk import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from aegis_sdk.modules.trust_posture import TrustPostureModule
from aegis_sdk.trust.postures import PosturesModule

#: The route the platform SERVES. Not the siblings' shape.
WITHDRAW_URL = "/api/v1/trust-posture/agent_1/withdraw"

#: The shape a sibling-shaped guess would produce, asserted AGAINST below.
SIBLING_SHAPED_URL = "/api/v1/agents/agent_1/trust-posture/withdraw"


class _WithdrawBody(BaseModel):
    """The route's withdraw body AS THE ROUTE DECLARES IT.

    ``request_id`` addresses the request. The route also accepts ``approvalId``
    as a compatibility alias; ``requestId`` is not accepted, and is dropped on
    arrival so it binds as ``None``. This model deliberately declares ONLY the
    canonical spelling, because that is what this SDK sends -- what the route
    WOULD accept from someone else is a different question from what we send.
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
            "A spelling the route does not accept is dropped by pydantic's "
            "extra='ignore', so request_id arrives None and a caller who named "
            "their target is refused as ambiguous."
        )

    async def test_body_carries_the_canonical_key_and_nothing_else(self, mock_http):
        """The body carries exactly the canonical spelling.

        NOT because the alias would fail -- ``approvalId`` binds too, and that
        is why this is narrower than the assertion it replaces. ``approvalId``
        binds only because the route keeps a compatibility alias for already-
        released clients; ``request_id`` is what the route declares and what
        survives the alias being withdrawn. A future edit that sends the alias
        spelling can be green on the wire and still be the wrong choice, which
        is the case this pin exists for.
        """
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


def _response(status: int, body: dict | None = None):
    """A real httpx.Response so the REAL status mapping runs, not a double."""
    import httpx

    return httpx.Response(
        status,
        json=body if body is not None else {"detail": "refused"},
        request=httpx.Request("POST", f"http://x{WITHDRAW_URL}"),
    )


def _html_response(status: int):
    """An error page rather than an error object — what an ingress returns."""
    import httpx

    return httpx.Response(
        status,
        text="<html><body><h1>409 Conflict</h1></body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("POST", f"http://x{WITHDRAW_URL}"),
    )


def _list_response(status: int):
    """Well-formed JSON that is not an object — the envelope branch cannot read it."""
    import httpx

    return httpx.Response(
        status,
        json=[{"detail": "a bare list, not the envelope"}],
        request=httpx.Request("POST", f"http://x{WITHDRAW_URL}"),
    )


def _map(response):
    """Drive ``HTTPClient._handle_response`` and return the raised exception.

    The mapping is exercised through the real client rather than a mock: these
    tests exist to pin which EXCEPTION a caller catches, so substituting the
    thing under test would pin nothing.

    Takes the RESPONSE rather than a status because the body SHAPE changes the
    branch `_extract_error_detail` takes — an HTML body never reaches
    `response.json()`, and a list body reaches it but is not a dict — and those
    are separate code paths that a status-only helper cannot reach at all.
    """
    from aegis_sdk._http import HTTPClient

    client = HTTPClient.__new__(HTTPClient)  # no __init__: the mapper needs no state
    try:
        client._handle_response(response)
    except Exception as exc:  # noqa: BLE001 — the point is to inspect what came out
        return exc
    raise AssertionError(f"status {response.status_code} raised nothing at all")


def _map_status(status: int):
    return _map(_response(status))


#: The platform's REAL error envelope. Every error Aegis returns is re-wrapped
#: into this shape by a global HTTPException handler before it leaves the
#: server, so a test built on the flat ``{"detail": ...}`` shape is testing a
#: body no deployment actually sends for a route like this one.
_ENVELOPE = {
    "error": {
        "code": "WITHDRAW_CONFLICT",
        "message": "Approval request approval_a is 'approved', not pending",
        "details": {"approval_id": "approval_a"},
        "request_id": "req-1151",
    }
}


class TestTheRefusalsAWithdrawCanProduceAreCatchable:
    """Each status a caller can actually receive, pinned BY TYPE and BY CODE.

    WHY THIS EXISTS. A status with no branch in ``_handle_response`` does not
    fail loudly -- it falls through to the generic ``else`` and raises
    ``AgenticOSError("Unexpected status code: N")``. The caller then cannot tell
    a deliberate refusal from a broken server, and any ``except <SpecificError>``
    they wrote raises ``NameError`` in their own code. 409 had exactly that gap
    until this change, so the 409 case below is the regression pin for it.
    """

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (400, "ValidationError"),
            (403, "AuthorizationError"),
            (404, "NotFoundError"),
            (409, "ConflictError"),
        ],
    )
    def test_the_status_maps_to_its_documented_exception(self, status, expected):
        exc = _map_status(status)

        assert type(exc).__name__ == expected, (
            f"HTTP {status} raised {type(exc).__name__}, expected {expected}. An "
            f"'Unexpected status code' message means this status has no branch, so "
            f"a caller cannot catch it by type."
        )
        assert exc.status_code == status, (
            f"{expected}.status_code is {exc.status_code!r}, expected {status}. The "
            f"wire value is the one thing a caller can branch on when the type is "
            f"unfamiliar."
        )

    def test_the_409_message_is_the_SERVER_s_explanation_not_a_placeholder(self):
        """``str(exc)`` carries the server's own sentence, through the REAL envelope.

        ⛔ THIS IS r1's ORIGINAL F1 SYMPTOM, and type-plus-code does not cover it.
        Before the 409 branch existed, a caller was told
        ``"Unexpected status code: 409"`` — a deliberate refusal reported as a
        platform malfunction. Substituting a DIFFERENT fixed sentence for it
        ("Request conflicts with the server's current state") would satisfy every
        type and status_code assertion in this class while still throwing away
        the one thing the server knew and the caller did not: WHICH request was
        no longer pending, and why.

        Built on the platform's real error envelope rather than the flat
        ``{"detail": ...}`` shape, because a global HTTPException handler
        re-wraps every error before it leaves the server — so the envelope is
        what a deployment actually sends, and the message has to survive being
        read one level in.

        FALSIFYING RESULT, named: replace the ``_message_or(error_detail, ...)``
        call in the 409 branch with a bare string literal and this reddens on the
        message assertion, while every other test in this class stays green.
        """
        exc = _map(_response(409, _ENVELOPE))

        assert str(exc) == _ENVELOPE["error"]["message"], (
            f"str(exc) is {str(exc)!r}; the server sent "
            f"{_ENVELOPE['error']['message']!r}. The message is the half of the "
            f"refusal the caller cannot reconstruct from the status."
        )
        assert "Unexpected status code" not in str(exc), (
            f"the refusal is still being reported as a surprise: {str(exc)!r}"
        )

    @pytest.mark.parametrize(
        ("label", "response_factory", "expected_code"),
        [
            ("html-body", lambda: _html_response(409), 409),
            ("list-body", lambda: _list_response(409), 409),
        ],
        ids=["html-body", "list-body"],
    )
    def test_a_409_with_an_unextraordinary_body_still_reports_its_status(
        self, label, response_factory, expected_code
    ):
        """The status survives a body the extractor cannot read as an object.

        WHY THIS IS A SEPARATE TEST AND NOT PART OF THE ONE ABOVE.
        ``_extract_error_detail`` has THREE returns: the JSON-decode fallback, a
        non-dict JSON body, and the normal object path. A mutation sweep found
        that removing ``status_code`` from the first two changes NOTHING in this
        file — because every other test here sends a dict body and only the third
        path is ever taken. The status code is the one field a caller can branch
        on when they do not recognise the type, so it has to be present on all
        three, not only the convenient one.

        An HTML error page is what a misrouted request or an ingress returns; a
        list body is a shape the envelope branch cannot read. Neither is exotic
        enough to lose the status over.

        FALSIFYING RESULT, named: drop ``status_code`` from the matching return
        in ``_extract_error_detail`` and this reddens for that id alone —
        ``html-body`` for the decode fallback, ``list-body`` for the non-dict
        branch.
        """
        exc = _map(response_factory())

        assert type(exc).__name__ == "ConflictError", (
            f"a 409 with a {label} got {type(exc).__name__}"
        )
        assert exc.status_code == expected_code, (
            f"a 409 with a {label} reported status_code={exc.status_code!r}, "
            f"expected {expected_code}. The status is the only field a caller can "
            f"branch on when the body is unreadable; losing it on this path means "
            f"the refusal cannot be identified at all."
        )

    @pytest.mark.asyncio
    async def test_conflict_error_is_importable_from_the_package_root(self):
        """Callers catch it as ``aegis_sdk.ConflictError``.

        The withdraw route's own docstrings have advertised ``Raises:
        ConflictError`` since 2026-09-11 while no such class was importable.
        A class that exists but is not exported leaves that promise uncatchable.
        """
        import aegis_sdk

        assert hasattr(aegis_sdk, "ConflictError"), (
            "ConflictError is not exported from the package root; the documented "
            "`Raises: ConflictError` contract cannot be honoured by a caller."
        )
        assert issubclass(aegis_sdk.ConflictError, aegis_sdk.AgenticOSError), (
            "ConflictError must stay a subclass of AgenticOSError or an existing "
            "`except AgenticOSError` handler stops catching a 409."
        )

    @pytest.mark.asyncio
    async def test_an_existing_base_class_handler_still_catches_a_409(self):
        """Backward compatibility, asserted rather than assumed.

        Before this change a 409 arrived as ``AgenticOSError``. Code written
        against that must keep working untouched.
        """
        from aegis_sdk import AgenticOSError

        try:
            raise _map_status(409)
        except AgenticOSError as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("a 409 was not catchable as AgenticOSError")


@pytest.mark.asyncio
class TestTheWithdrawPathIsEncoded:
    """An identifier needing encoding must not corrupt the route.

    ``agent_1`` is URL-safe, so every other test here would pass even if the
    path segment were interpolated raw. These use an identifier that is not.
    """

    NEEDY = "agent/with space+plus"

    async def test_the_trust_surface_encodes_the_path_segment(self, mock_http):
        await PosturesModule(mock_http).withdraw_transition(self.NEEDY, "no longer needed")

        _args, kwargs = mock_http.request.call_args
        sent = kwargs.get("json_data") is not None  # body present, path is args[1]
        assert sent
        url = mock_http.request.call_args[0][1]
        assert self.NEEDY not in url, f"the identifier was interpolated raw: {url!r}"
        assert " " not in url.split("/api")[1], f"a raw space survived into the URL: {url!r}"
        assert url.endswith("/withdraw"), url

    async def test_the_module_surface_encodes_the_path_segment(self, mock_http):
        await TrustPostureModule(mock_http).withdraw_posture_transition(
            self.NEEDY, "no longer needed"
        )

        url = mock_http.request.call_args[0][1]
        assert self.NEEDY not in url, f"the identifier was interpolated raw: {url!r}"
        assert " " not in url.split("/api")[1], f"a raw space survived into the URL: {url!r}"
        assert url.endswith("/withdraw"), url


@pytest.mark.asyncio
class TestTheModuleSurfaceBodyIsExactlyTheCanonicalKeys:
    """The MODULE surface had no exact-key assertion; the trust surface did.

    Without one, a body could gain an extra key that the route drops silently --
    the caller believes they sent something the server never read.
    """

    async def test_body_keys_are_exactly_notes_and_request_id(self, mock_http):
        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed", approval_id="approval_b"
        )

        _args, kwargs = mock_http.request.call_args
        assert set(kwargs["json_data"]) == {"notes", "request_id"}, (
            f"the module surface sent {sorted(kwargs['json_data'])}. An extra key "
            f"is dropped by the route's model and the caller is never told."
        )

    async def test_body_keys_without_an_identifier_omit_it_entirely(self, mock_http):
        await TrustPostureModule(mock_http).withdraw_posture_transition(
            "agent_1", "no longer needed"
        )

        _args, kwargs = mock_http.request.call_args
        assert set(kwargs["json_data"]) == {"notes"}, (
            f"expected exactly {{'notes'}}, got {sorted(kwargs['json_data'])}. A "
            f"null request_id is not the same sent value as an omitted one."
        )


@pytest.mark.asyncio
class TestEachSurfaceLetsARefusalThroughUnchanged:
    """The METHOD-level error path, on BOTH surfaces.

    The refusals pinned above drive ``HTTPClient._handle_response`` directly, so
    they pin what the MAPPER does. A surface that caught the refusal and
    returned an empty record would satisfy every one of them and still hand the
    caller a silent wrong answer. Each withdraw docstring promises these four
    types BY NAME, and that promise is kept only if the METHOD propagates them.

    ``type(...) is`` rather than ``isinstance``: the point is that a caller can
    match the SPECIFIC class, so a bare ``AgenticOSError`` must fail this even
    though it is the parent of the expected one.
    """

    EXPECTED = {
        400: ValidationError,
        403: AuthorizationError,
        404: NotFoundError,
        409: ConflictError,
    }

    @staticmethod
    def _refusing_http(status: int):
        """An HTTP double that refuses exactly the way the real client does."""
        http = MagicMock()

        def _refuse(*_args, **_kwargs):
            raise _map_status(status)

        http.request = AsyncMock(side_effect=_refuse)
        return http

    @pytest.mark.parametrize("status", [400, 403, 404, 409])
    async def test_the_trust_surface_propagates_it(self, status):
        expected = self.EXPECTED[status]

        with pytest.raises(expected) as caught:
            await PosturesModule(self._refusing_http(status)).withdraw_transition(
                "agent_1", "no longer needed"
            )

        assert type(caught.value) is expected, (
            f"the trust surface raised {type(caught.value).__name__}, and the "
            f"docstring promises {expected.__name__}. A caller writing "
            f"`except {expected.__name__}` would miss it."
        )
        assert caught.value.status_code == status

    @pytest.mark.parametrize("status", [400, 403, 404, 409])
    async def test_the_module_surface_propagates_it(self, status):
        expected = self.EXPECTED[status]

        with pytest.raises(expected) as caught:
            await TrustPostureModule(self._refusing_http(status)).withdraw_posture_transition(
                "agent_1", "no longer needed"
            )

        assert type(caught.value) is expected, (
            f"the module surface raised {type(caught.value).__name__}, and the "
            f"docstring promises {expected.__name__}. A caller writing "
            f"`except {expected.__name__}` would miss it."
        )
        assert caught.value.status_code == status
