"""Hybrid tier deployment for Nexus - Custom channel combinations.

This module provides flexible deployment with custom channel selection,
allowing workflows to be exposed on specific channel combinations.

Example:
    >>> from aegis_sdk.nexus import HybridTierDeployer, HybridConfig
    >>> config = HybridConfig(channels=["api", "cli"])  # No MCP
    >>> deployer = HybridTierDeployer(config=config)
    >>>
    >>> # Register workflow with channel override
    >>> deployer.register_workflow(
    ...     "admin-workflow",
    ...     handler=admin_handler,
    ...     channels=["api"],  # API only, overrides default
    ... )
    >>>
    >>> # Start configured channels
    >>> await deployer.start()
"""

from __future__ import annotations

import asyncio
import builtins
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for workflow handlers
WorkflowHandler = Callable[..., Any | Awaitable[Any]]


class HybridChannel(Enum):
    """Channel types for hybrid deployment."""

    API = auto()
    CLI = auto()
    MCP = auto()

    def __str__(self) -> str:
        """Return lowercase channel name."""
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> HybridChannel:
        """Convert string to HybridChannel.

        Args:
            value: String representation (case-insensitive).

        Returns:
            Corresponding HybridChannel enum value.

        Raises:
            ValueError: If the string does not match any channel.
        """
        mapping = {
            "api": cls.API,
            "rest": cls.API,
            "http": cls.API,
            "cli": cls.CLI,
            "command": cls.CLI,
            "mcp": cls.MCP,
            "model": cls.MCP,
        }
        normalized = value.lower().strip()
        if normalized not in mapping:
            valid = ", ".join(sorted(set(mapping.keys())))
            raise ValueError(f"Invalid channel: '{value}'. Valid values: {valid}")
        return mapping[normalized]

    @classmethod
    def from_strings(cls, values: list[str]) -> set[HybridChannel]:
        """Convert list of strings to set of HybridChannels.

        Args:
            values: List of string representations.

        Returns:
            Set of HybridChannel enum values.
        """
        return {cls.from_string(v) for v in values}


@dataclass
class HybridChannelConfig:
    """Configuration for a channel in hybrid deployment.

    Attributes:
        channel: Channel type.
        enabled: Whether channel is enabled.
        port: Port for network channels.
        host: Host to bind to.
        auth_required: Whether authentication is required.
        rate_limit: Requests per minute limit.
        config: Channel-specific configuration.
    """

    channel: HybridChannel
    enabled: bool = True
    port: int | None = None
    host: str = "0.0.0.0"
    auth_required: bool = False
    rate_limit: int | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Validate channel configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if self.port is not None and (self.port < 1 or self.port > 65535):
            errors.append(f"port must be between 1 and 65535, got {self.port}")

        if self.rate_limit is not None and self.rate_limit < 1:
            errors.append(f"rate_limit must be >= 1, got {self.rate_limit}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "channel": str(self.channel),
            "enabled": self.enabled,
            "port": self.port,
            "host": self.host,
            "auth_required": self.auth_required,
            "rate_limit": self.rate_limit,
            "config": self.config,
        }


