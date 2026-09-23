# Configuration

The SDK client is configured via `ClientConfig`, constructor arguments, or environment variables.

## ClientConfig

The `ClientConfig` dataclass holds all client settings:

```python
from aegis_sdk import ClientConfig

config = ClientConfig(
    base_url="https://aegis.example.com",  # API base URL
    api_key="sk_live_your_key_here",            # API key for authentication
    timeout=30.0,                            # Request timeout in seconds
    max_retries=3,                           # Max retry attempts
    retry_backoff=1.5,                       # Exponential backoff multiplier
    verify_ssl=True,                         # SSL certificate verification
    debug=False,                             # Debug logging
)
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | (required) | API base URL |
| `api_key` | `Optional[str]` | `None` | API key for Bearer auth |
| `oauth_config` | `Optional[OAuthConfig]` | `None` | OAuth2 configuration |
| `timeout` | `float` | `30.0` | Request timeout in seconds |
| `max_retries` | `int` | `3` | Maximum retry attempts for transient errors |
| `retry_backoff` | `float` | `1.5` | Backoff multiplier (delay = backoff^attempt) |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates |
| `debug` | `bool` | `False` | Enable debug logging |

## Creating the Client

### Option 1: Constructor Arguments

```python
from aegis_sdk import AgenticOSClient

client = AgenticOSClient(
    base_url="https://aegis.example.com",
    api_key="sk_live_your_key_here",
    timeout=60.0,
    max_retries=5,
    debug=True,
)
```

When using constructor arguments, a `ClientConfig` is built internally with sensible defaults for any omitted values.

### Option 2: Explicit ClientConfig

```python
from aegis_sdk import AgenticOSClient, ClientConfig

config = ClientConfig(
    base_url="https://custom.aegis.example.com",
    api_key="sk_live_your_key_here",
    timeout=60.0,
    max_retries=5,
    retry_backoff=2.0,
    verify_ssl=True,
    debug=False,
)

client = AgenticOSClient(config=config)
```

When `config` is provided, it takes precedence over other constructor arguments.

### Option 3: From Environment Variables

```python
from aegis_sdk import AgenticOSClient

client = AgenticOSClient.from_env()
```

This calls `ClientConfig.from_env()` internally.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTIC_OS_BASE_URL` | (required, no default) | API base URL |
| `AGENTIC_OS_API_KEY` | -- | API key for authentication |
| `AGENTIC_OS_TIMEOUT` | `30.0` | Request timeout in seconds |
| `AGENTIC_OS_MAX_RETRIES` | `3` | Maximum retry attempts |
| `AGENTIC_OS_VERIFY_SSL` | `true` | SSL certificate verification (`true`/`false`) |
| `AGENTIC_OS_DEBUG` | `false` | Enable debug logging (`true`/`false`) |

Example `.env` file:

```bash
AGENTIC_OS_BASE_URL=https://aegis.example.com
AGENTIC_OS_API_KEY=sk_live_your_key_here
AGENTIC_OS_TIMEOUT=60
AGENTIC_OS_MAX_RETRIES=5
AGENTIC_OS_VERIFY_SSL=true
AGENTIC_OS_DEBUG=false
```

## Immutable Config Variants

`ClientConfig` provides helper methods to create modified copies without mutating the original:

```python
from aegis_sdk import ClientConfig

config = ClientConfig(
    base_url="https://aegis.example.com",
    api_key="sk_live_key_1",
)

# Create a new config with a different API key
config_user2 = config.with_api_key("sk_live_key_2")

# Create a new config for a different environment
staging_config = config.with_base_url("https://staging.aegis.example.com")
```

## OAuthConfig

For OAuth2 authentication, configure via `OAuthConfig`:

```python
from aegis_sdk.config import OAuthConfig, ClientConfig

oauth = OAuthConfig(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_url="https://auth.aegis.example.com/oauth/token",
    scopes=["agents:read", "agents:write"],
)

config = ClientConfig(
    base_url="https://aegis.example.com",
    oauth_config=oauth,
)
```

