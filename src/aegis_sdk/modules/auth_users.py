"""
Auth-Users Module for Agentic OS SDK.

Adds the auth-users domain surface the existing ``AuthModule``
(``src/aegis_sdk/auth/client.py``) does not cover: user CRUD, the
auth-context endpoints (permissions / multi-org / email verification),
invitations, enterprise SSO connections, self-serve trial onboarding,
and the admin access-visualization surface.

Self-contained module: local Pydantic models, no
shared imports from client.py / modules/__init__.py / types.py.

Deliberately NOT duplicated here (per the fill-manifest annotation):
``AuthModule`` already exposes ``create_api_key`` / ``list_api_keys`` /
``get_api_key`` / ``delete_api_key`` / ``revoke_api_key`` — those method
names exist on the SDK surface today (``src/aegis_sdk/auth/client.py``),
so this module does not re-implement them. This module DOES add
``api_keys_regenerate`` (truly missing from ``AuthModule`` — no
``regenerate`` method exists there today).

Every route below is verified against the deployed API, mounted
at ``settings.api_prefix`` = ``/api/v1``:

    GET    /api/v1/users                        -> users_list()
    POST   /api/v1/users                         -> users_create()
    GET    /api/v1/users/me                      -> users_me()
    GET    /api/v1/users/{user_id}               -> users_get()
    PUT    /api/v1/users/{user_id}               -> users_update()
    DELETE /api/v1/users/{user_id}                -> users_delete()
    POST   /api/v1/users/{user_id}/reset-password -> users_reset_password()
    POST   /api/v1/api-keys/{key_id}/regenerate   -> api_keys_regenerate()
    GET    /api/v1/auth/permissions               -> auth_permissions()
    GET    /api/v1/auth/me/organizations          -> auth_organizations()
    POST   /api/v1/auth/me/switch-org             -> auth_switch_org()
    GET    /api/v1/auth/verify-email/{token}      -> auth_verify_email()
    GET    /api/v1/invitations                    -> invitations_list()
    POST   /api/v1/invitations                    -> invitations_create()
    POST   /api/v1/invitations/{token}/accept     -> invitations_accept()
    GET    /api/v1/sso/connections                -> sso_connections_list()
    POST   /api/v1/sso/connections                -> sso_connections_create()
    POST   /api/v1/onboarding/start-trial         -> onboarding_start_trial()
    GET    /api/v1/admin/access/tree              -> admin_access_tree()
    GET    /api/v1/admin/access/matrix            -> admin_access_matrix()
    GET    /api/v1/admin/access/audit             -> admin_access_audit()

Route + response-shape verification sources (all checked against the deployed API, not inferred):

    (users_* — router prefix "/users")
    (api_keys_regenerate — router prefix "/api-keys")
    (auth_* — router prefix "/auth")
    (invitations_* — router prefix "/invitations")
    (sso_connections_* — router prefix "/sso")
    (onboarding_start_trial — router prefix "/onboarding")
    (admin_access_* — router prefix "/admin/access",
                                        response_model_by_alias=True -> wire shape is
                                        camelCase; models below mirror that exactly)
"""

# NOTE: deferred annotation evaluation is required for the self-referential
# ``AccessTreeNode.children: list[AccessTreeNode]`` field (mirrors the pattern
# already used in tool_agents.py for the `list` shadowing hazard).
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


# ---------------------------------------------------------------------------
# Users (users.py)
# ---------------------------------------------------------------------------


class UserRecord(BaseModel):
    """User record (``UserResponse``, snake_case)."""

    id: str
    organization_id: str
    email: str
    name: str
    status: str
    role: str
    mfa_enabled: bool
    personas: list[str] = Field(default_factory=list)
    last_login_at: str | None = None
    created_at: str
    updated_at: str


class UserList(BaseModel):
    """``{records, total}`` envelope (``UserListResponse``)."""

    records: list[UserRecord]
    total: int


class MessageResult(BaseModel):
    """Simple ``{"message": ...}`` envelope shared by several endpoints."""

    message: str


# ---------------------------------------------------------------------------
# API keys — regenerate only (create/list/get/delete already on AuthModule)
# ---------------------------------------------------------------------------


