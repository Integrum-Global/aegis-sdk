"""
Unit tests for SDK compliance module.

Tests ComplianceModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.modules.compliance import (
    AuditEntry,
    AuditVerificationResult,
    ComplianceDashboard,
    ComplianceModule,
    HIPAADisableResult,
    HIPAAEnableResult,
    HIPAASettings,
    HIPAAStatus,
    RetentionExecutionResult,
    RetentionPolicy,
    SOC2Evidence,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def compliance_module(mock_http):
    """Create ComplianceModule with mock HTTP client."""
    return ComplianceModule(mock_http)


def make_audit_verification_response(valid=True):
    """Create audit verification response."""
    return {
        "valid": valid,
        "entriesChecked": 1000,
        "firstInvalidId": None if valid else "entry-500",
        "error": None if valid else "Hash mismatch detected",
    }


def make_audit_entry_response():
    """Create audit entry response."""
    return {
        "id": "audit-123",
        "timestamp": "2024-01-15T10:00:00Z",
        "organizationId": "org-456",
        "userId": "user-789",
        "agentId": None,
        "action": "login",
        "resourceType": "session",
        "resourceId": "session-001",
        "result": "success",
        "details": {"ip": "192.168.1.1"},
        "ipAddress": "192.168.1.1",
        "userAgent": "Mozilla/5.0",
        "sessionId": "sess-abc",
        "previousHash": "abc123",
        "entryHash": "def456",
        "sequenceNumber": 1000,
    }


def make_hipaa_status_response(compliant=True):
    """Create HIPAA status response."""
    return {
        "organizationId": "org-123",
        "isCompliant": compliant,
        "hipaaModeEnabled": True,
        "checkedAt": "2024-01-15T10:00:00Z",
        "totalChecks": 15,
        "passedChecks": 15 if compliant else 12,
        "compliancePercentage": 100.0 if compliant else 80.0,
        "accessControl": [
            {"name": "MFA Required", "passed": True, "requirement": "45 CFR 164.312(d)"}
        ],
        "auditControls": [
            {"name": "Audit Logging", "passed": True, "requirement": "45 CFR 164.312(b)"}
        ],
        "integrityControls": [
            {"name": "Encryption at Rest", "passed": True, "requirement": "45 CFR 164.312(c)"}
        ],
        "transmissionSecurity": [
            {"name": "TLS Required", "passed": True, "requirement": "45 CFR 164.312(e)"}
        ],
    }


def make_hipaa_settings_response():
    """Create HIPAA settings response."""
    return {
        "hipaaModeEnabled": True,
        "hipaaEnabledAt": "2024-01-01T00:00:00Z",
        "hipaaEnabledBy": "admin-123",
        "sessionTimeoutMinutes": 15,
        "passwordMinLength": 12,
        "requireMfa": True,
        "auditLoggingExtended": True,
        "encryptionAtRestEnabled": True,
        "encryptionInTransitEnabled": True,
        "auditLogRetentionYears": 6,
        "accountLockoutAttempts": 5,
        "accountLockoutMinutes": 30,
    }


def make_hipaa_enable_response():
    """Create HIPAA enable response."""
    return {
        "organizationId": "org-123",
        "hipaaModeEnabled": True,
        "enabledAt": "2024-01-15T10:00:00Z",
        "enabledBy": "admin-123",
        "settingsApplied": {
            "sessionTimeoutMinutes": 15,
            "requireMfa": True,
        },
    }


def make_hipaa_disable_response():
    """Create HIPAA disable response."""
    return {
        "organizationId": "org-123",
        "hipaaModeEnabled": False,
        "disabledAt": "2024-01-15T10:00:00Z",
        "disabledBy": "admin-123",
        "reason": "Migrating to new compliance framework",
    }


def make_soc2_evidence_response():
    """Create SOC 2 evidence response."""
    return {
        "generatedAt": "2024-01-15T10:00:00Z",
        "periodStart": "2024-01-01",
        "periodEnd": "2024-03-31",
        "summary": {
            "organizationId": "org-123",
            "totalEvidenceItems": 150,
            "cc6Items": 50,
            "cc7Items": 60,
            "cc8Items": 40,
            "periodDays": 90,
        },
        "cc6AccessControls": [
            {
                "type": "user_access_list",
                "timestamp": "2024-01-15T10:00:00Z",
                "description": "Current user access inventory",
                "evidenceData": {"users": 50},
                "controlReference": "CC6.1",
            }
        ],
        "cc7SystemOperations": [
            {
                "type": "monitoring_alert",
                "timestamp": "2024-01-15T10:00:00Z",
                "description": "Security monitoring active",
                "evidenceData": {"alerts": 10},
                "controlReference": "CC7.1",
            }
        ],
        "cc8ChangeManagement": [
            {
                "type": "deployment_log",
                "timestamp": "2024-01-15T10:00:00Z",
                "description": "Deployment approval records",
                "evidenceData": {"deployments": 25},
                "controlReference": "CC8.1",
            }
        ],
    }


def make_retention_policy_response():
    """Create retention policy response."""
    return {
        "id": "ret-123",
        "organizationId": "org-456",
        "name": "Audit Log Retention",
        "description": "Retain audit logs for 6 years",
        "enabled": True,
        "retentionDays": 2190,
        "actionOnExpiry": "archive",
        "archiveAfterDays": 365,
        "notifyBeforeDays": 30,
        "notifyRecipients": ["admin@example.com"],
        "legalHold": False,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_retention_execution_response():
    """Create retention execution response."""
    return {
        "affectedCount": 500,
        "action": "archive",
        "dryRun": True,
    }


def make_dashboard_response():
    """Create compliance dashboard response."""
    return {
        "organizationId": "org-123",
        "hipaa": {
            "enabled": True,
            "compliant": True,
            "compliancePercentage": 100.0,
            "passedChecks": 15,
            "totalChecks": 15,
        },
        "dataGovernance": {
            "classifications": 4,
            "policies": 10,
            "consents": 500,
        },
        "lastUpdated": "2024-01-15T10:00:00Z",
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestComplianceModuleAudit:
    """Test audit operations."""

    async def test_verify_audit_valid(self, mock_http, compliance_module):
        """verify_audit() should return valid result."""
        mock_http.request = AsyncMock(return_value=make_audit_verification_response(valid=True))

        result = await compliance_module.verify_audit()

        assert isinstance(result, AuditVerificationResult)
        assert result.valid is True
        assert result.entries_checked == 1000
        assert result.first_invalid_id is None

    async def test_verify_audit_invalid(self, mock_http, compliance_module):
        """verify_audit() should detect tampering."""
        mock_http.request = AsyncMock(return_value=make_audit_verification_response(valid=False))

        result = await compliance_module.verify_audit()

        assert result.valid is False
        assert result.first_invalid_id == "entry-500"

    async def test_verify_audit_with_range(self, mock_http, compliance_module):
        """verify_audit() should accept ID range."""
        mock_http.request = AsyncMock(return_value=make_audit_verification_response())

        await compliance_module.verify_audit(
            start_id="entry-100",
            end_id="entry-500",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["start_id"] == "entry-100"
        assert call_args[1]["params"]["end_id"] == "entry-500"

    async def test_export_audit(self, mock_http, compliance_module):
        """export_audit() should return binary data."""
        mock_http.request = AsyncMock(return_value=b"csv,data,here")

        result = await compliance_module.export_audit(
            start_date="2024-01-01",
            end_date="2024-01-31",
            format="csv",
        )

        assert result == b"csv,data,here"
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["format"] == "csv"
        assert call_args[1]["raw_response"] is True

    async def test_list_audit_entries(self, mock_http, compliance_module):
        """list_audit_entries() should return entries."""
        mock_http.request = AsyncMock(return_value={"entries": [make_audit_entry_response()]})

        result = await compliance_module.list_audit_entries()

        assert len(result) == 1
        assert isinstance(result[0], AuditEntry)
        assert result[0].action == "login"

    async def test_list_audit_entries_with_filters(self, mock_http, compliance_module):
        """list_audit_entries() should accept filters."""
        mock_http.request = AsyncMock(return_value={"entries": []})

        await compliance_module.list_audit_entries(
            action="login",
            resource_type="session",
            start_date="2024-01-01",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["action"] == "login"
        assert call_args[1]["params"]["resource_type"] == "session"


@pytest.mark.unit
@pytest.mark.asyncio
class TestComplianceModuleHIPAA:
    """Test HIPAA operations."""

    async def test_get_hipaa_status_compliant(self, mock_http, compliance_module):
        """get_hipaa_status() should return compliant status."""
        mock_http.request = AsyncMock(return_value=make_hipaa_status_response(compliant=True))

        result = await compliance_module.get_hipaa_status()

        assert isinstance(result, HIPAAStatus)
        assert result.is_compliant is True
        assert result.compliance_percentage == 100.0
        assert len(result.access_control) == 1

    async def test_get_hipaa_status_non_compliant(self, mock_http, compliance_module):
        """get_hipaa_status() should report non-compliance."""
        mock_http.request = AsyncMock(return_value=make_hipaa_status_response(compliant=False))

        result = await compliance_module.get_hipaa_status()

        assert result.is_compliant is False
        assert result.passed_checks < result.total_checks

    async def test_enable_hipaa(self, mock_http, compliance_module):
        """enable_hipaa() should enable HIPAA mode."""
        mock_http.request = AsyncMock(return_value=make_hipaa_enable_response())

        result = await compliance_module.enable_hipaa()

        assert isinstance(result, HIPAAEnableResult)
        assert result.hipaa_mode_enabled is True
        assert "sessionTimeoutMinutes" in result.settings_applied

    async def test_disable_hipaa(self, mock_http, compliance_module):
        """disable_hipaa() should disable HIPAA mode."""
        mock_http.request = AsyncMock(return_value=make_hipaa_disable_response())

        result = await compliance_module.disable_hipaa(
            reason="Migrating to new compliance framework"
        )

        assert isinstance(result, HIPAADisableResult)
        assert result.hipaa_mode_enabled is False
        assert result.reason == "Migrating to new compliance framework"

    async def test_get_hipaa_settings(self, mock_http, compliance_module):
        """get_hipaa_settings() should return settings."""
        mock_http.request = AsyncMock(return_value=make_hipaa_settings_response())

        result = await compliance_module.get_hipaa_settings()

        assert isinstance(result, HIPAASettings)
        assert result.hipaa_mode_enabled is True
        assert result.session_timeout_minutes == 15
        assert result.require_mfa is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestComplianceModuleSOC2:
    """Test SOC 2 operations."""

    async def test_generate_soc2_evidence(self, mock_http, compliance_module):
        """generate_soc2_evidence() should return evidence package."""
        mock_http.request = AsyncMock(return_value=make_soc2_evidence_response())

        result = await compliance_module.generate_soc2_evidence(
            start_date="2024-01-01",
            end_date="2024-03-31",
        )

        assert isinstance(result, SOC2Evidence)
        assert result.summary.total_evidence_items == 150
        assert len(result.cc6_access_controls) == 1
        assert len(result.cc7_system_operations) == 1
        assert len(result.cc8_change_management) == 1

    async def test_export_soc2_evidence(self, mock_http, compliance_module):
        """export_soc2_evidence() should return binary data."""
        mock_http.request = AsyncMock(return_value=b'{"evidence": "data"}')

        result = await compliance_module.export_soc2_evidence(
            start_date="2024-01-01",
            end_date="2024-03-31",
        )

        assert result == b'{"evidence": "data"}'
        call_args = mock_http.request.call_args
        assert call_args[1]["raw_response"] is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestComplianceModuleRetention:
    """Test retention policy operations."""

    async def test_list_retention_policies(self, mock_http, compliance_module):
        """list_retention_policies() should return policies."""
        mock_http.request = AsyncMock(return_value={"policies": [make_retention_policy_response()]})

        result = await compliance_module.list_retention_policies()

        assert len(result) == 1
        assert isinstance(result[0], RetentionPolicy)
        assert result[0].retention_days == 2190

    async def test_list_retention_policies_by_enabled(self, mock_http, compliance_module):
        """list_retention_policies() should filter by enabled."""
        mock_http.request = AsyncMock(return_value={"policies": []})

        await compliance_module.list_retention_policies(enabled=True)

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["enabled"] == "true"

    async def test_get_retention_policy(self, mock_http, compliance_module):
        """get_retention_policy() should return policy."""
        mock_http.request = AsyncMock(return_value=make_retention_policy_response())

        result = await compliance_module.get_retention_policy("ret-123")

        assert isinstance(result, RetentionPolicy)
        assert result.action_on_expiry == "archive"

    async def test_create_retention_policy(self, mock_http, compliance_module):
        """create_retention_policy() should create policy."""
        mock_http.request = AsyncMock(return_value=make_retention_policy_response())

        result = await compliance_module.create_retention_policy(
            name="Audit Log Retention",
            retention_days=2190,
            action_on_expiry="archive",
        )

        assert isinstance(result, RetentionPolicy)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["name"] == "Audit Log Retention"
        assert call_args[1]["json_data"]["retentionDays"] == 2190

    async def test_update_retention_policy(self, mock_http, compliance_module):
        """update_retention_policy() should update policy."""
        mock_http.request = AsyncMock(return_value=make_retention_policy_response())

        result = await compliance_module.update_retention_policy(
            policy_id="ret-123",
            enabled=False,
        )

        assert isinstance(result, RetentionPolicy)

    async def test_execute_retention_dry_run(self, mock_http, compliance_module):
        """execute_retention() should preview changes."""
        mock_http.request = AsyncMock(return_value=make_retention_execution_response())

        result = await compliance_module.execute_retention(
            policy_id="ret-123",
            dry_run=True,
        )

        assert isinstance(result, RetentionExecutionResult)
        assert result.affected_count == 500
        assert result.dry_run is True

    async def test_execute_retention_actual(self, mock_http, compliance_module):
        """execute_retention() should execute changes."""
        response = make_retention_execution_response()
        response["dryRun"] = False
        mock_http.request = AsyncMock(return_value=response)

        result = await compliance_module.execute_retention(
            policy_id="ret-123",
            dry_run=False,
        )

        assert result.dry_run is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestComplianceModuleDashboard:
    """Test dashboard operations."""

    async def test_get_dashboard(self, mock_http, compliance_module):
        """get_dashboard() should return summary."""
        mock_http.request = AsyncMock(return_value=make_dashboard_response())

        result = await compliance_module.get_dashboard()

        assert isinstance(result, ComplianceDashboard)
        assert result.hipaa["enabled"] is True
        assert result.hipaa["compliant"] is True
        assert result.data_governance["classifications"] == 4
