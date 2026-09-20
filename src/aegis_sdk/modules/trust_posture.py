"""
Trust Posture Module for Agentic OS SDK.

Provides posture-transition governance (approve/reject/history/evaluate/
upgrade-eligibility/evidence/pending-approvals), role-clearance and
role-envelope CRUD/lifecycle, CARE 5-dimension constraint-envelope
management, and EATP trust delegation/revocation/audit for the
trust-posture domain.

Self-contained module: local Pydantic models,
no shared imports from client.py / modules/__init__.py / types.py. Every
route below is verified against the deployed API:

    (prefix implicit /api/v1)
    (prefix /api/v1/role-clearances)
    (prefix /api/v1/role-envelopes)
    (prefix /api/v1/constraints)
    (Nexus bridge, prefix /api/v1/envelopes)
    (prefix /api/v1/trust)

Verified routes (38 methods, 7 P0 + 31 P1). The 14 P1 rows added
on top of the base are marked below:

    POST   .../trust-posture/approve       -> approve_posture_transition()
    POST   .../trust-posture/reject        -> reject_posture_transition()
    PUT    .../trust-posture               -> update_trust_posture()
    GET    .../trust-posture               -> get_trust_posture()
    GET    .../trust-posture/history       -> get_posture_history()
    GET    .../trust-posture/metrics       -> get_posture_metrics()
    GET    .../trust-posture/evaluate      -> evaluate_posture_progression()
    GET    .../trust-posture/pending       -> get_pending_approval()
    GET    .../trust-posture/upgrade-eligibility -> check_upgrade_eligibility()
    GET    .../trust-posture/evidence      -> get_posture_evidence()
    POST   .../trust-posture/request-upgrade -> request_upgrade()
    GET    /api/v1/posture/pending-approvals    -> get_pending_posture_approvals()

    POST   /api/v1/role-clearances                  -> create_role_clearance()
    GET    /api/v1/role-clearances                  -> list_role_clearances()
    GET    /api/v1/role-clearances/{role_id}        -> get_role_clearance()
    PUT    /api/v1/role-clearances/{role_id}        -> update_role_clearance()
    DELETE /api/v1/role-clearances/{role_id}        -> delete_role_clearance()
    POST   /api/v1/role-clearances/{role_id}/approve -> approve_role_clearance()
    POST   /api/v1/role-clearances/{role_id}/reject  -> reject_role_clearance()

    GET    /api/v1/role-envelopes                        -> list_role_envelopes()
    GET    /api/v1/role-envelopes/{envelope_id}          -> get_role_envelope()
    PUT    /api/v1/role-envelopes/{envelope_id}          -> update_role_envelope()
    DELETE /api/v1/role-envelopes/{envelope_id}          -> delete_role_envelope()
    POST   /api/v1/role-envelopes/{envelope_id}/activate -> activate_role_envelope()
    POST   /api/v1/role-envelopes/{envelope_id}/suspend  -> suspend_role_envelope()

    PUT    /api/v1/constraints/agents/{agent_id}           -> update_agent_constraints()
    GET    /api/v1/constraints/agents/{agent_id}           -> get_agent_constraints()
    POST   /api/v1/constraints/agents/{agent_id}/validate  -> validate_agent_constraints()
    GET    /api/v1/constraints/agents/{agent_id}/effective -> get_effective_constraints()
    GET    /api/v1/constraints/agents/{agent_id}/inherited -> get_inherited_constraints()
    GET    /api/v1/constraints/gradient-rules              -> get_gradient_rules()
    GET    /api/v1/constraints/organizations/{org_id}/defaults -> get_org_constraint_defaults()
    PUT    /api/v1/constraints/organizations/{org_id}/defaults -> update_org_constraint_defaults()

    GET    /api/v1/envelopes/defaults -> get_envelope_defaults()

    POST   /api/v1/trust/delegate                   -> delegate_trust()
    POST   /api/v1/trust/revoke-delegation          -> revoke_delegation()
    POST   /api/v1/trust/revoke/by-human/{human_id} -> revoke_trust_by_human()
    POST   /api/v1/trust/audit                      -> record_trust_audit()

("agent_id" prefix for the posture rows is /api/v1/agents/{agent_id})

Wire-shape notes -- behaviours a caller must plan for, because they are not
visible from the route table above:

    - ``PUT /api/v1/agents/{agent_id}/trust-posture`` returns a UNION: either
      a ``PostureTransitionResponse`` (the transition applied) or an
      ``ApprovalPendingResponse`` (it needs human approval first), both with
      status 200. ``update_trust_posture()`` discriminates on the
      ``approvalPending`` key and returns whichever shape the wire carries,
      so a caller must branch on the returned type rather than assume the
      transition took effect.
    - Role-clearance CREATE/UPDATE return the RAW persisted row, in which
      ``compartments_json`` is a JSON **string** -- not the joined
      ``ClearanceRecordResponse`` shape (``compartments`` as a list, plus
      ``role_name``/``role_address``) that LIST/GET return. So
      ``create_role_clearance()`` / ``update_role_clearance()`` return
      ``dict[str, Any]`` while ``list_role_clearances()`` returns the typed
      ``RoleClearanceRecord``. Do not feed a create response straight into
      code written against a list response.
    - Role-envelope routes carry no declared response model: every method
      returns the raw persisted row, with ``constraint_config_json`` as a
      JSON **string**. The single-envelope GET additionally carries
      ``is_degenerate`` / ``degenerate_warnings``; ``RoleEnvelope`` treats
      both as optional so one model covers both shapes without inventing
      fields on the paths that never emit them.
    - ``POST /api/v1/role-envelopes`` (create) is deliberately not wrapped by
      this module. Call it through the generic client if you need it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field, field_validator

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


# ---------------------------------------------------------------------------
# Client-side allowlists mirroring the server-side allowlists, so that
# obviously-invalid values fail fast before the
# network round-trip. The server independently re-validates every one of
# these (defense in depth) -- these are NOT a substitute for server-side
# checks, only an early client-side signal.
# ---------------------------------------------------------------------------

# Mirrors CLEARANCE_LEVELS, defined
# and models/role_clearance.py. Deliberately restated
# here rather than imported: aegis_sdk is a standalone client package and must
# not import server internals. Kept as a client-side fail-fast only — the
# server re-validates independently (see the note above).
ALLOWED_CLEARANCE_LEVELS: frozenset[str] = frozenset(
    {"public", "restricted", "confidential", "secret", "top_secret"}
)

# Mirrors VALID_POSTURE_VALUES.
ALLOWED_POSTURE_VALUES: frozenset[str] = frozenset(
    {"pseudo", "supervised", "shared_planning", "continuous_insight", "delegated"}
)


# ============================================================================
# Posture models (mirrors the server response shape -- camelCase wire shape)
# ============================================================================


class PostureTransition(TolerantModel):
    """A posture transition record (``PostureTransitionResponse``, camelCase wire)."""

    id: str
    agent_id: str = Field(alias="agentId")
    from_posture: str = Field(alias="fromPosture")
    to_posture: str = Field(alias="toPosture")
    reason: str
    trigger: str
    triggered_by: str | None = Field(default=None, alias="triggeredBy")
    triggered_by_name: str | None = Field(default=None, alias="triggeredByName")
    approved_by: str | None = Field(default=None, alias="approvedBy")
    approved_by_name: str | None = Field(default=None, alias="approvedByName")
    approved_at: str | None = Field(default=None, alias="approvedAt")
    transitioned_at: str = Field(alias="transitionedAt")
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class PostureTransitionsList(TolerantModel):
    """History list envelope (``PostureTransitionsListResponse``)."""

    transitions: list[PostureTransition] = Field(default_factory=list)
    total: int = 0


class PostureApproval(TolerantModel):
    """A pending posture approval request (``PostureApprovalResponse``)."""

    id: str
    agent_id: str = Field(alias="agentId")
    requested_posture: str = Field(alias="requestedPosture")
    current_posture: str = Field(alias="currentPosture")
    reason: str
    requested_by: str = Field(alias="requestedBy")
    requested_by_name: str = Field(alias="requestedByName")
    requested_at: str = Field(alias="requestedAt")
    status: str
    reviewed_by: str | None = Field(default=None, alias="reviewedBy")
    reviewed_by_name: str | None = Field(default=None, alias="reviewedByName")
    reviewed_at: str | None = Field(default=None, alias="reviewedAt")
    review_notes: str | None = Field(default=None, alias="reviewNotes")
    expires_at: str | None = Field(default=None, alias="expiresAt")
    config: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


def _literal_true(value: Any) -> bool:
    """``True`` only for a literal JSON ``true``.

    An older server omits ``alreadyPending``; absence — or any value that is
    not literally ``true`` — must never read as "this was a duplicate". Same
    rule as ``aegis_sdk.trust.postures`` applies to the same key.
    """
    return value is True


class PostureApprovalPending(TolerantModel):
    """The 202-shaped envelope PUT .../trust-posture returns when the
    transition requires approval (``ApprovalPendingResponse``).

    ``already_pending is True`` means this call collided with a request for the
    SAME transition that was already pending: :attr:`approval` is THAT request
    (its own reason, requester and ``requested_at``), and this call's reason
    and config were NOT recorded. Re-issuing does not change that.
    """

    approval_pending: bool = Field(default=True, alias="approvalPending")
    approval_id: str = Field(alias="approvalId")
    approval: PostureApproval
    already_pending: bool = Field(default=False, alias="alreadyPending")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("already_pending", mode="before")
    @classmethod
    def _already_pending_is_literal_true(cls, value: Any) -> bool:
        return _literal_true(value)


class MetricStatus(TolerantModel):
    """One metric's status within a progression evaluation."""

    metric: str
    current: float
    required: float
    met: bool


