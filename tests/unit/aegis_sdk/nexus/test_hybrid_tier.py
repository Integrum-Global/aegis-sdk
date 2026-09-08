"""Comprehensive tests for Nexus Hybrid Tier deployment module.

Tests cover:
- HybridChannel enum (3 tests)
- HybridChannelConfig (3 tests)
- HybridConfig (8 tests)
- HybridWorkflowConfig (3 tests)
- HybridWorkflowRegistration (5 tests)
- HybridSession (4 tests)
- HybridExecutionResult (3 tests)
- HybridSessionManager (5 tests)
- HybridTierDeployer (12 tests)
- deploy() function (4 tests)

Total: 50 tests
"""

import time
from datetime import datetime

import pytest

from aegis_sdk.nexus.hybrid_tier import (
    HybridChannel,
    HybridChannelConfig,
    HybridConfig,
    HybridExecutionResult,
    HybridSession,
    HybridSessionManager,
    HybridTierDeployer,
    HybridWorkflowConfig,
    HybridWorkflowRegistration,
    deploy,
)

# ==============================================================================
# HybridChannel Tests (3 tests)
# ==============================================================================


class TestHybridChannel:
    """Tests for HybridChannel enum."""

    def test_hybrid_channel_values_exist(self):
        """Test that all expected channel values exist."""
        assert HybridChannel.API is not None
        assert HybridChannel.CLI is not None
        assert HybridChannel.MCP is not None

    def test_hybrid_channel_from_string_valid(self):
        """Test from_string with valid values."""
        assert HybridChannel.from_string("api") == HybridChannel.API
        assert HybridChannel.from_string("rest") == HybridChannel.API
        assert HybridChannel.from_string("cli") == HybridChannel.CLI
        assert HybridChannel.from_string("command") == HybridChannel.CLI
        assert HybridChannel.from_string("mcp") == HybridChannel.MCP

    def test_hybrid_channel_from_strings(self):
        """Test from_strings with list of values."""
        channels = HybridChannel.from_strings(["api", "cli"])
        assert HybridChannel.API in channels
        assert HybridChannel.CLI in channels
        assert HybridChannel.MCP not in channels


# ==============================================================================
# HybridChannelConfig Tests (3 tests)
# ==============================================================================


class TestHybridChannelConfig:
    """Tests for HybridChannelConfig dataclass."""

    def test_channel_config_defaults(self):
        """Test HybridChannelConfig default values."""
        config = HybridChannelConfig(channel=HybridChannel.API)
        assert config.enabled is True
        assert config.host == "0.0.0.0"
        assert config.auth_required is False

    def test_channel_config_valid(self):
        """Test valid HybridChannelConfig."""
        config = HybridChannelConfig(
            channel=HybridChannel.API,
            port=8080,
            auth_required=True,
            rate_limit=100,
        )
        errors = config.validate()
        assert errors == []

    def test_channel_config_invalid(self):
        """Test HybridChannelConfig validation."""
        config = HybridChannelConfig(
            channel=HybridChannel.API,
            port=99999,
            rate_limit=-5,
        )
        errors = config.validate()
        assert any("port must be between" in e for e in errors)
        assert any("rate_limit must be >= 1" in e for e in errors)


# ==============================================================================
# HybridConfig Tests (8 tests)
# ==============================================================================


