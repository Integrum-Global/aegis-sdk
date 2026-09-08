# Authentication

The Aegis SDK supports multiple authentication methods: API keys, email/password login, and OAuth2.

## API Key Authentication (Recommended)

API keys are the recommended authentication method for scripts, CI/CD pipelines, and server-to-server communication.

### Direct API Key

```python
from aegis_sdk import AgenticOSClient

client = AgenticOSClient(api_key="sk_live_your_key_here")
```

### From Environment Variables

```bash
export AGENTIC_OS_API_KEY=sk_live_your_key_here
```

```python
from aegis_sdk import AgenticOSClient

client = AgenticOSClient.from_env()
```

The SDK reads the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTIC_OS_API_KEY` | -- | API key |
| `AGENTIC_OS_BASE_URL` | (required, no default) | API base URL |
| `AGENTIC_OS_TIMEOUT` | `30.0` | Request timeout (seconds) |
| `AGENTIC_OS_MAX_RETRIES` | `3` | Max retry attempts |
| `AGENTIC_OS_VERIFY_SSL` | `true` | SSL verification |
| `AGENTIC_OS_DEBUG` | `false` | Debug logging |

### API Key Management

Create, list, and revoke API keys programmatically:

```python
import asyncio
from aegis_sdk import AgenticOSClient, APIKey
from typing import List

async def manage_keys() -> None:
    async with AgenticOSClient(api_key="sk_live_admin_key") as client:
        # Create a scoped API key
        key: APIKey = await client.auth.create_api_key(
            name="CI/CD Pipeline",
            scopes=["agents:read", "agents:write", "pipelines:write"],
            expires_in_days=90,
        )
        print(f"Created key: {key.key_prefix}... (ID: {key.id})")

        # List all API keys
        keys: List[APIKey] = await client.auth.list_api_keys()
        for k in keys:
            print(f"  {k.name}: {k.key_prefix}... (created: {k.created_at})")

        # Get a specific key
        key_detail: APIKey = await client.auth.get_api_key(key.id)
        print(f"Scopes: {key_detail.scopes}")

        # Revoke a key
        await client.auth.revoke_api_key(key.id)
        print(f"Revoked key: {key.id}")

asyncio.run(manage_keys())
```

## Email/Password Authentication

For interactive applications or initial setup:

```python
import asyncio
from aegis_sdk import AgenticOSClient, AuthToken, AuthenticationError

async def login_flow() -> None:
    async with AgenticOSClient(base_url="https://aegis.example.com") as client:
        try:
            # Login
            token: AuthToken = await client.auth.login(
                email="user@example.com",
                password="your_password",
            )
            print(f"Access token: {token.access_token[:20]}...")
            print(f"Token type: {token.token_type}")
            print(f"Expires in: {token.expires_in}s")

            # login() already parsed the authenticated user from the same
            # response -- no second round-trip needed:
            print(f"Logged in as: {token.user.name} ({token.user.email})")
            print(f"Organization: {token.user.organization_id}")

            # Set the token on the client for subsequent requests
            client.set_auth_token(token.access_token)

            # (Equivalent, if you prefer a fresh fetch)
            user = await client.auth.get_current_user()
            print(f"Logged in as: {user.name} ({user.email})")
            print(f"Organization: {user.organization_id}")

        except AuthenticationError as e:
            print(f"Login failed: {e.message}")

asyncio.run(login_flow())
```

## User Registration

Create a new user account:

```python
import asyncio
from aegis_sdk import AgenticOSClient, AuthToken

async def register() -> None:
    async with AgenticOSClient(base_url="https://aegis.example.com") as client:
        token: AuthToken = await client.auth.register(
            email="newuser@example.com",
            password="secure_password_123",
            name="Jane Doe",
            organization_name="Acme Corp",
        )
        client.set_auth_token(token.access_token)
        print(f"Registration successful! Welcome, {token.user.name}.")

asyncio.run(register())
```

## Token Refresh

Access tokens expire after a set duration (default: 900 seconds / 15 minutes --
`jwt_access_token_expire_minutes`, confirmed live:
`POST /auth/login` returns `expires_in: 900`. ). Use the refresh token to
obtain a new access token:

```python
import asyncio
from aegis_sdk import AgenticOSClient, AuthToken, AuthenticationError

async def refresh_flow() -> None:
    async with AgenticOSClient(base_url="https://aegis.example.com") as client:
        # Initial login
        token: AuthToken = await client.auth.login("user@example.com", "password")
        client.set_auth_token(token.access_token)

        # Later, when token expires...
        try:
            user = await client.auth.get_current_user()
        except AuthenticationError:
            # Token expired, refresh it
            new_token: AuthToken = await client.auth.refresh_token(
                refresh_token=token.refresh_token,
            )
            client.set_auth_token(new_token.access_token)
            print(f"Token refreshed, new expiry: {new_token.expires_in}s")

asyncio.run(refresh_flow())
```

## Token Refresh Wrapper

For long-running applications, wrap API calls with automatic token refresh:

```python
import asyncio
from aegis_sdk import AgenticOSClient, AuthToken, AuthenticationError

class AutoRefreshClient:
    """Wrapper that automatically refreshes expired tokens."""

    def __init__(self, client: AgenticOSClient, refresh_token: str) -> None:
        self.client = client
        self._refresh_token = refresh_token

    async def ensure_authenticated(self) -> None:
        """Refresh the token if it has expired."""
        try:
            await self.client.auth.get_current_user()
        except AuthenticationError:
            new_token: AuthToken = await self.client.auth.refresh_token(
                refresh_token=self._refresh_token,
            )
            self.client.set_auth_token(new_token.access_token)
            self._refresh_token = new_token.refresh_token or self._refresh_token

async def main() -> None:
    async with AgenticOSClient(base_url="https://aegis.example.com") as client:
        token = await client.auth.login("user@example.com", "password")
        client.set_auth_token(token.access_token)

        wrapper = AutoRefreshClient(client, token.refresh_token or "")

        # Use wrapper before sensitive operations
        await wrapper.ensure_authenticated()
        agents = await client.agents.list()
        print(f"Found {agents.total} agents")

asyncio.run(main())
```

## Logout

Invalidate the current session:

```python
async with AgenticOSClient(api_key="sk_live_...") as client:
    await client.auth.logout()
    # Token is now invalid on the server
```

## OAuth2 Configuration

For OAuth2 authentication flows, configure via `OAuthConfig`:

```python
from aegis_sdk import AgenticOSClient, ClientConfig
from aegis_sdk.config import OAuthConfig

oauth = OAuthConfig(
    client_id="your_client_id",
    client_secret="your_client_secret",
    token_url="https://auth.agentic-os.com/oauth/token",
    scopes=["agents:read", "agents:write"],
)

config = ClientConfig(
    base_url="https://aegis.example.com",
    oauth_config=oauth,
)

client = AgenticOSClient(config=config)
```

## Security Best Practices

1. **Never hardcode API keys** in source code. Use environment variables or a secrets manager.
2. **Use scoped API keys** with minimal permissions for each use case.
3. **Set key expiration** using `expires_in_days` for temporary access.
4. **Rotate keys regularly** and revoke unused keys.
5. **Use HTTPS** in production (SSL verification is enabled by default).
6. **Store refresh tokens securely** -- they grant long-lived access.

## Related

- [Configuration](configuration.md) -- Full client configuration options
- [Error Handling](error-handling.md) -- Handling `AuthenticationError` and `AuthorizationError`
- [Quick Start](quickstart.md) -- Getting started guide
