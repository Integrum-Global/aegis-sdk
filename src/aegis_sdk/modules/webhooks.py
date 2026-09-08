"""
Webhooks Module for Agentic OS SDK.

Provides webhook management for event-driven integrations.

10 methods:
- list() - List webhooks
- create() - Create webhook
- get() - Get webhook details
- update() - Update webhook
- delete() - Delete webhook
- test() - Test webhook
- get_deliveries() - Get delivery history
- retry_delivery() - Retry failed delivery
- list_event_types() - List available event types
- rotate_secret() - Rotate webhook secret
"""

import builtins
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param


class Webhook(BaseModel):
    """
    Webhook model.

    Note:
        ``updated_at`` is Optional because the backend's webhook records do not currently emit an
        ``updated_at`` field — only ``created_at``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    url: str
    events: list[str]
    status: str
    last_triggered_at: str | None = Field(None, alias="lastTriggeredAt")
    failure_count: int = Field(0, alias="failureCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(None, alias="updatedAt")


class WebhookWithSecret(Webhook):
    """Webhook with secret (returned on create)."""

    secret: str = Field(repr=False)  # signing secret shown once -- hidden from repr/str (H1)


class WebhookDelivery(BaseModel):
    """
    Webhook delivery record.

    Note:
        ``payload`` is the raw JSON-encoded string the backend stores/emits
        (``webhook_service.py::deliver()`` -- ``payload = json.dumps(payload_dict)``),
        not a parsed ``dict``. Use ``json.loads(delivery.payload)`` to inspect
        the event body.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    webhook_id: str = Field(alias="webhookId")
    event_type: str = Field(alias="eventType")
    payload: str
    response_status: int | None = Field(None, alias="responseStatus")
    response_body: str | None = Field(None, alias="responseBody")
    status: str  # success, failed, pending
    attempt_count: int = Field(alias="attemptCount")
    created_at: str = Field(alias="createdAt")
    delivered_at: str | None = Field(None, alias="deliveredAt")


