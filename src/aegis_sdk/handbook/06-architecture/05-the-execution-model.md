# 06.5 — The execution model

Parts 02 and 04 told you what to call. This is the shape underneath: what a unit of
work *is*, what happens to it between submission and result, who can be holding it
at any moment, and what you can actually observe while it runs.

Read it before you design anything that submits work, watches it, or answers a
question about it. Most of the surprises are in the second half.

## The split that shapes everything: who decides, who executes

Before any object, there is one division. Aegis is built on **two planes**:

| plane | what lives there | the question it answers |
| --- | --- | --- |
| **Trust Plane** | envelopes, clearances, postures, delegations, approvals, revocations | *what is the agent allowed to do?* |
| **Execution Plane** | objectives, requests, tool calls, sessions, artifacts | *what does the agent actually do, inside what it was allowed?* |

The division of labour is the whole design in five words: **the human decides,
the AI executes.** A person sets the bounds and answers what the system escalates
to them. They do not approve every action — that would make throughput a function
of their attention, and the system would get slower as it got more capable.

What the split buys is a single structural property: **an agent cannot widen its
own mandate, because the mandate is not decided where the work happens.** That is
not a policy anyone has to remember to enforce. It is why the never-delegated set
below contains *changing the constraints* and *changing the governance* — an
agent at maximum autonomy still cannot reach either.

> ⛔ **Do not read the two planes as two services.** This is the reading that gets
> made and it is wrong. There is no trust-plane process to point at, no second
> cluster, and no database split — the split is between **who decides** and **who
> executes**, and it is realised inside the same deployment, across many
> components. A design that assumes a network boundary between the planes will
> build a hop that does not exist, and — worse — will locate the human in the
> wrong place. The human is on the loop in the trust plane, not in a queue
> beside it.

## Work is an object graph, not a call

Nothing here is a function you call and get a result from. An objective is
accepted, decomposed, executed by one or more agents, and produces files. Five
objects carry that, and they nest in a direction that is not the obvious one:

| object | what it is | how it is addressed |
| --- | --- | --- |
| **objective** | a goal you ask for | `api:POST /api/v1/objectives`, read back at `api:GET /api/v1/objectives/{}` |
| **request** | one work item, produced by decomposition; some need a person | `api:GET /api/v1/objectives/{}/requests` |
| **task graph** | that decomposition as nodes and edges | `api:GET /api/v1/objectives/{}/task-graph` |
| **session** | one agent's execution context against a request | `api:POST /api/v1/sessions/from-task`, read at `api:GET /api/v1/sessions/{}` |
| **artifact** | a file produced against a request | `api:POST /api/v1/artifacts`, read at `api:GET /api/v1/artifacts/{}` |

**The artifact edge points at the request, not the objective.** That is the one
relationship people get backwards, and it has consequences at the end of this
chapter. `api:GET /api/v1/objectives/{}/artifacts` exists, but it is a roll-up
across the objective's requests — it is not where an artifact lives.

A **session** is the unit of "what an agent actually did": messages, artifacts,
and any subagents it spawned, readable at `api:GET /api/v1/sessions/{}/subagents`
and streamed live (below).

### The second family: work units are definitions, not instances

Objectives are *things you asked for*. A **work unit** is a reusable, versioned
definition you keep and execute on demand — closer to a function than a job. It
has its own lifecycle, its own configuration and its own version chain:

| | objective | work unit |
| --- | --- | --- |
| lifetime | one piece of work | reusable across many runs |
| versioning | none | `api:GET /api/v1/work-units/{}/versions` |
| what runs | a decomposition into requests | the unit itself |
| executed via | confirm-implementation | `api:POST /api/v1/work-units/{}/run` or `api:POST /api/v1/work-units/{}/execute` |

The two execution routes are genuinely different and you should pick deliberately.
`run` is synchronous and hands back a run result. `execute` drives an agent: it
takes a message, returns a `run_id` with `cost_usd`, `cycles_used` and
`tokens_used`, and continues across turns if you pass a `session_id`. Only
`execute` produces something you can cancel mid-flight, with the `run_id`.