class ProgressionEvaluation(TolerantModel):
    """Progression-eligibility evaluation (``ProgressionEvaluationResponse``)."""

    can_progress: bool = Field(alias="canProgress")
    current_posture: str = Field(alias="currentPosture")
    next_posture: str | None = Field(default=None, alias="nextPosture")
    metrics_status: list[MetricStatus] = Field(default_factory=list, alias="metricsStatus")
    estimated_time_to_progression: str | None = Field(
        default=None, alias="estimatedTimeToProgression"
    )
    blockers: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class EvidenceMetrics(TolerantModel):
    """Persistent evidence metrics for posture-upgrade qualification
    (``EvidenceMetricsResponse``)."""

    agent_id: str = Field(alias="agentId")
    organization_id: str = Field(alias="organizationId")
    current_posture: str = Field(alias="currentPosture")
    posture_since: str | None = Field(default=None, alias="postureSince")
    operation_count: int = Field(default=0, alias="operationCount")
    success_count: int = Field(default=0, alias="successCount")
    failure_count: int = Field(default=0, alias="failureCount")
    incident_count: int = Field(default=0, alias="incidentCount")
    success_rate: float = Field(default=0.0, alias="successRate")
    shadow_evaluations: int = Field(default=0, alias="shadowEvaluations")
    shadow_pass_count: int = Field(default=0, alias="shadowPassCount")
    shadow_blocked_count: int = Field(default=0, alias="shadowBlockedCount")
    shadow_pass_rate: float | None = Field(default=None, alias="shadowPassRate")
    days_at_posture: int = Field(default=0, alias="daysAtPosture")
    first_operation_at: str | None = Field(default=None, alias="firstOperationAt")
    last_operation_at: str | None = Field(default=None, alias="lastOperationAt")

    model_config = ConfigDict(populate_by_name=True)


