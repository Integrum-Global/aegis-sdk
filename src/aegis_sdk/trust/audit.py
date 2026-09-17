"""
Agentic OS SDK Trust Audit Module.

Provides operations for querying trust audit logs.
All trust operations are logged for compliance and traceability.
"""

import warnings
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel
from ..exceptions import UnsupportedOperationError
from ..types import (
    PaginatedResponse,
    TrustAuditEntry,
)


class AuditRootSourceChain(TolerantModel):
    """The delegation chain from an audit entry back to its root human source.

    Warning:
        ``verified`` reports signature verification and defaults to ``True``
        for an entry that carries NO signature at all. It therefore means
        "no signature check failed", not "this entry is cryptographically
        verified". An unsigned entry and a validly-signed entry are
        indistinguishable on this field alone.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    root_user_id: str | None = None
    delegation_chain: list[dict] = Field(default_factory=list)
    delegation_depth: int = 0
    verified: bool = False


class AuditModule:
    """
    Trust audit log operations.

    All trust operations (establish, delegate, verify, revoke, override)
    are recorded in an immutable audit log for compliance and forensics.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # Query audit logs
        ...     entries = await client.trust.audit.query(
        ...         agent_id="agent_abc123",
        ...         action_type="verify",
        ...         start_date=datetime(2024, 1, 1)
        ...     )
        ...     for entry in entries.items:
        ...         print(f"{entry.timestamp}: {entry.action_type} - {entry.result}")
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def query(
        self,
        agent_id: str | None = None,
        human_origin_id: str | None = None,
        action_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResponse:
        """
        Query trust audit logs.

        Args:
            agent_id: Filter by agent
            human_origin_id: Filter by human origin
            action_type: Filter by action type ("establish", "delegate", "verify", "revoke", "override")
            start_date: Filter by start date
            end_date: Filter by end date
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Paginated list of audit entries

        Example:
            >>> entries = await client.trust.audit.query(
            ...     agent_id="agent_abc123",
            ...     action_type="verify",
            ...     start_date=datetime(2024, 1, 1),
            ...     end_date=datetime(2024, 12, 31)
            ... )
            >>> print(f"Found {entries.total} verification entries")
        """
        # Server routes:
        #   - GET /trust/audit/by-human/{human_id} (:752-819) when
        #     human_origin_id is supplied — human_id is a PATH param on
        #     this backend, not a query filter, and this is the ONLY
        #     route that supports filtering by human origin.
        #   - GET /trust/audit (:973-1040) otherwise — query params are
        #     `action` (not action_type) and `start_time`/`end_time`
        #     (not start_date/end_date); this route has no
        #     human_origin_id filter at all.
        # Neither response includes page/page_size/has_next — computed
        # below from `total`.
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if start_date:
            params["start_time"] = start_date.isoformat()
        if end_date:
            params["end_time"] = end_date.isoformat()
        if action_type:
            params["action"] = action_type

        if human_origin_id:
            response = await self._http.request(
                "GET",
                f"/api/v1/trust/audit/by-human/{encode_path_param(human_origin_id)}",
                params=params,
            )
        else:
            if agent_id:
                params["agent_id"] = agent_id
            response = await self._http.request("GET", "/api/v1/trust/audit", params=params)

        total = response.get("total", 0)
        items = [
            self._to_audit_entry(item, fallback_human_origin_id=human_origin_id)
            for item in response.get("items", [])
        ]
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
        )

    @staticmethod
    def _to_audit_entry(
        item: dict[str, Any],
        *,
        fallback_human_origin_id: str | None = None,
        chain_id: str | None = None,
    ) -> TrustAuditEntry:
        """Map a real ``AuditAnchor``/``EATPAuditAnchor`` dict onto
        :class:`TrustAuditEntry`.

        The real backend emits ``action`` (not ``action_type``),
        ``details`` (not ``action_data``), a nested ``human_origin``
        object (not a flat ``human_origin_id``), and no ``chain_id`` at
        all (260-271). Fields not present
        on the real response are filled with the most honest available
        default rather than fabricated; ``chain_id`` is populated from
        the caller's own query scope (e.g. :meth:`get_chain_history`'s
        agent_id) when known, since the server has no such field.
        """
        human_origin = item.get("human_origin") or {}
        return TrustAuditEntry(
            id=item["id"],
            timestamp=item["timestamp"],
            agent_id=item["agent_id"],
            human_origin_id=human_origin.get("human_id") or fallback_human_origin_id or "",
            action_type=item.get("action", ""),
            action_data=item.get("details") or {},
            result=item.get("result", ""),
            chain_id=chain_id,
        )

    async def get_entry(self, entry_id: str) -> TrustAuditEntry:
        """
        DEPRECATED — no backing server capability.

        No server route exists for fetching a single flat audit entry by
        ID — searched the published API for a
        ``/audit/{entry_id}`` route on 2026-07-13, none found. The
        closest real route, ``GET /audit/trace/{entry_id}``
        (:1134-1162), is a DIFFERENT capability — it traces an entry back
        to its root human authorizer (a delegation-lineage trace with
        signature verification), not a flat entry record — so repurposing
        it here would silently hand callers the wrong data shape under
        the right-looking name. Kept as a deprecation shim per
        zero-tolerance Rule 6a; will be removed in a future release.

        Raises:
            UnsupportedOperationError: Always — this method has no backing
                server route.
        """
        warnings.warn(
            "AuditModule.get_entry() is deprecated and non-functional — "
            "no server route exists for fetching a single flat audit "
            "entry by ID (the API serves no matching "
            "/audit/{entry_id} endpoint; /audit/trace/{entry_id} is a "
            "different capability — a root-source lineage trace, not an "
            "entry record). This method will be removed in a future "
            "release.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise UnsupportedOperationError(
            f"get_entry({entry_id!r}) has no backing server route; there "
            "is no flat audit-entry-by-ID endpoint on the Aegis API."
        )

    async def get_chain_history(self, chain_id: str) -> list[TrustAuditEntry]:
        """
        Get full audit history for a trust chain.

        Server route: GET /trust/audit,
        filtered by ``agent_id``. There is no separate
        ``/chains/{id}/audit`` endpoint on the real backend — trust chains
        are addressed by agent_id, so ``chain_id`` here IS the agent_id
        whose audit trail is requested (the same addressing
        ``GET /trust/chains/{agent_id}`` uses).

        Args:
            chain_id: Trust chain ID (the chain's agent_id in this backend)

        Returns:
            List of audit entries for the chain

        Example:
            >>> history = await client.trust.audit.get_chain_history("chain_abc123")
            >>> for entry in history:
            ...     print(f"{entry.timestamp}: {entry.action_type}")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/trust/audit",
            params={"agent_id": chain_id, "page": 1, "page_size": 200},
        )
        return [self._to_audit_entry(item, chain_id=chain_id) for item in response.get("items", [])]

    async def trace(self, entry_id: str) -> AuditRootSourceChain:
        """
        Trace an audit entry back to the human who authorized it.

        Every agent action in the trust plane descends from a human
        authorization. This walks that lineage backwards from a single audit
        entry to its root human source.

        Args:
            entry_id: Audit entry ID

        Returns:
            The delegation chain, its depth, the root human, and the
            signature-verification status -- read the warning on
            :class:`AuditRootSourceChain` before treating ``verified`` as
            proof.

        Raises:
            NotFoundError: If the entry does not exist, belongs to another
                organization, or has no traceable root human source. All three
                are answered as not-found, so an untraceable entry is
                indistinguishable from a missing one.

        Example:
            >>> chain = await client.trust.audit.trace("audit_abc123")
            >>> print(chain.root_user_id, chain.delegation_depth)
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/audit/trace/{encode_path_param(entry_id)}",
        )
        return AuditRootSourceChain(**response)
