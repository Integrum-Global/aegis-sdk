# 08.4 — Work and objectives

This chapter enumerates **what is being asked** and **how it resolves**. Where
08.3 catalogued the actors, this catalogues the work that reaches them — and the
distinction is sharper here than anywhere else in the platform, because Aegis
carries several work-shaped objects that look similar in a listing and behave
completely differently.

Four of them, and choosing the wrong one is a design error rather than a
preference:

| object        | what it is                                                         | who creates it   |
| ------------- | ------------------------------------------------------------------ | ---------------- |
| **Objective** | A stated outcome, decomposed by the platform into work             | A human, usually |
| **Work unit** | A reusable, versioned unit of executable work                      | An architect     |
| **Request**   | One piece of work assigned to one actor                            | Decomposition    |
| **Directive** | A standing instruction that binds until acknowledged or superseded | A role-holder    |

An objective is a _goal_; a work unit is a _capability_; a request is an
_assignment_; a directive is an _instruction_. **The objective is the entry
point for most work, and everything else in this chapter is either what it
decomposes into or what constrains it.**

[02.5](../02-working-through-the-harness/05-objectives-and-the-work-loop.md) is
the procedure. This is the inventory.

## Objectives

The primary work surface. You state an outcome; the platform clarifies it,
decomposes it into a task graph, executes it through agents, and stops to ask
when it reaches something it may not decide alone.

| capability                                          | what it does                                                 |
| --------------------------------------------------- | ------------------------------------------------------------ |
| **Create / update**                                 | State an objective, or revise it                             |
| **List / get / recent**                             | Enumerate and address objectives                             |
| **Templates**                                       | Prebuilt objective shapes                                    |
| **Submit**                                          | Hand the objective to the platform to begin work             |
| **Clarify**                                         | The platform asks; you answer, structured or freeform        |
| **Clarification status**                            | Whether it is waiting on you                                 |
| **Task graph**                                      | The decomposition — what it intends to do, and in what order |
| **Trigger execution**                               | Begin executing the graph                                    |
| **Implement**                                       | Drive the implementation phase                               |
| **Confirm implementation**                          | Accept what was produced                                     |
| **Progress / progress stream**                      | Where it has reached, polled or streamed                     |
| **Pause / resume / stop**                           | Lifecycle control on a running objective                     |
| **Retry node**                                      | Re-run one failed step without restarting the objective      |
| **Decide**                                          | Answer a decision the objective is blocked on                |
| **Decisions**                                       | Every decision this objective has raised                     |
| **Requests**                                        | The assignments it decomposed into                           |
| **Complete / check completion / completion status** | Finish it, or ask whether it can finish                      |
| **Artifacts / download**                            | What it produced                                             |
| **Participants**                                    | Who and what has been involved                               |
| **Summary**                                         | The rolled-up view                                           |

Entry points: `sdk:aegis_sdk.execution.objectives.ObjectivesModule` for the core
lifecycle, and `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule` for
clarification, the task graph and progress streaming.

Operations — lifecycle: `api:POST /api/v1/objectives` ·
`api:GET /api/v1/objectives` · `api:GET /api/v1/objectives/{id}` ·
`api:PUT /api/v1/objectives/{id}` · `api:GET /api/v1/objectives/recent` ·
`api:GET /api/v1/objectives/templates` ·
`api:POST /api/v1/objectives/{id}/submit` ·
`api:POST /api/v1/objectives/{id}/trigger-execution` ·
`api:POST /api/v1/objectives/{id}/implement` ·
`api:POST /api/v1/objectives/{id}/confirm-implementation` ·
`api:POST /api/v1/objectives/{id}/pause` ·
`api:POST /api/v1/objectives/{id}/resume` ·
`api:POST /api/v1/objectives/{id}/stop` ·
`api:POST /api/v1/objectives/{id}/complete` ·
`api:POST /api/v1/objectives/{id}/check-completion` ·
`api:GET /api/v1/objectives/{id}/completion-status`

