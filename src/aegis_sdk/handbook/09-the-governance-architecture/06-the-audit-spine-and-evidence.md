# 09.6 — The audit spine and evidence

Everything in the four preceding chapters decides something. This chapter is
about what is left afterwards — what is recorded, by which subsystem, how it is
queried, how it is shown to be intact, and how it becomes the artefact somebody
outside your organisation will accept.

This is where the product's actual claim is discharged. Aegis does not carry
your accountability for what your agents do; it gives you the proof that lets
you discharge it — bounded mandates you can show, human gates you can evidence,
a lineage that terminates at a named person, and a record whose integrity is
demonstrable rather than asserted.

The idea to carry out: **the decision and the record are different witnesses to
one event, and neither substitutes for the other.** The decision is about an
intent and is made before anything happens. The record is written after. A system
that can produce one and not the other cannot answer the question an auditor
actually asks, which is never "was something enforced" but "show me that it
was".

## Two logs, two questions

There are two distinct audit surfaces, they are written by different
subsystems, and conflating them is how an evidence request gets answered with
the wrong document.

|             | platform audit                              | trust audit                                         |
| ----------- | ------------------------------------------- | --------------------------------------------------- |
| **read at** | `api:GET /api/v1/audit/logs`                | `api:GET /api/v1/trust/audit`                       |
| **records** | user actions, resource changes              | trust decisions — who delegated what, on what basis |
| **module**  | `sdk:aegis_sdk.modules.ObserveAuditModule`  | `sdk:aegis_sdk.trust.AuditModule`                   |
| **answers** | "who changed this?"                         | "why was this agent allowed?"                       |
| **subject** | a resource and the principal who touched it | an agent and the authority it acted under           |

```python
changes = await client.observe_audit.list_logs(
    resource_type="role_envelope",
    limit=100,
)
decisions = await client.trust.audit.query(
    agent_id=agent_id,
    limit=100,
)
```

The platform log is the one to reach for when the question is about a _change_:
who edited this envelope, who approved this clearance, who moved this role.
Single entries are `api:GET /api/v1/audit/logs/{id}`, a resource's whole history
is `api:GET /api/v1/audit/resources/{type}/{id}`, and a principal's activity is
`api:GET /api/v1/audit/users/{id}`.

The trust log is the one to reach for when the question is about an _action_:
why was this agent permitted to do that, what chain was in force, what
capabilities matched. `api:POST /api/v1/trust/audit` records an entry;
`api:GET /api/v1/trust/audit/by-human/{id}` filters to everything that
originated with one person.

Two narrower surfaces exist and are worth knowing so you do not go looking for
their content in the two above. `api:GET /api/v1/settings/audit-log` records
configuration changes, with `api:POST /api/v1/settings/audit-log/revert` to undo
one. `api:GET /api/v1/admin/access/audit` records administrative access. And
`api:GET /api/v1/applications/{id}/audit-events` scopes to one application's
grants and invocations.

> ⚠ **"The audit log" is not one thing, and an evidence request phrased that way
> needs a clarifying question before it is answered.** The failure mode is an
> auditor asking for "the audit trail for this decision", being handed the
> platform log, finding nothing about the decision in it, and concluding the
> decision was not recorded. It was — in the other log. Name which surface you
> are quoting whenever you quote one.

## Walking a decision back to the human who authorised it

The trust audit's most valuable operation takes a single entry and walks its
lineage **backwards to the root human source** — the delegation chain, its depth,
and the person at the top.

```python
trace = await client.trust.audit.trace(entry_id=entry_id)
```

`api:GET /api/v1/trust/audit/trace/{id}` is the operation that discharges the
accountability claim in practice. An organisation can point at an action an
agent took, six months later, and name the human whose authority it descended
from — not by inference from an org chart, but from the chain that was actually
in force at the time.

That is the single most useful thing in this chapter, and it is worth building
your evidence process around it. When an incident review asks "who authorised
this", the answer is a call rather than a reconstruction.

> ⛔ **Read the `verified` flag on a trace with its own warning in hand.** That
> field reports signature verification and **defaults to true for an entry that
> carries no signature at all**. It therefore means _"no signature check
> failed"_, not _"this entry is cryptographically verified"_ — an unsigned entry
> and a validly signed one are indistinguishable on that field alone. Check
> whether the record carries a signature before treating the flag as evidence,
> and never report a trace as cryptographically verified on the strength of it.

## Is the log itself intact?

The audit log is tamper-evident, and there are two different reads for that
claim. They answer different questions and are frequently swapped.

