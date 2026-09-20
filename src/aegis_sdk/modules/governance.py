"""
Governance Module for Agentic OS SDK.

Provides governance, RBAC, policies, and data classification management.

33 methods:
- list_permissions() - List all permissions
- list_roles() - List roles
- get_role() - Get role details
- add_permission() - Add permission to role
- remove_permission() - Remove permission from role
- delete_role() - Delete custom role
- get_user_permissions() - Get user's effective permissions
- check_permission() - Evaluate whether a user holds a permission
- list_classifications() - List data classifications
- get_classification() - Get classification details
- create_classification() - Create classification
- update_classification() - Update classification
- delete_classification() - Delete classification
- list_policies() - List access policies
- get_policy() - Get policy details
- create_policy() - Create access policy
- update_policy() - Update policy
- delete_policy() - Delete policy
- evaluate_access() - Evaluate access request
- list_consents() - List consent records
- get_consent() - Get consent details
- record_consent() - Record new consent
- withdraw_consent() - Withdraw consent
- check_consent() - Check if valid consent exists
- get_lineage() - Get data lineage graph
- get_lineage_impact() - Get downstream impact analysis
- compile_policy_clauses() - Project a clause set into a compilation run (raises on widening)
- get_compilation_run() - Observe a run, with its measured effect and its outcome
- list_compilation_runs() - Enumerate runs (limit/offset only; no order promised)
- apply_compilation_run() - Apply a run via CAS, re-checking the effect at apply
- list_policy_clauses() - List the clauses of a set
- create_policy_clause() - Author a clause at a position
- retract_policy_clause() - Retract a clause (a STATE on a position, never a delete)

The seven compilation methods above are the SDK half of the policy-clause
compilation capability. Their refusals carry a THREE-VALUED reason vocabulary —
see § Policy-clause compilation below — and the module deliberately adds no
exception class of its own: a refusal arrives as the shared
``GovernanceViolationError`` that ``_http.py`` already maps HTTP 423 to.
"""

from typing import Any, Final, Literal

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class Permission(TolerantModel):
    """Permission model."""

    id: str
    name: str
    resource: str
    action: str
    description: str | None = None


class Role(TolerantModel):
    """Role model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    permissions: list[str]
    is_system: bool = Field(alias="isSystem")
    member_count: int = Field(alias="memberCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class UserPermissions(TolerantModel):
    """User permissions response."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    permissions: list[str]


class PermissionCheck(TolerantModel):
    """Result of a single permission check.

    Wire shape verified against ``CheckPermissionResponse`` at -- snake_case, NO Pydantic alias
    generator (``{"allowed": bool, "reason": str | None}``).
    """

    allowed: bool
    reason: str | None = None


class HandlingRequirements(TolerantModel):
    """Data handling requirements."""

    model_config = ConfigDict(populate_by_name=True)

    encryption: bool = False
    masking: bool = False
    access_control_required: bool = Field(False, alias="accessControlRequired")
    audit_logging: bool = Field(False, alias="auditLogging")


class Classification(TolerantModel):
    """Data classification model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    level: int  # 1=Public, 2=Internal, 3=Confidential, 4=Restricted
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    handling_requirements: HandlingRequirements | None = Field(None, alias="handlingRequirements")
    requires_consent: bool = Field(False, alias="requiresConsent")
    requires_encryption: bool = Field(False, alias="requiresEncryption")
    allows_export: bool = Field(True, alias="allowsExport")
    audit_access: bool = Field(False, alias="auditAccess")
    retention_default_days: int | None = Field(None, alias="retentionDefaultDays")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class PolicyCondition(TolerantModel):
    """ABAC policy condition."""

    field: str
    operator: str  # eq, ne, gt, lt, in, contains
    value: Any


class PolicyPrincipals(TolerantModel):
    """Policy principals (who the policy applies to)."""

    users: list[str] | None = None
    roles: list[str] | None = None
    teams: list[str] | None = None
    agents: list[str] | None = None


class PolicyResources(TolerantModel):
    """Policy resources (what the policy applies to)."""

    model_config = ConfigDict(populate_by_name=True)

    patterns: list[str] | None = None
    types: list[str] | None = None
    work_units: list[str] | None = Field(None, alias="workUnits")


class TimeRestrictions(TolerantModel):
    """Time-based access restrictions."""

    model_config = ConfigDict(populate_by_name=True)

    days: list[str] | None = None  # mon, tue, wed, etc.
    start_hour: int | None = Field(None, alias="startHour")
    end_hour: int | None = Field(None, alias="endHour")
    timezone: str | None = None


class AccessPolicy(TolerantModel):
    """Access policy model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    description: str | None = None
    enabled: bool = True
    priority: int = 1
    effect: str  # allow or deny
    classifications: list[str] | None = None
    principals: PolicyPrincipals | None = None
    resources: PolicyResources | None = None
    actions: list[str] | None = None
    conditions: list[PolicyCondition] | None = None
    time_restrictions: TimeRestrictions | None = Field(None, alias="timeRestrictions")
    requires_mfa: bool = Field(False, alias="requiresMfa")
    requires_justification: bool = Field(False, alias="requiresJustification")
    max_access_duration_minutes: int | None = Field(None, alias="maxAccessDurationMinutes")
    notification_recipients: list[str] | None = Field(None, alias="notificationRecipients")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class AccessEvaluation(TolerantModel):
    """Access evaluation result."""

    model_config = ConfigDict(populate_by_name=True)

    allowed: bool
    policy_id: str | None = Field(None, alias="policyId")
    reason: str | None = None
    requires_mfa: bool = Field(False, alias="requiresMfa")
    requires_justification: bool = Field(False, alias="requiresJustification")
    max_duration_minutes: int | None = Field(None, alias="maxDurationMinutes")


