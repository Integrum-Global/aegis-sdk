# 09.4 — The decision gradient

The Trust Plane does not return a boolean. It returns a position on a
four-zone gradient, and the zone determines not only whether the action proceeds
but who, if anyone, is told about it and what they can do.

This chapter is the delivery half of the governance argument. [09.2](02-envelopes-and-constraints.md)
and [09.3](03-clearance-and-classification.md) established what bounds an action
and what bounds a read; this chapter is what happens at the moment those bounds
are consulted — the four zones, who decides in each, how a held action reaches a
human, and the two escape hatches (emergency widening and the kill switch) that
exist for the cases the gradient cannot resolve on its own.

The idea to carry out: **a binary approve/reject collapses three genuinely
different outcomes into two, and the one it loses is the useful one.** `flagged`
— proceed, but tell somebody — is what makes autonomy survivable at scale,
because it is the zone that produces oversight without producing a queue.

## The four zones

| zone                | agent behaviour          | human involvement                  | latency cost         |
| ------------------- | ------------------------ | ---------------------------------- | -------------------- |
| **`auto_approved`** | proceeds autonomously    | none — observable after the fact   | none                 |
| **`flagged`**       | proceeds, human notified | notified; can intervene            | none to the agent    |
| **`held`**          | pauses for approval      | yes — a bounded, specific decision | blocks until decided |
| **`blocked`**       | cannot proceed           | none — denied automatically        | immediate refusal    |

The ordering is not a severity scale, and reading it as one leads to a design
where everything drifts toward `held`. The correct reading is **two independent
questions**:

```text
THE GRADIENT IS TWO AXES, NOT ONE DIAL

                    does the action PROCEED?
                    │
          YES ──────┼────── NO
                    │
  is a human   ┌────┴─────┬──────────────┐
  TOLD?        │          │              │
               │          │              │
        NO   ──┤ auto_    │   blocked    │  nobody is told because
               │ approved │              │  nobody needs to decide —
               │          │              │  the bound already did
        YES  ──┤ flagged  │   held       │
               │          │              │  a human is told because
               └──────────┴──────────────┘  a human must decide

  The LEFT column costs the agent nothing. The RIGHT column stops the work.
  The BOTTOM row costs a human's attention. The TOP row does not.

  A design that only uses the diagonal (auto_approved / blocked) has thrown
  away both of the zones that carry information.
```

Read it as: `flagged` buys you oversight for free, and `held` buys you a
decision at the cost of a human's attention and the agent's latency. The two
costs are genuinely different and should be spent on different things. Flag what
you want to _know about_; hold what you want to _decide_.

> ⛔ **Never implement `if approved: proceed else: deny` where the gradient
> applies.** The binary form has no way to express "this happened and you should
> look at it", so the actions that warrant attention either get promoted to
> `held` — producing an approval queue nobody can keep up with, which is
> abandoned within a fortnight — or demoted to `auto_approved`, where nothing
> records that anyone wanted to know. Both failure modes look like a working
> system until the incident review asks who saw it.

## Which zone an action lands in

Three things determine the zone, and they compose in this order:

1. **The action's own risk classification**, from the gradient rule set. Read the
   rules in force at `api:GET /api/v1/constraints/gradient-rules`.
2. **The agent's posture.** A `supervised` agent holds far more of its surface
   than a `delegated` one; this is most of what a posture _means_
   ([09.5](05-trust-chains-and-postures.md)).
3. **The envelope's `verification_defaults`**, which is the supervising role's
   handle on how thoroughly its delegate's actions are checked
   ([09.2](02-envelopes-and-constraints.md)).

An organisation-level policy authored at the `gate` tier targets this gradient
directly, carrying `{"zone": "flagged"|"held"|"blocked", "condition": "<text>"}`.
Note the absence: `auto_approved` is not a valid gate-tier target, and that is
correct rather than an omission — a policy that wants auto-approval is a policy
that should not exist, since the absence of a gate policy already produces
auto-approval.

```python
policy = await client.governance.create_policy(
    name="Outbound wires are held",
    node_address="D1-R1-D1-R1",
    enforcement_tier="gate",
    policy_body={"zone": "held", "condition": "action is an external wire transfer"},
)
```

