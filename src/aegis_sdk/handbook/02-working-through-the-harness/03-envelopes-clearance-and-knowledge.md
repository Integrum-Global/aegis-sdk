# 02.3 — Envelopes, clearance and knowledge

Three separate controls that people routinely collapse into one. They answer
different questions, they are checked at different moments, and a design that
confuses them fails in a way that is hard to diagnose because each individual
piece looks correct.

| control | answers | attached to |
| --- | --- | --- |
| **envelope** | what may this delegate *do*? | a role, defined by its supervising role |
| **clearance** | what may this role *see*? | a role |
| **classification** | how sensitive is this *thing*? | a unit (as a default) and each knowledge item |

Access is decided by clearance against classification. **Authority level does not
enter into it** — a C-suite role with no clearance sees less than a staff role
with clearance. This is the single most common modelling error on the platform.

## Envelopes — the five constraint dimensions

An envelope is created by a **defining role** (the supervisor) and applies to a
**target role** (the delegate):

```python
envelope = await client.role_envelopes.create(
    defining_role_id=head_role_id,
    target_role_id=analyst_role_id,
    constraint_config={
        "financial":   {"max_amount": 100_000, "currency": "USD"},
        "operational": {"blocked_actions": ["wire_transfer_external"]},
    },
    status="draft",
)
```

`api:POST /api/v1/role-envelopes`.

The five dimensions come from CARE and are the vocabulary to design in:

| dimension | bounds |
| --- | --- |
| **financial** | spend — amounts, currency, budget |
| **operational** | which actions are permitted or blocked |
| **temporal** | when, and for how long |
| **data access** | which data may be reached |
| **communication** | who or what may be contacted |

### `status` defaults to `draft`, and draft does not enforce

`create` takes `status` and its default is `"draft"`. A draft envelope is a
description of an intention. It is not in force.

```python
await client.org_standup.activate_role_envelope(envelope["id"])   # now it enforces
```

`api:POST /api/v1/role-envelopes/{id}/activate`, and
`api:POST /api/v1/role-envelopes/{id}/suspend` to take it back out of force.

**This is the failure mode to design against:** a provisioning script that
creates envelopes and never activates them produces an organisation that looks
fully bounded in every listing and enforces nothing. Nothing errors. The
`status` field is the only thing that distinguishes the two states, so assert on
it:

```python
envelopes = await client.org_standup.list_role_envelopes()
for e in envelopes.records:
    assert e.status == "active", f"envelope {e.id} is {e.status}, not enforcing"
```

You can pass `status="active"` at creation instead. Prefer that when the envelope
is fully specified, and use `draft` deliberately when a human is going to review
it first — not by accident.

### Envelopes tighten; they never widen

An active envelope is validated against the supervisor's own envelope, and the
composition is **monotonic tightening** — an intersection, never a union. A
delegate cannot be granted authority the defining role does not itself hold.

Two consequences worth designing around:

- **You cannot build an escalation path by adding an envelope.** Widening is not
  expressible. If a delegate needs to exceed its bounds, the answer is a human
  decision (02.6), not a second envelope.
- **Tightening a supervisor tightens everything beneath it,** immediately and
  without touching the children. That is a useful lever in an incident and a
  surprising one if you did not expect it.

`clearance_ceiling` on the envelope caps how far the target's clearance can carry
inside this delegation, and `verification_defaults` sets how thoroughly its
actions are checked.

Read envelopes back with `api:GET /api/v1/role-envelopes` and
`api:GET /api/v1/role-envelopes/{id}`. For an agent rather than a role, the
resolved picture is at `api:GET /api/v1/constraints/agents/{id}/effective` — and
that is the one to trust when you are debugging, because it is the composition
rather than any single input. `api:GET /api/v1/constraints/agents/{id}/inherited`
shows what came down from above, and
`api:POST /api/v1/constraints/agents/{id}/validate` checks a proposed change
before you make it.

## Clearance — what a role may see

Clearance is a separate axis, assigned per role:

```python
await client.trust_posture.create_role_clearance(
    role_id=analyst_role_id,
    max_clearance="confidential",
    justification="Handles cash-position reporting for the Treasury desk.",
)
```

`api:POST /api/v1/role-clearances`. Note it lives on `client.trust_posture`, not
on a `clearances` module.

