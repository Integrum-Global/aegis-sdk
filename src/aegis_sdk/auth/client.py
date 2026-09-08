"""
Agentic OS SDK Authentication Client.

Provides authentication operations for the SDK.
"""

import warnings
from typing import TYPE_CHECKING

from .._http import encode_path_param
from ..exceptions import AgenticOSError
from .models import APIKey, APIKeyCreate, AuthToken, User

if TYPE_CHECKING:
    from .._http import HTTPClient


class AuthModule:
    """
    Authentication operations.

    Provides methods for:
    - Email/password authentication
    - Token management
    - User registration
    - API key management

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     user = await client.auth.get_current_user()
        ...     print(f"Logged in as: {user.email}")
    """

    def __init__(self, http_client: "HTTPClient"):
        """
        Initialize auth module.

        Args:
            http_client: Internal HTTP client instance
        """
        self._http = http_client

    async def login(self, email: str, password: str) -> AuthToken:
        """
        Login with email and password.

        Args:
            email: User email address
            password: User password

        Returns:
            AuthToken with ``access_token`` / ``refresh_token`` (top-level,
            for backward compatibility) AND the authenticated ``.user``
            (:class:`User`) parsed from the same response -- no second
            round-trip to :meth:`get_current_user` needed.

        Raises:
            AuthenticationError: If credentials are invalid
            ValidationError: If email/password format is invalid

        Example:
            >>> token = await client.auth.login("user@example.com", "password123")
            >>> print(f"Access token: {token.access_token}")
            >>> print(f"Logged in as: {token.user.name} ({token.user.email})")
        """
        response = await self._http.request(
            "POST",
            "/api/v1/auth/login",
            json_data={"email": email, "password": password},
        )
        return self._parse_auth_envelope(response)

    async def logout(self) -> None:
        """
        Logout current session.

        Invalidates the current access token on the server.

        Raises:
            AuthenticationError: If not authenticated
        """
        await self._http.request("POST", "/api/v1/auth/logout")

    async def refresh_token(self, refresh_token: str | None = None) -> AuthToken:
        """
        Refresh access token.

        Args:
            refresh_token: Refresh token (optional if stored in cookies)

        Returns:
            New AuthToken with fresh access_token

        Raises:
            AuthenticationError: If refresh token is invalid or expired

        Example:
            >>> new_token = await client.auth.refresh_token(old_token.refresh_token)
            >>> client._http.set_auth_token(new_token.access_token)
        """
        json_data = {}
        if refresh_token:
            json_data["refresh_token"] = refresh_token

        response = await self._http.request(
            "POST",
            "/api/v1/auth/refresh",
            json_data=json_data if json_data else None,
        )
        return AuthToken(**response)

    async def register(
        self,
        email: str,
        password: str,
        name: str | None = None,
        organization_name: str | None = None,
        *,
        full_name: str | None = None,
    ) -> AuthToken:
        """
        Register new user account.

        Args:
            email: User email address
            password: User password -- must meet the server's password
                strength policy
            name: User's display name (matches the server's
                ``RegisterRequest.name`` field; a prior SDK
                release sent ``full_name``, which the server has never
                accepted, so every registration failed with a 422)
            organization_name: Name for the new organization (required by
                the server)
            full_name: Deprecated alias for ``name``. Kept as
                a keyword-only backward-compat shim -- emits a
                ``DeprecationWarning`` and will be removed in a future
                release once the shim has lived through one minor cycle.
                Passing BOTH ``name`` and ``full_name`` with DIFFERENT
                values raises ``ValueError`` ( review M1) --
                silently preferring one over the other would mask a
                caller bug (e.g. a partially-completed migration off
                ``full_name``) rather than surfacing it.

        Returns:
            AuthToken with ``access_token`` / ``refresh_token`` (top-level)
            AND the newly-registered ``.user`` (:class:`User`).

        Raises:
            ValueError: If neither ``name`` nor ``full_name`` is supplied,
                or if both are supplied with conflicting values.
            ValidationError: If registration data is invalid
            AgenticOSError: If email already registered

        Example:
            >>> token = await client.auth.register(
            ...     email="new@example.com",
            ...     password="secure123",
            ...     name="Jane Doe",
            ...     organization_name="Acme Corp"
            ... )
            >>> print(f"Registered: {token.user.name}")
        """
        if full_name is not None:
            if name is not None and name != full_name:
                raise ValueError(
                    f"register() received conflicting values for 'name' ({name!r}) "
                    f"and the deprecated 'full_name' alias ({full_name!r}). Pass "
                    f"only 'name' -- 'full_name' is a deprecated alias, not a "
                    f"separate field."
                )
            warnings.warn(
                "AuthModule.register(full_name=...) is deprecated and will be "
                "removed in a future release; use register(name=...) instead "
                "(the server field is 'name', not 'full_name').",
                DeprecationWarning,
                stacklevel=2,
            )
            if name is None:
                name = full_name
        if name is None:
            raise ValueError("register() requires 'name' (or the deprecated 'full_name' alias)")

        response = await self._http.request(
            "POST",
            "/api/v1/auth/register",
            json_data={
                "email": email,
                "password": password,
                "name": name,
                "organization_name": organization_name,
            },
        )
        return self._parse_auth_envelope(response)

    @staticmethod
    def _parse_auth_envelope(response: dict) -> AuthToken:
        """Parse the server's nested ``{"user": ..., "tokens": ...}`` envelope.

        Mirrors ``LoginResponse`` / ``RegisterResponse`` -- both ``/auth/login`` and
        ``/auth/register`` return this exact shape.: the
        prior SDK called ``AuthToken(**response)`` directly against the
        nested envelope, so ``access_token`` was never populated (it lives
        under ``response["tokens"]``, not at the top level).

        Raises:
            AgenticOSError: If the response is missing ``"tokens"`` and/or
                ``"user"`` -- e.g. an error-shaped body, a proxy/gateway
                error page, or a future server contract change. A bare
                ``KeyError`` here would be an opaque, un-catchable failure
                for SDK callers (this is the same wire-shape-drift class the
 auth cluster fixes, not a new one
                review).
        """
        missing = [key for key in ("tokens", "user") if key not in response]
        if missing:
            raise AgenticOSError(
                "Unexpected auth response shape: expected 'user'+'tokens', "
                f"missing {sorted(missing)}; got keys {sorted(response.keys())}",
                details={"missing_keys": sorted(missing), "response_keys": sorted(response.keys())},
            )
        tokens = response["tokens"]
        user = User(**response["user"])
        return AuthToken(**tokens, user=user)

    async def get_current_user(self) -> User:
        """
        Get current authenticated user.

        Returns:
            User object with profile information

        Raises:
            AuthenticationError: If not authenticated

        Example:
            >>> user = await client.auth.get_current_user()
            >>> print(f"Logged in as: {user.email} ({user.organization_id})")
        """
        response = await self._http.request("GET", "/api/v1/auth/me")
        return User(**response)

    # -------------------------------------------------------------------------
    # API Key Management
    # -------------------------------------------------------------------------

    async def create_api_key(
        self,
        name: str,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> APIKey:
        """
        Create new API key.

        Args:
            name: Descriptive name for the key
            scopes: List of permission scopes (e.g., ["agents:read", "agents:write"])
            expires_in_days: Optional expiration in days

        Returns:
            APIKey with the key_prefix (full key only shown once)

        Raises:
            AuthenticationError: If not authenticated
            AuthorizationError: If not allowed to create API keys

        Example:
            >>> key = await client.auth.create_api_key(
            ...     name="CI/CD Pipeline",
            ...     scopes=["agents:read", "pipelines:write"]
            ... )
            >>> print(f"Key prefix: {key.key_prefix}")
        """
        create_data = APIKeyCreate(
            name=name,
            scopes=scopes or [],
            expires_in_days=expires_in_days,
        )
        response = await self._http.request(
            "POST",
            "/api/v1/api-keys",
            json_data=create_data.model_dump(exclude_none=True),
        )
        return APIKey(**response)

    async def list_api_keys(self) -> list[APIKey]:
        """
        List all API keys for current user.

        Returns:
            List of APIKey objects

        Raises:
            AuthenticationError: If not authenticated

        Example:
            >>> keys = await client.auth.list_api_keys()
            >>> for key in keys:
            ...     print(f"{key.name}: {key.key_prefix}...")
        """
        response = await self._http.request("GET", "/api/v1/api-keys")
        return [APIKey(**key) for key in response]

    async def get_api_key(self, key_id: str) -> APIKey:
        """
        Get specific API key by ID.

        Args:
            key_id: API key ID

        Returns:
            APIKey object

        Raises:
            NotFoundError: If key doesn't exist
            AuthenticationError: If not authenticated
        """
        response = await self._http.request("GET", f"/api/v1/api-keys/{encode_path_param(key_id)}")
        return APIKey(**response)

    async def delete_api_key(self, key_id: str) -> None:
        """
        Delete API key.

        Args:
            key_id: API key ID to delete

        Raises:
            NotFoundError: If key doesn't exist
            AuthenticationError: If not authenticated
            AuthorizationError: If not allowed to delete this key

        Example:
            >>> await client.auth.delete_api_key("key_abc123")
        """
        await self._http.request("DELETE", f"/api/v1/api-keys/{encode_path_param(key_id)}")

    async def revoke_api_key(self, key_id: str) -> None:
        """
        Revoke API key (alias for delete).

        Args:
            key_id: API key ID to revoke
        """
        await self.delete_api_key(key_id)