`api:GET /api/v1/analytics/verification-gradient` is the aggregate view — how
the tenant's actions actually distributed across the four zones over a window.
It is the single most useful number for answering _is our governance calibrated_,
and the shape to look for is not a target percentage but a **non-degenerate
distribution**. All four zones should have traffic. A tenant whose actions are
99% `auto_approved` has a gradient that is not doing anything; a tenant with a
large `held` fraction has a gradient that operators are about to route around.

```python
distribution = await client.analytics.get_verification_gradient(days=30)
```

## Held — the human decision, and what makes it bounded

A `held` action does not stop the agent forever. It creates a specific decision,
for a specific human, with a specific set of options, and it waits.

```python
pending = await client.approvals.list_pending()
for item in pending.records:
    detail = await client.approvals.get(item.id)
```

| surface   | route                                     | what it carries                               |
| --------- | ----------------------------------------- | --------------------------------------------- |
| the queue | `api:GET /api/v1/approvals/pending`       | everything awaiting this principal            |
| one item  | `api:GET /api/v1/approvals/{id}`          | the action, the agent, the reason it was held |
| approve   | `api:POST /api/v1/approvals/{id}/approve` | releases the action                           |
| reject    | `api:POST /api/v1/approvals/{id}/reject`  | refuses it; the agent is told why             |

Decision points — a richer form, where the human is choosing between options
rather than approving a single action — have their own surface:
`api:GET /api/v1/decisions/pending`, `api:GET /api/v1/decisions/{id}`, and
`api:GET /api/v1/decisions/{id}/options` for the choices themselves. The
objective-scoped view is `api:GET /api/v1/objectives/{id}/decisions`.

**The property that makes a hold bounded rather than a blocker** is that the
decision is _specific_. A human is not being asked "should this agent be allowed
to operate"; they are being asked "should this particular wire, for this amount,
to this counterparty, go". That is a decision a domain expert can make in
seconds without understanding the platform, and it is why the hold zone scales at
all.

> ⚠ **A hold that nobody owns is an agent that stopped.** The decision routes to
> a human, and when the seat that human occupies is empty the routing walks _up_
> the reporting chain to the superior rather than stopping. That is the designed
> behaviour and it is what stops a vacancy severing a subtree. What it does not
> do is invent an approver: a hold routed to a chain whose upper reaches are also
> vacant sits in a queue with no reader, and the symptom is an objective that
> never completes and never errors. Put `api:GET /api/v1/approvals/pending` age
> on a dashboard.

## Escalation — when a hold ages

Holds that are not answered escalate, and escalation is its own surface rather
than a property of the hold.

| surface                             | route                                                |
| ----------------------------------- | ---------------------------------------------------- |
| what is currently escalating        | `api:GET /api/v1/escalation/pending`                 |
| the escalation chain for one task   | `api:GET /api/v1/escalation/tasks/{id}/history`      |
| escalation configuration for a unit | `api:GET /api/v1/escalation/config/{id}`             |
| aggregate                           | `api:GET /api/v1/escalation/stats`                   |
| acknowledge, stopping the clock     | `api:POST /api/v1/escalation/tasks/{id}/acknowledge` |

Agent-side escalations — an agent asking for help rather than a hold ageing out
— are `api:GET /api/v1/agent-escalations/pending`,
`api:GET /api/v1/agent-escalations/{id}` and the live feed at
`api:GET /api/v1/agent-escalations/stream`.

The design guidance here is one sentence: **escalation timeouts should be
shorter than the work's own deadline, and the chain should be shorter than you
think.** A three-hop escalation chain with a four-hour timeout per hop is a
twelve-hour delay on a decision somebody could have made immediately, and the
operational response to that is invariably to widen the envelope so the hold
stops happening — which removes the control rather than fixing the latency.

## Who may approve — distinctness, not seniority

Two properties bind every approval in the platform, and both are about identity
rather than rank.

**The approver's identity is derived server-side.** It comes from the
authenticated session, never from a field in the request body. An identity a
client can assert is an identity a client can forge, and an approval is exactly
the record that must not be able to lie about who made it.

**Self-approval is refused by distinctness, not by policy.** The requester and
the approver must be different principals. This is checked at the identity level
rather than at the role level, so holding two credentials does not produce two
approvers, and a service identity is never an eligible approver for a human
decision.

