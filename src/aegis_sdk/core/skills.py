"""
Agentic OS SDK Skills Module.

Provides skill management operations including:
- CRUD: Create, Read, Update, Delete, List

Skills are served under ``/api/v1/skills``. The API's
``CreateSkillRequest``/``UpdateSkillRequest``/``SkillResponse`` use a
different field vocabulary than :class:`~aegis_sdk.types.SkillCreate` /
:class:`~aegis_sdk.types.SkillUpdate` / :class:`~aegis_sdk.types.Skill`
(``category``/``content_markdown``/``tools_required``/``is_public`` on the
wire, against ``skill_type``/``config`` in the SDK types), so this module
builds request bodies directly rather than via
``SkillCreate(...).model_dump()``, and normalizes responses before
constructing :class:`Skill`. See ``_normalize_skill`` for the field mapping.

Known limitation: the SDK's ``Skill``/``SkillCreate``/``SkillUpdate`` types
still carry the older ``skill_type``/``config`` shape rather than the wire
vocabulary. Aligning them is a tracked follow-up; until then, prefer this
module's methods over constructing those types by hand.
"""

import builtins
from typing import TYPE_CHECKING, Any

from .._http import encode_path_param
from ..exceptions import ValidationError
from .models import PaginatedResponse, Skill

if TYPE_CHECKING:
    from .._http import HTTPClient


# Real backend category allowlist (VALID_CATEGORIES).
# Mirrored here (not authoritative) purely for an actionable client-side error;
# the server is still the source of truth and re-validates.
VALID_SKILL_CATEGORIES = {"coding", "data", "web", "file", "reasoning", "custom"}


