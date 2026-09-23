"""Organization units module — typed create/get/list/update for the standup path.

Verified against the server ``organization-units`` router (mounted at ``/api/v1``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


_UNSET: Any = object()
"""Sentinel distinguishing "argument omitted" from "explicitly None"."""


class OrganizationUnitsModule:
    """Organization unit management (create · get · list · update)."""

    def __init__(self, http_client: HTTPClient) -> None:
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

    async def update_unit(
        self,
        unit_id: str,
        *,
        name: str | None = None,
        unit_type: str | None = None,
        code: str | None = None,
        description: str | None = None,
        mission_statement: str | None = None,
        responsibilities: list[str] | None = None,
        budget_allocation: float | None = None,
        budget_currency: str | None = None,
        headcount_limit: int | None = None,
        default_constraint_template_id: str | None = None,
        constraint_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        display_subtype: str | None = None,
        default_classification: str | None = None,
        max_trust_posture: str | None = None,
        isolation_domain: str | None = _UNSET,
    ) -> dict[str, Any]:
        """Update an organization unit in place.

        Server: ``PUT /api/v1/organization-units/{unit_id}``.
        Requires ``organizations:update``.

        Every field is optional and each one is a PARTIAL update: a field you do
        not name is left unchanged. This is the rename path — without it a typo
        in a unit name during a live standup can only be fixed by archiving the
        unit and rebuilding it, because units cannot be merged. There is no
        delete equivalent here; ``status="archived"`` is how a unit is retired.

        ⚠ ``isolation_domain`` DOES NOT FOLLOW THAT RULE, and the difference is
        a control rather than a convenience. Every other field treats ``None``
        as "not supplied"; ``isolation_domain`` must also be able to mean
        UNASSIGN. So OMITTING it leaves the plane label unchanged, and passing
        ``None`` explicitly CLEARS it by sending the key with a null. A plain
        ``None`` default would make clearing the only reachable behaviour, on
        every call that merely renamed the unit.

        Args:
            unit_id: Unit ID.
            name: New name (1-200 chars).
            unit_type: ``department`` or ``team``.
            code: Short code (max 20 chars).
            description: Description (max 2000 chars).
            mission_statement: Mission statement (max 2000 chars).
            responsibilities: List of responsibilities.
            budget_allocation: Budget amount.
            budget_currency: Currency for ``budget_allocation``.
            headcount_limit: Maximum headcount.
            default_constraint_template_id: Constraint template to inherit.
            constraint_overrides: Per-unit constraint overrides.
            metadata: Free-form metadata.
            tags: Tags.
            status: ``active``, ``archived`` or ``suspended``.
            display_subtype: Display-only subtype label.
            default_classification: One of ``public``, ``restricted``,
                ``confidential``, ``secret``, ``top_secret``.
            max_trust_posture: CARE posture ceiling — one of ``pseudo``,
                ``supervised``, ``shared_planning``, ``continuous_insight``,
                ``delegated``. Agents in this unit cannot exceed it.
            isolation_domain: Hard-isolation plane label, or an explicit
                ``None`` to CLEAR it. Omit to leave it unchanged.

        Returns:
            The updated unit, as the server returns it.

        Raises:
            ValueError: If no field was supplied. A PUT carrying an empty body
                cannot change anything, and the server would answer it as a
                no-op rather than as the mistake it is.

        Example:
            >>> await client.units.update_unit("u1", name="Accounts Payable")
            >>> await client.units.update_unit("u1", isolation_domain=None)  # CLEARS
        """
        body: dict[str, Any] = {
            k: v
            for k, v in {
                "name": name,
                "unit_type": unit_type,
                "code": code,
                "description": description,
                "mission_statement": mission_statement,
                "responsibilities": responsibilities,
                "budget_allocation": budget_allocation,
                "budget_currency": budget_currency,
                "headcount_limit": headcount_limit,
                "default_constraint_template_id": default_constraint_template_id,
                "constraint_overrides": constraint_overrides,
                "metadata": metadata,
                "tags": tags,
                "status": status,
                "display_subtype": display_subtype,
                "default_classification": default_classification,
                "max_trust_posture": max_trust_posture,
            }.items()
            if v is not None
        }
        # Sent the key only when it was named — see the ⚠ above.
        if isolation_domain is not _UNSET:
            body["isolation_domain"] = isolation_domain
        if not body:
            raise ValueError(
                "update_unit() was called with no fields to change; name at "
                "least one field, or the request cannot alter the unit."
            )
        resp: dict[str, Any] = await self._http.request(
            "PUT",
            f"/api/v1/organization-units/{encode_path_param(unit_id)}",
            json_data=body,
        )
        return resp

    async def list(
        self,
        parent_unit_id: str | None = None,
        unit_type: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List organization units in the caller's organization.

        Server: ``GET /api/v1/organization-units``.
        This route is API-key-aware: a key holding ``units:read`` /
        ``organizations:read`` is admitted, not only a session persona.

        Args:
            parent_unit_id: Filter by parent unit.
            unit_type: Filter by unit type.
            include_archived: Include archived units (default False).
            limit: Maximum results (1-200, server default 50).
            offset: Pagination offset.

        Returns:
            ``{"records": [...], "total": int}``.
        """
        params: dict[str, Any] = {
            "include_archived": include_archived,
            "limit": limit,
            "offset": offset,
        }
        if parent_unit_id is not None:
            params["parent_unit_id"] = parent_unit_id
        if unit_type is not None:
            params["unit_type"] = unit_type
        resp: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/organization-units", params=params
        )
        return resp