class Consent(TolerantModel):
    """Consent record model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    subject_id: str = Field(alias="subjectId")
    subject_email: str | None = Field(None, alias="subjectEmail")
    subject_type: str = Field(alias="subjectType")  # user, customer, employee, vendor
    purpose: str
    purpose_category: str = Field(alias="purposeCategory")
    legal_basis: str = Field(alias="legalBasis")
    data_categories: list[str] = Field(alias="dataCategories")
    processing_activities: list[str] = Field(alias="processingActivities")
    consent_given: bool = Field(alias="consentGiven")
    consent_method: str = Field(alias="consentMethod")
    third_parties: list[str] | None = Field(None, alias="thirdParties")
    consent_proof_url: str | None = Field(None, alias="consentProofUrl")
    expires_at: str | None = Field(None, alias="expiresAt")
    withdrawn_at: str | None = Field(None, alias="withdrawnAt")
    version: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class LineageNode(TolerantModel):
    """Data lineage node."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    node_type: str = Field(alias="nodeType")  # source, transform, destination, agent
    metadata: dict[str, Any] | None = None


class LineageEdge(TolerantModel):
    """Data lineage edge."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    source_id: str = Field(alias="sourceId")
    target_id: str = Field(alias="targetId")
    edge_type: str = Field(alias="edgeType")  # derives_from, feeds_into, copies_to


class LineageGraph(TolerantModel):
    """Data lineage graph."""

    model_config = ConfigDict(populate_by_name=True)

    nodes: list[LineageNode]
    edges: list[LineageEdge]
    root_id: str | None = Field(None, alias="rootId")


# --------------------------------------------------------------------------- #
# Policy-clause compilation — outcome and reason vocabulary
# --------------------------------------------------------------------------- #
#
# THE OUTCOME IS THREE-VALUED, AND TWO OF THE THREE REFUSE. A boolean gate
# cannot express this: "widened" and "could not be measured" are byte-identical
# in a bool and opposite in consequence. Widening tells an operator to edit the
# clause set; an undecidable measurement tells them to RETRY, because nothing
# was measured and the set is very likely correct. Collapsing the two re-creates
# at the transport layer the exact indistinguishability the gate exists to
# remove, in its most expensive form: a gate that cannot read its input must
# not report "no widening".
#
# The precedent is exact and shipped: the tightening check returns an
# ``undetermined: bool`` alongside ``violations``, whose own comment reads "the
# check did not COMPLETE ... as distinct from completing and finding a
# violation. Both deny, and they must not be reported to the caller as the same
# thing". These constants are that distinction given stable names on the wire.

COMPILATION_OUTCOME_ADMIT: Final = "ADMIT"
"""The projection was measured and admits no new verdict — the run proceeds."""

COMPILATION_OUTCOME_WIDENS: Final = "WIDENS"
"""Measured, and it DOES admit a new verdict — the compilation is refused."""

COMPILATION_OUTCOME_UNDECIDABLE: Final = "UNDECIDABLE"
"""The projection could NOT be measured — the compilation is refused."""

#: The server's ``error.code`` on each refusal. They are pinned here so a caller
#: branches on a name rather than on a string literal, and so a drift between
#: this SDK and the 423 handler is greppable. The VALUES are the server's: this
#: module asserts nothing about which code means what beyond the plan's table.
COMPILATION_WIDENS_REQUESTER_AUTHORITY: Final = "COMPILATION_WIDENS_REQUESTER_AUTHORITY"
"""A WIDENS refusal: the projection admits an authority a protected principal did not hold."""

COMPILATION_EFFECT_UNDECIDABLE: Final = "COMPILATION_EFFECT_UNDECIDABLE"
"""An UNDECIDABLE refusal: something did not resolve, so nothing was measured."""

COMPILATION_RUN_STALE: Final = "COMPILATION_RUN_STALE"
"""An apply whose compare-and-swap on the clause-set version matched no row."""


def compilation_refusal_reason(exc: BaseException) -> str | None:
    """Read the SERVER's reason code off a compilation refusal.

    A refusal arrives as the shared :class:`~aegis_sdk.exceptions.GovernanceViolationError`
    that ``_http.py`` maps HTTP 423 to, and the server's ``error.code`` lands on
    ``exc.details["code"]`` (see ``_extract_error_detail`` for the envelope
    unpacking). This reader exists because that dictionary is NOT guaranteed to
    carry a ``code`` key: a 423 whose body will not parse yields a dict with
    ``message`` and ``status_code`` only, so a direct ``exc.details["code"]``
    raises ``KeyError`` on exactly the responses an operator most needs to read.

    FAIL-CLOSED IN THE ONLY DIRECTION THAT MATTERS: this returns ``None`` when
    the server named no reason, and it NEVER substitutes one of the three codes.
    A defaulted reason would report a refusal the server did not give — the
    failure mode this vocabulary exists to prevent. An UNRECOGNISED code is
    returned VERBATIM rather than coerced into the three, because partners clone
    this SDK and point it at servers that do not move in lockstep with it; ``None``
    means "the server did not name a reason", which is never the same as "the
    compilation was admitted".

    Args:
        exc: The exception raised by one of the compilation methods.

    Returns:
        The server's reason code unchanged, or ``None`` when there was none.
    """
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    code = details.get("code")
    return code if isinstance(code, str) and code else None


class PolicyClauseScope(TolerantModel):
    """The ``(resource_type, action)`` pair a clause governs.

    Each field admits ``"*"``, so containment of two of these is a symbolic
    question — never a sampled one.
    """

    resource_type: str
    action: str


class PolicyClause(TolerantModel):
    """One governance clause: a member of an ORDERED set.

    ``position`` is the ordinal within the set, and it is the **pairing key**.
    The projected state is aligned to the source clause set BY POSITION, so a
    retracted clause keeps its position and its role binding — retraction is a
    state on a position, never a deletion that compacts the sequence. A row read
    without its ``position`` cannot be paired, which is why the field is not
    optional here.
    """

    id: str
    organization_id: str
    clause_set_id: str
    position: int
    role_id: str
    effect: Literal["allow", "deny"]
    """The axis the widening classification is per. A third value is REFUSED
    rather than tolerated: an unrecognised effect on an authority-bearing row is
    a server change, and reading it as one of these two would be a guess."""
    scope: PolicyClauseScope
    condition: dict[str, Any] | None = None
    body: str | None = None
    is_retracted: bool
    """REQUIRED, deliberately — no default.

    A defaulted ``False`` would read "the server told us nothing" as "this clause
    is in force". That is the fail-open shape ``_tolerant.py``'s docstring names
    for a field whose default GRANTS something, and this is the field that decides
    whether a clause is live. A missing value here is a server fault worth
    raising on."""
    authored_by_role_id: str | None = None
    authored_by_authority_level: str | None = None
    """Snapshotted at author time by the SERVER. This surface never sends either
    one — see :meth:`GovernanceModule.create_policy_clause`."""


class CompilationRun(TolerantModel):
    """A compilation run: what was compiled, against which source version, and
    what effect the gate measured.
    """

    id: str
    organization_id: str
    clause_set_id: str
    source_version: int
    """The ``ClauseSet.version`` this run compiled — the compare-and-swap token
    an apply is pinned to."""
    requested_by: str
    requested_authority: str | None = None
    projected_state: dict[str, Any] | None = None
    """The projected effective-governance state, keyed by constraint dimension."""
    effect_outcome: str | None = None
    """One of :data:`COMPILATION_OUTCOME_ADMIT` / ``_WIDENS`` / ``_UNDECIDABLE``.

    Typed ``str`` and NOT ``Literal[...]``, which is a deliberate asymmetry with
    ``PolicyClause.effect`` above. This field is an OBSERVATION of a gate result
    on a surface whose job is to report what the server measured; a Literal here
    would make a fourth outcome unrepresentable and turn ``get_compilation_run``
    into a validation error against a newer server. Fidelity is the requirement,
    so the string is carried verbatim and the comparison names above are offered
    for callers that branch."""
    effect_measured: dict[str, Any] | None = None
    """The per-effect widening classification the gate computed, naming
    ``(dimension, field, pre, post)`` rows. Carried VERBATIM: the row shape is the
    server's to name, and re-typing a payload whose server has not landed would be
    a guess that raises on the real thing."""
    applied_at: str | None = None
    applied_version: int | None = None


class GovernanceModule:
    """
    Governance module for RBAC, policies, and data classification.

    Provides comprehensive access control and data governance capabilities.

    Examples:
        # Check user permissions
        >>> perms = await client.governance.get_user_permissions("user-123")
        >>> print(f"Permissions: {perms.permissions}")

        # Create access policy
        >>> policy = await client.governance.create_policy(
        ...     name="Confidential Data Access",
        ...     effect="allow",
        ...     classifications=["confidential"],
        ...     principals={"roles": ["data_analyst"]},
        ...     requires_mfa=True
        ... )
    """

    def __init__(self, http_client):
        """Initialize governance module."""
        self._http = http_client

    # RBAC Methods
    async def list_permissions(self) -> list[Permission]:
        """
        List all available permissions.

        Returns:
            List[Permission]: All system permissions
        """
        response = await self._http.request(
            "GET",
            "/api/v1/rbac/permissions",
        )
        return [Permission(**p) for p in response.get("permissions", [])]

    async def list_roles(
        self,
        search: str | None = None,
        include_system: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Role]:
        """
        List all roles.

        Args:
            search: Search by role name
            include_system: Include system roles
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Role]: List of roles
        """
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "include_system": str(include_system).lower(),
        }
        if search:
            params["search"] = search

        response = await self._http.request(
            "GET",
            "/api/v1/rbac/roles",
            params=params,
        )
        return [Role(**r) for r in response.get("records", [])]

    async def get_role(self, role: str) -> Role:
        """
        Get role with its permissions.

        Args:
            role: Role name

        Returns:
            Role: Role details with permissions
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/rbac/roles/{encode_path_param(role)}",
        )
        return Role(**response)

    async def add_permission(self, role: str, permission_id: str) -> Role:
        """
        Add permission to role.

        Args:
            role: Role name
            permission_id: Permission ID to add

        Returns:
            Role: Updated role
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/rbac/roles/{encode_path_param(role)}",
            json_data={"permissionId": permission_id},
        )
        return Role(**response)

    async def remove_permission(self, role: str, permission_id: str) -> Role:
        """
        Remove permission from role.

        Args:
            role: Role name
            permission_id: Permission ID to remove

        Returns:
            Role: Updated role
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/rbac/roles/{encode_path_param(role)}/{encode_path_param(permission_id)}",
        )
        return Role(**response)

    async def delete_role(self, role: str) -> bool:
        """
        Delete custom role.

        Args:
            role: Role name (system roles cannot be deleted)

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/rbac/roles/{encode_path_param(role)}",
        )
        return True

    async def get_user_permissions(self, user_id: str) -> UserPermissions:
        """
        Get effective permissions for a user.

        Args:
            user_id: User ID

        Returns:
            UserPermissions: User's effective permissions
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/rbac/users/{encode_path_param(user_id)}",
        )
        return UserPermissions(**response)

    async def check_permission(
        self,
        user_id: str,
        permission: str,
        resource: str | None = None,
    ) -> PermissionCheck:
        """
        Check whether a user holds a given permission.

        Evaluates the user's role-based permissions against the requested
        permission string (e.g. ``agents:read``, ``policies:*``); wildcard
        matching follows the RBAC middleware rules (POST /api/v1/rbac/check-permission).

        Args:
            user_id: User ID to check permissions for.
            permission: Permission string, e.g. ``agents:read``.
            resource: Optional resource identifier for context.

        Returns:
            PermissionCheck: ``allowed`` flag plus a ``reason`` when denied.
        """
        data: dict[str, Any] = {"user_id": user_id, "permission": permission}
        if resource is not None:
            data["resource"] = resource

        response = await self._http.request(
            "POST",
            "/api/v1/rbac/check-permission",
            json_data=data,
        )
        return PermissionCheck(**response)

    # Classification Methods
    async def list_classifications(
        self,
        min_level: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Classification]:
        """
        List data classifications.

        Args:
            min_level: Filter by minimum level (1-4)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Classification]: Data classifications
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if min_level is not None:
            params["min_level"] = min_level

        response = await self._http.request(
            "GET",
            "/api/v1/data-governance/classifications",
            params=params,
        )
        return [Classification(**c) for c in response.get("classifications", [])]

    async def get_classification(self, classification_id: str) -> Classification:
        """
        Get classification details.

        Args:
            classification_id: Classification ID

        Returns:
            Classification: Classification details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/classifications/{encode_path_param(classification_id)}",
        )
        return Classification(**response)

    async def create_classification(
        self,
        name: str,
        level: int,
        description: str | None = None,
        color: str | None = None,
        requires_consent: bool = False,
        requires_encryption: bool = False,
        allows_export: bool = True,
        audit_access: bool = False,
        retention_default_days: int | None = None,
    ) -> Classification:
        """
        Create data classification.

        Args:
            name: Classification name
            level: Classification level (1=Public, 2=Internal, 3=Confidential, 4=Restricted)
            description: Description
            color: Hex color code
            requires_consent: Whether data requires consent
            requires_encryption: Whether encryption is required
            allows_export: Whether export is allowed
            audit_access: Whether to audit all access
            retention_default_days: Default retention period

        Returns:
            Classification: Created classification
        """
        data: dict[str, Any] = {
            "name": name,
            "level": level,
            "requiresConsent": requires_consent,
            "requiresEncryption": requires_encryption,
            "allowsExport": allows_export,
            "auditAccess": audit_access,
        }
        if description:
            data["description"] = description
        if color:
            data["color"] = color
        if retention_default_days is not None:
            data["retentionDefaultDays"] = retention_default_days

        response = await self._http.request(
            "POST",
            "/api/v1/data-governance/classifications",
            json_data=data,
        )
        return Classification(**response)

    async def update_classification(
        self,
        classification_id: str,
        name: str | None = None,
        level: int | None = None,
        description: str | None = None,
        requires_encryption: bool | None = None,
    ) -> Classification:
        """
        Update classification.

        Args:
            classification_id: Classification ID
            name: New name
            level: New level
            description: New description
            requires_encryption: Update encryption requirement

        Returns:
            Classification: Updated classification
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if level is not None:
            data["level"] = level
        if description:
            data["description"] = description
        if requires_encryption is not None:
            data["requiresEncryption"] = requires_encryption

        response = await self._http.request(
            "PUT",
            f"/api/v1/data-governance/classifications/{encode_path_param(classification_id)}",
            json_data=data,
        )
        return Classification(**response)

    async def delete_classification(self, classification_id: str) -> bool:
        """
        Delete classification.

        Args:
            classification_id: Classification ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/data-governance/classifications/{encode_path_param(classification_id)}",
        )
        return True

    # Access Policy Methods
    async def list_policies(
        self,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AccessPolicy]:
        """
        List access policies.

        Args:
            enabled: Filter by enabled status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[AccessPolicy]: Access policies
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if enabled is not None:
            params["enabled"] = str(enabled).lower()

        response = await self._http.request(
            "GET",
            "/api/v1/data-governance/policies",
            params=params,
        )
        return [AccessPolicy(**p) for p in response.get("policies", [])]

    async def get_policy(self, policy_id: str) -> AccessPolicy:
        """
        Get access policy details.

        Args:
            policy_id: Policy ID

        Returns:
            AccessPolicy: Policy details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/policies/{encode_path_param(policy_id)}",
        )
        return AccessPolicy(**response)

    async def create_policy(
        self,
        name: str,
        effect: Literal["allow", "deny"],
        description: str | None = None,
        enabled: bool = True,
        priority: int = 1,
        classifications: list[str] | None = None,
        principals: dict[str, Any] | None = None,
        resources: dict[str, Any] | None = None,
        actions: list[str] | None = None,
        conditions: list[dict[str, Any]] | None = None,
        requires_mfa: bool = False,
        requires_justification: bool = False,
    ) -> AccessPolicy:
        """
        Create access policy.

        Args:
            name: Policy name
            effect: Policy effect (allow or deny)
            description: Policy description
            enabled: Whether policy is enabled
            priority: Policy priority (higher = evaluated first)
            classifications: Classification IDs this applies to
            principals: Who the policy applies to (users, roles, teams, agents)
            resources: What the policy applies to (patterns, types)
            actions: Allowed/denied actions
            conditions: ABAC conditions
            requires_mfa: Require MFA for access
            requires_justification: Require justification for access

        Returns:
            AccessPolicy: Created policy

        Example:
            >>> policy = await client.governance.create_policy(
            ...     name="Sensitive Data Access",
            ...     effect="allow",
            ...     classifications=["confidential", "restricted"],
            ...     principals={"roles": ["data_analyst", "compliance_officer"]},
            ...     actions=["read"],
            ...     requires_mfa=True
            ... )
        """
        data: dict[str, Any] = {
            "name": name,
            "effect": effect,
            "enabled": enabled,
            "priority": priority,
            "requiresMfa": requires_mfa,
            "requiresJustification": requires_justification,
        }
        if description:
            data["description"] = description
        if classifications:
            data["classifications"] = classifications
        if principals:
            data["principals"] = principals
        if resources:
            data["resources"] = resources
        if actions:
            data["actions"] = actions
        if conditions:
            data["conditions"] = conditions

        response = await self._http.request(
            "POST",
            "/api/v1/data-governance/policies",
            json_data=data,
        )
        return AccessPolicy(**response)

    async def update_policy(
        self,
        policy_id: str,
        name: str | None = None,
        enabled: bool | None = None,
        priority: int | None = None,
        effect: Literal["allow", "deny"] | None = None,
    ) -> AccessPolicy:
        """
        Update access policy.

        Args:
            policy_id: Policy ID
            name: New name
            enabled: Enable/disable
            priority: New priority
            effect: New effect

        Returns:
            AccessPolicy: Updated policy
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if enabled is not None:
            data["enabled"] = enabled
        if priority is not None:
            data["priority"] = priority
        if effect:
            data["effect"] = effect

        response = await self._http.request(
            "PUT",
            f"/api/v1/data-governance/policies/{encode_path_param(policy_id)}",
            json_data=data,
        )
        return AccessPolicy(**response)

    async def delete_policy(self, policy_id: str) -> bool:
        """
        Delete access policy.

        Args:
            policy_id: Policy ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/data-governance/policies/{encode_path_param(policy_id)}",
        )
        return True

    async def evaluate_access(
        self,
        accessor_id: str,
        accessor_type: Literal["user", "agent", "workflow"],
        resource_type: str,
        resource_id: str,
        action: str,
        classification_level: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> AccessEvaluation:
        """
        Evaluate access request against policies.

        Args:
            accessor_id: ID of who is accessing
            accessor_type: Type of accessor
            resource_type: Type of resource being accessed
            resource_id: ID of resource
            action: Action being performed
            classification_level: Classification level of resource
            context: Additional context for ABAC evaluation

        Returns:
            AccessEvaluation: Evaluation result

        Example:
            >>> result = await client.governance.evaluate_access(
            ...     accessor_id="user-123",
            ...     accessor_type="user",
            ...     resource_type="document",
            ...     resource_id="doc-456",
            ...     action="read",
            ...     classification_level=3
            ... )
            >>> if result.allowed:
            ...     print("Access granted")
        """
        data: dict[str, Any] = {
            "accessorId": accessor_id,
            "accessorType": accessor_type,
            "resourceType": resource_type,
            "resourceId": resource_id,
            "action": action,
        }
        if classification_level is not None:
            data["classificationLevel"] = classification_level
        if context:
            data["context"] = context

        response = await self._http.request(
            "POST",
            "/api/v1/data-governance/policies/evaluate",
            json_data=data,
        )
        return AccessEvaluation(**response)

    # Consent Methods
    async def list_consents(
        self,
        subject_id: str | None = None,
        purpose: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Consent]:
        """
        List consent records.

        Args:
            subject_id: Filter by subject ID
            purpose: Filter by purpose
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Consent]: Consent records
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if subject_id:
            params["subjectId"] = subject_id
        if purpose:
            params["purpose"] = purpose

        response = await self._http.request(
            "GET",
            "/api/v1/data-governance/consents",
            params=params,
        )
        return [Consent(**c) for c in response.get("consents", [])]

    async def get_consent(self, consent_id: str) -> Consent:
        """
        Get consent record.

        Args:
            consent_id: Consent ID

        Returns:
            Consent: Consent details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/consents/{encode_path_param(consent_id)}",
        )
        return Consent(**response)

    async def record_consent(
        self,
        subject_id: str,
        subject_type: Literal["user", "customer", "employee", "vendor"],
        purpose: str,
        purpose_category: Literal["marketing", "analytics", "operations", "legal"],
        legal_basis: str,
        data_categories: list[str],
        processing_activities: list[str],
        consent_given: bool,
        consent_method: str,
        subject_email: str | None = None,
        third_parties: list[str] | None = None,
        expires_at: str | None = None,
    ) -> Consent:
        """
        Record new consent.

        Args:
            subject_id: Subject ID
            subject_type: Type of subject
            purpose: Purpose of data processing
            purpose_category: Category of purpose
            legal_basis: Legal basis for processing
            data_categories: Categories of data covered
            processing_activities: Processing activities covered
            consent_given: Whether consent was given
            consent_method: How consent was obtained
            subject_email: Subject email (optional)
            third_parties: Third parties data shared with
            expires_at: Expiration date (ISO format)

        Returns:
            Consent: Created consent record
        """
        data: dict[str, Any] = {
            "subjectId": subject_id,
            "subjectType": subject_type,
            "purpose": purpose,
            "purposeCategory": purpose_category,
            "legalBasis": legal_basis,
            "dataCategories": data_categories,
            "processingActivities": processing_activities,
            "consentGiven": consent_given,
            "consentMethod": consent_method,
        }
        if subject_email:
            data["subjectEmail"] = subject_email
        if third_parties:
            data["thirdParties"] = third_parties
        if expires_at:
            data["expiresAt"] = expires_at

        response = await self._http.request(
            "POST",
            "/api/v1/data-governance/consents",
            json_data=data,
        )
        return Consent(**response)

    async def withdraw_consent(self, consent_id: str) -> Consent:
        """
        Withdraw consent.

        Args:
            consent_id: Consent ID

        Returns:
            Consent: Updated consent with withdrawal timestamp
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/data-governance/consents/{encode_path_param(consent_id)}/withdraw",
        )
        return Consent(**response)

    async def check_consent(
        self,
        subject_id: str,
        purpose: str,
        data_category: str,
    ) -> bool:
        """
        Check if valid consent exists.

        Args:
            subject_id: Subject ID
            purpose: Purpose to check
            data_category: Data category to check

        Returns:
            bool: True if valid consent exists
        """
        response = await self._http.request(
            "POST",
            "/api/v1/data-governance/consents/check",
            json_data={
                "subjectId": subject_id,
                "purpose": purpose,
                "dataCategory": data_category,
            },
        )
        return response.get("valid", False)

    # Lineage Methods
    async def get_lineage(
        self,
        root_type: str,
        root_id: str,
        depth: int = 3,
        direction: Literal["upstream", "downstream", "both"] = "both",
    ) -> LineageGraph:
        """
        Get data lineage graph.

        Args:
            root_type: Type of root node
            root_id: ID of root node
            depth: Maximum depth to traverse
            direction: Direction to traverse

        Returns:
            LineageGraph: Lineage graph with nodes and edges
        """
        response = await self._http.request(
            "GET",
            "/api/v1/data-governance/lineage/graph",
            params={
                "rootType": root_type,
                "rootId": root_id,
                "depth": depth,
                "direction": direction,
            },
        )
        return LineageGraph(**response)

    async def get_lineage_impact(
        self,
        node_id: str,
    ) -> list[LineageNode]:
        """
        Get downstream impact analysis for a node.

        Args:
            node_id: Lineage node ID

        Returns:
            List[LineageNode]: Affected downstream nodes
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/lineage/nodes/{encode_path_param(node_id)}/impact",
        )
        return [LineageNode(**n) for n in response.get("nodes", [])]

    # Policy clause compilation methods
    #
    # Wire shape: snake_case request and response fields, following the plan's
    # model tables (§ (b)) and the ``CheckPermissionRequest`` precedent in this
    # same module — NOT the alias-carrying camelCase the older RBAC models use.
    #
    # None of these methods wraps its transport call. That is deliberate and is
    # the whole refusal contract: a refusal arrives as the shared
    # GovernanceViolationError raised by ``_http.py`` on HTTP 423, carrying the
    # server's reason code on ``exc.details["code"]``. A ``try/except`` here that
    # re-raised with its own message — or that mapped "no code" onto one of the
    # three — would destroy the distinction between a measured widening and an
    # unmeasured one. Read the reason with :func:`compilation_refusal_reason`.
    async def compile_policy_clauses(
        self,
        clause_set_id: str,
    ) -> CompilationRun:
        """
        Project a clause set into a compilation run.

        Args:
            clause_set_id: The clause set to project.

        Returns:
            CompilationRun: The run, whose ``effect_outcome`` is
            ``COMPILATION_OUTCOME_ADMIT`` when the projection was measured and
            admits no new verdict for any protected principal.

        Raises:
            GovernanceViolationError: The compilation was REFUSED — HTTP 423.
                ``exc.details["code"]`` is ``COMPILATION_WIDENS_REQUESTER_AUTHORITY``
                when the projection was measured and DOES admit a new verdict,
                and ``COMPILATION_EFFECT_UNDECIDABLE`` when it could not be
                measured at all. The two prescribe opposite remedies: edit the
                clause set, versus retry. ``exc.details["details"]`` carries the
                ``clause_set_id``, the principal, and — for a widening — the
                ``(dimension, field, pre, post)`` rows.
        """
        response = await self._http.request(
            "POST",
            "/api/v1/compilation-runs",
            json_data={"clause_set_id": clause_set_id},
        )
        return CompilationRun(**response)

    async def get_compilation_run(self, run_id: str) -> CompilationRun:
        """
        Observe a compilation run, including its measured effect and its outcome.

        An OBSERVATION, so it does not refuse on a non-admitting outcome: a run
        whose ``effect_outcome`` is ``WIDENS`` or ``UNDECIDABLE`` is read as
        what it is. The refusal belongs to the write surfaces, where it decides.

        Args:
            run_id: Compilation run ID.

        Returns:
            CompilationRun: The run as recorded.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/compilation-runs/{encode_path_param(run_id)}",
        )
        return CompilationRun(**response)

    async def list_compilation_runs(
        self,
        clause_set_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CompilationRun]:
        """
        Enumerate compilation runs.

        NO ORDER IS PROMISED. ``limit`` and ``offset`` are forwarded and no sort
        key is sent, mirroring ``observe_audit.list_logs``. A saturated page is a
        cannot-determine, never an absence — so nothing may be derived from the
        order rows arrive in, and nothing here implies one.

        Args:
            clause_set_id: Restrict to one clause set.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List[CompilationRun]: Runs, in an order this surface does not define.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if clause_set_id:
            params["clause_set_id"] = clause_set_id

        response = await self._http.request(
            "GET",
            "/api/v1/compilation-runs",
            params=params,
        )
        return [CompilationRun(**r) for r in response.get("records", [])]

    async def apply_compilation_run(self, run_id: str) -> CompilationRun:
        """
        Apply a compilation run — a compare-and-swap on the clause-set version,
        re-checking the effect at apply.

        Args:
            run_id: Compilation run ID.

        Returns:
            CompilationRun: The applied run, carrying ``applied_at`` and
            ``applied_version``.

        Raises:
            GovernanceViolationError: The apply was REFUSED — HTTP 423.
                ``exc.details["code"]`` is ``COMPILATION_RUN_STALE`` when the
                compare-and-swap matched no row, which means the clause set moved
                under this run. That is a THIRD reason, distinct from a widening:
                the remedy is to re-compile against the current version, because
                the effect must be re-measured against a baseline that has moved —
                never to retry the stale run. It is also distinct from
                ``COMPILATION_WIDENS_REQUESTER_AUTHORITY``, which the re-check can
                raise at apply time.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/compilation-runs/{encode_path_param(run_id)}/apply",
        )
        return CompilationRun(**response)

    async def list_policy_clauses(
        self,
        clause_set_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyClause]:
        """
        List the clauses of a set.

        Pair by ``PolicyClause.position``, never by the order of this response:
        no order is promised here either, and a reconciliation that zips two
        paginated lists assumes an ordering no surface guarantees — failing
        exactly when a page saturates, which is to say on the largest tenants.

        Args:
            clause_set_id: Restrict to one clause set.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            List[PolicyClause]: Clauses, in an order this surface does not define.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if clause_set_id:
            params["clause_set_id"] = clause_set_id

        response = await self._http.request(
            "GET",
            "/api/v1/policy-clauses",
            params=params,
        )
        return [PolicyClause(**c) for c in response.get("records", [])]

    async def create_policy_clause(
        self,
        clause_set_id: str,
        position: int,
        role_id: str,
        effect: Literal["allow", "deny"],
        scope: dict[str, Any],
        condition: dict[str, Any] | None = None,
        body: str | None = None,
    ) -> PolicyClause:
        """
        Author a governance clause at a position in a set.

        THE AUTHORING IDENTITY IS NOT A PARAMETER, and that is load-bearing.
        ``authored_by_role_id`` and ``authored_by_authority_level`` are
        snapshotted by the SERVER from the authenticated session, so this method
        does not accept them and does not send them. An SDK that let a caller
        declare its own authority level would be a body-trusted approver
        identity — the same gap that lets a re-registration pass as
        "tightening".

        Args:
            clause_set_id: The set this clause joins.
            position: The ordinal within the set — the pairing key. Retraction
                later keeps this position; it is never re-used or compacted.
            role_id: The role binding this clause carries.
            effect: ``"allow"`` or ``"deny"`` — the axis wideness is classified per.
            scope: The ``{"resource_type": ..., "action": ...}`` pair; each field
                admits ``"*"``.
            condition: The condition tree, evaluated by ``abac_condition_mapper``.
            body: The clause's own declaration.

        Returns:
            PolicyClause: The authored clause, with the server's author snapshot.
        """
        json_data: dict[str, Any] = {
            "clause_set_id": clause_set_id,
            "position": position,
            "role_id": role_id,
            "effect": effect,
            "scope": scope,
        }
        if condition is not None:
            json_data["condition"] = condition
        if body is not None:
            json_data["body"] = body

        response = await self._http.request(
            "POST",
            "/api/v1/policy-clauses",
            json_data=json_data,
        )
        return PolicyClause(**response)

    async def retract_policy_clause(self, clause_id: str) -> PolicyClause:
        """
        Retract a clause.

        A STATE CHANGE, NOT A DELETION — hence ``POST .../retract`` rather than
        an HTTP ``DELETE``. Deleting the row and closing the gap would re-bind
        every following row to the position — and therefore to the role binding —
        of its predecessor, which is a silent authority misassignment: the
        compiled state reads as well-formed, every row resolves, and it governs
        the wrong roles.

        Args:
            clause_id: Clause ID.

        Returns:
            PolicyClause: The clause with ``is_retracted`` set — still at its
            position, still carrying its role binding.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/policy-clauses/{encode_path_param(clause_id)}/retract",
        )
        return PolicyClause(**response)
