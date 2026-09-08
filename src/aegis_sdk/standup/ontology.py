"""Ontology module — typed preset/config methods for the vertical-standup path.

Verified against the server ``ontology`` router(mounted at ``/api/v1``)). The server models use ``populate_by_name=True`` so
snake_case field names are accepted alongside the camelCase aliases.
"""

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class OntologyModule:
    """Organization ontology (vocabulary) management."""

    def __init__(self, http_client: "HTTPClient") -> None:
        self._http = http_client

    async def apply_preset(self, organization_id: str, preset_id: str) -> dict[str, Any]:
        """Apply a preset ontology to an organization.

        Server: ``POST /api/v1/ontology/preset/{organization_id}``. Replaces custom terms with the preset defaults.

        Args:
            organization_id: Target organization.
            preset_id: Preset identifier (see :meth:`list_presets`).
        """
        resp: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/ontology/preset/{encode_path_param(organization_id)}",
            json_data={"preset_id": preset_id},
        )
        return resp

    async def update_config(
        self,
        organization_id: str,
        name: str | None = None,
        description: str | None = None,
        base_preset: str | None = None,
        custom_terms: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update the ontology configuration for an organization.

        Server: ``PUT /api/v1/ontology/config/{organization_id}``.
        """
        body: dict[str, Any] = {}
        optional = {
            "name": name,
            "description": description,
            "base_preset": base_preset,
            "custom_terms": custom_terms,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        resp: dict[str, Any] = await self._http.request(
            "PUT",
            f"/api/v1/ontology/config/{encode_path_param(organization_id)}",
            json_data=body,
        )
        return resp

    async def get_config(self, organization_id: str) -> dict[str, Any]:
        """Get the resolved ontology configuration for an organization.

        Server: ``GET /api/v1/ontology/config/{organization_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/ontology/config/{encode_path_param(organization_id)}"
        )
        return resp

    async def list_presets(self) -> dict[str, Any]:
        """List the available ontology presets.

        Server: ``GET /api/v1/ontology/presets``.
        """
        resp: dict[str, Any] = await self._http.request("GET", "/api/v1/ontology/presets")
        return resp
