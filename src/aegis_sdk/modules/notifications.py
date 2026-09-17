"""
Notifications Module for Agentic OS SDK.

Provides notification management and real-time streaming.

12 methods:
- list() - List notifications
- get() - Get notification
- mark_read() - Mark notification as read
- mark_all_read() - Mark all as read
- delete() - Delete notification
- delete_all() - Delete all notifications
- get_stats() - Get notification statistics
- create_channel() - Create notification channel
- list_channels() - List channels
- update_channel() - Update channel
- delete_channel() - Delete channel
- test_channel() - Test channel
"""

import builtins
from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class Notification(TolerantModel):
    """Notification model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str = Field(alias="userId")
    organization_id: str = Field(alias="organizationId")
    type: str
    priority: str
    title: str
    message: str
    resource_type: str | None = Field(None, alias="resourceType")
    resource_id: str | None = Field(None, alias="resourceId")
    is_read: bool = Field(alias="isRead")
    created_at: str = Field(alias="createdAt")
    metadata: dict[str, Any] | None = None


class NotificationStats(TolerantModel):
    """Notification statistics."""

    model_config = ConfigDict(populate_by_name=True)

    unread_count: int = Field(alias="unreadCount")
    total_count: int = Field(alias="totalCount")
    by_type: dict[str, int] = Field(alias="byType")


class NotificationChannel(TolerantModel):
    """Notification channel model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    type: str  # email, slack, teams, sms, pagerduty
    config: dict[str, Any]
    status: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ChannelTestResult(TolerantModel):
    """Channel test result."""

    model_config = ConfigDict(populate_by_name=True)

    delivered: bool
    message: str
    latency_ms: float | None = Field(None, alias="latencyMs")


class NotificationPreferences(TolerantModel):
    """User notification preferences."""

    model_config = ConfigDict(populate_by_name=True)

    agent_failures: bool = Field(alias="agentFailures")
    budget_warnings: bool = Field(alias="budgetWarnings")
    daily_summary: bool = Field(alias="dailySummary")
    objective_completed: bool = Field(alias="objectiveCompleted")
    request_escalated: bool = Field(alias="requestEscalated")


