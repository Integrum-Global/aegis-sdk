# 02.5 — Objectives and the work loop

An **objective** is work you ask for. What comes back is not a result but a
process: the objective decomposes into **requests**, some of which need a person,
and agents run **sessions** against them.

```
objective  ->  requests  ->  sessions        and, wherever a human is needed,
                                             a decision (02.6)
```

## Creating one

```python
objective = await client.objectives.create(
    title="Reconcile the September cash position",
    description="Pull balances from all accounts, reconcile against ledger, "
                "flag discrepancies over $1,000.",
    priority=7,
)
```

`api:POST /api/v1/objectives`, returning `sdk:aegis_sdk.Objective`.

Points that are not obvious from the signature:

- **`agent_id` is optional, and omitting it is meaningful.** The server assigns
  the caller's delegate agent. That is usually right for a person submitting
  their own work and usually wrong for a provisioning script, which has no
  business delegate — name the agent explicitly when the caller is not the
  intended worker.
- **`priority` is an int 0–10 here and a string tier on the wire.** The SDK maps
  it to the server's low/medium/high/urgent tiers. So priority is coarser than it
  looks: 6 and 7 may be the same tier. Do not build scheduling logic on the
  integer.
- **There is no metadata bag.** Objectives have no persisted metadata field. An
  earlier client sent one and the server dropped it silently. If you need to
  correlate an objective with something in your own systems, put the correlation
  key in the title or description, where you can search for it.
- **`selected_posture`** lets the originator choose a posture for this work,
  bounded by `min(agent, ceiling, selected)` from 02.4. Choosing a *lower*
  posture than the agent holds is the useful direction — it is how you ask for a
  careful run of something ordinarily routine.

## The lifecycle, and the states you will actually see

Objectives move through `draft` → `pending` → `in_progress` → `completed`, with
`cancelled` and `failed` as terminal alternatives (`sdk:aegis_sdk.ObjectiveStatus`).

A created objective may need submitting before it starts:
`api:POST /api/v1/objectives/{id}/submit`. Check the status rather than assuming
creation started the work — this is the same create-is-not-activate shape as
draft envelopes and pending clearances (02.3), and it is the third place in this
part where the platform separates "described" from "in force".

Requests move through `pending` → `claimed` → `in_progress` → `completed`, with
`escalated` and `cancelled` (`sdk:aegis_sdk.RequestStatus`). **`escalated` is the
one to watch**: it means the work reached something it could not decide.

## Watching work

```python
progress = await client.objectives.get_progress(objective_id)
requests = await client.objectives.get_requests(objective_id)
decisions = await client.objectives.get_decisions(objective_id)
artifacts = await client.objectives.get_artifacts(objective_id)
```

`api:GET /api/v1/objectives/{id}/progress`,
`api:GET /api/v1/objectives/{id}/requests`,
`api:GET /api/v1/objectives/{id}/decisions`,
`api:GET /api/v1/objectives/{id}/artifacts`, and the decomposition itself at
`api:GET /api/v1/objectives/{id}/task-graph`.

**Prefer the stream over a polling loop.**
`api:GET /api/v1/objectives/{id}/progress/stream` gives you progress as it
happens. A poll on `get_progress` is the reflex and it costs you both latency and
request budget for a worse signal.

Those four reads answer genuinely different questions, and knowing which one you
want saves time:

| you want to know | read |
| --- | --- |
| how far along is it | progress |
| what is it broken into, and what is stuck | requests |
| what judgments were made, and by whom | decisions |
| what did it produce | artifacts |

`decisions` is the one architects under-use. It is the objective's own account of
what was decided along the way, and it is where a surprising outcome is usually
explained.

## When work needs a person

Requests that need human action surface through the request surface:

```python
await client.requests.claim(request_id)
await client.requests.complete(request_id, ...)
await client.requests.escalate(request_id, ...)
```

`api:POST /api/v1/requests/{id}/claim`,
`api:POST /api/v1/requests/{id}/complete`,
`api:POST /api/v1/requests/{id}/escalate`,
`api:POST /api/v1/requests/{id}/release` to put it back, and
`api:POST /api/v1/requests/{id}/findings` to attach what you found.

**Claim before you work.** A claimed request is one nobody else picks up; an
unclaimed one being worked by two people is the ordinary way duplicate effort
happens. And **release rather than abandoning** — a request claimed by someone
who went on holiday is invisible to everyone else and looks like it is being
handled.

## Sessions — what an agent actually did

```python
session = await client.sessions.get(session_id)
messages = await client.sessions.get_messages(session_id)
```

`api:GET /api/v1/sessions/{id}`, `api:GET /api/v1/sessions/{id}/messages`,
`api:GET /api/v1/sessions/{id}/artifacts`,
`api:GET /api/v1/sessions/{id}/context`,
`api:GET /api/v1/sessions/{id}/subagents`, and live at
`api:GET /api/v1/sessions/{id}/stream`. Your own are at
`api:GET /api/v1/sessions/my`.

Sessions can be paused and resumed —
`api:POST /api/v1/sessions/{id}/pause`, `api:POST /api/v1/sessions/{id}/resume`,
`api:POST /api/v1/sessions/{id}/end` — which is the humane way to stop something
that is going wrong without revoking the agent's trust (02.4). Reach for pause
first; revocation cascades and is not reversible.

## ⚠ A held action ends the run

Carried forward from 01.2 because it changes how you design work: under
`delegated` posture a constraint violation **returns** rather than parking, so a
held action terminates the agent's run instead of queuing it politely.

The practical consequence is that **long autonomous runs and tight envelopes
compose badly**. If a run is going to touch the edge of its envelope, it will
stop there, and everything after that point in the run does not happen. Either
widen the envelope deliberately for that class of work, or decompose the
objective so the boundary-crossing part is its own small request that can be
approved and re-run without discarding an hour of progress.

## Stopping work

`api:POST /api/v1/objectives/{id}/stop` and `client.objectives.cancel(...)`. Stop
the objective rather than the agent when the problem is this piece of work; the
agent is presumably fine and other work depends on it.

> **In the console:** submitting an objective is chapter 05.2, watching it is the
> inbox in 05.3, and a stopped-and-waiting objective is 05.4. Those chapters are
> written for the person doing the work rather than the person who designed the
> system, and they are worth reading if you are deciding what that person will
> meet.

---

*Next: [02.6 — Approvals, holds and evidence](06-approvals-holds-and-evidence.md)*
