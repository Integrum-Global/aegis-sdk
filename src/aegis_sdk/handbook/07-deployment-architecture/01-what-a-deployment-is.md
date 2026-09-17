# 07.1 — What a deployment is

Aegis is not something you install on a machine you already own. You are given a
**deployment** — a running platform at an address someone hands you — and you
administer *inside* it rather than operating the processes underneath it. The
distinction is the whole chapter: almost everything that surprises a new
integrator comes from assuming they are running the software when in fact they
are using it.

Every later chapter in this part is a detail of the shape below.

## What actually arrives

Three things, and it is worth being precise about which is which, because they
come from different places and have different lifetimes.

- **A running platform.** The services are already up, already configured,
  already storing data. You do not start them, and in the normal case you have no
  way to. Your work happens at the API and inside the namespace you are given.
- **An endpoint.** One HTTPS base URL, and it is the only address you need. It is
  the same address your browser uses and the same one your SDK uses; there is no
  separate administrative port to find.
- **A credential.** A key or token issued to your organisation, presented by your
  integration. What it can do is scoped by the roles your organisation has
  granted it, and that scoping is enforced server-side — see [07.6](06-identity-and-secrets.md)
  for how it is issued, scoped and revoked.

**What does not arrive: infrastructure credentials.** You are not given a
database password, a storage key, or a cluster administrator's kubeconfig,
because you do not need one to integrate. If you are asked to design against a
deployment and you find yourself looking for those, the design has drifted into
operating it.

## The components, and what each is for

Names vary between deployments and the ones below are generic roles, not a
inventory of any particular estate. What does not vary is the job each one does.

| Component | What it is for |
| --- | --- |
| **Managed Kubernetes cluster** | Where the platform's own services and yours actually run. Managed means the control plane is not your problem. |
| **Container registry** | Holds the platform's images. The cluster pulls from it; nothing is built on the cluster. |
| **Ingress / edge** | Terminates TLS, owns the public hostname, and is the single door into the deployment. |
| **Application namespace(s)** | Where the running services live, separated from the platform's own controllers. |
| **Job / agent execution namespace** | Ephemeral, short-lived workloads — the things that run once and exit. |
| **Managed relational database** | Where your organisation's state lives, permanently. Also where embeddings live. |
| **Cache** | Makes reads fast. Losing it costs latency, not data. |
| **Object storage** | Artifacts and evidence — the large, immutable, long-retained things. |
| **Secret store** | Holds the credentials the platform itself needs, referenced rather than embedded. |
| **Identity provider** | Who the humans are, and the federation that lets workloads hold identity without holding secrets. |

The ordering matters less than the split: the first five are the *substrate*,
the last five are *state and identity*. [07.5](05-stateful-services.md) covers the
state half and [07.6](06-identity-and-secrets.md) covers identity, because those
are the two places a design goes wrong quietly.

## The shape in one picture

Read this as the map for the rest of the part. The SDK's attach point is drawn
deliberately outside the boundary, because that is where it is: your code talks
to this deployment over one HTTP edge and reaches nothing else directly.

```
               Your integration — SDK over HTTPS
                              │
                              │  one HTTP edge · one base URL
                              ▼
┌──────────────────────────────────────────────────────────┐
│ ONE DEPLOYMENT                                           │
│                                                          │
│  Edge / ingress                                          │
│    TLS termination · one public hostname                 │
│                                                          │
│  Workloads                                               │
│    ├─ application services                               │
│    └─ ephemeral jobs and agent execution                 │
│                                                          │
│  State and identity                                      │
│    ├─ relational database    records and embeddings      │
│    ├─ cache                                              │
│    ├─ object storage         artifacts and evidence      │
│    ├─ secret store                                       │
│    └─ identity provider                                  │
└──────────────────────────────────────────────────────────┘
```

The state and identity components are not reachable from your network, and that
is a design property rather than a configuration detail —
[07.4](04-the-network-boundary.md) draws the line properly.

## Who owns what

This is the table to come back to. The honest answer is that ownership is
**split**, and most integration friction comes from assuming a row is entirely
one column or the other.

| Thing | Platform owns | You own | Notes |
| --- | --- | --- | --- |
| Cluster, node pools, control plane | yes | no | You never schedule pods directly. |
| Namespaces and their quotas | creates them | works inside them | Quota values are usually negotiable; the boundary is not. |
| Platform images and their digests | yes | no | You do not build or pin these — see [07.3](03-images-and-the-registry.md). |
| **Your** images, if you run any | registry, pull path | build and publish | Only if your deployment runs custom workloads at all. |
| Database engine, version, backup policy | yes | no | You choose what to store and how to index it. |
| Your organisation's schema and data | no | yes | Entirely yours, including retention decisions. |
| Network boundary and egress policy | default posture | requests for change | See [07.4](04-the-network-boundary.md) — this is where real deployments differ most. |
| Identity provider | runs it | configures your users | Federation into it is usually a shared task. |
| Your API credential | issues it | holds and rotates it | Scoped by the roles you grant it. |
| Upgrade timing | proposes and performs | your window preference | See [07.7](07-operating-the-deployment.md). |
| Audit evidence | produces and retains it | reads it | Retention and access differ from operational logs — [07.7](07-operating-the-deployment.md). |

*Design intent, not observable:* that the third column is exactly what the fourth
says and no more. You cannot verify the split from outside the deployment; you
can only verify the parts that surface at the API. The column is written so you
know what to ask, not so you can act as though it were settled.

**A working rule for the ambiguous rows:** if it changes what the platform *is*,
the platform owns it and you request a change. If it changes what your
organisation *means* — its units, roles, envelopes, knowledge — you own it and
you do it through the API.

## Where the SDK attaches

There is exactly one attachment point: **the edge**, over HTTP, at a base URL you
supply. Your client is configured with it through `sdk:aegis_sdk.ClientConfig`,
and nothing else in the SDK reaches the deployment by another route.

That single point is why the rest of this part matters less to your day-to-day
code than you might expect: once the base URL and the credential are right,
everything above is the platform's problem. It is also why a misconfigured
deployment is hard to diagnose from the client side — a base URL pointing at the
wrong estate produces a working client talking to the wrong system.

You can settle that question directly. `api:GET /api/v1/auth/me` answers which
principal you authenticated as, which is the cheapest way to confirm both halves
at once — the deployment you reached and the identity you reached it with.

## This is a reference shape

Say it plainly, because the rest of the part depends on the reader holding it:
**this is a reference architecture, not a description of a running estate.** A
given deployment may differ in detail — a component may be absent, an equivalent
substituted, a service pinned to a different engine. Where the differences matter
to you, they matter because they change what you can observe or control, and this
part names those places as they come up.

Three ways to find out which parts of this shape your deployment actually has:

1. **Ask your operator, and ask specifically.** "Do I get my own namespace, and
   what is its quota?" is answerable. "How does it work?" is not.
2. **Test what surfaces at the API.** Health operations, your own identity, and
   the error taxonomy are all observable; `api:GET /api/v1/auth/me` above is the
   simplest example.
3. **Read the rest of this part and notice which claims are marked.** Anything
   marked as design intent is a claim about construction you cannot check from
   where you sit. Treat those as questions for your operator rather than as
   facts about your deployment.

*Design intent, not observable:* the component split above, and the ownership
boundary that follows from it. The marker is not hedging — a reference
architecture that presented itself as an inventory would be wrong the moment any
deployment deviated, and wrong invisibly.

---

*Next: [07.2 — The cluster and its namespaces](02-the-cluster-and-namespaces.md)*
