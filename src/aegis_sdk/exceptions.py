"""
Agentic OS SDK Exception Hierarchy.

All SDK exceptions inherit from AgenticOSError, allowing users to catch
all SDK-related errors with a single except clause.
"""

from typing import Any


class AgenticOSError(Exception):
    """
    Base exception for all SDK errors.

    Attributes:
        message: Human-readable error message
        details: Additional error context as a dictionary
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(AgenticOSError):
    """
    Authentication failed.

    Raised when:
    - API key is invalid or malformed
    - Token has expired
    - Credentials are incorrect
    """

    pass


class AuthorizationError(AgenticOSError):
    """
    Insufficient permissions for requested operation.

    Raised when the authenticated user lacks the required
    permissions for the requested resource or action.
    """

    pass


class NotFoundError(AgenticOSError):
    """
    Requested resource not found.

    Raised when the specified resource (agent, skill, pipeline, etc.)
    does not exist or has been deleted.
    """

    pass


class ValidationError(AgenticOSError):
    """
    Request validation failed.

    Raised when the request payload fails server-side validation.
    Check the details dict for specific field errors.
    """

    pass


class RateLimitError(AgenticOSError):
    """
    Rate limit exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying
    """

    def __init__(self, message: str, retry_after: int = 60, details: dict[str, Any] | None = None):
        super().__init__(message, details)
        self.retry_after = retry_after


class ServiceError(AgenticOSError):
    """
    Backend service error (5xx).

    Raised when the Agentic OS backend encounters an internal error.
    These errors may be transient and retryable.
    """

    pass


class PaymentError(AgenticOSError):
    """
    Payment processing failed.

    Raised when:
    - Payment method is invalid or expired
    - Payment was declined by the processor
    - Insufficient funds
    - Stripe API errors during payment processing

    Attributes:
        decline_code: Payment processor decline code (if available)
    """

    def __init__(
        self,
        message: str,
        decline_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.decline_code = decline_code


class TrustViolationError(AgenticOSError):
    """
    EATP trust constraint violation.

    Raised when an operation violates the Enterprise Agent Trust Protocol
    constraints, such as trust chain verification failures or
    unauthorized trust delegation attempts.
    """

    pass


class GovernanceViolationError(AgenticOSError):
    """
    Governance policy violation.

    Raised when an operation violates configured governance policies,
    such as budget limits, approval requirements, or rate limits.
    """

    pass


class ServiceUnavailableError(AgenticOSError):
    """
    Required service or module unavailable.

    Raised when a required backend service (e.g., Kaizen, DataFlow)
    is not available or not properly configured.

    Attributes:
        error_code: Machine-readable error code
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.error_code = error_code


class ConfigurationError(AgenticOSError):
    """
    SDK configuration error.

    Raised when the SDK is misconfigured, such as missing
    required environment variables or invalid settings.
    """

    pass


class ConnectionError(AgenticOSError):
    """
    Network connection error.

    Raised when unable to establish or maintain connection
    to the Agentic OS API.
    """

    pass


class TimeoutError(AgenticOSError):
    """
    Request timeout.

    Raised when a request exceeds the configured timeout duration.
    """

    pass


class UnsupportedOperationError(AgenticOSError):
    """
    SDK method has no backing server capability.

    Distinct from a transient :class:`ServiceUnavailableError` (infra is down
    but the capability exists) — this is raised by SDK methods that were
    found, via route verification, to target a server operation that does
    not exist and is not specced. The method is kept as a
    deprecation shim per the zero-tolerance public-API-removal discipline;
    it will be deleted in a future release once the shim has lived through
    one minor cycle.
    """

    pass


# Aliases for convenience
NetworkError = ConnectionError
RequestTimeout = TimeoutError
