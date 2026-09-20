# Part 07 — Deployment architecture

**Audience: the lead engineer on a partner integration — you are designing
against a deployment whose internals you do not operate.** You will not run its
nodes, hold its cloud credentials, or open its cluster. You will point a client
at it over HTTPS, and you will be asked to answer for what it does. This part is
the shape of the thing you are attaching to.

**What it is.** A reference architecture for a production Aegis deployment on
**Azure** — that is what this part targets, and naming the cloud is a statement
about the reference rather than about your estate. It covers the components one
is built from, what each is for, who owns what, and where the boundaries fall; it
answers three questions in order — what am I deploying, what do I own, and where
does the line sit between me and the platform.

The reference deployment runs on managed Kubernetes in Azure: a managed cluster,
a container registry, an ingress edge, one or more application namespaces, an
ephemeral job and agent execution namespace, a managed relational database with a
vector extension, a cache, object storage, a secret store, and your identity
provider. Three of those are specifically Azure's — the managed cluster, the
container registry and workload identity federation. The rest are generic: a
namespace, a network policy, and a secret referenced at runtime rather than baked
in all exist under some name on every platform, and the chapters keep them
generic and say so where the distinction matters.

_Design intent, not observable_ — that **your** deployment has this shape. It is
the shape the chapters describe, and the deployment you are actually attached to
is the one you can check. [07.1](01-what-a-deployment-is.md) names each of them
and says what it is for; its ownership table is the one you will keep coming
back to.

**What it is not.** An inventory of any particular running estate. A given
deployment will differ from this reference in detail, and where the two
disagree, the one you are attached to is the real one. Every resource name in
this part is a placeholder — `<cluster-name>`, `<registry>.azurecr.io`,
`<app-namespace>` — because the names belong to the deployment rather than to
the architecture.

**Nothing here rests on a file you were not given**, which is the same rule the
rest of the book follows — and it costs this part something real. It describes
infrastructure from outside, so much of what it says is how a deployment is
*designed* rather than something you can measure from your own machine. The
convention for marking that is set out at the foot of this page, and it is worth
reading before the chapters.

## Where your code attaches

Your process holds a client configured against a base URL you supply, and that
base URL is the edge. `sdk:aegis_sdk.ClientConfig` is where the endpoint, the
credential and the timeout policy live, and `sdk:aegis_sdk.AgenticOSClient` is
the object that presents them.

The client half of that is checkable, and worth stating flatly: there is one
configured address, and no code path in this client that aims at any other.
Nothing else in this part is reachable from your process — not the cluster, not
the network, not the database. The other half — that the edge is the
deployment's *only* public entry point — is a claim about how the deployment is
built rather than something your side can check, and
[07.4](04-the-network-boundary.md) is where it is made and marked.

One more thing to expect, so that meeting it later is not a surprise: a
deployment **may** offer a second, non-public path into the cluster — a
namespace-scoped administrative path its operators use.
[07.2](02-the-cluster-and-namespaces.md) describes it, and marks whether a given
deployment provides one as a question to ask up front rather than discover during
an incident. It is not a second door for your integration: nothing in the SDK
reaches it, and the edge remains the only address your code has.

That gives you one check worth running on day one. A deployment pointed at the
wrong cluster, or answering as a principal you did not expect, looks identical
to a correct one until you ask: `api:GET /api/v1/auth/me` reports which
principal your credential resolves to on the deployment you are actually talking
to. Establish that before you debug anything else.

## The chapters

| #    | Chapter                                                    | Read it when                                                                                              |
| ---- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 07.1 | [What a deployment is](01-what-a-deployment-is.md)         | First. The whole shape in one place, and the ownership table that draws the line between what you own and what the platform operates |
| 07.2 | [The cluster and its namespaces](02-the-cluster-and-namespaces.md) | You are asking where the processes actually run, or what a namespace does and does not separate    |
| 07.3 | [Images and the registry](03-images-and-the-registry.md)   | You need to know which code is running, or you are planning an upgrade or a rollback                       |
| 07.4 | [The network boundary](04-the-network-boundary.md)         | You are drawing your own security boundary, or someone asks what is reachable from where                   |
| 07.5 | [Stateful services](05-stateful-services.md)               | You are reasoning about where the organisation's state lives, or what a backup and a restore are worth     |
| 07.6 | [Identity and secrets](06-identity-and-secrets.md)         | You hold a credential for your own integration, or you are auditing how anything authenticates             |
| 07.7 | [Operating the deployment](07-operating-the-deployment.md) | You are about to go to production, and want the checklist and the questions to put to your operator        |

## How the seven chapters relate

They are not seven topics. They are one deployment described in layers — where
the code runs, what encloses it, and what it holds — and knowing which layer a
question belongs to is most of the work of finding the answer.

