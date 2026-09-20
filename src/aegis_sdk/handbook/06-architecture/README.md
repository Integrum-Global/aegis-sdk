# Part 06 — Architecture

**Audience: the lead engineer designing a system against Aegis.** Parts 02 to
05 answer *how do I do this*. This part answers *what is this* — the platform's
internals as you need them in order to design: the split between its Trust Plane
and its Execution Plane, the governance objects and how they relate, what a
request and a run actually pass through, where enforcement happens, and what
this SDK can and cannot reach.

It assumes you are past orientation and have made at least one real call. It
does not assume you have seen the platform's source, and it never asks you to:
every structural claim here is one you can settle from what you do hold. Where
that evidence runs out, the chapter says so rather than filling the gap.

## The chapters

| #    | Chapter                                                                | You leave able to                                                                              |
| ---- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
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

The practical test is the question you are asking. *"How do I establish a trust
chain?"* is part 02. *"Why does authority have to originate with a person at
all?"* is part 06, and the answer changes what you can design. *"Why did this
call come back refused?"* starts at part 04, which carries the error taxonomy;
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
were *nothing*. This is the one architectural claim that gets made wrongly most
often, because a route that resolves, a field that is accepted and a status that
appears in an enum all *look* like guarantees. They are not. Where a chapter
claims something is enforced, it rests on observed behaviour or it is labelled —
never on the mere existence of the surface.

## How this part knows what it knows

This part describes the platform's internals, and it is worth being precise
about how — because the source is not part of what you were given.

Architecture is normally read from the inside: open the tree, follow the call,
see which component ends up holding the state. None of that is available here.
What is available is the outside — the operations this client performs, the
symbols the package exports, the shapes calls return, and the behaviour you can
observe against a running deployment. Everything this part says about the plane
split, about the governance objects and their relationships, and about where
enforcement happens is written against that evidence and bounded by it. Where a
claim about the deployment's internals outruns what an outside read can reach —
and some do, because the split between the planes is a split of responsibility
and not an observable boundary — the chapter marks it as a reading rather than
asserting it in the same voice. Three things in particular do not come with it:

- **Which line enforces a rule.** You can establish the layering, and this part
  does. You cannot open it and read the check — and a rule that is declared and
  never consulted looks identical from outside to one that is enforced, because
  both are simply operations that exist.
- **Why a boundary falls where it does.** Some boundaries are load-bearing and
  some are historical. The behaviour is the same either way, so no amount of
  observation separates them. Where a chapter offers a reason, it is a reading.
- **Anything on a path with no surface.** A capability with no operation behind
  it is invisible from here — not absent, just unreachable, and the two are
  indistinguishable in what you can measure.

So the markers matter more in this part than anywhere else in the book. Where a
claim rests on observed behaviour it is stated as observation. Where it explains
intent it is marked _design intent, not observable_. Where it could not be
settled from what is reachable it says **UNVERIFIED**. And where the shipped
behaviour is wrong it says **open defect** and describes the symptom, because a
structural explanation of a system that does not match the running one is worse
than no explanation: it will be believed.

A chapter in this part that uses none of those markers should be read as
claiming more than an outside read can support.

---

_Next: [06.1 — What core and the SDK are](01-what-core-and-the-sdk-are.md)_