| read                        | route                                        | what it does                                                 |
| --------------------------- | -------------------------------------------- | ------------------------------------------------------------ |
| **on-demand verification**  | `api:GET /api/v1/compliance/audit/verify`    | performs the hash-chain walk now, over an optional range     |
| **the last sweep's result** | `api:GET /api/v1/compliance/chain/integrity` | reads the result of the platform's own periodic verification |

```python
walk = await client.compliance.verify_audit(start_id=first, end_id=last)
integrity = await client.compliance.get_chain_integrity()
```

`api:GET /api/v1/compliance/audit/verify` returns whether the chain was valid,
how many entries were checked, and the id of the first invalid entry if tampering
was found. The entry count is the number to quote — "valid" over an unstated
range is a claim about an unknown population.

`api:GET /api/v1/compliance/chain/integrity` does not trigger a sweep; it reports
the last one.

> ⛔ **Check the last-verified timestamp before reading the ok flag.** A
> deployment that has not yet run a sweep reports _not ok_ — which is a "nothing
> has been checked yet" finding and not a "something is broken" one. Those two
> produce the same boolean and opposite alarms, and the timestamp is the only
> thing that distinguishes them. Read `last_verified_at` on a schedule of your
> own and alarm on staleness as well as on the flag; a sweep that stopped running
> six weeks ago reports `ok` forever.

`api:GET /api/v1/compliance/audit/entries` is the compliance-scoped entry
listing, and `api:POST /api/v1/compliance/audit/export` produces a portable copy
of it.

## Compliance frameworks

The platform models compliance frameworks as first-class objects with controls,
rather than as a report format. That distinction matters because it makes the
question _which control does this evidence satisfy_ answerable rather than
editorial.

```python
frameworks = await client.compliance.list_frameworks()
controls = await client.compliance.get_framework_controls(framework_id="soc2")
```

| read                                    | route                                                 |
| --------------------------------------- | ----------------------------------------------------- |
| which frameworks are modelled           | `api:GET /api/v1/compliance/frameworks`               |
| one framework                           | `api:GET /api/v1/compliance/frameworks/{id}`          |
| its controls                            | `api:GET /api/v1/compliance/frameworks/{id}/controls` |
| the current posture against all of them | `api:GET /api/v1/compliance/dashboard`                |
| a single score                          | `api:GET /api/v1/compliance/score`                    |
| open findings                           | `api:GET /api/v1/compliance/violations`               |
| the event stream behind them            | `api:GET /api/v1/compliance/events`                   |
| service health                          | `api:GET /api/v1/compliance/health`                   |

**SOC 2** has its own surfaces because the evidence package is a recurring
deliverable rather than a query: `api:GET /api/v1/compliance/soc2/status` reports
where you stand, `api:POST /api/v1/compliance/soc2/evidence` generates the
package, and `api:GET /api/v1/compliance/soc2/evidence/export` retrieves it.

**HIPAA** is a mode rather than a report, because it changes platform behaviour
rather than describing it: `api:POST /api/v1/compliance/hipaa/enable` and
`api:POST /api/v1/compliance/hipaa/disable` switch it,
`api:GET /api/v1/compliance/hipaa/settings` reads the configuration, and
`api:GET /api/v1/compliance/hipaa/status` reads the current state.

```python
await client.compliance.enable_hipaa()
status = await client.compliance.get_hipaa_status()
```

> ⚠ **Enabling a compliance mode is a change to how the deployment behaves, and
> it is recorded as one.** Treat it as you would an envelope change rather than
> as a settings toggle: decide it deliberately, record why, and expect the change
> itself to appear in the platform audit log. The symptom of treating it casually
> is a deployment whose compliance posture nobody can explain the history of,
> which is a worse position than not having enabled it.

Assessments and reports are `api:POST /api/v1/compliance/assess` to run one,
`api:POST /api/v1/compliance/reports` to generate a report,
`api:GET /api/v1/compliance/reports` to list them,
`api:GET /api/v1/compliance/report/summary` for the condensed form, and
`api:GET /api/v1/compliance/reports/{id}.pdf` for the document an auditor will
actually accept. `api:POST /api/v1/compliance/export` is the general export.
Alerts raised by an assessment are acknowledged at
`api:POST /api/v1/compliance/alerts/{id}/acknowledge`.

## Retention

Records that are kept forever are a liability as well as an asset, and retention
is modelled explicitly rather than left to infrastructure.

