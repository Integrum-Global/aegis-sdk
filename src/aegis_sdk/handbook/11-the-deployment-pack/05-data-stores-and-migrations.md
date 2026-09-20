# 11.5 — Data stores and migrations

Two stores, and they fail in opposite directions. The relational database holds
everything that must survive — the organisation, its roles and envelopes, its
governance record — and losing it is unrecoverable. The cache holds nothing
durable, and losing it costs latency. Almost every operational decision about
these two follows from which side of that line a thing is on.

[07.5](../07-deployment-architecture/05-stateful-services.md) describes what
lives where and why. This chapter is how you size them, tune them, move schema
through them, and take a backup you have actually restored.

**The one idea to carry out: a backup nobody has restored is a hypothesis, and
the only instrument that settles it is a restore that produces a usable
database.**

## The database

A single-replica StatefulSet with its own persistent volume in the reference
shape, or a managed instance outside the cluster. Either way the properties that
matter to you are the same.

| Property         | Reference                                                  |
| ---------------- | ---------------------------------------------------------- |
| Kind             | StatefulSet, 1 replica                                     |
| Volume claim     | 50Gi, single-writer                                        |
| Storage class    | Unset by default — **name an SSD-backed class explicitly** |
| Vector extension | Required. Embeddings live here, not in a separate service  |

### The image requirement — a vector-capable Postgres

Because embeddings live in this database, **the image you run must carry the
vector extension**, and you choose that image when you provision the data store.
[11.2](02-provisioning-the-substrate.md) has the selection step and the two
confirmation queries.

It is an **image** decision rather than a configuration one, and that is why it
belongs at provisioning: a stock Postgres image cannot be made vector-capable by
a setting, so meeting the requirement after the store is populated turns a
one-line image choice into a migration.

### Sizing, and the growth that is not a leak

Three things drive the size, and only one of them is what people plan for.

| Driver                   | Growth shape                                         |
| ------------------------ | ---------------------------------------------------- |
| Organisational records   | Grows with your organisation; roughly bounded        |
| **Audit and governance** | **Monotonic. Retained on purpose, never pruned**     |
| **Embeddings**           | Grows with the knowledge corpus, and indexes with it |

**Storage only grows, and that is the intended behaviour.** A capacity plan
built on a steady state is wrong in the only direction that matters, and the
symptom arrives as a full volume rather than as a slow degradation: writes begin
failing, the application surfaces them as generic errors, and the database is
the last thing anyone checks because it was healthy an hour ago.

The vector extension adds a second cost most plans miss: **index maintenance is
the most expensive routine database operation here**, and it scales with the
corpus. Adding knowledge is not free at the storage layer, and it is not free at
the CPU layer either.

### Connections are the ceiling nobody sizes for

Every backend replica holds a pool. Replicas times pool size is the demand; the
database's maximum connections is the supply, and the supply is usually much
smaller than people assume.

**More replicas is not unconditionally more throughput, and past a point it is
less.** The symptom is distinctive and easily misread: requests begin timing out
while the database's CPU is idle, because the work is queued waiting for a
connection rather than waiting for the database. Scaling the deployment up makes
it worse.

```bash
# Orientation: the supply, and what is currently drawn against it
kubectl -n <app-namespace> exec statefulset/<postgres> -- \
  psql -U "$PGUSER" -d "$PGDATABASE" -c "SHOW max_connections;"
kubectl -n <app-namespace> exec statefulset/<postgres> -- \
  psql -U "$PGUSER" -d "$PGDATABASE" -c "SELECT count(*) FROM pg_stat_activity;"
```

Raise the database's ceiling **before** raising the replica count, not after.
Reversing the order produces an outage during the scale-up.

## The cache

A single-replica Deployment with append-only persistence and a `Recreate`
update strategy — deliberately, because two replicas backed by one volume is a
corruption, not a redundancy.

| Property     | Reference                                            |
| ------------ | ---------------------------------------------------- |
| Kind         | Deployment, 1 replica                                |
| Strategy     | `Recreate` — the old pod exits before the new starts |
| Persistence  | Append-only                                          |
| Volume claim | 10Gi                                                 |

`Recreate` means a cache restart is a brief outage of the cache, not a rolling
handover. That is correct and it is worth knowing before you watch it happen:
during the gap, reads fall through to the database and latency rises sharply,
then recovers as the cache refills.

