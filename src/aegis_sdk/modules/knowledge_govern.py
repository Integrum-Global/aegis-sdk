"""
Knowledge Governance Module for Agentic OS SDK.

Provides the knowledge lifecycle, editorial review workflow,
knowledge-share-policy (KSP) management, knowledge categories, and the
adjacent content-governance surfaces (content reviews, content templates,
data-source registry, ABAC policies) that the GUI's Knowledge Management +
Content Governance pages consume but the SDK could not previously reach.

Self-contained module: local Pydantic
models, no shared imports from client.py / modules/__init__.py / types.py.
Complements (does NOT edit) ``standup/knowledge.py`` (create/get/publish
only) by adding the missing list/lifecycle/KSP/content-governance surface.

Every route below is verified against the deployed API:

    (prefix /api/v1/knowledge)
        GET    /api/v1/knowledge                          -> list()
        PUT    /api/v1/knowledge/{id}                      -> update()
        DELETE /api/v1/knowledge/{id}                      -> delete()
        GET    /api/v1/knowledge/search                    -> search()
        POST   /api/v1/knowledge/{id}/archive               -> archive()
        POST   /api/v1/knowledge/{id}/version               -> create_version()

    (no prefix; paths self-contained)
        POST   /api/v1/knowledge/{id}/submit                -> submit_for_review()
        POST   /api/v1/knowledge/{id}/assign-reviewer        -> assign_reviewer()
        POST   /api/v1/knowledge/{id}/approve                -> approve()
        POST   /api/v1/knowledge/{id}/reject                 -> reject()
        POST   /api/v1/knowledge/{id}/request-changes        -> request_changes()
        GET    /api/v1/knowledge-reviews                    -> list_review_queue()

    (prefix /api/v1/knowledge-share-policies)
        GET    /api/v1/knowledge-share-policies              -> list_share_policies()
        POST   /api/v1/knowledge-share-policies              -> create_share_policy()
        GET    /api/v1/knowledge-share-policies/{id}         -> get_share_policy()
        PUT    /api/v1/knowledge-share-policies/{id}         -> update_share_policy()
        DELETE /api/v1/knowledge-share-policies/{id}         -> delete_share_policy()
        POST   /api/v1/knowledge-share-policies/{id}/suspend  -> suspend_share_policy()
        POST   /api/v1/knowledge-share-policies/{id}/reactivate -> reactivate_share_policy()

    (prefix /api/v1/knowledge-categories)
        GET    /api/v1/knowledge-categories                 -> list_categories()
        POST   /api/v1/knowledge-categories                 -> create_category()
        PUT    /api/v1/knowledge-categories/{id}            -> update_category()
        DELETE /api/v1/knowledge-categories/{id}            -> delete_category()

    (prefix /api/v1/content-reviews)
        GET    /api/v1/content-reviews                      -> list_content_reviews()
        POST   /api/v1/content-reviews                      -> create_content_review()
        GET    /api/v1/content-reviews/{id}                 -> get_content_review()
        POST   /api/v1/content-reviews/{id}/submit          -> submit_content_review()
        POST   /api/v1/content-reviews/{id}/approve         -> approve_content_review()
        POST   /api/v1/content-reviews/{id}/reject          -> reject_content_review()
        POST   /api/v1/content-reviews/{id}/reopen          -> reopen_content_review()
        DELETE /api/v1/content-reviews/{id}                 -> delete_content_review()

    (prefix /api/v1/content-templates)
        GET    /api/v1/content-templates                    -> list_content_templates()
        POST   /api/v1/content-templates                    -> create_content_template()
        GET    /api/v1/content-templates/{id}               -> get_content_template()
        PUT    /api/v1/content-templates/{id}               -> update_content_template()
        DELETE /api/v1/content-templates/{id}               -> delete_content_template()

    (prefix /api/v1/data-source-registry)
        GET    /api/v1/data-source-registry                 -> list_data_sources()
        POST   /api/v1/data-source-registry                 -> create_data_source()
        GET    /api/v1/data-source-registry/{id}            -> get_data_source()
        PUT    /api/v1/data-source-registry/{id}            -> update_data_source()
        DELETE /api/v1/data-source-registry/{id}            -> delete_data_source()

    (prefix /api/v1/policies, ABAC)
        GET    /api/v1/policies                             -> list_policies()
        POST   /api/v1/policies                             -> create_policy()
        GET    /api/v1/policies/{id}                        -> get_policy()
        PUT    /api/v1/policies/{id}                        -> update_policy()
        DELETE /api/v1/policies/{id}                        -> delete_policy()
        POST   /api/v1/policies/{id}/assign                 -> assign_policy()
        DELETE /api/v1/policies/assignments/{id}            -> unassign_policy()
        GET    /api/v1/policies/user/{id}                   -> get_user_policies()
        POST   /api/v1/policies/evaluate                    -> evaluate_access()
        POST   /api/v1/policies/validate-conditions         -> validate_policy_conditions()
        GET    /api/v1/policies/{id}/references             -> get_policy_references()
        POST   /api/v1/policies/validate-conflicts          -> validate_policy_conflicts()
        POST   /api/v1/policies/resolve-conflict            -> resolve_policy_conflict()

Rows verified-and-corrected against the TRACK-C-FILL-MANIFEST.md manifest:

- The manifest's ``nearest_sdk_method`` column for ``GET /api/v1/knowledge``
  cites ``standup.knowledge.get`` — confirmed there is NO existing ``list()``
  anywhere in the SDK; this module adds it fresh.
- ``content-reviews`` / ``content-templates`` / ``data-source-registry`` /
  ABAC ``policies`` endpoints declare NO ``response_model`` on the backend
  (bare ``-> dict``), so this module returns ``dict[str, Any]`` /
  ``RecordsEnvelope`` for those surfaces rather than inventing a strict
  Pydantic contract the backend does not itself pin (dead-feature-detection
  MUST-1 — no consumed field without a verified producer).
- Skipped (P2, out of scope per manifest): ``by-path``, ``children``,
  ``review-history``, ``versions`` list, ``restore``, governance explainers,
  policy validate-conditions/validate-conflicts/resolve-conflict/references,
  policy assign/unassign/user-policies/evaluate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from .._http import encode_path_param

if TYPE_CHECKING:
    from .._http import HTTPClient


# ---------------------------------------------------------------------------
# Knowledge models (mirrors KnowledgeResponse)
# ---------------------------------------------------------------------------


class KnowledgeItem(BaseModel):
    """Knowledge item (KnowledgeResponse, snake_case)."""

    id: str
    organization_id: str
    title: str
    slug: str | None = None
    content_markdown: str
    summary: str | None = None
    knowledge_type: str
    category: str | None = None
    path: str
    parent_path: str | None = None
    classification: str | None = None
    access_level: str | None = None
    compartment: str | None = None
    owner_unit_id: str | None = None
    tags_json: str = "[]"
    keywords_json: str = "[]"
    content_version: int
    previous_version_id: str | None = None
    status: str
    metadata_json: str = "{}"
    review_date: str | None = None
    created_by: str | None = None
    last_reviewed_by: str | None = None
    last_reviewed_at: str | None = None
    created_at: str
    updated_at: str


class KnowledgeItemList(BaseModel):
    """Paginated knowledge listing (``{records, total}``)."""

    records: list[KnowledgeItem]
    total: int


class MessageResult(BaseModel):
    """Simple message response (MessageResponse)."""

    message: str


class KnowledgeReviewResult(BaseModel):
    """Result of a review-lifecycle transition (ReviewResponse)."""

    review_id: str
    status: str


class KnowledgeRevisionResult(BaseModel):
    """Result of creating a draft revision (RevisionResponse)."""

    new_knowledge_id: str
    previous_version_id: str
    content_version: int


# ---------------------------------------------------------------------------
# Knowledge-share-policy models (mirrors PolicyResponse in
# ---------------------------------------------------------------------------


class KnowledgeSharePolicy(BaseModel):
    """Knowledge-share-policy record (PolicyResponse, snake_case)."""

    id: str
    organization_id: str
    source_unit_id: str
    source_unit_name: str | None = None
    target_entity_type: str
    target_entity_id: str
    target_unit_name: str | None = None
    shared_paths_json: str = "[]"
    shared_classifications_json: str = "[]"
    shared_types_json: str = "[]"
    min_authority_level: int = 1
    conditions_json: str = "{}"
    granted_by_role_id: str
    status: str
    review_at: str | None = None
    expires_at: str | None = None
    metadata_json: str = "{}"
    created_at: str
    updated_at: str


class KnowledgeSharePolicyList(BaseModel):
    """Paginated KSP listing (``{records, total}``)."""

    records: list[KnowledgeSharePolicy]
    total: int


# ---------------------------------------------------------------------------
# Knowledge category model (mirrors KnowledgeCategoryResponse in
# ---------------------------------------------------------------------------


class KnowledgeCategory(BaseModel):
    """Knowledge category record (KnowledgeCategoryResponse)."""

    id: str
    organization_id: str
    name: str
    display_name: str
    description: str
    icon: str
    parent_id: str | None = None
    sort_order: int
    status: str
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Generic envelope for the un-typed content-governance surfaces
# (content-reviews, content-templates, data-source-registry, ABAC policies —
# none of these declare a backend response_model; see module docstring).
# ---------------------------------------------------------------------------


class RecordsEnvelope(BaseModel):
    """Generic ``{records, total}`` envelope for un-typed list endpoints."""

    records: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class KnowledgeGovernModule:
    """
    Knowledge governance module.

    Covers the knowledge lifecycle (list/update/delete/search/archive/
    version), the editorial review workflow (submit/assign/approve/reject/
    request-changes/queue), knowledge-share-policy management, knowledge
    categories, and the adjacent content-governance CRUD surfaces
    (content reviews, content templates, data-source registry, ABAC
    policies).

    Example:
        >>> items = await client.knowledge_govern.list(status="draft")
        >>> await client.knowledge_govern.submit_for_review(
        ...     items.records[0].id, change_summary="Initial draft"
        ... )
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    # ------------------------------------------------------------------
    # Knowledge core — list / update / delete / search / archive / version
    # ------------------------------------------------------------------

    async def list(
        self,
        path_prefix: str | None = None,
        knowledge_type: str | None = None,
        classification: str | None = None,
        category: str | None = None,
        owner_unit_id: str | None = None,
        status: str = "published",
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> KnowledgeItemList:
        """
        List knowledge items in the current user's organization.

        Server: ``GET /api/v1/knowledge``.

        Args:
            path_prefix: Filter by containment path prefix
            knowledge_type: Filter by type (policy/procedure/reference/faq)
            classification: Filter by EATP classification
            category: Filter by category
            owner_unit_id: Filter by owner unit
            status: Filter by lifecycle status (default "published")
            include_archived: Include archived items
            limit: Maximum results (1-200)
            offset: Pagination offset

        Returns:
            KnowledgeItemList: records + total
        """
        params: dict[str, Any] = {
            "status": status,
            "include_archived": include_archived,
            "limit": limit,
            "offset": offset,
        }
        if path_prefix:
            params["path_prefix"] = path_prefix
        if knowledge_type:
            params["knowledge_type"] = knowledge_type
        if classification:
            params["classification"] = classification
        if category:
            params["category"] = category
        if owner_unit_id:
            params["owner_unit_id"] = owner_unit_id

        response = await self._http.request("GET", "/api/v1/knowledge", params=params)
        return KnowledgeItemList(
            records=[KnowledgeItem(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def update(self, knowledge_id: str, **fields: Any) -> KnowledgeItem:
        """
        Update a knowledge item.

        Server: ``PUT /api/v1/knowledge/{knowledge_id}``.

        Args:
            knowledge_id: Knowledge item ID
            **fields: Any of title, content_markdown, knowledge_type, path,
                classification, access_level, compartment, slug, summary,
                category, parent_path, owner_unit_id, tags, keywords,
                metadata, review_date, status

        Returns:
            KnowledgeItem: Updated item
        """
        response = await self._http.request(
            "PUT", f"/api/v1/knowledge/{encode_path_param(knowledge_id)}", json_data=fields
        )
        return KnowledgeItem(**response)

    async def delete(self, knowledge_id: str, hard: bool = False) -> MessageResult:
        """
        Delete a knowledge item (soft-delete/archive by default).

        Server: ``DELETE /api/v1/knowledge/{knowledge_id}``.

        Args:
            knowledge_id: Knowledge item ID
            hard: If True, permanently delete instead of soft-delete

        Returns:
            MessageResult: Confirmation message
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}",
            params={"hard": hard},
        )
        return MessageResult(**response)

    async def search(
        self,
        q: str,
        knowledge_type: str | None = None,
        classification: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[KnowledgeItem]:
        """
        Full-text search across knowledge items.

        Server: ``GET /api/v1/knowledge/search``.

        Args:
            q: Search query (required, non-empty)
            knowledge_type: Filter by type
            classification: Filter by EATP classification
            tags: Filter by tags
            limit: Maximum results (1-200)

        Returns:
            list[KnowledgeItem]: Matching items, clearance-filtered
        """
        params: dict[str, Any] = {"q": q, "limit": limit}
        if knowledge_type:
            params["knowledge_type"] = knowledge_type
        if classification:
            params["classification"] = classification
        if tags:
            params["tags"] = tags

        response = await self._http.request("GET", "/api/v1/knowledge/search", params=params)
        return [KnowledgeItem(**r) for r in response]

    async def archive(self, knowledge_id: str) -> KnowledgeItem:
        """
        Archive a knowledge item (lifecycle transition).

        Server: ``POST /api/v1/knowledge/{knowledge_id}/archive``.

        Args:
            knowledge_id: Knowledge item ID

        Returns:
            KnowledgeItem: Archived item
        """
        response = await self._http.request(
            "POST", f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/archive"
        )
        return KnowledgeItem(**response)

    async def create_version(self, knowledge_id: str, content_markdown: str) -> KnowledgeItem:
        """
        Create a new content version of a knowledge item.

        Server: ``POST /api/v1/knowledge/{knowledge_id}/version``.

        Args:
            knowledge_id: Knowledge item ID
            content_markdown: New markdown content (non-empty)

        Returns:
            KnowledgeItem: The new version's record
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/version",
            json_data={"content_markdown": content_markdown},
        )
        return KnowledgeItem(**response)

    # ------------------------------------------------------------------
    # Editorial review workflow (knowledge_reviews.py)
    # ------------------------------------------------------------------

    async def submit_for_review(
        self, knowledge_id: str, change_summary: str
    ) -> KnowledgeReviewResult:
        """
        Submit a draft knowledge item for editorial review.

        Server: ``POST /api/v1/knowledge/{knowledge_id}/submit``.

        Args:
            knowledge_id: Knowledge item ID
            change_summary: Summary of what changed (non-empty)

        Returns:
            KnowledgeReviewResult: review_id + status
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/submit",
            json_data={"change_summary": change_summary},
        )
        return KnowledgeReviewResult(**response)

    async def assign_reviewer(self, knowledge_id: str, reviewer_id: str) -> KnowledgeReviewResult:
        """
        Assign a reviewer to the most recent pending review for this item.

        Server: ``POST /api/v1/knowledge/{knowledge_id}/assign-reviewer``.

        Args:
            knowledge_id: Knowledge item ID
            reviewer_id: ID of the reviewer to assign

        Returns:
            KnowledgeReviewResult: review_id + status
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/assign-reviewer",
            json_data={"reviewer_id": reviewer_id},
        )
        return KnowledgeReviewResult(**response)

    async def approve(self, knowledge_id: str, decision_comment: str) -> KnowledgeReviewResult:
        """
        Approve a knowledge item in review (self-approval prevention enforced).

        Server: ``POST /api/v1/knowledge/{knowledge_id}/approve``.

        Args:
            knowledge_id: Knowledge item ID
            decision_comment: Required reviewer comment (non-empty)

        Returns:
            KnowledgeReviewResult: review_id + status
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/approve",
            json_data={"decision_comment": decision_comment},
        )
        return KnowledgeReviewResult(**response)

    async def reject(self, knowledge_id: str, decision_comment: str) -> KnowledgeReviewResult:
        """
        Reject a knowledge item in review (reverts to draft).

        Server: ``POST /api/v1/knowledge/{knowledge_id}/reject``.

        Args:
            knowledge_id: Knowledge item ID
            decision_comment: Required reviewer comment (non-empty)

        Returns:
            KnowledgeReviewResult: review_id + status
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/reject",
            json_data={"decision_comment": decision_comment},
        )
        return KnowledgeReviewResult(**response)

    async def request_changes(
        self, knowledge_id: str, decision_comment: str
    ) -> KnowledgeReviewResult:
        """
        Request changes on a knowledge item under review (reverts to draft).

        Server: ``POST /api/v1/knowledge/{knowledge_id}/request-changes``.

        Args:
            knowledge_id: Knowledge item ID
            decision_comment: Required reviewer comment (non-empty)

        Returns:
            KnowledgeReviewResult: review_id + status
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/request-changes",
            json_data={"decision_comment": decision_comment},
        )
        return KnowledgeReviewResult(**response)

    async def create_revision(self, knowledge_id: str) -> KnowledgeRevisionResult:
        """
        Create a new draft revision of a published knowledge item.

        The original published version remains visible to agents until the
        new revision completes the review cycle and is published.

        Server: ``POST /api/v1/knowledge/{knowledge_id}/create-revision``.

        Args:
            knowledge_id: Knowledge item ID (must be published)

        Returns:
            KnowledgeRevisionResult: new_knowledge_id + previous_version_id +
            content_version
        """
        response = await self._http.request(
            "POST", f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/create-revision"
        )
        return KnowledgeRevisionResult(**response)

    async def unarchive(self, knowledge_id: str) -> KnowledgeReviewResult:
        """
        Unarchive a knowledge item by submitting it for re-review.

        Archived items cannot be directly restored to published status — they
        must pass through the full review cycle again.

        Server: ``POST /api/v1/knowledge/{knowledge_id}/unarchive``.

        Args:
            knowledge_id: Knowledge item ID (must be archived)

        Returns:
            KnowledgeReviewResult: review_id + status
        """
        response = await self._http.request(
            "POST", f"/api/v1/knowledge/{encode_path_param(knowledge_id)}/unarchive"
        )
        return KnowledgeReviewResult(**response)

    async def list_review_queue(self, status: str | None = None) -> list[dict[str, Any]]:
        """
        List the org-wide knowledge review queue (ReviewQueueWidget).

        Server: ``GET /api/v1/knowledge-reviews``.
        Returns a raw list (the backend declares no response_model and the
        service returns ``list[dict]`` directly — see
        ``KnowledgeReviewService.list_review_queue``).

        Args:
            status: Optional status filter

        Returns:
            list[dict]: Pending/in-review/etc. review records
        """
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        response = await self._http.request("GET", "/api/v1/knowledge-reviews", params=params)
        return response

    # ------------------------------------------------------------------
    # Knowledge-share-policies (KSP)
    # ------------------------------------------------------------------

    async def list_share_policies(
        self,
        source_unit_id: str | None = None,
        target_entity_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> KnowledgeSharePolicyList:
        """
        List cross-unit knowledge-share policies (KSP page).

        Server: ``GET /api/v1/knowledge-share-policies``.

        Args:
            source_unit_id: Filter by source unit ID
            target_entity_id: Filter by target entity ID
            status: Filter by status
            limit: Maximum results (1-500)
            offset: Pagination offset

        Returns:
            KnowledgeSharePolicyList: records + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if source_unit_id:
            params["source_unit_id"] = source_unit_id
        if target_entity_id:
            params["target_entity_id"] = target_entity_id
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET", "/api/v1/knowledge-share-policies", params=params
        )
        return KnowledgeSharePolicyList(
            records=[KnowledgeSharePolicy(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def list_share_policies_due_for_review(self) -> KnowledgeSharePolicyList:
        """
        List active knowledge-share policies whose review is overdue.

        Returns only active policies with a ``review_at`` in the past (the KSP
        page's "due for review" widget).

        Server: ``GET /api/v1/knowledge-share-policies/due-for-review``.

        Returns:
            KnowledgeSharePolicyList: records + total
        """
        response = await self._http.request(
            "GET", "/api/v1/knowledge-share-policies/due-for-review"
        )
        return KnowledgeSharePolicyList(
            records=[KnowledgeSharePolicy(**r) for r in response.get("records", [])],
            total=response.get("total", 0),
        )

    async def create_share_policy(
        self,
        source_unit_id: str,
        target_entity_type: str,
        target_entity_id: str,
        granted_by_role_id: str,
        shared_paths: list[str] | None = None,
        shared_classifications: list[str] | None = None,
        shared_types: list[str] | None = None,
        min_authority_level: int = 1,
        conditions: dict[str, Any] | None = None,
        review_at: str | None = None,
        expires_at: str | None = None,
    ) -> KnowledgeSharePolicy:
        """
        Create a knowledge-share policy (grant downward knowledge flow).

        Server: ``POST /api/v1/knowledge-share-policies``.

        Args:
            source_unit_id: Unit granting the share
            target_entity_type: "unit" or "role"
            target_entity_id: Target unit/role ID
            granted_by_role_id: Role authorizing the grant
            shared_paths: Path scopes shared (default: [])
            shared_classifications: EATP classifications shared (default: [])
            shared_types: Knowledge types shared (default: [])
            min_authority_level: Minimum authority level (1-5, default 1)
            conditions: Optional condition dict
            review_at: Optional ISO timestamp for scheduled review
            expires_at: Optional ISO timestamp for expiry

        Returns:
            KnowledgeSharePolicy: Created policy
        """
        data: dict[str, Any] = {
            "source_unit_id": source_unit_id,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
            "granted_by_role_id": granted_by_role_id,
            "shared_paths": shared_paths or [],
            "shared_classifications": shared_classifications or [],
            "shared_types": shared_types or [],
            "min_authority_level": min_authority_level,
        }
        if conditions is not None:
            data["conditions"] = conditions
        if review_at:
            data["review_at"] = review_at
        if expires_at:
            data["expires_at"] = expires_at

        response = await self._http.request(
            "POST", "/api/v1/knowledge-share-policies", json_data=data
        )
        return KnowledgeSharePolicy(**response)

    async def get_share_policy(self, policy_id: str) -> KnowledgeSharePolicy:
        """
        Get a knowledge-share policy by ID.

        Server: ``GET /api/v1/knowledge-share-policies/{policy_id}``.

        Args:
            policy_id: Policy ID

        Returns:
            KnowledgeSharePolicy: Policy detail
        """
        response = await self._http.request(
            "GET", f"/api/v1/knowledge-share-policies/{encode_path_param(policy_id)}"
        )
        return KnowledgeSharePolicy(**response)

    async def update_share_policy(self, policy_id: str, **fields: Any) -> KnowledgeSharePolicy:
        """
        Update a knowledge-share policy.

        Server: ``PUT /api/v1/knowledge-share-policies/{policy_id}``.

        Args:
            policy_id: Policy ID
            **fields: Any of shared_paths, shared_classifications,
                shared_types, min_authority_level, conditions, review_at,
                expires_at

        Returns:
            KnowledgeSharePolicy: Updated policy
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/knowledge-share-policies/{encode_path_param(policy_id)}",
            json_data=fields,
        )
        return KnowledgeSharePolicy(**response)

    async def delete_share_policy(self, policy_id: str) -> None:
        """
        Delete a knowledge-share policy (soft-delete by default).

        Server: ``DELETE /api/v1/knowledge-share-policies/{policy_id}``
        (204 No Content).

        Args:
            policy_id: Policy ID
        """
        await self._http.request(
            "DELETE", f"/api/v1/knowledge-share-policies/{encode_path_param(policy_id)}"
        )

    async def suspend_share_policy(
        self, policy_id: str, reason: str | None = None
    ) -> KnowledgeSharePolicy:
        """
        Suspend an active knowledge-share policy.

        Server: ``POST /api/v1/knowledge-share-policies/{policy_id}/suspend``.

        Args:
            policy_id: Policy ID
            reason: Optional suspension reason

        Returns:
            KnowledgeSharePolicy: Suspended policy
        """
        data = {"reason": reason} if reason is not None else None
        response = await self._http.request(
            "POST",
            f"/api/v1/knowledge-share-policies/{encode_path_param(policy_id)}/suspend",
            json_data=data,
        )
        return KnowledgeSharePolicy(**response)

    async def reactivate_share_policy(self, policy_id: str) -> KnowledgeSharePolicy:
        """
        Reactivate a suspended or expired knowledge-share policy.

        Server: ``POST /api/v1/knowledge-share-policies/{policy_id}/reactivate``.

        Args:
            policy_id: Policy ID

        Returns:
            KnowledgeSharePolicy: Reactivated policy
        """
        response = await self._http.request(
            "POST", f"/api/v1/knowledge-share-policies/{encode_path_param(policy_id)}/reactivate"
        )
        return KnowledgeSharePolicy(**response)

    # ------------------------------------------------------------------
    # Knowledge categories
    # ------------------------------------------------------------------

    async def list_categories(self, status: str | None = None) -> list[KnowledgeCategory]:
        """
        List knowledge categories for the current user's organization.

        Server: ``GET /api/v1/knowledge-categories``.

        Args:
            status: Filter by status (active/archived); defaults to all

        Returns:
            list[KnowledgeCategory]: Categories
        """
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        response = await self._http.request("GET", "/api/v1/knowledge-categories", params=params)
        return [KnowledgeCategory(**c) for c in response]

    async def create_category(
        self,
        name: str,
        display_name: str,
        description: str = "",
        icon: str = "",
        parent_id: str | None = None,
        sort_order: int = 0,
    ) -> KnowledgeCategory:
        """
        Create a new knowledge category.

        Server: ``POST /api/v1/knowledge-categories``.

        Args:
            name: Machine key for the category (auto-lowercased)
            display_name: Human-readable category name
            description: Optional description
            icon: Optional icon identifier
            parent_id: Optional parent category ID for hierarchy
            sort_order: Sort order (lower values sort first)

        Returns:
            KnowledgeCategory: Created category
        """
        data: dict[str, Any] = {
            "name": name,
            "display_name": display_name,
            "description": description,
            "icon": icon,
            "sort_order": sort_order,
        }
        if parent_id:
            data["parent_id"] = parent_id

        response = await self._http.request("POST", "/api/v1/knowledge-categories", json_data=data)
        return KnowledgeCategory(**response)

    async def update_category(self, category_id: str, **fields: Any) -> KnowledgeCategory:
        """
        Update an existing knowledge category (partial update).

        Server: ``PUT /api/v1/knowledge-categories/{category_id}``.

        Args:
            category_id: Category ID
            **fields: Any of display_name, description, icon, parent_id,
                sort_order, status ("active"/"archived")

        Returns:
            KnowledgeCategory: Updated category
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/knowledge-categories/{encode_path_param(category_id)}",
            json_data=fields,
        )
        return KnowledgeCategory(**response)

    async def delete_category(self, category_id: str) -> KnowledgeCategory:
        """
        Archive a knowledge category (soft-delete).

        Server: ``DELETE /api/v1/knowledge-categories/{category_id}``.

        Args:
            category_id: Category ID

        Returns:
            KnowledgeCategory: Archived category
        """
        response = await self._http.request(
            "DELETE", f"/api/v1/knowledge-categories/{encode_path_param(category_id)}"
        )
        return KnowledgeCategory(**response)

    # ------------------------------------------------------------------
    # Content reviews (generic content-review FSM, distinct from the
    # knowledge editorial workflow above)
    # ------------------------------------------------------------------

    async def list_content_reviews(self, state: str | None = None) -> RecordsEnvelope:
        """
        List the caller-tenant's content reviews.

        Server: ``GET /api/v1/content-reviews``.
        No response_model declared server-side — returns the raw
        ``{records, total}`` envelope.

        Args:
            state: Optional FSM state filter (draft/in_review/approved/
                rejected)

        Returns:
            RecordsEnvelope: records + total
        """
        params: dict[str, Any] = {}
        if state:
            params["state"] = state
        response = await self._http.request("GET", "/api/v1/content-reviews", params=params)
        return RecordsEnvelope(**response)

    async def create_content_review(
        self, content_ref: str, content_type: str = "generic", title: str = ""
    ) -> dict[str, Any]:
        """
        Create a content review (lands in draft) for the caller's tenant.

        Server: ``POST /api/v1/content-reviews``.

        Args:
            content_ref: Reference to the reviewed content (non-empty)
            content_type: Content type label (default "generic")
            title: Optional title

        Returns:
            dict: Created content review record
        """
        data = {"content_ref": content_ref, "content_type": content_type, "title": title}
        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/content-reviews", json_data=data
        )
        return response

    async def get_content_review(self, review_id: str) -> dict[str, Any]:
        """
        Get one content review (tenant-verified).

        Server: ``GET /api/v1/content-reviews/{review_id}``.

        Args:
            review_id: Content review ID

        Returns:
            dict: Content review record
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/content-reviews/{encode_path_param(review_id)}"
        )
        return response

    async def submit_content_review(self, review_id: str) -> dict[str, Any]:
        """
        Submit a content review: draft -> in_review.

        Server: ``POST /api/v1/content-reviews/{review_id}/submit``.

        Args:
            review_id: Content review ID

        Returns:
            dict: Content review record with updated state
        """
        response: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/content-reviews/{encode_path_param(review_id)}/submit"
        )
        return response

    async def approve_content_review(
        self, review_id: str, comment: str | None = None
    ) -> dict[str, Any]:
        """
        Approve a content review: in_review -> approved.

        Server: ``POST /api/v1/content-reviews/{review_id}/approve``.

        Args:
            review_id: Content review ID
            comment: Optional reviewer comment

        Returns:
            dict: Content review record with updated state
        """
        data = {"comment": comment} if comment is not None else None
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/content-reviews/{encode_path_param(review_id)}/approve",
            json_data=data,
        )
        return response

    async def reject_content_review(
        self, review_id: str, comment: str | None = None
    ) -> dict[str, Any]:
        """
        Reject a content review: in_review -> rejected.

        Server: ``POST /api/v1/content-reviews/{review_id}/reject``.

        Args:
            review_id: Content review ID
            comment: Optional reviewer comment

        Returns:
            dict: Content review record with updated state
        """
        data = {"comment": comment} if comment is not None else None
        response: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/content-reviews/{encode_path_param(review_id)}/reject", json_data=data
        )
        return response

    async def reopen_content_review(self, review_id: str) -> dict[str, Any]:
        """
        Reopen a content review: {rejected, in_review} -> draft.

        Server: ``POST /api/v1/content-reviews/{review_id}/reopen``.

        Args:
            review_id: Content review ID

        Returns:
            dict: Content review record with updated state
        """
        response: dict[str, Any] = await self._http.request(
            "POST", f"/api/v1/content-reviews/{encode_path_param(review_id)}/reopen"
        )
        return response

    async def delete_content_review(self, review_id: str) -> dict[str, Any]:
        """
        Soft-delete a content review (tenant-verified).

        Server: ``DELETE /api/v1/content-reviews/{review_id}``.

        Args:
            review_id: Content review ID

        Returns:
            dict: ``{"deleted": True, "id": review_id}``
        """
        response: dict[str, Any] = await self._http.request(
            "DELETE", f"/api/v1/content-reviews/{encode_path_param(review_id)}"
        )
        return response

    # ------------------------------------------------------------------
    # Content templates
    # ------------------------------------------------------------------

    async def list_content_templates(self) -> RecordsEnvelope:
        """
        List system + caller-tenant content templates.

        Server: ``GET /api/v1/content-templates``.

        Returns:
            RecordsEnvelope: records + total
        """
        response = await self._http.request("GET", "/api/v1/content-templates")
        return RecordsEnvelope(**response)

    async def create_content_template(
        self,
        name: str,
        description: str | None = None,
        body: str = "",
        template_format: str = "text",
        variables: list[Any] | None = None,
        tags: list[Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """
        Create an org-scoped content template.

        Server: ``POST /api/v1/content-templates``.

        Args:
            name: Template name (non-empty)
            description: Optional description
            body: Template body content
            template_format: Format label (default "text")
            variables: Optional list of template variables
            tags: Optional list of tags
            status: Status label (default "active")

        Returns:
            dict: Created content template record
        """
        data: dict[str, Any] = {
            "name": name,
            "body": body,
            "template_format": template_format,
            "status": status,
        }
        if description is not None:
            data["description"] = description
        if variables is not None:
            data["variables"] = variables
        if tags is not None:
            data["tags"] = tags

        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/content-templates", json_data=data
        )
        return response

    async def get_content_template(self, template_id: str) -> dict[str, Any]:
        """
        Get one content template (system or caller-owned).

        Server: ``GET /api/v1/content-templates/{template_id}``.

        Args:
            template_id: Content template ID

        Returns:
            dict: Content template record
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/content-templates/{encode_path_param(template_id)}"
        )
        return response

    async def update_content_template(self, template_id: str, **fields: Any) -> dict[str, Any]:
        """
        Update a caller-owned content template (partial update).

        Server: ``PUT /api/v1/content-templates/{template_id}``.

        Args:
            template_id: Content template ID
            **fields: Any of name, description, body, template_format,
                variables, tags, status

        Returns:
            dict: Updated content template record
        """
        response: dict[str, Any] = await self._http.request(
            "PUT", f"/api/v1/content-templates/{encode_path_param(template_id)}", json_data=fields
        )
        return response

    async def delete_content_template(self, template_id: str) -> dict[str, Any]:
        """
        Soft-delete a caller-owned content template.

        Server: ``DELETE /api/v1/content-templates/{template_id}``.

        Args:
            template_id: Content template ID

        Returns:
            dict: ``{"deleted": True, "id": template_id}``
        """
        response: dict[str, Any] = await self._http.request(
            "DELETE", f"/api/v1/content-templates/{encode_path_param(template_id)}"
        )
        return response

    # ------------------------------------------------------------------
    # Data-source registry
    # ------------------------------------------------------------------

    async def list_data_sources(self) -> RecordsEnvelope:
        """
        List the caller-tenant's governed external data sources.

        Server: ``GET /api/v1/data-source-registry``.

        Returns:
            RecordsEnvelope: records + total
        """
        response = await self._http.request("GET", "/api/v1/data-source-registry")
        return RecordsEnvelope(**response)

    async def create_data_source(
        self,
        name: str,
        source_type: str = "custom",
        endpoint_url: str | None = None,
        status: str = "pending",
        config: dict[str, Any] | None = None,
        credentials_ref: str | None = None,
    ) -> dict[str, Any]:
        """
        Register a governed external data source.

        Server: ``POST /api/v1/data-source-registry``. ``credentials_ref`` is an opaque
        pointer to a secret-store entry — never a plaintext secret.

        Args:
            name: Data source name (non-empty)
            source_type: Source type label (default "custom")
            endpoint_url: Optional endpoint URL
            status: Status label (default "pending")
            config: Optional config dict
            credentials_ref: Optional opaque secret-store pointer

        Returns:
            dict: Created data source record
        """
        data: dict[str, Any] = {"name": name, "source_type": source_type, "status": status}
        if endpoint_url is not None:
            data["endpoint_url"] = endpoint_url
        if config is not None:
            data["config"] = config
        if credentials_ref is not None:
            data["credentials_ref"] = credentials_ref

        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/data-source-registry", json_data=data
        )
        return response

    async def get_data_source(self, source_id: str) -> dict[str, Any]:
        """
        Get a single governed data-source registry entry.

        Server: ``GET /api/v1/data-source-registry/{source_id}``.

        Args:
            source_id: Data source ID

        Returns:
            dict: Data source record
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/data-source-registry/{encode_path_param(source_id)}"
        )
        return response

    async def update_data_source(self, source_id: str, **fields: Any) -> dict[str, Any]:
        """
        Update a governed data-source registry entry (partial update).

        Server: ``PUT /api/v1/data-source-registry/{source_id}``.

        Args:
            source_id: Data source ID
            **fields: Any of name, source_type, endpoint_url, status,
                config, credentials_ref

        Returns:
            dict: Updated data source record
        """
        response: dict[str, Any] = await self._http.request(
            "PUT", f"/api/v1/data-source-registry/{encode_path_param(source_id)}", json_data=fields
        )
        return response

    async def delete_data_source(self, source_id: str) -> dict[str, Any]:
        """
        Soft-delete a governed data-source registry entry.

        Server: ``DELETE /api/v1/data-source-registry/{source_id}``.

        Args:
            source_id: Data source ID

        Returns:
            dict: ``{"deleted": True, "id": source_id}``
        """
        response: dict[str, Any] = await self._http.request(
            "DELETE", f"/api/v1/data-source-registry/{encode_path_param(source_id)}"
        )
        return response

    # ------------------------------------------------------------------
    # ABAC policies (/govern/policies page)
    # ------------------------------------------------------------------

    async def list_policies(
        self,
        status: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> RecordsEnvelope:
        """
        List ABAC policies for the organization.

        Server: ``GET /api/v1/policies``.

        Args:
            status: Filter by status (active/inactive)
            resource_type: Filter by resource type
            limit: Maximum results
            offset: Pagination offset

        Returns:
            RecordsEnvelope: records + total
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if resource_type:
            params["resource_type"] = resource_type

        response = await self._http.request("GET", "/api/v1/policies", params=params)
        return RecordsEnvelope(**response)

    async def create_policy(
        self,
        name: str,
        resource_type: str,
        action: str,
        effect: str,
        description: str | None = None,
        conditions: dict[str, Any] | None = None,
        priority: int = 0,
        status: str = "active",
    ) -> dict[str, Any]:
        """
        Create a new ABAC policy.

        Server: ``POST /api/v1/policies``.

        Args:
            name: Policy name (non-empty)
            resource_type: Resource type pattern (lowercase, underscores, ``*``)
            action: Action pattern (lowercase, underscores, ``*``)
            effect: "allow" or "deny"
            description: Optional description
            conditions: Optional condition dict
            priority: Priority (0-1000, default 0)
            status: "active" or "inactive" (default "active")

        Returns:
            dict: Created policy record
        """
        data: dict[str, Any] = {
            "name": name,
            "resource_type": resource_type,
            "action": action,
            "effect": effect,
            "conditions": conditions or {},
            "priority": priority,
            "status": status,
        }
        if description is not None:
            data["description"] = description

        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/policies", json_data=data
        )
        return response

    async def get_policy(self, policy_id: str) -> dict[str, Any]:
        """
        Get a specific ABAC policy.

        Server: ``GET /api/v1/policies/{policy_id}``.

        Args:
            policy_id: Policy ID

        Returns:
            dict: Policy record
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/policies/{encode_path_param(policy_id)}"
        )
        return response

    async def update_policy(self, policy_id: str, **fields: Any) -> dict[str, Any]:
        """
        Update an ABAC policy (partial update).

        Server: ``PUT /api/v1/policies/{policy_id}``.

        Args:
            policy_id: Policy ID
            **fields: Any of name, description, resource_type, action,
                effect, conditions, priority, status

        Returns:
            dict: Updated policy record
        """
        response: dict[str, Any] = await self._http.request(
            "PUT", f"/api/v1/policies/{encode_path_param(policy_id)}", json_data=fields
        )
        return response

    async def delete_policy(self, policy_id: str) -> None:
        """
        Delete an ABAC policy.

        Server: ``DELETE /api/v1/policies/{policy_id}``
        (204 No Content).

        Args:
            policy_id: Policy ID
        """
        await self._http.request("DELETE", f"/api/v1/policies/{encode_path_param(policy_id)}")

    # ------------------------------------------------------------------
    # ABAC policies — assignment, evaluation, conflicts (/api/v1/policies)
    #
    # Router-level persona gate: ``admin`` ONLY. Not ``architect``, and not an
    # API key (an API-key principal carries no persona at all), so every method
    # below returns 403 for both. Each route then requires its own
    # ``policies:*`` permission.
    # ------------------------------------------------------------------

    async def assign_policy(
        self, policy_id: str, principal_type: str, principal_id: str
    ) -> dict[str, Any]:
        """
        Attach a policy to a principal. Responds ``201``.

        Server: ``POST /api/v1/policies/{policy_id}/assign``. Requires
        ``policies:assign``.

        Args:
            policy_id: Policy ID
            principal_type: ``"user"``, ``"team"`` or ``"role"``
            principal_id: For ``user`` and ``team`` this is a row id. For
                ``role`` **either vocabulary is accepted and both bind at
                evaluation time**: an RBAC role NAME (``"admin"``,
                ``"member"``, ``"developer"``), which applies to every user
                carrying that name, or an organization-role id from the D/T/R
                tree, which applies to that one role. The two have very
                different blast radii and the API does not distinguish them for
                you — pass the one you mean.

        Returns:
            dict: The created assignment record.

        Raises:
            NotFoundError: ``404`` — the policy does not exist, is in another
                organization, or the principal is in another organization. All
                three report identically, so a 404 does not tell you which.
            AuthorizationError: ``403`` — an API key, a non-``admin`` persona,
                or a session without ``policies:assign``.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            f"/api/v1/policies/{encode_path_param(policy_id)}/assign",
            json_data={"principal_type": principal_type, "principal_id": principal_id},
        )
        return response

    async def unassign_policy(self, assignment_id: str) -> None:
        """
        Remove a policy assignment.

        Server: ``DELETE /api/v1/policies/assignments/{assignment_id}``
        (``204``, no body). Requires ``policies:assign``.

        Args:
            assignment_id: Assignment ID. Note this is the ASSIGNMENT id
                returned by :meth:`assign_policy`, not the policy id.

        Returns:
            ``None`` — the platform returns no representation of what was
            removed, so capture the assignment record before deleting it if you
            need to audit or recreate it.

        Raises:
            NotFoundError: ``404`` — no such assignment, or it belongs to
                another organization. An assignment has no tenant of its own;
                its owning policy's organization is the boundary.
        """
        await self._http.request(
            "DELETE", f"/api/v1/policies/assignments/{encode_path_param(assignment_id)}"
        )

    async def get_user_policies(self, user_id: str) -> dict[str, Any]:
        """
        List the policies applicable to one user.

        Server: ``GET /api/v1/policies/user/{user_id}``. Requires
        ``policies:read``.

        Args:
            user_id: Subject user ID. Must belong to the caller's organization.

        Returns:
            dict: The user's applicable policies.

        Raises:
            NotFoundError: ``404`` — the subject is in another organization.
                Reported as absent rather than forbidden so this cannot be used
                to enumerate another tenant's users or read their effective
                policy set.
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/policies/user/{encode_path_param(user_id)}"
        )
        return response

    async def evaluate_access(
        self,
        user_id: str,
        resource_type: str,
        action: str,
        resource: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ask whether a subject may perform an action, per ABAC policy.

        Server: ``POST /api/v1/policies/evaluate``. Requires
        ``policies:evaluate``.

        What this is: a query against the policy set for a subject and an
        action you describe. It is **not** the enforcement path — asking here
        neither performs nor authorizes the action, and the real access check
        happens where the action is actually attempted. Use it to explain or
        preview a decision, never as the decision itself.

        Args:
            user_id: Subject user ID. Validated against the caller's
                organization first, so this endpoint cannot be used as an
                authorization oracle for other tenants.
            resource_type: Resource type being accessed
            action: Action being attempted
            resource: Resource attributes for condition evaluation
            context: Additional context attributes

        Returns:
            dict with ``allowed`` (bool) plus the echoed ``user_id``,
            ``resource_type`` and ``action``.

        Raises:
            NotFoundError: ``404`` — the subject is in another organization.
            ServiceUnavailableError: ``503`` — the policy lookup itself failed.
                **Do not read this as a deny.** It means the verdict is
                UNKNOWN; the platform declines to guess in either direction.
                Retry rather than treating it as a decision.
            AuthorizationError: ``403`` — an API key, a non-``admin`` persona,
                or a session without ``policies:evaluate``.
        """
        data: dict[str, Any] = {
            "user_id": user_id,
            "resource_type": resource_type,
            "action": action,
            "resource": resource if resource is not None else {},
            "context": context if context is not None else {},
        }
        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/policies/evaluate", json_data=data
        )
        return response

    async def validate_policy_conditions(
        self, conditions: dict[str, Any] | list[Any]
    ) -> dict[str, Any]:
        """
        Check that a condition expression is well-formed before saving it.

        Server: ``POST /api/v1/policies/validate-conditions``. Requires
        ``policies:read``.

        Validates SHAPE, not outcome: a condition set can be perfectly valid
        here and still match nothing, or match everything.

        Args:
            conditions: The condition expression, as a dict or a list.

        Returns:
            dict: The validation result.
        """
        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/policies/validate-conditions", json_data={"conditions": conditions}
        )
        return response

    async def get_policy_references(self, policy_id: str) -> dict[str, Any]:
        """
        List the resources a policy's conditions refer to, with their status.

        Server: ``GET /api/v1/policies/{policy_id}/references``. Requires
        ``policies:read``.

        Each reference carries a ``status`` of ``valid``, ``orphaned`` (the
        resource no longer exists) or ``changed``. An orphaned reference does
        not disable the policy — the policy stays active and its condition
        simply refers to something that is gone, so treat this as a maintenance
        report rather than a health check.

        Args:
            policy_id: Policy ID

        Returns:
            dict: The referenced resources and their statuses.

        Raises:
            NotFoundError: ``404`` — no such policy in this organization.
        """
        response: dict[str, Any] = await self._http.request(
            "GET", f"/api/v1/policies/{encode_path_param(policy_id)}/references"
        )
        return response

    async def validate_policy_conflicts(self, policy_ids: list[str]) -> dict[str, Any]:
        """
        Find contradictions among a set of policies.

        Server: ``POST /api/v1/policies/validate-conflicts``. Requires at least
        two policy ids; fewer is rejected.

        A conflict is two policies targeting the same ``resource_type`` and
        ``action`` with opposing effects (allow vs deny). Note that an
        **inactive** policy still counts as a member of a conflict pair — it is
        reported at a lower severity rather than dropped, so a conflict listed
        here is not necessarily live today.

        Args:
            policy_ids: At least two policy IDs to compare.

        Returns:
            dict with ``conflicts``: each carries ``id``, ``policy_ids``,
            ``description`` and ``severity`` (``low``/``medium``/``high``). The
            ``id`` is deterministic and is what :meth:`resolve_policy_conflict`
            expects.

        Raises:
            ValidationError: ``422`` — fewer than two ids supplied.
        """
        response: dict[str, Any] = await self._http.request(
            "POST", "/api/v1/policies/validate-conflicts", json_data={"policyIds": policy_ids}
        )
        return response

    async def resolve_policy_conflict(self, conflict_id: str, resolution: str) -> dict[str, Any]:
        """
        Apply a resolution strategy to a detected policy conflict.

        Server: ``POST /api/v1/policies/resolve-conflict``. Requires
        ``policies:update``.

        Args:
            conflict_id: The deterministic ``id`` from
                :meth:`validate_policy_conflicts`. It is recomputed from the
                caller's own organization's policies, so an id minted elsewhere
                reports as unknown.
            resolution: One of:

                * ``"priority"`` — keep the higher-priority policy active,
                  deactivate the other.
                * ``"disable_lower"`` — deactivate the lower-priority policy.
                * ``"merge"`` — **does not actually merge conditions.** It
                  deactivates the lower-priority policy as the safest outcome,
                  which makes it equivalent in effect to ``disable_lower``
                  today. Named for the intent, not the behaviour; do not choose
                  it expecting both policies to survive.

                Every strategy resolves by DEACTIVATING a policy. None of them
                edits a policy's conditions, and none is reversible by this
                endpoint — re-activate through the policy update method.

        Returns:
            dict with ``resolved`` (bool) and ``message``.

        Raises:
            ValidationError: ``400`` — unknown resolution strategy.
            NotFoundError: ``404`` — unknown conflict id, including one minted
                from another tenant's policies.
        """
        response: dict[str, Any] = await self._http.request(
            "POST",
            "/api/v1/policies/resolve-conflict",
            json_data={"conflictId": conflict_id, "resolution": resolution},
        )
        return response
