# 02.2 — Standing up an organisation

The provisioning path, in the order the platform requires it, with the
constraints that are not obvious from any single call.

## The order is not arbitrary

```
organisation  ->  unit  ->  head role  ->  further roles  ->  teams
```

Each step needs the identifier the previous one returned. A unit cannot exist
without an organisation to hold it; a role cannot exist without a unit; the
reporting chain is expressed by pointing one role at another, so the manager must
exist before the report.

You cannot usefully parallelise this. You can parallelise *sibling* roles under a
unit that already exists, and for a large org chart that is where the time goes.

## 1. The organisation

```python
org = await client.organizations.create(
    name="Northwind Manufacturing",
    slug="northwind",
    plan_tier="professional",
)
org_id = org["id"]
```

`api:POST /api/v1/organizations`. This is the tenant root; everything below is
scoped to it. Read it back with `api:GET /api/v1/organizations/{id}`, and list
the organisations your principal can see with
`api:GET /api/v1/auth/me/organizations`.

## 2. Units — and the classification decision you are making

```python
unit = await client.units.create(
    name="Treasury",
    unit_type="department",
    description="Cash and liquidity management",
    default_classification="confidential",
)
unit_id = unit["id"]
```

`api:POST /api/v1/organization-units`.

`unit_type` is `department` or `team`. Nest with `parent_unit_id`; omit it for a
root unit.

**`default_classification` is the most consequential argument on this call and it
defaults to the most permissive value.** The five levels, in order:

```
public  <  restricted  <  confidential  <  secret  <  top_secret
```

The default is `public`. Knowledge created in a unit inherits that level unless
overridden, and the level is what clearance is checked against later. A unit
created with the default and populated with real material is a unit whose
contents are readable more widely than anyone intended, and nothing will tell you
— it is not an error state, it is a choice you made by omission.

**Set it explicitly on every unit, every time.** If you take one habit from this
chapter, take that one.

