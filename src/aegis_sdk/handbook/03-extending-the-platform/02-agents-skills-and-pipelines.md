# 03.2 — Agents, skills and pipelines

Part 02 built the organisation and bounded it. This chapter is about what actually
does the work inside those bounds — the agents themselves, the skills they carry,
and the pipelines that sequence them.

[Chapter 03.6](06-choosing-between-them.md) is the decision between these shapes.
This one is the mechanics of each.

## Agents

```python
agent = await client.agents.create(
    name="Treasury Assistant",
    agent_type="chat",
    workspace_id=org_id,
    model_id=os.environ["AEGIS_MODEL"],
    system_prompt="You assist the Head of Treasury within policy.",
    capabilities=["cash_forecasting", "reporting"],
)
```

`api:POST /api/v1/agents`, returning `sdk:aegis_sdk.Agent`. Note this returns a
typed **model** — `agent.id`, not `agent["id"]` — unlike the standup modules from
02.2. Listing is `api:GET /api/v1/agents`; the ones you can reach are at
`api:GET /api/v1/agents/accessible`, returning
`sdk:aegis_sdk.core.agents.AccessibleAgent` records.

**Never hardcode a model name.** Read it from configuration, as above. A model
string baked into a provisioning script outlives the model.

### `agent_type` is a narrower field than it looks

`sdk:aegis_sdk.AgentType` accepts nine values, and **only four of them are
creatable**: `chat`, `task`, `pipeline`, `custom`. The other five — `shadow`,
`pseudo`, `tool`, `esa`, and the forward-compatibility sentinel `unknown` — are
minted server-side by internal generators and appear on _read_, never on _write_.
The creatable subset is exposed as `sdk:aegis_sdk.types.CREATABLE_AGENT_TYPES`, and
the SDK rejects a non-creatable value client-side before a request is made rather
than round-tripping a doomed one.

The asymmetry is deliberate: a read model has to accept everything the server can
persist, or `agents.list()` raises on any organisation that has a shadow agent in
it. If you are writing code that branches on `agent_type`, handle the read values —
you will meet them.

**`unit_type` is a different domain from `agent_type` and they are easy to
conflate.** `sdk:aegis_sdk.UnitType` is `atomic` or `composite`, the work-unit
classification; `agent_type` is behavioural. Sending `agent_type="atomic"` is a
mistake the type system will not catch for you, because both are strings on the
wire.

`sdk:aegis_sdk.AgentStatus` carries six values — `draft`, `active`, `archived`,
`deprecated`, `suspended`, `revoked` — and all six are reachable. An agent your
listing has never shown you in `suspended` is one your organisation has not needed
to suspend yet.

### Delegate agents — the shape that matters for governance

A **delegate agent** stands in for a human in a role. This is the configuration
that connects the agent to the org structure, and getting it right at creation is
what makes trust, envelopes and audit line up later:

```python
agent = await client.agents.create(
    name="Treasury Assistant",
    agent_type="chat",
    workspace_id=org_id,
    model_id=model_id,
    system_prompt="You assist the Head of Treasury within policy.",
    is_shadow_agent=True,
    shadow_for_user_id="user_head_treasury",
    human_role_id=head_role_id,
    organization_unit_id=unit_id,
)
```

The four fields at the bottom are the ones that matter. Without them you have an
agent that exists but is not anybody's delegate: it sits outside the reporting
chain, so trust chains do not flow to it (02.4), envelopes defined on its role do
not reach it (02.3), and its actions attribute to nothing in particular in the
audit trail.

**Prefer the dedicated path**, which takes the role and derives the rest:

```python
result = await client.agents.create_delegate_agent(role_id=head_role_id)
```

`api:POST /api/v1/delegate-agents`, returning
`sdk:aegis_sdk.core.agents.DelegateAgentCreateResult` — which is `{agent, role,
trust_chain}`. **It establishes the trust chain as part of the call**, which is the
real reason to prefer it: the hand-rolled version above creates an agent and leaves
you to remember 02.4.

Two server-side constraints will refuse it, and each is a governance rule rather
than a validation quirk:

- **The role must RESOLVE, and must belong to your tenant.** A `role_id` that
  names nothing, or names a role in another organisation, raises
  `sdk:aegis_sdk.ValidationError`. Note what this checks: that the role exists
  and is yours — not that anybody sits in it.
- **External and board roles receive governance-only agents**, not operational
  ones. A director's delegate can observe, approve and audit; it does not act.

### ⛔ A vacant role is ACCEPTED, and a previous revision of this page said otherwise

**A role with no human occupant is the ordinary case, not an error state.** Team
lead seats are routinely created before anyone is appointed to them, and a
deployment can legitimately run with every lead role vacant.

Earlier revisions of this page listed "the role must not be vacant" as a third
refusal. **That rule is retracted** and the server no longer enforces it —
neither on creation, nor on `POST /api/v1/trust/establish`, nor on activation.
What survives is the resolvability check above, which is a different question.

The retraction matters because the old rule was a **one-way door**. Vacating a
role suspended its delegate agent, and the gate then refused to bring it back
until a human was seated — so a role whose occupant left could not be re-enabled,
and a seat that was never filled could not be enabled at all. An agent could be
created and never completed: permanently `draft`, with no trust chain.

If you are running against a deployment that still refuses a vacant role, you are
on a build that predates the retraction. **Do not design around it** — the
workarounds all involve seating a placeholder human, which puts a fictitious
person in your audit trail. Upgrade the deployment instead.

**Do not pre-check occupancy client-side.** An SDK caller that refuses to call
because `is_vacant` is true is blocking a request the API now accepts.

Activate and deactivate with
`api:POST /api/v1/delegate-agents/{id}/activate` and
`api:POST /api/v1/delegate-agents/{id}/deactivate`, and see them all at
`api:GET /api/v1/delegate-agents`.

Recall from 02.2 that **`roles.create(auto_generate_agent=True)` is the default**,
so a role may already have its delegate. Check before creating a second one — the
call will not stop you.

### Versions — cut one before you change a production agent

```python
await client.agents.versions.create(agent.id, changelog="Tightened the refusal wording.")
```

`api:GET /api/v1/agents/{id}/versions` to list,
`api:GET /api/v1/agents/{id}/versions/{v}` to read one,
`api:POST /api/v1/agents/{id}/versions` to cut one, and
`api:POST /api/v1/agents/{id}/versions/{v}/rollback` to go back — which returns the
`sdk:aegis_sdk.Agent` at that version.

**Cut a version before you change a production agent's prompt or configuration.**
Rollback is the cheap way out of a bad prompt, and it only exists if you made the
version. The `changelog` argument is optional and you should always pass it: the
version number tells you _that_ something changed, and only the changelog tells you
what you were trying to do.

This surface is one of the real differences between an agent and a tool agent
(03.3), which has no versioning at all.

### Contexts and tools

Contexts carry named configuration an agent works within:
`api:GET /api/v1/agents/{id}/contexts` and
`api:POST /api/v1/agents/{id}/contexts`, which takes a `name`, a `content_type`
(`text`, `file` or `url`) and the `content` itself; `is_active` defaults to true.

Tools attached to an agent are at `api:GET /api/v1/agents/{id}/tools` and
`api:POST /api/v1/agents/{id}/tools`, on
`sdk:aegis_sdk.core.agents.AgentToolsModule`. The attach call takes a `tool_type`,
a `name` and a `description`, plus an optional `config`:

```python
await client.agents.tools.add(
    agent.id, tool_type="mcp", name="search", description="Search the docs.", config={...}
)
```

`tool_type` is the shape of the tool — `mcp`, `function`, `api`. Attachments are
updatable at `api:PUT /api/v1/agents/{id}/tools/{tool_id}` and removable at
`api:DELETE /api/v1/agents/{id}/tools/{tool_id}`.

There is a second route to the same place: `tools_json` on the create payload,
which carries a tool configuration array at creation time. Prefer the attachment
calls for anything you will change later — an attachment has an id, and a JSON blob
does not.

