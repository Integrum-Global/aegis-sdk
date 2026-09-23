# 03.6 — Choosing between a tool, a skill, an agent and a pipeline

This part has described six extension shapes. They overlap enough that a reader can
build almost anything with almost any of them, and differ enough that the wrong
choice is expensive to unwind six months later. This chapter is the decision.

Read it before you build, not after. Every one of these shapes is cheap to create
and none is cheap to migrate off, because what accumulates around them — grants,
policies, invocation history, audit records, other people's dependencies — does not
migrate with them.

## The six shapes, in one table

| shape               | is                                              | identity | governed at                 | reusable across agents         |
| ------------------- | ----------------------------------------------- | -------- | --------------------------- | ------------------------------ |
| **in-process tool** | a function in the agent's runtime               | none     | the tool call, by a hook    | no — it is code in one runtime |
| **skill**           | a reusable instruction attached to agents       | an id    | not directly                | **yes, by design**             |
| **agent**           | a configured worker with a prompt and a model   | an id    | its execution               | n/a                            |
| **tool agent**      | a shared capability others invoke               | an id    | the invoke, by the platform | **yes, via grants**            |
| **task agent**      | a delegation target another agent hands work to | an id    | its own posture ceiling     | yes                            |
| **pipeline**        | a fixed multi-step graph                        | an id    | per node                    | the graph is the reuse         |

The column that decides most arguments is the fourth. **A skill is not governed at
its own boundary** — it shapes what an agent does, and the agent's governance is
what applies. A tool agent _is_ governed at its boundary, which is why it costs
more to set up and why it is the right answer whenever the capability is shared.

## The four questions, in order

Work down this list. The first one that answers decides.

### 1. Does more than one thing need to invoke it, with its own bounds?

**Yes → a registered tool agent** (03.3, 03.4).

This is the single strongest signal in the chapter. The moment a capability has two
consumers who need different limits — different budgets, different postures,
different data in scope — you need an object that can hold per-consumer bounds, and
the tool agent plus grant plus invocation policy is that object. Nothing else here
can express "the same capability, bounded differently per caller".

The tell that you got this wrong: you are about to create a second, nearly-identical
copy of something because a second consumer needs slightly different limits.

**No, only one agent uses it → keep going.**

### 2. Is it _behaviour the agent performs_, or _instructions the agent follows_?

**Instructions → a skill.**

A skill is content: markdown instructions plus a declared list of required tools,
attached to agents by assignment. It changes how the agent approaches a job. It does
not execute anything itself. If what you want to add is "the agent should approach
cash forecasting this way", that is a skill and it will be simpler than anything
else you could reach for.

**Behaviour → keep going.** If what you want to add is "the agent can now query the
treasury feed", instructions cannot do it. Something has to run.

### 3. Does it run inside the agent's own process, or is it called across a boundary?

**Inside → an in-process tool** (03.1). No registration, no id, no lifecycle. The
hook governs the call. This is the lightest thing in this part and it is the right
answer for a capability one agent uses and nobody else needs to discover, audit
separately, or invoke on its own.

**Across a boundary, and the thing on the other side is outside your deployment →
an external agent.** `api:POST /api/v1/external-agents`, on
`sdk:aegis_sdk.IntegrationsModule` — `client.integrations.create_external_agent(...)`.
See § External agents below; it is a security decision, not a configuration one.

**Across a boundary, and it is another agent doing work for this one → a task
agent** (see below).

### 4. Is the _shape_ of the work fixed and known in advance?

**Yes, and it is multi-step → a pipeline.** A declared graph of nodes and
connections, with a composition pattern.

**No → an objective** (02.5). Objectives decompose themselves. A pipeline that
encodes a decomposition the platform would have derived is a maintenance burden you
chose: every change to the work becomes a change to the graph.

This is the one place in this chapter where the right answer is frequently "none of
these" — reach for a pipeline when you can draw the steps on a whiteboard and be
confident they will still be those steps next quarter.

## Skills, in more detail — and one trap

```python
skill = await client.skills.create(
    name="cash-forecasting",
    category="reasoning",
    description="How this organisation forecasts overnight cash.",
    content_markdown="# Cash forecasting\n1. Read the overnight position…",
    tools_required=["treasury_feed"],
)
await client.skills.assign_agent_skill(agent.id, skill.id, priority=1)
```

`api:POST /api/v1/skills`, then
`api:POST /api/v1/skills/agents/{id}/skills` to assign and
`api:GET /api/v1/skills/agents/{id}/skills` to list what an agent has.

**`category` is required and validated against a fixed set.** The SDK exposes it as
`sdk:aegis_sdk.core.skills.VALID_SKILL_CATEGORIES`:

```
coding · data · web · file · reasoning · custom
```

The SDK checks it client-side and raises `sdk:aegis_sdk.ValidationError` with an
actionable message rather than letting the server return an opaque 422. A skill
created without a valid category is not created at all.

