"""
Agentic OS SDK Type Definitions.

Provides Pydantic models for all SDK entities, enums, and response types.
These models provide type safety and automatic validation.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# =============================================================================
# Enums
# =============================================================================


class AgentType(str, Enum):
    """Agent behavioral type (READ-MODEL enum — accepts every server-persisted value).

    This enum MUST accept every ``agent_type`` value the server can PERSIST,
    because :class:`Agent` (returned by ``agents.list()`` / ``agents.get()``)
    deserializes into it. The server persists MORE values than the public
    create-validator accepts, because several agent classes are created
    INTERNALLY via the ``CreateAgent`` node, bypassing ``POST /agents``:

    Creatable via ``POST /agents`` (server pattern
    ``^(chat|task|pipeline|custom)$``):
        ``chat``, ``task``, ``pipeline``, ``custom``

    Server-persisted by internal generators (NOT creatable via the public API,
    but returned by ``agents.list()`` for every real org):
        ``shadow`` -- ShadowAgentGenerator
        ``pseudo`` -- PseudoAgentService
        ``tool``   -- ToolAgentService
        ``esa``    -- ESAService

    ``unknown`` is a forward-compat sentinel: :class:`Agent` coerces any
    ``agent_type`` string a FUTURE server release adds into ``unknown`` rather
    than raising ``pydantic.ValidationError`` on ``agents.list()``.

    Creation stays restricted to the creatable subset (:data:`CREATABLE_AGENT_TYPES`)
    by :class:`AgentCreate` -- widening this READ enum does NOT loosen the
    client-side create guard, and does NOT touch the server's strict
    create-validator (shadow/pseudo/tool/esa are minted server-side only).

    NOTE: This is a DIFFERENT domain from :class:`UnitType` (atomic/composite,
    the EATP work-unit classification carried in ``unit_type``). A prior SDK
    release conflated the two here, sending an ``agent_type="atomic"`` that the
    server rejects.
    """

    # Creatable via the public POST /agents API (server ^(chat|task|pipeline|custom)$)
    CHAT = "chat"
    TASK = "task"
    PIPELINE = "pipeline"
    CUSTOM = "custom"
    # Server-persisted by internal generators — READ-MODEL only, not creatable
    SHADOW = "shadow"
    PSEUDO = "pseudo"
    TOOL = "tool"
    ESA = "esa"
    # Forward-compat sentinel for agent_type values a future server release adds
    UNKNOWN = "unknown"


#: The subset of :class:`AgentType` that ``POST /agents`` accepts. Creation is
#: restricted to these; ``shadow``/``pseudo``/``tool``/``esa`` are minted
#: server-side only and ``unknown`` is a read-model sentinel.
CREATABLE_AGENT_TYPES: frozenset[AgentType] = frozenset(
    {AgentType.CHAT, AgentType.TASK, AgentType.PIPELINE, AgentType.CUSTOM}
)


class AgentStatus(str, Enum):
    """Agent lifecycle status.

    The backend model declares six
    status values; this enum previously carried only three, so any account
    with a suspended/deprecated/revoked agent made ``client.agents.list()``
    raise a Pydantic ``ValidationError`` -- a latent crash that fires exactly
    when something has gone wrong and a developer most needs to look.
    ``agent_service.py`` legitimately transitions an agent ``active ->
    suspended``, so this is a reachable state, not a theoretical one.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class UnitType(str, Enum):
    """Agent unit type (atomic vs composite)."""

    ATOMIC = "atomic"
    COMPOSITE = "composite"


class AgentSubtype(str, Enum):
    """Agent behavioral subtype.

    Mirrors the server ``CreateAgentRequest.agent_subtype`` pattern
    ``^(specialist|manager|esa|pseudo|governance)$``.
    """

    SPECIALIST = "specialist"
    MANAGER = "manager"
    ESA = "esa"
    PSEUDO = "pseudo"
    GOVERNANCE = "governance"


class PipelinePattern(str, Enum):
    """Pipeline execution pattern."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    ITERATIVE = "iterative"
    FALLBACK = "fallback"
    ROUTING = "routing"
    ENSEMBLE = "ensemble"
    SAGA = "saga"
    EVENT_DRIVEN = "event_driven"


class ExecutionStatus(str, Enum):
    """Execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ObjectiveStatus(str, Enum):
    """Objective lifecycle status."""

    DRAFT = "draft"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RequestStatus(str, Enum):
    """Request lifecycle status."""

    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    """Work session status."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class TrustPosture(str, Enum):
    """Agent trust posture level (CARE-aligned canonical vocabulary).

    Values mirror the backend's canonical lowercase posture names. The prior
    ``minimal/basic/standard/elevated/full`` values were a wire-shape bug:
    they matched no backend posture value, so any posture round-trip through
    the SDK mismatched..
    """

    PSEUDO = "pseudo"
    SUPERVISED = "supervised"
    SHARED_PLANNING = "shared_planning"
    CONTINUOUS_INSIGHT = "continuous_insight"
    DELEGATED = "delegated"


class TrustChainStatus(str, Enum):
    """Trust chain status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class DelegationStatus(str, Enum):
    """Delegation status."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


# =============================================================================
# Base Models
# =============================================================================


class BaseEntityModel(BaseModel):
    """Base model for all entity types with common fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        extra="ignore",
    )


