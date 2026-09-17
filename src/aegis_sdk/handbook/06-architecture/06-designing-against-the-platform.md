# 06.6 — Designing against the platform

This is the last chapter of part 06 and the only one you are meant to act on
directly. The first five describe a system. This one is where that description
turns into a decision about your integration.

Three questions, in the order they cost you money if you get them wrong:

1. **Where does my integration attach?** There are more surfaces than most
   people expect, and picking the wrong one is usually discovered late.
2. **What may I assume?** Some of what looks like a guarantee is a convention the
   client maintains for you.
3. **What will surprise me?** A short list of the failures that are expensive to
   find late, each with the symptom you will actually see.

If you read one chapter of this part before building, read this one and let it
send you backwards. It is written to be usable that way.

## Where your integration attaches

Start from what your code is *doing*, not from which module name looks likely.
The six intents below are mutually exclusive in practice, and each lands on a
surface with a different shape of guarantee — which is the point of drawing them
apart.

```
        What is your integration actually doing?
        │
        ├── putting work in             ─▶ Objective — decomposes into requests   02.5, 06.5
        │                                  Work unit — a versioned definition you execute,
        │                                  not a job   06.5
        ├── watching work run           ─▶ Progress stream — plan-step granularity, poll
        │                                  for state   06.5
        │                                  Session stream — what the agent is doing,
        │                                  different vocabulary   06.5
        │                                  Audit and reasoning traces — after the fact
        │                                  02.6, 04.5
        ├── being the human who answers ─▶ Six separate queues. Nothing aggregates
        │                                  them.   06.5, 02.6
        ├── adding a capability         ─▶ Skills, tools, pipelines, agents   part 03
        │                                  Tool agent — invoked through governance,
        │                                  not executed   06.5
        ├── changing the organisation   ─▶ Org, units, roles, envelopes   02.2, 02.3
        │                                  Change requests — approved is not
        │                                  applied   02.6
        └── taking output out           ─▶ Artifacts — clearance-checked, classified by
                                           the workspace, never by the caller   06.5
```

Every leaf in that diagram is expanded somewhere in this book, and each names
where. The two worth reading twice before you build anything: **the
human-decision surfaces are six queues with no aggregator**, and **the artifact's
classification is decided by the workspace you attach to, not by the argument you
pass**.

The client-side view of this map is `sdk:aegis_sdk.AgenticOSClient`: one object,
configured by `sdk:aegis_sdk.ClientConfig`, carrying every module as an
attribute. If you are orienting yourself in a REPL, that object is the index.

## What you can reach, and what you cannot

There is a hard line between the system's *state* and its *configuration*, and it
is not the same line as "what has a route". Your integration sits on one side of
it, and the most important properties in this book are on the other.

```
     you hold: a client · a credential · a base URL
──────────────────────────────────────────────────────────────────────────
  REACHABLE — anything behind an HTTP route your credential admits

   work        objectives · requests · work units · sessions
   output      artifacts · downloads · version history
   humans      decisions · approvals · escalations · pseudo requests
               inbox · change requests
   trust       chains · delegations · postures · revocation
   evidence    audit log · trust audit · compliance verify and export
   emergency   kill switch · emergency bypass
   structure   organisations · units · roles · envelopes · teams
   readiness   envelope coverage · hydration status · explain-access
──────────────────────────────────────────────────────────────────────────
                    the credential boundary
        refused, not invisible — you learn you were kept out,
        not that the surface is absent
──────────────────────────────────────────────────────────────────────────
  NOT REACHABLE — configuration, and the platform's own internals

   the deployment's posture
     which agent runtime is in force
     whether a pre-execution tool gate is attached
     whether outbound LLM content is classified
     the encryption and signing posture
     which environments are guarded

   the platform's internals
     which component refused you, and at which layer
     whether a control that exists is enforcing or merely present
     any capability with no route in front of it
──────────────────────────────────────────────────────────────────────────
```

Each reachable band above is a real surface, not a theme:
`sdk:aegis_sdk.modules.WorkObjectivesModule` for work,
`sdk:aegis_sdk.execution.ArtifactsModule` for output,
`sdk:aegis_sdk.ApprovalsModule` for the human queues,
`sdk:aegis_sdk.trust.ChainsModule` for authority,
`api:POST /api/v1/kill-switch/activate` for the emergency stop, and
`sdk:aegis_sdk.standup.OrganizationsModule` for the structure. Everything the
client carries about the deployment is in `sdk:aegis_sdk.ClientConfig` — a base
URL, a credential, a timeout — and nothing else. That short list is the whole of
what you decide about the system before you call it, and it is worth contrasting
with the lower half of the diagram.

