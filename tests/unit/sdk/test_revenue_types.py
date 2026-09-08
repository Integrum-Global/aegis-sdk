"""
Unit tests for SDK revenue type definitions.

Tests Pydantic models for subscriptions, plans, licenses, usage, quotas, and invoices.
"""

import pytest

from aegis_sdk.types import (
    BillingCycle,
    CancelRequest,
    Invoice,
    # Invoice models
    InvoiceLineItem,
    InvoicesResponse,
    InvoiceStatus,
    # License models
    License,
    LicenseEdition,
    LicenseGenerate,
    LicenseStatus,
    LicenseValidation,
    Plan,
    PlanFeatures,
    PlanTier,
    PortalSession,
    Quota,
    QuotaCheck,
    ResourceType,
    # Usage models
    ResourceUsage,
    SubscribeRequest,
    # Subscription models
    Subscription,
    # Enums
    SubscriptionStatus,
    TierComparison,
    UpgradeRequest,
    Usage,
)


@pytest.mark.unit
class TestRevenueEnums:
    """Test revenue enum definitions."""

    def test_subscription_status_values(self):
        """SubscriptionStatus should have all expected values."""
        assert SubscriptionStatus.ACTIVE == "active"
        assert SubscriptionStatus.PAST_DUE == "past_due"
        assert SubscriptionStatus.CANCELED == "canceled"
        assert SubscriptionStatus.INCOMPLETE == "incomplete"
        assert SubscriptionStatus.TRIALING == "trialing"
        assert SubscriptionStatus.UNPAID == "unpaid"

    def test_billing_cycle_values(self):
        """BillingCycle should have monthly and annual."""
        assert BillingCycle.MONTHLY == "monthly"
        assert BillingCycle.ANNUAL == "annual"

    def test_plan_tier_values(self):
        """PlanTier should have all tier values."""
        assert PlanTier.FREE == "free"
        assert PlanTier.STARTER == "starter"
        assert PlanTier.PROFESSIONAL == "professional"
        assert PlanTier.ENTERPRISE == "enterprise"

    def test_license_edition_values(self):
        """LicenseEdition should have all edition values."""
        assert LicenseEdition.STARTER == "starter"
        assert LicenseEdition.PROFESSIONAL == "professional"
        assert LicenseEdition.ENTERPRISE == "enterprise"

    def test_resource_type_values(self):
        """ResourceType should have all resource types."""
        assert ResourceType.AGENT_EXECUTION == "agent_execution"
        assert ResourceType.TOKEN == "token"
        assert ResourceType.STORAGE == "storage"
        assert ResourceType.API_CALL == "api_call"
        assert ResourceType.AGENTS == "agents"
        assert ResourceType.TEAM_MEMBERS == "team_members"

    def test_invoice_status_values(self):
        """InvoiceStatus should have all Stripe invoice statuses."""
        assert InvoiceStatus.DRAFT == "draft"
        assert InvoiceStatus.OPEN == "open"
        assert InvoiceStatus.PAID == "paid"
        assert InvoiceStatus.VOID == "void"
        assert InvoiceStatus.UNCOLLECTIBLE == "uncollectible"


@pytest.mark.unit
class TestSubscriptionModels:
    """Test subscription-related models."""

    def test_subscription_model(self):
        """Subscription model should parse correctly."""
        sub = Subscription(
            id="sub_123",
            organization_id="org_456",
            plan_tier=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            status=SubscriptionStatus.ACTIVE,
            current_period_start="2024-01-01T00:00:00Z",
            current_period_end="2024-02-01T00:00:00Z",
            cancel_at_period_end=False,
            stripe_customer_id="cus_abc",
            stripe_subscription_id="sub_xyz",
        )
        assert sub.id == "sub_123"
        assert sub.plan_tier == PlanTier.PROFESSIONAL
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.cancel_at_period_end is False

    def test_subscribe_request_model(self):
        """SubscribeRequest should validate correctly."""
        req = SubscribeRequest(
            plan_id="starter",
            billing_cycle=BillingCycle.MONTHLY,
            payment_method_id="pm_card_visa",
        )
        assert req.plan_id == "starter"
        assert req.billing_cycle == BillingCycle.MONTHLY
        assert req.payment_method_id == "pm_card_visa"

    def test_subscribe_request_optional_payment_method(self):
        """SubscribeRequest should allow optional payment_method_id."""
        req = SubscribeRequest(
            plan_id="professional",
            billing_cycle=BillingCycle.ANNUAL,
        )
        assert req.payment_method_id is None

    def test_upgrade_request_model(self):
        """UpgradeRequest should have default prorate=True."""
        req = UpgradeRequest(new_plan_id="enterprise")
        assert req.new_plan_id == "enterprise"
        assert req.prorate is True

    def test_cancel_request_model(self):
        """CancelRequest should have default at_period_end=True."""
        req = CancelRequest()
        assert req.at_period_end is True

    def test_cancel_request_immediate(self):
        """CancelRequest can cancel immediately."""
        req = CancelRequest(at_period_end=False)
        assert req.at_period_end is False