Other arguments worth knowing: `budget_allocation` and `budget_currency` (the
unit's financial envelope), `headcount_limit`, `responsibilities`, and
`constraint_overrides` for unit-level constraint defaults.

## 3. Roles — the reporting chain, and the head-role rule

Every unit needs a head. Create it first, flagged:

```python
head_role = await client.roles.create(
    organization_unit_id=unit_id,
    title="Head of Treasury",
    authority_level=4,
    is_primary_for_unit=True,
)
head_role_id = head_role["id"]
```

Then its reports, pointing at it:

```python
analyst = await client.roles.create(
    organization_unit_id=unit_id,
    title="Treasury Analyst",
    authority_level=1,
    reports_to_role_id=head_role_id,
)
```

`api:POST /api/v1/organization-roles`.

Three things about roles that are routinely misread:

- **`authority_level` is informational and does NOT gate access.** It runs 1
  (staff) to 5 (C-suite) and describes seniority. What gates access is
  *clearance*, which is a separate axis and is chapter 02.3. A level-5 role with
  no clearance sees less than a level-1 role with clearance. Designing a
  permission model around `authority_level` produces something that looks like it
  works and does not.
- **`reports_to_role_id` is the delegation path.** Trust chains follow the
  reporting chain, not the unit tree — a role with no manager is a chain root.
  Chapter 02.4 depends on this being right, so get the reporting lines correct at
  creation rather than fixing them later.
- **`auto_generate_agent` defaults to `True`.** Creating a role creates an agent
  for it unless you say otherwise. That is usually what you want, and it is
  occasionally a surprise when a provisioning run produces more agents than roles
  you meant to staff. Pass `auto_generate_agent=False` when you are building
  structure ahead of staffing it.
- **Creating a UNIT auto-creates its primary role, and that role arrives
  UNPARENTED** — `reports_to_role_id` is null, so by the bullet above it anchors
  its own trust chain instead of inheriting one. Nothing warns you. Parent it
  explicitly after creating the unit.

**Building structure ahead of staffing it is the normal case, not a degenerate
one** — a lead seat with nobody in it is valid, and a delegate agent can be stood
up, trusted and activated on it. Chapter 02.7 has that sequence, along with what
happens to the agent when somebody is eventually appointed, when they leave, and
when the role moves.

Read roles back with `api:GET /api/v1/organization-roles` and
`api:GET /api/v1/organization-roles/{id}`; the assembled hierarchy is at
`api:GET /api/v1/admin/roles/hierarchy`. Assign a human to a role with
`api:POST /api/v1/organization-roles/{id}/assign-user`.

## 4. Teams

```python
team = await client.teams.create(name="Cash Ops", description="Daily cash desk")
await client.org_standup.add_team_member(team["id"], user_id="user_...")
```

`api:POST /api/v1/teams`, members at `api:POST /api/v1/teams/{id}/members`. Teams
are working groups; they do not carry the knowledge-boundary semantics a unit
does. If you want a boundary, you want a unit.

Note where `add_team_member` lives — on `client.org_standup`, not on
`client.teams`. That is not a typo, and the next section is about why.

## 5. Vocabulary — make the vertical speak its own language

```python
await client.ontology.apply_preset(org_id, preset_id="finance")
```

`api:POST /api/v1/ontology/preset/{id}`. Available presets are at
`api:GET /api/v1/ontology/presets`, and the resolved configuration for an
organisation at `api:GET /api/v1/ontology/config/{id}`.

This changes the nouns the product uses in that tenant. It is cheap to do at
provisioning time and disruptive to change once people have learned the old
words, so decide it early.

## ⚠ Writing and reading are different modules, with different return types

This is the single thing about the SDK most likely to cost you an afternoon, so
it gets its own section.

**The typed standup modules — `client.organizations`, `client.units`,
`client.roles`, `client.teams`, `client.role_envelopes`, `client.knowledge` —
expose `create` and `get` and nothing else.** There is no `client.units.list()`.
Reaching for one is the obvious move and it raises `AttributeError`.

The list operations live on `client.org_standup`:

| you want | you call | you get back |
| --- | --- | --- |
| create a unit | `client.units.create(...)` | a `dict` — `unit["id"]` |
| get one unit | `client.units.get(unit_id)` | a `dict` |
| **list units** | `client.org_standup.list_units(...)` | an **`OrganizationUnitList`** model — `.records`, `.total` |
| list roles | `client.org_standup.list_roles(...)` | a model with `.records` |
| list teams | `client.org_standup.list_teams(...)` | a model with `.records` |
| list organisations | `client.org_standup.list_organizations(...)` | a model with `.records` |

So the write returns a dictionary and the read returns a Pydantic model, and the
two are accessed differently: `unit["id"]` on the way in, `unit.id` on the way
out. Mixing them is the most common first-run failure in a provisioning script,
and it fails at the point of *use* rather than at the call, which is what makes
it annoying to locate.

`list_units` also takes `parent_unit_id`, `unit_type`, `include_archived`, and
`limit` / `offset` — and **`limit` defaults to 50**. A tenant with more than 50
units silently gives you the first 50. Page it, or you will write a
create-if-missing check that re-creates everything past the first page.

## Writing this as a script you can run twice

The single highest-value habit in this chapter. A provisioning script that fails
halfway leaves an organisation in a state nobody designed, and the instinct — to
delete it and start over — stops being available the moment there is real data in
it.

```python
import asyncio
from aegis_sdk import AgenticOSClient


async def all_units(client):
    """Every unit, paged — list_units caps at 50 per call."""
    out, offset = [], 0
    while True:
        page = await client.org_standup.list_units(limit=200, offset=offset)
        out.extend(page.records)            # models: attribute access
        if len(out) >= page.total or not page.records:
            return out
        offset += len(page.records)


async def ensure_unit(client, *, name, unit_type, classification):
    """Return the existing unit with this name, or create it."""
    for u in await all_units(client):
        if u.name == name:                  # model -> u.name
            return u.id
    created = await client.units.create(    # dict -> created["id"]
        name=name, unit_type=unit_type, default_classification=classification
    )
    return created["id"]


async def provision() -> None:
    client = AgenticOSClient.from_env()
    treasury_id = await ensure_unit(
        client, name="Treasury", unit_type="department", classification="confidential"
    )
    print(treasury_id)


asyncio.run(provision())
```

**Match on something stable.** Names get edited, so if your units carry a `code`
or a tag, key on that instead of `name` — otherwise the day someone renames
"Treasury" to "Group Treasury" your idempotent script creates a second one.

> **In the console:** the organisation builder covers this ground —
> *Organisation → Builder*, with `api:POST /api/v1/organization-builder/validate`
> and `api:POST /api/v1/organization-builder/deploy` behind it, and progress at
> `api:GET /api/v1/organization-builder/deployment-status`. It is genuinely
> useful for *designing* a structure interactively and for showing a stakeholder
> what you propose. Export the result into a script before you rely on it.

## Verifying what you built

Before moving on, assert the structure rather than eyeballing it. This is the
kind of check nothing runs for you:

```python
for u in await all_units(client):
    assert u.default_classification != "public", f"{u.name} is public"
```

`default_classification` is a field on the returned unit model, so this reads the
committed state rather than the value you believe you sent. That one assertion
catches the failure mode this chapter opened with, and it costs a line.

---

*Next: [02.3 — Envelopes, clearance and knowledge](03-envelopes-clearance-and-knowledge.md)*
