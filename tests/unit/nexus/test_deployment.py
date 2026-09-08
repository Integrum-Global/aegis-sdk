"""Comprehensive tests for Nexus v1.1 Tiered Deployment module.

Tests cover:
- DeploymentTier enum (4 tests)
- TierConfig validation (10 tests)
- DeploymentManifest (8 tests)
- DeploymentManager (8+ tests)

Total: 30+ tests
"""

from datetime import datetime

import pytest

from aegis_sdk.nexus.deployment import (
    ChannelConfig,
    DeploymentManager,
    DeploymentManifest,
    DeploymentResult,
    DeploymentTier,
    HealthCheckConfig,
    ScalingPolicy,
    TierConfig,
)

# ==============================================================================
# DeploymentTier Tests (4 tests)
# ==============================================================================


class TestDeploymentTier:
    """Tests for DeploymentTier enum."""

    def test_tier_values_exist(self):
        """Test that all expected tier values exist."""
        assert DeploymentTier.DEVELOPMENT is not None
        assert DeploymentTier.STAGING is not None
        assert DeploymentTier.PRODUCTION is not None

    def test_tier_from_string_valid(self):
        """Test from_string with valid values."""
        assert DeploymentTier.from_string("development") == DeploymentTier.DEVELOPMENT
        assert DeploymentTier.from_string("dev") == DeploymentTier.DEVELOPMENT
        assert DeploymentTier.from_string("staging") == DeploymentTier.STAGING
        assert DeploymentTier.from_string("stage") == DeploymentTier.STAGING
        assert DeploymentTier.from_string("production") == DeploymentTier.PRODUCTION
        assert DeploymentTier.from_string("prod") == DeploymentTier.PRODUCTION

    def test_tier_from_string_case_insensitive(self):
        """Test from_string is case insensitive."""
        assert DeploymentTier.from_string("DEVELOPMENT") == DeploymentTier.DEVELOPMENT
        assert DeploymentTier.from_string("Production") == DeploymentTier.PRODUCTION
        assert DeploymentTier.from_string("STAGING") == DeploymentTier.STAGING

    def test_tier_from_string_invalid_raises(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid deployment tier"):
            DeploymentTier.from_string("invalid")
        with pytest.raises(ValueError, match="Invalid deployment tier"):
            DeploymentTier.from_string("")


# ==============================================================================
# ScalingPolicy Tests (5 tests)
# ==============================================================================


class TestScalingPolicy:
    """Tests for ScalingPolicy dataclass."""

    def test_scaling_policy_defaults(self):
        """Test ScalingPolicy default values."""
        policy = ScalingPolicy()
        assert policy.enabled is False
        assert policy.min_replicas == 1
        assert policy.max_replicas == 10
        assert policy.target_cpu_percent == 70
        assert policy.target_memory_percent == 80

    def test_scaling_policy_valid_config(self):
        """Test ScalingPolicy with valid configuration validates successfully."""
        policy = ScalingPolicy(
            enabled=True,
            min_replicas=2,
            max_replicas=5,
            target_cpu_percent=80,
        )
        errors = policy.validate()
        assert errors == []

    def test_scaling_policy_invalid_replicas(self):
        """Test ScalingPolicy validation catches invalid replica settings."""
        policy = ScalingPolicy(min_replicas=0, max_replicas=10)
        errors = policy.validate()
        assert "min_replicas must be >= 1" in errors

        policy = ScalingPolicy(min_replicas=5, max_replicas=3)
        errors = policy.validate()
        assert "min_replicas cannot exceed max_replicas" in errors

    def test_scaling_policy_invalid_percentages(self):
        """Test ScalingPolicy validation catches invalid percentages."""
        policy = ScalingPolicy(target_cpu_percent=150)
        errors = policy.validate()
        assert "target_cpu_percent must be between 0 and 100" in errors

        policy = ScalingPolicy(target_memory_percent=-10)
        errors = policy.validate()
        assert "target_memory_percent must be between 0 and 100" in errors

    def test_scaling_policy_invalid_cooldowns(self):
        """Test ScalingPolicy validation catches negative cooldowns."""
        policy = ScalingPolicy(scale_up_cooldown_s=-1)
        errors = policy.validate()
        assert "scale_up_cooldown_s must be >= 0" in errors


# ==============================================================================
# HealthCheckConfig Tests (4 tests)
# ==============================================================================


class TestHealthCheckConfig:
    """Tests for HealthCheckConfig dataclass."""

    def test_health_check_defaults(self):
        """Test HealthCheckConfig default values."""
        config = HealthCheckConfig()
        assert config.enabled is True
        assert config.interval_s == 30
        assert config.timeout_s == 10
        assert config.path == "/health"

    def test_health_check_valid_config(self):
        """Test HealthCheckConfig with valid configuration."""
        config = HealthCheckConfig(
            interval_s=60,
            timeout_s=30,
            unhealthy_threshold=5,
            path="/healthz",
        )
        errors = config.validate()
        assert errors == []

    def test_health_check_invalid_timing(self):
        """Test HealthCheckConfig validation catches invalid timing."""
        config = HealthCheckConfig(interval_s=10, timeout_s=15)
        errors = config.validate()
        assert "timeout_s must be less than interval_s" in errors

    def test_health_check_invalid_path(self):
        """Test HealthCheckConfig validation catches invalid path."""
        config = HealthCheckConfig(path="health")
        errors = config.validate()
        assert "path must start with '/'" in errors


# ==============================================================================
# ChannelConfig Tests (4 tests)
# ==============================================================================


class TestChannelConfig:
    """Tests for ChannelConfig dataclass."""

    def test_channel_config_defaults(self):
        """Test ChannelConfig default values."""
        config = ChannelConfig(name="api")
        assert config.enabled is True
        assert config.auth_required is False

    def test_channel_config_factory_methods(self):
        """Test ChannelConfig factory methods create proper defaults."""
        api = ChannelConfig.api_default()
        assert api.name == "api"
        assert api.port == 8000
        assert api.auth_required is True

        cli = ChannelConfig.cli_default()
        assert cli.name == "cli"
        assert cli.port is None

        mcp = ChannelConfig.mcp_default()
        assert mcp.name == "mcp"
        assert mcp.port == 3001

    def test_channel_config_valid(self):
        """Test ChannelConfig validation with valid config."""
        config = ChannelConfig(name="api", port=8080, rate_limit=200)
        errors = config.validate()
        assert errors == []

    def test_channel_config_invalid(self):
        """Test ChannelConfig validation catches invalid settings."""
        config = ChannelConfig(name="invalid_channel")
        errors = config.validate()
        assert len(errors) == 1
        assert "Invalid channel name" in errors[0]

        config = ChannelConfig(name="api", port=99999)
        errors = config.validate()
        assert "port must be between 1 and 65535" in errors[0]


# ==============================================================================
# TierConfig Validation Tests (10 tests)
# ==============================================================================


class TestTierConfig:
    """Tests for TierConfig dataclass."""

    def test_tier_config_defaults(self):
        """Test TierConfig default values."""
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT)
        assert config.replicas == 1
        assert config.memory_mb == 512
        assert config.cpu_cores == 0.5

    def test_tier_config_initializes_default_channels(self):
        """Test TierConfig initializes all three channels by default."""
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT)
        assert "api" in config.channels
        assert "cli" in config.channels
        assert "mcp" in config.channels

    def test_tier_config_valid_development(self):
        """Test valid development tier configuration."""
        config = TierConfig(
            tier=DeploymentTier.DEVELOPMENT,
            replicas=1,
            memory_mb=256,
            cpu_cores=0.25,
        )
        errors = config.validate()
        # Development can have warnings about replicas but shouldn't have errors
        blocking_errors = [e for e in errors if "must be" in e]
        assert blocking_errors == []

    def test_tier_config_valid_production(self):
        """Test valid production tier configuration."""
        config = TierConfig.production_default()
        errors = config.validate()
        assert errors == []

    def test_tier_config_invalid_replicas(self):
        """Test TierConfig validation catches invalid replicas."""
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT, replicas=0)
        errors = config.validate()
        assert "replicas must be >= 1" in errors

    def test_tier_config_invalid_memory(self):
        """Test TierConfig validation catches invalid memory."""
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT, memory_mb=64)
        errors = config.validate()
        assert "memory_mb must be >= 128" in errors

    def test_tier_config_invalid_cpu(self):
        """Test TierConfig validation catches invalid CPU."""
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT, cpu_cores=0.01)
        errors = config.validate()
        assert "cpu_cores must be >= 0.1" in errors

    def test_tier_config_scaling_validation(self):
        """Test TierConfig validates scaling configuration."""
        config = TierConfig(
            tier=DeploymentTier.STAGING,
            replicas=5,
            scaling=ScalingPolicy(enabled=True, min_replicas=3, max_replicas=2),
        )
        errors = config.validate()
        assert any("min_replicas cannot exceed max_replicas" in e for e in errors)

    def test_tier_config_production_requirements(self):
        """Test TierConfig enforces production requirements."""
        # Production with 1 replica should warn
        config = TierConfig(tier=DeploymentTier.PRODUCTION, replicas=1)
        # Disable auth on all channels
        for channel in config.channels.values():
            channel.auth_required = False
        errors = config.validate()
        assert any("production tier should have replicas >= 2" in e for e in errors)
        assert any("auth_required" in e for e in errors)

    def test_tier_config_channel_management(self):
        """Test TierConfig channel enable/disable methods."""
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT)

        # Disable API channel
        config.disable_channel("api")
        assert config.get_channel("api").enabled is False

        # Re-enable API channel
        config.enable_channel("api")
        assert config.get_channel("api").enabled is True