### OAuthConfig Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `client_id` | `str` | (required) | OAuth2 client ID |
| `client_secret` | `str` | (required) | OAuth2 client secret |
| `token_url` | `str` | (required) | Token endpoint URL |
| `scopes` | `List[str]` | `[]` | Requested OAuth2 scopes |

## Timeout Configuration

The timeout value controls the maximum duration for a single HTTP request. For long-running operations, increase it:

```python
# Short timeout for fast operations
fast_client = AgenticOSClient(api_key="sk_live_...", timeout=10.0)

# Long timeout for agent execution
exec_client = AgenticOSClient(api_key="sk_live_...", timeout=120.0)
```

Note: Streaming operations (`client.agents.stream()`, `client.sessions.stream_messages()`) use the same timeout for the initial connection. Once connected, the stream stays open until completion or disconnection.

## Retry Configuration

The SDK automatically retries on transient errors (network errors, timeouts) with exponential backoff — **for idempotent verbs only**. `GET`, `HEAD`, `OPTIONS`, `PUT` and `DELETE` are retried; `POST` and `PATCH` are not. Re-sending a non-idempotent request can produce a second effect, and the transport mints no idempotency key, so a `POST` that times out is sent once and raises.

```
Delay = retry_backoff ^ attempt
```

With the default `retry_backoff=1.5`:
- Attempt 0: immediate
- Attempt 1: 1.5s delay
- Attempt 2: 2.25s delay

That schedule applies to the retryable verbs above. To customize:

```python
from aegis_sdk import AgenticOSClient

client = AgenticOSClient(
    api_key="sk_live_...",
    max_retries=5,       # Up to 5 attempts, retryable verbs only
    timeout=60.0,        # 60s per attempt
)
```

Retryable errors: `TimeoutError`, `ConnectionError`, network-level failures — raised on an idempotent verb, where a repeat cannot double-apply.

Non-retryable errors (raised immediately): `AuthenticationError`, `AuthorizationError`, `NotFoundError`, `ValidationError`, `RateLimitError`, `GovernanceViolationError`, `TrustViolationError`.

## Debug Logging

Enable debug mode to log all HTTP requests and responses:

```python
client = AgenticOSClient(api_key="sk_live_...", debug=True)
```

Debug mode logs:
- Request method and URL
- Request body (JSON)
- Response status codes
- Retry attempts and delays
- Malformed SSE data warnings

Logs are written via Python's standard `logging` module under the `aegis_sdk._http` logger:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## SSL Configuration

SSL verification is enabled by default. Disable it only for local development:

```python
# Local development with self-signed certs
client = AgenticOSClient(
    base_url="https://localhost:8000",
    api_key="sk_live_...",
    config=ClientConfig(
        base_url="https://localhost:8000",
        api_key="sk_live_...",
        verify_ssl=False,
    ),
)
```

**Warning**: Never disable SSL verification in production.

## Updating Credentials at Runtime

Change the API key or auth token after client creation:

```python
from aegis_sdk import AgenticOSClient

async def main() -> None:
    client = AgenticOSClient(base_url="https://aegis.example.com")

    # Login and set token
    token = await client.auth.login("user@example.com", "password")
    client.set_auth_token(token.access_token)  # or client.set_api_key(...)

    # Use the client
    agents = await client.agents.list()
    print(f"Found {agents.total} agents")

    await client.close()
```

Both `set_api_key()` and `set_auth_token()` update the Bearer token in the HTTP Authorization header.

## Client Lifecycle

Always close the client when done to release HTTP connections:

```python
# Option 1: Async context manager (recommended)
async with AgenticOSClient.from_env() as client:
    ...

# Option 2: Manual close
client = AgenticOSClient.from_env()
try:
    ...
finally:
    await client.close()
```

## Convenience Alias

`Client` is an alias for `AgenticOSClient`:

```python
from aegis_sdk import Client

async with Client(api_key="sk_live_...") as client:
    ...
```

## Related

- [Authentication](authentication.md) -- Authentication methods and token management
- [Error Handling](error-handling.md) -- Exception types and retry strategies
- [Quick Start](quickstart.md) -- Getting started guide
