"""Teams module — typed create/get for the vertical-standup path.

Verified against the server ``teams`` router (mounted at ``/api/v1``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class TeamsModule:
    """Team (working group) management (create + get)."""

    def __init__(self, http_client: HTTPClient) -> None:
        self._http = http_client

    async def create(self, name: str, description: str | None = None) -> dict[str, Any]:
        """Create a team.

        Server: ``POST /api/v1/teams``. ``organization_id`` is
        derived server-side from the caller's tenant.

        Args:
            name: Team name (1-100 chars).
            description: Optional description (<=500 chars).
        """
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        resp: dict[str, Any] = await self._http.request("POST", "/api/v1/teams", json_data=body)
        return resp

    async def get(self, team_id: str) -> dict[str, Any]:
        """Get a team (with members) by ID.

        Server: ``GET /api/v1/teams/{team_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/teams/{encode_path_param(team_id)}"
        )
        return resp
    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List teams in the caller's organization.

        Server: ``GET /api/v1/teams``, gated on ``teams:read``.

        Args:
            limit: Maximum results (1-100, server default 50).
            offset: Pagination offset.

        Returns:
            ``{"records": [...], "total": int}``.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/teams", params=params
        )
        return resp
