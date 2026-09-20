"""The client-side findings of the 2026-09-09 capability sweep, held to code.

Each test here names ONE sweep finding and is written so that the SHAPE THE
SWEEP FOUND makes it RED. That is the only property that matters: a test that
passes both before and after a fix reports nothing, whatever it asserts.

The findings, and the falsifying result each test would produce had the finding
never been fixed:

  C1  the typed ``APIKey`` dropped ``key`` / ``status`` / ``rate_limit`` /
      ``organization_id``.  Falsifying result: parsing a revoked key yields an
      object with no ``status``, and a create response yields no ``key``.
  C2  the probe sent ``X-API-Key`` while the client sent ``Authorization:
      Bearer``.  Falsifying result: the two header names differ.
  C3  the six ``/licenses/...`` paths omitted the ``/api/v1`` prefix every
      other module carries.  Falsifying result: a declared path that is not
      under ``/api/v1/``.
  C4  ``logout()`` (and its untouched sibling ``refresh_token()``) sent NO
      body to an endpoint whose FastAPI signature makes the body required.
      Falsifying result: ``json_data is None``.

DERIVED, NOT LISTED. The C2 and C3 assertions parse the modules they are about
rather than restating their contents -- a hand-copied expectation is satisfied
by the copy, so it survives the very edit it exists to catch.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from aegis_sdk import APIKey, APIKeyCreated
from aegis_sdk._http import API_KEY_PREFIX, HTTPClient, _credential_headers
from aegis_sdk.auth.client import AuthModule

SDK_ROOT = Path(inspect.getfile(HTTPClient)).parent


# --------------------------------------------------------------------------- #
# C1 -- the typed model must not drop fields the server sends
# --------------------------------------------------------------------------- #

#: A response in the shape of the server's ``APIKeyResponse``, for a key that
#: has been REVOKED.
REVOKED_KEY_RESPONSE = {
    "id": "key_1",
    "organization_id": "org_1",
    "name": "CI pipeline",
    "key_prefix": "sk_live_",
    "scopes": ["agents:read"],
    "rate_limit": 1000,
    "expires_at": None,
    "last_used_at": None,
    "status": "revoked",
    "created_by": "user_1",
    "created_at": "2026-09-01T00:00:00Z",
}

#: The same key, live. Identical but for ``status`` -- which is the whole point.
ACTIVE_KEY_RESPONSE = {**REVOKED_KEY_RESPONSE, "status": "active"}


def test_c1_revoked_key_is_distinguishable_from_a_live_one():
    """A dropped ``status`` made these two responses parse identically."""
    revoked = APIKey(**REVOKED_KEY_RESPONSE)
    active = APIKey(**ACTIVE_KEY_RESPONSE)

    assert revoked.status == "revoked"
    assert active.status == "active"
    # The load-bearing half: before the fix BOTH sides of this were equal,
    # because the only differing field was the one the model discarded.
    assert revoked != active


def test_c1_governance_fields_survive_parsing():
    key = APIKey(**REVOKED_KEY_RESPONSE)
    assert key.organization_id == "org_1"
    assert key.rate_limit == 1000
    assert key.created_by == "user_1"


def test_c1_create_response_keeps_the_one_time_secret():
    """The secret is emitted once; dropping it loses the caller's only copy."""
    created = APIKeyCreated(
        id="key_1",
        organization_id="org_1",
        name="CI pipeline",
        key_prefix="sk_live_",
        key="sk_live_THE_ONLY_COPY",
        scopes=[],
        rate_limit=1000,
        expires_at=None,
        status="active",
        created_at="2026-09-01T00:00:00Z",
    )
    assert created.key == "sk_live_THE_ONLY_COPY"
    # Still an APIKey, so callers written against the previous return type of
    # create_api_key() keep working.
    assert isinstance(created, APIKey)


def test_c1_the_secret_is_never_rendered_into_a_repr():
    """Returned to the caller, invisible to logs and tracebacks (H1)."""
    created = APIKeyCreated(
        id="key_1",
        name="n",
        key_prefix="sk_live_",
        key="sk_live_THE_ONLY_COPY",
        created_at="2026-09-01T00:00:00Z",
    )
    assert "THE_ONLY_COPY" not in repr(created)
    assert "THE_ONLY_COPY" not in str(created)


def test_c1_list_shaped_response_still_parses():
    """The added fields are OPTIONAL -- an older/narrower payload must not 422."""
    key = APIKey(
        id="key_1", name="n", key_prefix="sk_live_", created_at="2026-09-01T00:00:00Z"
    )
    assert key.status is None


# --------------------------------------------------------------------------- #
# C2 -- the probe and the client must present a key on the same channel
# --------------------------------------------------------------------------- #


