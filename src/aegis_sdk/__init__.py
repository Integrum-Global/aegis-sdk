"""
Aegis SDK

A Python SDK for programmatic access to the Agentic OS platform.
Provides async-first APIs for managing agents, skills, pipelines,
and other platform resources.

Quick Start:
    >>> import os
    >>> from aegis_sdk import AgenticOSClient
    >>>
    >>> # base_url has no hardcoded default -- set AGENTIC_OS_BASE_URL to
    >>> # your Aegis deployment, or pass base_url=... explicitly.
    >>> async with AgenticOSClient(
    ...     base_url=os.environ["AGENTIC_OS_BASE_URL"],
    ...     api_key="sk_live_...",
    ... ) as client:
    ...     # List agents
    ...     agents = await client.agents.list()
    ...
    ...     # Create and execute an agent (agent_type is one of
    ...     # "chat" / "task" / "pipeline" / "custom"; model_id is read from
    ...     # env -- never hardcode a model name)
    ...     agent = await client.agents.create(
    ...         name="Research Assistant",
    ...         agent_type="chat",
    ...         model_id=os.environ["AGENTIC_OS_MODEL"],
    ...     )
    ...     result = await client.agents.execute(
    ...         agent.id,
    ...         objective="Research quantum computing"
    ...     )

Environment Variables:
    AEGIS_BASE_URL: API base URL -- REQUIRED, no default
    AEGIS_API_KEY: API key for authentication
    AEGIS_TIMEOUT: Request timeout in seconds (default: 30)
    AEGIS_DEBUG: Enable debug logging (default: false)

    The ``AGENTIC_OS_`` prefix is the SDK's original naming for the four
    variables above. It is still read, so existing deployments keep
    working, and emits a one-time DeprecationWarning naming its ``AEGIS_``
    replacement. When both names are set, the ``AEGIS_`` value wins.

    AEGIS_MODEL: LLM model ID to use for agents you create via the SDK
        (the SDK never hardcodes a model name -- your scripts should read
        this, or an equivalent, from your own environment)
    AEGIS_WORKSPACE_ID: Workspace to create agents in. Like AEGIS_MODEL
        this is a convention the shipped examples follow, not a variable
        the SDK reads: ``agents.create()`` REQUIRES ``workspace_id`` and
        raises ValidationError without it, so every example that creates
        an agent has to source one from somewhere. Because the SDK never
        reads these two, neither the precedence nor the deprecation
        warning above applies to them -- the shipped examples still read
        the ``AGENTIC_OS_`` spelling.

Documentation:
    https://docs.agentic-os.com/sdk
"""

from ._version import __version__, __version_info__

# Main client
from .client import AgenticOSClient, Client

# Configuration
from .config import ClientConfig, OAuthConfig

# Exceptions
from .exceptions import (
    AgenticOSError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    GovernanceViolationError,
    NetworkError,
    NotFoundError,
    PaymentError,
    RateLimitError,
    RequestTimeout,
    ServiceError,
    ServiceUnavailableError,
    TimeoutError,
    TrustViolationError,
    UnsupportedOperationError,
    ValidationError,
)

# /sw2 domain modules
from .modules import (
    AdminModule,
    AgenticDashboardModule,
    ApplicationsModule,
    AuthUsersModule,
    CredentialsModule,
    DecisionsModule,
    EmergencyBypassModule,
    GovernanceExplainModule,
    IntegrationsModule,
    KillSwitchModule,
    KnowledgeGovernModule,
    LlmProvidersModule,
    McpBinding,
    McpModule,
    McpRegistration,
    MetricsModule,
    ObserveAuditModule,
    OrgStandupModule,
    PromotionsModule,
    ReviewDecisionsModule,
    RolesModule,
    SettingsModule,
    SpecialistSystemModule,
    SurfaceDeleteResult,
    SurfaceManifest,
    SurfaceManifestEntry,
    SurfaceRegistration,
    SurfaceRegistrationListResult,
    SurfacesModule,
    TaskAgentsModule,
    ToolAgentsModule,
    TrustPostureModule,
    WorkObjectivesModule,
)

# Revenue modules
from .revenue import (
    InvoicesModule,
    LicensesModule,
    PlansModule,
    QuotasModule,
    SubscriptionsModule,
    UsageModule,
)

