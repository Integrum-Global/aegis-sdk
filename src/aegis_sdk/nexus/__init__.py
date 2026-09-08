"""Kailash Nexus SDK - Multi-channel platform deployment and orchestration.

This module provides deployment configuration and management for Nexus
multi-channel platforms (API + CLI + MCP).

Nexus v1.1 introduces Tiered Deployment:
- REST Tier: Lightweight API-only deployment
- Platform Tier: Full API + CLI + MCP deployment with unified sessions
- Hybrid Tier: Custom channel combinations per workflow

Usage:
    from aegis_sdk.nexus import (
        # Deployment
        DeploymentTier,
        TierConfig,
        DeploymentManifest,
        DeploymentManager,
        # Tiered Deployment (v1.1)
        RESTTierDeployer,
        PlatformTierDeployer,
        HybridTierDeployer,
        deploy,  # Unified entry point
        # Workflows
        WorkflowRegistry,
        WorkflowRegistration,
        WorkflowStatus,
        # Sessions
        SessionManager,
        Session,
        SessionState,
        # Events
        EventEmitter,
        Event,
        EventPriority,
        # Health
        HealthMonitor,
        HealthCheck,
        HealthStatus,
        # Plugins
        PluginManager,
        Plugin,
        PluginState,
    )

    # Create deployment manifest
    manifest = DeploymentManifest(name="my-platform", version="1.0.0")
    manifest.add_tier(TierConfig(
        tier=DeploymentTier.PRODUCTION,
        replicas=3,
        auto_scaling=True
    ))

    # Deploy
    manager = DeploymentManager
    result = await manager.deploy(DeploymentTier.PRODUCTION)

    # Register workflows
    registry = WorkflowRegistry()
    registry.register("my-workflow", handler=my_handler)

    # Manage sessions
    sessions = SessionManager()
    session = sessions.create("api")

    # Monitor health
    health = HealthMonitor()
    health.register("database", check_database)
    summary = await health.check_all()

    # Use plugins
    plugins = PluginManager()
    plugins.register(my_plugin)

    # Tiered Deployment (v1.1):
    # REST Tier - Lightweight API only
    rest = RESTTierDeployer()
    rest.register_workflow("my-workflow", handler=my_handler)
    await rest.start()

    # Platform Tier - Full features
    platform = PlatformTierDeployer()
    platform.register_workflow("my-workflow", handler=my_handler)
    await platform.start()

    # Hybrid Tier - Custom channels
    hybrid = HybridTierDeployer(config=HybridConfig(channels=["api", "cli"]))
    hybrid.register_workflow("my-workflow", handler=my_handler)
    await hybrid.start()

    # Or use the unified deploy() function
    deployer = deploy("rest", workflows={"my-workflow": my_handler})
    await deployer.start()
"""

# ---------------------------------------------------------------------------
# SDK AUDIENCE — this boundary is enforced by an automated fence in the
# platform's own build; it is not advisory.
# ---------------------------------------------------------------------------
__aegis_sdk_audience__ = "server-side"
__aegis_sdk_audience_reason__ = (
    "This package DEPLOYS and OPERATES a Nexus platform rather than calling one. "
    "sessions_module.py takes a database URL, rewrites it to a postgresql+asyncpg "
    "DSN (:716) and drives create_async_engine (:790), and also opens redis.asyncio "
    "connections (:567) -- so shipping it to the operator/consultant tier would put "
    "database and cache CREDENTIALS in the hands of whoever holds the SDK. The "
    "client-facing trust/ and core/ packages return zero on the same patterns "
    "(re-derived 2026-09-05). The criterion is CAPABILITY, not module size: a "
    "package that stands up and holds open the platform's own datastores is "
    "operator-tier by construction, whatever else it also offers."
)

# Built-in Plugins (v1.1)
from .builtin_plugins.builtins import (
    CachingPlugin,
    LoggingPlugin,
    MetricsPlugin,
)
from .deployment import (
    ChannelConfig,
    DeploymentManager,
    DeploymentManifest,
    DeploymentResult,
    DeploymentTier,
    HealthCheckConfig,
    ScalingPolicy,
    TierConfig,
)
from .events import (
    Event,
    EventEmitter,
    EventPriority,
    HandlerRegistration,
)

# Events Module (v1.1)
from .events_module import (
    ConnectionState,
    EventBus,
    EventQueue,
    EventsModule,
    EventType,
    StreamEvent,
    StreamProtocol,
    Subscription,
    WebSocketConnection,
)
from .health import (
    HealthCheck,
    HealthCheckType,
    HealthMonitor,
    HealthStatus,
    HealthSummary,
)
from .health import (
    HealthCheckConfig as HealthCheckMonitorConfig,
)

