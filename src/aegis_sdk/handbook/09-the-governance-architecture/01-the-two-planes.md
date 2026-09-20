# 09.1 — The two planes

Every action an agent takes in Aegis passes through two distinct systems, and
the entire governance architecture is a consequence of keeping them apart. One
decides whether the action is permitted and records that it was decided. The
other does the work. CARE calls them the **Trust Plane** and the **Execution
Plane**, and the split is not an implementation convenience — it is the claim
the product makes.

This chapter is the frame for the six that follow. It is not a tour of the
platform's internals; [06.1](../06-architecture/01-what-core-and-the-sdk-are.md)
draws the client/deployment boundary and [06.2](../06-architecture/02-the-request-path.md)
traces a call through the layers. What this chapter establishes is _which plane
a given control belongs to_, and why a control placed on the wrong one produces
a system that passes every review and governs nothing.

The single idea to carry out: **the harness is what an agent can do and what it
may do, inseparably.** Not two systems, one of which constrains the other. One
object, seen from two sides.

## Why the split exists at all

The intuitive design for AI governance is a permission layer in front of a model:
the model is the capability, the layer is the restriction, and you tune the layer
until the risk is acceptable. That design has a property nobody wants — the
capability is defined independently of the restriction, so every new capability
arrives unbounded by default and someone has to remember to bound it.

Aegis inverts it. An agent's capability **is** its envelope, its clearance, its
chain and its posture. There is no underlying unbounded agent that these
constrain. A role with no envelope does not have unlimited authority; it has
undefined authority, which the composition treats as a refusal
([09.2](02-envelopes-and-constraints.md)). A role with no clearance does not see
everything; it sees `public` and nothing else
([09.3](03-clearance-and-classification.md)). An agent with no trust chain is not
an ungoverned agent — it is invisible to trust discovery and refused at the
decision ([09.5](05-trust-chains-and-postures.md)).

That inversion is what makes autonomy _scalable_ rather than merely permitted.
Control here is not the tax paid on capability; it is the mechanism by which a
wider grant becomes safe enough to make. Ungoverned capability does not scale —
it stops at the first thing nobody dares let it touch.

> ⛔ **Never describe an Aegis control as only a guardrail, or only a
> capability.** Both halves are true of every object in this part, and naming
> one half describes a different system. An envelope grants a delegate the
> authority to spend and bounds the amount, in one declaration. A tool binding
> confers reach and, through the same object, decides the limit. Design
> documents that split them end up with a capability shipped without its bound —
> an exposure — or a bound with no capability behind it, which is ceremony.

## What each plane owns

|                        | Trust Plane                                                            | Execution Plane                                                  |
| ---------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **question**           | may this happen, and on whose authority?                               | make it happen                                                   |
| **objects**            | authority · chain · posture · envelope · clearance · policy · decision | objective · request · session · work unit · artifact             |
| **output**             | a verdict, plus the reasoning                                          | a result, plus the record that it ran                            |
| **failure mode**       | refuses, and names the constraint that refused                         | errors, retries, or times out                                    |
| **your read surfaces** | `sdk:aegis_sdk.trust` · `sdk:aegis_sdk.modules.GovernanceModule`       | `sdk:aegis_sdk.execution` · `sdk:aegis_sdk.WorkObjectivesModule` |

The division is sharper than it looks, and the sharpest part is this: **the Trust
Plane never produces a result and the Execution Plane never produces a verdict.**
A trust decision does not carry the output of the action it permitted — it cannot,
because the action has not happened yet. An execution record does not carry an
authorisation — it carries the fact that something ran. Asking either one for the
other's answer is the most common category error in designs built on this
platform, and it presents as a missing field rather than as a design problem.

```text
ONE ACTION, BOTH PLANES

  an agent forms an intent
        │
        ▼
  ╔═══ TRUST PLANE ════════════════════════════════════════════════════════╗
  ║                                                                        ║
  ║   chain      does this agent hold authority, and is it still valid?    ║
  ║   posture    how much may it use unaided, right now?                   ║
  ║   envelope   does the bound permit THIS action?                        ║
  ║   clearance  may it see the material the action touches?               ║
  ║                                                                        ║
  ║   ⇒ ONE verdict on THIS action:   auto_approved / flagged / held /     ║
  ║                                   blocked                              ║
  ╚═══════════════════════════════╤════════════════════════════════════════╝
                                  │
            ┌─────────────────────┴──────────────────────┐
            │                                            │
     permitted or flagged                          held or blocked
            │                                            │
            ▼                                            ▼
  ╔═══ EXECUTION PLANE ═══════════╗          the action does not run.
  ║  the work runs                ║          A HELD action waits on a
  ║  an artifact may be produced  ║          human decision (09.4);
  ║  the run is recorded          ║          a BLOCKED one is refused
  ╚═══════════════╤═══════════════╝          outright and the reason
                  │                          names the constraint.
                  ▼
  ╔═══ THE AUDIT SPINE ════════════════════════════════════════════════════╗
  ║  the decision AND the run are both recorded, by different subsystems,  ║
  ║  into two logs that answer two different questions (09.6)              ║
  ╚════════════════════════════════════════════════════════════════════════╝
```

