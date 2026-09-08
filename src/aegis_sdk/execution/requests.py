"""
Agentic OS SDK Requests Module.

Provides operations for managing requests (work items within objectives).

⛔ AUTHENTICATION — none of this module's routes accept an API key.

Every route here is gated on an operator PERSONA. An API-key principal is
synthesised with no role and an empty persona list, which is the platform's
deliberate fail-closed default, and these routes were never wired with the
key-aware variant of the persona gate. The gates are applied as a
CONJUNCTION, so a route carrying both a key-aware scope check and a plain
persona check still denies the key.

The consequence is concrete: a client built as ``AgenticOSClient(api_key=...)``
receives 403 from every method below, on reads as well as writes. Authenticate
with a session token instead -- ``await client.auth.login(...)`` followed by
``client.set_auth_token(token.access_token)``.

This is a platform-side gap, not a client limitation, and it is reported as
such. It is documented here rather than left for a caller to discover at
runtime, because a method that always 403s for the credential most consumers
hold is worse than an absent one unless it says so.
"""

import builtins
from typing import Any

from .._http import encode_path_param
from ..types import (
    Finding,
    PaginatedResponse,
    Request,
    RequestComplete,
    RequestEscalate,
    RequestStatus,
)


class RequestsModule:
    """
    Requests management operations.

    Requests are work items within objectives that agents can claim,
    execute, and complete.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # List pending requests
        ...     requests = await client.requests.list(status="pending")
        ...
        ...     # Claim a request
        ...     request = await client.requests.claim("req_abc123")
        ...
        ...     # Complete the request
        ...     await client.requests.complete(
        ...         "req_abc123",
        ...         result={"analysis": "completed"},
        ...         artifacts=["artifact_1"]
        ...     )
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def list(
        self,
        objective_id: str | None = None,
        status: RequestStatus | None = None,
        claimed_by: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse:
        """
        List requests with optional filters.

        Args:
            objective_id: Filter by objective
            status: Filter by request status
            claimed_by: Filter by claiming agent
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Paginated list of requests

        Example:
            >>> requests = await client.requests.list(status="pending")
            >>> print(f"Found {requests.total} pending requests")
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if objective_id:
            params["objective_id"] = objective_id
        if status:
            params["status"] = status.value if isinstance(status, RequestStatus) else status
        if claimed_by:
            params["claimed_by"] = claimed_by

        response = await self._http.request("GET", "/api/v1/requests", params=params)
        return PaginatedResponse(
            items=[Request(**item) for item in response.get("items", [])],
            total=response.get("total", 0),
            page=response.get("page", page),
            page_size=response.get("page_size", page_size),
            has_next=response.get("has_next", False),
        )

    async def get(self, request_id: str) -> Request:
        """
        Get request by ID.

        Args:
            request_id: Request ID

        Returns:
            Request details

        Raises:
            NotFoundError: If request doesn't exist

        Example:
            >>> request = await client.requests.get("req_abc123")
            >>> print(f"Request: {request.title} ({request.status})")
        """
        response = await self._http.request(
            "GET", f"/api/v1/requests/{encode_path_param(request_id)}"
        )
        return Request(**response)

    async def claim(self, request_id: str, agent_id: str | None = None) -> Request:
        """
        Claim a request for execution.

        Args:
            request_id: Request ID
            agent_id: Agent ID claiming the request (uses authenticated agent if not specified)

        Returns:
            Claimed request

        Raises:
            ValidationError: If request is already claimed
            AuthorizationError: If agent cannot claim this request

        Example:
            >>> request = await client.requests.claim("req_abc123")
            >>> print(f"Claimed by: {request.claimed_by}")
        """
        json_data = {}
        if agent_id:
            json_data["agent_id"] = agent_id

        response = await self._http.request(
            "POST",
            f"/api/v1/requests/{encode_path_param(request_id)}/claim",
            json_data=json_data if json_data else None,
        )
        return Request(**response)

    async def release(self, request_id: str) -> Request:
        """
        Release a claimed request.

        Args:
            request_id: Request ID

        Returns:
            Released request

        Raises:
            ValidationError: If request is not claimed by caller

        Example:
            >>> request = await client.requests.release("req_abc123")
            >>> print(f"Request released, status: {request.status}")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/requests/{encode_path_param(request_id)}/release",
        )
        return Request(**response)

    async def complete(
        self,
        request_id: str,
        result: dict[str, Any],
        artifacts: builtins.list[str] | None = None,
    ) -> Request:
        """
        Mark a request as complete.

        Args:
            request_id: Request ID
            result: Result data from execution
            artifacts: List of artifact IDs produced

        Returns:
            Completed request

        Raises:
            ValidationError: If request is not claimed by caller

        Example:
            >>> request = await client.requests.complete(
            ...     "req_abc123",
            ...     result={"summary": "Task completed successfully"},
            ...     artifacts=["artifact_1", "artifact_2"]
            ... )
        """
        complete_data = RequestComplete(
            result=result,
            artifacts=artifacts or [],
        )
        response = await self._http.request(
            "POST",
            f"/api/v1/requests/{encode_path_param(request_id)}/complete",
            json_data=complete_data.model_dump(),
        )
        return Request(**response)

    async def escalate(
        self,
        request_id: str,
        reason: str,
        target_id: str | None = None,
    ) -> Request:
        """
        Escalate a request to a human or higher authority.

        Args:
            request_id: Request ID
            reason: Reason for escalation
            target_id: Optional ID of target to escalate to

        Returns:
            Escalated request

        Example:
            >>> request = await client.requests.escalate(
            ...     "req_abc123",
            ...     reason="Requires human approval for budget over $10,000"
            ... )
        """
        escalate_data = RequestEscalate(
            reason=reason,
            target_id=target_id,
        )
        response = await self._http.request(
            "POST",
            f"/api/v1/requests/{encode_path_param(request_id)}/escalate",
            json_data=escalate_data.model_dump(exclude_none=True),
        )
        return Request(**response)

    async def get_findings(self, request_id: str) -> builtins.list[Finding]:
        """
        Get all findings for a request.

        Args:
            request_id: Request ID

        Returns:
            List of findings

        Example:
            >>> findings = await client.requests.get_findings("req_abc123")
            >>> for f in findings:
            ...     print(f"{f.finding_type}: {f.content}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/requests/{encode_path_param(request_id)}/findings",
        )
        return [Finding(**item) for item in response]

    async def add_finding(
        self,
        request_id: str,
        finding_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Finding:
        """
        Add a finding to a request.

        Args:
            request_id: Request ID
            finding_type: Type of finding ("info", "warning", "error", "recommendation")
            content: Finding content/description
            metadata: Additional metadata

        Returns:
            Created finding

        Example:
            >>> finding = await client.requests.add_finding(
            ...     "req_abc123",
            ...     finding_type="warning",
            ...     content="Data quality issues detected in source"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/requests/{encode_path_param(request_id)}/findings",
            json_data={
                "finding_type": finding_type,
                "content": content,
                "metadata": metadata or {},
            },
        )
        return Finding(**response)

    # ------------------------------------------------------------------
    # Objective-scoped operations
    #
    # These address routes nested under an objective. They are NOT aliases of
    # the flat ``/requests/{id}/...`` routes above: they take the objective
    # into account and report back on it, which the flat routes cannot.
    # ------------------------------------------------------------------

    async def complete_in_objective(
        self,
        objective_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """
        Complete a request and report whether its objective can continue.

        Distinct from :meth:`complete`, which addresses the flat request route
        and returns the request. This one evaluates the objective afterwards
        and tells you what is still blocking it.

        Args:
            objective_id: Objective the request belongs to
            request_id: Request ID

        Returns:
            ``success``, ``request_id``, ``status`` / ``new_status``, and
            ``objective_continuation`` -- itself ``None`` when the platform
            could not evaluate continuation, otherwise carrying
            ``can_continue``, ``next_step``, ``blocking_requests``,
            ``completed_requests`` and ``total_requests``.

            ``success`` can be ``False`` in a 200 response; a refused
            completion is reported in the body.

        Raises:
            AgenticOSError: On a 409 conflict -- the request is in a state from which it cannot be completed. The SDK maps NO
                exception subclass to 409, so this arrives as the BASE error
                rather than a conflict-specific type; discriminate on
                ``exc.details["status_code"] == 409``.

        Example:
            >>> outcome = await client.requests.complete_in_objective(
            ...     "obj_abc123", "req_def456"
            ... )
            >>> cont = outcome.get("objective_continuation")
            >>> if cont and not cont["can_continue"]:
            ...     print("still blocked by", cont["blocking_requests"])
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/requests/{encode_path_param(request_id)}/complete",
        )
        return response

    async def decompose(
        self,
        objective_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """
        Decompose a request into a task graph.

        Args:
            objective_id: Objective the request belongs to
            request_id: Request ID

        Returns:
            ``{"success": True, "request_id": ..., "objective_id": ...,
            "task_graph": {...}}``.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/requests/{encode_path_param(request_id)}/decompose",
        )
        return response

    async def submit_deliverable(
        self,
        objective_id: str,
        request_id: str,
        deliverable_text: str,
        artifact_ids: builtins.list[str] | None = None,
        sign_off_confirmed: bool = False,
    ) -> dict[str, Any]:
        """
        Submit a deliverable against a request.

        Args:
            objective_id: Objective the request belongs to
            request_id: Request ID
            deliverable_text: The deliverable content (1-50,000 characters).
                Required and non-empty -- there is no artifact-only submission
                on this route.
            artifact_ids: Already-uploaded artifact IDs to attach
            sign_off_confirmed: Whether the submitter confirmed sign-off terms

        Returns:
            ``success``, ``request_id``, ``artifact_id`` (the artifact created
            from ``deliverable_text``), ``status``,
            ``all_siblings_complete``, and the same
            ``objective_continuation`` block :meth:`complete_in_objective`
            returns.


        Raises:
            AgenticOSError: On a 409 conflict -- the request is in a state from which a deliverable cannot be submitted. The SDK maps NO
                exception subclass to 409, so this arrives as the BASE error
                rather than a conflict-specific type; discriminate on
                ``exc.details["status_code"] == 409``.

        Note:
            ``sign_off_confirmed`` is recorded as submitted. Passing ``True``
            asserts that a human confirmed the terms; do not default it on in
            automated callers.
        """
        body: dict[str, Any] = {
            "deliverable_text": deliverable_text,
            "artifact_ids": artifact_ids or [],
            "sign_off_confirmed": sign_off_confirmed,
        }
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/objectives/{encode_path_param(objective_id)}/requests/{encode_path_param(request_id)}/submit-deliverable",
            json_data=body,
        )
        return response