class APIKeyRegenerated(BaseModel):
    """Result of rotating an API key's secret (``CreateAPIKeyResponse``). The full key is shown ONLY in this response —
    it cannot be retrieved again. Callers MUST NOT log ``key``."""

    id: str
    organization_id: str
    name: str
    key_prefix: str
    key: str = Field(repr=False)  # full secret shown once -- hidden from repr/str (H1)
    scopes: list[str]
    rate_limit: int
    expires_at: str | None = None
    status: str
    created_at: str


# ---------------------------------------------------------------------------
# Auth context (auth.py)
# ---------------------------------------------------------------------------


class PermissionsResult(BaseModel):
    """``PermissionsResponse``."""

    permissions: list[str]


class OrganizationMembership(BaseModel):
    """``OrganizationMembership``."""

    id: str
    name: str
    slug: str
    role: str
    is_primary: bool
    joined_at: str
    joined_via: str


class OrganizationsResult(BaseModel):
    """``OrganizationsResponse``."""

    organizations: list[OrganizationMembership]


class SwitchOrgResult(BaseModel):
    """``SwitchOrganizationResponse``."""

    access_token: str = Field(repr=False)  # bearer credential -- hidden from repr/str (H1)
    refresh_token: str = Field(repr=False)  # bearer credential -- hidden from repr/str (H1)
    token_type: str = "bearer"
    expires_in: int
    active_organization: OrganizationMembership


class VerifyEmailResult(BaseModel):
    """``VerifyEmailResponse``."""

    message: str
    email_verified: bool = True


# ---------------------------------------------------------------------------
# Invitations (invitations.py)
# ---------------------------------------------------------------------------


class InvitationRecord(BaseModel):
    """``InvitationResponse``."""

    id: str
    organization_id: str
    email: str
    role: str
    invited_by: str
    status: str
    expires_at: str
    created_at: str


class InvitationWithToken(BaseModel):
    """``InvitationWithTokenResponse`` — the token is
    shown ONLY on create; callers MUST NOT log ``token``."""

    id: str
    organization_id: str
    email: str
    role: str
    invited_by: str
    token: str = Field(repr=False)  # one-time invite token -- hidden from repr/str (H1)
    status: str
    expires_at: str
    created_at: str


class InvitationList(BaseModel):
    """``InvitationListResponse``."""

    records: list[InvitationRecord]
    total: int


class AcceptInvitationResult(BaseModel):
    """``AcceptInvitationResponse``."""

    message: str
    user_id: str
    organization_id: str
    access_token: str | None = Field(default=None, repr=False)  # bearer credential -- hidden (H1)
    refresh_token: str | None = Field(default=None, repr=False)  # bearer credential -- hidden (H1)
    trust_chain_status: str = "active"


# ---------------------------------------------------------------------------
# SSO connections (sso.py)
# ---------------------------------------------------------------------------


class SSOConnection(BaseModel):
    """SSO connection record — shape verified against
    ``SSOService.create_connection``/``get_org_connections``
    (582-589). The encrypted
    secret is stripped server-side before the response is built; this
    model never carries ``client_secret``."""

    id: str
    organization_id: str
    provider: str
    client_id: str
    tenant_id: str | None = None
    domain: str | None = None
    is_default: bool
    auto_provision: bool
    default_role: str
    allowed_domains: str | None = None
    status: str
    created_at: str
    updated_at: str


class SSOConnectionList(BaseModel):
    """``{"connections": [...]}`` envelope."""

    connections: list[SSOConnection] = Field(default_factory=list)


class SSOProviders(BaseModel):
    """Which built-in login-page SSO providers are configured.

    Per-provider booleans only — derived server-side from whether the env
    credentials are present. No secret is exposed by this shape.
    """

    providers: dict[str, bool] = Field(default_factory=dict)


class SSOInitiation(BaseModel):
    """An OIDC authorization URL plus the CSRF ``state`` bound to it.

    ``state`` is single-use and stored server-side with a TTL; the callback
    refuses a state it did not issue. Send the user to ``auth_url`` — do not
    fetch it programmatically.
    """

    auth_url: str
    state: str


