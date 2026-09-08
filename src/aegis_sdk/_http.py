"""
Agentic OS SDK Internal HTTP Client.

Provides an async-first HTTP client with:
- Connection pooling
- Automatic retry with exponential backoff
- Exception mapping for HTTP status codes
- SDK version headers
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
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
            headers=self._build_headers(),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build default headers for all requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-SDK-Version": __version__,
            "X-API-Version": "v1",
            "User-Agent": f"AgenticOS-SDK/{__version__}",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def set_api_key(self, api_key: str) -> None:
        """Update the API key for authentication."""
        self._api_key = api_key
        self._client.headers["Authorization"] = f"Bearer {api_key}"

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

        for attempt in range(self._max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                    **kwargs,
                )

                if self._debug:
                    logger.debug("Response: %s", response.status_code)

                return self._handle_response(response, raw_response=raw_response)

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(
                    f"Request timed out after {self._timeout}s: {method} {safe_url}"
                )
                if attempt < self._max_retries - 1:
                    await self._retry_delay(attempt)
                    continue
                raise last_exception from e

            except httpx.NetworkError as e:
                last_exception = ConnectionError(
                    f"Network error: {e}",
                    details={"url": safe_url, "method": method},
                )
                if attempt < self._max_retries - 1:
                    await self._retry_delay(attempt)
                    continue
                raise last_exception from e

            except httpx.RequestError as e:
                last_exception = ConnectionError(
                    f"Request error: {e}",
                    details={"url": safe_url, "method": method},
                )
                if attempt < self._max_retries - 1:
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
                error_detail.get("message", "Bad request"),
                details=error_detail,
            )
        elif status == 401:
            raise AuthenticationError(
                error_detail.get("message", "Invalid API key or token expired"),
                details=error_detail,
            )
        elif status == 403:
            raise AuthorizationError(
                error_detail.get("message", "Insufficient permissions"),
                details=error_detail,
            )
        elif status == 404:
            raise NotFoundError(
                error_detail.get("message", "Resource not found"),
                details=error_detail,
            )
        elif status == 422:
            raise ValidationError(
                error_detail.get("message", "Validation failed"),
                details=error_detail,
            )
        elif status == 423:
            raise GovernanceViolationError(
                error_detail.get("message", "Governance policy violation"),
                details=error_detail,
            )
        elif status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise RateLimitError(
                error_detail.get("message", f"Rate limit exceeded. Retry after {retry_after}s"),
                retry_after=retry_after,
                details=error_detail,
            )
        elif status == 451:
            raise TrustViolationError(
                error_detail.get("message", "EATP trust constraint violation"),
                details=error_detail,
            )
        elif status >= 500:
            raise ServiceError(
                error_detail.get("message", f"Backend error: {status}"),
                details=error_detail,
            )
        else:
            raise AgenticOSError(
                f"Unexpected status code: {status}",
                details=error_detail,
            )

    def _extract_error_detail(self, response: httpx.Response) -> dict[str, Any]:
        """Extract error details from response body."""
        try:
            body = response.json()
            if isinstance(body, dict):
                return {
                    "message": body.get("detail") or body.get("message") or body.get("error"),
                    "code": body.get("code"),
                    "details": body.get("details"),
                    "status_code": response.status_code,
                }
            return {"message": str(body), "status_code": response.status_code}
        except (json.JSONDecodeError, ValueError):
            return {
                "message": response.text[:500] if response.text else "Unknown error",
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