A work unit also carries an **execution configuration** — runtime, model,
execution mode, budget ceiling in USD, cycle cap, timeout, memory depth, and the
allowed-tool list — read and written at
`api:GET /api/v1/work-units/{}/execution-config`. If you are building a
provisioning script, this is the object you set once and version, rather than
restating on every call.

`sdk:aegis_sdk.modules.WorkObjectivesModule` wraps this surface; the
objective-side methods live on `sdk:aegis_sdk.execution.ObjectivesModule`.

## The lifecycle, and the collapse in the middle of it

Here is the real state vocabulary an objective moves through on the wire:

```
   The main line — each state hands off to the next:

     [*] ──▶ draft ──▶ pending ──▶ plan_review ──▶ confirmed ──▶ executing

   Every transition, with the ones an OPERATION establishes marked in the
   third column. The unmarked rows are the ordering this book reads from
   the state names and the way the routes are named: design intent, not
   observable.

     from          to             established by
     ─────────────────────────────────────────────────────────────
     [*]           draft
     draft         pending
     pending       plan_review
     plan_review   confirmed
     plan_review   executing      confirm-implementation
     confirmed     executing      confirm-implementation
     executing     decision       the run stops to ask
     executing     completed
     executing     failed
     executing     cancelled      stop
     decision      executing      revise / more_analysis
     decision      completed      proceed
     decision      cancelled      reject
     completed     [*]
     cancelled     [*]
     failed        [*]

   Three of the sixteen are terminal, and `decision` is the only
   state that can return to `executing` — the loop in the middle of the
   lifecycle.
```

Edges carrying an operation name are established by that operation's documented
transition. The unlabelled edges are the ordering this book reads from the state
names and the way the routes are named; no single route documents them, so treat
the sequencing as **design intent, not observable**.

**Now the part that matters.** ⛔ **open defect** — the client's own module
documentation calls this a known limitation and a tracked follow-up, so it is
declared rather than accidental; it is still the thing most likely to shape your
design wrongly.

`sdk:aegis_sdk.ObjectiveStatus` declares six values, and the client maps those
nine states onto them:

| wire state | what `ObjectiveStatus` reports |
| --- | --- |
| `draft` | `DRAFT` |
| `pending`, `plan_review`, `confirmed` | `PENDING` |
| `executing`, `decision` | `IN_PROGRESS` |
| `completed` / `cancelled` / `failed` | `COMPLETED` / `CANCELLED` / `FAILED` |

Two collapses, and both bite:

- **`plan_review`, `confirmed` and `pending` are one value.** "Nobody has looked
  at it", "a human is reviewing the plan" and "the plan is approved and waiting
  to launch" are indistinguishable.
- **`decision` reads as `IN_PROGRESS`.** An objective that has *stopped and is
  waiting for a person* is reported by the typed model as one that is running.

So an operator dashboard that branches on the `status` field of
`sdk:aegis_sdk.Objective` cannot show that anything is waiting on a human. That
is the single most consequential fact on this page.

**And the mapping fails open on a state it does not recognise.** The nine above
are the client's belief about the platform's vocabulary; a status this client has
never heard of resolves to `PENDING`, not to an error. So a state the platform
adds later arrives looking like work nobody has started, rather than looking like
something your client does not understand.

The workaround is cheap and you should build it in from the start: **read the
status off the progress route instead.** `api:GET /api/v1/objectives/{}/progress`
returns a raw map carrying the unmapped `status` string alongside
`overall_progress`, `steps`, `graph_nodes`, `elapsed_ms`,
`estimated_remaining_ms`, `cost` and `constraint_dimensions`. The typed
`sdk:aegis_sdk.Objective` does not carry the raw value — it is dropped during
normalisation and the model has no field to hold it.

Standing advice, stated once for the whole book: **treat the SDK's status enums
as a convenience for coarse filtering, never as the thing you branch on for
control flow.** Where a raw-dict method exposes the wire value, prefer it.

## How work starts

Creation does not start anything, and the gap is wider here than anywhere else in
the platform. Three separate hand-offs stand between "created" and "running":

