# Part 08 — The capability catalogue

<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->

**Audience: the architect or evaluator who needs to know everything the platform
can do.** Parts 01 to 05 teach the working path — the sequence you follow to
stand an organisation up and run work through it. Part 06 is the architecture,
and part 07 is the deployment. None of them enumerates the surface. This part
does.

**What it is.** A complete, grouped inventory of the capabilities Aegis exposes:
what each one is for, which SDK module drives it, which operations it publishes,
and how the pieces relate. It is organised by capability area rather than by
module, because the question an architect arrives with is _"can it do X?"_ and
not _"what is in `modules/`?"_ — so the areas are named for the work, and the
module that serves each one is named inside it.

**What it is not.** A tutorial. Nothing here walks you through a first session or
explains why an envelope exists — parts 01 and 02 do that, and this part links to
them rather than repeating them. It is also not a substitute for
[04.1](../04-the-api-surface/01-calling-the-api.md) on how a call is made, or
[04.2](../04-the-api-surface/02-errors-and-refusals.md) on what a refusal means.
Read this part to find out **what exists**; read those to find out **how to call
it and what comes back**.

The surface is large. It is one client, one credential, and one base URL, and
every capability below is reachable through the same object you configured in
[01.3](../01-orientation/03-your-first-session.md).

## The chapters

| #    | Chapter                                                            | You leave able to                                                                                            |
| ---- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| 08.1 | [How to read this catalogue](01-how-to-read-this-catalogue.md)     | Navigate the taxonomy, map a capability to the module that serves it, and check reach on your own deployment |
| 08.2 | [Organisation and identity](02-organization-and-identity.md)       | Enumerate everything that models who the organisation is and who may act inside it                           |
| 08.3 | [Agents and execution](03-agents-and-execution.md)                 | Enumerate every kind of agent, how work reaches one, and every way one can be driven                         |
| 08.4 | [Work and objectives](04-work-and-objectives.md)                   | Enumerate the work-shaped objects — objectives, work units, requests, directives — and their lifecycles      |
| 08.5 | [Governance and trust](05-governance-and-trust.md)                 | Enumerate every control that bounds an agent, and every surface that explains or overrides one               |
| 08.6 | [Knowledge and data](06-knowledge-and-data.md)                     | Enumerate what the organisation knows, how it is classified and reviewed, and where it came from             |
| 08.7 | [Evidence and operations](07-evidence-and-operations.md)           | Enumerate what the platform records about itself and how you get it out                                      |
| 08.8 | [Commercial and extensibility](08-commercial-and-extensibility.md) | Enumerate the metering, licensing, and third-party-integration surfaces                                      |

## How the seven catalogue chapters relate

They are not seven topics chosen for convenience. They are the platform's own
layering, read from the bottom up — each chapter's subject is the thing the next
one acts on.

```
┌─ the stack, bottom to top ────────────────────────────────────────────────────
│
│  08.2  Organisation and identity        WHO exists, and who may act
│   │
│   ├─► 08.3  Agents and execution        WHAT acts, and how it is driven
│   │    │
│   │    └─► 08.4  Work and objectives    WHAT is asked of it, and how that resolves
│   │
│   ├─► 08.5  Governance and trust        WHAT bounds every one of the above
│   │
│   └─► 08.6  Knowledge and data          WHAT it may know, and where that came from
│
│  08.7  Evidence and operations          WHAT was recorded about all of it
│  08.8  Commercial and extensibility     WHAT it costs, and what attaches from outside
│
└───────────────────────────────────────────────────────────────────────────────
```

Read it as: 08.2 is the foundation, because a role is what a trust chain anchors
to and a unit is what an envelope scopes. 08.3 and 08.6 both hang off it — an
agent is linked to a role, and knowledge is classified against the clearance a
role holds. 08.4 sits on 08.3 because an objective decomposes into work that an
agent executes. **08.5 cuts across all of them**, which is why it is drawn to the
side rather than in the chain: an envelope bounds a role, an agent, a session and
a bridge alike. 08.7 and 08.8 are orthogonal — the first observes the whole stack,
the second surrounds it.

The practical consequence for reading order: if you are checking Aegis against a
requirements list, read 08.2 and 08.5 first. Most requirements that look like
they are about agents turn out to be about the bounds on agents, and those are in
08.5.

## Where this part sits relative to the others

Part 02 is the working reference — it shows you the sequence. Part 03 is how you
add a capability the platform does not ship. Part 04 is the call mechanics. Part
06 is the architecture, and part 07 is the deployment.

This part is the **index of what exists**. It deliberately says less about each
capability than the part that owns it, and more about the set as a whole. Where a
chapter here names something part 02 teaches, it links there rather than
re-explaining it.

The practical test is the question you are asking. _"How do I establish a trust
chain?"_ is [02.4](../02-working-through-the-harness/04-trust-chains-and-postures.md) —
it is a procedure. _"What does this error mean?"_ is
[04.2](../04-the-api-surface/02-errors-and-refusals.md) — it is call mechanics.
_"Does Aegis support cascade revocation, retention policies, and per-unit posture
ceilings?"_ is this part — it is an inventory question, and it is the one a
procurement review, a security questionnaire, or a build-versus-buy decision
actually asks.

## The shape of every capability entry

Every area in 08.2 through 08.8 is presented the same way, so you can scan for
the one you need rather than reading through:

1. **A paragraph** saying what the capability is for and what it is not.
2. **A capability table** — one row per distinct thing it can do.
3. **The SDK entry point**, as a resolvable symbol.
4. **The operations**, as resolvable routes.
5. **A short example** in the house style, so the call shape is concrete.

Where a capability has a lifecycle — a thing that is created, moved through
states, and retired — the states are given as a table rather than as prose,
because a state you did not know existed is the one that will surprise you in
production.

---

_Next: [08.1 — How to read this catalogue](01-how-to-read-this-catalogue.md)_
