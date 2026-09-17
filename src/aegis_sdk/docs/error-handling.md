# Error Handling

All SDK exceptions inherit from `AgenticOSError`, allowing you to catch all SDK errors with a single handler or handle specific error types individually.

## Exception Hierarchy

```
AgenticOSError (base)
|-- AuthenticationError        # 401 - Invalid API key or expired token
|-- AuthorizationError         # 403 - Insufficient permissions
|-- NotFoundError              # 404 - Resource not found
|-- ValidationError            # 400/422 - Invalid request data
|-- RateLimitError             # 429 - Rate limit exceeded (has retry_after)
|-- GovernanceViolationError   # 423 - Governance policy violation
|-- TrustViolationError        # 451 - EATP trust constraint violation
|-- ServiceError               # 5xx - Backend server error
|-- PaymentError               # Payment processing failure (has decline_code)
|-- ServiceUnavailableError    # Service module unavailable (has error_code)
|-- ConfigurationError         # SDK misconfiguration
|-- ConnectionError            # Network connection failure (alias: NetworkError)
|-- TimeoutError               # Request timeout (alias: RequestTimeout)
```

## Exception Attributes

All exceptions share these attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | `str` | Human-readable error message |
| `details` | `Dict[str, Any]` | Additional context (status code, error code, etc.) |

Special attributes on specific exceptions:

| Exception | Attribute | Type | Description |
|-----------|-----------|------|-------------|
| `RateLimitError` | `retry_after` | `int` | Seconds to wait before retrying |
| `PaymentError` | `decline_code` | `Optional[str]` | Stripe decline code |
| `ServiceUnavailableError` | `error_code` | `str` | Machine-readable error code |

## Basic Error Handling

### Catch All SDK Errors

```python
import asyncio
from aegis_sdk import AgenticOSClient, AgenticOSError

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        try:
            agent = await client.agents.get("agent_nonexistent")
        except AgenticOSError as e:
            print(f"SDK error: {e.message}")
            print(f"Details: {e.details}")

asyncio.run(main())
```

### Handle Specific Error Types

```python
import asyncio
from aegis_sdk import (
    AgenticOSClient,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServiceError,
    AgenticOSError,
)

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        try:
            agent = await client.agents.create(
                name="My Agent",
                agent_type="chat",
            )
        except AuthenticationError as e:
            print(f"Auth failed: {e.message}")
            # Re-authenticate or refresh token
        except AuthorizationError as e:
            print(f"Permission denied: {e.message}")
            # Request elevated permissions
        except ValidationError as e:
            print(f"Invalid data: {e.message}")
            print(f"Field errors: {e.details}")
            # Fix request payload
        except RateLimitError as e:
            print(f"Rate limited: {e.message}")
            print(f"Retry after {e.retry_after} seconds")
            # Wait and retry
        except NotFoundError as e:
            print(f"Not found: {e.message}")
            # Resource doesn't exist
        except ServiceError as e:
            print(f"Server error: {e.message}")
            # Retry or report
        except AgenticOSError as e:
            print(f"Other SDK error: {e.message}")

asyncio.run(main())
```

## Rate Limit Handling

The `RateLimitError` includes a `retry_after` attribute indicating how many seconds to wait:

```python
import asyncio
from aegis_sdk import AgenticOSClient, RateLimitError, AgenticOSError

async def with_rate_limit_retry(client: AgenticOSClient, agent_id: str) -> None:
    max_retries: int = 3

    for attempt in range(max_retries):
        try:
            result = await client.agents.execute(
                agent_id,
                objective="Analyze this data",
            )
            print(f"Result: {result.status}")
            return
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time: int = e.retry_after
                print(f"Rate limited. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                raise

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        await with_rate_limit_retry(client, "agent_abc123")

asyncio.run(main())
```

## Trust Violation Handling

`TrustViolationError` (HTTP 451) is raised when an operation violates EATP constraints:

```python
import asyncio
from aegis_sdk import AgenticOSClient, TrustViolationError

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        try:
            result = await client.trust.chains.verify(
                agent_id="agent_abc123",
                action="write",
                resource="restricted_resource",
            )
        except TrustViolationError as e:
            print(f"Trust violation: {e.message}")
            print(f"Details: {e.details}")
            # The agent lacks authorization for this action.
            # Check trust chain capabilities and constraints.

asyncio.run(main())
```

## Governance Violation Handling

`GovernanceViolationError` (HTTP 423) is raised when governance policies block an operation:

```python
import asyncio
from aegis_sdk import AgenticOSClient, GovernanceViolationError

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        try:
            execution = await client.agents.execute(
                "agent_abc123",
                objective="Deploy to production",
            )
        except GovernanceViolationError as e:
            print(f"Governance block: {e.message}")
            # The action requires approval or exceeds budget limits

asyncio.run(main())
```

### Explaining the decision instead of inferring it

