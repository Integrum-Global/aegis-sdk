"""
Compliance Module for Agentic OS SDK.

Provides compliance management, audit logs, HIPAA, and SOC 2 features.

30 methods.

Audit / HIPAA / SOC2 / retention:
- verify_audit() - Verify audit log integrity
- export_audit() - Export audit logs
- list_audit_entries() - List audit entries
- get_hipaa_status() - Get HIPAA compliance status
- enable_hipaa() - Enable HIPAA mode
- disable_hipaa() - Disable HIPAA mode
- get_hipaa_settings() - Get HIPAA settings
- generate_soc2_evidence() - Generate SOC 2 evidence package
- export_soc2_evidence() - Export SOC 2 evidence
- execute_retention() - Execute retention policy
- list_retention_policies() - List retention policies
- get_retention_policy() - Get retention policy
- create_retention_policy() - Create retention policy
- update_retention_policy() - Update retention policy
- get_dashboard() - Get compliance dashboard

Framework evaluation, scoring and reporting — COMPUTE ONLY, never enforcement
(see the section comment on the module class):
- get_chain_integrity() / get_trust_health()
- list_frameworks() / get_framework() / get_framework_controls()
- get_soc2_status() / get_score() / list_events() / run_assessment()
- list_violations() / acknowledge_alert()
- get_report_summary() / get_report() / get_report_pdf() / create_report()
- export_report()
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import HTTPClient, encode_path_param


class AuditVerificationResult(BaseModel):
    """Audit log verification result."""

    model_config = ConfigDict(populate_by_name=True)

    valid: bool
    entries_checked: int = Field(alias="entriesChecked")
    first_invalid_id: str | None = Field(None, alias="firstInvalidId")
    error: str | None = None


class AuditEntry(BaseModel):
    """Audit log entry."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    timestamp: str
    organization_id: str = Field(alias="organizationId")
    user_id: str | None = Field(None, alias="userId")
    agent_id: str | None = Field(None, alias="agentId")
    action: str
    resource_type: str = Field(alias="resourceType")
    resource_id: str | None = Field(None, alias="resourceId")
    result: str  # success, failure, error
    details: dict[str, Any] | None = None
    ip_address: str | None = Field(None, alias="ipAddress")
    user_agent: str | None = Field(None, alias="userAgent")
    session_id: str | None = Field(None, alias="sessionId")
    previous_hash: str | None = Field(None, alias="previousHash")
    entry_hash: str = Field(alias="entryHash")
    sequence_number: int = Field(alias="sequenceNumber")


class ComplianceCheck(BaseModel):
    """Individual compliance check result."""

    name: str
    passed: bool
    requirement: str
    evidence: str | None = None
    remediation: str | None = None


class HIPAAStatus(BaseModel):
    """HIPAA compliance status."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    is_compliant: bool = Field(alias="isCompliant")
    hipaa_mode_enabled: bool = Field(alias="hipaaModeEnabled")
    checked_at: str = Field(alias="checkedAt")
    total_checks: int = Field(alias="totalChecks")
    passed_checks: int = Field(alias="passedChecks")
    compliance_percentage: float = Field(alias="compliancePercentage")
    access_control: list[ComplianceCheck] = Field(alias="accessControl")
    audit_controls: list[ComplianceCheck] = Field(alias="auditControls")
    integrity_controls: list[ComplianceCheck] = Field(alias="integrityControls")
    transmission_security: list[ComplianceCheck] = Field(alias="transmissionSecurity")


class HIPAASettings(BaseModel):
    """HIPAA mode settings."""

    model_config = ConfigDict(populate_by_name=True)

    hipaa_mode_enabled: bool = Field(alias="hipaaModeEnabled")
    hipaa_enabled_at: str | None = Field(None, alias="hipaaEnabledAt")
    hipaa_enabled_by: str | None = Field(None, alias="hipaaEnabledBy")
    session_timeout_minutes: int = Field(alias="sessionTimeoutMinutes")
    password_min_length: int = Field(alias="passwordMinLength")
    require_mfa: bool = Field(alias="requireMfa")
    audit_logging_extended: bool = Field(alias="auditLoggingExtended")
    encryption_at_rest_enabled: bool = Field(alias="encryptionAtRestEnabled")
    encryption_in_transit_enabled: bool = Field(alias="encryptionInTransitEnabled")
    audit_log_retention_years: int = Field(alias="auditLogRetentionYears")
    account_lockout_attempts: int = Field(alias="accountLockoutAttempts")
    account_lockout_minutes: int = Field(alias="accountLockoutMinutes")


class HIPAAEnableResult(BaseModel):
    """HIPAA enable result."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    hipaa_mode_enabled: bool = Field(alias="hipaaModeEnabled")
    enabled_at: str = Field(alias="enabledAt")
    enabled_by: str = Field(alias="enabledBy")
    settings_applied: dict[str, Any] = Field(alias="settingsApplied")