**1. Clarification, if the objective needs it.** The platform can generate
questions before decomposing. Generation is asynchronous:
`api:POST /api/v1/objectives/{}/clarify/trigger` returns as soon as the work is
queued, and the questions are not in the response. Poll
`api:GET /api/v1/objectives/{}/clarification-status` or watch the progress stream.

Read the `status` field on that poll, because **an empty question list does not
mean there is nothing to ask**. `generating` means not yet. `failed` means
generation did not finish, and an explanatory `message` is present only in that
case — the questions are empty for a reason that is *not* "no clarification was
needed". Only `completed` settles it.

**Answering triggers the next stage.** `api:POST /api/v1/objectives/{}/clarify`
submits answers and starts decomposition as a background task; the free-form
variant accepts one block of text and does the same. Recording an answer is not a
passive act here.

**2. Decomposition.** The objective becomes a task graph — nodes, edges, an
estimated total in minutes and dollars. Read the result at
`api:GET /api/v1/objectives/{}/task-graph`. `trigger_execution` starts this and is
safe to repeat: it answers either `processing`, or `already_decomposed` with a
`task_count`. Branch on that string rather than treating a repeat call as an
error.

**3. Confirmation.** `api:POST /api/v1/objectives/{}/confirm-implementation`
takes no body, moves `plan_review`/`confirmed` to `executing`, and **launches
execution as a background task**. Read the last four words carefully: the call
returns when the work has been *launched*, not when it has been done. Everything
you learn about the run from here on comes from a poll or a stream.

This is the same *describing* versus *effecting* split you meet on draft
envelopes, unsubmitted objectives and unapplied change requests — by now it
should read as the platform's consistent habit rather than a quirk.

## Where a bound is actually consulted

> ⚠ **The mechanism below is the platform's account of itself, not something a
> client can observe.** None of it is derivable from the SDK surface: you can see
> that a call was refused, never which object consulted what, and no route
> returns the composition rules. It is set out because you are designing against
> it, and it is labelled because a design resting on an unlabelled description
> rests on a reading.

This is the section to read twice if you are designing anything that depends on a
control — because the answer is not *"at the API"* and it is not *"at the tool"*.
It is **both, and they are different moments, with different strengths**, and one
of the two is not guaranteed to be present at all.

Four governance objects are read on the execution path. They are the trust plane's
values, and the execution plane only ever reads them:

| object | what it contributes | who sets it |
| --- | --- | --- |
| **role envelope** | the bounds — five constraint dimensions | the role's owner, in the trust plane |
| **posture** | how much of those bounds the agent may use unsupervised | the posture ladder; effective value is the *tightest* of the agent's own, its unit's ceiling, and what the objective selected |
| **trust chain** | where its authority came from, and whether it is still valid | established once, revoked from the trust plane |
| **kill-switch state** | whether it may run at all | an operator, in an emergency |

A key property of the envelope axis, and it is the one designs get wrong: **bounds
compose by intersection, never by union.** Adding an envelope narrows; it never
widens. A delegate cannot hold more than the role defining it holds. If you are
relying on an escalation path that *adds* permission, there is no such path.

And the adjudication itself resolves into **exactly four zones** — there is no
fifth, and nothing "advisory" among them:

| zone | what happens |
| --- | --- |
| `auto_approved` | runs, and is recorded |
| `flagged` | runs, and is highlighted for later review |
| `held` | **stops and waits for a person** |
| `blocked` | refused, with a reason |

### The path, with the enforcement points marked

Read this as the shape of one action, from your call to the record. The thing to
notice is the vertical position of each box relative to the line marked *side
effect*.

> ⚠ **The boxes are documented; their arrangement is this chapter's reading of
> them.** Each layer and each gate is stated somewhere reachable — the runtime
> census below is the best-evidenced part of this page — but the *order*
> assembled here is a model of how an action passes through them, **not a trace
> anyone ran.** Nothing you can call returns the sequence. Read the vertical
> positions as a design claim to reason from rather than as a measurement, and
> expect a refusal to tell you that you were kept out rather than which box did
> it.

