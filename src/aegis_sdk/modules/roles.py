"""
Roles SDK Module (``/api/v1/roles``).

The full role-administration surface: list and hierarchy reads, create /
update / delete, and the two link surfaces a role carries — its delegate
agent and its assigned user.

Relationship to :class:`~aegis_sdk.standup.roles.OrganizationRolesModule`
(``client.roles``):
    Both reach the same underlying role service. ``client.roles`` covers two
    operations on ``/api/v1/organization-roles`` and returns untyped dicts;
    this module covers twelve operations on ``/api/v1/roles`` and returns
    typed models. Use this one unless you already depend on the other.

Credential:
    Unlike the decision surfaces, these routes ARE reachable with an API key —
    the router admits a key scoped to ``organizations`` or ``roles``, and each
    route then requires the matching fine-grained permission
    (``organizations:read`` for the five reads, ``organizations:update`` for
    the seven writes). A key with neither scope is refused at the router.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class Role(TolerantModel):
    """An organization role — the accountability anchor a unit is built from.

    Note:
        Six fields are JSON **strings**, not parsed objects, and are surfaced
        as the platform emits them: ``responsibilities_json``,
        ``required_skills_json``, ``required_capabilities_json``,
        ``approval_authority_json``, ``constraint_overrides_json``,
        ``metadata_json``, ``tags_json``, ``effective_constraints_json``. Call
        ``json.loads()`` yourself.

    Note:
        ``effective_constraints_json`` is populated on the LIST read only. Every
        endpoint that emits a single mutated role leaves it at its ``"{}"``
        default — so reading it after a write tells you nothing about the
        role's envelope. Re-read via :meth:`RolesModule.list` if you need it.

    Note:
        ``authority_level`` (1 = staff … 5 = C-suite) does **not** gate what a
        role's agent may access — knowledge clearance does that, separately. It
        does gate *assignment*: see :meth:`RolesModule.assign_user`.
    """

    model_config = ConfigDict(populate_by_name=True)

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


class RoleList(TolerantModel):
    """Paginated role list."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[Role] = Field(default_factory=list)
    total: int = 0


class RoleHierarchyNode(TolerantModel):
    """One node of the reporting tree.

    ``children`` nests recursively. Roots are roles with no parent, or whose
    parent falls outside the listed set (an archived parent, or a parent in a
    different unit when the listing is unit-filtered) — so a node appearing at
    the root of this tree is not proof it reports to nobody.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    organization_unit_id: str
    authority_level: int
    reports_to_role_id: str | None = None
    is_vacant: bool = True
    is_primary_for_unit: bool = False
    shadow_agent_id: str | None = None
    assigned_user_id: str | None = None
    direct_reports_count: int = 0
    children: list[RoleHierarchyNode] = Field(default_factory=list)


RoleHierarchyNode.model_rebuild()


class RoleHierarchy(TolerantModel):
    """Response envelope for the reporting-tree read."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[RoleHierarchyNode] = Field(default_factory=list)
    total: int = 0


class RoleAgentEntry(TolerantModel):
    """An agent linked to a role."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str
    name: str | None = None
    status: str | None = None
    is_shadow_agent: bool = True
    role_id: str


class RoleAgents(TolerantModel):
    """Response envelope for the role-agents read."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[RoleAgentEntry] = Field(default_factory=list)
    total: int = 0


class RoleUserEntry(TolerantModel):
    """A user attached to a role.

    ``assignment_type`` distinguishes the role's single canonical assignee
    (``"assigned"``) from users who merely hold access to the role's delegate
    agent (``"access"``). Only the former is the role's ``assigned_user_id``.
    """

    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    name: str | None = None
    email: str | None = None
    role_id: str
    assignment_type: str = "assigned"


class RoleUsers(TolerantModel):
    """Response envelope for the role-users read."""

    model_config = ConfigDict(populate_by_name=True)

    records: list[RoleUserEntry] = Field(default_factory=list)
    total: int = 0


