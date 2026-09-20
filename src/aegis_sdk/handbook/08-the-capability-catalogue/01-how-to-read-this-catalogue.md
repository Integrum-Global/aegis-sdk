# 08.1 — How to read this catalogue

This chapter is the key to the six that follow. It gives you the taxonomy the
catalogue is organised by, the rule for mapping a capability onto the module that
serves it, and — the part worth doing before you trust any of it — the commands
that check what **your** deployment actually exposes.

It is short on purpose. The value of this part is in 08.2 through 08.8; this page
exists so those chapters can be scanned rather than read, and so that a
capability you cannot find is a capability you can rule out rather than one you
are unsure about.

**Everything in this part is reachable from one object.** There is no second
client, no admin SDK, no separate management plane.

## The three kinds of thing in the catalogue

Every entry in this part is one of three kinds, and knowing which you are looking
at tells you where the failure will show up.

| kind           | what it is                                                                                  | how it fails                                                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Record**     | Something the platform stores and you address by id — a role, an agent, a policy            | Fails at create time, loudly, with a validation error naming the field                                                         |
| **Lifecycle**  | A record that moves through states — a bridge, an objective, a posture                      | Fails at a transition: the call returns a refusal naming the state it was in                                                   |
| **Projection** | A computed view over other records — effective constraints, an access matrix, a trust score | Never fails; returns a value computed from whatever inputs exist, which is why an empty input set reads as a permissive answer |

The third row is the one to internalise. A projection over an incomplete
organisation returns successfully and looks authoritative — an effective-envelope
call against a role whose ancestors carry no envelopes returns a shape, not an
error. When a governance answer surprises you, check whether you are reading a
projection and what it was computed from.

## Two surfaces, two sizes — and both numbers are correct

There are two different denominators in this catalogue and an evaluator will
meet both. They answer different questions, and treating either as "the size of
Aegis" produces a wrong conclusion.

| surface                       | size                       | what it is                                                                      |
| ----------------------------- | -------------------------- | ------------------------------------------------------------------------------- |
| **What the platform serves**  | ~1,254 authored operations | 1,133 are HTTP route operations a running deployment lists; the rest are reached through other governed surfaces |
| **What this client declares** | 933 operations             | The operations the SDK has a method for — the anchorable set                    |

**The client is deliberately smaller than the platform.** It covers the paths an
architect drives; the remainder are served over HTTP and reached directly. So a
capability described here without an anchored route is not a gap in the platform
and not a defect in the client — it is a surface you call the other way, and
[04.1](../04-the-api-surface/01-calling-the-api.md) is how.

Every `api:` anchor in this part comes from the 933. Where this catalogue
describes something the client has no method for, it says so and routes you to
part 04 rather than inventing an anchor.

> ⚠ **A route listing you generate yourself will not match these numbers.** This
> catalogue counts operations, not per-method variants: an introspection dump
> counts each HTTP verb on a path separately and includes framework-generated
> endpoints, so it reads higher. **Authored operations is the denominator a
> catalogue should use**, and it is the one above.

## The taxonomy, and why it is not the module list

The catalogue is grouped by **what the capability is for**, not by which module
implements it. Those two groupings genuinely differ, and following the module
layout would scatter related capabilities across chapters.

| chapter  | the question it answers                          | the areas inside it                                                         |
| -------- | ------------------------------------------------ | --------------------------------------------------------------------------- |
| **08.2** | Who exists, and who may act?                     | Organisations, units, roles, teams, users, SSO, invitations, API keys, RBAC |
| **08.3** | What acts, and how is it driven?                 | Agents of every kind, pools, sessions, pipelines, skills, tools, A2A, MCP   |
| **08.4** | What is being asked, and how does it resolve?    | Objectives, work units, requests, directives, decisions, escalation         |
| **08.5** | What bounds all of it?                           | Trust chains, postures, envelopes, clearances, policy, bridges, bypass      |
| **08.6** | What may it know, and where did that come from?  | Knowledge, categories, reviews, connectors, classification, lineage         |
| **08.7** | What was recorded?                               | Audit, compliance, analytics, metrics, notifications, webhooks, settings    |
| **08.8** | What does it cost, and what attaches externally? | Billing, licensing, applications, external agents, gateways, surfaces       |