A `423` tells you governance blocked the operation; it does not tell you which
step of the access chain decided that. `client.governance_explain` answers the
second question:

```python
import asyncio
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        why = await client.governance_explain.explain_access(
            role_id="role-analyst",
            knowledge_item={
                "id": "doc-9",
                "classification": "confidential",
                "unit_address": "D1-R1",
            },
            posture="supervised",
        )
        print(why.allowed, why.step_reached, why.reason)

asyncio.run(main())
```

Read `step_reached`: when `allowed` is `False` it names the step the chain
stopped at. `reason` and `access_path` carry the rest of the trace.

⚠ **This is a dry run over an item you describe, not a record of a past call.**
It reads no stored knowledge item and records no access, so the verdict is only
as good as the `knowledge_item` you pass — a wrong or missing field changes the
answer. It is not evidence that a real access was permitted or refused.

The same module carries the state readouts: `explain_envelope()` for a role's
effective envelope through its ancestor chain, `describe_address()` for a D/T/R
address, and `envelope_hydration_status()` / `envelope_coverage()` /
`probe_corrupted_roles()` for readiness over the org's envelopes and role
grammar.

## Payment Error Handling

`PaymentError` includes an optional `decline_code` from the payment processor:

```python
import asyncio
from aegis_sdk import AgenticOSClient, PaymentError

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        try:
            subscription = await client.revenue.subscriptions.subscribe(
                plan_id="professional",
                billing_cycle="monthly",
                payment_method_id="pm_card_visa",
            )
        except PaymentError as e:
            print(f"Payment failed: {e.message}")
            if e.decline_code:
                print(f"Decline code: {e.decline_code}")
            # Prompt user to update payment method

asyncio.run(main())
```

## Connection and Timeout Errors

Network issues raise `ConnectionError` (aliased as `NetworkError`) or `TimeoutError` (aliased as `RequestTimeout`):

```python
import asyncio
from aegis_sdk import (
    AgenticOSClient,
    ConnectionError,
    TimeoutError,
    # Aliases:
    NetworkError,      # Same as ConnectionError
    RequestTimeout,    # Same as TimeoutError
)

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        try:
            agents = await client.agents.list()
        except TimeoutError as e:
            print(f"Request timed out: {e.message}")
            # Increase timeout or retry
        except ConnectionError as e:
            print(f"Network error: {e.message}")
            print(f"Details: {e.details}")
            # Check network connectivity

asyncio.run(main())
```

## Generic Retry Helper

A reusable retry decorator for SDK operations:

```python
import asyncio
from typing import TypeVar, Callable, Awaitable
from aegis_sdk import (
    RateLimitError,
    ServiceError,
    ConnectionError,
    TimeoutError,
    AgenticOSError,
)

T = TypeVar("T")

async def retry_sdk_call(
    func: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """Retry an SDK call with exponential backoff.

    Retries on rate limits, server errors, and transient network errors.
    Non-retryable errors (auth, validation, not found) are raised immediately.
    """
    last_error: AgenticOSError | None = None

    for attempt in range(max_retries):
        try:
            return await func()

        except RateLimitError as e:
            last_error = e
            wait: float = float(e.retry_after)
            print(f"Rate limited, waiting {wait}s...")
            await asyncio.sleep(wait)

        except (ServiceError, ConnectionError, TimeoutError) as e:
            last_error = e
            if attempt < max_retries - 1:
                delay: float = base_delay * (2 ** attempt)
                print(f"Retryable error, waiting {delay}s: {e.message}")
                await asyncio.sleep(delay)
            else:
                raise

    if last_error:
        raise last_error
    raise AgenticOSError("Unknown error after retries")
```

Usage:

```python
from aegis_sdk import AgenticOSClient, Agent

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        agent: Agent = await retry_sdk_call(
            lambda: client.agents.get("agent_abc123"),
            max_retries=3,
        )
        print(f"Agent: {agent.name}")
```

## Built-in Retry Behavior

The SDK's HTTP client automatically retries on transient errors (timeouts, network errors) with exponential backoff. Configure via `ClientConfig`:

| Setting | Default | Description |
|---------|---------|-------------|
| `max_retries` | `3` | Maximum retry attempts |
| `retry_backoff` | `1.5` | Backoff multiplier (delay = backoff^attempt) |
| `timeout` | `30.0` | Request timeout in seconds |

```python
from aegis_sdk import AgenticOSClient

client = AgenticOSClient(
    api_key="sk_live_...",
    max_retries=5,
    timeout=60.0,
)
```

Note: The built-in retry applies to `TimeoutError`, `ConnectionError`, and network-level errors. HTTP-level errors (4xx, 5xx) are not automatically retried. Use the retry helper above for those.

## Related

- [Configuration](configuration.md) -- Timeout and retry settings
- [Streaming](streaming.md) -- Error handling during SSE streams
- [Trust Module](modules/trust.md) -- Trust verification and violations
