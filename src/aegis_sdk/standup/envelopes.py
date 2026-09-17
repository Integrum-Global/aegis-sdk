"""Role envelopes module — create/get/list for the vertical-standup path.

Verified against the server ``role-envelopes`` router (mounted at ``/api/v1``).

⛔ THE ENVELOPE LIFECYCLE IS SPLIT ACROSS TWO MODULES. ``create`` (here)
defaults to ``status="draft"``, and ``activate`` does NOT exist on this
module — it lives on ``client.trust_posture``
(``activate_role_envelope`` / ``suspend_role_envelope`` /
``update_role_envelope`` / ``delete_role_envelope``). A caller holding only
``client.role_envelopes`` can create an envelope and has no way to make it
effective. Reaching for ``client.trust_posture`` to finish is required, not
optional.

NOTE: the server ``CreateRoleEnvelopeRequest`` uses ``extra="forbid"`` +
``populate_by_name=True``, so this module sends ONLY the
declared field names — any extra key is rejected 422.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class RoleEnvelopesModule:
    """Operating-envelope (Layer-1 standing) management (create + get)."""

    def __init__(self, http_client: HTTPClient) -> None:
        self._http = http_client

    async def create(
        self,
        defining_role_id: str,
        target_role_id: str,
        constraint_config: dict[str, Any],
        verification_defaults: dict[str, Any] | None = None,
        clearance_ceiling: str | None = None,
        status: str = "draft",
        review_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a role envelope (defaults to draft).

        Server: ``POST /api/v1/role-envelopes``. Both
        roles MUST belong to the caller's org (cross-tenant defense).

        Args:
            defining_role_id: The supervising role that defines the envelope.
            target_role_id: The direct-report role the envelope applies to.
            constraint_config: The five-dimension constraint configuration.
            status: Creatable status — ``draft`` (default), ``active``, or
                ``suspended``. Active envelopes are validated against the
                supervisor's envelope (monotonic tightening).
        """
        body: dict[str, Any] = {
            "defining_role_id": defining_role_id,
            "target_role_id": target_role_id,
            "constraint_config": constraint_config,
            "status": status,
        }
        optional = {
            "verification_defaults": verification_defaults,
            "clearance_ceiling": clearance_ceiling,
            "review_at": review_at,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        resp: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/role-envelopes", json_data=body
        )
        return resp

    async def get(self, envelope_id: str) -> dict[str, Any]:
        """Get a role envelope by ID.

        Server: ``GET /api/v1/role-envelopes/{envelope_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}"
        )
        return resp
    async def list(
        self,
        defining_role_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List role envelopes for ONE supervising role.

        Server: ``GET /api/v1/role-envelopes``, gated on scope ``roles:read``.

        ⛔ ``defining_role_id`` is REQUIRED and is not a convenience filter.
        The service exposes NO org-wide enumeration path by design, and the
        server returns ``400`` rather than an empty list when it is missing.
        An idempotency check across a whole
        org must therefore ITERATE role-by-role; there is no single call that
        answers "does this envelope already exist anywhere".

        Sent on the wire as ``definingRoleId`` -- the server binds the
        parameter name via ``Query(alias=...)``.

        Args:
            defining_role_id: Supervisor role whose envelopes to list.
            status: Optional status filter (``draft``/``active``/``suspended``).
            limit: Maximum results (1-500, server default 100).
            offset: Pagination offset.

        Returns:
            ``{"records": [...], "total": int}`` -- raw persisted rows, with
            ``constraint_config_json`` as a JSON **string**, not an object.
        """
        params: dict[str, Any] = {
            "definingRoleId": defining_role_id,
            "limit": limit,
            "offset": offset,
        }
        if status is not None:
            params["status"] = status
        resp: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/role-envelopes", params=params
        )
        return resp