class TestHybridConfig:
    """Tests for HybridConfig dataclass."""

    def test_hybrid_config_defaults(self):
        """Test HybridConfig default values."""
        config = HybridConfig()
        assert config.name == "nexus-hybrid"
        assert config.channels == ["api", "cli", "mcp"]
        assert config.port == 8000
        assert config.session_enabled is True

    def test_hybrid_config_custom_channels(self):
        """Test HybridConfig with custom channels."""
        config = HybridConfig(channels=["api", "cli"])
        enabled = config.get_enabled_channels()
        assert HybridChannel.API in enabled
        assert HybridChannel.CLI in enabled
        assert HybridChannel.MCP not in enabled

    def test_hybrid_config_valid(self):
        """Test valid HybridConfig."""
        config = HybridConfig(
            name="my-hybrid",
            channels=["api", "cli"],
            port=8080,
        )
        errors = config.validate()
        assert errors == []

    def test_hybrid_config_invalid(self):
        """Test HybridConfig validation."""
        config = HybridConfig(
            name="",
            channels=[],
            session_ttl_s=-1,
        )
        errors = config.validate()
        assert any("name is required" in e for e in errors)
        assert any("at least one channel" in e for e in errors)
        assert any("session_ttl_s must be >= 0" in e for e in errors)

    def test_hybrid_config_invalid_channel(self):
        """Test HybridConfig with invalid channel name raises error."""
        # Invalid channel raises ValueError during __post_init__
        with pytest.raises(ValueError, match="Invalid channel"):
            HybridConfig(channels=["api", "invalid"])

    def test_hybrid_config_is_channel_enabled(self):
        """Test is_channel_enabled method."""
        config = HybridConfig(channels=["api", "cli"])
        assert config.is_channel_enabled(HybridChannel.API) is True
        assert config.is_channel_enabled(HybridChannel.CLI) is True
        assert config.is_channel_enabled(HybridChannel.MCP) is False

    def test_hybrid_config_factory_methods(self):
        """Test factory methods for common configurations."""
        api_cli = HybridConfig.api_cli_only()
        assert "api" in api_cli.channels
        assert "cli" in api_cli.channels
        assert "mcp" not in api_cli.channels

        api_mcp = HybridConfig.api_mcp_only()
        assert "api" in api_mcp.channels
        assert "mcp" in api_mcp.channels
        assert "cli" not in api_mcp.channels

        cli_only = HybridConfig.cli_only()
        assert cli_only.channels == ["cli"]

    def test_hybrid_config_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        original = HybridConfig(
            name="test-config",
            channels=["api", "cli"],
            port=9000,
        )
        data = original.to_dict()
        restored = HybridConfig.from_dict(data)

        assert restored.name == original.name
        assert restored.channels == original.channels
        assert restored.port == original.port


# ==============================================================================
# HybridWorkflowConfig Tests (3 tests)
# ==============================================================================


class TestHybridWorkflowConfig:
    """Tests for HybridWorkflowConfig dataclass."""

    def test_workflow_config_defaults(self):
        """Test HybridWorkflowConfig default values."""
        config = HybridWorkflowConfig()
        assert config.channels is None
        assert config.api_config == {}

    def test_workflow_config_uses_defaults(self):
        """Test get_enabled_channels uses defaults when channels is None."""
        config = HybridWorkflowConfig()
        default_channels = {HybridChannel.API, HybridChannel.CLI}
        enabled = config.get_enabled_channels(default_channels)
        assert enabled == default_channels

    def test_workflow_config_overrides_defaults(self):
        """Test get_enabled_channels overrides with custom channels."""
        config = HybridWorkflowConfig(channels=["api"])
        default_channels = {HybridChannel.API, HybridChannel.CLI, HybridChannel.MCP}
        enabled = config.get_enabled_channels(default_channels)
        assert enabled == {HybridChannel.API}


# ==============================================================================
# HybridWorkflowRegistration Tests (5 tests)
# ==============================================================================