```
  your call
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│ ADMISSION                                        before work exists│
│   credential · organisation · role · permission or persona         │
│   refuses: unauthenticated · wrong tenant · no permission          │
└────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│ RUN ADMISSION                                    before the run    │
│   kill switch · trust chain · posture materialisation              │
│   refuses: an agent that may not run at all, for any reason        │
└────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────────────────────────────┐
│ THE AGENT RUNS                                                     │
│                                                                    │
│   proposes an action                                               │
│      │                                                             │
│      ├─▶ envelope adjudication — the five constraint dimensions    │
│      ├─▶ posture ceiling · never-delegated override                │
│      ├─▶ budget — per call, then cumulative session spend          │
│      │                                                             │
│      │   ╔══════════════════════════════════════════════════════╗  │
│      │   ║ PRE-EXECUTION GATE                                   ║  │
│      │   ║ present on ONE runtime only.                         ║  │
│      │   ║ ABSENT on the shipped default.                       ║  │
│      │   ╚══════════════════════════════════════════════════════╝  │
│      ▼                                                             │
│                                                                    │
│   ══════════════════ the side effect ══════════════════            │
│                                                                    │
│      │                                                             │
│      ▼                                                             │
│   tool-use event ──▶ STOP POINT                                    │
│      halts the run · withholds everything downstream ·             │
│      records the attempt, the verdict and the reason               │
└────────────────────────────────────────────────────────────────────┘
      │
      ▼
  the record
```

Everything above the side-effect line is **prevention**. Everything below it is
**containment and evidence**. Which side a given verdict lands on is decided by
your runtime, not by your policy — and that is the next section, because it is
the single most consequential fact on this page.

### The pre-execution gate is runtime-dependent, and the default does not have one

Aegis registers **six** agent runtimes and they do **not** have the same
enforcement properties. Exactly one carries a genuine per-tool pre-dispatch gate:
it can return a refusal *before* the tool runs, and it fails closed when the check
itself is unavailable. Three declare no pre-execution gate at all. Two declare a
conditional path that attaches only when a further switch is turned on.

**The one with the real gate is `claude_agent_sdk`, and it is not the shipped
default.** The default is `kaizen_native`, whose conditional gate is off unless
the deployment enables it — so **in a stock deployment there is no pre-execution
tool gate at all**, and what remains is the event boundary below the line. The
platform does not hide this: it emits a warning at boot naming the condition — the
default runtime has no pre-execution gate, and agent rows with no explicit runtime
execute with no control adjudicating an action before its side effect. A
deployment that requires the gate can be configured to **refuse to start** without
it rather than warn, which converts the property from aspirational into
structural.

⚠ **This is a deployment fact, not an SDK one, and your integration cannot change
it.** You can read readiness for the *envelope* half of the question at
`api:GET /api/v1/governance/envelope-coverage`; whether a pre-execution gate is
attached is answered by the deployment's own configuration and its boot log, not
by any route in this client. **UNVERIFIED** from the SDK surface: which
configuration your deployment is running. Ask before you build a claim on it.

**And the event boundary is not a substitute for it.** A verdict decided from a
tool-use event is a *record*, not a control — the honest statement is that it
stops the run, withholds the action from everything downstream, and tells you
accurately what was attempted and refused. On every runtime but the one with the
real gate, the first side effect may already have landed by the time the verdict
exists. That is not a bug in the adjudication, which is correct and fails closed;
it is *when* the adjudication is consulted relative to the effect.

> ⛔ **Do not design around a refusal that happens before the effect unless you
> have confirmed you are on the runtime that provides it.** The failure this
> prevents is expensive and silent: a control you believe is preventive, which is
> in fact a very good record of something that already happened.

### Where the strongest layer actually is

> ⚠ **Same basis as the section above.** Which layer holds is argued from the
> platform's description of its own behaviour and from the custody property you
> can reason about from the client; it is not a trace of an action being stopped.

Pre-execution interception is the *weakest* layer here, which is counter-intuitive
enough to be worth stating plainly. The layers that hold on **every** runtime are:

1. **Credential custody.** The agent never holds the secret it acts with. A
   compromised agent — prompt-injected, jailbroken, or simply wrong — still cannot
   read the credential, so the worst it can do is *make requests*, and requests are
   adjudicated. This does not depend on any interception being correct, which is
   why it is the layer to lead with.
2. **Admission at the boundary.** Identity, organisation, role and permission
   decide who may call what at all.
3. **The kill switch.** Four scopes — a single agent, one person's work, a class of
   workflow, or the whole estate — in one of two modes: *hard stop* terminates
   in-flight work now, *drain* refuses new work and lets in-flight settle inside a
   bounded window before force-stopping stragglers. It is checked at several
   independent execution surfaces, fails closed if the state cannot be read, and
   **does not expire on its own** — clearing it is an explicit act.
4. **Envelope and posture adjudication**, which computes correctly and fails
   closed, subject to the timing question above.
5. **The audit chain and revocation**, which bound what you can prove and what you
   can stop after the fact — 06.4 owns that axis.

Two of these fail *toward* refusal in ways worth knowing, because they change what
your integration sees: the kill-switch gate answering "gated" when it cannot read
its own state, and a never-delegated check that raises being treated as *held*
rather than as permission.

## What a verdict does to work in flight

> ⚠ **This is the least observable claim in the chapter, and the one most likely
> to shape a design wrongly, so read its basis before its content.** Nothing here
> is derivable from the SDK surface and nothing here was measured: it is the
> platform's description of its own verdict semantics, and in particular the
> claim that a side effect already landed is *not undone* is a statement about an
> event boundary you cannot see from your side. Design as though the boundary is
> where the platform says it is — and, where the distinction matters to you,
> confirm it against your own deployment rather than against this page.

Knowing where a bound is consulted is half the question. The other half is what
happens to work that is already running when the answer comes back unfavourable.

**A `held` action genuinely suspends and waits.** It is not logged-and-continued.
The waiting coroutine blocks until a person answers, and on approval **the same
action object is re-emitted downstream** — so approval *resumes* the action rather
than replaying it. If no queue is available to hold in, the hold is treated as a
**denial**, on the explicit reasoning that a hold with nowhere to go is a denial
and not an approval. That is fail-closed, and it is the right default: design your
integration so a missing queue can never be read as consent.

**A `blocked` action is refused with a reason**, and nothing downstream proceeds.
The reason travels with the verdict; surface it rather than collapsing it to a
boolean, because it is the only thing that tells an operator which bound was hit.

**A never-delegated action is held regardless of posture.** The seven-action set
is checked on the surfaces that speak *business actions*, and where a verdict has
already been computed as approve, the never-delegated check **overrides it to
held**. Two entries make the set self-protecting: changing the constraints and
changing the governance are themselves never delegated, so no agent can reach the
machinery that bounds it. **UNVERIFIED:** whether every path to a tool boundary
passes one of those surfaces. If one does not, an action from that set could reach
a boundary that cannot recognise it. That question is open, and it is the right
one to ask of any deployment you are relying on.

**And the honest limit, which is the whole point of this section:** on every
runtime except the one with a genuine pre-dispatch gate, a `held` verdict stops
the **run** — everything downstream of the action does not happen — but it does
not undo a side effect that already landed. Read that as: *containment of the run,
and a durable record of the attempt*, which is real value. Do not read it as
prevention. Where a run is long and autonomous, a hold is a hard stop near the
edge of its envelope, which is why 02.5's advice to decompose work so the
boundary-crossing part is its own small request is a design constraint rather than
a style preference.

## What a running execution is

The platform tracks execution at three different resolutions, and they are not
views of one record:

| resolution | what you read | what it is good for |
| --- | --- | --- |
| **objective** | `api:GET /api/v1/objectives/{}/progress` | how far along, what it has cost, which constraint dimensions are under pressure |
| **task graph** | `api:GET /api/v1/objectives/{}/task-graph` | what the work is broken into, and which node is stuck |
| **session** | `api:GET /api/v1/sessions/{}` | what an agent did: messages, artifacts, subagents |

