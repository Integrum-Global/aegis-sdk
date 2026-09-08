# Billing integrity — the errors here are commercial, not cosmetic

**Scope:** quotas, usage, plans, subscriptions, invoices — everything under
`client.revenue`.

The distinguishing property of this surface: **a wrong reading costs money and
does not surface until reconciliation.** A rendering bug is found by whoever
looks at the screen. A rounded billed quantity is found by a customer's finance
team, months later, and the conversation starts from a position of doubt.

## MUST 1 — Never widen a billed number's type on the way through

If a quantity arrives as a string, keep it a string until something that
understands decimals takes it. Parsing it into a binary float and re-serialising
it **rounds a billed amount**.

```python
# DO — pass the wire value through, or parse to Decimal if you must compute
from decimal import Decimal
qty = Decimal(record["quantity"])

# DO NOT — the round-trip through float is silent and lossy
qty = float(record["quantity"])          # 0.1 + 0.2 territory, on an invoice line
payload = {"quantity": qty}
```

**Why:** JSON has one number type and it is binary floating point. A server
holding a decimal quantity and a client holding a float disagree by amounts too
small to notice per record and large enough to matter per million. The defect is
invisible in every test that round-trips through the same client.

⚠ **Check your own build before assuming the shape.** In the build this was
written against, the `quantity` field on the shipped model is typed `int | None`,
not a string — so the string-preservation discipline above is a **class-level**
obligation you must confirm against the surface in front of you, not a claim
about a field this package currently declares. If your build types it as a
string, keep it one; if it types it as an int, an integer count is not at risk
from this and the discipline costs nothing.

## MUST 2 — Read the success flag, not the status code, on a provider-backed write

Anything that must be recorded at an external payment provider has two outcomes
that both return `200`: the request was accepted, and the provider accepted it.

```python
# DO — the flag is the outcome; the status is only the transport
result = await <the provider-backed write>
if not getattr(result, "success", False):
    ...   # the provider did not take it; nothing is recorded

# DO NOT
await <the provider-backed write>          # "no exception raised" is not "done"
```

**Why:** the SDK raises on HTTP status. A `200` carrying `success: false` raises
nothing, so an exception-based caller records a payment-method change that did
not happen — and discovers it when a charge fails.

⚠ **Deliberately written without naming a method, because the build this was
written against does not have one.** `client.revenue.billing` exposes exactly one
method here — `setup_payment_method` — and the two-outcome response shape above
was reported from a build that carries more. Naming a method your package does
not export would be the same defect this file's MUST 4 is about. Confirm the
surface you have, then apply the shape.

Watch for a second tell on the same responses: a camelCase field
(`paymentMethodId`) inside an otherwise snake_case module. That is a wire shape
crossing a boundary, and a model that silently drops it will report `None` for a
value the server did send.

## MUST 3 — An over-report cannot be corrected by retrying

A metered usage record is append-only. Under-reporting self-heals: the next
report adds what was missed. **Over-reporting does not.** Correcting it requires
an operator credit, and the server refuses the correction attempt.

```
# DO      surface the conflict to a human; a customer may already be over-charged
# DO NOT  retry it, swallow it, or log it at debug
```

**Why:** a `409` on a usage correction is one of the few responses in this API
that means *a person needs to look at this now*. Retrying converts a recoverable
billing error into a hidden one, and the party who eventually finds it is the
customer.

## MUST 4 — Confirm which quota-update method your build actually reaches

There has been more than one method addressing quota update, and they have not
all pointed at a live route.

```bash
# DO — settle it in ten seconds, against your build
python -c "from aegis_sdk.handbook.check import declared_operations as d; \
print(sorted(p for m,p in d() if 'quota' in p))"
```

In the build this was written against that prints exactly one quota path —
`api:POST /api/v1/billing/quotas/adjust` — and
the method reaching it has been reported as targeting a route the server does not
serve — a `404` for every caller. **UNVERIFIED here:** whether that report holds
against your deployment, because settling it needs a live call and this package
cannot make one for you. Make the call once before you build on either method.

**Why:** a `404` from a client method reads as *"the platform does not support
this"* and sends an architect to the wrong team. It is worth ten seconds to know
whether the method or the platform is the problem.

## MUST 5 — Treat quota adjustment as a platform-administration action

Quota limits derive from the paid plan tier. Adjusting one outside the plan is a
commercial act, gated on platform administration rather than on ordinary tenant
authority — and the shipped docstrings understate the authority required.

**Why:** an architect who reads "admin-only" as *their* organisation's admin will
build a self-service flow that always refuses, and will diagnose it as a
permissions bug rather than as a plan-tier boundary.

## MUST NOT — Report a billing figure without its credential and its build

**Why:** every read here is tenant-scoped, and a figure with nothing attached
invites the reader to treat one organisation's view as the total. See the
measurement guardrail; on this surface the cost of that mistake is denominated
in currency.

## What this does not cover

What your plan actually entitles you to. This governs how to read and write the
billing surface without corrupting it; what the numbers should be is a commercial
question with a commercial owner.