class HIPAADisableResult(BaseModel):
    """HIPAA disable result."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    hipaa_mode_enabled: bool = Field(alias="hipaaModeEnabled")
    disabled_at: str = Field(alias="disabledAt")
    disabled_by: str = Field(alias="disabledBy")
    reason: str


class EvidenceItem(BaseModel):
    """SOC 2 evidence item."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    timestamp: str
    description: str
    evidence_data: dict[str, Any] = Field(alias="evidenceData")
    control_reference: str = Field(alias="controlReference")


class SOC2EvidenceSummary(BaseModel):
    """SOC 2 evidence summary."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    total_evidence_items: int = Field(alias="totalEvidenceItems")
    cc6_items: int = Field(alias="cc6Items")
    cc7_items: int = Field(alias="cc7Items")
    cc8_items: int = Field(alias="cc8Items")
    period_days: int = Field(alias="periodDays")


class SOC2Evidence(BaseModel):
    """SOC 2 evidence package."""

    model_config = ConfigDict(populate_by_name=True)

    generated_at: str = Field(alias="generatedAt")
    period_start: str = Field(alias="periodStart")
    period_end: str = Field(alias="periodEnd")
    summary: SOC2EvidenceSummary
    cc6_access_controls: list[EvidenceItem] = Field(alias="cc6AccessControls")
    cc7_system_operations: list[EvidenceItem] = Field(alias="cc7SystemOperations")
    cc8_change_management: list[EvidenceItem] = Field(alias="cc8ChangeManagement")


class RetentionPolicy(BaseModel):
    """Data retention policy."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    description: str | None = None
    enabled: bool = True
    retention_days: int = Field(alias="retentionDays")
    action_on_expiry: str = Field(alias="actionOnExpiry")  # delete, archive, anonymize
    archive_after_days: int | None = Field(None, alias="archiveAfterDays")
    delete_after_archive_days: int | None = Field(None, alias="deleteAfterArchiveDays")
    notify_before_days: int | None = Field(None, alias="notifyBeforeDays")
    notify_recipients: list[str] | None = Field(None, alias="notifyRecipients")
    legal_hold: bool = Field(False, alias="legalHold")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RetentionExecutionResult(BaseModel):
    """Retention policy execution result."""

    model_config = ConfigDict(populate_by_name=True)

    affected_count: int = Field(alias="affectedCount")
    action: str
    dry_run: bool = Field(alias="dryRun")