@pytest.mark.unit
class TestPlanModels:
    """Test plan-related models."""

    def test_plan_model(self):
        """Plan model should parse correctly."""
        plan = Plan(
            id="starter",
            name="Starter",
            tier=PlanTier.STARTER,
            description="Perfect for small teams",
            monthly_price=19900,
            annual_price=199900,
            features=["Feature 1", "Feature 2"],
            contact_sales=False,
        )
        assert plan.id == "starter"
        assert plan.monthly_price == 19900
        assert len(plan.features) == 2
        assert plan.contact_sales is False

    def test_plan_features_model(self):
        """PlanFeatures should hold feature list."""
        features = PlanFeatures(features=["AI agents", "Analytics", "Support"])
        assert len(features.features) == 3

    def test_tier_comparison_model(self):
        """TierComparison should show differences."""
        comp = TierComparison(
            tier1=PlanTier.STARTER,
            tier2=PlanTier.PROFESSIONAL,
            tier1_features=["Feature A"],
            tier2_features=["Feature A", "Feature B", "Feature C"],
            additional_in_tier2=["Feature B", "Feature C"],
            tier1_price_monthly=19900,
            tier2_price_monthly=59900,
            price_difference_monthly=40000,
        )
        assert comp.tier1 == PlanTier.STARTER
        assert comp.tier2 == PlanTier.PROFESSIONAL
        assert len(comp.additional_in_tier2) == 2
        assert comp.price_difference_monthly == 40000

    def test_portal_session_model(self):
        """PortalSession should hold URL."""
        session = PortalSession(url="https://billing.stripe.com/session/abc123")
        assert "stripe.com" in session.url


@pytest.mark.unit
class TestLicenseModels:
    """Test license-related models."""

    def test_license_model(self):
        """License model should parse correctly."""
        lic = License(
            license_id="lic_123",
            customer_id="cust_456",
            customer_name="Acme Corp",
            customer_email="admin@acme.com",
            edition=LicenseEdition.ENTERPRISE,
            max_agents=-1,
            max_users=-1,
            max_runs_per_month=-1,
            features=["All features"],
            expires_at="2025-01-01T00:00:00Z",
            phone_home_required=True,
            phone_home_interval_days=7,
            grace_period_days=30,
        )
        assert lic.license_id == "lic_123"
        assert lic.edition == LicenseEdition.ENTERPRISE
        assert lic.max_agents == -1  # unlimited

    def test_license_generate_request(self):
        """LicenseGenerate should have sensible defaults."""
        gen = LicenseGenerate(
            customer_id="cust_123",
            customer_name="Test Corp",
            customer_email="test@example.com",
            edition=LicenseEdition.PROFESSIONAL,
        )
        assert gen.max_agents == -1
        assert gen.validity_days == 365
        assert gen.phone_home_required is True

    def test_license_validation_model(self):
        """LicenseValidation should parse correctly."""
        val = LicenseValidation(
            valid=True,
            message="License is valid",
            expires_at="2025-01-01T00:00:00Z",
            entitlements={"agents": -1, "users": -1},
            next_check_days=7,
        )
        assert val.valid is True
        assert val.next_check_days == 7

    def test_license_validation_invalid(self):
        """LicenseValidation can indicate invalid license."""
        val = LicenseValidation(
            valid=False,
            message="License has been revoked",
            next_check_days=1,
        )
        assert val.valid is False
        assert "revoked" in val.message

    def test_license_status_model(self):
        """LicenseStatus should include grace period info."""
        status = LicenseStatus(
            valid=False,
            license_id="lic_123",
            customer_name="Acme Corp",
            edition=LicenseEdition.ENTERPRISE,
            grace_period_active=True,
            grace_period_days_remaining=20,
        )
        assert status.grace_period_active is True
        assert status.grace_period_days_remaining == 20


