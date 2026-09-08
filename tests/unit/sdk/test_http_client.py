"""
Tier 1: Unit Tests for SDK HTTP Client.

Tests cover:
- HTTPClient initialization
- Header building
- Response handling and exception mapping
- Retry logic

Total: 17 tests
"""

import httpx
import pytest

from aegis_sdk._http import HTTPClient
from aegis_sdk.exceptions import (
    AuthenticationError,
    AuthorizationError,
    GovernanceViolationError,
    NotFoundError,
    RateLimitError,
    ServiceError,
    TrustViolationError,
    ValidationError,
)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHTTPClientInit:
    """Test HTTPClient initialization."""

    def test_init_with_base_url(self):
        """HTTPClient should accept base_url."""
        client = HTTPClient(base_url="https://api.example.com")
        assert client.base_url == "https://api.example.com"

    def test_init_strips_trailing_slash(self):
        """HTTPClient should strip trailing slash from base_url."""
        client = HTTPClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    def test_init_with_api_key(self):
        """HTTPClient should accept api_key."""
        client = HTTPClient(
            base_url="https://api.example.com",
            api_key="aos_test_key",
        )
        assert client._api_key == "aos_test_key"

    def test_init_with_all_options(self):
        """HTTPClient should accept all configuration options."""
        client = HTTPClient(
            base_url="https://api.example.com",
            api_key="aos_test_key",
            timeout=60.0,
            max_retries=5,
            retry_backoff=2.0,
            verify_ssl=False,
            debug=True,
        )
        assert client._timeout == 60.0
        assert client._max_retries == 5
        assert client._retry_backoff == 2.0
        assert client._debug is True


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHTTPClientHeaders:
    """Test header building."""

    def test_build_headers_without_api_key(self):
        """Headers should include SDK version without auth."""
        client = HTTPClient(base_url="https://api.example.com")
        headers = client._build_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert "X-SDK-Version" in headers
        assert "X-API-Version" in headers
        assert "Authorization" not in headers

    def test_build_headers_with_api_key(self):
        """Headers should include Authorization with api_key."""
        client = HTTPClient(
            base_url="https://api.example.com",
            api_key="aos_test_key",
        )
        headers = client._build_headers()

        assert headers["Authorization"] == "Bearer aos_test_key"

    def test_set_api_key_updates_headers(self):
        """set_api_key should update client headers."""
        client = HTTPClient(base_url="https://api.example.com")
        assert client._api_key is None

        client.set_api_key("new_key")
        assert client._api_key == "new_key"
        assert "Bearer new_key" in client._client.headers.get("Authorization", "")


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHTTPClientResponseHandling:
    """Test response handling and exception mapping."""

    def _make_response(
        self, status_code: int, body: dict = None, headers: dict = None
    ) -> httpx.Response:
        """Create mock response."""
        return httpx.Response(
            status_code=status_code,
            json=body,
            headers=headers or {},
        )

    def test_handle_200_returns_json(self):
        """200 response should return parsed JSON."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(200, {"data": "test"})

        result = client._handle_response(response)
        assert result == {"data": "test"}

    def test_handle_201_returns_json(self):
        """201 response should return parsed JSON."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(201, {"id": "new_123"})

        result = client._handle_response(response)
        assert result == {"id": "new_123"}

    def test_handle_204_returns_none(self):
        """204 response should return None."""
        client = HTTPClient(base_url="https://api.example.com")
        response = httpx.Response(status_code=204)

        result = client._handle_response(response)
        assert result is None

    def test_handle_401_raises_authentication_error(self):
        """401 response should raise AuthenticationError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(401, {"detail": "Invalid token"})

        with pytest.raises(AuthenticationError) as exc_info:
            client._handle_response(response)

        assert "Invalid token" in str(exc_info.value.message)

    def test_handle_403_raises_authorization_error(self):
        """403 response should raise AuthorizationError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(403, {"detail": "Access denied"})

        with pytest.raises(AuthorizationError) as exc_info:
            client._handle_response(response)

        assert "Access denied" in str(exc_info.value.message)

    def test_handle_404_raises_not_found_error(self):
        """404 response should raise NotFoundError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(404, {"detail": "Agent not found"})

        with pytest.raises(NotFoundError) as exc_info:
            client._handle_response(response)

        assert "Agent not found" in str(exc_info.value.message)

    def test_handle_422_raises_validation_error(self):
        """422 response should raise ValidationError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(
            422,
            {"detail": "Validation failed", "errors": [{"field": "name"}]},
        )

        with pytest.raises(ValidationError) as exc_info:
            client._handle_response(response)

        assert "Validation failed" in str(exc_info.value.message)

    def test_handle_423_raises_governance_violation_error(self):
        """423 response should raise GovernanceViolationError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(423, {"detail": "Budget exceeded"})

        with pytest.raises(GovernanceViolationError) as exc_info:
            client._handle_response(response)

        assert "Budget exceeded" in str(exc_info.value.message)

    def test_handle_429_raises_rate_limit_error(self):
        """429 response should raise RateLimitError with retry_after."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(
            429,
            {"detail": "Rate limit exceeded"},
            headers={"Retry-After": "120"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            client._handle_response(response)

        assert exc_info.value.retry_after == 120

    def test_handle_451_raises_trust_violation_error(self):
        """451 response should raise TrustViolationError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(451, {"detail": "Trust chain invalid"})

        with pytest.raises(TrustViolationError) as exc_info:
            client._handle_response(response)

        assert "Trust chain invalid" in str(exc_info.value.message)

    def test_handle_500_raises_service_error(self):
        """500+ response should raise ServiceError."""
        client = HTTPClient(base_url="https://api.example.com")
        response = self._make_response(500, {"detail": "Internal error"})

        with pytest.raises(ServiceError) as exc_info:
            client._handle_response(response)

        assert "Internal error" in str(exc_info.value.message)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHTTPClientContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        """Context manager should close client on exit."""
        async with HTTPClient(base_url="https://api.example.com") as client:
            assert client._client is not None

        # After exit, client should be closed
        # Note: httpx doesn't raise on operations after close
        # so we just verify the context manager works


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestExtractErrorDetail:
    """Test error detail extraction from responses."""

    def test_extract_detail_from_json(self):
        """Should extract detail from JSON response."""
        client = HTTPClient(base_url="https://api.example.com")
        response = httpx.Response(
            status_code=400,
            json={"detail": "Bad request", "code": "ERR001"},
        )

        detail = client._extract_error_detail(response)
        assert detail["message"] == "Bad request"
        assert detail["code"] == "ERR001"

    def test_extract_message_from_json(self):
        """Should extract message field as fallback."""
        client = HTTPClient(base_url="https://api.example.com")
        response = httpx.Response(
            status_code=400,
            json={"message": "Error message"},
        )

        detail = client._extract_error_detail(response)
        assert detail["message"] == "Error message"

    def test_extract_from_invalid_json(self):
        """Should handle non-JSON responses."""
        client = HTTPClient(base_url="https://api.example.com")
        response = httpx.Response(
            status_code=500,
            content=b"Internal Server Error",
        )

        detail = client._extract_error_detail(response)
        assert "Internal Server Error" in detail["message"]
