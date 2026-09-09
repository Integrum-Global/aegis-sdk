"""
Observe-domain Audit Module for Agentic OS SDK.

Thin HTTP-wrapper over the backend's platform Audit API
(prefix ``/api/v1/audit``) — audit-log
query/export. Named ``observe_audit`` (not ``audit``) to avoid clashing
with the existing ``trust/audit.py`` module, which wraps the DISTINCT
EATP trust-plane audit surface (``/api/v1/trust/audit``). This module
covers the PLATFORM audit log (user actions, resource changes) — the
surface that powers the audit viewer, alerts list, and compliance export.

Every route below was verified against the deployed API before implementation — path, method, and
response shape (all snake_case, no camelCase aliasing) match exactly.
This module is self-contained (no imports from client.py /
modules/__init__.py / types.py) per the; a
separate orchestrator pass registers it on ``AgenticOSClient``.

5 methods:
- list_logs()          - GET /api/v1/audit/logs                              (P0)
- get_log()            - GET /api/v1/audit/logs/{id}
- user_activity()      - GET /api/v1/audit/users/{user_id}
- resource_history()   - GET /api/v1/audit/resources/{resource_type}/{resource_id}
- export()             - GET /api/v1/audit/export                            (P1)
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .._http import encode_path_param

# ============================================================================
# Response Models (local — mirror the server response shape exactly)
# ============================================================================


class AuditLogEntry(BaseModel):
    """Single audit log entry (already snake_case on the wire)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    details: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    status: str
    error_message: str | None = None
    created_at: str


class AuditLogListResult(BaseModel):
    """Paginated audit log list response."""

    model_config = ConfigDict(populate_by_name=True)

    logs: list[AuditLogEntry]
    total: int


class AlertThresholdListResult(BaseModel):
    """Paginated alert-threshold list response.

    Mirrors the ``list_thresholds`` return — ``{records, total}``. The threshold rows are the
    ``ThresholdService`` return shape (snake_case FE ``AlertThreshold``); the
    route declares no strict response_model so the records are returned
    unmodelled rather than inventing a field schema.
    """

    model_config = ConfigDict(populate_by_name=True)

    records: list[dict[str, Any]]
    total: int


class AlertLifecycleResult(BaseModel):
    """Confirmation of an alert lifecycle transition (acknowledge / resolve).

    Mirrors ``AlertLifecycleResponse`` —
    plain snake_case. ``audit_id`` is the id of the newly-written server-side
    audit row (alerts are audit-log entries, not a separate table).
    """

    model_config = ConfigDict(populate_by_name=True)

    alert_id: str
    status: str  # "acknowledged" | "resolved"
    audit_id: str


# ============================================================================
# Module
# ============================================================================