class TestHybridWorkflowRegistration:
    """Tests for HybridWorkflowRegistration dataclass."""

    def test_registration_defaults(self):
        """Test HybridWorkflowRegistration default values."""
        reg = HybridWorkflowRegistration(
            name="test",
            handler=lambda x: x,
        )
        assert reg.version == "1.0.0"
        assert reg.timeout_s == 300

    def test_registration_valid(self):
        """Test valid HybridWorkflowRegistration."""
        reg = HybridWorkflowRegistration(
            name="my-workflow",
            handler=lambda x: x,
            version="1.0.0",
        )
        errors = reg.validate()
        assert errors == []

    def test_registration_invalid(self):
        """Test HybridWorkflowRegistration validation."""
        reg = HybridWorkflowRegistration(
            name="",
            handler="not callable",  # type: ignore
            timeout_s=0,
        )
        errors = reg.validate()
        assert any("name is required" in e for e in errors)
        assert any("handler must be callable" in e for e in errors)
        assert any("timeout_s must be >= 1" in e for e in errors)

    def test_registration_is_channel_enabled(self):
        """Test is_channel_enabled with defaults and overrides."""
        # Workflow with default channels
        reg1 = HybridWorkflowRegistration(name="test1", handler=lambda: None)
        default_channels = {HybridChannel.API, HybridChannel.CLI}
        assert reg1.is_channel_enabled(HybridChannel.API, default_channels)
        assert reg1.is_channel_enabled(HybridChannel.CLI, default_channels)
        assert not reg1.is_channel_enabled(HybridChannel.MCP, default_channels)

        # Workflow with override
        reg2 = HybridWorkflowRegistration(
            name="test2",
            handler=lambda: None,
            workflow_config=HybridWorkflowConfig(channels=["api"]),
        )
        assert reg2.is_channel_enabled(HybridChannel.API, default_channels)
        assert not reg2.is_channel_enabled(HybridChannel.CLI, default_channels)

    def test_registration_with_channel_configs(self):
        """Test workflow with channel-specific configs."""
        reg = HybridWorkflowRegistration(
            name="test",
            handler=lambda: None,
            workflow_config=HybridWorkflowConfig(
                channels=["api", "cli"],
                api_config={"rate_limit": 100},
                cli_config={"timeout": 60},
            ),
        )
        assert reg.workflow_config.api_config["rate_limit"] == 100
        assert reg.workflow_config.cli_config["timeout"] == 60


# ==============================================================================
# HybridSession Tests (4 tests)
# ==============================================================================


class TestHybridSession:
    """Tests for HybridSession dataclass."""

    def test_session_creation(self):
        """Test HybridSession creation."""
        session = HybridSession(id="test-123", user_id="user-1")
        assert session.id == "test-123"
        assert session.user_id == "user-1"

    def test_session_touch(self):
        """Test session touch updates activity."""
        session = HybridSession(id="test")
        original = session.last_activity

        time.sleep(0.01)
        session.touch(HybridChannel.API)

        assert session.last_activity > original
        assert HybridChannel.API in session.channels_used

    def test_session_expiry(self):
        """Test session expiry."""
        session = HybridSession(id="test", ttl_s=1)
        assert session.is_expired() is False

        session.last_activity = time.time() - 2
        assert session.is_expired() is True

    def test_session_data(self):
        """Test session data get/set."""
        session = HybridSession(id="test")
        session.set("key", "value")
        assert session.get("key") == "value"
        assert session.get("missing", "default") == "default"


# ==============================================================================
# HybridExecutionResult Tests (3 tests)
# ==============================================================================


class TestHybridExecutionResult:
    """Tests for HybridExecutionResult dataclass."""

    def test_result_creation(self):
        """Test HybridExecutionResult creation."""
        result = HybridExecutionResult(
            success=True,
            workflow_name="test",
            channel=HybridChannel.API,
            result={"value": 42},
        )
        assert result.success is True
        assert result.channel == HybridChannel.API

    def test_result_duration(self):
        """Test duration calculation."""
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 3)

        result = HybridExecutionResult(
            success=True,
            workflow_name="test",
            channel=HybridChannel.CLI,
            started_at=start,
            completed_at=end,
        )
        assert result.duration_ms == 3000.0

    def test_result_to_dict(self):
        """Test result serialization."""
        result = HybridExecutionResult(
            success=False,
            workflow_name="test",
            channel=HybridChannel.MCP,
            error="Failed",
        )
        data = result.to_dict()
        assert data["success"] is False
        assert data["channel"] == "mcp"
        assert data["error"] == "Failed"


# ==============================================================================
# HybridSessionManager Tests (5 tests)
# ==============================================================================


