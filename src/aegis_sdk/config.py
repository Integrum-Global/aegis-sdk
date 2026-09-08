"""
Aegis SDK Configuration.

Provides configuration dataclasses for the SDK client.
Supports loading from environment variables for convenience.
"""

import os
from dataclasses import dataclass, field

from .exceptions import ConfigurationError


@dataclass
class OAuthConfig:
    """
    OAuth2 configuration for authentication.

    Attributes:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret
        token_url: URL to obtain tokens
        scopes: Requested OAuth2 scopes
    """

    client_id: str
    client_secret: str
    token_url: str
    scopes: list[str] = field(default_factory=list)


@dataclass
class ClientConfig:
    """
    Configuration for AgenticOSClient.

    Can be created directly or loaded from environment variables
    using the from_env() class method.

    Attributes:
        base_url: Base URL for Agentic OS API
        api_key: API key for authentication (optional if using OAuth)
        oauth_config: OAuth2 configuration (optional if using API key)
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        retry_backoff: Base backoff multiplier for retries
        verify_ssl: Whether to verify SSL certificates
        debug: Enable debug logging
    """

    base_url: str
    api_key: str | None = None
    oauth_config: OAuthConfig | None = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff: float = 1.5
    verify_ssl: bool = True
    debug: bool = False

    @classmethod
    def from_env(cls) -> "ClientConfig":
        """
        Load configuration from environment variables.

        Environment Variables:
            AGENTIC_OS_BASE_URL: API base URL -- REQUIRED, no default. The
                SDK targets a specific Aegis deployment; a hardcoded
                fallback host would silently point production traffic at a
                dead/placeholder endpoint, so a missing value
                raises :class:`~aegis_sdk.exceptions.ConfigurationError`
                instead.
            AGENTIC_OS_API_KEY: API key for authentication
            AGENTIC_OS_TIMEOUT: Request timeout in seconds (default: 30.0)
            AGENTIC_OS_MAX_RETRIES: Max retry attempts (default: 3)
            AGENTIC_OS_VERIFY_SSL: Verify SSL (default: true)
            AGENTIC_OS_DEBUG: Enable debug mode (default: false)

        Returns:
            ClientConfig instance populated from environment

        Raises:
            ConfigurationError: If ``AGENTIC_OS_BASE_URL`` is not set.

        Example:
            >>> import os
            >>> os.environ["AGENTIC_OS_BASE_URL"] = "https://your-aegis-instance.example.com"
            >>> config = ClientConfig.from_env()
            >>> client = AgenticOSClient(config=config)
        """
        base_url = os.environ.get("AGENTIC_OS_BASE_URL")
        if not base_url:
            raise ConfigurationError(
                "AGENTIC_OS_BASE_URL environment variable is not set. The SDK "
                "requires an explicit API base URL for your Aegis deployment "
                "-- set AGENTIC_OS_BASE_URL (e.g. "
                "'https://your-aegis-instance.example.com') or pass "
                "base_url=... to ClientConfig / AgenticOSClient directly."
            )
        return cls(
            base_url=base_url,
            api_key=os.environ.get("AGENTIC_OS_API_KEY"),
            timeout=float(os.environ.get("AGENTIC_OS_TIMEOUT", "30.0")),
            max_retries=int(os.environ.get("AGENTIC_OS_MAX_RETRIES", "3")),
            verify_ssl=os.environ.get("AGENTIC_OS_VERIFY_SSL", "true").lower() == "true",
            debug=os.environ.get("AGENTIC_OS_DEBUG", "false").lower() == "true",
        )

    def with_api_key(self, api_key: str) -> "ClientConfig":
        """
        Create a new config with a different API key.

        Args:
            api_key: New API key to use

        Returns:
            New ClientConfig with updated API key
        """
        return ClientConfig(
            base_url=self.base_url,
            api_key=api_key,
            oauth_config=self.oauth_config,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
            verify_ssl=self.verify_ssl,
            debug=self.debug,
        )

    def with_base_url(self, base_url: str) -> "ClientConfig":
        """
        Create a new config with a different base URL.

        Args:
            base_url: New base URL to use

        Returns:
            New ClientConfig with updated base URL
        """
        return ClientConfig(
            base_url=base_url,
            api_key=self.api_key,
            oauth_config=self.oauth_config,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff=self.retry_backoff,
            verify_ssl=self.verify_ssl,
            debug=self.debug,
        )