class SAMLInitiation(BaseModel):
    """A SAML AuthnRequest URL plus its single-use ``relay_state``.

    ``relay_state`` is the SAML CSRF / flow-replay token. The ACS validates the
    round-tripped value before accepting any assertion, so an ACS POST with no
    prior initiate carries no valid RelayState and is rejected.
    """

    auth_url: str
    relay_state: str


class SSODeleteResult(BaseModel):
    """``{"status": "deleted"}`` — the delete-connection acknowledgement."""

    status: str


# ---------------------------------------------------------------------------
# Onboarding (onboarding.py)
# ---------------------------------------------------------------------------


class StartTrialResult(BaseModel):
    """``StartTrialResponse`` — pinned wire shape
    per an automated envelope-shape check on the platform side."""

    organization_id: str
    slug: str
    plan_tier: str
    trial_expires_at: str
    operator_role_id: str | None = None
    agents_generated: int
    constraint_envelopes_generated: int
    export_clean: bool


# ---------------------------------------------------------------------------
# Admin access visualization (admin_access.py) — camelCase wire shape
# (response_model_by_alias=True on the backend; mirrored exactly here)
# ---------------------------------------------------------------------------

AccessType = Literal["direct", "inherited", "none"]
PermissionLevel = Literal["full", "limited", "read_only"]


class AccessAgent(BaseModel):
    """``AccessAgent``."""

    id: str
    name: str
    access_type: AccessType = Field(..., alias="accessType")
    permission_level: PermissionLevel = Field(..., alias="permissionLevel")

    model_config = ConfigDict(populate_by_name=True)


class AccessTreeNode(BaseModel):
    """``AccessTreeNode`` — recursive role tree."""

    id: str
    role_id: str = Field(..., alias="roleId")
    role_name: str = Field(..., alias="roleName")
    role_description: str | None = Field(None, alias="roleDescription")
    access_type: AccessType = Field(..., alias="accessType")
    agents: list[AccessAgent] = Field(default_factory=list)
    user_count: int = Field(0, alias="userCount")
    children: list[AccessTreeNode] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


AccessTreeNode.model_rebuild()


class AccessTreeResult(BaseModel):
    """``AccessTreeResponse``."""

    roots: list[AccessTreeNode] = Field(default_factory=list)


class AccessMatrixCell(BaseModel):
    """``AccessMatrixCell``."""

    role_id: str = Field(..., alias="roleId")
    agent_id: str = Field(..., alias="agentId")
    access_type: AccessType = Field(..., alias="accessType")
    permission_level: PermissionLevel | None = Field(None, alias="permissionLevel")

    model_config = ConfigDict(populate_by_name=True)


class AccessMatrixRow(BaseModel):
    """``AccessMatrixRow``."""

    role_id: str = Field(..., alias="roleId")
    role_name: str = Field(..., alias="roleName")
    cells: list[AccessMatrixCell] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class AccessMatrixAgent(BaseModel):
    """``AccessMatrixAgent``."""

    id: str
    name: str


class AccessMatrixResult(BaseModel):
    """``AccessMatrixResponse``."""

    roles: list[AccessMatrixRow] = Field(default_factory=list)
    agents: list[AccessMatrixAgent] = Field(default_factory=list)


class AccessAuditEntry(BaseModel):
    """``AccessAuditEntry``."""

    id: str
    action: Literal["grant", "revoke", "modify"]
    target_type: Literal["agent", "role", "user"] = Field(..., alias="targetType")
    target_id: str = Field(..., alias="targetId")
    target_name: str = Field(..., alias="targetName")
    role_id: str | None = Field(None, alias="roleId")
    role_name: str | None = Field(None, alias="roleName")
    performed_by: str = Field(..., alias="performedBy")
    performed_by_name: str = Field(..., alias="performedByName")
    details: str | None = None
    timestamp: str

    model_config = ConfigDict(populate_by_name=True)


class AccessAuditResult(BaseModel):
    """``AccessAuditResponse``."""

    records: list[AccessAuditEntry] = Field(default_factory=list)
    total: int = 0


