"""
Aegis SDK Main Client.

Provides the primary entry point for the SDK.
"""

from ._http import HTTPClient
from .auth import AuthModule
from .config import ClientConfig, _resolve_env
from .core import AgentsModule, PipelinesModule, SkillsModule
from .exceptions import ConfigurationError
from .execution import ArtifactsModule, ObjectivesModule, RequestsModule, SessionsModule
from .modules import (
    A2AModule,
    AdminModule,
    AgenticDashboardModule,
    AgentPoolsModule,
    AnalyticsModule,
    ApplicationsModule,
    AuthUsersModule,
    BridgesModule,
    ComplianceModule,
    ConnectorsModule,
    CredentialsModule,
    DecisionsModule,
    EmergencyBypassModule,
    GovernanceExplainModule,
    GovernanceModule,
    IntegrationsModule,
    KillSwitchModule,
    KnowledgeGovernModule,
    LlmProvidersModule,
    MetricsModule,
    NotificationsModule,
    ObserveAuditModule,
    OrgStandupModule,
    PoolsModule,
    PositionsModule,
    PromotionsModule,
    PseudoAgentsModule,
    ReviewDecisionsModule,
    RolesModule,
    SettingsModule,
    SpecialistSystemModule,
    SurfacesModule,
    TaskAgentsModule,
    ToolAgentsModule,
    ToolsModule,
    TrustPostureModule,
    WebhooksModule,
    WorkObjectivesModule,
    WorkspacesModule,
)
from .modules.presentation import PresentationModule
from .revenue import (
    BillingModule,
    FeaturesModule,
    InvoicesModule,
    LicensesModule,
    PlansModule,
    QuotasModule,
    SubscriptionsModule,
    UsageModule,
)
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
from .trust import (
    AgentTrustModule,
    AuditModule,
    AuthoritiesModule,
    ChainsModule,
    DelegationsModule,
    ESAModule,
    PipelineTrustModule,
    PosturesModule,
    RevocationModule,
    TrustObservabilityModule,
    TrustRegistryModule,
)

# isort: off
# APPENDED AT THE END OF THE IMPORT BLOCK, not inserted alphabetically, and the
# fence above is what makes that survive `ruff`. Several lanes append here
# concurrently; two additions at the tail merge cleanly, while two insertions
# "in the right place" interleave into an order neither branch produced — green
# on each branch alone, broken only in the composed tree, which is this repo's
# canonical composition hazard the repository's import-sort gate catches.
#
# ⛔ `isort: off` is NOT a lint suppression here — it is the declaration that
# ORDER IS DELIBERATE in this region. Without it `ruff` reports I001 and the
# blocking ruff gate reds; with it sorted, the merge hazard returns. Append new
# tail imports BELOW this line and above `isort: on`.
from .dataflow import DataFlowModules

# isort: on


class TrustModules:
    """
    Trust management modules container.

    Provides access to trust-related operations following EATP.

    Attributes:
        chains: Trust chain management
        delegations: Trust delegation management
        postures: Agent posture management
        audit: Trust audit log queries
        agents: Per-agent trust reads (capabilities, score, CARE budget)
        authorities: Organizational signing authorities
        registry: Agent registration and capability discovery
        pipeline: Pipeline-scoped trust validation
        revocation: Trust revocation and incomplete-cascade recovery
        observability: Trust metrics, compliance reports, plane health
        esa: Enterprise Security Authority configuration
    """

    def __init__(self, http_client):
        """Initialize trust modules."""
        self.chains = ChainsModule(http_client)
        self.delegations = DelegationsModule(http_client)
        self.postures = PosturesModule(http_client)
        self.audit = AuditModule(http_client)
        self.agents = AgentTrustModule(http_client)
        self.authorities = AuthoritiesModule(http_client)
        self.registry = TrustRegistryModule(http_client)
        self.pipeline = PipelineTrustModule(http_client)
        self.revocation = RevocationModule(http_client)
        self.observability = TrustObservabilityModule(http_client)
        self.esa = ESAModule(http_client)