def _probe_api_key_header() -> str:
    """The header name the probe uses for an API key, read from its source.

    Parsed rather than restated: an assertion against a copied literal is
    satisfied by the copy even after the probe changes.
    """
    tree = ast.parse((SDK_ROOT / "coc" / "probe.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Subscript):
            continue
        idx = target.slice
        if not (isinstance(idx, ast.Constant) and idx.value == "key"):
            continue
        if isinstance(node.value, ast.Dict) and len(node.value.keys) == 1:
            only_key = node.value.keys[0]
            if isinstance(only_key, ast.Constant) and isinstance(only_key.value, str):
                return only_key.value
    raise AssertionError(
        "could not find the probe's API-key header assignment; the probe was "
        "restructured and this cross-check has stopped checking anything"
    )


def test_c2_probe_and_client_agree_on_the_api_key_channel():
    probe_header = _probe_api_key_header()
    client_header = next(iter(_credential_headers(API_KEY_PREFIX + "abc")))
    assert client_header == probe_header, (
        f"the probe presents an API key as {probe_header!r} and the client as "
        f"{client_header!r}; the client's own diagnostic cannot reproduce the "
        f"client's auth failures while they disagree"
    )


def test_c2_a_session_jwt_still_goes_on_the_bearer_channel():
    """The slot is shared; routing a JWT to X-API-Key would silently drop it."""
    headers = _credential_headers("eyJhbGciOiJIUzI1NiJ9.payload.sig")
    assert set(headers) == {"Authorization"}
    assert headers["Authorization"].startswith("Bearer ")


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (API_KEY_PREFIX + "a", "eyJjwt", "Authorization"),
        ("eyJjwt", API_KEY_PREFIX + "a", "X-API-Key"),
    ],
)
def test_c2_swapping_credential_kind_retires_the_previous_header(first, second, expected):
    """Two credential headers at once lets the server pick which one it honours."""
    client = HTTPClient(base_url="https://example.invalid", api_key=first)
    client.set_api_key(second)
    present = {h for h in ("Authorization", "X-API-Key") if h in client._client.headers}
    assert present == {expected}


# --------------------------------------------------------------------------- #
# C3 -- declared paths must be under the prefix the server mounts them at
# --------------------------------------------------------------------------- #


def _license_operations() -> set[tuple[str, str]]:
    """The package's declared license operations, via the SHIPPED derivation.

    ``declared_operations`` is the gate the SDK already ships
    (``aegis_sdk.handbook.check``). Reusing it rather than re-implementing an
    AST walk here means this test and that gate cannot disagree about what a
    "declared operation" is -- and an f-string path is reconstructed to its
    real shape instead of splintering into its literal fragments.
    """
    from aegis_sdk.handbook.check import declared_operations

    return {(m, p) for m, p in declared_operations() if "/licenses/" in p}


def test_c3_license_paths_carry_the_api_v1_prefix():
    """The server mounts these under /api/v1; the client asked for the root."""
    ops = _license_operations()
    assert ops, "no license operations found -- this check has stopped checking"
    offenders = sorted(p for _, p in ops if not p.startswith("/api/v1/"))
    assert offenders == [], (
        f"these license paths are not under /api/v1 and 404 on the deployment: "
        f"{offenders}"
    )


def test_c3_license_operations_are_the_six_the_server_mounts():
    """Denominator, so a module emptied of calls cannot pass the check above.

    Six, matching the six ``/api/v1/licenses/...`` routes registered on
    ``aegis.main.app``. Pinned as a SET, not a count: a count survives a swap.
    """
    assert _license_operations() == {
        ("POST", "/api/v1/licenses/generate"),
        ("POST", "/api/v1/licenses/validate"),
        ("POST", "/api/v1/licenses/{}/revoke"),
        ("GET", "/api/v1/licenses/{}/usage"),
        ("GET", "/api/v1/licenses/status"),
        ("GET", "/api/v1/licenses/editions"),
    }


# --------------------------------------------------------------------------- #
# C4 -- endpoints whose FastAPI signature requires a body must receive one
# --------------------------------------------------------------------------- #


class _RecordingHTTP:
    """Captures the request the SDK would have made. No network."""

    def __init__(self, response: dict | None = None):
        self.calls: list[dict] = []
        self._response = response if response is not None else {}

    async def request(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **kwargs})
        return self._response


@pytest.mark.asyncio
async def test_c4_logout_sends_a_body():
    http = _RecordingHTTP()
    await AuthModule(http).logout()
    (call,) = http.calls
    assert call["path"] == "/api/v1/auth/logout"
    # `is not None` is the assertion, not truthiness: httpx sends `{}` as a
    # body and `None` as no body at all, and 422-vs-200 turns on exactly that.
    assert call["json_data"] is not None, "bodyless POST -- the server answers 422"
    assert call["json_data"] == {}


@pytest.mark.asyncio
async def test_c4_logout_forwards_a_refresh_token_when_given_one():
    http = _RecordingHTTP()
    await AuthModule(http).logout(refresh_token="rt_123")
    assert http.calls[0]["json_data"] == {"refresh_token": "rt_123"}


@pytest.mark.asyncio
async def test_c4_refresh_sends_a_body_on_the_cookie_session_path():
    """Same class as logout, same required-body signature, no argument to send.

    This is the SSO path the server documents: the refresh token lives in an
    HTTP-only cookie that JavaScript cannot read, so it can never be placed in
    the body -- and an empty body is what makes that path work rather than 422.
    """
    http = _RecordingHTTP({"access_token": "eyJnew", "token_type": "bearer"})
    await AuthModule(http).refresh_token()
    assert http.calls[0]["json_data"] is not None
    assert http.calls[0]["json_data"] == {}
