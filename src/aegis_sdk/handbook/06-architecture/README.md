# Part 06 — Architecture

**Audience: the lead engineer designing a system against Aegis.** Parts 02 to
05 answer _how do I do this_. This part answers _what is this_ — the platform's
internals as you need them in order to design: the split between its Trust Plane
and its Execution Plane, the governance objects and how they relate, what a
request and a run actually pass through, where enforcement happens, and what
this SDK can and cannot reach.

It assumes you are past orientation and have made at least one real call. It
does not assume you have seen the platform's source, and it never asks you to:
every structural claim here is one you can settle from what you do hold. Where
that evidence runs out, the chapter says so rather than filling the gap.

## The chapters

| #    | Chapter                                                                | You leave able to                                                                               |
| ---- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 06.1 | [What core and the SDK are](01-what-core-and-the-sdk-are.md)           | Say where the boundary is, and which half of the system a given responsibility belongs to       |
| 06.2 | [The request path](02-the-request-path.md)                             | Trace a call through the platform, and predict which layer will refuse it                       |
| 06.3 | [The governed organisation](03-the-governed-organization.md)           | Design the structure your agents live in, and know what each object constrains                  |
| 06.4 | [Trust and the audit spine](04-trust-and-the-audit-spine.md)           | Decide what will be provable later, and design for the decision the platform will actually make |
| 06.5 | [The execution model](05-the-execution-model.md)                       | Place work correctly in the run lifecycle, and design for the way a run ends                    |
| 06.6 | [Designing against the platform](06-designing-against-the-platform.md) | Choose where your integration attaches, and know what is guaranteed before you build on it      |

## The system the part describes

Two views of the same six chapters, and neither is redundant. This first one is
the system they describe. What is above the line is yours; what is below it
belongs to the deployment, and you reach it only through the calls you make.

```
aegis, from where you stand
│
├── what you hold ────────────────────────────────────────── 06.1
│     ├── the client — one object, pointed at one deployment
│     └── a credential, scoped to something
│
└── what the deployment holds
      │
      ├── the request path ────────────────────────────────── 06.2
      │     seven layers, from your module's call to the typed response
      │
      ├── the governance objects ──────────────────────────── 06.3
      │     organisation
      │       └── unit ── role ── envelope ── agent
      │                      └── trust chain ── posture
      │
      ├── the Trust Plane ─────────────────────────────────── 06.4
      │     whether an action is permitted, and the record it leaves
      │
      └── the Execution Plane ─────────────────────────────── 06.5
            work entering, running, carried, and stopped

06.6 ── where your integration attaches; it assumes all five above
```

## The three axes, and the two chapters that bracket them

The second view is how the six divide the system up. 06.1 frames the whole and
06.6 closes it; between them the part runs on three axes — the system at rest,
the system in motion, and the spine both of them pass through.

```
                             06.1 ── THE FRAME
                 which half you hold, and where the boundary sits
                                     │
               ┌─────────────────────┴────────────────┐
               │                                      │
               ▼                                      ▼
┌─ THE SYSTEM AT REST ────────┐   ┌─ THE SYSTEM IN MOTION ─────────────────┐
│                             │   │                                        │
│           06.3              │   │   06.2   one call, end to end          │
│   the governed organisation │   │   06.5   one run, over time            │
│   units · roles · envelopes │   │                                        │
│   · agents                  │   │   Both are sequences — one short,      │
│                             │   │   one long — and both pass through     │
│   what the other two act on │   │   the band below.                      │
└──────────────┬──────────────┘   └───────────────────┬────────────────────┘
               │                                      │
               └─────────────────────┬────────────────┘
                                     │
                                     ▼
┌─ 06.4 ── THE SPINE ──────────────────────────────────────────────────────┐
│   the decision a call and a run each reach, and the                      │
│   record it leaves — one mechanism, at two moments                       │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
                           06.6 ── THE ENDPOINT
                 where your integration attaches; it assumes all five
```

Three things follow from that shape, and each decides how you read the rest.