`priority` on the assignment is an ordering, `0` being highest, and must be `>= 0`.
It decides precedence when an agent holds several skills that speak to the same
situation. Assigning a skill twice raises rather than silently re-ordering.

**Skills cannot be forked: there is no skills duplicate route.** The fork convention
this part describes for other objects — `api:POST /api/v1/agents/{id}/duplicate`,
for example — was never implemented for skills, so `skills.duplicate()` raises
`sdk:aegis_sdk.UnsupportedOperationError` rather than answering a 404. To fork a
skill, `get` it and `create` a new one from the same fields; editing the shared one
and surprising every agent that had it is the alternative.

### ⚠ The trap: `get_by_name` scans a window, not the whole set

```python
skill = await client.skills.get_by_name("cash-forecasting")
if skill is None:
    skill = await client.skills.create(name="cash-forecasting", category="reasoning")
```

`get_by_name` returns `None` rather than raising when nothing matches, which makes
it the obvious primitive for an idempotent provisioning script — the
create-if-missing pattern 02.2 had to hand-roll for units.

**But it is a client-side convenience, not a server-side lookup.** It lists skills
and scans the result for a name match, and the listing it scans is bounded. Once
your organisation holds more skills than that window, an existing skill can sit
outside it — `get_by_name` returns `None`, and the script above creates a duplicate.

Nothing errors. You end up with two skills of the same name, agents assigned to
whichever one their provisioning run happened to create, and a change to "the" skill
that reaches half of them.

```
# DO      keep your own registry of provisioned skill ids, keyed by name
# DO NOT  rely on get_by_name as an existence check in a growing organisation
```

If you need create-if-missing at scale, record the id when you create it and look up
by id thereafter. The name is a label; the id is the identity.

## Agents, versions, and the thing to do before you change one

Agents are covered in 03.2. One point belongs here because it is a _choice_, not a
mechanic:

**Cut a version before you change a production agent's prompt or configuration.**
`api:POST /api/v1/agents/{id}/versions` with a changelog, then
`api:POST /api/v1/agents/{id}/versions/{v}/rollback` if the change was wrong.
Rollback is the cheap way out of a bad prompt, and it exists only if you made the
version.

**Tool agents have no version surface.** That asymmetry is a real input to the
choice between them: if the thing you are building will have its prompt tuned
repeatedly by someone who wants an undo, an agent gives you one and a tool agent
does not. For a tool agent, your provisioning script under source control is the
version history, which is another argument for building in code.

## Task agents — the delegation target

```python
agent = await client.task_agents.create(
    name="Invoice Totals Extractor",
    description="Extracts totals from an invoice document.",
    posture_ceiling="supervised",
)
```

`api:POST /api/v1/task-agents`, returning
`sdk:aegis_sdk.modules.task_agents.TaskAgent`. Updated at
`api:PUT /api/v1/task-agents/{id}`, removed at
`api:DELETE /api/v1/task-agents/{id}`, exercised at
`api:POST /api/v1/task-agents/{id}/test` (03.5).

A task agent is a **non-delegate** agent: it does not stand in for a human in a
role, which is what separates it from the delegate agents 03.2 covers. It is a unit
of work another agent hands something to.

**`posture_ceiling` is the field to set deliberately.** It defaults to `delegated` —
the _most_ autonomous posture — which is the one default in this part that is
permissive rather than restrictive. The SDK validates it client-side against
`sdk:aegis_sdk.modules.task_agents.ALLOWED_POSTURE_CEILINGS`:

```
pseudo · supervised · shared_planning · continuous_insight · delegated
```

Set it down to what the work actually needs. A task agent created with defaults is
a delegation target with the ceiling wide open, and the fact that a ceiling exists
does not mean it was chosen.

`authority_level` (`1`–`5`) is **informational and does not gate access** — clearance
does that (02.3). Do not reach for it as a permission.

The `get` path enriches the record with `unit_name` and `reporting_chain`, which
`list` does not carry — so if you are checking where a task agent sits in the
organisation, read it individually rather than from the roster.

## Tool agent versus task agent — the distinction people get wrong

They share the word "agent" and almost nothing else.

|                 | tool agent                                      | task agent                               |
| --------------- | ----------------------------------------------- | ---------------------------------------- |
| **is**          | a capability something else invokes             | a unit of work with a prompt             |
| **has**         | components, consumers, an envelope, invocations | a prompt, a posture ceiling, a test path |
| **called by**   | an application holding a grant                  | another agent, by delegation             |
| **lifecycle**   | `create` → components → `change_status`         | `create` → `test` → `update`             |
| **governed at** | the invoke, with a full verdict                 | its own posture ceiling                  |

The practical test: **does something _outside_ the agent world call it?** An
application, a console, a service — that is a tool agent, and it needs the grant
model. Is it another agent handing off a sub-task? That is a task agent.

