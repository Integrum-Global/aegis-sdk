# 06.1 — What core and the SDK are

Two things arrived together and they are not the same kind of thing. One is a
running system with an internal structure you are about to design against. The
other is a client for it. Almost every architectural mistake made against this
platform traces back to treating the second as if it were the first — most
expensively by concluding that something the deployment owns is yours to
enforce, or the reverse.

This chapter draws the boundary and the split behind it. Everything later in
this part is a statement about one side of one of them.

## The shape, in one picture

```text
aegis, from where you stand
│
├── what you hold ──────────────────────────────────────────────────── this package
│     ├── AgenticOSClient            one object, pointed at one deployment
│     ├── 59 module namespaces       one shared transport between them
│     └── never on the wire          the handbook · the working artifacts · the probe
│
│   ┌─────────────────────────────────────────────────────────────────────────┐
│   │  THE BOUNDARY — HTTPS only.  One credential header per request.          │
│   │  No organisation id travels: tenancy is derived from the credential.     │
│   └─────────────────────────────────────────────────────────────────────────┘
│
└── what the deployment holds ───────────────────────────────────────────── core
      │
      ├── Trust Plane ────────── whether an action is permitted, and the record it leaves
      │     │
      │     ├── the attestation  who attested this agent, and the chain it sits in
      │     ├── the standing     posture — how much it may do unaided
      │     ├── the bounds       the envelope the action is judged against
      │     └── the decision     whether THIS action was permitted
      │           └── the audit spine     every decision, in order, re-derivable later
      │
      └── Execution Plane ────── work entering, running, carried, and stopped
            │
            ├── objective        a goal you ask for
            ├── request          a work item, produced by decomposing the objective
            ├── session          one agent's execution against a request
            └── artifact         a file produced against a request
```

Read the middle band carefully. It is the part of the package that **never
crosses**. Knowing which band a thing is in is the difference between an
integration that works and one that quietly measures the wrong machine.

## The plane split

This is the single most load-bearing idea in the part, so it is worth stating
plainly: **the deployment is organised into two planes with different
responsibilities, and the distinction is about what each one is *for*, not about
where either one runs.**

**The Trust Plane decides.** Its subject is authority: whether a given agent may
take a given action, and whether that can be established at all. It owns the
attestation that made the agent, the chain that shows where its authority came
from, and the posture that says how much of that authority it may use
unsupervised. When it decides, it judges the action against the envelope that
bounds what the role's delegate may do — a bound the *structure* authors and
this plane consults. Its **product is a verdict and a record**:
`api:POST /api/v1/trust/verify` is the decision as a call,
`api:GET /api/v1/trust/audit` is the record afterwards, and
`api:GET /api/v1/trust/health` reports whether the plane itself is answering —
the client's own documentation describes that one as an **unauthenticated**
snapshot, which is worth knowing before you decide how to monitor a governed
deployment.

**The Execution Plane does the work.** Its subject is the work itself: goals
accepted, decomposed, executed, and turned into files. Its **product is work
products** — an `api:POST /api/v1/objectives` becomes requests, requests become
`sdk:aegis_sdk.execution.SessionsModule` runs, runs produce
`sdk:aegis_sdk.execution.ArtifactsModule`.

**The relationship between them runs one way.** Execution asks; trust answers.
The Trust Plane does not do work, and the Execution Plane does not decide its
own authority. That is the whole of the contract, and it is what lets you reason
about either half on its own:

```text
   your process · the client
             │
             ▼
   ┌───────────────────────────┐
   │ ADMISSION                 │
   │ credential · tenancy      │
   └───────────────────────────┘
                 │
                 ▼
   ┌───────────────────────────┐            ┌───────────────────────────┐
   │ EXECUTION PLANE           │            │ TRUST PLANE               │
   │ objective → request →     │ ─────────▶ │ chain · posture ·         │
   │ session → artifact        │ ◀───────── │ envelope                  │
   └─────────────┬─────────────┘            └─────────────┬─────────────┘
                 │  asks: may this agent do this?         │
                 │  one verdict on THIS action            │
                 ▼                                        ▼
   ┌───────────────────────────┐            ┌───────────────────────────┐
   │ work products             │            │ the audit spine           │
   │ artifacts · results       │            │ the decision, recorded    │
   └───────────────────────────┘            └───────────────────────────┘

   Both refusals end at the same place, for different reasons:

     refused at the door                 refused here
     no plane was reached                the run ends
     — from ADMISSION                    — from the TRUST PLANE

            │                                    │
            └─────────────────┬──────────────────┘
                              ▼
                     ┌─────────────────┐
                     │ the call ends   │
                     └─────────────────┘
```