# Vertical-standup modules
from .standup import (
    ApprovalsModule,
    KnowledgeModule,
    OntologyModule,
    OrganizationRolesModule,
    OrganizationsModule,
    OrganizationUnitsModule,
    RoleEnvelopesModule,
    TeamsModule,
)

# Types and models
from .types import (
    AffectedTrustAgent,
    # Agent models
    Agent,
    AgentCreate,
    AgentExecution,
    # Enums
    AgentStatus,
    AgentSubtype,
    AgentTrustContext,
    AgentType,
    AgentUpdate,
    # Auth models
    APIKey,
    APIKeyCreate,
    APIKeyCreated,
    AuthToken,
    BillingCycle,
    CancelRequest,
    CascadeRevocationResult,
    DelegationPath,
    DelegationStatus,
    Edition,
    EstablishedTrustChain,
    ExecutionStatus,
    Finding,
    Invoice,
    # Revenue models - Invoices
    InvoiceLineItem,
    InvoicesResponse,
    InvoiceStatus,
    # Revenue models - Licenses
    License,
    LicenseEdition,
    LicenseGenerate,
    LicenseStatus,
    LicenseUsage,
    LicenseValidation,
    LicenseValidationRequest,
    # Pipeline node-type catalogue
    NodeTypeCatalog,
    NodeTypeCategory,
    NodeTypeSummary,
    NodeTypeVerdict,
    # Execution models
    Objective,
    ObjectiveCreate,
    ObjectiveStatus,
    ObjectiveUpdate,
    # Common
    PaginatedResponse,
    # Pipeline models
    Pipeline,
    PipelineConnection,
    PipelineCreate,
    PipelineExecution,
    PipelineNode,
    PipelinePattern,
    PipelineUpdate,
    Plan,
    PlanFeatures,
    PlanTier,
    PortalSession,
    PostureMetrics,
    PostureOverride,
    PostureProgressionRequest,
    Quota,
    QuotaCheck,
    QuotaUpdate,
    Request,
    RequestClaim,
    RequestComplete,
    RequestEscalate,
    RequestStatus,
    ResourceType,
    # Revenue models - Usage & Quotas
    ResourceUsage,
    RevocationImpact,
    Session,
    SessionArtifact,
    SessionContext,
    SessionMessage,
    SessionStatus,
    # Skill models
    Skill,
    SkillCreate,
    SkillUpdate,
    StreamEvent,
    Subagent,
    SubscribeRequest,
    # Revenue models - Subscriptions & Plans
    Subscription,
    # Revenue enums
    SubscriptionStatus,
    TierComparison,
    TrustAuditEntry,
    TrustAuditQuery,
    # Trust models
    TrustChain,
    TrustChainEstablish,
    TrustChainStatus,
    TrustDelegation,
    TrustDelegationCreate,
    TrustDelegationRecord,
    TrustGenesisRecord,
    TrustHumanOriginInfo,
    TrustPosture,
    TrustPostureInfo,
    TrustVerification,
    TrustVerificationResult,
    UnitType,
    UpgradeRequest,
    Usage,
    UsageBreakdown,
    UsageHistory,
    User,
)