Clarification and decisions: `api:POST /api/v1/objectives/{id}/clarify` ·
`api:POST /api/v1/objectives/{id}/clarify/trigger` ·
`api:POST /api/v1/objectives/{id}/clarify/respond` ·
`api:POST /api/v1/objectives/{id}/clarify/respond-freeform` ·
`api:GET /api/v1/objectives/{id}/clarification-status` ·
`api:POST /api/v1/objectives/{id}/decide` ·
`api:GET /api/v1/objectives/{id}/decisions`

Progress and output: `api:GET /api/v1/objectives/{id}/task-graph` ·
`api:GET /api/v1/objectives/{id}/progress` ·
`api:GET /api/v1/objectives/{id}/progress/stream` ·
`api:POST /api/v1/objectives/{id}/nodes/{node_id}/retry` ·
`api:GET /api/v1/objectives/{id}/requests` ·
`api:GET /api/v1/objectives/{id}/artifacts` ·
`api:GET /api/v1/objectives/{id}/download` ·
`api:GET /api/v1/objectives/{id}/participants` ·
`api:GET /api/v1/objectives/{id}/summary`

Two administrative overrides sit alongside the normal lifecycle and bypass it:
`api:POST /api/v1/objectives/{id}/admin-status` sets an objective's status
directly, and `api:POST /api/v1/objectives/{id}/admin-tasks` injects tasks into
its graph. Both are recovery tools for an objective stuck in a state the normal
transitions cannot leave — **an objective moved by `admin-status` has not done
the work its new status implies**, so use them to unblock and then re-drive,
never to mark something complete.

```python
objective = await client.objectives.create(
    title="Close the Q3 books",
    description="Reconcile all ledgers, produce the trial balance, flag variances over $10k.",
)
await client.objectives.submit(objective_id=objective["id"])

status = await client.work_objectives.get_clarification_status(
    objective_id=objective["id"],
)
if status["pending"]:
    await client.work_objectives.respond_to_clarification(
        objective_id=objective["id"],
        question_id=status["questions"][0]["id"],
        answer="Use the consolidated ledger, not the per-entity ones.",
    )

graph = await client.work_objectives.get_task_graph(objective_id=objective["id"])
```

> ⛔ **Create and submit are two calls, and an unsubmitted objective does
> nothing.** `create` records the intent; `submit` hands it to the platform. An
> objective created and never submitted sits in the listing looking exactly like
> a live one, with no progress and no error to explain why — because nothing has
> gone wrong, nothing has started.

**The clarification loop is the second place work silently stalls.** The platform
asks a question and waits; if nothing polls
`api:GET /api/v1/objectives/{id}/clarification-status` and nothing answers, the
objective is blocked indefinitely. It is not failed, so it does not appear in a
failure query. Poll the status, or consume the progress stream, which carries the
clarification event.

## Work units

Reusable, versioned units of executable work. Where an objective is a one-off
goal, a work unit is a capability you define once and run repeatedly — with
version history, an execution configuration, and run records.

| capability                   | what it does                                            |
| ---------------------------- | ------------------------------------------------------- |
| **Create / update / delete** | Standard lifecycle                                      |
| **List / get / available**   | Enumerate, including which are available to run         |
| **Run / execute**            | Invoke it                                               |
| **Cancel execution**         | Stop a run in flight                                    |
| **Runs**                     | The execution history                                   |
| **Execution config**         | Read and adjust how it runs                             |
| **Versions**                 | Create, list, get, compare, restore and delete versions |

Entry point: `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule`.