class TestResult(BaseModel):
    """Webhook test result."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    status_code: int | None = Field(None, alias="statusCode")
    message: str
    latency_ms: float | None = Field(None, alias="latencyMs")


class WebhooksModule:
    """
    Webhooks module for event-driven integrations.

    Supports HMAC-signed webhook delivery with retry logic.

    Examples:
        # Create webhook
        >>> webhook = await client.webhooks.create(
        ...     name="My Webhook",
        ...     url="https://api.example.com/webhook",
        ...     events=["agent.created", "objective.completed"]
        ... )
        >>> print(f"Secret: {webhook.secret}")

        # Test webhook
        >>> result = await client.webhooks.test(webhook.id)
        >>> print(f"Status: {result.status_code}")
    """

    def __init__(self, http_client):
        """Initialize webhooks module."""
        self._http = http_client

    async def list(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Webhook]:
        """
        List webhooks.

        Args:
            status: Filter by status (active, inactive, error)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Webhook]: List of webhooks

        Note:
            The backend's ``GET /api/v1/webhooks`` handler returns a bare
            JSON array (``response_model=list[WebhookResponse]``), not an
            ``{"webhooks": [...]}`` envelope. It also does not currently
            declare ``status`` / ``limit`` / ``offset`` query parameters, so
            these filters are accepted here for forward-compatibility but
            are not yet enforced server-side.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            "/api/v1/webhooks",
            params=params,
        )
        return [Webhook(**w) for w in response]

    async def create(
        self,
        name: str,
        url: str,
        events: builtins.list[str],
        secret: str | None = None,
    ) -> WebhookWithSecret:
        """
        Create a new webhook.

        Args:
            name: Webhook name
            url: Webhook endpoint URL
            events: Events to subscribe to
            secret: Custom secret (optional, generated if not provided)

        Returns:
            WebhookWithSecret: Created webhook with secret

        Example:
            >>> webhook = await client.webhooks.create(
            ...     name="Notifications",
            ...     url="https://api.example.com/webhook",
            ...     events=["agent.created", "objective.completed"]
            ... )
            >>> # Store the secret securely
            >>> secret = webhook.secret
        """
        data: dict[str, Any] = {
            "name": name,
            "url": url,
            "events": events,
        }
        if secret:
            data["secret"] = secret

        response = await self._http.request(
            "POST",
            "/api/v1/webhooks",
            json_data=data,
        )
        return WebhookWithSecret(**response)

    async def get(self, webhook_id: str) -> Webhook:
        """
        Get webhook details (without secret).

        Args:
            webhook_id: Webhook ID

        Returns:
            Webhook: Webhook details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/webhooks/{encode_path_param(webhook_id)}",
        )
        return Webhook(**response)

    async def update(
        self,
        webhook_id: str,
        name: str | None = None,
        url: str | None = None,
        events: builtins.list[str] | None = None,
        status: str | None = None,
    ) -> Webhook:
        """
        Update webhook.

        Args:
            webhook_id: Webhook ID
            name: New name (optional)
            url: New URL (optional)
            events: New events list (optional)
            status: New status (optional)

        Returns:
            Webhook: Updated webhook
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if url:
            data["url"] = url
        if events:
            data["events"] = events
        if status:
            data["status"] = status

        response = await self._http.request(
            "PUT",
            f"/api/v1/webhooks/{encode_path_param(webhook_id)}",
            json_data=data,
        )
        return Webhook(**response)

    async def delete(self, webhook_id: str) -> bool:
        """
        Delete webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/webhooks/{encode_path_param(webhook_id)}",
        )
        return True

    async def test(self, webhook_id: str) -> TestResult:
        """
        Test webhook by sending a test event.

        Args:
            webhook_id: Webhook ID

        Returns:
            TestResult: Test result with status code

        Example:
            >>> result = await client.webhooks.test("wh-123")
            >>> if result.success:
            ...     print(f"Delivered in {result.latency_ms}ms")

        Note:
            The backend's ``POST /api/v1/webhooks/{id}/test`` handler returns
            ``{"message": str, "delivery": WebhookDeliveryResponse}`` — not a
            flat ``TestResult`` shape. The delivery sub-object is unpacked
            here into the ``TestResult`` fields the SDK exposes.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/webhooks/{encode_path_param(webhook_id)}/test",
        )
        delivery = response.get("delivery") or {}
        # Built as a dict + **-unpacked (matches the module's established
        # Model(**response) construction pattern) so mypy resolves the
        # aliased fields (status_code/latency_ms) via populate_by_name
        # instead of requiring the camelCase alias as an explicit kwarg.
        return TestResult(
            **{
                "success": delivery.get("status") == "success",
                "status_code": delivery.get("response_status"),
                "message": response.get("message", ""),
                "latency_ms": delivery.get("duration_ms"),
            }
        )

    async def get_deliveries(
        self,
        webhook_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> builtins.list[WebhookDelivery]:
        """
        Get webhook delivery history.

        Args:
            webhook_id: Webhook ID
            status: Filter by status (success, failed, pending)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[WebhookDelivery]: Delivery records

        Example:
            >>> deliveries = await client.webhooks.get_deliveries("wh-123")
            >>> for d in deliveries:
            ...     print(f"{d.event_type}: {d.status}")

        Note:
            The backend's ``GET /api/v1/webhooks/{id}/deliveries`` handler returns a bare
            JSON array (``response_model=list[WebhookDeliveryResponse]``),
            not a ``{"deliveries": [...]}`` envelope. It also only declares
            a ``limit`` query parameter — ``status``/``offset`` are accepted
            here for forward-compatibility but are not yet enforced
            server-side.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            f"/api/v1/webhooks/{encode_path_param(webhook_id)}/deliveries",
            params=params,
        )
        return [WebhookDelivery(**d) for d in response]

    async def retry_delivery(
        self,
        webhook_id: str,
        delivery_id: str,
    ) -> WebhookDelivery:
        """
        Retry failed delivery.

        Args:
            webhook_id: Webhook ID (accepted for API symmetry with
                ``get_deliveries``/``list``; not part of the request URL --
                the backend resolves the owning webhook from the delivery
                record itself,)
            delivery_id: Delivery ID

        Returns:
            WebhookDelivery: Updated delivery record
        """
        del webhook_id  # not part of the real backend route; see docstring
        response = await self._http.request(
            "POST",
            f"/api/v1/webhooks/deliveries/{encode_path_param(delivery_id)}/retry",
        )
        return WebhookDelivery(**response)

    async def list_event_types(self) -> builtins.list[str]:
        """
        List available webhook event type names.

        Returns:
            List[str]: Available event type names (e.g. "agent.created")

        Example:
            >>> events = await client.webhooks.list_event_types()
            >>> for name in events:
            ...     print(name)

        Note:
            The backend's ``GET /api/v1/webhooks/events`` handler returns
            ``{"events": list[str]}`` -- plain event-type name strings, not
            structured objects with description/category. There is no
            typed ``EventType`` shape on the wire.
        """
        response = await self._http.request(
            "GET",
            "/api/v1/webhooks/events",
        )
        return list(response.get("events", []))

    async def rotate_secret(self, webhook_id: str) -> str:
        """
        Rotate webhook secret.

        Args:
            webhook_id: Webhook ID

        Returns:
            str: New webhook secret

        Example:
            >>> new_secret = await client.webhooks.rotate_secret("wh-123")
            >>> # Update your integration with the new secret

        Warning:
            NO BACKEND EQUIVALENT. There is no
            ``rotate-secret`` route anywhere
            -- this call will 404 against the real backend until the
            corresponding endpoint is implemented server-side. Left
            unmodified per the phantom-route audit's "no invented routes"
            constraint; do not rely on this method until tracked.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/webhooks/{encode_path_param(webhook_id)}/rotate-secret",
        )
        return response.get("secret", "")