# Health Module (v1.1)
from .health_module import (
    AggregatedHealth,
    ComponentHealth,
    HealthAggregator,
    HealthCheckCategory,
    HealthCheckRegistration,
    HealthModule,
    ModuleHealthStatus,
)
from .hybrid_tier import (
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
from .platform_tier import (
    ChannelExecutionContext,
    ChannelType,
    PlatformConfig,
    PlatformExecutionResult,
    PlatformTierDeployer,
    PlatformWorkflowRegistration,
    SessionAffinity,
    UnifiedSession,
    UnifiedSessionManager,
)
from .plugins import (
    HookPriority,
    HookResult,
    Plugin,
    PluginManager,
    PluginMetadata,
    PluginState,
)

# Plugins Module (v1.1)
from .plugins_module import (
    PluginBase,
    PluginConfig,
    PluginExecutionResult,
    PluginInfo,
    PluginLifecycleState,
    PluginPriority,
    PluginRegistration,
    PluginsModule,
    PluginsModuleSingleton,
)

# Tiered Deployment (v1.1)
from .rest_tier import (
    AuthMode,
    RESTConfig,
    RESTEndpoint,
    RESTTierDeployer,
    RESTWorkflowRegistration,
    WorkflowSchema,
)
from .rest_tier import (
    ExecutionResult as RESTExecutionResult,
)
from .sessions import (
    Session,
    SessionManager,
    SessionMetrics,
    SessionState,
)

# Sessions Module (v1.1)
from .sessions_module import (
    AffinityMode,
    DatabaseStorage,
    InMemoryStorage,
    RedisStorage,
    SessionChannel,
    SessionContext,
    SessionManagerFactory,
    SessionMessage,
    SessionModuleState,
    SessionStorageBackend,
    UnifiedSessionsModule,
    WorkflowExecution,
)
from .sessions_module import (
    UnifiedSession as ModuleUnifiedSession,
)
from .workflows import (
    WorkflowMetadata,
    WorkflowPriority,
    WorkflowRegistration,
    WorkflowRegistry,
    WorkflowStatus,
)

# Workflows Module (v1.1)
from .workflows_module import (
    MetadataExtractor,
    ModuleWorkflowRegistration,
    ValidationMode,
    WorkflowExecutionResult,
    WorkflowMetadataInfo,
    WorkflowModuleStatus,
    WorkflowRegistrySingleton,
    WorkflowsModule,
    WorkflowVersionInfo,
)
from .workflows_module import (
    WorkflowSchema as WorkflowModuleSchema,
)

__version__ = "1.1.0"
__all__ = [
    # Deployment
    "DeploymentTier",
    "TierConfig",
    "ChannelConfig",
    "DeploymentManifest",
    "DeploymentResult",
    "DeploymentManager",
    "ScalingPolicy",
    "HealthCheckConfig",
    # Tiered Deployment (v1.1)
    # REST Tier
    "RESTTierDeployer",
    "RESTConfig",
    "RESTEndpoint",
    "RESTWorkflowRegistration",
    "RESTExecutionResult",
    "WorkflowSchema",
    "AuthMode",
    # Platform Tier
    "PlatformTierDeployer",
    "PlatformConfig",
    "PlatformWorkflowRegistration",
    "PlatformExecutionResult",
    "ChannelType",
    "SessionAffinity",
    "UnifiedSession",
    "UnifiedSessionManager",
    "ChannelExecutionContext",
    # Hybrid Tier
    "HybridTierDeployer",
    "HybridConfig",
    "HybridChannel",
    "HybridChannelConfig",
    "HybridWorkflowConfig",
    "HybridWorkflowRegistration",
    "HybridExecutionResult",
    "HybridSession",
    "HybridSessionManager",
    "deploy",  # Unified entry point
    # Workflows
    "WorkflowRegistry",
    "WorkflowRegistration",
    "WorkflowStatus",
    "WorkflowPriority",
    "WorkflowMetadata",
    # Sessions
    "SessionManager",
    "Session",
    "SessionState",
    "SessionMetrics",
    # Events
    "EventEmitter",
    "Event",
    "EventPriority",
    "HandlerRegistration",
    # Health
    "HealthMonitor",
    "HealthCheck",
    "HealthStatus",
    "HealthSummary",
    "HealthCheckType",
    "HealthCheckMonitorConfig",
    # Plugins
    "PluginManager",
    "Plugin",
    "PluginState",
    "PluginMetadata",
    "HookPriority",
    "HookResult",
    # Workflows Module (v1.1)
    "WorkflowsModule",
    "WorkflowModuleStatus",
    "ValidationMode",
    "WorkflowModuleSchema",
    "WorkflowVersionInfo",
    "WorkflowMetadataInfo",
    "ModuleWorkflowRegistration",
    "WorkflowExecutionResult",
    "MetadataExtractor",
    "WorkflowRegistrySingleton",
    # Sessions Module (v1.1)
    "UnifiedSessionsModule",
    "SessionModuleState",
    "SessionChannel",
    "AffinityMode",
    "SessionMessage",
    "WorkflowExecution",
    "SessionContext",
    "ModuleUnifiedSession",
    "SessionStorageBackend",
    "InMemoryStorage",
    "RedisStorage",
    "DatabaseStorage",
    "SessionManagerFactory",
    # Events Module (v1.1)
    "EventsModule",
    "EventType",
    "ConnectionState",
    "StreamProtocol",
    "StreamEvent",
    "Subscription",
    "WebSocketConnection",
    "EventQueue",
    "EventBus",
    # Health Module (v1.1)
    "HealthModule",
    "ModuleHealthStatus",
    "HealthCheckCategory",
    "ComponentHealth",
    "HealthCheckRegistration",
    "AggregatedHealth",
    "HealthAggregator",
    # Plugins Module (v1.1)
    "PluginsModule",
    "PluginsModuleSingleton",
    "PluginBase",
    "PluginInfo",
    "PluginConfig",
    "PluginLifecycleState",
    "PluginPriority",
    "PluginRegistration",
    "PluginExecutionResult",
    # Built-in Plugins (v1.1)
    "LoggingPlugin",
    "MetricsPlugin",
    "CachingPlugin",
]