Two consequences follow, and they are the design content of this section.

**Your integration inherits the enforcement posture; it does not set it.** The
runtime choice, the presence of a pre-execution tool gate, the egress
classification policy and the cryptographic posture are all **deployment
configuration**. Nothing in this client writes them. That means the single most
consequential question about your system — *does a bound get consulted before the
effect, or after it?* — is answered by whichever team configured the deployment,
and is not answerable from your code. 06.5 states the mechanism and the default;
what it cannot tell you is what **your** deployment runs.

Treat that as a question to ask, not an assumption to carry:

- Which agent runtime is in force, and does it carry a pre-execution tool gate?
- Is the deployment configured to refuse to start without one, or only to warn?
- Is outbound content classification actually live, and what classifier is
  installed?
- Which credential types does each surface in my path admit?

The one readiness read you *can* make is
`api:GET /api/v1/governance/envelope-coverage` — it answers not *"do bounds
exist"* but *"would they stop anything"* — and 06.4 covers how to read it
honestly. Everything else on that list is a conversation.

**A refusal tells you that you were kept out; it does not tell you by what.** The
credential boundary is a wall you can see, which is the good case. The
enforcement layers inside a run are not: when work stops, nothing in the response
distinguishes a posture ceiling from an envelope dimension from a never-delegated
override from a kill switch. *Derived, not observed here:* that opacity is
inherited from what the client documents about its refusals, not from a refusal
this chapter provoked — treat it as the model to design against and let your own
first held run confirm it. The record layer knows, and 06.4 has the reads that
ask it. Build the habit of asking *which* bound, rather than treating the first
plausible one as the answer.

## Guaranteed by the boundary, or only conventional?

This is the distinction this chapter exists to draw, and it is not visible from
the call signatures. Both columns below behave identically when everything is
working. They diverge on the day something is not.

**Guaranteed** means: the thing that holds the enforcement is outside your
process. You cannot get around it by calling the route yourself, and it is not
something you could neglect to configure. **Conventional** means: the behaviour is
maintained by this client, or by a field the platform records without acting on.
It is real, it is useful, and a design that depends on it is depending on a
contract that the server does not enforce on your behalf.

There is a third answer, and it is the one that costs the most to get wrong:
**runtime-dependent**. The behaviour is guaranteed *on some runtimes and not on
others*, decided by deployment configuration you cannot see from here.

| behaviour | which | why |
| --- | --- | --- |
| Clearance on artifact reads | **guaranteed** | the server refuses a read your clearance does not reach; the client cannot bypass it |
| Another organisation's artifact reads as *not found* | **guaranteed** | a deliberate refusal shape, so a 404 never confirms existence |
| Classification of an uploaded artifact | **guaranteed** | derived from the request's workspace; there is no argument to set it |
| Tenancy of anything you touch | **guaranteed** | derived from your credential, checked at more than one layer |
| An API key is refused on persona-gated routes | **guaranteed** | the key is built with no role and no personas; the refusal is the design |
| Governance on a tool-agent invocation | **guaranteed** | trust, posture and budget are checked server-side; fail-closed if the governance service is unavailable |
| A `held` verdict stopping the run | **guaranteed** | it suspends and waits for a person; with no queue to hold in it fails closed to a denial |
| A `blocked` verdict refusing the action | **guaranteed** | decided before anything downstream proceeds |
| **A verdict landing *before* the side effect** | **runtime-dependent** | only one runtime carries a genuine pre-execution tool gate, and it is not the shipped default |
| **A bound preventing an effect that already happened** | **impossible** | below the event boundary a verdict is a record; it stops the run, not the effect |
| **Outbound LLM content being classified** | **runtime-dependent** | the mechanism ships; the policy is the deployment's, and the default is a pass-through |
| Trust-chain and audit records | **guaranteed** | see 06.4 |
| The audit chain's integrity check | **guaranteed** | `api:GET /api/v1/compliance/audit/verify` is the operation that makes the trail evidence |
| **Objective status** | **conventional** | `sdk:aegis_sdk.ObjectiveStatus` is a *lossy* projection of nine wire states onto six values |
| **Quota adequacy** | **conventional** | the client's check reads a cached quota list and does the arithmetic locally |
| **Pagination** | **conventional** | some endpoints do not paginate at all and still return the envelope |
| **A `decision`'s `expires_at`** | **conventional** | recorded, not enforced — a past deadline on a pending decision means unswept |
| **Stream filtering** | **conventional** | the session stream's `event_types` argument is applied client-side |
| **Priority** | **conventional** | an integer here, a four-value tier on the wire |
| **Error signalling** | **partly conventional** | some refusals arrive as `success: false` inside a `200` |

