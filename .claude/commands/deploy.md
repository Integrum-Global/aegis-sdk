---
name: deploy
description: "Stand a deployment up and prove it — provision the substrate, set the configuration, apply the release, and verify the result against the repository rather than against a health check."
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/commands/deploy.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


<!-- anchor-floor: exempt (procedure; routes to handbook chapters and skills by name) -->

You are standing up, changing, or verifying a **deployment of Aegis**, and the
four steps below are ordered because each one fails silently when the one above
it was skipped. A missing storage class does not error — the claim stays
pending. A missing configuration key does not error — the deployment boots and
refuses everything. Run them in order.

This is the procedure. The reference behind each step is a chapter of **The
deployment pack**, named at the step; go there when a step needs a value rather
than an action.

## 1 — Provision the substrate, in dependency order

Nothing below boots until the cluster, namespace, quota, storage, ingress and
certificate exist. Read **Provisioning the substrate**, and hold two
requirements that are decided at this step and expensive afterwards.

**The database image must carry the vector extension.** The knowledge store uses
a vector column for similarity retrieval, so a stock image cannot serve it and no
setting will fix that later. Confirm both halves — the image can provide it, and
it is enabled here:

```bash
kubectl -n <app-namespace> exec statefulset/<postgres> -- \
  psql -U "$PGUSER" -d "$PGDATABASE" -c "SELECT name FROM pg_available_extensions WHERE name='vector';"
kubectl -n <app-namespace> exec statefulset/<postgres> -- \
  psql -U "$PGUSER" -d "$PGDATABASE" -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

An empty first result is an image to correct; an empty second is a one-line
enablement. Two different remedies, which is why both queries run.

**Provision the cluster WITH a network-policy engine.** A Kubernetes cluster
enforces NetworkPolicy only when one is enabled, and admission is not
enforcement — the policy objects list identically either way. Step 4 is what
proves it.

## 2 — Set the configuration, and generate the secrets

Read **Configuration reference** for the key-by-key table. Two things belong in
this procedure rather than in the reference.

**Run the generator before the first apply.** The secret template ships
placeholders, and a placeholder is a valid string — a deployment that never ran
the generator will start, serve, and store data under a value that is neither
secret nor yours.

```bash
bash <deployment-pack>/scripts/generate-secrets.sh
```

**Two keys are one-way doors. Decide them now.**

| Key               | Why it cannot be changed later                                                    |
| ----------------- | --------------------------------------------------------------------------------- |
| The PII hash salt | It pseudonymises personal data in derived records; there is no re-encryption path |
| The master key    | Every other derived key hangs from it                                             |

Set both at provisioning, back them up somewhere that outlives the cluster, and
do not leave either at its template value.

⛔ Confirm secrets by **key name**. Never decode a value into a terminal, a log
or a transcript — it lives in scrollback and in whatever captured the session,
and rotating a key because it was pasted somewhere is an avoidable afternoon.

## 3 — Apply the release

Read **Releasing and rolling back**. The deploy operation is manually
dispatched, takes a **commit** rather than a branch name, and refuses rather
than proceeds when a preflight fails.

Before dispatching, know what is running now:

```bash
kubectl -n <app-namespace> get deploy -o wide          # the image references in force
kubectl -n <app-namespace> rollout status deploy/<backend> --timeout=5m
```

Three properties of the rollout decide how you read it:

- **Zero unavailable.** A pod that will not boot halts the rollout with the
  previous version still serving every request. **A halted rollout is not an
  outage, and treating it as one causes the outage** — read the failing pod's
  logs rather than scaling the old version down to force the new one through.
- **Migrations gate the change.** If you are landing a schema change, read
  **Data stores and migrations** first: expand, migrate, contract, and know that
  the rollback window closes at the third.
- **Rollback is re-referencing the previous digest**, not a rebuild — but
  confirm schema compatibility first. That is the step that gets skipped, and it
  is what turns a routine reversal into an incident.

## 4 — Verify, and treat UNDETERMINED as a failure

Read **Verifying the deployment**. Five checks, each answering one question and
blind to the others — which is why you run all five rather than the cheapest.

| Check              | Confirms                                                     |
| ------------------ | ------------------------------------------------------------ |
| Drift              | The live cluster matches the repository                      |
| Policy enforcement | An engine is present, so the policies bind                   |
| Version surfaces   | Both halves name the commit you deployed, and the same one   |
| Reachability       | A partner can call it, as the principal you expect           |
| Governance record  | The audit chain is intact, not merely that the service is up |

⛔ **UNDETERMINED is a failure, not a pass.** It means the check did not look,
and "could not look" and "looked and found nothing" are the same silence from
anything treating the outcome as a boolean.

Two probes that answer fastest, from outside the cluster:

```python
me = await client.auth.get_me()                    # which deployment, and as whom
orgs = await client.auth.list_my_organizations()   # the scope — and no others
```

**Then attempt one operation you expect to be REFUSED, and confirm it is.** A
permission model tested only in the permissive direction is untested: every call
succeeding is exactly what a deployment with governance switched off produces.

## What this leaves you holding

- a substrate whose vector extension and policy engine are confirmed, not assumed
- generated secrets, with the two one-way doors decided and backed up
- a release applied by commit, with its schema compatibility checked
- five verification answers, none of them UNDETERMINED
- one observed refusal

If the last is missing you have verified that the deployment responds, not that
it governs.

## Next

- `/orient` — you have a deployment and now need to point a client at it
- `/diagnose` — something is failing and you need to attribute it

**Chapters:** **What is in the pack** routes any question to its chapter;
**Operating day to day** is the steady state and the incident playbooks.
