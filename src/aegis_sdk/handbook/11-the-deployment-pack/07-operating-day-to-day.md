# 11.7 — Operating day to day

Most of running a deployment is not releasing it. It is knowing which numbers
mean something, which ceilings you are approaching, and what to do in the first
five minutes of an incident — and the hardest part is that the deployment's own
health signals are narrower than they look.

This chapter is the steady state and the playbooks. Capacity limits that follow
from the architecture rather than from your usage live in
[07.7](../07-deployment-architecture/07-operating-the-deployment.md); what
follows here is what you act on.

**The one idea to carry out: a green health check means a process is answering,
and nothing more — every other question needs a different instrument.**

## Health and readiness, and what each actually asserts

Three probes, three different questions, and conflating them is how a broken
deployment stays in a rotation.

| Probe         | Asks                              | Failing it causes                                      |
| ------------- | --------------------------------- | ------------------------------------------------------ |
| **Startup**   | Has it finished booting yet?      | The other probes stay suspended                        |
| **Liveness**  | Is the process still alive?       | The container is **restarted**                         |
| **Readiness** | Can it serve traffic _right now_? | The pod is **removed from the service**, not restarted |

All three target the same health path in the reference shape. That is fine, and
it has one consequence worth holding: **a dependency failure that the health
path does not consult is invisible to all three.** The pod stays Ready, the
service keeps routing to it, and every request that needs that dependency fails.

At the API level there are governance-specific health operations, and they
answer a narrower question than the pod probes:

```python
trust = await client.trust.get_health()
compliance = await client.compliance.get_health()
```

`api:GET /api/v1/trust/health` and `api:GET /api/v1/compliance/health` report
that the governance services respond. **They do not report that governance is
configured as you intended, that your envelopes are the ones you think, or that
any control is enforced.** Treating a green there as evidence for those is how a
misconfiguration survives a monitoring system that was watching the wrong thing.

## What to watch

Six things, in the order they will hurt you.

| Watch                          | Where                                | Acts when                                    |
| ------------------------------ | ------------------------------------ | -------------------------------------------- |
| **Database volume headroom**   | Cluster metrics                      | Below ~25% — it only grows                   |
| **Connection-pool saturation** | `api:GET /api/v1/pools/{id}/metrics` | Waits appear while CPU is idle               |
| **Error rate**                 | `api:GET /api/v1/metrics/errors`     | Any sustained rise, especially post-release  |
| **Execution throughput**       | `api:GET /api/v1/metrics/executions` | Drops without a load change                  |
| **Backup recency**             | `api:GET /api/v1/settings/backups`   | Most recent is older than an hour            |
| **Spend**                      | `api:GET /api/v1/analytics/costs`    | Any step change — model calls are the driver |

Two aggregate views are worth a dashboard:

```python
summary = await client.metrics.get_summary()
overview = await client.analytics.get_overview()
```

`api:GET /api/v1/metrics/summary` is the operational roll-up and
`api:GET /api/v1/analytics/overview` the work-level one;
`api:GET /api/v1/metrics/timeseries` is where you go once you know which number
moved. For service-level attainment, `api:GET /api/v1/analytics/sla` is the
reporting surface.

> **In the console:** the same figures appear on the metrics and analytics
> dashboards, and `api:GET /api/v1/metrics/dashboard` is the operation behind
> the operational one.

## Logs and records — two kinds, not interchangeable

|                    | Audit evidence                      | Operational telemetry          |
| ------------------ | ----------------------------------- | ------------------------------ |
| **Answers**        | Who did what, and was it permitted  | Is it healthy, and is it fast  |
| **Produced by**    | The governance layer, deliberately  | The runtime, as a by-product   |
| **Retention**      | Long, set by policy                 | Short, set by cost             |
| **Completeness**   | Complete for its scope              | Sampled, dropped, rotated      |
| **If you lose it** | You cannot evidence your governance | You lose situational awareness |

**Evidence is a product artefact; telemetry is an operational one.** A retention
obligation is satisfied by the first column, never by the second — and the
mistake is easy to make because both are visible and one is far easier to query.

```python
entries = await client.audit.list_logs()
export = await client.audit.export()
```

`api:GET /api/v1/audit/logs` reads the governance record and
`api:GET /api/v1/audit/export` extracts it. `api:GET /api/v1/settings/audit-log`
is the settings-change record specifically — who changed the deployment's own
configuration, which is the log you will want during an incident whose cause
turns out to be a change.

