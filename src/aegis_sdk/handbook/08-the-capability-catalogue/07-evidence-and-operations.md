# 08.7 — Evidence and operations

This chapter enumerates **what the platform recorded about itself** and **how you
get it out**. It is the part of the catalogue a compliance reviewer reads first,
and the part an architect reaches for when something has already gone wrong.

The organising distinction is between **evidence** and **telemetry**, and they
are not the same asset. Evidence is the append-only, verifiable record of what
happened and who authorised it — it is produced for an auditor, it does not
change, and its integrity is itself checkable. Telemetry is measurement:
aggregated, sampled, useful for operating the system, and not something you would
put in front of a regulator.

**Aegis provides the proof; the deploying organisation keeps the
accountability.** That is the whole purpose of this chapter's surface — it exists
so that your organisation can evidence its own governance to whoever asks, not so
that the evidence-keeping becomes someone else's problem.

## The audit spine

The append-only record. Every governed act lands here, attributed along the trust
chain that authorised it.

| capability           | what it does                                    |
| -------------------- | ----------------------------------------------- |
| **List logs**        | Query the audit record                          |
| **Get log**          | One entry in full                               |
| **User activity**    | Everything one principal did                    |
| **Resource history** | Everything that happened to one resource        |
| **Export**           | Extract a set of entries for external retention |

Entry point: `sdk:aegis_sdk.modules.observe_audit.ObserveAuditModule`.

Operations: `api:GET /api/v1/audit/logs` · `api:GET /api/v1/audit/logs/{id}` ·
`api:GET /api/v1/audit/users/{user_id}` ·
`api:GET /api/v1/audit/resources/{resource_type}/{resource_id}` ·
`api:GET /api/v1/audit/export`

```python
history = await client.observe_audit.resource_history(
    resource_type="objective",
    resource_id=objective["id"],
)
activity = await client.observe_audit.user_activity(
    user_id=departing_user_id,
    since="2026-01-01T00:00:00Z",
)
```

The trust-specific face of the same spine —
`api:GET /api/v1/trust/audit/trace/{event_id}` and
`api:GET /api/v1/trust/audit/by-human/{human_id}` — is catalogued in
[08.5](05-governance-and-trust.md). Use the trust surface when the question is
_by what authority_; use this one when the question is _what happened to this
thing_.

## Alert thresholds

Turning the audit stream into notification: thresholds that fire, and a lifecycle
for what fires.

| capability                   | what it does                      |
| ---------------------------- | --------------------------------- |
| **List / create thresholds** | Define what should raise an alert |
| **Acknowledge**              | Record that someone has seen it   |
| **Resolve**                  | Close it out                      |

Entry point: `sdk:aegis_sdk.modules.observe_audit.ObserveAuditModule`.

Operations: `api:GET /api/v1/alerts/thresholds` ·
`api:POST /api/v1/alerts/thresholds` ·
`api:POST /api/v1/alerts/{id}/acknowledge` ·
`api:POST /api/v1/alerts/{id}/resolve`

**An acknowledged alert is not a resolved alert**, and a dashboard that counts
only unacknowledged ones hides every problem someone has looked at and not fixed.
Query both states.

## Compliance

The largest evidence surface: frameworks, controls, assessment, scoring,
evidence generation, and reports.

### Frameworks and assessment

| capability                | what it does                                       |
| ------------------------- | -------------------------------------------------- |
| **List / get frameworks** | Which compliance frameworks this deployment tracks |
| **Framework controls**    | The individual controls within one                 |
| **Run assessment**        | Evaluate the organisation against a framework      |
| **Score**                 | The current compliance score                       |
| **Dashboard**             | The compliance position at a glance                |
| **Events**                | Compliance-relevant events                         |
| **Violations**            | Where the organisation is out of compliance        |
| **Acknowledge alert**     | Record attention on a compliance alert             |
| **Health**                | Whether the compliance subsystem itself is sound   |

### Audit verification

| capability             | what it does                                      |
| ---------------------- | ------------------------------------------------- |
| **Verify audit**       | Check the audit record has not been tampered with |
| **Chain integrity**    | Verify the cryptographic chain over the record    |
| **List audit entries** | The compliance view of the audit spine            |
| **Export audit**       | Extract audit evidence                            |

