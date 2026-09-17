"""
Tool Registry SDK Module.

The tool registry is the catalogue of tools an agent may be granted. It is
read-mostly: tools are registered by the platform, and this module reads the
catalogue, resolves tools by id, and validates that a set of tool ids is real
before it is attached to an agent.

Provides programmatic access to the registry:

- list(): List tools, with optional filtering
- get(): Resolve one tool by id
- count(): How many tools are registered
- categories(): Categories with their counts
- danger_levels(): Danger-level definitions
- validate(): Split a set of tool ids into valid and invalid
- batch(): Resolve many tools by id in one call

⛔ AUTH: this surface admits a USER SESSION only. Its router gate does not
accept an API key, and an API-key principal carries no role and no personas
by design, so every method here answers 403 for a client built with
``api_key=``. Use the OAuth configuration instead.

Contract note: no operation on this surface declares a response schema, so
the envelopes below are modelled from what the platform emits consistently
and every tool record inside is carried as ``dict[str, Any]``. That is a
deliberate floor, not a guess — typing a tool record here would assert a
shape the API does not currently promise, and the moment those models are
declared server-side this module's method signatures do not have to change.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel

if TYPE_CHECKING:
    from .._http import HTTPClient


class ToolList(TolerantModel):
    """
    A page of tools.

    ``tools`` holds the backend-shaped tool payloads, unmodelled because the
    operation declares no response schema.
    """

    model_config = ConfigDict(populate_by_name=True)

    tools: builtins.list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ToolValidation(TolerantModel):
    """
    The result of validating a set of tool ids.

    ⛔ Read ``invalid``, not just ``valid``. This call does not raise on an
    unknown id — it partitions the set, so a request naming five tools of
    which two do not exist answers 200 with three in ``valid`` and two in
    ``invalid``. Attaching only ``valid`` silently drops the rest.
    """

    model_config = ConfigDict(populate_by_name=True)

    valid: builtins.list[str] = Field(default_factory=list)
    invalid: builtins.list[str] = Field(default_factory=list)


class ToolsModule:
    """
    Tool Registry SDK module.

    Methods:
        - list(): List tools with optional filtering
        - get(): Resolve one tool by id
        - count(): Number of registered tools
        - categories(): Categories with counts
        - danger_levels(): Danger-level definitions
        - validate(): Partition tool ids into valid and invalid
        - batch(): Resolve many tools by id

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(
        ...     api_key="your-api-key", base_url="https://your-host"
        ... )
        >>>
        >>> page = await client.tools.list(danger_level="low")
        >>> check = await client.tools.validate(["fs.read", "not-a-tool"])
        >>> check.invalid
        ['not-a-tool']
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize Tools module with HTTP client."""
        self._http = http_client

    async def list(
        self,
        category: str | None = None,
        danger_level: str | None = None,
        search: str | None = None,
        requires_approval: bool | None = None,
    ) -> ToolList:
        """
        List registered tools.

        Every filter is optional and they compose; omitting all of them
        returns the whole catalogue.

        Args:
            category: Restrict to one category — see :meth:`categories`
            danger_level: Restrict to one danger level — see
                :meth:`danger_levels`
            search: Free-text filter over tool names
            requires_approval: Restrict to tools that do or do not require
                approval before use

        Returns:
            ToolList: tool records plus their total

        Example:
            >>> risky = await client.tools.list(requires_approval=True)
        """
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        if danger_level is not None:
            params["danger_level"] = danger_level
        if search is not None:
            params["search"] = search
        if requires_approval is not None:
            params["requires_approval"] = requires_approval

        response = await self._http.request(
            "GET", "/api/v1/tools", params=params or None
        )
        return ToolList(**response)

    async def get(self, tool_id: str) -> dict[str, Any]:
        """
        Resolve one tool by id.

        Unlike :meth:`validate`, this RAISES when the tool does not exist
        (404). Use :meth:`validate` to test a set of ids without handling an
        exception per id.

        Args:
            tool_id: Tool ID

        Returns:
            The backend-shaped tool payload. This operation declares no
            response schema, so it is returned unmodelled.

        Example:
            >>> tool = await client.tools.get("fs.read")
        """
        payload: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/tools/{encode_path_param(tool_id)}"
        )
        return payload

    async def count(self) -> int:
        """
        Get the number of registered tools.

        Returns:
            int: The registered tool count

        Example:
            >>> await client.tools.count()
            42
        """
        response = await self._http.request("GET", "/api/v1/tools/count")
        total: int = response.get("count", 0)
        return total

    async def categories(self) -> builtins.list[dict[str, Any]]:
        """
        Get the tool categories with their counts.

        Returns:
            The backend-shaped category entries. This operation declares no
            response schema, so the entries are returned unmodelled.

        Example:
            >>> for category in await client.tools.categories():
            ...     print(category["name"], category["count"])
        """
        response = await self._http.request("GET", "/api/v1/tools/categories")
        entries: builtins.list[dict[str, Any]] = response.get("categories", [])
        return entries

    async def danger_levels(self) -> builtins.list[dict[str, Any]]:
        """
        Get the danger-level definitions.

        These are the values :meth:`list` accepts for ``danger_level``, with
        the platform's own description of what each one means — worth reading
        before gating on the level rather than assuming an ordering.

        Returns:
            The backend-shaped danger-level entries, unmodelled for the same
            reason as :meth:`categories`.
        """
        response = await self._http.request("GET", "/api/v1/tools/danger-levels")
        entries: builtins.list[dict[str, Any]] = response.get("danger_levels", [])
        return entries

    async def validate(self, tool_ids: builtins.list[str]) -> ToolValidation:
        """
        Partition a set of tool ids into those that exist and those that do
        not.

        ⛔ This does NOT raise on an unknown id — it reports one. Check
        ``result.invalid`` before attaching the set to an agent, or the
        unknown ids are silently dropped.

        Args:
            tool_ids: Tool ids to check

        Returns:
            ToolValidation: ``valid`` and ``invalid`` id lists

        Example:
            >>> check = await client.tools.validate(["fs.read", "nope"])
            >>> if check.invalid:
            ...     raise ValueError(f"unknown tools: {check.invalid}")
        """
        response = await self._http.request(
            "POST", "/api/v1/tools/validate", json_data={"tool_ids": tool_ids}
        )
        return ToolValidation(**response)

    async def batch(self, tool_ids: builtins.list[str]) -> ToolList:
        """
        Resolve many tools by id in one call.

        Unknown ids are OMITTED rather than reported, so ``total`` can be
        lower than the number of ids requested. Use :meth:`validate` when you
        need to know WHICH ids were unknown.

        Args:
            tool_ids: Tool ids to resolve

        Returns:
            ToolList: the tools that resolved, plus their total

        Example:
            >>> page = await client.tools.batch(["fs.read", "http.get"])
        """
        response = await self._http.request(
            "POST", "/api/v1/tools/batch", json_data={"tool_ids": tool_ids}
        )
        return ToolList(**response)