> ⚠ **Nothing authoritative belongs in the cache, and the way that rule gets
> broken is by accident.** A rate-limit counter, a lock, or a session that is
> not also persisted turns the cache from an optimisation into a dependency —
> and the failure only shows up the first time the cache restarts, which may be
> months after the change that caused it.

## Schema migrations

Migrations are applied **as part of the release**, before the new version begins
serving. Three properties govern how you plan them.

- **Ordered.** Migrations apply in sequence and the sequence is not negotiable.
  Applying them out of order, or applying one twice, is what a migration ledger
  exists to prevent.
- **Forward-only in practice.** A down-migration that drops a column drops the
  data in it. Plan reversals as new forward migrations.
- **They gate the rollout.** The rollout uses `maxUnavailable: 0`, so a failed
  migration halts the change with the previous version still serving — which is
  the right outcome, and it means a stuck rollout is often a migration question.

### The expand-migrate-contract sequence

A schema change that both old and new code must tolerate cannot be one step.

```
release N     ┌── EXPAND ────────────────────────────────────────────┐
              │  add the new column, nullable; write BOTH; read OLD  │
              └──────────────────────────────────────────────────────┘
                                    │  old and new code both work here
release N+1   ┌── MIGRATE ──────────────────────────────────────────┐
              │  backfill; switch reads to NEW; keep writing both    │
              └──────────────────────────────────────────────────────┘
                                    │  rollback to N is still safe here
release N+2   ┌── CONTRACT ─────────────────────────────────────────┐
              │  stop writing OLD; drop the old column               │
              └──────────────────────────────────────────────────────┘
```

Read it as: three releases, and **the rollback window closes at the third**.
Between N and N+2 you can go back; after CONTRACT you cannot, because the column
the previous version reads no longer exists.

**Collapsing this into one release is the migration failure to expect**, and it
does not fail at migration time. The migration succeeds. The rollout proceeds.
The old replicas — still serving during the surge — begin erroring against a
column that has gone, and the incident reads as a code fault in a version that
worked ten minutes ago.

## Backup and restore

The reference shape backs up hourly on a CronJob, with two containers: one takes
the dump, one uploads it.

| Property               | Reference                                            |
| ---------------------- | ---------------------------------------------------- |
| Schedule               | Hourly, offset from the top of the hour              |
| Concurrency            | `Forbid` — a slow dump must not stack                |
| Successful-run history | 1                                                    |
| **Failed-run history** | **3 — failures are kept visible, successes are not** |
| Service-account token  | Not mounted — the job has no cluster API identity    |
| Upload credential      | Its own secret, separate from the database's         |

The history asymmetry is deliberate and worth understanding: keeping failures
and discarding successes means `kubectl get jobs` shows you problems rather than
noise. **A job list that looks empty is the healthy state**, which is the
opposite of most people's instinct and causes the occasional false alarm.

> ⛔ **`concurrencyPolicy: Forbid` means a dump that overruns its hour SKIPS the
> next run rather than stacking.** That is the safe behaviour, and it produces a
> silent gap in the backup record — the job list shows no failure, because no
> run was attempted. A database that has grown past its backup window degrades
> the backup frequency without ever alarming.

### The restore drill

A configured backup and a working backup are different facts, and only one of
them is observable.

- [ ] A dump exists, from the last hour, with a size in the range you expect.
- [ ] It has been **restored into a real database**, not merely downloaded.
- [ ] The restored database serves a read the application recognises.
- [ ] You know how long the restore took, because that number is your recovery
      time and a number nobody has measured is not one.
- [ ] The restore landed somewhere you could validate **before** it replaced
      anything.

From the API, the backup surface is visible and drivable — which is the cheapest
way to confirm the record from outside the cluster:

```python
backups = await client.settings.list_backups()
created = await client.settings.create_backup()
```

`api:GET /api/v1/settings/backups` lists what exists,
`api:POST /api/v1/settings/backups` takes one on demand, and
`api:POST /api/v1/settings/backups/restore/{id}` drives a restore.

## Store checklist

- [ ] The database's storage class is named explicitly and is SSD-backed.
- [ ] You have checked whether that class allows volume expansion.
- [ ] `max_connections` exceeds replicas × pool size, with headroom.
- [ ] The cache holds nothing authoritative — confirm, do not assume.
- [ ] Migrations follow expand-migrate-contract wherever a rollback window
      matters.
- [ ] The hourly dump has completed within the last hour, and its size is sane.
- [ ] A restore has been **performed** within recent memory, and you know how
      long it took.

---

_Next: [11.6 — Releasing and rolling back](06-releasing-and-rolling-back.md)_
