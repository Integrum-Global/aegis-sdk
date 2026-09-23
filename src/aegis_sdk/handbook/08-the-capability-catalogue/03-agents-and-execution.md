# 08.3 — Agents and execution

This chapter enumerates **what acts** and **how it is driven**. It is the largest
area in the catalogue: `/agents` alone publishes 47 operations, and the agent
kinds below are genuinely different objects rather than variations on one.

The distinction that organises everything here is between an **agent** — a
durable, governed actor linked to a role — and an **execution** — one bounded run
of one. An agent persists, carries a posture and an envelope, and appears in the
audit spine; an execution is a single act by that agent, with inputs, a status,
and a result. Confusing the two produces the most common category error in this
part of the platform: treating an execution as if it carried authority of its
own.

**Every agent here is bounded by the controls in
[08.5](05-governance-and-trust.md), without exception.** This chapter says what
they can do; that one says what stops them.

## The agent kinds

Five distinct kinds. They are not interchangeable, and choosing the wrong one is
a design error you feel later rather than at create time.

| kind               | what it is                                                                                                  | linked to a role?   |
| ------------------ | ----------------------------------------------------------------------------------------------------------- | ------------------- |
| **Agent**          | The general actor — configured, executable, versioned                                                       | Optionally          |
| **Role agent**     | An agent bound to an organisational role, acting with that role's authority                                 | Yes, definitionally |
| **Delegate agent** | An agent acting on behalf of a role-holder under an explicit delegation                                     | Yes                 |
| **Task agent**     | A narrow agent for one repeated task shape                                                                  | Usually not         |
| **Tool agent**     | A governed wrapper around a capability other agents invoke — see [08.8](08-commercial-and-extensibility.md) | Not directly        |
| **Pseudo agent**   | A human in an agent-shaped slot, reached through a channel                                                  | Yes                 |

The pseudo agent is the one most often missed on a first reading of the platform.
It exists so that a step requiring human judgement occupies the same position in
a workflow as an automated one — the work routes to a person through a channel,
their answer returns in the same shape, and the audit spine records it
identically.
[02.7](../02-working-through-the-harness/07-role-agents-and-re-orgs.md) covers
role agents in depth.

## Agents — the core surface

| capability                    | what it does                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------ |
| **Create / update / delete**  | Standard record lifecycle                                                                        |
| **List / get**                | Enumerate and address agents                                                                     |
| **Duplicate**                 | Copy an agent's configuration as a starting point                                                |
| **Accessible**                | The agents this principal may actually use — RBAC- and authority-capped                          |
| **Status**                    | A live status roll-up across agents                                                              |
| **Summary**                   | One agent's rolled-up state                                                                      |
| **Presets**                   | Prebuilt agent configurations                                                                    |
| **Execute**                   | Run the agent once, synchronously                                                                |
| **Execute (stream)**          | Run it with incremental output — see [04.5](../04-the-api-surface/05-concurrency-and-streams.md) |
| **Execution status**          | Where a run has reached                                                                          |
| **List / get executions**     | The run history for one agent                                                                    |
| **Cancel execution**          | Stop a run in flight                                                                             |
| **Test draft**                | Exercise an unsaved configuration without creating the agent                                     |
| **Analyze objective**         | Ask which agents suit a stated objective                                                         |
| **Versions**                  | Create, list, get and roll back agent configuration versions                                     |
| **Contexts**                  | Attach, update and remove durable context the agent reads                                        |
| **Tools**                     | Attach, update and remove the capabilities the agent may invoke                                  |
| **Subagents**                 | The agents this one may spawn                                                                    |
| **Connectors / data sources** | The external data this agent is wired to — see [08.6](06-knowledge-and-data.md)                  |
| **Trust posture**             | Read, move and evidence this agent's autonomy — see [08.5](05-governance-and-trust.md)           |
| **Register from manifest**    | Create an agent from a declarative manifest, by value or by upload                               |

