---
name: govern
description: "Do governance work against a live deployment — read what actually bounds an agent, establish which control refused, move or withdraw standing safely, and produce the evidence an auditor will accept."
stage: 09-the-governance-architecture
---

<!-- anchor-floor: exempt (procedure; routes to handbook chapters and skills by name) -->

You are about to read, change or evidence a governance control on a running
deployment. **Almost everything here reports, and the few things that enforce are
the few that are hard to undo.** Load the **reading-trust-and-governance** skill
for the surface in full; this is the order to work it in.

## Step 0 — Decide which of four things you are doing

| you are        | the question                      | the risk if you skip step 0                  |
| -------------- | --------------------------------- | -------------------------------------------- |
| **reading**    | what bounds this agent right now? | you quote an input as the composition        |
| **explaining** | which control would refuse this?  | you widen the wrong one                      |
| **changing**   | move standing, up or down         | upward needs approval; downward is immediate |
| **evidencing** | what will an auditor accept?      | you hand over the wrong log                  |

Different calls, opposite blast radii. Name yours before you type anything.

## Step 1 — Reading a bound: trust the composition, never an input

```python
effective = await client.governance.get_agent_constraints(
    agent_id=agent_id,
    resolution="effective",
)
```

A delegate's actual bound is the **intersection of every ancestor's envelope**
from the organisation root down, so an envelope you authored is an _input_ — a
locally-valid one can be inert because an ancestor three levels up is tighter.
`resolution="inherited"` shows what came down; only `"effective"` decides.

Two states look identical in a listing and change nothing: an envelope in
**`draft`**, and a clearance in **`vetting_status="pending"`** (the role reads at
`public`). Both present as an empty screen rather than an error, so assert on the
state field in provisioning, not at review. Handbook chapters **Envelopes and
constraints** and **Clearance and classification**.

## Step 2 — Explaining a refusal: a dry run, read one field

```python
trace = await client.governance_explain.explain_access(
    agent_id=agent_id,
    knowledge_item_id=item_id,
)
```

⛔ **This is a DIAGNOSTIC YOU RUN, never a lookup of what happened.** It
evaluates a role against the item you describe: nothing is accessed, nothing is
recorded, and a wrong or missing field changes the verdict. It answers _what
would the model decide_ — not _why was my request refused_. For that, step 4.

**Read `step_reached`, not `allowed`.** `allowed` restates an outcome you already
observed; the step name is the phase the evaluation stopped at, and the only
field that narrows a refusal to one control. A read denial has three independent
causes — clearance, classification, containment — presenting identically. Check
them in that order; a pending clearance is the commonest and cheapest to confirm.

If the refusal might be about your credential rather than the agent's bounds, run
`/diagnose` first — both are `403`, and no governance change fixes that one.

## Step 3 — Changing standing: one call, two outcomes, one irreversible path

Both a governed progression and an administrative override go through the same
call, which decides internally whether the change applies or is held.

```python
pending = await client.trust_posture.get_pending(agent_id=agent_id)
if pending is None:
    result = await client.trust_posture.update(
        agent_id=agent_id,
        posture="continuous_insight",
        reason="<the evidence, stated for someone reading this in a year>",
    )
```

Branch on `approval_pending`. When it is `True` the agent is **still running at
the old posture** and the result reports the old value — reporting it as the new
one is the common integration defect, and re-issuing to "make it take" files a
second request the server then refuses. **Downward always applies immediately**,
which makes a downward override the correct reversible brake.

⛔ **Revocation is permanent, and there is no non-cascading revoke.** Every
revocation route cascades: revoking one agent revokes everything that derived
authority from it. There is also **no operation that suspends a chain** — methods
that look like one always raise.

```python
impact = await client.trust.revocation.get_impact(agent_id=agent_id)   # ALWAYS first
```

The impact preview is the difference between removing one agent and silently
removing a department's, and it costs one call. Then choose deliberately:

| you mean                            | use                                                   |
| ----------------------------------- | ----------------------------------------------------- |
| stop it, reversibly                 | a **downward posture override** — immediate, liftable |
| remove ONE delegation edge          | `revoke-delegation` — the only narrow removal         |
| remove an agent and its descendants | cascade revocation — **not undoable**                 |
| remove everything from one person   | the by-human route, when someone leaves               |

⚠ **A cascade can fail to complete, and that is a discoverable state.** List
incomplete revocation jobs on a schedule and read the two counts — completed
against total — rather than the status string. A revocation you believe landed
and which did not is the most expensive failure here: the agent is gone from
every dashboard and still holds standing. Handbook chapter **Trust chains and
postures**.

## Step 4 — Evidencing it

| the question              | the surface                                             |
| ------------------------- | ------------------------------------------------------- |
| what bounded this agent?  | the effective envelope, plus its inherited layer        |
| who decided it could act? | the trust-audit **lineage trace** to a named human      |
| what was recorded?        | both logs — platform _and_ trust — scoped to the window |
| is the record intact?     | the audit hash-chain verification, with its entry count |

**There are two logs and they answer different questions.** The platform log
answers _who changed this_; the trust log answers _why was this agent allowed_.
Neither contains the other's rows, so a request answered from the wrong one reads
as "the decision was never recorded". The lineage trace joins them.

Three readings the chapter states precisely and you must not round off — the
chain-integrity flag before its first sweep, an export with no stated range, and
what `verified` means on a trace. Handbook chapter **The audit spine and
evidence**; guardrail **reading-a-measurement**.

## Before you report

- [ ] every bound quoted is the **effective** composition, not an input
- [ ] every "in force" claim checked a state field, not the object's existence
- [ ] any refusal is attributed to one named control, or reported unattributed
- [ ] nothing destructive ran without its impact preview
- [ ] every number names what it counted and when

⛔ **The deploying organisation keeps accountability for what its agents do; this
surface gives you the proof.** State what you established and what you did not —
an inferred control reported as an observed one is worse than a gap, because
somebody will rely on it.

## Next

- `/diagnose` — if the refusal may be about the credential rather than the bound
- `/construct` — if the structure itself needs changing
- `/extend` — if a tool or agent needs a bound it does not yet have

**Skills:** `reading-trust-and-governance` (the surface in full), `day-two-operations`.