### Running one

`api:POST /api/v1/agents/{id}/execute`, or
`api:POST /api/v1/agents/{id}/execute/stream` for streamed output.

```python
result = await client.agents.execute(agent.id, message="Summarise the position.")
```

**This is a synchronous chat-completion call, and three properties follow from
that.** The body key is `message`, not `objective`. There is no wait-or-poll
concept: the call either completes or raises. And `context` here is a dict injected
into the agent's system prompt for this call — not the persisted `contexts`
resource above, which is a different thing with a confusingly similar name.

`thread_id` is yours to supply for correlation; the server generates one if you do
not. The streaming variant emits Server-Sent Events, each carrying its kind under
the key `type`.

> ⛔ **Correction to an earlier edition.** This chapter previously stated that
> executions are listed at `api:GET /api/v1/agents/{id}/executions` and cancellable
> at `api:POST /api/v1/agents/{id}/executions/{eid}/cancel`. **Those calls return
> 404, and so does `api:GET /api/v1/agents/{id}/executions/{eid}`.** The SDK carries
> an explicit warning on each of the three. Agent execution is synchronous and is
> **not persisted as an individually-addressable record**, so there is nothing to
> poll, list, or cancel — the result comes back from `execute` and that is the only
> place it exists.
>
> The methods remain on the client, which is why the earlier claim looked
> well-grounded: **a method existing is not the same as an operation being served.**
> That is the exact limit the handbook's own anchor check names — a resolving
> `api:` anchor proves this client declares the operation, never that the server
> answers it. Three anchors in one paragraph, all resolving, all 404.

For most work you do not call execute directly — you submit an objective (02.5) and
let the platform dispatch. Direct execution is for testing and for cases where you
are the orchestrator.

Test before you ship: `api:POST /api/v1/agents/{id}/test-draft` exercises a draft
without putting it in front of anyone, and without persisting the draft. Chapter
03.5 covers it and what it does and does not prove.

`api:POST /api/v1/agents/{id}/duplicate` forks an agent — the right move for trying
a variant without touching the original.

## Skills

A skill is a reusable capability you attach to agents rather than re-describing per
agent. It is **content**, not execution: markdown instructions plus a declared list
of required tools.

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

`api:POST /api/v1/skills`;
`api:POST /api/v1/skills/agents/{id}/skills` assigns and
`api:GET /api/v1/skills/agents/{id}/skills` lists what an agent has.

**`category` is required**, and it is validated against a fixed set the SDK exposes
as `sdk:aegis_sdk.core.skills.VALID_SKILL_CATEGORIES` — `coding`, `data`, `web`,
`file`, `reasoning`, `custom`. The SDK checks it client-side and raises
`sdk:aegis_sdk.ValidationError` with an actionable message rather than letting the
server return an opaque 422. There is no `config` field on this surface, and the
older `skill_type` vocabulary is not what the endpoint reads.

`priority` on the assignment is an ordering, `0` being highest, and must be `>= 0`.
Assigning the same skill twice raises rather than silently re-ordering.

The skills module is the fuller CRUD surface in this part — `list`, `create`,
`get`, `update`, `delete`, `duplicate`, and `get_by_name`. `list` filters on
`category`, `is_public` and a `search` substring.

**`get_by_name` returns `None` rather than raising** when nothing matches, which
makes it the obvious primitive for an idempotent provisioning script:

```python
skill = await client.skills.get_by_name("cash-forecasting")
if skill is None:
    skill = await client.skills.create(name="cash-forecasting", category="reasoning", ...)
```

That is the create-if-missing pattern 02.2 had to hand-roll for units. **⚠ But it
is a client-side scan over a bounded listing, not a server-side lookup**, so in an
organisation with more skills than that window an existing skill can sit outside it,
`get_by_name` returns `None`, and the script above creates a duplicate. Nothing
errors. 03.6 has the full treatment and the mitigation — keep your own name→id
registry once you are past a handful.

`duplicate` (`api:POST /api/v1/skills/{id}/duplicate`) is the honest way to fork a
skill for a variant rather than editing the shared one and surprising every agent
that had it.