__all__ = [
    # Version
    "__version__",
    "__version_info__",
    # Client
    "AgenticOSClient",
    "Client",
    # Configuration
    "ClientConfig",
    "OAuthConfig",
    # Exceptions
    "AgenticOSError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "ConnectionError",
    "GovernanceViolationError",
    "NetworkError",
    "NotFoundError",
    "PaymentError",
    "RateLimitError",
    "RequestTimeout",
    "ServiceError",
    "ServiceUnavailableError",
    "TimeoutError",
    "TrustViolationError",
    "UnsupportedOperationError",
    "ValidationError",
    # Enums
    "AgentStatus",
    "AgentSubtype",
    "AgentType",
    "DelegationStatus",
    "ExecutionStatus",
    "ObjectiveStatus",
    "PipelinePattern",
    "RequestStatus",
    "SessionStatus",
    "TrustChainStatus",
    "TrustPosture",
    "UnitType",
    # Revenue enums
    "SubscriptionStatus",
    "BillingCycle",
    "PlanTier",
    "LicenseEdition",
    "ResourceType",
    "InvoiceStatus",
    # Agent models
    "Agent",
    "AgentCreate",
    "AgentExecution",
    "AgentUpdate",
    # Skill models
    "Skill",
    "SkillCreate",
    "SkillUpdate",
    # Pipeline models
    "Pipeline",
    "PipelineConnection",
    "PipelineCreate",
    "PipelineExecution",
    "PipelineNode",
    "PipelineUpdate",
    # Pipeline node-type catalogue
    "NodeTypeCatalog",
    "NodeTypeCategory",
    "NodeTypeSummary",
    "NodeTypeVerdict",
    # Auth models
    "APIKey",
    "APIKeyCreate",
    "APIKeyCreated",
    "AuthToken",
    "User",
    # Common
    "PaginatedResponse",
    # Execution models
    "Objective",
    "ObjectiveCreate",
    "ObjectiveUpdate",
    "Request",
    "RequestClaim",
    "RequestComplete",
    "RequestEscalate",
    "Finding",
    "Session",
    "SessionMessage",
    "SessionArtifact",
    "SessionContext",
    "Subagent",
    # Trust models
    "TrustChain",
    "TrustChainEstablish",
    "TrustVerification",
    "TrustVerificationResult",
    "DelegationPath",
    "AgentTrustContext",
    "TrustDelegation",
    "TrustDelegationCreate",
    "RevocationImpact",
    "AffectedTrustAgent",
    "CascadeRevocationResult",
    "EstablishedTrustChain",
    "TrustGenesisRecord",
    "TrustHumanOriginInfo",
    "TrustDelegationRecord",
    "TrustPostureInfo",
    "PostureProgressionRequest",
    "PostureOverride",
    "PostureMetrics",
    "TrustAuditEntry",
    "TrustAuditQuery",
    "StreamEvent",
    # Revenue models - Subscriptions & Plans
    "Subscription",
    "SubscribeRequest",
    "UpgradeRequest",
    "CancelRequest",
    "Plan",
    "PlanFeatures",
    "TierComparison",
    "PortalSession",
    # Revenue models - Licenses
    "License",
    "LicenseGenerate",
    "LicenseValidation",
    "LicenseValidationRequest",
    "LicenseUsage",
    "LicenseStatus",
    "Edition",
    # Revenue models - Usage & Quotas
    "ResourceUsage",
    "Usage",
    "UsageHistory",
    "UsageBreakdown",
    "Quota",
    "QuotaUpdate",
    "QuotaCheck",
    # Revenue models - Invoices
    "InvoiceLineItem",
    "Invoice",
    "InvoicesResponse",
    # Revenue modules
    "SubscriptionsModule",
    "PlansModule",
    "LicensesModule",
    "UsageModule",
    "QuotasModule",
    "InvoicesModule",
    # Vertical-standup modules
    "OrganizationsModule",
    "OrganizationUnitsModule",
    "OrganizationRolesModule",
    "TeamsModule",
    "RoleEnvelopesModule",
    "KnowledgeModule",
    "OntologyModule",
    "ApprovalsModule",
    #
    "AdminModule",
    "AgenticDashboardModule",
    "ApplicationsModule",
    "LlmProvidersModule",
    "McpBinding",
    "McpModule",
    "McpRegistration",
    "MetricsModule",
    "ObserveAuditModule",
    "SettingsModule",
    "SpecialistSystemModule",
    "SurfaceDeleteResult",
    "SurfaceManifest",
    "SurfaceManifestEntry",
    "SurfaceRegistration",
    "SurfaceRegistrationListResult",
    "SurfacesModule",
    "TaskAgentsModule",
    "ToolAgentsModule",
    # s
    "AuthUsersModule",
    "CredentialsModule",
    "DecisionsModule",
    "EmergencyBypassModule",
    "GovernanceExplainModule",
    "KillSwitchModule",
    "PromotionsModule",
    "ReviewDecisionsModule",
    "RolesModule",
    "IntegrationsModule",
    "KnowledgeGovernModule",
    "OrgStandupModule",
    "TrustPostureModule",
    "WorkObjectivesModule",
]
