"""
Billing Module for Agentic OS SDK.

Provides billing operations that are distinct from the subscription lifecycle,
starting with PCI-safe payment-method setup via a Stripe Checkout Session.

Covers the billing surface: usage and usage detail, quotas, billing periods,
cost estimation and pricing, payment methods, billing contact, usage alerts, and
metered-billing attach/reconcile.

Two routes return raw dicts because the SERVER declares no model for them
(``/plans`` is annotated ``response_model=dict``; ``/summary`` declares none).
On a commercial surface an invented shape is worse than an untyped one, because
it reads as a guarantee the API never made.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import HTTPClient, encode_path_param


class ResourceUsage(BaseModel):
    """Usage of ONE resource type within a period."""

    quantity: str
    cost: float
    unit: str


class UsageSummary(BaseModel):
    """Aggregated usage and cost for a window.

    ``quantity`` is carried as a STRING here and throughout this module,
    matching the server. Usage quantities are Decimal-backed; serialising them
    as JSON numbers would round them, and rounding a billed quantity is a
    commercial defect rather than a display one. Parse with ``Decimal``, never
    ``float``, if you intend to do arithmetic.
    """

    organization_id: str
    start_date: str
    end_date: str
    by_resource: dict[str, ResourceUsage] = Field(default_factory=dict)
    total_cost: float
    record_count: int


class UsageRecord(BaseModel):
    """One metered usage record."""

    id: str
    organization_id: str
    resource_type: str
    quantity: str
    unit: str
    unit_cost: float
    total_cost: float
    metadata: str | None = None
    recorded_at: str
    created_at: str


class UsageRecordList(BaseModel):
    """A page of usage records."""

    records: list[UsageRecord] = Field(default_factory=list)
    total: int


class BillingQuota(BaseModel):
    """A quota row.

    ``limit_value`` of ``-1`` means UNLIMITED — it is a sentinel, not a
    negative allowance, so compare against it explicitly before treating the
    number as a bound.
    """

    id: str
    organization_id: str
    resource_type: str
    limit_value: float
    current_usage: float
    reset_period: str
    last_reset_at: str
    created_at: str
    updated_at: str


class BillingQuotaList(BaseModel):
    """``{"quotas": [...]}`` envelope."""

    quotas: list[BillingQuota] = Field(default_factory=list)


class BillingPeriod(BaseModel):
    """One billing period."""

    id: str
    organization_id: str
    start_date: str
    end_date: str
    status: str
    total_usage: float
    total_cost: float
    invoice_id: str | None = None
    created_at: str


class BillingPeriodList(BaseModel):
    """A page of billing periods."""

    records: list[BillingPeriod] = Field(default_factory=list)
    total: int


class CostEstimate(BaseModel):
    """An estimate. NOT a quote, and not a commitment to a price."""

    resource_type: str
    quantity: str
    unit: str
    unit_cost: float
    total_cost: float


class Pricing(BaseModel):
    """Current pricing, keyed by resource type."""

    pricing: dict[str, Any] = Field(default_factory=dict)


class DefaultPaymentMethodResult(BaseModel):
    """Outcome of setting the default payment method.

    ⚠ camelCase on the wire (``paymentMethodId``), unlike the rest of this
    module — hence the alias. ``success`` is True ONLY when the default was
    actually recorded at the payment provider; it previously reported success
    on paths where nothing had been recorded, so do not read it as "the request
    was accepted".
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    payment_method_id: str = Field(alias="paymentMethodId")


class BillingContact(BaseModel):
    """Billing contact details. Every field is optional server-side."""

    company_name: str | None = None
    billing_email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    tax_id: str | None = None


class BillingContactEnvelope(BaseModel):
    """``{"contact": {...}}`` envelope."""

    contact: BillingContact


class AlertResource(BaseModel):
    """Per-resource alert threshold."""

    id: str
    enabled: bool = True
    threshold: int = 0


class UsageAlerts(BaseModel):
    """Usage-alert settings."""

    global_enabled: bool = False
    email_recipients: list[str] = Field(default_factory=list)
    resources: list[AlertResource] = Field(default_factory=list)


