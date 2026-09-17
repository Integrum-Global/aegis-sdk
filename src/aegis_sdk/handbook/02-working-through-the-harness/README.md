# Part 02 — Working through the harness

This is the spine of the book. Everything an architect designs and an operator
runs is here, in the order you actually do it: describe the organisation, bound
it, wire trust through it, put work into it, and pull evidence out of it.

Each chapter shows the **harness path first** — the SDK call you write, run and
review — and then names the **console equivalent** where one exists, so you can
find the same thing on a screen when a human needs to look at it.

| #    | Chapter                                                                          | You leave able to                                                          |
| ---- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 02.1 | [The two surfaces](01-the-two-surfaces.md)                                        | Choose the right surface for a task, and know why the choice matters       |
| 02.2 | [Standing up an organisation](02-standing-up-an-organization.md)                  | Provision a tenant, units, roles and teams from code                       |
| 02.3 | [Envelopes, clearance and knowledge](03-envelopes-clearance-and-knowledge.md)     | Bound what a role's delegate may do, and control what it can see           |
| 02.4 | [Trust chains and postures](04-trust-chains-and-postures.md)                      | Establish delegated authority, move an agent's autonomy, and revoke safely |
| 02.5 | [Objectives and the work loop](05-objectives-and-the-work-loop.md)                | Put work in, watch it, and understand the states it passes through         |
| 02.6 | [Approvals, holds and evidence](06-approvals-holds-and-evidence.md)               | Answer what Aegis stops to ask, and export the record afterwards           |
| 02.7 | [Role agents, and surviving a re-org](07-role-agents-and-re-orgs.md)              | Stand up a delegate on a seat nobody occupies, and move the org chart without losing it |

## The shape of the whole thing, in one sequence

Every chapter below is a slice of this. It is worth reading once as a whole
before reading any part of it in detail, because each step constrains the next
and the constraint direction is not obvious from any single call.

```
organisation                     the tenant root
   └── unit                      a knowledge boundary, with a default classification
        ├── head role            authority level, and the unit's primary role — often VACANT, which is fine (02.7)
        ├── role                 reports_to another role; the reporting chain
        │    └── envelope        what this role's delegate may do — five dimensions
        │         └── agent      the delegate itself
        │              └── trust chain    where its authority came from
        │                   └── posture   how much of that authority it may use unsupervised
        └── knowledge            governing documents, classified, with a review lifecycle
                 objective       work you ask for
                   └── request   a work item; some need a human
                        └── approval    the human decision, recorded
```

Two properties of that tree decide most design questions, and both are easy to
get backwards:

1. **A unit is a knowledge boundary, not just a box on a chart.** Being a
   colleague of someone does not grant sight of their work. Visibility is a
   property of the unit and the clearance, not of the org chart's shape.
2. **Envelopes compose by intersection, never by union.** A delegate cannot be
   granted more than the role that defines its envelope holds. Adding a second
   envelope narrows; it does not widen. Chapter 02.3 is explicit about this
   because designs that assume otherwise fail late, at the point where someone
   expects an escalation path that cannot exist.

## Before you start: build it twice

The reason this part is harness-first rather than console-first is not aesthetic.
An organisation you can re-create from a script is one you can review before it
exists, promote from staging to production unchanged, diff when it drifts, and
rebuild after an incident. An organisation assembled by clicking is none of
those, and the difference is invisible until the day you need it.

Write your provisioning as an idempotent script from the beginning, even for a
pilot. Chapter 02.2 shows the shape.