class RevenueModules:
    """
    Revenue management modules container.

    Provides access to billing, subscriptions, licenses, and usage tracking.

    Attributes:
        subscriptions: Subscription management (subscribe, upgrade, cancel)
        plans: Plan information and comparison
        licenses: License management for self-hosted deployments
        usage: Usage tracking against quotas
        quotas: Quota management and limit checking
        invoices: Invoice history and downloads
        features: Feature-gate / entitlement checks
        billing: Non-subscription billing (payment-method setup)
    """

    def __init__(self, http_client):
        """Initialize revenue modules."""
        self.subscriptions = SubscriptionsModule(http_client)
        self.plans = PlansModule(http_client)
        self.licenses = LicensesModule(http_client)
        self.usage = UsageModule(http_client)
        self.quotas = QuotasModule(http_client)
        self.invoices = InvoicesModule(http_client)
        self.features = FeaturesModule(http_client)
        self.billing = BillingModule(http_client)


class AgenticOSClient:
    """
    Main client for Aegis SDK.

    Provides access to all SDK modules for managing agents, skills,
    pipelines, and other platform resources.

    Examples:
        # API key authentication (base_url is REQUIRED — either pass it
        # explicitly, as shown, or set AEGIS_BASE_URL and omit it)
        >>> client = AgenticOSClient(
        ...     base_url="https://your-aegis-instance.example.com",  # placeholder — your deployment
        ...     api_key="sk_live_...",
        ... )
        >>> agents = await client.agents.list()

        # From environment variables (AEGIS_BASE_URL + AEGIS_API_KEY set)
        >>> client = AgenticOSClient.from_env()
        >>> agent = await client.agents.create(name="My Agent")

        # As async context manager (recommended)
        >>> async with AgenticOSClient(
        ...     base_url="https://your-aegis-instance.example.com",  # placeholder
        ...     api_key="sk_live_...",
        ... ) as client:
        ...     agent = await client.agents.create(name="My Agent")
        ...     result = await client.agents.execute(agent.id, "Hello!")

        # With custom configuration
        >>> config = ClientConfig(
        ...     base_url="https://your-aegis-instance.example.com",  # placeholder
        ...     api_key="sk_live_...",
        ...     timeout=60.0
        ... )
        >>> client = AgenticOSClient(config=config)

    Attributes:
        auth: Authentication module for login, logout, API keys
        agents: Agent management and execution
        skills: Skill management
        pipelines: Pipeline management and execution
        objectives: Objective management (top-level work units)
        requests: Request management (work items within objectives)
        sessions: Work session management with streaming
        artifacts: Artifact upload, version history, supersede, download, delete
        trust: Trust management (chains, delegations, postures, audit)
        revenue: Revenue management (subscriptions, licenses, usage, quotas, invoices)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        config: ClientConfig | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        debug: bool = False,
        **kwargs,
    ):
        """
        Initialize the Agentic OS client.

        Args:
            base_url: API base URL for your Aegis deployment. REQUIRED --
                pass it explicitly here, or set the ``AEGIS_BASE_URL``
                environment variable and omit this argument (the former
                ``AGENTIC_OS_BASE_URL`` is still read, and is deprecated).
                There is no hardcoded fallback host: a dead/placeholder
                default would silently misdirect every request.
            api_key: API key for authentication
            config: Full ClientConfig object (overrides other args)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            debug: Enable debug logging
            **kwargs: Additional ClientConfig options

        Raises:
            ConfigurationError: If no ``base_url`` is resolvable from either
                the ``base_url`` argument or the ``AEGIS_BASE_URL``
                environment variable -- nor the deprecated
                ``AGENTIC_OS_BASE_URL`` -- and ``config`` was not supplied.
        """
        # Build config from arguments
        if config is None:
            resolved_base_url = base_url or _resolve_env("BASE_URL")
            if not resolved_base_url:
                raise ConfigurationError(
                    "AgenticOSClient requires a base_url. Pass base_url=... "
                    "explicitly, set the AEGIS_BASE_URL environment "
                    "variable, or use AgenticOSClient.from_env() / "
                    "ClientConfig.from_env(). (The former name "
                    "AGENTIC_OS_BASE_URL is still read, and is deprecated.)"
                )
            config = ClientConfig(
                base_url=resolved_base_url,
                api_key=api_key,
                timeout=timeout or 30.0,
                max_retries=max_retries or 3,
                debug=debug,
                **kwargs,
            )

        self._config = config

        # Initialize HTTP client
        self._http = HTTPClient(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=config.max_retries,
            retry_backoff=config.retry_backoff,
            verify_ssl=config.verify_ssl,
            debug=config.debug,
        )

        # Initialize modules
        self.auth = AuthModule(self._http)
        self.agents = AgentsModule(self._http)
        self.skills = SkillsModule(self._http)
        self.pipelines = PipelinesModule(self._http)

        # Execution modules
        self.objectives = ObjectivesModule(self._http)
        self.requests = RequestsModule(self._http)
        self.sessions = SessionsModule(self._http)
        self.artifacts = ArtifactsModule(self._http)
        self.presentation = PresentationModule(self._http)

        # Trust modules (grouped under trust namespace)
        self.trust = TrustModules(self._http)

        # Revenue modules (grouped under revenue namespace)
        self.revenue = RevenueModules(self._http)

        # Vertical-standup modules (org hierarchy, knowledge, HOTL)
        self.organizations = OrganizationsModule(self._http)
        self.units = OrganizationUnitsModule(self._http)
        self.roles = OrganizationRolesModule(self._http)
        self.teams = TeamsModule(self._http)
        self.role_envelopes = RoleEnvelopesModule(self._http)
        self.knowledge = KnowledgeModule(self._http)
        self.ontology = OntologyModule(self._http)
        self.approvals = ApprovalsModule(self._http)

        # Advanced modules (SDK-only features)
        self.a2a = A2AModule(self._http)
        # Bridges: standing / scoped / ad-hoc (three distinct record types)
        self.bridges = BridgesModule(self._http)
        self.analytics = AnalyticsModule(self._http)
        self.connectors = ConnectorsModule(self._http)
        self.notifications = NotificationsModule(self._http)
        self.webhooks = WebhooksModule(self._http)
        self.governance = GovernanceModule(self._http)
        self.compliance = ComplianceModule(self._http)
        self.pools = PoolsModule(self._http)
        self.agent_pools = AgentPoolsModule(self._http)
        self.positions = PositionsModule(self._http)
        self.tools = ToolsModule(self._http)
        self.workspaces = WorkspacesModule(self._http)
        self.pseudo_agents = PseudoAgentsModule(self._http)

        # Governance decision surfaces (write methods need a user session,
        # not an API key — see DecisionsModule's credential note)
        self.decisions = DecisionsModule(self._http)
        self.review_decisions = ReviewDecisionsModule(self._http)

        # Full role-administration surface (/api/v1/roles). Distinct from
        # self.roles above, which covers two operations on
        # /api/v1/organization-roles and returns untyped dicts.
        self.role_admin = RolesModule(self._http)

        # Encrypted credential store. Whole surface needs a user session;
        # an API key is refused on every route including the reads.
        self.credentials = CredentialsModule(self._http)

        # Break-glass surfaces. Both need a user session; an API key is
        # refused on every route, reads included.
        self.emergency_bypass = EmergencyBypassModule(self._http)
        self.kill_switch = KillSwitchModule(self._http)

        # Environment promotion. Architect persona only — an org admin
        # holding every promotions grant is still refused.
        self.promotions = PromotionsModule(self._http)

        # Governance diagnostics mount (/api/v1/governance). Read-only, and
        # unlike the write surfaces above it does accept an API key.
        self.governance_explain = GovernanceExplainModule(self._http)

        #(observe, agents-build, admin-settings domains)
        self.agentic_dashboard = AgenticDashboardModule(self._http)
        self.metrics = MetricsModule(self._http)
        self.observe_audit = ObserveAuditModule(self._http)
        self.tool_agents = ToolAgentsModule(self._http)
        self.task_agents = TaskAgentsModule(self._http)
        self.specialist_system = SpecialistSystemModule(self._http)
        self.admin = AdminModule(self._http)
        self.applications = ApplicationsModule(self._http)
        self.settings = SettingsModule(self._http)
        self.llm_providers = LlmProvidersModule(self._http)

        #s (trust-posture, knowledge-govern,
        # work-objectives, auth-users, org-standup, integrations)
        self.trust_posture = TrustPostureModule(self._http)
        self.knowledge_govern = KnowledgeGovernModule(self._http)
        self.work_objectives = WorkObjectivesModule(self._http)
        self.auth_users = AuthUsersModule(self._http)
        self.org_standup = OrgStandupModule(self._http)
        self.integrations = IntegrationsModule(self._http)

        # Architect-tier surface registry. The manifest read is open to every
        # persona; every authoring route additionally requires an
        # architect/admin/executive persona AND a surfaces:<verb> permission.
        self.surfaces = SurfacesModule(self._http)

        # APPENDED AT THE END of the module list, not grouped beside a related
        # surface — see the import-block note above for why the tail is the
        # only safe insertion point while sibling lanes are appending too.
        #
        # Data-plane reach: invocation lineage (/api/v1/lineage) and the data
        # lineage graph (/api/v1/data-governance/lineage). Ten routes that the
        # SDK could not address, so a partner could read an impact analysis of
        # a graph they had no way to build.
        self.dataflow = DataFlowModules(self._http)

    @classmethod
    def from_env(cls) -> "AgenticOSClient":
        """
        Create client from environment variables.

        Environment Variables:
            AEGIS_BASE_URL: API base URL -- REQUIRED, no default
            AEGIS_API_KEY: API key for authentication
            AEGIS_TIMEOUT: Request timeout in seconds
            AEGIS_DEBUG: Enable debug mode ("true"/"false")

        The ``AGENTIC_OS_`` prefix is the SDK's original naming; it is still
        read for each variable above and emits a one-time deprecation
        warning. When both names are set, the ``AEGIS_`` value wins.

        Returns:
            AgenticOSClient configured from environment

        Raises:
            ConfigurationError: If neither ``AEGIS_BASE_URL`` nor the
                deprecated ``AGENTIC_OS_BASE_URL`` is set

        Example:
            >>> # Set env vars first:
            >>> #   export AEGIS_BASE_URL=https://your-aegis-instance.example.com
            >>> #   export AEGIS_API_KEY=sk_live_...
            >>> client = AgenticOSClient.from_env()
        """
        config = ClientConfig.from_env()
        return cls(config=config)

    @property
    def base_url(self) -> str:
        """Get the configured base URL."""
        return self._config.base_url

    @property
    def api_key(self) -> str | None:
        """Get the configured API key (partially masked)."""
        if self._config.api_key:
            key = self._config.api_key
            if len(key) > 12:
                return f"{key[:8]}...{key[-4:]}"
            return key[:4] + "..."
        return None

    def set_api_key(self, api_key: str) -> None:
        """
        Update the API key.

        Args:
            api_key: New API key to use

        Example:
            >>> # After login, set the received token
            >>> token = await client.auth.login(email, password)
            >>> client.set_api_key(token.access_token)
        """
        self._config.api_key = api_key
        self._http.set_api_key(api_key)

    def set_auth_token(self, token: str) -> None:
        """
        Set authentication token (alias for set_api_key).

        Args:
            token: Authentication token

        Example:
            >>> token = await client.auth.login(email, password)
            >>> client.set_auth_token(token.access_token)
        """
        self.set_api_key(token)

    async def close(self) -> None:
        """
        Close the HTTP client and release connections.

        Should be called when done using the client, or use
        the async context manager pattern instead.

        Example:
            >>> client = AgenticOSClient(api_key="sk_live_...")
            >>> try:
            ...     await client.agents.list()
            ... finally:
            ...     await client.close()
        """
        await self._http.close()

    async def __aenter__(self) -> "AgenticOSClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - closes HTTP client."""
        await self.close()

    def __repr__(self) -> str:
        """String representation. API key is masked to prevent credential leakage in logs."""
        masked = (
            f"{self.api_key[:8]}...{self.api_key[-4:]}"
            if self.api_key and len(self.api_key) > 12
            else "***"
        )
        return f"AgenticOSClient(base_url='{self.base_url}', api_key='{masked}')"


# Convenience alias
Client = AgenticOSClient