**Not everything that runs is an addressable record, and this is worth knowing
before you build a poller.** `api:POST /api/v1/agents/{}/execute` is a
*synchronous* chat completion: it either returns a result or raises. Agent
executions are not persisted as individually-addressable objects, so the client's
`get_execution`, `list_executions` and `cancel_execution` have nothing to
address. ⛔ **open defect** — those three methods are declared by the client, and
**each carries a warning in its own documentation saying the call answers 404.**
Note what that rests on: the client's account of itself, not a call this chapter
made. One call would settle it, and a docstring is not a measurement — this
book's own gate says an anchor proves a surface exists and never that it
behaves. Whether the three should be present at all is a fair question; the
answer that matters to you is that **a method existing is not evidence a route
exists** — see 06.6, where that distinction decides how much you may trust any
anchor in this book, including this page's.

That leaves three things you can stop, and they are different things:

- the **objective** — `api:POST /api/v1/objectives/{}/stop`, described as terminal
  and not resumable;
- a **work-unit execution** — cancel takes a `run_id`, and only works while an
  autonomous execution is still running;
- a **session** — pause, resume or end at
  `api:POST /api/v1/sessions/{}/pause` and its siblings. Prefer pausing a session
  to revoking an agent: revocation cascades and does not undo.

## Watching it: three streams, three vocabularies

Everything long-running is observable over Server-Sent Events, and there is more
than one stream. They do not share an event vocabulary, so one consumer cannot
serve all three:

| stream | route | events |
| --- | --- | --- |
| objective progress | `api:GET /api/v1/objectives/{}/progress/stream` | `execution_started`, `step_started`, `step_completed`, `progress_update`, `execution_completed`, `execution_error`, `heartbeat` |
| session | `api:GET /api/v1/sessions/{}/stream` | `started`, `thinking`, `message`, `tool_use`, `tool_result`, `subagent_spawn`, `cost_update`, `completed`, `error` |
| agent execution | `api:POST /api/v1/agents/{}/execute/stream` | `start`, `content`, `done`, `error` |
| escalations | `api:GET /api/v1/agent-escalations/stream` | pending human decisions |

Read the right-hand column as three different *granularities*, not three
spellings of one: the agent stream emits model tokens, the objective stream emits
plan steps, and the session stream emits what the agent is doing. Pick by the
question you are answering.

Two mechanical traps, both of which cost an afternoon:

> ⛔ **The objective progress stream authenticates by query parameter, and only
> by query parameter.** It takes a `?token=`, because a browser `EventSource`
> cannot send an `Authorization` header — and it does **not** fall back to the
> bearer header the rest of this client uses. The client defaults the parameter to
> its configured API key when you omit it, which is convenient and worth knowing
> when you are debugging why the same credential works everywhere else.

> ⛔ **The session stream has no server-side filter.** Its `event_types` argument
> is applied client-side, so every event crosses the wire and is discarded after
> arrival. If you are budgeting bandwidth on a high-volume session, filtering is
> not buying you anything.

For anything you need to keep rather than react to, poll the progress route. The
streams are for liveness; the progress and task-graph reads are for state.

## Where a human gets asked to decide

There are **six** places work can stop for a person, and they are six different
records with six different resolutions. A design that assumes one queue is the
most common integration mistake in this platform.

| what is waiting | the record | where you read it | how it is answered |
| --- | --- | --- | --- |
| the agent reached a decision point | an objective **decision** | `api:GET /api/v1/decisions/pending` | `api:POST /api/v1/decisions/{}/decide`, or from the objective at `api:POST /api/v1/objectives/{}/decide` |
| an action is held by the verification gradient | an **approval** request | `api:GET /api/v1/approvals/pending` | `api:POST /api/v1/approvals/{}/approve` (or reject, or approve-modified) |
| the agent is out of its depth | an **escalation** | `api:GET /api/v1/agent-escalations/pending` | `api:POST /api/v1/agent-escalations/{}/resolve` |
| a step was routed to people | a **pseudo request** | `api:GET /api/v1/pseudo-requests` | claim at `api:POST /api/v1/pseudo-requests/{}/claim`, then respond |
| a finished request needs sign-off | an **inbox item** | `api:GET /api/v1/agentic/inbox` | `api:POST /api/v1/agentic/requests/{}/validate` — approve, reject or revise |
| the organisation itself is changing | a **change request** | `api:GET /api/v1/change-requests` | see 02.6 |

