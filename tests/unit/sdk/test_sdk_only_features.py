"""
Unit tests for SDK-only features.

Tests methods that are only available via SDK (no UI):
- Agent versioning (create)
- Agent contexts (update)
- Pool timer operations (extend_timeout, cancel_timeout)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.core.agents import AgentContextsModule, AgentVersionsModule
from aegis_sdk.modules.pools import PoolsModule


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


# =============================================================================
# Agent Versions Module Tests
# =============================================================================


@pytest.fixture
def versions_module(mock_http):
    """Create AgentVersionsModule with mock HTTP client."""
    return AgentVersionsModule(mock_http)


def make_version_response():
    """Create version response."""
    return {
        "id": "ver-123",
        "agent_id": "agent-456",
        "version_number": 3,
        "config_snapshot": {
            "name": "My Agent",
            "model_id": "gpt-4",
            "system_prompt": "You are helpful",
        },
        "changelog": "Updated system prompt",
        "created_by": "user-789",
        "created_at": "2024-01-15T10:00:00Z",
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentVersionsCreate:
    """Test version creation (SDK-only)."""

    async def test_create_version(self, mock_http, versions_module):
        """create() should create version snapshot."""
        mock_http.request = AsyncMock(return_value=make_version_response())

        result = await versions_module.create(
            agent_id="agent-456",
            changelog="Updated system prompt",
        )

        assert result["version_number"] == 3
        assert result["changelog"] == "Updated system prompt"
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/agents/agent-456/versions",
            json_data={"changelog": "Updated system prompt"},
        )

    async def test_create_version_no_changelog(self, mock_http, versions_module):
        """create() should work without changelog."""
        mock_http.request = AsyncMock(return_value=make_version_response())

        await versions_module.create(agent_id="agent-456")

        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/agents/agent-456/versions",
            json_data=None,
        )


# =============================================================================
# Agent Contexts Module Tests
# =============================================================================


@pytest.fixture
def contexts_module(mock_http):
    """Create AgentContextsModule with mock HTTP client."""
    return AgentContextsModule(mock_http)


def make_context_response():
    """Create context response."""
    return {
        "id": "ctx-123",
        "agent_id": "agent-456",
        "name": "System Context",
        "content_type": "text",
        "content": "You are an assistant for Acme Corp.",
        "is_active": True,
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T12:00:00Z",
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentContextsUpdate:
    """Test context update (SDK-only)."""

    async def test_update_context_name(self, mock_http, contexts_module):
        """update() should update context name."""
        mock_http.request = AsyncMock(return_value=make_context_response())

        result = await contexts_module.update(
            agent_id="agent-456",
            context_id="ctx-123",
            name="New Context Name",
        )

        assert result["name"] == "System Context"
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["name"] == "New Context Name"

    async def test_update_context_content(self, mock_http, contexts_module):
        """update() should update context content."""
        mock_http.request = AsyncMock(return_value=make_context_response())

        await contexts_module.update(
            agent_id="agent-456",
            context_id="ctx-123",
            content="Updated context content",
            content_type="text",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["content"] == "Updated context content"
        assert call_args[1]["json_data"]["content_type"] == "text"

    async def test_update_context_active(self, mock_http, contexts_module):
        """update() should toggle active flag."""
        mock_http.request = AsyncMock(return_value=make_context_response())

        await contexts_module.update(
            agent_id="agent-456",
            context_id="ctx-123",
            is_active=False,
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["is_active"] is False


# =============================================================================
# Pool Timer Operations Tests
# =============================================================================


@pytest.fixture
def pools_module(mock_http):
    """Create PoolsModule with mock HTTP client."""
    return PoolsModule(mock_http)


@pytest.mark.unit
@pytest.mark.asyncio
class TestPoolTimerOperations:
    """Test pool timer operations (SDK-only)."""

    async def test_extend_timeout(self, mock_http, pools_module):
        """extend_timeout() should extend task timer."""
        mock_http.request = AsyncMock(
            return_value={
                "success": True,
                "task_id": "task-123",
                "new_timeout_minutes": 60,
                "expires_at": "2024-01-15T11:00:00Z",
            }
        )

        result = await pools_module.extend_timeout(
            task_id="task-123",
            timeout_minutes=60,
        )

        assert result["success"] is True
        assert result["new_timeout_minutes"] == 60
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/escalation/tasks/task-123/reset-timer",
            params={"timeout_minutes": 60},
        )

    async def test_cancel_timeout(self, mock_http, pools_module):
        """cancel_timeout() should cancel task timer."""
        mock_http.request = AsyncMock(return_value={"success": True})

        result = await pools_module.cancel_timeout("task-123")

        assert result is True
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/escalation/tasks/task-123/cancel-timer",
        )

    async def test_cancel_timeout_failure(self, mock_http, pools_module):
        """cancel_timeout() should handle failure."""
        mock_http.request = AsyncMock(return_value={"success": False})

        result = await pools_module.cancel_timeout("task-123")

        assert result is False