Getting this wrong is not fatal but it is expensive: a task agent has no consumers
list, no impact analysis and no grant model, so the day you need to know who depends
on it, there is no call that answers.

## Specialists — the authoring surface

`client.specialist_system` (`sdk:aegis_sdk.SpecialistSystemModule`) is the
agent-authoring console's resource: `api:GET /api/v1/specialist-system/specialists`,
`api:POST /api/v1/specialist-system/specialists`, and
`api:POST /api/v1/specialist-system/specialists/{id}/clone`, returning
`sdk:aegis_sdk.modules.specialist_system.Specialist`.

Two things to know. **Its wire shape is camelCase**, not the snake_case the rest of
this part uses — `systemPrompt`, `planningStrategy`, `budgetLimit`,
`checkpointFrequency`, `timeoutSeconds`. The SDK model accepts either spelling, but
`update_specialist(**fields)` passes your keys through, so use the camelCase names
there. **And the server fills defaults on create** from its own default specialist,
so `create_specialist(name=...)` gives you a fully-configured object whose
configuration you did not choose. Read it back.

This surface is the console's, and it is the least SDK-complete of the six — the
backend exposes considerably more than the specialists resource this module covers.
If you are working here, expect to reach for HTTP directly (04.1) for the
sub-resources.

## External agents — the boundary case

`api:POST /api/v1/external-agents`, on `client.integrations`, returning
`sdk:aegis_sdk.modules.integrations.ExternalAgent`. Invoked at
`api:POST /api/v1/external-agents/{id}/invoke`, with history at
`api:GET /api/v1/external-agents/{id}/invocations`.

```python
ext = await client.integrations.create_external_agent(
    workspace_id=workspace_id,
    name="Support Triage Bot",
    platform="slack",
    webhook_url="https://…",
    auth_type="api_key",
    auth_config={...},
    budget_limit_daily=25.0,
    budget_limit_monthly=500.0,
    rate_limit_per_minute=60,
    rate_limit_per_hour=1000,
)
```

Note the money types here are **floats**, not the decimal strings the applications
module takes (03.4). The two surfaces disagree, and the disagreement is easy to
carry across from one provisioning function to the other. Check the signature.

`platform` is one of `teams`, `discord`, `slack`, `telegram`, `notion` or
`custom_http`; `auth_type` one of `oauth2`, `api_key`, `bearer_token`, `basic`,
`custom` or `none`. The webhook URL is validated server-side against server-side
request forgery.

**Treat registering one as a security change rather than a configuration change.**
It is the point at which your governed organisation acquires an edge to a system it
does not govern. It carries credentials of its own, it reaches outside the
deployment, and the budget and rate limits you set on it are the only bounds on that
edge.

### ⚠ The four limits default to unlimited, expressed as `-1`

`budget_limit_daily`, `budget_limit_monthly`, `rate_limit_per_minute` and
`rate_limit_per_hour` all default to **`-1`, which means unlimited**. So an external
agent registered without them is an ungoverned outbound edge with a credential —
created by a call that looks complete and raises nothing.

Two consequences worth stating separately:

**Set all four, explicitly, every time.** Do not rely on the defaults, and do not
let a provisioning helper omit them.

**Never compare these numerically.** `-1` is smaller than every threshold you will
ever set, so `if agent.budget_limit_daily < warn_at:` fires loudest on precisely the
agent that has _no_ limit. A sentinel drawn from the ordinary numeric range does not
announce itself at the comparison site; test for `== -1` first.
[`coc/guardrails/sentinels-and-defaults.md`](../../coc/guardrails/sentinels-and-defaults.md)
treats this class at length, and it is worth reading before you write any check
over a limit field.

`sdk:aegis_sdk.modules.integrations.ExternalAgentInvokeResult` gives you
`invocation_id`, `trace_id`, `status` and `output`; the per-invocation records
(`sdk:aegis_sdk.modules.integrations.ExternalAgentInvocation`) carry
`execution_time_ms`, `response_code`, `error_message` and `cost` — which is the
surface to watch, because an external agent's failures are outside your deployment
and this is where they become visible inside it.

## The decision, condensed

- More than one consumer, each with its own bounds → **tool agent**.
- Instructions rather than execution → **skill**.
- One agent, in-process, nobody else needs it → **in-process tool**.
- Another agent hands it work → **task agent**.
- Fixed multi-step shape → **pipeline**. Not fixed → **objective**.
- Reaches outside your deployment → **external agent**, and treat it as security.

And one rule that outranks all of them: **if the capability has to be evidenced,
it needs an identity.** An in-process tool has no consumers list, no invocation
history and no impact analysis, so every audit question about it has to be answered
by hand from your own logs. If someone will one day ask "who called this, when,
under what authority, and what did it cost?", build the shape that can answer.

---

_This is the last chapter of part 03. Next: [Part 04 — The API surface](../04-the-api-surface/)._