Operations: `api:POST /api/v1/work-units` · `api:GET /api/v1/work-units` ·
`api:GET /api/v1/work-units/{id}` · `api:PUT /api/v1/work-units/{id}` ·
`api:DELETE /api/v1/work-units/{id}` ·
`api:GET /api/v1/work-units/available` ·
`api:POST /api/v1/work-units/{id}/run` ·
`api:POST /api/v1/work-units/{id}/execute` ·
`api:POST /api/v1/work-units/{id}/execute/cancel` ·
`api:GET /api/v1/work-units/{id}/runs` ·
`api:GET /api/v1/work-units/{id}/execution-config` ·
`api:PATCH /api/v1/work-units/{id}/execution-config` ·
`api:GET /api/v1/work-units/{id}/versions` ·
`api:POST /api/v1/work-units/{id}/versions` ·
`api:GET /api/v1/work-units/{id}/versions/{version_id}` ·
`api:GET /api/v1/work-units/{id}/versions/compare` ·
`api:POST /api/v1/work-units/{id}/versions/{version_id}/restore` ·
`api:DELETE /api/v1/work-units/{id}/versions/{version_id}`

```python
unit = await client.work_objectives.create_work_unit(
    name="monthly-variance-report",
    description="Produce the variance report for one period.",
)
await client.work_objectives.create_work_unit_version(work_unit_id=unit["id"])

run = await client.work_objectives.run_work_unit(
    work_unit_id=unit["id"],
    inputs={"period": "2026-09"},
)
```

**Version before you change a work unit that is in service.** Editing in place
changes the behaviour of every future run with no record of what it used to do,
and a run record from last month then describes a unit that no longer exists in
that form. Create a version, then edit.

## Requests

One piece of work assigned to one actor. Requests are what objectives decompose
into and what pools distribute.

| capability             | what it does                             |
| ---------------------- | ---------------------------------------- |
| **List / get**         | Enumerate and address requests           |
| **Claim / release**    | Take ownership, or give it back          |
| **Complete**           | Finish the request                       |
| **Escalate**           | Raise it to whoever is above             |
| **Findings**           | Record and read what the work discovered |
| **Decompose**          | Break a request into smaller ones        |
| **Submit deliverable** | Attach the output that satisfies it      |

Entry point: `sdk:aegis_sdk.execution.requests.RequestsModule`.

Operations: `api:GET /api/v1/requests` · `api:GET /api/v1/requests/{id}` ·
`api:POST /api/v1/requests/{id}/claim` ·
`api:POST /api/v1/requests/{id}/release` ·
`api:POST /api/v1/requests/{id}/complete` ·
`api:POST /api/v1/requests/{id}/escalate` ·
`api:GET /api/v1/requests/{id}/findings` ·
`api:POST /api/v1/requests/{id}/findings` ·
`api:POST /api/v1/objectives/{id}/requests/{request_id}/complete` ·
`api:POST /api/v1/objectives/{id}/requests/{request_id}/decompose` ·
`api:POST /api/v1/objectives/{id}/requests/{request_id}/submit-deliverable`

```python
mine = await client.requests.list(assigned_to_me=True)
await client.requests.claim(request_id=mine["records"][0]["id"])
await client.requests.add_finding(
    request_id=mine["records"][0]["id"],
    summary="Ledger 4400 has 12 unmatched entries.",
    severity="high",
)
await client.requests.complete(request_id=mine["records"][0]["id"])
```

> ⚠ **A claimed request that is neither completed nor released holds its claim
> until the pool's timeout expires.** Until then no other actor can take it, and
> it does not appear in any pending queue. An agent that crashes mid-request
> leaves exactly this state — the work is invisible rather than failed. Pool
> health in [08.3](03-agents-and-execution.md) is where you see it.

## Directives

Standing instructions. A directive is published to an audience, must be
acknowledged, and binds until it expires, is revoked, or is superseded. It is the
mechanism for organisation-wide instruction that outlives any single objective.

| capability                   | what it does                                              |
| ---------------------------- | --------------------------------------------------------- |
| **Create / update / delete** | Author a directive                                        |
| **List / get**               | Enumerate them                                            |
| **Publish**                  | Put it into force                                         |
| **Acknowledge**              | Record that a recipient has read and accepted it          |
| **Batch acknowledge**        | Acknowledge on behalf of many                             |
| **Acknowledgment status**    | Who has and has not acknowledged                          |
| **Expire**                   | End it at its natural end                                 |
| **Revoke**                   | Withdraw it immediately                                   |
| **Supersede**                | Replace it with a newer directive, preserving the lineage |

