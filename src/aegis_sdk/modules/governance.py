"""
Governance Module for Agentic OS SDK.

Provides governance, RBAC, policies, and data classification management.

26 methods:
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
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param


class Permission(BaseModel):
    """Permission model."""

    id: str
    name: str
    resource: str
    action: str
    description: str | None = None


class Role(BaseModel):
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


class UserPermissions(BaseModel):
    """User permissions response."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    permissions: list[str]


class PermissionCheck(BaseModel):
    """Result of a single permission check.

    Wire shape verified against ``CheckPermissionResponse`` at -- snake_case, NO Pydantic alias
    generator (``{"allowed": bool, "reason": str | None}``).
    """

    allowed: bool
    reason: str | None = None


class HandlingRequirements(BaseModel):
    """Data handling requirements."""

    model_config = ConfigDict(populate_by_name=True)

    encryption: bool = False
    masking: bool = False
    access_control_required: bool = Field(False, alias="accessControlRequired")
    audit_logging: bool = Field(False, alias="auditLogging")


class Classification(BaseModel):
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


class PolicyCondition(BaseModel):
    """ABAC policy condition."""

    field: str
    operator: str  # eq, ne, gt, lt, in, contains
    value: Any


class PolicyPrincipals(BaseModel):
    """Policy principals (who the policy applies to)."""

    users: list[str] | None = None
    roles: list[str] | None = None
    teams: list[str] | None = None
    agents: list[str] | None = None


class PolicyResources(BaseModel):
    """Policy resources (what the policy applies to)."""

    model_config = ConfigDict(populate_by_name=True)

    patterns: list[str] | None = None
    types: list[str] | None = None
    work_units: list[str] | None = Field(None, alias="workUnits")


class TimeRestrictions(BaseModel):
    """Time-based access restrictions."""

    model_config = ConfigDict(populate_by_name=True)

    days: list[str] | None = None  # mon, tue, wed, etc.
    start_hour: int | None = Field(None, alias="startHour")
    end_hour: int | None = Field(None, alias="endHour")
    timezone: str | None = None


class AccessPolicy(BaseModel):
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


class AccessEvaluation(BaseModel):
    """Access evaluation result."""

    model_config = ConfigDict(populate_by_name=True)

    allowed: bool
    policy_id: str | None = Field(None, alias="policyId")
    reason: str | None = None
    requires_mfa: bool = Field(False, alias="requiresMfa")
    requires_justification: bool = Field(False, alias="requiresJustification")
    max_duration_minutes: int | None = Field(None, alias="maxDurationMinutes")


class Consent(BaseModel):
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


class LineageNode(BaseModel):
    """Data lineage node."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    node_type: str = Field(alias="nodeType")  # source, transform, destination, agent
    metadata: dict[str, Any] | None = None


class LineageEdge(BaseModel):
    """Data lineage edge."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    source_id: str = Field(alias="sourceId")
    target_id: str = Field(alias="targetId")
    edge_type: str = Field(alias="edgeType")  # derives_from, feeds_into, copies_to


class LineageGraph(BaseModel):
    """Data lineage graph."""

    model_config = ConfigDict(populate_by_name=True)

    nodes: list[LineageNode]
    edges: list[LineageEdge]
    root_id: str | None = Field(None, alias="rootId")


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
