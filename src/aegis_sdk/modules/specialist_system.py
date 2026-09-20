"""
Specialist System Module for Agentic OS SDK.

Provides the primary CRUD surface for the agent-authoring console's
**specialists** resource. The full backend
router exposes 26 routes (specialists, skills, tools, templates,
import/export/validate, directory, tenant config) — this module covers the
specialists resource only; the remaining sub-resources have no SDK coverage
yet (see the wiring manifest for the flagged gaps).

Self-contained module: local Pydantic models, no shared imports from
client.py / modules/__init__.py / types.py. Every route below is verified
against the deployed API
(prefix ``/api/v1/specialist-system``):

    GET    /api/v1/specialist-system/specialists                -> list_specialists()
    GET    /api/v1/specialist-system/specialists/{id}            -> get_specialist()
    POST   /api/v1/specialist-system/specialists                 -> create_specialist()
    PUT    /api/v1/specialist-system/specialists/{id}             -> update_specialist()
    DELETE /api/v1/specialist-system/specialists/{id}             -> delete_specialist()
    POST   /api/v1/specialist-system/specialists/{id}/clone       -> clone_specialist()

Wire shape is camelCase (FE ``SpecialistDefinition`` interface) per the
router's own module docstring;
list responses use the ``{items, total, page, pageSize}`` envelope.
"""

from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


class Specialist(TolerantModel):
    """
    Specialist definition (agent-authoring console).

    The backend has no fixed ``response_model`` on these routes — it returns
    the service's raw camelCase dict (verified at). This model declares the
    fields visible on ``UpdateSpecialistBody`` (the most complete field
    enumeration in the router) and allows extra backend fields to pass
    through rather than raising on drift.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    name: str
    description: str | None = None
    system_prompt: str | None = Field(default=None, alias="systemPrompt")
    capabilities: dict[str, Any] | None = None
    skills: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    planning_strategy: str | None = Field(default=None, alias="planningStrategy")
    budget_limit: float | None = Field(default=None, alias="budgetLimit")
    checkpoint_frequency: int | None = Field(default=None, alias="checkpointFrequency")
    metadata: dict[str, Any] | None = None
    model: str | None = None
    temperature: float | None = None
    timeout_seconds: int | None = Field(default=None, alias="timeoutSeconds")


class SpecialistList(TolerantModel):
    """Paginated specialist roster (``{items, total, page, pageSize}``)."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[Specialist]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class SpecialistSystemModule:
    """
    Specialist System module (agent-authoring console — specialists resource).

    Example:
        >>> result = await client.specialist_system.list_specialists(search="analyst")
        >>> specialist = await client.specialist_system.create_specialist(
        ...     name="Research Analyst",
        ...     description="Summarizes market research",
        ... )
    """

    def __init__(self, http_client: "HTTPClient"):
        self._http = http_client

    async def list_specialists(
        self,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
    ) -> SpecialistList:
        """
        List specialists for the caller's tenant.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page (1-200)
            search: Optional free-text search filter

        Returns:
            SpecialistList: items + total + page + pageSize

        ⚠ ``items`` can hold fewer rows than the tenant does. A definition whose
        classification the caller's clearance does not admit is dropped
        server-side before the page is built, and the row is not reported as
        dropped — the server answers "not there" and "not admitted" identically,
        on purpose, so a short list is NOT by itself evidence that anything was
        deleted. Same gate as :meth:`get_specialist`.
        """
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if search:
            params["search"] = search

        response = await self._http.request(
            "GET", "/api/v1/specialist-system/specialists", params=params
        )
        return SpecialistList(**response)

    async def get_specialist(self, specialist_id: str) -> Specialist:
        """
        Get a single specialist (tenant-verified).

        Args:
            specialist_id: Specialist ID

        Returns:
            Specialist: Specialist detail

        Raises:
            NotFoundError: If the specialist is not available to this caller —
                either it does not exist, or it exists and its classification is
                not admitted to the caller's clearance. The server answers both
                with the same not-found response deliberately, so the refusal
                carries no discriminator and this exception is NOT proof the row
                was deleted. Do not retry: a clearance decision does not change
                on retry.
        """
        response = await self._http.request(
            "GET", f"/api/v1/specialist-system/specialists/{encode_path_param(specialist_id)}"
        )
        return Specialist(**response)

    async def create_specialist(
        self,
        name: str,
        description: str | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> Specialist:
        """
        Create a specialist (defaults filled server-side from DEFAULT_SPECIALIST).

        Args:
            name: Specialist name
            description: Optional description
            capabilities: Optional capabilities object

        Returns:
            Specialist: Created specialist
        """
        data: dict[str, Any] = {"name": name}
        if description is not None:
            data["description"] = description
        if capabilities is not None:
            data["capabilities"] = capabilities

        response = await self._http.request(
            "POST", "/api/v1/specialist-system/specialists", json_data=data
        )
        return Specialist(**response)

    async def update_specialist(self, specialist_id: str, **fields: Any) -> Specialist:
        """
        Update a specialist (tenant-verified).

        Args:
            specialist_id: Specialist ID
            **fields: camelCase fields accepted by ``UpdateSpecialistBody``
                — name, description, systemPrompt, capabilities, skills,
                tools, planningStrategy, budgetLimit, checkpointFrequency,
                metadata, model, temperature, timeoutSeconds

        Returns:
            Specialist: Updated specialist

        Raises:
            NotFoundError: If the specialist is not available to this caller —
                either it does not exist, or it exists and its classification is
                not admitted to the caller's clearance. The server answers both
                with the same not-found response deliberately, so the refusal
                carries no discriminator and this exception is NOT proof the row
                was deleted. Do not retry: a clearance decision does not change
                on retry.
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/specialist-system/specialists/{encode_path_param(specialist_id)}",
            json_data=fields,
        )
        return Specialist(**response)

    async def delete_specialist(self, specialist_id: str) -> None:
        """
        Soft-delete a specialist (tenant-verified).

        Args:
            specialist_id: Specialist ID

        Raises:
            NotFoundError: If the specialist is not available to this caller —
                either it does not exist, or it exists and its classification is
                not admitted to the caller's clearance. The server answers both
                with the same not-found response deliberately, so the refusal
                carries no discriminator and this exception is NOT proof the row
                was deleted. Do not retry: a clearance decision does not change
                on retry.
        """
        await self._http.request(
            "DELETE", f"/api/v1/specialist-system/specialists/{encode_path_param(specialist_id)}"
        )

    async def clone_specialist(self, specialist_id: str, name: str) -> Specialist:
        """
        Clone a specialist into a new artifact (tenant-verified).

        Args:
            specialist_id: Source specialist ID
            name: Name for the cloned specialist

        Returns:
            Specialist: Newly cloned specialist

        Raises:
            NotFoundError: If the source specialist is not available to this
                caller — either it does not exist, or it exists and its
                classification is not admitted to the caller's clearance. The
                server answers both identically and deliberately, so this is NOT
                proof the source was deleted. Do not retry: a clearance decision
                does not change on retry.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/specialist-system/specialists/{encode_path_param(specialist_id)}/clone",
            json_data={"name": name},
        )
        return Specialist(**response)
