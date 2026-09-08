"""
Workspaces SDK Module.

A *workspace* groups people and work units under one owner. Membership and
work-unit attachment are separate operations from workspace creation, so a
freshly created workspace is empty unless ``initial_members`` is supplied.

Provides programmatic access to workspace lifecycle and composition:

- list(): List workspaces visible to the caller (summary shape)
- get(): Read one workspace, including members and work units
- create(): Create a workspace
- update(): Rename / re-describe / re-colour a workspace
- archive(): Archive a workspace (reversible)
- restore(): Restore an archived workspace
- delete(): Delete a workspace
- add_member() / update_member() / remove_member(): Membership
- add_work_unit() / remove_work_unit(): Work-unit attachment

Archive and delete are different operations with different consequences:
``archive`` is reversible via :meth:`WorkspacesModule.restore`, ``delete`` is
not. Both currently answer with a message envelope rather than the affected
workspace, so neither returns a :class:`Workspace`.

Wire-shape note: this surface is camelCase on the wire, so the models below
carry explicit camelCase aliases. Field names remain snake_case in Python and
either spelling is accepted when constructing a model directly.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class WorkspaceMember(BaseModel):
    """A person attached to a workspace, with their role in it."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    user_name: str = Field(alias="userName")
    role: str
    joined_at: str = Field(alias="joinedAt")
    email: str | None = None
    department: str | None = None
    constraints: dict[str, Any] | None = None
    invited_by: str | None = Field(None, alias="invitedBy")


class WorkspaceWorkUnit(BaseModel):
    """A work unit attached to a workspace, with its trust state."""

    model_config = ConfigDict(populate_by_name=True)

    work_unit_id: str = Field(alias="workUnitId")
    work_unit_name: str = Field(alias="workUnitName")
    work_unit_type: str = Field(alias="workUnitType")
    trust_status: str = Field(alias="trustStatus")
    added_at: str = Field(alias="addedAt")
    added_by: str = Field(alias="addedBy")
    delegation_id: str | None = Field(None, alias="delegationId")
    constraints: dict[str, Any] | None = None
    department: str | None = None


class Workspace(BaseModel):
    """
    A workspace with its full composition.

    ``members`` and ``work_units`` are populated on this shape; the lighter
    :class:`WorkspaceSummary` returned by :meth:`WorkspacesModule.list` carries
    only their counts.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    workspace_type: str = Field(alias="workspaceType")
    owner_id: str = Field(alias="ownerId")
    owner_name: str = Field(alias="ownerName")
    organization_id: str = Field(alias="organizationId")
    members: list[WorkspaceMember] = Field(default_factory=list)
    work_units: list[WorkspaceWorkUnit] = Field(default_factory=list, alias="workUnits")
    member_count: int = Field(alias="memberCount")
    work_unit_count: int = Field(alias="workUnitCount")
    is_archived: bool = Field(alias="isArchived")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    description: str | None = None
    color: str | None = None
    expires_at: str | None = Field(None, alias="expiresAt")
    archived_at: str | None = Field(None, alias="archivedAt")


class WorkspaceSummary(BaseModel):
    """
    A workspace without its member / work-unit detail.

    This is the list shape. It carries ``member_count`` and
    ``work_unit_count`` but not the collections themselves, and it adds
    ``is_personal``, which the full shape does not carry. Call
    :meth:`WorkspacesModule.get` when the composition is needed.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    workspace_type: str = Field(alias="workspaceType")
    owner_id: str = Field(alias="ownerId")
    owner_name: str = Field(alias="ownerName")
    member_count: int = Field(alias="memberCount")
    work_unit_count: int = Field(alias="workUnitCount")
    is_archived: bool = Field(alias="isArchived")
    is_personal: bool = Field(alias="isPersonal")
    description: str | None = None
    color: str | None = None
    expires_at: str | None = Field(None, alias="expiresAt")


class WorkspaceMessage(BaseModel):
    """Message envelope returned by archive and delete."""

    model_config = ConfigDict(populate_by_name=True)

    message: str