Entry point: `sdk:aegis_sdk.core.agents.AgentsModule`, with
`sdk:aegis_sdk.core.agents.AgentVersionsModule`,
`sdk:aegis_sdk.core.agents.AgentContextsModule` and
`sdk:aegis_sdk.core.agents.AgentToolsModule` for the three sub-surfaces.

Operations — the core lifecycle: `api:POST /api/v1/agents` ·
`api:GET /api/v1/agents` · `api:GET /api/v1/agents/{id}` ·
`api:PUT /api/v1/agents/{id}` · `api:DELETE /api/v1/agents/{id}` ·
`api:POST /api/v1/agents/{id}/duplicate` ·
`api:GET /api/v1/agents/accessible` · `api:GET /api/v1/agents/status` ·
`api:GET /api/v1/agents/presets` · `api:GET /api/v1/agents/{id}/summary`

Execution: `api:POST /api/v1/agents/{id}/execute` ·
`api:POST /api/v1/agents/{id}/execute/stream` ·
`api:GET /api/v1/agents/{id}/execute/status` ·
`api:GET /api/v1/agents/{id}/executions` ·
`api:GET /api/v1/agents/{id}/executions/{execution_id}` ·
`api:POST /api/v1/agents/{id}/executions/{execution_id}/cancel` ·
`api:POST /api/v1/agents/{id}/test-draft` ·
`api:POST /api/v1/agents/analyze-objective`

Composition: `api:GET /api/v1/agents/{id}/versions` ·
`api:GET /api/v1/agents/{id}/versions/{version_id}` ·
`api:POST /api/v1/agents/{id}/versions` ·
`api:POST /api/v1/agents/{id}/versions/{version_id}/rollback` ·
`api:GET /api/v1/agents/{id}/connectors` ·
`api:GET /api/v1/agents/{id}/data-sources` ·
`api:GET /api/v1/agents/{id}/contexts` ·
`api:GET /api/v1/agents/{id}/contexts/{context_id}` ·
`api:POST /api/v1/agents/{id}/contexts` ·
`api:PUT /api/v1/agents/{id}/contexts/{context_id}` ·
`api:DELETE /api/v1/agents/{id}/contexts/{context_id}` ·
`api:GET /api/v1/agents/{id}/tools` ·
`api:POST /api/v1/agents/{id}/tools` ·
`api:PUT /api/v1/agents/{id}/tools/{tool_id}` ·
`api:DELETE /api/v1/agents/{id}/tools/{tool_id}` ·
`api:GET /api/v1/agents/{id}/subagents` ·
`api:POST /api/v1/agents/register-from-manifest` ·
`api:POST /api/v1/agents/register-from-manifest/upload`

```python
agent = await client.agents.create(
    name="reconciliation-analyst",
    agent_type="role",
    organization_role_id=controller_role_id,
)

result = await client.agents.execute(
    agent_id=agent["id"],
    inputs={"period": "2026-Q3", "ledger": "general"},
)

history = await client.agents.list_executions(agent_id=agent["id"], limit=20)
```

> ⚠ **`api:GET /api/v1/agents` and `api:GET /api/v1/agents/accessible` answer
> different questions.** The first lists what exists; the second lists what this
> principal may drive, capped by RBAC and by authority. Building a picker on the
> first produces a list where selecting some entries returns a refusal — and the
> refusal arrives at execute time, not at list time, which is the worst place for
> a user to meet it.

## Delegate agents

An agent acting on behalf of a role-holder, under a delegation that is itself a
governed record. Distinct from a role agent: a role agent **is** the role's
actor, while a delegate agent acts **for** someone occupying it.

| capability                   | what it does                                      |
| ---------------------------- | ------------------------------------------------- |
| **Create / update / delete** | Standard lifecycle                                |
| **List / get**               | Enumerate delegations                             |
| **For unit**                 | Every delegate agent beneath one unit             |
| **Activate / deactivate**    | Turn a delegation on or off without destroying it |
| **Activity**                 | What this delegate has done                       |
| **Health**                   | Whether it is functioning                         |
| **Trust chain**              | The delegation chain that authorises it           |
| **Dashboard summary**        | A roll-up across delegates                        |

