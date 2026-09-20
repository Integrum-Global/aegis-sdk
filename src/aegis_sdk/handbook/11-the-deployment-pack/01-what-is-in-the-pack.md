# 11.1 — What is in the pack

The deployment pack is everything you need to stand an Aegis deployment up, run
it, change it, and prove it — as opposed to everything you need to _understand_
one, which is part 07. It is a small set of artefacts with a strict division of
labour, and most operator confusion comes from reaching for the wrong one: a
manifest change where a configuration key was wanted, a rebuild where a
re-reference would have done.

This chapter is the inventory and the routing. It does not tell you how to use
any single artefact — each of the seven chapters that follow does exactly that
for one row of the table below.

**The one idea to carry out: the pack separates what you DECLARE from what you
BUILD from what you RUN, and those three never touch the same file.**

## The three layers, and what lives in each

| Layer         | Artefacts                                                           | Changes when                                                 |
| ------------- | ------------------------------------------------------------------- | ------------------------------------------------------------ |
| **Declare**   | Kubernetes manifests, overlays, quotas, network policy, ingress     | The deployment's shape changes — replicas, limits, routes    |
| **Configure** | A config map of non-secret settings, a secret set, a licence file   | An environment-specific value changes — a URL, a key, a mode |
| **Build**     | Two Dockerfiles, their pins, the build stamp, the provenance record | The code changes                                             |
| **Run**       | The deploy operation, its preflights, the drift verifier            | You are releasing, rolling back, or checking                 |

The split matters because the three have different blast radii and different
reversal costs. A manifest change affects every environment that inherits the
base. A configuration change affects one. A rebuild produces different bytes and
must be re-verified. **Reaching for a rebuild when a configuration value was
wrong is the most common wasted hour in this pack**, and the symptom is a
release that ships identical code with a new digest, changes nothing, and leaves
you no closer to the cause.

## The inventory

```
┌──────────────────────────────────────────────────────────────────────┐
│ DECLARE — Kubernetes, inherited by every environment                 │
│   base/       namespace · backend · web · postgres · redis           │
│               ingress · network-policy · resource-quota · monitoring │
│               backup CronJob · configmap · secrets                   │
│   overlays/   per-environment patches; the base is never edited      │
│                                                                      │
│ CONFIGURE — values, not structure                                    │
│   config map  non-secret settings, readable by anyone in the cluster │
│   secrets     credentials and keys, mounted rather than baked        │
│   licence     a signed file, mounted from a secret, never in an image│
│                                                                      │
│ BUILD — two images, pinned                                           │
│   api image   the backend: API on one port, agent listener on another│
│   web image   nginx serving a built single-page app, unprivileged    │
│                                                                      │
│ RUN — operations, each with its own gate                             │
│   deploy      manual dispatch, takes a ref, refuses on preflight     │
│   drift check compares the live cluster against the repository       │
└──────────────────────────────────────────────────────────────────────┘
```

Read it as: the four boxes are **ownership boundaries**, not directories. A
change that crosses one is a change with a wider blast radius than it looks, and
the crossing is where review should concentrate.

## The four workloads, and the fifth thing

A running deployment is four pod-producing workloads in one namespace, plus a
scheduled job. Their shapes are the subject of [11.2](02-provisioning-the-substrate.md)
and [11.5](05-data-stores-and-migrations.md); the inventory is here so you can
recognise what you are looking at in a pod list.

| Workload            | Kind        | Replicas | What it is                                                     |
| ------------------- | ----------- | -------- | -------------------------------------------------------------- |
| **backend**         | Deployment  | 3        | Two listeners in one container — the API and an agent listener |
| **web**             | Deployment  | 2        | nginx serving a built SPA, unprivileged, read-only root        |
| **postgres**        | StatefulSet | 1        | In-cluster relational store with its own persistent volume     |
| **redis**           | Deployment  | 1        | Cache and ephemeral state, append-only persistence             |
| **postgres-backup** | CronJob     | —        | Hourly dump and upload, two containers, never overlapping runs |

> ⛔ **The backend runs TWO listeners in ONE container, and that is load-bearing.**
> The API and the agent listener share a process tree. The entrypoint is PID 1,
> arms a termination forwarder **before** the first spawn, and exits the
> container when **either** listener exits. Get that ordering wrong and a
> shutdown signal reaches the wrapper but not the children: the pod lingers, the
> rollout stalls at its grace period, and the logs show a clean shutdown that
> never completed.

## What is NOT in the pack, and where it is instead

Being precise about the absences saves more time than any of the inclusions.

| Not here                          | Where it is                                                                                  |
| --------------------------------- | -------------------------------------------------------------------------------------------- |
| The platform source               | Not distributed. You deploy images, not code.                                                |
| The runtime's source              | Not distributed. It arrives as a published package — [11.4](04-the-runtime-and-its-nodes.md) |
| Your organisation's data          | The database, which you operate but do not author                                            |
| The governance model              | Configured through the API, not through manifests — part 02                                  |
| The integration's own credentials | Issued per organisation at the API, not provisioned in the cluster                           |
| Cloud account setup               | Your cloud provider's problem, upstream of everything here                                   |

**The row that catches people is the second.** The runtime is a published
package with a version constraint, and there is no repository of it to clone,
patch or build. When a node behaves unexpectedly the remedy is a version change
and a workflow change, never a source change — and a plan that assumes otherwise
stalls at the point where someone goes looking for a file that was never shipped.

## Routing a question to a chapter

| You are asking                                          | Chapter                                                          |
| ------------------------------------------------------- | ---------------------------------------------------------------- |
| "What has to exist before I can apply anything?"        | [11.2](02-provisioning-the-substrate.md)                         |
| "Which keys are required, and which are secrets?"       | [11.3](03-configuration-reference.md)                            |
| "What node types can a workflow use?"                   | [11.4](04-the-runtime-and-its-nodes.md)                          |
| "How big should the database be, and how do I migrate?" | [11.5](05-data-stores-and-migrations.md)                         |
| "How do I ship this, and how do I take it back?"        | [11.6](06-releasing-and-rolling-back.md)                         |
| "It is up — what do I watch?"                           | [11.7](07-operating-day-to-day.md)                               |
| "How do I prove it is right?"                           | [11.8](08-verifying-the-deployment.md)                           |
| "Who owns this bit, me or the platform?"                | [07.1](../07-deployment-architecture/01-what-a-deployment-is.md) |

## The one call to make first

Before anything else, confirm you are talking to the deployment you think you
are talking to, as the principal you expect. `api:GET /api/v1/auth/me` answers
both at once, and a deployment pointed at the wrong estate is indistinguishable
from a correct one until you ask.

```bash
# Orientation: which deployment, and as whom
curl -sS -H "Authorization: Bearer $AEGIS_TOKEN" \
  "$AEGIS_BASE_URL/api/v1/auth/me"          # the principal your credential resolves to
```

From the SDK the same check is one call, and `sdk:aegis_sdk.ClientConfig` is
where the base URL and credential are held:

```python
client = AgenticOSClient(ClientConfig(base_url=base_url, api_key=api_key))
me = await client.auth.get_me()
```

**Run it before you debug anything else.** A correct client pointed at a stale
environment produces working calls, plausible data, and conclusions that do not
apply to the deployment you are actually changing — and nothing in the response
says so.

---

_Next: [11.2 — Provisioning the substrate](02-provisioning-the-substrate.md)_
