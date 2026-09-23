"""Role envelopes module — the full envelope lifecycle for the standup path.

Verified against the server ``role-envelopes`` router (mounted at ``/api/v1``).

THE LIFECYCLE IS COMPLETE ON THIS MODULE. ``create`` defaults to
``status="draft"``, and a draft constrains nothing — ``activate`` is the call
that makes an envelope effective, and it lives here alongside ``suspend``,
``update`` and ``delete``.

The same four verbs are ALSO on ``client.trust_posture``
(``activate_role_envelope`` / ``suspend_role_envelope`` /
``update_role_envelope`` / ``delete_role_envelope``), over the same routes.
Both surfaces are kept deliberately: ``trust_posture`` already carries typed
duplicates of this module's ``list`` and ``get``, so this module carrying the
other four is the same trade in the reverse direction. Reach for
``trust_posture`` when you want the parsed ``RoleEnvelope`` model; reach for
this module when you are already in ``client.role_envelopes`` and want a raw
dict like its siblings.

NOTE: the server ``CreateRoleEnvelopeRequest`` uses ``extra="forbid"`` +
``populate_by_name=True``, so this module sends ONLY the
declared field names — any extra key is rejected 422.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param
from ..modules.trust_posture import ALLOWED_CLEARANCE_LEVELS

if TYPE_CHECKING:
    from .._http import HTTPClient


class RoleEnvelopesModule:
    """Operating-envelope (Layer-1 standing) management — the full lifecycle."""

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

    async def activate(self, envelope_id: str) -> dict[str, Any]:
        """Activate an envelope so it starts enforcing.

        Server: ``POST /api/v1/role-envelopes/{envelope_id}/activate``.

        ``create`` defaults to ``status="draft"`` and a draft constrains
        nothing, so this is the call that makes an envelope effective. The typed
        equivalent on ``client.trust_posture`` is ``activate_role_envelope``.

        Args:
            envelope_id: Envelope ID.

        Returns:
            The activated envelope, as the server returns it.
        """
        resp: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}/activate",
        )
        return resp

    async def suspend(self, envelope_id: str) -> dict[str, Any]:
        """Suspend an active envelope.

        Server: ``POST /api/v1/role-envelopes/{envelope_id}/suspend``.

        A suspended envelope stops enforcing without being deleted, so it can be
        brought back with :meth:`activate`. The typed equivalent on
        ``client.trust_posture`` is ``suspend_role_envelope``.

        Args:
            envelope_id: Envelope ID.

        Returns:
            The suspended envelope, as the server returns it.
        """
        resp: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}/suspend",
        )
        return resp

    async def update(
        self,
        envelope_id: str,
        constraint_config: dict[str, Any] | None = None,
        verification_defaults: dict[str, Any] | None = None,
        clearance_ceiling: str | None = None,
        review_at: str | None = None,
    ) -> dict[str, Any]:
        """Edit an envelope's constraint config, clearance ceiling or review date.

        Server: ``PUT /api/v1/role-envelopes/{envelope_id}``.

        ⛔ This route does NOT change ``status``, and the omission is a control
        rather than a gap: status transitions go through :meth:`activate` /
        :meth:`suspend` / :meth:`delete`, so an edit cannot move an envelope
        through its lifecycle as a side effect.

        Args:
            envelope_id: Envelope ID.
            constraint_config: Replacement constraint config.
            verification_defaults: Replacement per-dimension gradient config.
            clearance_ceiling: Replacement clearance ceiling; one of ``public``,
                ``restricted``, ``confidential``, ``secret``, ``top_secret``.
            review_at: Replacement next-review timestamp.

        Returns:
            The updated envelope, as the server returns it.

        Raises:
            ValueError: If ``clearance_ceiling`` is not in the allowed set.
        """
        if clearance_ceiling is not None and clearance_ceiling not in ALLOWED_CLEARANCE_LEVELS:
            raise ValueError(
                f"clearance_ceiling must be one of {sorted(ALLOWED_CLEARANCE_LEVELS)}; "
                f"got {clearance_ceiling!r}"
            )
        data: dict[str, Any] = {}
        if constraint_config is not None:
            data["constraint_config"] = constraint_config
        if verification_defaults is not None:
            data["verification_defaults"] = verification_defaults
        if clearance_ceiling is not None:
            data["clearance_ceiling"] = clearance_ceiling
        if review_at is not None:
            data["review_at"] = review_at
        resp: dict[str, Any] = await self._http.request(
            "PUT",
            f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}",
            json_data=data,
        )
        return resp

    async def delete(self, envelope_id: str) -> None:
        """Delete an envelope.

        Server: ``DELETE /api/v1/role-envelopes/{envelope_id}``.

        Not reversible through this client. To stop an envelope enforcing while
        keeping it, use :meth:`suspend` instead.

        Args:
            envelope_id: Envelope ID.
        """
        await self._http.request(
            "DELETE", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}"
        )
