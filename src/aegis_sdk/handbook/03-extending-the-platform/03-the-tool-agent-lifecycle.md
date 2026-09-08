# 03.3 — The tool-agent lifecycle, definition to retirement

[Chapter 03.1](01-writing-a-tool.md) drew the line between an in-process tool and a
**registered tool agent**. This chapter is the second one, end to end: what you
declare, what the server fills in, how it becomes callable, what an invocation
gives you back, and how you take it out of service without breaking whatever was
depending on it.

Everything here is `client.tool_agents`, whose module type is
`sdk:aegis_sdk.ToolAgentsModule`. Thirteen operations, and the order you use them
in matters more than any individual one.

> **The working checklist is
> [`coc/skills/registering-a-tool-or-agent.md`](../../coc/skills/registering-a-tool-or-agent.md).**
> That is the artifact to have open while you register something — the order of
> operations, condensed, with the places the order matters. This chapter is the
> explanation behind it: what each object is, what the server decides for you, and
> what each step's evidence does and does not establish. If the two ever disagree,
> one of them is wrong — say so rather than picking.

## The shape of the object

A tool agent is `sdk:aegis_sdk.modules.tool_agents.ToolAgent` — a typed model, so
`agent.id`, not `agent["id"]`. The fields that decide its behaviour:

| field                                                    | why it matters                                                   |
| -------------------------------------------------------- | ---------------------------------------------------------------- |
| `id`                                                     | everything downstream keys on it — grants, policies, invocations |
| `status`                                                 | which lifecycle state it is in; gates whether it can be invoked  |
| `registered_to_role_id`                                  | the **accountable role**; see below                              |
| `capabilities_json`                                      | how a grant flow matches it to a request                         |
| `composition_role`                                       | `standalone`, or a role within a composite                       |
| `parent_composite_id`                                    | set when this agent is a component of another                    |
| `consumer_count`                                         | how many applications currently depend on it                     |
| `model_id`, `temperature`, `max_tokens`, `system_prompt` | its own inference configuration                                  |

Two of those carry more weight than their names suggest, and they are where
registrations go wrong.

## Step 1 — Create, and understand what the two required arguments are for

```python
agent = await client.tool_agents.create(
    name="Cash Position Summariser",
    registered_to_role_id=head_of_treasury_role_id,
    capabilities=["cash_forecasting", "summarise"],
    description="Summarises the overnight cash position from the treasury feed.",
    model_id=os.environ["AEGIS_MODEL"],
    system_prompt="Summarise a cash position. Never advise on a transaction.",
)
```

`api:POST /api/v1/tool-agents`, returning `sdk:aegis_sdk.modules.tool_agents.ToolAgent`.

**`registered_to_role_id` is required, and it is the accountability anchor —
not a piece of metadata.** It names the role that owns this capability. The grant
flow (03.4) matches approvals against it, and the audit trail attributes the
agent's actions through it. An agent registered to the wrong role is not
mis-labelled; it is accountable to the wrong person, and everything downstream —
who approves a grant, whose envelope bounds it, whose name is on the record —
follows the wrong chain. Pick it deliberately.

**`capabilities` must be non-empty, and the server refuses an empty array.** The
reason is worth internalising: a zero-capability agent cannot be matched by the
grant-approval flow, so it is an agent nothing can ever be authorised to call.
The refusal is the platform declining to create an object that could not work. The
SDK accepts either a `list[str]` or a pre-serialised JSON array string and
serialises the list for you.

**Read the returned object rather than assuming it echoes your input.** The
server fills defaults — `temperature`, `max_tokens`, `composition_role`, and the
initial `status`. A default you did not choose is still a default you now own.

**It is created in `draft`.** Nothing can invoke it yet. That is deliberate and it
gives you the next two steps.

## Step 2 — Components, and why they go before the status move

A tool agent can be **composite**: built from other tool agents.

```python
await client.tool_agents.add_component(
    parent.id,
    component_agent_id=child.id,
    role="summariser",
    version_constraint=">=1.2",
)
components = await client.tool_agents.list_components(parent.id)   # confirm; do not assume
```

`api:POST /api/v1/tool-agents/{id}/components`,
`api:GET /api/v1/tool-agents/{id}/components`, and
`api:DELETE /api/v1/tool-agents/{id}/components/{dep}` to remove one. **Cycle
detection is enforced server-side**, so a composition that would loop is refused
rather than accepted and discovered at invocation time.

