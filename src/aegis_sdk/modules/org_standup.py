"""
Org Standup Module for Agentic OS SDK.

Fills the LIST + org-builder-deploy + role-edit/assign-user + team-members
gaps left by ``aegis_sdk.standup`` (create+get only "vertical standup" shim,). Composes alongside ``standup.OrganizationsModule`` /
``OrganizationUnitsModule`` / ``OrganizationRolesModule`` / ``TeamsModule`` —
this module does NOT replace them, and does not import from them.

Self-contained module: local Pydantic models, no
shared imports from client.py / modules/__init__.py / types.py /
aegis_sdk/standup/*. Every route below is verified against the real backend
routers (all mounted at ``/api/v1``):

    GET  /api/v1/organizations                              -> list_organizations()
    GET  /api/v1/organization-units                          -> list_units()
    GET  /api/v1/organization-roles                           -> list_roles()
    GET  /api/v1/teams                                        -> list_teams()
    POST /api/v1/organization-builder/deploy                   -> deploy()
    PUT  /api/v1/organization-roles/{role_id}                   -> update_role()
    DELETE /api/v1/organization-units/{unit_id}                 -> delete_unit()
    DELETE /api/v1/organization-roles/{role_id}                 -> delete_role()
    POST /api/v1/organization-roles/{role_id}/assign-user        -> assign_user_to_role()
    POST /api/v1/teams/{team_id}/members                         -> add_team_member()
    POST /api/v1/organization-builder/validate                   -> validate_structure()
    GET  /api/v1/organization-builder/deployment-status            -> get_deployment_status()
    POST /api/v1/organization-builder/compile                      -> compile_organization()
    POST /api/v1/organization-builder/preview                       -> preview_compilation()
    POST /api/v1/organization-builder/generate-agents                -> generate_agents()
    POST /api/v1/organization-builder/generate-trust-chains           -> generate_trust_chains()
    POST /api/v1/organization-builder/generate-constraints             -> generate_constraints()
    GET  /api/v1/organization-builder/templates                         -> list_constraint_templates()
    GET  /api/v1/organization-builder/templates/{level}                  -> get_constraint_template()
    POST /api/v1/organization-builder/rollback/{deployment_id}            -> rollback_deployment()
    POST /api/v1/organization-builder/import-yaml                          -> import_yaml()
    GET  /api/v1/organization-builder/verify-integration                    -> verify_integration()

Wire shape: nearly every backend response model above is plain snake_case with
no ``alias_generator`` / camelCase aliasing, so the local models mirror the wire
shape field-for-field with no case translation. ⚠ ONE EXCEPTION, and it is not
cosmetic: ``organization_units.py::PostureCeilingResponse`` emits camelCase
(``unitId``, ``maxTrustPosture``, ...). :class:`PostureCeiling` below carries
explicit aliases for exactly that reason — without them every field on it
parses as ``None``. The blanket claim this paragraph used to make was verified
against five routers and was true of them; it stopped being true of the whole
surface when the hierarchy routes were added here.
"""

from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


# ---------------------------------------------------------------------------
# Organizations (organizations.py::OrganizationResponse / OrganizationListResponse)
# ---------------------------------------------------------------------------


class Organization(TolerantModel):
    """Organization record (organizations.py::OrganizationResponse).

    The server emits ONE response model for create, get and list, so these
    four fields are optional rather than a separate subclass (contrast
    ``aegis_sdk.types.APIKeyCreated``, where the server itself splits create
    from list/get into two distinct response types). Populated ONLY by
    ``POST /organizations``, when the creator's session was successfully
    switched into the new org's context -- ``None`` on every GET/PUT response
    this model also serializes, and ``None`` on create when the switch could
    not complete. Before these were declared, a caller that constructed this
    model from a create response (``Organization(**resp)``) had the one-time
    credential silently dropped on the floor -- there is no second chance,
    the server never re-emits it.
    """

    id: str
    name: str
    slug: str
    status: str
    plan_tier: str
    created_by: str
    created_at: str
    updated_at: str
    access_token: str | None = Field(default=None, repr=False)  # bearer credential -- hidden (H1)
    refresh_token: str | None = Field(default=None, repr=False)  # bearer credential -- hidden (H1)
    token_type: str | None = None
    expires_in: int | None = None


class OrganizationList(TolerantModel):
    """Paginated organization list (``{records, total}``)."""

    records: list[Organization]
    total: int


# ---------------------------------------------------------------------------
# Organization units (organization_units.py::UnitResponse / UnitListResponse)
# ---------------------------------------------------------------------------


class OrganizationUnit(TolerantModel):
    """Organization unit record (organization_units.py::UnitResponse)."""

    id: str
    organization_id: str
    name: str
    unit_type: str
    code: str | None = None
    parent_unit_id: str | None = None
    level: int
    path: str | None = None
    address: str | None = None
    display_subtype: str | None = None
    default_classification: str = "public"
    # Present on the server's UnitResponse and absent here until now, so a
    # caller reading it got nothing and no type checker objected.
    isolation_domain: str | None = None
    description: str | None = None
    mission_statement: str | None = None
    responsibilities_json: str = "[]"
    budget_allocation: float | None = None
    budget_currency: str = "USD"
    headcount_limit: int | None = None
    default_constraint_template_id: str | None = None
    constraint_overrides_json: str = "{}"
    max_trust_posture: str | None = None
    status: str
    version: int = 1
    metadata_json: str = "{}"
    tags_json: str = "[]"
    created_by: str | None = None
    created_at: str
    updated_at: str


class OrganizationUnitList(TolerantModel):
    """Paginated organization-unit list (``{records, total}``)."""

    records: list[OrganizationUnit]
    total: int


# ---------------------------------------------------------------------------
# Organization roles (organization_roles.py::RoleResponse / RoleListResponse)
# ---------------------------------------------------------------------------