Entry point: `sdk:aegis_sdk.core.agents.AgentsModule` — the delegate surface is
served by the same module.

Operations: `api:POST /api/v1/delegate-agents` ·
`api:GET /api/v1/delegate-agents` ·
`api:GET /api/v1/delegate-agents/{id}` ·
`api:PATCH /api/v1/delegate-agents/{id}` ·
`api:DELETE /api/v1/delegate-agents/{id}` ·
`api:GET /api/v1/delegate-agents/dashboard-summary` ·
`api:GET /api/v1/delegate-agents/for-unit/{unit_id}` ·
`api:POST /api/v1/delegate-agents/{id}/activate` ·
`api:POST /api/v1/delegate-agents/{id}/deactivate` ·
`api:GET /api/v1/delegate-agents/{id}/activity` ·
`api:GET /api/v1/delegate-agents/{id}/health` ·
`api:GET /api/v1/delegate-agents/{id}/trust-chain`

```python
delegates = await client.agents.list_delegate_agents_for_unit(unit_id=finance_id)
health = await client.agents.get_delegate_agent_health(delegate_agent_id=d_id)
```

**Deactivation is not revocation.** A deactivated delegate stops acting; its
trust chain still exists and its past acts remain attributed. If you need the
authority withdrawn rather than paused, that is revocation and it lives in
[08.5](05-governance-and-trust.md).

## Task agents and specialists

Two narrower kinds. A **task agent** is scoped to one repeated task shape. A
**specialist** is a reusable expert configuration that can be cloned into
several agents.

| capability               | task agents | specialists |
| ------------------------ | ----------- | ----------- |
| Create / update / delete | yes         | yes         |
| List / get               | yes         | yes         |
| Test                     | yes         | —           |
| Clone                    | —           | yes         |

Entry points: `sdk:aegis_sdk.modules.task_agents.TaskAgentsModule` and
`sdk:aegis_sdk.modules.specialist_system.SpecialistSystemModule`.

Operations: `api:POST /api/v1/task-agents` · `api:GET /api/v1/task-agents` ·
`api:GET /api/v1/task-agents/{id}` · `api:PUT /api/v1/task-agents/{id}` ·
`api:DELETE /api/v1/task-agents/{id}` ·
`api:POST /api/v1/task-agents/{id}/test` ·
`api:GET /api/v1/specialist-system/specialists` ·
`api:POST /api/v1/specialist-system/specialists` ·
`api:GET /api/v1/specialist-system/specialists/{id}` ·
`api:PUT /api/v1/specialist-system/specialists/{id}` ·
`api:DELETE /api/v1/specialist-system/specialists/{id}` ·
`api:POST /api/v1/specialist-system/specialists/{id}/clone`

## Pseudo agents — humans in an agent-shaped slot

The capability that makes a human step indistinguishable, structurally, from an
automated one. Work routes to a person through a configured channel; their
response returns in the agent response shape.

| capability                     | what it does                                                   |
| ------------------------------ | -------------------------------------------------------------- |
| **Create / update / delete**   | Configure the human-backed slot, its operators and its channel |
| **List / get**                 | Enumerate them                                                 |
| **Test channel**               | Confirm the channel delivers before relying on it              |
| **Route task**                 | Send a task to the human behind the slot                       |
| **Requests**                   | The queue of outstanding human requests                        |
| **Claim / respond / reassign** | The operator-side lifecycle of one request                     |
| **Stats**                      | Queue depth and response behaviour                             |

Entry point: `sdk:aegis_sdk.modules.pseudo_agents.PseudoAgentsModule`, with the
request-queue surface on `sdk:aegis_sdk.modules.pools.PoolsModule`.

