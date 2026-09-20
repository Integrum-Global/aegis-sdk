# 10.2 — The D/T/R grammar

The organisation is one tree with three node types, and there is exactly one
structural rule governing how they attach. This chapter is that rule: what the
three types are, what the rule says, why it is enforced at write time rather than
checked later, and what the structures it forbids would have cost you.

The rule is worth stating before anything else, because everything in the rest of
this part is downstream of it:

> **A containment node — a Department or a Team — must be immediately followed by
> exactly one Role, its head, before any further Department, Team or Role can
> attach beneath it.**

The one-sentence rationale is the one to carry: **containers do not make
decisions, people do.** Every department has a head. Every team unit has a lead. Every
budget, every delegation and every escalation terminates at a person who is
accountable for it. The grammar is that principle made structural — it is not
possible to express an organisation on this platform in which authority passes
through a container without passing through a person.

**The single idea to carry out of this chapter: the grammar is not a style guide,
it is the precondition for your organisation being addressable at all.**

## The three node types

| type           | symbol | what it is                                        | persistence                                 |
| -------------- | ------ | ------------------------------------------------- | ------------------------------------------- |
| **Department** | `D`    | a knowledge container and organisational division | persistent                                  |
| **Team**       | `T`    | a knowledge container and working group           | fluid; may be temporary                     |
| **Role**       | `R`    | a person's position and accountability anchor     | the position persists; the occupant changes |

`D` and `T` are both **units**, distinguished by the `unit_type` field, whose
only two values are `department` and `team`. They are structurally
interchangeable in the grammar — everything the rule says about `D` it says about
`T` — and they differ in intent and in one placement restriction covered below.
Both are created through `api:POST /api/v1/organization-units` and read through
`api:GET /api/v1/organization-units/{id}`; `sdk:aegis_sdk.OrganizationUnitsModule`
is the typed path.

> ⛔ **"Team" names two unrelated things on this platform, and only one of them
> is in this tree.** A **team unit** is the `T` node above: a container with an
> address, a head role, a classification default and a posture ceiling. A **Team**
> — the flat entity at `api:GET /api/v1/teams`, with its own identifier and a
> membership list — is not in the D/T/R tree at all, has no address, no head role
> and no boundary semantics. They are separate constructs that share a word.
> **This part says "team unit" whenever it means the `T` node**, and names the
> other one explicitly. [10.7](07-re-orgs-bridges-and-workspaces.md) covers when
> you want which; the short version is that only the team unit fences anything.

`R` is created through `api:POST /api/v1/organization-roles`, with the fuller
surface on `sdk:aegis_sdk.modules.RolesModule`.

⚠ **`unit_type` has exactly two values, and there is no `executive`.** The root of
the organisation is an ordinary department — conventionally the CEO Office,
addressed `D1`. An earlier generation of this model had a third type for the top
of the chart; it is gone, and the root department replaces it. A structure that
tries to express "this is the executive layer" as a type is expressing it in the
wrong place: seniority is a property of roles
([10.4](04-roles-authority-and-intent.md)), not a kind of container.

> ⛔ **`sdk:aegis_sdk.UnitType` is not the organisational unit type.** That enum
> classifies a _work_ unit — a different domain that happens to share the word.
> The organisational unit type is the string `department` or `team` on an
> organisation unit. Two meanings, one word, and the enum name points at the one
> you probably did not mean.

## The rule, stated as a grammar

Eight attachment sequences are legal and four are not. The four illegal ones are
exactly the cases where a container attaches directly to a container.

```text
VALID                                    INVALID
  D-R    a department and its head         D-D   department under department
  D-R-D  a department beneath that head    D-T   team unit under department
  D-R-T  a team unit beneath that head     T-T   team unit under team unit
  D-R-R  another role at that level        T-D   department under team unit
  T-R    a team unit and its lead
  T-R-T  a team unit beneath that lead
  T-R-D  a department beneath that lead
  T-R-R  another role at that level

Read the valid column as one pattern: every container is followed by its
head role, and everything else attaches to the HEAD ROLE — not to the
container. The invalid column is the same pattern with the person removed.
```

Read it as: `R` is unrestricted in what may follow it — any combination of `D`,
`T` and `R`. `D` and `T` are restricted to exactly one thing: their head role.
The asymmetry is the whole rule.

Two corollaries fall straight out and are worth having explicitly.

**Exactly one primary role per unit.** The head role is the one carrying
`is_primary_for_unit = true`. A unit with two would have two candidate
attachment points for its children and an ambiguous address; a unit with none
cannot attach children at all. The platform refuses both: a second primary on a
unit that already has one is rejected, and so is unsetting the only primary on a
unit that would be left headless.

**A team unit may not be the organisation's root.** `D` and `T` are otherwise
interchangeable, and this is the exception. The root of the tree is a department;
a team unit with no parent is refused. A team unit is a working group inside an
organisation, and an organisation whose top node is a working group has no
durable container for the classification defaults and posture ceilings that
cascade from the root.

## Enforcement is at write time, and it is a refusal

The grammar is checked when you write, not when you compile. Four things are
refused, and each refusal names the node and what to do about it.