### The two that surprise people most, in full

**Status is a projection, and it collapses the two states you most need to tell
apart.** `sdk:aegis_sdk.ObjectiveStatus` maps `plan_review` and `confirmed` and
`pending` onto one value, and maps `decision` — *stopped, waiting for a person* —
onto `IN_PROGRESS`. An operator view built on the typed model cannot show that
anything is waiting on a human. Read the status off
`api:GET /api/v1/objectives/{}/progress`, which returns the wire string. Full
table in 06.5.

**The quota check is a local calculation, and its unknown-input branch fails
open.** `sdk:aegis_sdk.revenue.QuotasModule` reads the organisation's quotas at
`api:GET /api/v1/features/limits` and caches them; the check method compares
`remaining` against the amount you name and answers yes or no from that cached
copy. Two consequences you should design around rather than discover:

> ⛔ **It is a check-then-act with no atomicity.** Another caller can consume the
> headroom between your check and your create. The check tells you the answer as
> of the last read, not that the next write will succeed — so treat a pass as
> permission to *try*, and handle the refusal at the write.
>
> ⛔ **An unrecognised resource type answers "allowed".** If the type you pass is
> not a quota the platform tracks, the check returns allowed with a limit and
> remaining of zero. That is the client's documented branch, not a bug in your
> call — and a documented fail-open is still a fail-open. A design that gates on
> that answer is safe exactly as long as the spelling is right and nothing
> about the response tells you when it is wrong.

Whether the platform *additionally* enforces a quota when you actually attempt
the write is **UNVERIFIED** here. The client exposes a read of the limits and a
local judgement on them; it does not expose the refusal. Do not build a capacity
plan on the assumption either way without testing it against your deployment.

**Pagination is the quiet one.** `sdk:aegis_sdk.PaginatedResponse` is a clean
envelope — `items`, `total`, `page`, `page_size`, `has_next` — and some endpoints
that return it do not paginate at all. On those, `total` is the length of the
page you were handed rather than a count of anything, `page` is always 1, and
`has_next` is a heuristic comparing the number of records against the page size.
A consumer that loops on `has_next` over such an endpoint will either miss
records or repeat them, depending on which way the boundary falls. Check that the
endpoint actually accepts a page parameter before you write a pagination loop
around it. This is the same family as the status collapse: **the shape of the
response is not a statement about the endpoint's behaviour.**

## The failure modes that cost the most to find late

Each of these is a design that looks right, works in a demo, and fails once real
volume or a real refusal arrives. The symptom is what you will actually observe.

The first four are about **where enforcement happens**, and they lead the list
because they are the ones that cannot be discovered by testing harder. A control
at the wrong layer behaves identically to a correct one right up until the
question is asked by someone who will not accept a demonstration.

**1. Assuming enforcement sits at the layer you designed against.**
*Symptom:* a control that refuses reliably in a demo and does not refuse in
production, or the reverse; a test that proves your integration handles a refusal
on a path where no refusal is ever produced.
*Diagnosis:* enforcement here is layered, and the layers do not live in the same
place. Admission at the boundary is a different layer from adjudication inside
the run, which is a different layer again from the tool gate — 06.5 maps where
each is consulted relative to the effect. Before you depend on a control,
establish *which* layer produces it, and confirm that layer is on the path your
work actually takes. A refusal you can reproduce proves a layer exists; it does
not prove it is the layer you think it is.