Operations: `api:POST /api/v1/work-units/pseudo` ·
`api:GET /api/v1/work-units/pseudo` ·
`api:GET /api/v1/work-units/pseudo/{id}` ·
`api:PATCH /api/v1/work-units/pseudo/{id}` ·
`api:DELETE /api/v1/work-units/pseudo/{id}` ·
`api:POST /api/v1/work-units/pseudo/test-channel` ·
`api:POST /api/v1/work-units/pseudo/{id}/route` ·
`api:GET /api/v1/pseudo-requests` ·
`api:GET /api/v1/pseudo-requests/stats` ·
`api:POST /api/v1/pseudo-requests/{id}/claim` ·
`api:POST /api/v1/pseudo-requests/{id}/respond` ·
`api:POST /api/v1/pseudo-requests/{id}/reassign`

```python
await client.pseudo_agents.test_channel(
    pseudo_agent_id=approver_slot_id,
)
await client.pseudo_agents.route_task(
    pseudo_agent_id=approver_slot_id,
    task={"summary": "Confirm Q3 write-off", "amount_cents": 4_200_00},
)
```

> ⛔ **Test the channel before the work depends on it.** A pseudo agent whose
> channel is misconfigured accepts routed tasks and queues them against a person
> who is never notified. Nothing errors, the queue grows, and the symptom is work
> that sits in `pending` forever with no failure anywhere to point at.

## Pools — how work finds an actor

A pool is a set of agents or operators that work is distributed across, with
claiming, escalation, and load management. This is the routing layer between a
request and whoever handles it.

| capability                         | what it does                                              |
| ---------------------------------- | --------------------------------------------------------- |
| **Create / update / delete**       | Standard lifecycle                                        |
| **Members**                        | Add, list and remove the actors in the pool               |
| **Summaries / user pools**         | Roll-ups, and the pools one user belongs to               |
| **Pending tasks**                  | What is waiting, globally or per pool                     |
| **Claim / release task**           | Take a task, or put it back                               |
| **Extend / cancel claim timeout**  | Manage a held claim's clock                               |
| **Pause / resume / drain**         | Stop intake, restart it, or let the pool finish and empty |
| **Health / statistics / metrics**  | Operational state of the pool                             |
| **Load distribution / rebalance**  | See how work is spread, and redistribute it               |
| **Escalation config**              | What happens when a task is not handled in time           |
| **Pending escalations / escalate** | The escalation queue and manual escalation                |
| **Acknowledge / history / stats**  | The operator side of escalation                           |
| **Utilization**                    | How heavily the pool is used                              |

Entry point: `sdk:aegis_sdk.modules.pools.PoolsModule`. Agent-only pools have a
narrower surface at `sdk:aegis_sdk.modules.agent_pools.AgentPoolsModule`.

Operations — pool lifecycle: `api:POST /api/v1/pools` · `api:GET /api/v1/pools` ·
`api:GET /api/v1/pools/{id}` · `api:PUT /api/v1/pools/{id}` ·
`api:DELETE /api/v1/pools/{id}` · `api:GET /api/v1/pools/summaries` ·
`api:GET /api/v1/pools/user/{user_id}` · `api:GET /api/v1/pools/{id}/members` ·
`api:POST /api/v1/pools/{id}/members` ·
`api:DELETE /api/v1/pools/{id}/members/{member_id}`

Work distribution: `api:GET /api/v1/pools/tasks/pending` ·
`api:GET /api/v1/pools/{id}/tasks/pending` ·
`api:POST /api/v1/pools/tasks/{task_id}/claim` ·
`api:POST /api/v1/pools/tasks/{task_id}/release` ·
`api:POST /api/v1/pools/{id}/operations/extend_timeout` ·
`api:POST /api/v1/pools/{id}/operations/cancel_timeout` ·
`api:POST /api/v1/pools/{id}/operations/rebalance` ·
`api:GET /api/v1/pools/{id}/operations/load_distribution`

