# 10.1 — The organisation is the system

This chapter is the premise the rest of the part rests on. It is not a tour of
the objects — [06.3](../06-architecture/03-the-governed-organization.md) does
that, and this part assumes you have read it — but an argument about what kind
of thing the organisation chart _is_ on this platform, and what changes in your
design once you accept it.

The claim is short and it is not a metaphor: **the organisation chart is not
metadata about the system, it is the addressing scheme of the system.** Every
governance decision the platform makes resolves through it. An envelope composes
along one of its edges. A clearance attaches at one of its nodes. A trust chain
is derived from one of its relations. A knowledge item is owned by one of its
containers. There is no second structure the platform consults and no override
table sitting beside the chart.

**So describing your organisation is not configuration, it is the largest
engineering decision you will make on this platform.** A schema you got wrong
produces queries that are awkward; a structure you got wrong produces governance
that is wrong — bounds that resolve to the wrong ancestor, delegations that
reach where you did not intend, knowledge that crosses a boundary you thought you
had drawn. And it produces all of that silently, because a structure the platform
can address is a structure it will happily operate.

## What the organisation carries

Six distinct things hang off the structure, and none of them has a parallel
mechanism. If the structure is wrong, each of them is wrong in a different way.

| what resolves through the structure | the relation it uses        | what goes wrong when the structure is wrong             |
| ----------------------------------- | --------------------------- | ------------------------------------------------------- |
| **operating envelopes**             | the reporting edge          | a delegate is bounded by an ancestor you did not intend |
| **trust chains**                    | the reporting edge          | authority traces to the wrong human                     |
| **posture ceilings**                | the containment edge        | an agent is permitted autonomy the unit never granted   |
| **knowledge boundaries**            | the containment edge        | material is visible where it should not be              |
| **classification defaults**         | the containment edge        | new material is born at the wrong sensitivity           |
| **addresses**                       | both, encoded into one path | every one of the above resolves against the wrong node  |

Read the middle column carefully, because it is the structural fact that costs
most: **two of these run on the reporting relation and three run on the
containment relation, and those are different relations over the same objects.**
A role belongs to exactly one unit and reports to exactly one other role, and
those two facts are independent. The chart you draw on a whiteboard collapses
them into one set of lines; the platform does not.

The practical consequence is that "this role sits under Finance" is an ambiguous
sentence, and the ambiguity has governance weight. If it means _contained by
Finance_, the role inherits Finance's classification default and posture ceiling.
If it means _reports to the head of Finance_, the role's envelope composes down
from that role's envelope and its trust chain descends from that role's agent.
Usually you want both. Sometimes you deliberately want one — a security officer
contained in Engineering but reporting to the General Counsel is a real and
supported shape. **What you must not do is assume one implies the other.**

## Why one address rather than two trees

A design that kept containment and reporting as two separate graphs would be
simpler to write and impossible to reason about, because every governance
question would require walking both and reconciling the answers. Aegis instead
encodes both into a single traversable path — the **address** — so that one
string answers _where in the structure is this, under whose authority, inside
which boundary_.

```text
ONE STRUCTURE, TWO RELATIONS, ONE ADDRESS

   BOD                                        L0   governance root
   └── D1  CEO Office                         L1   a CONTAINER
       └── D1-R1  CEO                         L2   the container's HEAD ROLE
           ├── D1-R1-R2  Staff Officer        L3   a role reporting in at CEO level
           ├── D1-R1-D1  CFO Office           L3   a container attached THROUGH the CEO
           │   └── D1-R1-D1-R1  CFO           L4   its head role
           └── D1-R1-T1  Audit Committee      L3   a TEAM UNIT, attached through the CEO

   The `-R1-` in the middle of every branch is not decoration. A child
   container attaches to its parent's HEAD ROLE, never to the parent
   container directly. That is why `D1-R1-D1` is expressible and `D1-D1`
   is not — the containment edge is forced to pass through a person.
```

Read it as: the address is a path down the containment tree, but every hop
between two containers passes through the head role of the upper one. That single
construction is what fuses the two relations. Containment is the sequence of `D`
and `T` segments; authority is the sequence of `R` segments they are threaded
through.

This is why the grammar in [10.2](02-the-d-t-r-grammar.md) is enforced rather
than recommended, and why the addressing algebra in
[10.3](03-addressing.md) works at all. An organisation that violated the grammar
could not be given an address, and an organisation that cannot be given an
address cannot have its governance computed.

## Describing an organisation is a compile, not a write

You do not assemble the structure by writing rows and hoping they cohere. The
platform takes a described structure, validates it, computes everything derived
from it, and deploys the result — and each of those is a separate call you can
run independently.

