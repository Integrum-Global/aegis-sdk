"""
Settings Module for Agentic OS SDK.

Thin HTTP-wrapper for organization + user settings, settings backups,
export/import, and the settings-change audit log.

Self-contained module: request/response models are
defined LOCALLY in this file. Do not import from ``aegis_sdk.types`` or
edit ``modules/__init__.py`` / ``client.py`` -- a separate orchestrator
wiring pass registers this module on the client.

Backend router (verified against the real source, cited per-method below):
  (FastAPI prefix ``/settings``), mounted
under the app-wide ``settings.api_prefix`` (``/api/v1`` -- verified), so every path
below is ``/api/v1/settings/...``.

13 of the router's 15 routes (P0 org/user get+update, P1 backups +
export/import, P2 audit-log read/revert):

  Org/user settings:
    - get_organization()   GET /api/v1/settings/organization
    - update_organization() PUT /api/v1/settings/organization
    - get_user()           GET /api/v1/settings/user
    - update_user()        PUT /api/v1/settings/user
  Backups:
    - list_backups()       GET    /api/v1/settings/backups
    - create_backup()      POST   /api/v1/settings/backups
    - restore_backup()     POST   /api/v1/settings/backups/restore/{id}
    - delete_backup()      DELETE /api/v1/settings/backups/{id}
  Export/import:
    - export()             POST /api/v1/settings/export
    - preview_import()     POST /api/v1/settings/import/preview (multipart)
    - import_settings()    POST /api/v1/settings/import (multipart)
  Audit log:
    - revert_audit_log()   POST /api/v1/settings/audit-log/revert
    - get_audit_log()      GET  /api/v1/settings/audit-log/{id}
    - list_audit_log()     GET  /api/v1/settings/audit-log

Also wraps the tenant site/branding config admin surface (separate router, prefix ``/site-config``,
mounted under ``/api/v1``):
  - get_site_config()    GET /api/v1/site-config
  - upsert_site_config() PUT /api/v1/site-config

Known limitation (documented, not a phantom route): ``GET
/settings/audit-log/export`` always returns raw
``text/csv`` bytes with no JSON option -- the shared ``HTTPClient.request()``
always calls ``response.json()`` for a 200, which raises on
non-JSON content. That route is intentionally NOT
wrapped here; a raw-bytes export requires a transport-layer addition out
of this module's self-contained scope.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param

SettingsCategory = Literal[
    "general", "appearance", "ontology", "notifications", "security", "preferences"
]
ExportFormat = Literal["json", "yaml"]


# ---------------------------------------------------------------------------
# Response models -- Org/user settings (verified; both
# response models use ``populate_by_name=True`` + camelCase aliases).
# ---------------------------------------------------------------------------


class NotificationSettings(BaseModel):
    """Notification settings."""

    email: bool = True
    push: bool = True
    slack: bool = False
    digest: bool = True


class SecuritySettings(BaseModel):
    """Security settings."""

    model_config = ConfigDict(populate_by_name=True)

    mfa_enabled: bool = Field(False, alias="mfaEnabled")
    session_timeout: int = Field(30, alias="sessionTimeout")
    ip_whitelist: list[str] = Field(default_factory=list, alias="ipWhitelist")


class OrganizationSettings(BaseModel):
    """Organization settings (response shape)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(..., alias="organizationId")
    name: str
    theme: str = "system"
    timezone: str = "UTC"
    language: str = "en"
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    created_at: str = Field("", alias="createdAt")
    updated_at: str = Field("", alias="updatedAt")


class UserSettings(BaseModel):
    """Current user's settings (response shape)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str = Field(..., alias="userId")
    theme: str = "system"
    timezone: str = "UTC"
    language: str = "en"
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    created_at: str = Field("", alias="createdAt")
    updated_at: str = Field("", alias="updatedAt")


# ---------------------------------------------------------------------------
# Response models -- Backups (verified; FE
# ``SettingsBackup`` / ``SettingsImportResult`` shapes).
# ---------------------------------------------------------------------------


class SettingsBackup(BaseModel):
    """A settings backup."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    created_at: str = Field("", alias="createdAt")
    size: int = 0
    categories: list[str] = Field(default_factory=list)
    auto_backup: bool = Field(False, alias="autoBackup")


