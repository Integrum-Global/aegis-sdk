"""Tiered deployment configuration for Nexus multi-channel platform.

This module provides comprehensive deployment configuration for deploying
Nexus platforms across development, staging, and production environments
with support for auto-scaling, health checks, and multi-channel orchestration.

Example:
    >>> from aegis_sdk.nexus import DeploymentTier, TierConfig, DeploymentManifest
    >>> manifest = DeploymentManifest(name="my-platform", version="1.0.0")
    >>> manifest.add_tier(TierConfig(tier=DeploymentTier.PRODUCTION, replicas=3))
    >>> manager = DeploymentManager
    >>> result = await manager.deploy(DeploymentTier.PRODUCTION)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class DeploymentTier(Enum):
    """Deployment environment tiers.

    Defines the standard deployment environments for Nexus platforms,
    each with different resource and security requirements.

    Attributes:
        DEVELOPMENT: Local development environment with minimal resources.
        STAGING: Pre-production testing environment.
        PRODUCTION: Live production environment with full resources.
    """

    DEVELOPMENT = auto()
    STAGING = auto()
    PRODUCTION = auto()

    @classmethod
    def from_string(cls, value: str) -> DeploymentTier:
        """Convert string to DeploymentTier.

        Args:
            value: String representation of tier (case-insensitive).

        Returns:
            Corresponding DeploymentTier enum value.

        Raises:
            ValueError: If the string does not match any tier.
        """
        mapping = {
            "development": cls.DEVELOPMENT,
            "dev": cls.DEVELOPMENT,
            "staging": cls.STAGING,
            "stage": cls.STAGING,
            "production": cls.PRODUCTION,
            "prod": cls.PRODUCTION,
        }
        normalized = value.lower().strip()
        if normalized not in mapping:
            valid = ", ".join(sorted(set(mapping.keys())))
            raise ValueError(f"Invalid deployment tier: '{value}'. Valid values: {valid}")
        return mapping[normalized]

    def __str__(self) -> str:
        """Return lowercase tier name."""
        return self.name.lower()


@dataclass
class ScalingPolicy:
    """Auto-scaling policy configuration.

    Defines how the deployment should scale based on resource utilization.

    Attributes:
        enabled: Whether auto-scaling is enabled.
        min_replicas: Minimum number of replicas to maintain.
        max_replicas: Maximum number of replicas to scale to.
        target_cpu_percent: Target CPU utilization for scaling (0-100).
        target_memory_percent: Target memory utilization for scaling (0-100).
        scale_up_cooldown_s: Seconds to wait after scaling up.
        scale_down_cooldown_s: Seconds to wait after scaling down.
    """

    enabled: bool = False
    min_replicas: int = 1
    max_replicas: int = 10
    target_cpu_percent: int = 70
    target_memory_percent: int = 80
    scale_up_cooldown_s: int = 60
    scale_down_cooldown_s: int = 300

    def validate(self) -> list[str]:
        """Validate scaling policy configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []
        if self.min_replicas < 1:
            errors.append("min_replicas must be >= 1")
        if self.max_replicas < 1:
            errors.append("max_replicas must be >= 1")
        if self.min_replicas > self.max_replicas:
            errors.append("min_replicas cannot exceed max_replicas")
        if not 0 <= self.target_cpu_percent <= 100:
            errors.append("target_cpu_percent must be between 0 and 100")
        if not 0 <= self.target_memory_percent <= 100:
            errors.append("target_memory_percent must be between 0 and 100")
        if self.scale_up_cooldown_s < 0:
            errors.append("scale_up_cooldown_s must be >= 0")
        if self.scale_down_cooldown_s < 0:
            errors.append("scale_down_cooldown_s must be >= 0")
        return errors


