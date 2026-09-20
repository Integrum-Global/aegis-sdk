# 10.3 — Addressing

Every unit and every role carries an `address` — a compact string naming its
position in the structure. This chapter is the address in full: how it is
composed, what the composition guarantees, the algebra you can compute over it in
your own code, and the one consistency rule that makes all of it mean something.

The address is worth understanding rather than treating as an opaque key, for two
reasons. It is **the identifier that survives renames** — titles get edited,
addresses get recomputed from structure — and it is **the input to the platform's
own governance explanations**, which take an address and tell you how a bound or
an access decision was reached. An integration that keys on titles breaks when
someone edits a title; an integration that keys on addresses breaks only when the
structure actually changes, which is the event you wanted to know about.

**The single idea to carry out: an address encodes containment and authority in
one path, so the string alone answers questions that would otherwise require
walking the tree.**

## The segment format

An address is a sequence of typed, numbered **segments** joined with `-`. Each
segment is one letter from `D`, `T`, `R` followed by an integer.

```text
D1-R1-D1-R1-T1-R2
│  │  │  │  │  └── R2  the second role in that team unit — not its lead
│  │  │  │  └───── T1  the first team unit beneath the CFO
│  │  │  └──────── R1  the CFO — the head role of that department
│  │  └─────────── D1  the first department beneath the CEO
│  └────────────── R1  the CEO — the head role of the root department
└───────────────── D1  the root department

Read right to left to answer "who is this?", left to right to answer
"under whose authority?". Both readings are available because both
relations are in the same string.
```

Read it as: the `D` and `T` segments are the containment path; the `R` segments
are the authority path threaded through it. `D1-R1-D1` means _the first department
beneath the head role of the root department_ — and the `-R1-` in the middle is
the structural expression of [10.2](02-the-d-t-r-grammar.md)'s grammar. It is why
`D1-D1` is not merely discouraged but unrepresentable.

## How the numbers are assigned

The numbering is deterministic, which matters because it means the same structure
always produces the same addresses. Four rules produce every address in the tree.

| position                 | rule                                                                   |
| ------------------------ | ---------------------------------------------------------------------- |
| **root units**           | `D` and `T` are counted by **separate counters**, ordered by unit name |
| **roles within a unit**  | the **primary role is always `R1`**; the rest follow, ordered by title |
| **child units**          | attach as `<parent unit address>-R1-<D\|T><n>`, ordered by unit name   |
| **child unit numbering** | again **separate `D` and `T` counters**, scoped to that parent         |

Three consequences fall out of this that are easy to get wrong.

**`D` and `T` numbering are independent.** A unit containing one department and
one team unit produces `…-R1-D1` and `…-R1-T1`, not `D1` and `T2`. Counting the
children to predict a number will be wrong whenever both types are present.

**`R1` is the head role, always, by construction rather than by convention.** It
is not "the first role created" and not "the most senior"; it is the role carrying
`is_primary_for_unit`. Non-primary roles in the same unit are `R2`, `R3`, …,
ordered by title. So `D1-R1-R2` is a second role reporting in at CEO level — a
staff officer, a chief of staff — and it is _not_ the head of anything.

**Child units attach to `-R1-`, never to the container.** This is the mechanism
described in [10.2](02-the-d-t-r-grammar.md) rendered as a string operation. It is
also why a unit with no primary role is structurally incomplete: there is no
`-R1-` to attach through, so the unit and everything beneath it drops out of
address computation entirely.

⚠ **A headless unit does not produce a bad address — it produces no address, and
its whole subtree produces none either.** The unit stays visible in every listing,
its rows are real, and it simply has no position in the governance graph. The
symptom is a governance explanation that stops higher up the tree than you
expected, or a unit that appears in `api:GET /api/v1/organization-units/tree` and
resolves in no envelope composition. `api:GET /api/v1/organization-units/validate`
names it; `api:GET /api/v1/governance/probe-corrupted-roles` names roles carrying
a null address for the same reason.

## Two bounds on the structure

The structure is bounded in depth and it is cycle-checked, and both are refusals
rather than warnings.

