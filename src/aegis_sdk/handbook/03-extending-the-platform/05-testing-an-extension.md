# 03.5 — Testing an extension before it touches a real organisation

The extension you have built will run inside a governed organisation, with real
roles, real budgets, a real audit trail and real people whose work depends on it.
This chapter is about what you can exercise before that, what each surface
actually proves, and — the part most testing plans get wrong — **what each one
does not prove.**

The organising question, and it is worth asking of every check in this chapter:
_would this have produced a different result if my extension were broken?_ A check
that answers the same way either way is not a test, whatever it printed.

## The four testing surfaces, and what each one covers

| surface                                      | what runs                             | governed?               | writes?    |
| -------------------------------------------- | ------------------------------------- | ----------------------- | ---------- |
| **draft test** (`agents.test_draft`)         | a real model call with unsaved config | no                      | nothing    |
| **task-agent test** (`task_agents.test`)     | a direct model call                   | **no — stated plainly** | nothing    |
| **pipeline validate** (`pipelines.validate`) | a structural check                    | n/a                     | nothing    |
| **the real invoke** (`tool_agents.invoke`)   | the production path                   | **yes**                 | everything |

Read the "governed?" column carefully. **Three of the four testing surfaces bypass
governance.** That is what makes them fast and safe; it is also what makes them
silent about the half of your extension that governance decides. Nothing on this
platform lets you dry-run a governed invocation.

## Testing a draft agent configuration

The most useful of the four, because it separates two things people usually change
together: what the agent is configured to do, and whether that configuration is
saved.

```python
result = await client.agents.test_draft(
    agent.id,
    message="Summarise last night's cash position.",
    draft_system_prompt="You summarise cash positions. Never advise on a transaction.",
)
print(result.content, result.finish_reason)
```

`api:POST /api/v1/agents/{id}/test-draft`, returning
`sdk:aegis_sdk.core.agents.TestDraftResult` — `content`, `model`, `usage`,
`finish_reason`, `thread_id`, `timestamp`, and `is_test`, which is always `True`.

Three properties make it the right tool for prompt iteration:

- **Nothing is written.** The draft prompt and draft instructions are used for this
  call and discarded. The saved agent is untouched, so a colleague using it in
  parallel sees no change.
- **It runs against a separate per-request test budget, capped server-side.** You
  are not spending the agent's production allowance to iterate on wording.
- **`draft_instructions_json` and `draft_system_prompt` substitute for the saved
  ones**, so you can test a change before committing to it.

Two constraints that bite: `conversation_history` entries must be `user` or
`assistant` — a `system` role is rejected server-side, because the system prompt
is what you are testing rather than something you supply. And **an archived agent
cannot be tested**, raising `sdk:aegis_sdk.ValidationError`; if a draft test fails
on an agent you have not touched, check its status before you check your payload.

**What it does not prove:** anything about governance. The verdict, the envelope,
the budget, the audit record — none of them are exercised. A draft test tells you
the model does the right thing when asked. It says nothing about whether the agent
will be _allowed_ to ask.

## Testing a task agent, and the caveat that comes with it

```python
result = await client.task_agents.test(agent.id, prompt="Extract the totals.")
```

`api:POST /api/v1/task-agents/{id}/test`, returning
`sdk:aegis_sdk.modules.task_agents.TaskAgentTestResult` — `agent_id`, `prompt`,
`result`.

**This is a direct model call and it is explicitly not governance-gated.** The SDK
says so in its own documentation of the method, which is the honest thing for it to
do and the thing to carry away from this section. A green task-agent test proves
the prompt produces sensible output. It is evidence about the model, not about the
platform.

`max_turns` is accepted and is reserved for future multi-turn testing; do not build
a multi-turn test plan around it today.

## Validating a pipeline before you run it

```python
report = await client.pipelines.validate(pipeline.id)
```

`api:POST /api/v1/pipelines/{id}/validate`. It checks node connectivity, missing
required configuration, circular dependencies, and agent availability — the four
structural ways a pipeline is wrong before it has done anything.