| step          | call                                                  | what it establishes                           |
| ------------- | ----------------------------------------------------- | --------------------------------------------- |
| **validate**  | `api:POST /api/v1/organization-builder/validate`      | the structure is legal before anything lands  |
| **preview**   | `api:POST /api/v1/organization-builder/preview`       | what the structure will look like once built  |
| **compile**   | `api:POST /api/v1/organization-builder/compile`       | addresses, ceilings and envelopes are derived |
| **deploy**    | `api:POST /api/v1/organization-builder/deploy`        | the compiled structure becomes the live one   |
| **roll back** | `api:POST /api/v1/organization-builder/rollback/{id}` | a deployment is reverted as a unit            |

Three of the derived artifacts have their own generation calls, which is worth
knowing because it tells you what "derived" actually covers:
`api:POST /api/v1/organization-builder/generate-agents`,
`api:POST /api/v1/organization-builder/generate-constraints`, and
`api:POST /api/v1/organization-builder/generate-trust-chains`. **Agents,
constraint envelopes and trust chains are all outputs of the structure, not
inputs to it.** You do not author a trust chain and then find a place for it in
the chart; you describe the chart and the chains follow from it
([10.5](05-trust-chains-and-delegation.md)).

For a structure you already hold in a file,
`api:POST /api/v1/organization-builder/import-yaml` takes it in one pass, and
`api:GET /api/v1/organization-builder/templates` lists the shapes the deployment
ships. `api:GET /api/v1/organization-builder/deployment-status` reports where a
build got to.

**The failure mode here is validating nothing and deploying anyway.** A structure
with a headless container is not rejected at write time — the container is real,
its rows exist, and every listing shows it. What happens instead is that the
compile cannot address it, so the container and everything beneath it drops out
of the computed governance while remaining perfectly visible in the chart. The
symptom is an agent that answers `404` to a governance question about a unit you
can see, or an envelope explanation that stops higher up the tree than you
expected. Run `api:GET /api/v1/organization-units/validate` before a deploy, and
`api:GET /api/v1/governance/probe-corrupted-roles` after any bulk provisioning
pass; both are seconds and both name the node.

## The structure survives the people

A role is a **position**, not a person. It is created before anyone occupies it,
it persists when the occupant leaves, and it is what every bound attaches to. The
occupant is an attribute of the position, set by
`api:POST /api/v1/organization-roles/{id}/assign-user` and cleared by
`api:POST /api/v1/organization-roles/{id}/unassign-user`.

That split is what makes the structure durable under the thing organisations do
most, which is change who is in which chair. A departure clears an assignment; it
does not disturb an envelope, a clearance, a trust chain, an address, or a
subtree. The governance you described stays described.

It also means an empty chair is an ordinary state rather than a broken one.
**Roles are born vacant** — a container's head role is created with the
container, before anyone is appointed — and the platform is built to operate that
way. [10.4](04-roles-authority-and-intent.md) develops what vacancy does and does
not change; the short version is that it changes exactly one thing, and it is not
the one most people expect.

## The unit is three boundaries at once

A container is not only a container. Three fields on a unit cascade down the
containment tree, and each makes the unit a different kind of boundary. You get
all three whenever you create one, which is why "I just need somewhere to group
these" is never quite what a unit does.

| field                    | what it decides                                                                    |
| ------------------------ | ---------------------------------------------------------------------------------- |
| `default_classification` | the sensitivity material created in this unit is born at, absent an explicit level |
| `max_trust_posture`      | the autonomy ceiling for agents running as roles in this unit                      |
| `isolation_domain`       | the hard-isolation plane the unit sits in                                          |

**Creating a unit with the default classification is a decision, not the absence
of one.** Every knowledge item created inside it inherits that level, and the
inheritance is silent. A unit stood up for a sensitive function at the lowest
default produces correctly-classified-looking material at the wrong sensitivity
for as long as nobody looks.

⚠ **Read the _effective_ posture ceiling, never the declared one.**
`api:GET /api/v1/organization-units/{id}/posture-ceiling` returns both, and a
ceiling cascades — a child can never exceed its parent's effective value whatever
its own field reads. Setting a permissive ceiling on a leaf beneath a restrictive
branch changes nothing, and nothing tells you that.
[10.6](06-role-agents.md) covers the composition and the setter's sharp edge.

The isolation-domain registry is tenant-supplied:
`api:GET /api/v1/organization-units/isolation-domains` reads what your deployment
has configured and `api:PUT /api/v1/organization-units/isolation-domains` sets it.
The setter **replaces the whole set rather than merging**, which is what makes
de-registering a plane expressible at all — and also means a careless write
silently removes every plane you did not re-list.

## Standing a structure up

The sequence below is the shape of every provisioning script that works, and the
ordering is not stylistic. Each step depends on the one before it: a child unit
cannot attach until its parent has a head role, and a head role cannot be attached
to a reporting chain that does not exist yet.