**Maximum depth is 50 segments.** That is an extremely deep organisation — a
fifty-segment address is twenty-five levels of container, each with its head role
— and hitting it in a structure you intended almost always means something is
wrong upstream. Treat it as a tripwire, not as a budget.

**Cycles are detected during traversal.** A unit whose parent chain returns to
itself is refused with the cycle named. This is reachable by a re-parent operation
that would make a unit its own ancestor, and it is refused at the move rather than
discovered later.

## The algebra you can compute yourself

An address is a string with an algebra, and the whole algebra is derivable from
the string. You do not need a round trip to answer any of these — which matters
when you are filtering a page of results client-side, or deciding whether to make
a call at all.

| question                            | operation on the address                                  | example                                            |
| ----------------------------------- | --------------------------------------------------------- | -------------------------------------------------- |
| **What kind of thing is this?**     | read the **last** segment's letter                        | `…-T1` → a unit · `…-R2` → a role                  |
| **How deep is it?**                 | count the segments                                        | `D1-R1-T1-R2` → 4                                  |
| **What is its parent?**             | drop the last segment                                     | `D1-R1-T1-R2` → `D1-R1-T1`                         |
| **What is its ancestry?**           | every prefix, **root-first**, **inclusive of itself**     | `D1-R1-T1` → `D1`, `D1-R1`, `D1-R1-T1`             |
| **Is A beneath B?**                 | A equals B, **or** A starts with `B` + `-`                | `D1-R1-T1` is beneath `D1-R1` — and beneath itself |
| **Which department is it in?**      | truncate at the **first** `T` segment                     | `D1-R1-D2-R1-T1-R2` → `D1-R1-D2-R1`                |
| **Which team unit is it in?**            | take from the **last** `T` segment onward                 | `D1-R1-D2-R1-T1-R2` → `T1-R2`                      |
| **Are two roles in the same team unit?** | strip each trailing `R` segment and compare the remainder | `D1-R1-T1-R1` and `D1-R1-T1-R2` → yes              |
| **What is their common ancestor?**  | the longest shared prefix, cut at a segment boundary      | `D1-R1-D1-R1` and `D1-R1-T1` → `D1-R1`             |

Two of those have a sharp edge worth stating outright, because they are the two
most likely to be implemented slightly wrong and then behave correctly in testing.

> ⛔ **The descendant test is descendant-**or-equal**, and ancestry is
> **inclusive**.** A node is beneath itself and appears in its own ancestry list.
> That is deliberate — it is what makes "everything at or below this address" a
> single test rather than a union of two — and it is the opposite of a strict
> prefix check. An implementation that excludes the node itself will silently drop
> the node you were asking about from every subtree operation, which looks like an
> off-by-one and is really a semantics error.

The prefix test also needs the trailing `-`. Comparing `"D1-R1-T1".startsWith("D1-R1")`
without it means `D1-R12` tests as a descendant of `D1-R1`, which it is not. Split
on segment boundaries or include the separator; do not compare raw prefixes.

```python
# Filter a page of roles to one subtree, client-side, with no extra call.
def is_at_or_below(address: str, root: str) -> bool:
    return address == root or address.startswith(root + "-")

roles = await client.roles.list(limit=200)
under_finance = [
    role for role in roles["items"]
    if role.get("address") and is_at_or_below(role["address"], "D1-R1-D2-R1")
]
```

## What the platform computes for you

Three calls take an address and return something you could not derive from the
string, because they read the live structure rather than parsing a path.

| call                                           | takes                 | returns                                                            |
| ---------------------------------------------- | --------------------- | ------------------------------------------------------------------ |
| `api:POST /api/v1/governance/describe-address` | an address            | the position in plain language — what this address names           |
| `api:POST /api/v1/governance/explain-envelope` | an address            | how that role's effective envelope was composed down its ancestors |
| `api:POST /api/v1/governance/explain-access`   | a subject and an item | which step of the access evaluation refused, and the path taken    |

`describe-address` is the right way to learn the grammar against your own
deployment rather than against this page — pass an address you hold and read what
comes back.

