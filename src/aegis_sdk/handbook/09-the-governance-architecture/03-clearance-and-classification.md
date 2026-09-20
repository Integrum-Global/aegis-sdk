# 09.3 — Clearance and classification

Clearance is the answer to _what may this role see_. It is the second of the two
independent bounds in the Trust Plane, it runs on a five-level ladder inherited
from EATP, and it is the axis most often collapsed into something it is not.

This chapter is the complete read-access model: the ladder and its ranks, how a
role's clearance is granted and approved, what compartments add at the top two
levels, how an agent's _effective_ clearance is computed from its role's
clearance and its posture, and the three-way check a read actually passes
through. [09.2](02-envelopes-and-constraints.md) covered the action axis; the two
compose but never substitute.

The idea to carry out: **authority level does not enter into read access at
all.** A C-suite role with no clearance sees less than a staff role with
clearance. This is the single most common modelling error on the platform, it
survives review because the org chart looks right, and the symptom is a senior
person reporting an empty screen.

## The ladder

Five levels, lowercase, ordered. They are EATP's, and Aegis uses them
unmodified.

| level              | rank | display           | compartment required? |
| ------------------ | ---- | ----------------- | --------------------- |
| **`public`**       | 0    | Public (C0)       | no                    |
| **`restricted`**   | 1    | Restricted (C1)   | no                    |
| **`confidential`** | 2    | Confidential (C2) | no                    |
| **`secret`**       | 3    | Secret (C3)       | **yes**               |
| **`top_secret`**   | 4    | Top Secret (C4)   | **yes**               |

Every access decision on this axis is a rank comparison: the reader's effective
clearance rank against the item's classification rank, with `>=` admitting. At
the top two levels a rank comparison alone is not sufficient and compartments
supply the need-to-know dimension — see § Compartments below.

Two properties of the ladder are load-bearing and neither is obvious:

**The levels are fixed and validated client-side.** Anything outside the five
raises before a request is made. That is deliberate: a typo'd level is a bound
that silently matches nothing, and catching it at the client costs one
round-trip rather than one incident.

**Unknown is not `public`.** An item whose classification cannot be resolved —
absent, or a value no level maps — is treated as _unknown_, and unknown denies at
every egress boundary. This is the opposite of the intuitive default and it is
the right one: "we do not know what this is" must never resolve to "the least
sensitive thing there is". [09.7](07-containment-and-explainable-refusal.md)
carries the full treatment, because it is where the consequences land.

## Granting a clearance, and the state it lands in

```python
clearance = await client.trust_posture.create_role_clearance(
    role_id=analyst_role_id,
    max_clearance="confidential",
    justification="Handles cash-position reporting for the Treasury desk.",
)
await client.trust_posture.approve_role_clearance(clearance["id"])
```

`api:POST /api/v1/role-clearances` creates it. Note it lives on
`sdk:aegis_sdk.TrustPostureModule`, not on a clearances module of its own —
clearance and posture are read together often enough that they share a surface.

Four rules bind the write, and each has a distinct failure signature:

1. **The levels are fixed.** Anything outside the five raises client-side,
   before a request is made.
2. **`justification` is required by the server at `confidential` and above.**
   Omitting it fails server-side, which is a different error from the one above
   and reads differently — a `422` rather than a `ValueError`.
3. **`secret` and `top_secret` require `compartments`.** A level alone does not
   grant sight at those two; see below.
4. **A new clearance lands in `vetting_status="pending"` and is not yet in
   force.**

> ⛔ **The fourth rule is the expensive one, and it is the same shape as the
> `draft` envelope in [09.2](02-envelopes-and-constraints.md).** Creating a
> clearance is not granting it. Approval and rejection are separate governance
> steps — `api:POST /api/v1/role-clearances/{id}/approve` and
> `api:POST /api/v1/role-clearances/{id}/reject` — and until approval the role
> reads at `public`. A provisioning script that creates clearances and walks away
> has staffed an organisation whose roles cannot see their own material, and the
> symptom is **an empty screen rather than an error**. There is nothing in the
> UI, nothing in the logs, and nothing in the clearance listing that reads as
> wrong; the row exists, it names the right level, and `vetting_status` is the
> only field that says it is not in force.

