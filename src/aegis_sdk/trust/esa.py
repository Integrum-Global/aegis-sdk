"""
Aegis SDK Enterprise Security Authority (ESA) Module.

Configuration for the external security authority an organization federates
its trust decisions with, plus a connectivity probe against it.

Operations:
- get_config(): read the organization's ESA configuration
- update_config(): write it
- test_connection(): probe the configured ESA endpoint
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ESAConfig(BaseModel):
    """ESA configuration for an organization.

    Warning:
        ``api_key`` is MASKED on read (for example ``abc****wxyz``, or
        ``****`` for a short key) and is ``None`` when no key is stored. The
        write route stores whatever it is given, so a read-modify-write round
        trip PERSISTS THE MASK AS THE KEY and destroys the real credential.
        Never feed a value returned by :meth:`ESAModule.get_config` back into
        :meth:`ESAModule.update_config`; supply the real key each time you
        write, or use :meth:`ESAModule.update_config` with a key you hold
        independently.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    enabled: bool = False
    url: str | None = None
    api_key: str | None = None
    sync_interval_minutes: int = 60


class ESAConnectionTest(BaseModel):
    """Result of an ESA connectivity probe.

    The probe never raises for a reachability problem: a refused connection, a
    timeout, a disallowed URL and a non-200 response all come back as
    ``success=False`` with a human-readable ``message``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool
    message: str | None = None


class ESAModule:
    """
    Enterprise Security Authority configuration.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     result = await client.trust.esa.test_connection()
        ...     if not result.success:
        ...         print("ESA unreachable:", result.message)
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def get_config(self) -> ESAConfig:
        """
        Get the organization's ESA configuration.

        Returns:
            The configuration, with ``api_key`` masked. A caller with no
            organization context, or an organization with no ESA settings,
            gets a default-valued config rather than an error -- so an
            ``enabled=False`` result does not distinguish "disabled" from
            "never configured".
        """
        response = await self._http.request(
            "GET",
            "/api/v1/trust/esa/config",
        )
        return ESAConfig(**response)

    async def update_config(
        self,
        enabled: bool,
        url: str | None = None,
        api_key: str | None = None,
        sync_interval_minutes: int = 60,
    ) -> ESAConfig:
        """
        Replace the organization's ESA configuration.

        Args:
            enabled: Whether ESA federation is active
            url: ESA base URL
            api_key: ESA API key. Pass the REAL key -- see the warning on
                :class:`ESAConfig`; passing a masked value read back from
                :meth:`get_config` overwrites the stored credential with the
                mask.
            sync_interval_minutes: Sync cadence in minutes

        Returns:
            The configuration as written. This echoes the request, so the
            ``api_key`` it carries is the one you sent, unmasked.

        Note:
            This is a full replacement, not a partial update: every field is
            written, and omitting one writes its default.
        """
        body = {
            "enabled": enabled,
            "url": url,
            "api_key": api_key,
            "sync_interval_minutes": sync_interval_minutes,
        }
        response = await self._http.request(
            "PUT",
            "/api/v1/trust/esa/config",
            json_data=body,
        )
        return ESAConfig(**response)

    async def test_connection(self) -> ESAConnectionTest:
        """
        Probe the configured ESA endpoint.

        Returns:
            The probe result. ``success=False`` covers every failure mode --
            no organization context, ESA not enabled, no URL configured, a URL
            rejected by outbound-request validation, a connection error, a
            timeout, or a non-200 response -- distinguished only by
            ``message``.

        Note:
            The probe uses the STORED configuration; it does not accept a
            candidate URL or key, so it cannot be used to validate settings
            before saving them.
        """
        response = await self._http.request(
            "POST",
            "/api/v1/trust/esa/test-connection",
        )
        return ESAConnectionTest(**response)
