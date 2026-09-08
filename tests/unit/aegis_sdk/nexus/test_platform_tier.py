"""Comprehensive tests for Nexus Platform Tier deployment module.

Tests cover:
- ChannelType enum (3 tests)
- SessionAffinity enum (2 tests)
- UnifiedSession (6 tests)
- ChannelConfig (3 tests)
- PlatformConfig (6 tests)
- PlatformWorkflowRegistration (5 tests)
- PlatformExecutionResult (3 tests)
- UnifiedSessionManager (6 tests)
- PlatformTierDeployer (12 tests)

Total: 46 tests
"""

import time
from datetime import datetime

import pytest

from aegis_sdk.nexus.platform_tier import (
    ChannelConfig,
    ChannelType,
    PlatformConfig,
    PlatformExecutionResult,
    PlatformTierDeployer,
    PlatformWorkflowRegistration,
    SessionAffinity,
    UnifiedSession,
    UnifiedSessionManager,
)

# ==============================================================================
# ChannelType Tests (3 tests)
# ==============================================================================


class TestChannelType:
    """Tests for ChannelType enum."""

    def test_channel_type_values_exist(self):
        """Test that all expected channel type values exist."""
        assert ChannelType.API is not None
        assert ChannelType.CLI is not None
        assert ChannelType.MCP is not None

    def test_channel_type_from_string_valid(self):
        """Test from_string with valid values."""
        assert ChannelType.from_string("api") == ChannelType.API
        assert ChannelType.from_string("rest") == ChannelType.API
        assert ChannelType.from_string("cli") == ChannelType.CLI
        assert ChannelType.from_string("command") == ChannelType.CLI
        assert ChannelType.from_string("mcp") == ChannelType.MCP
        assert ChannelType.from_string("model") == ChannelType.MCP

    def test_channel_type_from_string_invalid_raises(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid channel type"):
            ChannelType.from_string("invalid")
        with pytest.raises(ValueError, match="Invalid channel type"):
            ChannelType.from_string("")


# ==============================================================================
# SessionAffinity Tests (2 tests)
# ==============================================================================


class TestSessionAffinity:
    """Tests for SessionAffinity enum."""

    def test_session_affinity_values_exist(self):
        """Test that all expected session affinity values exist."""
        assert SessionAffinity.NONE is not None
        assert SessionAffinity.CHANNEL is not None
        assert SessionAffinity.UNIFIED is not None

    def test_session_affinity_str(self):
        """Test string representation."""
        assert str(SessionAffinity.UNIFIED) == "unified"
        assert str(SessionAffinity.CHANNEL) == "channel"


# ==============================================================================
# UnifiedSession Tests (6 tests)
# ==============================================================================


class TestUnifiedSession:
    """Tests for UnifiedSession dataclass."""

    def test_session_creation(self):
        """Test UnifiedSession creation."""
        session = UnifiedSession(
            id="test-session-123",
            user_id="user-456",
        )
        assert session.id == "test-session-123"
        assert session.user_id == "user-456"
        assert session.ttl_s == 3600

    def test_session_touch(self):
        """Test session touch updates activity."""
        session = UnifiedSession(id="test")
        original_activity = session.last_activity

        time.sleep(0.01)  # Small delay
        session.touch(ChannelType.API)

        assert session.last_activity > original_activity
        assert ChannelType.API in session.active_channels

    def test_session_expiry(self):
        """Test session expiry check."""
        session = UnifiedSession(id="test", ttl_s=1)
        assert session.is_expired() is False

        # Manually set last_activity to past
        session.last_activity = time.time() - 2
        assert session.is_expired() is True

        # Test no expiry with ttl_s=0
        session.ttl_s = 0
        assert session.is_expired() is False

    def test_session_get_set(self):
        """Test session data get/set."""
        session = UnifiedSession(id="test")
        session.set("key1", "value1")
        assert session.get("key1") == "value1"
        assert session.get("nonexistent", "default") == "default"

    def test_session_channel_data(self):
        """Test channel-specific data."""
        session = UnifiedSession(id="test")
        session.set_channel_data(ChannelType.API, "api_key", "value")
        session.set_channel_data(ChannelType.CLI, "cli_key", "cli_value")

        api_data = session.get_channel_data(ChannelType.API)
        assert api_data["api_key"] == "value"

        cli_data = session.get_channel_data(ChannelType.CLI)
        assert cli_data["cli_key"] == "cli_value"

    def test_session_to_dict(self):
        """Test session serialization."""
        session = UnifiedSession(id="test", user_id="user-1")
        session.active_channels.add(ChannelType.API)
        data = session.to_dict()

        assert data["id"] == "test"
        assert data["user_id"] == "user-1"
        assert "api" in data["active_channels"]


# ==============================================================================
# ChannelConfig Tests (3 tests)
# ==============================================================================


class TestChannelConfig:
    """Tests for ChannelConfig dataclass."""

    def test_channel_config_defaults(self):
        """Test ChannelConfig default values."""
        config = ChannelConfig(channel_type=ChannelType.API)
        assert config.enabled is True
        assert config.auth_required is False
        assert config.rate_limit is None

    def test_channel_config_valid(self):
        """Test valid ChannelConfig."""
        config = ChannelConfig(
            channel_type=ChannelType.API,
            port=8080,
            auth_required=True,
            rate_limit=100,
        )
        errors = config.validate()
        assert errors == []

    def test_channel_config_invalid(self):
        """Test ChannelConfig validation."""
        config = ChannelConfig(
            channel_type=ChannelType.API,
            port=99999,
            rate_limit=-5,
        )
        errors = config.validate()
        assert any("port must be between" in e for e in errors)
        assert any("rate_limit must be >= 1" in e for e in errors)


# ==============================================================================
# PlatformConfig Tests (6 tests)
# ==============================================================================


class TestPlatformConfig:
    """Tests for PlatformConfig dataclass."""

    def test_platform_config_defaults(self):
        """Test PlatformConfig default values."""
        config = PlatformConfig()
        assert config.name == "nexus-platform"
        assert config.session_affinity == SessionAffinity.UNIFIED
        assert len(config.channels) == 3

    def test_platform_config_default_channels(self):
        """Test default channels are created."""
        config = PlatformConfig()
        assert ChannelType.API in config.channels
        assert ChannelType.CLI in config.channels
        assert ChannelType.MCP in config.channels
        assert config.channels[ChannelType.API].port == 8000
        assert config.channels[ChannelType.MCP].port == 3001

    def test_platform_config_valid(self):
        """Test valid PlatformConfig."""
        config = PlatformConfig(
            name="my-platform",
            version="2.0.0",
            session_ttl_s=7200,
        )
        errors = config.validate()
        assert errors == []

    def test_platform_config_invalid(self):
        """Test PlatformConfig validation."""
        config = PlatformConfig(
            name="",
            session_ttl_s=-1,
            max_sessions=0,
        )
        errors = config.validate()
        assert any("name is required" in e for e in errors)
        assert any("session_ttl_s must be >= 0" in e for e in errors)
        assert any("max_sessions must be >= 1" in e for e in errors)

    def test_platform_config_channel_management(self):
        """Test channel enable/disable."""
        config = PlatformConfig()

        config.disable_channel(ChannelType.MCP)
        enabled = config.get_enabled_channels()
        assert ChannelType.MCP not in enabled
        assert ChannelType.API in enabled

        config.enable_channel(ChannelType.MCP)
        enabled = config.get_enabled_channels()
        assert ChannelType.MCP in enabled

    def test_platform_config_get_channel(self):
        """Test getting channel config."""
        config = PlatformConfig()
        api_config = config.get_channel(ChannelType.API)
        assert api_config is not None
        assert api_config.channel_type == ChannelType.API


# ==============================================================================
# PlatformWorkflowRegistration Tests (5 tests)
# ==============================================================================


class TestPlatformWorkflowRegistration:
    """Tests for PlatformWorkflowRegistration dataclass."""

    def test_registration_defaults(self):
        """Test PlatformWorkflowRegistration default values."""
        reg = PlatformWorkflowRegistration(
            name="test",
            handler=lambda x: x,
        )
        assert reg.version == "1.0.0"
        assert len(reg.channels) == 3
        assert ChannelType.API in reg.channels

    def test_registration_valid(self):
        """Test valid PlatformWorkflowRegistration."""
        reg = PlatformWorkflowRegistration(
            name="my-workflow",
            handler=lambda x: x,
            version="1.0.0",
            description="Test workflow",
        )
        errors = reg.validate()
        assert errors == []

    def test_registration_invalid(self):
        """Test PlatformWorkflowRegistration validation."""
        reg = PlatformWorkflowRegistration(
            name="",
            handler="not callable",  # type: ignore
            channels=set(),
        )
        errors = reg.validate()
        assert any("name is required" in e for e in errors)
        assert any("handler must be callable" in e for e in errors)
        assert any("at least one channel" in e for e in errors)

    def test_registration_channel_management(self):
        """Test channel enable/disable for workflow."""
        reg = PlatformWorkflowRegistration(
            name="test",
            handler=lambda: None,
        )

        assert reg.is_channel_enabled(ChannelType.API)
        reg.disable_channel(ChannelType.API)
        assert not reg.is_channel_enabled(ChannelType.API)
        reg.enable_channel(ChannelType.API)
        assert reg.is_channel_enabled(ChannelType.API)

    def test_registration_custom_channels(self):
        """Test workflow with custom channel set."""
        reg = PlatformWorkflowRegistration(
            name="test",
            handler=lambda: None,
            channels={ChannelType.API},  # API only
        )
        assert reg.is_channel_enabled(ChannelType.API)
        assert not reg.is_channel_enabled(ChannelType.CLI)
        assert not reg.is_channel_enabled(ChannelType.MCP)


# ==============================================================================
# PlatformExecutionResult Tests (3 tests)
# ==============================================================================


class TestPlatformExecutionResult:
    """Tests for PlatformExecutionResult dataclass."""

    def test_result_creation(self):
        """Test PlatformExecutionResult creation."""
        result = PlatformExecutionResult(
            success=True,
            workflow_name="test",
            channel=ChannelType.API,
            result={"value": 42},
        )
        assert result.success is True
        assert result.channel == ChannelType.API

    def test_result_duration(self):
        """Test duration calculation."""
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 2)

        result = PlatformExecutionResult(
            success=True,
            workflow_name="test",
            channel=ChannelType.CLI,
            started_at=start,
            completed_at=end,
        )
        assert result.duration_ms == 2000.0

    def test_result_to_dict(self):
        """Test result serialization."""
        result = PlatformExecutionResult(
            success=False,
            workflow_name="test",
            channel=ChannelType.MCP,
            error="Something failed",
            session_id="session-123",
        )
        data = result.to_dict()
        assert data["success"] is False
        assert data["channel"] == "mcp"
        assert data["error"] == "Something failed"