class UpgradeEligibility(TolerantModel):
    """Evidence-based upgrade eligibility evaluation (``UpgradeEligibilityResponse``)."""

    eligible: bool
    current_posture: str = Field(alias="currentPosture")
    next_posture: str | None = Field(default=None, alias="nextPosture")
    reason: str
    evidence: EvidenceMetrics | None = None
    requirements: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class PostureOverrideInfo(TolerantModel):
    """Active posture-override info nested in the config response
    (``PostureOverrideInfo``, camelCase wire)."""

    id: str
    original_posture: str = Field(alias="originalPosture")
    override_posture: str = Field(alias="overridePosture")
    reason: str
    override_type: str = Field(alias="overrideType")
    initiated_by: str = Field(alias="initiatedBy")
    initiated_by_name: str | None = Field(default=None, alias="initiatedByName")
    initiated_at: str = Field(alias="initiatedAt")
    expires_at: str | None = Field(default=None, alias="expiresAt")
    is_active: bool = Field(default=True, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class PostureConfig(TolerantModel):
    """Current effective posture configuration for an agent
    (``PostureConfigResponse``, camelCase wire)."""

    posture: str
    base_posture: str = Field(alias="basePosture")
    config: dict[str, Any] = Field(default_factory=dict)
    current_since: str = Field(alias="currentSince")
    configured_by: str = Field(alias="configuredBy")
    configured_by_name: str = Field(alias="configuredByName")
    configured_at: str = Field(alias="configuredAt")
    approved_by: str | None = Field(default=None, alias="approvedBy")
    approved_by_name: str | None = Field(default=None, alias="approvedByName")
    approved_at: str | None = Field(default=None, alias="approvedAt")
    review_due_at: str | None = Field(default=None, alias="reviewDueAt")
    override_active: bool = Field(default=False, alias="overrideActive")
    override_info: PostureOverrideInfo | None = Field(default=None, alias="overrideInfo")

    model_config = ConfigDict(populate_by_name=True)


class ProgressionMetrics(TolerantModel):
    """Progression metrics feeding posture-advancement evaluation
    (``ProgressionMetricsResponse``, camelCase wire)."""

    interaction_count: int = Field(default=0, alias="interactionCount")
    approval_rate: float = Field(default=0.0, alias="approvalRate")
    override_rate: float = Field(default=0.0, alias="overrideRate")
    error_rate: float = Field(default=0.0, alias="errorRate")
    plan_acceptance_rate: float | None = Field(default=None, alias="planAcceptanceRate")
    alert_accuracy: float | None = Field(default=None, alias="alertAccuracy")
    autonomous_success_rate: float | None = Field(default=None, alias="autonomousSuccessRate")
    last_evaluated_at: str = Field(alias="lastEvaluatedAt")

    model_config = ConfigDict(populate_by_name=True)


class UpgradeRequestResult(TolerantModel):
    """Outcome of an evidence-based upgrade request
    (``UpgradeRequestResponse``, camelCase wire)."""

    status: str
    current_posture: str = Field(alias="currentPosture")
    target_posture: str | None = Field(default=None, alias="targetPosture")
    reason: str
    approval_id: str | None = Field(default=None, alias="approvalId")
    #: ``True`` when an approval request for this transition was already
    #: pending and is returned instead of a new one (``status`` is still
    #: ``approval_pending``). :attr:`requested_at` is then the EARLIER request's
    #: submission time, not this call's.
    already_pending: bool = Field(default=False, alias="alreadyPending")
    requested_at: str | None = Field(default=None, alias="requestedAt")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("already_pending", mode="before")
    @classmethod
    def _already_pending_is_literal_true(cls, value: Any) -> bool:
        return _literal_true(value)


# ============================================================================
# Role-clearance models (mirrors the server response shape -- snake_case wire)
# ============================================================================


class RoleClearanceRecord(TolerantModel):
    """A joined role-clearance record as LIST/GET emit it
    (``ClearanceRecordResponse`` -- ``compartments`` is a deserialized list;
    ``role_name``/``role_address`` are joined from OrganizationRole)."""

    id: str
    organization_id: str
    role_id: str
    max_clearance: str
    compartments: list[str] = Field(default_factory=list)
    vetting_status: str
    justification: str | None = None
    version: int = 0
    vetted_by: str | None = None
    vetted_at: str | None = None
    review_at: str | None = None
    role_name: str | None = None
    role_address: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = ConfigDict(extra="ignore")


class RoleClearanceList(TolerantModel):
    """List envelope for the clearance admin table (``ClearanceListResponse``)."""

    records: list[RoleClearanceRecord] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Role-envelope models (mirrors the server response shape -- raw dict, no
# response_model; snake_case wire, JSON-string-valued config columns)
# ============================================================================


class RoleEnvelope(TolerantModel):
    """A RoleEnvelope record as the raw persisted row is emitted (no
    ``response_model`` on the backend route -- ``constraint_config_json`` /
    ``verification_defaults_json`` are JSON **strings**, not deserialized
    objects). ``is_degenerate``/``degenerate_warnings`` are only present on
    the single-envelope GET route (not wired this module) -- optional here
    so the shared model does not fabricate them on paths that never emit
    them."""

    id: str
    organization_id: str
    defining_role_id: str
    target_role_id: str
    constraint_config_json: str
    verification_defaults_json: str | None = None
    status: str
    clearance_ceiling: str | None = None
    review_at: str | None = None
    signature_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    is_degenerate: bool | None = None
    degenerate_warnings: list[dict[str, Any]] | None = None

    model_config = ConfigDict(extra="ignore")


class RoleEnvelopeList(TolerantModel):
    """List envelope for the supervisor-scoped envelope list (raw
    ``{"records": [...], "total": N}`` -- no ``response_model``, see
    ``list_role_envelopes``)."""

    records: list[RoleEnvelope] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Constraint-envelope models (mirrors the server response shape -- CARE
# 5-dimension standard names, snake_case wire, no aliasing)
# ============================================================================


class TimeRange(TolerantModel):
    """A 24-hour time range (``TimeRangeModel``)."""

    start: int
    end: int


class FinancialConstraints(TolerantModel):
    """CARE Financial dimension (``FinancialConstraintsModel``)."""

    max_cost_usd: float | None = None
    max_tokens: int | None = None
    max_api_calls: int | None = None
    max_tool_invocations: int | None = None


class TemporalConstraints(TolerantModel):
    """CARE Temporal dimension (``TemporalConstraintsModel``)."""

    valid_hours: list[TimeRange] | None = None
    valid_days: list[int] | None = None
    timezone: str = "UTC"


class DataAccessConstraints(TolerantModel):
    """CARE Data Access dimension (``DataAccessConstraintsModel``)."""

    max_records_accessed: int | None = None
    prohibited_data_fields: list[str] = Field(default_factory=list)
    data_masking_required: list[str] = Field(default_factory=list)


class OperationalConstraints(TolerantModel):
    """CARE Operational dimension (``OperationalConstraintsModel``)."""

    require_human_approval: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)


#: The explicit-unbounded DoA declaration, RESTATED rather than imported: this
#: module is self-contained by contract (see its header — local models, no
#: shared imports). The value mirrors the server's own unbounded-DoA token and
#: a test pins the two spellings together.
_UNBOUNDED_DOA_TOKEN = "unbounded"


class TransactionConstraints(TolerantModel):
    """Transaction constraints (``TransactionConstraintsModel``).

    ⛔ THE TWO FIELDS DO **NOT** CARRY THE SAME STATES. This model previously
    annotated both as ``float | Literal["unbounded"] | None`` and said in its own
    docstring that "the wire accepts all three" for both — an assertion of a
    state core forbids on one of them. Corrected against core, field by field:

    ``max_transaction_amount`` (the CEILING) carries THREE:

    - a finite amount — a real ceiling that blocks a larger transaction;
    - ``None`` — NOTHING DECLARED, which keeps failing closed. An absence must
      never be rendered as the declaration below, and the two are separate model
      values here, not two spellings of one;
    - ``"unbounded"`` — the EXPLICIT declaration that no amount bounds this
      tier. Without it a partner had to write a large finite number instead,
      i.e. a limit nobody chose.

    The declaration is the core's ``UNBOUNDED_DOA_TOKEN``, recognised
    server-side by ONE shared recogniser.
    That recogniser folds CASE and SURROUNDING WHITESPACE, and this model now
    folds identically — a bare ``Literal`` rejected ``"UNBOUNDED"``,
    ``"Unbounded"`` and ``"  unbounded  "`` with a ``ValidationError``, i.e. it
    refused spellings the server honours and the endpoint would have accepted.
    Folding repairs the ACCEPTANCE SET; it does not widen the TYPE, which still
    admits the declaration and nothing else.

    ``require_approval_above`` (the THRESHOLD) carries TWO — there is NO
    unbounded state. A ceiling is a BOUND, and "no bound" is a meaningful thing
    to declare about a bound; a threshold is a TRIGGER, so reading the token
    there would mean "approval is never required" — deleting a control rather
    than stating one. Core refuses it and fails closed to ``$0``, the most
    restrictive reading and what enforcement applies -- the server's own
    threshold parser returns a ``float``, which makes the marker unassignable
    to that field.

    So a token on the THRESHOLD raises here rather than being quietly rewritten
    into a number, and that direction is deliberate: core never emits one on the
    read path (it has already folded it to ``0.0``), and on the write path a
    caller who asks for "no approval required" and silently receives "approval
    required above $0" is the exact silent substitution this model must not make.
    A caller who wants no threshold declares ``None`` and owns that choice.
    """

    max_transaction_amount: float | Literal["unbounded"] | None = None
    require_approval_above: float | None = None

    @field_validator("max_transaction_amount", mode="before")
    @classmethod
    def _fold_doa_declaration(cls, value: Any) -> Any:
        """Fold the declaration's spellings exactly as core's recogniser does.

        ``str.strip().lower() == "unbounded"`` is the whole rule, and it is the
        SAME rule as ``is_explicit_unbounded_declaration``. Every DIFFERENT word
        is left untouched and still fails validation, so the state cannot be
        reached by approximation.
        """
        if isinstance(value, str) and value.strip().lower() == _UNBOUNDED_DOA_TOKEN:
            return _UNBOUNDED_DOA_TOKEN
        return value

    @field_validator("require_approval_above", mode="before")
    @classmethod
    def _refuse_unbounded_threshold(cls, value: Any) -> Any:
        """Refuse the declaration on the field that has no such state.

        Named explicitly rather than left to a union's parse error: the default
        message ("unable to parse string as a number") would read as a bad
        number, when what is actually wrong is that this field has no unbounded
        state at all.
        """
        if isinstance(value, str) and value.strip().lower() == _UNBOUNDED_DOA_TOKEN:
            raise ValueError(
                "require_approval_above has no unbounded state: an unbounded "
                "approval trigger would delete the control rather than bound it, "
                "so the server fails it closed to $0. Declare a finite threshold, "
                "or None for no declared threshold."
            )
        return value


class CommunicationConstraints(TolerantModel):
    """CARE Communication dimension -- the 5th dimension (``CommunicationConstraintsModel``)."""

    internal_only: bool = True
    allowed_channels: list[str] = Field(default_factory=list)
    external_requires_approval: bool = True


class ConstraintEnvelope(TolerantModel):
    """Complete constraint envelope (``ConstraintEnvelopeResponse``)."""

    id: str
    organization_id: str
    agent_id: str | None = None
    parent_envelope_id: str | None = None
    financial: FinancialConstraints
    temporal: TemporalConstraints
    data_access: DataAccessConstraints
    operational: OperationalConstraints
    transaction: TransactionConstraints
    communication: CommunicationConstraints
    name: str
    description: str
    created_by: str
    created_at: str
    updated_at: str


class EffectiveConstraints(TolerantModel):
    """Effective constraints merged from the inheritance chain
    (``EffectiveConstraintsResponse``)."""

    agent_id: str
    financial: FinancialConstraints
    temporal: TemporalConstraints
    data_access: DataAccessConstraints
    operational: OperationalConstraints
    transaction: TransactionConstraints
    communication: CommunicationConstraints
    inheritance_chain: list[str] = Field(default_factory=list)


class GradientRuleItem(TolerantModel):
    """One four-zone verification-gradient rule (``GradientRuleItemResponse``)."""

    id: str
    name: str
    dimension: str
    condition: str
    result_level: Literal["auto_approved", "flagged", "held", "blocked"]
    match_count: int
    match_rate_percent: float
    enabled: bool


class GradientRulesList(TolerantModel):
    """Read-only list of gradient rules (``GradientRulesListResponse``)."""

    records: list[GradientRuleItem] = Field(default_factory=list)


class ConstraintValidationError(TolerantModel):
    """One monotonic-tightening validation error (``ValidationErrorResponse``, snake_case wire)."""

    category: str
    field: str
    message: str
    parent_value: str
    child_value: str


class ConstraintValidationWarning(TolerantModel):
    """One validation warning (``ValidationWarningResponse``, snake_case wire)."""

    category: str
    field: str
    message: str


class ConstraintValidationResult(TolerantModel):
    """Real-time constraint validation result used by the envelope editor to
    preview whether a child envelope tightens the parent before saving
    (``ValidationResultResponse``)."""

    valid: bool
    errors: list[ConstraintValidationError] = Field(default_factory=list)
    warnings: list[ConstraintValidationWarning] = Field(default_factory=list)


class EnvelopeDefaults(TolerantModel):
    """Default 5-dimension CARE envelope for a posture level (``EnvelopeDefaultsResponse``)."""

    posture: str
    dimensions: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Trust delegation / revocation / audit models (mirrors the server response shape )
# ============================================================================


class DelegationRecord(TolerantModel):
    """A trust delegation record (``DelegationRecord``)."""

    delegator_id: str
    delegatee_id: str
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    created_at: str | None = None
    expires_at: str | None = None


class CascadeRevocationResult(TolerantModel):
    """Result of a cascade / by-human trust revocation (``CascadeRevocationResult``)."""

    revoked_agent_ids: list[str] = Field(default_factory=list)
    total_revoked: int
    reason: str
    initiated_by: str
    completed_at: str


class TrustPostureModule:
    """
    Trust Posture module.

    Governs agent trust-posture transitions (pseudo -> supervised -> ... ->
    delegated), role clearances and operating envelopes (PACT hierarchy),
    CARE 5-dimension constraint envelopes, and EATP trust delegation /
    revocation / audit.

    Example:
        >>> pending = await client.trust_posture.get_pending_posture_approvals()
        >>> transition = await client.trust_posture.approve_posture_transition("agent_123")
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    # ------------------------------------------------------------------
    # Posture transitions (P0: approve, reject, update; P1: history,
    # evaluate, upgrade-eligibility, evidence, pending-approvals)
    # ------------------------------------------------------------------

    async def approve_posture_transition(
        self, agent_id: str, notes: str | None = None, approval_id: str | None = None
    ) -> PostureTransition:
        """
        Approve a pending posture-transition request.

        ledger ``ewl-20260913-4137c62903``: parity with
        ``aegis_sdk.trust.postures.PosturesModule.approve_transition`` — this
        can name WHICH pending request it decides.

        Args:
            agent_id: Agent ID with a pending transition
            notes: Optional approval notes
            approval_id: Which pending request to approve (the ``id`` of a
                :class:`PostureApproval`). Optional while the agent has exactly
                one pending request; REQUIRED in effect once it has more than
                one — the server refuses rather than picking one.

        Returns:
            PostureTransition: The completed transition record

        Raises:
            NotFoundError: If no pending approval matches (none pending, or
                ``approval_id`` does not name a pending request for this agent)
            ValidationError: If ``approval_id`` was omitted while more than one
                request is pending, or the request passed its ``expires_at``
                before a decision (it is not approvable; file a new request)
        """
        data: dict[str, Any] = {}
        if notes is not None:
            data["notes"] = notes
        # Omitted entirely (never sent as null) when not given, so the
        # single-pending wire body is unchanged.
        if approval_id is not None:
            data["approvalId"] = approval_id
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/approve",
            json_data=data,
        )
        return PostureTransition(**response)

    async def reject_posture_transition(
        self, agent_id: str, notes: str, approval_id: str | None = None
    ) -> PostureApproval:
        """
        Reject a pending posture-transition request.

        ledger ``ewl-20260913-4137c62903``: parity with
        ``aegis_sdk.trust.postures.PosturesModule.reject_transition``. Without
        ``approval_id``, two pending requests made every rejection a
        ``ValidationError`` no caller could resolve.

        Args:
            agent_id: Agent ID with a pending transition
            notes: Rejection reason (min length 10 -- server-enforced)
            approval_id: Which pending request to reject. Optional while the
                agent has exactly one pending request; REQUIRED in effect once
                it has more than one.

        Returns:
            PostureApproval: The now-rejected approval record

        Raises:
            NotFoundError: If no pending approval matches (none pending, or
                ``approval_id`` does not name a pending request for this agent)
            ValidationError: If notes is too short, ``approval_id`` was omitted
                while more than one request is pending, or the request passed
                its ``expires_at`` before a decision
        """
        json_body: dict[str, Any] = {"notes": notes}
        if approval_id is not None:
            json_body["approvalId"] = approval_id
        response = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/reject",
            json_data=json_body,
        )
        return PostureApproval(**response)

    async def update_trust_posture(
        self,
        agent_id: str,
        posture: str,
        reason: str,
        config: dict[str, Any] | None = None,
    ) -> PostureTransition | PostureApprovalPending:
        """
        Change an agent's trust posture (pseudo -> supervised -> ... -> delegated).

        The backend returns a UNION response: a completed transition when no
        approval is required, or an approval-pending envelope when the
        target posture requires sign-off. This method discriminates on the
        ``approvalPending`` key so callers get the correctly-typed shape.

        Args:
            agent_id: Agent ID
            posture: Target posture
            reason: Justification (min length 10 -- server-enforced)
            config: Optional posture-specific config

        Returns:
            PostureTransition when the transition completed immediately,
            PostureApprovalPending when it requires approval

        Raises:
            ValidationError: If the update request is invalid
        """
        data: dict[str, Any] = {"posture": posture, "reason": reason, "config": config or {}}
        response = await self._http.request(
            "PUT", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture", json_data=data
        )
        if response.get("approvalPending"):
            return PostureApprovalPending(**response)
        return PostureTransition(**response)

    async def get_posture_history(
        self, agent_id: str, limit: int = 20, offset: int = 0
    ) -> PostureTransitionsList:
        """
        Get posture-transition history for an agent.

        Args:
            agent_id: Agent ID
            limit: Maximum results (1-100)
            offset: Pagination offset

        Returns:
            PostureTransitionsList: transitions + total
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/history",
            params={"limit": limit, "offset": offset},
        )
        return PostureTransitionsList(**response)

    async def evaluate_posture_progression(self, agent_id: str) -> ProgressionEvaluation:
        """
        Evaluate whether an agent is eligible for posture progression.

        Args:
            agent_id: Agent ID

        Returns:
            ProgressionEvaluation: canProgress + metrics status
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/evaluate"
        )
        return ProgressionEvaluation(**response)

    async def check_upgrade_eligibility(self, agent_id: str) -> UpgradeEligibility:
        """
        Check evidence-based upgrade eligibility (CARE requirements gate).

        Args:
            agent_id: Agent ID

        Returns:
            UpgradeEligibility: eligible + evidence + requirements
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/upgrade-eligibility"
        )
        return UpgradeEligibility(**response)

    async def get_posture_evidence(self, agent_id: str) -> EvidenceMetrics:
        """
        Get persistent evidence metrics tracked for posture-upgrade qualification.

        Args:
            agent_id: Agent ID

        Returns:
            EvidenceMetrics: operation/success/incident counters + shadow-eval rates
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/evidence"
        )
        return EvidenceMetrics(**response)

    async def get_pending_posture_approvals(self) -> list[PostureApproval]:
        """
        List the current user's pending posture approvals (reviewer inbox).

        Returns:
            list[PostureApproval]: pending approval requests
        """
        response = await self._http.request("GET", "/api/v1/posture/pending-approvals")
        return [PostureApproval(**item) for item in response]

    async def get_trust_posture(self, agent_id: str) -> PostureConfig:
        """
        Read an agent's current effective trust-posture configuration.

        Surfaces the effective posture, base posture, config, review-due date
        and any active override (drift/incident/maintenance/policy) for the
        agent's trust-posture detail panel.

        Args:
            agent_id: Agent ID

        Returns:
            PostureConfig: effective + base posture, config, override info
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture"
        )
        return PostureConfig(**response)

    async def get_posture_metrics(self, agent_id: str, refresh: bool = False) -> ProgressionMetrics:
        """
        Get the progression metrics that feed posture-advancement evaluation.

        Args:
            agent_id: Agent ID
            refresh: Force recalculation server-side rather than serving cached metrics

        Returns:
            ProgressionMetrics: interaction/approval/override/error rates + timestamps
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/metrics",
            params={"refresh": refresh},
        )
        return ProgressionMetrics(**response)

    async def get_pending_approval(self, agent_id: str) -> PostureApproval | None:
        """
        Get the single pending posture-transition approval for one agent.

        Distinct from :meth:`get_pending_posture_approvals` (the current user's
        whole reviewer inbox): this returns the ONE pending request for a
        specific agent, or ``None`` when the agent has no pending transition.

        Args:
            agent_id: Agent ID

        Returns:
            PostureApproval when a pending request exists, else None
        """
        response = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/pending"
        )
        if not response:
            return None
        return PostureApproval(**response)

    async def request_upgrade(self, agent_id: str) -> UpgradeRequestResult:
        """
        Request an evidence-based posture upgrade for an agent.

        If the accumulated evidence qualifies, the server creates an approval
        request for the reporting manager; otherwise it returns an
        ``ineligible`` status with the blocking reason.

        Args:
            agent_id: Agent ID

        Returns:
            UpgradeRequestResult: status (eligible/ineligible/approval_pending) + reason
        """
        response = await self._http.request(
            "POST", f"/api/v1/agents/{encode_path_param(agent_id)}/trust-posture/request-upgrade"
        )
        return UpgradeRequestResult(**response)

    # ------------------------------------------------------------------
    # Role clearances (P0: create; P1: list, get, update, delete, approve, reject)
    # ------------------------------------------------------------------

    async def create_role_clearance(
        self,
        role_id: str,
        max_clearance: str,
        compartments: list[str] | None = None,
        justification: str | None = None,
        review_at: str | None = None,
    ) -> dict[str, Any]:
        """
        Assign a security clearance level + compartments to a role.

        New clearances always land in ``vetting_status="pending"`` --
        approve/reject are separate governance endpoints not exposed here.

        Args:
            role_id: Role to assign clearance to
            max_clearance: One of public/restricted/confidential/secret/top_secret
            compartments: Optional compartment names (SECRET/TOP_SECRET only)
            justification: Required by the server for CONFIDENTIAL and above
            review_at: Optional next-review ISO-8601 timestamp (must carry tz info)

        Returns:
            dict: The raw persisted clearance row (``compartments_json`` is a
                JSON string here, NOT a deserialized list -- see module docstring)

        Raises:
            ValueError: If max_clearance is not in the allowed set
        """
        if max_clearance not in ALLOWED_CLEARANCE_LEVELS:
            raise ValueError(
                f"max_clearance must be one of {sorted(ALLOWED_CLEARANCE_LEVELS)}; "
                f"got {max_clearance!r}"
            )
        data: dict[str, Any] = {
            "role_id": role_id,
            "max_clearance": max_clearance,
            "compartments": compartments or [],
        }
        if justification is not None:
            data["justification"] = justification
        if review_at is not None:
            data["review_at"] = review_at

        response = await self._http.request("POST", "/api/v1/role-clearances", json_data=data)
        return response

    async def list_role_clearances(self, limit: int = 50, offset: int = 0) -> RoleClearanceList:
        """
        List clearances for the caller's organization (admin clearance table).

        Args:
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            RoleClearanceList: records (with deserialized compartments + role join) + total
        """
        response = await self._http.request(
            "GET", "/api/v1/role-clearances", params={"limit": limit, "offset": offset}
        )
        return RoleClearanceList(**response)

    async def update_role_clearance(
        self,
        role_id: str,
        compartments: list[str] | None = None,
        review_at: str | None = None,
    ) -> dict[str, Any]:
        """
        Update compartments and/or review_at for a role's active clearance.

        Changing ``max_clearance`` is NOT exposed via this route (forces a
        new clearance record + re-vetting per the service contract).

        Args:
            role_id: Role whose clearance to update
            compartments: Replacement compartment list (omit to leave unchanged)
            review_at: Replacement next-review ISO-8601 timestamp

        Returns:
            dict: The raw persisted clearance row (see module docstring)
        """
        data: dict[str, Any] = {}
        if compartments is not None:
            data["compartments"] = compartments
        if review_at is not None:
            data["review_at"] = review_at

        response = await self._http.request(
            "PUT", f"/api/v1/role-clearances/{encode_path_param(role_id)}", json_data=data
        )
        return response

    async def delete_role_clearance(self, role_id: str) -> None:
        """
        Revoke a role's active clearance (terminal -- ``vetting_status='revoked'``).

        Args:
            role_id: Role whose clearance to revoke
        """
        await self._http.request("DELETE", f"/api/v1/role-clearances/{encode_path_param(role_id)}")

    async def get_role_clearance(self, role_id: str) -> RoleClearanceRecord:
        """
        Get a role's active clearance (joined ``ClearanceRecordResponse`` shape).

        Returns the same enriched shape as :meth:`list_role_clearances`
        (``compartments`` as a list plus ``role_name``/``role_address``),
        NOT the raw persisted row that CREATE/UPDATE return.

        Args:
            role_id: Role whose active clearance to read

        Returns:
            RoleClearanceRecord: the joined clearance record

        Raises:
            NotFoundError: If the role has no active clearance (or belongs to
                another tenant -- cross-tenant reads surface as 404)
        """
        response = await self._http.request(
            "GET", f"/api/v1/role-clearances/{encode_path_param(role_id)}"
        )
        return RoleClearanceRecord(**response)

    async def approve_role_clearance(self, role_id: str) -> dict[str, Any]:
        """
        Approve a role's PENDING clearance (pending -> active).

        The server enforces the approval chain: self-approval is blocked,
        justification is required for CONFIDENTIAL and above, and
        SECRET/TOP_SECRET need dual/triple approval (a partial approval
        returns the still-pending record). Distinct from reject.

        Args:
            role_id: Role whose pending clearance to approve

        Returns:
            dict: The raw persisted clearance row (``vetting_status`` reflects
                whether the approval completed or is still pending more approvers)

        Raises:
            NotFoundError: If the role has no pending clearance
            ValidationError: On self-approval / duplicate approver / missing justification
        """
        response = await self._http.request(
            "POST", f"/api/v1/role-clearances/{encode_path_param(role_id)}/approve"
        )
        return response

    async def reject_role_clearance(
        self, role_id: str, reason: str | None = None
    ) -> dict[str, Any]:
        """
        Reject a role's PENDING clearance (pending -> rejected).

        Distinct from :meth:`delete_role_clearance` (revoke of an ACTIVE
        clearance): reject declines a request that never became active and
        emits the ``role_clearance.reject`` audit action.

        Args:
            role_id: Role whose pending clearance to reject
            reason: Optional operator context recorded in the audit row
                (not persisted as a clearance column)

        Returns:
            dict: The raw persisted clearance row (now ``vetting_status='rejected'``)

        Raises:
            NotFoundError: If the role has no pending clearance
        """
        data: dict[str, Any] = {}
        if reason is not None:
            data["reason"] = reason
        response = await self._http.request(
            "POST", f"/api/v1/role-clearances/{encode_path_param(role_id)}/reject", json_data=data
        )
        return response

    # ------------------------------------------------------------------
    # Role envelopes (P0: activate; P1: list, get, edit, delete, suspend)
    # ------------------------------------------------------------------

    async def list_role_envelopes(
        self,
        defining_role_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> RoleEnvelopeList:
        """
        List RoleEnvelopes for a supervisor role, optionally filtered by status.

        ``defining_role_id`` is REQUIRED -- the backend exposes no org-wide
        enumeration path (list-by-supervisor is the only supported scope).

        Args:
            defining_role_id: Supervisor role ID (sent as the ``definingRoleId``
                query parameter -- the server's ``Query(alias=...)`` binds the
                wire parameter name, independent of body-field aliasing)
            status: Optional status filter (draft/active/suspended/revoked)
            limit: Maximum results (1-500)
            offset: Pagination offset

        Returns:
            RoleEnvelopeList: records (raw persisted rows) + total
        """
        params: dict[str, Any] = {
            "definingRoleId": defining_role_id,
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/role-envelopes", params=params)
        return RoleEnvelopeList(**response)

    async def update_role_envelope(
        self,
        envelope_id: str,
        constraint_config: dict[str, Any] | None = None,
        verification_defaults: dict[str, Any] | None = None,
        clearance_ceiling: str | None = None,
        review_at: str | None = None,
    ) -> RoleEnvelope:
        """
        Edit a RoleEnvelope's constraint_config / clearance_ceiling / review date.

        Status transitions MUST use activate/suspend/delete -- this route
        does NOT change status (prevents FSM bypass).

        Args:
            envelope_id: Envelope to update
            constraint_config: Replacement 5-dimension CARE constraint config
            verification_defaults: Replacement per-dimension gradient config
            clearance_ceiling: Replacement clearance ceiling (must be one of
                ALLOWED_CLEARANCE_LEVELS -- server-validated)
            review_at: Replacement next-review timestamp

        Returns:
            RoleEnvelope: The raw updated envelope row

        Raises:
            ValueError: If clearance_ceiling is not in the allowed set
        """
        if clearance_ceiling is not None and clearance_ceiling not in ALLOWED_CLEARANCE_LEVELS:
            raise ValueError(
                f"clearance_ceiling must be one of {sorted(ALLOWED_CLEARANCE_LEVELS)}; "
                f"got {clearance_ceiling!r}"
            )
        data: dict[str, Any] = {}
        if constraint_config is not None:
            data["constraint_config"] = constraint_config
        if verification_defaults is not None:
            data["verification_defaults"] = verification_defaults
        if clearance_ceiling is not None:
            data["clearance_ceiling"] = clearance_ceiling
        if review_at is not None:
            data["review_at"] = review_at

        response = await self._http.request(
            "PUT", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}", json_data=data
        )
        return RoleEnvelope(**response)

    async def delete_role_envelope(self, envelope_id: str) -> None:
        """
        Revoke a RoleEnvelope (terminal -- cannot be reactivated).

        Args:
            envelope_id: Envelope to revoke
        """
        await self._http.request(
            "DELETE", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}"
        )

    async def activate_role_envelope(self, envelope_id: str) -> RoleEnvelope:
        """
        Activate a draft operating envelope (draft -> active).

        Makes the constraints in the envelope enforced. The server validates
        monotonic tightening against the supervisor's envelope before
        activating.

        Args:
            envelope_id: Envelope to activate

        Returns:
            RoleEnvelope: The raw activated envelope row

        Raises:
            ValidationError: If tightening validation fails
        """
        response = await self._http.request(
            "POST", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}/activate"
        )
        return RoleEnvelope(**response)

    async def suspend_role_envelope(self, envelope_id: str) -> RoleEnvelope:
        """
        Suspend an active operating envelope (active -> suspended, re-activatable).

        Args:
            envelope_id: Envelope to suspend

        Returns:
            RoleEnvelope: The raw suspended envelope row
        """
        response = await self._http.request(
            "POST", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}/suspend"
        )
        return RoleEnvelope(**response)

    async def get_role_envelope(self, envelope_id: str) -> RoleEnvelope:
        """
        Get a single RoleEnvelope by ID, augmented with degenerate-envelope analysis.

        Unlike the list route, the single-envelope GET adds ``is_degenerate``
        (bool) and ``degenerate_warnings`` (governance warning dicts) derived
        from the envelope's constraint_config, so the UI can surface actionable
        alerts without a second call.

        Args:
            envelope_id: Envelope to read

        Returns:
            RoleEnvelope: The raw persisted row plus ``is_degenerate`` /
                ``degenerate_warnings``

        Raises:
            NotFoundError: If the envelope does not exist (or belongs to
                another tenant -- cross-tenant reads surface as 404)
        """
        response = await self._http.request(
            "GET", f"/api/v1/role-envelopes/{encode_path_param(envelope_id)}"
        )
        return RoleEnvelope(**response)

    # ------------------------------------------------------------------
    # Constraint envelopes (P0: update; P1: get, validate, effective,
    # inherited, gradient-rules, org-defaults get/update)
    # ------------------------------------------------------------------

    async def update_agent_constraints(
        self,
        agent_id: str,
        financial: dict[str, Any] | None = None,
        temporal: dict[str, Any] | None = None,
        data_access: dict[str, Any] | None = None,
        operational: dict[str, Any] | None = None,
        transaction: dict[str, Any] | None = None,
        communication: dict[str, Any] | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> ConstraintEnvelope:
        """
        Edit an agent's 5-dimension CARE constraint envelope.

        EATP: constraints are SUBTRACTIVE -- the server validates that the
        new envelope does not exceed the parent (inherited) constraints and
        returns 400 (raised by the HTTP client as ValidationError) if it does.

        Args:
            agent_id: Agent whose envelope to update
            financial: Financial dimension overrides (max_cost_usd, max_tokens, ...)
            temporal: Temporal dimension overrides (valid_hours, valid_days, timezone)
            data_access: Data Access dimension overrides
            operational: Operational dimension overrides
            transaction: Transaction dimension overrides
            communication: Communication dimension overrides (5th CARE dimension)
            name: Envelope display name
            description: Envelope description

        Returns:
            ConstraintEnvelope: The updated envelope (CARE standard dimension names)

        Raises:
            ValidationError: If the child envelope exceeds the parent constraints
        """
        data: dict[str, Any] = {}
        if financial is not None:
            data["financial"] = financial
        if temporal is not None:
            data["temporal"] = temporal
        if data_access is not None:
            data["data_access"] = data_access
        if operational is not None:
            data["operational"] = operational
        if transaction is not None:
            data["transaction"] = transaction
        if communication is not None:
            data["communication"] = communication
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        response = await self._http.request(
            "PUT", f"/api/v1/constraints/agents/{encode_path_param(agent_id)}", json_data=data
        )
        return ConstraintEnvelope(**response)

    async def get_effective_constraints(self, agent_id: str) -> EffectiveConstraints:
        """
        Read the effective (merged, most-restrictive) constraints across the
        inheritance chain for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            EffectiveConstraints: merged CARE dimensions + inheritance_chain
        """
        response = await self._http.request(
            "GET", f"/api/v1/constraints/agents/{encode_path_param(agent_id)}/effective"
        )
        return EffectiveConstraints(**response)

    async def get_gradient_rules(self) -> GradientRulesList:
        """
        Render the 4-zone verification gradient rules (auto/flagged/held/blocked).

        These are product defaults computed from posture mapping at runtime
        (no per-tenant persistence yet); match telemetry is reported as zero.

        Returns:
            GradientRulesList: records (one per gradient rule)
        """
        response = await self._http.request("GET", "/api/v1/constraints/gradient-rules")
        return GradientRulesList(**response)

    async def get_agent_constraints(self, agent_id: str) -> ConstraintEnvelope:
        """
        Read an agent's persisted 5-dimension CARE constraint envelope.

        Returns the agent's current envelope, or a default (empty) envelope
        when none is configured.

        Args:
            agent_id: Agent whose envelope to read

        Returns:
            ConstraintEnvelope: The agent's constraint envelope (CARE dimension names)
        """
        response = await self._http.request(
            "GET", f"/api/v1/constraints/agents/{encode_path_param(agent_id)}"
        )
        return ConstraintEnvelope(**response)

    async def get_inherited_constraints(self, agent_id: str) -> ConstraintEnvelope:
        """
        Read the constraints an agent inherits from its parent envelope (read-only).

        EATP: inherited constraints are the ceiling a child envelope cannot
        exceed (subtractive-constraint invariant). Sourced from the canonical
        ConstraintEnvelope store, NOT the trust-chain capability blob.

        Args:
            agent_id: Agent whose inherited (parent) envelope to read

        Returns:
            ConstraintEnvelope: The parent envelope (CARE dimension names)
        """
        response = await self._http.request(
            "GET", f"/api/v1/constraints/agents/{encode_path_param(agent_id)}/inherited"
        )
        return ConstraintEnvelope(**response)

    async def validate_agent_constraints(
        self,
        agent_id: str,
        financial: dict[str, Any] | None = None,
        temporal: dict[str, Any] | None = None,
        data_access: dict[str, Any] | None = None,
        operational: dict[str, Any] | None = None,
        transaction: dict[str, Any] | None = None,
        communication: dict[str, Any] | None = None,
    ) -> ConstraintValidationResult:
        """
        Validate a candidate constraint envelope against the parent WITHOUT saving.

        Powers real-time editor validation: the server checks that the
        candidate child envelope tightens (does not exceed) the agent's
        effective parent constraints and returns per-dimension errors/warnings.

        Args:
            agent_id: Agent whose parent constraints to validate against
            financial: Financial dimension candidate (max_cost_usd, max_tokens, ...)
            temporal: Temporal dimension candidate (valid_hours, valid_days, timezone)
            data_access: Data Access dimension candidate
            operational: Operational dimension candidate
            transaction: Transaction dimension candidate
            communication: Communication dimension candidate (5th CARE dimension)

        Returns:
            ConstraintValidationResult: valid + errors + warnings (no persistence)
        """
        data: dict[str, Any] = {}
        if financial is not None:
            data["financial"] = financial
        if temporal is not None:
            data["temporal"] = temporal
        if data_access is not None:
            data["data_access"] = data_access
        if operational is not None:
            data["operational"] = operational
        if transaction is not None:
            data["transaction"] = transaction
        if communication is not None:
            data["communication"] = communication

        response = await self._http.request(
            "POST",
            f"/api/v1/constraints/agents/{encode_path_param(agent_id)}/validate",
            json_data=data,
        )
        return ConstraintValidationResult(**response)

    async def get_org_constraint_defaults(self, org_id: str) -> ConstraintEnvelope:
        """
        Read an organization's default constraint envelope.

        These defaults apply to every agent in the organization unless a more
        specific per-agent envelope overrides them. Returns an empty
        ``Organization Defaults`` envelope when none is configured.

        Args:
            org_id: Organization ID (must match the caller's tenant)

        Returns:
            ConstraintEnvelope: The org-level default envelope (CARE dimension names)
        """
        response = await self._http.request(
            "GET", f"/api/v1/constraints/organizations/{encode_path_param(org_id)}/defaults"
        )
        return ConstraintEnvelope(**response)

    async def update_org_constraint_defaults(
        self,
        org_id: str,
        financial: dict[str, Any] | None = None,
        temporal: dict[str, Any] | None = None,
        data_access: dict[str, Any] | None = None,
        operational: dict[str, Any] | None = None,
        transaction: dict[str, Any] | None = None,
        communication: dict[str, Any] | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> ConstraintEnvelope:
        """
        Set the organization-wide default 5-dimension CARE constraint envelope.

        Requires ``organizations:update`` permission server-side. Creates the
        org-default envelope if absent, otherwise updates it in place.

        Args:
            org_id: Organization ID (must match the caller's tenant)
            financial: Financial dimension overrides (max_cost_usd, max_tokens, ...)
            temporal: Temporal dimension overrides
            data_access: Data Access dimension overrides
            operational: Operational dimension overrides
            transaction: Transaction dimension overrides
            communication: Communication dimension overrides (5th CARE dimension)
            name: Envelope display name
            description: Envelope description

        Returns:
            ConstraintEnvelope: The updated org-default envelope
        """
        data: dict[str, Any] = {}
        if financial is not None:
            data["financial"] = financial
        if temporal is not None:
            data["temporal"] = temporal
        if data_access is not None:
            data["data_access"] = data_access
        if operational is not None:
            data["operational"] = operational
        if transaction is not None:
            data["transaction"] = transaction
        if communication is not None:
            data["communication"] = communication
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        response = await self._http.request(
            "PUT",
            f"/api/v1/constraints/organizations/{encode_path_param(org_id)}/defaults",
            json_data=data,
        )
        return ConstraintEnvelope(**response)

    # ------------------------------------------------------------------
    # Envelope defaults (P1)
    # ------------------------------------------------------------------

    async def get_envelope_defaults(self, posture: str) -> EnvelopeDefaults:
        """
        Pre-populate the envelope editor with the SDK default 5-dimension
        CARE envelope for a given posture level.

        Args:
            posture: One of pseudo/supervised/shared_planning/continuous_insight/delegated

        Returns:
            EnvelopeDefaults: posture + dimensions

        Raises:
            ValueError: If posture is not in the allowed set
        """
        if posture not in ALLOWED_POSTURE_VALUES:
            raise ValueError(
                f"posture must be one of {sorted(ALLOWED_POSTURE_VALUES)}; got {posture!r}"
            )
        response = await self._http.request(
            "GET", "/api/v1/envelopes/defaults", params={"posture": posture}
        )
        return EnvelopeDefaults(**response)

    # ------------------------------------------------------------------
    # Trust delegation / revocation / audit (P0: delegate; P1: revoke-by-human, audit)
    # ------------------------------------------------------------------

    async def delegate_trust(
        self,
        delegator_id: str,
        delegatee_id: str,
        capabilities: list[str],
        constraints: list[str] | None = None,
        expires_in_days: int = 30,
    ) -> DelegationRecord:
        """
        Delegate trust from one agent to another (core EATP delegation flow).

        EATP: constraints can only TIGHTEN through delegation -- the server
        enforces this and raises a validation error otherwise.

        Args:
            delegator_id: Agent delegating trust
            delegatee_id: Agent receiving delegated trust
            capabilities: Capabilities being delegated
            constraints: Optional constraint identifiers on the delegation
            expires_in_days: Delegation lifetime in days (default 30)

        Returns:
            DelegationRecord: The created delegation

        Raises:
            ValidationError: If the delegation request is invalid
        """
        data: dict[str, Any] = {
            "delegator_id": delegator_id,
            "delegatee_id": delegatee_id,
            "capabilities": capabilities,
            "constraints": constraints or [],
            "expires_in_days": expires_in_days,
        }
        response = await self._http.request("POST", "/api/v1/trust/delegate", json_data=data)
        return DelegationRecord(**response)

    async def revoke_trust_by_human(self, human_id: str, reason: str) -> CascadeRevocationResult:
        """
        Revoke all delegations originating from a departing human (offboarding).

        EATP: when a human's access is revoked, every agent they delegated to
        (recursively) is also revoked.

        Args:
            human_id: The human whose delegations to revoke
            reason: Revocation reason (required)

        Returns:
            CascadeRevocationResult: revoked_agent_ids + total_revoked
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/trust/revoke/by-human/{encode_path_param(human_id)}",
            json_data={"reason": reason},
        )
        return CascadeRevocationResult(**response)

    async def record_trust_audit(
        self,
        agent_id: str,
        action: str,
        resource: str | None = None,
        result: str = "success",
        context: dict[str, Any] | None = None,
        parent_anchor_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Record an agent-action audit anchor (AdminAuditRecorder writes
        DENY/success/failure/partial entries into the EATP audit chain).

        When ``result`` is "denied", the server also records an immutable
        DENY entry in the tamper-proof compliance audit chain.

        Args:
            agent_id: Agent the action is attributed to
            action: Action name being audited
            resource: Resource or resource-type string
            result: One of success/failure/denied/partial
            context: Additional key/value context for the event
            parent_anchor_id: Optional link to a parent audit entry

        Returns:
            dict: The raw persisted audit anchor row
        """
        data: dict[str, Any] = {
            "agent_id": agent_id,
            "action": action,
            "result": result,
        }
        if resource is not None:
            data["resource"] = resource
        if context is not None:
            data["context"] = context
        if parent_anchor_id is not None:
            data["parent_anchor_id"] = parent_anchor_id

        response = await self._http.request("POST", "/api/v1/trust/audit", json_data=data)
        return response

    async def revoke_delegation(
        self, delegatee_id: str, delegator_id: str, reason: str
    ) -> dict[str, Any]:
        """
        Revoke a single trust delegation between two agents.

        Requires ``trust:revoke`` permission (org_admin / org_owner). Under the
        hood the server revokes trust on the delegatee, cascading to any
        further delegations rooted at it.

        Args:
            delegatee_id: Agent that received the delegated trust
            delegator_id: Agent that granted the delegation
            reason: Revocation reason (required)

        Returns:
            dict: ``{"message": ..., "reason": ..., **cascade_result}`` -- the
                cascade result carries ``revoked_agent_ids`` / ``total_revoked``
                / ``initiated_by`` / ``completed_at``

        Raises:
            NotFoundError: If either agent is not found in the caller's tenant
        """
        response = await self._http.request(
            "POST",
            "/api/v1/trust/revoke-delegation",
            params={
                "delegatee_id": delegatee_id,
                "delegator_id": delegator_id,
                "reason": reason,
            },
        )
        return response