# ==============================================================================
# DeploymentManifest Tests (8 tests)
# ==============================================================================


class TestDeploymentManifest:
    """Tests for DeploymentManifest dataclass."""

    def test_manifest_creation(self):
        """Test DeploymentManifest creation with basic fields."""
        manifest = DeploymentManifest(name="my-app", version="1.0.0")
        assert manifest.name == "my-app"
        assert manifest.version == "1.0.0"
        assert manifest.channels == ["api", "cli", "mcp"]

    def test_manifest_add_and_get_tier(self):
        """Test adding and retrieving tier configurations."""
        manifest = DeploymentManifest(name="my-app", version="1.0.0")

        config = TierConfig(tier=DeploymentTier.STAGING, replicas=2)
        manifest.add_tier(config)

        retrieved = manifest.get_config(DeploymentTier.STAGING)
        assert retrieved.replicas == 2

    def test_manifest_get_config_returns_default_for_missing(self):
        """Test get_config returns appropriate defaults for missing tiers."""
        manifest = DeploymentManifest(name="my-app", version="1.0.0")

        dev_config = manifest.get_config(DeploymentTier.DEVELOPMENT)
        assert dev_config.tier == DeploymentTier.DEVELOPMENT

        prod_config = manifest.get_config(DeploymentTier.PRODUCTION)
        assert prod_config.tier == DeploymentTier.PRODUCTION
        assert prod_config.replicas >= 2  # Production default

    def test_manifest_has_and_remove_tier(self):
        """Test has_tier and remove_tier methods."""
        manifest = DeploymentManifest(name="my-app", version="1.0.0")
        manifest.add_tier(TierConfig(tier=DeploymentTier.STAGING))

        assert manifest.has_tier(DeploymentTier.STAGING) is True
        assert manifest.has_tier(DeploymentTier.PRODUCTION) is False

        removed = manifest.remove_tier(DeploymentTier.STAGING)
        assert removed is True
        assert manifest.has_tier(DeploymentTier.STAGING) is False

    def test_manifest_validation_valid(self):
        """Test manifest validation with valid configuration."""
        manifest = DeploymentManifest(name="my-app", version="1.0.0")
        manifest.add_tier(TierConfig.production_default())
        errors = manifest.validate()
        assert errors == []

    def test_manifest_validation_invalid_name(self):
        """Test manifest validation catches invalid names."""
        manifest = DeploymentManifest(name="", version="1.0.0")
        errors = manifest.validate()
        assert "name is required" in errors

        manifest = DeploymentManifest(name="invalid name with spaces", version="1.0.0")
        errors = manifest.validate()
        assert any("alphanumeric" in e for e in errors)

    def test_manifest_to_dict_and_from_dict(self):
        """Test manifest serialization and deserialization."""
        original = DeploymentManifest(name="my-app", version="2.0.0")
        original.add_tier(
            TierConfig(
                tier=DeploymentTier.STAGING,
                replicas=3,
                memory_mb=1024,
            )
        )

        data = original.to_dict()
        restored = DeploymentManifest.from_dict(data)

        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.has_tier(DeploymentTier.STAGING)
        assert restored.get_config(DeploymentTier.STAGING).replicas == 3

    def test_manifest_get_enabled_channels(self):
        """Test get_enabled_channels method."""
        manifest = DeploymentManifest(name="my-app", version="1.0.0")
        config = TierConfig(tier=DeploymentTier.DEVELOPMENT)
        config.disable_channel("mcp")
        manifest.add_tier(config)

        enabled = manifest.get_enabled_channels(DeploymentTier.DEVELOPMENT)
        assert "api" in enabled
        assert "cli" in enabled
        assert "mcp" not in enabled


