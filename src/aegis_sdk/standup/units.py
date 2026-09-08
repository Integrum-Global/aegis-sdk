"""Organization units module — typed create/get for the vertical-standup path.

Verified against the server ``organization-units`` router(mounted at ``/api/v1``)).
"""

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class OrganizationUnitsModule:
    """Organization unit management (create + get)."""

    def __init__(self, http_client: "HTTPClient") -> None:
        self._http = http_client

    async def create(
        self,
        name: str,
        unit_type: str,
        parent_unit_id: str | None = None,
        code: str | None = None,
        description: str | None = None,
        mission_statement: str | None = None,
        responsibilities: list[str] | None = None,
        budget_allocation: float | None = None,
        budget_currency: str = "USD",
        headcount_limit: int | None = None,
        default_constraint_template_id: str | None = None,
        constraint_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        display_subtype: str | None = None,
        default_classification: str = "public",
    ) -> dict[str, Any]:
        """Create an organization unit (department or team container).

        Server: ``POST /api/v1/organization-units``.
        ``organization_id`` is derived server-side from the caller's tenant.

        Args:
            name: Unit name (1-200 chars).
            unit_type: ``department`` or ``team`` (``^(department|team)$``).
            parent_unit_id: Parent unit ID; ``None`` for the root unit.
            default_classification: One of ``public``, ``restricted``,
                ``confidential``, ``secret``, ``top_secret`` (default ``public``).
        """
        body: dict[str, Any] = {
            "name": name,
            "unit_type": unit_type,
            "budget_currency": budget_currency,
            "default_classification": default_classification,
        }
        optional = {
            "parent_unit_id": parent_unit_id,
            "code": code,
            "description": description,
            "mission_statement": mission_statement,
            "responsibilities": responsibilities,
            "budget_allocation": budget_allocation,
            "headcount_limit": headcount_limit,
            "default_constraint_template_id": default_constraint_template_id,
            "constraint_overrides": constraint_overrides,
            "metadata": metadata,
            "tags": tags,
            "display_subtype": display_subtype,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        resp: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/organization-units", json_data=body
        )
        return resp

    async def get(self, unit_id: str) -> dict[str, Any]:
        """Get an organization unit by ID.

        Server: ``GET /api/v1/organization-units/{unit_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/organization-units/{encode_path_param(unit_id)}"
        )
        return resp
