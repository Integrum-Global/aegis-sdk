# 11.6 — Releasing and rolling back

<!-- anchor-floor: exempt (image build and rollout; no version operation is declared) -->

A release here is four things in a fixed order: build two images from one
commit, stamp them so the running system can say what it is, apply them behind
preflights that refuse rather than proceed, and keep the previous digest so the
reversal is a re-reference rather than a rebuild.

[07.3](../07-deployment-architecture/03-images-and-the-registry.md) makes the
case for digests over tags and owns that argument. This chapter is the
operation: what the build hardens, what the stamp is for, what the deploy
refuses, and what a rollback actually does.

**The one idea to carry out: the deploy operation is manual, takes a commit, and
every preflight in it exists because something once passed without it.**

## Two images, built from one commit

| Image              | Contents                                       | Runs as                                                       |
| ------------------ | ---------------------------------------------- | ------------------------------------------------------------- |
| `<registry>/<api>` | The backend — API listener plus agent listener | Non-root, capabilities dropped                                |
| `<registry>/<web>` | nginx serving a built single-page app          | Non-root, read-only root, one capability re-added for binding |

Both pin their base image to an exact patch version. Neither installs a
toolchain that survives into the runtime layer.

### What the build hardens, and why each step is there

- **Toolchain tarballs are verified against digests pinned in the Dockerfile
  itself**, with length validators on the hex. A pinned digest that is silently
  truncated verifies nothing while looking rigorous, so the length check is the
  part that makes the pin real.
- **Vendored dependency floors are re-pinned with independent digests**, and the
  build **fails** rather than continuing when one does not match. An `else`
  branch that warns and proceeds is the same as no check at all.
- **The front-end module tree is deleted from the runtime image** after the
  build, while the guards that produced it remain. The artefact ships; the
  machinery that made it does not.
- **The build toolchain and its installers are purged and asserted gone.** The
  assertion matters more than the purge: a removal that silently fails leaves a
  compiler in a production image and nothing says so.
- **The licence signature's public key is baked in as a trust anchor.** The
  licence itself never is — it is mounted from a secret
  ([11.3](03-configuration-reference.md)).

### The lockfile is what makes the image deterministic — not the ranges

This is the most useful sentence in the build section, so it is stated on its
own: **the dependency ranges are not what pins the image. The lockfile is.**

Of the 33 runtime dependencies, **7 carry an upper bound and the other 26 are
deliberately unbounded.** A reader who audits the ranges and concludes the build
is reproducible has audited the wrong artefact — the ranges express
compatibility intent, and the lockfile expresses what actually installs.

The install path is what enforces it:

1. `uv export --frozen` resolves **from the lockfile**, never from the range
   set, and emits a hash-pinned requirements file.
2. The build **asserts that export actually contains the runtime pin**, and
   fails fatally if it does not.
3. `pip install --no-deps --require-hashes` installs exactly that, refusing any
   unpinned or unhashed line.
4. The resolver tool is then **removed, and its absence verified**.

**To change a pinned version, edit the constraint AND re-resolve the
lockfile.** Editing the manifest alone fails the build — the frozen export
refuses to re-resolve, so the assertion in step 2 catches the mismatch rather
than silently installing the old version. That refusal is the design: a manifest
edit that appeared to succeed while installing something else is the outcome
`--frozen` exists to prevent.

### The production interpreter is the image's pin

The image pins **Python 3.12.9 exactly**. The project manifest declares only a
`>=3.12` floor, and a CI workflow pins its own interpreter for tooling.

> ⛔ **Do not infer the production interpreter from a CI workflow.** The three
> numbers serve three different purposes — the floor says what the code
> tolerates, the CI pin says what a checking job runs on, and **only the image
> pin says what production executes.** Reading the CI pin as production's is a
> conclusion nothing in the logs will contradict, because both interpreters run
> the same code successfully right up until one of them does not.

> ⛔ **The single most consequential build mistake is baking the licence.** The
> image still runs everywhere. It simply reports the wrong entitlements in every
> deployment it was not built for, with no error at any point — so the first
> symptom is a capability behaving differently in two environments that are
> supposedly running the same version.

## Stamping — one tag, both images, asserted back

One value — the commit — drives the build argument and both image tags. Three
rules make the stamp trustworthy:

1. **The commit argument is REQUIRED, with no silent default.** A default would
   produce a build that succeeds and is unattributable.
2. **A dirty tree or a shallow clone is REFUSED.** Both produce a stamp that
   names a commit whose content is not what was built.
3. **Each image generates its stamp INSIDE the build, after the source copy, and
   asserts it back.** Generating it outside lets a host file shadow it; the
   assertion is what catches a stamp that did not take.

The result is two surfaces you can read at runtime: a **version operation on the
backend**, and a **static version file the web image serves**. Both should name
the same commit, and [11.8](08-verifying-the-deployment.md) is where that gets
checked.

**Two images stamped with different commits is the failure this design exists to
catch**, and without the stamp it is invisible: the deployment works, the front
end and the back end are from different releases, and the mismatch presents as
an intermittent contract error weeks later.

## Provenance — what it proves, and what it does not

A signed build-provenance record binds the image digest to the build stamp. It
is emitted on **release events only** — never on a proposal — and it **fails
closed** without its signing key rather than emitting an unsigned record.

> ⚠ **The attested image and a later rebuild agree on INPUTS, not on bytes.** A
> digest difference between a rebuild and the attestation is EXPECTED, and it is
> not evidence of tampering. Use an attested digest to verify **that** artifact;
> never to predict what another build of the same commit will produce. Reading a
> legitimate digest difference as a supply-chain incident is the misreading to
> expect, and it is expensive because it is alarming.

