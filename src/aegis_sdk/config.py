"""
Aegis SDK Configuration.

Provides configuration dataclasses for the SDK client.
Supports loading from environment variables for convenience.
"""

import logging
import os
import warnings
from dataclasses import dataclass, field
from typing import overload

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# --- Environment variable naming -------------------------------------------
#
# ``AEGIS_`` is the supported prefix: it matches the environment an Aegis
# deployment already defines, so one set of variables configures both the
# product and this SDK.
#
# ``AGENTIC_OS_`` is the prefix the SDK originally shipped with. It is still
# read -- this is a published package with external consumers, so the old
# names are DEPRECATED, not removed -- and reading one emits a one-time
# deprecation warning naming its replacement.
#
# When both names are set, the ``AEGIS_`` value wins.
#
# Every name is SPELLED OUT here rather than composed from a prefix at call
# time. Composing ``f"{prefix}{suffix}"`` works at runtime but makes the
# variable invisible to every literal-string tool -- grep, the repository's
# documented-vs-read drift guard, an operator searching the source for the
# variable their runbook names. A variable that is read but unsearchable is
# how a documented setting silently stops being discoverable, so the table
# below is the SDK's declared environment surface.
ENV_NAMES: dict[str, tuple[str, str]] = {
    # suffix         (supported name,       deprecated name)
    "BASE_URL": ("AEGIS_BASE_URL", "AGENTIC_OS_BASE_URL"),
    "API_KEY": ("AEGIS_API_KEY", "AGENTIC_OS_API_KEY"),
    "TIMEOUT": ("AEGIS_TIMEOUT", "AGENTIC_OS_TIMEOUT"),
    "MAX_RETRIES": ("AEGIS_MAX_RETRIES", "AGENTIC_OS_MAX_RETRIES"),
    "VERIFY_SSL": ("AEGIS_VERIFY_SSL", "AGENTIC_OS_VERIFY_SSL"),
    "DEBUG": ("AEGIS_DEBUG", "AGENTIC_OS_DEBUG"),
}

# Legacy variable names already warned about in this process. A client that
# builds config in a loop should hear about each name once, not once per read.
_warned_legacy_env: set[str] = set()


def env_names(suffix: str) -> tuple[str, str]:
    """Return ``(supported_name, legacy_name)`` for a setting suffix.

    Raises:
        KeyError: If the suffix is not a declared setting. Failing loudly
            beats composing a name for a variable nobody ever sets, which
            would read as "unconfigured" forever.
    """
    try:
        return ENV_NAMES[suffix]
    except KeyError:
        raise KeyError(
            f"{suffix!r} is not a declared SDK environment setting; "
            f"expected one of {sorted(ENV_NAMES)}"
        ) from None


@overload
def _resolve_env(suffix: str) -> str | None: ...


@overload
def _resolve_env(suffix: str, default: str) -> str: ...


def _resolve_env(suffix: str, default: str | None = None) -> str | None:
    """
    Read one setting from the environment, preferring the ``AEGIS_`` name.

    Args:
        suffix: The setting suffix, e.g. ``"BASE_URL"``.
        default: Returned when neither name is set.

    Returns:
        The ``AEGIS_<suffix>`` value if set; otherwise the deprecated
        ``AGENTIC_OS_<suffix>`` value if set (emitting a one-time
        deprecation warning); otherwise ``default``.
    """
    name, legacy_name = env_names(suffix)

    value = os.environ.get(name)
    if value is not None:
        return value

    legacy_value = os.environ.get(legacy_name)
    if legacy_value is not None:
        _warn_legacy_env_name(legacy_name, name)
        return legacy_value

    return default


def _warn_legacy_env_name(legacy_name: str, name: str) -> None:
    """Announce a deprecated variable name once per process.

    Emits BOTH a ``DeprecationWarning`` and a log record, deliberately.
    Python's default warning filters DROP a ``DeprecationWarning`` raised
    inside a library module, so the warning alone would be silent for
    exactly the operators this notice is written for; the log line is what
    they actually see. The warning is what ``-W error::DeprecationWarning``
    and test suites can act on.
    """
    if legacy_name in _warned_legacy_env:
        return
    _warned_legacy_env.add(legacy_name)

    message = (
        f"{legacy_name} is deprecated and will be removed in a future release; "
        f"use {name} instead. {legacy_name} is still read for now, and {name} "
        "takes precedence when both are set."
    )
    warnings.warn(message, DeprecationWarning, stacklevel=3)
    logger.warning(message)


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
            AEGIS_BASE_URL: API base URL -- REQUIRED, no default. The
                SDK targets a specific Aegis deployment; a hardcoded
                fallback host would silently point production traffic at a
                dead/placeholder endpoint, so a missing value
                raises :class:`~aegis_sdk.exceptions.ConfigurationError`
                instead.
            AEGIS_API_KEY: API key for authentication
            AEGIS_TIMEOUT: Request timeout in seconds (default: 30.0)
            AEGIS_MAX_RETRIES: Max retry attempts (default: 3)
            AEGIS_VERIFY_SSL: Verify SSL (default: true)
            AEGIS_DEBUG: Enable debug mode (default: false)

        Deprecated Environment Variables:
            The ``AGENTIC_OS_`` prefix is the SDK's original naming and is
            still read for every variable above, so existing deployments
            keep working. Each one emits a one-time ``DeprecationWarning``
            naming its ``AEGIS_`` replacement. When both names are set, the
            ``AEGIS_`` value wins.

        Returns:
            ClientConfig instance populated from environment

        Raises:
            ConfigurationError: If neither ``AEGIS_BASE_URL`` nor the
                deprecated ``AGENTIC_OS_BASE_URL`` is set.

        Example:
            >>> import os
            >>> os.environ["AEGIS_BASE_URL"] = "https://your-aegis-instance.example.com"
            >>> config = ClientConfig.from_env()
            >>> client = AgenticOSClient(config=config)
        """
        base_url = _resolve_env("BASE_URL")
        if not base_url:
            raise ConfigurationError(
                "AEGIS_BASE_URL environment variable is not set. The SDK "
                "requires an explicit API base URL for your Aegis deployment "
                "-- set AEGIS_BASE_URL (e.g. "
                "'https://your-aegis-instance.example.com') or pass "
                "base_url=... to ClientConfig / AgenticOSClient directly. "
                "(The former name AGENTIC_OS_BASE_URL is still read, and is "
                "deprecated.)"
            )
        return cls(
            base_url=base_url,
            api_key=_resolve_env("API_KEY"),
            timeout=float(_resolve_env("TIMEOUT", "30.0")),
            max_retries=int(_resolve_env("MAX_RETRIES", "3")),
            verify_ssl=_resolve_env("VERIFY_SSL", "true").lower() == "true",
            debug=_resolve_env("DEBUG", "false").lower() == "true",
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