Entry point: `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule`.

Operations: `api:POST /api/v1/directives` · `api:GET /api/v1/directives` ·
`api:GET /api/v1/directives/{id}` · `api:PUT /api/v1/directives/{id}` ·
`api:DELETE /api/v1/directives/{id}` ·
`api:POST /api/v1/directives/{id}/publish` ·
`api:POST /api/v1/directives/{id}/acknowledge` ·
`api:POST /api/v1/directives/{id}/batch-acknowledge` ·
`api:GET /api/v1/directives/{id}/acknowledgments` ·
`api:POST /api/v1/directives/{id}/expire` ·
`api:POST /api/v1/directives/{id}/revoke` ·
`api:POST /api/v1/directives/{id}/supersede`

```python
directive = await client.work_objectives.create_directive(
    title="Freeze discretionary spend",
    body="No new commitments above $5,000 without CFO sign-off until year end.",
)
await client.work_objectives.publish_directive(directive_id=directive["id"])

status = await client.work_objectives.get_acknowledgment_status(
    directive_id=directive["id"],
)
```

**An unpublished directive binds nobody**, the same shape as an unsubmitted
objective. And a directive that is revoked rather than superseded leaves no
pointer to what replaced it — use `supersede` when there is a successor, so the
lineage survives for whoever audits the decision later.

## Change requests

A proposal to change something, with a negotiation lifecycle: submit, approve,
deny, counter-propose, accept the counter, and apply.

| capability          | what it does                |
| ------------------- | --------------------------- |
| **Create**          | Draft the proposed change   |
| **Submit**          | Put it forward for decision |
| **Approve / deny**  | Decide it                   |
| **Counter-propose** | Offer a modified version    |
| **Accept counter**  | Take the counter-proposal   |
| **Apply**           | Effect the approved change  |
| **List / get**      | Enumerate them              |

Entry point: `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule`.

Operations: `api:POST /api/v1/change-requests` ·
`api:GET /api/v1/change-requests` · `api:GET /api/v1/change-requests/{id}` ·
`api:PATCH /api/v1/change-requests/{id}/submit` ·
`api:PATCH /api/v1/change-requests/{id}/approve` ·
`api:PATCH /api/v1/change-requests/{id}/deny` ·
`api:PATCH /api/v1/change-requests/{id}/counter-propose` ·
`api:PATCH /api/v1/change-requests/{id}/accept-counter` ·
`api:PATCH /api/v1/change-requests/{id}/apply`

**Approval and application are separate steps on purpose.** An approved change
request has a decision recorded against it and has changed nothing. Forgetting
`apply` produces a change everyone believes is in force and no system reflects —
the most expensive failure in this chapter, because the audit trail says approved
and the behaviour says otherwise.

## Decisions

The surface where held work waits for a human answer. This is the decision
gradient made concrete: an objective that reaches something it may not decide
alone raises a decision, and the decision blocks until answered.

| capability       | what it does                                   |
| ---------------- | ---------------------------------------------- |
| **List pending** | Every decision waiting on a human              |
| **Get**          | One decision in full                           |
| **Options**      | The choices available, with their consequences |
| **Decide**       | Answer it                                      |
| **Cancel**       | Withdraw the decision request                  |

Entry point: `sdk:aegis_sdk.modules.decision_points.DecisionsModule`.

Operations: `api:GET /api/v1/decisions/pending` ·
`api:GET /api/v1/decisions/{id}` · `api:GET /api/v1/decisions/{id}/options` ·
`api:POST /api/v1/decisions/{id}/decide` ·
`api:POST /api/v1/decisions/{id}/cancel`

```python
pending = await client.decisions.list_pending()
for d in pending["records"]:
    options = await client.decisions.get_options(decision_id=d["id"])
    await client.decisions.decide(decision_id=d["id"], option_id=options[0]["id"])
```

## Review decisions