Read them back with `api:GET /api/v1/role-clearances` and
`api:GET /api/v1/role-clearances/{id}`; amend with
`api:PUT /api/v1/role-clearances/{id}`; remove with
`api:DELETE /api/v1/role-clearances/{id}`. Assert on `vetting_status` in
provisioning the same way you assert on envelope `status`:

```python
clearances = await client.trust_posture.list_role_clearances()
for c in clearances.records:
    assert c.vetting_status == "active", f"clearance {c.id} is {c.vetting_status}"
```

The separation is the point rather than an inconvenience. Clearance is the one
governance object whose grant a machine should not be able to complete
unattended, and the approval step is where a human takes responsibility for it.
The console is where a reviewer approves a pending clearance; the harness is
where you create the fifty that need reviewing.

## Compartments — the need-to-know dimension

At `secret` and `top_secret`, a rank comparison is not an access model. Two
roles both cleared to `secret` are not thereby cleared to each other's material,
and the mechanism that expresses this is the compartment.

```python
clearance = await client.trust_posture.create_role_clearance(
    role_id=treasury_lead_role_id,
    max_clearance="secret",
    compartments=["treasury-positions", "counterparty-exposure"],
    justification="Desk lead; requires position and exposure detail.",
)
```

The rule has two halves and both must hold:

- the reader's clearance rank must reach the item's classification rank, **and**
- at `secret` / `top_secret`, the item's compartment must be one the reader is
  specifically cleared for.

A `secret`-cleared role with no membership in the item's compartment is refused,
and so is a `secret` item that carries no compartment at all — the latter fails
closed rather than being treated as uncompartmented material. An item at those
levels without a compartment is an item whose need-to-know boundary was never
declared, and serving it would be enforcing a rank comparison while presenting
it as need-to-know isolation.

> ⚠ **A container that cannot express compartments cannot hold compartmented
> material.** Several object kinds in Aegis carry a classification and no
> compartment — and their writable vocabulary is therefore capped at
> `{public, restricted, confidential}`. This is not a limitation to work around;
> it is the model refusing to offer protection it cannot deliver. A control that
> reads stronger than what runs is worse than a narrower one that is honest.
> [09.7](07-containment-and-explainable-refusal.md) § "A container may only hold
> what it can enforce" is the general statement.

The return value of the clearance create is the raw persisted row, in which
`compartments_json` is a JSON _string_ rather than a deserialised list. Parse it
if you need it; indexing it as a list produces a character.

## Effective clearance — clearance capped by posture

A role's clearance is not an agent's clearance. An agent acting in that role has
an **effective clearance**, and it is the lower of two things:

```
effective_clearance = min( role.max_clearance , posture_ceiling[agent.posture] )
```

The posture ceiling is fixed by CARE and is not configurable per agent:

| posture              | maximum effective clearance |
| -------------------- | --------------------------- |
| `pseudo`             | `public`                    |
| `supervised`         | `restricted`                |
| `shared_planning`    | `confidential`              |
| `continuous_insight` | `secret`                    |
| `delegated`          | the role's full clearance   |

Read that table as the answer to a question people ask the wrong way round. It
is not "what clearance does this posture grant" — a posture grants nothing. It
is "how much of the seat's clearance may an agent at this standing actually
carry". A newly provisioned agent at `supervised` sitting in a role cleared to
`secret` reads at `restricted`, and that is correct: the agent has not yet
demonstrated anything, and the seat's clearance is a property of the seat.

There is a third cap. An envelope's `clearance_ceiling`
([09.2](02-envelopes-and-constraints.md)) narrows how far the target role's
clearance carries _inside that particular delegation_, which lets a supervisor
delegate a task without delegating the whole of the delegate's sight.

**The failure mode this produces:** an agent that could read a document
yesterday and cannot today, with no change to the document and no change to the
role's clearance — because an emergency posture override
([09.5](05-trust-chains-and-postures.md)) moved the agent down a level and the
ceiling moved with it. The remedy is not to raise the clearance. Read the
posture first.

## Classifying the material

The other half of the comparison is the item's own classification. Knowledge is
the principal classified object and carries the full model — classification,
compartment, containment path, and a review lifecycle.

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