| you attempt                                             | refused because                                        |
| ------------------------------------------------------- | ------------------------------------------------------ |
| a `unit_type` other than `department` or `team`         | the grammar has two container types                    |
| a team unit with no parent                                  | the organisation's root is a department                |
| any unit beneath a **team unit** that has no head role       | the child would have no attachment point               |
| a unit beneath any parent that has no primary role      | the `D/T-R` invariant — create the parent's head first |
| a second primary role on a unit that already has one    | the attachment point must be unambiguous               |
| unsetting the only primary role on a unit with children | it would leave the subtree unattachable                |

The last two are the ones that catch provisioning scripts. A script that creates
units in one pass and roles in a second will hit the head-role refusal on its very
first child unit, which is the good outcome — the refusal arrives at the write
that would have produced the broken structure, not three steps later.

**Creating a unit auto-creates its head role**, which is what makes the grammar
liveable rather than tedious. You create the department; the platform creates the
role that heads it, marks it primary, and leaves it vacant with its vacancy
recorded as a structural placeholder. The seat exists, it is addressable, and its
agent is active from that moment ([10.6](06-role-agents.md)) — it simply has no
human in it yet.

⚠ **The auto-created head role arrives with no reporting edge.** It is contained
correctly and it is attached to nothing. That is the one thing the grammar does
_not_ do for you, and it is the most common structural defect in a
freshly-provisioned organisation: a set of units whose subtrees are each a
separate authority structure, unattached from each other and from the top. No call
fails and nothing warns you. Set `reports_to_role_id` on every head role you
create, and verify with
`api:GET /api/v1/organization-roles/{id}/reporting-chain` — a chain that comes
back with a single entry is a root, and on a role you meant to nest, that is the
finding.

```python
# Create the container; its head role is created with it, vacant and primary.
unit = await client.organization_units.create(
    name="Treasury",
    unit_type="department",
    parent_unit_id=finance_unit_id,
    default_classification="confidential",
)

# Attach the head to the reporting chain — the platform does not infer this.
await client.roles.update(
    role_id=unit["head_role"]["id"],
    reports_to_role_id=cfo_role_id,
    authority_level=3,
)
```

## What the forbidden structures would have cost

`D-D` looks harmless. It is the shape every filing system has, and the instinct
to reach for it is strong — you want a "Finance" container with "Treasury" and
"Payables" inside it and no particular person in between. The grammar refuses it,
and the three things that refusal buys are each load-bearing.

**Authority would have no anchor.** An envelope is defined by a role _for_ a role,
and a trust chain runs from an agent _to_ an agent
([10.5](05-trust-chains-and-delegation.md)). Under `D-D`, a delegation crossing
from Finance to Treasury would have no role at the boundary to originate from —
so either the platform invents one, or authority crosses the boundary unattributed.
Both are worse than a refusal.

**Escalation would have a hole in it.** When a decision exceeds a delegate's
bounds it escalates to the superior. Under `D-D` the superior of everything in
Treasury is a _container_, which cannot approve anything, so escalation would have
to skip a level — silently widening who sees the decision.

**The address would be ambiguous.** `D1-D1` cannot be parsed as a position in the
authority graph, because the graph is defined by the role segments. An
organisation that could produce such an address could not have its governance
computed ([10.3](03-addressing.md)), and the failure would land at compile time,
far from the write that caused it.

> ⛔ **The refusal is the cheap outcome; the expensive one is the structure that
> gets built around it.** A team unit that hits the headless-parent refusal and
> "resolves" it by re-parenting the child somewhere it does fit has not satisfied
> the grammar, it has moved the work under an authority that was never meant to
> hold it — and every envelope and trust chain beneath will compose from that
> wrong ancestor, correctly, forever. When a write is refused, create the missing
> head role. Do not find a different parent.

## Three role flags that change what a role is for

Beyond `is_primary_for_unit`, two flags alter a role's participation in the
structure. Neither is cosmetic.

| flag                  | what it marks                            | structural effect                                                      |
| --------------------- | ---------------------------------------- | ---------------------------------------------------------------------- |
| `is_primary_for_unit` | the unit's head role                     | the attachment point for the unit's children; exactly one per unit     |
| `is_external`         | a board member, advisor, outside counsel | governance participation only; receives no operational delegate agent  |
| `is_coordinator`      | a cross-team coordinator                 | a **non-primary** role bound to a bridge-only, zero-financial envelope |

`is_external` is how a board is expressed. A board is an **L0 governance root** —
it sits above the organisation's root department, its member roles carry
`is_external = true`, and it is the signing authority for the organisation-level
envelope. External roles can hold governance agents that approve, observe and
audit; they do not get operational delegate agents, and the platform enforces
that rather than trusting you to remember it. **The failure mode a flag prevents
here is a board seat that can execute work** — which reads, in every listing, like
an ordinary senior role.

`is_coordinator` is the construct for a person who works across team units without
reporting into each of them. It is deliberately non-primary: a coordinator is not
the head of anything, and making one primary would put a cross-cutting role at a
structural attachment point. Its envelope is bridge-scoped with no financial
dimension — it can traverse, it cannot spend.

