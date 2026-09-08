---
name: registering-a-tool-or-agent
description: Stand up a tool agent or task agent against a deployed Aegis — create, wire components, check its envelope, move it through status, and prove it is actually callable.
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/skills/registering-a-tool-or-agent.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


# Registering a tool or an agent

Two distinct things share the word "agent" here and they are not
interchangeable. Establish which you are building before anything else, because
the surfaces do not overlap.

| | **tool agent** (`client.tool_agents`) | **task agent** (`client.task_agents`) |
| --- | --- | --- |
| is | a capability something else invokes | a unit of work with a prompt |
| has | components, consumers, an envelope, invocations | a prompt, a test path |
| lifecycle | `create` → components → `change_status` | `create` → `test` → `update` |

Roster reads: `api:GET /api/v1/tool-agents` and `api:GET /api/v1/task-agents`.
A single agent: `api:GET /api/v1/tool-agents/{id}`.

The handbook chapter *Writing a tool an agent can call* is the prose for the
tool case and is not repeated here. This is the order of operations, and the
places the order matters.

## Before you start — establish you can write at all

Registration is a mutation. The reachability of a *write* is frequently
different from the read beside it, and the probe deliberately does not test
writes — it will not tell you this.

```python
me = await client.auth.get_current_user()
```

If your personas list is empty you are holding an API key, and a large part of
the mutating surface is closed to you regardless of scopes. Read
[the credential guardrail](../guardrails/credential-reachability.md) before you
spend an afternoon on it. **Register with a session unless
you have proven the specific write is key-reachable.**

## Step 1 — Create, and keep the returned id

```python
agent = await client.tool_agents.create(...)
```

Read the created object rather than assuming it echoes your input. The server
applies defaults, and a default you did not choose is still a default you now
own — [the sentinels guardrail](../guardrails/sentinels-and-defaults.md) is about exactly this class.

## Step 2 — Wire components before status, not after

```python
await client.tool_agents.add_component(agent.id, ...)
await client.tool_agents.list_components(agent.id)     # confirm, do not assume
```

**Why the order matters:** a status transition is a governance event. Moving an
incomplete agent forward and then completing it means the transition was recorded
against something that did not yet exist in the shape the record claims. Land the
shape, then move the status.

## Step 3 — Read the envelope, and read it as a bound rather than a description

```python
env = await client.tool_agents.get_envelope_summary(agent.id)
```

That reads `api:GET /api/v1/tool-agents/{id}/envelope-summary`.

The envelope is what this agent may do. It is derived, not declared — it composes
from what contains the agent, so it can be narrower than anything you set
directly, and it can change without anyone touching this agent.

```
# DO      re-read the envelope after any change to what contains the agent
# DO NOT  cache it at registration and treat it as a property of the agent
```

## Step 4 — Move the status deliberately

```python
await client.tool_agents.change_status(agent.id, ...)
```

`draft` is initial-only and is never a valid transition target — you cannot put
an agent back. Plan the path before you take the first step; there is no undo
edge, by design.

## Step 5 — Prove it is callable, and be exact about what the proof covers

```python
await client.tool_agents.invoke(agent.id, ...)        # a tool agent
await client.task_agents.test(agent.id, prompt="…")   # a task agent
```

**A successful invoke proves the path is live. It does not prove the agent is
correct, and it does not prove anything was governed.** Confirm separately that
the invocation appears where it should:

```python
await client.tool_agents.list_invocations(agent.id)
```

That reads `api:GET /api/v1/tool-agents/{id}/invocations`. The status move is
`api:PATCH /api/v1/tool-agents/{id}/status`.

An empty invocation list after a successful invoke is a finding, not a
formality — it means the call happened and the record did not, and the record is
the thing an auditor will ask for.

## Step 6 — Before you call it done

- Re-read the agent. Compare it to what you intended, field by field, not by
  eyeballing the shape.
- Confirm the envelope is the bound you meant.
- Confirm one invocation is recorded.
- Say which credential did the registration. An agent registered by a key and an
  agent registered by a session are the same object with different provenance,
  and the provenance is what the audit trail carries.

## What this skill does not cover

Writing the tool's implementation, or changing what the platform does with it.
That is the handbook's chapter and, past a point, platform work you cannot do
from here.