class UsageAlertsEnvelope(BaseModel):
    """``{"alerts": {...}}`` envelope."""

    alerts: UsageAlerts


class MeteredItem(BaseModel):
    """A metered subscription item attached to the org's subscription."""

    organization_id: str
    dimension: str
    metered_items: dict[str, str] = Field(default_factory=dict)


class ReconcileResult(BaseModel):
    """Outcome of reconciling reported metered usage against internal usage.

    An UNDER-report self-heals: internal usage exceeding what was reported is
    re-reported with a deterministic identifier, so the leak closes. An
    OVER-report cannot be auto-corrected — a metered meter is append-only, so
    it needs an operator-issued credit — and the server answers 409 rather than
    silently adjusting.
    """

    organization_id: str
    reconciled: bool
    healed: dict[str, Any] = Field(default_factory=dict)
    dimensions: dict[str, Any] = Field(default_factory=dict)


class PaymentMethodSetup(BaseModel):
    """Result of a payment-method setup request.

    Mirrors the wire shape emitted by ``POST /api/v1/billing/setup-payment-method``
    (476-483 → SetupPaymentMethodResponse). The single
    ``url`` field is a Stripe Checkout Session URL the caller redirects the user
    to so that raw card data never transits our servers (PCI DSS).
    """

    url: str


