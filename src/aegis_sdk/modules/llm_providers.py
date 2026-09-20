"""
LLM Providers Module for Agentic OS SDK.

Thin HTTP-wrapper for LLM provider listing and CONFIGURATION, model discovery,
validation, health checks and effective rate-card reads -- the Live LLM Provider
Integrations admin surface.

Self-contained module: request/response models are
defined LOCALLY in this file. Do not import from ``aegis_sdk.types`` or
edit ``modules/__init__.py`` / ``client.py`` -- a separate orchestrator
wiring pass registers this module on the client.

Backend routes, cited per-method below. The server mounts this surface under
``/api/v1/llm``, so every path below is ``/api/v1/llm/...``.

All 11 routes on that surface -- DERIVED from the router, never hand-counted.
A surface-parity test fails when this table and the router disagree in EITHER
direction:
  - list_providers()        GET    /api/v1/llm/providers
  - create_provider()       POST   /api/v1/llm/providers
  - update_provider()       PUT    /api/v1/llm/providers/{provider}
  - delete_provider()       DELETE /api/v1/llm/providers/{provider} -- answers
    405 METHOD_NOT_ALLOWED by design and is deliberately NOT wrapped: disable a
    provider with ``update_provider(..., is_enabled=False)`` instead.
  - list_models()           GET    /api/v1/llm/models
  - get_all_models()        GET    /api/v1/llm/models/all
  - validate_model()        POST   /api/v1/llm/models/validate
  - refresh_provider_cache() POST  /api/v1/llm/providers/{provider}/refresh
  - check_provider_health() GET    /api/v1/llm/providers/{provider}/health
  - get_model_metadata()    GET    /api/v1/llm/models/{provider}/{model_id}/metadata
  - get_rate_card()         GET    /api/v1/llm/pricing

⛔ THIS TABLE SAID "All 7 routes" UNTIL 2026-09-18, AND THAT DENOMINATOR WAS THE
DEFECT. The router mounts 11. Nothing compares the two sides at method
granularity, so the undercount did not merely mislead a reader -- it was the
instrument: three served operations (create, update, rate card) had no SDK
method, and the docstring certified the surface as complete. A denominator
nobody derives drifts silently in exactly this direction, which is why the table
is now pinned by a test rather than maintained by attention.

Security note: API keys are NEVER exposed in any
of these responses (backend-only); ``refresh_provider_cache`` is rate
limited server-side to 5 requests/hour/user. ``service_account_secret_ref`` is
the NAME of an environment variable and never a credential -- this API cannot
install or rotate a provider credential at runtime, for any provider family.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

# ---------------------------------------------------------------------------
# Response models (verified -- no Pydantic alias
# generator on any model, so JSON keys are the same snake_case as the
# field names below).
# ---------------------------------------------------------------------------


class Provider(TolerantModel):
    """LLM provider status (response shape)."""

    name: str
    display_name: str = ""
    status: str = "offline"  # available, degraded, offline
    is_configured: bool = False
    is_enabled: bool = True
    last_health_check: str | None = None
    rate_limit_rpm: int = 0
    rate_limit_tpm: int = 0


class ProvidersListResult(TolerantModel):
    """Envelope for GET /llm/providers."""

    providers: list[Provider] = Field(default_factory=list)


class ModelCapabilities(TolerantModel):
    """Model capabilities."""

    vision: bool = False
    function_calling: bool = False
    streaming: bool = True
    json_mode: bool = False
    code_interpreter: bool = False


class LlmModel(TolerantModel):
    """LLM model metadata (response shape)."""

    model_id: str
    display_name: str = ""
    description: str = ""
    is_available: bool = True
    is_deprecated: bool = False
    deprecation_date: str | None = None
    replacement_model: str | None = None
    context_window: int = 0
    max_output_tokens: int = 0
    cost_per_1k_input_tokens: float = 0.0
    cost_per_1k_output_tokens: float = 0.0
    capabilities: ModelCapabilities | None = None
    model_family: str | None = None
    model_version: str | None = None
    avg_latency_ms: int = 0


class ModelsListResult(TolerantModel):
    """Envelope for GET /llm/models."""

    provider: str = ""
    models: list[LlmModel] = Field(default_factory=list)
    cached_at: str | None = None
    from_cache: bool = False
    fallback: bool = False


class AllModelsResult(TolerantModel):
    """Envelope for GET /llm/models/all."""

    models: dict[str, list[LlmModel]] = Field(default_factory=dict)


class ModelValidationResult(TolerantModel):
    """Result of POST /llm/models/validate."""

    is_valid: bool
    message: str = ""
    is_deprecated: bool = False
    replacement_model: str | None = None
    model: LlmModel | None = None


class CacheRefreshResult(TolerantModel):
    """Result of POST /llm/providers/{provider}/refresh."""

    success: bool = False
    models_found: int = 0
    cached_at: str | None = None
    fallback: bool = False


class ProviderHealth(TolerantModel):
    """Result of GET /llm/providers/{provider}/health."""

    provider: str
    is_healthy: bool = False
    status: str = "offline"  # available, degraded, offline
    message: str = ""
    latency_ms: int = 0
    rate_limit_rpm: int = 0
    rate_limit_remaining: int | None = None
    checked_at: str = ""


class ModelMetadata(TolerantModel):
    """Result of GET /llm/models/{provider}/{model_id}/metadata."""

    model_id: str
    provider: str
    display_name: str = ""
    description: str = ""
    context_window: int = 0
    max_output_tokens: int = 0
    cost_per_1k_input_tokens: float = 0.0
    cost_per_1k_output_tokens: float = 0.0
    cost_per_1k_cached_tokens: float = 0.0
    avg_latency_ms: int = 0
    capabilities: ModelCapabilities | None = None
    is_available: bool = True
    is_deprecated: bool = False
    deprecation_date: str | None = None
    replacement_model: str | None = None
    model_family: str | None = None
    model_version: str | None = None
    last_validated: str | None = None


class ProviderConfig(TolerantModel):
    """One organization's provider CONFIGURATION row -- the response of
    ``POST /llm/providers`` and ``PUT /llm/providers/{provider}``.

    Mirrors the server's ``ProviderConfigResponse`` whitelist, which is built
    field-by-field rather than splatted from the row precisely so a FUTURE
    credential-bearing column cannot reach the wire by default. The same
    reading applies here: this model names every field it accepts rather than
    passing the response dict through.

    ``service_account_secret_ref`` is the NAME of an environment variable, never
    a credential value -- the API cannot install or rotate a provider credential
    at runtime, so the variable must already exist in the running deployment.

    Field defaults mirror the server's OWN defaults (``LLMProvider`` /
    ``CreateLLMProviderRequest``), which is the only condition under which a
    default may stand in for an absent value.
    """

    id: str
    organization_id: str
    name: str
    display_name: str = ""
    api_base_url: str = ""
    health_check_endpoint: str = ""
    status: str = "offline"  # available, degraded, offline
    is_enabled: bool = True
    is_configured: bool = False
    timeout_seconds: int = 30
    priority: int = 0
    deployment_preset: str | None = None
    gcp_project: str | None = None
    gcp_region: str | None = None
    service_account_secret_ref: str | None = None
    azure_resource: str | None = None
    azure_deployment: str | None = None
    aws_region: str | None = None
    bedrock_auth_kind: str | None = None
    default_model: str | None = None
    created_at: str = ""
    updated_at: str = ""


class RateCardEntry(TolerantModel):
    """One priced model, as the METERING path actually sees it."""

    model_id: str
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    base_cost_per_call: float = 0.0
    source_sku: str = ""


class RateCardProvider(TolerantModel):
    """One provider's rate table plus how much it can be trusted today.

    ``last_verified`` / ``age_days`` / ``is_stale`` / ``is_expired`` are REQUIRED
    here, deliberately and against this module's usual generous-defaulting
    style: the freshness of the table is the point of the endpoint, and a
    defaulted ``is_stale=False`` would turn "the server told us nothing" into
    "the rates are current" -- a default that GRANTS, which is the fail-open
    shape ``_tolerant.py`` forbids. An absent one is a server fault and raises.
    """

    provider: str
    last_verified: str
    age_days: int
    is_stale: bool
    is_expired: bool
    source_url: str
    basis: str
    models: list[RateCardEntry] = Field(default_factory=list)


class RateCard(TolerantModel):
    """The effective LLM rate card and its freshness -- ``GET /llm/pricing``.

    ``any_stale`` is REQUIRED for the same reason as ``RateCardProvider``'s
    freshness fields: a defaulted ``False`` reads as "nothing needs
    re-checking".
    """

    providers: list[RateCardProvider] = Field(default_factory=list)
    stale_after_days: int
    expired_after_days: int
    any_stale: bool
    azure_deployment_model_map: dict[str, str] = Field(default_factory=dict)
    generated_at: str


class LlmProvidersModule:
    """
    LLM providers module -- provider listing, model discovery, model
    validation, and provider health checks.

    Examples:
        # List configured providers
        >>> providers = await client.llm_providers.list_providers()
        >>> for p in providers.providers:
        ...     print(f"{p.name}: {p.status}")

        # Discover models for a provider
        >>> models = await client.llm_providers.list_models("anthropic")
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize LLM providers module.

        Args:
            http_client: HTTPClient instance for API requests.
        """
        self._http = http_client

    async def list_providers(self) -> ProvidersListResult:
        """List all configured LLM providers with status
        (GET /llm/providers)."""
        response = await self._http.request(
            "GET",
            "/api/v1/llm/providers",
        )
        return ProvidersListResult(**response)

    async def create_provider(
        self,
        name: str,
        display_name: str | None = None,
        deployment_preset: str | None = None,
        gcp_project: str | None = None,
        gcp_region: str | None = None,
        service_account_secret_ref: str | None = None,
        azure_resource: str | None = None,
        azure_deployment: str | None = None,
        aws_region: str | None = None,
        bedrock_auth_kind: str | None = None,
        default_model: str | None = None,
        api_base_url: str | None = None,
        is_enabled: bool = True,
        priority: int = 0,
        timeout_seconds: int = 30,
    ) -> ProviderConfig:
        """Create this organization's provider configuration
        (POST /llm/providers).

        Args:
            name: Provider name, one of the platform's ``VALID_PROVIDERS``
                (openai, anthropic, google, ollama, ...). Rejected with 400 at
                the route AND again in the service layer.
            display_name: Human-readable label.
            deployment_preset: Named deployment shape, validated at WRITE time
                against the rest of the supplied fields -- a Vertex preset with
                no ``service_account_secret_ref`` is a 400 before anything is
                persisted, rather than a row that fails later at call time.
            gcp_project: Vertex project id.
            gcp_region: Vertex region.
            service_account_secret_ref: NAME of an environment variable holding
                the service-account JSON -- never the credential itself. This
                API cannot install or rotate a provider credential at runtime,
                so the variable must already exist in the running deployment.
            azure_resource: Azure OpenAI resource name.
            azure_deployment: Azure deployment name.
            aws_region: Bedrock region.
            bedrock_auth_kind: Bedrock credential kind.
            default_model: Model this organization binds to the provider when a
                caller supplies none. Consulted BEFORE the deployment's
                environment variables, so a routine model change is
                configuration rather than a redeploy.
            api_base_url: Override of the provider's API base.
            is_enabled: Usable immediately.
            priority: Selection order among configured providers.
            timeout_seconds: Per-call timeout for this provider.

        Returns:
            ProviderConfig for the created row. The row belongs to the CALLER's
            organization, derived from the authenticated session and never from
            this body.

        Raises:
            ValidationError: 400 -- unknown provider name, or a
                ``deployment_preset`` inconsistent with the supplied fields.
            AuthorizationError: 403 -- the caller is outside the router's
                persona gate (admin / architect).
        """
        data: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("display_name", display_name),
            ("deployment_preset", deployment_preset),
            ("gcp_project", gcp_project),
            ("gcp_region", gcp_region),
            ("service_account_secret_ref", service_account_secret_ref),
            ("azure_resource", azure_resource),
            ("azure_deployment", azure_deployment),
            ("aws_region", aws_region),
            ("bedrock_auth_kind", bedrock_auth_kind),
            ("default_model", default_model),
            ("api_base_url", api_base_url),
            ("is_enabled", is_enabled),
            ("priority", priority),
            ("timeout_seconds", timeout_seconds),
        ):
            if value is not None:
                data[key] = value

        response = await self._http.request(
            "POST",
            "/api/v1/llm/providers",
            json_data=data,
        )
        return ProviderConfig(**response)

    async def update_provider(
        self,
        provider: str,
        display_name: str | None = None,
        deployment_preset: str | None = None,
        gcp_project: str | None = None,
        gcp_region: str | None = None,
        service_account_secret_ref: str | None = None,
        azure_resource: str | None = None,
        azure_deployment: str | None = None,
        aws_region: str | None = None,
        bedrock_auth_kind: str | None = None,
        default_model: str | None = None,
        api_base_url: str | None = None,
        is_enabled: bool | None = None,
        priority: int | None = None,
        timeout_seconds: int | None = None,
    ) -> ProviderConfig:
        """Update this organization's provider configuration, disabling included
        (PUT /llm/providers/{provider}).

        Only the SUPPLIED arguments are merged onto the existing row: an omitted
        one is not sent at all, so it is left alone rather than reset. (The
        server merges ``exclude_unset``, so this method omits fields instead of
        sending nulls -- which also means a field cannot be CLEARED through this
        method, only changed.) The MERGED ``deployment_preset`` config is
        re-validated server-side, so a partial update that would leave an
        inconsistent preset -- clearing ``gcp_project`` while
        ``deployment_preset`` stays ``vertex_gemini`` -- is rejected rather than
        silently accepted.

        DISABLING A PROVIDER IS THIS METHOD, not a delete::

            await client.llm_providers.update_provider("anthropic", is_enabled=False)

        Deleting is not a supported operation at all. The router's delete route
        answers 405 by design and points the caller here, and this module
        deliberately ships no wrapper for it -- a client method whose every call
        raises is worse than an absent one.

        Args:
            provider: Provider name to update (validated server-side).
            display_name: New label.
            deployment_preset: New deployment shape; re-validated against the
                MERGED row.
            gcp_project: Vertex project id.
            gcp_region: Vertex region.
            service_account_secret_ref: NAME of an environment variable (never
                the credential).
            azure_resource: Azure OpenAI resource name.
            azure_deployment: Azure deployment name.
            aws_region: Bedrock region.
            bedrock_auth_kind: Bedrock credential kind.
            default_model: Model bound to this provider when a caller names
                none.
            api_base_url: Override of the provider's API base.
            is_enabled: Set ``False`` to DISABLE the provider.
            priority: Selection order among configured providers.
            timeout_seconds: Per-call timeout for this provider.

        Returns:
            ProviderConfig for the updated row.

        Raises:
            ValidationError: 400 -- invalid provider name, or an inconsistent
                merged ``deployment_preset``.
            NotFoundError: 404 -- the provider is not configured for the
                caller's organization.
            AuthorizationError: 403 -- the caller is outside the router's
                persona gate (admin / architect).
        """
        fields: dict[str, Any] = {}
        for key, value in (
            ("display_name", display_name),
            ("deployment_preset", deployment_preset),
            ("gcp_project", gcp_project),
            ("gcp_region", gcp_region),
            ("service_account_secret_ref", service_account_secret_ref),
            ("azure_resource", azure_resource),
            ("azure_deployment", azure_deployment),
            ("aws_region", aws_region),
            ("bedrock_auth_kind", bedrock_auth_kind),
            ("default_model", default_model),
            ("api_base_url", api_base_url),
            ("is_enabled", is_enabled),
            ("priority", priority),
            ("timeout_seconds", timeout_seconds),
        ):
            if value is not None:
                fields[key] = value

        response = await self._http.request(
            "PUT",
            f"/api/v1/llm/providers/{encode_path_param(provider)}",
            json_data=fields,
        )
        return ProviderConfig(**response)

    async def list_models(self, provider: str) -> ModelsListResult:
        """List available models for a provider (GET /llm/models). Models are cached for 1 hour server-side.

        Args:
            provider: Provider name (openai, anthropic, google, ollama).
        """
        response = await self._http.request(
            "GET",
            "/api/v1/llm/models",
            params={"provider": provider},
        )
        return ModelsListResult(**response)

    async def get_all_models(self, include_unavailable: bool = False) -> AllModelsResult:
        """Get all models from all configured providers, grouped by
        provider (GET /llm/models/all)."""
        response = await self._http.request(
            "GET",
            "/api/v1/llm/models/all",
            params={"include_unavailable": include_unavailable},
        )
        return AllModelsResult(**response)

    async def validate_model(self, provider: str, model_id: str) -> ModelValidationResult:
        """Validate that a specific model is available
        (POST /llm/models/validate)."""
        response = await self._http.request(
            "POST",
            "/api/v1/llm/models/validate",
            json_data={"provider": provider, "model_id": model_id},
        )
        return ModelValidationResult(**response)

    async def refresh_provider_cache(self, provider: str) -> CacheRefreshResult:
        """Force-refresh the model cache for a provider
        (POST /llm/providers/{provider}/refresh).
        Rate limited server-side to 5 requests/hour/user."""
        response = await self._http.request(
            "POST",
            f"/api/v1/llm/providers/{encode_path_param(provider)}/refresh",
        )
        return CacheRefreshResult(**response)

    async def check_provider_health(self, provider: str) -> ProviderHealth:
        """Check the health of a specific provider (GET /llm/providers/{provider}/health)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/llm/providers/{encode_path_param(provider)}/health",
        )
        return ProviderHealth(**response)

    async def get_model_metadata(self, provider: str, model_id: str) -> ModelMetadata:
        """Get detailed metadata for a specific model
        (GET /llm/models/{provider}/{model_id}/metadata)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/llm/models/{encode_path_param(provider)}/{encode_path_param(model_id)}/metadata",
        )
        return ModelMetadata(**response)

    async def get_rate_card(self) -> RateCard:
        """The EFFECTIVE LLM rate card, with per-provider verification age
        (GET /llm/pricing).

        This is NOT the per-adapter catalogue behind ``list_models``, and the two
        DISAGREE. The metering path -- and therefore the budget cap actually
        enforced against a partner's spend -- consults THIS table. The Azure
        adapter reports ``cost_per_1k_*: 0.0`` for every deployment ("Azure
        pricing varies by agreement"), so a partner sizing a workload from
        ``list_models()`` alone can be wrong by the entire rate while the
        platform is metering against the number here.

        ``last_verified`` / ``is_stale`` / ``is_expired`` per provider are the
        reason to read it: a rate card nobody re-checks drifts out of agreement
        with the vendor silently, and the cap is enforced against whatever it
        drifted to. ``is_stale`` is advisory; ``is_expired`` is the state that
        fails the platform's own merge gate.

        Read-only, process-wide configuration: no tenant dimension, no record
        lookup and no credentials of any kind.

        Returns:
            RateCard, with one RateCardProvider per priced provider and
            ``azure_deployment_model_map`` for the opaque Azure deployment names
            -- a deployment absent from that map is UNPRICED and wedges the
            session that uses it, so read it rather than assuming the rates
            cover every name.
        """
        response = await self._http.request(
            "GET",
            "/api/v1/llm/pricing",
        )
        return RateCard(**response)