class ObserveAuditModule:
    """
    Observe-domain audit module — platform audit-log query/export.

    Distinct from ``trust.audit.AuditModule``, which covers the EATP
    trust-plane audit surface (``/api/v1/trust/audit``, agent-action audit
    anchors). This module covers the platform audit log — user actions,
    resource changes, compliance export.

    Examples:
        >>> logs = await client.observe_audit.list_logs(action="user.login", limit=50)
        >>> for entry in logs.logs:
        ...     print(entry.action, entry.created_at)

        >>> entry = await client.observe_audit.get_log("audit-123")

        >>> csv_text = await client.observe_audit.export(format="csv")
    """

    def __init__(self, http_client):
        """
        Initialize the observe-audit module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def list_logs(
        self,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AuditLogListResult:
        """
        List audit logs with filters — powers the audit viewer, alerts list,
        alert history, and compliance dashboards.

        GET /api/v1/audit/logs

        Scoped server-side to the authenticated user's organization — the
        caller cannot request logs from a different organization.

        Args:
            user_id: Filter by user id
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource id
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            limit: Maximum results (1-200, default 100)
            offset: Pagination offset (default 0)

        Returns:
            AuditLogListResult: logs + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if user_id:
            params["user_id"] = user_id
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if resource_id:
            params["resource_id"] = resource_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/audit/logs",
            params=params,
        )
        return AuditLogListResult(**response)

    async def get_log(self, log_id: str) -> AuditLogEntry:
        """
        Get a specific audit log entry.

        GET /api/v1/audit/logs/{id}

        Returns the entry only if it belongs to the caller's organization
        (backend returns 404 on cross-tenant mismatch to prevent resource
        enumeration).

        Args:
            log_id: Audit log id

        Returns:
            AuditLogEntry: The audit log entry
        """
        response = await self._http.request(
            "GET", f"/api/v1/audit/logs/{encode_path_param(log_id)}"
        )
        return AuditLogEntry(**response)

    async def user_activity(self, user_id: str, limit: int = 50) -> list[AuditLogEntry]:
        """
        Get activity history for a specific user.

        GET /api/v1/audit/users/{user_id}

        Returns entries only if the target user belongs to the caller's
        organization (404 on mismatch to prevent enumeration).

        Args:
            user_id: Target user id
            limit: Maximum results (1-500, default 50)

        Returns:
            list[AuditLogEntry]: Activity history for the user
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/audit/users/{encode_path_param(user_id)}",
            params={"limit": limit},
        )
        return [AuditLogEntry(**item) for item in response]

    async def resource_history(self, resource_type: str, resource_id: str) -> list[AuditLogEntry]:
        """
        Get audit history for a specific resource.

        GET /api/v1/audit/resources/{resource_type}/{resource_id}

        Filtered server-side to the caller's organization.

        Args:
            resource_type: Resource type (e.g. "objective", "agent")
            resource_id: Resource id

        Returns:
            list[AuditLogEntry]: Audit history for the resource
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/audit/resources/{encode_path_param(resource_type)}/{encode_path_param(resource_id)}",
        )
        return [AuditLogEntry(**item) for item in response]

    async def export(
        self,
        format: Literal["json"] = "json",
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 1000,
        mask_level: Literal["none", "betriebsrat", "gdpr_export"] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Export audit logs for compliance reporting.

        GET /api/v1/audit/export

        Scoped server-side to the caller's organization. PII masking level
        defaults server-side to "none" for admin-class roles and
        "betriebsrat" otherwise.

        KNOWN LIMITATION (documented, not invented): the backend also
        supports ``format="csv"``, returning a ``text/csv`` body via a raw
        FastAPI ``Response``. The shared
        ``HTTPClient._handle_response`` (src/aegis_sdk/_http.py, out of
        scope for this self-contained module) unconditionally calls
        ``response.json()`` on any 200 — which raises ``JSONDecodeError``
        against CSV text. Only ``format="json"`` is exposed here until the
        shared HTTPClient gains a raw-text response mode; the ``format``
        param is typed ``Literal["json"]`` to make that constraint explicit
        rather than silently passing through a broken "csv" option.

        Args:
            format: Export format — only "json" is safe via this client today
            user_id: Filter by user id
            action: Filter by action type
            resource_type: Filter by resource type
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            limit: Maximum results for export (1-5000, default 1000)
            mask_level: PII masking level — none, betriebsrat, or gdpr_export.
                The server derives a floor from the caller's role and this
                value may only TIGHTEN it; a request for less masking than
                the caller's role allows is clamped server-side, so the
                returned records may be masked more than asked.

        Returns:
            list[dict]: Exported audit log records (JSON-parsed)
        """
        params: dict[str, Any] = {"format": format, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if mask_level:
            params["mask_level"] = mask_level

        return await self._http.request(
            "GET",
            "/api/v1/audit/export",
            params=params,
        )

    async def list_thresholds(
        self,
        search: str | None = None,
        metric: str | None = None,
        severity: str | None = None,
        enabled: bool | None = None,
        limit: int = 12,
        offset: int = 0,
    ) -> AlertThresholdListResult:
        """
        List alert thresholds for the caller's tenant (analytics thresholds manager).

        GET /api/v1/alerts/thresholds.
        Requires an executive/admin persona (router-level dependency).

        Args:
            search: Free-text filter over threshold name (applied post-list)
            metric: Filter by metric
            severity: Filter by severity
            enabled: Filter by enabled state
            limit: Maximum results (1-200, default 12)
            offset: Pagination offset (default 0)

        Returns:
            AlertThresholdListResult: records + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if metric:
            params["metric"] = metric
        if severity:
            params["severity"] = severity
        if enabled is not None:
            params["enabled"] = enabled

        response = await self._http.request(
            "GET",
            "/api/v1/alerts/thresholds",
            params=params,
        )
        return AlertThresholdListResult(**response)

    async def create_threshold(
        self,
        name: str,
        metric: str,
        operator: str,
        threshold: float,
        duration: int,
        severity: str,
        enabled: bool = True,
        notification_channels: list[str] | None = None,
        description: str | None = None,
        message_template: str | None = None,
    ) -> dict[str, Any]:
        """
        Create an alert threshold.

        POST /api/v1/alerts/thresholds.
        Enum fields (``operator`` / ``severity``) are allowlist-validated
        server-side (422 on invalid); the create is audit-logged server-side.

        Args:
            name: Threshold name
            metric: Metric the threshold watches
            operator: Comparison operator (server-side allowlist)
            threshold: Numeric threshold value
            duration: Sustained-breach duration in seconds (>= 0)
            severity: Severity level (server-side allowlist)
            enabled: Whether the threshold is active (default True)
            notification_channels: Notification channel ids to alert
            description: Optional description
            message_template: Optional alert-message template

        Returns:
            dict: The created threshold record
        """
        body: dict[str, Any] = {
            "name": name,
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "duration": duration,
            "severity": severity,
            "enabled": enabled,
        }
        if notification_channels is not None:
            body["notification_channels"] = notification_channels
        if description is not None:
            body["description"] = description
        if message_template is not None:
            body["message_template"] = message_template

        return await self._http.request(
            "POST",
            "/api/v1/alerts/thresholds",
            json_data=body,
        )

    async def acknowledge_alert(
        self,
        alert_id: str,
        note: str | None = None,
    ) -> AlertLifecycleResult:
        """
        Acknowledge an alert (audit-derived alerts lifecycle).

        POST /api/v1/alerts/{alert_id}/acknowledge. Alerts ARE audit-log rows; the handler writes a
        new ``alert_acknowledged`` audit row server-side (the caller cannot
        inject arbitrary action/resource fields).

        Args:
            alert_id: The originating audit-log id of the alert
            note: Optional operator note (<= 1024 chars, carried into the
                audit row)

        Returns:
            AlertLifecycleResult: alert_id + status + new audit row id
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/alerts/{encode_path_param(alert_id)}/acknowledge",
            json_data={"note": note} if note is not None else None,
        )
        return AlertLifecycleResult(**response)

    async def resolve_alert(self, alert_id: str) -> AlertLifecycleResult:
        """
        Resolve an alert.

        POST /api/v1/alerts/{alert_id}/resolve. Writes an ``alert_resolved`` audit row server-side; same
        defenses as :meth:`acknowledge_alert`.

        Args:
            alert_id: The originating audit-log id of the alert

        Returns:
            AlertLifecycleResult: alert_id + status + new audit row id
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/alerts/{encode_path_param(alert_id)}/resolve",
        )
        return AlertLifecycleResult(**response)