Distinct from decision points: a review decision is the recorded verdict of a
review, with conditions that may be marked met later.

| capability              | what it does                                                  |
| ----------------------- | ------------------------------------------------------------- |
| **List / get**          | Enumerate review verdicts                                     |
| **Latest for request**  | The most recent verdict on one request                        |
| **Mark conditions met** | Record that a conditional approval's conditions are satisfied |

Entry point: `sdk:aegis_sdk.modules.decision_points.ReviewDecisionsModule`.

Operations: `api:GET /api/v1/review-decisions` ·
`api:GET /api/v1/review-decisions/{id}` ·
`api:GET /api/v1/review-decisions/latest/{request_id}` ·
`api:PATCH /api/v1/review-decisions/{id}/conditions`

```python
verdict = await client.review_decisions.get_latest(request_id=request["id"])
if verdict["conditional"]:
    await client.review_decisions.mark_conditions_met(decision_id=verdict["id"])
```

**A conditional approval is not an approval until its conditions are marked
met.** The verdict reads `approved` in every listing while the conditions are
outstanding, so the work it gates stays blocked with nothing showing why.

## Approvals

The general approval queue — the human gate that several other surfaces route
into.

| capability           | what it does                 |
| -------------------- | ---------------------------- |
| **List pending**     | Everything awaiting approval |
| **Get**              | One approval in full         |
| **Approve / reject** | Decide it                    |
| **Modify**           | Approve with changes         |

Entry point: `sdk:aegis_sdk.standup.approvals.ApprovalsModule`.

Operations: `api:GET /api/v1/approvals/pending` ·
`api:GET /api/v1/approvals/{id}` ·
`api:POST /api/v1/approvals/{id}/approve` ·
`api:POST /api/v1/approvals/{id}/reject`

## Escalation

What happens when work is not handled in time. Escalation is configured per pool
and fires on a timer, but can also be triggered manually.

| capability               | what it does                                      |
| ------------------------ | ------------------------------------------------- |
| **Get / update config**  | The escalation chain and its timings for one pool |
| **Pending**              | Escalations currently in flight                   |
| **Escalate**             | Raise a task manually                             |
| **Acknowledge**          | Accept an escalated task                          |
| **Reset / cancel timer** | Manage the escalation clock on one task           |
| **History**              | What has escalated, and to whom                   |
| **Stats**                | Escalation rates and patterns                     |

Entry point: `sdk:aegis_sdk.modules.pools.PoolsModule`, with the objective-side
surface on `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule`.

Operations: `api:GET /api/v1/escalation/config/{pool_id}` ·
`api:PUT /api/v1/escalation/config/{pool_id}` ·
`api:GET /api/v1/escalation/pending` · `api:GET /api/v1/escalation/stats` ·
`api:POST /api/v1/escalation/tasks/{task_id}/escalate` ·
`api:POST /api/v1/escalation/tasks/{task_id}/acknowledge` ·
`api:POST /api/v1/escalation/tasks/{task_id}/reset-timer` ·
`api:POST /api/v1/escalation/tasks/{task_id}/cancel-timer` ·
`api:GET /api/v1/escalation/tasks/{task_id}/history`

**An escalation chain whose last link is vacant terminates silently.** The task
escalates upward until it runs out of chain and then stops, still unhandled and
no longer in any pending queue anyone watches. Check the chain against the
reporting structure in [08.2](02-organization-and-identity.md) after any
re-organisation.

## Agent escalations

Distinct from task escalation: this is an agent stopping to ask, because it has
reached the edge of what it may decide. It carries the trigger, the options, a
recommendation, and the constraint state at the moment it stopped.

| capability       | what it does                          |
| ---------------- | ------------------------------------- |
| **List pending** | Agents currently waiting on a human   |
| **Stream**       | Consume escalations as they happen    |
| **Get**          | One escalation, with its full context |
| **Resolve**      | Answer it and let the agent continue  |
| **Cancel**       | Withdraw it                           |

Entry point: `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule`.