@pytest.mark.unit
class TestUsageModels:
    """Test usage-related models."""

    def test_resource_usage_model(self):
        """ResourceUsage should track limit and current."""
        usage = ResourceUsage(
            limit=10000,
            current=5000,
            unit="count",
            remaining=5000,
            unlimited=False,
        )
        assert usage.limit == 10000
        assert usage.current == 5000
        assert usage.remaining == 5000

    def test_resource_usage_unlimited(self):
        """ResourceUsage can be unlimited."""
        usage = ResourceUsage(
            limit=-1,
            current=0,
            unit="count",
            unlimited=True,
        )
        assert usage.unlimited is True

    def test_usage_model(self):
        """Usage should have all resource types."""
        usage = Usage(
            agent_execution=ResourceUsage(limit=10000, current=5000, unit="count"),
            token=ResourceUsage(limit=1000000, current=250000, unit="1000 tokens"),
            storage=ResourceUsage(limit=100, current=25, unit="GB"),
            api_call=ResourceUsage(limit=100000, current=10000, unit="count"),
        )
        assert usage.agent_execution.current == 5000
        assert usage.storage.unit == "GB"


@pytest.mark.unit
class TestQuotaModels:
    """Test quota-related models."""

    def test_quota_model(self):
        """Quota should track resource limits."""
        quota = Quota(
            resource_type=ResourceType.AGENTS,
            limit=10,
            current=5,
            remaining=5,
            unlimited=False,
        )
        assert quota.resource_type == ResourceType.AGENTS
        assert quota.remaining == 5

    def test_quota_check_allowed(self):
        """QuotaCheck should indicate if action allowed."""
        check = QuotaCheck(
            resource_type=ResourceType.AGENTS,
            allowed=True,
            current=5,
            limit=10,
            remaining=5,
            amount_requested=1,
        )
        assert check.allowed is True
        assert check.amount_requested == 1

    def test_quota_check_denied(self):
        """QuotaCheck should indicate when at limit."""
        check = QuotaCheck(
            resource_type=ResourceType.AGENTS,
            allowed=False,
            current=10,
            limit=10,
            remaining=0,
            amount_requested=1,
        )
        assert check.allowed is False
        assert check.remaining == 0


@pytest.mark.unit
class TestInvoiceModels:
    """Test invoice-related models."""

    def test_invoice_line_item(self):
        """InvoiceLineItem should parse correctly."""
        item = InvoiceLineItem(
            description="Professional plan - Monthly",
            amount=59900,
            quantity=1,
            currency="usd",
        )
        assert item.amount == 59900
        assert item.currency == "usd"

    def test_invoice_model(self):
        """Invoice model should parse correctly."""
        invoice = Invoice(
            id="inv_123",
            number="INV-2024-001",
            status=InvoiceStatus.PAID,
            amount_due=59900,
            amount_paid=59900,
            currency="usd",
            created=1704067200,
            invoice_pdf="https://stripe.com/invoice.pdf",
            hosted_invoice_url="https://invoice.stripe.com/abc",
            lines=[
                InvoiceLineItem(
                    description="Professional plan",
                    amount=59900,
                    currency="usd",
                )
            ],
        )
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.amount_paid == 59900
        assert len(invoice.lines) == 1

    def test_invoices_response(self):
        """InvoicesResponse should paginate correctly."""
        response = InvoicesResponse(
            invoices=[
                Invoice(
                    id="inv_1",
                    status=InvoiceStatus.PAID,
                    amount_due=100,
                    amount_paid=100,
                    currency="usd",
                    created=1704067200,
                    lines=[],
                ),
            ],
            has_more=True,
        )
        assert len(response.invoices) == 1
        assert response.has_more is True