| surface                         | route                                            |
| ------------------------------- | ------------------------------------------------ |
| compliance retention policies   | `api:GET /api/v1/compliance/retention/policies`  |
| execute a retention pass        | `api:POST /api/v1/compliance/retention/execute`  |
| data-governance retention rules | `api:POST /api/v1/data-governance/retention`     |
| read one                        | `api:GET /api/v1/data-governance/retention/{id}` |
| amend one                       | `api:PUT /api/v1/data-governance/retention/{id}` |

The design guidance is short and consequential: **retention policy is a
governance decision, not an operational one, and the person who sets it should
not be the person who runs it.** A retention pass deletes evidence. Authoring the
policy and executing it are separate calls precisely so they can be separately
authorised, and a deployment where the same automation does both has removed the
step where somebody notices the window is wrong.

## Consent and lineage

Two data-governance surfaces belong in an evidence chapter because they answer
questions auditors ask that the audit logs cannot.

**Consent** records that a subject permitted a use, and is queried rather than
inferred. `api:POST /api/v1/data-governance/consents` records one,
`api:POST /api/v1/data-governance/consents/check` tests whether a given use is
covered, `api:GET /api/v1/data-governance/consents` and
`api:GET /api/v1/data-governance/consents/{id}` read them back, and
`api:POST /api/v1/data-governance/consents/{id}/withdraw` withdraws one.

```python
covered = await client.governance.check_consent(
    subject_id=subject_id,
    purpose="model_training",
)
```

**Lineage** records where data came from and where it went.

| read            | route                                                           | answers                               |
| --------------- | --------------------------------------------------------------- | ------------------------------------- |
| the whole graph | `api:GET /api/v1/data-governance/lineage/graph`                 | the shape                             |
| one node        | `api:GET /api/v1/data-governance/lineage/nodes/{id}`            | what it is                            |
| what fed it     | `api:GET /api/v1/data-governance/lineage/nodes/{id}/upstream`   | provenance                            |
| what it fed     | `api:GET /api/v1/data-governance/lineage/nodes/{id}/downstream` | propagation                           |
| blast radius    | `api:GET /api/v1/data-governance/lineage/nodes/{id}/impact`     | what a change or a withdrawal touches |

Nodes and edges are declared with `api:POST /api/v1/data-governance/lineage/nodes`
and `api:POST /api/v1/data-governance/lineage/edges`.

The **impact** read is the one that earns its place. When a consent is withdrawn
or a source is found to have been mis-classified, the question is not "what is
this" but "what did this touch" — and answering it by search rather than by
lineage is how a remediation misses the derived artefact that carries the same
sensitivity under a different name. [09.7](07-containment-and-explainable-refusal.md)
carries the classification half of the same argument.

## What an evidence request actually looks like

Four questions cover almost every request, and each has one primary surface.

| the question                            | the surface                                                      | what you hand over                                             |
| --------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------- |
| _"What bounded this agent?"_            | `api:GET /api/v1/constraints/agents/{id}/effective`              | the composed envelope, plus its ancestors from `.../inherited` |
| _"Who decided it could act?"_           | `api:GET /api/v1/trust/audit/trace/{id}`                         | the lineage walk to a named human                              |
| _"What was recorded?"_                  | `api:GET /api/v1/audit/export` and `api:GET /api/v1/trust/audit` | both logs, scoped to the window                                |
| _"How do I know the record is intact?"_ | `api:GET /api/v1/compliance/audit/verify`                        | the hash-chain walk, with its entry count                      |

```python
bundle = {
    "bounds": await client.governance.get_agent_constraints(
        agent_id=agent_id, resolution="effective"
    ),
    "authority": await client.trust.audit.trace(entry_id=entry_id),
    "decisions": await client.trust.audit.query(agent_id=agent_id),
    "integrity": await client.compliance.verify_audit(),
}
```

A fifth question arrives in any engagement that has read
[09.5](05-trust-chains-and-postures.md): _"was this agent's autonomy earned?"_
The answer is `api:GET /api/v1/agents/{id}/trust-posture/history` alongside
`api:GET /api/v1/agents/{id}/trust-posture/evidence`, and it is the one most
likely to surprise you the first time you run it.

> ⛔ **Run the evidence bundle before the audit, not during it.** Every surface
> above is a query, and every query has a shape you will want to have seen once
> already. The findings that cost the most are structural rather than
> substantive — a tenant whose whole authority structure descends from a service
> account, a posture history that is all overrides, a chain-integrity sweep that
> has never run. None of those is a breach and all three are difficult to explain
> under time pressure. All three are visible in a single afternoon.

## One event, both logs

