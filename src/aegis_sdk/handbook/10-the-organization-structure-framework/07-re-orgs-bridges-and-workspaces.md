# 10.7 — Re-orgs, bridges and workspaces

The six chapters before this one describe a structure at rest. Real organisations
are not at rest: they restructure, they need people to work across the boundaries
they just drew, and they run temporary efforts that do not fit the chart at all.
This chapter is the three mechanisms for that — moving the structure, crossing it,
and working beside it — plus the tenant boundary that contains all of them.

The through-line is worth stating up front, because it is what makes these three
one chapter rather than three appendices: **none of them weakens the structure.**
A move recomputes governance rather than detaching it. A bridge is an explicit,
authorised, bounded crossing — not a hole. A workspace groups people without
granting them anything. Every mechanism here is additive and every one of them
composes by intersection.

**The single idea to carry out: when two bounds meet, the most restrictive wins —
on every one of these paths, without exception.**

## Moving a unit is a governance event

`api:POST /api/v1/organization-units/{id}/move` re-parents a unit and everything
beneath it. It is not a chart edit, and the response's cascade summary is the
honest measure of what it touched.

```text
WHAT A MOVE CASCADES, AND WHICH PARTS ARE MANDATORY

  1  snapshot        the old parent, level and path, and every descendant

  2  re-parent       the unit and its subtree

  3  ADDRESSES       recomputed for the ORGANISATION — not patched in place,
     [MANDATORY]     because sequential numbering means a move can renumber
                     nodes outside the subtree. Failure rolls the move back.

  4  POSTURE         ceilings recomputed down the tree
     CEILINGS        [MANDATORY] — failure rolls the move back.

  5  KNOWLEDGE       every share policy touching the moved subtree is
     SHARE POLICIES  re-checked for ancestry. Any that no longer holds is
     [MANDATORY]     SUSPENDED. If the re-check itself fails, ALL policies
                     touching the subtree are suspended pending review —
                     and if even that fails, the move is rolled back.

  6  bridges         role-anchored bridges survive; their denormalised unit
                     references are re-derived

  7  trust chains    chains whose structural premise changed are revoked and
                     replacements created — scoped to the moved subtree, so a
                     concurrent change elsewhere is not swept up

  8  audit           the move is recorded
```

Read it as: steps 3, 4 and 5 are load-bearing enough that failing them undoes the
move. Step 5 is the strictest, and the reasoning is explicit — **a stale share
policy grants knowledge access from a unit the role is no longer part of**, which
is a live exposure rather than an inconsistency. When the platform cannot
determine which policies still hold, it suspends all of them rather than guessing.

⛔ **Read the cascade summary before treating a move as tidying up the chart.**
Addresses change, and every address beneath the moved node changes with them
([10.3](03-addressing.md)). Anything you cached by address is now stale. Trust
chains under the moved subtree are torn down and rebuilt, which means the
delegation an agent held a moment ago has a new identity. **Nothing about the
chart looks different afterwards, which is exactly why the summary is the thing to
read.**

Re-parenting a _role_ — changing `reports_to_role_id` — is the other half of
restructuring, and it carries its own check: the new reporting edge is validated
for envelope tightening before it is accepted. A move that would place a role
under a parent whose envelope does not contain the role's own is refused, because
accepting it would express a widening, and widening is not something the model can
say ([10.4](04-roles-authority-and-intent.md)).

## Bridges — crossing the structure, deliberately

A bridge is a governed edge between two parts of the organisation that do not have
a reporting relationship. It is how Legal advises Engineering, how an incident
incident-response effort reaches across three departments, how a committee spanning four units does
its work.

> ⛔ **A bridge is not a reporting edge and never becomes one.** Trust chains
> minted by a bridge carry `source_bridge_id` and are marked as bridge-originated;
> they are not part of the reporting-derived delegation graph
> ([10.5](05-trust-chains-and-delegation.md)). A bridge lets authority _cross_; it
> does not restructure who reports to whom, and it does not survive as a
> relationship when the bridge is revoked.