class TimestampMixin(BaseModel):
    """Mixin for models with timestamps."""

    created_at: datetime
    updated_at: datetime


# =============================================================================
# Pagination
# =============================================================================


class PaginatedResponse[T](BaseModel):
    """
    Paginated response wrapper.

    Attributes:
        items: List of items in current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Number of items per page
        has_next: Whether there are more pages
    """

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50
    has_next: bool = False


# =============================================================================
# Agent Models
# =============================================================================


def _normalize_capabilities(parsed: list[Any]) -> list[str]:
    """Normalise a dual-format ``capabilities_json`` list to ``list[str]``.

    Accepts a bare string element as-is and reduces an object element to its
    ``name``. Anything else -- or an object whose ``name`` is missing, empty,
    or not a string -- is DROPPED with a WARN naming the offending element,
    so one malformed capability degrades that single entry instead of failing
    the whole response.

    Returns a list of names; order is preserved so a caller indexing into it
    still lines up with the surviving server elements.
    """
    names: list[str] = []
    for element in parsed:
        if isinstance(element, str):
            names.append(element)
            continue
        if isinstance(element, dict):
            name = element.get("name")
            if isinstance(name, str) and name:
                names.append(name)
                continue
        logger.warning(
            "Dropping unparseable capability element %r: expected a string or "
            "an object carrying a non-empty string 'name'.",
            element,
        )
    return names


class Agent(BaseEntityModel, TimestampMixin):
    """
    Agent entity model.

    Represents an AI agent in the Agentic OS platform.
    """

    id: str
    name: str
    agent_type: AgentType
    unit_type: UnitType
    agent_subtype: AgentSubtype | None = None
    status: AgentStatus
    model_id: str | None = None
    system_prompt: str | None = None
    organization_id: str
    workspace_id: str
    capabilities: list[str] = Field(default_factory=list)
    capabilities_json: str | None = None
    a2a_enabled: bool = False
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_unknown_agent_type(cls, data: Any) -> Any:
        """Coerce an unrecognized server-emitted ``agent_type`` to
        ``AgentType.UNKNOWN`` so ``agents.list()`` never raises
        ``pydantic.ValidationError`` on an ``agent_type`` this SDK release
        predates.

        The four internal generators (shadow/pseudo/tool/esa) are named
        members of :class:`AgentType`, so they deserialize to their true
        value; this guard only fires for a value a FUTURE server release
        introduces before the SDK enum catches up -- a read model must be
        forgiving of forward drift, never fail the whole list on one row.
        """
        if isinstance(data, dict):
            raw = data.get("agent_type")
            if isinstance(raw, str) and raw not in AgentType._value2member_map_:
                data = {**data, "agent_type": AgentType.UNKNOWN.value}
        return data

    @model_validator(mode="before")
    @classmethod
    def _parse_capabilities_json(cls, data: Any) -> Any:
        """Derive ``capabilities`` (list[str]) from the server's raw
        ``capabilities_json`` string when the response doesn't already
        provide a ``capabilities`` list.

        The server's ``AgentResponse``
        only ever emits ``capabilities_json`` (a JSON-encoded string) --
        never a bare ``capabilities`` list. Without this, ``Agent.capabilities``
        silently stayed ``[]`` for every agent returned by the server (the
        dead-feature class).

        ``capabilities_json`` is a DUAL-FORMAT column: an element is EITHER a
        bare string (the capability name) OR an object
        ``{name, description, keywords}``. Both shapes are live on the server
        today and both reach this parser:

        * the STRING form is what ``pseudo_agent_service`` persists at agent
          creation, what ``api/task_agents.py``'s validator documents, and
          what this SDK itself writes via :class:`AgentCreate`;
        * the OBJECT form is what ``models/agent.py`` documents, and
          ``services/objective_router.py`` and ``services/shadow_agent_factory.py``
          each implement BOTH shapes.

        So an element is normalised to its ``name`` rather than rejected. The
        alternative -- pinning one canonical shape -- would fail every agent
        written in the other form, which is a breaking change to a live
        documented contract rather than a tightening; the server-side reader
        took the same dual-format decision for the same reason.

        A malformed element is DROPPED with a WARN, never raised: the same
        forgiving-read-model principle :meth:`_coerce_unknown_agent_type`
        records above -- one unparseable capability must not fail the whole
        ``agents.list()`` page.
        """
        if isinstance(data, dict) and "capabilities" not in data:
            raw = data.get("capabilities_json")
            if raw:
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    parsed = None
                if isinstance(parsed, list):
                    data = {**data, "capabilities": _normalize_capabilities(parsed)}
        return data