Read it as: the verdict is reached _before_ the work, over an intent — a tool
name and its arguments, an action and a resource kind. The record is written
_after_. They are two different witnesses to one event, and neither substitutes
for the other. A system that can produce one and not the other cannot answer the
question an auditor actually asks, which is never "was something enforced" but
"show me that it was".

## The three planes people expect, and the one that is not there

Architects arriving from a policy-engine background reach for a third plane: a
**Policy Plane** holding rules, separate from the Trust Plane that evaluates
them. Aegis does not have one, deliberately, and knowing why saves a design
cycle.

Policies in Aegis are not free-standing documents consulted at decision time.
They are **compiled into the objects the decision already reads**. An
organisation-level policy with an `envelope` enforcement tier is intersected
into the affected agents' constraint envelopes through the same
monotonic-tightening path every other envelope uses; from that moment the
constraint engine enforces it at every invocation, with no separate policy
lookup. Authoring is `api:POST /api/v1/policies` and
`api:POST /api/v1/policies/{id}/assign`; the compiled result is read back where
every other bound is read, at `api:GET /api/v1/constraints/agents/{id}/effective`.

```python
policy = await client.governance.create_policy(
    name="Treasury spend ceiling",
    node_address="D1-R1-D1-R1",
    enforcement_tier="envelope",
    policy_body={
        "max_cost_usd": "500.00",
        "action_constraints": {"prohibited": ["wire_transfer_external"]},
    },
)
await client.governance.list_policies()
```

Three enforcement tiers exist, and the difference between them is the difference
between a rule and a control:

| tier           | what it does                                                                                 | binding?                                                   |
| -------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **`soft`**     | advisory rule text injected into the agent's instructions                                    | no — honestly labelled non-binding                         |
| **`envelope`** | intersected into the constraint envelope; the engine enforces it at every invocation         | yes, hard                                                  |
| **`gate`**     | targets the four-zone verification gradient, recorded onto the agent's posture configuration | yes, at the gradient ([09.4](04-the-decision-gradient.md)) |

> ⛔ **A financial or action-limit policy authored at `soft` is not a control.**
> The tier is named honestly and the platform refuses to pretend otherwise: a
> spend cap enforced by a sentence in a prompt is a request, not a ceiling. The
> symptom when this goes wrong is the worst possible one — the policy appears in
> `api:GET /api/v1/policies`, reads correctly to every reviewer, and the agent
> exceeds it without anything erroring, because nothing was ever asked to stop
> it. Author limits at `envelope`.

The absence of a Policy Plane is what makes the guarantee checkable. If policies
lived in their own plane, "is this policy in force?" would be a question about
two systems agreeing. Because they compile into the envelope, it is a question
about one object, and `api:GET /api/v1/governance/envelope-coverage` can answer
it mechanically.

## The five harness classes

CARE's dual plane is a philosophical claim. What implements it in a running
deployment is a **harness** — and the harness has parts, each of which grants
something and bounds something in the same breath.

| class         | what it grants                                          | what it bounds                                          |
| ------------- | ------------------------------------------------------- | ------------------------------------------------------- |
| **intent**    | the role's purpose, its job description, what it is for | everything that is not that purpose                     |
| **skills**    | a competence the role can exercise                      | the scope that competence may be exercised in           |
| **rules**     | the invariants the deployment holds                     | the shapes an agent may not produce                     |
| **tools**     | reach into a system outside the platform                | whether the binding is enabled, and under what envelope |
| **knowledge** | what an agent knows                                     | what it may not know, by classification                 |

Read the table as five instances of one pattern, not five different mechanisms.
In each row the two columns are the same declaration read in opposite
directions. A tool binding is the clearest case: the object that gives an agent
reach into an external system is the same object whose enabled flag decides the
limit, and there is no second object to consult. Part 03 covers authoring them;
what matters here is the shape.

> ⚠ **An empty harness class is never neutral.** A role with no skills is not a
> role with general competence — it is a role whose competence is undeclared. A
> deployment with no rules is not a permissive deployment; it is one where
> nothing expresses what a wrong answer looks like. When you audit a class and
> find it empty, the finding is _which_ — capability left unbounded, or control
> left ungranted — and the two have opposite remedies.

