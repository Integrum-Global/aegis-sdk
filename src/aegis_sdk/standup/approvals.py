"""Approvals (HOTL) module — human-on-the-loop decision surface.

Verified against the server ``approvals`` router(mounted at ``/api/v1``)).

MODIFY-VERB FINDING ( §3): there is NO dedicated ``/modify`` route.
The server ``approve`` endpoint accepts an ``ApprovalDecisionRequest`` whose
``modification`` field carries an edited payload (handler at :313 documents "Optionally include modifications to the proposed
action"). :meth:`modify` therefore approves-with-an-edited-payload against the
real ``/approve`` route — it does NOT invent a non-existent path.
"""

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class ApprovalsModule:
    """Human-on-the-loop approval queue (list/get/approve/reject/modify)."""

    def __init__(self, http_client: "HTTPClient") -> None:
        self._http = http_client

    async def list_pending(
        self,
        organization_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List pending approval requests.

        Server: ``GET /api/v1/approvals/pending``.

        Args:
            limit: Maximum results (1-100, default 50).
        """
        params: dict[str, Any] = {"limit": limit}
        if organization_id is not None:
            params["organization_id"] = organization_id
        if agent_id is not None:
            params["agent_id"] = agent_id
        if session_id is not None:
            params["session_id"] = session_id
        resp: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/approvals/pending", params=params
        )
        return resp

    async def get(self, request_id: str) -> dict[str, Any]:
        """Get an approval request by ID.

        Server: ``GET /api/v1/approvals/{request_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/approvals/{encode_path_param(request_id)}"
        )
        return resp

    async def approve(
        self,
        request_id: str,
        reviewed_by: str,
        reason: str | None = None,
        modification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Approve an approval request.

        Server: ``POST /api/v1/approvals/{request_id}/approve``.

        Args:
            reviewed_by: Reviewer identity.
            reason: Optional rationale.
            modification: Optional edited action payload to apply on approval.
        """
        body: dict[str, Any] = {"reviewed_by": reviewed_by}
        if reason is not None:
            body["reason"] = reason
        if modification is not None:
            body["modification"] = modification
        resp: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/approvals/{encode_path_param(request_id)}/approve", json_data=body
        )
        return resp

    async def reject(
        self,
        request_id: str,
        reviewed_by: str,
        reason: str,
    ) -> dict[str, Any]:
        """Reject an approval request.

        Server: ``POST /api/v1/approvals/{request_id}/reject``. A reason is required for rejection.
        """
        resp: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/approvals/{encode_path_param(request_id)}/reject",
            json_data={"reviewed_by": reviewed_by, "reason": reason},
        )
        return resp

    async def modify(
        self,
        request_id: str,
        reviewed_by: str,
        modification: dict[str, Any],
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Approve an approval request WITH an edited action payload.

        This is the counter-propose / modify verb. There is NO dedicated
        ``/modify`` route server-side; this approves against the real
        ``/approve`` endpoint carrying the ``modification`` payload
        (:313). See this module's docstring.
        """
        return await self.approve(
            request_id,
            reviewed_by=reviewed_by,
            reason=reason,
            modification=modification,
        )
