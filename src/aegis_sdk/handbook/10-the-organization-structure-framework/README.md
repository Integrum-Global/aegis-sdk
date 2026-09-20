# Part 10 — The organisation structure framework

**Audience: the architect designing the organisation their agents will live in.**
This part is PACT's organisational architecture as Aegis implements it — the
grammar that constrains the structure, the addressing scheme derived from it, and
the five things that resolve through it. Aegis is Integrum's commercial
implementation of PACT, one of four open standards published by the Terrene
Foundation under CC BY 4.0.

It assumes [06.3](../06-architecture/03-the-governed-organization.md), which names
the objects and says what each one constrains. This part answers the next
question: **given those objects, how do you describe _your_ organisation so the
governance comes out the way you meant it?**

## The chapters

| #    | Chapter                                                                 | You leave able to                                                                  |
| ---- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 10.1 | [The organisation is the system](01-the-organization-is-the-system.md)  | Say what a structural decision costs, and stop treating the chart as metadata      |
| 10.2 | [The D/T/R grammar](02-the-d-t-r-grammar.md)                            | Build a structure the platform will accept, and know why each refusal is a saving  |
| 10.3 | [Addressing](03-addressing.md)                                          | Read an address, compute its algebra in your own code, and key on the right field  |
| 10.4 | [Roles, authority and intent](04-roles-authority-and-intent.md)         | Fill the fields that actually decide behaviour, and stop using authority as a gate |
| 10.5 | [Trust chains and delegation](05-trust-chains-and-delegation.md)        | Trace authority to a person, and withdraw it completely when you need to           |
| 10.6 | [Role agents](06-role-agents.md)                                        | Provision agents by describing positions, and set autonomy through the right lever |
| 10.7 | [Re-orgs, bridges and workspaces](07-re-orgs-bridges-and-workspaces.md) | Restructure without detaching governance, and cross a boundary deliberately        |

## How the chapters relate

```text
                    10.1 ── THE PREMISE
        the chart IS the addressing scheme of the system
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
┌─ THE STRUCTURE ─────────┐   ┌─ WHAT HANGS OFF IT ──────────────┐
│                         │   │                                  │
│  10.2  the grammar      │   │  10.4  roles — intent, authority │
│        what may attach  │   │  10.5  trust — derived lineage   │
│        to what          │   │  10.6  agents — the position,    │
│                         │   │        acting                    │
│  10.3  addressing       │   │                                  │
│        the string that  │   │  Each of these resolves THROUGH  │
│        encodes both     │   │  the structure on the left.      │
│        relations        │   │                                  │
└───────────┬─────────────┘   └────────────────┬─────────────────┘
            │                                  │
            └────────────────┬─────────────────┘
                             ▼
              10.7 ── THE STRUCTURE IN MOTION
      moving it · crossing it · working beside it · the tenant
                          boundary
```

Read it as: 10.1 argues the premise, 10.2 and 10.3 are the structure itself, 10.4
through 10.6 are what the structure produces, and 10.7 is what happens once the
organisation starts changing — which it will, before you finish provisioning it.

Three things follow from that shape.

**10.2 and 10.3 are one idea in two forms.** The grammar says a container attaches
through its head role; the address is that rule rendered as a string. Reading
either alone leaves the other looking arbitrary.

**10.4 through 10.6 run in one direction.** A role is described, its agent is
derived from the description, and its authority is derived from its reporting
edge. Nothing in that chain is configured independently, which is why a
misbehaving agent is nearly always a role with an empty field.

**10.7 is not an appendix.** Every structure gets restructured, and the cascade a
move triggers is the best test of whether the structure was described well. Read
it before you provision, not after.

## Where this part sits relative to the others

Part 02 is the working reference for standing an organisation up — the calls, in
order, with the gotchas. Part 06 is the system-level picture: the planes, the
objects, the request path. This part is neither. It is the **design framework**:
the constraints that make a structure legal, the derivations that make it
governable, and the failure modes that make a plausible structure the wrong one.

The practical test is the question you are asking. _"How do I create a unit and
its head role?"_ is part 02. _"Which of these objects carries authority and which
is only context?"_ is [06.3](../06-architecture/03-the-governed-organization.md).
_"Should this group be a team unit in the tree, or a flat Team beside it — and what do I lose
either way?"_ is part
10, and the answer changes what you can enforce for the lifetime of the
deployment.

Two neighbouring parts sit either side of this one.
[Part 09](../09-the-governance-architecture/README.md) is the **governance argument** —
this part says what a bound attaches to and how it is derived from the structure; part
09 says how bounds compose into a decision and what an auditor can be shown.
[Part 08](../08-the-capability-catalogue/README.md) is the **inventory**: when you need
the full set of organisational operations rather than the design reasoning behind them,
[08.2](../08-the-capability-catalogue/02-organization-and-identity.md) enumerates it.

One more routing note, because it is the question most often asked at the wrong
address. _"Why did this agent get refused?"_ is a request-path question — part 06
carries the layers and part 04 the error taxonomy. But _"why is this agent's bound
narrower than the envelope I wrote?"_ is a structure question, and it has a single
answer: some ancestor on the reporting chain contributes a tighter bound.
`api:POST /api/v1/governance/explain-envelope` returns that composition directly,
and [10.3](03-addressing.md) is where to read about it.

## Two ideas this part keeps returning to

**Two relations, one structure.** A role is contained by exactly one unit and
reports to at most one role, and those are independent facts. Containment carries
classification, posture ceilings and knowledge boundaries. Reporting carries
envelopes and trust lineage. The address encodes both, which is why one string
answers both kinds of question — and why assuming one relation implies the other
is the most expensive mistake available here.

**The most restrictive bound wins, everywhere.** Envelopes intersect down the
reporting chain and can never widen. Posture ceilings cascade as a minimum. A
bridge crossing takes the tightest posture of the three parties. Workspace
admission is a floor the joiner must clear. There is no path through this model
along which a bound gets wider — so a design that needs one is a design that needs
a different structure, not an exception.

---

_Next: [10.1 — The organisation is the system](01-the-organization-is-the-system.md)_
