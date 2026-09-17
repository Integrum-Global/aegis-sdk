"""Organizations module — typed create/get for the vertical-standup path.

Verified against the server ``organizations`` router(mounted at ``/api/v1``)).
"""

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class OrganizationsModule:
    """Organization management (create + get)."""

    def __init__(self, http_client: "HTTPClient") -> None:
        self._http = http_client

    async def create(
        self,
        name: str,
        slug: str,
        plan_tier: str = "free",
    ) -> dict[str, Any]:
        """Create an organization.

        Server: ``POST /api/v1/organizations``.

        For a session (JWT) caller the server also enrolls the creator in the
        new organization and switches their session into it, returning a fresh
        ``access_token`` / ``refresh_token`` / ``token_type`` / ``expires_in``
        in the response. That switch ROTATES the session: the access token
        this request authenticated with, and its refresh partner, are revoked
        immediately. The SDK does not adopt the returned token for you (the
        same contract as ``client.auth.refresh_token``): when
        ``resp["access_token"]`` is not ``None``, call
        ``client.set_auth_token(resp["access_token"])`` before sending further
        requests, or they are rejected with ``401``.

        For an API-key caller, and when the server-side switch could not
        complete, the four token fields are ``None`` and the caller's
        credential is unchanged.

        Args:
            name: Organization display name (1-100 chars).
            slug: URL slug, lowercase alphanumeric + hyphens (``^[a-z0-9-]+$``).
            plan_tier: One of ``free``, ``pro``, ``enterprise`` (default ``free``).

        Example:
            >>> resp = await client.organizations.create(name="Acme", slug="acme")
            >>> if resp.get("access_token"):
            ...     client.set_auth_token(resp["access_token"])

        ⛔ Do not print, log, or serialize the returned token fields.
        """
        resp: dict[str, Any] = await self._http.request(
            "POST",
            "/api/v1/organizations",
            json_data={"name": name, "slug": slug, "plan_tier": plan_tier},
        )
        return resp

    async def get(self, org_id: str) -> dict[str, Any]:
        """Get an organization by ID.

        Server: ``GET /api/v1/organizations/{org_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/organizations/{encode_path_param(org_id)}"
        )
        return resp
