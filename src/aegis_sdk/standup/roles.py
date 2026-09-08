"""Organization roles module — typed create/get for the vertical-standup path.

Verified against the server ``organization-roles`` router(mounted at ``/api/v1``)).
"""

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class OrganizationRolesModule:
    """Organization role (accountability anchor) management (create + get)."""

    def __init__(self, http_client: "HTTPClient") -> None:
        self._http = http_client

    async def create(
        self,
        organization_unit_id: str,
        title: str,
        description: str | None = None,
        job_description: str | None = None,
        responsibilities: list[str] | None = None,
        required_skills: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        authority_level: int = 1,
        approval_authority: dict[str, Any] | None = None,
        reports_to_role_id: str | None = None,
        constraint_template_id: str | None = None,
        constraint_overrides: dict[str, Any] | None = None,
        auto_generate_agent: bool = True,
        is_primary_for_unit: bool = False,
        is_external: bool = False,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an organization role.

        Server: ``POST /api/v1/organization-roles``.

        Args:
            organization_unit_id: Unit this role belongs to.
            title: Role title (1-200 chars).
            authority_level: L1 (staff) .. L5 (C-suite), informational only
                (1-5, default 1).
            reports_to_role_id: Manager role in the reporting chain.
            is_primary_for_unit: Whether this is the unit's head role.
        """
        body: dict[str, Any] = {
            "organization_unit_id": organization_unit_id,
            "title": title,
            "authority_level": authority_level,
            "auto_generate_agent": auto_generate_agent,
            "is_primary_for_unit": is_primary_for_unit,
            "is_external": is_external,
        }
        optional = {
            "description": description,
            "job_description": job_description,
            "responsibilities": responsibilities,
            "required_skills": required_skills,
            "required_capabilities": required_capabilities,
            "approval_authority": approval_authority,
            "reports_to_role_id": reports_to_role_id,
            "constraint_template_id": constraint_template_id,
            "constraint_overrides": constraint_overrides,
            "metadata": metadata,
            "tags": tags,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        resp: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/organization-roles", json_data=body
        )
        return resp

    async def get(self, role_id: str) -> dict[str, Any]:
        """Get an organization role by ID.

        Server: ``GET /api/v1/organization-roles/{role_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/organization-roles/{encode_path_param(role_id)}"
        )
        return resp