Three consequences follow, and each is a design decision rather than trivia.

**The two planes fail differently, and only one of them fails closed.** When
the Trust Plane cannot be reached, there is no verdict to give — and a governance
system that permitted on *no answer* would be worthless, so the refusal is the
safe reading. What you observe is a refusal. What actually happened is an
outage, and it is retryable, where a real refusal is not. That distinction is
[04.2](../04-the-api-surface/02-errors-and-refusals.md)'s, and it is the one
place this architecture can cost you a day: read a refusal on a governed action
as *the apparatus could not be consulted* before you read it as *the platform
decided about you*.

**The two products are different evidence, and you need both.** The record is
the Trust Plane's — what was decided, on what basis, in what order. The work
product is the Execution Plane's. A compliance story built only from artifacts
is a story about outputs, with nothing to say about authority; a story built
only from decisions has nothing to show for the work. Design for both from the
start, because the record is not reconstructible after the fact.

**A refusal at a plane is not the same as a refusal at the door.** Access
control decides whether your *call* is admitted. The Trust Plane decides whether
an *agent's action* is permitted. They produce overlapping statuses and have
completely different remedies. [06.2](02-the-request-path.md) puts both on one
path so you can tell which one you are looking at.

> ⚠ **The split is a split of responsibility. Whether it is a split of
> machines is not observable from here.** The two planes may be one process,
> two services, or two clusters; nothing you can reach distinguishes those, and
> nothing in your design should depend on the answer. What you *can* rely on is
> the direction of asking and the shape of what each one produces — and that is
> the part that binds you.

The Trust Plane gets a chapter of its own — [06.4](04-trust-and-the-audit-spine.md)
is the decision mechanism and the audit spine; the execution lifecycle is
[06.5](05-the-execution-model.md). This chapter only needs you to know which
half owns what.

## The governance objects, and which plane owns each

Before the planes are useful you need to know what they operate on. The objects
have a containment order, and it is the deployment's, not yours to rearrange:

```text
organisation                        the tenant root
   └── unit                         a knowledge boundary, with a default classification
        └── role                    reports_to another role; the reporting chain
             └── envelope           what this role's delegate may do — five dimensions
                  └── agent         the delegate itself
                       ├── trust chain    where its authority came from
                       └── posture        how much it may use unsupervised
```

| object | the question it answers | plane | read it at |
| --- | --- | --- | --- |
| **organisation**, **unit**, **role** | what the structure is | neither — it is the context both planes read | `sdk:aegis_sdk.standup.OrganizationsModule`, `sdk:aegis_sdk.standup.OrganizationRolesModule` |
| **envelope** | what may this role's delegate do? | authored in the structure; **consulted** by the Trust Plane when it decides | `sdk:aegis_sdk.RoleEnvelopesModule` |
| **agent** | who is the delegate? | acted by the Execution Plane, bounded by the Trust Plane | `sdk:aegis_sdk.core.AgentsModule` |
| **authority** | who attested this agent? | Trust Plane | `sdk:aegis_sdk.trust.AuthoritiesModule` |
| **chain** | where did its authority come from? | Trust Plane | `sdk:aegis_sdk.trust.ChainsModule` |
| **posture** | how much may it do unaided, now? | Trust Plane | `sdk:aegis_sdk.TrustPosture` |
| **decision** | was *this* action permitted? | Trust Plane — and it is a record, not a setting | `api:GET /api/v1/trust/audit` |
| **objective**, **request**, **session**, **artifact** | what work was asked for, and what came out | Execution Plane | `sdk:aegis_sdk.execution.ObjectivesModule` |

Two things about that table are worth carrying before you meet the chapters that
develop it.

**An agent is the one object both planes touch**, from opposite sides. The
Execution Plane acts as it; the Trust Plane bounds it. That is why an agent can
be perfectly healthy and still unable to do the thing you asked — the two planes
are answering different questions about it.

