"""
Advanced SDK Modules.

Provides programmatic access to platform operations including analytics,
connectors, notifications, webhooks, governance, compliance, admin, pools, and A2A.
"""

from .a2a import A2AModule
from .admin import AdminModule
from .agent_pools import AgentPoolList, AgentPoolMemberList, AgentPoolsModule
from .agentic_dashboard import AgenticDashboardModule
from .analytics import AnalyticsModule
from .applications import ApplicationsModule
from .auth_users import AuthUsersModule
from .bridges import (
    AdHocBridgesModule,
    BridgesModule,
    ScopedBridgesModule,
    StandingBridgesModule,
)
from .compliance import ComplianceModule
from .connectors import ConnectorsModule
from .credentials import CredentialsModule
from .decision_points import DecisionsModule, ReviewDecisionsModule
from .emergency import EmergencyBypassModule, KillSwitchModule
from .governance import GovernanceModule
from .governance_explain import GovernanceExplainModule
from .integrations import IntegrationsModule
from .knowledge_govern import KnowledgeGovernModule
from .llm_providers import LlmProvidersModule
from .mcp import McpBinding, McpModule, McpRegistration
from .metrics import MetricsModule
from .notifications import NotificationsModule
from .objective_workspaces import (
    ObjectiveWorkspace,
    ObjectiveWorkspacesModule,
    WorkspaceAgentSession,
    WorkspaceAuditTrail,
    WorkspaceCondensePreview,
    WorkspaceHierarchy,
    WorkspaceProgress,
    WorkspaceReply,
    WorkspaceThread,
    WorkspaceThreadList,
    WorkspaceThreadMessage,
    WorkspaceThreadMessageList,
)
from .observe_audit import ObserveAuditModule
from .org_standup import OrgStandupModule
from .pools import PoolsModule
from .positions import Position, PositionsModule
from .promotions import PromotionsModule
from .pseudo_agents import PseudoAgentsModule
from .roles import RolesModule
from .settings import SettingsModule
from .specialist_system import SpecialistSystemModule
from .surfaces import (
    SurfaceDeleteResult,
    SurfaceManifest,
    SurfaceManifestEntry,
    SurfaceRegistration,
    SurfaceRegistrationListResult,
    SurfacesModule,
)
from .task_agents import TaskAgentsModule
from .tool_agents import ToolAgentsModule
from .tools import ToolList, ToolsModule, ToolValidation
from .trust_posture import TrustPostureModule
from .webhooks import WebhooksModule
from .work_objectives import WorkObjectivesModule
from .workspaces import (
    Workspace,
    WorkspaceMember,
    WorkspaceMessage,
    WorkspacesModule,
    WorkspaceSummary,
    WorkspaceWorkUnit,
)

__all__ = [
    "A2AModule",
    "AdHocBridgesModule",
    "AdminModule",
    "AgentPoolList",
    "AgentPoolMemberList",
    "AgentPoolsModule",
    "AgenticDashboardModule",
    "AnalyticsModule",
    "ApplicationsModule",
    "AuthUsersModule",
    "BridgesModule",
    "ComplianceModule",
    "ConnectorsModule",
    "CredentialsModule",
    "DecisionsModule",
    "EmergencyBypassModule",
    "GovernanceExplainModule",
    "GovernanceModule",
    "IntegrationsModule",
    "KillSwitchModule",
    "KnowledgeGovernModule",
    "LlmProvidersModule",
    "McpBinding",
    "McpModule",
    "McpRegistration",
    "MetricsModule",
    "NotificationsModule",
    "ObjectiveWorkspace",
    "ObjectiveWorkspacesModule",
    "ObserveAuditModule",
    "OrgStandupModule",
    "PoolsModule",
    "Position",
    "PositionsModule",
    "PromotionsModule",
    "PseudoAgentsModule",
    "ReviewDecisionsModule",
    "RolesModule",
    "ScopedBridgesModule",
    "SettingsModule",
    "SpecialistSystemModule",
    "StandingBridgesModule",
    "SurfaceDeleteResult",
    "SurfaceManifest",
    "SurfaceManifestEntry",
    "SurfaceRegistration",
    "SurfaceRegistrationListResult",
    "SurfacesModule",
    "TaskAgentsModule",
    "ToolAgentsModule",
    "ToolList",
    "ToolValidation",
    "ToolsModule",
    "TrustPostureModule",
    "WebhooksModule",
    "WorkObjectivesModule",
    "Workspace",
    "WorkspaceAgentSession",
    "WorkspaceAuditTrail",
    "WorkspaceCondensePreview",
    "WorkspaceHierarchy",
    "WorkspaceMember",
    "WorkspaceMessage",
    "WorkspaceProgress",
    "WorkspaceReply",
    "WorkspaceSummary",
    "WorkspaceThread",
    "WorkspaceThreadList",
    "WorkspaceThreadMessage",
    "WorkspaceThreadMessageList",
    "WorkspaceWorkUnit",
    "WorkspacesModule",
]
