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

        Args:
            name: Organization display name (1-100 chars).
            slug: URL slug, lowercase alphanumeric + hyphens (``^[a-z0-9-]+$``).
            plan_tier: One of ``free``, ``pro``, ``enterprise`` (default ``free``).
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