**"Decision" is an object, not an event that vanishes.** It is written down,
addressable, and re-derivable. That is unusual enough to be worth noticing: most
systems treat a permission check as a step, and this one treats it as a record
you can go back and read.

## What the SDK is not

Three non-identities, each of which someone assumes at least once.

**It is not the deployment's source code.** The package contains no server.
Measured: no HTTP framework is imported anywhere in it, by any form of import —
every occurrence of one is a comment *about* the shape core answers with. You
were not given core, and nothing here is a copy of it.

**It is not an evaluator.** No plane runs in your process. Nothing here decides
whether a call is allowed, resolves an envelope, evaluates a clearance, or
consults a chain. When you read a verdict, you are reading a response. That is
why `sdk:aegis_sdk.modules.GovernanceExplainModule` is a set of *calls* —
`api:POST /api/v1/governance/explain-access` and its siblings — rather than a
local reasoning step: explaining a decision is itself a request to the plane
that made it.

**It is not a place to keep the truth.** Every read is a round trip, and a value
you read is a snapshot from the moment core answered.

The client caches nothing — measured: no response cache, no memoised read
anywhere in the transport or the modules. That removes one class of bug
entirely: there is no local copy that can disagree with the server, and nothing
to invalidate. **But it does not make a read fresh**, because the deployment
caches, and a cached answer is still an answer.

Some surfaces are explicit about it, and they are the ones to model on.
`sdk:aegis_sdk.modules.LlmProvidersModule` reads a provider's model list from
`api:GET /api/v1/llm/models` and the result carries `from_cache`, `cached_at`
and a `fallback` flag; a separate call,
`api:POST /api/v1/llm/providers/{}/refresh`, forces the recalculation. Where a
surface offers you that shape, read the flag rather than assuming freshness —
and where it does not, treat the read as a snapshot with no guarantee about its
age, because you have nothing to check.

> ⛔ **The client's route table is a belief, not a specification.** Every `api:`
> anchor in this book resolves against *the calls this package makes*. If the
> client and the deployment disagree about a path, the client is wrong in the
> same direction and nothing here notices. The check that ships with this book
> verifies existence, never enforcement — an operation can exist and check
> nothing at all. Treat "this route is declared" and "this route does a thing"
> as the two separate claims they are.

## What you reach, and how

The client presents **59 namespaces carrying 828 public members between them**.
The number is measured, and it is large enough that the useful question is not
what exists but which plane a namespace serves.

| family | reaches | plane | examples |
| --- | --- | --- | --- |
| **trust** | whether an action is permitted, and the record | Trust Plane | `sdk:aegis_sdk.trust.ChainsModule`, `sdk:aegis_sdk.trust.AgentTrustModule` |
| **structure** | the organisation the planes read | neither | `sdk:aegis_sdk.standup.OrganizationRolesModule`, `sdk:aegis_sdk.RoleEnvelopesModule` |
| **work** | what runs, and what it produced | Execution Plane | `sdk:aegis_sdk.execution.ObjectivesModule`, `sdk:aegis_sdk.execution.SessionsModule` |
| **lineage** | what produced what, and from what | neither — it observes both | `sdk:aegis_sdk.dataflow.DataFlowModules` |
| **commercial** | subscription, quota, license | neither — it bounds the tenant | `sdk:aegis_sdk.revenue.SubscriptionsModule` |

Four details of the surface's shape will save you time.

**Some namespaces are grouped and some are flat.** `trust`, `revenue` and
`dataflow` are containers: `client.trust.chains`, not `client.chains`. The rest
are direct: `client.agents`, `client.objectives`. Nothing distinguishes the two
by name.

**The name is not the surface.** `client.roles` and `client.role_admin` are
different APIs over different routes with different return shapes — one returns
untyped dictionaries, the other typed models. The client's own comments say so.
When two similarly-named namespaces exist, read both before assuming one is an
alias.

**Some surfaces require a kind of credential you may not hold.** Several
modules — `sdk:aegis_sdk.modules.CredentialsModule`,
`sdk:aegis_sdk.modules.EmergencyBypassModule`,
`sdk:aegis_sdk.modules.KillSwitchModule` and
`sdk:aegis_sdk.modules.PromotionsModule` — refuse an API key on *every* route,
reads included. That is not a scope problem and no scope fixes it.