**Wire components before you move the status, not after.** A status transition is
a governance event: it is recorded, and the record asserts something about the
agent as it stood at that moment. Moving an incomplete agent to `active` and then
completing it means the transition was recorded against a shape that did not yet
exist. The record is not wrong about the transition; it is wrong about what was
transitioned. Land the shape, then move the status.

`version_constraint` is worth using even when there is only one version. It is the
declaration that makes a later component upgrade a decision rather than a surprise.

## Step 3 — Read the envelope, and read it as a bound rather than a description

```python
env = await client.tool_agents.get_envelope_summary(agent.id)
```

`api:GET /api/v1/tool-agents/{id}/envelope-summary`, returning
`sdk:aegis_sdk.modules.tool_agents.ToolAgentEnvelopeSummary`:

| field                                            | what it tells you                                                                                        |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `trust_posture` / `posture_source`               | the posture in force, **and where it came from**                                                         |
| `unit_ceiling` / `unit_ceiling_source`           | the ceiling the containing unit imposes, and its origin                                                  |
| `budget_allocated_usd` / `budget_used_usd`       | the spend envelope and what is left of it                                                                |
| `active_capabilities` / `total_capabilities`     | how many of its declared capabilities are live                                                           |
| `must_rules` / `must_not_rules` / `should_rules` | the constraint counts in force                                                                           |
| `constraint_sources`                             | a list of `sdk:aegis_sdk.modules.tool_agents.ConstraintSource`, each naming a level and its contribution |

**The `_source` fields are the most useful thing on this object and the easiest to
skim past.** They answer "why is this the posture?" — which is the question you
actually have when a posture is not what you set. `constraint_sources` goes
further: it decomposes the envelope by the inheritance level each constraint came
from, so you can see that a bound you did not set came from the unit above.

**The envelope is derived, not declared.** It composes from what contains the
agent, so it can be tighter than anything you set directly, and it can change
without anyone touching this agent — a supervisor tightening their own envelope
tightens this one immediately (02.3). Two consequences:

```
# DO      re-read the envelope after ANY change to what contains the agent
# DO NOT  cache it at registration and treat it as a property of the agent
```

A cached envelope is a claim about the past. On this platform, that specific claim
goes stale by design.

## Step 4 — Move the status deliberately, because some edges are one-way

```python
await client.tool_agents.change_status(agent.id, "active")
```

`api:PATCH /api/v1/tool-agents/{id}/status`. The SDK mirrors the server's
allowlist client-side as
`sdk:aegis_sdk.modules.tool_agents.ALLOWED_TOOL_AGENT_STATUS_TARGETS`, so an
invalid target raises before a request is made:

```
active · suspended · deprecated · revoked · archived
```

**`draft` is not in that set, and its absence is the design.** `draft` is
initial-only: it is where an agent starts and it is never a valid transition
_target_. You cannot put an agent back into draft to "unpublish" it and rework it
quietly. There is no undo edge.

The practical reading, for the five targets that do exist:

- **`active`** — invocable, subject to grants and governance.
- **`suspended`** — temporarily out of service. This is the reach for a
  misbehaving tool; it stops invocations without asserting the agent is finished.
- **`deprecated`** — still there, signalling that consumers should move off.
- **`revoked`** — withdrawn. Reach for this when the agent should not have been
  callable.
- **`archived`** — retired.

The server enforces the transition machine, so an invalid move raises rather than
silently landing. Plan the path before you take the first step.

## Step 5 — Invoke it, and be exact about what a success proves

```python
result = await client.tool_agents.invoke(
    agent.id,
    message="Summarise last night's cash position.",
    application_id=app.id,
)
```

`api:POST /api/v1/tool-agents/{id}/invoke`, returning
`sdk:aegis_sdk.modules.tool_agents.ToolAgentInvocationResult` — the eight-field
shape 03.1 tabulates, of which `verification_zone`, `constraint_status`,
`trust_chain_id`, `cost` and `audit_anchor_id` are the governance half.

**Passing `application_id` changes what the call means.** With it, the invocation
is made _on behalf of an application_, and the platform requires that application
to be active and to hold an active grant for this agent; the application's budget
is what gets consumed. Without it, you are invoking as yourself. Chapter 03.4 is
the grant model, and it is the difference between a tool you can call and a tool
your organisation can call.

**A successful invoke proves the path is live. It does not prove the agent is
correct, and it does not prove anything was governed.** Confirm the record
separately:

```python
history = await client.tool_agents.list_invocations(agent.id)
```

`api:GET /api/v1/tool-agents/{id}/invocations`. **An empty invocation list after a
successful invoke is a finding, not a formality** — it means the call happened and
the record did not, and the record is what an auditor will ask for.

Read `verification_zone` on every result you care about. A `flagged` invocation
succeeded _and_ was surfaced for attention; treating it as a plain success discards
the signal the gradient exists to give you.

## Step 6 — Before you change or retire it, ask who is depending on it

Two reads, one call each, and they answer different questions.

```python
consumers = await client.tool_agents.list_consumers(agent.id)          # who holds a grant
impact = await client.tool_agents.get_impact(agent.id)                  # what breaks
```

`api:GET /api/v1/tool-agents/{id}/consumers` lists the applications granted access,
filterable by `active`, `revoked` or `all`. `api:GET /api/v1/tool-agents/{id}/impact`
is the stronger one: it reports direct composites, **transitive** composites, and
affected applications — the blast radius including the composites you did not know
this agent was inside.

**Run the impact read before deprecating, revoking, or changing a shared tool
agent.** It is the same discipline as revocation impact in 02.4: the operation that
tells you the blast radius exists, it is one call, and the alternative is finding
out afterwards from someone whose workflow stopped.

`consumer_count` on the agent record is a cheap pre-filter — a zero there means
nothing currently holds a grant — but it counts consumers, not composites, so it is
not a substitute for the impact read.

## Updating a live tool agent

```python
await client.tool_agents.update(agent.id, system_prompt="…", max_tokens=8192)
```

`api:PUT /api/v1/tool-agents/{id}` takes any of `name`, `description`,
`composition_role`, `capabilities_json`, `tools_json`, `model_id`, `system_prompt`,
`temperature` and `max_tokens`.

Two of those are governance changes wearing the clothes of configuration:

**Changing `capabilities_json` changes what grants can match.** Capabilities are
how the grant-approval flow finds this agent. Narrowing them can silently strip an
agent out of a matching set; widening them can make it eligible for authorisations
nobody intended. Re-read the consumers after either.

**Changing `system_prompt` changes behaviour with no version to roll back to.**
Unlike an ordinary agent (03.2), a tool agent has no versions endpoint — there is
no `versions` list and no rollback for this object type. If you need the ability to
return to a known prompt, keep it yourself, in the code that provisions the agent,
under source control. This is the strongest argument in this part for provisioning
tool agents from a script rather than by hand.

## Retiring one without breaking its consumers

The order that does not surprise anyone:

1. **`get_impact`** — establish the blast radius, including transitive composites.
2. **`change_status(..., "deprecated")`** — signal, do not sever. Existing consumers
   keep working while they migrate.
3. **Migrate the consumers** — revoke their grants once each has moved (03.4).
4. **`change_status(..., "revoked")` or `"archived"`** — sever.

Skipping straight to `revoked` on an agent with live consumers works exactly as
designed and breaks exactly what the impact read would have named.

## A checklist before you call a registration done

- **Re-read the agent** and compare it to what you intended, field by field, not by
  eyeballing the shape. The server filled defaults you did not choose.
- **Confirm the envelope is the bound you meant**, and that you understand where
  each `_source` points.
- **Confirm one invocation is recorded**, not merely that one succeeded.
- **Confirm the accountable role is right.** This is the hardest one to change
  later and the easiest to get wrong now.
- **Say which credential did the registration.** An agent registered by a key and
  one registered by a session are the same object with different provenance, and
  the provenance is what the audit trail carries. Check yours with
  `api:GET /api/v1/auth/me` — an API key has no role and no personas, ever, which
  also means a large part of the mutating surface may be closed to it (04.1).

## What is not settled

**UNVERIFIED:** whether a tool agent's `status` is re-checked at invocation time or
only at grant time. Moving an agent to `suspended` is the documented way to take it
out of service, and this edition could not establish from the client surface
whether an in-flight or immediately-subsequent invocation is refused. If you are
relying on `suspended` as an incident control, test the latency of it against your
own deployment before you need it.

**UNVERIFIED:** whether a `revoked` or `archived` agent's invocation history remains
readable. The retention question matters for an audit that outlives the agent, and
the client surface does not answer it.

---

_Next: [03.4 — Who may call your tool](04-applications-grants-and-policy.md)_