```python
# 1. The tenant root.
org = await client.organizations.create(name="Northwind Industrials")

# 2. The root department. Its head role is created with it, vacant and primary.
ceo_office = await client.organization_units.create(
    name="CEO Office",
    unit_type="department",
    default_classification="confidential",
)
ceo_role_id = ceo_office["head_role"]["id"]

# 3. Give the head role its intent and its band. It is a chain ROOT — it has
#    no reporting edge, and that is correct at the top of the organisation.
await client.roles.update(
    role_id=ceo_role_id,
    title="Chief Executive Officer",
    authority_level=5,
    job_description="Accountable for the whole of Northwind's operations...",
)

# 4. Now a child department can attach — through the CEO role, per the grammar.
finance = await client.organization_units.create(
    name="Finance",
    unit_type="department",
    parent_unit_id=ceo_office["id"],
    default_classification="confidential",
)

# 5. Attach ITS head to the reporting chain. The platform does not infer this,
#    and skipping it is the defect that produces a detached authority island.
await client.roles.update(
    role_id=finance["head_role"]["id"],
    title="Chief Financial Officer",
    authority_level=5,
    reports_to_role_id=ceo_role_id,
)
```

**The step people skip is 5**, and skipping it fails nothing. The department
exists, it is contained correctly, it has a head, it addresses correctly, and its
head reports to nobody — so every envelope beneath it composes from a root rather
than from the CEO, and every trust chain beneath it traces to a different origin
than you intended. The check is one call:
`api:GET /api/v1/organization-roles/{id}/reporting-chain` on a role you meant to
nest, returning a single entry.

## What the structure does not decide

It is as useful to know what the chart is _not_ load-bearing for, because
designing these into it produces containers that exist for no governance reason.

| this is **not** decided by the structure | it is decided by                             |
| ---------------------------------------- | -------------------------------------------- |
| what a role may **see**                  | its clearance, and the item's classification |
| how autonomous an agent is               | its posture, capped by the unit's ceiling    |
| who works together on something          | workspace membership — an orthogonal axis    |
| who may cross to another part of the org | a bridge, explicitly authorised              |
| what vocabulary your tenant uses         | the ontology, set once at provisioning       |

The last is worth setting early. `api:GET /api/v1/ontology/presets` lists the
available vocabularies, `api:POST /api/v1/ontology/preset/{id}` applies one, and
`sdk:aegis_sdk.OntologyModule` wraps them. It is nearly free at provisioning time
and disruptive once people have learned the old words — which makes it a decision
worth making deliberately rather than by never making it.

## Four consequences for your design

Each of these is a decision you will otherwise make by accident.

**Model your real accountability, not your product taxonomy.** The structure is
the authority graph, so a node in it should correspond to something a person is
answerable for. Team units named after subsystems, containers created to group
documents, and roles minted to hold a permission all produce a chart that reads
sensibly and governs strangely — because the platform will faithfully compose
envelopes along edges you drew for filing reasons.

**Draw the containment boundary where you want a knowledge boundary.** A unit is
simultaneously an organisational container, a classification default and a
visibility boundary, and you get all three or none. If you want material fenced,
you want a unit; if you only want people grouped, see
[10.7](07-re-orgs-bridges-and-workspaces.md), which covers the constructs that
group without fencing.

**Decide the reporting edge deliberately, including where it is absent.** A role
with no reporting edge is a **chain root** — it anchors its own lineage instead of
inheriting one. For the top of the organisation that is correct. Everywhere else
it is an orphan, and the two are indistinguishable in every listing.
`api:GET /api/v1/organization-roles/{id}/reporting-chain` returning a single entry
is the check: on a role you meant to nest, that single entry is the finding.

**Expect to restructure, and design so restructuring is survivable.** Re-parenting
a unit recomputes addresses, revalidates knowledge-share policies, re-derives
bridges and rebuilds trust chains beneath it. That is a governance event with a
cascade, not a chart edit, and
[10.7](07-re-orgs-bridges-and-workspaces.md) is about making it one you can
absorb. Structures that anchor on roles rather than on containers survive it best,
which is why bridges anchor on roles.

## The idea, once

| the conventional reading           | what is actually true here                                           |
| ---------------------------------- | -------------------------------------------------------------------- |
| the org chart describes the system | the org chart **is** the addressing scheme of the system             |
| roles are labels on people         | roles are **positions**; people are an attribute of them             |
| "under Finance" is one fact        | containment and reporting are **two** relations, independently set   |
| trust is configured                | trust is **derived** from the reporting relation                     |
| restructuring is a chart edit      | restructuring is a **cascade** across five derived artifacts         |
| an empty seat is a gap             | an empty seat is an **ordinary state** the platform operates through |

---

_Next: [10.2 — The D/T/R grammar](02-the-d-t-r-grammar.md)_