class TestHybridSessionManager:
    """Tests for HybridSessionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a session manager for testing."""
        return HybridSessionManager(ttl_s=3600, max_sessions=100)

    def test_manager_create(self, manager):
        """Test session creation."""
        session = manager.create(user_id="user-1", channel=HybridChannel.API)
        assert session.id is not None
        assert session.user_id == "user-1"
        assert HybridChannel.API in session.channels_used

    def test_manager_get(self, manager):
        """Test getting session."""
        session = manager.create()
        retrieved = manager.get(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    def test_manager_get_or_create(self, manager):
        """Test get_or_create."""
        session1 = manager.get_or_create()
        session2 = manager.get_or_create(session_id=session1.id)
        assert session2.id == session1.id

        session3 = manager.get_or_create(session_id="nonexistent")
        assert session3.id != session1.id

    def test_manager_delete(self, manager):
        """Test session deletion."""
        session = manager.create()
        assert manager.delete(session.id) is True
        assert manager.get(session.id) is None

    def test_manager_max_sessions(self, manager):
        """Test max sessions limit."""
        small_manager = HybridSessionManager(max_sessions=2)
        small_manager.create()
        small_manager.create()

        with pytest.raises(RuntimeError, match="Maximum sessions"):
            small_manager.create()


# ==============================================================================
# HybridTierDeployer Tests (12 tests)
# ==============================================================================


class TestHybridTierDeployer:
    """Tests for HybridTierDeployer class."""

    @pytest.fixture
    def deployer(self):
        """Create a deployer for testing."""
        return HybridTierDeployer(config=HybridConfig(name="test-hybrid", channels=["api", "cli"]))

    def test_deployer_creation(self, deployer):
        """Test deployer creation."""
        assert deployer.name == "test-hybrid"
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

    def test_deployer_register_with_channel_override(self, deployer):
        """Test workflow registration with channel override."""
        reg = deployer.register_workflow(
            name="api-only",
            handler=lambda x: x,
            channels=["api"],  # Override default
        )
        assert reg.workflow_config.channels == ["api"]

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
            channels=["api"],
        )

        all_workflows = deployer.list_workflows()
        assert len(all_workflows) == 2

        api_workflows = deployer.list_workflows(channel=HybridChannel.API)
        assert len(api_workflows) == 2

        cli_workflows = deployer.list_workflows(channel=HybridChannel.CLI)
        assert len(cli_workflows) == 1  # Only wf1

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_success(self, deployer):
        """Test successful workflow execution."""
        deployer.register_workflow(
            name="double",
            handler=lambda x: {"result": x.get("value", 0) * 2},
        )

        await deployer.start()

        result = await deployer.execute_workflow(
            name="double",
            channel=HybridChannel.API,
            inputs={"value": 21},
        )
        assert result.success is True
        assert result.result["result"] == 42

        await deployer.stop()

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_not_found(self, deployer):
        """Test execution of non-existent workflow."""
        result = await deployer.execute_workflow(
            name="nonexistent",
            channel=HybridChannel.API,
        )
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_deployer_execute_channel_not_running(self, deployer):
        """Test execution on channel that's not running."""
        deployer.register_workflow(name="test", handler=lambda: None)

        result = await deployer.execute_workflow(
            name="test",
            channel=HybridChannel.API,
        )
        assert result.success is False
        assert "not running" in result.error

    @pytest.mark.asyncio
    async def test_deployer_start_and_stop(self, deployer):
        """Test deployer start and stop."""
        await deployer.start()
        assert deployer.is_running
        assert deployer._channel_status[HybridChannel.API]
        assert deployer._channel_status[HybridChannel.CLI]

        await deployer.stop()
        assert not deployer.is_running

    def test_deployer_status(self, deployer):
        """Test deployer status."""
        status = deployer.status()
        assert status["name"] == "test-hybrid"
        assert status["running"] is False

    def test_deployer_health_check(self, deployer):
        """Test health check."""
        health = deployer.health_check()
        assert health["status"] == "unhealthy"


# ==============================================================================
# deploy() Function Tests (4 tests)
# ==============================================================================


