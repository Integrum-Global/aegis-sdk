# 09.2 — Envelopes and constraints

An envelope is the answer to _what may this delegate do_. It is the Trust
Plane's bound on action, it is authored by a supervising role rather than by the
delegate, and it composes down a hierarchy by intersection — which is the whole
of its safety property and the source of every surprise it produces.

[02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
shows you how to create and activate one. This chapter is about the algebra: the
five dimensions the bound is expressed in, the three layers an effective bound is
composed from, why the composition can only ever tighten, and what it means when
a link in the chain is missing. Clearance — _what may this delegate see_ — is a
separate axis with a separate algebra and is [09.3](03-clearance-and-classification.md).

The idea to carry out: **an envelope is not a list of permissions, it is a
ceiling, and every ceiling beneath it is lower.** Designs that treat envelopes
as grants — "add an envelope to let this agent do more" — are expressing
something the model cannot represent, and the failure is silent.

## The five constraint dimensions

CARE defines five, and they are the complete vocabulary. Every bound on action
in Aegis is expressed as one of them; there is no sixth, and a limit that does
not fit one of the five is a limit the model is not carrying.

| dimension         | canonical name  | bounds                                 | typical shape                                     |
| ----------------- | --------------- | -------------------------------------- | ------------------------------------------------- |
| **Financial**     | `financial`     | spend — amounts, currency, budget      | `{"max_amount": 100000, "currency": "USD"}`       |
| **Operational**   | `operational`   | which actions are permitted or blocked | `{"blocked_actions": ["wire_transfer_external"]}` |
| **Temporal**      | `temporal`      | when, and for how long                 | window, duration, expiry                          |
| **Data Access**   | `data_access`   | which data may be reached              | prohibited fields, scopes                         |
| **Communication** | `communication` | who or what may be contacted           | internal-only, recipient allowlists               |

The names above are the canonical CARE spellings, lowercase, and they are what
you write in `constraint_config`. Three of the five are worth a sentence of
design guidance each, because they are the ones people under-use:

- **Temporal** is the dimension that makes an emergency widening safe. A bound
  with no temporal component cannot expire, so every widening becomes permanent
  by default and somebody has to remember to undo it. [09.4](04-the-decision-gradient.md)
  § "The emergency path" is built on this.
- **Data Access** is not clearance. Clearance answers _is this reader permitted
  to see material at this classification_; Data Access answers _may this
  delegate reach this data at all, whatever its classification_. A delegate can
  hold `secret` clearance and still be refused a table its envelope excludes.
- **Communication** is the dimension most often left empty, and an empty
  Communication constraint on an agent with outbound tool bindings is the
  clearest case of a capability shipped without its bound. If the agent can send
  email, the envelope should say to whom.

> ⚠ **Aegis persists several historical spellings of these names and translates
> them at their boundaries.** An organisation-level policy may carry `data`
> where a role envelope carries `data_access`; a wire shape may carry
> `transaction`, which CARE treats as a sub-type of Financial. They name the same
> dimensions and the platform relates them. What matters for your own authoring
> is that you write the canonical five and read the composed result from
> `api:GET /api/v1/constraints/agents/{id}/effective`, which resolves them for
> you rather than leaving you to match spellings.

## Three layers, one effective bound

A delegate's actual bound is never a single object. It is the composition of
three layers, and knowing which layer you are looking at is the difference
between debugging the right thing and debugging a symptom.

```text
THE THREE LAYERS OF THE OPERATING ENVELOPE

  LAYER 1 · ROLE ENVELOPE  (standing)
      Authored ONCE by a supervising role, for its DIRECT reports.
      Applies to every task that role's delegate ever performs.
      api:POST /api/v1/role-envelopes   →   defining_role_id + target_role_id
              │
              │  narrowed, optionally, per task
              ▼
  LAYER 2 · TASK ENVELOPE  (ephemeral)
      Narrows layer 1 for ONE task. Cannot widen it.
      Exists for the duration of the work and then does not.
              │
              │  intersected with EVERY ancestor's envelope
              ▼
  LAYER 3 · EFFECTIVE ENVELOPE  (computed, never authored)
      The intersection of all ancestor envelopes from the organisation
      root down to this invocation, plus layers 1 and 2.
      api:GET /api/v1/constraints/agents/{id}/effective

      THIS is what the engine consults. Neither of the two above is.
```

Read it as: you author layers 1 and 2; the platform computes layer 3; the
decision consults only layer 3. The consequence people trip on is that an
envelope can be perfectly correct at layer 1 and produce a bound at layer 3 that
looks nothing like it, because an ancestor three levels up is tighter.

Three read surfaces separate the layers, and using the right one is most of the
debugging:

| you want to know          | read                                                | what it answers                  |
| ------------------------- | --------------------------------------------------- | -------------------------------- |
| what I authored           | `api:GET /api/v1/role-envelopes/{id}`               | one envelope, as written         |
| what came down from above | `api:GET /api/v1/constraints/agents/{id}/inherited` | the ancestors' contribution      |
| what actually binds       | `api:GET /api/v1/constraints/agents/{id}/effective` | the composition — trust this one |

```python
effective = await client.governance.get_agent_constraints(
    agent_id=agent_id,
    resolution="effective",
)
inherited = await client.governance.get_agent_constraints(
    agent_id=agent_id,
    resolution="inherited",
)
```

**The failure mode to design against:** a supervisor tightens their own envelope
to respond to an incident, and every delegate beneath them tightens immediately
and without any of their envelopes being touched. That is the model working
exactly as intended, and it is a genuinely useful lever. It is also a surprise
if you did not expect it, and the symptom is a fleet of agents that begin
refusing actions they performed yesterday, with no change to any of their own
objects. Before concluding that a delegate's envelope is broken, read its
inherited layer.

## Monotonic tightening — the property everything rests on

The composition rule has one sentence: **a child envelope must be tighter than
or equal to its parent, on every dimension, and the platform refuses a write
that is not.** Composition is an intersection, never a union.

```python
proposed = await client.governance.validate_agent_constraints(
    agent_id=agent_id,
    constraints={"financial": {"max_amount": 250000, "currency": "USD"}},
)
```

`api:POST /api/v1/constraints/agents/{id}/validate` checks a proposed change
against the composition before you make it — which is the call to reach for
whenever a bound change is going to be applied programmatically, because the
refusal it gives you is cheap and the refusal the write gives you arrives after
a partially-provisioned organisation exists.

Two consequences shape every design built on this:

**You cannot build an escalation path by adding an envelope.** Widening is not
expressible in the model. If a delegate genuinely needs to exceed its bounds, the
answer is a human decision ([09.4](04-the-decision-gradient.md)) or a
time-bounded emergency widening authored by someone whose own envelope is wide
enough to contain it — never a second envelope. Attempts to express escalation
as an envelope produce one of two symptoms: the write is refused, which is the
good case, or the envelope is written at a level nobody consults, which is the
bad one.

**A bound is only as wide as the narrowest ancestor.** This is obvious stated
directly and consistently surprising in practice, because organisational
hierarchies are deep and people reason about the two roles either side of a
delegation rather than the whole chain. `api:POST /api/v1/governance/explain-envelope`
exists for exactly this: it returns the composition as a trace, so you can see
which ancestor supplied each binding term.

> ⛔ **A missing ancestor envelope is a DENY, not a skip.** When the composition
> walks the reporting chain and finds a role with no envelope, it does not
> continue to the next ancestor — it fails closed. A gap in the chain means
> governance is undefined at that level, and undefined is not permissive here.
> The symptom is an agent that refuses everything with a constraint reason,
> several levels below the role whose envelope was never authored, and the
> remedy is to author the missing one rather than to widen the delegate.

`api:GET /api/v1/governance/probe-corrupted-roles` is the sweep for this class —
roles whose envelope state cannot be resolved — and it is worth running after
any bulk organisational change.

## `draft` does not enforce, and that is the most expensive thing in this chapter

An envelope is created in one of two states, and `create` defaults to `draft`.

```python
envelope = await client.role_envelopes.create(
    defining_role_id=head_role_id,
    target_role_id=analyst_role_id,
    constraint_config={
        "financial": {"max_amount": 100_000, "currency": "USD"},
        "operational": {"blocked_actions": ["wire_transfer_external"]},
        "communication": {"internal_only": True},
    },
    status="draft",
)
await client.org_standup.activate_role_envelope(envelope["id"])
```

`api:POST /api/v1/role-envelopes` creates it;
`api:POST /api/v1/role-envelopes/{id}/activate` puts it in force;
`api:POST /api/v1/role-envelopes/{id}/suspend` takes it back out. A `draft`
envelope is a description of an intention. It appears in
`api:GET /api/v1/role-envelopes`, it reads correctly to every human who looks at
it, and it changes no decision.

**This is the failure mode to design against, stated plainly:** a provisioning
script that creates envelopes and never activates them produces an organisation
that looks fully bounded in every listing and enforces nothing. Nothing errors.
There is no warning. The only thing that distinguishes the two states is the
`status` field, so assert on it as part of provisioning rather than as part of
review:

```python
envelopes = await client.org_standup.list_role_envelopes()
for e in envelopes.records:
    assert e.status == "active", f"envelope {e.id} is {e.status}, not enforcing"
```

Pass `status="active"` at creation when the envelope is fully specified. Use
`draft` deliberately, when a human is going to review it before it binds — not
by accident, and never as the default in automation.

Two further fields on the envelope are worth knowing before you author one.
`clearance_ceiling` caps how far the target role's clearance can carry _inside
this delegation_, which is the one place the two axes of this part meet.
`verification_defaults` sets how thoroughly the delegate's actions are checked,
which is the envelope's handle on the gradient in
[09.4](04-the-decision-gradient.md).

## Defaults, ceilings and the organisation root

Not every bound is authored per-role. Three surfaces set bounds that apply
before any role envelope is consulted.

| surface                              | scope                                   | read                                                      | write                                                     |
| ------------------------------------ | --------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------- |
| **organisation constraint defaults** | every agent in the tenant               | `api:GET /api/v1/constraints/organizations/{id}/defaults` | `api:PUT /api/v1/constraints/organizations/{id}/defaults` |
| **envelope defaults**                | the template a new envelope starts from | `api:GET /api/v1/envelopes/defaults`                      | —                                                         |
| **unit posture ceiling**             | every agent under a unit                | `api:GET /api/v1/organization-units/{id}/posture-ceiling` | `api:PUT /api/v1/organization-units/{id}/posture-ceiling` |

The posture ceiling is the one that behaves differently from the others and the
one worth understanding here even though postures are
[09.5](05-trust-chains-and-postures.md)'s subject. It cascades the same way
envelopes do — a child unit cannot set a higher ceiling than its parent — and it
caps how autonomous _any_ agent beneath that unit may become, regardless of what
that agent has individually earned. It is the organisational brake, and it is
the correct lever when the answer to "how much autonomy should this department
have" is different from "how much has this particular agent earned".

Per-agent bounds are read back at `api:GET /api/v1/trust/agents/{id}/constraints`
and written at `api:PUT /api/v1/constraints/agents/{id}`. For a tool agent
specifically, `api:GET /api/v1/tool-agents/{id}/envelope-summary` is the compact
projection — which dimensions are bounded, and how tightly — and is the one to
put on a dashboard.

## Tightening in an incident

Envelopes are also the incident control, and this is where the temporal
dimension earns its place. `api:POST /api/v1/interventions/{id}/tighten-constraints`
narrows a running session's bounds without stopping it, which is frequently what
you want: the agent keeps working on the part of the task that is still in
scope, and the part that is not begins refusing.

```python
await client.interventions.tighten_constraints(
    intervention_id=session_id,
    constraints={"financial": {"max_amount": 0, "currency": "USD"}},
)
```

The sibling controls are `api:POST /api/v1/interventions/{id}/pause`,
`api:POST /api/v1/interventions/{id}/resume` and
`api:POST /api/v1/interventions/{id}/fence`, with the history at
`api:GET /api/v1/interventions/{id}/history`. Choose between them by blast
radius: tightening is surgical and leaves the work running, pausing stops one
session, and the kill switch ([09.4](04-the-decision-gradient.md)) stops a class
of work across the tenant.

> ⚠ **Tightening an ancestor is not the same instrument as tightening a
> session.** The first is permanent until undone and propagates to every
> descendant; the second is scoped to one run. In an incident the temptation is
> to reach for the ancestor because it is broader, and the cost lands afterwards
> — the incident ends, the session ends with it, and the ancestor's tightening
> stays in force silently bounding work nobody connected to the incident. If you
> tighten an ancestor, author the restoration in the same change.

## A composition, worked

Four roles on one reporting chain, each with an active envelope, and one
delegate at the bottom. This is the whole algebra in one example, and the answer
is not the one most people predict.

```text
COMPOSING FOUR ENVELOPES DOWN ONE CHAIN

  role                      financial.max_amount    operational.blocked_actions
  ───────────────────────────────────────────────────────────────────────────
  CEO            (D1-R1)          10,000,000        []
  CFO            (…-D1-R1)         2,000,000        ["equity_issuance"]
  Treasury lead  (…-T1-R1)           500,000        ["wire_transfer_external"]
  Analyst        (…-T1-R2)           750,000        []
  ───────────────────────────────────────────────────────────────────────────
  EFFECTIVE for the analyst          500,000        ["equity_issuance",
                                                     "wire_transfer_external"]

  FINANCIAL   is an intersection of RANGES → the LOWEST ceiling wins.
              The analyst's own 750,000 is IGNORED: it is wider than the
              treasury lead's 500,000, and a delegate cannot exceed its
              supervisor. The write that authored it was accepted because
              750,000 is below the CFO's 2,000,000 — the refusal only fires
              when a value exceeds the IMMEDIATE parent.

  OPERATIONAL is an intersection of PERMITTED SETS → blocks ACCUMULATE.
              Every ancestor's block survives all the way down. The analyst
              cannot issue equity, and nobody in the chain below the CFO can
              make that possible again.
```

Read it as: **the two dimensions compose in the same direction and it does not
look the same.** A financial ceiling gets lower; a block list gets longer. Both
are the intersection. The confusion is that one reads as a number shrinking and
the other as a list growing, and an operator who has internalised "tightening
means the number goes down" will look at a lengthening block list and read it as
a widening.

Two things fall out of the worked example directly.

**A locally-valid envelope can be entirely inert.** The analyst's 750,000 was a
legal write and contributes nothing to any decision. It will appear correct in
`api:GET /api/v1/role-envelopes/{id}` forever. The only surface that reveals it
is the effective composition, which is why that read is the one to trust when
debugging.

**Removing a bound in the middle of a chain does not restore anything below
it.** Lifting the treasury lead's 500,000 does not give the analyst 750,000 — it
gives them 2,000,000, the CFO's ceiling, because the analyst's own envelope was
never the binding term. Widening a chain is not a local operation, and the safe
procedure is to read the effective composition before and after rather than to
predict it.

## Is the layer enforcing anything at all?

Two reads answer the question an auditor will ask about envelopes as a class,
rather than about any one of them, and both belong on a schedule.

`api:GET /api/v1/governance/envelope-coverage` answers not _"do envelopes
exist"_ but _"would they stop anything"_. It is honest in the way that makes it
usable: an envelope that resolves to allow-all is counted in its own bucket
rather than as coverage, and the report carries a completeness flag. Read the
completeness flag first — when the measurement did not fully complete, the
counts are a floor rather than a total, and quoting a floor as a total is how a
coverage number ends up in a compliance document and stays there.

```python
coverage = await client.governance.get_envelope_coverage()
hydration = await client.governance.get_envelope_hydration_status()
```

`api:GET /api/v1/governance/envelope-hydration-status` is the layer beneath it.
Hydration is the pass that materialises an envelope into the form the engine
consults, and the envelopes a pass **skipped** are surfaced rather than silently
dropped. A skipped envelope means the engine fell back to a restrictive bootstrap
default — fail-closed, so not a hole, but also not what you authored, and
invisible everywhere else.

**The failure mode these two exist to catch:** an organisation where every role
has an envelope, every envelope is `active`, and the coverage report shows most
of them resolving to allow-all because the constraint configuration was
generated from a template nobody filled in. Every listing is green. Nothing
refuses anything. The coverage bucket is the only surface that distinguishes it
from a correctly bounded organisation.

## Reading an envelope in the console

> **In the console:** envelopes appear under the governance area, on the role
> they bound rather than on the role that authored them — which is the reverse
> of how you create them. The `status` chip is the field to look at first; a
> `draft` envelope renders identically to an active one apart from that chip.
> The effective composition is shown on the agent rather than on the role,
> because composition is a property of the invocation and roles do not invoke.

## Summary

| you need                            | the object            | the call                                                  |
| ----------------------------------- | --------------------- | --------------------------------------------------------- |
| bound a delegate's actions          | role envelope         | `api:POST /api/v1/role-envelopes`                         |
| put that bound in force             | activation            | `api:POST /api/v1/role-envelopes/{id}/activate`           |
| see what actually binds an agent    | effective envelope    | `api:GET /api/v1/constraints/agents/{id}/effective`       |
| see what came from above            | inherited constraints | `api:GET /api/v1/constraints/agents/{id}/inherited`       |
| test a change before making it      | validation            | `api:POST /api/v1/constraints/agents/{id}/validate`       |
| understand a composition            | envelope trace        | `api:POST /api/v1/governance/explain-envelope`            |
| bound a whole department's autonomy | unit posture ceiling  | `api:PUT /api/v1/organization-units/{id}/posture-ceiling` |
| narrow a live session               | intervention          | `api:POST /api/v1/interventions/{id}/tighten-constraints` |
| know whether the layer enforces     | coverage              | `api:GET /api/v1/governance/envelope-coverage`            |

---

_Next: [09.3 — Clearance and classification](03-clearance-and-classification.md)_