### The eighteen capability areas, and where each one is

The seven catalogue chapters group eighteen distinct capability areas. If you
arrived with a requirements list organised by area rather than by chapter, this
is the index to read:

| #   | capability area                                           | chapter                                                                         |
| --- | --------------------------------------------------------- | ------------------------------------------------------------------------------- |
| 1   | Identity, access and tenancy                              | [08.2](02-organization-and-identity.md)                                         |
| 2   | PACT organisational modelling                             | [08.2](02-organization-and-identity.md)                                         |
| 3   | Trust plane — chains, delegation, revocation              | [08.5](05-governance-and-trust.md)                                              |
| 4   | Trust posture and the verification gradient               | [08.5](05-governance-and-trust.md)                                              |
| 5   | Constraint envelopes, clearance and compartments          | [08.5](05-governance-and-trust.md)                                              |
| 6   | Bridges and information barriers                          | [08.5](05-governance-and-trust.md)                                              |
| 7   | Agents, pools and the agent catalogue                     | [08.3](03-agents-and-execution.md)                                              |
| 8   | Objectives, work and sessions                             | [08.4](04-work-and-objectives.md)                                               |
| 9   | Human-on-the-loop — approvals, escalations, interventions | [08.4](04-work-and-objectives.md)                                               |
| 10  | Emergency controls and kill switch                        | [08.5](05-governance-and-trust.md)                                              |
| 11  | Knowledge, retrieval and ingestion                        | [08.6](06-knowledge-and-data.md)                                                |
| 12  | Connectors, integrations, A2A and MCP                     | [08.3](03-agents-and-execution.md)                                              |
| 13  | Execution runtime and LLM governance                      | [08.3](03-agents-and-execution.md) · [08.8](08-commercial-and-extensibility.md) |
| 14  | Audit, compliance and independent assurance               | [08.7](07-evidence-and-operations.md)                                           |
| 15  | Observability, analytics and drift                        | [08.7](07-evidence-and-operations.md)                                           |
| 16  | Commercial — licensing, billing, entitlement              | [08.8](08-commercial-and-extensibility.md)                                      |
| 17  | Platform administration and extensibility                 | [08.8](08-commercial-and-extensibility.md)                                      |
| 18  | Developer surface                                         | [08.1](01-how-to-read-this-catalogue.md) · part 04                              |

**Five of the eighteen areas land in 08.5**, which is why that chapter is the
longest and why it is the one to read first against a governance requirement.
Areas 3 to 6 and 10 are all controls, and a requirements list that separates them
is describing one apparatus from five angles.

**One capability appears in two chapters when two chapters genuinely own a piece
of it**, and the entry says so. Trust posture is the clearest case: the _agent_
side of it is in 08.3 because posture is what decides whether an agent may act
autonomously, and the _governance_ side is in 08.5 because posture is one of the
controls an architect sets. Neither chapter repeats the other; each links across.

## Mapping a capability to the module that serves it

Every area names its entry point as a resolvable symbol. Two shapes appear, and
the difference is only how the SDK organises itself:

| shape                 | example                                   | reached as            |
| --------------------- | ----------------------------------------- | --------------------- |
| **Top-level module**  | `sdk:aegis_sdk.modules.pools.PoolsModule` | `client.pools`        |
| **Namespaced module** | `sdk:aegis_sdk.trust.chains.ChainsModule` | `client.trust.chains` |

There are two namespaces, `trust` and `revenue`, plus a `dataflow` namespace for
lineage. Everything else hangs directly off the client. When an entry names
`sdk:aegis_sdk.trust.postures.PosturesModule`, the call is
`await client.trust.postures.get(...)`.

`sdk:aegis_sdk.AgenticOSClient` is the object that presents all of them, and
`sdk:aegis_sdk.ClientConfig` is where its endpoint and credential live.

