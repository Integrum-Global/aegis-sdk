# Part 09 — The governance architecture

<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->

**Audience: the architect who has to satisfy an auditor.** Parts 02 to 05 tell
you how to operate the platform. Part 06 tells you what the platform is. This
part tells you what the platform _governs_, end to end — the complete control
surface, in one argument, in the order the controls actually compose.

It is written for the conversation you will eventually have with someone who
does not care how the system is built and cares enormously whether it can be
shown to have behaved. That person will ask four things: what bounded this
agent, who decided it could act, what was recorded, and how do I know the
record is intact. This part answers all four, and names the object that answers
each.

One idea governs the whole part, and it is worth carrying from the first page:
**governance here is not a layer wrapped around a capability — it is the same
object seen from the other side.** A role envelope is simultaneously what a
delegate _may_ do and what it _can_ do. A clearance is simultaneously what a
role knows and what it may not. A trust chain is simultaneously the authority
an agent holds and the ceiling on it. Nothing in this part is a restriction
bolted onto something that would otherwise be unbounded, and designs that treat
it that way end up with two systems that disagree.

## The chapters

| #    | Chapter                                                                          | You leave able to                                                                             |
| ---- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 09.1 | [The two planes](01-the-two-planes.md)                                           | Say which plane a decision belongs to, and why the split is the product rather than a feature |
| 09.2 | [Envelopes and constraints](02-envelopes-and-constraints.md)                     | Design a bound that composes correctly down a hierarchy, and know when it starts enforcing    |
| 09.3 | [Clearance and classification](03-clearance-and-classification.md)               | Model who sees what, and predict which of three checks refused a read                         |
| 09.4 | [The decision gradient](04-the-decision-gradient.md)                             | Place an action in the right zone, and design the human step that resolves it                 |
| 09.5 | [Trust chains and postures](05-trust-chains-and-postures.md)                     | Establish, move, suspend and withdraw an agent's standing, and evidence each                  |
| 09.6 | [The audit spine and evidence](06-the-audit-spine-and-evidence.md)               | Produce the artefact an auditor asks for, and show that it has not been altered               |
| 09.7 | [Containment and explainable refusal](07-containment-and-explainable-refusal.md) | Keep classified material inside a container that can enforce it, and read a refusal correctly |

## How the seven compose

```
THE GOVERNANCE STACK — read top to bottom; each layer consumes the one above

┌─ 09.1 · THE TWO PLANES ───────────────────────────────────────────────────┐
│  Trust Plane — may this happen?      Execution Plane — make it happen     │
│  Everything below is an object on one plane or the other.                 │
└───────────────────────────┬───────────────────────────────────────────────┘
                            │
     ┌──────────────────────┴──────────────────────┐
     │                                             │
     ▼                                             ▼
┌─ 09.2 · WHAT MAY BE DONE ────────┐   ┌─ 09.3 · WHAT MAY BE SEEN ──────────┐
│  five constraint dimensions      │   │  five classification levels        │
│  role envelope · task envelope   │   │  role clearance · compartments     │
│  composition is an INTERSECTION  │   │  admission is a RANK comparison    │
└──────────────┬───────────────────┘   └──────────────┬─────────────────────┘
               │                                      │
               └──────────────────┬───────────────────┘
                                  ▼
               ┌─ 09.4 · HOW THE ANSWER IS DELIVERED ──────────────────┐
               │  auto_approved · flagged · held · blocked             │
               │  four zones, not a boolean                            │
               └──────────────────────┬───────────────────────────────-┘
                                      ▼
               ┌─ 09.5 · WHO IS ASKING, AND ON WHOSE AUTHORITY ───────┐
               │  authority → chain → posture → decision              │
               │  the standing behind every request above             │
               └──────────────────────┬───────────────────────────────┘
                                      ▼
               ┌─ 09.6 · WHAT SURVIVES IT ────────────────────────────┐
               │  two logs · lineage trace · hash-chain verification  │
               │  compliance frameworks and export                    │
               └──────────────────────┬───────────────────────────────┘
                                      ▼
               ┌─ 09.7 · WHERE IT ALL LIVES ──────────────────────────┐
               │  containers that carry a mark and enforce it         │
               │  refusals that name the rule that refused            │
               └──────────────────────────────────────────────────────┘
```

Read it as: 09.1 establishes the two halves. 09.2 and 09.3 are the two
independent bounds — _what may be done_ and _what may be seen_ — and they are
genuinely separate axes that people collapse constantly. 09.4 is how a verdict
reaches a human. 09.5 is the standing every request in the three layers above
rests on. 09.6 is what is left afterwards. 09.7 is the container discipline that
makes all six survivable when material of different sensitivities sits side by
side.

## Where this part sits relative to the others

Part 02 is the working reference — how to create an envelope, grant a clearance,
establish a chain. Part 06 is the architecture — what the platform is and how a
request moves through it. This part is neither. It is the **governance argument**:
why these controls and not others, how they compose, which one refuses in a given
case, and what you can show afterwards.

The practical test is the question you are asking.

_"How do I activate a role envelope?"_ is [02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
— a procedure, with the call.

_"My delegate has an active envelope and still cannot read the document. Which
control refused?"_ is 09.3, which carries the three-way check and the order to
test it in.

_"My auditor wants to see that an agent's autonomy was earned rather than
assigned. What do I give them?"_ is 09.5 and 09.6 together — the posture history
and evidence surfaces, then the export that makes them portable.

If you read only one chapter, read [09.1](01-the-two-planes.md). Every other
chapter is a statement about one plane or the other, and a control read without
knowing which plane it sits on is the single most common way a governance design
ends up looking complete and enforcing nothing.

## Two things this part keeps returning to

**Declared is not enforced.** Every governance object in Aegis has a state in
which it exists and a state in which it is consulted, and they are different
states with different names. An envelope in `draft`. A clearance awaiting
vetting. A policy authored but not compiled. Each appears in every listing you
will read and changes no decision. This is not a defect in the model — it is
what makes review possible — but a provisioning script that creates the objects
and never advances them produces an organisation that looks fully governed and
is not. The state field is the only thing that distinguishes the two, so assert
on it.

**The organisation stays accountable; Aegis supplies the proof.** Nothing in
this part transfers responsibility for what your agents do. What it gives you is
the ability to _show_ what bounded them, who decided, and what happened —
bounded mandates, tamper-evident records, fail-closed permissions, attestable
lineage. That is the product: governance you can prove to an auditor, against an
external published standard, rather than autonomy you have branded as safe.

Aegis is Integrum's commercial implementation of four open standards published
by the Terrene Foundation under CC BY 4.0 — **CARE** (the governance
philosophy and its two planes), **PACT** (the organisational architecture and
its envelopes), **EATP** (the trust protocol and its classification ladder) and
**CO** (the orchestration methodology). The vocabulary in this part is theirs.
Where a name looks like a platform invention, it is almost always a term of art
from one of the four, and reading the specification will tell you more about the
intent than any amount of API inspection.

---

_Next: [09.1 — The two planes](01-the-two-planes.md)_