class NotificationsModule:
    """
    Notifications module for managing alerts and channels.

    Supports email, Slack, Teams, SMS, and PagerDuty channels.

    Examples:
        # List unread notifications
        >>> notifications = await client.notifications.list(is_read=False)
        >>> for n in notifications:
        ...     print(f"{n.title}: {n.message}")

        # Create Slack channel
        >>> channel = await client.notifications.create_channel(
        ...     name="Alerts",
        ...     type="slack",
        ...     config={"webhook_url": "https://hooks.slack.com/..."}
        ... )
    """

    def __init__(self, http_client):
        """Initialize notifications module."""
        self._http = http_client

    async def list(
        self,
        types: list[str] | None = None,
        is_read: bool | None = None,
        priority: list[str] | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """
        List notifications.

        Args:
            types: Filter by notification types
            is_read: Filter by read status
            priority: Filter by priority levels
            since: Filter by timestamp (ISO format)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Notification]: List of notifications
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if types:
            params["types"] = ",".join(types)
        if is_read is not None:
            params["is_read"] = str(is_read).lower()
        if priority:
            params["priority"] = ",".join(priority)
        if since:
            params["since"] = since

        response = await self._http.request(
            "GET",
            "/api/v1/notifications",
            params=params,
        )
        return [Notification(**n) for n in response.get("records", [])]

    async def get(self, notification_id: str) -> Notification:
        """
        Get notification by ID.

        Args:
            notification_id: Notification ID

        Returns:
            Notification: Notification details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/notifications/{encode_path_param(notification_id)}",
        )
        return Notification(**response)

    async def mark_read(self, notification_id: str) -> Notification:
        """
        Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            Notification: Updated notification
        """
        response = await self._http.request(
            "PATCH",
            f"/api/v1/notifications/{encode_path_param(notification_id)}/read",
        )
        return Notification(**response)

    async def mark_multiple_read(self, notification_ids: builtins.list[str]) -> int:
        """
        Mark multiple notifications as read.

        Args:
            notification_ids: List of notification IDs

        Returns:
            int: Number of notifications marked
        """
        response = await self._http.request(
            "PATCH",
            "/api/v1/notifications/read",
            json_data={"ids": notification_ids},
        )
        return response.get("count", 0)

    async def mark_all_read(self) -> int:
        """
        Mark all notifications as read.

        Returns:
            int: Number of notifications marked
        """
        response = await self._http.request(
            "PATCH",
            "/api/v1/notifications/read-all",
        )
        return response.get("count", 0)

    async def delete(self, notification_id: str) -> bool:
        """
        Delete notification.

        Args:
            notification_id: Notification ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/notifications/{encode_path_param(notification_id)}",
        )
        return True

    async def delete_multiple(self, notification_ids: builtins.list[str]) -> int:
        """
        Delete multiple notifications.

        Args:
            notification_ids: List of notification IDs

        Returns:
            int: Number deleted
        """
        response = await self._http.request(
            "DELETE",
            "/api/v1/notifications",
            json_data={"ids": notification_ids},
        )
        return response.get("count", 0)

    async def delete_all(self) -> int:
        """
        Delete all notifications.

        Returns:
            int: Number deleted
        """
        response = await self._http.request(
            "DELETE",
            "/api/v1/notifications/all",
        )
        return response.get("count", 0)

    async def get_stats(self) -> NotificationStats:
        """
        Get notification statistics.

        Returns:
            NotificationStats: Statistics including unread count

        Example:
            >>> stats = await client.notifications.get_stats()
            >>> print(f"Unread: {stats.unread_count}")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/notifications/stats",
        )
        return NotificationStats(**response)

    # Channel management
    #
    # WARNING: NONE of the six methods
    # below (list_channels/create_channel/get_channel/update_channel/
    # delete_channel/test_channel) have a backend equivalent. There is no
    # `/api/v1/notifications/channels*` route anywhere in
    # or `notifications_stream.py`. The
    # closest real surface is the read-only, differently-shaped
    # `GET /api/v1/alerts/notification-channels` --
    # a distinct resource (alert-threshold notification targets) with no
    # create/update/delete/test operations, and NOT a substitute for a
    # generic pluggable notification-channel CRUD resource. Left unmodified
    # per the phantom-route audit's "no invented routes" constraint; every
    # call below will 404 against the real backend until the corresponding
    # endpoints are implemented server-side.
    async def list_channels(
        self,
        type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> builtins.list[NotificationChannel]:
        """
        List notification channels.

        Args:
            type: Filter by channel type (email, slack, teams, etc.)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[NotificationChannel]: List of channels
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if type:
            params["type"] = type

        response = await self._http.request(
            "GET",
            "/api/v1/notifications/channels",
            params=params,
        )
        return [NotificationChannel(**c) for c in response.get("channels", [])]

    async def create_channel(
        self,
        name: str,
        type: str,
        config: dict[str, Any],
    ) -> NotificationChannel:
        """
        Create notification channel.

        Args:
            name: Channel name
            type: Channel type (email, slack, teams, sms, pagerduty)
            config: Channel configuration

        Returns:
            NotificationChannel: Created channel

        Example:
            >>> channel = await client.notifications.create_channel(
            ...     name="Engineering Alerts",
            ...     type="slack",
            ...     config={
            ...         "webhook_url": "https://hooks.slack.com/...",
            ...         "channel": "#alerts"
            ...     }
            ... )
        """
        response = await self._http.request(
            "POST",
            "/api/v1/notifications/channels",
            json_data={
                "name": name,
                "type": type,
                "config": config,
            },
        )
        return NotificationChannel(**response)

    async def get_channel(self, channel_id: str) -> NotificationChannel:
        """
        Get channel by ID.

        Args:
            channel_id: Channel ID

        Returns:
            NotificationChannel: Channel details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/notifications/channels/{encode_path_param(channel_id)}",
        )
        return NotificationChannel(**response)

    async def update_channel(
        self,
        channel_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> NotificationChannel:
        """
        Update notification channel.

        Args:
            channel_id: Channel ID
            name: New name (optional)
            config: New configuration (optional)
            status: New status (optional)

        Returns:
            NotificationChannel: Updated channel
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if config:
            data["config"] = config
        if status:
            data["status"] = status

        response = await self._http.request(
            "PUT",
            f"/api/v1/notifications/channels/{encode_path_param(channel_id)}",
            json_data=data,
        )
        return NotificationChannel(**response)

    async def delete_channel(self, channel_id: str) -> bool:
        """
        Delete notification channel.

        Args:
            channel_id: Channel ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/notifications/channels/{encode_path_param(channel_id)}",
        )
        return True

    async def test_channel(
        self,
        channel_id: str,
        message: str | None = None,
    ) -> ChannelTestResult:
        """
        Test notification channel.

        Args:
            channel_id: Channel ID
            message: Optional test message

        Returns:
            ChannelTestResult: Test result

        Example:
            >>> result = await client.notifications.test_channel("ch-123")
            >>> if result.delivered:
            ...     print("Channel working!")
        """
        data = {"message": message} if message else {}
        response = await self._http.request(
            "POST",
            f"/api/v1/notifications/channels/{encode_path_param(channel_id)}/test",
            json_data=data if data else None,
        )
        return ChannelTestResult(**response)

    # WARNING: neither get_preferences nor
    # update_preferences below has a backend equivalent -- there is no
    # `/api/v1/notifications/preferences` route, and no
    # agent_failures/budget_warnings/daily_summary/objective_completed/
    # request_escalated preference model anywhere in the backend. Left
    # unmodified per the phantom-route audit's "no invented routes"
    # constraint; both calls will 404 against the real backend until the
    # corresponding endpoints are implemented server-side.
    async def get_preferences(self) -> NotificationPreferences:
        """
        Get user notification preferences.

        Returns:
            NotificationPreferences: Current preferences
        """
        response = await self._http.request(
            "GET",
            "/api/v1/notifications/preferences",
        )
        return NotificationPreferences(**response)

    async def update_preferences(
        self,
        agent_failures: bool | None = None,
        budget_warnings: bool | None = None,
        daily_summary: bool | None = None,
        objective_completed: bool | None = None,
        request_escalated: bool | None = None,
    ) -> NotificationPreferences:
        """
        Update notification preferences.

        Args:
            agent_failures: Notify on agent failures
            budget_warnings: Notify on budget warnings
            daily_summary: Send daily summary
            objective_completed: Notify on objective completion
            request_escalated: Notify on request escalation

        Returns:
            NotificationPreferences: Updated preferences
        """
        data: dict[str, Any] = {}
        if agent_failures is not None:
            data["agentFailures"] = agent_failures
        if budget_warnings is not None:
            data["budgetWarnings"] = budget_warnings
        if daily_summary is not None:
            data["dailySummary"] = daily_summary
        if objective_completed is not None:
            data["objectiveCompleted"] = objective_completed
        if request_escalated is not None:
            data["requestEscalated"] = request_escalated

        response = await self._http.request(
            "PUT",
            "/api/v1/notifications/preferences",
            json_data=data,
        )
        return NotificationPreferences(**response)