class AgentCreate(BaseModel):
    """Agent creation payload.

    Field-for-field mirror of the server ``CreateAgentRequest``. Every field the server accepts is
    declared here so ``model_dump(exclude_none=True)`` cannot silently drop a
    value the caller supplied.

    ``capabilities`` is an SDK ergonomics field: a ``list[str]`` that
    :meth:`to_request_body` serialises into the server-accepted
    ``capabilities_json`` string. Advanced callers may set ``capabilities_json``
    directly (it takes precedence over ``capabilities``).
    """

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("agent_type", mode="before")
    @classmethod
    def _restrict_to_creatable(cls, value: Any) -> Any:
        """Creation is restricted to the server-creatable subset
        (``chat``/``task``/``pipeline``/``custom``). The internal types
        (``shadow``/``pseudo``/``tool``/``esa``) are minted server-side only;
        the server's create-validator would ``422`` them, so fail fast
        client-side rather than round-trip a doomed request.

        ``AgentType`` was widened to accept those internal values on the READ
        model (:class:`Agent`); this guard keeps the WRITE model narrow so
        widening the read enum does not silently loosen creation.
        """
        raw = value.value if isinstance(value, AgentType) else value
        creatable = {t.value for t in CREATABLE_AGENT_TYPES}
        if raw not in creatable:
            allowed = ", ".join(sorted(creatable))
            raise ValueError(
                f"agent_type {raw!r} is not creatable via the SDK; "
                f"allowed: {allowed}. Internal agent types (shadow, pseudo, "
                f"tool, esa) are created server-side only."
            )
        return value

    # --- Server-required fields ---
    # workspace_id + model_id are server-required (207
    # workspace_id: str; :210 model_id: str = Field(..., min_length=1)) but are
    # declared Optional HERE by design: AgentsModule.create() already guards
    # both client-side (core/agents.py) and the Optional model-level shape
    # preserves exclude_none wire-shape flexibility for partial-body building
    # (locked by an automated regression check). Do NOT make these
    # required without also removing the create() guard.
    name: str
    agent_type: AgentType = AgentType.CHAT
    workspace_id: str | None = None
    model_id: str | None = None

    # --- Optional identity / prompt config ---
    id: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    instructions: dict[str, Any] | None = None

    # --- EATP work-unit classification ---
    unit_type: UnitType = UnitType.ATOMIC
    agent_subtype: AgentSubtype = AgentSubtype.SPECIALIST

    # --- LLM provider (server pattern ^(openai|anthropic|google|azure|custom)$) ---
    provider: str | None = None

    # --- A2A capability discovery ---
    capabilities: list[str] = Field(default_factory=list)
    capabilities_json: str | None = None
    tools_json: str | None = None
    a2a_enabled: bool = False

    # --- Manager / orchestration configuration ---
    orchestration_config: str | None = None

    # --- Delegate / shadow agent (org-chart mapping) ---
    is_shadow_agent: bool = False
    shadow_for_user_id: str | None = None
    human_role_id: str | None = None
    organization_unit_id: str | None = None

    def to_request_body(self) -> dict[str, Any]:
        """Build the exact JSON body the server expects.

        Serialises the ergonomic ``capabilities`` list into
        ``capabilities_json`` (the field the server actually reads) unless an
        explicit ``capabilities_json`` was already supplied.
        """
        body = self.model_dump(exclude_none=True)
        caps = body.pop("capabilities", None)
        if caps and not body.get("capabilities_json"):
            body["capabilities_json"] = json.dumps(caps)
        return body


class AgentUpdate(BaseModel):
    """Agent update payload (all fields optional).

    Field-for-field mirror of the server ``UpdateAgentRequest``. See :class:`AgentCreate` for the
    ``capabilities`` / ``capabilities_json`` reconciliation.
    """

    model_config = ConfigDict(use_enum_values=True)

    name: str | None = None
    status: AgentStatus | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    instructions: dict[str, Any] | None = None

    # --- EATP work-unit classification ---
    unit_type: UnitType | None = None
    agent_subtype: AgentSubtype | None = None

    # --- LLM provider ---
    provider: str | None = None

    # --- A2A capability discovery ---
    capabilities: list[str] | None = None
    capabilities_json: str | None = None
    tools_json: str | None = None
    a2a_enabled: bool | None = None

    # --- Manager / orchestration configuration ---
    orchestration_config: str | None = None

    # --- Delegate / shadow agent (org-chart mapping) ---
    is_shadow_agent: bool | None = None
    shadow_for_user_id: str | None = None
    human_role_id: str | None = None
    organization_unit_id: str | None = None

    def to_request_body(self) -> dict[str, Any]:
        """Build the exact JSON body the server expects (excludes unset fields)."""
        body = self.model_dump(exclude_none=True)
        caps = body.pop("capabilities", None)
        if caps and not body.get("capabilities_json"):
            body["capabilities_json"] = json.dumps(caps)
        return body


class AgentExecution(BaseEntityModel):
    """Agent execution result."""

    id: str
    agent_id: str
    status: ExecutionStatus
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


