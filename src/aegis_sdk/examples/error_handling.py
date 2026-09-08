"""
Error Handling Example

Demonstrates: retry patterns, rate limit handling, trust violation recovery,
and graceful error handling for all SDK exception types.

Prerequisites:
    # NOT on PyPI -- `pip install aegis-sdk` installs an unrelated
    # third-party package. Install from source (see docs/quickstart.md):
    pip install -e .
    export AGENTIC_OS_BASE_URL=https://your-deployment.example.com   # REQUIRED, no default
    export AGENTIC_OS_API_KEY=sk_live_your_key_here
    export AGENTIC_OS_MODEL=<your model id>                          # examples never hardcode one
    export AGENTIC_OS_WORKSPACE_ID=<your workspace id>               # agents.create() requires it
"""

import asyncio
import os
from collections.abc import Awaitable, Callable

from aegis_sdk import (
    Agent,
    AgenticOSClient,
    AgenticOSError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    GovernanceViolationError,
    NotFoundError,
    PaymentError,
    RateLimitError,
    ServiceError,
    TimeoutError,
    TrustViolationError,
    ValidationError,
)

# ============================================================================
# Retry Helper
# ============================================================================


async def retry_with_backoff[T](
    func: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    operation_name: str = "operation",
) -> T:
    """Retry an SDK call with exponential backoff.

    Handles:
    - RateLimitError: waits for the server-specified retry_after period
    - ServiceError: retries with exponential backoff (transient server issues)
    - ConnectionError/TimeoutError: retries with backoff (network issues)

    Does NOT retry:
    - AuthenticationError: invalid credentials (fix and retry manually)
    - AuthorizationError: insufficient permissions
    - ValidationError: bad request data
    - NotFoundError: resource doesn't exist
    - TrustViolationError: EATP constraint violation
    - GovernanceViolationError: governance policy block
    """
    last_error: AgenticOSError | None = None

    for attempt in range(max_retries):
        try:
            return await func()

        except RateLimitError as e:
            last_error = e
            wait_time: float = float(e.retry_after)
            print(
                f"[{operation_name}] Rate limited (attempt {attempt + 1}/{max_retries}). "
                f"Waiting {wait_time}s..."
            )
            await asyncio.sleep(wait_time)

        except ServiceError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay: float = base_delay * (2**attempt)
                print(
                    f"[{operation_name}] Server error (attempt {attempt + 1}/{max_retries}): "
                    f"{e.message}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                print(f"[{operation_name}] Server error after {max_retries} attempts: {e.message}")
                raise

        except (ConnectionError, TimeoutError) as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                print(
                    f"[{operation_name}] Network error (attempt {attempt + 1}/{max_retries}): "
                    f"{e.message}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                print(f"[{operation_name}] Network error after {max_retries} attempts: {e.message}")
                raise

    if last_error:
        raise last_error
    raise AgenticOSError(f"Unknown error after {max_retries} retries")


# ============================================================================
# Comprehensive Error Handling
# ============================================================================


async def handle_all_error_types(client: AgenticOSClient) -> None:
    """Demonstrate handling each SDK exception type."""
    print("=== Comprehensive Error Handling ===\n")

    # --- Authentication Error (401) ---
    try:
        bad_client = AgenticOSClient(
            base_url="https://aegis.example.com",
            api_key="sk_live_invalid_key",
        )
        await bad_client.agents.list()
    except AuthenticationError as e:
        print(f"[AUTH] {e.message}")
        print("  Action: Check API key or re-authenticate")
        # Optionally refresh the token:
        # new_token = await client.auth.refresh_token(refresh_token)
        # client.set_auth_token(new_token.access_token)
    finally:
        await bad_client.close()

    # --- Authorization Error (403) ---
    try:
        await client.agents.delete("agent_protected")
    except AuthorizationError as e:
        print(f"\n[AUTHZ] {e.message}")
        print("  Action: Request elevated permissions or use admin account")
    except NotFoundError:
        pass  # Agent might not exist, which is fine for this demo

    # --- Not Found Error (404) ---
    try:
        await client.agents.get("agent_nonexistent_xyz")
    except NotFoundError as e:
        print(f"\n[404] {e.message}")
        print("  Action: Verify resource ID or create the resource first")

    # --- Validation Error (400/422) ---
    try:
        # model_id / workspace_id are supplied deliberately: agents.create()
        # pre-flights BOTH and raises client-side before any request goes out,
        # so omitting them would demonstrate that pre-flight instead of the
        # server-side 400/422 this block is about.
        await client.agents.create(
            name="",  # Empty name will fail validation
            agent_type="invalid_type",
            workspace_id=os.environ["AGENTIC_OS_WORKSPACE_ID"],
            model_id=os.environ["AGENTIC_OS_MODEL"],
        )
    except ValidationError as e:
        print(f"\n[VALIDATION] {e.message}")
        print(f"  Details: {e.details}")
        print("  Action: Fix the request payload")

    # --- Rate Limit Error (429) ---
    # Simulated -- in practice, hit the API rapidly to trigger
    print("\n[RATE LIMIT] Handled via retry_with_backoff (see retry helper)")

    # --- Trust Violation Error (451) ---
    try:
        await client.trust.chains.verify(
            agent_id="agent_restricted",
            action="delete",
            resource="production_database",
        )
    except TrustViolationError as e:
        print(f"\n[TRUST] {e.message}")
        print("  Action: Verify trust chain capabilities and constraints")
    except (NotFoundError, AgenticOSError):
        print("\n[TRUST] Would be raised for EATP constraint violations (HTTP 451)")

    # --- Governance Violation Error (423) ---
    try:
        # Operations that exceed governance policies
        await client.agents.execute(
            "agent_abc123",
            message="Deploy to production without approval",
        )
    except GovernanceViolationError as e:
        print(f"\n[GOVERNANCE] {e.message}")
        print("  Action: Obtain required approvals or adjust governance policies")
    except (NotFoundError, AgenticOSError):
        print("\n[GOVERNANCE] Would be raised for policy violations (HTTP 423)")

    # --- Payment Error ---
    try:
        await client.revenue.subscriptions.subscribe(
            plan_id="enterprise",
            billing_cycle="monthly",
            payment_method_id="pm_invalid",
        )
    except PaymentError as e:
        print(f"\n[PAYMENT] {e.message}")
        if e.decline_code:
            print(f"  Decline code: {e.decline_code}")
        print("  Action: Update payment method")
    except AgenticOSError:
        print("\n[PAYMENT] Would be raised for payment failures")


# ============================================================================
# Rate Limit Handling with Batch Operations
# ============================================================================


async def batch_with_rate_limiting(client: AgenticOSClient) -> None:
    """Execute batch operations with rate limit awareness."""
    print("\n=== Batch Operations with Rate Limiting ===\n")

    agent_names = [
        "Researcher Alpha",
        "Researcher Beta",
        "Researcher Gamma",
        "Analyst Alpha",
        "Analyst Beta",
    ]

    created_agents: list[Agent] = []

    for name in agent_names:
        def _create(n: str = name) -> Awaitable[Agent]:
            return client.agents.create(
                name=n,
                agent_type="chat",
                workspace_id=os.environ["AGENTIC_OS_WORKSPACE_ID"],
                model_id=os.environ["AGENTIC_OS_MODEL"],
            )

        agent: Agent = await retry_with_backoff(
            _create,
            max_retries=5,
            operation_name=f"create_{name}",
        )
        created_agents.append(agent)
        print(f"Created: {agent.name} ({agent.id})")

    print(f"\nTotal created: {len(created_agents)}")

    # Clean up
    for agent in created_agents:
        try:
            await client.agents.delete(agent.id)
            print(f"Deleted: {agent.name}")
        except (NotFoundError, AgenticOSError) as e:
            print(f"Failed to delete {agent.name}: {e.message}")


# ============================================================================
# Token Refresh Pattern
# ============================================================================


async def with_token_refresh(client: AgenticOSClient) -> None:
    """Demonstrate automatic token refresh on authentication failure."""
    print("\n=== Token Refresh Pattern ===\n")

    refresh_token: str | None = None

    async def authenticated_call() -> None:
        """Make an API call with automatic token refresh."""
        try:
            agents = await client.agents.list(page_size=5)
            print(f"Agents: {agents.total}")
        except AuthenticationError:
            if refresh_token:
                print("Token expired, refreshing...")
                new_token = await client.auth.refresh_token(refresh_token)
                client.set_auth_token(new_token.access_token)
                # Retry the call
                agents = await client.agents.list(page_size=5)
                print(f"Agents (after refresh): {agents.total}")
            else:
                print("No refresh token available, re-authentication required")
                raise

    await authenticated_call()


# ============================================================================
# Graceful Degradation
# ============================================================================


async def graceful_degradation(client: AgenticOSClient) -> None:
    """Demonstrate graceful handling when services are unavailable."""
    print("\n=== Graceful Degradation ===\n")

    # Try primary operation, fall back to cached/default data
    try:
        agent = await client.agents.get("agent_primary")
        print(f"Primary agent: {agent.name}")
    except NotFoundError:
        print("Primary agent not found, listing available agents...")
        result = await client.agents.list(status="active", page_size=1)
        if result.items:
            agent = result.items[0]
            print(f"Falling back to: {agent.name}")
        else:
            print("No active agents available")
            return
    except (ConnectionError, TimeoutError) as e:
        print(f"Cannot reach API: {e.message}")
        print("Operating in offline mode...")
        return
    except ServiceError as e:
        print(f"Backend error: {e.message}")
        print("Will retry later...")
        return

    # Try streaming, fall back to polling
    try:
        async for event in client.agents.stream(
            agent.id,
            message="Quick test",
        ):
            print(f"Event: {event.get('event_type')}")
            break  # Just test the first event
    except (ConnectionError, TimeoutError):
        print("Streaming unavailable, falling back to polling...")
        # `execute` is synchronous -- it returns a finished execution or
        # raises. There is no `wait` flag and nothing to poll.
        execution = await client.agents.execute(
            agent.id,
            message="Quick test",
        )
        print(f"Polled result: {execution.status}")


# ============================================================================
# Main
# ============================================================================


async def main() -> None:
    """Run all error handling examples."""
    try:
        async with AgenticOSClient.from_env() as client:
            await handle_all_error_types(client)
            # await batch_with_rate_limiting(client)
            # await with_token_refresh(client)
            # await graceful_degradation(client)

    except ConfigurationError as e:
        print(f"\nConfiguration error: {e.message}")
        print("Make sure AGENTIC_OS_API_KEY environment variable is set")

    except AgenticOSError as e:
        print(f"\nUnhandled SDK error: {e.message}")
        if e.details:
            print(f"Details: {e.details}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