### SOC 2 and HIPAA

| capability                  | what it does                                       |
| --------------------------- | -------------------------------------------------- |
| **SOC 2 status**            | Where the organisation stands                      |
| **Generate SOC 2 evidence** | Produce the evidence pack                          |
| **Export SOC 2 evidence**   | Extract it                                         |
| **HIPAA status / settings** | Whether HIPAA mode is on, and how it is configured |
| **Enable / disable HIPAA**  | Turn the regime on or off                          |

### Retention and reports

| capability                        | what it does                         |
| --------------------------------- | ------------------------------------ |
| **List / get retention policies** | What is kept, and for how long       |
| **Create / update policy**        | Define retention                     |
| **Execute retention**             | Apply it — deletes what has aged out |
| **Create / list / get report**    | Compliance reports                   |
| **Report summary**                | The headline view                    |
| **Report PDF**                    | The report as a document             |
| **Export report**                 | Extract it                           |

Entry point: `sdk:aegis_sdk.modules.compliance.ComplianceModule`.

Operations — frameworks and assessment:
`api:GET /api/v1/compliance/frameworks` ·
`api:GET /api/v1/compliance/frameworks/{id}` ·
`api:GET /api/v1/compliance/frameworks/{id}/controls` ·
`api:POST /api/v1/compliance/assess` · `api:GET /api/v1/compliance/score` ·
`api:GET /api/v1/compliance/dashboard` ·
`api:GET /api/v1/compliance/events` ·
`api:GET /api/v1/compliance/violations` ·
`api:POST /api/v1/compliance/alerts/{id}/acknowledge` ·
`api:GET /api/v1/compliance/health`

Verification: `api:GET /api/v1/compliance/audit/verify` ·
`api:GET /api/v1/compliance/chain/integrity` ·
`api:GET /api/v1/compliance/audit/entries` ·
`api:POST /api/v1/compliance/audit/export`

SOC 2 and HIPAA: `api:GET /api/v1/compliance/soc2/status` ·
`api:POST /api/v1/compliance/soc2/evidence` ·
`api:GET /api/v1/compliance/soc2/evidence/export` ·
`api:GET /api/v1/compliance/hipaa/status` ·
`api:GET /api/v1/compliance/hipaa/settings` ·
`api:POST /api/v1/compliance/hipaa/enable` ·
`api:POST /api/v1/compliance/hipaa/disable`

Retention and reports: `api:GET /api/v1/compliance/retention/policies` ·
`api:POST /api/v1/compliance/retention/execute` ·
`api:GET /api/v1/compliance/reports` ·
`api:POST /api/v1/compliance/reports` ·
`api:GET /api/v1/compliance/report/summary` ·
`api:GET /api/v1/compliance/reports/{id}.pdf` ·
`api:POST /api/v1/compliance/export`

```python
integrity = await client.compliance.get_chain_integrity()
if not integrity["valid"]:
    raise RuntimeError("audit chain integrity check failed")

await client.compliance.run_assessment(framework="soc2")
evidence = await client.compliance.generate_soc2_evidence(
    period_start="2026-07-01",
    period_end="2026-09-30",
)
```

> ⛔ **Verify the chain before you present the evidence, not after.**
> `api:GET /api/v1/compliance/chain/integrity` is what makes an evidence pack
> worth anything — an export taken from an unverified record is a document, not
> evidence. The check is cheap and it is the one thing a reviewer will ask you
> whether you ran.

> ⛔ **`api:POST /api/v1/compliance/retention/execute` deletes.** It applies the
> retention policies, which means it removes records that have aged past their
> window. Run `api:GET /api/v1/compliance/retention/policies` and read what is
> about to be applied first — a policy with a wrong window destroys evidence you
> are required to hold, and the deletion is not reversible.

**Enabling HIPAA mode changes platform behaviour, not just a flag.** It tightens
handling requirements across data surfaces. Enable it in a non-production
environment first and confirm your integrations still function — the symptom of
enabling it late is a set of refusals on paths that worked yesterday.

## Analytics

Aggregate measurement over work, agents, pools and cost. This is telemetry — use
it to operate the system, not to evidence it.