The clearest way to internalise the split is to follow a single action through
it. An analyst agent drafts an outbound wire; the gradient holds it; a treasury
lead approves; the wire is drafted.

```text
ONE ACTION — WHAT EACH LOG RECORDS

  TRUST AUDIT                               PLATFORM AUDIT
  ─────────────────────────────────────     ─────────────────────────────────
  the agent's chain was resolved            —
  the envelope permitted a draft            —
  the posture placed it in `held`           —
  —                                         the approval row was created
  —                                         the lead approved it (who, when)
  the decision was re-evaluated and          —
    permitted
  —                                         the draft artifact was created
  ─────────────────────────────────────     ─────────────────────────────────
  answers: on whose authority,              answers: who did what,
           against which bounds                      to which resource

  NEITHER log contains the other's rows. The approval is a RESOURCE CHANGE
  and lives in the platform log; the decision it unblocked is a TRUST
  DECISION and lives in the trust log. An evidence bundle for this single
  action needs BOTH, plus the trace that joins them.
```

Read it as: the join between the two logs is the action, and the operation that
performs the join is the lineage trace. That is why the trace matters more than
either listing — it is the only surface that takes a point in one log and walks
to the authority behind it.

The record shape itself is `sdk:aegis_sdk.TrustAuditEntry`, and queries against
it are expressed as `sdk:aegis_sdk.TrustAuditQuery`. Three fields on an entry do
most of the work in an evidence conversation:

| field                          | what it settles                                                        |
| ------------------------------ | ---------------------------------------------------------------------- |
| the agent and the action       | _what was decided_, precisely enough to match against a policy         |
| the chain in force at the time | _on whose authority_ — and it is the chain as it was, not as it is now |
| the reason                     | _why_ the verdict went the way it did, in the engine's own words       |

The middle one is the property people assume and should verify: the entry
records the chain **as it stood at the decision**, so a later revocation does not
retroactively change what the record says was permitted. That is what makes the
log usable as evidence of a past state rather than as a view of the present one.

## Exports, and what makes them portable

`api:GET /api/v1/audit/export` produces the platform log in a form you can hand
over. `api:GET /api/v1/trust/metrics/export` does the same for trust metrics.
`api:GET /api/v1/compliance/soc2/evidence/export` produces the SOC 2 package.

Two properties make an export defensible rather than merely large:

**It names its range.** An export with no stated window is a claim about an
unknown population, and the first thing a competent reviewer will ask is what it
excluded. State the window in the request and carry it into whatever you hand
over.

**It is paired with an integrity walk over the same range.**
`api:GET /api/v1/compliance/audit/verify` accepts start and end bounds for this
reason. An export plus a verification over the same bounds is a materially
stronger artefact than either alone, because together they say _this is what
happened, and here is why you can believe the record was not altered_.

> **In the console:** the compliance area carries the dashboard, the framework
> status surfaces and the report list, and generated reports appear there for
> download rather than arriving by any other route. The audit surfaces are
> deliberately read-only in the console — the only audit-adjacent write is the
> settings revert, which is itself recorded.

## Summary

| you need                            | the surface          | the call                                                    |
| ----------------------------------- | -------------------- | ----------------------------------------------------------- |
| who changed this resource           | platform audit       | `api:GET /api/v1/audit/resources/{type}/{id}`               |
| why this agent was allowed          | trust audit          | `api:GET /api/v1/trust/audit`                               |
| the human behind an action          | lineage trace        | `api:GET /api/v1/trust/audit/trace/{id}`                    |
| everything from one person          | by-human filter      | `api:GET /api/v1/trust/audit/by-human/{id}`                 |
| prove the log is unaltered          | hash-chain walk      | `api:GET /api/v1/compliance/audit/verify`                   |
| the last sweep's verdict            | chain integrity      | `api:GET /api/v1/compliance/chain/integrity`                |
| where you stand against a framework | compliance dashboard | `api:GET /api/v1/compliance/dashboard`                      |
| the SOC 2 package                   | evidence export      | `api:GET /api/v1/compliance/soc2/evidence/export`           |
| a document to hand over             | report PDF           | `api:GET /api/v1/compliance/reports/{id}.pdf`               |
| what a withdrawal would touch       | lineage impact       | `api:GET /api/v1/data-governance/lineage/nodes/{id}/impact` |
| bound how long records are kept     | retention policy     | `api:POST /api/v1/data-governance/retention`                |

---

_Next: [09.7 — Containment and explainable refusal](07-containment-and-explainable-refusal.md)_