## Pipelines

Pipelines compose multi-step work: `client.pipelines`, with `sdk:aegis_sdk.Pipeline`,
`sdk:aegis_sdk.PipelineNode` and `sdk:aegis_sdk.PipelineConnection` describing the
graph, and `sdk:aegis_sdk.PipelinePattern` naming the composition shapes available:

```
sequential · parallel · conditional · iterative · fallback
routing · ensemble · saga · event_driven
```

`api:POST /api/v1/pipelines` creates one, `api:GET /api/v1/pipelines` lists them.

### What nodes can I use? Ask the deployment — never carry a list

**No number of node types belongs on this page, and none would survive.** The
catalogue is the built-in types PLUS every node type your deployment's packs
added, intersected with what that deployment permits on its canvas — so the same
client against two deployments sees two different sets, and a node type this
SDK never names can exist on yours. A count copied from someone else's
deployment, or from an earlier release of your own, is a wrong answer given
confidently.

Ask at runtime:

```python
catalog = await client.pipelines.list_node_types()
for node in catalog.flat:
    print(node.type, "—", node.label)
```

`api:GET /api/v1/pipelines/node-types`, requiring the same `agents:read` as
reading pipelines, and returning `sdk:aegis_sdk.NodeTypeCatalog`.

**It carries two counts because they answer different questions.** `total_types`
is the **palette** — what this deployment offers on its canvas. `node_types`
covers the **whole pipeline vocabulary**, including types the palette withholds,
each carrying its own verdict: `executable`, `reason`, and `fabricates`.