> ⛔ **Do not implement dual control by requiring two approvals from a queue
> anyone can read.** Two approvals from the same person under two credentials is
> one approval, and a design that counts rows rather than distinct principals
> will count it as two. Where genuine dual control is required, the platform's
> distinctness check is the mechanism — build on it rather than beside it.

The self-approval identity is pinned at creation time rather than re-resolved
when the decision is made. That matters in a re-org: an approval created while
someone held a role, decided after they left it, is still evaluated against the
identity that created it. Re-resolving from current role occupancy would let a
role change retroactively legalise a self-approval.

## The emergency path

Sometimes the correct answer is that the bound is wrong _right now_ and the work
cannot wait for the bound to be re-authored. The platform has a first-class path
for this and it is deliberately uncomfortable.

```python
bypass = await client.emergency.create(
    agent_id=agent_id,
    reason="Counterparty settlement failure; manual wire required within the hour.",
    duration_hours=4,
    widened_constraints={"financial": {"max_amount": 250000, "currency": "USD"}},
)
```

| surface                  | route                                                                                              |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| request one              | `api:POST /api/v1/emergency-bypass/create`                                                         |
| what is active right now | `api:GET /api/v1/emergency-bypass/active`                                                          |
| all of them              | `api:GET /api/v1/emergency-bypass`                                                                 |
| one                      | `api:GET /api/v1/emergency-bypass/{id}`                                                            |
| approve / reject         | `api:POST /api/v1/emergency-bypass/{id}/approve` · `api:POST /api/v1/emergency-bypass/{id}/reject` |
| end one early            | `api:POST /api/v1/emergency-bypass/{id}/revoke`                                                    |

Four properties make it safe enough to exist:

1. **It auto-expires, on a hard timer.** Default four hours, maximum
   seventy-two. Expiry is enforced deterministically rather than by an
   application-level check that happens to run — a bypass whose window closes
   while no request is in flight still closes.
2. **The approval level scales with the duration.** Up to four hours is the
   immediate supervisor's call; four to twenty-four goes two levels up;
   twenty-four to seventy-two requires C-suite. Beyond seventy-two hours it is
   not an emergency and the answer is to change the envelope properly.
3. **It cannot widen beyond the approver's own envelope.** The monotonic rule
   from [09.2](02-envelopes-and-constraints.md) still holds — an emergency
   widening is bounded by whoever authorised it, so nobody can grant authority
   they do not themselves have.
4. **It carries distinct audit anchors** and a post-incident review obligation
   within seven days. The record is deliberately separate from ordinary approval
   records so that "how often do we bypass" is a question with an answer.

> ⛔ **An emergency bypass with no expiry is not an emergency bypass.** The
> whole safety property is the hard timer; a widening that persists is simply a
> wider envelope, authored through a path with less review than the envelope
> would have had. The platform will not create one without an expiry. The failure
> mode to watch for in your own tooling is a scheduled job that re-creates the
> bypass as it lapses — which produces a permanent widening whose audit trail
> reads as a series of four-hour emergencies, and is the one shape a reviewer
> scanning `api:GET /api/v1/emergency-bypass` will spot immediately.

## The kill switch

The gradient handles actions. The kill switch handles situations, and it is the
only control in this part that operates on a class of work rather than on a
single decision.

```python
await client.kill_switch.activate(
    scope="agent",
    target_id=agent_id,
    reason="Anomalous outbound volume; halting pending investigation.",
)
open_switches = await client.kill_switch.list_open()
```

`api:POST /api/v1/kill-switch/activate` opens one,
`api:GET /api/v1/kill-switch/open` lists what is currently halted,
`api:GET /api/v1/kill-switch/{id}` reads one, and
`api:POST /api/v1/kill-switch/{id}/clear` ends it.

Choose between the four stop controls by blast radius and reversibility:

| control             | stops                             | reversible?         | reach for it when                    |
| ------------------- | --------------------------------- | ------------------- | ------------------------------------ |
| tighten constraints | one session's scope, partially    | yes, by re-widening | part of the work is still in scope   |
| pause               | one session                       | yes, `resume`       | you need time to look                |
| kill switch         | a class of work across the tenant | yes, `clear`        | you do not yet know the blast radius |
| revoke              | an agent's standing, permanently  | no                  | the decision is meant to be final    |