class RoleDeleted(TolerantModel):
    """Confirmation message returned by the delete route."""

    model_config = ConfigDict(populate_by_name=True)

    message: str


class RolesModule:
    """
    Role administration SDK module (``/api/v1/roles``).

    Methods:
        - list(): Roles in the caller's organization, filtered and paginated
        - hierarchy(): The reporting tree
        - get(): One role
        - create(): Create a role
        - update(): Update a role
        - delete(): Delete a role (soft by default)
        - list_agents() / link_agent() / unlink_agent()
        - list_users() / assign_user() / unassign_user()

    Tenant scope:
        Every route is scoped to the caller's organization, and a role in
        another organization is reported as **absent** (``404``), never as
        forbidden. A ``NotFoundError`` here therefore does not establish that
        the role does not exist anywhere.

    Authority ceiling (applies to create, update and assign_user):
        The platform refuses to let a caller mint, raise, or staff a role whose
        ``authority_level`` exceeds the caller's own effective ceiling. This is
        a real, enforced check — not an advisory field — and it surfaces as
        ``403``.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key="your-api-key")
        >>>
        >>> roles = await client.role_admin.list(is_vacant=True)
        >>> tree = await client.role_admin.hierarchy()
        >>> role = await client.role_admin.create(
        ...     organization_unit_id="unit-1", title="Head of Reliability",
        ...     authority_level=3,
        ... )
    """

    def __init__(self, http_client):
        """Initialize the roles module with an HTTP client."""
        self._http = http_client

    async def list(
        self,
        organization_unit_id: str | None = None,
        authority_level: int | None = None,
        is_vacant: bool | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> RoleList:
        """
        List roles in the caller's organization.

        This is the only read that populates ``effective_constraints_json`` on
        each record — the per-role reads and every write do not.

        Args:
            organization_unit_id: Restrict to one unit
            authority_level: Restrict to one level (1-5); outside that range
                the platform rejects the request
            is_vacant: Restrict to vacant (``True``) or staffed (``False``)
                roles
            include_archived: Include archived roles
            limit: Page size (1-500, default 50)
            offset: Page offset

        Returns:
            The matching roles and the total count.

        Example:
            >>> vacant = await client.role_admin.list(is_vacant=True, limit=200)
            >>> print(f"{vacant.total} vacant roles")
        """
        params: dict[str, Any] = {
            "include_archived": include_archived,
            "limit": limit,
            "offset": offset,
        }
        if organization_unit_id is not None:
            params["organization_unit_id"] = organization_unit_id
        if authority_level is not None:
            params["authority_level"] = authority_level
        if is_vacant is not None:
            params["is_vacant"] = is_vacant

        response = await self._http.request("GET", "/api/v1/roles", params=params)
        return RoleList(**response)

    async def hierarchy(
        self,
        organization_unit_id: str | None = None,
        include_archived: bool = False,
    ) -> RoleHierarchy:
        """
        Get the role reporting tree.

        Args:
            organization_unit_id: Restrict the tree to one unit. Note that
                filtering can promote a node to a root: a role whose manager
                sits outside the filtered set appears at the top level.
            include_archived: Include archived roles

        Returns:
            The reporting tree, and the total node count.

        Example:
            >>> tree = await client.role_admin.hierarchy()
            >>> for root in tree.records:
            ...     print(root.title, len(root.children))
        """
        params: dict[str, Any] = {"include_archived": include_archived}
        if organization_unit_id is not None:
            params["organization_unit_id"] = organization_unit_id

        response = await self._http.request("GET", "/api/v1/roles/hierarchy", params=params)
        return RoleHierarchy(**response)

    async def get(self, role_id: str) -> Role:
        """
        Get a single role by ID.

        Args:
            role_id: Role ID

        Returns:
            The role. ``effective_constraints_json`` is ``"{}"`` on this read —
            use :meth:`list` when the envelope is needed.

        Raises:
            NotFoundError: No such role in the caller's organization.

        Example:
            >>> role = await client.role_admin.get("role-1")
            >>> print(role.title, role.assigned_user_name)
        """
        response = await self._http.request(
            "GET", f"/api/v1/roles/{encode_path_param(role_id)}"
        )
        return Role(**response)

    async def create(
        self,
        organization_unit_id: str,
        title: str,
        description: str | None = None,
        job_description: str | None = None,
        responsibilities: list[str] | None = None,
        required_skills: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        authority_level: int = 1,
        approval_authority: dict[str, Any] | None = None,
        reports_to_role_id: str | None = None,
        constraint_template_id: str | None = None,
        constraint_overrides: dict[str, Any] | None = None,
        auto_generate_agent: bool = True,
        is_primary_for_unit: bool = False,
        is_external: bool = False,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Role:
        """
        Create a role. Responds ``201``.

        Args:
            organization_unit_id: Unit the role belongs to
            title: Role title (1-200 characters)
            description: Short description (max 2000 characters)
            job_description: Full job description (max 2000 characters)
            responsibilities: Responsibility statements
            required_skills: Required skills
            required_capabilities: Required capabilities
            authority_level: 1 (staff) to 5 (C-suite), default 1. Subject to
                the caller's authority ceiling — see the class docstring.
            approval_authority: Approval-authority payload recorded on the role
            reports_to_role_id: The role this one reports to
            constraint_template_id: Envelope template to derive constraints from
            constraint_overrides: Role-specific constraint overrides. These
                narrow the template; they are recorded as the role's own
                writable overrides and are not the computed envelope.
            auto_generate_agent: Mint a delegate agent for the role
            is_primary_for_unit: Make this the unit's head role
            is_external: Mark the role as external to the organization
            metadata: Free-form metadata
            tags: Tags

        Returns:
            The created role.

        Raises:
            AuthorizationError: ``403`` — the caller's authority ceiling is
                below ``authority_level``, or the credential lacks
                ``organizations:update``.
            NotFoundError: ``404`` — the unit does not exist in this
                organization.
            ValidationError: ``400``/``422`` — field constraints rejected.

        Example:
            >>> role = await client.role_admin.create(
            ...     organization_unit_id="unit-1",
            ...     title="Head of Reliability",
            ...     authority_level=3,
            ...     reports_to_role_id="role-cto",
            ... )
        """
        body: dict[str, Any] = {
            "organization_unit_id": organization_unit_id,
            "title": title,
            "authority_level": authority_level,
            "auto_generate_agent": auto_generate_agent,
            "is_primary_for_unit": is_primary_for_unit,
            "is_external": is_external,
        }
        optional: dict[str, Any] = {
            "description": description,
            "job_description": job_description,
            "responsibilities": responsibilities,
            "required_skills": required_skills,
            "required_capabilities": required_capabilities,
            "approval_authority": approval_authority,
            "reports_to_role_id": reports_to_role_id,
            "constraint_template_id": constraint_template_id,
            "constraint_overrides": constraint_overrides,
            "metadata": metadata,
            "tags": tags,
        }
        body.update({k: v for k, v in optional.items() if v is not None})

        response = await self._http.request("POST", "/api/v1/roles", json_data=body)
        return Role(**response)

    async def update(
        self,
        role_id: str,
        *,
        organization_unit_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        job_description: str | None = None,
        responsibilities: list[str] | None = None,
        required_skills: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        authority_level: int | None = None,
        approval_authority: dict[str, Any] | None = None,
        reports_to_role_id: str | None = None,
        clear_reports_to: bool = False,
        constraint_template_id: str | None = None,
        constraint_overrides: dict[str, Any] | None = None,
        auto_generate_agent: bool | None = None,
        is_primary_for_unit: bool | None = None,
        is_external: bool | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        replace_with_role_id: str | None = None,
    ) -> Role:
        """
        Update a role. Only the arguments you pass are sent.

        Args:
            role_id: Role ID
            clear_reports_to: Set ``True`` to detach the role from its manager.
                ``reports_to_role_id`` is the one field where an explicit
                ``null`` means "clear this" rather than "omitted", so the SDK
                exposes it as a separate flag instead of overloading ``None``.
                Passing both ``reports_to_role_id`` and ``clear_reports_to`` is
                a caller error; the clear wins.
            status: ``"active"`` or ``"archived"``. Any other value is rejected.
            replace_with_role_id: Names an already-active role in the SAME unit
                to promote to primary, authorizing an update that would
                otherwise leave the unit headless (archiving the unit's only
                active primary, or moving it to another unit). **This is a
                best-effort ordered pair of writes, not one transaction** — a
                failure after the first write leaves the pair half-applied, so
                re-read the unit rather than assuming both landed. Ignored on
                any update that does neither of those two things.
            authority_level: Subject to the caller's authority ceiling; a
                caller cannot self-promote or grant above their own level.

        Returns:
            The updated role, with ``effective_constraints_json`` at ``"{}"``.

        Raises:
            AuthorizationError: ``403`` — authority escalation, or the
                credential lacks ``organizations:update``.
            NotFoundError: ``404`` — no such role, or the named unit does not
                exist in this organization.
            ValidationError: ``400``/``422`` — including a reports-to change
                that would create a cycle in the reporting tree.

        Example:
            >>> await client.role_admin.update("role-1", title="Head of SRE")
            >>> await client.role_admin.update("role-1", clear_reports_to=True)
        """
        body: dict[str, Any] = {}
        optional: dict[str, Any] = {
            "organization_unit_id": organization_unit_id,
            "title": title,
            "description": description,
            "job_description": job_description,
            "responsibilities": responsibilities,
            "required_skills": required_skills,
            "required_capabilities": required_capabilities,
            "authority_level": authority_level,
            "approval_authority": approval_authority,
            "constraint_template_id": constraint_template_id,
            "constraint_overrides": constraint_overrides,
            "auto_generate_agent": auto_generate_agent,
            "is_primary_for_unit": is_primary_for_unit,
            "is_external": is_external,
            "metadata": metadata,
            "tags": tags,
            "status": status,
            "replace_with_role_id": replace_with_role_id,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        if clear_reports_to:
            body["reports_to_role_id"] = None
        elif reports_to_role_id is not None:
            body["reports_to_role_id"] = reports_to_role_id

        response = await self._http.request(
            "PUT", f"/api/v1/roles/{encode_path_param(role_id)}", json_data=body
        )
        return Role(**response)

    async def delete(self, role_id: str, hard: bool = False) -> RoleDeleted:
        """
        Delete a role. Soft by default.

        What happens first:
            Before the role goes, the platform archives the role's delegate
            agent and revokes that agent's trust chain. If the revoke cannot
            complete, the whole call fails with ``409`` and the role is left
            in place — it will not delete a role while leaving a live,
            un-revoked delegate agent behind.

        Args:
            role_id: Role ID
            hard: ``True`` to delete permanently rather than archiving

        Returns:
            A confirmation message.

        Raises:
            ValidationError: ``400`` — the role has direct reports. Reassign or
                remove them first; the platform will not re-parent them for you.
            NotFoundError: ``404`` — no such role in this organization.
            AgenticOSError: ``409`` — either the delegate agent's trust chain
                could not be revoked, or the role is the head of a still-active
                unit. Both surface as the base error; read
                ``.details["message"]`` to tell them apart.

        Example:
            >>> await client.role_admin.delete("role-1")
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/roles/{encode_path_param(role_id)}",
            params={"hard": hard},
        )
        return RoleDeleted(**response)

    async def list_agents(self, role_id: str) -> RoleAgents:
        """
        List agents linked to a role.

        A role carries at most one delegate agent, so this list is empty or has
        a single entry.

        Args:
            role_id: Role ID

        Returns:
            The role's linked agents.

        Raises:
            NotFoundError: No such role in this organization.

        Example:
            >>> agents = await client.role_admin.list_agents("role-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/roles/{encode_path_param(role_id)}/agents"
        )
        return RoleAgents(**response)

    async def link_agent(self, role_id: str, agent_id: str) -> Role:
        """
        Link a delegate agent to a role.

        Args:
            role_id: Role ID
            agent_id: Agent ID. Must be a **delegate** agent in the caller's
                organization, and must not already be linked to another role.

        Returns:
            The updated role.

        Raises:
            NotFoundError: ``404`` — no such role, or no such agent in this
                organization.
            ValidationError: ``400`` — the agent is not a delegate agent, or is
                already linked to a different role.
            AuthorizationError: ``403`` — missing ``organizations:update``.

        Example:
            >>> await client.role_admin.link_agent("role-1", "agent-9")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/roles/{encode_path_param(role_id)}/agents",
            json_data={"agent_id": agent_id},
        )
        return Role(**response)

    async def unlink_agent(self, role_id: str, agent_id: str) -> Role:
        """
        Unlink an agent from a role.

        Args:
            role_id: Role ID
            agent_id: Agent ID currently linked to the role

        Returns:
            The updated role.

        Raises:
            NotFoundError: No such role, or the agent is not linked to it.
            AuthorizationError: ``403`` — missing ``organizations:update``.

        Example:
            >>> await client.role_admin.unlink_agent("role-1", "agent-9")
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/roles/{encode_path_param(role_id)}/agents/{encode_path_param(agent_id)}",
        )
        return Role(**response)

    async def list_users(self, role_id: str) -> RoleUsers:
        """
        List users attached to a role.

        Returns two different kinds of attachment — read ``assignment_type`` on
        each entry. ``"assigned"`` is the role's single canonical holder;
        ``"access"`` is a user who can reach the role's delegate agent without
        holding the role.

        Args:
            role_id: Role ID

        Returns:
            The role's attached users.

        Raises:
            NotFoundError: No such role in this organization.

        Example:
            >>> users = await client.role_admin.list_users("role-1")
            >>> holder = next(
            ...     (u for u in users.records if u.assignment_type == "assigned"),
            ...     None,
            ... )
        """
        response = await self._http.request(
            "GET", f"/api/v1/roles/{encode_path_param(role_id)}/users"
        )
        return RoleUsers(**response)

    async def assign_user(self, role_id: str, user_id: str) -> Role:
        """
        Assign a user to a role.

        Authority ceiling — this is enforced, not advisory:
            A caller cannot attach anyone, **including themselves**, to a role
            whose ``authority_level`` is above the caller's own effective
            ceiling. Minting roles above your tier is blocked separately; this
            closes the path of self-assigning into an existing high-authority
            role that somebody else legitimately created.

        Args:
            role_id: Role ID
            user_id: User ID. Must belong to the caller's organization.

        Returns:
            The updated role, with ``assigned_user_id`` and
            ``assigned_user_name`` populated.

        Raises:
            NotFoundError: ``404`` — no such role in this organization.
            ValidationError: ``400`` — the user is not in this organization.
            AuthorizationError: ``403`` — the role's authority level exceeds
                the caller's ceiling, or the credential lacks
                ``organizations:update``.

        Example:
            >>> await client.role_admin.assign_user("role-1", "user-7")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/roles/{encode_path_param(role_id)}/users",
            json_data={"user_id": user_id},
        )
        return Role(**response)

    async def unassign_user(self, role_id: str, user_id: str) -> Role:
        """
        Unassign a user from a role.

        Args:
            role_id: Role ID
            user_id: The role's **current** assignee. A mismatch is reported as
                ``404`` rather than a distinct error, so that guessing at ids
                reveals nothing.

        Returns:
            The updated, now-vacant role.

        Raises:
            NotFoundError: ``404`` — no such role, or ``user_id`` is not the
                role's current assignee.
            AuthorizationError: ``403`` — missing ``organizations:update``.

        Example:
            >>> await client.role_admin.unassign_user("role-1", "user-7")
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/roles/{encode_path_param(role_id)}/users/{encode_path_param(user_id)}",
        )
        return Role(**response)
