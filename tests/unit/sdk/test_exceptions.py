"""
Tier 1: Unit Tests for SDK Exception Hierarchy.

Tests cover:
- Base exception creation and attributes
- All exception subclasses
- RateLimitError with retry_after
- ServiceUnavailableError with error_code
- Exception message and details

Total: 16 tests
"""

import pytest

from aegis_sdk.exceptions import (
    AgenticOSError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    GovernanceViolationError,
    NotFoundError,
    RateLimitError,
    ServiceError,
    ServiceUnavailableError,
    TimeoutError,
    TrustViolationError,
    UnsupportedOperationError,
    ValidationError,
)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestAgenticOSError:
    """Test base exception class."""

    def test_create_with_message(self):
        """Base exception should accept message."""
        error = AgenticOSError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_create_with_details(self):
        """Base exception should accept details dict."""
        details = {"code": "ERR001", "field": "email"}
        error = AgenticOSError("Validation failed", details=details)
        assert error.message == "Validation failed"
        assert error.details == details
        assert error.details["code"] == "ERR001"

    def test_details_default_to_empty_dict(self):
        """Details should default to empty dict if not provided."""
        error = AgenticOSError("Test")
        assert error.details == {}
        assert isinstance(error.details, dict)

    def test_is_exception_subclass(self):
        """AgenticOSError should inherit from Exception."""
        assert issubclass(AgenticOSError, Exception)
        error = AgenticOSError("Test")
        assert isinstance(error, Exception)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestAuthExceptions:
    """Test authentication/authorization exceptions."""

    def test_authentication_error(self):
        """AuthenticationError for invalid credentials."""
        error = AuthenticationError("Invalid API key")
        assert error.message == "Invalid API key"
        assert isinstance(error, AgenticOSError)

    def test_authorization_error(self):
        """AuthorizationError for insufficient permissions."""
        error = AuthorizationError(
            "Insufficient permissions",
            details={"required_scope": "agents:write"},
        )
        assert error.message == "Insufficient permissions"
        assert error.details["required_scope"] == "agents:write"
        assert isinstance(error, AgenticOSError)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestResourceExceptions:
    """Test resource-related exceptions."""

    def test_not_found_error(self):
        """NotFoundError for missing resources."""
        error = NotFoundError(
            "Agent not found",
            details={"resource_type": "agent", "resource_id": "agent_123"},
        )
        assert error.message == "Agent not found"
        assert error.details["resource_type"] == "agent"
        assert isinstance(error, AgenticOSError)

    def test_validation_error(self):
        """ValidationError for invalid request data."""
        error = ValidationError(
            "Validation failed",
            details={
                "errors": [
                    {"field": "name", "message": "required"},
                    {"field": "email", "message": "invalid format"},
                ]
            },
        )
        assert error.message == "Validation failed"
        assert len(error.details["errors"]) == 2
        assert isinstance(error, AgenticOSError)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestRateLimitError:
    """Test rate limit exception with retry_after."""

    def test_rate_limit_with_retry_after(self):
        """RateLimitError should include retry_after attribute."""
        error = RateLimitError("Rate limit exceeded", retry_after=120)
        assert error.message == "Rate limit exceeded"
        assert error.retry_after == 120
        assert isinstance(error, AgenticOSError)

    def test_rate_limit_default_retry_after(self):
        """RateLimitError should have default retry_after of 60."""
        error = RateLimitError("Rate limit exceeded")
        assert error.retry_after == 60

    def test_rate_limit_with_details(self):
        """RateLimitError should accept details."""
        error = RateLimitError(
            "Rate limit exceeded",
            retry_after=30,
            details={"limit": 100, "remaining": 0},
        )
        assert error.retry_after == 30
        assert error.details["limit"] == 100


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestServiceUnavailableError:
    """Test service unavailable exception with error_code."""

    def test_service_unavailable_with_error_code(self):
        """ServiceUnavailableError should include error_code."""
        error = ServiceUnavailableError(
            error_code="KAIZEN_UNAVAILABLE",
            message="Kaizen SDK is required",
            details={"installation": "pip install kailash-kaizen"},
        )
        assert error.error_code == "KAIZEN_UNAVAILABLE"
        assert error.message == "Kaizen SDK is required"
        assert error.details["installation"] == "pip install kailash-kaizen"
        assert isinstance(error, AgenticOSError)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestGovernanceExceptions:
    """Test governance and trust exceptions."""

    def test_governance_violation_error(self):
        """GovernanceViolationError for policy violations."""
        error = GovernanceViolationError(
            "Budget limit exceeded",
            details={"policy": "monthly_budget", "limit": 1000, "current": 1200},
        )
        assert error.message == "Budget limit exceeded"
        assert error.details["policy"] == "monthly_budget"
        assert isinstance(error, AgenticOSError)

    def test_trust_violation_error(self):
        """TrustViolationError for EATP violations."""
        error = TrustViolationError(
            "Trust chain verification failed",
            details={"chain_id": "chain_123", "reason": "expired_delegation"},
        )
        assert error.message == "Trust chain verification failed"
        assert error.details["chain_id"] == "chain_123"
        assert isinstance(error, AgenticOSError)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestNetworkExceptions:
    """Test network-related exceptions."""

    def test_service_error(self):
        """ServiceError for 5xx backend errors."""
        error = ServiceError("Backend error: 503")
        assert error.message == "Backend error: 503"
        assert isinstance(error, AgenticOSError)

    def test_connection_error(self):
        """ConnectionError for network issues."""
        error = ConnectionError(
            "Failed to connect",
            details={"url": "https://api.example.com"},
        )
        assert error.message == "Failed to connect"
        assert isinstance(error, AgenticOSError)

    def test_timeout_error(self):
        """TimeoutError for request timeouts."""
        error = TimeoutError("Request timed out after 30s")
        assert error.message == "Request timed out after 30s"
        assert isinstance(error, AgenticOSError)

    def test_configuration_error(self):
        """ConfigurationError for SDK configuration issues."""
        error = ConfigurationError(
            "Missing API key",
            details={"env_var": "AGENTIC_OS_API_KEY"},
        )
        assert error.message == "Missing API key"
        assert isinstance(error, AgenticOSError)

    def test_unsupported_operation_error(self):
        """UnsupportedOperationError for SDK methods with no backing server route."""
        error = UnsupportedOperationError(
            "suspend() has no backing server route",
            details={"issue": "1135"},
        )
        assert error.message == "suspend() has no backing server route"
        assert error.details == {"issue": "1135"}
        assert isinstance(error, AgenticOSError)