Four rules the SDK and server enforce, worth knowing before you write the call:

1. **The levels are fixed** — `public`, `restricted`, `confidential`, `secret`,
   `top_secret`. Anything else raises `ValueError` client-side, before a request
   is made.
2. **`justification` is required by the server at `confidential` and above.**
   Omitting it fails server-side, which is a different error from the one above
   and reads differently.
3. **`secret` and `top_secret` require `compartments`.** Clearance at those
   levels is compartmented; a level alone does not grant sight.
4. **⚠ A new clearance lands in `vetting_status="pending"` and is not yet in
   force.** Approval and rejection are separate governance endpoints —
   `api:POST /api/v1/role-clearances/{id}/approve` and
   `api:POST /api/v1/role-clearances/{id}/reject`. This is the same shape as the
   draft envelope above: creating it is not granting it. A provisioning script
   that creates clearances and walks away has staffed an organisation whose roles
   cannot see their own material, and the symptom is an empty screen rather than
   an error.

The return value of `create_role_clearance` is the **raw persisted row**, in
which `compartments_json` is a JSON *string* rather than a deserialised list.
Parse it if you need it; do not index it as a list.

## Knowledge — the governed material itself

```python
policy = await client.knowledge.create(
    title="Treasury Approval Policy",
    content_markdown="# Approval Policy\nAll wires above $50k require sign-off.",
    knowledge_type="policy",
    path="/treasury/policies/approvals",
    classification="confidential",
    owner_unit_id=unit_id,
)
await client.knowledge.publish(policy["id"])
```

`api:POST /api/v1/knowledge`, then `api:POST /api/v1/knowledge/{id}/publish`.

- `knowledge_type` is one of `policy`, `procedure`, `reference`, `faq`.
- `classification` uses the same five levels; **`secret` and `top_secret` require
  a `compartment`**, mirroring clearance.
- `path` is a containment path and is how material is organised and addressed.

**Creating knowledge does not publish it** — a third instance of the same shape.
The lifecycle has more stages than create-and-publish, and for anything that goes
through review you will want them: `api:POST /api/v1/knowledge/{id}/submit`,
`api:POST /api/v1/knowledge/{id}/assign-reviewer`,
`api:POST /api/v1/knowledge/{id}/approve`,
`api:POST /api/v1/knowledge/{id}/request-changes`,
`api:POST /api/v1/knowledge/{id}/reject`, and
`api:POST /api/v1/knowledge/{id}/archive`. Versioning is
`api:POST /api/v1/knowledge/{id}/version` and
`api:POST /api/v1/knowledge/{id}/create-revision`.

### Sharing across a unit boundary is explicit and non-transitive

Units are knowledge boundaries. Material does not flow between them because two
units are adjacent on the chart — it flows because someone wrote a share policy:
`api:POST /api/v1/knowledge-share-policies`, listed at
`api:GET /api/v1/knowledge-share-policies`, and suspended or reactivated at
`api:POST /api/v1/knowledge-share-policies/{id}/suspend` /
`api:POST /api/v1/knowledge-share-policies/{id}/reactivate`.

**Sharing is not transitive.** If A shares with B and B shares with C, C does not
see A's material. Every hop is its own policy and its own decision. Designs that
assume transitivity produce an access model that is more permissive on paper than
in practice — which is the safe direction, but it means the capability you
promised a stakeholder does not exist.

`api:GET /api/v1/knowledge-share-policies/due-for-review` is worth putting on a
schedule; share policies are exactly the thing that gets created for a project
and outlives it.

## The three-way check, once

When a request to read something is evaluated, three things have to line up: the
**role's clearance** (approved, not pending), the **item's classification** (plus
compartment, at the top two levels), and any **share policy** if the reader is
outside the owning unit. A failure in any one of them presents as "you cannot see
this", and the three are not distinguished in the message.

When you are debugging an unexpected denial, check them in that order — clearance
first, because `vetting_status="pending"` is the most common cause and the
cheapest to confirm.

> **In the console:** clearances and envelopes appear under the governance and
> admin areas, and a held or refused access shows up in the approvals queue
> (02.6). The console is where the *reviewer* approves a pending clearance; the
> harness is where you create the fifty that need reviewing.

---

*Next: [02.4 — Trust chains and postures](04-trust-chains-and-postures.md)*