Operations: `api:GET /api/v1/agent-escalations/pending` ·
`api:GET /api/v1/agent-escalations/stream` ·
`api:GET /api/v1/agent-escalations/{id}` ·
`api:POST /api/v1/agent-escalations/{id}/resolve` ·
`api:POST /api/v1/agent-escalations/{id}/cancel`

```python
async for esc in client.work_objectives.stream_agent_escalations():
    detail = await client.work_objectives.get_agent_escalation(escalation_id=esc["id"])
    await client.work_objectives.resolve_agent_escalation(
        escalation_id=esc["id"],
        decision="approve",
        rationale="Within the revised Q3 ceiling.",
    )
```

## Interventions

Acting on a running session from outside it — the operator's hand on the wheel.

| capability              | what it does                                            |
| ----------------------- | ------------------------------------------------------- |
| **List sessions**       | Sessions available to intervene in                      |
| **Get / history**       | One session's intervention state and past interventions |
| **Pause / resume**      | Halt or restart the session                             |
| **Tighten constraints** | Narrow the envelope on a session already running        |
| **Fence**               | Confine the session to a reduced scope                  |

Entry point: `sdk:aegis_sdk.modules.work_objectives.WorkObjectivesModule`.

Operations: `api:GET /api/v1/interventions/sessions` ·
`api:GET /api/v1/interventions/{id}` ·
`api:GET /api/v1/interventions/{id}/history` ·
`api:POST /api/v1/interventions/{id}/pause` ·
`api:POST /api/v1/interventions/{id}/resume` ·
`api:POST /api/v1/interventions/{id}/tighten-constraints` ·
`api:POST /api/v1/interventions/{id}/fence`

```python
await client.work_objectives.tighten_constraints(
    session_id=session["id"],
    constraints={"financial": {"max_amount_cents": 50_000}},
)
```

**Tightening is one-way within a session.** Constraints narrow; they do not widen
back. If you need the original bounds restored, that is a new session — which is
the intended behaviour, because an operator who can widen mid-run has removed the
envelope's meaning.

## Promotions

Moving something to a higher state of trust or scope, with an approval gate and
rules that can automate the decision.

| capability              | what it does                                          |
| ----------------------- | ----------------------------------------------------- |
| **Create / list / get** | The promotion record                                  |
| **Approve / reject**    | Decide it                                             |
| **Execute**             | Effect an approved promotion                          |
| **Rules**               | Create, list, get, update and delete automation rules |

Entry point: `sdk:aegis_sdk.modules.promotions.PromotionsModule`.

Operations: `api:POST /api/v1/promotions` · `api:GET /api/v1/promotions` ·
`api:GET /api/v1/promotions/{id}` ·
`api:POST /api/v1/promotions/{id}/approve` ·
`api:POST /api/v1/promotions/{id}/reject` ·
`api:POST /api/v1/promotions/{id}/execute` ·
`api:GET /api/v1/promotions/rules` · `api:POST /api/v1/promotions/rules` ·
`api:GET /api/v1/promotions/rules/{id}` ·
`api:PUT /api/v1/promotions/rules/{id}` ·
`api:DELETE /api/v1/promotions/rules/{id}`

```python
promotion = await client.promotions.create(subject_id=agent["id"], target="delegated")
await client.promotions.approve(promotion_id=promotion["id"])
await client.promotions.execute(promotion_id=promotion["id"])   # without this, nothing moved
```

As with change requests, **approve and execute are separate** — and for the same
reason, and with the same failure mode.

## Positions

A lightweight claim-and-consume primitive: a position is staked, ratified or
retracted, and consumed once.

| capability  | what it does                          |
| ----------- | ------------------------------------- |
| **Create**  | Stake the position                    |
| **Get**     | Read it                               |
| **Ratify**  | Confirm it                            |
| **Retract** | Withdraw it                           |
| **Consume** | Spend it — single-use by construction |

Entry point: `sdk:aegis_sdk.modules.positions.PositionsModule`.

