---
name: running-an-objective
description: Submit an objective, track it through clarification and execution, read the task graph, act on a hold, and confirm completion — without mistaking acceptance for progress.
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/skills/running-an-objective.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


# Running an objective end to end

The handbook chapters *Submitting an objective*, *Your inbox* and *When something
is held* are the prose. This is the loop, and the four places a careful person
still gets it wrong.

## The one thing to internalise first

**Acceptance is not execution, and execution is not completion.** An objective
can be admitted, clarified, decomposed, paused, held for a human, resumed, and
still not be done. Every one of those is a normal state. A caller that treats a
successful submit as "running" and an absence of errors as "finished" will report
success for work that is sitting in someone's queue.

## Step 0 — Know that TWO modules address objectives, and they are not the same

```
client.objectives        submit · get · get_progress · get_artifacts · decide ·
                         confirm_implementation · cancel · get_requests
client.work_objectives   clarify · get_task_graph · stream_progress · decide ·
                         work units · directives · sessions · escalations
```

They overlap (`decide`, `get_progress`, `confirm_implementation` appear on both)
and they are **not interchangeable** — each wraps its own set of routes. Confirm
which one your build exposes for a given verb rather than assuming:

```bash
python -c "import aegis_sdk.execution.objectives as m; \
print([n for n in dir(m.ObjectivesModule) if not n.startswith('_')])"
```

**Why this is step zero:** reaching for the wrong module surfaces as an
`AttributeError`, which reads like a missing capability and is not one.

## Step 1 — Submit, then immediately stop trusting the response

The submit response tells you the objective was accepted. Poll the objective
itself for everything else.

```python
obj = await client.objectives.submit(...)
await client.objectives.get_progress(obj.id)
```

The roster is `api:GET /api/v1/objectives`; one objective is
`api:GET /api/v1/objectives/{id}`.

## Step 2 — Expect clarification, and treat it as part of the loop

```python
await client.work_objectives.clarify(objective_id, ...)
```

An objective waiting on clarification is **not** stalled and **not** failed. It
is the platform declining to guess, which is the behaviour you want. Answer it
and the loop continues.

## Step 3 — Read the task graph before you conclude anything about progress

```python
await client.work_objectives.get_task_graph(objective_id)
```

⚠ **An empty graph is ambiguous and is the trap on this surface.** It reads
identically for "decomposition has not run yet", "decomposition produced
nothing", and "your credential cannot see the nodes". Establish which before
reporting; a graph that has never been non-empty has not been shown capable of
being non-empty.

## Step 4 — Streaming, and what a silent stream means

```python
async for event in client.work_objectives.stream_progress(objective_id):
    ...
```

A stream that yields nothing is not evidence that nothing is happening. It is
consistent with a completed objective, a held one, a connection that dropped, and
a credential that cannot read the feed. **Poll the objective's state to settle
it** — never infer state from stream silence.

## Step 5 — A hold is a decision, not an error

When an objective or a request is held, the path forward is the decision surface:

```python
await client.objectives.decide(objective_id, ...)
await client.approvals.list_pending(...)
await client.approvals.approve(request_id, ...)     # or .reject(...) / .modify(...)
```

```
# DO      route it to whoever holds the authority, with what they need to decide
# DO NOT  widen your credential, retry, or re-submit to get past it
```

**Why:** the hold is the product working. Re-submitting produces a second
objective in the same state and a confused audit trail; widening a credential
does not address a governance decision and, on a persona-gated path, changes
nothing at all.

**The approver identity is derived from the authenticated session and pinned when
the record is created.** A body field naming an approver is not how approval
works here, and that is deliberate — do not build a flow that depends on it.

## Step 6 — Completion, and the difference between the two questions

```python
await client.objectives.get(objective_id)                    # what state is it in?
await client.objectives.get_artifacts(objective_id)          # what did it produce?
await client.objectives.confirm_implementation(objective_id) # your assertion
```

"Is it complete?" and "has completion been confirmed?" are different questions
with different answers and different consequences. Confirming implementation is
an assertion **you** are making, recorded against your identity. Make it because
you opened the artifacts, not because the status looked right.

⚠ `get_artifacts` returns **bytes**, not a parsed object. An empty byte string is
not an error and not proof of an empty result — apply the same three-worlds test
as any other empty reading before concluding the objective produced nothing.

## Step 7 — Reporting

State the objective id, its actual state, the credential you read it with, and
what you verified rather than inferred.

```
# DO      "objective <id>: completed, 4 artifacts present and opened, confirmed
#          by me at 14:02 UTC with a session token"
# DO NOT  "objective done"
```

## Where the console is the better answer

Reading a rich task graph, comparing artifacts side by side, and working a long
approval queue are genuinely better in the console. The harness is the default
because it is scriptable, reproducible and leaves a receipt — not because the console
is wrong. **Use the console to look; use the harness to act and to record.** If you
find yourself reconstructing a visualisation in a terminal, that is the signal to
switch surfaces, not to keep going.

## What this skill does not cover

What makes a *good* objective. That is a question about your domain, and the
handbook's chapter on submitting one is written for it.
