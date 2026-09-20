# The Aegis Architect and Operator Handbook

<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->

You have been given a deployed Aegis and the SDK that drives it. This book is how
you work with both.

Aegis is Integrum's commercial implementation of four open standards — **CARE**,
**PACT**, **EATP** and **CO** — published by the **Terrene Foundation** under
CC BY 4.0. Aegis implements those standards; it does not own them.

## Who this is for, and what it assumes

You are an **architect**, an **operator**, or an **engineer designing against the
platform**. The first two design the governed organisation, stand it up, give
agents their bounds, and keep the result running and evidenced. The third is
building something that talks to Aegis — an integration, a service, a product
surface — and needs to know how the platform is put together before choosing
where to attach. Parts 01 to 05 are written for the first two; part 06 is
written for the third, and every part is readable by all three. None of you is
writing the platform's own source, and you were not given it — nothing here asks
you to open a file you do not have.

It assumes you can read Python and are comfortable at a shell. It does not assume
you have used Aegis, or that you know what any of the four standards say.

## The one thing to understand before you start

**The harness is the primary working surface. The web console is the second one.**

Almost everything an architect or operator does — creating an organisation,
defining units and roles, writing an operating envelope, establishing a trust
chain, moving an agent's posture, submitting work, pulling evidence — is done by
driving the SDK from your own code, against a deployment you point it at. That
path is scriptable, reviewable, diffable, and repeatable across environments.

The console is real and it is not a toy: it is where humans answer the questions
Aegis stops to ask, and it is where you look when you want to see the state
rather than change it. But an organisation built by clicking is an organisation
nobody can rebuild, review or promote between environments. Build it in code.

Every chapter in parts 01 to 04 shows the harness path. Where the console does
the same thing, the chapter names the screen so you can find it. Part 05 covers
the console on its own terms. Part 06 is neither path: it is the system-level
picture both of them drive.

## The parts

| #      | Part                                                                             | Read it when                                                                                                                                                   |
| ------ | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **01** | [Orientation](01-orientation/)                                                   | First. What you were given, how governance actually works here, and your first working session                                                                 |
| **02** | [Working through the harness](02-working-through-the-harness/)                   | The spine. Standing up an organisation, bounding it, running work through it, and evidencing it                                                                |
| **03** | [Extending the platform](03-extending-the-platform/)                             | You are adding a capability — a tool, an agent, a skill, a pipeline                                                                                            |
| **04** | [The API surface](04-the-api-surface/)                                           | You are calling Aegis over HTTP directly, debugging an authorization failure, or asking what the client does with errors, credentials, pages, load and streams |
| **05** | [The web console](05-the-web-console/)                                           | You want to know what a screen shows, or you are the human answering a held decision                                                                           |
| **06** | [Architecture](06-architecture/)                                                 | The system-level picture. The plane split, the governance objects, where enforcement happens, and where your integration attaches                              |
| **07** | [Deployment architecture](07-deployment-architecture/)                           | You are deploying the platform, sizing it, or asking where its boundaries actually fall                                                                        |
| **08** | [The capability catalogue](08-the-capability-catalogue/)                         | You are asking what Aegis can do — the complete capability surface, by area, with the operation that reaches each one                                          |
| **09** | [The governance architecture](09-the-governance-architecture/)                   | You are satisfying an auditor. The two planes, envelopes, clearance, the decision gradient, trust chains, the audit spine, and containment                     |
| **10** | [The organisation structure framework](10-the-organization-structure-framework/) | You are designing the organisation your agents will live in — the D/T/R grammar, addressing, roles, trust chains and re-orgs                                   |
| **11** | [The deployment pack](11-the-deployment-pack/)                                   | You are standing a deployment up and running it — provisioning, the configuration reference, the runtime's node catalogue, releasing, operating, verifying     |

Read **01** in order. After that, **02** is the working reference you will return
to; **03** through **11** are consulted rather than read through.

**If you were handed this book to answer one question**, three parts answer the
three most common ones on their own: **08** for _what can it do_, **09** for _how
is it governed_, and **10** for _how do we model our organisation in it_.

The tree below says which part you reach for, not which part to read next:

```
the book
│
├── 01  Orientation                      read in order — start here
├── 02  Working through the harness      the spine; you return to it
│     ├── 03  Extending the platform
│     ├── 04  The API surface
│     └── 05  The web console
│
├── 06  Architecture                     consulted from any part above
│     └── the system-level picture: how the platform is put together,
│         where its boundaries are, and where your integration attaches
│
├── 07  Deployment architecture          consulted from any part above
│     └── the reference deployment: the cluster, the network boundary,
│         the stateful services, and how identity and secrets reach them
│
├── 08  The capability catalogue         the reference. What the platform does,
│     └── organised by capability area, each with the operation that reaches it
│
├── 09  The governance architecture      the auditor's part
│     └── two planes, envelopes, clearance, the decision gradient, trust
│         chains and postures, the audit spine, containment and refusal
│
├── 10  The organisation structure       the designer's part
│     └── D/T/R, addressing, roles and intent, trust chains, role agents,
│         re-orgs, bridges and workspaces
│
└── 11  The deployment pack              the operator's working set
      └── provisioning, the configuration reference, the runtime's node
          catalogue, releasing and rolling back, operating, verifying
```

## How claims in this handbook are kept true

Every load-bearing claim names something **you can reach from what you were
given**: an HTTP operation this client performs, or a symbol this package
exports. Both are checkable, by you, on your own machine:

```
python -m aegis_sdk.handbook.check
```

That command re-resolves every anchor against your installed build and fails
naming any that no longer resolves. It also fails on a broken cross-reference
between chapters, so a link in this book either goes somewhere or the check says
so. Because every anchor names something you hold, the check runs on your own
machine rather than ours — the book's claims are verifiable by its reader, not
only by its author.

## What this book covers

This book is written for the surface you were given: the deployment, the client
that drives it, and the console that shows it. Every chapter is actionable from
there — you are never asked to open a file you do not have.

**Part 06 covers the platform's architecture, and that is not a contradiction**,
because _architecture_ is a word that usually means the inside. Part 06 describes
the split between the Trust Plane and the Execution Plane, the governance objects
and how they relate, and where enforcement happens — and every claim it makes
rests on an operation you can call or a symbol you can import. It gives you the
shape of the system you are designing against, in terms you can verify yourself.

## Who is accountable

The organisation deploying an agent keeps the accountability for what that agent
does. It cannot be delegated, and no amount of autonomy transfers it. What this
platform provides is the **proof** — the bounded mandate, the tamper-evident
audit trail, the fail-closed gate, the attestable lineage — that lets that
organisation show an auditor how it discharged the accountability it already had.

You keep the accountability. This gives you the evidence.
