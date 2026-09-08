# 02.6 — Approvals, holds and evidence

This is the chapter that closes the loop the whole product exists for. Aegis
stops and asks a human; a human answers; the question, the answer and the
reasoning become evidence someone else can inspect later.

## The approvals queue

```python
pending = await client.approvals.list_pending(agent_id=agent.id, limit=25)
for record in pending.get("records", []):
    await client.approvals.approve(
        record["id"],
        reviewed_by="user_head_treasury",
        reason="Within envelope; policy satisfied.",
    )
```

`api:GET /api/v1/approvals/pending`, then
`api:POST /api/v1/approvals/{id}/approve` or
`api:POST /api/v1/approvals/{id}/reject`. There is also
`client.approvals.modify(...)`, which approves a changed version of what was
asked — the middle answer between yes and no, and the one reviewers reach for
most once they know it exists.

**`reason` is not decoration.** It is the part of the record that answers *why*,
and it is the only part a future auditor cannot reconstruct from anything else.
"Approved" tells them what happened; it does not tell them whether the decision
was sound. Write the reason as though the reader is a stranger, because they are.

## ⚠ There is more than one queue, and this catches people

An approval is not the only thing that can be waiting on a person, and the
different kinds surface in different places:

| waiting on a person | where it is |
| --- | --- |
| an action held by the verification gradient | `api:GET /api/v1/approvals/pending` |
| a posture progression request | `api:GET /api/v1/posture/pending-approvals` |
| a pending role clearance | the clearance surface (02.3) |
| an escalated request | `api:GET /api/v1/agent-escalations/pending` |
| a pseudo-agent request needing a human to act | `api:GET /api/v1/pseudo-requests` |
| a change request against the organisation | `api:GET /api/v1/change-requests` |

So **an empty approvals queue does not mean nothing is waiting.** This is a real
source of confusion for operators, who reasonably read one empty queue as "all
clear" and leave a posture upgrade or a pending clearance sitting for weeks.

If you build one operational check, build the one that sweeps all six. Nothing in
the product does it for you.

Escalations have their own live channel at
`api:GET /api/v1/agent-escalations/stream`, and are resolved with
`api:POST /api/v1/agent-escalations/{id}/resolve` or cancelled with
`api:POST /api/v1/agent-escalations/{id}/cancel`.

## Change requests — governed change to the organisation itself

Structural change can go through review rather than being applied directly:

```
create   -> api:POST /api/v1/change-requests
submit   -> api:PATCH /api/v1/change-requests/{id}/submit
approve  -> api:PATCH /api/v1/change-requests/{id}/approve
deny     -> api:PATCH /api/v1/change-requests/{id}/deny
apply    -> api:PATCH /api/v1/change-requests/{id}/apply
```

There is also a counter-proposal path —
`api:PATCH /api/v1/change-requests/{id}/counter-propose` and
`api:PATCH /api/v1/change-requests/{id}/accept-counter` — which is how a reviewer
says "not that, but this" without rejecting outright.

**Note that approve and apply are separate steps.** An approved change request
has not changed anything yet. Same shape as draft envelopes, pending clearances
and unsubmitted objectives — the fourth instance in this part, and by now it
should read as the platform's consistent habit rather than a quirk: *describing*
and *effecting* are always two operations.

For an architect this is the mechanism that lets org changes be reviewed the way
code is. It is worth using for anything that touches envelopes or clearances,
which are precisely the changes nobody notices until they matter.

## The audit trail

Two surfaces, and they answer different questions.

**The general audit log** — operational, everything that happened:

```python
logs = await client.observe_audit.list_logs(...)
history = await client.observe_audit.resource_history("agent", agent_id)
activity = await client.observe_audit.user_activity(user_id)
```

`api:GET /api/v1/audit/logs`, `api:GET /api/v1/audit/logs/{id}`,
`api:GET /api/v1/audit/resources/{type}/{id}`,
`api:GET /api/v1/audit/users/{id}`, exported at `api:GET /api/v1/audit/export`.

**The trust audit** — governance, who delegated what and why (02.4):
`api:GET /api/v1/trust/audit`.

When someone asks "what did this agent do", the first is the answer. When they
ask "on whose authority", the second is.

## Evidence you can hand to a third party

This is the product's actual value proposition, so it is worth knowing the
operations by name.

```python
verification = await client.compliance.verify_audit(...)
export = await client.compliance.export_audit(...)
```

`api:GET /api/v1/compliance/audit/verify` — **verify the audit chain's
integrity**, and `api:POST /api/v1/compliance/audit/export` to export it, with
entries at `api:GET /api/v1/compliance/audit/entries`.

The verification operation is the one that matters and the one most operators
never run. A tamper-evident trail is only evidence if someone has checked that it
has not been tampered with; an unverified trail is a claim about itself. **Run
the verification on a schedule and keep the result** — a verification you ran
after an incident is worth much less than a series of them from before it.

The compliance module also carries SOC 2 evidence generation and export, HIPAA
enablement and settings, retention policies (list, create, update, execute), and
a dashboard at `client.compliance.get_dashboard()`.

### Retention deserves a deliberate decision

Retention policies decide how long the record survives. Set them knowingly:
evidence you discarded to save storage is evidence you cannot produce, and the
question is usually asked long after the decision. Conversely, a policy that
keeps everything forever has its own regulatory cost. This is a decision for the
organisation, not a default to inherit — but it is exactly the kind of default
that gets inherited.

## What the accountability actually rests on

The organisation deploying an agent keeps the accountability for what that agent
does. It cannot be delegated, and no amount of autonomy transfers it.

What this chapter's surfaces give you is the **proof** that the accountability
was discharged: the bounded mandate (02.3), the attestable lineage (02.4), the
human decision with its reasoning (this chapter), and a trail whose integrity can
be checked rather than asserted.

That proof is only as good as the habits behind it. Three that do most of the
work, and none of which the platform will do for you:

1. **Write real reasons on decisions.** A queue of "approved" with no reasoning
   is a record that a person clicked, not that a person decided.
2. **Verify the chain on a schedule, and keep the results.**
3. **Sweep all six waiting-queues, not just the approvals one.**

You keep the accountability. This gives you the evidence.

> **In the console:** the approvals queue is where a named human answers, and
> chapter 05.4 explains the same thing from that person's side — including why
> the approvals queue can be empty while something is genuinely held, which is
> the console-side face of the multiple-queues problem above.

---

*This is the last chapter of part 02. Next: [Part 03 — Extending the platform](../03-extending-the-platform/), or [Part 04 — The API surface](../04-the-api-surface/) if you are debugging a call.*