**2. Assuming a `held` verdict prevented the action.**
*Symptom:* a run that stopped, a hold that was answered, and an external system
that had already been changed. Or an audit that reads clean on the record and
surprising in the world.
*Diagnosis:* this is the most expensive misreading available on this platform. A
hold stops the run and everything downstream of it. On every runtime except the
one with a genuine pre-dispatch gate, the first side effect may already have
landed before the verdict exists. The verdict is **containment and evidence, not
prevention** — real value, and a different claim. If your design needs
prevention, it needs the runtime that provides it, and you need to have confirmed
you have it rather than assumed it.

**3. Assuming the deployment has a pre-execution gate.**
*Symptom:* a governance claim you cannot support, discovered in the room where
you have to support it.
*Diagnosis:* the shipped default runtime has no pre-execution tool gate, and the
platform says so out loud at boot rather than leaving it to be discovered. Of the
six runtimes, one carries the gate. Whether *your* deployment is on it is a
configuration fact, not a code fact, and no route in this client answers it. Ask;
and if the answer matters to what you are promising, have the deployment
configured to refuse to start without the gate rather than merely warn about it.

**4. Assuming outbound content is classified.**
*Symptom:* a design that depends on no unclassified content leaving the process,
and content leaving unclassified.
*Diagnosis:* the classification mechanism ships, is fail-closed inside a guarded
environment, and covers four in-process surfaces — but in the canonical default
no environment is guarded and no classifier is installed, so it is a no-op
pass-through. Both halves are the deployment's to supply. It also cannot cover a
runtime that spawns a subprocess, by construction: 06.2 has that boundary and it
is the reason some designs must disable those runtimes rather than police them.

**5. Building control flow on the typed status enums.**
*Symptom:* work that is stopped on a human reads as running, so nothing
escalates and nothing reminds anyone. You find out when a request has been
sitting for a week.
*Diagnosis:* read the wire status from a raw-dict route and keep your own state
machine. Treat the enums as filters for coarse queries.

**6. Treating a `403` as a scope problem.**
*Symptom:* a refusal whose message names personas you do not have, on a route
that works for a colleague using a session. You go and inspect the key's scopes
and find nothing wrong — because nothing there is wrong.
*Diagnosis:* on persona-gated routes the scopes are never consulted. Retry the
identical call with a user session (`api:POST /api/v1/auth/login`, then the same
call). If the session succeeds, no amount of scope editing will move it, and
widening the key leaves you holding a stronger credential for no benefit.
Confirm what the credential carries at `api:GET /api/v1/auth/me`.

**7. One queue where there are several.**
*Symptom:* the approvals queue is empty, so the operator reports all clear,
while a pending decision and an escalated request sit unanswered for weeks.
*Diagnosis:* there is no aggregating endpoint — each kind of waiting is its own
record with its own inbox route. If you build one check, build the sweep across
`api:GET /api/v1/approvals/pending`, `api:GET /api/v1/decisions/pending`,
`api:GET /api/v1/agent-escalations/pending`, `api:GET /api/v1/pseudo-requests`,
`api:GET /api/v1/agentic/inbox`, `api:GET /api/v1/posture/pending-approvals` and
`api:GET /api/v1/change-requests`. 02.6 has the same list from the operator's
side, and both stop short of claiming it is exhaustive: an organisation can wait
on things this book never enumerated, and nothing in the platform will tell you
that you missed one.

**8. Assuming a hold resumes on its own.**
*Symptom:* a decision nobody answered, and work that never completed. No error
anywhere.
*Diagnosis:* the work holds a state; it does not occupy a queue. A decision's
deadline is recorded, not enforced. If nobody answers, nothing happens — so the
scheduler that nudges a human is yours to write, not the platform's to provide.

**9. Adopting a workflow on a method that is declared but not served.**
*Symptom:* a well-shaped method that answers `404` every time — or, worse, one
you wire into a retry path and never notice.
*Diagnosis:* this client declares operations the server does not serve. Whether
they should be declared is a fair question; the useful move is to call each
method your design depends on **once**, against a real deployment, before you
build on it. The known cases are marked where you would look for them —
`.. warning::` blocks in the package's own method docstrings, which is exactly
what `help()` on any method in this SDK shows you — and the family is
recognisable: whole-object **update**, **submit**, and **list** operations on
resources whose real lifecycle is driven by a background task rather than by a
request. If a method's docstring says a call 404s, believe it, and design the
workflow around the route it names instead.

