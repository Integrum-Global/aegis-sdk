"""Platform tier deployment for Nexus - Full API + CLI + MCP deployment.

This module provides full-featured deployment of workflows across all three
channels (API, CLI, MCP) with unified session management and state sharing.

Example:
    >>> from aegis_sdk.nexus import PlatformTierDeployer
    >>> deployer = PlatformTierDeployer()
    >>>
    >>> # Register workflow handlers
    >>> deployer.register_workflow("process-data", handler=process_data)
    >>>
    >>> # Start all channels
    >>> await deployer.start()
    >>>
    >>> # Access via any channel:
    >>> # - API: POST /workflows/process-data/execute
    >>> # - CLI: nexus run process-data --input data.json
    >>> # - MCP: Tool "process-data" exposed to AI agents
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


class ChannelType(Enum):
    """Channel types for platform deployment."""

    API = auto()
    CLI = auto()
    MCP = auto()

    def __str__(self) -> str:
        """Return lowercase channel name."""
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> ChannelType:
        """Convert string to ChannelType.

        Args:
            value: String representation (case-insensitive).

        Returns:
            Corresponding ChannelType enum value.

        Raises:
            ValueError: If the string does not match any type.
        """
        mapping = {
            "api": cls.API,
            "rest": cls.API,
            "http": cls.API,
            "cli": cls.CLI,
            "command": cls.CLI,
            "terminal": cls.CLI,
            "mcp": cls.MCP,
            "model": cls.MCP,
            "tool": cls.MCP,
        }
        normalized = value.lower().strip()
        if normalized not in mapping:
            valid = ", ".join(sorted(set(mapping.keys())))
            raise ValueError(f"Invalid channel type: '{value}'. Valid values: {valid}")
        return mapping[normalized]


class SessionAffinity(Enum):
    """Session affinity modes for cross-channel access."""

    NONE = auto()  # No session sharing between channels
    CHANNEL = auto()  # Session per channel
    UNIFIED = auto()  # Single session across all channels

    def __str__(self) -> str:
        """Return lowercase affinity name."""
        return self.name.lower()


@dataclass
class UnifiedSession:
    """Unified session across all channels.

    Attributes:
        id: Unique session identifier.
        user_id: Associated user identifier.
        created_at: Session creation timestamp.
        last_activity: Last activity timestamp.
        data: Session data store.
        channel_data: Per-channel data.
        active_channels: Channels that have used this session.
        ttl_s: Session time-to-live in seconds.
    """

    id: str
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)
    channel_data: dict[ChannelType, dict[str, Any]] = field(default_factory=dict)
    active_channels: builtins.set[ChannelType] = field(default_factory=set)
    ttl_s: int = 3600

    def touch(self, channel: ChannelType | None = None) -> None:
        """Update last activity timestamp.

        Args:
            channel: Channel that triggered the activity.
        """
        self.last_activity = time.time()
        if channel:
            self.active_channels.add(channel)

    def is_expired(self) -> bool:
        """Check if session has expired.

        Returns:
            True if session is expired.
        """
        if self.ttl_s == 0:
            return False
        return (time.time() - self.last_activity) > self.ttl_s

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from session data.

        Args:
            key: Data key to retrieve.
            default: Default value if key not found.

        Returns:
            Value from session data or default.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in session data.

        Args:
            key: Data key to set.
            value: Value to store.
        """
        self.data[key] = value
        self.touch()

    def get_channel_data(self, channel: ChannelType) -> dict[str, Any]:
        """Get channel-specific data.

        Args:
            channel: Channel type.

        Returns:
            Channel-specific data dictionary.
        """
        if channel not in self.channel_data:
            self.channel_data[channel] = {}
        return self.channel_data[channel]

    def set_channel_data(self, channel: ChannelType, key: str, value: Any) -> None:
        """Set channel-specific data.

        Args:
            channel: Channel type.
            key: Data key.
            value: Value to store.
        """
        if channel not in self.channel_data:
            self.channel_data[channel] = {}
        self.channel_data[channel][key] = value
        self.touch(channel)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "data": self.data,
            "channel_data": {str(k): v for k, v in self.channel_data.items()},
            "active_channels": [str(c) for c in self.active_channels],
            "ttl_s": self.ttl_s,
            "is_expired": self.is_expired(),
        }


