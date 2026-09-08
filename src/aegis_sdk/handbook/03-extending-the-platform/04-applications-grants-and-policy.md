# 03.4 — Who may call your tool: applications, grants and policy

[Chapter 03.3](03-the-tool-agent-lifecycle.md) got a tool agent to `active`. That
makes it _callable_; it does not make it _available to anything_. This chapter is
the other half — the model that decides which consumers may invoke it, under what
posture, against whose budget, and with what data in scope.

The whole model is `client.applications`
(`sdk:aegis_sdk.ApplicationsModule`), and it is four objects that compose:

| object                | answers                                                       |
| --------------------- | ------------------------------------------------------------- |
| **application**       | who is asking, and what are _its_ outer bounds?               |
| **grant**             | may this application invoke this tool agent at all?           |
| **invocation policy** | for this application/agent pair, what are the tighter bounds? |
| **delegation matrix** | which of those bounds may an application operator change?     |

Read that table as a chain of narrowing. Nothing further down widens anything
further up — the same monotonic-tightening property envelopes have (02.3), applied
to consumers rather than to roles.

## The distinction that makes the model make sense

**Applications hold authority to invoke shared tool agents. They do not own tool
agents.** A tool agent is registered once, to an accountable role (03.3); any
number of applications may then be granted the right to call it. That separation is
what makes a tool agent _shared_ rather than copied — one implementation, one
accountable owner, many authorised consumers, each with its own bounds and its own
budget.

If you find yourself creating a second tool agent because a second consumer needs
slightly different limits, stop: that is what an invocation policy is for.

## Step 1 — Create the application

```python
app = await client.applications.create(
    name="Treasury Console",
    owner_role_id=head_of_treasury_role_id,
    description="Internal console used by the treasury desk.",
    default_posture_ceiling="supervised",
    budget_monthly="2500.00",
)
```

`api:POST /api/v1/applications`, returning
`sdk:aegis_sdk.modules.applications.Application`.

Four things about the arguments:

**`owner_role_id` is required and is an accountability anchor**, exactly as
`registered_to_role_id` is on a tool agent. The application answers to a role.

**`default_posture_ceiling` is the application's own ceiling and it bounds every
grant beneath it.** It defaults to `pseudo` — the most restrictive posture, which
is the right default and an easy one to be surprised by. A grant cannot exceed it,
and the server enforces that rather than trusting the caller.

**Money is a string.** `budget_monthly` is `"2500.00"`, not `2500.00`. So are
`budget_allocation` on a grant and `budget_per_invocation` on a policy. Passing a
float where a decimal string is expected is the kind of mistake that works in
testing and rounds wrongly in production; the string type is deliberate.

**`data_scope_json` and `allowed_models_json` are JSON strings**, defaulting to
`"[]"`. An empty scope is not "everything" — see the caution below.

**It is created in a pending state, not an active one.** An application has to be
approved before it can consume anything, which is the same create-is-not-grant
shape envelopes, clearances and knowledge all have (02.3). A provisioning script
that creates applications and walks away has built a console nobody can use, and
the symptom is a refusal rather than an error.

Lifecycle moves go through `api:PATCH /api/v1/applications/{id}/status`, whose
targets are `active`, `suspended`, `archived` and `rejected`.

## Step 2 — Grant the tool agent

```python
grant = await client.applications.grant_tool_agent(
    app.id,
    agent_id=agent.id,
    posture_ceiling="supervised",
    rationale="Treasury desk needs overnight cash summaries in the console.",
    budget_allocation="500.00",
)
```

`api:POST /api/v1/applications/{id}/grants`, returning
`sdk:aegis_sdk.modules.applications.ToolAgentGrant`. Read them back with
`api:GET /api/v1/applications/{id}/grants` and remove one with
`api:DELETE /api/v1/applications/{id}/grants/{grant_id}`.

**`rationale` is mandatory, and this is a CARE requirement rather than a form
field.** A constraint without a stated reason is a constraint nobody can review:
six months later the question is not "what is the ceiling?" — that is on the
record — but "why is it this?", and only the rationale answers it. Write it for
the person who will read it during an audit, not for the validator.

**`posture_ceiling` cannot exceed the application's own `default_posture_ceiling`,
and the server enforces it.** You cannot grant an application more posture than the
application has. This is the monotonic tightening again, one level down.

`budget_allocation` carves out part of the application's budget for this specific
agent. `constraint_summary_json` carries the constraint summary that was in force
when the grant was made — a snapshot, for the record.

The grant record carries `status`, `granted_by`, `granted_at` and `revoked_at`. A
revoked grant is not deleted; it is a revoked row, and it stays readable — pass
`status="revoked"` or `status="all"` to `list_consumers` on the agent side (03.3) to
see them.

## Step 3 — Tighten with an invocation policy

A grant says _whether_. A policy says _how far_, for one application/agent pair.