This is the strongest pre-execution check in this part, because a pipeline is a
declared graph and a graph can be checked. It is also the narrowest: it establishes
that the pipeline _can_ run, never that running it produces the right answer.

Note a genuine hazard in the pipelines module: **the create path and the graph-save
path do not take the same node shape.** `pipelines.create(nodes=[...])` builds
`sdk:aegis_sdk.PipelineNode`, which requires `id`, `name` and `node_type`;
`api:PUT /api/v1/pipelines/{id}/graph` takes nodes requiring `node_type` and
**`label`**, with `id` optional. A node dict that works in one call is rejected by
the other, and the difference is a single field name. Build the graph one way and
stay with it.

## Provisioning a place to test in

Nothing here sandboxes for you. The isolation you get is the isolation you build,
and there are three levels of it.

**Duplicate the object.** Every configurable object in this part has a fork
operation: `api:POST /api/v1/agents/{id}/duplicate`,
`api:POST /api/v1/skills/{id}/duplicate`,
`api:POST /api/v1/pipelines/{id}/duplicate`, and
`api:POST /api/v1/specialist-system/specialists/{id}/clone`. Fork, change the fork,
test the fork. This is the cheapest isolation available and it is the honest way to
try a variant — editing the shared one and surprising every agent that had it is
the alternative.

**Use a separate application.** Create a test application with its own tiny
`budget_monthly`, grant it the agent under a deliberately low `posture_ceiling`,
and invoke through it (03.4). This is the only way to exercise the _governed_ path
without touching a production consumer's budget or bounds — and because the
posture ceiling is yours to set, you can watch the agent be refused on purpose,
which is the most informative test in this chapter.

**Use a separate organisation.** The strongest isolation, and the most work. Stand
up a whole test organisation as 02.2 describes and provision your extension into
it from the same script that provisions production. If the script is the artifact,
both environments are the same artifact with different inputs, which is the entire
argument for building in code rather than by clicking.

## Testing the governed path — the only way there is

There is no dry-run for a governed invocation. To exercise governance, you invoke
for real against a scope you control:

```python
result = await client.tool_agents.invoke(
    agent.id, message="…", application_id=test_app.id,
)
assert result.verification_zone in ("auto_approved", "flagged")
assert result.audit_anchor_id
history = await client.tool_agents.list_invocations(agent.id)
assert history.get("records"), "the call succeeded and the record did not land"
```

The history call returns the raw payload rather than a typed model, so read it
defensively — the assertion above is about the record _existing_, not about a shape
this edition can pin.

Three assertions, and each one is doing distinct work:

- **`verification_zone`** — the actual verdict, not merely that the call returned.
  A `held` or `blocked` zone on a call you expected to succeed is the finding.
- **`audit_anchor_id`** — the record exists and is anchored.
- **the invocation history** — the record is _retrievable_, which is the property an
  auditor depends on and the one a successful call does not by itself establish.

**Test the refusal too, and test it deliberately.** Set the test application's
posture ceiling low, or its per-invocation budget to something a real call will
exceed, and confirm you get `sdk:aegis_sdk.GovernanceViolationError` rather than a
success. A governance configuration that has never refused anything has not been
shown to be capable of refusing anything — and "we never saw it deny" is a
statement about your test inputs, not about your controls.

## The discipline that makes all of this worth anything

**A green check proves nothing until you have seen it go red.** Before you trust a
test as evidence that your extension works, establish that the same test fails when
the extension is broken — remove the grant, drop the posture, point at the wrong
agent id. If it passes both ways, it was never measuring what you thought.

This applies with particular force to refusal tests, because the failure mode is
silent: a test asserting "this is refused" passes identically when the call is
refused for the reason you intended and when it is refused because the agent id was
a typo. Assert on _which_ refusal — the exception type, and the status in
`details["status_code"]` — not merely that one occurred.

