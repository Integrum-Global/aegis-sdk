"""The transport retries IDEMPOTENT verbs only — pinned in both directions.

WHY THIS FILE EXISTS

``HTTPClient.request`` is also its own send loop. Before this guard, an
``httpx.TimeoutException`` on ANY verb took the ``continue`` path, so a ``POST``
that timed out after the deployment had already applied it was sent again. The
measured case: a ``POST /organization-units`` that timed out once the unit
existed produced a SECOND unit, and units cannot be renamed or merged, so
nothing in this client could undo it. The transport mints no idempotency key,
which leaves the verb as the only discriminator available at that layer.

WHAT THESE TESTS PIN, AND HOW A GREEN COULD BE WRONG

Three claims, each with a control that must still fail:

1. A non-idempotent verb is sent EXACTLY ONCE and raises. The control is the
   idempotent verb: ``GET`` must still be sent three times at the default
   ``max_retries``, or "sent once" would also describe a transport whose retry
   loop had simply died.
2. The caller's exception is unchanged — same SDK type, same ``__cause__``. A
   guard that suppressed the retry by swallowing the error would pass claim 1
   and fail this one.
3. ``PUT`` and ``DELETE`` keep retrying. They are idempotent by HTTP definition,
   and a fix that quietly narrowed retry to ``GET`` would pass claim 1 too.

The fake transport raises on every send, so "how many sends happened" is the
measurement and no HTTP status is involved.
"""

from __future__ import annotations

import httpx
import pytest

from aegis_sdk._http import HTTPClient
from aegis_sdk.exceptions import ConnectionError as SDKConnectionError
from aegis_sdk.exceptions import TimeoutError as SDKTimeoutError

_NON_IDEMPOTENT = ("POST", "PATCH")
_IDEMPOTENT = ("GET", "HEAD", "OPTIONS", "PUT", "DELETE")

_UNITS = "/api/v1/organization-units"


class _FakeTransport:
    """Counts every send and raises the configured exception."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls: list[str] = []

    async def request(self, *, method: str, **kwargs: object) -> object:
        self.calls.append(method)
        raise self._exc


async def _no_delay(attempt: int) -> None:
    """Stand-in for the backoff so the test does not actually sleep."""
    return None


async def _client(exc: BaseException, *, max_retries: int = 3) -> tuple[HTTPClient, _FakeTransport]:
    http = HTTPClient(base_url="https://aegis.example.com", max_retries=max_retries)
    await http._client.aclose()
    transport = _FakeTransport(exc)
    http._client = transport  # type: ignore[assignment]
    http._retry_delay = _no_delay  # type: ignore[assignment]
    return http, transport


@pytest.mark.parametrize("method", _NON_IDEMPOTENT)
async def test_non_idempotent_verb_is_sent_once_and_raises(method: str) -> None:
    http, transport = await _client(httpx.TimeoutException("late"))
    with pytest.raises(SDKTimeoutError):
        await http.request(method, _UNITS)
    assert transport.calls == [method], (
        f"{method} was sent {len(transport.calls)} times; a second send can "
        f"double-apply a request the deployment already accepted"
    )


@pytest.mark.parametrize("method", _IDEMPOTENT)
async def test_idempotent_verb_still_retries(method: str) -> None:
    """Control for the test above: three sends, not one."""
    http, transport = await _client(httpx.TimeoutException("late"))
    with pytest.raises(SDKTimeoutError):
        await http.request(method, _UNITS)
    assert transport.calls == [method] * 3, (
        f"{method} is idempotent and must still be retried to max_retries"
    )


async def test_non_idempotent_failure_keeps_its_type_and_cause() -> None:
    """Control: swallowing the error would pass 'sent once' and lose the cause."""
    cause = httpx.TimeoutException("late")
    http, _ = await _client(cause)
    with pytest.raises(SDKTimeoutError) as caught:
        await http.request("POST", _UNITS)
    assert caught.value.__cause__ is cause


async def test_network_error_on_a_post_is_not_retried_either() -> None:
    """The guard is on the VERB, not on the timeout branch alone."""
    cause = httpx.ConnectError("refused")
    http, transport = await _client(cause)
    with pytest.raises(SDKConnectionError) as caught:
        await http.request("POST", _UNITS)
    assert transport.calls == ["POST"]
    assert caught.value.__cause__ is cause


async def test_max_retries_of_one_still_sends_once_for_any_verb() -> None:
    """The floor: the loop is the send loop, so it must always send at least once."""
    for method in ("POST", "GET"):
        http, transport = await _client(httpx.TimeoutException("late"), max_retries=1)
        with pytest.raises(SDKTimeoutError):
            await http.request(method, _UNITS)
        assert transport.calls == [method]
