---
name: day-two-operations
description: The operator's recurring loop against a running Aegis — work the queues, sweep the states that hide, produce evidence, and hand decisions to the people who own them.
---

# Day-two operations

For the operator, not the builder. The platform is running. This is the loop you
run on a cadence, and the order is chosen so that the cheap checks eliminate the
expensive investigations.

## Before the loop — establish your instrument, once per session

```bash
python -m aegis_sdk.coc.probe --base-url "$URL" --api-key "$KEY" --token "$TOK"
```

Two things this gives you that nothing else does: which reads your credential can
actually perform, and an exit code that distinguishes *nothing wrong* from *I
could not tell* (`3` UNDETERMINED, never `0`).

**Why first:** every sweep below can return empty because there is nothing to
find, or because you cannot see it. Knowing which reads you can perform turns the
first case into information and the second into a known blind spot rather than a
false all-clear.

## 1. The queues — things waiting on a human

```python
await client.trust_posture.get_pending_posture_approvals()
await client.approvals.list_pending(...)
await client.work_objectives.list_pending_escalations(...)
```

Those read `api:GET /api/v1/posture/pending-approvals` and
`api:GET /api/v1/approvals/pending`; a single request is
`api:GET /api/v1/approvals/{id}`.

For each item: **who owns this decision, and do they know it is waiting?** That
is the whole job. An operator does not decide these; an operator makes sure the
decider has what they need and that nothing is ageing silently.

```
# DO      route it, with the objective, the requester, and why it was held
# DO NOT  approve it because the queue is long
```

## 2. Escalations — the ones that already failed to resolve themselves

```python
await client.work_objectives.list_agent_escalations(...)
await client.work_objectives.get_escalation_stats(...)
```

An escalation that has been open longer than its configured window is a finding
even if nothing is obviously wrong with it. Ageing is the signal.

## 3. The sweeps that hide their own emptiness

Run each, and for each ask the question in the right-hand column **before**
recording the result.

| sweep | ask first |
| --- | --- |
| `client.observe_audit.list_logs(...)` | can this query return a row at all? |
| `client.compliance.verify_audit(...)` | when did the verifier last actually run? |
| `client.analytics.sla(...)` | is the rate null, or genuinely zero? |
| `client.trust.chains` integrity | verified, broken, or **unverified**? |

**The technique, and it is one technique applied four times:** run the query over
a window containing an event you already know about. If it returns your known
event, an empty result elsewhere is information. If it does not, you have found a
broken instrument, which is a more urgent finding than anything the sweep was
looking for.

## 4. Spend and quota

```python
await client.revenue.quotas.get()
await client.revenue.usage.<the usage read for your build>
```

⚠ **Do not gate anything on the client-side quota check.** It answers `allowed=
True` for an unknown resource type and treats a limit of zero as unlimited — both
fail-open. It is a hint. The server's refusal is the control.
[Billing integrity](../guardrails/billing-integrity.md) and
[sentinels and defaults](../guardrails/sentinels-and-defaults.md) have the
mechanisms.

Watch for the `409` on a usage correction specifically. It is one of the few
responses here that means *a person needs to look at this now*, because it
usually means a customer has already been over-charged and the meter cannot take
the correction back.

## 5. Evidence — produce it as an artifact, not as a summary

```python
await client.compliance.export_audit(...)
await client.compliance.generate_soc2_evidence(...)
await client.trust_posture.get_posture_history(agent_id)
```

Every export must carry, in the same place as the data: **the credential type**,
**the organisation**, **the window**, and **the time it was taken**. An export
without those is not evidence — a third party cannot tell whose view it is.

**And be plain about what it establishes.** These are records. A clean export is
evidence that the recorded events were as stated; it is not evidence that the
conduct was. Nothing in this loop observes an execution being stopped.

## 6. Closing the loop — the handover note

State, for the period: what you swept, what you could not see, what is ageing,
what you routed and to whom, and what you changed. **List the blind spots
explicitly** — the reads your credential could not perform are part of the
report, not an omission from it.

```
# DO      "audit sweep clean for org <X>, session credential, 00:00–24:00 UTC.
#          BLIND: interventions and sessions are unreachable with this credential.
#          Chain integrity UNVERIFIED — last sweep null. 2 approvals ageing >48h,
#          routed to <owner>."
# DO NOT  "all clear"
```

## Where the console is the right answer

Working a long approval queue, comparing artifacts, and anything where you are
forming a judgement about a specific customer. The harness is the default because
it is reproducible and leaves a receipt; it is not better at helping you *look*
at something. Switch surfaces deliberately and say in the note which one you
used — a decision taken in the console and a decision taken here are equally valid and
leave different traces.

## What this skill does not cover

Infrastructure. Restarts, scaling, network and storage are not reachable from the
client and are not yours from here. If the answer is "the deployment is
unhealthy", your output is the evidence that says so, routed to whoever operates
the infrastructure.