Operational control: `api:POST /api/v1/pools/{id}/pause` ·
`api:POST /api/v1/pools/{id}/resume` · `api:POST /api/v1/pools/{id}/drain` ·
`api:GET /api/v1/pools/{id}/health` · `api:GET /api/v1/pools/{id}/metrics` ·
`api:GET /api/v1/pools/{id}/statistics`

Agent pools: `api:GET /api/v1/agent-pools` · `api:POST /api/v1/agent-pools` ·
`api:GET /api/v1/agent-pools/{id}` · `api:PUT /api/v1/agent-pools/{id}` ·
`api:DELETE /api/v1/agent-pools/{id}` ·
`api:GET /api/v1/agent-pools/{id}/members` ·
`api:POST /api/v1/agent-pools/{id}/members` ·
`api:DELETE /api/v1/agent-pools/{id}/role-members/{member_id}`

```python
pending = await client.pools.list_pool_pending_tasks(pool_id=triage_pool_id)
await client.pools.claim_task(task_id=pending["tasks"][0]["id"])

await client.pools.drain_pool(pool_id=triage_pool_id)   # finish, then stop
health = await client.pools.get_pool_health(pool_id=triage_pool_id)

# Agent-only pools are the narrower surface, addressed separately
roster = await client.agent_pools.list_members(pool_id=analysis_pool_id)
```

**Pause and drain are different, and the difference bites during an incident.**
Pause stops the pool acting on anything, including work already claimed. Drain
stops new intake and lets in-flight work finish. Reaching for pause when you
meant drain abandons work mid-execution; reaching for drain when you meant pause
lets the thing you are trying to stop keep running to completion.

## Sessions — stateful, multi-turn work

A session is a durable conversation with an agent: it accumulates messages,
artifacts, context and memory, and it can spawn subagents.

| capability                   | what it does                                        |
| ---------------------------- | --------------------------------------------------- |
| **Create from task**         | Start a session from an existing task               |
| **Initialize agent**         | Start one by naming the agent directly              |
| **Get / list / my**          | Address sessions, all or your own                   |
| **Messages**                 | Read the transcript, or send into it                |
| **Stream messages / events** | Consume the session live                            |
| **Artifacts**                | Attach outputs to the session, or read them         |
| **Context / memory**         | What the session is carrying                        |
| **Subagents**                | Spawn and enumerate child agents inside the session |
| **Pause / resume / end**     | Session lifecycle control                           |

Entry point: `sdk:aegis_sdk.execution.sessions.SessionsModule`.

Operations: `api:POST /api/v1/sessions/from-task` ·
`api:POST /api/v1/sessions/initialize-agent` · `api:GET /api/v1/sessions` ·
`api:GET /api/v1/sessions/my` · `api:GET /api/v1/sessions/{id}` ·
`api:GET /api/v1/sessions/{id}/messages` ·
`api:POST /api/v1/sessions/{id}/messages` ·
`api:GET /api/v1/sessions/{id}/stream` ·
`api:GET /api/v1/sessions/{id}/artifacts` ·
`api:POST /api/v1/sessions/{id}/artifacts` ·
`api:GET /api/v1/sessions/{id}/context` ·
`api:GET /api/v1/sessions/{id}/memory` ·
`api:GET /api/v1/sessions/{id}/subagents` ·
`api:POST /api/v1/sessions/{id}/subagents` ·
`api:POST /api/v1/sessions/{id}/pause` ·
`api:POST /api/v1/sessions/{id}/resume` ·
`api:POST /api/v1/sessions/{id}/end`

```python
session = await client.sessions.create_from_task(task_id=task["id"])
await client.sessions.send_message(session_id=session["id"], content="Proceed.")

async for event in client.sessions.stream_events(session_id=session["id"]):
    handle(event)
```

**A session that is never ended is not merely untidy.** It continues to hold
context and count against whatever the deployment budgets sessions by. End them
explicitly; `pause` is for work you intend to resume.

