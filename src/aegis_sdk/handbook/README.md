# The Aegis Architect and Operator Handbook

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

| #      | Part                                                                   | Read it when                                                                                  |
| ------ | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **01** | [Orientation](01-orientation/)                                         | First. What you were given, how governance actually works here, and your first working session |
| **02** | [Working through the harness](02-working-through-the-harness/)         | The spine. Standing up an organisation, bounding it, running work through it, and evidencing it |
| **03** | [Extending the platform](03-extending-the-platform/)                   | You are adding a capability — a tool, an agent, a skill, a pipeline                            |
| **04** | [The API surface](04-the-api-surface/)                                 | You are calling Aegis over HTTP directly, debugging an authorization failure, or asking what the client does with errors, credentials, pages, load and streams |
| **05** | [The web console](05-the-web-console/)                                 | You want to know what a screen shows, or you are the human answering a held decision           |
| **06** | [Architecture](06-architecture/)                                       | The system-level picture. The plane split, the governance objects, where enforcement happens, and where your integration attaches |
| **07** | [Deployment architecture](07-deployment-architecture/)                 | You are deploying the platform, sizing it, or asking where its boundaries actually fall |

Read **01** in order. After that, **02** is the working reference you will return
to; **03**, **04**, **05**, **06** and **07** are consulted rather than read through.

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
└── 07  Deployment architecture          consulted from any part above
      └── the reference deployment: the cluster, the network boundary,
          the stateful services, and how identity and secrets reach them
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
so.

**Be precise about what a green run means, because the limit is real.** It proves
every named surface still exists in the build you have. It does **not** prove the
server behaves as the prose says — an operation can exist and enforce nothing.
The check cannot see a control that silently stopped enforcing, and it cannot see
fail-open at all. The route table it checks against is *this client's belief*
about the API, extracted from the calls this package makes; if the client is
wrong about a path, the anchor is wrong in the same direction and nothing here
notices.

This is a deliberate trade and it is worth naming. An earlier edition anchored
claims on coordinates in the platform's own source, which could point at the line
that enforces a rule — strictly stronger evidence, and unusable here, because
that source is not part of what you were given. A citation you cannot open is not
evidence to you; it is an assertion with a decoration. What you have instead is
weaker evidence you can actually check yourself.

## Three markers you will see, and what each one means

This book distinguishes what it observed from what it inferred, because the
difference changes what you should do about it.

- **UNVERIFIED** — a claim that could not be settled from what is reachable here.
  Treat it as a lead, not a fact. It is written down rather than dropped because
  a silent omission is indistinguishable from a claim nobody thought to make.
- **design intent, not observable** — an explanation of *why* something behaves
  as it does. A behaviour can be observed; a designer's reason cannot. These are
  the book's own reading, offered because knowing the intent usually tells you
  what else will be true — but labelled, so you never mistake the reading for the
  measurement.
- **open defect** — behaviour that is currently wrong, described with the symptom
  you will recognise it by. A handbook that describes the intended design as if
  it were the shipped design is worse than no handbook.

## What is not in this book

The parts covering the platform's own construction — its codebase, its build, its
internal test suite — are not here. They describe modifying the platform source,
which is not part of what you were given, and nothing in them would be actionable
from here. This is a reachability boundary, not a secrecy one: a chapter telling
you to open a file you do not have is answering a question you cannot act on.

**Part 06 does not contradict that boundary, and the distinction is worth
drawing**, because *architecture* is a word that usually means the inside. Part
06 does describe the platform's internals — the split between its Trust Plane and
its Execution Plane, the governance objects and how they relate, where
enforcement happens — but every claim it makes about them rests on an operation
you can call or a symbol you can import, never on a file you cannot open. The
source, the build and the internal test suite are still not in this book. What is
in it is the shape of the system you are designing against, with the limits of an
outside read stated rather than glossed.

## Who is accountable

The organisation deploying an agent keeps the accountability for what that agent
does. It cannot be delegated, and no amount of autonomy transfers it. What this
platform provides is the **proof** — the bounded mandate, the tamper-evident
audit trail, the fail-closed gate, the attestable lineage — that lets that
organisation show an auditor how it discharged the accountability it already had.

You keep the accountability. This gives you the evidence.
