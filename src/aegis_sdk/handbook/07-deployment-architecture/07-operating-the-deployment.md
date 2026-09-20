# 07.7 — Operating the deployment

This chapter is about what happens after the design is settled: changing the
thing, watching it, sizing it, and recovering it. It closes with a checklist you
can actually run through, and that checklist is the part to come back to.

## Change: rollout, health gate, rollback

A change to the platform is not a file copy. It is a **rollout**: new instances
of a service are started alongside the old ones, checked, and only then does
traffic move. If the check fails, traffic never moves and nothing is lost.

```
┌──────────────┐
│   RUNNING    │◀─────────────────┐
└──────┬───────┘                  │
       │  new digest pinned       │
       ▼                          │
┌──────────────┐                  │
│   STAGED     │                  │
└──────┬───────┘                  │
       ▼                          │
┌──────────────────────┐          │
│   VERIFYING          │─────────┘  health gate passes
│   serves no traffic  │
└──────┬───────────────┘
       │  health gate fails
       ▼
┌──────────────┐
│   REVERTING  │
└──────┬───────┘
       │  previous digest re-pinned
       └──────────────────────────▶ RUNNING
```

The states matter more than the arrows. **Verifying is a state in which the new
version exists and serves nothing** — that is what makes the gate meaningful, and
it is why a failed rollout is usually an absence of change rather than an
incident.

**Health gating** decides the transition: the new instances must demonstrate they
are working before they receive traffic. What counts as working is a per-service
definition, and _design intent, not observable_ applies to its details.

**Rollback ties directly back to [07.3](03-images-and-the-registry.md).** Because
the deployed reference is a **digest** rather than a tag, reverting is re-pinning
the previous digest — the exact bytes that ran before, still in the registry,
still verifiable. No rebuild, no reconstruction, no "approximately what ran
before". This is the operational payoff of the digest discipline, and it is the
reason that chapter insisted on it.

## Upgrades, and what you control

_Design intent, not observable:_ platform upgrades are **initiated by the
platform**, not by you. That follows from [07.1](01-what-a-deployment-is.md)'s
boundary — you administer inside the deployment, and the platform is operated for
you — and it is the reference shape's operating model rather than something you
can read from your own integration.

**What the platform decides:** what is upgraded, and that an upgrade is
available. **What is usually negotiable:** when it happens.

The reference expectation is that upgrades are scheduled into an agreed window
rather than applied at the platform's convenience — an upgrade is a change to
something you are integrating against, and applying one during your launch week
is a decision somebody should make deliberately.

**What a partner can reasonably ask for:**

- Advance notice of a change, and what it contains.
- A maintenance window that respects your own change freezes.
- A statement of whether the change is backward-compatible for the operations
  you use.
- A rollback position if something you depend on regresses — which
  [07.3](03-images-and-the-registry.md) makes a real possibility rather than a
  hope.

**Your own changes are separate.** If your deployment runs workloads you own,
those roll out on your schedule, through the same rollout and rollback machinery.
The distinction is worth holding: the platform upgrades itself, you upgrade what
you put on it.

_Design intent, not observable:_ the notice period, the window policy, and who
makes the call. These are contractual and operational rather than architectural,
and they vary. Ask.

## Observability: two kinds of record, and they are not interchangeable

A common and expensive mistake is assuming that because a system emits logs, its
audit evidence is in them. It is not, and the two differ on every axis that
matters.

|                    | Audit evidence                        | Operational telemetry                 |
| ------------------ | ------------------------------------- | ------------------------------------- |
| **Answers**        | Who did what, and was it permitted    | Is the system healthy, and is it fast |
| **Produced by**    | The governance layer, deliberately    | The runtime, as a by-product          |
| **Retention**      | Long, and set by policy               | Short, and set by cost                |
| **Access**         | Restricted, and itself auditable      | Broad — engineers read it daily       |
| **Completeness**   | Intended to be complete for its scope | Sampled, dropped, rotated             |
| **If you lose it** | You cannot evidence your governance   | You lose situational awareness        |

_Design intent, not observable:_ every row above. The split between the two
columns is the architecture's intent, and the retention, access and completeness
properties are how a deployment is built rather than something you can measure
from your integration. Read "long" and "restricted" as the shape to confirm with
your operator, not as figures you were given.

**Evidence is a product artifact; telemetry is an operational one.** The
governance record — approvals, holds, refusals, the decisions and who made them
— is the material an auditor is shown, retained for as long as an auditor may
ask for it. Telemetry is how the platform is run, and it is allowed to be
lossy in ways evidence is not.

**Check that your own retention obligations are met by the evidence store rather
than by a log pipeline.** If you have a requirement to retain a record of
governance decisions for a period, it is the first column that satisfies it, and
its retention is a policy you should confirm rather than a property you can
assume from the fact that you can see log lines.