class TestDeployFunction:
    """Tests for the deploy() convenience function."""

    def test_deploy_rest_tier(self):
        """Test deploy() creates REST tier."""
        from aegis_sdk.nexus.rest_tier import RESTTierDeployer

        deployer = deploy("rest", workflows={"test": lambda x: x})
        assert isinstance(deployer, RESTTierDeployer)
        assert "test" in deployer

    def test_deploy_platform_tier(self):
        """Test deploy() creates Platform tier."""
        from aegis_sdk.nexus.platform_tier import PlatformTierDeployer

        deployer = deploy("platform", workflows={"test": lambda x: x})
        assert isinstance(deployer, PlatformTierDeployer)
        assert "test" in deployer

    def test_deploy_hybrid_tier(self):
        """Test deploy() creates Hybrid tier."""
        deployer = deploy("hybrid", workflows={"test": lambda x: x})
        assert isinstance(deployer, HybridTierDeployer)
        assert "test" in deployer

    def test_deploy_with_channel_list(self):
        """Test deploy() with comma-separated channel list."""
        deployer = deploy("api,cli", workflows={"test": lambda x: x})
        assert isinstance(deployer, HybridTierDeployer)
        assert HybridChannel.API in deployer.config.get_enabled_channels()
        assert HybridChannel.CLI in deployer.config.get_enabled_channels()
        assert HybridChannel.MCP not in deployer.config.get_enabled_channels()


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestHybridTierIntegration:
    """Integration tests for Hybrid tier."""

    @pytest.mark.asyncio
    async def test_full_hybrid_lifecycle(self):
        """Test complete hybrid lifecycle."""
        # Create with API + CLI only
        config = HybridConfig(
            name="integration-hybrid",
            channels=["api", "cli"],
        )
        deployer = HybridTierDeployer(config=config)

        # Register workflows
        deployer.register_workflow(
            name="add",
            handler=lambda x: {"sum": x.get("a", 0) + x.get("b", 0)},
        )

        # API only workflow
        deployer.register_workflow(
            name="admin",
            handler=lambda x: {"admin": True},
            channels=["api"],
        )

        # Start
        await deployer.start()
        assert deployer.is_running

        # Execute on API
        api_result = await deployer.execute_workflow(
            "add",
            HybridChannel.API,
            {"a": 5, "b": 3},
        )
        assert api_result.success
        assert api_result.result["sum"] == 8

        # Execute on CLI
        cli_result = await deployer.execute_workflow(
            "add",
            HybridChannel.CLI,
            {"a": 2, "b": 4},
        )
        assert cli_result.success
        assert cli_result.result["sum"] == 6

        # Admin on API works
        admin_api = await deployer.execute_workflow("admin", HybridChannel.API)
        assert admin_api.success

        # Admin on CLI fails (not enabled)
        admin_cli = await deployer.execute_workflow("admin", HybridChannel.CLI)
        assert not admin_cli.success
        assert "not enabled" in admin_cli.error

        # Check stats
        stats = deployer.get_stats()
        assert stats["metrics"]["successful_executions"] == 3
        assert stats["metrics"]["failed_executions"] == 1

        # Stop
        await deployer.stop()

    @pytest.mark.asyncio
    async def test_workflow_channel_override(self):
        """Test per-workflow channel overrides."""
        deployer = HybridTierDeployer(config=HybridConfig(channels=["api", "cli", "mcp"]))

        # Workflow available on all channels
        deployer.register_workflow(
            name="public",
            handler=lambda x: {"public": True},
        )

        # Workflow only on API
        deployer.register_workflow(
            name="api-only",
            handler=lambda x: {"api_only": True},
            channels=["api"],
        )

        # Workflow on API and CLI
        deployer.register_workflow(
            name="api-cli",
            handler=lambda x: {"api_cli": True},
            channels=["api", "cli"],
        )

        await deployer.start()

        # Public works on all
        for channel in [HybridChannel.API, HybridChannel.CLI, HybridChannel.MCP]:
            result = await deployer.execute_workflow("public", channel)
            assert result.success, f"Public should work on {channel}"

        # api-only only works on API
        assert (await deployer.execute_workflow("api-only", HybridChannel.API)).success
        assert not (await deployer.execute_workflow("api-only", HybridChannel.CLI)).success
        assert not (await deployer.execute_workflow("api-only", HybridChannel.MCP)).success

        # api-cli works on API and CLI
        assert (await deployer.execute_workflow("api-cli", HybridChannel.API)).success
        assert (await deployer.execute_workflow("api-cli", HybridChannel.CLI)).success
        assert not (await deployer.execute_workflow("api-cli", HybridChannel.MCP)).success

        await deployer.stop()
