# 11.2 — Provisioning the substrate

<!-- anchor-floor: exempt (cluster provisioning; kubectl/psql surface only) -->

Everything in the rest of this part assumes a cluster that already has a
namespace, quotas, storage classes, an ingress controller and a working
certificate. This chapter is how those come to exist, in the order they have to
exist in, and what each one is actually for.

[07.2](../07-deployment-architecture/02-the-cluster-and-namespaces.md) describes
what a namespace does and does not separate — read it for the boundary model.
This chapter does not restate it; it tells you what to create.

**The one idea to carry out: provisioning is ordered, and every dependency is
silent when unmet.** A missing storage class does not error at apply time — the
claim simply stays pending, and a pod that never schedules looks identical to a
pod that is slow to start.

## The order, and why it is an order

```
1. cluster              node pools: one for platform components, one or more for workloads
      │
2. namespace            the unit everything below is scoped to
      │
3. storage class        must exist BEFORE any claim is made against it
      │
4. resource quota       and a limit range, so unbounded pods get bounds
      │
5. ingress controller   the thing that will terminate TLS and own the hostname
      │
6. certificate          issued for the hostname, before the ingress references it
      │
7. secrets + config     what the workloads read at start — chapter 11.3
      │
8. workloads            only now does anything boot
```

Read it as: each step is a **precondition** for the one below, and each unmet
precondition fails **quietly**. Steps 3 and 6 are the two that reliably catch
people out, because a pending volume claim and an unresolved certificate both
present as "the deployment did not come up" with nothing in the application's
own logs.

## The cluster and its node pools

Two pool kinds, at minimum:

- **A system pool** for the cluster's own components — ingress, controllers,
  the machinery that makes the cluster work. Tainted, so only components that
  explicitly tolerate the taint land there.
- **One or more workload pools** for the application workloads and any
  ephemeral job execution.

The separation exists so a workload that consumes its pool's capacity cannot
take the cluster's own control components down with it. **When the split is
absent the failure presents as the platform being broken rather than as one
workload being greedy** — ingress stops answering, and the first thing anyone
looks at is the application.

Size the workload pool against the resource quota below, not against the request
sums: a quota that exceeds the pool's real capacity admits pods the scheduler
then cannot place, and pending-for-capacity is a different problem with a
different fix from pending-for-quota.

## The namespace and its quota

One application namespace holds all four workloads and the backup job. Create it
first; everything else is scoped to it.

The quota is a ceiling on the namespace's total consumption, and the limit range
supplies bounds for containers that declare none:

| Object            | What it bounds                          | Reference shape                                                                 |
| ----------------- | --------------------------------------- | ------------------------------------------------------------------------------- |
| **ResourceQuota** | The namespace's total                   | Requests around 20 CPU / 40Gi; limits around 40 / 80Gi; a pod ceiling around 50 |
| **LimitRange**    | Any single container that declares none | A default request and limit per container, plus a maximum                       |

Treat those numbers as the reference starting point and size them against your
own workload profile. **The limit range is the half people skip, and the symptom
is memorable**: one container with no declared limit expands until it takes the
node's memory, and every unrelated pod on that node is evicted — so the incident
looks like a node failure rather than like one unbounded container.

> ⚠ **A quota and a limit are different mechanisms with different symptoms.**
> Hitting the quota refuses NEW workloads while existing ones keep running.
> Hitting a memory limit restarts ONE container. Hitting a CPU limit throttles
> it without restarting — slower responses, no restart, nothing in the logs.
> That third one is routinely mistaken for an application performance problem
> and profiled for days.

## Storage classes and persistent volumes

Two claims are made in the reference shape, both inside the namespace:

| Claim        | Reference size | Access | Holds                                 |
| ------------ | -------------- | ------ | ------------------------------------- |
| **postgres** | 50Gi           | single | The relational store's data directory |
| **redis**    | 10Gi           | single | Append-only persistence for the cache |

Both leave the storage class **unset by default**, which means the cluster's
default class is used. Set it explicitly for anything you care about
performance on — the database in particular wants an SSD-backed class, and the
default on many clusters is not one.

**Sizing the database claim is a one-way door on some platforms.** Expanding a
volume is supported by many storage classes and by no means all of them, so a
claim provisioned at the reference 50Gi on a non-expandable class becomes a
migration rather than a resize. Check `allowVolumeExpansion` on the class you
choose before you make the claim, not after the disk fills.

```bash
# Orientation: does the class you are about to use support expansion?
kubectl get storageclass                      # the classes available, and which is default
kubectl get storageclass <class> -o jsonpath='{.allowVolumeExpansion}{"\n"}'
```

## The database image must carry the vector extension

The knowledge store uses a **vector column** for similarity retrieval, so **the
deployment requires a Postgres image with the vector extension available**, and
you select that image when you provision the data store. A stock Postgres image
does not carry it.

Two provisioning consequences, both decided before first boot:

- **Pick a vector-capable image**, not a stock one. The extension must be
  present in the image for the database to enable it.
- **The extension is enabled in the database**, once, at provisioning. It is a
  property of the database instance, not of the application.

Confirm it positively, as a provisioning step rather than a later diagnosis:

```bash
# Orientation: is the extension available to install, and is it installed?
kubectl -n <app-namespace> exec statefulset/<postgres> -- \
  psql -U "$PGUSER" -d "$PGDATABASE" -c "SELECT name FROM pg_available_extensions WHERE name='vector';"
kubectl -n <app-namespace> exec statefulset/<postgres> -- \
  psql -U "$PGUSER" -d "$PGDATABASE" -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

The first query answers _can this image provide it_; the second answers _is it
enabled here_. **An empty first result is an image choice to correct, and an
empty second is a one-line enablement** — two different remedies, which is why
both queries are run rather than one.

[11.5](05-data-stores-and-migrations.md) covers what the extension costs you in
storage and index maintenance once the corpus grows.

## Ingress and certificates

The ingress is the deployment's single public door: it terminates TLS, owns the
hostname, and routes to the web and backend services.
[07.4](../07-deployment-architecture/04-the-network-boundary.md) owns the
boundary model; the provisioning facts are these.

- **The controller comes first.** An ingress resource with no controller
  watching it is accepted by the API server and does nothing. There is no error
  — the resource simply never acquires an address.
- **The certificate must exist before the ingress references it.** An ingress
  referencing an absent TLS secret serves the controller's default certificate,
  so clients get a name-mismatch error while the deployment reports healthy.
- **The hostname is yours.** It is a placeholder everywhere in this pack
  (`<your-deployment>`), and it appears in more than one place — the ingress,
  the allowed-origins configuration, and the front-end's own base URL. Setting
  it in one place and not the others produces a deployment that loads and then
  fails every request from the browser on a cross-origin check.

```bash
# Orientation: has the ingress actually acquired an address?
kubectl -n <app-namespace> get ingress                # ADDRESS empty means no controller took it
kubectl -n <app-namespace> get secret <tls-secret>    # absent means the default cert is being served
```

## Network policy — provision the cluster with an engine

The namespace ships a default-deny posture with explicit allowances. **Provision
the cluster WITH a network-policy engine**, because a Kubernetes cluster only
enforces NetworkPolicy when one is enabled — and admission is not enforcement.

This is a property of Kubernetes rather than of any one deployment, and it is
the reason the requirement is a provisioning step rather than a review item:

|                                        | Cluster WITH an engine | Cluster WITHOUT one |
| -------------------------------------- | ---------------------- | ------------------- |
| The API server accepts policy objects  | yes                    | **yes**             |
| `kubectl get networkpolicy` lists them | yes                    | **yes**             |
| A manifest review passes               | yes                    | **yes**             |
| Traffic is actually restricted         | yes                    | **no**              |

Read the table down the right-hand column: **every readable signal is identical,
and only the last row differs.** So the engine is selected when the cluster is
created, or added to a running cluster with the provider's own update command —
and the enforcement check in [11.8](08-verifying-the-deployment.md) is what
proves it, rather than any amount of reading the objects.

### The policy invariants — design rules the pack holds

Five properties every policy in the set satisfies. Hold them when you add one:

- **Every `podSelector` matches a real workload.** A selector matching nothing
  is a policy with no subject.
- **Every ingress port is a real `containerPort`.** A port nothing listens on
  admits nothing and protects nothing.
- **Egress-restricted policies permit DNS on both UDP and TCP 53.** Name
  resolution falls back to TCP for large responses, and a UDP-only allowance
  produces intermittent resolution failures under exactly the conditions that
  make them hardest to reproduce.
- **No bare wildcard egress peer.** An allowance wide enough to reach anything
  is the absence of an egress policy wearing one.
- **Ingress and egress are reciprocal.** If A may egress to B, B admits ingress
  from A. A one-sided pair is denied by the other half, and the symptom is a
  connection that times out rather than one that is refused.

> ⛔ **The backup job needs a policy allowance of its own.** It is a CronJob pod
> with its own labels, and a policy written around the four long-running
> workloads will not match it. The symptom is an hourly job that connects to
> nothing, fails, and — because failed job history is kept deliberately short in
> a cluster's default settings — leaves you a gap in the backup record rather
> than an alarm.

## Pod security

The reference posture across every workload: non-root, no privilege escalation,
all capabilities dropped. The web image re-adds exactly one — the capability to
bind a privileged port — and runs with a **read-only root filesystem**, which
requires writable scratch mounts for the cache, runtime and temporary
directories.

**Adding a read-only root to a container that was not built for it is the
failure to expect**, and it does not present as a permissions error. The process
starts, tries to write its first temporary file, and dies in a way the
application's own logging never reaches — so the pod crash-loops with an empty
log.

## Provisioning checklist

Run through this before applying any workload.

- [ ] The cluster has a system pool and at least one workload pool, and the
      system pool is tainted so tenant workloads cannot land on it.
- [ ] The namespace exists, and the quota and limit range are applied to it.
- [ ] The storage class you intend is named explicitly, and you have checked
      whether it allows volume expansion.
- [ ] The Postgres image carries the **vector extension**, and the extension is
      enabled in the database.
- [ ] An ingress controller is running and healthy.
- [ ] A certificate for your hostname is issued and its secret is present in the
      namespace.
- [ ] The cluster was provisioned **with a network-policy engine**, and
      enforcement is confirmed per [11.8](08-verifying-the-deployment.md) rather
      than by reading the policy objects.
- [ ] The backup job's labels are covered by a policy allowance.
- [ ] Secrets and configuration are present — [11.3](03-configuration-reference.md)
      is the list, and no workload will start without them.

---

_Next: [11.3 — Configuration reference](03-configuration-reference.md)_