class OrganizationRole(TolerantModel):
    """Organization role record (organization_roles.py::RoleResponse)."""

    id: str
    organization_id: str
    organization_unit_id: str
    title: str
    description: str | None = None
    job_description: str | None = None
    responsibilities_json: str = "[]"
    required_skills_json: str = "[]"
    required_capabilities_json: str = "[]"
    authority_level: int
    approval_authority_json: str = "{}"
    reports_to_role_id: str | None = None
    direct_reports_count: int = 0
    constraint_template_id: str | None = None
    constraint_overrides_json: str = "{}"
    # Same drift on the role side: declared by the server, absent here.
    effective_constraints_json: str = "{}"
    shadow_agent_id: str | None = None
    auto_generate_agent: bool = True
    assigned_user_id: str | None = None
    assigned_user_name: str | None = None
    is_vacant: bool = True
    address: str | None = None
    is_primary_for_unit: bool = False
    is_external: bool = False
    status: str
    metadata_json: str = "{}"
    tags_json: str = "[]"
    created_by: str | None = None
    created_at: str
    updated_at: str


class OrganizationRoleList(TolerantModel):
    """Paginated organization-role list (``{records, total}``)."""

    records: list[OrganizationRole]
    total: int


# ---------------------------------------------------------------------------
# Teams (teams.py::TeamResponse / TeamListResponse / TeamMemberResponse)
# ---------------------------------------------------------------------------


class Team(TolerantModel):
    """Team record (teams.py::TeamResponse)."""

    id: str
    organization_id: str
    name: str
    description: str | None = None
    created_at: str
    updated_at: str


class TeamList(TolerantModel):
    """Paginated team list (``{records, total}``)."""

    records: list[Team]
    total: int


class TeamMember(TolerantModel):
    """Team member record (teams.py::TeamMemberResponse)."""

    id: str
    team_id: str
    user_id: str
    role: str
    created_at: str


# ---------------------------------------------------------------------------
# Organization builder (organization_builder.py)
# ---------------------------------------------------------------------------


class ValidationIssue(TolerantModel):
    """Single validation issue with node reference (organization_builder.py::ValidationIssue)."""

    node_id: str
    message: str
    severity: str


class ValidationResult(TolerantModel):
    """Org-structure validation result (organization_builder.py::ValidationResultResponse)."""

    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)


class DeploymentResult(TolerantModel):
    """Org-builder deployment result (organization_builder.py::DeploymentResultResponse).

    ``status`` mirrors the frontend ``DeploymentStatus`` union the backend
    maps onto: ``pending | creating_agents | creating_trust_chains |
    creating_constraints | linking | complete | failed``.
    """

    deployment_id: str
    status: str
    created_agents: int
    created_trust_chains: int
    created_constraints: int
    error: str | None = None
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Organization builder — compile / preview / generate / templates / rollback
# (organization_builder.py response models)
# ---------------------------------------------------------------------------


class CompilationResult(TolerantModel):
    """Outcome of a full organizational compilation."""

    org_id: str
    status: str
    agents_generated: int
    trust_chains_generated: int
    constraint_envelopes_generated: int
    knowledge_policies_generated: int
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    compilation_time_ms: int


class CompilationPreview(TolerantModel):
    """What a compilation WOULD generate. Nothing is created."""

    agent_count: int
    trust_chain_count: int
    constraint_envelope_count: int
    knowledge_policy_count: int
    warnings: list[ValidationIssue] = Field(default_factory=list)
    estimated_time_seconds: float


class AgentsGenerated(TolerantModel):
    """Delegate agents generated for organizational roles."""

    agents: list[dict[str, Any]] = Field(default_factory=list)
    count: int


class TrustChainsGenerated(TolerantModel):
    """Trust chains generated from the reporting hierarchy."""

    trust_chains: list[dict[str, Any]] = Field(default_factory=list)
    count: int


class ConstraintsGenerated(TolerantModel):
    """Constraint envelopes generated from templates."""

    constraints: list[dict[str, Any]] = Field(default_factory=list)
    count: int


class TemplatesList(TolerantModel):
    """Built-in constraint templates, by authority level."""

    templates: list[dict[str, Any]] = Field(default_factory=list)


class RollbackResult(TolerantModel):
    """Outcome of rolling a deployment back."""

    success: bool
    message: str


class YAMLImportResult(TolerantModel):
    """Outcome of importing an organization from YAML."""

    units_created: int
    roles_created: int
    units_updated: int = 0
    roles_updated: int = 0
    compilation: CompilationResult


_UNSET: Any = object()
"""Sentinel distinguishing "argument omitted" from "explicitly None".

Required, not stylistic: the posture-ceiling route treats an OMITTED field as
"leave unchanged" and an explicit ``null`` as "CLEAR the ceiling". A plain
``None`` default would send ``null`` on every call, so calling the setter
without naming a posture would silently WIDEN the ceiling — the exact
composed failure the server hardened against. The server also sets
``extra="forbid"``, so the key must be omitted entirely rather than sent empty.
"""


# ---------------------------------------------------------------------------
# Unit hierarchy + role graph (organization_units.py / organization_roles.py)
# ---------------------------------------------------------------------------


class UnitTreeNode(OrganizationUnit):
    """A unit with its children nested beneath it."""

    children: list["UnitTreeNode"] = Field(default_factory=list)


UnitTreeNode.model_rebuild()


class HierarchyValidation(TolerantModel):
    """Result of validating the unit hierarchy (orphans, cycles)."""

    valid: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    unit_count: int | None = None
    root_count: int | None = None


class IsolationDomains(TolerantModel):
    """The tenant's registered hard-isolation plane set.

    Canonical Aegis ships ZERO planes — the vocabulary is tenant-supplied.
    """

    isolation_domains: list[str] = Field(default_factory=list)


class UnitSummary(TolerantModel):
    """Lightweight unit projection.

    ``has_primary_role`` carries the D/T/R grammar invariant: a department or
    team WITHOUT a head role is structurally incomplete.
    """

    id: str
    name: str
    unit_type: str
    address: str | None = None
    parent_unit_id: str | None = None
    has_primary_role: bool


