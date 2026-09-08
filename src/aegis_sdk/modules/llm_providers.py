"""
LLM Providers Module for Agentic OS SDK.

Thin HTTP-wrapper for LLM provider listing, model discovery, validation,
and health checks -- the Live LLM Provider Integrations admin surface.

Self-contained module: request/response models are
defined LOCALLY in this file. Do not import from ``aegis_sdk.types`` or
edit ``modules/__init__.py`` / ``client.py`` -- a separate orchestrator
wiring pass registers this module on the client.

Backend router (verified against the real source, cited per-method below):
  (FastAPI prefix ``/llm``), mounted
under the app-wide ``settings.api_prefix`` (``/api/v1`` -- verified), so every path
below is ``/api/v1/llm/...``.

All 7 routes on the router (llm_providers.py):
  - list_providers()        GET  /api/v1/llm/providers
  - list_models()           GET  /api/v1/llm/models
  - get_all_models()        GET  /api/v1/llm/models/all
  - validate_model()        POST /api/v1/llm/models/validate
  - refresh_provider_cache() POST /api/v1/llm/providers/{provider}/refresh
  - check_provider_health() GET  /api/v1/llm/providers/{provider}/health
  - get_model_metadata()    GET  /api/v1/llm/models/{provider}/{model_id}/metadata

Security note: API keys are NEVER exposed in any
of these responses (backend-only); ``refresh_provider_cache`` is rate
limited server-side to 5 requests/hour/user.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .._http import encode_path_param

# ---------------------------------------------------------------------------
# Response models (verified -- no Pydantic alias
# generator on any model, so JSON keys are the same snake_case as the
# field names below).
# ---------------------------------------------------------------------------


class Provider(BaseModel):
    """LLM provider status (response shape)."""

    name: str
    display_name: str = ""
    status: str = "offline"  # available, degraded, offline
    is_configured: bool = False
    is_enabled: bool = True
    last_health_check: str | None = None
    rate_limit_rpm: int = 0
    rate_limit_tpm: int = 0


class ProvidersListResult(BaseModel):
    """Envelope for GET /llm/providers."""

    providers: list[Provider] = Field(default_factory=list)


class ModelCapabilities(BaseModel):
    """Model capabilities."""

    vision: bool = False
    function_calling: bool = False
    streaming: bool = True
    json_mode: bool = False
    code_interpreter: bool = False


class LlmModel(BaseModel):
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


class ModelsListResult(BaseModel):
    """Envelope for GET /llm/models."""

    provider: str = ""
    models: list[LlmModel] = Field(default_factory=list)
    cached_at: str | None = None
    from_cache: bool = False
    fallback: bool = False


class AllModelsResult(BaseModel):
    """Envelope for GET /llm/models/all."""

    models: dict[str, list[LlmModel]] = Field(default_factory=dict)


class ModelValidationResult(BaseModel):
    """Result of POST /llm/models/validate."""

    is_valid: bool
    message: str = ""
    is_deprecated: bool = False
    replacement_model: str | None = None
    model: LlmModel | None = None


class CacheRefreshResult(BaseModel):
    """Result of POST /llm/providers/{provider}/refresh."""

    success: bool = False
    models_found: int = 0
    cached_at: str | None = None
    fallback: bool = False


class ProviderHealth(BaseModel):
    """Result of GET /llm/providers/{provider}/health."""

    provider: str
    is_healthy: bool = False
    status: str = "offline"  # available, degraded, offline
    message: str = ""
    latency_ms: int = 0
    rate_limit_rpm: int = 0
    rate_limit_remaining: int | None = None
    checked_at: str = ""


class ModelMetadata(BaseModel):
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