class BillingModule:
    """
    Billing operations module.

    Provides billing methods outside the subscription lifecycle. Payment-method
    setup returns a Stripe Checkout Session URL for a PCI-safe redirect flow.

    Examples:
        # Start the add-a-card flow
        >>> setup = await client.revenue.billing.setup_payment_method()
        >>> # Redirect the user's browser to setup.url
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """
        Initialize billing module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def setup_payment_method(self) -> PaymentMethodSetup:
        """
        Create a Stripe Checkout Session for adding a payment method.

        Backend: ``POST /api/v1/billing/setup-payment-method``. The frontend redirects the user to
        the returned URL so raw card data never passes through our servers
        (PCI DSS compliance).

        Returns:
            PaymentMethodSetup: contains the Stripe Checkout Session ``url``.

        Raises:
            AuthenticationError: If not authenticated
            APIError: If Stripe integration is not configured (backend 503,
                ``code="STRIPE_NOT_CONFIGURED"``)

        Example:
            >>> setup = await client.revenue.billing.setup_payment_method()
            >>> # window.location = setup.url  (redirect to Stripe Checkout)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/billing/setup-payment-method",
        )

        return PaymentMethodSetup(url=response.get("url", ""))

    # -- usage ---------------------------------------------------------------

    async def get_usage(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> UsageSummary:
        """
        Get the usage summary for a window.

        Server: ``GET /api/v1/billing/usage``. Defaults to the current billing
        period when the dates are omitted.

        Args:
            start_date: ISO 8601 start; defaults to the period start
            end_date: ISO 8601 end; defaults to the period end

        Returns:
            UsageSummary: per-resource usage and total cost

        Example:
            >>> usage = await client.revenue.billing.get_usage()
            >>> print(usage.total_cost, usage.record_count)
        """
        params: dict[str, Any] = {}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        response = await self._http.request(
            "GET", "/api/v1/billing/usage", params=params or None
        )
        return UsageSummary(**response)

    async def get_usage_details(
        self,
        resource_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> UsageRecordList:
        """
        Get individual usage records.

        Server: ``GET /api/v1/billing/usage/details``.

        Args:
            resource_type: One of ``agent_execution``, ``token``, ``storage``,
                ``api_call``; the server rejects anything else
            limit: Maximum results (1-200)
            offset: Result offset

        Returns:
            UsageRecordList

        Example:
            >>> page = await client.revenue.billing.get_usage_details(limit=50)
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if resource_type is not None:
            params["resource_type"] = resource_type
        response = await self._http.request(
            "GET", "/api/v1/billing/usage/details", params=params
        )
        return UsageRecordList(**response)

    # -- quotas --------------------------------------------------------------

    async def get_quotas(self) -> BillingQuotaList:
        """
        Get the organization's quotas.

        Server: ``GET /api/v1/billing/quotas``. A ``limit_value`` of ``-1``
        means unlimited.

        Args:
            None

        Returns:
            BillingQuotaList

        Example:
            >>> quotas = await client.revenue.billing.get_quotas()
            >>> for q in quotas.quotas:
            ...     print(q.resource_type, q.current_usage, q.limit_value)
        """
        response = await self._http.request("GET", "/api/v1/billing/quotas")
        return BillingQuotaList(**response)

    async def update_quota(self, resource_type: str, limit_value: float) -> BillingQuota:
        """
        Override the quota limit for one resource type.

        Server: ``PUT /api/v1/billing/quotas/{resource_type}``.

        ⚠ PLATFORM-ADMIN ONLY, and that is a narrower authority than it sounds.
        Quota limits are DERIVED from the organization's paid plan tier; this
        route is an override, not a self-service control. It is gated on
        genuine platform admin — a capability NO org-scoped role implies, not
        org_owner, org_admin or tenant_admin. An org admin calling this is
        refused, by design: the gate previously accepted org-scoped roles,
        which let any organization raise its own quota to unlimited without
        paying.

        Args:
            resource_type: Resource type to override
            limit_value: New limit; ``-1`` for unlimited

        Returns:
            BillingQuota: the updated quota

        Example:
            >>> await client.revenue.billing.update_quota("agents", 20)
        """
        response = await self._http.request(
            "PUT",
            f"/api/v1/billing/quotas/{encode_path_param(resource_type)}",
            json_data={"limit_value": limit_value},
        )
        return BillingQuota(**response)

    # -- periods -------------------------------------------------------------

    async def list_periods(self, limit: int = 12, offset: int = 0) -> BillingPeriodList:
        """
        List billing periods, most recent first.

        Server: ``GET /api/v1/billing/periods``.

        Args:
            limit: Maximum results (1-100)
            offset: Result offset

        Returns:
            BillingPeriodList

        Example:
            >>> periods = await client.revenue.billing.list_periods()
        """
        response = await self._http.request(
            "GET", "/api/v1/billing/periods", params={"limit": limit, "offset": offset}
        )
        return BillingPeriodList(**response)

    async def get_current_period(self) -> BillingPeriod:
        """
        Get the open billing period.

        Server: ``GET /api/v1/billing/periods/current``.

        Args:
            None

        Returns:
            BillingPeriod

        Example:
            >>> period = await client.revenue.billing.get_current_period()
            >>> print(period.total_cost)
        """
        response = await self._http.request("GET", "/api/v1/billing/periods/current")
        return BillingPeriod(**response)

    async def get_period(self, period_id: str) -> BillingPeriod:
        """
        Get one billing period.

        Server: ``GET /api/v1/billing/periods/{period_id}``.

        Args:
            period_id: Period ID

        Returns:
            BillingPeriod

        Example:
            >>> period = await client.revenue.billing.get_period("per-1")
        """
        response = await self._http.request(
            "GET", f"/api/v1/billing/periods/{encode_path_param(period_id)}"
        )
        return BillingPeriod(**response)

    async def close_period(self, period_id: str) -> BillingPeriod:
        """
        Close a billing period.

        Server: ``POST /api/v1/billing/periods/{period_id}/close``. Admin-class
        roles only.

        ⚠ Closing a period finalises what it will be billed for. Usage
        backdated into a closed window is exactly the case the metered
        reconciliation exists to catch, so treat this as a one-way step.

        Args:
            period_id: Period to close

        Returns:
            BillingPeriod: the closed period

        Example:
            >>> await client.revenue.billing.close_period("per-1")
        """
        response = await self._http.request(
            "POST", f"/api/v1/billing/periods/{encode_path_param(period_id)}/close"
        )
        return BillingPeriod(**response)

    # -- pricing -------------------------------------------------------------

    async def estimate_cost(self, resource_type: str, quantity: float) -> CostEstimate:
        """
        Estimate the cost of a given resource usage.

        Server: ``POST /api/v1/billing/estimate``. An estimate at CURRENT
        pricing — it is not a quote and does not hold a price.

        Args:
            resource_type: Resource type to price
            quantity: How much of it

        Returns:
            CostEstimate

        Example:
            >>> est = await client.revenue.billing.estimate_cost("token", 1_000_000)
            >>> print(est.total_cost)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/billing/estimate",
            json_data={"resource_type": resource_type, "quantity": quantity},
        )
        return CostEstimate(**response)

    async def get_pricing(self) -> Pricing:
        """
        Get current pricing by resource type.

        Server: ``GET /api/v1/billing/pricing``.

        Args:
            None

        Returns:
            Pricing

        Example:
            >>> pricing = await client.revenue.billing.get_pricing()
        """
        response = await self._http.request("GET", "/api/v1/billing/pricing")
        return Pricing(**response)

    async def get_plans(self) -> dict[str, Any]:
        """
        Get the available plans.

        ⚠ Returns a raw dict: the server route is annotated
        ``response_model=dict``, so there is no declared schema to wrap. A model
        here would be this client's invention rather than the API's contract —
        and on a commercial surface an invented shape is worse than an untyped
        one, because it reads as a guarantee.

        Args:
            None

        Returns:
            The plans exactly as the server emits them

        Example:
            >>> plans = await client.revenue.billing.get_plans()
        """
        response = await self._http.request("GET", "/api/v1/billing/plans")
        return dict(response)

    async def get_summary(self) -> dict[str, Any]:
        """
        Get a combined billing summary for the organization.

        ⚠ Returns a raw dict: this route declares NO response model at all, so
        there is no contract to type against. Same reasoning as
        :meth:`get_plans`.

        Args:
            None

        Returns:
            The summary exactly as the server emits it

        Example:
            >>> summary = await client.revenue.billing.get_summary()
        """
        response = await self._http.request("GET", "/api/v1/billing/summary")
        return dict(response)

    # -- payment methods -----------------------------------------------------

    async def remove_payment_method(self, payment_method_id: str) -> None:
        """
        Remove a payment method.

        Server: ``DELETE /api/v1/billing/payment-methods/{payment_method_id}``.
        Detaches it at the payment provider when one is configured. Answers
        ``204 No Content``, so there is nothing to return — that is the
        server's declared shape, not a missing model.

        Args:
            payment_method_id: Payment method to remove

        Returns:
            None

        Example:
            >>> await client.revenue.billing.remove_payment_method("pm_1")
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/billing/payment-methods/{encode_path_param(payment_method_id)}",
        )

    async def set_default_payment_method(
        self, payment_method_id: str
    ) -> DefaultPaymentMethodResult:
        """
        Make a payment method the organization's default.

        Server: ``POST /api/v1/billing/payment-methods/{id}/default``.

        ⚠ Read ``success`` rather than assuming a 200 means it took. It is True
        ONLY when the default was actually recorded at the payment provider;
        the route previously answered success on paths where nothing had been
        recorded.

        Args:
            payment_method_id: Payment method to make default

        Returns:
            DefaultPaymentMethodResult

        Example:
            >>> result = await client.revenue.billing.set_default_payment_method("pm_1")
            >>> assert result.success
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/billing/payment-methods/"
            f"{encode_path_param(payment_method_id)}/default",
        )
        return DefaultPaymentMethodResult(**response)

    # -- contact + alerts ----------------------------------------------------

    async def get_billing_contact(self) -> BillingContactEnvelope:
        """
        Get the organization's billing contact.

        Server: ``GET /api/v1/billing/contact``.

        Args:
            None

        Returns:
            BillingContactEnvelope

        Example:
            >>> contact = await client.revenue.billing.get_billing_contact()
            >>> print(contact.contact.billing_email)
        """
        response = await self._http.request("GET", "/api/v1/billing/contact")
        return BillingContactEnvelope(**response)

    async def update_billing_contact(self, **fields: Any) -> BillingContactEnvelope:
        """
        Update the organization's billing contact. Admin-class roles only.

        Server: ``PUT /api/v1/billing/contact``.

        ⚠ The server takes the payload as the WHOLE contact, so a field you
        omit is not preserved — read the current contact first and send it
        back with your change applied if you mean to edit rather than replace.

        Args:
            **fields: Any of ``company_name``, ``billing_email``,
                ``address_line1``, ``address_line2``, ``city``, ``state``,
                ``postal_code``, ``country``, ``tax_id``

        Returns:
            BillingContactEnvelope: the stored contact

        Example:
            >>> await client.revenue.billing.update_billing_contact(
            ...     billing_email="ap@example.com"
            ... )
        """
        response = await self._http.request(
            "PUT", "/api/v1/billing/contact", json_data=fields
        )
        return BillingContactEnvelope(**response)

    async def get_usage_alerts(self) -> UsageAlertsEnvelope:
        """
        Get usage-alert settings.

        Server: ``GET /api/v1/billing/alerts``.

        Args:
            None

        Returns:
            UsageAlertsEnvelope

        Example:
            >>> alerts = await client.revenue.billing.get_usage_alerts()
            >>> print(alerts.alerts.global_enabled)
        """
        response = await self._http.request("GET", "/api/v1/billing/alerts")
        return UsageAlertsEnvelope(**response)

    async def update_usage_alerts(
        self,
        global_enabled: bool | None = None,
        email_recipients: list[str] | None = None,
        resources: list[dict[str, Any]] | None = None,
    ) -> UsageAlertsEnvelope:
        """
        Update usage-alert settings. Admin-class roles only.

        Server: ``PUT /api/v1/billing/alerts``.

        ⚠ Like the contact route, the payload is the whole settings object —
        an omitted field falls back to the server's default rather than being
        preserved. Read the current settings first if you mean to edit one.

        Args:
            global_enabled: Master on/off for usage alerts
            email_recipients: Who receives them
            resources: Per-resource thresholds, each ``{"id", "enabled",
                "threshold"}``

        Returns:
            UsageAlertsEnvelope: the stored settings

        Example:
            >>> await client.revenue.billing.update_usage_alerts(
            ...     global_enabled=True, email_recipients=["ops@example.com"]
            ... )
        """
        body: dict[str, Any] = {}
        if global_enabled is not None:
            body["global_enabled"] = global_enabled
        if email_recipients is not None:
            body["email_recipients"] = email_recipients
        if resources is not None:
            body["resources"] = resources
        response = await self._http.request(
            "PUT", "/api/v1/billing/alerts", json_data=body
        )
        return UsageAlertsEnvelope(**response)

    # -- metered billing -----------------------------------------------------

    async def attach_metered_item(
        self, dimension: str, subscription_item_id: str | None = None
    ) -> MeteredItem:
        """
        Attach a metered subscription item, switching on usage-based billing.

        Server: ``POST /api/v1/billing/metered-items``. Additive — the flat
        plan tier is untouched. This is the ACTIVATION surface for metered
        billing, so calling it starts charging the organization for usage.

        Args:
            dimension: Metered dimension to attach
            subscription_item_id: Existing provider item to bind, if any

        Returns:
            MeteredItem

        Example:
            >>> await client.revenue.billing.attach_metered_item("tokens")
        """
        body: dict[str, Any] = {"dimension": dimension}
        if subscription_item_id is not None:
            body["subscription_item_id"] = subscription_item_id
        response = await self._http.request(
            "POST", "/api/v1/billing/metered-items", json_data=body
        )
        return MeteredItem(**response)

    async def reconcile_metered_usage(
        self, period_start: str, period_end: str
    ) -> ReconcileResult:
        """
        Reconcile reported metered usage against internal usage for a period.

        Server: ``POST /api/v1/billing/metered-reconcile``.

        An UNDER-report self-heals: usage the provider was never told about is
        re-reported with a deterministic identifier, so the revenue leak
        closes. An OVER-report does NOT: a metered meter is append-only, so it
        needs an operator-issued credit, and the server answers ``409`` with
        the per-dimension detail rather than silently adjusting. Handle that
        409 — it is the case where money has already been over-charged.

        Args:
            period_start: ISO 8601 window start
            period_end: ISO 8601 window end

        Returns:
            ReconcileResult

        Example:
            >>> result = await client.revenue.billing.reconcile_metered_usage(
            ...     "2026-08-01", "2026-09-01"
            ... )
            >>> print(result.healed)
        """
        response = await self._http.request(
            "POST",
            "/api/v1/billing/metered-reconcile",
            json_data={"period_start": period_start, "period_end": period_end},
        )
        return ReconcileResult(**response)
