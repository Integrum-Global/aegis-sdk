"""Knowledge module — typed create/get/publish for the vertical-standup path.

Verified against the server ``knowledge`` router(mounted at ``/api/v1``)).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


class KnowledgeModule:
    """Knowledge item management (create + get + publish)."""

    def __init__(self, http_client: HTTPClient) -> None:
        self._http = http_client

    async def create(
        self,
        title: str,
        content_markdown: str,
        knowledge_type: str,
        path: str,
        classification: str | None = None,
        compartment: str | None = None,
        slug: str | None = None,
        summary: str | None = None,
        category: str | None = None,
        parent_path: str | None = None,
        owner_unit_id: str | None = None,
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        review_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a knowledge item.

        Server: ``POST /api/v1/knowledge``.

        Args:
            title: Item title (1-200 chars).
            content_markdown: Markdown body (non-empty).
            knowledge_type: One of ``policy``, ``procedure``, ``reference``,
                ``faq`` (``^(policy|procedure|reference|faq)$``).
            path: Containment path (1-500 chars).
            classification: EATP level — ``public``, ``restricted``,
                ``confidential``, ``secret``, ``top_secret``. ``secret`` and
                ``top_secret`` REQUIRE ``compartment``.
        """
        body: dict[str, Any] = {
            "title": title,
            "content_markdown": content_markdown,
            "knowledge_type": knowledge_type,
            "path": path,
        }
        optional = {
            "classification": classification,
            "compartment": compartment,
            "slug": slug,
            "summary": summary,
            "category": category,
            "parent_path": parent_path,
            "owner_unit_id": owner_unit_id,
            "tags": tags,
            "keywords": keywords,
            "metadata": metadata,
            "review_date": review_date,
        }
        body.update({k: v for k, v in optional.items() if v is not None})
        resp: dict[str, Any] = await self._http.request("POST", "/api/v1/knowledge", json_data=body)
        return resp

    async def get(self, knowledge_id: str) -> dict[str, Any]:
        """Get a knowledge item by ID.

        Server: ``GET /api/v1/knowledge/{knowledge_id}``.
        """
        resp: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/knowledge/{encode_path_param(knowledge_id)}"
        )
        return resp

    async def publish(self, knowledge_id: str) -> dict[str, Any]:
        """Publish a knowledge item (draft -> published).

        Server: ``POST /api/v1/knowledge/{knowledge_id}/publish``.
        """
        resp: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/publish"
        )
        return resp
    async def list(
        self,
        path_prefix: str | None = None,
        knowledge_type: str | None = None,
        classification: str | None = None,
        category: str | None = None,
        owner_unit_id: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List knowledge items in the caller's organization.

        Server: ``GET /api/v1/knowledge``.

        ⚠ The server's ``status`` default is ``"published"``, NOT "all". Leaving
        ``status`` as ``None`` therefore omits DRAFT items -- an idempotency
        check that does not pass ``status`` will not see an unpublished item
        and will try to create it again. Pass ``status`` explicitly when
        reconciling.

        Args:
            path_prefix: Filter by path prefix.
            knowledge_type: Filter by type.
            classification: Filter by classification level.
            category: Filter by category.
            owner_unit_id: Filter by owning unit.
            status: Filter by status. Omitted -> server applies ``published``.
            include_archived: Include archived items (default False).
            limit: Maximum results (1-200, server default 50).
            offset: Pagination offset.

        Returns:
            ``{"records": [...], "total": int}``.
        """
        params: dict[str, Any] = {
            "include_archived": include_archived,
            "limit": limit,
            "offset": offset,
        }
        optional = {
            "path_prefix": path_prefix,
            "knowledge_type": knowledge_type,
            "classification": classification,
            "category": category,
            "owner_unit_id": owner_unit_id,
            "status": status,
        }
        params.update({k: v for k, v in optional.items() if v is not None})
        resp: dict[str, Any] = await self._http.request(
            "GET", "/api/v1/knowledge", params=params
        )
        return resp