class WorkspacesModule:
    """
    Workspaces SDK module.

    Methods:
        - list(): List visible workspaces (summary shape)
        - get(): Read one workspace with members and work units
        - create(): Create a workspace
        - update(): Update workspace attributes
        - archive() / restore(): Reversible retirement
        - delete(): Irreversible removal
        - add_member() / update_member() / remove_member(): Membership
        - add_work_unit() / remove_work_unit(): Work-unit attachment

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(
        ...     api_key="your-api-key", base_url="https://your-host"
        ... )
        >>>
        >>> workspaces = await client.workspaces.list(include_archived=False)
        >>> detail = await client.workspaces.get(workspaces[0].id)
        >>> for member in detail.members:
        ...     print(f"{member.user_name}: {member.role}")
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize Workspaces module with HTTP client."""
        self._http = http_client

    async def list(
        self,
        search: str | None = None,
        workspace_type: str | None = None,
        include_archived: bool = False,
        owner_id: str | None = None,
    ) -> builtins.list[WorkspaceSummary]:
        """
        List workspaces visible to the caller.

        Archived workspaces are excluded unless ``include_archived`` is set,
        so a workspace that "disappears" after :meth:`archive` is still
        present here with that flag on.

        Args:
            search: Free-text filter over workspace names
            workspace_type: Restrict to one workspace type
            include_archived: Include archived workspaces
            owner_id: Restrict to workspaces owned by this user

        Returns:
            Workspace summaries, without member or work-unit detail

        Example:
            >>> workspaces = await client.workspaces.list(search="platform")
        """
        params: dict[str, Any] = {"includeArchived": include_archived}
        if search is not None:
            params["search"] = search
        if workspace_type is not None:
            params["type"] = workspace_type
        if owner_id is not None:
            params["ownerId"] = owner_id

        response = await self._http.request("GET", "/api/v1/workspaces", params=params)
        return [WorkspaceSummary(**item) for item in response]

    async def get(self, workspace_id: str) -> Workspace:
        """
        Get one workspace, including its members and work units.

        Args:
            workspace_id: Workspace ID

        Returns:
            The workspace with its full composition

        Example:
            >>> workspace = await client.workspaces.get("ws-123")
            >>> len(workspace.members) == workspace.member_count
            True
        """
        response = await self._http.request(
            "GET", f"/api/v1/workspaces/{encode_path_param(workspace_id)}"
        )
        return Workspace(**response)

    async def create(
        self,
        name: str,
        description: str | None = None,
        workspace_type: str | None = None,
        color: str | None = None,
        expires_at: str | None = None,
        initial_members: builtins.list[dict[str, Any]] | None = None,
    ) -> Workspace:
        """
        Create a workspace.

        The workspace is empty unless ``initial_members`` is supplied; work
        units are attached separately via :meth:`add_work_unit`.

        Args:
            name: Workspace name
            description: Optional description
            workspace_type: Optional workspace type; the platform default
                applies when omitted
            color: Optional display colour
            expires_at: Optional expiry timestamp
            initial_members: Optional members to seed the workspace with

        Returns:
            The created workspace

        Example:
            >>> workspace = await client.workspaces.create(
            ...     name="Platform", description="Core platform work"
            ... )
        """
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if workspace_type is not None:
            body["workspaceType"] = workspace_type
        if color is not None:
            body["color"] = color
        if expires_at is not None:
            body["expiresAt"] = expires_at
        if initial_members is not None:
            body["initialMembers"] = initial_members

        response = await self._http.request(
            "POST", "/api/v1/workspaces", json_data=body
        )
        return Workspace(**response)

    async def update(
        self,
        workspace_id: str,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
        expires_at: str | None = None,
    ) -> Workspace:
        """
        Update workspace attributes.

        Only the arguments supplied are sent, so omitting one leaves the
        stored value untouched rather than clearing it.

        Args:
            workspace_id: Workspace ID
            name: New name
            description: New description
            color: New display colour
            expires_at: New expiry timestamp

        Returns:
            The updated workspace

        Example:
            >>> await client.workspaces.update("ws-123", name="Platform Core")
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        if expires_at is not None:
            body["expiresAt"] = expires_at

        response = await self._http.request(
            "PATCH",
            f"/api/v1/workspaces/{encode_path_param(workspace_id)}",
            json_data=body,
        )
        return Workspace(**response)

    async def archive(self, workspace_id: str) -> WorkspaceMessage:
        """
        Archive a workspace.

        Reversible — see :meth:`restore`. The workspace stops appearing in
        :meth:`list` unless ``include_archived`` is set.

        Args:
            workspace_id: Workspace ID

        Returns:
            A message envelope; the workspace itself is not returned

        Example:
            >>> await client.workspaces.archive("ws-123")
        """
        response = await self._http.request(
            "POST", f"/api/v1/workspaces/{encode_path_param(workspace_id)}/archive"
        )
        return WorkspaceMessage(**response)

    async def restore(self, workspace_id: str) -> Workspace:
        """
        Restore an archived workspace.

        Unlike :meth:`archive`, this answers with the workspace itself.

        Args:
            workspace_id: Workspace ID

        Returns:
            The restored workspace

        Example:
            >>> workspace = await client.workspaces.restore("ws-123")
            >>> workspace.is_archived
            False
        """
        response = await self._http.request(
            "POST", f"/api/v1/workspaces/{encode_path_param(workspace_id)}/restore"
        )
        return Workspace(**response)

    async def delete(self, workspace_id: str) -> WorkspaceMessage:
        """
        Delete a workspace.

        Not reversible. Use :meth:`archive` when the workspace may be wanted
        again.

        Args:
            workspace_id: Workspace ID

        Returns:
            A message envelope

        Example:
            >>> await client.workspaces.delete("ws-123")
        """
        response = await self._http.request(
            "DELETE", f"/api/v1/workspaces/{encode_path_param(workspace_id)}"
        )
        return WorkspaceMessage(**response)

    async def add_member(
        self, workspace_id: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """
        Add a member to a workspace.

        ``role`` is required — the platform has no default role for a new
        member, so it must be chosen at the point of adding.

        Args:
            workspace_id: Workspace ID
            user_id: User to add
            role: Role to grant within the workspace

        Returns:
            The backend-shaped membership payload.

        Note:
            This operation declares no response schema, so the payload is
            returned unmodelled rather than typed against a guess. Read
            :meth:`get` afterwards for a typed :class:`WorkspaceMember`.

        Example:
            >>> await client.workspaces.add_member("ws-123", "user-456", role="editor")
        """
        payload: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/workspaces/{encode_path_param(workspace_id)}/members",
            json_data={"userId": user_id, "role": role},
        )
        return payload

    async def update_member(
        self, workspace_id: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """
        Update a workspace member's role.

        Role is the only mutable membership attribute on this operation.

        Args:
            workspace_id: Workspace ID
            user_id: Member to update
            role: New role

        Returns:
            The backend-shaped membership payload.

        Note:
            This operation declares no response schema; see
            :meth:`add_member`.

        Example:
            >>> await client.workspaces.update_member("ws-123", "user-456", role="viewer")
        """
        payload: dict[str, Any] = await self._http.request(
            "PATCH",
            f"/api/v1/workspaces/{encode_path_param(workspace_id)}/members/{encode_path_param(user_id)}",
            json_data={"role": role},
        )
        return payload

    async def remove_member(self, workspace_id: str, user_id: str) -> dict[str, Any]:
        """
        Remove a member from a workspace.

        Args:
            workspace_id: Workspace ID
            user_id: Member to remove

        Returns:
            The backend-shaped payload.

        Note:
            This operation declares no response schema; see
            :meth:`add_member`.

        Example:
            >>> await client.workspaces.remove_member("ws-123", "user-456")
        """
        payload: dict[str, Any] = await self._http.request(
            "DELETE",
            f"/api/v1/workspaces/{encode_path_param(workspace_id)}/members/{encode_path_param(user_id)}",
        )
        return payload

    async def add_work_unit(
        self,
        workspace_id: str,
        work_unit_id: str,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Attach a work unit to a workspace.

        Args:
            workspace_id: Workspace ID
            work_unit_id: Work unit to attach
            constraints: Optional per-attachment constraints

        Returns:
            The backend-shaped attachment payload.

        Note:
            This operation declares no response schema, so the payload is
            returned unmodelled. Read :meth:`get` afterwards for a typed
            :class:`WorkspaceWorkUnit`, which also carries ``trust_status``.

        Example:
            >>> await client.workspaces.add_work_unit("ws-123", "wu-789")
        """
        body: dict[str, Any] = {"workUnitId": work_unit_id}
        if constraints is not None:
            body["constraints"] = constraints

        payload: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/workspaces/{encode_path_param(workspace_id)}/work-units",
            json_data=body,
        )
        return payload

    async def remove_work_unit(
        self, workspace_id: str, work_unit_id: str
    ) -> dict[str, Any]:
        """
        Detach a work unit from a workspace.

        Args:
            workspace_id: Workspace ID
            work_unit_id: Work unit to detach

        Returns:
            The backend-shaped payload.

        Note:
            This operation declares no response schema; see
            :meth:`add_work_unit`.

        Example:
            >>> await client.workspaces.remove_work_unit("ws-123", "wu-789")
        """
        payload: dict[str, Any] = await self._http.request(
            "DELETE",
            f"/api/v1/workspaces/{encode_path_param(workspace_id)}/work-units/{encode_path_param(work_unit_id)}",
        )
        return payload