@dataclass
class ChannelConfig:
    """Configuration for a single channel.

    Attributes:
        channel_type: Type of channel.
        enabled: Whether the channel is enabled.
        port: Port for the channel (API/MCP).
        auth_required: Whether authentication is required.
        rate_limit: Requests per minute limit.
        custom_config: Channel-specific configuration.
    """

    channel_type: ChannelType
    enabled: bool = True
    port: int | None = None
    auth_required: bool = False
    rate_limit: int | None = None
    custom_config: dict[str, Any] = field(default_factory=dict)

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


@dataclass
class PlatformConfig:
    """Configuration for platform tier deployment.

    Attributes:
        name: Platform name.
        version: Platform version.
        channels: Channel configurations.
        session_affinity: Session affinity mode.
        session_ttl_s: Default session TTL.
        max_sessions: Maximum concurrent sessions.
        enable_metrics: Enable metrics collection.
        enable_tracing: Enable distributed tracing.
    """

    name: str = "nexus-platform"
    version: str = "1.0.0"
    channels: dict[ChannelType, ChannelConfig] = field(default_factory=dict)
    session_affinity: SessionAffinity = SessionAffinity.UNIFIED
    session_ttl_s: int = 3600
    max_sessions: int = 10000
    enable_metrics: bool = True
    enable_tracing: bool = False

    def __post_init__(self):
        """Initialize default channel configurations."""
        if not self.channels:
            self.channels = {
                ChannelType.API: ChannelConfig(
                    channel_type=ChannelType.API,
                    port=8000,
                    auth_required=True,
                    rate_limit=100,
                ),
                ChannelType.CLI: ChannelConfig(
                    channel_type=ChannelType.CLI,
                    enabled=True,
                ),
                ChannelType.MCP: ChannelConfig(
                    channel_type=ChannelType.MCP,
                    port=3001,
                    auth_required=True,
                    rate_limit=50,
                ),
            }

    def validate(self) -> list[str]:
        """Validate platform configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if not self.name:
            errors.append("name is required")

        if self.session_ttl_s < 0:
            errors.append("session_ttl_s must be >= 0")

        if self.max_sessions < 1:
            errors.append("max_sessions must be >= 1")

        # Validate channel configs
        for channel_type, config in self.channels.items():
            channel_errors = config.validate()
            errors.extend([f"channels.{channel_type}.{e}" for e in channel_errors])

        return errors

    def get_channel(self, channel_type: ChannelType) -> ChannelConfig | None:
        """Get channel configuration.

        Args:
            channel_type: Channel type.

        Returns:
            ChannelConfig or None.
        """
        return self.channels.get(channel_type)

    def enable_channel(self, channel_type: ChannelType) -> None:
        """Enable a channel.

        Args:
            channel_type: Channel type to enable.
        """
        if channel_type in self.channels:
            self.channels[channel_type].enabled = True

    def disable_channel(self, channel_type: ChannelType) -> None:
        """Disable a channel.

        Args:
            channel_type: Channel type to disable.
        """
        if channel_type in self.channels:
            self.channels[channel_type].enabled = False

    def get_enabled_channels(self) -> list[ChannelType]:
        """Get list of enabled channels.

        Returns:
            List of enabled channel types.
        """
        return [ct for ct, config in self.channels.items() if config.enabled]


@dataclass
class PlatformWorkflowRegistration:
    """Workflow registration for platform deployment.

    Attributes:
        name: Workflow name.
        handler: Workflow handler function.
        version: Workflow version.
        description: Workflow description.
        channels: Enabled channels for this workflow.
        input_schema: JSON schema for inputs.
        output_schema: JSON schema for outputs.
        cli_config: CLI-specific configuration.
        mcp_config: MCP-specific configuration.
    """

    name: str
    handler: WorkflowHandler
    version: str = "1.0.0"
    description: str = ""
    channels: set[ChannelType] = field(
        default_factory=lambda: {ChannelType.API, ChannelType.CLI, ChannelType.MCP}
    )
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    cli_config: dict[str, Any] = field(default_factory=dict)
    mcp_config: dict[str, Any] = field(default_factory=dict)

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

        if not self.channels:
            errors.append("at least one channel must be enabled")

        return errors

    def is_channel_enabled(self, channel: ChannelType) -> bool:
        """Check if channel is enabled for this workflow.

        Args:
            channel: Channel type.

        Returns:
            True if channel is enabled.
        """
        return channel in self.channels

    def enable_channel(self, channel: ChannelType) -> None:
        """Enable a channel for this workflow.

        Args:
            channel: Channel type to enable.
        """
        self.channels.add(channel)

    def disable_channel(self, channel: ChannelType) -> None:
        """Disable a channel for this workflow.

        Args:
            channel: Channel type to disable.
        """
        self.channels.discard(channel)


@dataclass
class ChannelExecutionContext:
    """Context for workflow execution in a specific channel.

    Attributes:
        channel: Channel type.
        session: Unified session.
        workflow_name: Name of the workflow being executed.
        inputs: Workflow inputs.
        execution_id: Unique execution identifier.
        started_at: Execution start time.
        metadata: Additional context metadata.
    """

    channel: ChannelType
    session: UnifiedSession | None
    workflow_name: str
    inputs: dict[str, Any]
    execution_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformExecutionResult:
    """Result of workflow execution on platform.

    Attributes:
        success: Whether execution succeeded.
        workflow_name: Name of the executed workflow.
        channel: Channel that executed the workflow.
        result: Execution result data.
        error: Error message if failed.
        execution_id: Unique execution identifier.
        session_id: Session identifier.
        started_at: Execution start time.
        completed_at: Execution completion time.
    """

    success: bool
    workflow_name: str
    channel: ChannelType
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
        """Convert result to dictionary.

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