class AuthUsersModule:
    """
    Auth-users domain module: user CRUD, auth-context, invitations, SSO
    connections, self-serve trial onboarding, and admin access visualization.

    Example:
        >>> users = await client.auth_users.users_list()
        >>> key = await client.auth_users.api_keys_regenerate("key_123")
        >>> store_in_secret_manager(key.key)   # returned ONCE; never recoverable
        >>> print(f"Rotated {key.key_prefix}... at {key.created_at}")

    ⛔ ``key.key`` is the full secret. Do not print, log, or serialize it.
    It is masked in ``repr()`` but NOT in ``model_dump()`` /
    ``model_dump_json()``, so a structured log line carrying the dumped
    model emits the credential in cleartext. Log ``key.key_prefix``.
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    # -- Users ----------------------------------------------------------

    async def users_list(
        self,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> UserList:
        """
        List users in the current user's organization.

        Args:
            search: Filter by name or email substring
            status: Filter by status ("active"/"suspended")
            role: Filter by role
            limit: Maximum results (1-100)
            offset: Pagination offset

        Returns:
            UserList: records + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        if role:
            params["role"] = role

        response = await self._http.request("GET", "/api/v1/users", params=params)
        return UserList(**response)

    async def users_create(
        self,
        email: str,
        name: str,
        password: str,
        role: str,
    ) -> UserRecord:
        """
        Create a new user in the organization (admin-class roles only).

        Args:
            email: User email address
            name: User's display name
            password: Must meet the server's password strength policy
            role: One of "org_admin", "developer", "viewer"

        Returns:
            UserRecord: The created user
        """
        response = await self._http.request(
            "POST",
            "/api/v1/users",
            json_data={"email": email, "name": name, "password": password, "role": role},
        )
        return UserRecord(**response)

    async def users_me(self) -> UserRecord:
        """
        Get the current authenticated user's profile (users-service shape,
        distinct from the auth-session ``/auth/me`` on ``AuthModule``).

        Returns:
            UserRecord: The current user's profile
        """
        response = await self._http.request("GET", "/api/v1/users/me")
        return UserRecord(**response)

    async def users_get(self, user_id: str) -> UserRecord:
        """
        Get a user by ID (same organization only).

        Args:
            user_id: User ID

        Returns:
            UserRecord
        """
        response = await self._http.request("GET", f"/api/v1/users/{encode_path_param(user_id)}")
        return UserRecord(**response)

    async def users_update(self, user_id: str, **fields: Any) -> UserRecord:
        """
        Update a user.

        Args:
            user_id: User ID
            **fields: Any of name, email, role, status, mfa_enabled, personas

        Returns:
            UserRecord: The updated user
        """
        response = await self._http.request(
            "PUT", f"/api/v1/users/{encode_path_param(user_id)}", json_data=fields
        )
        return UserRecord(**response)

    async def users_delete(self, user_id: str) -> MessageResult:
        """
        Delete (soft-delete) a user. Only admin-class roles; users cannot
        delete themselves; the org owner cannot be deleted.

        Args:
            user_id: User ID

        Returns:
            MessageResult
        """
        response = await self._http.request("DELETE", f"/api/v1/users/{encode_path_param(user_id)}")
        return MessageResult(**response)

    async def users_reset_password(self, user_id: str, new_password: str) -> MessageResult:
        """
        Reset a user's password. Admins can reset anyone's; users can reset
        their own.

        Args:
            user_id: User ID
            new_password: Must meet the unified password strength policy

        Returns:
            MessageResult
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/users/{encode_path_param(user_id)}/reset-password",
            json_data={"new_password": new_password},
        )
        return MessageResult(**response)

    # -- API keys (regenerate only — create/list/get/delete on AuthModule) --

    async def api_keys_regenerate(self, key_id: str) -> APIKeyRegenerated:
        """
        Rotate an API key's secret. The previous secret is invalidated
        immediately; the new full key is returned ONLY in this response
        and cannot be retrieved later. ``id``, ``name``, ``scopes``,
        ``rate_limit``, ``organization_id`` and ``expires_at`` survive the
        rotation; ``last_used_at`` is cleared, since the prior secret no
        longer works.

        ⛔ OWNERSHIP IS NOT AMONG THE PRESERVED FIELDS. ``created_by``
        is RE-ANCHORED by the server to the rotating caller. That column is the
        principal the key's continued validity is BOUND to -- not a record
        of who first created it -- because the server's ``validate`` denies
        on ``owner_inactive`` / ``owner_not_member_of_key_org`` against THAT
        id. So after you rotate a key, it answers for YOU: it stops
        authenticating when your access ends, not the original creator's.
        Re-anchoring is unconditional; rotating your own key rewrites the
        same value.

        The original creator is NOT retained by the row -- there is one
        column and it now holds the current bound principal. A caller that
        needs provenance reads the audit log, never this response.

        ⛔ ROTATION ALSO REACTIVATES A REVOKED KEY. It is the only
        un-revoke path in the product and is retained by decision, so a
        successful rotation always returns a key with status ``active``,
        even when the stored row was ``revoked``. Whether revocation
        should instead be terminal is an open question and may change in a
        future release, so treat this behaviour as current-version; do not rely on
        revocation alone to retire a credential that anyone with mint
        authority over its scopes can still rotate.

        Args:
            key_id: API key ID

        Returns:
            APIKeyRegenerated: includes the new full key (shown once —
                callers MUST NOT log ``.key``)
        """
        response = await self._http.request(
            "POST", f"/api/v1/api-keys/{encode_path_param(key_id)}/regenerate"
        )
        return APIKeyRegenerated(**response)

    # -- Auth context -----------------------------------------------------

    async def auth_permissions(self) -> PermissionsResult:
        """
        Get the current user's permission list (drives UI gating).

        Returns:
            PermissionsResult
        """
        response = await self._http.request("GET", "/api/v1/auth/permissions")
        return PermissionsResult(**response)

    async def auth_organizations(self) -> OrganizationsResult:
        """
        List the organizations the current user belongs to (org switcher).

        Returns:
            OrganizationsResult
        """
        response = await self._http.request("GET", "/api/v1/auth/me/organizations")
        return OrganizationsResult(**response)

    async def auth_switch_org(self, organization_id: str) -> SwitchOrgResult:
        """
        Switch the active organization; re-issues tokens with new org context.

        Args:
            organization_id: Organization ID to switch into

        Returns:
            SwitchOrgResult: fresh access/refresh tokens + active_organization
        """
        response = await self._http.request(
            "POST",
            "/api/v1/auth/me/switch-org",
            json_data={"organization_id": organization_id},
        )
        return SwitchOrgResult(**response)

    async def auth_verify_email(self, token: str) -> VerifyEmailResult:
        """
        Verify an email address via a one-time token (no auth required).

        Args:
            token: One-time verification token from the registration email

        Returns:
            VerifyEmailResult
        """
        response = await self._http.request(
            "GET", f"/api/v1/auth/verify-email/{encode_path_param(token)}"
        )
        return VerifyEmailResult(**response)

    # -- Invitations --------------------------------------------------------

    async def invitations_list(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InvitationList:
        """
        List invitations for the current user's organization (admin-class only).

        Args:
            status: Filter by status ("pending"/"accepted"/"expired")
            limit: Maximum results (1-100)
            offset: Pagination offset

        Returns:
            InvitationList: records + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._http.request("GET", "/api/v1/invitations", params=params)
        return InvitationList(**response)

    async def invitations_create(self, email: str, role: str) -> InvitationWithToken:
        """
        Create a new invitation (admin-class only). Returns the invitation
        WITH its one-time token — the token is shown only on create.

        Args:
            email: Invitee email address
            role: One of "org_admin", "developer", "viewer"

        Returns:
            InvitationWithToken: callers MUST NOT log ``.token``
        """
        response = await self._http.request(
            "POST",
            "/api/v1/invitations",
            json_data={"email": email, "role": role},
        )
        return InvitationWithToken(**response)

    async def invitations_accept(
        self,
        token: str,
        email: str,
        name: str,
        password: str,
    ) -> AcceptInvitationResult:
        """
        Accept an invitation and create an account (unauthenticated flow).
        Auto-logs the new user in when token generation succeeds.

        Args:
            token: The invitation token
            email: Must match the invited email address
            name: Display name for the new account
            password: Must meet the password complexity policy

        Returns:
            AcceptInvitationResult
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/invitations/{encode_path_param(token)}/accept",
            json_data={"email": email, "name": name, "password": password},
        )
        return AcceptInvitationResult(**response)

    # -- SSO connections --------------------------------------------------

    async def sso_connections_list(self) -> SSOConnectionList:
        """
        List all enterprise SSO connections for the organization.

        Returns:
            SSOConnectionList
        """
        response = await self._http.request("GET", "/api/v1/sso/connections")
        return SSOConnectionList(**response)

    async def sso_connections_create(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        tenant_id: str | None = None,
        domain: str | None = None,
        is_default: bool = False,
        auto_provision: bool = True,
        default_role: str = "developer",
        allowed_domains: str | None = None,
        custom_urls: dict[str, str] | None = None,
    ) -> SSOConnection:
        """
        Create a new enterprise SSO connection (admin-class only).

        Args:
            provider: Provider type (e.g. "azure", "google", "okta", "custom")
            client_id: OAuth client ID
            client_secret: OAuth client secret (encrypted server-side; the
                response never echoes it back)
            tenant_id: Azure tenant ID (provider-specific)
            domain: Okta/Auth0 domain (provider-specific)
            is_default: Set as the org's default connection
            auto_provision: Auto-create users on first login
            default_role: Role assigned to auto-provisioned users
            allowed_domains: Comma-separated allowed email domains
            custom_urls: Custom authorize/token/userinfo URLs (provider="custom" only)

        Returns:
            SSOConnection: never carries the plaintext or encrypted secret
        """
        data: dict[str, Any] = {
            "provider": provider,
            "client_id": client_id,
            "client_secret": client_secret,
            "is_default": is_default,
            "auto_provision": auto_provision,
            "default_role": default_role,
        }
        if tenant_id:
            data["tenant_id"] = tenant_id
        if domain:
            data["domain"] = domain
        if allowed_domains:
            data["allowed_domains"] = allowed_domains
        if custom_urls:
            data["custom_urls"] = custom_urls

        response = await self._http.request("POST", "/api/v1/sso/connections", json_data=data)
        return SSOConnection(**response)

    # -- Onboarding -----------------------------------------------------

    async def onboarding_start_trial(
        self,
        name: str,
        department_name: str | None = None,
        operator_role_title: str | None = None,
    ) -> StartTrialResult:
        """
        Self-serve boot of a governed trial organization. No approval
        step-up required to boot an empty trial (that gate is on real-data
        import + upgrade-to-paid).

        Args:
            name: Trial organization name
            department_name: Optional seed department name
            operator_role_title: Optional seed operator role title

        Returns:
            StartTrialResult
        """
        data: dict[str, Any] = {"name": name}
        if department_name:
            data["department_name"] = department_name
        if operator_role_title:
            data["operator_role_title"] = operator_role_title

        response = await self._http.request(
            "POST", "/api/v1/onboarding/start-trial", json_data=data
        )
        return StartTrialResult(**response)

    # -- Admin access visualization ---------------------------------------

    async def admin_access_tree(self) -> AccessTreeResult:
        """
        Get the role hierarchy with direct/inherited access flags per agent
        (Access Visualization Tree tab).

        Returns:
            AccessTreeResult
        """
        response = await self._http.request("GET", "/api/v1/admin/access/tree")
        return AccessTreeResult(**response)

    async def admin_access_matrix(self) -> AccessMatrixResult:
        """
        Get the role x agent access matrix (Matrix tab).

        Returns:
            AccessMatrixResult
        """
        response = await self._http.request("GET", "/api/v1/admin/access/matrix")
        return AccessMatrixResult(**response)

    async def admin_access_audit(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> AccessAuditResult:
        """
        Get the access grant/revoke/modify audit trail (Audit Trail tab).

        Args:
            start_date: Optional ISO date lower bound
            end_date: Optional ISO date upper bound
            action: Filter by "grant"/"revoke"/"modify"
            target_type: Filter by "agent"/"role"/"user"
            page: Page number (1-indexed)
            page_size: Results per page (1-200)

        Returns:
            AccessAuditResult
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if action:
            params["action"] = action
        if target_type:
            params["target_type"] = target_type

        response = await self._http.request("GET", "/api/v1/admin/access/audit", params=params)
        return AccessAuditResult(**response)

    # -- SSO: connection CRUD ------------------------------------------------

    async def sso_connections_get(self, connection_id: str) -> SSOConnection:
        """
        Get one SSO connection.

        Server: ``GET /api/v1/sso/connections/{connection_id}``. The encrypted
        client secret is stripped server-side, so it never reaches this model.

        Args:
            connection_id: Connection ID

        Returns:
            SSOConnection

        Example:
            >>> conn = await client.auth_users.sso_connections_get("conn-1")
            >>> print(conn.provider, conn.status)
        """
        response = await self._http.request(
            "GET", f"/api/v1/sso/connections/{encode_path_param(connection_id)}"
        )
        return SSOConnection(**response)

    async def sso_connections_update(
        self, connection_id: str, **fields: Any
    ) -> SSOConnection:
        """
        Update an SSO connection.

        Server: ``PUT /api/v1/sso/connections/{connection_id}``. Only the
        fields supplied are sent.

        Args:
            connection_id: Connection ID
            **fields: Connection fields to change (e.g. ``is_default``,
                ``auto_provision``, ``default_role``, ``allowed_domains``,
                ``status``)

        Returns:
            SSOConnection: the updated connection

        Example:
            >>> await client.auth_users.sso_connections_update(
            ...     "conn-1", is_default=True
            ... )
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/sso/connections/{encode_path_param(connection_id)}",
            json_data=fields,
        )
        return SSOConnection(**response)

    async def sso_connections_delete(self, connection_id: str) -> SSODeleteResult:
        """
        Delete an SSO connection.

        Server: ``DELETE /api/v1/sso/connections/{connection_id}``.

        Args:
            connection_id: Connection ID

        Returns:
            SSODeleteResult

        Example:
            >>> await client.auth_users.sso_connections_delete("conn-1")
        """
        response = await self._http.request(
            "DELETE", f"/api/v1/sso/connections/{encode_path_param(connection_id)}"
        )
        return SSODeleteResult(**response)

    # -- SSO: login flows ----------------------------------------------------
    #
    # Every route in this section is UNDECLARED server-side: sso.py carries
    # ZERO `response_model=` and none of its handlers has a return annotation,
    # so FastAPI publishes no schema for any of them. The models above are
    # built from each handler's literal return expression, not guessed — and
    # they are provisional until the core lane declares the contract.

    async def sso_providers(self) -> SSOProviders:
        """
        Report which built-in login-page SSO providers are configured.

        Server: ``GET /api/v1/sso/providers``. Public and unauthenticated.
        Render a provider whose value is False as unavailable rather than
        calling initiate on it, which would answer 503.

        Args:
            None

        Returns:
            SSOProviders: a boolean per provider

        Example:
            >>> p = await client.auth_users.sso_providers()
            >>> print([k for k, on in p.providers.items() if on])
        """
        response = await self._http.request("GET", "/api/v1/sso/providers")
        return SSOProviders(**response)

    async def sso_initiate(self, provider: str) -> SSOInitiation:
        """
        Begin a login-page SSO flow for a built-in provider.

        Server: ``GET /api/v1/sso/initiate/{provider}``.

        ⚠ Returns a URL to send the USER to; it does not log anyone in. The
        flow completes in the browser at the callback, which this SDK
        deliberately does not wrap — see the note at the end of this module.

        Args:
            provider: Provider key, as reported by :meth:`sso_providers`

        Returns:
            SSOInitiation: the authorization URL and its CSRF state

        Example:
            >>> init = await client.auth_users.sso_initiate("google")
            >>> webbrowser.open(init.auth_url)
        """
        response = await self._http.request(
            "GET", f"/api/v1/sso/initiate/{encode_path_param(provider)}"
        )
        return SSOInitiation(**response)

    async def sso_auth_url(
        self, connection_id: str, redirect_uri: str | None = None
    ) -> str:
        """
        Get the authorization URL for a configured SSO connection.

        Server: ``GET /api/v1/sso/auth/{connection_id}``. The route responds
        with a bare JSON STRING — the service's ``get_authorization_url``
        returns ``str`` — so this returns a string rather than a model.

        ⚠ As with :meth:`sso_initiate`, send the user to this URL; fetching it
        programmatically does not authenticate anyone.

        Args:
            connection_id: Connection ID
            redirect_uri: Where the provider should return the user

        Returns:
            The provider's authorization URL

        Example:
            >>> url = await client.auth_users.sso_auth_url("conn-1")
        """
        params = {"redirect_uri": redirect_uri} if redirect_uri is not None else None
        response = await self._http.request(
            "GET", f"/api/v1/sso/auth/{encode_path_param(connection_id)}", params=params
        )
        return str(response)

    async def sso_saml_initiate(self, connection_id: str) -> SAMLInitiation:
        """
        Begin an SP-initiated SAML SSO flow.

        Server: ``GET /api/v1/sso/saml/initiate/{connection_id}``. Mints a
        single-use RelayState bound to the connection with a TTL. The ACS
        refuses any assertion whose RelayState it did not issue, so this call
        is a precondition of the flow, not an optimisation.

        Args:
            connection_id: Connection ID

        Returns:
            SAMLInitiation: the IdP AuthnRequest URL and its relay state

        Example:
            >>> init = await client.auth_users.sso_saml_initiate("conn-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/sso/saml/initiate/{encode_path_param(connection_id)}"
        )
        return SAMLInitiation(**response)

    async def sso_link_account(
        self, connection_id: str, code: str
    ) -> dict[str, Any]:
        """
        Link the authenticated user's account to an SSO provider.

        Server: ``POST /api/v1/sso/link``.

        ⚠ Returns a raw dict: the route declares no response model and the
        service's ``link_user_to_sso`` is annotated ``-> dict``, so there is no
        contract to type against. A model here would be this client's
        invention rather than the API's.

        Args:
            connection_id: Connection to link through
            code: Authorization code obtained from the provider

        Returns:
            The identity record exactly as the server emits it

        Example:
            >>> identity = await client.auth_users.sso_link_account("conn-1", code)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/sso/link",
            json_data={"connection_id": connection_id, "code": code},
        )
        return dict(response)

    async def sso_identities(self) -> list[dict[str, Any]]:
        """
        List the SSO identities linked to the authenticated user.

        Server: ``GET /api/v1/sso/identities``.

        ⚠ Returns raw dicts for the same reason as :meth:`sso_link_account` —
        the route declares no response model.

        Args:
            None

        Returns:
            The identity records exactly as the server emits them

        Example:
            >>> for identity in await client.auth_users.sso_identities():
            ...     print(identity.get("provider"))
        """
        response = await self._http.request("GET", "/api/v1/sso/identities")
        return list(response)


# ---------------------------------------------------------------------------
# DELIBERATELY NOT WRAPPED — browser / IdP flow endpoints
# ---------------------------------------------------------------------------
#
# Three live SSO routes have no SDK method, and their absence is a decision
# rather than a gap. Each is a target for a BROWSER or an IdP, not for a
# programmatic client, so a method wrapping one would be a method nobody could
# correctly call:
#
#   GET  /api/v1/sso/callback         the IdP redirects the USER'S BROWSER here
#                                     with a provider code; the route answers
#                                     307 and sets HTTP-only, host-only session
#                                     cookies. An SDK call receives a redirect
#                                     and cannot hold the cookie it depends on.
#   GET  /api/v1/sso/callback/public  same shape, unauthenticated variant.
#   POST /api/v1/sso/saml/acs         the SAML Assertion Consumer Service. Takes
#                                     form-encoded SAMLResponse + RelayState
#                                     produced by the IdP and signed by it. A
#                                     client cannot construct a valid assertion,
#                                     and should not be able to.
#
# The parity instrument measures REACH, not intent — its own docstring says
# deliberate withholding is a valid answer — so these will keep reporting as
# uncovered live paths. That is the honest reading: they are reachable and
# unwrapped on purpose.
