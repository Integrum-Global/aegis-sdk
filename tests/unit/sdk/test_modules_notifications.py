"""
Unit tests for SDK notifications module.

Tests NotificationsModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.modules.notifications import (
    ChannelTestResult,
    Notification,
    NotificationChannel,
    NotificationPreferences,
    NotificationsModule,
    NotificationStats,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def notifications_module(mock_http):
    """Create NotificationsModule with mock HTTP client."""
    return NotificationsModule(mock_http)


def make_notification_response(is_read=False):
    """Create notification response dict."""
    return {
        "id": "notif-123",
        "userId": "user-456",
        "organizationId": "org-789",
        "type": "agent_failure",
        "priority": "high",
        "title": "Agent Failed",
        "message": "Agent 'Customer Bot' failed with error",
        "resourceType": "agent",
        "resourceId": "agent-001",
        "isRead": is_read,
        "createdAt": "2024-01-15T10:00:00Z",
        "metadata": {"error_code": "TIMEOUT"},
    }


def make_stats_response():
    """Create notification stats response."""
    return {
        "unreadCount": 5,
        "totalCount": 25,
        "byType": {"agent_failure": 3, "budget_warning": 2},
    }


def make_channel_response(channel_type="slack"):
    """Create notification channel response."""
    return {
        "id": "ch-123",
        "organizationId": "org-456",
        "name": "Engineering Alerts",
        "type": channel_type,
        "config": {"webhook_url": "https://hooks.slack.com/..."},
        "status": "active",
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_test_result(delivered=True):
    """Create channel test result."""
    return {
        "delivered": delivered,
        "message": "Test notification sent" if delivered else "Delivery failed",
        "latencyMs": 250.0 if delivered else None,
    }


def make_preferences_response():
    """Create preferences response."""
    return {
        "agentFailures": True,
        "budgetWarnings": True,
        "dailySummary": False,
        "objectiveCompleted": True,
        "requestEscalated": True,
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationsModuleCRUD:
    """Test notification CRUD operations."""

    async def test_list_notifications(self, mock_http, notifications_module):
        """list() should return notifications."""
        mock_http.request = AsyncMock(return_value={"records": [make_notification_response()]})

        result = await notifications_module.list()

        assert len(result) == 1
        assert isinstance(result[0], Notification)
        assert result[0].id == "notif-123"
        assert result[0].type == "agent_failure"

    async def test_list_with_filters(self, mock_http, notifications_module):
        """list() should accept filters."""
        mock_http.request = AsyncMock(return_value={"records": []})

        await notifications_module.list(
            types=["agent_failure", "budget_warning"],
            is_read=False,
            priority=["high", "critical"],
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["types"] == "agent_failure,budget_warning"
        assert call_args[1]["params"]["is_read"] == "false"
        assert call_args[1]["params"]["priority"] == "high,critical"

    async def test_get_notification(self, mock_http, notifications_module):
        """get() should return notification details."""
        mock_http.request = AsyncMock(return_value=make_notification_response())

        result = await notifications_module.get("notif-123")

        assert isinstance(result, Notification)
        assert result.id == "notif-123"

    async def test_mark_read(self, mock_http, notifications_module):
        """mark_read() should mark notification as read."""
        mock_http.request = AsyncMock(return_value=make_notification_response(is_read=True))

        result = await notifications_module.mark_read("notif-123")

        assert isinstance(result, Notification)
        assert result.is_read is True
        mock_http.request.assert_called_once_with(
            "PATCH",
            "/api/v1/notifications/notif-123/read",
        )

    async def test_mark_multiple_read(self, mock_http, notifications_module):
        """mark_multiple_read() should mark multiple as read."""
        mock_http.request = AsyncMock(return_value={"count": 3})

        result = await notifications_module.mark_multiple_read(["notif-1", "notif-2", "notif-3"])

        assert result == 3
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["ids"] == ["notif-1", "notif-2", "notif-3"]

    async def test_mark_all_read(self, mock_http, notifications_module):
        """mark_all_read() should mark all as read."""
        mock_http.request = AsyncMock(return_value={"count": 10})

        result = await notifications_module.mark_all_read()

        assert result == 10

    async def test_delete_notification(self, mock_http, notifications_module):
        """delete() should delete notification."""
        mock_http.request = AsyncMock(return_value={})

        result = await notifications_module.delete("notif-123")

        assert result is True

    async def test_delete_multiple(self, mock_http, notifications_module):
        """delete_multiple() should delete multiple."""
        mock_http.request = AsyncMock(return_value={"count": 5})

        result = await notifications_module.delete_multiple(
            ["notif-1", "notif-2", "notif-3", "notif-4", "notif-5"]
        )

        assert result == 5

    async def test_delete_all(self, mock_http, notifications_module):
        """delete_all() should delete all."""
        mock_http.request = AsyncMock(return_value={"count": 25})

        result = await notifications_module.delete_all()

        assert result == 25


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationsModuleStats:
    """Test notification stats operations."""

    async def test_get_stats(self, mock_http, notifications_module):
        """get_stats() should return statistics."""
        mock_http.request = AsyncMock(return_value=make_stats_response())

        result = await notifications_module.get_stats()

        assert isinstance(result, NotificationStats)
        assert result.unread_count == 5
        assert result.total_count == 25
        assert "agent_failure" in result.by_type


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationsModuleChannels:
    """Test notification channel operations."""

    async def test_list_channels(self, mock_http, notifications_module):
        """list_channels() should return channels."""
        mock_http.request = AsyncMock(return_value={"channels": [make_channel_response()]})

        result = await notifications_module.list_channels()

        assert len(result) == 1
        assert isinstance(result[0], NotificationChannel)
        assert result[0].type == "slack"

    async def test_list_channels_by_type(self, mock_http, notifications_module):
        """list_channels() should filter by type."""
        mock_http.request = AsyncMock(return_value={"channels": []})

        await notifications_module.list_channels(type="email")

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["type"] == "email"

    async def test_create_channel(self, mock_http, notifications_module):
        """create_channel() should create channel."""
        mock_http.request = AsyncMock(return_value=make_channel_response())

        result = await notifications_module.create_channel(
            name="Engineering Alerts",
            type="slack",
            config={"webhook_url": "https://hooks.slack.com/..."},
        )

        assert isinstance(result, NotificationChannel)
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json_data"]["name"] == "Engineering Alerts"
        assert call_args[1]["json_data"]["type"] == "slack"

    async def test_get_channel(self, mock_http, notifications_module):
        """get_channel() should return channel details."""
        mock_http.request = AsyncMock(return_value=make_channel_response())

        result = await notifications_module.get_channel("ch-123")

        assert isinstance(result, NotificationChannel)
        assert result.id == "ch-123"

    async def test_update_channel(self, mock_http, notifications_module):
        """update_channel() should update channel."""
        mock_http.request = AsyncMock(return_value=make_channel_response())

        result = await notifications_module.update_channel(
            channel_id="ch-123",
            name="New Name",
            status="paused",
        )

        assert isinstance(result, NotificationChannel)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["name"] == "New Name"

    async def test_delete_channel(self, mock_http, notifications_module):
        """delete_channel() should delete channel."""
        mock_http.request = AsyncMock(return_value={})

        result = await notifications_module.delete_channel("ch-123")

        assert result is True

    async def test_test_channel(self, mock_http, notifications_module):
        """test_channel() should test channel."""
        mock_http.request = AsyncMock(return_value=make_test_result(delivered=True))

        result = await notifications_module.test_channel("ch-123")

        assert isinstance(result, ChannelTestResult)
        assert result.delivered is True
        assert result.latency_ms == 250.0

    async def test_test_channel_with_message(self, mock_http, notifications_module):
        """test_channel() should accept custom message."""
        mock_http.request = AsyncMock(return_value=make_test_result())

        await notifications_module.test_channel(
            channel_id="ch-123",
            message="Custom test message",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["message"] == "Custom test message"


@pytest.mark.unit
@pytest.mark.asyncio
class TestNotificationsModulePreferences:
    """Test notification preferences operations."""

    async def test_get_preferences(self, mock_http, notifications_module):
        """get_preferences() should return preferences."""
        mock_http.request = AsyncMock(return_value=make_preferences_response())

        result = await notifications_module.get_preferences()

        assert isinstance(result, NotificationPreferences)
        assert result.agent_failures is True
        assert result.daily_summary is False

    async def test_update_preferences(self, mock_http, notifications_module):
        """update_preferences() should update preferences."""
        mock_http.request = AsyncMock(return_value=make_preferences_response())

        result = await notifications_module.update_preferences(
            agent_failures=False,
            daily_summary=True,
        )

        assert isinstance(result, NotificationPreferences)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["agentFailures"] is False
        assert call_args[1]["json_data"]["dailySummary"] is True
