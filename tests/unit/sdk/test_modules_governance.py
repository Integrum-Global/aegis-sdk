"""
Unit tests for SDK governance module.

Tests GovernanceModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.modules.governance import (
    AccessEvaluation,
    AccessPolicy,
    Classification,
    Consent,
    GovernanceModule,
    LineageGraph,
    LineageNode,
    Permission,
    PermissionCheck,
    Role,
    UserPermissions,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def governance_module(mock_http):
    """Create GovernanceModule with mock HTTP client."""
    return GovernanceModule(mock_http)


def make_permission_response():
    """Create permission response."""
    return {
        "id": "perm-123",
        "name": "agents:read",
        "resource": "agents",
        "action": "read",
        "description": "Read agent information",
    }


def make_role_response(is_system=True):
    """Create role response."""
    return {
        "id": "role-456",
        "name": "developer",
        "description": "Developer role",
        "permissions": ["agents:read", "agents:create", "deployments:*"],
        "isSystem": is_system,
        "memberCount": 15,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_classification_response(level=3):
    """Create classification response."""
    return {
        "id": "class-789",
        "organizationId": "org-123",
        "name": "Confidential",
        "level": level,
        "description": "Confidential business data",
        "color": "#ff6b6b",
        "requiresConsent": True,
        "requiresEncryption": True,
        "allowsExport": False,
        "auditAccess": True,
        "retentionDefaultDays": 365,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_policy_response(effect="allow"):
    """Create access policy response."""
    return {
        "id": "pol-123",
        "organizationId": "org-456",
        "name": "Confidential Data Access",
        "description": "Policy for confidential data",
        "enabled": True,
        "priority": 10,
        "effect": effect,
        "classifications": ["confidential"],
        "principals": {"roles": ["data_analyst"]},
        "actions": ["read"],
        "requiresMfa": True,
        "requiresJustification": False,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_evaluation_response(allowed=True):
    """Create access evaluation response."""
    return {
        "allowed": allowed,
        "policyId": "pol-123" if not allowed else None,
        "reason": "Access granted" if allowed else "Policy denied",
        "requiresMfa": not allowed,
        "requiresJustification": not allowed,
        "maxDurationMinutes": 60 if allowed else None,
    }


def make_consent_response():
    """Create consent response."""
    return {
        "id": "consent-123",
        "organizationId": "org-456",
        "subjectId": "user-789",
        "subjectEmail": "user@example.com",
        "subjectType": "customer",
        "purpose": "marketing",
        "purposeCategory": "marketing",
        "legalBasis": "consent",
        "dataCategories": ["email", "name"],
        "processingActivities": ["email_campaigns"],
        "consentGiven": True,
        "consentMethod": "web_form",
        "version": "1.0",
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_lineage_graph_response():
    """Create lineage graph response."""
    return {
        "nodes": [
            {"id": "node-1", "name": "Source DB", "nodeType": "source"},
            {"id": "node-2", "name": "Transform", "nodeType": "transform"},
        ],
        "edges": [
            {"id": "edge-1", "sourceId": "node-1", "targetId": "node-2", "edgeType": "feeds_into"}
        ],
        "rootId": "node-1",
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestGovernanceModuleRBAC:
    """Test RBAC operations."""

    async def test_list_permissions(self, mock_http, governance_module):
        """list_permissions() should return permissions."""
        mock_http.request = AsyncMock(return_value={"permissions": [make_permission_response()]})

        result = await governance_module.list_permissions()

        assert len(result) == 1
        assert isinstance(result[0], Permission)
        assert result[0].name == "agents:read"

    async def test_list_roles(self, mock_http, governance_module):
        """list_roles() should return roles."""
        mock_http.request = AsyncMock(return_value={"records": [make_role_response()]})

        result = await governance_module.list_roles()

        assert len(result) == 1
        assert isinstance(result[0], Role)
        assert result[0].name == "developer"
        assert result[0].is_system is True

    async def test_list_roles_with_search(self, mock_http, governance_module):
        """list_roles() should accept search parameter."""
        mock_http.request = AsyncMock(return_value={"records": []})

        await governance_module.list_roles(search="admin", include_system=False)

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["search"] == "admin"
        assert call_args[1]["params"]["include_system"] == "false"

    async def test_get_role(self, mock_http, governance_module):
        """get_role() should return role details."""
        mock_http.request = AsyncMock(return_value=make_role_response())

        result = await governance_module.get_role("developer")

        assert isinstance(result, Role)
        assert "agents:read" in result.permissions

    async def test_add_permission(self, mock_http, governance_module):
        """add_permission() should add permission to role."""
        mock_http.request = AsyncMock(return_value=make_role_response())

        result = await governance_module.add_permission("developer", "perm-new")

        assert isinstance(result, Role)
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json_data"]["permissionId"] == "perm-new"

    async def test_remove_permission(self, mock_http, governance_module):
        """remove_permission() should remove permission from role."""
        mock_http.request = AsyncMock(return_value=make_role_response())

        result = await governance_module.remove_permission("developer", "perm-123")

        assert isinstance(result, Role)
        mock_http.request.assert_called_once_with(
            "DELETE",
            "/api/v1/rbac/roles/developer/perm-123",
        )

    async def test_delete_role(self, mock_http, governance_module):
        """delete_role() should delete custom role."""
        mock_http.request = AsyncMock(return_value={})

        result = await governance_module.delete_role("custom-role")

        assert result is True

    async def test_get_user_permissions(self, mock_http, governance_module):
        """get_user_permissions() should return user's permissions."""
        mock_http.request = AsyncMock(
            return_value={"userId": "user-123", "permissions": ["agents:read"]}
        )

        result = await governance_module.get_user_permissions("user-123")

        assert isinstance(result, UserPermissions)
        assert result.user_id == "user-123"
        assert "agents:read" in result.permissions

    async def test_check_permission_allowed(self, mock_http, governance_module):
        """check_permission() should return the allowed flag + reason."""
        mock_http.request = AsyncMock(return_value={"allowed": True, "reason": None})

        result = await governance_module.check_permission("user-123", "agents:read")

        assert isinstance(result, PermissionCheck)
        assert result.allowed is True
        assert result.reason is None
        call_args = mock_http.request.call_args
        assert call_args[0] == ("POST", "/api/v1/rbac/check-permission")
        assert call_args[1]["json_data"] == {
            "user_id": "user-123",
            "permission": "agents:read",
        }

    async def test_check_permission_denied_with_resource(self, mock_http, governance_module):
        """check_permission() should forward the optional resource + surface reason."""
        mock_http.request = AsyncMock(
            return_value={
                "allowed": False,
                "reason": "User does not have permission 'agents:delete'",
            }
        )

        result = await governance_module.check_permission(
            "user-123", "agents:delete", resource="agent-9"
        )

        assert isinstance(result, PermissionCheck)
        assert result.allowed is False
        assert "agents:delete" in result.reason
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"] == {
            "user_id": "user-123",
            "permission": "agents:delete",
            "resource": "agent-9",
        }


