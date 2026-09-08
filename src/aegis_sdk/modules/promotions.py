"""
Promotions SDK Module (``/api/v1/promotions``).

Environment promotion: move an agent deployment from one environment to
another, under rules that decide whether the move needs an approval first.

Two resources share the prefix:

* **Promotions** — one request to move one deployment. Created, optionally
  approved or rejected, then executed.
* **Promotion rules** — the standing policy that decides whether a promotion
  between a given pair of environments needs approval, how many approvers, and
  whether it runs automatically.

.. important::
    **This router requires the ``architect`` persona and nothing else will do.**
    An API-key credential carries no persona and is refused on every route,
    reads included. So is an organization administrator: the persona gate runs
    **before** RBAC, so a caller holding every ``promotions:*`` and
    ``promotion_rules:*`` grant is still refused without that persona. Use an
    ``architect`` user session.

    Past the persona gate, each route additionally requires its own permission
    (``promotions:create``/``read``/``approve``/``execute``,
    ``promotion_rules:create``/``read``/``update``/``delete``).

.. note::
    Every method here returns ``dict[str, Any]`` (or a list of them), because at
    the time they were written the platform declared no response model for these
    operations and the SDK will not invent one. The keys described per method are
    therefore **observed, not guaranteed**.

    That is the SDK's rule rather than a standing claim about the server: if the
    platform declares models for these operations, the return type can be
    narrowed to them without any signature here changing.
"""

from __future__ import annotations

from typing import Any

from .._http import encode_path_param