`api:POST /api/v1/knowledge` then `api:POST /api/v1/knowledge/{id}/publish`.
`knowledge_type` is one of `policy`, `procedure`, `reference`, `faq`; `path` is
a containment path and is how material is organised and addressed;
`classification` uses the same five levels, with the same compartment
requirement at the top two.

**Creating knowledge does not publish it** — a third instance of the shape this
part keeps returning to. For anything going through review the lifecycle has
more stages than create-and-publish, and each is its own call:
`api:POST /api/v1/knowledge/{id}/submit`,
`api:POST /api/v1/knowledge/{id}/assign-reviewer`,
`api:POST /api/v1/knowledge/{id}/approve`,
`api:POST /api/v1/knowledge/{id}/request-changes`,
`api:POST /api/v1/knowledge/{id}/reject`, and
`api:POST /api/v1/knowledge/{id}/archive` with
`api:POST /api/v1/knowledge/{id}/unarchive` as its inverse. Versioning is
`api:POST /api/v1/knowledge/{id}/version` and
`api:POST /api/v1/knowledge/{id}/create-revision`. The review queue itself is
`api:GET /api/v1/knowledge-reviews`.

Beyond knowledge, `sdk:aegis_sdk.modules.GovernanceModule` carries the data
classification registry — `api:GET /api/v1/data-governance/classifications`,
`api:POST /api/v1/data-governance/classifications`,
`api:PUT /api/v1/data-governance/classifications/{id}` — which is where field-
and dataset-level classifications live for material that is not a knowledge
item. The two share the ladder.

## Units are boundaries, and sharing is explicit

Classification is one of two things that gate a read. The other is containment:
material belongs to a unit, and units are knowledge boundaries.

Material does not flow between units because the two are adjacent on the org
chart. It flows because somebody wrote a share policy:
`api:POST /api/v1/knowledge-share-policies`, listed at
`api:GET /api/v1/knowledge-share-policies`, suspended and reactivated at
`api:POST /api/v1/knowledge-share-policies/{id}/suspend` and
`api:POST /api/v1/knowledge-share-policies/{id}/reactivate`.

> ⛔ **Sharing is not transitive.** If A shares with B and B shares with C, C
> does not see A's material. Every hop is its own policy and its own decision.
> A design that assumes transitivity produces an access model more permissive on
> paper than in practice — the safe direction, but it means a capability you
> promised a stakeholder does not exist, and the symptom is a user who can see
> the material through one route and not through the route they were told to
> use.

`api:GET /api/v1/knowledge-share-policies/due-for-review` belongs on a schedule.
Share policies are exactly the object that gets created for a project and
outlives it, and a review cadence is the only thing that catches one.

For the broader containment question — which units are isolated from which at
the tenancy level — `api:GET /api/v1/organization-units/isolation-domains` reads
the current partition and `api:PUT /api/v1/organization-units/isolation-domains`
sets it.

## The three-way check

When a read is evaluated, three things must line up.

```text
A READ, EVALUATED — three gates, one message

  reader asks for item X
        │
        ▼
  ┌─ GATE A · CLEARANCE ────────────────────────────────────────────────┐
  │  effective_clearance = min(role.max_clearance, posture_ceiling)      │
  │  is vetting_status ACTIVE?  is rank(effective) >= rank(item)?        │
  │  at secret/top_secret: is the item's compartment one I hold?         │
  └────────────────────────────┬────────────────────────────────────────-┘
                               │ pass
                               ▼
  ┌─ GATE B · CLASSIFICATION ───────────────────────────────────────────┐
  │  does the item carry a resolvable mark at all?                       │
  │  UNKNOWN denies — it is not read as `public`                         │
  └────────────────────────────┬────────────────────────────────────────┘
                               │ pass
                               ▼
  ┌─ GATE C · CONTAINMENT ──────────────────────────────────────────────┐
  │  is the reader inside the owning unit?                               │
  │  if not: is there an ACTIVE share policy for this exact hop?         │
  └────────────────────────────┬────────────────────────────────────────┘
                               │ pass
                               ▼
                        the item is served

  A FAILURE IN ANY ONE OF THE THREE PRESENTS IDENTICALLY:
  "you cannot see this" — and the three are not distinguished in the message.
```

