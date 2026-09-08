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
from .metrics import MetricsModule
from .notifications import NotificationsModule
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
    "BridgesModule",
    "ScopedBridgesModule",
    "StandingBridgesModule",
    "AnalyticsModule",
    "ConnectorsModule",
    "CredentialsModule",
    "DecisionsModule",
    "EmergencyBypassModule",
    "KillSwitchModule",
    "ReviewDecisionsModule",
    "NotificationsModule",
    "WebhooksModule",
    "GovernanceModule",
    "GovernanceExplainModule",
    "ComplianceModule",
    "PoolsModule",
    "Position",
    "AgentPoolList",
    "AgentPoolMemberList",
    "AgentPoolsModule",
    "PositionsModule",
    "ToolList",
    "ToolValidation",
    "ToolsModule",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceMessage",
    "WorkspaceSummary",
    "WorkspaceWorkUnit",
    "WorkspacesModule",
    "PseudoAgentsModule",
    "PromotionsModule",
    "RolesModule",
    #
    "AdminModule",
    "AgenticDashboardModule",
    "ApplicationsModule",
    "LlmProvidersModule",
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
    #s
    "AuthUsersModule",
    "IntegrationsModule",
    "KnowledgeGovernModule",
    "OrgStandupModule",
    "TrustPostureModule",
    "WorkObjectivesModule",
]