## Pipelines — declarative multi-step execution

Where a session is conversational, a pipeline is a graph: nodes, connections,
and a deterministic execution order.

| capability                   | what it does                            |
| ---------------------------- | --------------------------------------- |
| **Create / update / delete** | Standard lifecycle                      |
| **Duplicate**                | Copy a pipeline as a starting point     |
| **Save graph**               | Replace the node-and-edge structure     |
| **Node types**               | Which node kinds this deployment offers |
| **Validate**                 | Check the graph before running it       |
| **Execute**                  | Run it                                  |
| **Executions**               | List and get runs                       |
| **Cancel execution**         | Stop a run in flight                    |

Entry point: `sdk:aegis_sdk.core.pipelines.PipelinesModule`.

Operations: `api:POST /api/v1/pipelines` · `api:GET /api/v1/pipelines` ·
`api:GET /api/v1/pipelines/{id}` · `api:PUT /api/v1/pipelines/{id}` ·
`api:DELETE /api/v1/pipelines/{id}` ·
`api:POST /api/v1/pipelines/{id}/duplicate` ·
`api:PUT /api/v1/pipelines/{id}/graph` ·
`api:GET /api/v1/pipelines/node-types` ·
`api:POST /api/v1/pipelines/{id}/validate` ·
`api:GET /api/v1/pipelines/{id}/executions` ·
`api:GET /api/v1/pipelines/{id}/executions/{execution_id}` ·
`api:POST /api/v1/pipelines/{id}/executions/{execution_id}/cancel`

Standalone execution control sits alongside:
`api:POST /api/v1/executions/start` · `api:GET /api/v1/executions/{id}` ·
`api:POST /api/v1/executions/{id}/stop` ·
`api:GET /api/v1/executions/history/{id}`

Registered workflows — the named, reusable graphs a deployment publishes — are
read-only from the client: `api:GET /api/v1/workflows` ·
`api:GET /api/v1/workflows/{id}`. A workflow is what a pipeline is built from;
you enumerate them to discover what the deployment offers, and compose pipelines
against them.

```python
await client.pipelines.validate(pipeline_id=p_id)
run = await client.pipelines.execute(pipeline_id=p_id, inputs={"batch": "2026-09"})
```

## Skills

Reusable capability definitions assigned to agents — what an agent knows how to
do, as distinct from the tools it may call.

| capability                   | what it does                               |
| ---------------------------- | ------------------------------------------ |
| **Create / update / delete** | Standard lifecycle                         |
| **List / get / by name**     | Address skills                             |
| **Duplicate**                | Not served — `get` then `create` instead   |
| **Agent skills**             | List and assign the skills one agent holds |

Entry point: `sdk:aegis_sdk.core.skills.SkillsModule`.

Operations: `api:POST /api/v1/skills` · `api:GET /api/v1/skills` ·
`api:GET /api/v1/skills/{id}` · `api:PUT /api/v1/skills/{id}` ·
`api:DELETE /api/v1/skills/{id}` ·
`api:GET /api/v1/skills/agents/{agent_id}/skills` ·
`api:POST /api/v1/skills/agents/{agent_id}/skills`

⚠ Skills have **no** duplicate route, unlike agents and pipelines, so
`skills.duplicate()` raises `sdk:aegis_sdk.UnsupportedOperationError` rather
than answering a 404.

## Tools

The invocable capabilities, and the validation surface for them.
[03.1](../03-extending-the-platform/01-writing-a-tool.md) is how you write one.

| capability             | what it does                           |
| ---------------------- | -------------------------------------- |
| **List / get / count** | Enumerate what is available            |
| **Categories**         | How tools are grouped                  |
| **Danger levels**      | The risk classification a tool carries |
| **Validate**           | Check a tool definition                |
| **Batch**              | Resolve several tools in one call      |