```
┌─ reading order ───────────────────────────────────────────────────────────────
│
│  07.1  What a deployment is                       the frame: the whole shape, and who owns what
│   │
│   ├─► 07.2  The cluster and its namespaces        where the code runs, and what bounds it
│   │    │
│   │    ├─► 07.3  Images and the registry          which code is running, pinned by a digest
│   │    │
│   │    └─► 07.4  The network boundary             what is reachable, and from where
│   │         │
│   │         └─► 07.5  Stateful services           where the organisation's state lives
│   │              │
│   │              └─► 07.6  Identity and secrets   which identities reach what, and as whom
│   │
│   └─► 07.7  Operating the deployment              change, upgrade, evidence, recovery
│
└───────────────────────────────────────────────────────────────────────────────
```

Read it top to bottom. Each branch is a **reading dependency**, not traffic —
what has to be understood before the next chapter lands. The chapters nest where
one chapter's subject is the context for the next, and four things follow from
the shape:

- **07.1 is the frame.** Every chapter below it is a detail of it, and the
  ownership table there is what gives each later boundary statement its meaning:
  a boundary you do not control is a different kind of fact from one you do.
- **07.2 and 07.3 are where the code runs, and which code it is.** 07.4 reads
  after both: a boundary drawn without knowing what it separates is a diagram,
  not a design.
- **07.4 is the hinge.** 07.5 and 07.6 both hang off it — where the state lives,
  and which identities may reach what. The network decides who may *try*; those
  two chapters are about what is there and who succeeds.
- **07.7 is the only chapter you act on over time**, and it assumes the rest: a
  rollout is a digest change from 07.3, and a restore is 07.5's subject. It is
  also where the questions the earlier chapters told you to ask are collected.

## Where this part sits relative to the others

Part 02 is the working reference: it shows you how to stand an organisation up
and run work through it, and this part does not repeat any of that. Part 04 is
the API surface — how you call a deployment over HTTP, what a credential is,
what an error looks like. Part 06 is the platform's architecture: what the
system *is*, and why its boundaries fall where they do.

This part is the deployment those three run on. Part 06 describes a system you
never see the inside of; this part describes the machine that holds it — the
cluster, the network, the state, the identities, and the operations that change
them over time.

The practical test is the question you are asking. *"How do I establish a trust
chain?"* is part 02. *"Why did this call come back refused, and what does this
error mean?"* is part 04. *"What is actually running, who can change it, and what
happens to it during an upgrade?"* is this part — and it is the one your
security review will ask, because it is the one that decides what you can
promise about the deployment you do not operate.

## What a reference architecture can and cannot tell you

This section is the one to read if you read nothing else here, because a
reference shape is easy to mistake for a description of your deployment.

**What it can tell you:**

- The components a production deployment is built from, and what each is for
  before how it is configured.
- Where ownership usually falls — which parts you administer inside, which the
  platform operates, and which are genuinely shared.
- Where your code attaches, and what it presents when it does.
- The shape of the operations a deployment undergoes — rollout, upgrade,
  rotation, restore — and what each one touches.

**What it cannot tell you:**

- **It cannot tell you what your deployment is.** A reference shape is a
  design; a running deployment is an instance of it. Where they differ, yours
  is the one you are attached to, and only whoever operates it can tell you
  which case you are in.
- **It cannot tell you where a boundary is enforced.** From your side a refusal
  is a refusal. Which component produced it is not visible, and a refusal that
  arrives from a different layer than you assumed will send you to change the
  wrong thing.
- **It cannot tell you which boundaries are structural and which are
  historical.** Some are load-bearing and some are the residue of how a system
  grew. The behaviour is identical either way, so no amount of watching from
  your position separates them.
- **It cannot tell you that a control does anything.** A resource that exists is
  not a check that runs; this is the book's standing warning, and it applies
  twice over to infrastructure you cannot instrument yourself.
- **It cannot tell you the numbers.** Any figure here is an illustrative
  example and is labelled as one. Real deployments vary, and a number you cannot
  source is worse than no number.
- **It cannot tell you your operator's choices.** Egress policy, retention
  windows, recovery objectives and capacity ceilings are set by whoever runs
  the deployment, and it is precisely there that real deployments differ from
  the reference.

So the markers matter more in this part than anywhere else in the book. Where a
claim rests on something you can observe, it is stated as observation. Where it
explains how the deployment is *designed*, it is marked _design intent, not
observable_. Where it could not be settled from outside, it says **UNVERIFIED**.
Where the shipped behaviour is wrong it says **open defect**, with the symptom
you will recognise it by.

A chapter in this part that uses none of those markers should be read as
claiming more than an outside read can support.

[07.7](07-operating-the-deployment.md) closes with the checklist to run through
before production and with the questions to put to whoever operates your
deployment — which is the right destination for everything this page has just
said it cannot answer.

---

_Next: [07.1 — What a deployment is](01-what-a-deployment-is.md)_