**What you can check from outside:** whether the governance services are
responding at all. `api:GET /api/v1/trust/health` and
`api:GET /api/v1/compliance/health` are the operations this client declares for
that question — that they exist and that you can call them is verifiable from
your own machine, and what a healthy response actually reports is not. They are a
reasonable first call in any diagnostic sequence, because before you debug a
refusal it is worth knowing whether the service that would have made the decision
is up.

**Be precise about what a health check establishes, though, because it is easy to
over-read.** A healthy response means the service is responding. It does not mean
governance is configured the way you intended, that your envelopes are the ones
you think, or that any particular control is enforced. Those are different
questions with different instruments, and treating a green health check as
evidence for them is how a misconfiguration survives a monitoring system that
was watching the wrong thing.

## Capacity: what scales, and what does not

| Scales with demand           | Does not scale                                      |
| ---------------------------- | --------------------------------------------------- |
| Application service replicas | The relational database's write throughput          |
| Node pool size (autoscaling) | The vector extension's index build cost             |
| Cache capacity               | Retention requirements — evidence grows and is kept |
| Job execution concurrency    | Storage growth, which is monotonic                  |

_Design intent, not observable:_ the directions above — which way each limit
moves when it is reached — as well as the thresholds themselves. That storage
only grows, and that write throughput scales up rather than out, are design
properties of the reference shape rather than measurements you were handed.

**The row that catches people is storage.** Evidence and artifacts are retained
on purpose, so object storage grows and never shrinks. That is the intended
behaviour rather than a leak, and it means a capacity plan that assumes a steady
state will be wrong in the only direction that matters.

**Which limits are structural, and therefore worth designing around rather than
arguing with:**

- **Database write throughput** is bounded by the managed instance's size. It
  scales up, not out, and it does so on a change request rather than
  automatically.
- **Vector index maintenance** is the most expensive routine database operation,
  and it is the one most sensitive to corpus size. Adding knowledge is not free
  at the storage layer.
- **Connection counts** are bounded by the database, and every additional
  service replica consumes some. More replicas is not unconditionally more
  throughput, and past a point it is less.

_Design intent, not observable:_ the specific thresholds. The reference shape
says what scales and what does not; only your operator can say at what point each
one bites, and that is a better question to ask before a launch than after.

## Disaster recovery: objectives, not guarantees

Two numbers define a recovery posture, and both are **things an operator
chooses**, not properties a platform has:

- **Recovery point objective** — how much data loss is tolerable. "One hour" means
  a restore may lose the last hour of changes.
- **Recovery time objective** — how long recovery may take. "Four hours" means
  four hours of degraded or absent service is an accepted outcome.

They are targets bought with cost and complexity, so different deployments will
have chosen differently, and neither is more correct in the abstract.

**What to ask your operator — and these are the questions, not a preamble to
them:**

1. What are the recovery point and recovery time objectives for this deployment?
2. When was a restore last **performed** — not configured, performed — and what
   did it demonstrate?
3. Where does a restore land, and does it land somewhere you can validate before
   it replaces anything?
4. Who decides to invoke a recovery, and how are you told?

Question 2 is the one that matters. As [07.5](05-stateful-services.md) puts it, a
backup nobody has restored is a hypothesis, and a recovery objective that has
never been tested against is a number rather than a capability.

**UNVERIFIED — and this is the chapter's largest one:** every objective, policy
and threshold above, for any particular deployment. A reference architecture can
tell you what to ask and why it matters. It cannot tell you your operator's
answers, and no amount of reading this part substitutes for the conversation.

## Pre-production checklist

Run through this before you depend on a deployment. Each item is answerable, and
together they cover the gaps this part has flagged.

**From your side, at the API:**

- [ ] The base URL points at the deployment you intend, and `api:GET /api/v1/auth/me`
      names the principal you expect.
- [ ] `api:GET /api/v1/auth/me/organizations` lists the organisations you expect —
      and no others.
- [ ] `api:GET /api/v1/trust/health` and `api:GET /api/v1/compliance/health` both
      respond.
- [ ] Your credential's scope is what you think: attempt one operation you
      expect to be **refused**, and confirm it is. A permission model you have
      only tested in the permissive direction is untested.
- [ ] Your error handling treats a refusal as a first-class outcome rather than
      an unexpected failure — a governance product refuses things as normal
      operation.
- [ ] You can revoke the credential, and you know who to tell if it leaks.

**From your operator, before you commit:**

- [ ] The recovery point and recovery time objectives, and when a restore was
      last actually performed.
- [ ] The egress posture: allowlisted or default-allow, and whether the agent-to-provider
      path is recorded.
- [ ] The upgrade policy: notice period, window, and whether you can request a
      freeze.
- [ ] The retention policy for audit evidence, against your own obligations.
- [ ] The support path and escalation route, in writing.

**One item that is easy to skip and should not be:** confirm that the person
answering these questions is able to answer them. "I will find out" is a fine
answer. A confident answer about a deployment the respondent has not inspected
is not, and this part has marked a dozen claims as unverifiable-from-outside
precisely so you can tell the two apart.

---

_Next: [Part 08 — The capability catalogue](../08-the-capability-catalogue/README.md)_
