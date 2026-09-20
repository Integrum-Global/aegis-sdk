# 07.2 — The cluster and its namespaces

<!-- anchor-floor: exempt (Kubernetes substrate; no Aegis operation or SDK symbol in scope) -->

Underneath everything in this part is a Kubernetes cluster. You will rarely
touch it, and you never administer it — but you will meet its boundaries
constantly, because they are what your workloads run inside. This chapter is
about those boundaries and, more usefully, about which of them are real.

## Managed, and what "managed" covers

The cluster is **managed**: the control plane — the API server, the scheduler,
the controllers that keep the declared state true — is operated by the platform.
That is a real removal of work, and it is worth being precise about what it
removes and what it does not.

- **Covered:** control-plane availability, version upgrades, certificate rotation
  for the control plane, and the operational burden of keeping the scheduler
  healthy. You do not patch a managed control plane.
- **Not covered:** anything running _in_ the cluster. Your workloads, their
  resource requests, their behaviour under load, and whether they are healthy are
  not the platform's problem by virtue of the cluster being managed. "Managed"
  describes the control plane, not your services.

A managed control plane also means the cluster's API server is not something you
reach directly. You interact with the deployment through the edge described in
[07.4](04-the-network-boundary.md) or, where a deployment offers it, through a
namespace-scoped administrative path. Which of those your deployment provides is
a question worth asking up front rather than discovering during an incident.

## Node pools, and why there is more than one

The nodes the workloads land on are grouped into **pools**, and the reference
shape has at least two kinds:

- **A system pool**, carrying the platform's own components — the controllers,
  ingress, and the services that make the cluster work at all.
- **One or more workload pools**, carrying application services and the
  ephemeral job execution described below.

The split exists for one reason: **the platform's own components must not be
starved by tenant workloads.** If everything shared one pool, a workload that
consumed the pool's capacity would take the cluster's own control components down
with it — and the failure would look like the platform being broken rather than
like a workload being greedy.

**Autoscaling is the normal state, not an event.** Pools grow and shrink as
demand moves. A consequence worth internalising: a pod that cannot be scheduled
is not necessarily a quota problem — it may be a node that has not come up yet,
and the two have different fixes and different durations.

```
┌──────────────────────────────────────────────────────────┐
│ SYSTEM POOL — platform components                        │
│   tenant workloads are kept out of this pool             │
│                                                          │
│     └─ platform namespace                                │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ WORKLOAD POOL — autoscaling                              │
│                                                          │
│     ├─ application namespace                             │
│     └─ job execution namespace                           │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ FURTHER WORKLOAD POOLS — optional                        │
│                                                          │
│     └─ additional application namespaces                 │
└──────────────────────────────────────────────────────────┘
```

Read it as: the pools are the top-level grouping, and namespaces live _inside_
them. The separation is not a network path — it is the placement rule that keeps
tenant workloads out of the system pool, which is enforced as described below.

The number and naming of pools is the deployment's. The reference shape is one
system pool plus one or more workload pools; a specific deployment may carry
more, sized differently. Do not plan against a pool count — plan against the rule
that separates them.

## The namespace model

Namespaces are how work is separated. The reference shape uses three kinds:

| Namespace kind    | What runs there                                                      | Who puts things there                       |
| ----------------- | -------------------------------------------------------------------- | ------------------------------------------- |
| **Platform**      | Controllers, ingress, the services that run the deployment itself    | The platform, exclusively                   |
| **Application**   | The long-running services that serve the API                         | The platform; you configure what they serve |
| **Job execution** | Ephemeral, short-lived workloads — the things that run once and exit | The platform, on demand                     |

The separation is worth having even though it is not a security boundary (next
section), because it gives you three useful things: independent quota, a
meaningful blast radius when something misbehaves, and a resource view that
separates "the platform is unhealthy" from "my work is unhealthy".

## A namespace is not a security boundary

This is the point readers most often get wrong, so it is stated flatly:

**A namespace is a naming and quota boundary. It is not a security boundary.**
Two pods in different namespaces on the same cluster are not, by virtue of that
fact, isolated from one another. Namespaces do not create a network partition, do
not prevent one workload from reaching another's endpoints, and do not by
themselves stop a compromised workload from doing anything the node permits.

What actually enforces isolation, where it exists, sits elsewhere:

| Enforcement                  | Where it lives                                     | What it actually separates                                                                             |
| ---------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Network policy**           | Inside the cluster, applied to namespaces and pods | Which pods may open connections to which others                                                        |
| **Private endpoints**        | The deployment's network                           | The data plane from the public internet — [07.4](04-the-network-boundary.md)                           |
| **Workload identity**        | The identity provider, federated into the cluster  | What a pod may authenticate _as_, and therefore what it may reach — [07.6](06-identity-and-secrets.md) |
| **Authorization at the API** | The application layer                              | What a principal may do, regardless of network position — part 04                                      |

The practical consequence: **a namespace boundary should be treated as an
organisational convenience, and every real control assumed to be somewhere
else.** If your design depends on "it is in a different namespace, so it cannot
reach us", the design depends on something a namespace does not provide.

Which of the enforcement mechanisms above your deployment applies, and how
strictly, is the operator's configuration. Network policy in particular is
present in the reference shape and enforced to a degree each deployment sets.
That is a question for your operator, and one of the more important ones to ask.

## Quotas and limits, and what hitting one looks like

Two different mechanisms, and conflating them is a common source of confusion:

- **Quotas** cap the total a namespace may consume — how much CPU, memory, and
  how many objects. A quota is a namespace-level ceiling.
- **Limits** bound an individual container. A limit is what happens to one pod.

| You hit            | Symptom                                   | What it means                                                        |
| ------------------ | ----------------------------------------- | -------------------------------------------------------------------- |
| **A quota**        | New workloads are refused or stay pending | The namespace is at its ceiling. Existing work keeps running.        |
| **A memory limit** | The container is restarted                | The pod exceeded its own bound. This is per-pod, not namespace-wide. |
| **A CPU limit**    | The container is throttled, not killed    | Slower responses, no restart. Easily mistaken for a performance bug. |
| **Pool capacity**  | Pods stay pending until nodes arrive      | Not a quota at all — the pool is growing, or cannot.                 |

The third row is the one that costs people days: a throttled container returns
slow responses and logs nothing, so it reads as an application problem. If
latency rises under load and nothing else changed, check throttling before
profiling.

## Placement: how tenant workloads stay off the system pool

The rule that separates the pools is enforced with the cluster's own placement
mechanisms:

- **Taints and tolerations.** The system pool carries a taint; only components
  that explicitly tolerate it may be scheduled there. Tenant workloads do not
  carry that toleration, so they cannot land there.
- **Node affinity.** Workloads are steered toward the pools intended for them,
  rather than being left to the scheduler's default preference.

These are the mechanism, and they are why the pool separation in the diagram
above is a rule rather than a hope. You will normally not configure them — but if your
deployment runs custom workloads, and you are asked to supply a scheduling
constraint, this is the machinery your request is expressed in.

The reference shape uses the two above; a specific estate may add admission
policy on top of them.

---

_Next: [07.3 — Images and the registry](03-images-and-the-registry.md)_