Container logs are the telemetry half, and the backend's two listeners share one
stream:

```bash
# Orientation: recent backend output, both listeners interleaved
kubectl -n <app-namespace> logs deploy/<backend> --since=15m --tail=200
kubectl -n <app-namespace> logs deploy/<backend> --previous     # the container that just died
```

**`--previous` is the flag people forget under pressure.** After a crash-loop
restart the current container's log is empty and reassuring; the one that
explains the crash belongs to the container that has already gone.

## Capacity — what scales and what does not

| Scales with demand        | Does not scale                                        |
| ------------------------- | ----------------------------------------------------- |
| Backend and web replicas  | Database write throughput — it scales **up**, not out |
| Node pool size            | Vector index build cost                               |
| Cache capacity            | Retention — evidence grows and is kept                |
| Job execution concurrency | Storage growth, which is monotonic                    |

Three ceilings are structural, and worth designing around rather than arguing
with.

- **Database write throughput** is bounded by the instance size, and changing it
  is a planned operation rather than an automatic one.
- **Vector index maintenance** scales with the knowledge corpus and is the most
  expensive routine database operation.
- **Connection counts** are bounded by the database. Every replica consumes
  some, so **more replicas is not unconditionally more throughput, and past a
  point it is less** — see [11.5](05-data-stores-and-migrations.md) for the
  arithmetic and the order of operations.

## Incident playbooks

Five shapes, with the distinguishing signal first because that is what you have
at minute one.

### Pods are Ready and every request fails

**Distinguishing signal:** health green, error rate at or near 100%, logs show
requests arriving.

The permissive-lifespan failure: a startup exception was swallowed and the pod
reports Ready while nothing works. Check the backend's start-up log lines for an
exception that did not prevent the process continuing. **Roll back rather than
restart** — a restart reproduces the same start.

### A rollout has stopped part-way

**Distinguishing signal:** old and new pods both present, `rollout status`
hanging, previous version still serving.

This is `maxUnavailable: 0` working. **It is not an outage.** Read the new
pod's logs — most often a migration, a missing configuration key, or a probe
budget too short for a slow start. Do not scale the old version down to force
the new one through; that converts a safe halt into a real interruption.

### Latency rose, nothing changed

**Distinguishing signal:** CPU idle, error rate flat, response times up.

Two candidates in order. **CPU throttling** — a container at its CPU limit is
slowed rather than killed and logs nothing, which is why this is routinely
profiled as an application problem for days. **Connection-pool waits** — the
work is queued for a connection rather than for the database. Check
`api:GET /api/v1/pools/{id}/metrics` before profiling anything.

### The backup record has a gap, with no failed job

**Distinguishing signal:** job list clean, most recent dump older than an hour.

`concurrencyPolicy: Forbid` skipped a run because the previous dump was still
going. No run was attempted, so nothing failed and nothing alarmed. The database
has outgrown its backup window — fix the window or the dump, not the alert.

### A capability works in one environment and not another

**Distinguishing signal:** identical image reference, different behaviour.

Three candidates, in cost order: a configuration key differing between the two
environments ([11.3](03-configuration-reference.md)); a licence baked into an
image rather than mounted ([11.6](06-releasing-and-rolling-back.md)); or a
runtime version difference changing the node catalogue
([11.4](04-the-runtime-and-its-nodes.md)). Compare configuration first — it is
the cheapest to check and the most often the answer.

## The first five minutes

```bash
# 1. Is it up, and which version?
kubectl -n <app-namespace> get pods -o wide
kubectl -n <app-namespace> get deploy -o wide          # image references in force

# 2. What died, and what did it say before it died?
kubectl -n <app-namespace> logs deploy/<backend> --previous --tail=100

# 3. Is this a change? (the settings-change record, not the container log)
```

Then, from the API, in this order: `api:GET /api/v1/auth/me` to confirm you are
looking at the deployment you think you are;
`api:GET /api/v1/metrics/errors` for shape and onset;
`api:GET /api/v1/settings/audit-log` for a recent configuration change.

**Step one of step three is the one that resolves incidents fastest**, because a
large share of them are a change somebody made and nobody correlated.

---

_Next: [11.8 — Verifying the deployment](08-verifying-the-deployment.md)_