```python
from aegis_sdk import AgenticOSClient, ClientConfig

client = AgenticOSClient(
    ClientConfig(
        base_url="https://aegis.example.com",
        api_key="<your key>",
        timeout=30.0,
    )
)

roles = await client.roles.list()
chains = await client.trust.chains.list()
usage = await client.revenue.billing.get_usage()
```

## Checking reach on your own deployment

A catalogue is a statement about the platform. What **your** credential can reach
on **your** deployment is a different question, and it is one you can answer
yourself rather than take on trust.

Two commands. Both ship inside the SDK you were given.

```bash
# What does this package declare, and which routes does my credential reach?
python -m aegis_sdk.coc.probe --base-url https://aegis.example.com --api-key "$AEGIS_API_KEY"

# Offline: does every module actually perform a request, or does one fabricate a response?
python -m aegis_sdk.coc.probe --transports-only
```

The probe derives its operation set from this package's own call sites rather
than from a written list, calls the subset that is safe to call blind — `GET`
with no path parameters — and reports where your credential and the route
disagree.

**Read its exit code, not just its output.** The four values are distinct and
collapsing them is how a failed run gets banked as a clean one:

| exit | meaning                                                                     |
| ---- | --------------------------------------------------------------------------- |
| `0`  | Clean — every probed route behaved as the catalogue says                    |
| `1`  | Findings — at least one route was refused, or a transport was simulated     |
| `2`  | Usage — the invocation itself was wrong; nothing was measured               |
| `3`  | **Undetermined** — a credential failed to authenticate, so nothing is known |

> ⛔ **Exit 3 is not a pass.** An expired token and a perfectly reachable API
> produce the same empty finding set, so the probe refuses to report a zero it
> did not earn. If you see `3`, fix the credential and run it again — a
> catalogue claim checked against an unauthenticated run has been checked against
> nothing.

The failure mode to expect: a probe run with a key that lacks a scope reports
refusals across a whole family and reads like the capability is absent. It is
not — it is unreachable _by that credential_.
[04.3](../04-the-api-surface/03-credentials-and-keys.md) is where that
distinction is drawn, and it is worth reading before you conclude anything from
a run with findings.

## Checking the book against the package

The handbook ships with its own checker. Every route and symbol named in this
part is resolved against the package you hold — so a capability named here that
your build does not carry is caught mechanically rather than discovered at
runtime.

```bash
python -m aegis_sdk.handbook.check     # prints OK, or FAIL with a finding per problem
```

It resolves every `api:` route against the operation set derived from the
package's call sites, resolves every `sdk:` symbol by import, and follows every
internal link. Run it after upgrading the SDK: a route that stops resolving is
the earliest signal that a capability moved.

## Reading an operations list

Each area lists its operations in the anchored form, for example
`api:GET /api/v1/organization-roles/{id}` — method, then path, with `{id}`
standing for any path parameter. The lists are representative rather than
exhaustive for the largest families: `/agents` alone publishes 47 operations and
`/trust` another 47, and a chapter that printed every one would be a worse
reference than one that names the shape and the notable exceptions.

**Where a family is listed in full, the chapter says so.** Where it is not,
assume the CRUD five — list, create, get, update, delete — exist even when only
the interesting ones are named, and use the SDK module's own method list as the
enumeration. That is the honest granularity: the module is the surface you call,
and its methods are the catalogue at its finest grain.

```python
# The module's own methods are the finest-grained catalogue there is
import aegis_sdk.modules.pools as pools

print([m for m in dir(pools.PoolsModule) if not m.startswith("_")])
```

## A note on vocabulary

Aegis implements four open standards, and their vocabulary is load-bearing
throughout this part. Postures are always lowercase — `pseudo`, `supervised`,
`shared_planning`, `continuous_insight`, `delegated` — and the five constraint
dimensions are **Financial**, **Operational**, **Temporal**, **Data Access** and
**Communication**. [02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
and [06.3](../06-architecture/03-the-governed-organization.md) are where those
are taught; this part uses them as given.

---

_Next: [08.2 — Organisation and identity](02-organization-and-identity.md)_
