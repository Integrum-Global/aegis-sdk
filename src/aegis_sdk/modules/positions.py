"""
Agent Positions SDK Module.

A *position* is a signed stance an agent holds on behalf of a principal. It is
created **fail-closed**: a new position is ``unratified`` and therefore NOT
binding. The represented principal must ratify it before any consumer may act
on it, and may retract it afterwards.

Provides programmatic access to the position binding lifecycle:

- create(): Create a position (starts unratified / non-binding)
- get(): Read a position, including its derived ``is_binding`` flag
- ratify(): The represented principal makes the position binding
- retract(): The represented principal withdraws a position
- consume(): Enforced read — returns the position ONLY if it is binding

⛔ AUTH: this surface admits a USER SESSION only. Its router gate does not
accept an API key, and an API-key principal carries no role and no personas
by design, so every method here answers 403 for a client built with
``api_key=``. Use the OAuth configuration instead.

Actor identity is **server-derived** from the authenticated session for every
decision operation, so no method here takes an actor or ratifier argument.
Supplying one would not change who the platform records as having acted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


class Position(TolerantModel):
    """
    A signed position and its binding state.

    ``binding_status`` is the stored lifecycle state (``unratified``,
    ``ratified``, ``retracted``); ``is_binding`` is the derived flag a caller
    should branch on, and is true only while the position is actually
    actionable. Prefer ``is_binding`` over comparing ``binding_status`` to a
    string — the derivation is the platform's, and it is the same one
    :meth:`PositionsModule.consume` enforces.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    sender_agent_id: str = Field(alias="senderAgentId")
    represented_principal_id: str = Field(alias="representedPrincipalId")
    binding_status: str = Field(alias="bindingStatus")
    is_binding: bool = Field(alias="isBinding")
    created_at: str | None = Field(None, alias="createdAt")
    created_by_user_id: str | None = Field(None, alias="createdByUserId")
    ratified_at: str | None = Field(None, alias="ratifiedAt")
    ratified_by_user_id: str | None = Field(None, alias="ratifiedByUserId")
    retracted_at: str | None = Field(None, alias="retractedAt")
    retracted_by_user_id: str | None = Field(None, alias="retractedByUserId")
    retraction_reason: str | None = Field(None, alias="retractionReason")


class PositionsModule:
    """
    Agent Positions SDK module.

    Methods:
        - create(): Create a position (fail-closed: unratified, non-binding)
        - get(): Read a position and its binding state
        - ratify(): Make a position binding
        - retract(): Withdraw a position
        - consume(): Read a position only if it is binding

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(
        ...     api_key="your-api-key", base_url="https://your-host"
        ... )
        >>>
        >>> position = await client.positions.create(
        ...     signed_message_json=signed_payload,
        ...     sender_agent_id="agent-123",
        ...     represented_principal_id="user-456",
        ... )
        >>> position.is_binding
        False
        >>>
        >>> ratified = await client.positions.ratify(position.id)
        >>> ratified.is_binding
        True
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize Positions module with HTTP client."""
        self._http = http_client

    async def create(
        self,
        signed_message_json: str,
        sender_agent_id: str,
        represented_principal_id: str,
    ) -> Position:
        """
        Create a position.

        The new position is created **unratified**, so ``is_binding`` is false
        until :meth:`ratify` succeeds. The creating user is recorded from the
        authenticated session for attribution.

        Args:
            signed_message_json: The signed position payload, as a JSON string
            sender_agent_id: Agent asserting the position
            represented_principal_id: Principal the agent claims to represent

        Returns:
            The created position, unratified and non-binding

        Example:
            >>> position = await client.positions.create(
            ...     signed_message_json=signed_payload,
            ...     sender_agent_id="agent-123",
            ...     represented_principal_id="user-456",
            ... )
        """
        response = await self._http.request(
            "POST",
            "/api/v1/positions",
            json_data={
                "signed_message_json": signed_message_json,
                "sender_agent_id": sender_agent_id,
                "represented_principal_id": represented_principal_id,
            },
        )
        return Position(**response)

    async def get(self, position_id: str) -> Position:
        """
        Get a position by ID.

        Args:
            position_id: Position ID

        Returns:
            The position, including its derived ``is_binding`` flag

        Example:
            >>> position = await client.positions.get("pos-123")
            >>> if not position.is_binding:
            ...     print(f"not actionable: {position.binding_status}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/positions/{encode_path_param(position_id)}",
        )
        return Position(**response)

    async def ratify(self, position_id: str) -> Position:
        """
        Ratify a position, making it binding.

        Only the represented principal may ratify. The ratifying identity is
        derived from the authenticated session, which is why this method takes
        no actor argument.

        Args:
            position_id: Position ID

        Returns:
            The ratified position, with ``is_binding`` true

        Raises:
            Propagates the platform error for a position that is absent (404),
            a caller who is not the represented principal (403), or a position
            that is not in a ratifiable state (409).

        Example:
            >>> ratified = await client.positions.ratify("pos-123")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/positions/{encode_path_param(position_id)}/ratify",
            json_data={},
        )
        return Position(**response)

    async def retract(self, position_id: str, reason: str | None = None) -> Position:
        """
        Retract a position, making it non-binding.

        Only the represented principal may retract. The retracting identity is
        derived from the authenticated session.

        Args:
            position_id: Position ID
            reason: Optional free-text reason, retained on the record

        Returns:
            The retracted position, with ``is_binding`` false

        Raises:
            Propagates the platform error for a position that is absent (404),
            a caller who is not the represented principal (403), or a position
            that is not in a retractable state (409).

        Example:
            >>> await client.positions.retract("pos-123", reason="superseded")
        """
        body: dict[str, Any] = {}
        if reason is not None:
            body["reason"] = reason
        response = await self._http.request(
            "POST",
            f"/api/v1/positions/{encode_path_param(position_id)}/retract",
            json_data=body,
        )
        return Position(**response)

    async def consume(self, position_id: str) -> Position:
        """
        Read a position only if it is binding.

        This is the enforced surface: a position that is unratified or
        retracted is REFUSED (409) rather than returned with a false
        ``is_binding`` flag. Use this — not :meth:`get` — at the point where
        the position is about to be acted on, so that a non-binding position
        cannot be consumed by a caller that forgot to check the flag.

        Args:
            position_id: Position ID

        Returns:
            The position, guaranteed binding

        Raises:
            Propagates the platform error for a position that is absent (404)
            or not binding (409).

        Example:
            >>> position = await client.positions.consume("pos-123")
            >>> # reaching here means the position is binding
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/positions/{encode_path_param(position_id)}/consume",
        )
        return Position(**response)