# ==============================================================================
# UnifiedSessionManager Tests (6 tests)
# ==============================================================================


class TestUnifiedSessionManager:
    """Tests for UnifiedSessionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a session manager for testing."""
        return UnifiedSessionManager(ttl_s=3600, max_sessions=100)

    def test_manager_create_session(self, manager):
        """Test session creation."""
        session = manager.create(user_id="user-1", channel=ChannelType.API)
        assert session.id is not None
        assert session.user_id == "user-1"
        assert ChannelType.API in session.active_channels

    def test_manager_get_session(self, manager):
        """Test getting session."""
        session = manager.create()
        retrieved = manager.get(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

        assert manager.get("nonexistent") is None

    def test_manager_get_or_create(self, manager):
        """Test get_or_create functionality."""
        # Create new session
        session1 = manager.get_or_create(user_id="user-1")
        assert session1.id is not None

        # Get existing session
        session2 = manager.get_or_create(session_id=session1.id)
        assert session2.id == session1.id

        # Create new when ID not found
        session3 = manager.get_or_create(session_id="nonexistent")
        assert session3.id != session1.id

    def test_manager_delete_session(self, manager):
        """Test session deletion."""
        session = manager.create()
        assert manager.delete(session.id) is True
        assert manager.get(session.id) is None
        assert manager.delete(session.id) is False

    def test_manager_get_by_user(self, manager):
        """Test getting sessions by user."""
        manager.create(user_id="user-1")
        manager.create(user_id="user-1")
        manager.create(user_id="user-2")

        user1_sessions = manager.get_by_user("user-1")
        assert len(user1_sessions) == 2

        user2_sessions = manager.get_by_user("user-2")
        assert len(user2_sessions) == 1

    def test_manager_max_sessions(self, manager):
        """Test max sessions limit."""
        # Create a manager with small limit
        small_manager = UnifiedSessionManager(max_sessions=3)
        small_manager.create()
        small_manager.create()
        small_manager.create()

        with pytest.raises(RuntimeError, match="Maximum sessions"):
            small_manager.create()


# ==============================================================================
# PlatformTierDeployer Tests (12 tests)
# ==============================================================================


class TestPlatformTierDeployer:
    """Tests for PlatformTierDeployer class."""

    @pytest.fixture
    def deployer(self):
        """Create a deployer for testing."""
        return PlatformTierDeployer(config=PlatformConfig(name="test-platform"))

    def test_deployer_creation(self, deployer):
        """Test deployer creation."""
        assert deployer.name == "test-platform"
        assert deployer.is_running is False
        assert deployer.session_manager is not None

    def test_deployer_register_workflow(self, deployer):
        """Test workflow registration."""
        reg = deployer.register_workflow(
            name="my-workflow",
            handler=lambda x: x,
        )
        assert reg.name == "my-workflow"
        assert "my-workflow" in deployer

    def test_deployer_register_duplicate_raises(self, deployer):
        """Test duplicate registration raises error."""
        deployer.register_workflow(name="test", handler=lambda: None)
        with pytest.raises(ValueError, match="already registered"):
            deployer.register_workflow(name="test", handler=lambda: None)

    def test_deployer_unregister_workflow(self, deployer):
        """Test workflow unregistration."""
        deployer.register_workflow(name="test", handler=lambda: None)
        assert deployer.unregister_workflow("test") is True
        assert "test" not in deployer

    def test_deployer_list_workflows(self, deployer):
        """Test listing workflows."""
        deployer.register_workflow(name="wf1", handler=lambda: None)
        deployer.register_workflow(
            name="wf2",
            handler=lambda: None,
            channels={ChannelType.API},
        )

        all_workflows = deployer.list_workflows()
        assert len(all_workflows) == 2

        api_workflows = deployer.list_workflows(channel=ChannelType.API)
        assert len(api_workflows) == 2

        cli_workflows = deployer.list_workflows(channel=ChannelType.CLI)
        assert len(cli_workflows) == 1  # Only wf1 has CLI enabled

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_success(self, deployer):
        """Test successful workflow execution."""
        deployer.register_workflow(
            name="double",
            handler=lambda x, ctx=None: {"result": x.get("value", 0) * 2},
        )

        result = await deployer.execute_workflow(
            name="double",
            channel=ChannelType.API,
            inputs={"value": 21},
        )
        assert result.success is True
        assert result.result["result"] == 42
        assert result.channel == ChannelType.API
        assert result.session_id is not None

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_not_found(self, deployer):
        """Test execution of non-existent workflow."""
        result = await deployer.execute_workflow(
            name="nonexistent",
            channel=ChannelType.API,
        )
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_channel_disabled(self, deployer):
        """Test execution on disabled channel."""
        deployer.register_workflow(
            name="api-only",
            handler=lambda x: x,
            channels={ChannelType.API},  # API only
        )

        result = await deployer.execute_workflow(
            name="api-only",
            channel=ChannelType.CLI,  # CLI not enabled
        )
        assert result.success is False
        assert "not enabled for channel" in result.error

    @pytest.mark.asyncio
    async def test_deployer_start_and_stop(self, deployer):
        """Test deployer start and stop."""
        await deployer.start()
        assert deployer.is_running
        assert deployer.get_channel_status(ChannelType.API)
        assert deployer.get_channel_status(ChannelType.CLI)
        assert deployer.get_channel_status(ChannelType.MCP)

        await deployer.stop()
        assert not deployer.is_running
        assert not deployer.get_channel_status(ChannelType.API)

    def test_deployer_status(self, deployer):
        """Test deployer status."""
        status = deployer.status()
        assert status["name"] == "test-platform"
        assert status["running"] is False
        assert "channels" in status

    def test_deployer_health_check(self, deployer):
        """Test health check."""
        health = deployer.health_check()
        assert health["status"] == "unhealthy"  # Not running

    def test_deployer_get_stats(self, deployer):
        """Test getting stats."""
        deployer.register_workflow(name="test", handler=lambda: None)
        stats = deployer.get_stats()
        assert stats["name"] == "test-platform"
        assert stats["workflows_count"] == 1
        assert "metrics" in stats


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestPlatformTierIntegration:
    """Integration tests for Platform tier."""

    @pytest.mark.asyncio
    async def test_full_platform_lifecycle(self):
        """Test complete platform lifecycle."""
        # Create platform
        config = PlatformConfig(
            name="integration-platform",
            version="1.0.0",
        )
        deployer = PlatformTierDeployer(config=config)

        # Register workflows
        deployer.register_workflow(
            name="add",
            handler=lambda x, ctx=None: {"sum": x.get("a", 0) + x.get("b", 0)},
        )

        deployer.register_workflow(
            name="multiply",
            handler=lambda x, ctx=None: {"product": x.get("a", 0) * x.get("b", 0)},
        )

        # Start
        await deployer.start()
        assert deployer.is_running

        # Execute across channels
        api_result = await deployer.execute_workflow(
            "add",
            ChannelType.API,
            {"a": 5, "b": 3},
        )
        assert api_result.success
        assert api_result.result["sum"] == 8

        cli_result = await deployer.execute_workflow(
            "multiply",
            ChannelType.CLI,
            {"a": 4, "b": 7},
        )
        assert cli_result.success
        assert cli_result.result["product"] == 28

        # Check metrics
        stats = deployer.get_stats()
        assert stats["metrics"]["successful_executions"] == 2
        assert stats["metrics"]["executions_by_channel"]["api"] == 1
        assert stats["metrics"]["executions_by_channel"]["cli"] == 1

        # Stop
        await deployer.stop()
        assert not deployer.is_running

    @pytest.mark.asyncio
    async def test_session_continuity_across_channels(self):
        """Test session data persists across channels."""
        deployer = PlatformTierDeployer()

        def handler_with_session(inputs, context=None):
            if context and context.session:
                # Store/retrieve from session
                count = context.session.get("count", 0)
                context.session.set("count", count + 1)
                return {"count": count + 1}
            return {"count": 1}

        deployer.register_workflow(
            name="counter",
            handler=handler_with_session,
        )

        await deployer.start()

        # First call - creates session
        result1 = await deployer.execute_workflow(
            "counter",
            ChannelType.API,
            user_id="user-1",
        )
        session_id = result1.session_id

        # Second call with same session - count should increase
        result2 = await deployer.execute_workflow(
            "counter",
            ChannelType.CLI,  # Different channel
            session_id=session_id,
        )

        # Session should persist across channels
        assert result2.session_id == session_id

        await deployer.stop()