**Scaling autonomy means thickening the harness, never loosening it.** When the
answer to "this agent needs to do more" is to remove a bound, the result is an
agent that does more of what nobody is watching. The answer that works is more
harness: a wider envelope with a tighter gradient, a higher posture with richer
evidence behind it, a broader clearance with compartments that scope it.
[09.5](05-trust-chains-and-postures.md) is the whole of that argument, made on
the posture axis.

## Which plane refused you

This is the practical payoff of the split, and it is worth one concrete
procedure because the two refusals arrive with overlapping status codes and have
completely different remedies.

```bash
# Establish who you are holding, as distinct from who you assumed
curl -H "Authorization: Bearer $TOKEN" "$AEGIS/api/v1/auth/me"   # the principal
```

`api:GET /api/v1/auth/me` reports the principal currently in force. Read the
refusal against it:

| symptom                                                     | plane              | what it means                                              | remedy                                                                               |
| ----------------------------------------------------------- | ------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `401` / `403` naming a **scope**                            | neither — the door | the credential does not carry the scope the route requires | mint a key with the scope ([04.3](../04-the-api-surface/03-credentials-and-keys.md)) |
| `403` naming a **constraint**                               | Trust Plane        | the bound refused this action for this agent               | widen the envelope deliberately, or route through a human decision                   |
| `403` naming **clearance** or presenting as an empty result | Trust Plane        | the reader may not see the material                        | grant and approve the clearance ([09.3](03-clearance-and-classification.md))         |
| `409` naming a **state**                                    | Trust Plane        | the object exists but is not in force — `draft`, `pending` | activate or approve it                                                               |
| `500` / timeout                                             | Execution Plane    | the work failed; nothing about authorisation is implied    | retry, or read the execution record                                                  |

The distinction that costs the most when it is missed is the second row against
the first. A scope refusal is a statement about _your credential_ and no amount
of governance change will fix it. A constraint refusal is a statement about _the
agent's bounds_ and no amount of credential change will fix it. Both read
`403 Forbidden` from outside, and the only reliable discriminator is the body:
a constraint refusal names the constraint.

The client raises distinct exception types along the same line, which is the
cheapest discriminator available to code rather than to a human:
`sdk:aegis_sdk.AuthorizationError` for the door,
`sdk:aegis_sdk.GovernanceViolationError` when a governance bound refused, and
`sdk:aegis_sdk.TrustViolationError` when the refusal came from the trust
decision itself. Catching them separately is worth the three lines — a handler
that catches the base error and retries will retry a governance refusal forever,
because nothing about the passage of time changes an envelope.

`api:POST /api/v1/governance/explain-access` is the tool for the second and
third rows. It is a **dry run**: it evaluates a role against a knowledge item you
describe and returns the decision as a trace rather than a verdict — whether
access would be allowed, the reason, the `step_reached`, and the path it took.
The step name is the useful field, because it tells you _where_ the evaluation
stopped rather than merely that it did.

```python
trace = await client.governance_explain.explain_access(
    agent_id=agent_id,
    knowledge_item_id=document_id,
)
```

Nothing is accessed and nothing is recorded by that call, so it answers _what
would the model decide_ rather than _why was my request refused_. The second
question belongs to the audit spine ([09.6](06-the-audit-spine-and-evidence.md)).

> **In the console:** the two planes are separate areas by design. Governance,
> trust and approvals live under the governance section; objectives, sessions
> and runs live under work. When an operator says "the agent did nothing", the
> first question is which of those two areas shows the event — a held action
> appears in the approvals queue and never in the run history, which reads as
> silence from the work side.

## Where each plane surfaces in the client

The client you hold is partitioned along the same line, and knowing which
namespace a module lives in is a reliable shortcut for knowing which plane a
question belongs to.

| namespace                                       | plane     | what it carries                                                         |
| ----------------------------------------------- | --------- | ----------------------------------------------------------------------- |
| `sdk:aegis_sdk.trust`                           | Trust     | authorities, chains, postures, delegations, revocation, the trust audit |
| `sdk:aegis_sdk.modules.GovernanceModule`        | Trust     | policies, permissions, classifications, consent, lineage                |
| `sdk:aegis_sdk.modules.GovernanceExplainModule` | Trust     | the explain surfaces — access, envelope, address                        |
| `sdk:aegis_sdk.standup.RoleEnvelopesModule`     | Trust     | envelope authoring and activation                                       |
| `sdk:aegis_sdk.standup.ApprovalsModule`         | Trust     | the human decision surface                                              |
| `sdk:aegis_sdk.modules.ComplianceModule`        | Trust     | frameworks, reports, retention, chain integrity                         |
| `sdk:aegis_sdk.execution`                       | Execution | objectives, requests, sessions, artifacts                               |
| `sdk:aegis_sdk.WorkObjectivesModule`            | Execution | work as it is planned and carried                                       |
| `sdk:aegis_sdk.modules.ObserveAuditModule`      | the spine | the platform record of what changed                                     |

