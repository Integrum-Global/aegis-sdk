"""
Agentic OS SDK Internal HTTP Client.

Provides an async-first HTTP client with:
- Connection pooling
- Automatic retry with exponential backoff, for idempotent verbs only
- Exception mapping for HTTP status codes
- SDK version headers
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Mapping
from typing import Any
from urllib.parse import quote

import httpx

from ._version import __version__
from .exceptions import (
    AgenticOSError,
    AuthenticationError,
    AuthorizationError,
    ConnectionError,
    GovernanceViolationError,
    NotFoundError,
    RateLimitError,
    ServiceError,
    TimeoutError,
    TrustViolationError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Underscore-stripped canonical tokens so both snake_case ("api_key") AND
# camelCase ("apiKey" — e.g. Pydantic alias fields) redact identically.
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "apikey",
        "token",
        "secret",
        "authorization",
        "accesstoken",
        "refreshtoken",
        "apisecret",
        "privatekey",
        "clientsecret",
    }
)

# Redaction rule (see _scrub_sensitive): a normalized key is redacted when it is
# an exact member of _SENSITIVE_KEYS above OR when it CONTAINS any of these base
# tokens as a substring. Exact membership alone missed compound field names the
# server actually posts — e.g. "new_password" ("newpassword"), "old_password",
# "current_password", "refresh_token", "api_key" variants — leaking plaintext to
# the DEBUG body log ( same-class). The substring check is fail-safe:
# it over-redacts benign look-alikes (e.g. "secret_santa") rather than leak a
# credential, which is the correct trade for a DEBUG-log scrubber. Plain `in`
# checks (no regex) keep it O(len(key)) per field with no ReDoS surface.
_SENSITIVE_SUBSTRINGS: tuple[str, ...] = ("password", "secret", "token", "apikey")


def encode_path_param(value: object) -> str:
    """Percent-encode a single path SEGMENT before it is interpolated into an
    f-string request path (defense-in-depth).

    Every ``aegis_sdk`` module builds its request path via an f-string like
    ``f"/api/v1/applications/{app_id}/grants/{grant_id}"`` and hands the
    result to :meth:`HTTPClient.request`. Neither the module nor the shared
    client validates that ``app_id`` / ``grant_id`` are well-formed resource
    identifiers before they land in the path. An id containing ``/`` or
    ``..`` could shift which path SEGMENTS the request actually addresses
    before the server's own route-matching + permission checks ever run
    (e.g. ``app_id = "../../admin"``).

    This is a **path-segment** encoder, not a whole-URL encoder — it is
    applied to each interpolated identifier individually, at the call site,
    never to the assembled path string. Encoding the whole assembled path
    at the :class:`HTTPClient` boundary was considered and rejected: it
    cannot distinguish a legitimate route separator (``/``) from a ``/``
    smuggled inside an id, so it would either leave the smuggled ``/``
    intact (encoding done too late — after the string is already
    assembled and indistinguishable from a real separator) or percent-encode
    every literal ``/`` in the route template (breaking every request).
    Encoding at the call site, before interpolation, keeps the two
    unambiguous: route separators are typed by the developer as literal
    ``/`` in the f-string template; ids are always the wrapped, encoded
    values.

    ``safe=""`` means ``/`` inside an id is encoded to ``%2F`` (not left
    alone) — the whole point is that ``/`` and ``..`` in an id MUST NOT be
    interpreted as path structure. httpx does not re-decode a caller-supplied
    ``%2F`` back into a literal slash before dispatch, so the encoded
    segment reaches the server as inert bytes for a single, longer segment
    of the URL, not as a route boundary.

    Args:
        value: The path-segment value (id, token, slug, etc.). Coerced to
            ``str`` before encoding, matching the f-string's own implicit
            ``str()`` coercion.

    Returns:
        The percent-encoded segment, safe to interpolate into a path
        f-string without shifting which route is requested.
    """
    return quote(str(value), safe="")


#: Keys that may legitimately accompany "data" in a response ENVELOPE.
#:
#: These are pagination and status fields the server attaches BESIDE the
#: payload. A response whose top-level keys are a subset of ``{"data"} |
#: _ENVELOPE_SIBLING_KEYS`` is an envelope and nothing else, so the payload can
#: be lifted out of it without losing information.
_ENVELOPE_SIBLING_KEYS = frozenset(
    {"total", "message", "meta", "page", "page_size", "has_next", "limit", "offset", "count"}
)


def unwrap_envelope(response: Any) -> Any:
    """Return the payload from a ``{"data": ...}`` response envelope.

    Many endpoints wrap their payload as ``{"data": <payload>}``, sometimes with
    a pagination sibling such as ``{"data": [...], "total": 12}``. A client that
    reads the payload fields straight off the outer object finds none of them.
    That failure is quiet rather than loud -- a list reads as EMPTY and a
    single object reads as missing -- so it surfaces as "the account has no
    pipelines" rather than as an error anyone can act on.

    THE SIBLING-KEY GUARD IS THE WHOLE POINT, AND IT IS WHY THIS IS NOT
    AUTOMATIC. Some payloads legitimately OWN a top-level ``data`` field: a
    settings export is ``{"version", "exportedAt", "format", "categories",
    "data"}``, and a query result is ``{"success", "query", "params", "data",
    "row_count", ...}``. In both, ``data`` is one field of the answer, not a
    wrapper around it, and lifting it would DESTROY the response -- silently,
    and in the same shape as the bug this function exists to fix. The guard
    separates the two cases mechanically: an envelope carries ``data`` and
    nothing beyond the known pagination siblings, so a response carrying any
    other key is returned untouched.

    Unwrapping is therefore OPT-IN PER CALL SITE **and** guarded. It is
    deliberately not applied inside :meth:`HTTPClient.request`: a transport-level
    unwrap would change the return shape of every method at once, including the
    many that are correct today and the endpoints that answer with a bare list,
    a bare scalar, or a payload that owns a ``data`` field. A method opts in
    only where its own endpoint is known to wrap, which keeps the blast radius
    of this change equal to the set of methods actually being repaired.

    Args:
        response: A parsed JSON response body, of any shape.

    Returns:
        ``response["data"]`` when ``response`` is an envelope; otherwise
        ``response`` exactly as given -- including when it is not a dict, has no
        ``data`` key, or carries a key outside the sibling allowlist.
    """
    if not isinstance(response, dict) or "data" not in response:
        return response
    if not (set(response) - {"data"}) <= _ENVELOPE_SIBLING_KEYS:
        return response
    return response["data"]


def _message_or(error_detail: dict[str, Any], default: str) -> Any:
    """Return the extracted error message, or ``default`` when there isn't one.

    Substitutes on a FALSY value, not on an absent key. ``_extract_error_detail``
    always emits a ``message`` key — ``exc.details["message"]`` is a documented
    spelling, so dropping the key would ``KeyError`` anyone following the docs —
    and sets it to ``None`` when the body carried no message at all. A plain
    ``.get("message", default)`` would therefore return that ``None`` verbatim,
    which is how ``str(exc)`` came to print the literal string ``'None'`` at
    exactly the moment a caller most needs the message.

    The return is deliberately untyped as ``Any`` rather than ``str``: a ``422``
    carries a LIST of per-field validation objects in this slot, and callers
    iterate it.
    """
    return error_detail.get("message") or default


def _scrub_url_path(url: str) -> str:
    """Redact one-time tokens embedded in URL paths before logging.

    Two SDK endpoints carry a single-use token as a PATH segment rather than in
    the (already-scrubbed) request body: ``/api/v1/auth/verify-email/{token}``
    and ``/api/v1/invitations/{token}/accept``. The verbatim request URL is
    emitted on the DEBUG line and interpolated into retry-path exception
    messages, so the token would leak to any log sink at DEBUG.

    The redaction is deliberately ROUTE-SCOPED (only these two token-bearing
    routes) rather than a blanket last-segment redactor, so legitimate resource
    ids (e.g. ``/api/v1/agents/abc-123``) still log intact for debugging.
    """
    url = re.sub(r"(/auth/verify-email/)[^/?#]+", r"\1***", url)
    url = re.sub(r"(/invitations/)[^/?#]+(/accept)", r"\1***\2", url)
    return url


def _scrub_sensitive(data: dict | None) -> dict | None:
    """Redact sensitive fields from log data."""
    if not data or not isinstance(data, dict):
        return data
    result = {}
    for key, value in data.items():
        normalized = key.lower().replace("_", "")
        if normalized in _SENSITIVE_KEYS or any(
            token in normalized for token in _SENSITIVE_SUBSTRINGS
        ):
            result[key] = "****REDACTED****"
        elif isinstance(value, dict):
            result[key] = _scrub_sensitive(value)
        elif isinstance(value, list):
            result[key] = [
                _scrub_sensitive(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            result[key] = value
    return result


#: The prefix that makes a credential an Aegis API key rather than a session
#: JWT. The server's own credential extractors gate on exactly this string --
#: a value without it can never be validated as a key, whichever header it
#: arrives in -- so it is the only sound way to tell the two credentials apart
#: from the client side.
API_KEY_PREFIX = "sk_live_"

#: Every header this client may use to present a credential. Enumerated so a
#: credential swap can RETIRE the header it is not using -- see
#: :meth:`HTTPClient.set_api_key`.
_JSON_CONTENT_TYPE = "application/json"


def _httpx_types_the_body(httpx_kwargs: Mapping[str, Any]) -> bool:
    """True when httpx's own body encoder will set this request's ``Content-Type``.

    Mirrors ``httpx._content.encode_request``'s precedence exactly: a
    non-mapping ``data`` and any ``content`` are raw bytes (httpx sets no type);
    otherwise ``files`` is encoded as ``multipart/form-data; boundary=...`` and a
    non-empty mapping ``data`` as ``application/x-www-form-urlencoded``.
    ``json=`` is not listed: its type IS the SDK default, so applying the default
    to it changes nothing.
    """
    data = httpx_kwargs.get("data")
    if data is not None and not isinstance(data, Mapping):
        return False
    if httpx_kwargs.get("content") is not None:
        return False
    return bool(httpx_kwargs.get("files")) or bool(data)


def _with_default_content_type(
    headers: Mapping[str, str] | None, httpx_kwargs: Mapping[str, Any]
) -> dict[str, str] | None:
    """Return the per-request headers, carrying the SDK's JSON ``Content-Type`` default when due.

    ``Content-Type`` describes a BODY, so it is applied here, per request, and
    is never installed on the ``httpx.AsyncClient`` as a client-wide default.
    It used to be: httpx only ``setdefault``s the type its encoder
    computes, so the client default WON, and every multipart upload in the SDK
    went out labelled ``application/json`` with no boundary. The server could
    not parse the form and answered 422 ``body.file Field required`` — every
    call, for every upload method — while the module tests, which mock
    ``request()``, stayed green.

    Precedence: a caller-supplied ``Content-Type`` (any case) always wins; a body
    httpx types itself keeps httpx's type; everything else — ``json=``, raw
    ``content=``, no body — gets ``application/json``, exactly as before.
    """
    if headers and any(name.lower() == "content-type" for name in headers):
        return dict(headers)
    if _httpx_types_the_body(httpx_kwargs):
        return dict(headers) if headers is not None else None
    return {**(headers or {}), "Content-Type": _JSON_CONTENT_TYPE}


_CREDENTIAL_HEADERS: tuple[str, ...] = ("Authorization", "X-API-Key")

#: Verbs the transport may retry after a timeout or a dropped connection.
#:
#: THE SET IS THE HTTP IDEMPOTENCY DEFINITION, NOT A PREFERENCE. A retry is only
#: sound when re-sending the SAME request cannot produce a second effect, and
#: ``POST``/``PATCH`` are excluded for that reason alone. See ``request()`` for
#: what this fences and the measured case that put it here.
_IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


def _credential_headers(credential: str) -> dict[str, str]:
    """Return the header(s) that present ``credential`` on its own channel.

    THE TWO CREDENTIALS DO NOT SHARE A CHANNEL, even though this client stores
    them in one field. The server accepts an API key on either
    ``X-API-Key: sk_live_...`` or ``Authorization: Bearer sk_live_...``, and
    documents the FIRST as canonical and the Bearer form as "the documented
    alternative". A session JWT has only the
    ``Authorization`` channel -- placed in ``X-API-Key`` it is ignored, since
    both server extractors require the ``sk_live_`` prefix before a value
    reaches key validation.

    So the routing is by credential SHAPE, not by caller intent: a key goes to
    the canonical key header, anything else to Bearer. Sending an API key on
    the alternative channel worked and still would; the reason to move it is
    that this client's own diagnostic (``python -m aegis_sdk.coc.probe``)
    already used ``X-API-Key``, and a probe that authenticates differently
    from the client it diagnoses cannot reproduce the client's auth failures.

    CSRF is unaffected: the server's exemption for ``X-API-Key`` is gated on
    SUCCESSFUL key validation, which a real key passes.
    """
    if credential.startswith(API_KEY_PREFIX):
        return {"X-API-Key": credential}
    return {"Authorization": f"Bearer {credential}"}


class HTTPClient:
    """
    Internal HTTP client with retry, timeout, and connection pooling.

    This is an internal class not intended for direct use.
    Use AgenticOSClient instead.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.5,
        verify_ssl: bool = True,
        debug: bool = False,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for API requests
            api_key: API key for Bearer auth (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_backoff: Exponential backoff multiplier
            verify_ssl: Whether to verify SSL certificates
            debug: Enable debug logging
        """
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._verify_ssl = verify_ssl
        self._debug = debug

        # Create async client with connection pooling
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            verify=verify_ssl,
            # Content-Type is withheld from the CLIENT defaults and applied per
            # request by `_with_default_content_type` — see that function for
            # the upload failure a client-wide Content-Type caused.
            headers={
                name: value
                for name, value in self._build_headers().items()
                if name.lower() != "content-type"
            },
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build the SDK's default headers.

        ``Content-Type`` here is the default for a request whose body httpx does
        not type itself. It is applied per request by
        ``_with_default_content_type`` and is NOT installed on the underlying
        client, because a client-wide Content-Type overrides the multipart
        type (and boundary) httpx computes for an upload.
        """
        headers = {
            "Content-Type": _JSON_CONTENT_TYPE,
            "Accept": "application/json",
            "X-SDK-Version": __version__,
            "X-API-Version": "v1",
            "User-Agent": f"AgenticOS-SDK/{__version__}",
        }
        if self._api_key:
            headers.update(_credential_headers(self._api_key))
        return headers

    def set_api_key(self, api_key: str) -> None:
        """Update the API key for authentication.

        BOTH credential headers are rewritten on every call, never just the
        one being set. This slot holds an API key OR a session JWT (the
        client's own documented flow is
        ``client.set_api_key(token.access_token)``), so swapping one kind for
        the other must RETIRE the previous header -- leaving a stale
        ``X-API-Key`` beside a fresh ``Authorization`` would present two
        credentials at once and let the server authenticate as whichever it
        checked first.
        """
        self._api_key = api_key
        chosen = _credential_headers(api_key)
        for name in _CREDENTIAL_HEADERS:
            if name in chosen:
                self._client.headers[name] = chosen[name]
            else:
                self._client.headers.pop(name, None)

    def set_auth_token(self, token: str) -> None:
        """Update the auth token (same as API key)."""
        self.set_api_key(token)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        raw_response: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        Make HTTP request with automatic retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API path (e.g., "/api/v1/agents")
            params: Query parameters
            json_data: JSON request body
            headers: Additional headers
            raw_response: Return the response BODY AS BYTES instead of parsed
                JSON. For endpoints that emit a file (PDF, CSV, a signed
                export) rather than a JSON document — calling ``.json()`` on
                those raises. Error statuses still map to the same exceptions;
                only the SUCCESS path changes shape.

                This parameter previously did not exist while two shipped
                methods already passed it, so it fell into ``**kwargs`` and
                reached ``httpx.AsyncClient.request()``, which rejected it —
                ``export_audit`` and ``export_soc2_evidence`` raised
                ``TypeError: AsyncClient.request() got an unexpected keyword
                argument 'raw_response'`` on EVERY call, before any request was
                attempted.
            **kwargs: Additional httpx request arguments

        Returns:
            Parsed JSON response or None for 204

        Raises:
            AuthenticationError: For 401 responses
            AuthorizationError: For 403 responses
            NotFoundError: For 404 responses
            ValidationError: For 422 responses
            GovernanceViolationError: For 423 responses
            RateLimitError: For 429 responses
            TrustViolationError: For 451 responses
            ServiceError: For 5xx responses
            TimeoutError: On request timeout
            ConnectionError: On network errors
            AgenticOSError: For other errors
        """
        url = path if path.startswith("http") else path
        # Token-bearing routes carry a one-time token in the PATH; scrub it from
        # every logged / exception-surfaced rendering (the real `url` is still
        # sent to the transport below). See _scrub_url_path.
        safe_url = _scrub_url_path(url)

        if self._debug:
            logger.debug("SDK Request: %s %s", method, safe_url)
            if json_data:
                logger.debug("Request body: %s", _scrub_sensitive(json_data))

        last_exception: Exception | None = None

        # ⛔ ONLY IDEMPOTENT VERBS ARE RETRIED, and the reason is measured
        # rather than stylistic. This loop IS the send loop, so a retried verb
        # re-sends a request the server may already have applied: a
        # ``POST /organization-units`` that timed out AFTER the unit was created
        # produced a SECOND unit on the retry, and units cannot be renamed or
        # merged, so the duplicate was unfixable through this client. The
        # transport mints no idempotency key, so the verb is the only
        # discriminator available here — a reply that never arrived and a reply
        # that arrived too slowly are indistinguishable at this layer.
        #
        # A non-retryable verb still SENDS on the first pass and still re-raises
        # with the same type and the same ``__cause__`` as before this guard
        # existed; only the ``continue`` is suppressed.
        retryable = method.upper() in _IDEMPOTENT_METHODS

        for attempt in range(self._max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=_with_default_content_type(headers, kwargs),
                    **kwargs,
                )

                if self._debug:
                    logger.debug("Response: %s", response.status_code)

                return self._handle_response(response, raw_response=raw_response)

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(
                    f"Request timed out after {self._timeout}s: {method} {safe_url}"
                )
                if retryable and attempt < self._max_retries - 1:
                    await self._retry_delay(attempt)
                    continue
                raise last_exception from e

            except httpx.NetworkError as e:
                last_exception = ConnectionError(
                    f"Network error: {e}",
                    details={"url": safe_url, "method": method},
                )
                if retryable and attempt < self._max_retries - 1:
                    await self._retry_delay(attempt)
                    continue
                raise last_exception from e

            except httpx.RequestError as e:
                last_exception = ConnectionError(
                    f"Request error: {e}",
                    details={"url": safe_url, "method": method},
                )
                if retryable and attempt < self._max_retries - 1:
                    await self._retry_delay(attempt)
                    continue
                raise last_exception from e

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise ServiceError("Unknown error after retries")

    async def _retry_delay(self, attempt: int) -> None:
        """Calculate and apply retry delay with exponential backoff."""
        delay = self._retry_backoff**attempt
        if self._debug:
            logger.debug("Retrying in %ss (attempt %s)", delay, attempt + 1)
        await asyncio.sleep(delay)

    def _handle_response(self, response: httpx.Response, raw_response: bool = False) -> Any:
        """
        Handle HTTP response and map to exceptions.

        Args:
            response: httpx Response object

        Returns:
            The parsed JSON body, raw ``bytes`` when the body is not JSON
            (a file download, for example), or ``None`` for 204.

        Raises:
            Various AgenticOSError subclasses based on status code
        """
        status = response.status_code

        # Success responses.
        #
        # `raw_response` short-circuits BEFORE `.json()` (sdk/governance-cluster):
        # a PDF / CSV / signed-export body is not JSON, and parsing it raises.
        # That is the caller declaring intent up front.
        #
        # The parse-failure fallback below (sdk/p5-partial) is the safety net for
        # the routes that answer 200 with something non-JSON WITHOUT the caller
        # knowing -- a zip of an objective's artifacts, for instance. Before it
        # existed those raised a bare JSONDecodeError, which is in no documented
        # exception list and which no caller could reasonably handle.
        #
        # The predicate is "did the parse fail", NOT "what does the content-type
        # header say". That distinction is load-bearing: a JSON body served under
        # a wrong or missing content-type parses today and must keep parsing, so
        # branching on the header would change behaviour on paths that currently
        # work. Branching on the parse failure cannot -- every response that
        # parses today still parses, and only the responses that CRASH today take
        # the new path.
        #
        # 202 is grouped with 200/201 deliberately. The governance-cluster side
        # listed only 200 and 201, which would have dropped 202 through to the
        # error branch below; keeping the p5-partial grouping preserves it.
        # 204 still yields None rather than b"" -- "no content" is not an empty
        # file, and a caller writing b"" to disk would produce a zero-byte
        # artefact indistinguishable from a real but empty export.
        if status in (200, 201, 202) and raw_response:
            return response.content
        if status in (200, 201, 202):
            try:
                return response.json()
            except ValueError:
                return response.content
        elif status == 204:
            return None

        # Error responses
        error_detail = self._extract_error_detail(response)

        if status == 400:
            raise ValidationError(
                _message_or(error_detail, "Bad request"),
                details=error_detail,
            )
        elif status == 401:
            raise AuthenticationError(
                _message_or(error_detail, "Invalid API key or token expired"),
                details=error_detail,
            )
        elif status == 403:
            raise AuthorizationError(
                _message_or(error_detail, "Insufficient permissions"),
                details=error_detail,
            )
        elif status == 404:
            raise NotFoundError(
                _message_or(error_detail, "Resource not found"),
                details=error_detail,
            )
        elif status == 422:
            raise ValidationError(
                _message_or(error_detail, "Validation failed"),
                details=error_detail,
            )
        elif status == 423:
            raise GovernanceViolationError(
                _message_or(error_detail, "Governance policy violation"),
                details=error_detail,
            )
        elif status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError(
                _message_or(error_detail, f"Rate limit exceeded. Retry after {retry_after}s"),
                retry_after=retry_after,
                details=error_detail,
            )
        elif status == 451:
            raise TrustViolationError(
                _message_or(error_detail, "EATP trust constraint violation"),
                details=error_detail,
            )
        elif status >= 500:
            raise ServiceError(
                _message_or(error_detail, f"Backend error: {status}"),
                details=error_detail,
            )
        else:
            raise AgenticOSError(
                f"Unexpected status code: {status}",
                details=error_detail,
            )

    def _extract_error_detail(self, response: httpx.Response) -> dict[str, Any]:
        """Extract error details from an error response body.

        TWO WIRE SHAPES REACH THIS METHOD, AND ONLY ONE OF THEM IS THE ONE
        AEGIS ACTUALLY SENDS.

        The flat shape — ``{"detail": "...", "code": "..."}`` — is FastAPI's
        default and is what this method was originally written for. Aegis
        registers a global ``HTTPException`` handler, so **every** error the
        platform returns is re-wrapped into a canonical ENVELOPE before it
        leaves the server::

            {"error": {"code": "FORBIDDEN",
                       "message": "Constraint violation: ...",
                       "details": {...},
                       "request_id": "..."}}

        Read flat, that envelope produced three wrong answers at once, all of
        them quiet:

        * ``message`` fell through to ``body.get("error")`` and became the
          whole inner **dict**, so ``exc.message`` was not a string and
          ``str(exc)`` rendered a Python dict repr into user-facing output;
        * ``code`` read ``body["code"]``, which does not exist at the top
          level, so the server's error code was reported as ``None`` on every
          single error the platform raises;
        * ``details`` read ``body["details"]``, likewise absent at the top
          level, so **every structured field the server attaches was
          discarded** — including the ``dependency`` name on a 503 and any
          governance discriminator attached to a denial.

        That last one is the load-bearing failure. A caller cannot branch on a
        refusal it can only read as prose, so the structured channel being dead
        forced string-matching an English sentence — which is precisely what
        the structured channel exists to avoid.

        BOTH shapes stay supported. The envelope is recognised by an ``error``
        key whose value is a ``dict``; anything else takes the flat path
        unchanged, so a gateway, proxy or non-Aegis server answering in
        FastAPI's default shape still parses exactly as before. An ``error``
        key holding a plain STRING is not an envelope — some servers use it as
        the message itself — and is read that way.

        Returns:
            A dict carrying ``message``, ``code``, ``details``, ``request_id``
            and ``status_code``.

            The ``message`` key is ALWAYS present, and is ``None`` when the
            body carried no message at all. It is deliberately not omitted:
            ``exc.details["message"]`` is a documented spelling (see
            ``modules/roles.py``), and dropping the key would turn a body with
            no message into a ``KeyError`` for anyone following the docs.
            :meth:`_handle_response` substitutes its per-status default on a
            falsy value rather than on an absent key, so a caller still sees
            ``"Insufficient permissions"`` rather than a literal ``None``.

            ``message`` is passed through VERBATIM and is **not** coerced to
            ``str``. A ``422`` legitimately carries a *list* of per-field
            validation objects there, which callers iterate (the handbook
            documents doing exactly that), and stringifying it would destroy
            the most useful error body the API produces while looking like a
            tidy-up. The dict-shaped ``message`` this method used to return is
            fixed by recognising the envelope above, not by flattening it here.
        """
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            return {
                "message": response.text[:500] if response.text else "Unknown error",
                "status_code": response.status_code,
            }

        if not isinstance(body, dict):
            return {"message": str(body), "status_code": response.status_code}

        envelope = body.get("error")
        if isinstance(envelope, dict):
            # Canonical Aegis error envelope: every field lives one level in.
            source: dict[str, Any] = envelope
            message = envelope.get("message") or envelope.get("detail") or envelope.get("error")
        else:
            # Flat/FastAPI-default shape. `envelope` here is either absent or a
            # plain string, in which case it IS the message.
            source = body
            message = body.get("detail") or body.get("message") or envelope

        return {
            "message": message,
            "code": source.get("code"),
            "details": source.get("details"),
            "request_id": source.get("request_id"),
            "status_code": response.status_code,
        }

    async def stream(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Make streaming HTTP request (SSE).

        Args:
            method: HTTP method
            path: API path
            json_data: JSON request body
            **kwargs: Additional arguments

        Yields:
            Parsed SSE data events

        Example:
            >>> async for event in client.stream("POST", "/api/v1/agents/x/stream"):
            ...     print(event)
        """
        url = path if path.startswith("http") else path
        kwargs["headers"] = _with_default_content_type(kwargs.get("headers"), kwargs)

        async with self._client.stream(
            method=method,
            url=url,
            json=json_data,
            **kwargs,
        ) as response:
            # Check for error responses
            if response.status_code >= 400:
                # Read full body for error
                await response.aread()
                self._handle_response(response)

            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue

                # Parse SSE format
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        if self._debug:
                            logger.warning("Failed to parse SSE data: %s", data_str)
                        continue

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        await self._client.aclose()

    async def __aenter__(self) -> "HTTPClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Sync wrapper for the HTTP client (if needed)
class SyncHTTPClient:
    """
    Synchronous wrapper for HTTPClient.

    Provides blocking methods that run the async client in a new event loop.
    Useful for scripts and non-async contexts.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self._async_client = HTTPClient(*args, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make synchronous HTTP request."""
        return asyncio.get_event_loop().run_until_complete(
            self._async_client.request(method, path, **kwargs)
        )

    def close(self) -> None:
        """Close the HTTP client."""
        asyncio.get_event_loop().run_until_complete(self._async_client.close())

    def __enter__(self) -> "SyncHTTPClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