Entry point: `sdk:aegis_sdk.modules.tools.ToolsModule`.

Operations: `api:GET /api/v1/tools` · `api:GET /api/v1/tools/{id}` ·
`api:GET /api/v1/tools/count` · `api:GET /api/v1/tools/categories` ·
`api:GET /api/v1/tools/danger-levels` · `api:POST /api/v1/tools/validate` ·
`api:POST /api/v1/tools/batch`

```python
available = await client.tools.list(category="data")
levels = await client.tools.danger_levels()
```

**Read `danger_levels` before granting a tool to an agent.** The classification
is what an envelope's Operational dimension is written against, and a tool
attached without regard to it is bounded by whatever the envelope happened to
say.

## Agent-to-agent (A2A)

Discovery and invocation across agent boundaries — including agents this
deployment does not own.

| capability      | what it does                                           |
| --------------- | ------------------------------------------------------ |
| **Discover**    | Find agents matching a capability requirement          |
| **Model card**  | Read one agent's published capability description      |
| **Workers**     | The workers behind an agent                            |
| **Route**       | Pick the right agent for a request without invoking it |
| **Invoke**      | Call one agent                                         |
| **Orchestrate** | Drive a multi-agent interaction                        |

Entry point: `sdk:aegis_sdk.modules.a2a.A2AModule`.

Operations: `api:POST /api/v1/a2a/discover` ·
`api:GET /api/v1/a2a/agent/{agent_id}/card` ·
`api:GET /api/v1/a2a/workers/{agent_id}` · `api:POST /api/v1/a2a/route` ·
`api:POST /api/v1/a2a/invoke` · `api:POST /api/v1/a2a/orchestrate`

```python
candidates = await client.a2a.discover(capability="invoice-extraction")
chosen = await client.a2a.route(task={"kind": "extract", "document_id": doc_id})
result = await client.a2a.invoke(agent_id=chosen["agent_id"], payload=payload)
```

## MCP — model context protocol

Registering external MCP servers and binding their tools into agents.

| capability                            | what it does                                                |
| ------------------------------------- | ----------------------------------------------------------- |
| **Register / update / delete server** | Manage an MCP server registration                           |
| **List / get registrations**          | Enumerate registered servers                                |
| **Bind / bind inline**                | Attach a server's tools to an agent, by reference or inline |
| **List bindings / unbind**            | Manage those attachments                                    |
| **Datasets**                          | Create, list, get, update and delete MCP-exposed datasets   |

Entry point: `sdk:aegis_sdk.modules.mcp.McpModule`.

Operations: `api:GET /api/v1/datasets` · `api:POST /api/v1/datasets` ·
`api:GET /api/v1/datasets/{id}` · `api:PUT /api/v1/datasets/{id}` ·
`api:DELETE /api/v1/datasets/{id}`

```python
reg = await client.mcp.register_server(
    name="ledger-mcp",
    url="https://mcp.internal.example.com",
    transport="http",
)
await client.mcp.bind(agent_id=agent["id"], registration_id=reg["id"])
```

### The three MCP surfaces, and which one you are on

MCP appears at three places in Aegis, and they are different surfaces with
different audiences. Confusing them is the reason a tool you can see from one
side is absent from the other.

| surface                       | what it exposes                                                                                                                                                                                                | audience                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| **External MCP serving**      | **3 tools** — `query_knowledge`, `list_datasets`, `read_dataset`, each with per-tool authorization                                                                                                             | An outside MCP client       |
| **The enterprise MCP server** | Tools for callers inside the organisation, reached under governance rather than from outside                                                                                                                    | Governed enterprise callers |
| **The internal tool bridge**  | **10 tools** — `decompose_objective`, `route_task`, `escalate`, `delegate_to_agent`, `query_knowledge`, `check_directive`, `create_deliverable`, `create_presentation`, `submit_upstream`, `invoke_task_agent` | Agents inside the platform  |