**`client.trust.observability` is the plane looking at itself.** It aggregates
chain and verification metrics and returns a health snapshot of the Trust Plane
— `sdk:aegis_sdk.trust.TrustObservabilityModule`. If you are deciding whether a
refusal was a decision or an outage, that is the surface that separates them,
and [06.4](04-trust-and-the-audit-spine.md) is where it is developed.

## The part of the package that never crosses

The middle band of the first diagram is easy to skip past, and skipping it is
how you lose a day. Beside the client the package ships:

- **this handbook**, which explains behaviour;
- **the working artifacts** — agent briefs, skills, guardrails, and a set of
  enforcing hooks that run in your own CLI session rather than against core;
- **a probe**, `python -m aegis_sdk.coc.probe`, a runnable reachability check;
- and **a local orchestration subpackage**, `sdk:aegis_sdk.nexus`.

That last one is the one to be careful with, and it is worth stating exactly.

> ⛔ **`sdk:aegis_sdk.nexus` does not touch your deployment — and its most
> convincing-looking verb returns success without doing anything.** Measured:
> the subpackage imports no HTTP client, no socket, no subprocess, and no
> container or cluster tooling anywhere. `sdk:aegis_sdk.nexus.DeploymentManager`'s
> `deploy()` validates a configuration object, then returns a
> `sdk:aegis_sdk.nexus.DeploymentResult` with `success=True` and a set of
> endpoints synthesised as `http://localhost:<port>` from the manifest. It
> deploys nothing. Its own source says the real implementation would talk to
> Kubernetes or Docker; the shipped one does not.
>
> Nothing is broken relative to what that code claims internally. The hazard is
> entirely in the reading: a method called `deploy()`, returning a result
> object, next to configuration models named for production tiers, invites the
> conclusion that you have a deployment tool. You have a **configuration
> model**. Use it to *describe* a shape — and do not build a workflow on the
> belief that calling it changed anything anywhere.
>
> **UNVERIFIED:** whether this subpackage is intended for partners at all, or is
> an internal library that happened to travel in the wheel. Nothing in the
> package says, and the question is not answerable from what you were given.

The handbook, the working artifacts and the probe are in the same band: they are
things you *read and run locally*. None of them is a client for core, and none
of them makes a governance decision. A hook running in your session can refuse
what *your tooling* does — that is a real control and it is worth wiring — but it
is not the deployment's enforcement, and it does not bind an agent that is
already running somewhere else.

## Where the standards sit

Core implements four open specifications published by the Terrene Foundation
under CC BY 4.0. Core implements them; it does not own them, and this package is
a client for the implementation rather than a home for the specifications.

The vocabulary is not decoration — it is how you predict names, and the plane
split itself is one of the four standards' central claims.

| specification | what it contributes | where it shows up |
| --- | --- | --- |
| **CARE** | the dual plane — Trust Plane and Execution Plane — with the posture ladder and the four-zone verdict | the split itself; `sdk:aegis_sdk.TrustPosture` |
| **PACT** | the organisation model: units, roles, D/T/R addressing, envelopes, clearance | `sdk:aegis_sdk.standup.OrganizationRolesModule`, `sdk:aegis_sdk.RoleEnvelopesModule` |
| **EATP** | the trust protocol: attestation, chains, delegation, revocation, the trust verdicts | `sdk:aegis_sdk.TrustChain`, `api:POST /api/v1/trust/establish` |
| **CO** | the method — *how* to work with the system, including this book | the working artifacts beside this handbook |

Read the third column as naming where the vocabulary is *expressed*, never where
it is enforced. A module named for a concept means core implements that concept
and this client can reach it. Enforcement is the deployment's — the same fact as
everything else on this page, arrived at from a different direction.

## What you can reach, in one paragraph

You can call any operation this client declares, with a credential core accepts,
and you will get back one of three things: a parsed payload, raw bytes, or a
typed error. You can read the state core holds and change it to the extent the
governance on it permits; you can read a decision the Trust Plane made, and ask
it to explain one. You cannot evaluate a governance decision locally, boot a
copy of core, read core's source, or reach anything the API does not expose. And
you cannot, from this position, see *which* component refused you — only that
something did, and with what status. Where the two halves disagree, core is
right: the client is a belief about it, and this book is a belief about the
client, both re-checkable against the build in your hands.

---

*Next: [06.2 — The request path](02-the-request-path.md)*
