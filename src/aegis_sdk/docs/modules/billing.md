# Billing Module

The revenue module (`client.revenue`) provides management for subscriptions, plans, licenses, usage tracking, quotas, and invoices.

| Sub-Module | Access | Description |
|------------|--------|-------------|
| Subscriptions | `client.revenue.subscriptions` | Subscribe, upgrade, cancel, reactivate |
| Plans | `client.revenue.plans` | List plans, get features, compare tiers |
| Licenses | `client.revenue.licenses` | Generate, validate, revoke licenses |
| Usage | `client.revenue.usage` | Current usage, history, breakdown |
| Quotas | `client.revenue.quotas` | Get quotas, update limits, check capacity |
| Invoices | `client.revenue.invoices` | List, download, get invoice details |

---

## Subscriptions (`client.revenue.subscriptions`)

### Get Current Subscription

```python
from aegis_sdk import Subscription

subscription: Subscription = await client.revenue.subscriptions.get()
print(f"Plan: {subscription.plan_tier}")
print(f"Status: {subscription.status}")
print(f"Billing: {subscription.billing_cycle}")
print(f"Period: {subscription.current_period_start} to {subscription.current_period_end}")
print(f"Cancel at period end: {subscription.cancel_at_period_end}")
```

### Subscription Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Subscription ID |
| `organization_id` | `str` | Organization ID |
| `plan_tier` | `PlanTier` | `"free"`, `"starter"`, `"professional"`, `"enterprise"` |
| `billing_cycle` | `BillingCycle` | `"monthly"`, `"annual"` |
| `status` | `SubscriptionStatus` | `"active"`, `"past_due"`, `"canceled"`, `"incomplete"`, `"trialing"`, `"unpaid"` |
| `current_period_start` | `str` | Current billing period start |
| `current_period_end` | `str` | Current billing period end |
| `cancel_at_period_end` | `bool` | Whether cancellation is scheduled |
| `trial_start` | `Optional[str]` | Trial start date |
| `trial_end` | `Optional[str]` | Trial end date |
| `stripe_customer_id` | `str` | Stripe customer ID |
| `stripe_subscription_id` | `str` | Stripe subscription ID |

### Subscribe to a Plan

```python
from aegis_sdk import Subscription, PaymentError

try:
    subscription: Subscription = await client.revenue.subscriptions.subscribe(
        plan_id="professional",
        billing_cycle="monthly",
        payment_method_id="pm_card_visa",  # Stripe payment method ID
    )
    print(f"Subscribed to {subscription.plan_tier}")
    print(f"Status: {subscription.status}")
except PaymentError as e:
    print(f"Payment failed: {e.message}")
    if e.decline_code:
        print(f"Decline code: {e.decline_code}")
```

### Upgrade or Downgrade

```python
from aegis_sdk import Subscription

subscription: Subscription = await client.revenue.subscriptions.upgrade(
    new_plan_id="enterprise",
    prorate=True,   # Prorate charges (default)
)
print(f"Upgraded to: {subscription.plan_tier}")
```

### Cancel Subscription

```python
from aegis_sdk import Subscription

# Cancel at end of billing period (keeps access until then)
subscription: Subscription = await client.revenue.subscriptions.cancel(
    at_period_end=True,
)
print(f"Cancels at: {subscription.current_period_end}")

# Cancel immediately (no refund)
subscription = await client.revenue.subscriptions.cancel(at_period_end=False)
print(f"Status: {subscription.status}")
```

### Reactivate Subscription

Undo a pending cancellation:

```python
from aegis_sdk import Subscription

subscription: Subscription = await client.revenue.subscriptions.reactivate()
print(f"Reactivated: {subscription.status}")
print(f"Cancel at period end: {subscription.cancel_at_period_end}")
```

### Stripe Customer Portal

Redirect users to manage billing through Stripe:

```python
from aegis_sdk import PortalSession

portal: PortalSession = await client.revenue.subscriptions.create_portal_session()
print(f"Billing portal URL: {portal.url}")
# Redirect user to portal.url
```

---

## Plans (`client.revenue.plans`)

### List Available Plans

```python
from aegis_sdk import Plan
from typing import List

plans: List[Plan] = await client.revenue.plans.list()
for plan in plans:
    if not plan.contact_sales:
        print(f"{plan.name}: ${plan.monthly_price / 100}/month (${plan.annual_price / 100}/year)")
    else:
        print(f"{plan.name}: Contact sales")
    print(f"  Features: {', '.join(plan.features[:3])}...")
```