| capability                     | what it does                                        |
| ------------------------------ | --------------------------------------------------- |
| **Overview**                   | The headline numbers                                |
| **Summary**                    | A composed multi-section view                       |
| **Tasks**                      | Task throughput and outcomes                        |
| **Agents / agent performance** | Per-agent measurement                               |
| **Top agents**                 | The most active                                     |
| **Pools / pool utilization**   | How heavily pools are used                          |
| **Costs / cost breakdown**     | What it is costing, and where                       |
| **Export costs / metrics**     | Extract for external analysis                       |
| **Trends**                     | Completion rate over time                           |
| **Usage history / breakdown**  | Consumption over time and by dimension              |
| **SLA**                        | Service-level measurement                           |
| **HITL**                       | How much human-in-the-loop involvement is occurring |
| **Verification gradient**      | The distribution of decisions across the gradient   |
| **Workspace / team metrics**   | Measurement scoped to a workspace or team           |

Entry point: `sdk:aegis_sdk.modules.analytics.AnalyticsModule`.

Operations: `api:GET /api/v1/analytics/overview` ·
`api:GET /api/v1/analytics/summary` · `api:GET /api/v1/analytics/tasks` ·
`api:GET /api/v1/analytics/agents` ·
`api:GET /api/v1/analytics/agents/{agent_id}/performance` ·
`api:GET /api/v1/analytics/top-agents` · `api:GET /api/v1/analytics/pools` ·
`api:GET /api/v1/analytics/pools/{pool_id}/utilization` ·
`api:GET /api/v1/analytics/costs` · `api:GET /api/v1/analytics/export` ·
`api:GET /api/v1/analytics/trends/completion-rate` ·
`api:GET /api/v1/analytics/sla` · `api:GET /api/v1/analytics/hitl` ·
`api:GET /api/v1/analytics/verification-gradient` ·
`api:GET /api/v1/analytics/workspaces/{workspace_id}` ·
`api:GET /api/v1/analytics/teams/{team_id}`

```python
overview = await client.analytics.overview(period="30d")
gradient = await client.analytics.verification_gradient()
costs = await client.analytics.cost_breakdown(group_by="agent")
```

**`verification-gradient` is the most under-used call in this chapter.** It shows
how decisions are distributing across auto-approved, flagged, held and blocked —
and a governed organisation whose gradient is 99% auto-approved is either very
well tuned or not enforcing anything. The distribution is the diagnostic; the
count of blocked actions alone is not.

## Metrics

Lower-level than analytics: the operational measures, including a recording
surface for your own.

| capability             | what it does                                                             |
| ---------------------- | ------------------------------------------------------------------------ |
| **Dashboard**          | The operational dashboard numbers                                        |
| **Summary**            | Rolled-up measures                                                       |
| **Timeseries**         | Measures over time                                                       |
| **Executions**         | Execution-level measurement                                              |
| **Errors**             | The top errors                                                           |
| **Agent metrics**      | Per-agent operational measures                                           |
| **Deployment metrics** | Per-deployment measures — see [08.8](08-commercial-and-extensibility.md) |
| **Record**             | Push your own metric                                                     |

Entry point: `sdk:aegis_sdk.modules.metrics.MetricsModule`.

Operations: `api:GET /api/v1/metrics/dashboard` ·
`api:GET /api/v1/metrics/summary` · `api:GET /api/v1/metrics/timeseries` ·
`api:GET /api/v1/metrics/executions` · `api:GET /api/v1/metrics/errors` ·
`api:GET /api/v1/metrics/agents/{agent_id}` ·
`api:GET /api/v1/metrics/deployments/{deployment_id}` ·
`api:POST /api/v1/metrics/record`

```python
await client.metrics.record_metric(
    name="reconciliation.unmatched_entries",
    value=12,
    labels={"ledger": "4400", "period": "2026-09"},
)
errors = await client.metrics.top_errors(period="24h")
```

## Invocation analytics

Measurement scoped to invocations — who called what, how often, at what cost.
This is the surface that answers commercial questions about usage.

| capability         | what it does                          |
| ------------------ | ------------------------------------- |
| **Summary**        | Invocation totals                     |
| **By application** | Grouped by the calling application    |
| **By agent**       | Grouped by the agent invoked          |
| **SDK overview**   | Measurement of SDK-originated traffic |

