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
        message: Human-readable error message.
        details: Additional error context as a dictionary. Always carries
            ``status_code`` for an error that came back from the server.
        error_code: The server's machine-readable error code for this
            refusal (``"FORBIDDEN"``, ``"DEPENDENCY_UNAVAILABLE"``, …), or
            ``None`` when the error did not originate from a server response
            (a local timeout or connection failure, for instance).
        server_details: The **structured** fields the server attached beside
            the message — an empty dict when it attached none. This is the
            channel to branch on. Read a field off it; do not parse
            :attr:`message`, which is prose written for a human and may be
            reworded in any release without notice.
        request_id: The server's correlation id for this request, when it
            supplied one. Quote it when reporting a refusal you cannot
            explain — it is what lets an operator find the same event on
            their side.

    Branching on a refusal::

        try:
            await client.agents.execute(agent_id, message="...")
        except AgenticOSError as exc:
            if exc.error_code == "DEPENDENCY_UNAVAILABLE":
                # A named component is down; the request is retryable.
                dependency = exc.server_details.get("dependency")
            else:
                # A decision about THIS caller. Retrying changes nothing.
                ...

    ⚠ **What a field's ABSENCE from** :attr:`server_details` **means.** It
    means the server did not send that field on this response — never that
    the underlying condition does not hold. Several refusal paths still
    serialise only a prose sentence, so their structured half arrives empty.
    Treat a missing key as UNDETERMINED and say so, rather than inferring the
    negative case from it. The gaps known at the time of writing, and what
    closes each, are enumerated in
    ``handbook/04-the-api-surface/02-errors-and-refusals.md``.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        # Projected from `details` rather than stored twice: `_http` builds
        # that dict from the response envelope, so anything read here stays in
        # agreement with it by construction. Subclasses that take an explicit
        # `error_code` (see `ServiceUnavailableError`) assign it AFTER calling
        # super(), overwriting the projection — deliberate, and the reason
        # these are plain attributes rather than properties, which could not
        # be overwritten that way.
        # Every projection is type-guarded, because the source is a SERVER
        # response body and these are the attributes the docstring above tells
        # partners to branch on. An unguarded `error_code` holding a dict makes
        # `exc.error_code.startswith(...)` raise AttributeError, while
        # `exc.error_code == "X"` silently never matches — two different wrong
        # answers from one malformed field. Coercing to None instead gives the
        # documented `str | None` contract a value that is actually true.
        source = self.details if isinstance(self.details, dict) else {}
        code = source.get("code")
        self.error_code: str | None = code if isinstance(code, str) else None
        req_id = source.get("request_id")
        self.request_id: str | None = req_id if isinstance(req_id, str) else None
        nested = source.get("details")
        self.server_details: dict[str, Any] = nested if isinstance(nested, dict) else {}
        # `server_details["unverifiable_scope"]` is THE PARTNER'S HALF of a
        # governance-refusal split, and it is documented here because the SDK
        # is where a caller reads it. A refusal caused by the GOVERNANCE
        # APPARATUS being unreachable and one caused by THIS AGENT's own
        # declared restriction are different answers:
        #
        #     "apparatus"   — the refusal could not be evaluated; retrying may
        #                     succeed, and the caller should not treat it as a
        #                     statement about the agent's authority.
        #     "subject"     — the agent's own declared restriction produced the
        #                     refusal; retrying changes nothing.
        #     "unspecified" — the server denied on an unverifiable condition but
        #                     did not classify it. Treat EXACTLY as a missing
        #                     key: UNDETERMINED, and never as "subject".
        #
        # ⛔ THAT SET IS CLOSED, and this was a real defect until a later fix. An
        # earlier revision of this comment named only the first two values while
        # the server could already emit the third — so a partner branching on
        # the documented contract had no defined behaviour for "unspecified",
        # and the value it did get for the unclassifiable case contradicted the
        # paragraph below (which said that case arrives ABSENT). The producer is
        # live: `constraint_enforcer.py`'s temporal-unverifiable emit site
        # places exactly these three under `metadata["unverifiable_scope"]`, and
        # `api/agent_execute.py` forwards it into the 403 body. Do NOT
        # pattern-match a fourth value; if the server learns one, this contract
        # learns it in the same change.
        #
        # ⛔ AND THE KEY IS GENUINELY ABSENT (`{}`) FOR LOCAL ERRORS AND FOR
        # SERVER REFUSAL PATHS THAT CARRY NO STRUCTURED HALF AT ALL. Absent
        # means "not reported" — which is NOT the same state as "unspecified".
        # "unspecified" is a report that the server had nothing to classify the
        # refusal with; absence is no report at all. Both resolve to
        # UNDETERMINED for remediation purposes, and neither is a statement
        # about the agent's authority.
        #
        # Before this attribute both converged on one opaque 403 body, so a
        # caller could only string-match English prose to tell them apart.
        # ⛔ PROSE IS NOT A CONTRACT — branch on this attribute, never on the
        # message text.
        super().__init__(self.message)

    @property
    def status_code(self) -> int | None:
        """The HTTP status this error was mapped from, or ``None`` if local.

        ``exc.details["status_code"]`` is the long-standing spelling and keeps
        working; this is the same value without the ``KeyError`` risk on an
        error the SDK raised locally, where no response existed to carry one.
        """
        source = self.details if isinstance(self.details, dict) else {}
        value = source.get("status_code")
        return value if isinstance(value, int) else None


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