class CascadeResult(TolerantModel):
    """What a unit move changed BESIDES the unit itself.

    Moving a unit re-parents everything under it: ceilings recompute,
    knowledge-share policies revalidate, bridges re-derive and trust chains are
    revoked and recreated. Read this before treating a move as a small edit.
    """

    descendants_updated: int = 0
    posture_ceilings_recomputed: int = 0
    ksps_suspended: int = 0
    bridges_re_derived: int = 0
    trust_chains_revoked: int = 0
    trust_chains_created: int = 0
    warnings: list[str] = Field(default_factory=list)


class UnitMoveResult(OrganizationUnit):
    """The moved unit's updated fields, with the cascade summary nested."""

    cascade: CascadeResult


class PostureCeiling(TolerantModel):
    """The CARE posture ceiling for a unit.

    ⚠ This is the ONE camelCase response on this module's surface. Every other
    backend model here is plain snake_case, so the aliases below are not
    decoration — without them every field parses as None. Python-side names
    stay snake_case, and ``populate_by_name`` keeps construction by either.

    ``effective_max_trust_posture`` is the one to read: a ceiling cascades, so
    a child can never exceed its parent however its own value reads.
    """

    model_config = ConfigDict(populate_by_name=True)

    unit_id: str = Field(alias="unitId")
    max_trust_posture: str | None = Field(None, alias="maxTrustPosture")
    effective_max_trust_posture: str | None = Field(None, alias="effectiveMaxTrustPosture")
    parent_effective_ceiling: str | None = Field(None, alias="parentEffectiveCeiling")
    allowed_postures: list[str] = Field(default_factory=list, alias="allowedPostures")


class RoleConstraints(TolerantModel):
    """A role's effective constraint envelope."""

    max_cost_usd: float
    max_tokens: int
    max_api_calls: int
    max_actions_per_hour: int


class RoleValidation(TolerantModel):
    """Result of validating a role against the D/T/R grammar."""

    valid: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    role_count: int | None = None
    role_results: list[dict[str, Any]] | None = None