Entry point: `sdk:aegis_sdk.modules.metrics.MetricsModule`.

Operations: `api:GET /api/v1/invocation-analytics/summary` ·
`api:GET /api/v1/invocation-analytics/by-application` ·
`api:GET /api/v1/invocation-analytics/by-agent` ·
`api:GET /api/v1/sdk-metrics/overview`

## Notifications

Getting things in front of people. Notifications have channels, per-user
preferences, and a live stream.

| capability                                  | what it does                         |
| ------------------------------------------- | ------------------------------------ |
| **List / get**                              | The notification queue               |
| **Mark read** (one, many, all)              | Clear notifications                  |
| **Delete** (one, many, all)                 | Remove them                          |
| **Stats**                                   | Queue depth and read rates           |
| **List / create / update / delete channel** | Manage delivery channels             |
| **Get channel / test channel**              | Inspect one, and confirm it delivers |
| **Get / update preferences**                | Per-user notification settings       |
| **Stream**                                  | Consume notifications live over SSE  |

Entry point: `sdk:aegis_sdk.modules.notifications.NotificationsModule`.

Operations: `api:GET /api/v1/notifications` ·
`api:GET /api/v1/notifications/{id}` ·
`api:PATCH /api/v1/notifications/{id}/read` ·
`api:PATCH /api/v1/notifications/read` ·
`api:PATCH /api/v1/notifications/read-all` ·
`api:DELETE /api/v1/notifications/{id}` ·
`api:DELETE /api/v1/notifications` ·
`api:DELETE /api/v1/notifications/all` ·
`api:GET /api/v1/notifications/stats` ·
`api:GET /api/v1/notifications/channels` ·
`api:POST /api/v1/notifications/channels` ·
`api:GET /api/v1/notifications/channels/{id}` ·
`api:PUT /api/v1/notifications/channels/{id}` ·
`api:DELETE /api/v1/notifications/channels/{id}` ·
`api:POST /api/v1/notifications/channels/{id}/test` ·
`api:GET /api/v1/notifications/preferences` ·
`api:PUT /api/v1/notifications/preferences` ·
`api:GET /api/v1/notifications/stream/sse`

```python
await client.notifications.test_channel(channel_id=ops_channel_id)

async for note in client.notifications.stream():
    handle(note)
```

**Test the channel when you create it.** An untested notification channel
accepts every notification and delivers none, and the symptom is a held decision
nobody answers — which reads as an unresponsive team rather than as a broken
channel. This is the same failure shape as an untested pseudo-agent channel in
[08.3](03-agents-and-execution.md), and it is worth checking both together.

## Webhooks

Outbound integration: the platform calls you when something happens.

| capability                   | what it does                         |
| ---------------------------- | ------------------------------------ |
| **Create / update / delete** | Manage a webhook                     |
| **List / get**               | Enumerate them                       |
| **Event types**              | Which events you may subscribe to    |
| **Test**                     | Fire a test delivery                 |
| **Deliveries**               | The delivery history for one webhook |
| **Retry delivery**           | Re-send a failed delivery            |
| **Rotate secret**            | Change the signing secret            |

Entry point: `sdk:aegis_sdk.modules.webhooks.WebhooksModule`.

Operations: `api:POST /api/v1/webhooks` · `api:GET /api/v1/webhooks` ·
`api:GET /api/v1/webhooks/{id}` · `api:PUT /api/v1/webhooks/{id}` ·
`api:DELETE /api/v1/webhooks/{id}` · `api:GET /api/v1/webhooks/events` ·
`api:POST /api/v1/webhooks/{id}/test` ·
`api:GET /api/v1/webhooks/{id}/deliveries` ·
`api:POST /api/v1/webhooks/deliveries/{delivery_id}/retry` ·
`api:POST /api/v1/webhooks/{id}/rotate-secret`

```python
hook = await client.webhooks.create(
    url="https://ops.example.com/aegis-events",
    events=["objective.completed", "decision.raised", "trust.revoked"],
)
await client.webhooks.test(webhook_id=hook["id"])

failed = await client.webhooks.get_deliveries(webhook_id=hook["id"], status="failed")
```

