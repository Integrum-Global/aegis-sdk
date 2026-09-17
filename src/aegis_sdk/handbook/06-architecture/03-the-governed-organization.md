# 06.3 — The governed organisation

This chapter is the object model. Not how to create things — [02.2](../02-working-through-the-harness/02-standing-up-an-organization.md)
and [02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
do that — but what the things *are*, how they nest, and which of them your own
concepts map onto.

The organising idea is worth stating plainly, because it changes where you look
for a problem: **the organisation chart is not metadata about the system, it is
the addressing scheme of the system.** An envelope resolves through it, a
clearance attaches at a node in it, a trust chain follows one edge of it, and a
knowledge item is owned by a node in it. When a governance decision comes out
differently from what you expected, the answer is usually "some ancestor
contributes a bound you did not account for", and the reason you can compute
that answer at all is that the structure is the input.

**If you are designing against this, the question to hold onto is which of
these objects carries authority and which is only context.** Most of them are
context. A small number of them decide whether an action happens, and those are
the ones whose lifecycle you have to get right — because a context object that
is wrong produces a confusing org chart, while an authority object that is wrong
produces a bound that reads as a bound and stops nothing.

| role in the system | objects | what follows |
| --- | --- | --- |
| **the context both planes read** | organisation, unit, role, team | wrong values mislead; nothing is enforced by them directly |
| **the authority objects** | authority, trust chain, posture, envelope, clearance | **their values change a verdict** — this is where enforcement attaches |
| **the acted-upon objects** | agent, knowledge item, position | bounded by the authority objects; they do not bound themselves |

The middle row is the one to study, and note where those five attach: the
**envelope and clearance hang off a role**, and the **chain and posture hang off
an agent**, while an authority is the signing root above both. A role is
therefore context *and* the anchor the bounds are bolted to — the seat survives
whoever occupies it, which is the property that makes a re-org survivable. That
division is set out precisely in [06.4](04-trust-and-the-audit-spine.md).

[06.1](01-what-core-and-the-sdk-are.md) assigns each object to a plane and
[06.5](05-the-execution-model.md) shows what the execution side does with them.
This chapter stays on the shared substrate both planes sit on, and on the
authority objects in it, because that is the layer you cannot change by writing
code — only by describing it correctly.

## The containment tree

```text
   CONTAINMENT — solid: delete the parent and the child has nowhere
   to live.

     Organisation · the tenant root — one per customer
     │
     └── Unit · department ────── default classification · posture ceiling
         │                        · isolation domain
         │
         ├── Unit · team ──────── nested; inherits from the department
         │
         ├── Role · head ──────── is_primary_for_unit = true
         │
         ├── Role · report ────── belongs to the same unit
         │   ├── Agent ─────────── at most one linked per role
         │   │
         │   └── Human user ────── assigned to a role
         │
         └── Knowledge item ────── owned by a unit

   BINDING — dotted: an envelope does not CONTAIN a role, it
   CONSTRAINS one. Dotted edges over the same objects as the tree above.

     Role · head      ── defines ─────────▶  Role envelope
     Role envelope    ── binds ───────────▶  Role · report
     Role clearance   ── binds ───────────▶  Role · report
     Role · report    ── reports_to ──────▶  Role · head
     Organisation     ── membership only ─▶  Team · working group

   The two nodes those edges reach:

     Role envelope  ── defined BY a supervising role, FOR a target role
     Role clearance ── what the role may see
```

The solid edges are containment: delete the parent and the child has nowhere to
live. The dotted edges are bindings: an envelope does not *contain* a role, it
constrains one.

## Organisation — the tenant root

Everything else in this chapter is scoped to one. `api:POST /api/v1/organizations`
creates it; `api:GET /api/v1/organizations/{id}` reads it back, and
`api:GET /api/v1/auth/me/organizations` lists the ones your principal can see —
which is how you discover you are holding credentials for more than one.

The tenant boundary is enforced by *answering as not-found*, not by refusing.
A unit, role, chain, or agent belonging to another organisation comes back 404,
never 403. `sdk:aegis_sdk.OrganizationsModule` is the thin typed write path;
`sdk:aegis_sdk.OrgStandupModule` is where the list reads live, which is the
split chapter 02.2 warns about.

**Plan for one organisation per customer, and treat a second one as a migration
you have not decided to make yet.** The scoping is total, so anything you build
across two organisations is something you are maintaining outside the platform's
own model.

## Units — the boundary that carries a classification

A unit is where the structure acquires *semantics*: it is simultaneously an
organisational container, a knowledge boundary, and the carrier of a default
data classification. `api:POST /api/v1/organization-units`, and
`sdk:aegis_sdk.OrganizationUnitsModule` for the typed create/get pair.

Three fields on a unit do most of the work, and all three cascade down the tree:

| field | what it does |
| --- | --- |
| `default_classification` | the level knowledge created in this unit inherits unless overridden |
| `max_trust_posture` | the posture ceiling for agents running as roles in this unit |
| `isolation_domain` | the tenant-defined hard-isolation plane the unit sits in |

**Read `effective_max_trust_posture`, never `max_trust_posture`.**
`api:GET /api/v1/organization-units/{id}/posture-ceiling` returns both, and the
declared value is only half the picture: a ceiling cascades, so a child can never
exceed its parent *whatever its own value reads*. Setting a permissive ceiling on
a leaf under a restrictive branch changes nothing, and nothing tells you that.
The setter, `api:PUT /api/v1/organization-units/{id}/posture-ceiling`, has a
genuinely dangerous asymmetry worth carrying into your code: **omitting the
argument leaves the ceiling unchanged, while passing an explicit null clears
it** — and clearing a ceiling widens what the unit may do. Those two are one
keyword apart at the call site and opposite in effect.

`isolation_domain` deserves a warning about defaults. The registry of planes is
tenant-supplied — `api:GET /api/v1/organization-units/isolation-domains` — and
**canonical Aegis ships zero planes**, which is the client's own wording for it.
Read that as a claim about the product rather than about your estate: a
deployment that has configured planes is no longer the canonical one, and an
empty default tells you nothing about what your own deployment holds. *Design
intent, not observable:* the
grading of planes is a deployment's own doctrine about what must not touch what,
so shipping an empty registry keeps the product generic and leaves the decision
where the knowledge is. The setter replaces the whole set rather than merging,
which is what makes *de-registering* a plane expressible at all — and also means
a careless write silently removes every plane you did not re-list.

### Two hierarchies, and they are not the same hierarchy

This is the structural fact most likely to cost you a day, so it gets its own
heading — and its own diagram, because the two relations are easy to read as one
until you see them drawn over the same objects.

```text
TWO HIERARCHIES OVER THE SAME OBJECTS — and they can disagree

── 1 ── CONTAINMENT ── what a thing LIVES INSIDE ────────────────────────────
        Carries: default classification · posture ceiling · isolation plane

  organisation                  the tenant root
    │
    └── unit ───────────────┐ A KNOWLEDGE BOUNDARY ─────────────────
         │                   │
         ├── unit  (nested)  │  A unit is a unit of VISIBILITY as well
         │                   │  as of structure. Material crosses it
         └── role            │  only by an explicit share policy —
              │              │  never by adjacency, and not
              ├── envelope   │  transitively: if A shares with B and
              ├── clearance  │  B with C, C still cannot see A. A
              │              │  nested unit is a boundary of its own.
              └── agent      │
                             ┘

   envelope   what the delegate may DO — five dimensions
   clearance  what the role may SEE
   agent      the acting party. Its trust chain records where its authority
              came from; its posture, how much of that it may use unaided.

── 2 ── REPORTING CHAIN ── what a thing ANSWERS TO ──────────────────────────
        Carries: envelope composition · trust lineage · who delegates to whom

  role ──reports_to──▶ role ──reports_to──▶ role ──▶ (no manager ⇒ CHAIN ROOT)

  ⚠ These are DIFFERENT RELATIONS over the same objects, and they can
    disagree. A role's manager may sit in a different unit from the one that
    contains it. The two are edited separately, and the divergence surfaces
    in the audit export rather than in anything that fails loudly.
```

Read the boundary column first. The knowledge boundary is drawn as a **region**,
not as another edge in the tree, because visibility is not the containment
relation — a unit's subtree does not become readable because it is nested inside
something readable, and it does not become readable because a sibling is. Then
note that panel 2 shares objects with panel 1 but not its shape: a role has
exactly one containing unit and exactly one manager, and **those two facts are
independent.**

There is a **unit tree** (`parent_unit_id`) and there is a **reporting chain**
(`reports_to_role_id`). They are both real, both editable, and they can disagree.
They do different jobs:

- The **unit tree** is where knowledge boundaries, classifications and posture
  ceilings live. It is read top-down: `api:GET /api/v1/organization-units/tree`,
  `/roots`, and per-unit `/{id}/children`, `/{id}/ancestors`,
  `/{id}/descendants`.
- The **reporting chain** is where authority and lineage live. Envelopes compose
  along it, and trust chains follow it. It is read with
  `api:GET /api/v1/organization-roles/{id}/reporting-chain` and
  `/{id}/direct-reports`, or as a whole picture at
  `api:GET /api/v1/admin/roles/hierarchy`.

A role with no `reports_to_role_id` is a **chain root**: it anchors its own
lineage instead of inheriting one. That is legitimate, and it is also how an
accidental orphan happens.

Creating a unit auto-creates that unit's head role, and **the auto-created head
role arrives with no manager.** So a provisioning script that builds a tree but
never parents the heads produces a set of units whose subtrees are each a
separate authority structure, unattached from each other and from the top. No
call fails. Nothing warns you.

The validators will not catch it, and it is worth knowing exactly what each one
covers so you do not rely on the wrong one. `api:GET
/api/v1/organization-units/validate` checks the **unit hierarchy** for orphaned
units and circular references — units, not roles.
`api:POST /api/v1/organization-builder/validate` checks a proposed structure for
circular dependencies, missing fields, invalid relationships and constraint
conflicts. Neither is described as a reporting-chain test.

**So check it yourself, and check the right thing.** `has_primary_role` on
`api:GET /api/v1/organization-units/{id}/summary` tells you the head role exists;
it does not tell you whether that head is *attached*. For that, walk the reporting
chain — `api:GET /api/v1/organization-roles/{id}/reporting-chain` — on every role
you expected to have a manager. A chain that comes back with a single entry is a
root, and on a role you meant to nest, that is the finding.

### Moving a unit is not a small edit

`api:POST /api/v1/organization-units/{id}/move` re-parents everything beneath
the unit, and the response's cascade summary is the honest measure of what that
touched: posture ceilings recompute, knowledge-share policies revalidate, bridges
re-derive, and **trust chains are revoked and recreated**. Read that summary
before treating a move as tidying up the chart. A re-parent is a governance
event.

## Roles — the accountability anchor

A role is the node almost everything else attaches to. It belongs to exactly one
unit, it is what a human is assigned to, what an agent is linked to, what an
envelope constrains and what a clearance is granted on.
`api:POST /api/v1/organization-roles`, or the fuller twelve-operation surface on
`sdk:aegis_sdk.modules.RolesModule`.

| field | what it actually does |
| --- | --- |
| `organization_unit_id` | the unit it belongs to — structural, exactly one |
| `reports_to_role_id` | the reporting edge; null makes it a chain root |
| `is_primary_for_unit` | marks the unit's head role |
| `authority_level` | 1 (staff) … 5 (C-suite) — **informational** |
| `auto_generate_agent` | creates a delegate agent with the role; defaults `true` |
| `is_external` | marks a role representing an outside party |

**`authority_level` does not gate access.** It is seniority, and it is a
tempting thing to build a permission model on. What gates seeing is clearance,
what gates doing is the envelope, and neither of them reads `authority_level`.
A level-5 role with no clearance sees less than a level-1 role with clearance —
that is the intended behaviour, not a bug to work around.

It does gate *assignment*, and that half is enforced rather than advisory: a
caller cannot attach anyone — including themselves — to a role whose
`authority_level` sits above the caller's own effective ceiling. The rule closes
the path of self-assigning into an existing high-authority role that somebody
else legitimately created, which is why it is stated as a ceiling on the caller
rather than as a property of the role.

**A role holds at most one delegate agent**, which is why the link calls take
the role as the identifier: `api:POST /api/v1/organization-roles/{id}/link-agent`
and the bodyless `/{id}/unlink-agent`. Linking does not widen anything — the
agent acts inside the envelope the role already carries — so the link is a
*naming* of who acts as this role, not a grant.

That is also why a role with nobody in it is a normal state rather than an
incomplete one. The platform tracks vacancy explicitly, and a role can be stood
up, linked to an agent, and be doing work before a human is ever appointed to
it.

## The address — one name for a position in the structure

Units and roles both carry an `address`, and it is the compact way to say *where
in the structure this is* — a sequence of typed, numbered segments such as
`D1-R1-T1-R2`. You do not have to decode it yourself: the platform will read one
back to you in plain language with
`api:POST /api/v1/governance/describe-address`, which is the right way to learn
the grammar on your own deployment.

**Half of this is read and half is not, and the difference is the part that
matters.** That a two-segment address names a *unit* is read: the explainer's own
examples pass a field literally called `unit_address` holding `D1-R1`, so the
association is the client's rather than this chapter's. What is **UNVERIFIED** is
narrower, and it is what a parser would trip on — nothing this chapter could read
expands the letters into domain, team and role, and nothing states that the
**segment count** is a grammar rule rather than a coincidence of the examples.
Do not carry "two segments means a unit, four means a role" out of this page: you
have seen the pattern twice, not been told it.
`api:POST /api/v1/governance/describe-address` settles it in one call, against
your own deployment.

The address is worth knowing about for two reasons. It is **the identifier that
survives renames** (titles get edited, addresses get recomputed), and it is **the
input to envelope explanation**: `api:POST /api/v1/governance/explain-envelope`
takes an address and returns the prose account of how that role's effective
envelope was composed down through its ancestors. That is the single most useful
call in this chapter when a bound is not what you expected, because it shows you
the composition rather than making you reconstruct it.

`api:GET /api/v1/organization-units/validate` checks the tree for structural
violations before you commit to one. Role-grammar violations — a head role not
flagged as primary, a role whose address is null, an auto-generated role with no
shadow agent — are enumerable at `api:GET /api/v1/governance/probe-corrupted-roles`,
which is worth running after any bulk provisioning pass.

## Agents — what occupies a role

An agent is the acting party. It is not a user, and it is not a role; it is the
thing that runs, and a role gives it its position. `sdk:aegis_sdk.AgentType` and
`sdk:aegis_sdk.AgentSubtype` are the two axes, and they are genuinely different
questions.

**Type** separates what the agent *is* from a lifecycle standpoint, and the
vocabularies are wider than the create surface — a distinction that matters
because you will see values in listings you cannot create:

| creatable through the API | minted by the platform itself |
| --- | --- |
| `chat`, `task`, `pipeline`, `custom` | `shadow`, `pseudo`, `tool`, `esa` |

Presence in the right-hand column is not something you provision; those agents
come into existence because some *other* object did. A tool agent is created by
registering a tool. **A unit's head role carries a shadow agent — and that
causal direction is inferred here rather than read.** The role model exposes a
`shadow_agent_id`, and the platform raises
`shadow_agent_id_null_despite_auto_generate` when it is absent, which establishes
that the two are linked; *which* of them brings the other into existence is not
stated anywhere this chapter could read. Reading `agents.list()` and finding an
agent you never made is normal, and finding it does not mean someone made it
behind your back.

**Subtype** is behavioural — `specialist`, `manager`, `esa`, `pseudo`,
`governance` — and describes the part the agent plays rather than its container.

**Status** (`sdk:aegis_sdk.AgentStatus`) is the lifecycle: `draft`, `active`,
`archived`, `deprecated`, `suspended`, `revoked`. Treat `suspended` and `revoked`
as reachable rather than exotic; an agent is transitioned to `suspended` by the
platform when something goes wrong, which is exactly the moment your code is
running and reading.

> ⛔ **`sdk:aegis_sdk.UnitType` is not the unit tree's unit type.** That enum is
> `atomic` / `composite` and classifies a *work* unit — a different domain that
> happens to share the word. The organisational unit type is the string
> `department` or `team` on an organisation unit. Two meanings, one word, and the
> enum name points at the one you probably did not mean.

## Positions — a stance, which is not a structure

One object here is genuinely outside the org chart, and it is easy to miss
because it sounds like it belongs in it. A **position** is a signed stance an
agent holds on behalf of a principal — an opinion, a recommendation, a
commitment — and the platform treats it as a claim that needs a human's
authority before anyone may act on it. `sdk:aegis_sdk.modules.PositionsModule`.

It is created **fail-closed**. A new position is `unratified` and therefore not
binding; the represented principal ratifies it
(`api:POST /api/v1/positions/{id}/ratify`) before it means anything, and may
retract it afterwards (`/{id}/retract`). Consumers read it through
`api:POST /api/v1/positions/{id}/consume`, which returns the position *only if it
is binding* — so a design that reads a position and then decides for itself
whether to trust it is re-implementing a check the platform already enforces.

Branch on the derived `is_binding` flag rather than comparing `binding_status` to
a string. The status is the stored lifecycle state; the flag is the platform's
own derived answer, and it is the same derivation `consume` enforces — so reading
the flag is reading the value that actually decides.

> ⛔ **The positions surface admits a user session only.** It answers 403 for a
> client built with an API key, because an API-key principal carries no role and
> no personas by design. Use OAuth configuration for anything that touches it.
> Actor identity is server-derived for every decision operation, so no method
> takes an actor argument — supplying one would not change who the platform
> records.

## The bounds that attach to a role

Two independent limits attach to the same node, and designing as though they were
one is the most common modelling error on the platform.
[02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
has the task-level treatment; the structural statement is this:

- An **envelope** bounds what a delegate may *do*. It is authored by a
  *defining role* for a *target role* — `api:POST /api/v1/role-envelopes`, via
  `sdk:aegis_sdk.RoleEnvelopesModule` — and it is composed along the reporting
  chain by **monotonic tightening**, an intersection and never a union.
- A **clearance** bounds what a role may *see* —
  `api:POST /api/v1/role-clearances`, reached through the trust-posture module
  rather than through a module named for clearances.

The structural consequence is worth drawing out, and it is a **derivation** from
the tightening rule rather than a separate guarantee: because a target's bounds
are always a subset of its definer's, **the envelope graph is a DAG rooted in the
reporting chain, not a free-form overlay.** You cannot express an escalation by
adding an envelope. Widening is not a thing the model can say. If a delegate
genuinely needs to exceed its bounds, the answer is a human decision, not a
second envelope — and if you find yourself wanting one, that is the signal you
are modelling the wrong structure.

Both take a **draft/active distinction**, and in both cases creating is not
granting: an envelope defaults to `draft` and does not enforce until activated,
and a new clearance lands in a pending vetting state and is not in force until
approved. These are the same shape in two places, and the failure mode is
identical — a provisioning script that creates fifty of something and walks away
has produced an organisation that lists as bounded and enforces nothing.

## Where classification meets clearance

Units carry a **default** classification; knowledge items carry an **explicit**
one. Material created in a unit without an explicit level inherits the unit's
default, which is why a unit created with the default value is a decision rather
than a non-decision.

Knowledge itself is a tree, not a flat set. Each item carries a `path` that
expresses containment — `api:POST /api/v1/knowledge`, with lifecycle operations
on `sdk:aegis_sdk.KnowledgeModule` and the fuller review and share surface on
`sdk:aegis_sdk.modules.KnowledgeGovernModule`. An item's `owner_unit_id` points
it at a unit, and that ownership is what makes unit boundaries real: material
sharing across a boundary does not follow adjacency on the chart, it follows a
knowledge-share policy somebody wrote
(`api:POST /api/v1/knowledge-share-policies`). **Sharing is not transitive** —
if A shares with B and B shares with C, C still cannot see A's material, because
every hop is its own policy. Designs that assume otherwise promise a capability
that does not exist, in the safe direction.

A read is permitted when the role's clearance, the item's classification (plus
compartment, at the top two levels), and any applicable share policy all line up.
A failure in any of them presents identically, which is why
`api:POST /api/v1/governance/explain-access` exists — it returns the step the
evaluation reached and the access path taken, so you can see *which* of the
three refused you instead of guessing.

## Teams — a membership list, not a boundary

`api:POST /api/v1/teams`, members at `api:POST /api/v1/teams/{id}/members`. A
team is a working group: a set of people, with no classification of its own and
no knowledge-boundary semantics. It sits *beside* the containment tree rather
than in it.

The practical rule: **if you want a boundary, you want a unit.** Teams are the
right construct for "these people work together"; they are the wrong construct
for "these people and nobody else may see this", and reaching for one there
produces an access model that is more permissive than you believe it is.

## Vocabulary — the ontology

Finally, the tenant has a vocabulary. `api:POST /api/v1/ontology/preset/{id}`
applies a preset — replacing custom terms with that preset's defaults —
`api:GET /api/v1/ontology/presets` and `api:GET /api/v1/ontology/config/{id}`
read what is in force, and `sdk:aegis_sdk.OntologyModule` wraps them.

What is documented is that applying a preset **replaces the terms**. That the
objects underneath are unaffected is **UNVERIFIED** — it is the behaviour you
would expect of a vocabulary layer, and the safe assumption until you check it on
your own deployment, but this chapter did not establish it. If your integration
keys on a term rather than on an identifier, confirm the two independently.

Set it early. It is nearly free at provisioning time and disruptive once people
have learned the old words, which makes it a decision worth making deliberately
rather than by never making it.

## The model, once

| object | answers | nests in | bounded by |
| --- | --- | --- | --- |
| Organisation | whose tenant is this? | — | — |
| Unit | where in the boundary tree? | a unit, or none (root) | default classification, ceiling, isolation plane |
| Role | who is accountable here? | exactly one unit | envelope, clearance, reporting edge |
| Agent | who acts? | a role (at most one) | envelope and clearance, via the role |
| User | which human? | a role, by assignment | role + its bounds |
| Team | who works together? | nothing — membership only | — |
| Position | what does an agent assert? | nothing — a stance | ratification by the represented principal |
| Knowledge item | what is the governed material? | a path, owned by a unit | classification + compartment + share policy |
| Envelope / Clearance | what may this role do / see? | attached to a role | the definer's own bounds (tightening only) |

---

*Next: [06.4 — Trust and the audit spine](04-trust-and-the-audit-spine.md)*