Two entries repay a second look. `sdk:aegis_sdk.modules.ObserveAuditModule` is
deliberately placed in neither plane — the audit spine is written _by_ both and
owned by neither, which is [09.6](06-the-audit-spine-and-evidence.md)'s subject.
And `sdk:aegis_sdk.modules.ComplianceModule` sits on the Trust Plane rather than
alongside it, because a compliance framework here is a set of controls over the
governance objects rather than a reporting layer draped over them.

You hold one client — `sdk:aegis_sdk.AgenticOSClient`, configured through
`sdk:aegis_sdk.ClientConfig` against a base URL you supply — and both planes are
reached through it. The configuration surface is entirely about the connection:
which deployment, with which credential, under which timeout and retry policy.
None of it is about the organisation's content, which is asked for per call.

## The harness classes, worked

The five classes are easiest to see on one role. Take a treasury analyst whose
job is to reconcile settlement positions and draft, but never send, outbound
wires.

| class         | the grant                                                                             | the bound                                                                                           |
| ------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **intent**    | "reconcile settlement positions and draft outbound wires for review"                  | everything outside reconciliation and drafting                                                      |
| **skills**    | position reconciliation, wire drafting                                                | no settlement execution competence is declared, so none is exercisable                              |
| **rules**     | the invariants — a wire always names a counterparty, a reconciliation always balances | shapes the agent may not produce                                                                    |
| **tools**     | a binding to the positions system, read-only                                          | the binding's envelope bounds which accounts, and its enabled flag decides whether it exists at all |
| **knowledge** | the treasury desk's procedures at `confidential`                                      | nothing at `secret`, because the role's clearance stops there                                       |

Read down the second column and you have the role's capability. Read down the
third and you have its governance. **They are the same five declarations.** There
is no sixth object holding the restrictions, which is why there is no way to
remove the restrictions and keep the role.

The operational consequence is worth stating because it changes how you
provision: **when a role needs to do something new, the change is always additive
and always in both columns.** Add the skill and its scope. Add the tool binding
and its envelope dimension. Add the knowledge and the clearance that reaches it.
A change that touches only one column is the one to catch in review — a skill
with no scope, or a scope with no skill.

## Why governance is the product

It is tempting to read this part as the safety documentation for a capability
product. It is the other way round, and the distinction has practical
consequences for what you build.

A competitor bolting a permission layer onto a model has built a different thing,
not a cheaper version of this one. Their capability exists independently of their
controls, so their controls can be removed and the capability survives. Here they
cannot: remove an agent's envelope and the composition refuses; remove its chain
and the decision refuses; remove its clearance and it sees `public`. The system
degrades toward _doing nothing_, not toward _doing anything_.

That is the property the architecture exists to deliver, and it is the one to
carry into your own design. **When you extend the platform, extend both halves
in the same change.** A new tool with no envelope dimension covering it is an
exposure. A new gate on a surface nothing can invoke is ceremony. The chapters
that follow are, between them, the vocabulary for keeping the two together.

## Summary

| you want to know                  | plane     | the call                                            |
| --------------------------------- | --------- | --------------------------------------------------- |
| which principal am I holding      | the door  | `api:GET /api/v1/auth/me`                           |
| which organisations can I act in  | the door  | `api:GET /api/v1/auth/me/organizations`             |
| switch the acting organisation    | the door  | `api:POST /api/v1/auth/me/switch-org`               |
| may this agent take this action   | Trust     | `api:POST /api/v1/trust/verify`                     |
| why a read would be refused       | Trust     | `api:POST /api/v1/governance/explain-access`        |
| what bounds this agent right now  | Trust     | `api:GET /api/v1/constraints/agents/{id}/effective` |
| is the governance layer enforcing | Trust     | `api:GET /api/v1/governance/envelope-coverage`      |
| author a rule that binds          | Trust     | `api:POST /api/v1/policies` at `envelope` tier      |
| which agents exist                | Execution | `api:GET /api/v1/agents`                            |
| what changed, and who changed it  | the spine | `api:GET /api/v1/audit/logs`                        |

---

_Next: [09.2 — Envelopes and constraints](02-envelopes-and-constraints.md)_