@dataclass
class HealthCheckConfig:
    """Health check configuration for deployment monitoring.

    Attributes:
        enabled: Whether health checks are enabled.
        interval_s: Seconds between health checks.
        timeout_s: Seconds before health check times out.
        unhealthy_threshold: Consecutive failures before marking unhealthy.
        healthy_threshold: Consecutive successes before marking healthy.
        path: HTTP path for health check endpoint.
        port: Port for health check (None uses service port).
    """

    enabled: bool = True
    interval_s: int = 30
    timeout_s: int = 10
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    path: str = "/health"
    port: int | None = None

    def validate(self) -> list[str]:
        """Validate health check configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []
        if self.interval_s < 1:
            errors.append("interval_s must be >= 1")
        if self.timeout_s < 1:
            errors.append("timeout_s must be >= 1")
        if self.timeout_s >= self.interval_s:
            errors.append("timeout_s must be less than interval_s")
        if self.unhealthy_threshold < 1:
            errors.append("unhealthy_threshold must be >= 1")
        if self.healthy_threshold < 1:
            errors.append("healthy_threshold must be >= 1")
        if not self.path.startswith("/"):
            errors.append("path must start with '/'")
        if self.port is not None and (self.port < 1 or self.port > 65535):
            errors.append("port must be between 1 and 65535")
        return errors


@dataclass
class ChannelConfig:
    """Configuration for a Nexus channel (API, CLI, or MCP).

    Attributes:
        name: Channel name ('api', 'cli', or 'mcp').
        enabled: Whether the channel is enabled.
        port: Port for the channel service.
        rate_limit: Requests per minute limit.
        auth_required: Whether authentication is required.
        custom_config: Additional channel-specific configuration.
    """

    name: str
    enabled: bool = True
    port: int | None = None
    rate_limit: int | None = None
    auth_required: bool = False
    custom_config: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate channel configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []
        valid_channels = {"api", "cli", "mcp"}
        if self.name.lower() not in valid_channels:
            errors.append(f"Invalid channel name: '{self.name}'. Valid: {valid_channels}")
        if self.port is not None and (self.port < 1 or self.port > 65535):
            errors.append(f"port must be between 1 and 65535, got {self.port}")
        if self.rate_limit is not None and self.rate_limit < 1:
            errors.append(f"rate_limit must be >= 1, got {self.rate_limit}")
        return errors

    @classmethod
    def api_default(cls, port: int = 8000) -> ChannelConfig:
        """Create default API channel configuration."""
        return cls(name="api", port=port, rate_limit=100, auth_required=True)

    @classmethod
    def cli_default(cls) -> ChannelConfig:
        """Create default CLI channel configuration."""
        return cls(name="cli", port=None, rate_limit=None, auth_required=False)

    @classmethod
    def mcp_default(cls, port: int = 3001) -> ChannelConfig:
        """Create default MCP channel configuration."""
        return cls(name="mcp", port=port, rate_limit=50, auth_required=True)


@dataclass
class TierConfig:
    """Configuration for a deployment tier.

    Defines resource allocation and behavior for a specific deployment
    environment tier.

    Attributes:
        tier: The deployment tier (DEVELOPMENT, STAGING, PRODUCTION).
        replicas: Number of replicas to deploy.
        memory_mb: Memory allocation per replica in megabytes.
        cpu_cores: CPU cores allocated per replica.
        scaling: Auto-scaling policy configuration.
        health_check: Health check configuration.
        channels: Channel-specific configurations.
        environment: Environment variables to set.
        labels: Labels/tags for the deployment.
        annotations: Annotations for the deployment.
    """

    tier: DeploymentTier
    replicas: int = 1
    memory_mb: int = 512
    cpu_cores: float = 0.5
    scaling: ScalingPolicy = field(default_factory=ScalingPolicy)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    channels: dict[str, ChannelConfig] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default channels if not provided."""
        if not self.channels:
            self.channels = {
                "api": ChannelConfig.api_default(),
                "cli": ChannelConfig.cli_default(),
                "mcp": ChannelConfig.mcp_default(),
            }

    def validate(self) -> list[str]:
        """Validate tier configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        # Basic resource validation
        if self.replicas < 1:
            errors.append("replicas must be >= 1")
        if self.memory_mb < 128:
            errors.append("memory_mb must be >= 128")
        if self.cpu_cores < 0.1:
            errors.append("cpu_cores must be >= 0.1")
        if self.cpu_cores > 128:
            errors.append("cpu_cores must be <= 128")
        if self.memory_mb > 1024 * 1024:  # 1TB
            errors.append("memory_mb must be <= 1048576 (1TB)")

        # Scaling validation
        if self.scaling.enabled:
            scaling_errors = self.scaling.validate()
            errors.extend([f"scaling.{e}" for e in scaling_errors])

            # Check replicas against scaling bounds
            if self.replicas < self.scaling.min_replicas:
                errors.append(
                    f"replicas ({self.replicas}) must be >= "
                    f"scaling.min_replicas ({self.scaling.min_replicas})"
                )
            if self.replicas > self.scaling.max_replicas:
                errors.append(
                    f"replicas ({self.replicas}) must be <= "
                    f"scaling.max_replicas ({self.scaling.max_replicas})"
                )

        # Health check validation
        health_errors = self.health_check.validate()
        errors.extend([f"health_check.{e}" for e in health_errors])

        # Channel validation
        for name, channel in self.channels.items():
            channel_errors = channel.validate()
            errors.extend([f"channels.{name}.{e}" for e in channel_errors])

        # Production-specific validation
        if self.tier == DeploymentTier.PRODUCTION:
            if self.replicas < 2:
                errors.append("production tier should have replicas >= 2")
            if not any(c.auth_required for c in self.channels.values() if c.enabled):
                errors.append("production tier should have auth_required on at least one channel")

        return errors

    def get_channel(self, name: str) -> ChannelConfig | None:
        """Get channel configuration by name.

        Args:
            name: Channel name ('api', 'cli', or 'mcp').

        Returns:
            ChannelConfig if found, None otherwise.
        """
        return self.channels.get(name.lower())

    def enable_channel(self, name: str, config: ChannelConfig | None = None) -> None:
        """Enable a channel with optional custom configuration.

        Args:
            name: Channel name to enable.
            config: Optional custom configuration.
        """
        if config:
            self.channels[name.lower()] = config
        elif name.lower() in self.channels:
            self.channels[name.lower()].enabled = True

    def disable_channel(self, name: str) -> None:
        """Disable a channel.

        Args:
            name: Channel name to disable.
        """
        if name.lower() in self.channels:
            self.channels[name.lower()].enabled = False

    @classmethod
    def development_default(cls) -> TierConfig:
        """Create default development tier configuration."""
        return cls(
            tier=DeploymentTier.DEVELOPMENT,
            replicas=1,
            memory_mb=256,
            cpu_cores=0.25,
            scaling=ScalingPolicy(enabled=False),
            health_check=HealthCheckConfig(interval_s=60),
        )

    @classmethod
    def staging_default(cls) -> TierConfig:
        """Create default staging tier configuration."""
        return cls(
            tier=DeploymentTier.STAGING,
            replicas=2,
            memory_mb=512,
            cpu_cores=0.5,
            scaling=ScalingPolicy(enabled=True, min_replicas=1, max_replicas=4),
            health_check=HealthCheckConfig(interval_s=30),
        )

    @classmethod
    def production_default(cls) -> TierConfig:
        """Create default production tier configuration."""
        config = cls(
            tier=DeploymentTier.PRODUCTION,
            replicas=3,
            memory_mb=1024,
            cpu_cores=1.0,
            scaling=ScalingPolicy(enabled=True, min_replicas=2, max_replicas=10),
            health_check=HealthCheckConfig(interval_s=15, unhealthy_threshold=2),
        )
        # Ensure auth is required on API and MCP in production
        config.channels["api"].auth_required = True
        config.channels["mcp"].auth_required = True
        return config


@dataclass
class DeploymentManifest:
    """Complete deployment specification for a Nexus platform.

    The manifest defines all tier configurations, channels, and metadata
    for deploying a Nexus platform across environments.

    Attributes:
        name: Platform/application name.
        version: Application version string.
        tiers: Configuration for each deployment tier.
        channels: Default channel names to enable.
        metadata: Additional deployment metadata.
        created_at: Manifest creation timestamp.
    """

    name: str
    version: str
    tiers: dict[DeploymentTier, TierConfig] = field(default_factory=dict)
    channels: list[str] = field(default_factory=lambda: ["api", "cli", "mcp"])
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> list[str]:
        """Validate the deployment manifest.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        # Name validation
        if not self.name:
            errors.append("name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append(
                "name must contain only alphanumeric characters, hyphens, and underscores"
            )
        elif len(self.name) > 63:
            errors.append("name must be <= 63 characters")

        # Version validation
        if not self.version:
            errors.append("version is required")

        # Channel validation
        valid_channels = {"api", "cli", "mcp"}
        for channel in self.channels:
            if channel.lower() not in valid_channels:
                errors.append(f"Invalid channel: '{channel}'. Valid: {valid_channels}")

        # Tier validation
        for tier, config in self.tiers.items():
            tier_errors = config.validate()
            errors.extend([f"tiers.{tier.name}.{e}" for e in tier_errors])

        return errors

    def get_config(self, tier: DeploymentTier) -> TierConfig:
        """Get configuration for a specific tier.

        If no configuration exists for the tier, returns a default
        configuration based on the tier type.

        Args:
            tier: The deployment tier to get configuration for.

        Returns:
            TierConfig for the specified tier.
        """
        if tier in self.tiers:
            return self.tiers[tier]

        # Return default configuration based on tier
        defaults = {
            DeploymentTier.DEVELOPMENT: TierConfig.development_default,
            DeploymentTier.STAGING: TierConfig.staging_default,
            DeploymentTier.PRODUCTION: TierConfig.production_default,
        }
        return defaults.get(tier, TierConfig.development_default)()

    def add_tier(self, config: TierConfig) -> None:
        """Add or update a tier configuration.

        Args:
            config: TierConfig to add/update.
        """
        self.tiers[config.tier] = config

    def remove_tier(self, tier: DeploymentTier) -> bool:
        """Remove a tier configuration.

        Args:
            tier: Tier to remove.

        Returns:
            True if tier was removed, False if it didn't exist.
        """
        if tier in self.tiers:
            del self.tiers[tier]
            return True
        return False

    def has_tier(self, tier: DeploymentTier) -> bool:
        """Check if a tier configuration exists.

        Args:
            tier: Tier to check.

        Returns:
            True if tier configuration exists.
        """
        return tier in self.tiers

    def get_enabled_channels(self, tier: DeploymentTier) -> list[str]:
        """Get list of enabled channels for a tier.

        Args:
            tier: Tier to get channels for.

        Returns:
            List of enabled channel names.
        """
        config = self.get_config(tier)
        return [name for name, ch in config.channels.items() if ch.enabled]

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary representation.

        Returns:
            Dictionary representation of the manifest.
        """
        return {
            "name": self.name,
            "version": self.version,
            "channels": self.channels,
            "tiers": {
                str(tier): {
                    "replicas": config.replicas,
                    "memory_mb": config.memory_mb,
                    "cpu_cores": config.cpu_cores,
                    "scaling": {
                        "enabled": config.scaling.enabled,
                        "min_replicas": config.scaling.min_replicas,
                        "max_replicas": config.scaling.max_replicas,
                    },
                }
                for tier, config in self.tiers.items()
            },
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeploymentManifest:
        """Create manifest from dictionary representation.

        Args:
            data: Dictionary containing manifest data.

        Returns:
            DeploymentManifest instance.
        """
        manifest = cls(
            name=data["name"],
            version=data["version"],
            channels=data.get("channels", ["api", "cli", "mcp"]),
            metadata=data.get("metadata", {}),
        )

        # Parse tiers
        for tier_str, tier_data in data.get("tiers", {}).items():
            tier = DeploymentTier.from_string(tier_str)
            scaling_data = tier_data.get("scaling", {})
            config = TierConfig(
                tier=tier,
                replicas=tier_data.get("replicas", 1),
                memory_mb=tier_data.get("memory_mb", 512),
                cpu_cores=tier_data.get("cpu_cores", 0.5),
                scaling=ScalingPolicy(
                    enabled=scaling_data.get("enabled", False),
                    min_replicas=scaling_data.get("min_replicas", 1),
                    max_replicas=scaling_data.get("max_replicas", 10),
                ),
            )
            manifest.add_tier(config)

        return manifest


@dataclass
class DeploymentResult:
    """Result of a deployment operation.

    Attributes:
        success: Whether the deployment succeeded.
        tier: The deployment tier.
        version: The deployed version.
        replicas: Number of replicas deployed.
        endpoints: Channel endpoint URLs.
        errors: List of error messages if failed.
        warnings: List of warning messages.
        deployment_id: Unique deployment identifier.
        started_at: Deployment start timestamp.
        completed_at: Deployment completion timestamp.
    """

    success: bool
    tier: DeploymentTier
    version: str
    replicas: int
    endpoints: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deployment_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Get deployment duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "success": self.success,
            "tier": str(self.tier),
            "version": self.version,
            "replicas": self.replicas,
            "endpoints": self.endpoints,
            "errors": self.errors,
            "warnings": self.warnings,
            "deployment_id": self.deployment_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


class DeploymentManager:
    """Manages deployment operations across tiers.

    The DeploymentManager handles deploying, scaling, and managing
    Nexus platform deployments across different environment tiers.

    Attributes:
        manifest: The deployment manifest to use.

    Example:
        >>> manifest = DeploymentManifest(name="my-app", version="1.0.0")
        >>> manager = DeploymentManager
        >>> result = await manager.deploy(DeploymentTier.STAGING)
    """

    def __init__(self, manifest: DeploymentManifest):
        """Initialize deployment manager.

        Args:
            manifest: Deployment manifest to manage.
        """
        self.manifest = manifest
        self._deployments: dict[DeploymentTier, DeploymentResult] = {}
        self._deployment_hooks: dict[str, list[Callable]] = {
            "pre_deploy": [],
            "post_deploy": [],
            "pre_scale": [],
            "post_scale": [],
        }
        self._deployment_counter = 0

    def _generate_deployment_id(self) -> str:
        """Generate a unique deployment ID."""
        self._deployment_counter += 1
        timestamp = int(time.time())
        return f"{self.manifest.name}-{timestamp}-{self._deployment_counter}"

    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a deployment lifecycle hook.

        Args:
            event: Event name ('pre_deploy', 'post_deploy', 'pre_scale', 'post_scale').
            callback: Callback function to invoke.

        Raises:
            ValueError: If event name is invalid.
        """
        if event not in self._deployment_hooks:
            valid = ", ".join(self._deployment_hooks.keys())
            raise ValueError(f"Invalid hook event: '{event}'. Valid: {valid}")
        self._deployment_hooks[event].append(callback)

    async def _invoke_hooks(self, event: str, **kwargs) -> None:
        """Invoke all registered hooks for an event."""
        for callback in self._deployment_hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(**kwargs)
                else:
                    callback(**kwargs)
            except Exception as e:
                logger.warning("Hook %s failed: %s", event, e)

    async def deploy(
        self,
        tier: DeploymentTier,
        dry_run: bool = False,
    ) -> DeploymentResult:
        """Deploy to specified tier.

        Args:
            tier: The deployment tier to deploy to.
            dry_run: If True, validate without deploying.

        Returns:
            DeploymentResult with deployment outcome.
        """
        started_at = datetime.now(UTC)
        deployment_id = self._generate_deployment_id()
        config = self.manifest.get_config(tier)

        # Validate configuration
        errors = self.manifest.validate()
        tier_errors = config.validate()
        errors.extend(tier_errors)

        if errors:
            return DeploymentResult(
                success=False,
                tier=tier,
                version=self.manifest.version,
                replicas=0,
                errors=errors,
                deployment_id=deployment_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        if dry_run:
            return DeploymentResult(
                success=True,
                tier=tier,
                version=self.manifest.version,
                replicas=config.replicas,
                warnings=["dry_run=True, deployment simulated"],
                deployment_id=deployment_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        # Invoke pre-deploy hooks
        await self._invoke_hooks("pre_deploy", tier=tier, config=config)

        # Simulate deployment (in real implementation, this would
        # interact with Kubernetes, Docker, etc.)
        try:
            endpoints = {}
            for name, channel in config.channels.items():
                if channel.enabled and channel.port:
                    endpoints[name] = f"http://localhost:{channel.port}"

            result = DeploymentResult(
                success=True,
                tier=tier,
                version=self.manifest.version,
                replicas=config.replicas,
                endpoints=endpoints,
                deployment_id=deployment_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

            self._deployments[tier] = result

            # Invoke post-deploy hooks
            await self._invoke_hooks("post_deploy", tier=tier, result=result)

            return result

        except Exception as e:
            logger.error("Deployment failed: %s", e)
            return DeploymentResult(
                success=False,
                tier=tier,
                version=self.manifest.version,
                replicas=0,
                errors=[str(e)],
                deployment_id=deployment_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

    async def scale(
        self,
        tier: DeploymentTier,
        replicas: int,
    ) -> DeploymentResult:
        """Scale deployment to specified replica count.

        Args:
            tier: The deployment tier to scale.
            replicas: Target number of replicas.

        Returns:
            DeploymentResult with scaling outcome.
        """
        started_at = datetime.now(UTC)

        if tier not in self._deployments:
            return DeploymentResult(
                success=False,
                tier=tier,
                version=self.manifest.version,
                replicas=0,
                errors=[f"No active deployment for tier: {tier}"],
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        config = self.manifest.get_config(tier)

        # Validate replica count
        errors = []
        if replicas < 1:
            errors.append("replicas must be >= 1")
        if config.scaling.enabled:
            if replicas < config.scaling.min_replicas:
                errors.append(f"replicas must be >= min_replicas ({config.scaling.min_replicas})")
            if replicas > config.scaling.max_replicas:
                errors.append(f"replicas must be <= max_replicas ({config.scaling.max_replicas})")

        if errors:
            return DeploymentResult(
                success=False,
                tier=tier,
                version=self.manifest.version,
                replicas=self._deployments[tier].replicas,
                errors=errors,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        # Invoke pre-scale hooks
        await self._invoke_hooks("pre_scale", tier=tier, replicas=replicas)

        # Update replica count
        previous = self._deployments[tier]
        result = DeploymentResult(
            success=True,
            tier=tier,
            version=previous.version,
            replicas=replicas,
            endpoints=previous.endpoints,
            deployment_id=previous.deployment_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )
        self._deployments[tier] = result

        # Invoke post-scale hooks
        await self._invoke_hooks("post_scale", tier=tier, result=result)

        return result

    async def rollback(
        self,
        tier: DeploymentTier,
        version: str,
    ) -> DeploymentResult:
        """Rollback to a previous version.

        Args:
            tier: The deployment tier to rollback.
            version: The version to rollback to.

        Returns:
            DeploymentResult with rollback outcome.
        """
        started_at = datetime.now(UTC)
        deployment_id = self._generate_deployment_id()

        if tier not in self._deployments:
            return DeploymentResult(
                success=False,
                tier=tier,
                version=version,
                replicas=0,
                errors=[f"No active deployment for tier: {tier}"],
                deployment_id=deployment_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        config = self.manifest.get_config(tier)

        # In real implementation, this would restore from deployment history
        result = DeploymentResult(
            success=True,
            tier=tier,
            version=version,
            replicas=config.replicas,
            endpoints=self._deployments[tier].endpoints,
            warnings=[f"Rolled back from {self.manifest.version} to {version}"],
            deployment_id=deployment_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

        self._deployments[tier] = result
        return result

    def get_deployment(self, tier: DeploymentTier) -> DeploymentResult | None:
        """Get current deployment for a tier.

        Args:
            tier: The deployment tier.

        Returns:
            DeploymentResult if deployed, None otherwise.
        """
        return self._deployments.get(tier)

    def get_all_deployments(self) -> dict[DeploymentTier, DeploymentResult]:
        """Get all active deployments.

        Returns:
            Dictionary of tier to deployment result.
        """
        return dict(self._deployments)

    def is_deployed(self, tier: DeploymentTier) -> bool:
        """Check if a tier is currently deployed.

        Args:
            tier: The deployment tier to check.

        Returns:
            True if tier has an active deployment.
        """
        return tier in self._deployments and self._deployments[tier].success

    async def undeploy(self, tier: DeploymentTier) -> bool:
        """Remove deployment from a tier.

        Args:
            tier: The deployment tier to undeploy.

        Returns:
            True if deployment was removed, False if not found.
        """
        if tier in self._deployments:
            del self._deployments[tier]
            return True
        return False

    def get_status_summary(self) -> dict[str, Any]:
        """Get summary of all deployment statuses.

        Returns:
            Dictionary with deployment status summary.
        """
        return {
            "manifest": {
                "name": self.manifest.name,
                "version": self.manifest.version,
            },
            "deployments": {
                str(tier): {
                    "success": result.success,
                    "replicas": result.replicas,
                    "endpoints": result.endpoints,
                }
                for tier, result in self._deployments.items()
            },
            "total_replicas": sum(d.replicas for d in self._deployments.values() if d.success),
        }