```python
await client.applications.update_policy(
    app.id,
    agent.id,
    posture_ceiling="supervised",
    budget_per_invocation="0.75",
    data_scope_json='["treasury/cash-positions"]',
    allowed_models_json='["<model-id-from-your-config>"]',
    prompt_prefix="You are answering inside the Treasury Console. Do not advise.",
    knowledge_attachment_ids_json='["kn_abc123"]',
)
```

`api:PUT /api/v1/applications/{id}/policy/{agent_id}`, read at
`api:GET /api/v1/applications/{id}/policy/{agent_id}`, returning
`sdk:aegis_sdk.modules.applications.InvocationPolicy`.

The six knobs, and what each is really for:

| field                           | bounds                                                      |
| ------------------------------- | ----------------------------------------------------------- |
| `posture_ceiling`               | how autonomous this pairing may be                          |
| `budget_per_invocation`         | per-call spend cap (a decimal **string**)                   |
| `data_scope_json`               | which data this pairing may reach                           |
| `allowed_models_json`           | which models it may use                                     |
| `prompt_prefix`                 | context prepended to every invocation from this application |
| `knowledge_attachment_ids_json` | which knowledge items are attached                          |

**`prompt_prefix` is the one to be careful with, because it is the only knob here
that shapes behaviour rather than bounding it.** It is a governance surface with a
usability feel: it changes what the agent is told on every call from this
application, and it is invisible from the agent's own configuration. If an agent
behaves differently for one consumer than another and its own configuration is
identical, this is the first place to look.

**⚠ An empty `data_scope_json` is ambiguous from the client, and you should settle
it against your own deployment before relying on it.** `"[]"` could mean "no data
in scope" (the restrictive reading) or "no restriction declared" (the permissive
one), and the two are opposite. The client cannot tell you which; test it. This is
the sentinel hazard
[`coc/guardrails/sentinels-and-defaults.md`](../../coc/guardrails/sentinels-and-defaults.md)
treats at length — a value in the ordinary range that means something outside it,
where the ambiguity resolves permissively by default and nothing announces it.

_Design intent, not observable:_ that the policy is intended to be strictly
narrowing relative to the grant. The narrowing relationship between the application
ceiling and the grant ceiling **is** server-enforced and stated as such by the SDK;
whether every policy field is validated against its grant in the same way is not
established from the client surface. Do not assume a policy cannot widen — check.

## Step 4 — Decide what an operator may change, with the delegation matrix

The delegation matrix is the answer to "who may adjust these bounds without coming
back to you?". It is per-parameter, and it is where an architect encodes the
difference between a knob a desk manager may turn and one only governance may.

```python
await client.applications.update_delegation_matrix(app.id, entries=[
    {"parameter_name": "prompt_prefix",
     "permission_level": "edit",
     "rationale": "Desk owns its own phrasing."},
    {"parameter_name": "posture_ceiling",
     "permission_level": "locked",
     "rationale": "Autonomy level is a governance decision, not a desk one."},
    {"parameter_name": "budget_per_invocation",
     "permission_level": "view",
     "rationale": "Desk should see the cap; only finance changes it."},
])
```

`api:PUT /api/v1/applications/{id}/delegation-matrix`, read at
`api:GET /api/v1/applications/{id}/delegation-matrix`, returning
`sdk:aegis_sdk.modules.applications.DelegationMatrixEntry` records. Four permission
levels:

| level    | meaning                                       |
| -------- | --------------------------------------------- |
| `edit`   | the operator may change the value             |
| `toggle` | the operator may switch it, within bounds     |
| `view`   | visible, not changeable                       |
| `locked` | not changeable, and not an operator's concern |

Three constraints worth knowing before you write one: **every entry requires a
`rationale`** — the same CARE requirement as on a grant; **the bulk set is capped at
50 entries**; and **changing the matrix itself requires application-admin
authority**, which is what stops an operator from widening their own permissions.

**The matrix is enforced on the policy write path.** `update_policy` is gated
through it server-side: a parameter at `locked` or `view` cannot be updated, and
the attempt returns a 403 that the SDK raises as
`sdk:aegis_sdk.AuthorizationError`. So a 403 on a policy update that your role
otherwise permits is usually the matrix, not your permissions — a genuinely useful
thing to know, because the two failures look identical from the outside.

## Step 5 — Operators, and what assignment actually does

```python
await client.applications.add_operator(app.id, user_id=user_id, role="app_admin")
```

`api:POST /api/v1/applications/{id}/operators`, listed at
`api:GET /api/v1/applications/{id}/operators`, removed at
`api:DELETE /api/v1/applications/{id}/operators/{user_id}`. Two roles:
`app_operator` and `app_admin`. Adding or removing one requires
application-admin authority.

**Operator assignment also decides visibility, not just capability.** Org admins
see every application; scoped roles see only the applications they are explicitly
assigned to as operators, filtered server-side. So an application a colleague
cannot find is frequently an assignment they do not have rather than a bug — and
`api:GET /api/v1/applications` returning fewer rows for them than for you is the
system working.

## Watching what the application actually does