Read it as: three independent conditions, one indistinguishable symptom. That is
deliberate — a refusal that told you _which_ gate refused would let a reader map
the classification of material they cannot see, and existence is itself
information at the top two levels.

It does mean you need an order to debug in, and the order is not the order the
gates run in. **Check clearance first**, because `vetting_status="pending"` is
the most common cause and the cheapest to confirm. Then classification, because
an unmarked item is the second most common and is invisible from the reader's
side. Containment last, because a missing share policy is the one a human
usually remembers not creating.

`api:POST /api/v1/governance/explain-access` short-circuits the whole procedure
when you hold the right credential: it evaluates a **role against a knowledge
item** and returns the decision as a trace — allowed or not, the reason, the
`step_reached` (the phase name the evaluation stopped at), and the access path
taken.

```python
trace = await client.governance_explain.explain_access(
    agent_id=agent_id,
    knowledge_item_id=document_id,
)
```

⛔ **Read `step_reached`, not `allowed`, when you are diagnosing.** `allowed`
tells you the outcome you already observed; `step_reached` tells you _which of
the three gates above the evaluation stopped at_, which is the whole reason to
call it. A trace that stops at the clearance phase and one that stops at
containment produce the same `allowed: false` and send you to different remedies.

⚠ **It is a DRY RUN, and that is the property to design around.** The call
evaluates the item you describe: nothing is read from any stored refusal record,
nothing is accessed, and nothing is recorded. A wrong or missing field in the
subject you pass changes the verdict — so a trace is only as good as the
description it was given, and a clean result is evidence about the model's
decision on that description, not about any access that actually happened. To
find out what happened, read the audit spine
([09.6](06-the-audit-spine-and-evidence.md)); this surface answers _what would
the model decide_, and the two questions are not interchangeable.

## Where classification meets the rest of the model

Three cross-references, each of which is a place a design goes wrong by treating
this axis in isolation.

**Classification is a property of the field, not of the verb.** A write
operation that returns a row is a read surface. Every mutation return path in the
platform applies the same redaction the read path applies, which is why an agent
that creates a record containing a field above its clearance gets that field back
redacted rather than echoed. Design your own integrations the same way: the
caller having just supplied a value is not a reason to return it to them.

**Retrieval filters before it ranks.** When classified material backs a
retrieval surface, the clearance filter is applied before retrieval rather than
after. Post-retrieval filtering leaks through ranking scores and result counts —
a `restricted`-cleared agent could infer the existence of `secret` documents by
watching how many results come back. The filter belongs in the query.

**Lineage carries classification forward.** Derived material inherits the
high-water mark of everything it was derived from, so a summary of a `secret`
input is `secret` even if the summary itself reads innocuously.
`api:GET /api/v1/data-governance/lineage/graph` and
`api:GET /api/v1/data-governance/lineage/nodes/{id}/upstream` are the read
surfaces for the general case; [09.7](07-containment-and-explainable-refusal.md)
is where the rule is stated in full.

> **In the console:** clearances appear under the governance area and a pending
> one shows in the approvals queue for whoever holds the reviewing persona. The
> clearance surface is deliberately gated behind an administrative persona — a
> director cannot read or grant clearances, which is why "I can see the role but
> not its clearance" is a correct outcome rather than a permissions bug.

## Summary

| you need                                        | the object                    | the call                                                  |
| ----------------------------------------------- | ----------------------------- | --------------------------------------------------------- |
| let a role see classified material              | role clearance                | `api:POST /api/v1/role-clearances`                        |
| put that clearance in force                     | approval                      | `api:POST /api/v1/role-clearances/{id}/approve`           |
| add need-to-know at `secret`+                   | compartments on the clearance | `compartments=[...]` at create                            |
| mark material                                   | knowledge classification      | `api:POST /api/v1/knowledge`                              |
| put material in force                           | publication                   | `api:POST /api/v1/knowledge/{id}/publish`                 |
| let material cross a unit boundary              | share policy                  | `api:POST /api/v1/knowledge-share-policies`               |
| find share policies that outlived their project | review queue                  | `api:GET /api/v1/knowledge-share-policies/due-for-review` |
| find out which gate would refuse                | access dry run                | `api:POST /api/v1/governance/explain-access`              |

---

_Next: [09.4 — The decision gradient](04-the-decision-gradient.md)_