class ComplianceDashboard(BaseModel):
    """Compliance dashboard summary."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    hipaa: dict[str, Any]
    data_governance: dict[str, Any] = Field(alias="dataGovernance")
    last_updated: str = Field(alias="lastUpdated")


class ChainIntegrity(BaseModel):
    """Result of the most recent audit-chain verification sweep.

    ⚠ ``ok=False`` does **not** mean the chain is broken. It also means the
    verifier has not completed a sweep yet — on a cold start this endpoint
    returns ``ok=False`` with ``last_verified_at=None`` and ``error="verifier
    has not completed a sweep yet"``. Read ``last_verified_at`` before treating
    a ``False`` as evidence of tampering: no timestamp means nobody has looked.

    This surface is READ-ONLY and does not trigger a sweep. Use
    :meth:`ComplianceModule.verify_audit` for an on-demand walk.
    """

    model_config = ConfigDict(populate_by_name=True)

    ok: bool
    broken_at: str | None = None
    total_entries: int = 0
    last_verified_at: str | None = None
    interval_seconds: int = 0
    error: str | None = None


class TrustHealth(BaseModel):
    """Trust-chain health counters for the organization.

    ⚠ ``percentage`` is deliberately **nullable, and must not be defaulted**.
    ``None`` means no percentage could honestly be computed, and ``measured``
    says which of two very different worlds you are in:

    * ``measured=False`` — the query FAILED. Chain state is UNKNOWN.
    * ``measured=True`` with ``total=0`` — the query succeeded and there is
      nothing to score. An empty set, not a failure.

    Neither is 0% and neither is 100%. Substituting either — in your own code,
    a template default, or a dashboard — reproduces the exact defect this
    field's design exists to prevent: an outage rendering as perfect health.
    ``reason`` names the case in prose when ``percentage`` is ``None``.
    """

    model_config = ConfigDict(populate_by_name=True)

    valid: int = 0
    expiring: int = 0
    expired: int = 0
    revoked: int = 0
    total: int = 0
    percentage: float | None = None
    measured: bool = False
    reason: str | None = None


class ComplianceModule:
    """
    Compliance module for audit, HIPAA, and SOC 2.

    Provides comprehensive compliance management capabilities.

    Examples:
        # Check HIPAA compliance
        >>> status = await client.compliance.get_hipaa_status()
        >>> print(f"Compliant: {status.is_compliant}")
        >>> print(f"Score: {status.compliance_percentage}%")

        # Generate SOC 2 evidence
        >>> evidence = await client.compliance.generate_soc2_evidence(
        ...     start_date="2024-01-01",
        ...     end_date="2024-03-31"
        ... )
        >>> print(f"Evidence items: {evidence.summary.total_evidence_items}")
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize compliance module."""
        self._http = http_client

    # Audit Methods
    async def verify_audit(
        self,
        start_id: str | None = None,
        end_id: str | None = None,
    ) -> AuditVerificationResult:
        """
        Verify audit log integrity.

        Uses cryptographic hash chain verification to detect tampering.

        Args:
            start_id: Starting entry ID (optional)
            end_id: Ending entry ID (optional)

        Returns:
            AuditVerificationResult: Verification result

        Example:
            >>> result = await client.compliance.verify_audit()
            >>> if result.valid:
            ...     print(f"Verified {result.entries_checked} entries")
            ... else:
            ...     print(f"Tampering detected at {result.first_invalid_id}")
        """
        params: dict[str, Any] = {}
        if start_id:
            params["start_id"] = start_id
        if end_id:
            params["end_id"] = end_id

        response = await self._http.request(
            "GET",
            "/api/v1/compliance/audit/verify",
            params=params if params else None,
        )
        return AuditVerificationResult(**response)

    async def export_audit(
        self,
        start_date: str,
        end_date: str,
        format: Literal["json", "csv", "cef", "syslog"] = "json",
    ) -> bytes:
        """
        Export audit logs.

        Args:
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            format: Export format (json, csv, cef/syslog)

        Returns:
            bytes: Exported data

        Example:
            >>> data = await client.compliance.export_audit(
            ...     start_date="2024-01-01",
            ...     end_date="2024-01-31",
            ...     format="csv"
            ... )
            >>> with open("audit.csv", "wb") as f:
            ...     f.write(data)
        """
        response: bytes = await self._http.request(
            "POST",
            "/api/v1/compliance/audit/export",
            json_data={
                "start_date": start_date,
                "end_date": end_date,
                "format": format,
            },
            raw_response=True,
        )
        return response

    async def list_audit_entries(
        self,
        action: str | None = None,
        resource_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """
        List audit log entries.

        Args:
            action: Filter by action type
            resource_type: Filter by resource type
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            limit: Maximum results (1-1000)
            offset: Pagination offset

        Returns:
            List[AuditEntry]: Audit entries
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        response = await self._http.request(
            "GET",
            "/api/v1/compliance/audit/entries",
            params=params,
        )
        return [AuditEntry(**e) for e in response.get("entries", [])]

    # HIPAA Methods
    async def get_hipaa_status(self) -> HIPAAStatus:
        """
        Get HIPAA compliance status.

        Performs comprehensive check of HIPAA technical safeguards
        per 45 CFR 164.312.

        Returns:
            HIPAAStatus: Compliance status with detailed checks

        Example:
            >>> status = await client.compliance.get_hipaa_status()
            >>> print(f"Compliance: {status.compliance_percentage}%")
            >>> for check in status.access_control:
            ...     if not check.passed:
            ...         print(f"Failed: {check.name} - {check.remediation}")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/compliance/hipaa/status",
        )
        return HIPAAStatus(**response)

    async def enable_hipaa(self) -> HIPAAEnableResult:
        """
        Enable HIPAA compliance mode.

        Applies all required HIPAA settings:
        - 15 minute session timeout
        - 12 character minimum password
        - Required MFA
        - Extended audit logging
        - Encryption at rest and in transit
        - 6 year audit retention
        - 5 attempt lockout, 30 minute duration

        Returns:
            HIPAAEnableResult: Enablement result with settings applied

        Note:
            Requires admin or owner role.
        """
        response = await self._http.request(
            "POST",
            "/api/v1/compliance/hipaa/enable",
        )
        return HIPAAEnableResult(**response)

    async def disable_hipaa(self, reason: str) -> HIPAADisableResult:
        """
        Disable HIPAA compliance mode.

        Args:
            reason: Reason for disabling (required for audit trail)

        Returns:
            HIPAADisableResult: Disablement result

        Warning:
            Disabling HIPAA mode may affect BAA compliance.
            A documented reason is required for audit purposes.
        """
        response = await self._http.request(
            "POST",
            "/api/v1/compliance/hipaa/disable",
            json_data={"reason": reason},
        )
        return HIPAADisableResult(**response)

    async def get_hipaa_settings(self) -> HIPAASettings:
        """
        Get current HIPAA settings.

        Returns:
            HIPAASettings: Current HIPAA configuration
        """
        response = await self._http.request(
            "GET",
            "/api/v1/compliance/hipaa/settings",
        )
        return HIPAASettings(**response)

    # SOC 2 Methods
    async def generate_soc2_evidence(
        self,
        start_date: str,
        end_date: str,
    ) -> SOC2Evidence:
        """
        Generate SOC 2 evidence package.

        Collects evidence for SOC 2 Type I/II audit preparation:
        - CC6: Logical and Physical Access Controls
        - CC7: System Operations
        - CC8: Change Management

        Args:
            start_date: Period start (ISO 8601)
            end_date: Period end (ISO 8601)

        Returns:
            SOC2Evidence: Evidence package

        Example:
            >>> evidence = await client.compliance.generate_soc2_evidence(
            ...     start_date="2024-01-01",
            ...     end_date="2024-03-31"
            ... )
            >>> print(f"CC6 items: {evidence.summary.cc6_items}")
            >>> print(f"CC7 items: {evidence.summary.cc7_items}")
            >>> print(f"CC8 items: {evidence.summary.cc8_items}")
        """
        response = await self._http.request(
            "POST",
            "/api/v1/compliance/soc2/evidence",
            json_data={
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return SOC2Evidence(**response)

    async def export_soc2_evidence(
        self,
        start_date: str,
        end_date: str,
    ) -> bytes:
        """
        Export SOC 2 evidence as downloadable file.

        Args:
            start_date: Period start (ISO 8601)
            end_date: Period end (ISO 8601)

        Returns:
            bytes: JSON file content
        """
        response: bytes = await self._http.request(
            "GET",
            "/api/v1/compliance/soc2/evidence/export",
            params={
                "start_date": start_date,
                "end_date": end_date,
            },
            raw_response=True,
        )
        return response

    # Retention Methods
    async def list_retention_policies(
        self,
        enabled: bool | None = None,
    ) -> list[RetentionPolicy]:
        """
        List retention policies.

        Args:
            enabled: Filter by enabled status

        Returns:
            List[RetentionPolicy]: Retention policies
        """
        params: dict[str, Any] = {}
        if enabled is not None:
            params["enabled"] = str(enabled).lower()

        response = await self._http.request(
            "GET",
            "/api/v1/compliance/retention/policies",
            params=params if params else None,
        )
        return [RetentionPolicy(**p) for p in response.get("policies", [])]

    async def get_retention_policy(self, policy_id: str) -> RetentionPolicy:
        """
        Get retention policy details.

        Args:
            policy_id: Policy ID

        Returns:
            RetentionPolicy: Policy details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/data-governance/retention/{encode_path_param(policy_id)}",
        )
        return RetentionPolicy(**response)

    async def create_retention_policy(
        self,
        name: str,
        retention_days: int,
        action_on_expiry: Literal["delete", "archive", "anonymize", "notify"],
        description: str | None = None,
        enabled: bool = True,
        archive_after_days: int | None = None,
        notify_before_days: int | None = None,
        notify_recipients: list[str] | None = None,
    ) -> RetentionPolicy:
        """
        Create retention policy.

        Args:
            name: Policy name
            retention_days: Days to retain data
            action_on_expiry: Action when data expires
            description: Policy description
            enabled: Whether policy is enabled
            archive_after_days: Days before archiving (optional)
            notify_before_days: Days before to notify
            notify_recipients: Email recipients for notifications

        Returns:
            RetentionPolicy: Created policy
        """
        data: dict[str, Any] = {
            "name": name,
            "retentionDays": retention_days,
            "actionOnExpiry": action_on_expiry,
            "enabled": enabled,
        }
        if description:
            data["description"] = description
        if archive_after_days is not None:
            data["archiveAfterDays"] = archive_after_days
        if notify_before_days is not None:
            data["notifyBeforeDays"] = notify_before_days
        if notify_recipients:
            data["notifyRecipients"] = notify_recipients

        response = await self._http.request(
            "POST",
            "/api/v1/data-governance/retention",
            json_data=data,
        )
        return RetentionPolicy(**response)

    async def update_retention_policy(
        self,
        policy_id: str,
        name: str | None = None,
        enabled: bool | None = None,
        retention_days: int | None = None,
        action_on_expiry: str | None = None,
    ) -> RetentionPolicy:
        """
        Update retention policy.

        Args:
            policy_id: Policy ID
            name: New name
            enabled: Enable/disable
            retention_days: New retention period
            action_on_expiry: New expiry action

        Returns:
            RetentionPolicy: Updated policy
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if enabled is not None:
            data["enabled"] = enabled
        if retention_days is not None:
            data["retentionDays"] = retention_days
        if action_on_expiry:
            data["actionOnExpiry"] = action_on_expiry

        response = await self._http.request(
            "PUT",
            f"/api/v1/data-governance/retention/{encode_path_param(policy_id)}",
            json_data=data,
        )
        return RetentionPolicy(**response)

    async def execute_retention(
        self,
        policy_id: str,
        dry_run: bool = True,
    ) -> RetentionExecutionResult:
        """
        Execute retention policy.

        Args:
            policy_id: Policy ID
            dry_run: If True, simulate without making changes

        Returns:
            RetentionExecutionResult: Execution result

        Example:
            >>> # Preview what would be affected
            >>> result = await client.compliance.execute_retention(
            ...     policy_id="pol-123",
            ...     dry_run=True
            ... )
            >>> print(f"Would affect {result.affected_count} records")
            >>>
            >>> # Execute for real
            >>> result = await client.compliance.execute_retention(
            ...     policy_id="pol-123",
            ...     dry_run=False
            ... )
        """
        response = await self._http.request(
            "POST",
            "/api/v1/compliance/retention/execute",
            json_data={
                "policy_id": policy_id,
                "dry_run": dry_run,
            },
        )
        return RetentionExecutionResult(**response)

    # Dashboard
    async def get_dashboard(self) -> ComplianceDashboard:
        """
        Get compliance dashboard summary.

        Returns:
            ComplianceDashboard: Summary across all compliance frameworks

        Example:
            >>> dashboard = await client.compliance.get_dashboard()
            >>> print(f"HIPAA: {dashboard.hipaa['compliancePercentage']}%")
        """
        response = await self._http.request(
            "GET",
            "/api/v1/compliance/dashboard",
        )
        return ComplianceDashboard(**response)

    # ------------------------------------------------------------------
    # Framework evaluation, scoring and reporting
    #
    # ⚠ THIS WHOLE SURFACE COMPUTES AND REPORTS. IT DOES NOT ENFORCE.
    #
    # Nothing in the platform's execution path consults these results before
    # allowing work: the compliance services are reachable only from this API
    # and from report generation. A framework at 0%, a failing control, or a
    # recorded violation does not stop an agent, block a deployment, or gate a
    # request. Treat every number here as EVIDENCE you can show an auditor —
    # which is its real value — and never as proof that something was
    # prevented. `list_violations` is the one that most invites the wrong
    # reading: it returns records of what an enforcement subsystem observed
    # elsewhere, not enforcement performed by this endpoint.
    #
    # All routes require `audit:read`; the two state-changing ones additionally
    # require a creator-class role.
    # ------------------------------------------------------------------

    async def get_chain_integrity(self) -> ChainIntegrity:
        """
        Read the most recent audit-chain verification sweep.

        Read-only: this does NOT start a sweep. The periodic background task is
        the authoritative scheduler; :meth:`verify_audit` is the on-demand walk.

        Returns:
            ChainIntegrity. **Check ``last_verified_at`` before reading
            ``ok``** — a cold start reports ``ok=False`` because nothing has run
            yet, which is not the same finding as a detected break.

        Example:
            >>> chain = await client.compliance.get_chain_integrity()
            >>> if not chain.ok and chain.last_verified_at is None:
            ...     print("not yet verified — no finding either way")
        """
        response = await self._http.request("GET", "/api/v1/compliance/chain/integrity")
        return ChainIntegrity(**response)

    async def get_trust_health(self) -> TrustHealth:
        """
        Get trust-chain health counters for the organization.

        Returns:
            TrustHealth. Read ``measured`` and ``percentage is None`` together —
            see the model docstring; do not coerce a null score to a number.

        Example:
            >>> health = await client.compliance.get_trust_health()
            >>> if health.percentage is None:
            ...     print("undetermined:", health.reason)
        """
        response = await self._http.request("GET", "/api/v1/compliance/health")
        return TrustHealth(**response)

    async def list_frameworks(self) -> dict[str, Any]:
        """
        List registered compliance frameworks with live-computed scores.

        Returns:
            ``{"frameworks": [...]}``. Scores are computed at read time from
            current control state, not read from a stored assessment.

        Example:
            >>> frameworks = (await client.compliance.list_frameworks())["frameworks"]
        """
        response: dict[str, Any] = await self._http.request("GET", "/api/v1/compliance/frameworks")
        return response

    async def get_framework(self, framework_id: str) -> dict[str, Any]:
        """
        Get the live-computed summary for one framework.

        Args:
            framework_id: Framework key, e.g. ``"soc2"``, ``"hipaa"``,
                ``"gdpr"``, ``"iso27001"``, ``"pci_dss"``.

        Returns:
            dict: The framework summary.

        Raises:
            NotFoundError: ``404`` — unknown framework key.
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/compliance/frameworks/{encode_path_param(framework_id)}"
        )
        return response

    async def get_framework_controls(self, framework_id: str) -> dict[str, Any]:
        """
        List the current control set for one framework.

        Args:
            framework_id: Framework key

        Returns:
            ``{"controls": [...]}``, each with a ``status`` such as
            ``compliant`` / ``non_compliant``. **An unconfigured control reports
            NON-COMPLIANT, not unknown** — the platform fails closed here rather
            than fabricating a pass, so a low score on a freshly-seeded
            framework means "no evidence configured yet", not "controls failed".

        Raises:
            NotFoundError: ``404`` — unknown framework key.
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/compliance/frameworks/{encode_path_param(framework_id)}/controls"
        )
        return response

    async def get_soc2_status(self) -> dict[str, Any]:
        """
        Evaluate SOC 2 status against the Trust Services Criteria.

        This is the EVALUATION surface. :meth:`generate_soc2_evidence` is the
        separate one that COLLECTS artifacts.

        Returns:
            dict (camelCase) with ``isCompliant``, ``compliancePercentage``,
            ``totalChecks``, ``passedChecks`` and per-rule ``checks``.
            Unconfigured controls count as failures, never as passes.

        Example:
            >>> status = await client.compliance.get_soc2_status()
            >>> print(status["compliancePercentage"], status["isCompliant"])
        """
        response: dict[str, Any] = await self._http.request("GET", "/api/v1/compliance/soc2/status")
        return response

    async def get_score(self) -> dict[str, Any]:
        """
        Get the overall compliance score across registered frameworks.

        Returns:
            dict with ``overall`` (a weighted average), ``trend``,
            ``trendValue`` and per-framework entries. The trend compares against
            the most recent stored assessment, so it is empty until
            :meth:`run_assessment` has been run at least twice.

        Example:
            >>> score = await client.compliance.get_score()
            >>> print(score["overall"], score["trend"])
        """
        response: dict[str, Any] = await self._http.request("GET", "/api/v1/compliance/score")
        return response

    async def list_events(
        self,
        framework: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List compliance timeline events.

        Args:
            framework: Filter by framework key
            event_type: One of ``assessment``, ``violation``, ``remediation``,
                ``audit``, ``report``. An unrecognized value is rejected with
                ``400`` rather than returning an empty page, so a typo cannot
                read as a clean timeline.
            limit: 1-200, default 50
            offset: Pagination offset

        Returns:
            ``{"events": [...], "total": int}``.

        Raises:
            ValidationError: ``400`` — unknown ``framework`` or ``event_type``.

        Example:
            >>> events = await client.compliance.list_events(framework="soc2")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if framework is not None:
            params["framework"] = framework
        if event_type is not None:
            params["type"] = event_type
        response: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/compliance/events", params=params
        )
        return response

    async def run_assessment(self, framework: str | None = None) -> dict[str, Any]:
        """
        Run a compliance assessment and record the result.

        This WRITES: an assessment record per framework, refreshed control rows,
        and one timeline event per framework plus one per non-compliant control
        found. It does not remediate anything and does not block anything — the
        violations it records are evidence, not enforcement.

        Args:
            framework: Assess one framework, or omit to assess all registered
                frameworks.

        Returns:
            ``{"assessed": [{"framework": ..., "overallScore": ..., ...}]}``.

        Raises:
            AuthorizationError: ``403`` — this needs a creator-class role in
                addition to ``audit:read``. The platform has no ``audit:write``
                action, so a state-changing compliance action is gated by role
                rather than by a write permission.
            ValidationError: ``400`` — unknown framework key.

        Example:
            >>> result = await client.compliance.run_assessment(framework="soc2")
        """
        body: dict[str, Any] = {"framework": framework} if framework is not None else {}
        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/compliance/assess", json_data=body
        )
        return response

    async def list_violations(
        self,
        severity: str | None = None,
        department_id: str | None = None,
        user_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List recorded constraint violations.

        These are records produced by the enforcement/surveillance subsystem.
        Reading them tells you what was OBSERVED; this endpoint enforces
        nothing, and an empty result is not evidence that nothing happened —
        only that nothing was recorded in the window you asked about.

        Args:
            severity: ``warning``, ``error`` or ``critical``
            department_id: Filter by department
            user_id: Filter by user
            start_date: ISO-8601 window start
            end_date: ISO-8601 window end
            limit: 1-200, default 50
            offset: Pagination offset

        Returns:
            dict: The matching violation records.

        Example:
            >>> violations = await client.compliance.list_violations(severity="critical")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for key, value in (
            ("severity", severity),
            ("departmentId", department_id),
            ("userId", user_id),
            ("startDate", start_date),
            ("endDate", end_date),
        ):
            if value is not None:
                params[key] = value
        response: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/compliance/violations", params=params
        )
        return response

    async def acknowledge_alert(self, alert_id: str) -> dict[str, Any]:
        """
        Acknowledge a compliance alert.

        Acknowledging HIDES the alert from the active view and records who did
        it. It does not remediate the underlying condition, and the condition
        will not re-raise the same alert. Acknowledge as a triage record, not
        as a fix.

        Args:
            alert_id: Alert ID

        Returns:
            dict: Confirmation with the alert id and the acknowledging user.

        Raises:
            NotFoundError: ``404`` — no such alert.
            ValidationError: ``400`` — already acknowledged.

        Example:
            >>> await client.compliance.acknowledge_alert("alert-123")
        """
        response: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/compliance/alerts/{encode_path_param(alert_id)}/acknowledge"
        )
        return response

    async def get_report_summary(self, period: str = "last-30-days") -> dict[str, Any]:
        """
        Get an aggregated compliance report summary.

        Args:
            period: Reporting window, e.g. ``"2026-Q1"``, ``"2026-04"``,
                ``"last-30-days"``.

        Returns:
            dict aggregating chain integrity, entry counts, retention state and
            per-policy violation counts.

            ⚠ ``chain_integrity`` here is THREE-valued —
            ``verified`` / ``broken`` / ``unverified``. An unwalked chain
            reports ``unverified``, which is neither a pass nor a failure.
            Any code branching on ``== "verified"`` else "broken" will
            mis-report the third case.

        Example:
            >>> summary = await client.compliance.get_report_summary(period="2026-Q1")
        """
        response: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/compliance/report/summary", params={"period": period}
        )
        return response

    async def get_report(self, period: str) -> dict[str, Any]:
        """
        Get the JSON compliance report for a calendar month.

        Args:
            period: Period in ``YYYY-MM`` form, e.g. ``"2026-05"``. Unlike
                :meth:`get_report_summary`, relative windows are not accepted.

        Returns:
            dict: The generated report.

        Example:
            >>> report = await client.compliance.get_report("2026-05")
        """
        response: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/compliance/reports", params={"period": period}
        )
        return response

    async def get_report_pdf(self, period: str) -> bytes:
        """
        Download the compliance report for a month as a PDF.

        Args:
            period: Period in ``YYYY-MM`` form.

        Returns:
            bytes: The PDF document. Write it with ``"wb"``; it is not JSON.

        Example:
            >>> pdf = await client.compliance.get_report_pdf("2026-05")
            >>> with open("compliance-2026-05.pdf", "wb") as f:
            ...     f.write(pdf)
        """
        response: bytes = await self._http.request(
            "GET",
            f"/api/v1/compliance/reports/{encode_path_param(period)}.pdf",
            raw_response=True,
        )
        return response

    async def create_report(
        self,
        framework: str,
        format: Literal["pdf", "json"] = "pdf",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Request a compliance report and get a download URL back.

        This does NOT return a report body. It resolves a URL pointing at the
        period-based generators — :meth:`get_report_pdf` for ``pdf``,
        :meth:`get_report` for ``json`` — so the response is a pointer, and the
        document is produced when you fetch it.

        Args:
            framework: Framework key. Note the framework selects the report's
                subject only; the generators underneath are period-based.
            format: ``"pdf"`` or ``"json"``. ``"csv"`` is **rejected with 400**
                rather than silently substituted — no generator backs it.
            start_date: ISO-8601 start, used to derive the period
            end_date: ISO-8601 end

        Returns:
            ``{"downloadUrl": "/api/v1/compliance/reports/<period>.pdf"}``.

        Raises:
            ValidationError: ``400`` — unknown framework, or a format other
                than ``pdf``/``json``.

        Example:
            >>> ref = await client.compliance.create_report(
            ...     framework="soc2", format="pdf", start_date="2026-06-01"
            ... )
            >>> print(ref["downloadUrl"])
        """
        body: dict[str, Any] = {"framework": framework, "format": format}
        if start_date is not None:
            body["startDate"] = start_date
        if end_date is not None:
            body["endDate"] = end_date
        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/compliance/reports", json_data=body
        )
        return response

    async def export_report(
        self,
        format: Literal["json", "csv", "pdf"] = "json",
        mask_level: Literal["none", "betriebsrat", "gdpr_export"] | None = None,
        filter: dict[str, Any] | None = None,
        include_audit_events: bool = True,
        include_violations: bool = True,
        include_trust_health: bool = True,
    ) -> bytes:
        """
        Export a combined compliance report as a file.

        Combines trust-health metrics, constraint violations and audit events
        into one document.

        Args:
            format: ``"json"``, ``"csv"`` or ``"pdf"``
            mask_level: PII masking applied to the exported audit events.
                **Omitting this does not mean "safe" — the default is
                ROLE-DEPENDENT**: an admin-class caller defaults to ``"none"``
                (unmasked personal data), everyone else to ``"betriebsrat"``.
                Pass the level explicitly whenever the export leaves your
                control or its audience is not the caller.
            filter: Optional filter parameters
            include_audit_events: Include audit events
            include_violations: Include constraint violations
            include_trust_health: Include trust-health metrics

        Returns:
            bytes: The exported document.

        Example:
            >>> data = await client.compliance.export_report(
            ...     format="csv", mask_level="gdpr_export"
            ... )
            >>> with open("compliance.csv", "wb") as f:
            ...     f.write(data)
        """
        body: dict[str, Any] = {
            "format": format,
            "includeAuditEvents": include_audit_events,
            "includeViolations": include_violations,
            "includeTrustHealth": include_trust_health,
        }
        if filter is not None:
            body["filter"] = filter
        params = {"mask_level": mask_level} if mask_level is not None else None
        response: bytes = await self._http.request(
            "POST",
            "/api/v1/compliance/export",
            json_data=body,
            params=params,
            raw_response=True,
        )
        return response