Four read surfaces, and they answer different questions:

- `api:GET /api/v1/applications/{id}/invocations` — this application's tool-agent
  invocation history, returning
  `sdk:aegis_sdk.modules.applications.InvocationListResult`. The consumer-side view
  of what 03.3 shows agent-side.
- `api:GET /api/v1/applications/{id}/audit-events` — **the one to reach for.** It
  aggregates the application's own events with events on _every tool agent it has
  been granted_, newest first. That composition is exactly the question an auditor
  asks and exactly the join you would otherwise write by hand. Note it returns a
  **flat list**, not an enveloped one.
- `api:GET /api/v1/applications/{id}/notifications` — pending constraint-change
  notifications for you on this application. ⚠ **Only notifications inside a 24-hour
  grace window are returned**, so this is a surface to poll rather than to check
  occasionally; a constraint change you did not see is a constraint change you are
  now operating under.
- `api:GET /api/v1/applications/{id}/summary` — a lightweight
  `sdk:aegis_sdk.modules.applications.ApplicationSummary` for a listing.

## Content freeze — the control most deployments never find

An application can be put under a **content freeze**: a declared window during which
its content is not to change, with a staleness threshold.

```python
status = await client.applications.get_freeze_status(app.id)
```

`api:GET /api/v1/applications/{id}/freeze-status`, returning
`sdk:aegis_sdk.modules.applications.FreezeStatus` — `is_frozen`, `reason`,
`freeze_start`, `freeze_end`, `staleness_days` and a `warning`. The freeze is
configured through the ordinary update path
(`api:PUT /api/v1/applications/{id}`) via `content_freeze_enabled`,
`content_freeze_start`, `content_freeze_end` and `content_freeze_staleness_days`.

**While a freeze is active, an update touching the freeze fields can be refused
with a 403 requiring application-admin authority.** That is the verification
gradient's `held` zone arriving on a configuration surface: the change is not
rejected as invalid, it is held pending someone with the authority to make it. If
you meet an inexplicable 403 on an application update, check the freeze status
before you check your permissions.

Reach for a freeze during a period where a consumer-facing surface must be stable —
a reporting close, an audit window, a regulated quiet period. It is the mechanism
that makes "nothing changed during the window" an assertion you can evidence rather
than a claim you make.

## Archiving, and the cascade you should expect

```python
await client.applications.archive(app.id)
```

`api:DELETE /api/v1/applications/{id}` — and read what it does before you call it:

1. it **revokes every active grant**,
2. it **invalidates every active invocation policy**,
3. then it transitions the application to `archived`.

It requires org-admin authority, and it returns the archived application record
rather than an empty response.

That cascade is the correct behaviour and it is wider than the word "archive"
suggests. Every consumer relationship this application had is severed in one call.
Before you make it, run the impact read from the _agent_ side (03.3) for each agent
this application was the significant consumer of — the cascade tells you what the
application loses; the impact read tells you what everything else loses.

## Diagnosing a refused invocation

An invoke that fails through this model has five plausible causes, and they present
similarly. Check them in this order, because it is cheapest-first:

1. **Is the application active?** A pending or suspended application consumes
   nothing. `api:GET /api/v1/applications/{id}`.
2. **Is there an active grant for this agent?**
   `api:GET /api/v1/applications/{id}/grants` — and check `status`, since a revoked
   grant is still a row.
3. **Is the agent itself `active`?** A `suspended` or `revoked` tool agent is not
   callable regardless of the grant (03.3).
4. **Is a budget exhausted?** Application budget, grant allocation, and
   per-invocation cap are three separate limits and any one of them refuses.
   `budget_consumed` against `budget_monthly` on the application is the first read.
5. **Is the posture ceiling too low for what was asked?** The effective ceiling is
   the tightest of the application's default, the grant's, and the policy's.

A `sdk:aegis_sdk.GovernanceViolationError` is the shape most of these arrive in.
Retrying is wrong for every one of them — each is a decision, not a transient
failure. The general procedure for telling one kind of refusal from another is
[`coc/skills/diagnosing-a-refusal.md`](../../coc/skills/diagnosing-a-refusal.md);
the list above is its tool-agent-specific case.

## What is not settled

**UNVERIFIED:** whether an invocation policy is validated against its grant the way
a grant is validated against the application ceiling. The grant-versus-application
check is stated as server-enforced; the policy-versus-grant relationship is not
established from the client surface. Until you have tested it on your own
deployment, do not treat a policy as structurally incapable of widening.

**UNVERIFIED:** the semantics of an empty `data_scope_json`. Restrictive and
permissive readings are both consistent with what is reachable from here, and they
are opposite. Settle it before you rely on the empty default as a bound.

**UNVERIFIED:** whether revoking a grant terminates an in-flight invocation or only
prevents new ones. If you need a revocation to be an incident control rather than a
housekeeping action, measure it before you need it.

---

_Next: [03.5 — Testing an extension](05-testing-an-extension.md)_
