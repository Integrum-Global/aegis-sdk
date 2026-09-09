---
name: construct
description: "Build and run the governed organisation — describe it, bound it, wire trust through it, put work into it, and pull the evidence back out, in the one order that works."
stage: 02-working-through-the-harness
---

This is the architect's unit of work: **a deployment construction**. Not a code
change — an organisation that exists on somebody's live platform when you are
done, and that somebody else has to be able to rebuild, review and promote.

Build it in code. An organisation built by clicking is an organisation nobody
can rebuild.

**Precondition:** `/orient` has run in this session and you are holding a named
deployment, a named credential type, and a probe verdict of `0`. If you are not,
stop and run it — every step below mutates a live deployment.

## The order, and why it is not negotiable

Each step constrains the next, and the constraint direction is not obvious from
any single call. Doing them out of order produces an organisation that has to be
torn down rather than corrected.

```
organisation          the tenant root
  └── unit            a knowledge boundary, with a default classification
       ├── role       reports to another role; this is the reporting chain
       │    └── envelope   what this role's delegate may do
       │         └── agent          the delegate itself
       │              └── trust chain   where its authority came from
       │                   └── posture  how much of it may be used unsupervised
       └── knowledge   governing documents, classified, with a review lifecycle
```

## 1 — Describe it

Handbook chapter **Standing up an organisation**. Provision the tenant, then
units, then roles and teams — in that order, because a role has nowhere to live
until its unit exists.

Before the first mutating call, say which deployment it lands on. A guard
refuses it otherwise, and on a client's production tenant that refusal is the
feature.

## 2 — Bound it

Handbook chapter **Envelopes, clearance and knowledge**. An envelope is what a
role's delegate *may do*; clearance is what it *may see*. They are independent,
and conflating them is the second-most-expensive mistake on this platform.

Write the envelope before the agent exists. An agent created ahead of its bound
is an agent that was, briefly, unbounded.

## 3 — Wire trust through it

Handbook chapter **Trust chains and postures**. The chain records where an
agent's authority came from; the posture records how much of it may be exercised
without a human. An agent can hold a high posture and a narrow envelope — those
are not in conflict, and reading one as the other is how a summary becomes wrong.

Load the **reading-trust-and-governance** skill before you summarise any of this
for someone else. Almost everything on this surface **reports**; almost nothing
**enforces**, and the two share vocabulary.

## 4 — Put work into it

Handbook chapter **Objectives and the work loop**. Load the
**running-an-objective** skill — it carries the loop and the four places a
careful person still gets it wrong.

**Acceptance is not execution, and execution is not completion.** An objective
can be admitted, clarified, decomposed, paused, held for a human, resumed, and
still not be done. Every one of those is a normal state. Do not report a
successful submit as "running", and do not report an absence of errors as
"finished".

Note that two surfaces address objectives and they are not the same one. The
skill says which is which; guessing costs a rebuild.

## 5 — Pull the evidence back out

Handbook chapter **Approvals, holds and evidence**. Aegis stops and asks
questions; that is the product working. Answer them where they are attributable
to a named human — not from a provisioning key.

Then export the record. The construction is not finished when it runs; it is
finished when someone else can show an auditor how it was governed.

⛔ **Numbers off these surfaces are read carelessly more often than they are
wrong.** Three states render as zero here, and two of them are not "none".
Branch on the null before you branch on the flag, and load the
**reading-a-measurement** guardrail before any figure reaches a human.

## Before you call it done

- [ ] every unit has a default classification you chose, not one you inherited
- [ ] every role's envelope exists and was written before its agent
- [ ] every agent's posture is one you can justify to the person accountable
- [ ] the work loop was observed to a terminal state, not to a successful submit
- [ ] the evidence export was actually run, and read
- [ ] anything you could not verify is written down as unverified

That last line is the one that makes the rest worth anything. You cannot read
the platform's implementation from here, so some of what you would like to
assert is not available to you. Say which parts, and say what would settle them.

## Next

- `/extend` — the organisation needs a capability it does not have
- `/diagnose` — a call in this construction was refused

**Skills:** `working-against-a-deployment` (order of operations),
`running-an-objective` (the work loop), `reading-trust-and-governance` (reading
the state without overstating it), `day-two-operations` (once it is running).