⛔ **Read the verdicts before you wire a graph. A type can be recognised, appear
in the catalogue, and still refuse to run** — validation and execution ask
different questions (03.2's `validate` section below is the same split). The
verdicts are per-type on `sdk:aegis_sdk.NodeTypeVerdict`, and the catalogue-wide
`executable` / `unavailable_reason` state it once for the whole palette when the
deployment cannot run its own — which is a real configuration, not a defect
report: a deployment whose palette holds only connector-shaped nodes answers
`executable: False` and explains that the default compiled executor has no SDK
binding for them.

**`fabricates` is the field that matters most, and it is not a synonym for
`executable: False`.** It separates the two ways a node fails to run:

- `fabricates: False` — a **loud** failure. The run stops and names the node.
- `fabricates: True` — a **silent** one. The node emits a diagnostic string **as
  its output** and feeds it downstream, so the pipeline completes carrying a
  plausible-looking result built on an error message.

Any surface that renders those two identically is how a fabricated result
reaches a client. Read `fabricates: True` as _unusable_, not as _unavailable_.

### From the catalogue to a running graph

Discovery on its own builds nothing. The order that avoids learning things late:

```python
catalog = await client.pipelines.list_node_types()

# 1. Filter BEFORE building. A graph assembled from non-executable types
#    passes validate() and then refuses at RUN time — a slow way to learn
#    what the catalogue already said.
runnable = {n for n, verdict in catalog.node_types.items() if verdict.executable}

# 2. Build from `runnable`. create() takes id + name + node_type.
pipeline = await client.pipelines.create(
    name="Draft",
    pattern="sequential",
    nodes=[
        {"id": "n1", "name": "Topic", "node_type": "input"},
        {"id": "n2", "name": "Draft", "node_type": "agent", "agent_id": some_agent_id},
        {"id": "n3", "name": "Result", "node_type": "output"},
    ],
    connections=[
        {"source_node_id": "n1", "target_node_id": "n2"},
        {"source_node_id": "n2", "target_node_id": "n3"},
    ],
)

# 3. Validate, and read the WARNINGS as well as `valid`.
report = await client.pipelines.validate(pipeline.id)

# 4. Only then run.
execution = await client.pipelines.execute(pipeline.id, inputs={"topic": "..."})
```

A working version of exactly this ships as `build_a_pipeline.py` under
`examples/` — it prints your deployment's verdicts first, and stops with the
catalogue's own explanation rather than assembling a graph that cannot run.

**Two failure modes this ordering avoids**, each of which costs an afternoon when
you build first and ask afterwards:

- A graph built from **non-executable types validates clean** and refuses at
  execution, because validation and execution ask different questions.
- An `agent` node with **no `agent_id`** is a valid graph that resolves to no
  agent at run time.

Both are the same lesson as the verdict list above: the catalogue answers "will
this run?" and `validate` answers "is this wired?", and only the first is cheap.

### ⚠ The create path and the graph-save path take different node shapes

This is the one thing in this section most likely to cost you an afternoon.

`pipelines.create(nodes=[...])` builds `sdk:aegis_sdk.PipelineNode`, which requires
`id`, `name` and `node_type`. `api:PUT /api/v1/pipelines/{id}/graph` — the editor's
save path — takes nodes requiring `node_type` and **`label`**, with `id` optional,
plus optional `agent_id`, `position_x`, `position_y` and `config`.

```python
# create() — needs id + name + node_type
{"id": "n1", "name": "Research", "node_type": "agent", "agent_id": "agent_1"}

# save_graph() — needs node_type + label
{"id": "n1", "label": "Research", "node_type": "agent", "agent_id": "agent_1"}
```

A node dict that works in one is rejected by the other, and the difference is a
single field name. Build the graph one way and stay with it.

`save_graph` **replaces the whole graph wholesale** rather than merging, so read
before you write if anything else might have edited it. A cross-pipeline id
collision surfaces as a 409, which the SDK raises as
`sdk:aegis_sdk.ValidationError` rather than an opaque 500 — a useful, specific
error, and worth recognising.

Connections take `source_node_id` and `target_node_id`, with optional
`source_handle`, `target_handle` and a `condition`.

### Validating and running

```python
report = await client.pipelines.validate(pipeline.id)
result = await client.pipelines.execute(pipeline.id, inputs={"topic": "cash"})
```

`api:POST /api/v1/pipelines/{id}/validate` returns a raw dict —
`{"valid": bool, "errors": [...], "warnings": [...]}` — and checks node
connectivity, missing configuration, circular dependencies and agent
availability. **Run it before every execution of a graph you have edited**;
it is the cheapest check in this part.

⛔ **`report["valid"]` being `True` does not mean the graph is free of every
real risk.** By deliberate severity contract, several defect classes are
reported as `warnings` rather than `errors`, and a warning never flips
`valid` to `False`:

- a node bound to an agent id with **no trust posture configured at all**
  (fail-closes to `pseudo` at execution — refused, but for a different reason
  than a posture deliberately set low)
- a node bound to an agent **already at `pseudo`** (refused at execution; the
  graph did not change, the agent's posture did)
- an approval gate with **no outbound edges at all** (indistinguishable from
  an unfinished draft, so it is not condemned as broken)
- an approval gate with **no timeout configured** (an unanswered approval
  holds the run open indefinitely)
- an **agent node with no outbound edge** (a legitimate terminal step, but
  also indistinguishable from a graph nobody finished wiring — a run ending
  there records no outcome)

Two related classes ARE hard errors and do flip `valid` to `False`: a node
type with **no execution handler that the run can actually reach**, and an
agent binding that **resolves to no agent in the organization** — the second
of these previously read back as a silent `valid: true` and is the confirmed
root cause of the partner-reported symptom _"validate returns `valid: true`
... over graphs carrying ... an agent id that resolves on no agent route"_.

**If your acceptance criterion is "nothing could possibly go wrong", check
`report["warnings"]` too, not only `report["valid"]`.** A pipeline that
validates clean can still refuse at execution time on a posture that changed
between the two calls — posture is read from a mutable store, not from the
graph — which is why that class is a warning rather than an error: the graph
itself did nothing wrong.

`execute` starts the run at `api:POST /api/v1/executions/start`, which answers only
once the run has finished, then reads the run record back from
`api:GET /api/v1/pipelines/{id}/executions/{eid}`. It returns
`sdk:aegis_sdk.PipelineExecution`, carrying `status` (a
`sdk:aegis_sdk.ExecutionStatus`), `outputs`, `error`, `node_results`,
`duration_ms`. `node_results` is the field to read when a pipeline half-worked: it
is per-node, so it tells you _where_ it stopped rather than only that it did.

Unlike agent executions, **pipeline executions are individually addressable**:
`api:GET /api/v1/pipelines/{id}/executions` lists them and
`api:POST /api/v1/pipelines/{id}/executions/{eid}/cancel` cancels one. The
listing's `status` filter is applied by the SDK across every page, because the
route itself does not filter. `execute`'s `wait` argument is deprecated: the
server has no asynchronous mode, so it changes nothing, and passing it warns.

`api:POST /api/v1/pipelines/{id}/duplicate` forks a pipeline, which is how to try a
change to a graph other work depends on.

**Reach for a pipeline when the _shape_ of the work is fixed and known in advance.**
Reach for an objective (02.5) when it is not — objectives decompose themselves, and
a pipeline that encodes a decomposition the platform would have derived is a
maintenance burden you chose.

## Tool agents and task agents

Two further kinds, each with its own surfaces and its own governance. Both get full
treatment elsewhere in this part; the summary here is so you recognise which is
which.

- **Tool agents** — `api:GET /api/v1/tool-agents`, `api:POST /api/v1/tool-agents`,
  composed of components (`api:POST /api/v1/tool-agents/{id}/components`) and
  invoked at `api:POST /api/v1/tool-agents/{id}/invoke`. Two reads matter before
  you change one: `api:GET /api/v1/tool-agents/{id}/consumers` tells you who
  depends on it, and `api:GET /api/v1/tool-agents/{id}/impact` tells you what
  breaks if you change it — including transitive composites. Its bounds are
  summarised at `api:GET /api/v1/tool-agents/{id}/envelope-summary`. Full lifecycle:
  [03.3](03-the-tool-agent-lifecycle.md). Who may call it:
  [03.4](04-applications-grants-and-policy.md).
- **Task agents** — `api:GET /api/v1/task-agents`, `api:POST /api/v1/task-agents`,
  with `api:POST /api/v1/task-agents/{id}/test`. A delegation target another agent
  hands work to. **Its `posture_ceiling` defaults to `delegated`** — the most
  autonomous posture, and the one permissive default in this part. Set it down
  deliberately; [03.6](06-choosing-between-them.md) has the detail.

**Check consumers and impact before editing a shared tool agent.** It is the same
discipline as revocation impact in 02.4: the operation that tells you the blast
radius exists, it is one call, and the alternative is finding out afterwards.

## External agents — the boundary case

`api:GET /api/v1/external-agents`, `api:POST /api/v1/external-agents`, invoked at
`api:POST /api/v1/external-agents/{id}/invoke`, with an invocation history at
`api:GET /api/v1/external-agents/{id}/invocations`.

**These live on `client.integrations`** (`sdk:aegis_sdk.IntegrationsModule`), not on
a module of their own — worth knowing, because looking for `client.external_agents`
finds nothing.

They reach something outside your deployment, so they carry credentials and budget
of their own. Treat registering one as a security change rather than a
configuration change: it is the point where your governed organisation acquires an
edge to a system it does not govern. **Their four limit fields default to `-1`,
meaning unlimited** — [03.6](06-choosing-between-them.md) covers the sentinel and
why you must never compare it numerically.

## Drift

Agents drift — behaviour moves away from what was configured and approved.
`api:GET /api/v1/agentic/agents/{id}/drift` for one agent,
`api:GET /api/v1/agentic/drift/alerts` for the tenant, with
`api:POST /api/v1/agentic/agents/{id}/drift/escalate` and
`api:POST /api/v1/agentic/agents/{id}/drift/recover`.

This is a monitoring surface most deployments never wire up, and it is the one that
answers "is this agent still doing what we approved?" — a question the trust
posture (02.4) assumes someone is asking, and which no test suite can answer for
you (03.5).

---

_Next: [03.3 — The tool-agent lifecycle](03-the-tool-agent-lifecycle.md)_