**The external surface is deliberately narrow.** Three read-shaped tools, each
separately authorized — it is knowledge retrieval for an outside client, not a
remote control for the organisation. The ten-tool internal bridge is what agents
inside the platform use to decompose work, escalate, and delegate, and it is not
reachable from outside.

`query_knowledge` appears on both the external surface and the internal bridge,
and it is the same capability under the same clearance rules — an external caller
does not get a wider view of knowledge than an internal agent with the same
clearance would. **The failure mode to expect is an outside integrator asking why
they cannot call `delegate_to_agent`**: it is an internal bridge tool, it was
never externally exposed, and no authorization change reaches it.

## The agentic dashboard

The operator-facing roll-up across everything in this chapter — the inbox, the
activity feed, and agent drift.

| capability                         | what it does                                             |
| ---------------------------------- | -------------------------------------------------------- |
| **Dashboard stats**                | The headline numbers                                     |
| **Inbox**                          | What is waiting for this operator                        |
| **Activity feed**                  | What has been happening                                  |
| **Get / claim / validate request** | The operator lifecycle on one request                    |
| **Pools**                          | Pool state from the operator's view                      |
| **Agent drift**                    | Whether an agent's behaviour has moved from its baseline |
| **Escalate / recover drift**       | Act on a drifting agent                                  |
| **Drift alerts**                   | The queue of drift signals                               |
| **Reasoning traces**               | Why an agent decided what it decided                     |

Entry point: `sdk:aegis_sdk.modules.agentic_dashboard.AgenticDashboardModule`.

Operations: `api:GET /api/v1/agentic/dashboard/stats` ·
`api:GET /api/v1/agentic/dashboard/activity-feed` ·
`api:GET /api/v1/agentic/inbox` · `api:GET /api/v1/agentic/pools` ·
`api:GET /api/v1/agentic/pools/{id}` ·
`api:GET /api/v1/agentic/requests/{id}` ·
`api:POST /api/v1/agentic/requests/{id}/claim` ·
`api:POST /api/v1/agentic/requests/{id}/validate` ·
`api:GET /api/v1/agentic/agents/{agent_id}/drift` ·
`api:POST /api/v1/agentic/agents/{agent_id}/drift/escalate` ·
`api:POST /api/v1/agentic/agents/{agent_id}/drift/recover` ·
`api:GET /api/v1/agentic/drift/alerts` ·
`api:GET /api/v1/reasoning-traces`

```python
inbox = await client.agentic_dashboard.inbox()
drift = await client.agentic_dashboard.get_agent_drift(agent_id=agent["id"])
traces = await client.agentic_dashboard.list_reasoning_traces(agent_id=agent["id"])
```

> **In the console:** the inbox, the activity feed and the drift alerts are the
> three panels an operator lives in.
> [05.3](../05-the-web-console/03-your-inbox.md) covers the inbox screen.

## Summary — what this chapter covered

| area              | entry point                               | scale         |
| ----------------- | ----------------------------------------- | ------------- |
| Agents            | `core.agents`                             | 47 operations |
| Delegate agents   | `core.agents`                             | 12 operations |
| Task agents       | `modules.task_agents`                     | 6 operations  |
| Specialists       | `modules.specialist_system`               | 6 operations  |
| Pseudo agents     | `modules.pseudo_agents` · `modules.pools` | 12 operations |
| Pools             | `modules.pools` · `modules.agent_pools`   | 32 operations |
| Sessions          | `execution.sessions`                      | 17 operations |
| Pipelines         | `core.pipelines`                          | 16 operations |
| Skills            | `core.skills`                             | 8 operations  |
| Tools             | `modules.tools`                           | 7 operations  |
| A2A               | `modules.a2a`                             | 6 operations  |
| MCP and datasets  | `modules.mcp`                             | 5 + binding   |
| Agentic dashboard | `modules.agentic_dashboard`               | 13 operations |

---

_Next: [08.4 — Work and objectives](04-work-and-objectives.md)_