A vulnerability scan runs daily and on changes to dependency manifests, at high
and critical severity. It is **advisory** — it reports, it does not block — so
treat its output as a queue to work rather than as a gate that has already been
satisfied.

## The deploy operation

Manually dispatched. There is no push, merge or schedule that triggers it, and
that separation is deliberate: merging is a code decision and deploying is an
operational one.

| Input     | Meaning                                                                                      |
| --------- | -------------------------------------------------------------------------------------------- |
| `ref`     | The **commit** to deploy. A full or abbreviated SHA, **not a branch name**                   |
| `confirm` | The target namespace, typed out                                                              |
| `deliver` | The commit or commits this deploy MUST land, checked against the ref AND the running cluster |

### The preflights, and what each one catches

| Preflight                      | Refuses when                                                                           |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| **Confirmation gate**          | The typed namespace does not match the target. Without it, any string deploys          |
| **Ref identity fence**         | `HEAD` does not resolve to the requested ref — verified by effect, not by trust        |
| **Delivery check**             | The ref does not contain the commits the deploy claims to deliver                      |
| **Tooling and credentials**    | A required tool is missing, or no cluster context is selected, each named individually |
| **Network policy enforcement** | Rendered policy would not actually be enforced                                         |

**The delivery check is the one that saves you from the most embarrassing
failure**: deploying a ref that builds, applies and comes up healthy, while not
containing the fix everyone believes has just shipped. Nothing about a healthy
rollout distinguishes that case, which is why the check compares against the
running cluster as well as against the ref.

```bash
# Orientation: what the cluster is running right now, before you change it
kubectl -n <app-namespace> get deploy -o wide          # the image references in force
kubectl -n <app-namespace> rollout status deploy/<backend> --timeout=5m
```

## The rollout, and why it cannot half-finish

Both Deployments roll with `maxSurge: 1` and **`maxUnavailable: 0`**.

```
  RUNNING  ──┐
             │  new pod starts alongside the old ones (surge 1)
             ▼
  VERIFYING  ──── probes pass ────▶  old pod retires, next one surges
             │
             └── probes fail ─────▶  ROLLOUT HALTS
                                     previous version still serving 100%
```

Read it as: **`maxUnavailable: 0` is what makes a bad release a non-event.** A
pod that will not boot halts the rollout with the previous version serving every
request. Nothing is lost, and the deployment sits in a mixed state until someone
acts.

The consequence to internalise: **a halted rollout is not an outage, and
treating it as one causes the outage.** The instinct under pressure is to force
the new version through by scaling down the old; that trades a safe halt for a
real interruption. Read the failing pod's logs first.

### Probes are single slots, not lists

Each container has **one** liveness probe, **one** readiness probe and **one**
startup probe. Each is a single object, not a list.

> ⛔ **Adding a second `livenessProbe:` key does not add a probe — it REPLACES
> the first.** The manifest is valid, the apply succeeds, and the check you
> thought you had added has silently removed the check you already had. There is
> no warning at any layer. If you need two conditions, they go inside one probe's
> target, not into two keys.

Reference shape for the backend: liveness after 30s, every 10s, 3 failures to
act; readiness after 10s, every 5s; startup after 10s, every 5s, 12 failures —
a 60-second budget for a slow start.

**The startup probe is what stops a slow boot being read as a failed one.**
Without it, a database migration that takes 40 seconds trips liveness, the
container is killed, and the pod crash-loops through a migration that would have
succeeded.

### Explicit lifespan handling is load-bearing

The permissive default swallows a startup exception and leaves a pod **Ready
while every request fails**. That is the worst available outcome: the rollout
completes, the previous version retires, and the deployment reports healthy
while serving nothing but errors. Explicit lifespan handling turns that into a
failed start, which `maxUnavailable: 0` then converts into a halted rollout.

The worker health-check timeout is raised for a related reason. The default kills
a worker whose interpreter is busy across a model round-trip — a normal, long,
entirely healthy operation. **A hard kill runs no handler**, so a dispatched task
row is left in progress forever, and the symptom is a queue that accumulates
work nobody is processing and nothing has marked failed.

## Rolling back

Reversal is re-referencing the previous digest. The image still exists, it is
the exact bytes that ran before, and the operation is minutes with no build.

| Step | Action                                                                         |
| ---- | ------------------------------------------------------------------------------ |
| 1    | Identify the previous digest. Do not reconstruct it from a tag                 |
| 2    | Confirm the schema is compatible — [11.5](05-data-stores-and-migrations.md)    |
| 3    | Dispatch the deploy operation with the **previous commit** as `ref`            |
| 4    | Watch the rollout; `maxUnavailable: 0` protects you if the reversal is bad too |
| 5    | Verify — [11.8](08-verifying-the-deployment.md)                                |

**Step 2 is the step that is skipped**, and it is the one that makes a rollback
dangerous rather than routine. If the release you are reversing included a
CONTRACT migration, the previous version reads a column that no longer exists:
the rollback applies cleanly, the pods come up, and every request touching that
table fails. The expand-migrate-contract sequence exists precisely so this
window is known rather than discovered.

**A rollback you have never rehearsed is a hypothesis.** Knowing the previous
digest exists is not the same as having deployed it.

---

_Next: [11.7 — Operating day to day](07-operating-day-to-day.md)_