def _normalize_skill(raw: dict[str, Any]) -> dict[str, Any]:
    """Adapt the real ``SkillResponse`` wire shape into the fields
    :class:`~aegis_sdk.types.Skill` requires.

    The wire response has no ``skill_type`` field at all (it has
    ``category``); ``skill_type`` is mapped from it so ``Skill(**normalized)``
    does not raise a missing-required-field error. The wire-only fields
    (``content_markdown``, ``tools_required``, ``is_public``, ``created_by``,
    ``priority``, ``assignment_id``) are preserved in ``config`` so callers
    can still reach them without data loss, even though ``Skill`` has no
    dedicated field for them yet.
    """
    return {
        "id": raw.get("id", ""),
        "name": raw.get("name", ""),
        "description": raw.get("description"),
        "skill_type": raw.get("category", raw.get("skill_type", "custom")),
        "organization_id": raw.get("organization_id", ""),
        "config": {
            "category": raw.get("category"),
            "content_markdown": raw.get("content_markdown", ""),
            "tools_required": raw.get("tools_required", []),
            "is_public": raw.get("is_public", True),
            "created_by": raw.get("created_by"),
            "priority": raw.get("priority"),
            "assignment_id": raw.get("assignment_id"),
        },
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


class SkillsModule:
    """
    Skill management operations.

    Provides full lifecycle management for skills including:
    - CRUD operations (create, read, update, delete, list)
    - Filtering by category

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     # List skills
        ...     skills = await client.skills.list()
        ...
        ...     # Create skill
        ...     skill = await client.skills.create(
        ...         name="Web Search",
        ...         category="web",
        ...         content_markdown="Search the web for a query.",
        ...     )
    """

    def __init__(self, http_client: "HTTPClient"):
        """
        Initialize skills module.

        Args:
            http_client: Internal HTTP client instance
        """
        self._http = http_client

    async def list(
        self,
        category: str | None = None,
        is_public: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[Skill]:
        """
        List skills with optional filters.

        Verified route: ``GET /api/v1/skills`` — params are ``category``,
        ``is_public``, ``search``, ``limit``, ``offset`` (NOT ``skill_type``
        / ``page`` / ``page_size``; the prior signature sent
        ``skill_type``/``page``/``page_size``, none of which the real
        endpoint reads, so filters silently no-opped and pagination always
        returned the same first page). Response envelope is
        ``{"skills": [...], "total", "limit", "offset"}`` (NOT ``items`` /
        ``page`` / ``page_size`` / ``has_next``, and NOT a bare array).

        Args:
            category: Filter by category (coding, data, web, file,
                reasoning, custom)
            is_public: Filter by public/private visibility
            search: Filter by name substring search
            limit: Items per page (max 100)
            offset: Pagination offset

        Returns:
            PaginatedResponse containing Skill objects

        Example:
            >>> result = await client.skills.list(category="web")
            >>> print(f"Found {result.total} web skills")
            >>> for skill in result.items:
            ...     print(f"  - {skill.name}: {skill.description}")
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        if is_public is not None:
            params["is_public"] = is_public
        if search:
            params["search"] = search

        response = await self._http.request("GET", "/api/v1/skills", params=params)

        skills = response.get("skills", [])
        total = response.get("total", len(skills))
        resp_limit = response.get("limit", limit)
        resp_offset = response.get("offset", offset)
        page = (resp_offset // resp_limit) + 1 if resp_limit else 1

        return PaginatedResponse[Skill](
            items=[Skill(**_normalize_skill(item)) for item in skills],
            total=total,
            page=page,
            page_size=resp_limit,
            has_next=(resp_offset + len(skills)) < total,
        )

    async def create(
        self,
        name: str,
        category: str,
        description: str | None = None,
        content_markdown: str | None = None,
        tools_required: builtins.list[str] | None = None,
        is_public: bool = True,
    ) -> Skill:
        """
        Create a new skill.

        Verified route: ``POST /api/v1/skills`` with
        ``CreateSkillRequest`` —
        ``category`` is REQUIRED (``Field(...)``, validated against
        ``VALID_CATEGORIES``); there is no ``config`` field at all (the
        prior signature took ``skill_type``/``config``, neither of which
        the real endpoint accepts — every call 422'd on the missing
        required ``category``).

        Args:
            name: Skill name
            category: One of ``coding``, ``data``, ``web``, ``file``,
                ``reasoning``, ``custom`` (server-validated; a client-side
                check is applied here to fail fast with an actionable
                message instead of an opaque 422)
            description: Optional description
            content_markdown: Optional skill instructions/content
            tools_required: Optional list of required tool names
            is_public: Whether the skill is visible org-wide (default True)

        Returns:
            Created Skill object

        Raises:
            ValidationError: If required fields missing or invalid
            AuthorizationError: If not allowed to create skills

        Example:
            >>> skill = await client.skills.create(
            ...     name="Code Interpreter",
            ...     category="coding",
            ...     description="Execute Python code",
            ...     content_markdown="Run the given Python snippet and return output.",
            ... )
        """
        if category not in VALID_SKILL_CATEGORIES:
            raise ValidationError(
                f"skills.create() requires 'category' to be one of "
                f"{sorted(VALID_SKILL_CATEGORIES)}; got {category!r}."
            )

        json_data: dict[str, Any] = {"name": name, "category": category, "is_public": is_public}
        if description is not None:
            json_data["description"] = description
        if content_markdown is not None:
            json_data["content_markdown"] = content_markdown
        if tools_required is not None:
            json_data["tools_required"] = tools_required

        response = await self._http.request(
            "POST",
            "/api/v1/skills",
            json_data=json_data,
        )
        return Skill(**_normalize_skill(response))

    async def get(self, skill_id: str) -> Skill:
        """
        Get skill by ID.

        Args:
            skill_id: Skill ID

        Returns:
            Skill object

        Raises:
            NotFoundError: If skill doesn't exist

        Example:
            >>> skill = await client.skills.get("skill_abc123")
            >>> print(f"Skill: {skill.name} ({skill.skill_type})")
        """
        response = await self._http.request("GET", f"/api/v1/skills/{encode_path_param(skill_id)}")
        return Skill(**_normalize_skill(response))

    async def update(
        self,
        skill_id: str,
        name: str | None = None,
        category: str | None = None,
        description: str | None = None,
        content_markdown: str | None = None,
        tools_required: builtins.list[str] | None = None,
        is_public: bool | None = None,
    ) -> Skill:
        """
        Update skill fields.

        Verified route: ``PUT /api/v1/skills/{skill_id}`` with
        ``UpdateSkillRequest`` — fields
        are ``name``/``category``/``description``/``content_markdown``/
        ``tools_required``/``is_public`` (NOT ``config``; the prior
        ``**kwargs`` signature accepted ``config`` and silently dropped it
        server-side since ``UpdateSkillRequest`` has no such field).

        Args:
            skill_id: Skill ID
            name: New name
            category: New category (one of coding/data/web/file/reasoning/custom)
            description: New description
            content_markdown: New skill instructions/content
            tools_required: New list of required tool names
            is_public: New public/private visibility

        Returns:
            Updated Skill object

        Raises:
            NotFoundError: If skill doesn't exist
            ValidationError: If update data is invalid

        Example:
            >>> skill = await client.skills.update(
            ...     "skill_abc123",
            ...     name="Updated Name",
            ...     is_public=False,
            ... )
        """
        if category is not None and category not in VALID_SKILL_CATEGORIES:
            raise ValidationError(
                f"skills.update() 'category' must be one of "
                f"{sorted(VALID_SKILL_CATEGORIES)}; got {category!r}."
            )

        json_data: dict[str, Any] = {}
        if name is not None:
            json_data["name"] = name
        if category is not None:
            json_data["category"] = category
        if description is not None:
            json_data["description"] = description
        if content_markdown is not None:
            json_data["content_markdown"] = content_markdown
        if tools_required is not None:
            json_data["tools_required"] = tools_required
        if is_public is not None:
            json_data["is_public"] = is_public

        response = await self._http.request(
            "PUT",
            f"/api/v1/skills/{encode_path_param(skill_id)}",
            json_data=json_data,
        )
        return Skill(**_normalize_skill(response))

    async def delete(self, skill_id: str) -> None:
        """
        Delete skill.

        Verified route: ``DELETE /api/v1/skills/{skill_id}`` — returns
        ``200 {"message": "Skill deleted successfully"}`` (NOT ``204``);
        the return value is discarded either way.

        Args:
            skill_id: Skill ID

        Raises:
            NotFoundError: If skill doesn't exist
            AuthorizationError: If not allowed to delete

        Example:
            >>> await client.skills.delete("skill_abc123")
        """
        await self._http.request("DELETE", f"/api/v1/skills/{encode_path_param(skill_id)}")

    async def duplicate(self, skill_id: str, name: str) -> Skill:
        """
        Duplicate an existing skill.

        .. warning::
            **Not available in the current API — this call returns 404.**
            ``POST /api/v1/skills/{skill_id}/duplicate`` is not served. To
            duplicate a skill today, :meth:`get` it and :meth:`create` a new
            one with the same fields.

        Args:
            skill_id: Source skill ID
            name: Name for the duplicated skill

        Returns:
            New Skill object (copy)

        Raises:
            NotFoundError: If source skill doesn't exist

        Example:
            >>> copy = await client.skills.duplicate(
            ...     "skill_abc123",
            ...     name="Web Search (Copy)"
            ... )
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/skills/{encode_path_param(skill_id)}/duplicate",
            json_data={"name": name},
        )
        return Skill(**_normalize_skill(response))

    # -------------------------------------------------------------------------
    # Agent-Skill Assignment
    # -------------------------------------------------------------------------

    async def list_agent_skills(self, agent_id: str) -> builtins.list[Skill]:
        """
        List the skills assigned to an agent.

        Verified route: ``GET /api/v1/skills/agents/{agent_id}/skills`` returning ``AgentSkillsResponse`` — the envelope is
        ``{"skills": [...], "total": int}`` (NOT the top-level CRUD
        ``{"skills", "total", "limit", "offset"}`` shape; agent-skill listings
        are unpaginated). Each element is a ``SkillResponse`` carrying the assignment-only
        ``priority``/``assignment_id`` fields, preserved in ``config`` by
        :func:`_normalize_skill`.

        Args:
            agent_id: Agent ID whose assigned skills to list

        Returns:
            List of Skill objects assigned to the agent, in priority order

        Raises:
            NotFoundError: If the agent doesn't exist or is out of tenant scope

        Example:
            >>> skills = await client.skills.list_agent_skills("agent_abc123")
            >>> for skill in skills:
            ...     print(f"  - {skill.name} (priority {skill.config['priority']})")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/skills/agents/{encode_path_param(agent_id)}/skills",
        )
        return [Skill(**_normalize_skill(item)) for item in response.get("skills", [])]

    async def assign_agent_skill(
        self,
        agent_id: str,
        skill_id: str,
        priority: int = 0,
    ) -> dict[str, Any]:
        """
        Assign a skill to an agent with a priority.

        Verified route: ``POST /api/v1/skills/agents/{agent_id}/skills`` with ``AssignSkillRequest`` — body is
        ``{"skill_id": str, "priority": int}`` (``priority`` defaults to 0,
        ``ge=0``). Returns ``AssignmentResponse``: ``{"id", "agent_id",
        "skill_id", "priority", "created_at"}`` at HTTP 201. There is no SDK
        model for an assignment record, so the raw assignment dict is returned.

        Args:
            agent_id: Agent to assign the skill to
            skill_id: Skill to assign
            priority: Assignment priority (0 = highest), must be >= 0

        Returns:
            The assignment record dict (id, agent_id, skill_id, priority,
            created_at)

        Raises:
            ValidationError: If the skill is already assigned or priority < 0
            NotFoundError: If the agent or skill doesn't exist

        Example:
            >>> assignment = await client.skills.assign_agent_skill(
            ...     "agent_abc123", "skill_def456", priority=1
            ... )
            >>> print(f"Assigned: {assignment['id']}")
        """
        if priority < 0:
            raise ValidationError(
                f"skills.assign_agent_skill() 'priority' must be >= 0; got {priority}."
            )

        return await self._http.request(
            "POST",
            f"/api/v1/skills/agents/{encode_path_param(agent_id)}/skills",
            json_data={"skill_id": skill_id, "priority": priority},
        )

    async def get_by_name(self, name: str) -> Skill | None:
        """
        Get skill by name (convenience method).

        Args:
            name: Skill name to search for

        Returns:
            Skill if found, None otherwise

        Example:
            >>> skill = await client.skills.get_by_name("Web Search")
            >>> if skill:
            ...     print(f"Found: {skill.id}")
        """
        # Use list with filter and find first match
        result = await self.list(limit=100)
        for skill in result.items:
            if skill.name == name:
                return skill
        return None