Operations: `api:POST /api/v1/positions` · `api:GET /api/v1/positions/{id}` ·
`api:POST /api/v1/positions/{id}/ratify` ·
`api:POST /api/v1/positions/{id}/retract` ·
`api:POST /api/v1/positions/{id}/consume`

```python
position = await client.positions.create(subject_id=claim_subject_id)
await client.positions.ratify(position_id=position["id"])
await client.positions.consume(position_id=position["id"])   # single-use; the second call fails
```

**A position is spent, not read.** `consume` succeeds once; a retry after a
partial failure is refused, so treat the consume as the commit point and record
its result rather than re-deriving it.

## Artifacts

The outputs. Artifacts are versioned, downloadable, and supersedable — the
durable record of what work produced.

| capability     | what it does                        |
| -------------- | ----------------------------------- |
| **Create**     | Record an artifact                  |
| **List / get** | Enumerate and address them          |
| **Versions**   | The version history of one artifact |
| **Supersede**  | Replace it, keeping the lineage     |
| **Download**   | Retrieve the content                |
| **Delete**     | Remove it                           |

Entry point: `sdk:aegis_sdk.execution.artifacts.ArtifactsModule`.

Operations: `api:POST /api/v1/artifacts` · `api:GET /api/v1/artifacts` ·
`api:GET /api/v1/artifacts/{id}` ·
`api:GET /api/v1/artifacts/{id}/versions` ·
`api:GET /api/v1/artifacts/{id}/download` ·
`api:POST /api/v1/artifacts/{id}/supersede` ·
`api:DELETE /api/v1/artifacts/{id}`

```python
artifacts = await client.objectives.get_artifacts(objective_id=objective["id"])
content = await client.artifacts.download(artifact_id=artifacts[0]["id"])
```

**Supersede rather than delete when an artifact was wrong.** Deleting removes the
evidence that the wrong version ever existed, which is precisely what an auditor
asks about. Superseding keeps both and records which replaced which.

## The work lifecycle, end to end

```
   create ──► submit ──► clarify ◄──┐          the loop that stalls silently
                │                   │          if nobody answers
                ▼                   │
          task graph ───────────────┘
                │
                ▼
          trigger execution
                │
                ├──► requests ──► claim ──► findings ──► complete
                │
                ├──► decision raised ──► decide ──────────┐
                │                                          │
                ├──► agent escalation ──► resolve ─────────┤
                │                                          │
                ▼                                          ▼
          check completion ◄──────────────────────── work resumes
                │
                ▼
          complete ──► artifacts
```

Read it as: the left column is the objective's own progress, and the two branches
in the middle are the places it stops and waits for a human. **Both branches are
blocking and neither is a failure**, which is why an objective that has stopped
does not appear in any error query. If work has gone quiet, check
`api:GET /api/v1/decisions/pending` and
`api:GET /api/v1/agent-escalations/pending` before looking for a fault.

## Summary — what this chapter covered

| area              | entry point                                        | scale         |
| ----------------- | -------------------------------------------------- | ------------- |
| Objectives        | `execution.objectives` · `modules.work_objectives` | 37 operations |
| Work units        | `modules.work_objectives`                          | 25 operations |
| Requests          | `execution.requests`                               | 11 operations |
| Directives        | `modules.work_objectives`                          | 12 operations |
| Change requests   | `modules.work_objectives`                          | 9 operations  |
| Decisions         | `modules.decision_points`                          | 5 operations  |
| Review decisions  | `modules.decision_points`                          | 4 operations  |
| Approvals         | `standup.approvals`                                | 4 operations  |
| Escalation        | `modules.pools`                                    | 9 operations  |
| Agent escalations | `modules.work_objectives`                          | 5 operations  |
| Interventions     | `modules.work_objectives`                          | 7 operations  |
| Promotions        | `modules.promotions`                               | 11 operations |
| Positions         | `modules.positions`                                | 5 operations  |
| Artifacts         | `execution.artifacts`                              | 7 operations  |

---

_Next: [08.5 — Governance and trust](05-governance-and-trust.md)_
