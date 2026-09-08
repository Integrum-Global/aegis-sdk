"""
Agentic OS SDK Trust Postures Module.

Provides operations for managing agent trust postures.
Postures define the level of autonomy and trust granted to an agent.
"""

from typing import Any

from .._http import encode_path_param
from ..types import (
    PostureMetrics,
    TrustPosture,
    TrustPostureInfo,
)


class PosturesModule:
    """
    Trust posture management operations.

    Postures define progressive levels of autonomy (CARE-aligned; these are
    the exact lowercase values the backend accepts):
    - pseudo: Human approval required for all actions
    - supervised: Human approval for high-impact actions
    - shared_planning: Autonomous low-risk actions, approval for medium/high
    - continuous_insight: Autonomous medium-risk actions, approval for high
    - delegated: Fully autonomous (rarely granted)

    Agents progress through postures based on track record.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # Check current posture
        ...     info = await client.trust.postures.get("agent_abc123")
        ...     print(f"Current posture: {info.posture}")
        ...
        ...     # Request progression
        ...     if info.progression_eligible:
        ...         new_info = await client.trust.postures.request_progression(
        ...             "agent_abc123",
        ...             target_posture="shared_planning",
        ...             justification="50 successful tasks without issues"
        ...         )
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def get(self, agent_id: str) -> TrustPostureInfo:
        """
        Get current posture for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Current posture information

        Example:
            >>> info = await client.trust.postures.get("agent_abc123")
            >>> print(f"Posture: {info.posture}")
            >>> print(f"Eligible for progression: {info.progression_eligible}")
        """
        # Server route: GET /agents/{agent_id}/trust-posture — the posture
        # router mounts at /api/v1 WITHOUT the /trust prefix.
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture",
        )
        return TrustPostureInfo(**response)

    async def request_progression(
        self,
        agent_id: str,
        target_posture: TrustPosture,
        justification: str,
    ) -> TrustPostureInfo:
        """
        Request posture progression for an agent.

        Server route: PUT /agents/{agent_id}/trust-posture
        (UpdatePostureRequest at :151-156).
        There is no dedicated "/posture/progression" endpoint on the real
        backend — a posture-change request (whether self-initiated
        progression or an admin override, see :meth:`override`) goes
        through this single PUT, which internally decides whether the
        transition applies immediately or requires manager approval
        (returns 202 + ApprovalPendingResponse in that case). The wire
        body is ``{posture, config, reason}`` — NOT ``target_posture`` /
        ``justification`` (those SDK-side names are kept for API
        stability; they map onto the real field names below).

        Args:
            agent_id: Agent ID
            target_posture: Target posture level
            justification: Justification for progression

        Returns:
            Updated posture information (may require approval)

        Raises:
            ValidationError: If progression is not allowed

        Example:
            >>> info = await client.trust.postures.request_progression(
            ...     "agent_abc123",
            ...     target_posture="shared_planning",
            ...     justification="Completed 100 tasks with 99% success rate"
            ... )
        """
        posture_value = (
            target_posture.value
            if isinstance(target_posture, TrustPosture)
            else TrustPosture(target_posture).value
        )
        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture",
            json_data={"posture": posture_value, "config": {}, "reason": justification},
        )
        return TrustPostureInfo(**response)

    async def override(
        self,
        agent_id: str,
        new_posture: TrustPosture,
        reason: str,
    ) -> TrustPostureInfo:
        """
        Override an agent's posture (admin action).

        Server route: PUT /agents/{agent_id}/trust-posture — the SAME endpoint as
        :meth:`request_progression`. There is no separate
        ``/posture/override`` endpoint on the real backend; the PUT
        handler is the single posture-change surface, and
        ``Permission("trust:delegate")`` gates which callers may invoke
        it regardless of whether the caller's intent is a self-requested
        progression or an admin override.

        Args:
            agent_id: Agent ID
            new_posture: New posture to set
            reason: Reason for override

        Returns:
            Updated posture information

        Raises:
            AuthorizationError: If caller cannot override postures

        Example:
            >>> # Emergency restriction
            >>> info = await client.trust.postures.override(
            ...     "agent_abc123",
            ...     new_posture="pseudo",
            ...     reason="Security review pending"
            ... )
        """
        posture_value = (
            new_posture.value
            if isinstance(new_posture, TrustPosture)
            else TrustPosture(new_posture).value
        )
        response = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture",
            json_data={"posture": posture_value, "config": {}, "reason": reason},
        )
        return TrustPostureInfo(**response)

    async def approve_transition(
        self,
        agent_id: str,
        notes: str | None = None,
    ) -> TrustPostureInfo:
        """
        Approve a pending posture transition for an agent.

        Server route: POST /agents/{agent_id}/trust-posture/approve
        (ApproveTransitionRequest at
        :167-170). The server resolves the agent's current pending
        approval itself — no approval_id is passed by the caller.

        Args:
            agent_id: Agent ID
            notes: Optional approval notes

        Returns:
            Updated posture information after approval

        Raises:
            NotFoundError: If no pending approval exists for the agent

        Example:
            >>> info = await client.trust.postures.approve_transition(
            ...     "agent_abc123",
            ...     notes="Reviewed evidence, approved"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/approve",
            json_data={"notes": notes},
        )
        return TrustPostureInfo(**response)

    async def reject_transition(
        self,
        agent_id: str,
        notes: str,
    ) -> dict[str, Any]:
        """
        Reject a pending posture transition for an agent.

        Server route: POST /agents/{agent_id}/trust-posture/reject
        (RejectTransitionRequest at
        :173-176 — ``notes`` requires >= 10 characters server-side).
        Returns the rejected approval record (server's
        ``PostureApprovalResponse`` shape: id, agentId, requestedPosture,
        currentPosture, reason, status, reviewedBy, ...). This SDK has no
        typed model for that shape yet, so the raw response dict is
        returned as-is rather than coerced into an unrelated type.

        Args:
            agent_id: Agent ID
            notes: Rejection reason (server requires >= 10 characters)

        Returns:
            Raw rejected-approval record from the server

        Raises:
            NotFoundError: If no pending approval exists for the agent
            ValidationError: If notes is too short

        Example:
            >>> record = await client.trust.postures.reject_transition(
            ...     "agent_abc123",
            ...     notes="Insufficient evidence for this posture level"
            ... )
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/reject",
            json_data={"notes": notes},
        )
        return response

    async def get_metrics(self, agent_id: str) -> PostureMetrics:
        """
        Get posture progression metrics for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Posture metrics including task history and progression score

        Example:
            >>> metrics = await client.trust.postures.get_metrics("agent_abc123")
            >>> print(f"Tasks completed: {metrics.tasks_completed}")
            >>> print(f"Success rate: {metrics.successful_verifications / (metrics.successful_verifications + metrics.failed_verifications) * 100:.1f}%")
            >>> print(f"Progression score: {metrics.progression_score}")
        """
        # Server route: GET /agents/{agent_id}/trust-posture/metrics
        # (posture router mounts at /api/v1).
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/metrics",
        )
        return PostureMetrics(**response)