Three kinds exist, and they are three separate constructs rather than one with a
duration field.

| kind         | shape                                         | duration                                                | approval                                                            | mints trust chains |
| ------------ | --------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------- | ------------------ |
| **standing** | **role ↔ role**, two parties                  | permanent, with optional review and expiry              | **two distinct humans**, each currently occupying their anchor role | **yes**            |
| **scoped**   | N units, tied to a workspace and an objective | bounded window; may auto-expire on objective completion | approved as a unit                                                  | no                 |
| **ad-hoc**   | unit → unit, directional                      | minutes, from activation                                | the target unit approves the initiator's request                    | no                 |

**Standing bridges anchor on roles, not units — and that is what makes them
survive a re-org.** A bridge between the Head of Legal and the Head of Platform
is a relationship between two positions; moving either position's unit re-derives
the bridge's bookkeeping and leaves the bridge itself intact. A bridge anchored on
containers would break on every restructure.

Standing bridges are created with `api:POST /api/v1/standing-bridges`, authorised
with `api:POST /api/v1/standing-bridges/{id}/authorize`, and brought into force
with `api:POST /api/v1/standing-bridges/{id}/activate`.
`api:POST /api/v1/standing-bridges/{id}/check-interaction` asks whether a
specific interaction would be permitted, and `/{id}/review`, `/{id}/suspend` and
`/{id}/revoke` are the lifecycle.
`api:GET /api/v1/standing-bridges/for-unit/{id}` lists what touches a unit and
`api:GET /api/v1/standing-bridges/overdue` finds the ones past review.
`sdk:aegis_sdk.modules.StandingBridgesModule` is the typed surface.

⛔ **Dual authorisation means two different people, each of whom currently holds
the anchor role they are signing for.** All three conditions are checked at
activation: both signatures present, the two signatories distinct, and each still
occupying the position they signed as. A signature from someone who has since
moved on does not carry the bridge, and the platform re-derives occupancy rather
than trusting the stored record. **The failure mode that closes is a cross-unit
grant carrying one person's authority under two names.**

Scoped bridges are the construct for a bounded, multi-party effort:
`api:POST /api/v1/scoped-bridges`, with `/{id}/approve`, `/{id}/extend`,
`/{id}/renew`, `/{id}/complete`, `/{id}/expire` and `/{id}/cancel` as the
lifecycle, `/{id}/add-unit` to bring a unit in, and
`api:GET /api/v1/scoped-bridges/for-workspace/{id}` to find the ones attached to a
workspace. `sdk:aegis_sdk.modules.ScopedBridgesModule` wraps them.

Ad-hoc bridges are the urgent path — a request from one unit to another that the
target approves and activates, bounded to a duration in minutes.
`api:GET /api/v1/ad-hoc-bridges/pending-for/{id}` is the inbox,
`api:POST /api/v1/ad-hoc-bridges/{id}/approve`, `/{id}/reject` and
`/{id}/activate` are the decisions, and
`sdk:aegis_sdk.modules.AdHocBridgesModule` is the typed path.

### What is checked when something crosses

An interaction over a bridge passes an ordered set of checks and stops at the
first refusal, with the refusal naming the check that produced it:

| #   | check                  | asks                                                                     |
| --- | ---------------------- | ------------------------------------------------------------------------ |
| 1   | **bridge status**      | is this bridge in force at all?                                          |
| 2   | **direction**          | does the bridge permit traffic this way?                                 |
| 3   | **interaction type**   | is this interaction on the allowed list and off the prohibited one?      |
| 4   | **dual authorisation** | for a standing bridge requiring it, is it properly authorised?           |
| 5   | **participant role**   | for a scoped bridge, is the actor a participant in a permitted capacity? |
| 6   | **path access**        | is the material being reached within the bridge's shared paths?          |

And over the crossing itself, the composition rule:

```text
EFFECTIVE POSTURE AT A CROSSING
    = min( the source's posture,
           the target's posture,
           the bridge's own ceiling )
```

**That minimum is what prevents trust laundering.** Without it, an agent at a
restrictive posture could route work through a bridge into a permissive part of
the organisation and come back with an answer it was never entitled to compute.
The crossing takes the tightest of the three, so a bridge can never be a route to
more autonomy than either side already held.

A standing bridge's `knowledge_sharing_level` is `restricted`, `partial` or
`full`, and **only `partial` and `full` grant anything**. A bridge at `restricted`
is a communication channel, not a knowledge grant — and a bridge that is not
active grants nothing whatever its level says.

## Knowledge share policies — downward, and never transitive

Units are knowledge boundaries. Material crosses one by an explicit policy, never
by adjacency and never by proximity on the chart.
`api:POST /api/v1/knowledge-share-policies` creates one, with `/{id}/suspend` and
`/{id}/reactivate` as the controls and
`api:GET /api/v1/knowledge-share-policies/due-for-review` for the ones needing
attention.

Three properties govern them, and each blocks a different wrong assumption.

**Downward only.** The source unit must be an **ancestor** of the target in the
containment tree. A policy sharing sideways or upward is refused at creation.
Knowledge flows down the tree by grant; it does not flow up or across by policy.

**Never transitive.** If A shares with B and B shares with C, **C still cannot see
A's material.** Every hop is its own policy. Designs that assume otherwise promise
a capability that does not exist — in the safe direction, which is why they
survive review and surface as "why can't they see it?" months later.

**The authority floor is on the requester.** A policy's `min_authority_level`
bounds who may _receive_ under it. It does not bound who may author it, and
reading it the other way produces an authoring model the platform does not
implement.

Policies can carry conditions — a time window, a project scope, a requirement for
an active session — so a grant can be narrower than "this unit, these paths".

⚠ **A policy that explicitly denies is not the same as no policy at all, and the
difference decides whether a bridge can help.** When an access evaluation finds a
matching policy that refuses — wrong path, wrong classification, wrong type,
authority below the floor, a condition unmet — that is an explicit denial and a
bridge does not override it. When no policy matches, a bridge may legitimately
supply the access. `api:POST /api/v1/governance/explain-access` is the read that
tells you which of the two you are looking at, and it is worth reaching for
immediately: a clearance failure, a classification failure and a missing policy
all present identically from outside.

`sdk:aegis_sdk.KnowledgeModule` covers the item lifecycle and
`sdk:aegis_sdk.modules.KnowledgeGovernModule` the review and share surface.

## Workspaces — the orthogonal axis

A workspace is where work happens, and it is deliberately **not** part of the
organisational tree. It has no unit and no role. Its membership is by **user**,
so a workspace can assemble people from four departments without altering any
reporting line or containment edge — which is the whole point of it.

`api:POST /api/v1/workspaces` creates one, `api:POST /api/v1/workspaces/{id}/members`
adds a person, `api:POST /api/v1/workspaces/{id}/work-units` attaches work, and
`api:POST /api/v1/workspaces/{id}/documents` attaches material.
`api:POST /api/v1/workspaces/{id}/archive` and `/{id}/restore` are the lifecycle.
`sdk:aegis_sdk.modules.WorkspacesModule` is the typed surface.

Governance in a workspace is **classification-based**, and the two classification
fields are different quantities that are easy to conflate:

| field                     | is a                  | meaning                                                    |
| ------------------------- | --------------------- | ---------------------------------------------------------- |
| `classification`          | **write default**     | what should material created here be marked?               |
| `contains_classification` | **read-side ceiling** | the high-water mark of everything currently attached to it |

`contains_classification` rises as material is attached and **does not fall when
material is detached** — lowering it is a deliberate, recorded act by a named
actor with a reason, not a side effect. It is the admission test: a person may
join only if their effective clearance meets or exceeds it.