### Plan Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Plan ID |
| `name` | `str` | Plan display name |
| `tier` | `PlanTier` | `"free"`, `"starter"`, `"professional"`, `"enterprise"` |
| `description` | `str` | Plan description |
| `monthly_price` | `int` | Monthly price in cents |
| `annual_price` | `int` | Annual price in cents |
| `features` | `List[str]` | Feature list |
| `contact_sales` | `bool` | Whether sales contact is required |

### Get Features for a Tier

```python
from aegis_sdk import PlanFeatures

features: PlanFeatures = await client.revenue.plans.get_features("professional")
for feature in features.features:
    print(f"  - {feature}")
```

### Compare Tiers

```python
from aegis_sdk import TierComparison

comparison: TierComparison = await client.revenue.plans.compare_tiers(
    "starter",
    "professional",
)
print(f"Comparing {comparison.tier1} vs {comparison.tier2}")
print(f"Price difference: ${comparison.price_difference_monthly / 100}/month")
print(f"Additional features in {comparison.tier2}:")
for feature in comparison.additional_in_tier2:
    print(f"  + {feature}")
```

---

## Licenses (`client.revenue.licenses`)

For self-hosted deployments.

### Generate a License (Admin)

```python
from aegis_sdk import License

license: License = await client.revenue.licenses.generate(
    customer_id="cust_123",
    customer_name="Acme Corp",
    customer_email="admin@acme.com",
    edition="enterprise",             # "starter", "professional", "enterprise"
    max_agents=-1,                     # -1 = unlimited
    max_users=50,
    max_runs_per_month=10000,
    validity_days=365,
    machine_binding=False,
    domain_restriction=["acme.com"],
    phone_home_required=True,
    phone_home_interval_days=7,
    grace_period_days=30,
)

print(f"License ID: {license.license_id}")
print(f"Edition: {license.edition}")
print(f"Expires: {license.expires_at}")
```

### Validate License (Phone-Home)

```python
from datetime import datetime, UTC
from aegis_sdk import LicenseValidation

validation: LicenseValidation = await client.revenue.licenses.validate(
    license_id="lic_123",
    machine_id="machine-001",
    timestamp=datetime.now(UTC).isoformat(),
    app_version="1.0.0",
    usage={"agents_created": 5, "runs_this_month": 100},
)

if validation.valid:
    print(f"Valid until: {validation.expires_at}")
    print(f"Next check in: {validation.next_check_days} days")
    print(f"Entitlements: {validation.entitlements}")
else:
    print(f"Invalid: {validation.message}")
```

### Get License Status

```python
from aegis_sdk import LicenseStatus

status: LicenseStatus = await client.revenue.licenses.get_status()
if status.valid:
    print(f"License: {status.license_id}")
    print(f"Edition: {status.edition}")
    print(f"Days remaining: {status.days_remaining}")
elif status.grace_period_active:
    print(f"Grace period: {status.grace_period_days_remaining} days left")
else:
    print(f"License invalid: {status.error}")
```

### Revoke a License

```python
revoked: bool = await client.revenue.licenses.revoke(
    "lic_123",
    reason="Customer churned",
)
print(f"Revoked: {revoked}")
```

### Get License Usage

```python
from aegis_sdk import LicenseUsage

usage: LicenseUsage = await client.revenue.licenses.get_usage("lic_123")
print(f"Total validations: {usage.total_validations}")
for v in usage.validations[-5:]:
    print(f"  {v.get('timestamp')}: {v.get('machine_id')}")
```

### List Editions

```python
from aegis_sdk import Edition
from typing import Dict

editions: Dict[str, Edition] = await client.revenue.licenses.list_editions()
for name, edition in editions.items():
    print(f"{name}:")
    print(f"  Features: {edition.features}")
    print(f"  Limits: {edition.limits}")
```

---

## Usage (`client.revenue.usage`)

### Get Current Usage

```python
from aegis_sdk import Usage

usage: Usage = await client.revenue.usage.get_current()
print(f"Agent executions: {usage.agent_execution.current}/{usage.agent_execution.limit}")
print(f"Tokens: {usage.token.current}/{usage.token.limit}")
print(f"Storage: {usage.storage.current}/{usage.storage.limit} {usage.storage.unit}")
print(f"API calls: {usage.api_call.current}/{usage.api_call.limit}")

# Check if approaching limits
if not usage.agent_execution.unlimited:
    remaining = usage.agent_execution.limit - usage.agent_execution.current
    if remaining < 10:
        print(f"Warning: only {remaining} agent executions remaining!")
```