# =============================================================================
# Skill Models
# =============================================================================


class Skill(BaseEntityModel, TimestampMixin):
    """
    Skill entity model.

    Represents a reusable capability that can be assigned to agents.
    """

    id: str
    name: str
    description: str | None = None
    skill_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    organization_id: str


class SkillCreate(BaseModel):
    """Skill creation payload."""

    name: str
    description: str | None = None
    skill_type: str
    config: dict[str, Any] = Field(default_factory=dict)


class SkillUpdate(BaseModel):
    """Skill update payload (all fields optional)."""

    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None


# =============================================================================
# Pipeline Models
# =============================================================================


class PipelineNode(BaseModel):
    """Pipeline node definition."""

    id: str
    name: str
    node_type: str
    agent_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] | None = None


class PipelineConnection(BaseModel):
    """Pipeline connection between nodes."""

    source_node_id: str
    target_node_id: str
    source_output: str = "default"
    target_input: str = "default"
    condition: str | None = None


class Pipeline(BaseEntityModel, TimestampMixin):
    """
    Pipeline entity model.

    Represents a workflow pipeline that orchestrates agent execution.
    """

    id: str
    name: str
    description: str | None = None
    pattern: PipelinePattern
    nodes: list[PipelineNode] = Field(default_factory=list)
    connections: list[PipelineConnection] = Field(default_factory=list)
    organization_id: str
    workspace_id: str


class PipelineCreate(BaseModel):
    """Pipeline creation payload."""

    name: str
    description: str | None = None
    pattern: PipelinePattern = PipelinePattern.SEQUENTIAL
    nodes: list[PipelineNode] = Field(default_factory=list)
    connections: list[PipelineConnection] = Field(default_factory=list)
    workspace_id: str | None = None


class PipelineUpdate(BaseModel):
    """Pipeline update payload (all fields optional)."""

    name: str | None = None
    description: str | None = None
    pattern: PipelinePattern | None = None
    nodes: list[PipelineNode] | None = None
    connections: list[PipelineConnection] | None = None


class PipelineExecution(BaseEntityModel):
    """Pipeline execution result."""

    id: str
    pipeline_id: str
    status: ExecutionStatus
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    error: str | None = None
    node_results: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


# =============================================================================
# Auth Models
# =============================================================================