## Department or team unit — choosing between the two containers

The grammar treats `D` and `T` identically, so the choice between them is a
modelling decision rather than a structural one. Three differences guide it.

| axis            | Department                                     | Team unit                                        |
| --------------- | ---------------------------------------------- | ------------------------------------------------ |
| **persistence** | durable — outlives the work it was created for | fluid — may be created for an effort and retired |
| **head role**   | "Head of …"                                    | "Lead of …"                                      |
| **placement**   | may be the organisation's root                 | may **not** be the root                          |

Both are knowledge boundaries, both carry a classification default and a posture
ceiling, and both cascade those to what they contain. **So the choice is about
lifespan and about how the organisation talks about itself**, not about what the
container enforces.

The practical rule: reach for a department when the boundary should outlive its
current membership and its current purpose, and for a team unit when it should not. A
"Q3 Migration" team unit that is archived when the migration completes is the
construct behaving as intended; a "Q3 Migration" department is a boundary that
will still be there in three years, still carrying a classification default,
still cascading a ceiling, with nobody remembering why.

⚠ **Neither is the construct for "these people work together but nothing is
fenced".** Both fence. [10.7](07-re-orgs-bridges-and-workspaces.md) covers the
constructs that group without fencing — and it also covers the vocabulary
collision waiting here, because a **team unit** in the grammar and a **team** on
the teams surface are two different things sharing one word.

## Provisioning a structure without fighting the grammar

A script that creates all the units first and all the roles second will be refused
on its first child unit, because the parent has no head role yet. The order that
works is depth-first, and each level completes before the next begins.

```text
THE ORDER THAT SATISFIES THE GRAMMAR

  for each unit, top-down:
      1. create the unit              -> head role auto-created, vacant, primary
      2. set the head role's intent   -> title, authority_level, job_description
      3. attach the head role         -> reports_to_role_id = parent's head role
      4. create any non-primary roles in this unit
      5. recurse into this unit's children

  Step 3 is the one with no automatic counterpart. Steps 1 and 2 concern
  CONTAINMENT and the platform helps with both; step 3 concerns REPORTING
  and the platform will not infer it from the containment you just built.
```

Read it as: the grammar guarantees you a head role, and guarantees it is in the
right container. It guarantees nothing about who that head answers to, because
that is the other relation ([10.1](01-the-organization-is-the-system.md)) and it
is genuinely a separate decision — a role contained in one unit and reporting into
another is a legitimate shape the platform will not second-guess.

For a structure you already hold, `api:POST /api/v1/organization-builder/import-yaml`
takes the whole thing in one pass and does the ordering for you, and
`api:POST /api/v1/organization-builder/validate` will tell you whether it is legal
before anything lands.

## Checking a structure you did not build

Three reads answer three different questions, and they are not substitutes for
each other.

| call                                               | answers                                                                    |
| -------------------------------------------------- | -------------------------------------------------------------------------- |
| `api:GET /api/v1/organization-units/validate`      | is the **unit hierarchy** structurally sound — orphans, cycles?            |
| `api:POST /api/v1/organization-builder/validate`   | is a **proposed** structure legal before it is built?                      |
| `api:GET /api/v1/governance/probe-corrupted-roles` | which **roles** violate the grammar — no address, head not marked primary? |

`api:GET /api/v1/organization-units/{id}/summary` reports `has_primary_role`,
which tells you a head exists. **It does not tell you the head is attached** —
that is the reporting-chain read above, and conflating the two is how a
disconnected subtree passes a review. A unit can have a head role, satisfy every
grammar check, and sit in its own authority island.

For the shape of what you have, `api:GET /api/v1/organization-units/tree` returns
the whole containment tree, `api:GET /api/v1/organization-units/roots` the top
nodes, and `api:GET /api/v1/admin/roles/hierarchy` the reporting picture as a
whole.

```bash
# Before a deploy: does the structure hold together at all?
curl -s "$AEGIS/api/v1/organization-units/validate"        # orphans + circular refs
curl -s "$AEGIS/api/v1/governance/probe-corrupted-roles"   # grammar violations on roles

# After provisioning: is every head role actually attached?
curl -s "$AEGIS/api/v1/organization-roles/$ROLE/reporting-chain"   # length 1 == a root
```

## The grammar, once

| question                                 | answer                                                                |
| ---------------------------------------- | --------------------------------------------------------------------- |
| What may follow a `D` or a `T`?          | Exactly one `R` — its head role. Nothing else.                        |
| What may follow an `R`?                  | Any combination of `D`, `T` and `R`.                                  |
| How many primary roles per unit?         | Exactly one — enforced on create, on update, and on move.             |
| Can a team unit be the root?                  | No. The root is a department.                                         |
| Where does a child unit attach?          | To its parent's **head role**, never to the parent container.         |
| Who creates the head role?               | The platform, when the unit is created — vacant, primary, and active. |
| What does the platform _not_ do for you? | Attach that head role to a reporting chain.                           |
| When is the grammar checked?             | At write time. The refusal arrives at the write that would break it.  |

---

_Next: [10.3 — Addressing](03-addressing.md)_