### Get Usage History

```python
from aegis_sdk import UsageHistory
from typing import List

history: List[UsageHistory] = await client.revenue.usage.get_history(
    start_date="2024-01-01",
    end_date="2024-01-31",
    resource_type="agent_execution",   # Optional filter
)

for record in history:
    print(f"  {record.date}: {record.usage}/{record.limit}")
```

### Get Usage Breakdown

```python
from aegis_sdk import UsageBreakdown

breakdown: UsageBreakdown = await client.revenue.usage.get_breakdown(
    resource_type="agent_execution",
    dimension="agent",   # "agent", "user", "date"
)

if breakdown.by_agent:
    for agent_id, count in breakdown.by_agent.items():
        print(f"  Agent {agent_id}: {count} executions")
```

---

## Quotas (`client.revenue.quotas`)

### Get All Quotas

```python
from aegis_sdk import Quota
from typing import List

quotas: List[Quota] = await client.revenue.quotas.get()
for quota in quotas:
    if quota.unlimited:
        print(f"  {quota.resource_type}: Unlimited")
    else:
        pct = (quota.current / quota.limit) * 100 if quota.limit > 0 else 0
        print(f"  {quota.resource_type}: {quota.current}/{quota.limit} ({pct:.1f}%)")
```

### Check Quota Before Action

```python
from aegis_sdk import QuotaCheck

check: QuotaCheck = await client.revenue.quotas.check_limit(
    resource_type="agents",
    amount=1,
)

if check.allowed:
    agent = await client.agents.create(name="New Agent", agent_type="chat")
    print(f"Agent created, {check.remaining - 1} remaining")
else:
    print(f"Cannot create agent: at limit ({check.current}/{check.limit})")
```

### Update Quota (Admin)

```python
from aegis_sdk import Quota

quota: Quota = await client.revenue.quotas.update(
    resource_type="agents",
    new_limit=20,          # -1 for unlimited
)
print(f"New limit: {quota.limit}")
```

---

## Invoices (`client.revenue.invoices`)

### List Invoices

```python
from aegis_sdk import InvoicesResponse

response: InvoicesResponse = await client.revenue.invoices.list(limit=10)
for invoice in response.invoices:
    status_mark = "[paid]" if invoice.status == "paid" else f"[{invoice.status}]"
    print(f"  {status_mark} {invoice.number}: ${invoice.amount_paid / 100}")
if response.has_more:
    print("More invoices available...")
```

### Get Invoice Details

```python
from aegis_sdk import Invoice
from typing import Optional

invoice: Optional[Invoice] = await client.revenue.invoices.get_details("inv_123")
if invoice:
    print(f"Invoice #{invoice.number}")
    print(f"Status: {invoice.status}")
    print(f"Total: ${invoice.amount_due / 100}")
    print("Line items:")
    for line in invoice.lines:
        print(f"  - {line.description}: ${line.amount / 100}")
```

### Download Invoice PDF

```python
from typing import Optional

url: Optional[str] = await client.revenue.invoices.download("inv_123")
if url:
    print(f"Download PDF: {url}")
else:
    print("No PDF available")
```

### Invoice Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Invoice ID |
| `number` | `Optional[str]` | Invoice number |
| `status` | `InvoiceStatus` | `"draft"`, `"open"`, `"paid"`, `"void"`, `"uncollectible"` |
| `amount_due` | `int` | Amount due in cents |
| `amount_paid` | `int` | Amount paid in cents |
| `currency` | `str` | Currency code (e.g., `"usd"`) |
| `created` | `int` | Unix timestamp |
| `due_date` | `Optional[int]` | Due date (Unix timestamp) |
| `invoice_pdf` | `Optional[str]` | PDF download URL |
| `hosted_invoice_url` | `Optional[str]` | Stripe hosted invoice URL |
| `lines` | `List[InvoiceLineItem]` | Line items |

---

## Related

- [Configuration](../configuration.md) -- Client setup
- [Error Handling](../error-handling.md) -- `PaymentError` handling
- [Quick Start](../quickstart.md) -- Getting started