class PromotionsModule:
    """
    Promotion SDK module (``/api/v1/promotions``).

    Methods:
        - create() / list() / get(): Promotion requests
        - approve() / reject() / execute(): Move a request along
        - create_rule() / list_rules() / get_rule() / update_rule() /
          delete_rule(): The standing policy

    The target environment is server-verified; the source is not:
        On :meth:`create` the platform reads the target gateway's own recorded
        environment and **refuses the request if your declared
        ``target_environment`` disagrees with it** — so the value that decides
        whether the release is gated cannot be set from the request body.
        ``source_environment`` is taken from your declaration as given; the
        platform does not cross-check it against the source deployment. Treat
        the source half as a label you are asserting, not one the platform
        confirmed.

    Approval and execution are genuinely separated:
        * :meth:`approve` refuses when the approver is the same principal as
          the promotion's recorded requester, and the requester identity is
          captured immutably at create time rather than re-derived later.
        * It also refuses a **machine principal** outright — approval is a
          human act on this surface.
        * :meth:`execute` cannot be used to route around that. A ``pending``
          promotion that requires approval is refused with a message naming the
          missing approval; ``pending`` is executable only when no rule ever
          required an approval for that environment pair.

    Approval executes immediately:
        :meth:`approve` does not merely record a verdict — it runs the
        promotion. There is no approved-but-not-yet-executed window to inspect,
        so do not approve as a "stage it for later" step.

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(base_url=base_url, api_key=architect_session_token)
        >>>
        >>> promo = await client.promotions.create(
        ...     agent_id="agent-1",
        ...     source_deployment_id="dep-staging",
        ...     target_gateway_id="gw-prod",
        ...     source_environment="staging",
        ...     target_environment="production",
        ... )
        >>> if promo["status"] == "pending":
        ...     await client.promotions.approve(promo["id"])
    """

    def __init__(self, http_client):
        """Initialize the promotions module with an HTTP client."""
        self._http = http_client

    async def create(
        self,
        agent_id: str,
        source_deployment_id: str,
        target_gateway_id: str,
        source_environment: str,
        target_environment: str,
    ) -> dict[str, Any]:
        """
        Create a promotion request.

        **This may execute the promotion immediately.** If no rule requires
        approval for this environment pair, the promotion is auto-executed as
        part of this call. Read ``status`` on the result before assuming
        anything is waiting for a human.

        Args:
            agent_id: The agent being promoted
            source_deployment_id: The deployment to promote from
            target_gateway_id: The gateway to promote to. Its **recorded**
                environment is what arms the approval requirement.
            source_environment: The source environment. Caller-declared; not
                cross-checked against the source deployment.
            target_environment: The target environment. Must equal the target
                gateway's recorded environment or the request is refused.

        Returns:
            The created promotion as an untyped dict, carrying at least ``id``,
            ``organization_id``, ``agent_id``, ``status``, the two environment
            fields, and ``created_by``.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, a session
                without the ``architect`` persona, or one lacking
                ``promotions:create``.
            ValidationError: ``400`` — ``target_environment`` disagrees with
                the gateway's recorded environment, or the gateway does not
                exist, belongs to another organization, or has no recorded
                environment. All four deny rather than defaulting to
                unapproved.

        Example:
            >>> promo = await client.promotions.create(
            ...     agent_id="agent-1",
            ...     source_deployment_id="dep-staging",
            ...     target_gateway_id="gw-prod",
            ...     source_environment="staging",
            ...     target_environment="production",
            ... )
        """
        response = await self._http.request(
            "POST",
            "/api/v1/promotions",
            json_data={
                "agent_id": agent_id,
                "source_deployment_id": source_deployment_id,
                "target_gateway_id": target_gateway_id,
                "source_environment": source_environment,
                "target_environment": target_environment,
            },
        )
        return response

    async def list(
        self, status: str | None = None, agent_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List promotions in the caller's organization.

        Args:
            status: Filter by status
            agent_id: Filter by agent

        Returns:
            A **bare list** of untyped promotion dicts — note that
            :meth:`list_rules` returns an envelope instead; the two are not
            symmetrical.

        Example:
            >>> pending = await client.promotions.list(status="pending")
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if agent_id is not None:
            params["agent_id"] = agent_id

        response = await self._http.request(
            "GET", "/api/v1/promotions", params=params or None
        )
        return response or []

    async def get(self, promotion_id: str) -> dict[str, Any]:
        """
        Get one promotion by ID.

        Args:
            promotion_id: Promotion ID

        Returns:
            The promotion as an untyped dict.

        Raises:
            NotFoundError: ``404`` — no such promotion, or it belongs to
                another organization. Both report identically.

        Example:
            >>> promo = await client.promotions.get("promo-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/promotions/{encode_path_param(promotion_id)}"
        )
        return response

    async def approve(self, promotion_id: str) -> dict[str, Any]:
        """
        Approve a pending promotion — and run it.

        Approval and execution are one step. The approver is taken from your
        authenticated session; there is no body and no way to name a different
        approver.

        Args:
            promotion_id: Promotion ID

        Returns:
            The result of the executed promotion, as an untyped dict.

        Raises:
            AuthorizationError: ``403`` — you are the promotion's requester
                (self-approval is refused, against the identity captured when
                it was created), you are a machine principal rather than a
                human, an API-key credential, a missing ``architect`` persona,
                or a missing ``promotions:approve`` permission.
            NotFoundError: ``404`` — no such promotion in this organization.
            ValidationError: ``400`` — the promotion is not ``pending``.

        Example:
            >>> result = await client.promotions.approve("promo-1")
        """
        response = await self._http.request(
            "POST", f"/api/v1/promotions/{encode_path_param(promotion_id)}/approve"
        )
        return response

    async def reject(self, promotion_id: str, reason: str) -> dict[str, Any]:
        """
        Reject a pending promotion.

        Args:
            promotion_id: Promotion ID
            reason: Why it is refused. Required and non-empty.

        Returns:
            The updated promotion as an untyped dict.

        Raises:
            AuthorizationError: ``403`` — a machine principal, an API-key
                credential, a missing ``architect`` persona, or a missing
                ``promotions:approve`` permission (reject shares approve's
                permission, not a separate one).
            NotFoundError: ``404`` — no such promotion in this organization.
            ValidationError: ``400`` — the promotion is not in a rejectable
                state.

        Example:
            >>> await client.promotions.reject("promo-1", reason="Failing canary.")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/promotions/{encode_path_param(promotion_id)}/reject",
            json_data={"reason": reason},
        )
        return response

    async def execute(self, promotion_id: str) -> dict[str, Any]:
        """
        Execute an approved promotion, or a pending one that never needed
        approval.

        This is not a way around :meth:`approve`. A ``pending`` promotion whose
        environment pair requires approval is refused, with a message that
        names the missing approval rather than only the status.

        Args:
            promotion_id: Promotion ID

        Returns:
            The execution result as an untyped dict.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, a missing
                ``architect`` persona, or a missing ``promotions:execute``
                permission.
            NotFoundError: ``404`` — no such promotion in this organization.
            ValidationError: ``400`` — the promotion still awaits approval, or
                its status is otherwise not executable.

        Example:
            >>> await client.promotions.execute("promo-1")
        """
        response = await self._http.request(
            "POST", f"/api/v1/promotions/{encode_path_param(promotion_id)}/execute"
        )
        return response

    async def create_rule(
        self,
        name: str,
        source_environment: str,
        target_environment: str,
        requires_approval: bool = True,
        auto_promote: bool = False,
        required_approvers: int = 1,
        conditions: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """
        Create a promotion rule.

        Args:
            name: Rule name
            source_environment: Source environment this rule governs
            target_environment: Target environment this rule governs
            requires_approval: Whether promotions matching this rule wait for
                an approval. Setting this ``False`` for a pair means
                :meth:`create` auto-executes those promotions with no human in
                the loop — the rule is the control, so treat editing it as a
                governance change rather than configuration.
            auto_promote: Whether matching promotions are raised automatically
            required_approvers: Approver count recorded on the rule
            conditions: Free-form conditions recorded on the rule
            status: ``"active"`` by default

        Returns:
            The created rule as an untyped dict.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, a missing
                ``architect`` persona, or a missing ``promotion_rules:create``
                permission.
            ValidationError: ``400`` — the rule was rejected.

        Example:
            >>> rule = await client.promotions.create_rule(
            ...     name="staging to production",
            ...     source_environment="staging",
            ...     target_environment="production",
            ...     requires_approval=True,
            ... )
        """
        body: dict[str, Any] = {
            "name": name,
            "source_environment": source_environment,
            "target_environment": target_environment,
            "requires_approval": requires_approval,
            "auto_promote": auto_promote,
            "required_approvers": required_approvers,
            "status": status,
        }
        if conditions is not None:
            body["conditions"] = conditions

        response = await self._http.request(
            "POST", "/api/v1/promotions/rules", json_data=body
        )
        return response

    async def list_rules(self, status: str | None = None) -> dict[str, Any]:
        """
        List promotion rules in the caller's organization.

        Args:
            status: Filter by status

        Returns:
            ``{"rules": [...]}`` — an envelope, unlike :meth:`list`, which
            returns a bare list. The asymmetry is the platform's, not the SDK's.

        Example:
            >>> rules = (await client.promotions.list_rules())["rules"]
        """
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status

        response = await self._http.request(
            "GET", "/api/v1/promotions/rules", params=params or None
        )
        return response

    async def get_rule(self, rule_id: str) -> dict[str, Any]:
        """
        Get one promotion rule by ID.

        Args:
            rule_id: Rule ID

        Returns:
            The rule as an untyped dict.

        Raises:
            NotFoundError: ``404`` — no such rule, or it belongs to another
                organization. Both report identically.

        Example:
            >>> rule = await client.promotions.get_rule("rule-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/promotions/rules/{encode_path_param(rule_id)}"
        )
        return response

    async def update_rule(
        self,
        rule_id: str,
        *,
        name: str | None = None,
        requires_approval: bool | None = None,
        auto_promote: bool | None = None,
        required_approvers: int | None = None,
        conditions: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a promotion rule. Only the arguments you pass are sent.

        The environment pair cannot be changed — the platform accepts no
        ``source_environment`` or ``target_environment`` on an update. Create a
        new rule to govern a different pair.

        Args:
            rule_id: Rule ID
            requires_approval: Turning this off removes the human approval step
                for every future promotion matching the rule. Nothing warns
                about that at call time.

        Returns:
            The updated rule as an untyped dict.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, a missing
                ``architect`` persona, or a missing ``promotion_rules:update``
                permission.
            NotFoundError: ``404`` — no such rule in this organization.
            ValidationError: ``400`` — the update was rejected.

        Example:
            >>> await client.promotions.update_rule("rule-1", required_approvers=2)
        """
        body: dict[str, Any] = {}
        optional: dict[str, Any] = {
            "name": name,
            "requires_approval": requires_approval,
            "auto_promote": auto_promote,
            "required_approvers": required_approvers,
            "conditions": conditions,
            "status": status,
        }
        body.update({k: v for k, v in optional.items() if v is not None})

        response = await self._http.request(
            "PUT",
            f"/api/v1/promotions/rules/{encode_path_param(rule_id)}",
            json_data=body,
        )
        return response

    async def delete_rule(self, rule_id: str) -> dict[str, Any]:
        """
        Delete a promotion rule.

        Deleting the rule that required approval for an environment pair means
        future promotions for that pair are no longer gated by it. Check what
        else covers the pair before removing one.

        Args:
            rule_id: Rule ID

        Returns:
            ``{"message": "Promotion rule deleted"}``.

        Raises:
            AuthorizationError: ``403`` — an API-key credential, a missing
                ``architect`` persona, or a missing ``promotion_rules:delete``
                permission.
            NotFoundError: ``404`` — no such rule in this organization.

        Example:
            >>> await client.promotions.delete_rule("rule-1")
        """
        response = await self._http.request(
            "DELETE", f"/api/v1/promotions/rules/{encode_path_param(rule_id)}"
        )
        return response