class SettingsConflict(BaseModel):
    """A single unresolved import/restore conflict."""

    model_config = ConfigDict(populate_by_name=True)

    category: str
    field: str
    current_value: Any = Field(None, alias="currentValue")
    import_value: Any = Field(None, alias="importValue")
    reason: str = ""


class SettingsImportResult(BaseModel):
    """Result of an import/restore apply."""

    success: bool
    applied: int = 0
    skipped: int = 0
    conflicts: list[SettingsConflict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response models -- Export/import (verified)
# ---------------------------------------------------------------------------


class SettingsExport(BaseModel):
    """Portable settings export."""

    model_config = ConfigDict(populate_by_name=True)

    version: str
    exported_at: str = Field("", alias="exportedAt")
    format: str = "json"
    categories: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class SettingsImportPreviewChange(BaseModel):
    """A single non-conflicting proposed change."""

    model_config = ConfigDict(populate_by_name=True)

    category: str
    field: str
    old_value: Any = Field(None, alias="oldValue")
    new_value: Any = Field(None, alias="newValue")


class SettingsImportPreview(BaseModel):
    """Diff-only preview of an uploaded export file."""

    valid: bool
    version: str = ""
    categories: list[str] = Field(default_factory=list)
    changes: list[SettingsImportPreviewChange] = Field(default_factory=list)
    conflicts: list[SettingsConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response models -- Audit log (verified)
# ---------------------------------------------------------------------------


class SettingsActor(BaseModel):
    """The user who made a settings change."""

    id: str
    name: str = ""
    email: str = ""
    avatar: str | None = None


class SettingsChange(BaseModel):
    """A single recorded field change."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    old_value: Any = Field(None, alias="oldValue")
    new_value: Any = Field(None, alias="newValue")


class SettingsAuditLog(BaseModel):
    """A single settings-audit record."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    timestamp: str = ""
    actor: SettingsActor
    action: str = ""
    category: str = ""
    changes: list[SettingsChange] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
    revertable: bool = False


class SettingsAuditList(BaseModel):
    """Paginated settings-audit list."""

    model_config = ConfigDict(populate_by_name=True)

    logs: list[SettingsAuditLog] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(50, alias="pageSize")


# ---------------------------------------------------------------------------
# Response models -- Site configuration (verified against the real backend
# projection). Wire shape is snake_case (NO Pydantic alias generator on the
# projection), pinned by an automated envelope-shape check on the platform
# side. The router is mounted under the client's configured ``api_prefix``,
# so the path is ``/api/v1/site-config``.
# ---------------------------------------------------------------------------


class SiteConfig(BaseModel):
    """Tenant site / branding configuration."""

    id: str | None = None
    organization_id: str | None = None
    site_name: str = ""
    logo_url: str | None = None
    primary_color: str | None = None
    support_email: str | None = None
    navigation: list[Any] = Field(default_factory=list)
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class SettingsModule:
    """
    Settings module -- organization + user preferences, backups,
    export/import, and the settings-change audit trail.

    Examples:
        # Read + update organization settings
        >>> org = await client.settings.get_organization()
        >>> updated = await client.settings.update_organization(theme="dark")

        # Snapshot before a risky change
        >>> backup = await client.settings.create_backup(name="pre-migration")
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize settings module.

        Args:
            http_client: HTTPClient instance for API requests.
        """
        self._http = http_client

    # -------------------------------------------------------------------
    # Organization / user settings
    # -------------------------------------------------------------------

    async def get_organization(self) -> OrganizationSettings:
        """Get organization settings for the caller's org
        (GET /settings/organization)."""
        response = await self._http.request(
            "GET",
            "/api/v1/settings/organization",
        )
        return OrganizationSettings(**response)

    async def update_organization(
        self,
        name: str | None = None,
        theme: str | None = None,
        timezone: str | None = None,
        language: str | None = None,
        notifications: dict[str, Any] | None = None,
        security: dict[str, Any] | None = None,
    ) -> OrganizationSettings:
        """Update organization settings (PUT
        /settings/organization). Requires org_owner / org_admin /
        tenant_admin role server-side."""
        data: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("theme", theme),
            ("timezone", timezone),
            ("language", language),
            ("notifications", notifications),
            ("security", security),
        ):
            if value is not None:
                data[key] = value

        response = await self._http.request(
            "PUT",
            "/api/v1/settings/organization",
            json_data=data,
        )
        return OrganizationSettings(**response)

    async def get_user(self) -> UserSettings:
        """Get the current user's settings (GET
        /settings/user)."""
        response = await self._http.request(
            "GET",
            "/api/v1/settings/user",
        )
        return UserSettings(**response)

    async def update_user(
        self,
        theme: str | None = None,
        timezone: str | None = None,
        language: str | None = None,
        notifications: dict[str, Any] | None = None,
    ) -> UserSettings:
        """Update the current user's settings (PUT
        /settings/user)."""
        data: dict[str, Any] = {}
        for key, value in (
            ("theme", theme),
            ("timezone", timezone),
            ("language", language),
            ("notifications", notifications),
        ):
            if value is not None:
                data[key] = value

        response = await self._http.request(
            "PUT",
            "/api/v1/settings/user",
            json_data=data,
        )
        return UserSettings(**response)

    # -------------------------------------------------------------------
    # Backups
    # -------------------------------------------------------------------

    async def list_backups(self) -> list[SettingsBackup]:
        """List settings backups (GET
        /settings/backups). BARE array response -- matches the FE
        ``settingsApi.getBackups(): Promise<SettingsBackup[]>`` contract."""
        response = await self._http.request(
            "GET",
            "/api/v1/settings/backups",
        )
        return [SettingsBackup(**b) for b in response]

    async def create_backup(self, name: str | None = None) -> SettingsBackup:
        """Create a settings backup (POST
        /settings/backups)."""
        response = await self._http.request(
            "POST",
            "/api/v1/settings/backups",
            json_data={"name": name} if name is not None else {},
        )
        return SettingsBackup(**response)

    async def restore_backup(self, backup_id: str) -> SettingsImportResult:
        """Restore organization + user settings from a backup
        (POST /settings/backups/restore/{id}).
        Requires org_owner / org_admin / tenant_admin role server-side."""
        response = await self._http.request(
            "POST",
            f"/api/v1/settings/backups/restore/{encode_path_param(backup_id)}",
        )
        return SettingsImportResult(**response)

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a settings backup (DELETE
        /settings/backups/{id}, returns 204)."""
        await self._http.request(
            "DELETE",
            f"/api/v1/settings/backups/{encode_path_param(backup_id)}",
        )
        return True

    # -------------------------------------------------------------------
    # Export / import
    # -------------------------------------------------------------------

    async def export(
        self,
        categories: list[SettingsCategory],
        format: ExportFormat = "json",
        include_sensitive: bool = False,
    ) -> SettingsExport:
        """Export organization (+ personal preferences) settings
        (POST /settings/export). The HTTP
        response is always a JSON envelope regardless of the requested
        ``format`` -- ``format`` only controls the shape of the nested
        ``data`` field."""
        data: dict[str, Any] = {
            "categories": categories,
            "format": format,
            "include_sensitive": include_sensitive,
        }
        response = await self._http.request(
            "POST",
            "/api/v1/settings/export",
            json_data=data,
        )
        return SettingsExport(**response)

    async def preview_import(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> SettingsImportPreview:
        """Diff an exported settings file against current settings
        WITHOUT applying it (POST
        /settings/import/preview -- multipart upload).

        Args:
            file_bytes: Raw bytes of the export file to preview.
            filename: Original filename (used for content-type sniffing
                server-side).
        """
        response = await self._http.request(
            "POST",
            "/api/v1/settings/import/preview",
            files={"file": (filename, file_bytes)},
        )
        return SettingsImportPreview(**response)

    async def import_settings(
        self,
        file_bytes: bytes,
        filename: str,
        conflicts: dict[str, str] | None = None,
    ) -> SettingsImportResult:
        """Apply the non-conflicting (and caller-resolved) changes from an
        uploaded export file (POST /settings/import
        -- multipart upload). Requires org_owner / org_admin / tenant_admin
        role server-side.

        Args:
            file_bytes: Raw bytes of the export file to import.
            filename: Original filename.
            conflicts: Optional {"<category>-<field>": "keep"|"replace"}
                resolution map, sent as a JSON-encoded form field.
        """
        import json as _json

        data: dict[str, Any] = {}
        if conflicts is not None:
            data["conflicts"] = _json.dumps(conflicts)

        response = await self._http.request(
            "POST",
            "/api/v1/settings/import",
            files={"file": (filename, file_bytes)},
            data=data,
        )
        return SettingsImportResult(**response)

    # -------------------------------------------------------------------
    # Audit log
    # -------------------------------------------------------------------

    async def revert_audit_log(
        self,
        audit_log_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Revert a settings change by applying its recorded before-values
        (POST /settings/audit-log/revert).

        Returns ``OrganizationSettings | UserSettings`` -- the backend
        does not declare a ``response_model`` union for this route, so
        this method returns the raw dict rather than risk mis-coercing one shape into the other.
        """
        data: dict[str, Any] = {"audit_log_id": audit_log_id}
        if reason is not None:
            data["reason"] = reason

        return await self._http.request(
            "POST",
            "/api/v1/settings/audit-log/revert",
            json_data=data,
        )

    async def get_audit_log(self, audit_log_id: str) -> SettingsAuditLog:
        """Get a single settings-audit log record (GET /settings/audit-log/{id})."""
        response = await self._http.request(
            "GET",
            f"/api/v1/settings/audit-log/{encode_path_param(audit_log_id)}",
        )
        return SettingsAuditLog(**response)

    async def list_audit_log(
        self,
        category: str | None = None,
        action: str | None = None,
        user_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> SettingsAuditList:
        """List settings-audit log entries for the caller's organization
        (GET /settings/audit-log)."""
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if category:
            params["category"] = category
        if action:
            params["action"] = action
        if user_id:
            params["userId"] = user_id
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if search:
            params["search"] = search

        response = await self._http.request(
            "GET",
            "/api/v1/settings/audit-log",
            params=params,
        )
        return SettingsAuditList(**response)

    # -------------------------------------------------------------------
    # Site configuration
    # -------------------------------------------------------------------

    async def get_site_config(self) -> SiteConfig | None:
        """Get the caller-tenant's site / branding configuration
        (GET /site-config).

        Returns ``None`` when the tenant has no site configuration set --
        the backend returns a JSON ``null`` body (``dict | None`` return
        type), which the shared transport decodes to
        Python ``None``. Requires the ``executive``/``admin`` persona +
        ``organizations:read`` server-side.
        """
        response = await self._http.request(
            "GET",
            "/api/v1/site-config",
        )
        if response is None:
            return None
        return SiteConfig(**response)

    async def upsert_site_config(
        self,
        site_name: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        support_email: str | None = None,
        navigation: list[Any] | None = None,
        feature_flags: dict[str, Any] | None = None,
    ) -> SiteConfig:
        """Create or update the caller-tenant's site / branding
        configuration (PUT /site-config).

        All fields are optional (partial upsert -- ``UpsertSiteConfigBody``). Requires the ``executive``/``admin``
        persona + ``organizations:update`` server-side.
        """
        data: dict[str, Any] = {}
        for key, value in (
            ("site_name", site_name),
            ("logo_url", logo_url),
            ("primary_color", primary_color),
            ("support_email", support_email),
            ("navigation", navigation),
            ("feature_flags", feature_flags),
        ):
            if value is not None:
                data[key] = value

        response = await self._http.request(
            "PUT",
            "/api/v1/site-config",
            json_data=data,
        )
        return SiteConfig(**response)