The last row is [09.5](05-trust-chains-and-postures.md)'s, and the distinction
between it and the kill switch is the one that matters in an incident. A kill
switch is a brake; revocation is a permanent removal that cascades to everything
that derived authority from the revoked agent. Reaching for revocation because
it feels more decisive is the mistake, and it is not undoable.

> **In the console:** held actions and decision points both surface in the
> operator inbox ([05.3](../05-the-web-console/03-your-inbox.md)), and a held
> action is what [05.4](../05-the-web-console/04-when-something-is-held.md) is
> about from the human side. Flagged actions do not appear there — by design,
> since they did not stop — and are read from the activity surfaces instead.
> "The agent did nothing and there is nothing in my inbox" usually means
> `blocked` rather than `held`: a blocked action produces no decision because
> there is nothing to decide.

## The delegation matrix — the gradient for an application

An application invoking agents on a user's behalf has its own version of the
same question: which agent may it invoke, for which user, in which zone. That is
the **delegation matrix**, and it is the gradient applied at the application
boundary rather than at the action boundary.

```python
matrix = await client.applications.get_delegation_matrix(application_id=app_id)
await client.applications.update_delegation_matrix(
    application_id=app_id,
    matrix=updated,
)
```

`api:GET /api/v1/applications/{id}/delegation-matrix` reads it and
`api:PUT /api/v1/applications/{id}/delegation-matrix` sets it. The application's
own record of what it actually did is
`api:GET /api/v1/applications/{id}/audit-events`, which is the surface to reach
for when the question is "what did this integration invoke last Tuesday" rather
than "what is it permitted to invoke".

The matrix is worth calling out separately because of a specific confusion:
**an application's grant and an agent's envelope are different bounds and both
apply.** An application authorised to invoke an agent does not thereby widen that
agent — the agent's envelope, posture and clearance are unchanged, and the
invocation is decided the same way any other invocation is. What the matrix
decides is whether the invocation is attempted at all.

The failure mode is granting through the matrix and expecting the agent to
become capable. The symptom is an integration that is correctly authorised, makes
the call successfully, and receives a constraint refusal — which reads as a
platform inconsistency and is the two bounds doing exactly their separate jobs.

## Designing a gradient that survives contact

Four pieces of guidance, in the order they matter.

**Start narrow and widen on evidence.** A new agent's surface should be mostly
`held`, and each action class should move to `flagged` and then `auto_approved`
as the posture evidence accumulates. That progression is the whole of
[09.5](05-trust-chains-and-postures.md), and doing it in the other direction —
starting permissive and tightening after an incident — produces a control whose
first calibration data point is the incident.

**Flag generously; hold sparingly.** Flagging costs the agent nothing and gives
you a record and a notification. It is the correct zone for the large class of
actions that are almost certainly fine and that somebody would want to know about
afterwards.

**Measure the queue, not the policy.** A `held` zone whose queue ages is a
control that is about to be removed. Watch queue depth and age on
`api:GET /api/v1/approvals/pending` and treat a growing queue as a calibration
failure rather than a staffing one.

**Make the emergency path pleasant enough to use.** The failure mode of a
painful bypass process is not that people wait — it is that they find a route
that does not go through it, and that route has no audit trail at all. Four
hours, one approver, one form field, and a review afterwards is a process people
follow.

## Summary

| you need                                 | the zone or control | the call                                          |
| ---------------------------------------- | ------------------- | ------------------------------------------------- |
| know an action happened                  | `flagged`           | gate-tier policy, `zone: flagged`                 |
| decide an action yourself                | `held`              | `api:GET /api/v1/approvals/pending`               |
| refuse an action outright                | `blocked`           | gate-tier policy, or the envelope refuses it      |
| see how the gradient is calibrated       | aggregate           | `api:GET /api/v1/analytics/verification-gradient` |
| read the rules in force                  | gradient rules      | `api:GET /api/v1/constraints/gradient-rules`      |
| widen a bound for hours, not permanently | emergency bypass    | `api:POST /api/v1/emergency-bypass/create`        |
| see what is currently widened            | active bypasses     | `api:GET /api/v1/emergency-bypass/active`         |
| halt a class of work now                 | kill switch         | `api:POST /api/v1/kill-switch/activate`           |
| stop one session and keep it             | intervention        | `api:POST /api/v1/interventions/{id}/pause`       |

---

_Next: [09.5 — Trust chains and postures](05-trust-chains-and-postures.md)_