**`explain-envelope` is the single most useful call in this part.** When a bound
is not what you expected, the question is almost always "which ancestor
contributed this?", and reconstructing the answer by hand means walking the
reporting chain and intersecting envelopes at every hop. The explainer returns the
composition. Reach for it before you reach for the tree reads.

`explain-access` does the same job for a read that was refused. A clearance
failure, a classification failure and a missing share policy all present
identically from outside — the call tells you which of the three refused you
instead of leaving you to guess ([10.7](07-re-orgs-bridges-and-workspaces.md)).

```python
# A delegate is bounded more tightly than its own envelope says. Ask why.
explanation = await client.governance.explain_envelope(
    address="D1-R1-D2-R1-T1-R2",
)
# The response carries the composition, ancestor by ancestor — read it
# instead of reconstructing the intersection yourself.
```

## Walking the structure through the API

When you need the live tree rather than the string, the reads split by relation —
and the split is the one [10.1](01-the-organization-is-the-system.md) insists on.

| relation        | reads                                                                                                                        |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **containment** | `api:GET /api/v1/organization-units/tree` · `/roots` · `/{id}/children` · `/{id}/ancestors` · `/{id}/descendants`            |
| **reporting**   | `api:GET /api/v1/organization-roles/{id}/reporting-chain` · `/{id}/direct-reports` · `api:GET /api/v1/admin/roles/hierarchy` |

⛔ **Never walk containment to answer a question about authority.** The ancestors
of a _unit_ are its containers; the ancestors of a _role's authority_ are the
roles it reports to, and those are different sequences over the same tree. A
delegation check, an envelope composition, an escalation target and a trust
lineage all run on the reporting relation. Using
`api:GET /api/v1/organization-units/{id}/ancestors` for any of them produces an
answer that is well-formed, plausible, and about the wrong relation — which is
the worst combination, because nothing about the response looks wrong.

The address is what lets you avoid the choice in the common case: its `R`
segments _are_ the authority path, so parsing the address answers authority
questions without a walk at all.

## Two hierarchies, drawn over the same objects

The reason the address has to encode both relations is that the two hierarchies
are genuinely different shapes, and they can disagree. This is the structural fact
most likely to cost you a day, so it is worth seeing drawn.

```text
TWO HIERARCHIES OVER THE SAME OBJECTS — and they can disagree

── 1 ── CONTAINMENT ── what a thing LIVES INSIDE ─────────────────────────
        Carries: classification default · posture ceiling · isolation plane

  organisation                  the tenant root
    │
    └── unit ───────────────┐  A KNOWLEDGE BOUNDARY
         │                  │
         ├── unit (nested)  │  A unit is a unit of VISIBILITY as well as
         │                  │  of structure. Material crosses it only by an
         └── role           │  explicit share policy — never by adjacency,
              │             │  and NEVER transitively. A nested unit is a
              ├── envelope  │  boundary of its own.
              ├── clearance │
              └── agent     ┘

── 2 ── REPORTING ── what a thing ANSWERS TO ─────────────────────────────
        Carries: envelope composition · trust lineage · delegation

  role ──reports_to──▶ role ──reports_to──▶ role ──▶ (none ⇒ CHAIN ROOT)

  ⚠ A role's manager may sit in a DIFFERENT UNIT from the one containing
    it. The two are edited separately and neither constrains the other.
```

Read the boundary in panel 1 as a **region**, not as another edge — visibility is
not the containment relation. A unit's subtree does not become readable because it
is nested inside something readable, and it does not become readable because a
sibling is. Then note that panel 2 shares objects with panel 1 but not its shape:
a role has exactly one containing unit and exactly one manager, and **those two
facts are independent.**

The address is what reconciles them into one identifier. Its `D` and `T` segments
are panel 1; its `R` segments are panel 2. That is why a single string can answer
both kinds of question — and why reaching for the wrong one of the two read families above returns a
confident answer about the relation you did not ask about.

## Using the algebra: three things it is actually for

The operations in the table above are not trivia. Three common jobs reduce to
them, and each avoids a round trip or a wrong answer.