class OrgStandupModule:
    """
    Org-standup LIST + org-builder-deploy + role/team management module.

    Fills the LIST + + role-edit/assign-user
    + team-members gaps left by ``aegis_sdk.standup`` (create+get only,). Use alongside the ``standup`` package's per-family
    create/get modules for a complete vertical-standup surface — this module
    does not duplicate their create/get methods.

    Example:
        >>> orgs = await client.org_standup.list_organizations()
        >>> units = await client.org_standup.list_units()
        >>> roles = await client.org_standup.list_roles()
        >>> result = await client.org_standup.deploy()
    """

    def __init__(self, http_client: "HTTPClient") -> None:
        self._http = http_client

    # ------------------------------------------------------------------
    # P0 — LIST endpoints
    # ------------------------------------------------------------------

    async def list_organizations(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> OrganizationList:
        """
        List organizations visible to the current user.

        Server: ``GET /api/v1/organizations``. Executive users see every
        organization; non-executive users see only their own (server-side
        scoping — no client filter needed for that case).

        Args:
            status: Optional status filter (e.g. ``"active"``, ``"suspended"``).
            limit: Maximum results (1-100).
            offset: Pagination offset.

        Returns:
            OrganizationList: records + total.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/organizations", params=params)
        return OrganizationList(
            records=[Organization(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def list_units(
        self,
        parent_unit_id: str | None = None,
        unit_type: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> OrganizationUnitList:
        """
        List organization units in the current user's organization.

        Server: ``GET /api/v1/organization-units``. Powers the org-builder
        canvas tree load.

        Args:
            parent_unit_id: Filter by parent unit.
            unit_type: Filter by ``"department"`` or ``"team"``.
            include_archived: Include archived units.
            limit: Maximum results (1-200).
            offset: Pagination offset.

        Returns:
            OrganizationUnitList: records + total.
        """
        params: dict[str, Any] = {
            "include_archived": include_archived,
            "limit": limit,
            "offset": offset,
        }
        if parent_unit_id:
            params["parent_unit_id"] = parent_unit_id
        if unit_type:
            params["unit_type"] = unit_type

        response = await self._http.request("GET", "/api/v1/organization-units", params=params)
        return OrganizationUnitList(
            records=[OrganizationUnit(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def list_roles(
        self,
        organization_unit_id: str | None = None,
        authority_level: int | None = None,
        is_vacant: bool | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> OrganizationRoleList:
        """
        List organization roles in the current user's organization.

        Server: ``GET /api/v1/organization-roles``. Powers the org-builder
        reporting-tree load.

        Args:
            organization_unit_id: Filter by unit.
            authority_level: Filter by authority level (1-5).
            is_vacant: Filter by vacancy status.
            include_archived: Include archived roles.
            limit: Maximum results (1-500).
            offset: Pagination offset.

        Returns:
            OrganizationRoleList: records + total.
        """
        params: dict[str, Any] = {
            "include_archived": include_archived,
            "limit": limit,
            "offset": offset,
        }
        if organization_unit_id:
            params["organization_unit_id"] = organization_unit_id
        if authority_level is not None:
            params["authority_level"] = authority_level
        if is_vacant is not None:
            params["is_vacant"] = is_vacant

        response = await self._http.request("GET", "/api/v1/organization-roles", params=params)
        return OrganizationRoleList(
            records=[OrganizationRole(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def list_teams(self, limit: int = 50, offset: int = 0) -> TeamList:
        """
        List teams in the current user's organization.

        Server: ``GET /api/v1/teams``.

        Args:
            limit: Maximum results (1-100).
            offset: Pagination offset.

        Returns:
            TeamList: records + total.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        response = await self._http.request("GET", "/api/v1/teams", params=params)
        return TeamList(
            records=[Team(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    # ------------------------------------------------------------------
    # P0 — organization-builder deploy (THE "stand up the org" action)
    # ------------------------------------------------------------------

    async def deploy(
        self,
        dry_run: bool = False,
        structure: dict[str, Any] | None = None,
    ) -> DeploymentResult:
        """
        Compile and deploy the shadow enterprise.

        Server: ``POST /api/v1/organization-builder/deploy``. When
        ``structure`` is provided (the canvas's
        ``OrganizationStructureRequest`` shape — ``workspace_id``, ``units``,
        ``roles``, ``hierarchy``, ``bridges``), it is saved to the database
        first; otherwise the structure already stored for the organization is
        compiled and deployed.

        Args:
            dry_run: Preview without creating (default ``False``).
            structure: Optional canvas structure body. Omit to deploy the
                structure already saved for the organization.

        Returns:
            DeploymentResult: deployment_id, status, and created-object counts.
        """
        response = await self._http.request(
            "POST",
            "/api/v1/organization-builder/deploy",
            params={"dry_run": dry_run},
            json_data=structure,
        )
        return DeploymentResult(**response)

    # ------------------------------------------------------------------
    # P1 — role edit / assign-user, team members, org-builder validate/status
    # ------------------------------------------------------------------

    async def update_role(self, role_id: str, **fields: Any) -> OrganizationRole:
        """
        Update an organization role — including setting ``reports_to_role_id``
        to build the reporting tree.

        Server: ``PUT /api/v1/organization-roles/{role_id}``.

        Args:
            role_id: Role ID to update.
            **fields: Any of ``organization_unit_id``, ``title``,
                ``description``, ``job_description``, ``responsibilities``,
                ``required_skills``, ``required_capabilities``,
                ``authority_level``, ``approval_authority``,
                ``reports_to_role_id``, ``constraint_template_id``,
                ``constraint_overrides``, ``auto_generate_agent``,
                ``is_primary_for_unit``, ``is_external``, ``metadata``,
                ``tags``, ``status`` (``"active"`` or ``"archived"``).

        Returns:
            OrganizationRole: Updated role.
        """
        response = await self._http.request(
            "PUT", f"/api/v1/organization-roles/{encode_path_param(role_id)}", json_data=fields
        )
        return OrganizationRole(**response)

    async def assign_user_to_role(self, role_id: str, user_id: str) -> OrganizationRole:
        """
        Assign a human to a vacant (or occupied) role.

        Server: ``POST /api/v1/organization-roles/{role_id}/assign-user``.

        Args:
            role_id: Role ID.
            user_id: User ID to assign — must belong to the same organization.

        Returns:
            OrganizationRole: Updated role (``is_vacant=False``,
            ``assigned_user_id`` set).
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/organization-roles/{encode_path_param(role_id)}/assign-user",
            json_data={"user_id": user_id},
        )
        return OrganizationRole(**response)

    # -----------------------------------------------------------------------
    # Deletes
    #
    # Both routes below have ALWAYS existed on the server and had NO SDK
    # method at all -- not merely "no hard delete". A partner holding this SDK
    # could create an organization unit or role and then had no way to remove
    # one, by any means, which is why a rehearsal tenant could not be reset.
    #
    # The gap was found by sweeping the CLASS rather than the reported
    # instance: seven server routers declare ``hard: bool = Query(False)``
    # (bridges, roles, directives, organization-units, organization-roles,
    # api-keys, knowledge). Four of their SDK counterparts already passed
    # ``hard`` through; api-keys passed no ``hard``; these two had no delete
    # method whatsoever. Core+SDK parity: a capability the
    # partner cannot reach is not a delivered capability.
    #
    # The return type is ``dict[str, Any]`` rather than a new model, matching
    # ``work_objectives.py::delete_directive`` -- the established convention
    # in this SDK for the server's ``MessageResponse`` shape.
    # -----------------------------------------------------------------------

    async def delete_unit(self, unit_id: str, hard: bool = False) -> dict[str, Any]:
        """
        Delete an organization unit. Default is a SOFT delete (archives it).

        Server: ``DELETE /api/v1/organization-units/{unit_id}``.

        ⛔ ``hard=True`` is IRREVERSIBLE and removes the row rather than
        archiving it. Prefer the default: an archived unit stays available to
        forensic and audit queries, which is usually the point of keeping org
        structure at all. ``hard=True`` is for resetting a rehearsal or demo
        tenant.

        ⚠ This route FAILS CLOSED with ``409`` when any delegate agent in the
        unit holds trust that could not be settled. On that response
        the unit is left COMPLETELY UNTOUCHED -- it is not partially deleted,
        so the call is safe to retry once the trust is settled.

        Requires the ``organizations:update`` permission (org_owner or
        org_admin).

        Args:
            unit_id: Unit ID to delete.
            hard: If True, permanently delete instead of archiving.
                Defaults to False, matching the server's default.

        Returns:
            ``{"message": str}``

        Raises:
            NotFoundError: ``404`` — unit does not exist, or belongs to
                another organization.
            AuthorizationError: ``403`` — missing ``organizations:update``.

        Example:
            >>> await client.org_standup.delete_unit("unit-1")
            >>> await client.org_standup.delete_unit("unit-1", hard=True)
        """
        result: dict[str, Any] = await self._http.request(
            "DELETE",
            f"/api/v1/organization-units/{encode_path_param(unit_id)}",
            params={"hard": hard},
        )
        return result

    async def delete_role(self, role_id: str, hard: bool = False) -> dict[str, Any]:
        """
        Delete an organization role. Default is a SOFT delete (archives it).

        Server: ``DELETE /api/v1/organization-roles/{role_id}``.

        ⛔ ``hard=True`` is IRREVERSIBLE and removes the row rather than
        archiving it. Prefer the default; a role participates in reporting
        trees and trust chains whose records outlive the role itself.

        ⚠ NOT the same call as ``client.role_admin.delete()``, despite the
        similar name. That one targets the RBAC router at ``/api/v1/roles``
        (a permission-bearing role); this one targets an ORGANIZATION role at
        ``/api/v1/organization-roles`` -- a position in the org chart, with an
        occupant and a ``reports_to_role_id``. The two routers are distinct
        and an id from one does not resolve on the other.

        Requires the ``organizations:update`` permission (org_owner or
        org_admin).

        Args:
            role_id: Organization role ID to delete.
            hard: If True, permanently delete instead of archiving.
                Defaults to False, matching the server's default.

        Returns:
            ``{"message": str}``

        Raises:
            NotFoundError: ``404`` — role does not exist, or belongs to
                another organization.
            AuthorizationError: ``403`` — missing ``organizations:update``.

        Example:
            >>> await client.org_standup.delete_role("org-role-1")
            >>> await client.org_standup.delete_role("org-role-1", hard=True)
        """
        result: dict[str, Any] = await self._http.request(
            "DELETE",
            f"/api/v1/organization-roles/{encode_path_param(role_id)}",
            params={"hard": hard},
        )
        return result

    async def add_team_member(
        self,
        team_id: str,
        user_id: str,
        role: str = "member",
    ) -> TeamMember:
        """
        Add a member to a team.

        Server: ``POST /api/v1/teams/{team_id}/members``.

        Args:
            team_id: Team ID.
            user_id: User ID to add.
            role: ``"team_lead"`` or ``"member"`` (default ``"member"``).

        Returns:
            TeamMember: Created membership record.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/teams/{encode_path_param(team_id)}/members",
            json_data={"user_id": user_id, "role": role},
        )
        return TeamMember(**response)

    async def validate_structure(self, structure: dict[str, Any] | None = None) -> ValidationResult:
        """
        Validate the organization structure before deployment.

        Server: ``POST /api/v1/organization-builder/validate``. Checks for
        circular dependencies, missing required fields, invalid
        relationships, and constraint conflicts.

        Args:
            structure: Optional canvas structure body (same shape as
                :meth:`deploy`'s ``structure``). Omit to validate the
                structure already stored for the organization.

        Returns:
            ValidationResult: valid flag + structured errors/warnings.
        """
        response = await self._http.request(
            "POST", "/api/v1/organization-builder/validate", json_data=structure
        )
        return ValidationResult(
            valid=response["valid"],
            errors=[ValidationIssue(**e) for e in response.get("errors", [])],
            warnings=[ValidationIssue(**w) for w in response.get("warnings", [])],
        )

    async def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        """
        Poll the status of a deployment fired via :meth:`deploy`.

        Server: ``GET /api/v1/organization-builder/deployment-status``.
        Checks the in-memory cache first, falling back to the database so
        status lookups survive service restarts.

        Args:
            deployment_id: Deployment ID returned by :meth:`deploy`.

        Returns:
            DeploymentResult: Current deployment status.
        """
        response = await self._http.request(
            "GET",
            "/api/v1/organization-builder/deployment-status",
            params={"deployment_id": deployment_id},
        )
        return DeploymentResult(**response)

    # -- organization builder ------------------------------------------------

    async def compile_organization(
        self,
        include_shadow_agents: bool = True,
        include_trust_chains: bool = True,
        include_constraints: bool = True,
        include_knowledge_policies: bool = True,
        generate_for_unit_id: str | None = None,
    ) -> CompilationResult:
        """
        Compile the organizational structure into agents, trusts and constraints.

        Server: ``POST /api/v1/organization-builder/compile``. This CREATES
        records — use :meth:`preview_compilation` to see what it would do
        without doing it.

        Args:
            include_shadow_agents: Generate delegate agents for roles
            include_trust_chains: Generate trust chains from the hierarchy
            include_constraints: Generate constraint envelopes from templates
            include_knowledge_policies: Generate knowledge-sharing policies
            generate_for_unit_id: Limit compilation to one unit

        Returns:
            CompilationResult: counts per artefact kind, plus warnings/errors

        Example:
            >>> result = await client.org_standup.compile_organization()
            >>> print(f"{result.agents_generated} agents in {result.compilation_time_ms}ms")
            >>> for err in result.errors:
            ...     print(err)
        """
        options: dict[str, Any] = {
            "include_shadow_agents": include_shadow_agents,
            "include_trust_chains": include_trust_chains,
            "include_constraints": include_constraints,
            "include_knowledge_policies": include_knowledge_policies,
        }
        if generate_for_unit_id is not None:
            options["generate_for_unit_id"] = generate_for_unit_id

        response = await self._http.request(
            "POST", "/api/v1/organization-builder/compile", json_data={"options": options}
        )
        return CompilationResult(**response)

    async def preview_compilation(
        self, structure: dict[str, Any] | None = None
    ) -> CompilationPreview:
        """
        Preview what a compilation would generate, creating nothing.

        Server: ``POST /api/v1/organization-builder/preview``.

        Args:
            structure: Optional canvas structure body (same shape as
                :meth:`deploy`'s ``structure``). Omit to preview the structure
                already stored for the organization.

        Returns:
            CompilationPreview: per-artefact counts, warnings, and an estimate

        Example:
            >>> preview = await client.org_standup.preview_compilation()
            >>> print(f"would generate {preview.agent_count} agents")
        """
        response = await self._http.request(
            "POST", "/api/v1/organization-builder/preview", json_data=structure
        )
        return CompilationPreview(**response)

    async def generate_agents(self, unit_id: str | None = None) -> AgentsGenerated:
        """
        Generate delegate agents for organizational roles.

        Server: ``POST /api/v1/organization-builder/generate-agents``.

        Args:
            unit_id: Limit generation to one unit; omit for the whole org

        Returns:
            AgentsGenerated: the agents created, and how many

        Example:
            >>> result = await client.org_standup.generate_agents(unit_id="unit-1")
            >>> print(result.count)
        """
        params = {"unit_id": unit_id} if unit_id is not None else None
        response = await self._http.request(
            "POST", "/api/v1/organization-builder/generate-agents", params=params
        )
        return AgentsGenerated(**response)

    async def generate_trust_chains(self) -> TrustChainsGenerated:
        """
        Generate trust chains from the organizational hierarchy.

        Server: ``POST /api/v1/organization-builder/generate-trust-chains``.
        Trust follows the REPORTING structure and authority levels — it is
        derived from the org chart, not declared separately.

        Args:
            None

        Returns:
            TrustChainsGenerated: the chains created, and how many

        Example:
            >>> result = await client.org_standup.generate_trust_chains()
            >>> print(result.count)
        """
        response = await self._http.request(
            "POST", "/api/v1/organization-builder/generate-trust-chains"
        )
        return TrustChainsGenerated(**response)

    async def generate_constraints(self) -> ConstraintsGenerated:
        """
        Generate constraint envelopes from the built-in templates.

        Server: ``POST /api/v1/organization-builder/generate-constraints``.
        Templates are applied by authority level, so a role's envelope follows
        from where it sits rather than from a per-role decision.

        Args:
            None

        Returns:
            ConstraintsGenerated: the envelopes created, and how many

        Example:
            >>> result = await client.org_standup.generate_constraints()
            >>> print(result.count)
        """
        response = await self._http.request(
            "POST", "/api/v1/organization-builder/generate-constraints"
        )
        return ConstraintsGenerated(**response)

    async def list_constraint_templates(self) -> TemplatesList:
        """
        List the built-in constraint templates by authority level.

        Server: ``GET /api/v1/organization-builder/templates``.

        Args:
            None

        Returns:
            TemplatesList: every built-in template

        Example:
            >>> templates = await client.org_standup.list_constraint_templates()
            >>> print(len(templates.templates))
        """
        response = await self._http.request(
            "GET", "/api/v1/organization-builder/templates"
        )
        return TemplatesList(**response)

    async def get_constraint_template(self, level: int) -> dict[str, Any]:
        """
        Get the constraint template for one authority level (1-5).

        ⚠ Returns a raw dict, not a typed model, because the SERVER declares
        none: the route is annotated ``response_model=dict``, so there is no
        schema to wrap and a model here would be this client's invention rather
        than the API's contract. Typing it belongs with declaring it.

        Levels are 1 Staff, 2 Manager, 3 Director, 4 VP, 5 C-Suite. Authority
        level is informational and does NOT gate access — clearance does.

        Args:
            level: Authority level, 1 to 5

        Returns:
            The template exactly as the server emits it

        Example:
            >>> template = await client.org_standup.get_constraint_template(3)
            >>> print(template.get("max_budget"))
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-builder/templates/{encode_path_param(level)}"
        )
        return dict(response)

    async def rollback_deployment(self, deployment_id: str) -> RollbackResult:
        """
        Roll a deployment back, removing what it created.

        Server: ``POST /api/v1/organization-builder/rollback/{deployment_id}``.
        Removes the agents, trust chains and constraints that deployment
        created. The server verifies the deployment belongs to the caller's
        organization before acting.

        Args:
            deployment_id: The deployment to roll back

        Returns:
            RollbackResult: success flag and a message

        Example:
            >>> result = await client.org_standup.rollback_deployment("dep-1")
            >>> assert result.success
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/organization-builder/rollback/{encode_path_param(deployment_id)}",
        )
        return RollbackResult(**response)

    async def import_yaml(self, yaml_content: str) -> YAMLImportResult:
        """
        Import an organization structure from a YAML definition.

        Server: ``POST /api/v1/organization-builder/import-yaml``. Validates
        the D/T/R grammar — every department and team must have a head role —
        persists the units and roles, then triggers a full compilation, which
        is why the result carries a nested :class:`CompilationResult`.

        Args:
            yaml_content: The YAML document, as a string

        Returns:
            YAMLImportResult: created/updated counts plus the compilation

        Example:
            >>> result = await client.org_standup.import_yaml(yaml_text)
            >>> print(result.units_created, result.compilation.agents_generated)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/organization-builder/import-yaml",
            json_data={"yaml_content": yaml_content},
        )
        return YAMLImportResult(**response)

    async def verify_integration(self) -> dict[str, Any]:
        """
        Verify the org chart is coherently wired.

        Checks that units resolve to roles, that trust chains exist for every
        agent, that user-access records are correct, and that budgets and
        constraints are linked.

        ⚠ Returns a raw dict: the server route declares NO response model at
        all, so there is no contract to type against. Left untyped
        deliberately rather than guessed at.

        Args:
            None

        Returns:
            The verification report exactly as the server emits it

        Example:
            >>> report = await client.org_standup.verify_integration()
            >>> print(report)
        """
        response = await self._http.request(
            "GET", "/api/v1/organization-builder/verify-integration"
        )
        return dict(response)

    # -- unit hierarchy ------------------------------------------------------

    async def get_unit_tree(self) -> list[UnitTreeNode]:
        """
        Get the whole organizational tree, nested.

        Server: ``GET /api/v1/organization-units/tree``.

        Args:
            None

        Returns:
            The root units, each carrying its children recursively

        Example:
            >>> tree = await client.org_standup.get_unit_tree()
            >>> for root in tree:
            ...     print(root.name, len(root.children))
        """
        response = await self._http.request("GET", "/api/v1/organization-units/tree")
        return [UnitTreeNode(**node) for node in response]

    async def get_root_units(self) -> list[OrganizationUnit]:
        """
        Get every unit with no parent.

        Server: ``GET /api/v1/organization-units/roots``.

        Args:
            None

        Returns:
            The organization's root units

        Example:
            >>> roots = await client.org_standup.get_root_units()
        """
        response = await self._http.request("GET", "/api/v1/organization-units/roots")
        return [OrganizationUnit(**u) for u in response]

    async def validate_hierarchy(self) -> HierarchyValidation:
        """
        Validate the unit hierarchy for orphans and circular references.

        Server: ``GET /api/v1/organization-units/validate``.

        Args:
            None

        Returns:
            HierarchyValidation: validity plus structured errors and warnings

        Example:
            >>> result = await client.org_standup.validate_hierarchy()
            >>> if not result.valid:
            ...     print(result.errors)
        """
        response = await self._http.request("GET", "/api/v1/organization-units/validate")
        return HierarchyValidation(**response)

    async def get_isolation_domains(self) -> IsolationDomains:
        """
        Get the tenant's registered hard-isolation plane set.

        Server: ``GET /api/v1/organization-units/isolation-domains``.

        Args:
            None

        Returns:
            IsolationDomains: the plane labels units may be assigned

        Example:
            >>> domains = await client.org_standup.get_isolation_domains()
        """
        response = await self._http.request(
            "GET", "/api/v1/organization-units/isolation-domains"
        )
        return IsolationDomains(**response)

    async def set_isolation_domains(self, isolation_domains: list[str]) -> IsolationDomains:
        """
        Replace the tenant's registered plane set.

        Server: ``PUT /api/v1/organization-units/isolation-domains``. This
        REPLACES rather than merges, which is what makes de-registration
        expressible at all — pass the whole intended state, not a delta.

        Args:
            isolation_domains: The complete plane set after this call

        Returns:
            IsolationDomains: the registered set, normalized server-side

        Example:
            >>> await client.org_standup.set_isolation_domains(["alpha", "beta"])
        """
        response = await self._http.request(
            "PUT",
            "/api/v1/organization-units/isolation-domains",
            json_data={"isolation_domains": isolation_domains},
        )
        return IsolationDomains(**response)

    async def get_unit_summary(self, unit_id: str) -> UnitSummary:
        """
        Get a lightweight unit projection, including the D/T/R invariant.

        Server: ``GET /api/v1/organization-units/{unit_id}/summary``. Read
        ``has_primary_role``: a department or team without a head role is
        structurally incomplete, not merely unpopulated.

        Args:
            unit_id: Unit ID

        Returns:
            UnitSummary

        Example:
            >>> s = await client.org_standup.get_unit_summary("unit-1")
            >>> if not s.has_primary_role:
            ...     print(f"{s.name} has no head role")
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-units/{encode_path_param(unit_id)}/summary"
        )
        return UnitSummary(**response)

    async def get_unit_children(self, unit_id: str) -> list[OrganizationUnit]:
        """
        Get a unit's immediate children.

        Server: ``GET /api/v1/organization-units/{unit_id}/children``.

        Args:
            unit_id: Unit ID

        Returns:
            The direct children, one level down

        Example:
            >>> kids = await client.org_standup.get_unit_children("unit-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-units/{encode_path_param(unit_id)}/children"
        )
        return [OrganizationUnit(**u) for u in response]

    async def get_unit_ancestors(self, unit_id: str) -> list[OrganizationUnit]:
        """
        Get a unit's ancestors, up the containment chain.

        Server: ``GET /api/v1/organization-units/{unit_id}/ancestors``.

        Args:
            unit_id: Unit ID

        Returns:
            The ancestor units

        Example:
            >>> chain = await client.org_standup.get_unit_ancestors("unit-9")
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-units/{encode_path_param(unit_id)}/ancestors"
        )
        return [OrganizationUnit(**u) for u in response]

    async def get_unit_descendants(self, unit_id: str) -> list[OrganizationUnit]:
        """
        Get every unit beneath this one, at any depth.

        Server: ``GET /api/v1/organization-units/{unit_id}/descendants``.

        Args:
            unit_id: Unit ID

        Returns:
            All descendant units

        Example:
            >>> all_below = await client.org_standup.get_unit_descendants("unit-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-units/{encode_path_param(unit_id)}/descendants"
        )
        return [OrganizationUnit(**u) for u in response]

    async def move_unit(
        self, unit_id: str, new_parent_id: str | None = None
    ) -> UnitMoveResult:
        """
        Move a unit to a new parent, with the full cascade.

        Server: ``POST /api/v1/organization-units/{unit_id}/move``.

        ⚠ This is not a small edit. Re-parenting recomputes posture ceilings
        across every descendant, revalidates knowledge-share policies,
        re-derives bridges, and revokes and recreates trust chains. Read the
        returned ``cascade`` rather than assuming only the parent changed.

        Args:
            unit_id: Unit to move
            new_parent_id: New parent's ID, or None to make the unit a root

        Returns:
            UnitMoveResult: the unit's post-move fields plus a cascade summary

        Example:
            >>> result = await client.org_standup.move_unit("unit-9", "unit-2")
            >>> print(result.cascade.trust_chains_revoked)
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/organization-units/{encode_path_param(unit_id)}/move",
            json_data={"new_parent_id": new_parent_id},
        )
        return UnitMoveResult(**response)

    async def get_posture_ceiling(self, unit_id: str) -> PostureCeiling:
        """
        Get a unit's CARE posture ceiling.

        Server: ``GET /api/v1/organization-units/{unit_id}/posture-ceiling``.
        Read ``effective_max_trust_posture``: ceilings cascade, so a child can
        never exceed its parent whatever its own value says.

        Args:
            unit_id: Unit ID

        Returns:
            PostureCeiling: declared, effective, parent, and allowed postures

        Example:
            >>> ceiling = await client.org_standup.get_posture_ceiling("unit-1")
            >>> print(ceiling.effective_max_trust_posture)
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-units/{encode_path_param(unit_id)}/posture-ceiling"
        )
        return PostureCeiling(**response)

    async def set_posture_ceiling(
        self, unit_id: str, max_trust_posture: str | None = _UNSET
    ) -> PostureCeiling:
        """
        Set or clear a unit's posture ceiling.

        Server: ``PUT /api/v1/organization-units/{unit_id}/posture-ceiling``.

        ⚠ OMITTING the argument and passing ``None`` are DIFFERENT operations,
        and the difference is a security control. Omit it and the ceiling is
        left UNCHANGED; pass ``None`` explicitly and the ceiling is CLEARED,
        which WIDENS what the unit may do. A plain ``None`` default would send
        ``null`` on every call and silently widen the ceiling of any unit whose
        setter was invoked for another reason — so this method sends the key
        only when you name it.

        Args:
            unit_id: Unit ID
            max_trust_posture: The new ceiling (lowercase CARE posture name),
                or an explicit None to CLEAR it. Omit to leave it unchanged.

        Returns:
            PostureCeiling: the updated ceiling values

        Example:
            >>> await client.org_standup.set_posture_ceiling("u1", "supervised")
            >>> await client.org_standup.set_posture_ceiling("u1", None)  # CLEARS
        """
        body: dict[str, Any] = {}
        if max_trust_posture is not _UNSET:
            body["maxTrustPosture"] = max_trust_posture
        response = await self._http.request(
            "PUT",
            f"/api/v1/organization-units/{encode_path_param(unit_id)}/posture-ceiling",
            json_data=body,
        )
        return PostureCeiling(**response)

    # -- role graph ----------------------------------------------------------

    async def get_roles_without_agents(
        self, auto_generate_only: bool = True
    ) -> list[OrganizationRole]:
        """
        Get roles with no delegate agent linked.

        Server: ``GET /api/v1/organization-roles/without-agents``. Useful for
        finding which roles still need agent generation.

        Args:
            auto_generate_only: Restrict to roles marked for auto-generation

        Returns:
            The roles with no linked agent

        Example:
            >>> roles = await client.org_standup.get_roles_without_agents()
        """
        response = await self._http.request(
            "GET",
            "/api/v1/organization-roles/without-agents",
            params={"auto_generate_only": auto_generate_only},
        )
        return [OrganizationRole(**r) for r in response]

    async def get_role_constraints(self, role_id: str) -> RoleConstraints:
        """
        Get a role's effective constraint envelope.

        Server: ``GET /api/v1/organization-roles/{role_id}/constraints``.

        Args:
            role_id: Role ID

        Returns:
            RoleConstraints: the effective spend, token and rate limits

        Example:
            >>> c = await client.org_standup.get_role_constraints("role-1")
            >>> print(c.max_cost_usd)
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-roles/{encode_path_param(role_id)}/constraints"
        )
        return RoleConstraints(**response)

    async def validate_role(self, role_id: str) -> RoleValidation:
        """
        Validate one role against the organizational grammar.

        Server: ``GET /api/v1/organization-roles/{role_id}/validate``.

        Args:
            role_id: Role ID

        Returns:
            RoleValidation: validity plus structured errors and warnings

        Example:
            >>> result = await client.org_standup.validate_role("role-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-roles/{encode_path_param(role_id)}/validate"
        )
        return RoleValidation(**response)

    async def unassign_user_from_role(self, role_id: str) -> OrganizationRole:
        """
        Remove the assigned user from a role, leaving it vacant.

        Server: ``POST /api/v1/organization-roles/{role_id}/unassign-user``.
        The counterpart of :meth:`assign_user_to_role`; takes no body, since
        the role identifies what is being vacated.

        Args:
            role_id: Role ID

        Returns:
            The role, now vacant

        Example:
            >>> role = await client.org_standup.unassign_user_from_role("role-1")
            >>> assert role.is_vacant
        """
        response = await self._http.request(
            "POST", f"/api/v1/organization-roles/{encode_path_param(role_id)}/unassign-user"
        )
        return OrganizationRole(**response)

    async def link_agent(self, role_id: str, agent_id: str) -> OrganizationRole:
        """
        Link a delegate agent to a role.

        Server: ``POST /api/v1/organization-roles/{role_id}/link-agent``. The
        role is the accountability anchor; the agent acts within the envelope
        the role already carries, so linking does not widen anything.

        Args:
            role_id: Role ID
            agent_id: Agent to link

        Returns:
            The role, with the agent linked

        Example:
            >>> await client.org_standup.link_agent("role-1", "agent-7")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/organization-roles/{encode_path_param(role_id)}/link-agent",
            json_data={"agent_id": agent_id},
        )
        return OrganizationRole(**response)

    async def unlink_agent(self, role_id: str) -> OrganizationRole:
        """
        Unlink the delegate agent from a role.

        Server: ``POST /api/v1/organization-roles/{role_id}/unlink-agent``.
        Takes no body — a role holds at most one delegate agent, so the role
        identifies which link is being removed.

        Args:
            role_id: Role ID

        Returns:
            The role, with no agent linked

        Example:
            >>> await client.org_standup.unlink_agent("role-1")
        """
        response = await self._http.request(
            "POST", f"/api/v1/organization-roles/{encode_path_param(role_id)}/unlink-agent"
        )
        return OrganizationRole(**response)

    async def get_direct_reports(self, role_id: str) -> list[OrganizationRole]:
        """
        Get the roles reporting directly to this one.

        Server: ``GET /api/v1/organization-roles/{role_id}/direct-reports``.

        Args:
            role_id: Role ID

        Returns:
            The direct reports, one level down

        Example:
            >>> reports = await client.org_standup.get_direct_reports("role-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-roles/{encode_path_param(role_id)}/direct-reports"
        )
        return [OrganizationRole(**r) for r in response]

    async def get_reporting_chain(self, role_id: str) -> list[OrganizationRole]:
        """
        Get the reporting chain from this role up to the top.

        Server: ``GET /api/v1/organization-roles/{role_id}/reporting-chain``.
        Reporting is the axis trust delegation follows, so this is the chain
        an escalation would travel.

        Args:
            role_id: Role ID

        Returns:
            The chain of roles above this one

        Example:
            >>> chain = await client.org_standup.get_reporting_chain("role-9")
            >>> print(" -> ".join(r.title for r in chain))
        """
        response = await self._http.request(
            "GET", f"/api/v1/organization-roles/{encode_path_param(role_id)}/reporting-chain"
        )
        return [OrganizationRole(**r) for r in response]