> ⚠ **Check deliveries, not just the webhook record.** A webhook whose endpoint
> started returning errors keeps its `active` state and stops delivering. The
> webhook listing looks healthy; the deliveries listing is where the failures
> are. Rotate the secret on any suspicion of exposure — it is a single call and
> it invalidates every signature an attacker might have captured.

## Settings

Organisation and user configuration, with backup, export, import and an audit log
of its own.

| capability                        | what it does                                    |
| --------------------------------- | ----------------------------------------------- |
| **Get / update organisation**     | Organisation-wide settings                      |
| **Get / update user**             | Per-user settings                               |
| **List / create / delete backup** | Snapshot settings                               |
| **Restore backup**                | Return to a snapshot                            |
| **Export**                        | Extract settings                                |
| **Import / preview import**       | Apply settings from elsewhere, previewing first |
| **Audit log / get entry**         | What changed, when, and by whom                 |
| **Revert audit entry**            | Undo one settings change                        |
| **Site config**                   | Public-facing configuration                     |

Entry point: `sdk:aegis_sdk.modules.settings.SettingsModule`.

Operations: `api:GET /api/v1/settings/organization` ·
`api:PUT /api/v1/settings/organization` · `api:GET /api/v1/settings/user` ·
`api:PUT /api/v1/settings/user` · `api:GET /api/v1/settings/backups` ·
`api:POST /api/v1/settings/backups` ·
`api:POST /api/v1/settings/backups/restore/{backup_id}` ·
`api:DELETE /api/v1/settings/backups/{backup_id}` ·
`api:POST /api/v1/settings/export` · `api:POST /api/v1/settings/import` ·
`api:POST /api/v1/settings/import/preview` ·
`api:GET /api/v1/settings/audit-log` ·
`api:GET /api/v1/settings/audit-log/{id}` ·
`api:POST /api/v1/settings/audit-log/revert` ·
`api:GET /api/v1/site-config` · `api:PUT /api/v1/site-config`

```python
await client.settings.create_backup(label="pre-Q4-config-change")

preview = await client.settings.preview_import(payload=incoming_settings)
if not preview["conflicts"]:
    await client.settings.import_settings(payload=incoming_settings)
```

> ⛔ **Preview every settings import.** `import/preview` reports the conflicts an
> import would resolve silently, and a settings import that overwrites a
> governance-relevant value is a control change with no approval attached to it.
> Take a backup first; the settings audit log tells you what changed, and
> `audit-log/revert` undoes one entry — but only if you know which one.

## Putting evidence together

The sequence that produces a defensible evidence pack, in order:

| step                            | call                                              |
| ------------------------------- | ------------------------------------------------- |
| 1. Verify the record is sound   | `api:GET /api/v1/compliance/chain/integrity`      |
| 2. Assess against the framework | `api:POST /api/v1/compliance/assess`              |
| 3. Read what failed             | `api:GET /api/v1/compliance/violations`           |
| 4. Generate the evidence        | `api:POST /api/v1/compliance/soc2/evidence`       |
| 5. Extract it                   | `api:GET /api/v1/compliance/soc2/evidence/export` |
| 6. Extract the underlying audit | `api:POST /api/v1/compliance/audit/export`        |

Step 1 is the one that is skipped and the one that matters: an evidence pack
whose chain was never verified proves that the platform _reported_ something, not
that the record is intact.

## Summary — what this chapter covered

| area                 | entry point             | scale         |
| -------------------- | ----------------------- | ------------- |
| Audit spine          | `modules.observe_audit` | 5 operations  |
| Alert thresholds     | `modules.observe_audit` | 4 operations  |
| Compliance           | `modules.compliance`    | 28 operations |
| Analytics            | `modules.analytics`     | 16 operations |
| Metrics              | `modules.metrics`       | 8 operations  |
| Invocation analytics | `modules.metrics`       | 4 operations  |
| Notifications        | `modules.notifications` | 18 operations |
| Webhooks             | `modules.webhooks`      | 10 operations |
| Settings             | `modules.settings`      | 16 operations |

---

_Next: [08.8 — Commercial and extensibility](08-commercial-and-extensibility.md)_