@dataclass
class HybridConfig:
    """Configuration for hybrid tier deployment.

    Attributes:
        name: Deployment name.
        channels: List of enabled channel names.
        port: Default port for API channel.
        mcp_port: Port for MCP channel.
        channel_configs: Per-channel configuration overrides.
        session_enabled: Enable session management.
        session_ttl_s: Session time-to-live.
        max_sessions: Maximum concurrent sessions.
    """

    name: str = "nexus-hybrid"
    channels: list[str] = field(default_factory=lambda: ["api", "cli", "mcp"])
    port: int = 8000
    mcp_port: int = 3001
    channel_configs: dict[str, HybridChannelConfig] = field(default_factory=dict)
    session_enabled: bool = True
    session_ttl_s: int = 3600
    max_sessions: int = 10000

    def __post_init__(self):
        """Initialize channel configurations."""
        # Create default configs for each channel
        channel_enums = HybridChannel.from_strings(self.channels)
        for channel in channel_enums:
            if str(channel) not in self.channel_configs:
                port = None
                if channel == HybridChannel.API:
                    port = self.port
                elif channel == HybridChannel.MCP:
                    port = self.mcp_port

                self.channel_configs[str(channel)] = HybridChannelConfig(
                    channel=channel,
                    port=port,
                )

    def validate(self) -> list[str]:
        """Validate hybrid configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if not self.name:
            errors.append("name is required")

        if not self.channels:
            errors.append("at least one channel must be specified")

        # Validate channel names
        valid_channels = {"api", "cli", "mcp"}
        for channel in self.channels:
            if channel.lower() not in valid_channels:
                errors.append(f"Invalid channel: '{channel}'. Valid: {valid_channels}")

        if self.session_ttl_s < 0:
            errors.append("session_ttl_s must be >= 0")

        if self.max_sessions < 1:
            errors.append("max_sessions must be >= 1")

        # Validate channel configs
        for name, config in self.channel_configs.items():
            config_errors = config.validate()
            errors.extend([f"channel_configs.{name}.{e}" for e in config_errors])

        return errors

    def get_enabled_channels(self) -> set[HybridChannel]:
        """Get set of enabled channels.

        Returns:
            Set of enabled HybridChannel values.
        """
        return HybridChannel.from_strings(self.channels)

    def get_channel_config(self, channel: HybridChannel) -> HybridChannelConfig | None:
        """Get configuration for a channel.

        Args:
            channel: Channel type.

        Returns:
            HybridChannelConfig or None.
        """
        return self.channel_configs.get(str(channel))

    def is_channel_enabled(self, channel: HybridChannel) -> bool:
        """Check if a channel is enabled.

        Args:
            channel: Channel type.

        Returns:
            True if channel is enabled.
        """
        return channel in self.get_enabled_channels()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "name": self.name,
            "channels": self.channels,
            "port": self.port,
            "mcp_port": self.mcp_port,
            "channel_configs": {k: v.to_dict() for k, v in self.channel_configs.items()},
            "session_enabled": self.session_enabled,
            "session_ttl_s": self.session_ttl_s,
            "max_sessions": self.max_sessions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HybridConfig:
        """Create from dictionary.

        Args:
            data: Dictionary containing configuration.

        Returns:
            HybridConfig instance.
        """
        return cls(
            name=data.get("name", "nexus-hybrid"),
            channels=data.get("channels", ["api", "cli", "mcp"]),
            port=data.get("port", 8000),
            mcp_port=data.get("mcp_port", 3001),
            session_enabled=data.get("session_enabled", True),
            session_ttl_s=data.get("session_ttl_s", 3600),
            max_sessions=data.get("max_sessions", 10000),
        )

    @classmethod
    def api_cli_only(cls, name: str = "nexus-api-cli") -> HybridConfig:
        """Create config for API + CLI only deployment.

        Args:
            name: Deployment name.

        Returns:
            HybridConfig for API + CLI.
        """
        return cls(name=name, channels=["api", "cli"])

    @classmethod
    def api_mcp_only(cls, name: str = "nexus-api-mcp") -> HybridConfig:
        """Create config for API + MCP only deployment.

        Args:
            name: Deployment name.

        Returns:
            HybridConfig for API + MCP.
        """
        return cls(name=name, channels=["api", "mcp"])

    @classmethod
    def cli_only(cls, name: str = "nexus-cli") -> HybridConfig:
        """Create config for CLI only deployment.

        Args:
            name: Deployment name.

        Returns:
            HybridConfig for CLI only.
        """
        return cls(name=name, channels=["cli"])


@dataclass
class HybridWorkflowConfig:
    """Per-workflow channel configuration for hybrid deployment.

    Attributes:
        channels: Channels enabled for this workflow (None = use defaults).
        api_config: API-specific configuration.
        cli_config: CLI-specific configuration.
        mcp_config: MCP-specific configuration.
    """

    channels: list[str] | None = None
    api_config: dict[str, Any] = field(default_factory=dict)
    cli_config: dict[str, Any] = field(default_factory=dict)
    mcp_config: dict[str, Any] = field(default_factory=dict)

    def get_enabled_channels(
        self,
        default_channels: set[HybridChannel],
    ) -> set[HybridChannel]:
        """Get enabled channels for this workflow.

        Args:
            default_channels: Default channels from deployer config.

        Returns:
            Set of enabled channels.
        """
        if self.channels is None:
            return default_channels
        return HybridChannel.from_strings(self.channels)


@dataclass
class HybridWorkflowRegistration:
    """Registered workflow for hybrid deployment.

    Attributes:
        name: Workflow name.
        handler: Workflow handler function.
        version: Workflow version.
        description: Workflow description.
        workflow_config: Per-workflow channel configuration.
        input_schema: JSON schema for inputs.
        output_schema: JSON schema for outputs.
        timeout_s: Workflow timeout in seconds.
        tags: Tags for categorization.
    """

    name: str
    handler: WorkflowHandler
    version: str = "1.0.0"
    description: str = ""
    workflow_config: HybridWorkflowConfig = field(default_factory=HybridWorkflowConfig)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    timeout_s: int = 300
    tags: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Validate workflow registration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if not self.name:
            errors.append("name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("name must be alphanumeric with hyphens/underscores")

        if not callable(self.handler):
            errors.append("handler must be callable")

        if self.timeout_s < 1:
            errors.append("timeout_s must be >= 1")

        return errors

    def is_channel_enabled(
        self,
        channel: HybridChannel,
        default_channels: set[HybridChannel],
    ) -> bool:
        """Check if channel is enabled for this workflow.

        Args:
            channel: Channel to check.
            default_channels: Default enabled channels.

        Returns:
            True if channel is enabled.
        """
        enabled = self.workflow_config.get_enabled_channels(default_channels)
        return channel in enabled


@dataclass
class HybridSession:
    """Session for hybrid deployment.

    Attributes:
        id: Session identifier.
        user_id: Associated user identifier.
        created_at: Creation timestamp.
        last_activity: Last activity timestamp.
        data: Session data.
        channels_used: Channels that have used this session.
        ttl_s: Time-to-live in seconds.
    """

    id: str
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)
    channels_used: builtins.set[HybridChannel] = field(default_factory=set)
    ttl_s: int = 3600

    def touch(self, channel: HybridChannel | None = None) -> None:
        """Update last activity.

        Args:
            channel: Channel that triggered activity.
        """
        self.last_activity = time.time()
        if channel:
            self.channels_used.add(channel)

    def is_expired(self) -> bool:
        """Check if session is expired.

        Returns:
            True if expired.
        """
        if self.ttl_s == 0:
            return False
        return (time.time() - self.last_activity) > self.ttl_s

    def get(self, key: str, default: Any = None) -> Any:
        """Get session data.

        Args:
            key: Data key.
            default: Default value.

        Returns:
            Value or default.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set session data.

        Args:
            key: Data key.
            value: Value to store.
        """
        self.data[key] = value
        self.touch()


@dataclass
class HybridExecutionResult:
    """Result of hybrid workflow execution.

    Attributes:
        success: Whether execution succeeded.
        workflow_name: Name of executed workflow.
        channel: Channel that executed.
        result: Execution result.
        error: Error message if failed.
        execution_id: Execution identifier.
        session_id: Session identifier.
        started_at: Start timestamp.
        completed_at: Completion timestamp.
    """

    success: bool
    workflow_name: str
    channel: HybridChannel
    result: Any = None
    error: str | None = None
    execution_id: str | None = None
    session_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "success": self.success,
            "workflow_name": self.workflow_name,
            "channel": str(self.channel),
            "result": self.result,
            "error": self.error,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class HybridSessionManager:
    """Session manager for hybrid deployments."""

    def __init__(
        self,
        ttl_s: int = 3600,
        max_sessions: int = 10000,
    ):
        """Initialize session manager.

        Args:
            ttl_s: Default session TTL.
            max_sessions: Maximum sessions.
        """
        self._ttl_s = ttl_s
        self._max_sessions = max_sessions
        self._sessions: dict[str, HybridSession] = {}

    def create(
        self,
        user_id: str | None = None,
        channel: HybridChannel | None = None,
    ) -> HybridSession:
        """Create a new session.

        Args:
            user_id: User identifier.
            channel: Creating channel.

        Returns:
            Created session.

        Raises:
            RuntimeError: If max sessions exceeded.
        """
        self._cleanup_expired()

        if len(self._sessions) >= self._max_sessions:
            raise RuntimeError(f"Maximum sessions ({self._max_sessions}) exceeded")

        session = HybridSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            ttl_s=self._ttl_s,
        )

        if channel:
            session.channels_used.add(channel)

        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> HybridSession | None:
        """Get session by ID.

        Args:
            session_id: Session ID.

        Returns:
            Session or None.
        """
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            return session
        return None

    def get_or_create(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        channel: HybridChannel | None = None,
    ) -> HybridSession:
        """Get existing session or create new one.

        Args:
            session_id: Optional existing session ID.
            user_id: User identifier.
            channel: Channel accessing session.

        Returns:
            Session instance.
        """
        if session_id:
            session = self.get(session_id)
            if session:
                session.touch(channel)
                return session

        return self.create(user_id=user_id, channel=channel)

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID.

        Returns:
            True if deleted.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def _cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number removed.
        """
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics.

        Returns:
            Statistics dictionary.
        """
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": len([s for s in self._sessions.values() if not s.is_expired()]),
            "ttl_s": self._ttl_s,
            "max_sessions": self._max_sessions,
        }


class HybridTierDeployer:
    """Deploys workflows with custom channel selection.

    Allows flexible deployment where different workflows can be
    exposed on different channel combinations.

    Example:
        >>> config = HybridConfig(channels=["api", "cli"])
        >>> deployer = HybridTierDeployer(config=config)
        >>>
        >>> # Register workflow for all default channels
        >>> deployer.register_workflow("public-workflow", handler=public_handler)
        >>>
        >>> # Register workflow for specific channels
        >>> deployer.register_workflow(
        ...     "admin-workflow",
        ...     handler=admin_handler,
        ...     channels=["api"],  # API only
        ... )
        >>>
        >>> await deployer.start()
    """

    def __init__(
        self,
        config: HybridConfig | None = None,
    ):
        """Initialize hybrid tier deployer.

        Args:
            config: Hybrid configuration.
        """
        self._config = config or HybridConfig()
        self._workflows: dict[str, HybridWorkflowRegistration] = {}
        self._session_manager: HybridSessionManager | None = None
        if self._config.session_enabled:
            self._session_manager = HybridSessionManager(
                ttl_s=self._config.session_ttl_s,
                max_sessions=self._config.max_sessions,
            )
        self._running = False
        self._channel_status: dict[HybridChannel, bool] = {}
        self._start_time: float | None = None
        self._execution_counter = 0
        self._metrics: dict[str, Any] = {
            "total_executions": 0,
            "executions_by_channel": {str(c): 0 for c in HybridChannel},
            "successful_executions": 0,
            "failed_executions": 0,
        }

    @property
    def name(self) -> str:
        """Get deployer name."""
        return self._config.name

    @property
    def config(self) -> HybridConfig:
        """Get configuration."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Check if deployer is running."""
        return self._running

    @property
    def uptime_s(self) -> float | None:
        """Get uptime in seconds."""
        if self._start_time:
            return time.time() - self._start_time
        return None

    @property
    def session_manager(self) -> HybridSessionManager | None:
        """Get session manager."""
        return self._session_manager

    def register_workflow(
        self,
        name: str,
        handler: WorkflowHandler,
        version: str = "1.0.0",
        description: str = "",
        channels: list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        timeout_s: int = 300,
        tags: list[str] | None = None,
        api_config: dict[str, Any] | None = None,
        cli_config: dict[str, Any] | None = None,
        mcp_config: dict[str, Any] | None = None,
    ) -> HybridWorkflowRegistration:
        """Register a workflow with optional channel override.

        Args:
            name: Workflow name.
            handler: Workflow handler.
            version: Workflow version.
            description: Workflow description.
            channels: Channels for this workflow (None = use defaults).
            input_schema: Input JSON schema.
            output_schema: Output JSON schema.
            timeout_s: Timeout in seconds.
            tags: Categorization tags.
            api_config: API-specific configuration.
            cli_config: CLI-specific configuration.
            mcp_config: MCP-specific configuration.

        Returns:
            HybridWorkflowRegistration instance.

        Raises:
            ValueError: If validation fails or name exists.
        """
        if name in self._workflows:
            raise ValueError(f"Workflow already registered: {name}")

        workflow_config = HybridWorkflowConfig(
            channels=channels,
            api_config=api_config or {},
            cli_config=cli_config or {},
            mcp_config=mcp_config or {},
        )

        registration = HybridWorkflowRegistration(
            name=name,
            handler=handler,
            version=version,
            description=description,
            workflow_config=workflow_config,
            input_schema=input_schema,
            output_schema=output_schema,
            timeout_s=timeout_s,
            tags=tags or [],
        )

        errors = registration.validate()
        if errors:
            raise ValueError(f"Invalid workflow registration: {'; '.join(errors)}")

        self._workflows[name] = registration
        logger.info("Registered hybrid workflow: %s", name)
        return registration

    def unregister_workflow(self, name: str) -> bool:
        """Unregister a workflow.

        Args:
            name: Workflow name.

        Returns:
            True if removed.
        """
        if name in self._workflows:
            del self._workflows[name]
            logger.info("Unregistered hybrid workflow: %s", name)
            return True
        return False

    def get_workflow(self, name: str) -> HybridWorkflowRegistration | None:
        """Get workflow registration.

        Args:
            name: Workflow name.

        Returns:
            Registration or None.
        """
        return self._workflows.get(name)

    def list_workflows(
        self,
        channel: HybridChannel | None = None,
    ) -> list[HybridWorkflowRegistration]:
        """Get all registered workflows.

        Args:
            channel: Filter by channel.

        Returns:
            List of registrations.
        """
        workflows = list(self._workflows.values())
        if channel:
            default_channels = self._config.get_enabled_channels()
            workflows = [w for w in workflows if w.is_channel_enabled(channel, default_channels)]
        return workflows

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        self._execution_counter += 1
        timestamp = int(time.time() * 1000)
        return f"hybrid-exec-{timestamp}-{self._execution_counter}"

    async def execute_workflow(
        self,
        name: str,
        channel: HybridChannel,
        inputs: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> HybridExecutionResult:
        """Execute a workflow on specified channel.

        Args:
            name: Workflow name.
            channel: Channel to execute on.
            inputs: Workflow inputs.
            session_id: Optional session ID.
            user_id: Optional user ID.

        Returns:
            Execution result.
        """
        started_at = datetime.now(UTC)
        execution_id = self._generate_execution_id()

        # Update metrics
        self._metrics["total_executions"] += 1
        self._metrics["executions_by_channel"][str(channel)] += 1

        # Get or create session
        session = None
        if self._session_manager:
            session = self._session_manager.get_or_create(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
            )

        # Check workflow exists
        if name not in self._workflows:
            result = HybridExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error=f"Workflow not found: {name}",
                execution_id=execution_id,
                session_id=session.id if session else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            return result

        registration = self._workflows[name]
        default_channels = self._config.get_enabled_channels()

        # Check channel is enabled for this workflow
        if not registration.is_channel_enabled(channel, default_channels):
            result = HybridExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error=f"Workflow not enabled for channel: {channel}",
                execution_id=execution_id,
                session_id=session.id if session else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            return result

        # Check channel is running
        if not self._channel_status.get(channel, False):
            result = HybridExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error=f"Channel not running: {channel}",
                execution_id=execution_id,
                session_id=session.id if session else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            return result

        try:
            # Execute handler with timeout
            if asyncio.iscoroutinefunction(registration.handler):
                handler_result = await asyncio.wait_for(
                    registration.handler(inputs or {}),
                    timeout=registration.timeout_s,
                )
            else:
                handler_result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        registration.handler,
                        inputs or {},
                    ),
                    timeout=registration.timeout_s,
                )

            result = HybridExecutionResult(
                success=True,
                workflow_name=name,
                channel=channel,
                result=handler_result,
                execution_id=execution_id,
                session_id=session.id if session else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["successful_executions"] += 1

        except TimeoutError:
            result = HybridExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error=f"Execution timed out after {registration.timeout_s}s",
                execution_id=execution_id,
                session_id=session.id if session else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1

        except Exception as e:
            result = HybridExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error="Workflow execution failed",
                execution_id=execution_id,
                session_id=session.id if session else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            logger.error("Hybrid workflow execution failed for %s: %s", name, e, exc_info=True)

        return result

    async def start(self) -> None:
        """Start all configured channels."""
        if self._running:
            logger.warning("Hybrid deployer already running")
            return

        # Validate configuration
        errors = self._config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {'; '.join(errors)}")

        self._running = True
        self._start_time = time.time()

        # Start enabled channels
        for channel in self._config.get_enabled_channels():
            await self._start_channel(channel)

        enabled = [str(c) for c in self._config.get_enabled_channels()]
        logger.info("Hybrid deployer '%s' started with channels: %s", self._config.name, enabled)

    async def _start_channel(self, channel: HybridChannel) -> None:
        """Start a specific channel.

        Args:
            channel: Channel to start.
        """
        config = self._config.get_channel_config(channel)
        if not config or not config.enabled:
            return

        # In real implementation, this would start the actual channel
        self._channel_status[channel] = True
        logger.info("Started %s channel", channel)

    async def stop(self) -> None:
        """Stop all channels."""
        if not self._running:
            logger.warning("Hybrid deployer not running")
            return

        # Stop all channels
        for channel in HybridChannel:
            await self._stop_channel(channel)

        self._running = False
        logger.info("Hybrid deployer '%s' stopped", self._config.name)

    async def _stop_channel(self, channel: HybridChannel) -> None:
        """Stop a specific channel.

        Args:
            channel: Channel to stop.
        """
        if self._channel_status.get(channel):
            self._channel_status[channel] = False
            logger.info("Stopped %s channel", channel)

    async def reload(self) -> None:
        """Reload configuration and restart."""
        await self.stop()
        await self.start()

    def status(self) -> dict[str, Any]:
        """Get deployer status.

        Returns:
            Status dictionary.
        """
        return {
            "name": self._config.name,
            "running": self._running,
            "uptime_s": self.uptime_s,
            "channels": {
                str(c): {
                    "enabled": self._config.is_channel_enabled(c),
                    "running": self._channel_status.get(c, False),
                }
                for c in HybridChannel
            },
            "workflows_count": len(self._workflows),
            "sessions": self._session_manager.get_stats() if self._session_manager else None,
        }

    def health_check(self) -> dict[str, Any]:
        """Perform health check.

        Returns:
            Health check result.
        """
        healthy = self._running and any(self._channel_status.values())
        return {
            "status": "healthy" if healthy else "unhealthy",
            "name": self._config.name,
            "channels": {
                str(c): "healthy" if self._channel_status.get(c) else "stopped"
                for c in self._config.get_enabled_channels()
            },
        }

    def get_stats(self) -> dict[str, Any]:
        """Get deployer statistics.

        Returns:
            Statistics dictionary.
        """
        return {
            "name": self._config.name,
            "is_running": self._running,
            "uptime_s": self.uptime_s,
            "workflows_count": len(self._workflows),
            "enabled_channels": [str(c) for c in self._config.get_enabled_channels()],
            "metrics": self._metrics,
            "sessions": self._session_manager.get_stats() if self._session_manager else None,
        }

    def __len__(self) -> int:
        """Get number of registered workflows."""
        return len(self._workflows)

    def __contains__(self, name: str) -> bool:
        """Check if workflow is registered."""
        return name in self._workflows


# Convenience function for unified deployment
def deploy(
    tier: str,
    workflows: dict[str, WorkflowHandler] | None = None,
    config: dict[str, Any] | None = None,
) -> HybridTierDeployer | Any:
    """Main entry point for deployment.

    Args:
        tier: Tier type ("rest", "platform", "hybrid", or channel list).
        workflows: Dictionary of workflow name to handler.
        config: Configuration dictionary.

    Returns:
        Appropriate deployer instance.

    Example:
        >>> deployer = deploy("hybrid", workflows={"my-workflow": handler})
        >>> await deployer.start()
    """
    from .platform_tier import PlatformConfig, PlatformTierDeployer
    from .rest_tier import RESTConfig, RESTTierDeployer

    tier_lower = tier.lower()

    if tier_lower == "rest":
        deployer = RESTTierDeployer(config=RESTConfig(**config) if config else None)
        if workflows:
            for name, handler in workflows.items():
                deployer.register_workflow(name, handler)
        return deployer

    elif tier_lower == "platform":
        deployer = PlatformTierDeployer(config=PlatformConfig(**config) if config else None)
        if workflows:
            for name, handler in workflows.items():
                deployer.register_workflow(name, handler)
        return deployer

    elif tier_lower == "hybrid" or "," in tier or tier_lower in {"api", "cli", "mcp"}:
        # Parse channel list if comma-separated
        if "," in tier:
            channels = [c.strip() for c in tier.split(",")]
        elif tier_lower in {"api", "cli", "mcp"}:
            channels = [tier_lower]
        else:
            channels = ["api", "cli", "mcp"]  # Default for hybrid

        hybrid_config = HybridConfig(channels=channels)
        if config:
            hybrid_config = HybridConfig.from_dict({**hybrid_config.to_dict(), **config})

        deployer = HybridTierDeployer(config=hybrid_config)
        if workflows:
            for name, handler in workflows.items():
                deployer.register_workflow(name, handler)
        return deployer

    else:
        raise ValueError(f"Unknown tier: {tier}. Valid: rest, platform, hybrid, or channel list")