**10. Reading `approve` as `applied`.**
*Symptom:* a change that was approved and never took effect; a system where the
review says done and the state says otherwise.
*Diagnosis:* approve and apply are separate steps on the change-request surface.
Same shape as draft envelopes and unsubmitted objectives — describing and
effecting are always two operations here.

**11. Assuming you can name an artifact's classification, or file it where you
want.**
*Symptom:* an upload accepted with an unexpected classification, or refused
because the request is not attached to a workspace.
*Diagnosis:* the workspace comes from the request and there is no argument for
it. Choose the request you attach to; it chooses everything else.

**12. Reading a version gap as corruption.**
*Symptom:* `api:GET /api/v1/artifacts/{}/versions` returns `1, 2, 4`.
*Diagnosis:* each version is clearance-checked individually, so a version you may
not see is omitted and the numbers are as stored, not renumbered. A gap is
information about your clearance, not a fault.

**13. Treating a failure signal as the only failure signal.**
*Symptom:* a write that reports success and did not happen; or the opposite —
you handle exceptions and miss the refusals that arrive inside `200` bodies.
*Diagnosis:* several operations here report a refusal in the body rather than by
raising, and the platform's conflict status has no dedicated exception class, so
a `409` arrives as the base error you would need to discriminate by status code.
`sdk:aegis_sdk.AgenticOSError` and its subclasses carry the status; read the
documented return shape of each write, not only its raise list.

**14. Depending on a guard this client holds.**
*Symptom:* a check that works from your code and not from a direct HTTP call —
and you discover it when someone else's integration does the thing you thought
was refused.
*Diagnosis:* the clearest example is tool-agent invocation, where this client
raises *before* sending anything if a tool call is malformed, precisely because
the server would otherwise answer from the model and report success. That
protection is a property of the SDK, not of the platform. If your design's
safety rests on it, and anything else in your estate can reach the same route
without the SDK, the safety is not where you think it is.

## What to do differently, in one list

Design practice that follows from the fourteen above:

1. **Establish which layer enforces what you are promising.** For each guarantee
   your design rests on, name the layer that produces it and confirm that layer
   is on the path your work actually takes. The first four failure modes are all
   this one question, asked of four different controls, and none of them can be
   settled by testing harder.
2. **Branch on wire values, not on client enums.** Where a raw-dict route
   exposes the platform's own vocabulary, use it for anything that decides
   behaviour.
3. **Prefer the stream for liveness and a poll for state.** They answer different
   questions and the streams do not keep a history.
4. **Treat every declared operation as unverified until you have called it**,
   and treat every anchor in this book the same way — including the ones on this
   page. An anchor proves the surface exists in the client you were given; it
   says nothing about what the server checks when you call it.
5. **Own the states the platform does not hold.** Your integration's timeout, its
   nudge, its retry and its exhaustion handling are all yours. Nothing in the
   product schedules them.
6. **Build the sweep before you build any single queue.** Retrofitting an
   aggregator onto surfaces you integrated one at a time is worse than building
   the sweep first, and the sweep is the only view an operator can act on.
7. **Verify what you will later have to prove.** The integrity check over the
   audit chain is worth running on a schedule from day one, because a
   verification taken after an incident is worth a fraction of a series taken
   before it (02.6 covers this and is worth the re-read).
8. **Write the check before you need the answer.** Whatever your organisation
   will one day be asked to demonstrate, build the read for it now — while you
   still remember why it matters.

## What this chapter cannot establish

It draws a line between guaranteed and conventional, and the line is only as
sharp as an outside read allows. Three limits, stated rather than implied:

- **"Guaranteed" here means the enforcement is not in your process.** It does not
  mean the enforcement is correct, complete, or free of defects. A control that
  is genuinely server-side can still be wrong; 04.1 documents one that is.
- **The conventional column is a list of what this client does, not an exhaustive
  list of everything the platform does not enforce.** There is a path with no
  surface anywhere in this book, and a behaviour nothing exposes cannot be
  classified here at all — it is invisible, not absent.
- **Nothing on this page was verified against a running deployment by writing
  it.** Every claim derives from the client's own declared behaviour. Where that
  was not enough, the page says **UNVERIFIED** rather than choosing the reading
  that makes the sentence tidier.

You have reached the end of part 06. If you arrived here first, the part index
maps what to read next; the chapters are ordered as reading dependencies, and
each one is a statement about one side of the boundary 06.1 draws.

---

*Next: [Part 06 — Architecture](README.md)*