Two more habits worth carrying:

**Pair every zero with a positive control.** "No invocations recorded" and "the
history call returned nothing because I passed the wrong id" are the same output.
Prove the call can return non-empty before you read an empty result as a finding.

**Do not read a timeout as a denial.** `sdk:aegis_sdk.ConnectionError` and
`sdk:aegis_sdk.TimeoutError` mean the deployment did not answer. They are not
evidence about permissions, existence, or state — and recording one as a refusal is
how a whole test sweep comes back clean for the wrong reason.

All three habits are the same discipline, and
[`coc/guardrails/reading-a-measurement.md`](../../coc/guardrails/reading-a-measurement.md)
is the artifact for it: name what would have proved you wrong before you cite what
you measured.

## Probing the deployment itself

Before any of the above, establish that the deployment you are pointed at is the
one you think, and that you can reach it:

```
python -m aegis_sdk.coc.probe --base-url https://<your-deployment>
```

`sdk:aegis_sdk.coc` ships this alongside the handbook; the working procedure around
it is
[`coc/skills/working-against-a-deployment.md`](../../coc/skills/working-against-a-deployment.md).
**The probe deliberately does not test writes**, and that limitation is
load-bearing for this part: the reachability of a _write_ is frequently different
from the read beside it, so a clean probe tells you nothing about whether you can
register anything.

Establish the write side yourself, cheaply, before you start:

```python
me = await client.auth.get_current_user()
```

`api:GET /api/v1/auth/me`. **If your personas list is empty you are holding an API
key**, and a large part of the mutating surface is closed to it regardless of
scopes — a documented open defect covered in 04.1. Register with a session unless
you have proven the specific write is key-reachable. Discovering this at the end of
a provisioning script is the expensive way, and
[`coc/guardrails/credential-reachability.md`](../../coc/guardrails/credential-reachability.md)
is the cheap one.

## After it ships — watching for drift

Testing establishes behaviour at a moment. Agents drift: behaviour moves away from
what was configured and approved, without anything changing in the configuration.

- `api:GET /api/v1/agentic/agents/{id}/drift` — one agent.
- `api:GET /api/v1/agentic/drift/alerts` — the tenant.
- `api:POST /api/v1/agentic/agents/{id}/drift/escalate` and
  `api:POST /api/v1/agentic/agents/{id}/drift/recover` — the responses.

This is the surface most deployments never wire up, and it answers the question
your test suite structurally cannot: _is this still doing what we approved?_ A
trust posture (02.4) assumes someone is asking it. If nobody is, the posture is a
statement about the day it was set.

## A pre-flight checklist

1. **`auth/me`** — which credential am I holding, and can it write?
2. **The probe** — is the deployment reachable and the one I meant?
3. **Draft-test the prompt** — does the model do the right thing, unsaved?
4. **Validate the structure** — for a pipeline, does the graph hold together?
5. **Invoke through a test application** — does the _governed_ path work?
6. **Invoke past a deliberate bound** — does it refuse, and with the right error?
7. **Read the invocation history** — is the record retrievable, not merely created?
8. **Establish each of the above can fail** — remove the grant and watch step 5 go
   red. A check you have only ever seen pass is a check you have not yet read.

## What is not settled

**UNVERIFIED:** whether `test_draft`'s separate test budget is shared across an
organisation or is genuinely per-request. "Capped server-side" is stated; the
sharing scope is not, and it decides whether a colleague iterating in parallel can
exhaust your ability to test.

**UNVERIFIED:** whether an invocation refused by governance appears in
`api:GET /api/v1/tool-agents/{id}/invocations`. If a refusal is recorded, that
history is your evidence that controls fired; if only successes are recorded, you
need a different surface for it, and you should find out which before an auditor
asks. This is the same open question 03.1 records for the in-process side, at the
registered-agent surface.

---

_Next: [03.6 — Choosing between a tool, a skill, an agent and a pipeline](06-choosing-between-them.md)_