# ==============================================================================
# DeploymentResult Tests (3 tests)
# ==============================================================================


class TestDeploymentResult:
    """Tests for DeploymentResult dataclass."""

    def test_result_creation(self):
        """Test DeploymentResult creation."""
        result = DeploymentResult(
            success=True,
            tier=DeploymentTier.STAGING,
            version="1.0.0",
            replicas=2,
        )
        assert result.success is True
        assert result.tier == DeploymentTier.STAGING
        assert result.replicas == 2

    def test_result_duration_calculation(self):
        """Test DeploymentResult duration calculation."""
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 1, 30)

        result = DeploymentResult(
            success=True,
            tier=DeploymentTier.STAGING,
            version="1.0.0",
            replicas=2,
            started_at=start,
            completed_at=end,
        )
        assert result.duration_seconds == 90.0

    def test_result_to_dict(self):
        """Test DeploymentResult serialization."""
        result = DeploymentResult(
            success=True,
            tier=DeploymentTier.PRODUCTION,
            version="1.0.0",
            replicas=3,
            endpoints={"api": "http://localhost:8000"},
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["tier"] == "production"
        assert data["replicas"] == 3
        assert "api" in data["endpoints"]


# ==============================================================================
# DeploymentManager Tests (8 tests)
# ==============================================================================


class TestDeploymentManager:
    """Tests for DeploymentManager class."""

    @pytest.fixture
    def manifest(self):
        """Create a basic deployment manifest for testing."""
        manifest = DeploymentManifest(name="test-app", version="1.0.0")
        manifest.add_tier(TierConfig.development_default())
        manifest.add_tier(TierConfig.staging_default())
        manifest.add_tier(TierConfig.production_default())
        return manifest

    @pytest.fixture
    def manager(self, manifest):
        """Create a deployment manager for testing."""
        return DeploymentManager(manifest)

    @pytest.mark.asyncio
    async def test_deploy_success(self, manager):
        """Test successful deployment."""
        result = await manager.deploy(DeploymentTier.STAGING)
        assert result.success is True
        assert result.tier == DeploymentTier.STAGING
        assert result.replicas > 0
        assert result.deployment_id is not None

    @pytest.mark.asyncio
    async def test_deploy_dry_run(self, manager):
        """Test deployment dry run."""
        result = await manager.deploy(DeploymentTier.PRODUCTION, dry_run=True)
        assert result.success is True
        assert "dry_run" in result.warnings[0]
        # Should not be marked as deployed
        assert not manager.is_deployed(DeploymentTier.PRODUCTION)

    @pytest.mark.asyncio
    async def test_deploy_with_invalid_config(self):
        """Test deployment fails with invalid configuration."""
        manifest = DeploymentManifest(name="", version="")  # Invalid
        manager = DeploymentManager(manifest)

        result = await manager.deploy(DeploymentTier.DEVELOPMENT)
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_scale_deployment(self, manager):
        """Test scaling an existing deployment."""
        # First deploy
        await manager.deploy(DeploymentTier.STAGING)

        # Then scale
        result = await manager.scale(DeploymentTier.STAGING, replicas=3)
        assert result.success is True
        assert result.replicas == 3

    @pytest.mark.asyncio
    async def test_scale_non_existent_fails(self, manager):
        """Test scaling a non-existent deployment fails."""
        result = await manager.scale(DeploymentTier.PRODUCTION, replicas=5)
        assert result.success is False
        assert "No active deployment" in result.errors[0]

    @pytest.mark.asyncio
    async def test_rollback_deployment(self, manager):
        """Test rolling back a deployment."""
        await manager.deploy(DeploymentTier.STAGING)

        result = await manager.rollback(DeploymentTier.STAGING, version="0.9.0")
        assert result.success is True
        assert result.version == "0.9.0"
        assert any("Rolled back" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_get_deployment_status(self, manager):
        """Test getting deployment status."""
        await manager.deploy(DeploymentTier.STAGING)

        deployment = manager.get_deployment(DeploymentTier.STAGING)
        assert deployment is not None
        assert deployment.success is True

        # Non-existent tier
        assert manager.get_deployment(DeploymentTier.PRODUCTION) is None

    @pytest.mark.asyncio
    async def test_undeploy(self, manager):
        """Test undeploying from a tier."""
        await manager.deploy(DeploymentTier.STAGING)
        assert manager.is_deployed(DeploymentTier.STAGING) is True

        removed = await manager.undeploy(DeploymentTier.STAGING)
        assert removed is True
        assert manager.is_deployed(DeploymentTier.STAGING) is False

    @pytest.mark.asyncio
    async def test_get_status_summary(self, manager):
        """Test getting status summary of all deployments."""
        await manager.deploy(DeploymentTier.DEVELOPMENT)
        await manager.deploy(DeploymentTier.STAGING)

        summary = manager.get_status_summary()
        assert summary["manifest"]["name"] == "test-app"
        assert "development" in summary["deployments"]
        assert "staging" in summary["deployments"]
        assert summary["total_replicas"] > 0

    @pytest.mark.asyncio
    async def test_deployment_hooks(self, manager):
        """Test deployment lifecycle hooks."""
        pre_deploy_called = []
        post_deploy_called = []

        def pre_hook(tier, config):
            pre_deploy_called.append(tier)

        def post_hook(tier, result):
            post_deploy_called.append(tier)

        manager.register_hook("pre_deploy", pre_hook)
        manager.register_hook("post_deploy", post_hook)

        await manager.deploy(DeploymentTier.STAGING)

        assert DeploymentTier.STAGING in pre_deploy_called
        assert DeploymentTier.STAGING in post_deploy_called

    def test_register_invalid_hook_raises(self, manager):
        """Test registering an invalid hook event raises ValueError."""
        with pytest.raises(ValueError, match="Invalid hook event"):
            manager.register_hook("invalid_event", lambda: None)


# ==============================================================================
# Integration Tests (Combined functionality)
# ==============================================================================


class TestDeploymentIntegration:
    """Integration tests for deployment module."""

    @pytest.mark.asyncio
    async def test_full_deployment_lifecycle(self):
        """Test complete deployment lifecycle: deploy -> scale -> rollback."""
        # Create manifest
        manifest = DeploymentManifest(name="lifecycle-app", version="1.0.0")
        manifest.add_tier(
            TierConfig(
                tier=DeploymentTier.STAGING,
                replicas=2,
                scaling=ScalingPolicy(enabled=True, min_replicas=1, max_replicas=5),
            )
        )

        manager = DeploymentManager(manifest)

        # Deploy
        deploy_result = await manager.deploy(DeploymentTier.STAGING)
        assert deploy_result.success is True
        assert deploy_result.replicas == 2

        # Scale up
        scale_result = await manager.scale(DeploymentTier.STAGING, replicas=4)
        assert scale_result.success is True
        assert scale_result.replicas == 4

        # Rollback
        rollback_result = await manager.rollback(DeploymentTier.STAGING, "0.9.0")
        assert rollback_result.success is True

        # Undeploy
        await manager.undeploy(DeploymentTier.STAGING)
        assert not manager.is_deployed(DeploymentTier.STAGING)

    def test_default_tier_configurations(self):
        """Test all default tier configurations are valid."""
        dev = TierConfig.development_default()
        staging = TierConfig.staging_default()
        prod = TierConfig.production_default()

        assert dev.validate() == []  # Development can have warnings
        assert staging.validate() == []
        assert prod.validate() == []