class UnifiedSessionManager:
    """Manages unified sessions across channels.

    Provides session creation, retrieval, and cross-channel access
    with configurable affinity modes.
    """

    def __init__(
        self,
        affinity: SessionAffinity = SessionAffinity.UNIFIED,
        ttl_s: int = 3600,
        max_sessions: int = 10000,
    ):
        """Initialize session manager.

        Args:
            affinity: Session affinity mode.
            ttl_s: Default session TTL.
            max_sessions: Maximum concurrent sessions.
        """
        self._affinity = affinity
        self._ttl_s = ttl_s
        self._max_sessions = max_sessions
        self._sessions: dict[str, UnifiedSession] = {}
        self._user_sessions: dict[str, set[str]] = {}

    def create(
        self,
        user_id: str | None = None,
        channel: ChannelType | None = None,
        data: dict[str, Any] | None = None,
    ) -> UnifiedSession:
        """Create a new session.

        Args:
            user_id: Optional user identifier.
            channel: Channel creating the session.
            data: Initial session data.

        Returns:
            Created UnifiedSession.

        Raises:
            RuntimeError: If maximum sessions exceeded.
        """
        self._cleanup_expired()

        if len(self._sessions) >= self._max_sessions:
            raise RuntimeError(f"Maximum sessions ({self._max_sessions}) exceeded")

        session = UnifiedSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            data=data or {},
            ttl_s=self._ttl_s,
        )

        if channel:
            session.active_channels.add(channel)

        self._sessions[session.id] = session

        if user_id:
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session.id)

        return session

    def get(self, session_id: str) -> UnifiedSession | None:
        """Get a session by ID.

        Args:
            session_id: Session ID.

        Returns:
            UnifiedSession or None.
        """
        session = self._sessions.get(session_id)
        if session and not session.is_expired():
            return session
        return None

    def get_or_create(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        channel: ChannelType | None = None,
    ) -> UnifiedSession:
        """Get an existing session or create a new one.

        Args:
            session_id: Optional existing session ID.
            user_id: Optional user identifier.
            channel: Channel accessing the session.

        Returns:
            UnifiedSession instance.
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
            True if deleted, False if not found.
        """
        session = self._sessions.get(session_id)
        if session:
            if session.user_id and session.user_id in self._user_sessions:
                self._user_sessions[session.user_id].discard(session_id)
            del self._sessions[session_id]
            return True
        return False

    def get_by_user(self, user_id: str) -> list[UnifiedSession]:
        """Get all sessions for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of user's sessions.
        """
        session_ids = self._user_sessions.get(user_id, set())
        return [
            self._sessions[sid]
            for sid in session_ids
            if sid in self._sessions and not self._sessions[sid].is_expired()
        ]

    def _cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions cleaned up.
        """
        expired = [sid for sid, session in self._sessions.items() if session.is_expired()]
        for sid in expired:
            self.delete(sid)
        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get session manager statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": len([s for s in self._sessions.values() if not s.is_expired()]),
            "unique_users": len(self._user_sessions),
            "affinity": str(self._affinity),
            "ttl_s": self._ttl_s,
            "max_sessions": self._max_sessions,
        }


class PlatformTierDeployer:
    """Deploys workflows across API + CLI + MCP simultaneously.

    Provides unified session management and state sharing across
    all three channels for a full-featured platform deployment.

    Example:
        >>> deployer = PlatformTierDeployer(config=PlatformConfig(name="my-platform"))
        >>> deployer.register_workflow("my-workflow", handler=my_handler)
        >>> await deployer.start()

    Channels:
        - API: HTTP REST endpoints
        - CLI: Command-line interface
        - MCP: Model Context Protocol for AI agents
    """

    def __init__(
        self,
        config: PlatformConfig | None = None,
    ):
        """Initialize platform tier deployer.

        Args:
            config: Platform configuration.
        """
        self._config = config or PlatformConfig()
        self._workflows: dict[str, PlatformWorkflowRegistration] = {}
        self._session_manager = UnifiedSessionManager(
            affinity=self._config.session_affinity,
            ttl_s=self._config.session_ttl_s,
            max_sessions=self._config.max_sessions,
        )
        self._running = False
        self._channel_status: dict[ChannelType, bool] = {
            ChannelType.API: False,
            ChannelType.CLI: False,
            ChannelType.MCP: False,
        }
        self._start_time: float | None = None
        self._execution_counter = 0
        self._metrics: dict[str, Any] = {
            "total_executions": 0,
            "executions_by_channel": {str(ct): 0 for ct in ChannelType},
            "successful_executions": 0,
            "failed_executions": 0,
        }

    @property
    def name(self) -> str:
        """Get platform name."""
        return self._config.name

    @property
    def version(self) -> str:
        """Get platform version."""
        return self._config.version

    @property
    def config(self) -> PlatformConfig:
        """Get platform configuration."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Check if platform is running."""
        return self._running

    @property
    def uptime_s(self) -> float | None:
        """Get uptime in seconds."""
        if self._start_time:
            return time.time() - self._start_time
        return None

    @property
    def session_manager(self) -> UnifiedSessionManager:
        """Get session manager."""
        return self._session_manager

    def register_workflow(
        self,
        name: str,
        handler: WorkflowHandler,
        version: str = "1.0.0",
        description: str = "",
        channels: set[ChannelType] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        cli_config: dict[str, Any] | None = None,
        mcp_config: dict[str, Any] | None = None,
    ) -> PlatformWorkflowRegistration:
        """Register a workflow for platform deployment.

        Args:
            name: Unique workflow name.
            handler: Workflow handler function.
            version: Workflow version.
            description: Workflow description.
            channels: Enabled channels (default: all).
            input_schema: JSON schema for inputs.
            output_schema: JSON schema for outputs.
            cli_config: CLI-specific configuration.
            mcp_config: MCP-specific configuration.

        Returns:
            PlatformWorkflowRegistration instance.

        Raises:
            ValueError: If validation fails or name already exists.
        """
        if name in self._workflows:
            raise ValueError(f"Workflow already registered: {name}")

        if channels is None:
            channels = {ChannelType.API, ChannelType.CLI, ChannelType.MCP}

        registration = PlatformWorkflowRegistration(
            name=name,
            handler=handler,
            version=version,
            description=description,
            channels=channels,
            input_schema=input_schema,
            output_schema=output_schema,
            cli_config=cli_config or {},
            mcp_config=mcp_config or {},
        )

        errors = registration.validate()
        if errors:
            raise ValueError(f"Invalid workflow registration: {'; '.join(errors)}")

        self._workflows[name] = registration
        logger.info("Registered platform workflow: %s", name)
        return registration

    def unregister_workflow(self, name: str) -> bool:
        """Unregister a workflow.

        Args:
            name: Workflow name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self._workflows:
            del self._workflows[name]
            logger.info("Unregistered platform workflow: %s", name)
            return True
        return False

    def get_workflow(self, name: str) -> PlatformWorkflowRegistration | None:
        """Get a workflow registration.

        Args:
            name: Workflow name.

        Returns:
            PlatformWorkflowRegistration or None.
        """
        return self._workflows.get(name)

    def list_workflows(
        self,
        channel: ChannelType | None = None,
    ) -> list[PlatformWorkflowRegistration]:
        """Get all registered workflows.

        Args:
            channel: Filter by channel (None for all).

        Returns:
            List of workflow registrations.
        """
        workflows = list(self._workflows.values())
        if channel:
            workflows = [w for w in workflows if w.is_channel_enabled(channel)]
        return workflows

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        self._execution_counter += 1
        timestamp = int(time.time() * 1000)
        return f"plat-exec-{timestamp}-{self._execution_counter}"

    async def execute_workflow(
        self,
        name: str,
        channel: ChannelType,
        inputs: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> PlatformExecutionResult:
        """Execute a workflow on a specific channel.

        Args:
            name: Workflow name to execute.
            channel: Channel executing the workflow.
            inputs: Workflow inputs.
            session_id: Optional session ID.
            user_id: Optional user ID.

        Returns:
            PlatformExecutionResult with execution outcome.
        """
        started_at = datetime.now(UTC)
        execution_id = self._generate_execution_id()

        # Update metrics
        self._metrics["total_executions"] += 1
        self._metrics["executions_by_channel"][str(channel)] += 1

        # Get or create session
        session = self._session_manager.get_or_create(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
        )

        # Check workflow exists
        if name not in self._workflows:
            result = PlatformExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error=f"Workflow not found: {name}",
                execution_id=execution_id,
                session_id=session.id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            return result

        registration = self._workflows[name]

        # Check channel is enabled
        if not registration.is_channel_enabled(channel):
            result = PlatformExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error=f"Workflow not enabled for channel: {channel}",
                execution_id=execution_id,
                session_id=session.id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            return result

        # Create execution context
        context = ChannelExecutionContext(
            channel=channel,
            session=session,
            workflow_name=name,
            inputs=inputs or {},
            execution_id=execution_id,
        )

        try:
            # Execute handler
            if asyncio.iscoroutinefunction(registration.handler):
                handler_result = await registration.handler(inputs or {}, context)
            else:
                # For sync handlers, use functools.partial to pass both args
                import functools

                handler_with_context = functools.partial(
                    registration.handler,
                    inputs or {},
                    context,
                )
                handler_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    handler_with_context,
                )

            result = PlatformExecutionResult(
                success=True,
                workflow_name=name,
                channel=channel,
                result=handler_result,
                execution_id=execution_id,
                session_id=session.id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["successful_executions"] += 1

        except Exception as e:
            result = PlatformExecutionResult(
                success=False,
                workflow_name=name,
                channel=channel,
                error="Workflow execution failed",
                execution_id=execution_id,
                session_id=session.id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_executions"] += 1
            logger.error("Platform workflow execution failed for %s: %s", name, e, exc_info=True)

        return result

    def get_channel_status(self, channel: ChannelType) -> bool:
        """Get channel running status.

        Args:
            channel: Channel type.

        Returns:
            True if channel is running.
        """
        return self._channel_status.get(channel, False)

    def is_channel_enabled(self, channel: ChannelType) -> bool:
        """Check if channel is enabled in configuration.

        Args:
            channel: Channel type.

        Returns:
            True if channel is enabled.
        """
        config = self._config.get_channel(channel)
        return config is not None and config.enabled

    async def start(self) -> None:
        """Start all enabled channels."""
        if self._running:
            logger.warning("Platform already running")
            return

        # Validate configuration
        errors = self._config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {'; '.join(errors)}")

        self._running = True
        self._start_time = time.time()

        # Start enabled channels
        for channel_type in self._config.get_enabled_channels():
            await self._start_channel(channel_type)

        logger.info(
            "Platform '%s' started with channels: %s",
            self._config.name,
            self._config.get_enabled_channels(),
        )

    async def _start_channel(self, channel: ChannelType) -> None:
        """Start a specific channel.

        Args:
            channel: Channel type to start.
        """
        config = self._config.get_channel(channel)
        if not config or not config.enabled:
            return

        # In a real implementation, this would start the actual channel
        # (HTTP server for API, MCP server for MCP, etc.)
        self._channel_status[channel] = True
        logger.info("Started %s channel", channel)

    async def stop(self) -> None:
        """Stop all channels."""
        if not self._running:
            logger.warning("Platform not running")
            return

        # Stop all channels
        for channel_type in ChannelType:
            await self._stop_channel(channel_type)

        self._running = False
        logger.info("Platform '%s' stopped", self._config.name)

    async def _stop_channel(self, channel: ChannelType) -> None:
        """Stop a specific channel.

        Args:
            channel: Channel type to stop.
        """
        if self._channel_status.get(channel):
            self._channel_status[channel] = False
            logger.info("Stopped %s channel", channel)

    async def reload(self) -> None:
        """Reload configuration and restart channels."""
        await self.stop()
        await self.start()

    def status(self) -> dict[str, Any]:
        """Get platform status.

        Returns:
            Dictionary with platform status.
        """
        return {
            "name": self._config.name,
            "version": self._config.version,
            "running": self._running,
            "uptime_s": self.uptime_s,
            "channels": {
                str(ct): {
                    "enabled": self.is_channel_enabled(ct),
                    "running": self.get_channel_status(ct),
                }
                for ct in ChannelType
            },
            "workflows_count": len(self._workflows),
            "sessions": self._session_manager.get_stats(),
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
            "version": self._config.version,
            "channels": {
                str(ct): "healthy" if self._channel_status.get(ct) else "stopped"
                for ct in ChannelType
            },
        }

    def get_stats(self) -> dict[str, Any]:
        """Get platform statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            "name": self._config.name,
            "version": self._config.version,
            "is_running": self._running,
            "uptime_s": self.uptime_s,
            "workflows_count": len(self._workflows),
            "metrics": self._metrics,
            "sessions": self._session_manager.get_stats(),
        }

    def __len__(self) -> int:
        """Get number of registered workflows."""
        return len(self._workflows)

    def __contains__(self, name: str) -> bool:
        """Check if workflow is registered."""
        return name in self._workflows
