"""Role envelopes module — typed create/get for the vertical-standup path.

Verified against the server ``role-envelopes`` router(mounted at ``/api/v1``)).

NOTE: the server ``CreateRoleEnvelopeRequest`` uses ``extra="forbid"`` +
``populate_by_name=True``, so this module sends ONLY the
declared field names — any extra key is rejected 422.
"""

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class RoleEnvelopesModule:
    """Operating-envelope (Layer-1 standing) management (create + get)."""

    def __init__(self, http_client: "HTTPClient") -> None:
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