**06.1 frames everything else.** Every later chapter is a statement about one
side of the boundary it draws, and a statement read without the boundary is easy
to misplace — most expensively by concluding that something the platform owns is
yours to enforce, or the reverse.

**06.4 is a spine, not a topic.** Both the request path and the execution model
pass through it: a call reaches a decision, and a run reaches several. It sits
between them rather than under either, because the decision mechanism and what
it leaves behind — `sdk:aegis_sdk.TrustAuditEntry` is the shape of that record —
are one thing seen at two moments.

**Reading out of order is fine, with one exception.** Once 06.1 has landed,
06.2 through 06.5 can be taken in any order. 06.6 should not be: it is the only
chapter you are meant to act on directly, and it assumes the other five.

## Where this part sits relative to the others

Part 02 is the working reference: it tells you how to stand an organisation up
and run work through it. Part 06 does not repeat any of that. What it adds is
the system those steps operate on — the reason they come in that order, the
reason the shapes are those shapes, and the reason some of them cannot be
rearranged. That is what you need when no recipe covers your case.

The practical test is the question you are asking. _"How do I establish a trust
chain?"_ is part 02. _"Why does authority have to originate with a person at
all?"_ is part 06, and the answer changes what you can design. _"Why did this
call come back refused?"_ starts at part 04, which carries the error taxonomy;
06.2 explains what the call passed through on its way to the refusal, which is
what tells you whether the answer is to change the credential or to change the
design.

That third question is worth one concrete step. A refusal does not identify which
layer produced it, and the layers are not interchangeable — a credential problem
and a policy problem look alike from outside. So the useful first move is to
establish who you are: `api:GET /api/v1/auth/me` reports the principal you are
currently holding, as distinct from the one you assumed. Read 06.2 with that in
hand and the refusal stops being opaque.

If you can read only one chapter first, read 06.6 and let it send you backwards.
It is written to be usable that way.

## Two ideas this part keeps returning to

**Which half holds it.** You hold a client — one object,
`sdk:aegis_sdk.AgenticOSClient`, configured against a base URL you supply, since
the package ships no default endpoint — and a credential. The deployment holds
the state, the policy, the decision, and the record. Almost every structural
question in this part reduces to asking which side of that line a thing sits on.
The client's configuration surface, `sdk:aegis_sdk.ClientConfig`, is entirely
about the connection — which deployment, with which credential, under which
timeout and retry policy. None of it is about the organisation's content: that
is all asked for at the time, per call.

**Existing is not the same as enforced.** An operation this client declares is
an operation that exists in the surface you were given. It is not evidence that
anything is checked when you call it. The distinction sounds pedantic until you
apply it: this client declares `api:GET /api/v1/agents`, and that declaration
tells you the operation is part of the surface. It cannot tell you what the
server checked before answering, and it would read identically if the answer
were _nothing_. This is the one architectural claim that gets made wrongly most
often, because a route that resolves, a field that is accepted and a status that
appears in an enum all _look_ like guarantees. They are not. Where a chapter
claims something is enforced, it rests on observed behaviour or it is labelled —
never on the mere existence of the surface.

## What this part describes, and what sits outside it

This part describes the platform at its boundary: the operations the client
performs, the symbols the package exports, the shapes calls return, and how a
running deployment responds. That boundary is the architecture you design
against, and it is the one these chapters are written to.

Three things sit outside it, and each changes what you should build:

- **Which line enforces a rule.** You can establish the layering, and this part
  does. A rule that is declared and one that is enforced look the same from
  outside, because both are simply operations that exist — so treat "this route
  is declared" and "this route checks something" as two separate claims.
- **Why a boundary falls where it does.** Some boundaries are load-bearing and
  some are historical. The behaviour is the same either way, so design to the
  behaviour rather than to the reason for it.
- **Anything on a path with no surface.** A capability with no operation behind
  it is unreachable from here — not absent, just unreachable, and the two are
  indistinguishable from outside.

---

_Next: [06.1 — What core and the SDK are](01-what-core-and-the-sdk-are.md)_
