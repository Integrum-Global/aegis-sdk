"""
Applications Module for Agentic OS SDK.

Thin HTTP-wrapper for the Applications governance surface -- the P0 core
admin-governance object of the admin-settings domain. Applications hold
authority to invoke shared tool agents within platform bounds; they do NOT
own tool agents.

Self-contained module: request/response models are
defined LOCALLY in this file. Do not import from ``aegis_sdk.types`` or
edit ``modules/__init__.py`` / ``client.py`` -- a separate orchestrator
wiring pass registers this module on the client.

Backend routes, cited per-method below. The server mounts this surface under
``/api/v1/applications``, so every path below is ``/api/v1/applications/...``.

20 methods (of the router's 23 routes -- the 3 skipped are FE-compat
aliases ``/{app_id}/agents/{agent_id}/policy`` that byte-for-byte mirror
the canonical ``/{app_id}/policy/{agent_id}`` this module already covers,):

  CRUD:
    - list()              GET    /api/v1/applications
    - create()             POST   /api/v1/applications
    - get()                GET    /api/v1/applications/{app_id}
    - get_summary()        GET    /api/v1/applications/{app_id}/summary
    - update()             PUT    /api/v1/applications/{app_id}
    - archive()            DELETE /api/v1/applications/{app_id}
    - change_status()      PATCH  /api/v1/applications/{app_id}/status
  Grants:
    - list_grants()        GET    /api/v1/applications/{app_id}/grants
    - grant_tool_agent()   POST   /api/v1/applications/{app_id}/grants
    - revoke_grant()       DELETE /api/v1/applications/{app_id}/grants/{grant_id}
  Invocation policy:
    - get_policy()         GET    /api/v1/applications/{app_id}/policy/{agent_id}
    - update_policy()      PUT    /api/v1/applications/{app_id}/policy/{agent_id}
  Delegation matrix:
    - get_delegation_matrix()    GET /api/v1/applications/{app_id}/delegation-matrix
    - update_delegation_matrix() PUT /api/v1/applications/{app_id}/delegation-matrix
  Operators:
    - list_operators()     GET    /api/v1/applications/{app_id}/operators
    - add_operator()       POST   /api/v1/applications/{app_id}/operators
    - remove_operator()    DELETE /api/v1/applications/{app_id}/operators/{user_id}
  Read-only surfaces:
    - list_notifications() GET /api/v1/applications/{app_id}/notifications
    - list_invocations()   GET /api/v1/applications/{app_id}/invocations
    - list_audit_events()  GET /api/v1/applications/{app_id}/audit-events
    - get_freeze_status()  GET /api/v1/applications/{app_id}/freeze-status
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

PostureCeiling = Literal[
    "pseudo", "supervised", "shared_planning", "continuous_insight", "delegated"
]
DelegationPermissionLevel = Literal["edit", "toggle", "view", "locked"]
OperatorRole = Literal["app_admin", "app_operator"]
ApplicationStatusTarget = Literal["active", "suspended", "archived", "rejected"]


# ---------------------------------------------------------------------------
# Response models -- Application (verified; the
# backend model has NO Pydantic alias generator, so JSON keys are the same
# snake_case as the field names below -- ).
# ---------------------------------------------------------------------------


class Application(TolerantModel):
    """Application record (response shape)."""

    id: str
    organization_id: str
    name: str
    description: str = ""
    owner_role_id: str
    status: str
    default_posture_ceiling: str
    budget_monthly: str
    budget_consumed: str = "0.00"
    data_scope_json: str = "[]"
    allowed_models_json: str = "[]"
    content_freeze_enabled: bool = False
    content_freeze_start: str | None = None
    content_freeze_end: str | None = None
    content_freeze_staleness_days: int = 7
    feature_flags_json: str = "{}"
    scheduling_context_json: str = "{}"
    public_config_json: str = "{}"
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    owner_role_name: str | None = None
    tool_agent_count: int = 0
    operator_count: int = 0


class ApplicationListResult(TolerantModel):
    """Paginated application-list envelope."""

    records: list[Application] = Field(default_factory=list)
    total: int = 0


class ApplicationSummary(TolerantModel):
    """Lightweight application summary DTO (verified)."""

    id: str
    name: str
    status: str
    organization_id: str
    created_at: str
    agent_count: int | None = None


class FreezeStatus(TolerantModel):
    """Content freeze state (response shape)."""

    is_frozen: bool
    reason: str
    freeze_start: str | None = None
    freeze_end: str | None = None
    staleness_days: int = 7
    warning: str | None = None


# ---------------------------------------------------------------------------
# Response models -- Grants (verified
# ``CreateApplicationToolAgentGrant`` payload / enriched list records; the
# route declares no ``response_model``, so this pins the real service shape).
# ---------------------------------------------------------------------------


class ToolAgentGrant(TolerantModel):
    """Application-to-tool-agent grant record."""

    id: str
    application_id: str = ""
    agent_id: str = ""
    agent_name: str | None = None
    posture_ceiling: str = "pseudo"
    budget_allocation: str = "0.00"
    constraint_summary_json: str = "{}"
    rationale: str = ""
    status: str = "active"
    granted_by: str = ""
    granted_at: str = ""
    revoked_at: str | None = None


class GrantListResult(TolerantModel):
    """Envelope for GET /{app_id}/grants."""

    records: list[ToolAgentGrant] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Response models -- Invocation policy (verified
# ---------------------------------------------------------------------------


class InvocationPolicy(TolerantModel):
    """Per-application-agent invocation policy."""

    id: str
    organization_id: str | None = None
    application_id: str = ""
    agent_id: str = ""
    posture_ceiling: str = "pseudo"
    budget_per_invocation: str = "0.00"
    data_scope_json: str = "[]"
    allowed_models_json: str = "[]"
    prompt_prefix: str = ""
    knowledge_attachment_ids_json: str = "[]"
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Response models -- Delegation matrix (verified
# ---------------------------------------------------------------------------


class DelegationMatrixEntry(TolerantModel):
    """A single parameter x permission delegation-matrix entry."""

    id: str
    organization_id: str | None = None
    application_id: str = ""
    agent_id: str | None = None
    operator_id: str | None = None
    parameter_name: str
    permission_level: str
    rationale: str = ""
    created_at: str = ""
    updated_at: str = ""


class DelegationMatrixResult(TolerantModel):
    """Envelope for GET/PUT .../delegation-matrix."""

    records: list[DelegationMatrixEntry] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Response models -- Operators (verified
# -- CreateApplicationOperator)
# ---------------------------------------------------------------------------


class ApplicationOperator(TolerantModel):
    """Operator (user) assigned to an application."""

    id: str
    application_id: str = ""
    user_id: str = ""
    role: str = "app_operator"
    created_at: str = ""


class OperatorListResult(TolerantModel):
    """Envelope for GET /{app_id}/operators."""

    records: list[ApplicationOperator] = Field(default_factory=list)
    total: int = 0


class NotificationListResult(TolerantModel):
    """Envelope for GET /{app_id}/notifications.

    Individual notification shape (``ConstraintChangeNotification``) is not
    pinned by a backend ``response_model`` -- represented as loose dicts.
    """

    records: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class InvocationListResult(TolerantModel):
    """Envelope for GET /{app_id}/invocations (verified --
    ``{"records": [...], "total": n}``).
    """

    records: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ApplicationsModule:
    """
    Applications module -- the governance boundary for tool agent
    invocation. Applications hold authority to invoke shared tool agents
    within platform-defined constraint envelopes.

    Examples:
        # Create an application and grant it a tool agent
        >>> app = await client.applications.create(
        ...     name="Support Bot", owner_role_id="role-1"
        ... )
        >>> grant = await client.applications.grant_tool_agent(
        ...     app.id, agent_id="agent-1", posture_ceiling="supervised",
        ...     rationale="Customer support triage",
        ... )
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize applications module.

        Args:
            http_client: HTTPClient instance for API requests.
        """
        self._http = http_client

    # -------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------

    async def list(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ApplicationListResult:
        """List applications (GET /applications).

        Org admins see all applications; scoped roles (app_operator,
        app_admin, developer, viewer) see only applications they are
        explicitly assigned to as operators (server-side filtering).

        Args:
            status: Filter by status. When omitted, archived/deleted/
                rejected applications are excluded from the default view.
            limit: Max results (1-200).
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            "/api/v1/applications",
            params=params,
        )
        return ApplicationListResult(**response)

    async def create(
        self,
        name: str,
        owner_role_id: str,
        description: str = "",
        default_posture_ceiling: PostureCeiling = "pseudo",
        budget_monthly: str = "0.00",
        data_scope_json: str = "[]",
        allowed_models_json: str = "[]",
    ) -> Application:
        """Create a new application in pending_approval status
        (POST /applications)."""
        data: dict[str, Any] = {
            "name": name,
            "owner_role_id": owner_role_id,
            "description": description,
            "default_posture_ceiling": default_posture_ceiling,
            "budget_monthly": budget_monthly,
            "data_scope_json": data_scope_json,
            "allowed_models_json": allowed_models_json,
        }
        response = await self._http.request(
            "POST",
            "/api/v1/applications",
            json_data=data,
        )
        return Application(**response)

    async def get(self, app_id: str) -> Application:
        """Get an application by ID (GET
        /applications/{app_id})."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}",
        )
        return Application(**response)

    async def get_summary(self, app_id: str) -> ApplicationSummary:
        """Get a lightweight application summary DTO (GET /applications/{app_id}/summary)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/summary",
        )
        return ApplicationSummary(**response)

    async def update(
        self,
        app_id: str,
        name: str | None = None,
        description: str | None = None,
        default_posture_ceiling: PostureCeiling | None = None,
        budget_monthly: str | None = None,
        data_scope_json: str | None = None,
        allowed_models_json: str | None = None,
        content_freeze_enabled: bool | None = None,
        content_freeze_start: str | None = None,
        content_freeze_end: str | None = None,
        content_freeze_staleness_days: int | None = None,
        feature_flags_json: str | None = None,
        scheduling_context_json: str | None = None,
        public_config_json: str | None = None,
    ) -> Application:
        """Update an application (PUT
        /applications/{app_id}).

        M10-T06: if the application has an active content freeze and this
        update modifies freeze-related fields, the server may return 403
        (HELD zone -- requires ``applications:admin`` authority).
        """
        data: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("description", description),
            ("default_posture_ceiling", default_posture_ceiling),
            ("budget_monthly", budget_monthly),
            ("data_scope_json", data_scope_json),
            ("allowed_models_json", allowed_models_json),
            ("content_freeze_enabled", content_freeze_enabled),
            ("content_freeze_start", content_freeze_start),
            ("content_freeze_end", content_freeze_end),
            ("content_freeze_staleness_days", content_freeze_staleness_days),
            ("feature_flags_json", feature_flags_json),
            ("scheduling_context_json", scheduling_context_json),
            ("public_config_json", public_config_json),
        ):
            if value is not None:
                data[key] = value

        response = await self._http.request(
            "PUT",
            f"/api/v1/applications/{encode_path_param(app_id)}",
            json_data=data,
        )
        return Application(**response)

    async def archive(self, app_id: str) -> Application:
        """Archive an application with cascade (DELETE /applications/{app_id}).

        Cascade: revokes all active grants, invalidates all active
        invocation policies, then transitions status to 'archived'. Org
        admins only. Returns the archived application record (NOT 204).
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/applications/{encode_path_param(app_id)}",
        )
        return Application(**response)

    async def change_status(
        self,
        app_id: str,
        new_status: ApplicationStatusTarget,
    ) -> Application:
        """Change an application's lifecycle status (PATCH /applications/{app_id}/status). Enforces state-machine
        transitions server-side."""
        response = await self._http.request(
            "PATCH",
            f"/api/v1/applications/{encode_path_param(app_id)}/status",
            json_data={"status": new_status},
        )
        return Application(**response)

    # -------------------------------------------------------------------
    # Grants
    # -------------------------------------------------------------------

    async def list_grants(self, app_id: str) -> GrantListResult:
        """List tool agent grants for an application (GET /{app_id}/grants)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/grants",
        )
        return GrantListResult(**response)

    async def grant_tool_agent(
        self,
        app_id: str,
        agent_id: str,
        posture_ceiling: PostureCeiling,
        rationale: str,
        budget_allocation: str = "0.00",
        constraint_summary_json: str = "{}",
    ) -> ToolAgentGrant:
        """Grant an application authority to invoke a tool agent
        (POST /{app_id}/grants).

        ``rationale`` is mandatory (CARE constraint-rationale requirement)
        and ``posture_ceiling`` cannot exceed the application's own
        ``default_posture_ceiling`` (server-enforced).
        """
        data: dict[str, Any] = {
            "agent_id": agent_id,
            "posture_ceiling": posture_ceiling,
            "budget_allocation": budget_allocation,
            "constraint_summary_json": constraint_summary_json,
            "rationale": rationale,
        }
        response = await self._http.request(
            "POST",
            f"/api/v1/applications/{encode_path_param(app_id)}/grants",
            json_data=data,
        )
        return ToolAgentGrant(**response)

    async def revoke_grant(self, app_id: str, grant_id: str) -> bool:
        """Revoke a tool-agent grant (DELETE
        /{app_id}/grants/{grant_id}, returns 204)."""
        await self._http.request(
            "DELETE",
            f"/api/v1/applications/{encode_path_param(app_id)}/grants/{encode_path_param(grant_id)}",
        )
        return True

    # -------------------------------------------------------------------
    # Invocation policy
    # -------------------------------------------------------------------

    async def get_policy(self, app_id: str, agent_id: str) -> InvocationPolicy:
        """Get the invocation policy for an application+agent pair
        (GET /{app_id}/policy/{agent_id})."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/policy/{encode_path_param(agent_id)}",
        )
        return InvocationPolicy(**response)

    async def update_policy(
        self,
        app_id: str,
        agent_id: str,
        posture_ceiling: PostureCeiling | None = None,
        budget_per_invocation: str | None = None,
        data_scope_json: str | None = None,
        allowed_models_json: str | None = None,
        prompt_prefix: str | None = None,
        knowledge_attachment_ids_json: str | None = None,
    ) -> InvocationPolicy:
        """Update an invocation policy (PUT
        /{app_id}/policy/{agent_id}).

        Each parameter update is gated through the delegation matrix
        server-side -- parameters with 'locked' or 'view' permission
        cannot be updated and the server returns 403.
        """
        data: dict[str, Any] = {}
        for key, value in (
            ("posture_ceiling", posture_ceiling),
            ("budget_per_invocation", budget_per_invocation),
            ("data_scope_json", data_scope_json),
            ("allowed_models_json", allowed_models_json),
            ("prompt_prefix", prompt_prefix),
            ("knowledge_attachment_ids_json", knowledge_attachment_ids_json),
        ):
            if value is not None:
                data[key] = value

        response = await self._http.request(
            "PUT",
            f"/api/v1/applications/{encode_path_param(app_id)}/policy/{encode_path_param(agent_id)}",
            json_data=data,
        )
        return InvocationPolicy(**response)

    # -------------------------------------------------------------------
    # Delegation matrix
    # -------------------------------------------------------------------

    async def get_delegation_matrix(self, app_id: str) -> DelegationMatrixResult:
        """Get the delegation matrix (parameter permissions) for an
        application (GET /{app_id}/delegation-matrix)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/delegation-matrix",
        )
        return DelegationMatrixResult(**response)

    async def update_delegation_matrix(
        self,
        app_id: str,
        entries: list[dict[str, Any]],
    ) -> DelegationMatrixResult:
        """Bulk-set the delegation matrix for an application
        (PUT /{app_id}/delegation-matrix).

        Requires ``applications:admin`` permission server-side. Each entry
        MUST have ``parameter_name``, ``permission_level`` (one of edit,
        toggle, view, locked), and ``rationale``. Capped at 50 entries.

        Args:
            app_id: Application ID.
            entries: List of
                {parameter_name, permission_level, rationale} dicts.
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/applications/{encode_path_param(app_id)}/delegation-matrix",
            json_data={"entries": entries},
        )
        return DelegationMatrixResult(**response)

    # -------------------------------------------------------------------
    # Operators
    # -------------------------------------------------------------------

    async def list_operators(self, app_id: str) -> OperatorListResult:
        """List operators assigned to an application (GET /{app_id}/operators)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/operators",
        )
        return OperatorListResult(**response)

    async def add_operator(
        self,
        app_id: str,
        user_id: str,
        role: OperatorRole,
    ) -> ApplicationOperator:
        """Add a user as an operator on an application (POST /{app_id}/operators). Requires ``applications:admin``."""
        response = await self._http.request(
            "POST",
            f"/api/v1/applications/{encode_path_param(app_id)}/operators",
            json_data={"user_id": user_id, "role": role},
        )
        return ApplicationOperator(**response)

    async def remove_operator(self, app_id: str, user_id: str) -> bool:
        """Remove a user's operator assignment (DELETE /{app_id}/operators/{user_id}, returns 204). Requires
        ``applications:admin``."""
        await self._http.request(
            "DELETE",
            f"/api/v1/applications/{encode_path_param(app_id)}/operators/{encode_path_param(user_id)}",
        )
        return True

    # -------------------------------------------------------------------
    # Read-only surfaces
    # -------------------------------------------------------------------

    async def list_notifications(self, app_id: str) -> NotificationListResult:
        """List pending constraint-change notifications for the caller on
        this application (GET
        /{app_id}/notifications). Only notifications within the 24h grace
        period are returned."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/notifications",
        )
        return NotificationListResult(**response)

    async def list_invocations(
        self,
        app_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> InvocationListResult:
        """List tool-agent invocation history for an application
        (GET /{app_id}/invocations)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/invocations",
            params={"limit": limit, "offset": offset},
        )
        return InvocationListResult(**response)

    async def list_audit_events(
        self,
        app_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List audit events for an application, aggregating direct
        application events with events on every granted tool agent
        (GET /{app_id}/audit-events). Returns a
        flat list (NOT enveloped -- matches the real backend response
        shape) sorted newest-first, capped by ``limit``."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/audit-events",
            params={"limit": limit},
        )
        return response if isinstance(response, list) else []

    async def get_freeze_status(self, app_id: str) -> FreezeStatus:
        """Get the current content-freeze state for an application
        (GET /{app_id}/freeze-status)."""
        response = await self._http.request(
            "GET",
            f"/api/v1/applications/{encode_path_param(app_id)}/freeze-status",
        )
        return FreezeStatus(**response)