class User(BaseModel):
    """User model.

    Mirrors the server ``UserResponse``.
    The user identity field is ``name`` -- NOT ``full_name`` (a
    prior SDK release declared a required ``full_name`` field the server
    never emits, so every ``User(**response)`` construction from
    ``get_current_user()`` / ``login()`` / ``register()`` raised a
    ``pydantic.ValidationError``).
    """

    id: str
    email: str = Field(repr=False)  # PII -- hidden from repr/str ( review H1)
    name: str
    organization_id: str
    organization_name: str
    role: str
    personas: list[str] = Field(default_factory=list)
    status: str | None = None
    mfa_enabled: bool | None = None
    last_login_at: str | None = None
    created_at: str | None = None
    email_verified: bool = False

    # Mirrors the server's ``UserResponse``, which gained these three fields so
    # that ``GET /auth/me`` could serve TWO principal kinds -- a human session
    # and an API key -- from one route, with ``auth_type`` as the authoritative
    # discriminator. The server change was additive and safe (pydantic ignores
    # unknown fields), which is exactly what let this model fall silently
    # behind: ``User(**response)`` kept succeeding while DROPPING the
    # discriminator, so an SDK caller holding an API key could not tell which
    # credential kind it was holding -- the one question the route exists to
    # answer, and the reason its handbook points integrators at it.
    #
    # ``auth_type`` defaults to "user" to match the server default, so every
    # existing emitter (``/auth/login``, ``/auth/register``, the JWT ``/auth/me``
    # path) keeps its current meaning with no call-site change. The other two
    # stay None/empty for a user session -- an API key is the only principal
    # that has them, and this response never describes another principal's key.
    auth_type: str = "user"
    api_key_id: str | None = None
    api_key_scopes: list[str] = Field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Deprecated alias for :attr:`name` (backward-compat shim).

        The server has never emitted a ``full_name`` field -- this alias
        exists only so callers upgrading from the older SDK do not need
        to touch every read site in the same release. It will be removed in
        a future release once the shim has lived through one minor cycle.
        """
        return self.name


class AuthToken(BaseModel):
    """Authentication token response, with the authenticated user attached.

    Mirrors the server's nested envelope
    (``LoginResponse`` / ``RegisterResponse``):
    ``{"user": UserResponse, "tokens": TokenResponse}``. The SDK flattens the
    ``tokens`` sub-object onto this model's top-level fields for backward
    compatibility (``token.access_token`` keeps working exactly as before) and additionally attaches the parsed ``user`` object so
    callers do not need a second round-trip to ``get_current_user()``.
    """

    access_token: str = Field(repr=False)  # bearer credential -- hidden from repr/str (H1)
    refresh_token: str | None = Field(default=None, repr=False)  # bearer credential -- hidden (H1)
    token_type: str = "bearer"
    expires_in: int = 3600
    expires_at: datetime | None = None
    user: User | None = None


class APIKey(BaseModel):
    """API key model.

    Mirrors the server's ``APIKeyResponse``.

    ``status`` IS THE FIELD THAT MAKES THIS MODEL SAFE TO ACT ON. Pydantic
    ignores response fields a model does not declare, so while ``status`` was
    absent a REVOKED key and a live one parsed into byte-identical objects --
    a caller auditing its own keys through this model could not tell a dead
    credential from a working one, and nothing about the result looked
    partial. The same silence dropped ``organization_id`` and ``rate_limit``.

    The four fields added for that reason are OPTIONAL, and deliberately so:
    the server has two API-key response shapes and only one carries every
    field (``CreateAPIKeyResponse`` omits ``last_used_at`` and ``created_by``).
    Requiring them would turn a successful create into a parse error.
    """

    id: str
    name: str
    key_prefix: str  # First 8 chars for identification
    scopes: list[str] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    # --- present on the server's responses; see the class docstring for why
    # these four are optional rather than required ---
    organization_id: str | None = None
    rate_limit: int | None = None
    status: str | None = None  # e.g. "active" / "revoked" -- see class docstring
    # The principal the key's liveness is BOUND to, not merely its creator:
    # validate() denies on owner_inactive / owner_not_member_of_key_org against
    # THIS id, and regenerate RE-ANCHORS it to the rotating caller, so
    # on a rotated key it names the last rotator. update() never rewrites it.
    created_by: str | None = None


class APIKeyCreated(APIKey):
    """An API key as returned by CREATION, carrying the one-time secret.

    ``key`` is the full credential and the server emits it EXACTLY ONCE, in
    the create response; it is not retrievable afterwards. Parsing that
    response into the plain :class:`APIKey` therefore discarded the only copy
    of the secret the caller was ever going to see -- the create call appeared
    to succeed and left the caller with nothing to store.

    A SUBCLASS, NOT A NEW FIELD ON ``APIKey``. Putting ``key`` on the shared
    model would make it ``None`` on every list/get result, which invites
    callers to log or forward a field that is a live credential whenever it is
    not None. Keeping it on the type that ALWAYS has it means the secret
    exists only where it is real, and ``isinstance(x, APIKey)`` still holds
    for callers written against the old return type.

    ``repr=False`` matches :class:`AuthToken`'s treatment of bearer
    credentials (H1): the value is returned to the caller and never rendered
    into a repr or a traceback.

    ⛔ It is NOT excluded from ``model_dump()`` or ``model_dump_json()``, which
    return the secret in full. A log line carrying the dumped model emits the
    credential in cleartext. Scrub it explicitly, or log ``key_prefix``.
    """

    key: str = Field(repr=False)  # full secret, shown once -- never log this


class APIKeyCreate(BaseModel):
    """API key creation payload."""

    name: str
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: int | None = None


# =============================================================================
# Execution Models - Objectives, Requests, Sessions
# =============================================================================


class Objective(BaseModel):
    """Objective model - top-level work unit."""

    id: str
    title: str
    description: str
    agent_id: str
    status: ObjectiveStatus
    priority: int = 0
    organization_id: str
    workspace_id: str
    created_by: str
    assigned_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ObjectiveCreate(BaseModel):
    """Objective creation payload."""

    title: str
    description: str
    agent_id: str
    priority: int = 0
    workspace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObjectiveUpdate(BaseModel):
    """Objective update payload."""

    title: str | None = None
    description: str | None = None
    priority: int | None = None
    assigned_to: str | None = None
    metadata: dict[str, Any] | None = None


class Request(BaseModel):
    """Request model - work item within an objective."""

    id: str
    objective_id: str
    title: str
    description: str
    request_type: str  # "approval", "action", "information", "decision"
    status: RequestStatus
    priority: int = 0
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class RequestClaim(BaseModel):
    """Request claim payload."""

    agent_id: str


class RequestComplete(BaseModel):
    """Request completion payload."""

    result: dict[str, Any]
    artifacts: list[str] = Field(default_factory=list)


class RequestEscalate(BaseModel):
    """Request escalation payload."""

    reason: str
    target_id: str | None = None  # Who to escalate to


class Finding(BaseModel):
    """Finding attached to a request."""

    id: str
    request_id: str
    finding_type: str  # "info", "warning", "error", "recommendation"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Session(BaseModel):
    """Work session model."""

    id: str
    request_id: str
    agent_id: str
    status: SessionStatus
    start_time: datetime
    end_time: datetime | None = None
    pause_time: datetime | None = None
    message_count: int = 0
    artifact_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionMessage(BaseModel):
    """Message within a session."""

    id: str
    session_id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SessionArtifact(BaseModel):
    """Artifact created during a session."""

    id: str
    session_id: str
    artifact_type: str  # "file", "code", "image", "json", etc.
    name: str
    data: dict[str, Any]
    created_at: datetime


class SessionContext(BaseModel):
    """Session context information."""

    session_id: str
    agent_context: dict[str, Any]
    memory_context: dict[str, Any]
    active_tools: list[str]


class Subagent(BaseModel):
    """Spawned subagent within a session."""

    id: str
    session_id: str
    subagent_id: str
    task: str
    status: str  # "running", "completed", "failed"
    created_at: datetime
    completed_at: datetime | None = None


# =============================================================================
# Trust Models - Chains, Delegations, Postures, Audit
# =============================================================================


class TrustGenesisRecord(BaseModel):
    """Genesis record within an established trust chain.

    Mirrors the server ``GenesisRecord`` response model. Note ``constraints`` is a
    ``list[str]`` server-side (constraint labels), NOT a dict.
    """

    agent_id: str
    authority_id: str | None = None
    established_at: str | None = None
    expires_at: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class TrustHumanOriginInfo(BaseModel):
    """Human who authorized an agent action (EATP origin tracking).

    Mirrors the server ``HumanOriginResponse``.
    All fields are optional — the server returns ``None`` for incomplete
    legacy records rather than omitting the object.
    """

    human_id: str | None = None
    display_name: str | None = None
    auth_provider: str | None = None
    session_id: str | None = None
    authenticated_at: str | None = None


class TrustDelegationRecord(BaseModel):
    """A single delegation entry within an established trust chain.

    Mirrors the server ``DelegationRecord``.
    """

    delegator_id: str
    delegatee_id: str
    capabilities: list[str]
    constraints: list[str] = Field(default_factory=list)
    created_at: str | None = None
    expires_at: str | None = None


class EstablishedTrustChain(BaseModel):
    """Trust chain returned by ``POST /trust/establish``.

    Mirrors the server ``TrustChain`` response model. Distinct from the legacy
    :class:`TrustChain` model below, which does not match this route's
    (or any other trust-chain route's) real response shape.
    """

    agent_id: str
    genesis: TrustGenesisRecord
    delegations: list[TrustDelegationRecord] = Field(default_factory=list)
    status: str = "active"
    human_origin: TrustHumanOriginInfo | None = None


class AffectedTrustAgent(BaseModel):
    """An agent affected by a cascade revocation preview.

    Mirrors the server ``AffectedAgent``.
    """

    agent_id: str
    agent_name: str | None = None
    delegation_depth: int
    active_tasks: int = 0
    status: str = "valid"


class CascadeRevocationResult(BaseModel):
    """Result of a cascade trust revocation.

    Mirrors the server ``CascadeRevocationResult``, returned by both
    ``POST /trust/revoke`` (:589) and ``POST /trust/revoke/{agent_id}/cascade``
    (:681) — both routes call the same ``revoke_cascade`` service method.
    """

    revoked_agent_ids: list[str]
    total_revoked: int
    reason: str
    initiated_by: str
    completed_at: str


class TrustChain(BaseModel):
    """Trust chain model.

    Previously required ``id``, ``human_origin_id``,
    ``human_origin_data``, ``capabilities``, ``constraints`` (a dict),
    ``delegation_depth``, and datetime-typed ``created_at``/``revoked_at`` --
    none of which the server emits on ANY trust-chain route. Every real
    response is ``{agent_id, genesis, delegations, status, human_origin}``
    (``GET /trust/chains``:; identical
    shape on ``GET /trust/chains/{agent_id}``), so ``chains.list()`` and
    ``chains.get()`` raised a Pydantic ``ValidationError`` on every call.
    Now mirrors the server model field-for-field, reusing the same
    ``TrustGenesisRecord``/``TrustDelegationRecord``/``TrustHumanOriginInfo``
    sub-models :class:`EstablishedTrustChain` already defined correctly for
    ``POST /trust/establish`` -- that route was the one path this shape was
    ever right for.
    """

    agent_id: str
    genesis: TrustGenesisRecord
    delegations: list[TrustDelegationRecord] = Field(default_factory=list)
    status: str = "active"
    human_origin: TrustHumanOriginInfo | None = None


class TrustChainEstablish(BaseModel):
    """Trust chain establishment payload."""

    agent_id: str
    human_origin_data: dict[str, Any]
    capabilities: list[str]
    constraints: dict[str, Any] = Field(default_factory=dict)


class TrustVerification(BaseModel):
    """Trust verification request."""

    agent_id: str
    action: str
    resource: str
    context: dict[str, Any] = Field(default_factory=dict)


class TrustVerificationResult(BaseModel):
    """Trust verification result."""

    allowed: bool
    chain_id: str | None = None
    reason: str | None = None
    constraints_applied: list[str] = Field(default_factory=list)


class DelegationPath(BaseModel):
    """Delegation path in a trust chain."""

    chain_id: str
    path: list[dict[str, Any]]  # List of delegation steps
    depth: int


class AgentTrustContext(BaseModel):
    """Trust context for an agent."""

    agent_id: str
    chain_id: str
    posture: TrustPosture
    capabilities: list[str]
    constraints: dict[str, Any]
    delegation_depth: int


class TrustDelegation(BaseModel):
    """Trust delegation model."""

    id: str
    chain_id: str
    delegator_id: str
    delegatee_id: str
    capabilities: list[str]
    constraints: dict[str, Any]
    status: DelegationStatus
    created_at: datetime
    revoked_at: datetime | None = None


class TrustDelegationCreate(BaseModel):
    """Trust delegation creation payload."""

    delegator_id: str
    delegatee_id: str
    capabilities: list[str]
    constraints: dict[str, Any] = Field(default_factory=dict)


class RevocationImpact(BaseModel):
    """Preview of cascade revocation impact.

    Mirrors the server ``RevocationImpactPreview`` returned by
    ``GET /trust/revoke/{agent_id}/impact`` (model at ``:229-237``). The previous field set (``chain_id``,
    ``affected_agents: list[str]``, ``affected_delegations``,
    ``cascading_revocations``) matched no real server response — this route
    keys by ``agent_id`` (trust chains don't have a separate ``chain_id`` in
    this API) and returns rich ``AffectedAgent`` records, not bare ID strings.
    """

    target_agent_id: str
    target_agent_name: str | None = None
    affected_agents: list[AffectedTrustAgent] = Field(default_factory=list)
    total_affected: int = 0
    has_active_workloads: bool = False
    warnings: list[str] = Field(default_factory=list)


class TrustPostureInfo(BaseModel):
    """Trust posture information."""

    agent_id: str
    posture: TrustPosture
    progression_eligible: bool
    last_assessment: datetime
    metrics: dict[str, Any] = Field(default_factory=dict)


class PostureProgressionRequest(BaseModel):
    """Posture progression request payload."""

    target_posture: TrustPosture
    justification: str


class PostureOverride(BaseModel):
    """Posture override payload."""

    new_posture: TrustPosture
    reason: str


class PostureMetrics(BaseModel):
    """Posture progression metrics."""

    agent_id: str
    current_posture: TrustPosture
    tasks_completed: int
    successful_verifications: int
    failed_verifications: int
    time_at_current: int  # Days
    progression_score: float


class TrustAuditEntry(BaseModel):
    """Trust audit log entry."""

    id: str
    timestamp: datetime
    agent_id: str
    human_origin_id: str
    action_type: str  # "establish", "delegate", "verify", "revoke", "override"
    action_data: dict[str, Any]
    result: str  # "success", "failure", "blocked"
    chain_id: str | None = None


class TrustAuditQuery(BaseModel):
    """Trust audit query parameters."""

    agent_id: str | None = None
    human_origin_id: str | None = None
    action_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


# =============================================================================
# Streaming Event Models
# =============================================================================


class StreamEvent(BaseModel):
    """Server-Sent Event (SSE) wrapper."""

    event: str
    data: dict[str, Any]


class ExecutionEvent(BaseModel):
    """Agent execution streaming event."""

    event_type: str  # "started", "thinking", "output", "completed", "error"
    timestamp: datetime
    data: dict[str, Any]


# =============================================================================
# API Response Models
# =============================================================================


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None
    code: str | None = None


# =============================================================================
# Revenue Enums
# =============================================================================


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class BillingCycle(str, Enum):
    """Billing cycle options."""

    MONTHLY = "monthly"
    ANNUAL = "annual"


class PlanTier(str, Enum):
    """Subscription plan tier."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class LicenseEdition(str, Enum):
    """License edition for self-hosted deployments."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class ResourceType(str, Enum):
    """Resource types for usage tracking."""

    AGENT_EXECUTION = "agent_execution"
    TOKEN = "token"
    STORAGE = "storage"
    API_CALL = "api_call"
    AGENTS = "agents"
    TEAM_MEMBERS = "team_members"


class InvoiceStatus(str, Enum):
    """Invoice status from Stripe."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


# =============================================================================
# Revenue Models - Subscriptions & Plans
# =============================================================================


class Subscription(BaseModel):
    """Subscription model."""

    id: str
    organization_id: str
    plan_tier: PlanTier
    billing_cycle: BillingCycle
    status: SubscriptionStatus
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool = False
    trial_start: str | None = None
    trial_end: str | None = None
    stripe_customer_id: str
    stripe_subscription_id: str


class SubscribeRequest(BaseModel):
    """Subscription creation payload."""

    plan_id: str
    billing_cycle: BillingCycle
    payment_method_id: str | None = None


class UpgradeRequest(BaseModel):
    """Subscription upgrade payload."""

    new_plan_id: str
    prorate: bool = True


class CancelRequest(BaseModel):
    """Subscription cancellation payload."""

    at_period_end: bool = True


class Plan(BaseModel):
    """Subscription plan model."""

    id: str
    name: str
    tier: PlanTier
    description: str
    monthly_price: int  # in cents
    annual_price: int  # in cents
    features: list[str]
    contact_sales: bool = False


class PlanFeatures(BaseModel):
    """Plan features list."""

    features: list[str]


class TierComparison(BaseModel):
    """Plan tier comparison result."""

    tier1: PlanTier
    tier2: PlanTier
    tier1_features: list[str]
    tier2_features: list[str]
    additional_in_tier2: list[str]
    tier1_price_monthly: int
    tier2_price_monthly: int
    price_difference_monthly: int


class PortalSession(BaseModel):
    """Stripe customer portal session."""

    url: str


# =============================================================================
# Revenue Models - Licenses
# =============================================================================


class License(BaseModel):
    """License model for self-hosted deployments."""

    license_id: str
    customer_id: str
    customer_name: str
    customer_email: str
    edition: LicenseEdition
    max_agents: int  # -1 for unlimited
    max_users: int  # -1 for unlimited
    max_runs_per_month: int  # -1 for unlimited
    features: list[str]
    expires_at: str | None = None
    machine_binding: bool = False
    domain_restriction: list[str] | None = None
    phone_home_required: bool = True
    phone_home_interval_days: int = 7
    grace_period_days: int = 30
    revoked: bool = False
    created_at: str | None = None


class LicenseGenerate(BaseModel):
    """License generation payload."""

    customer_id: str
    customer_name: str
    customer_email: str
    edition: LicenseEdition
    max_agents: int = -1
    max_users: int = -1
    max_runs_per_month: int = -1
    features: list[str] | None = None
    validity_days: int = 365
    machine_binding: bool = False
    # REQUIRED by the server when machine_binding is true: a license that
    # declares binding but names no machine is unenforceable and the verifier
    # rejects it, so /api/v1/licenses/generate returns 400 without it.
    machine_id: str | None = None
    domain_restriction: list[str] | None = None
    phone_home_required: bool = True
    phone_home_interval_days: int = 7
    grace_period_days: int = 30


class LicenseValidation(BaseModel):
    """License validation response."""

    valid: bool
    message: str | None = None
    expires_at: str | None = None
    entitlements: dict[str, Any] | None = None
    next_check_days: int = 7


class LicenseValidationRequest(BaseModel):
    """License validation (phone-home) request."""

    license_id: str
    machine_id: str
    timestamp: str
    app_version: str
    usage: dict[str, Any] | None = None


class LicenseUsage(BaseModel):
    """License usage telemetry."""

    license_id: str
    validations: list[dict[str, Any]]
    total_validations: int


class LicenseStatus(BaseModel):
    """Current license status."""

    valid: bool
    license_id: str | None = None
    customer_name: str | None = None
    edition: LicenseEdition | None = None
    expires_at: str | None = None
    days_remaining: int | None = None
    grace_period_active: bool = False
    grace_period_days_remaining: int | None = None
    entitlements: dict[str, Any] | None = None
    error: str | None = None


class Edition(BaseModel):
    """License edition information."""

    name: str
    features: list[str]
    limits: dict[str, Any]


# =============================================================================
# Revenue Models - Usage & Quotas
# =============================================================================


class ResourceUsage(BaseModel):
    """Usage for a single resource type."""

    limit: int
    current: int
    unit: str
    remaining: int | None = None
    unlimited: bool = False


class Usage(BaseModel):
    """Current usage against quotas."""

    agent_execution: ResourceUsage
    token: ResourceUsage
    storage: ResourceUsage
    api_call: ResourceUsage


class UsageHistory(BaseModel):
    """Historical usage data."""

    date: str
    resource_type: ResourceType
    usage: int
    limit: int


class UsageBreakdown(BaseModel):
    """Usage breakdown by dimension."""

    resource_type: ResourceType
    by_agent: dict[str, int] | None = None
    by_user: dict[str, int] | None = None
    by_date: dict[str, int] | None = None


class Quota(BaseModel):
    """Quota for a resource type."""

    resource_type: ResourceType
    limit: int
    current: int
    remaining: int
    unlimited: bool = False


class QuotaUpdate(BaseModel):
    """Quota update payload."""

    resource_type: ResourceType
    new_limit: int


class QuotaCheck(BaseModel):
    """Quota limit check result."""

    resource_type: ResourceType
    allowed: bool
    current: int
    limit: int
    remaining: int
    amount_requested: int


# =============================================================================
# Revenue Models - Invoices
# =============================================================================


class InvoiceLineItem(BaseModel):
    """Invoice line item."""

    description: str
    amount: int
    quantity: int | None = None
    currency: str = "usd"


class Invoice(BaseModel):
    """Invoice model."""

    id: str
    number: str | None = None
    status: InvoiceStatus
    amount_due: int
    amount_paid: int
    currency: str
    created: int  # Unix timestamp
    due_date: int | None = None
    invoice_pdf: str | None = None
    hosted_invoice_url: str | None = None
    lines: list[InvoiceLineItem]


class InvoicesResponse(BaseModel):
    """Paginated invoices response."""

    invoices: list[Invoice]
    has_more: bool