**An empty approvals queue means nothing about the other five.** That is stated
in 02.6 from the operator's side; here is the structural reason — each is a
different table with its own inbox route, and nothing in the platform
aggregates them.

Two of these have admission rules that a design can run into late:

- **A decision is addressed to a named person, not to whoever holds write
  authority.** The pending list is scoped server-side to the authenticated
  caller's own user id and organisation, with no parameter to list or override
  it — so "show me all pending decisions" is not a query the API answers.
  Resolving one requires being the assignee or an organisation administrator; a
  correctly-credentialed user resolving someone else's still gets refused. And
  writes on that surface **reject an API key outright**, because the platform
  authorises them from the caller's role and an API-key principal carries no role.
- **A pseudo request is claimed, and claiming is how you avoid duplicate work.**
  Two people answering the same unclaimed request is the ordinary failure, and
  a claimed request held by someone who has moved on is invisible to everyone
  else.

## What happens to the work while it waits

The structural answer, and it is not what most people assume: **the work holds a
state; it does not occupy a queue.** An objective at `decision` is not running in
the background waiting to be unblocked. It has stopped, and the direction it
resumes in is decided by the option that is chosen:

- an option resolving to *proceed* completes the objective;
- one resolving to *reject* cancels it;
- *revise* or *more_analysis* returns it to `executing`.

So "what happens while it waits" is the honest answer **nothing** — which is
exactly why an unanswered hold is expensive and why the deadline fields below are
weaker than they look.

Three caveats, each of which changes what you build:

> ⚠ **A recorded deadline is not an enforced one.** A decision carries an
> `expires_at`. The client's own documentation says plainly that this is a
> deadline the platform records, not a commitment to act at that instant, and that
> a past `expires_at` on a still-pending decision should be read as *not yet
> swept* — re-read the status rather than assuming the platform resolved it. **Do
> not build a timeout on it.** If you need work to move when a human does not
> answer, that is a scheduler you own.

Escalations carry an `expiresAt` on the same terms, alongside status, resolution
and reasoning fields that stay empty until somebody answers. **UNVERIFIED:** what
the platform actually does when either deadline passes. Reading those fields
tells you the deadline is not a promise; it does not tell you what the sweeper
does, and this book will not guess.

And the caution applies in reverse when you are *building* the queue: a decision
your code reads and never answers is a piece of work that stops permanently.
Whatever you integrate, integrate the notification as well as the read.

## Who can carry the work

Not every agent is the same kind of thing, and the differences decide what you can
ask of one. Two independent axes — what the agent *is*
(`sdk:aegis_sdk.AgentType`) and what role it plays
(`sdk:aegis_sdk.AgentSubtype`) — and a third field that is not an agent axis at
all.

| type | what it is | how it runs |
| --- | --- | --- |
| `chat`, `task`, `pipeline`, `custom` | the four you can create | `api:POST /api/v1/agents/{}/execute`, or the stream above |
| `shadow` | a **role agent** — the delegate attached to a seat | assigned objectives (02.7) |
| `pseudo` | a human in the loop, behind an agent-shaped interface | routes a task to people |
| `tool` | a shared capability other applications invoke | governance-gated invocation |
| `esa` | minted by the platform's own machinery | — |
| `unknown` | a sentinel for a type a future release adds | — |

**Only the first four are creatable.** `sdk:aegis_sdk.core.AgentsModule` will not
create a shadow, pseudo, tool or esa agent: those are minted server-side, and the
read enum accepts them so that listing an organisation that has them does not
fail. `unknown` exists so a future value arrives as a sentinel rather than a
validation error — a design that branches exhaustively on this enum should have a
default branch.

Those types differ in more than name:

- **A tool agent is invoked, not executed.** `api:POST /api/v1/tool-agents/{}/invoke`
  runs it *through governance* — trust, posture and budget are all checked, and a
  refusal is a governance refusal rather than an error. It can run a registered
  built-in tool with no model round-trip at all, in which case the result reports
  that dispatch path and a zero cost. Two behaviours worth designing around: an
  unregistered tool name is refused outright rather than answered by the model,
  and declaring a governance category that was never delegated to the agent is
  refused regardless of the agent's posture. The client raises before the request
  on a malformed tool call, deliberately — see 06.6, because that is the clearest
  example in the package of a boundary being held client-side.
- **A task agent exists for agent-to-agent delegation** and is testable before you
  rely on it, at `api:POST /api/v1/task-agents/{}/test`. It is not a delegate: it
  carries no role envelope and its posture ceiling is an explicit field.
- **A pseudo agent is the human-in-the-loop work unit.** It presents the same
  interface as an autonomous agent; behind it, requests route to human operators
  over the channels you configure, at `api:POST /api/v1/work-units/pseudo/{}/route`.

**Pools hold role slots, not people.** Membership is keyed by role, so whoever
occupies the role is in the pool and a re-org moves the membership with the seat
(`sdk:aegis_sdk.modules.AgentPoolsModule` for the registry, and the operational
claiming and load distribution surface alongside it). If you were about to build
a roster, build it as a role mapping instead or every re-org becomes a data
migration.

Lastly: **`unit_type` is not `agent_type`.** `sdk:aegis_sdk.UnitType` — atomic
and composite — is the work-unit classification, and it travels in a field of its
own. A previous release of this client sent `agent_type="atomic"` and the server
rejected it; the two vocabularies look adjacent and are unrelated.

**Subagents exist at runtime but not as a request.** Sessions list what an agent
spawned at `api:GET /api/v1/sessions/{}/subagents`, and spawns arrive on the
session stream as `subagent_spawn` — but there is no request-side route to trigger
one. If your design needs to direct a subagent, it is directed by the agent, not
by you.

## The output end, and where it attaches

Artifacts are the product of all this, and three rules about them are structural
rather than incidental.

**An artifact attaches to a request, in a workspace.** The request must be in your
organisation *and* attached to a workspace; if it is not, the upload is refused
with a conflict. `sdk:aegis_sdk.execution.ArtifactsModule` is the surface.

⛔ **You cannot choose the workspace, and that is deliberate.** There is no
`workspace_id` argument on the upload route, and the server would ignore it if
you sent one. The workspace is derived from the request, and the workspace is what
decides how highly the upload is classified. Letting a caller name it would let
them choose whose classification mark the artifact carries. Design your upload
path around the request you are attaching to, not around a folder you want to
file it in.

**A new version inherits its predecessor's classification as a floor.** Superseding
at `api:POST /api/v1/artifacts/{}/supersede` takes the next version number and
cannot lower the mark. Version history is at
`api:GET /api/v1/artifacts/{}/versions`, and there is one behaviour that looks
like corruption and is not: **each version is clearance-checked individually**, so
a version you may not see is simply omitted and the numbers arrive with a gap —
`1, 2, 4`. The values are as stored, not renumbered. A gap is information, not a
fault.

**Reads are clearance-checked, and the refusals are asymmetric on purpose.** A
clearance you do not reach is refused with a 403; another organisation's artifact
is reported as **not found**, never as forbidden — so a 404 does not confirm that
something exists. Downloads return raw bytes rather than parsed JSON, and can
fail in two distinct ways that a retry loop should treat differently: the record
exists but its bytes are unreachable, which is a service condition, versus a file
too large to serve, which a retry will never fix.

## Where the next page goes

This chapter described what is guaranteed by the shape of the system. Not all of
it is. The next page is the one to read before you commit to a design: which of
these behaviours are enforced by a boundary you can rely on, which are only
conventional, where your integration attaches, and the failure modes that cost
the most to find late.

---

*Next: [06.6 — Designing against the platform](06-designing-against-the-platform.md)*