**Scoping a query to a subtree.** Anything at or below an address is a single
prefix test, so a page of results can be filtered client-side without a second
call. This is the descendant-or-equal semantics earning its keep: "this unit and
everything under it" is one predicate, not a union.

**Deciding whether a crossing is even needed.** Two roles in the same team unit do not
need a bridge to collaborate; two roles in different departments may. The
same-team-unit test answers that from two strings, before you go looking for a bridge
that might not exist ([10.7](07-re-orgs-bridges-and-workspaces.md)).

**Finding where two parts of the organisation meet.** The lowest common ancestor
of two addresses is the node whose authority covers both — which is the role that
can legitimately decide something spanning them, and therefore the right
escalation target for a dispute between them.

```python
# Where do these two positions meet, and who can decide across them?
def lowest_common_ancestor(a: str, b: str) -> str | None:
    seg_a, seg_b = a.split("-"), b.split("-")
    shared = []
    for x, y in zip(seg_a, seg_b):
        if x != y:
            break
        shared.append(x)
    return "-".join(shared) or None

# "D1-R1-D1-R1" (CFO) and "D1-R1-D2-R1" (CTO) meet at "D1-R1" — the CEO.
meeting_point = lowest_common_ancestor(cfo_address, cto_address)
```

⚠ **Cut at segment boundaries, not at characters.** A naive longest-common-string
over `D1-R1-D1` and `D1-R1-D12` returns `D1-R1-D1`, which is a real address and
the wrong answer. Split first, compare segment by segment, and join back.

## The consistency rule

One invariant ties the address to the rows it is derived from:

> **A stored address must agree with the structure it came from** — with
> `parent_unit_id` on a unit, and with both `organization_unit_id` and
> `reports_to_role_id` on a role.

The platform maintains this by **always recomputing**, never by patching.
Sequential numbering at every level means a single move can change addresses
anywhere in the tree — re-parenting a unit can renumber its former siblings — so
there is no such thing as a safe partial recomputation. A structural change
triggers a full recompute for the organisation, and a compile that cannot address
every representable unit is a structural error rather than a quiet omission.

Two practical consequences for your integration:

**Addresses are stable under renames and unstable under moves.** Editing a unit's
name or a role's title does not change any address. Moving a unit changes its
address, every address beneath it, and potentially its former siblings' addresses
too. If you cache addresses, invalidate on move
([10.7](07-re-orgs-bridges-and-workspaces.md)); renames are free.

**Do not construct an address by hand and expect it to resolve.** You can _parse_
an address, and the algebra above is yours to compute. You cannot _mint_ one — the
numbering is assigned by the structure, and a string of the right shape naming a
position that does not exist is simply a string. Read addresses from the objects
that carry them.

⚠ **A unit's `path` field is not its address.** Units also carry a materialised
name path — a slug trail like `/ceo/cfo/finance` — used for fast lookups by name.
It contains no `R` segments, knows nothing about roles, and expresses containment
only. It is a convenience for human-facing search. **The address is the governance
identifier; the path is not**, and keying authorisation logic on the path reads
containment while claiming to read authority.

## Addressing, once

| property              | answer                                                           |
| --------------------- | ---------------------------------------------------------------- |
| Segment shape         | `D`, `T` or `R` followed by an integer; joined with `-`          |
| Head role             | always `R1` in its unit                                          |
| Non-primary roles     | `R2`, `R3`, … ordered by title                                   |
| Child unit attachment | `<parent unit address>-R1-<D\|T><n>`                             |
| `D` and `T` numbering | separate counters, at every level                                |
| Depth ceiling         | 50 segments                                                      |
| Descendant test       | descendant-**or-equal**; requires the trailing `-`               |
| Ancestry              | every prefix, root-first, **inclusive**                          |
| Stable under          | renames, title edits, occupant changes                           |
| Unstable under        | moves — recomputed for the organisation, not patched in place    |
| Derived, not minted   | read it from the object; constructing one by hand names nothing  |
| Not the address       | the unit `path` field — containment only, no roles, no authority |

---

_Next: [10.4 — Roles, authority and intent](04-roles-authority-and-intent.md)_