@pytest.mark.unit
@pytest.mark.asyncio
class TestGovernanceModuleClassifications:
    """Test classification operations."""

    async def test_list_classifications(self, mock_http, governance_module):
        """list_classifications() should return classifications."""
        mock_http.request = AsyncMock(
            return_value={"classifications": [make_classification_response()]}
        )

        result = await governance_module.list_classifications()

        assert len(result) == 1
        assert isinstance(result[0], Classification)
        assert result[0].level == 3

    async def test_list_classifications_by_min_level(self, mock_http, governance_module):
        """list_classifications() should filter by min level."""
        mock_http.request = AsyncMock(return_value={"classifications": []})

        await governance_module.list_classifications(min_level=3)

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["min_level"] == 3

    async def test_get_classification(self, mock_http, governance_module):
        """get_classification() should return details."""
        mock_http.request = AsyncMock(return_value=make_classification_response())

        result = await governance_module.get_classification("class-789")

        assert isinstance(result, Classification)
        assert result.name == "Confidential"

    async def test_create_classification(self, mock_http, governance_module):
        """create_classification() should create classification."""
        mock_http.request = AsyncMock(return_value=make_classification_response())

        result = await governance_module.create_classification(
            name="Confidential",
            level=3,
            description="Confidential data",
            requires_encryption=True,
        )

        assert isinstance(result, Classification)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["name"] == "Confidential"
        assert call_args[1]["json_data"]["level"] == 3
        assert call_args[1]["json_data"]["requiresEncryption"] is True

    async def test_update_classification(self, mock_http, governance_module):
        """update_classification() should update classification."""
        mock_http.request = AsyncMock(return_value=make_classification_response())

        result = await governance_module.update_classification(
            classification_id="class-789",
            name="Updated Name",
        )

        assert isinstance(result, Classification)

    async def test_delete_classification(self, mock_http, governance_module):
        """delete_classification() should delete classification."""
        mock_http.request = AsyncMock(return_value={})

        result = await governance_module.delete_classification("class-789")

        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestGovernanceModulePolicies:
    """Test access policy operations."""

    async def test_list_policies(self, mock_http, governance_module):
        """list_policies() should return policies."""
        mock_http.request = AsyncMock(return_value={"policies": [make_policy_response()]})

        result = await governance_module.list_policies()

        assert len(result) == 1
        assert isinstance(result[0], AccessPolicy)
        assert result[0].effect == "allow"

    async def test_list_policies_by_enabled(self, mock_http, governance_module):
        """list_policies() should filter by enabled."""
        mock_http.request = AsyncMock(return_value={"policies": []})

        await governance_module.list_policies(enabled=True)

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["enabled"] == "true"

    async def test_get_policy(self, mock_http, governance_module):
        """get_policy() should return policy details."""
        mock_http.request = AsyncMock(return_value=make_policy_response())

        result = await governance_module.get_policy("pol-123")

        assert isinstance(result, AccessPolicy)
        assert result.requires_mfa is True

    async def test_create_policy(self, mock_http, governance_module):
        """create_policy() should create policy."""
        mock_http.request = AsyncMock(return_value=make_policy_response())

        result = await governance_module.create_policy(
            name="Confidential Data Access",
            effect="allow",
            classifications=["confidential"],
            principals={"roles": ["data_analyst"]},
            requires_mfa=True,
        )

        assert isinstance(result, AccessPolicy)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["name"] == "Confidential Data Access"
        assert call_args[1]["json_data"]["effect"] == "allow"
        assert call_args[1]["json_data"]["requiresMfa"] is True

    async def test_update_policy(self, mock_http, governance_module):
        """update_policy() should update policy."""
        mock_http.request = AsyncMock(return_value=make_policy_response())

        result = await governance_module.update_policy(
            policy_id="pol-123",
            enabled=False,
        )

        assert isinstance(result, AccessPolicy)

    async def test_delete_policy(self, mock_http, governance_module):
        """delete_policy() should delete policy."""
        mock_http.request = AsyncMock(return_value={})

        result = await governance_module.delete_policy("pol-123")

        assert result is True

    async def test_evaluate_access_allowed(self, mock_http, governance_module):
        """evaluate_access() should return allowed result."""
        mock_http.request = AsyncMock(return_value=make_evaluation_response(allowed=True))

        result = await governance_module.evaluate_access(
            accessor_id="user-123",
            accessor_type="user",
            resource_type="document",
            resource_id="doc-456",
            action="read",
        )

        assert isinstance(result, AccessEvaluation)
        assert result.allowed is True

    async def test_evaluate_access_denied(self, mock_http, governance_module):
        """evaluate_access() should return denied result."""
        mock_http.request = AsyncMock(return_value=make_evaluation_response(allowed=False))

        result = await governance_module.evaluate_access(
            accessor_id="user-123",
            accessor_type="user",
            resource_type="document",
            resource_id="doc-456",
            action="delete",
            classification_level=4,
        )

        assert result.allowed is False
        assert result.requires_mfa is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestGovernanceModuleConsents:
    """Test consent operations."""

    async def test_list_consents(self, mock_http, governance_module):
        """list_consents() should return consents."""
        mock_http.request = AsyncMock(return_value={"consents": [make_consent_response()]})

        result = await governance_module.list_consents()

        assert len(result) == 1
        assert isinstance(result[0], Consent)
        assert result[0].consent_given is True

    async def test_list_consents_by_subject(self, mock_http, governance_module):
        """list_consents() should filter by subject."""
        mock_http.request = AsyncMock(return_value={"consents": []})

        await governance_module.list_consents(subject_id="user-789")

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["subjectId"] == "user-789"

    async def test_get_consent(self, mock_http, governance_module):
        """get_consent() should return consent details."""
        mock_http.request = AsyncMock(return_value=make_consent_response())

        result = await governance_module.get_consent("consent-123")

        assert isinstance(result, Consent)
        assert result.purpose == "marketing"

    async def test_record_consent(self, mock_http, governance_module):
        """record_consent() should record new consent."""
        mock_http.request = AsyncMock(return_value=make_consent_response())

        result = await governance_module.record_consent(
            subject_id="user-789",
            subject_type="customer",
            purpose="marketing",
            purpose_category="marketing",
            legal_basis="consent",
            data_categories=["email", "name"],
            processing_activities=["email_campaigns"],
            consent_given=True,
            consent_method="web_form",
        )

        assert isinstance(result, Consent)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["subjectId"] == "user-789"
        assert call_args[1]["json_data"]["consentGiven"] is True

    async def test_withdraw_consent(self, mock_http, governance_module):
        """withdraw_consent() should withdraw consent."""
        response = make_consent_response()
        response["withdrawnAt"] = "2024-01-20T10:00:00Z"
        mock_http.request = AsyncMock(return_value=response)

        result = await governance_module.withdraw_consent("consent-123")

        assert isinstance(result, Consent)
        assert result.withdrawn_at is not None

    async def test_check_consent(self, mock_http, governance_module):
        """check_consent() should check if valid consent exists."""
        mock_http.request = AsyncMock(return_value={"valid": True})

        result = await governance_module.check_consent(
            subject_id="user-789",
            purpose="marketing",
            data_category="email",
        )

        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestGovernanceModuleLineage:
    """Test data lineage operations."""

    async def test_get_lineage(self, mock_http, governance_module):
        """get_lineage() should return lineage graph."""
        mock_http.request = AsyncMock(return_value=make_lineage_graph_response())

        result = await governance_module.get_lineage(
            root_type="table",
            root_id="table-123",
        )

        assert isinstance(result, LineageGraph)
        assert len(result.nodes) == 2
        assert len(result.edges) == 1

    async def test_get_lineage_with_options(self, mock_http, governance_module):
        """get_lineage() should accept depth and direction."""
        mock_http.request = AsyncMock(return_value=make_lineage_graph_response())

        await governance_module.get_lineage(
            root_type="table",
            root_id="table-123",
            depth=5,
            direction="downstream",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["depth"] == 5
        assert call_args[1]["params"]["direction"] == "downstream"

    async def test_get_lineage_impact(self, mock_http, governance_module):
        """get_lineage_impact() should return impacted nodes."""
        mock_http.request = AsyncMock(
            return_value={
                "nodes": [{"id": "node-2", "name": "Downstream", "nodeType": "destination"}]
            }
        )

        result = await governance_module.get_lineage_impact("node-1")

        assert len(result) == 1
        assert isinstance(result[0], LineageNode)