⛔ **That test is a floor, not an intersection — and the thing it prevents is
declassification by invite.** The joiner's clearance is checked against the
workspace's mark; the mark does not move down to accommodate the joiner. If it
did, adding one under-cleared member would silently reduce the sensitivity the
workspace claims to hold, and every subsequent admission would be judged against
the reduced value.

Workspace classification runs `public`, `restricted`, `confidential` and stops
there — the two highest levels require compartment-level need-to-know, which is a
property of knowledge items rather than of workspaces. Material above
`confidential` is governed where compartments exist, not here.

Scoped bridges are the link between the two axes: a scoped bridge carries a
`workspace_id`, which is how unit participation is brought into a workspace under
governance rather than by membership alone.

## The flat Team is membership; a unit is a boundary

One more construct is easy to reach for and usually wrong.
`api:POST /api/v1/teams` and `api:POST /api/v1/teams/{id}/members` create a
working group: a set of people, with no classification of its own and no
knowledge-boundary semantics. `sdk:aegis_sdk.TeamsModule` wraps it.

**If you want a boundary, you want a unit.** Flat Teams are the right construct for
"these people work together". They are the wrong construct for "these people and
nobody else may see this", and reaching for one there produces an access model
that is more permissive than you believe it is — with nothing in any listing to
distinguish the two intentions.

Note the vocabulary collision this creates with the `T` in the D/T/R grammar: a
**team unit** (`unit_type: "team"`) is a container in the tree with a head role, a
classification default and a posture ceiling. A flat **Team** created through the teams
surface is a membership list beside the tree. Two constructs, one word, and only
the first is addressable.

## The tenant boundary contains all of it

Everything in this part is scoped to one organisation.
`api:POST /api/v1/organizations` creates one,
`api:GET /api/v1/organizations/{id}` reads it, and
`api:GET /api/v1/auth/me/organizations` lists the ones your principal can see —
which is how you discover you are holding credentials for more than one.
`sdk:aegis_sdk.OrganizationsModule` is the typed write path;
`sdk:aegis_sdk.OrgStandupModule` carries the list reads.

**The tenant boundary is enforced by answering as not-found, not by refusing.** A
unit, role, chain, agent, bridge or workspace belonging to another organisation
comes back `404`, never `403` — because a `403` would confirm the object exists.
Every lookup verifies tenancy, including lookups by primary key and lookups served
from cache.

**Plan for one organisation per customer, and treat a second as a migration you
have not decided to make yet.** The scoping is total: nothing crosses it, and no
bridge, policy or workspace spans it. Anything you build across two organisations
is something you are maintaining outside the platform's model, with none of the
guarantees the rest of this part describes.

## The three mechanisms, once

| mechanism                  | changes the structure? | grants access?                           | survives a re-org?                   |
| -------------------------- | ---------------------- | ---------------------------------------- | ------------------------------------ |
| **unit move**              | yes — and cascades     | no                                       | it **is** the re-org                 |
| **standing bridge**        | no                     | yes, at `partial` or `full`, when active | yes — anchored on **roles**          |
| **scoped bridge**          | no                     | within its window and paths              | within its window                    |
| **ad-hoc bridge**          | no                     | briefly, on approval                     | it expires in minutes                |
| **knowledge share policy** | no                     | downward, non-transitively               | **revalidated**, suspended if broken |
| **workspace**              | no                     | no — membership only                     | unaffected; it is orthogonal         |
| **Team** (flat entity)     | no                     | no — membership only                     | unaffected                           |

And the rule they all obey: **when two bounds meet, the most restrictive wins.**
Envelopes intersect down the reporting chain. Posture takes the minimum at a
bridge crossing. Unit ceilings cascade as a minimum. Workspace admission is a
floor the joiner must clear. There is no path through this model along which a
bound gets wider, and if you find yourself designing one, the structure is the
thing to change.

---

_Next: [Part 11 — The deployment pack](../11-the-deployment-pack/README.md)_
