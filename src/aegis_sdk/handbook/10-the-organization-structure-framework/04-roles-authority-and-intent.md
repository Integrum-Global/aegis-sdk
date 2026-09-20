# 10.4 — Roles, authority and intent

A role is the node almost everything attaches to. It belongs to exactly one unit,
it reports to at most one other role, it is what a human is assigned to and what
an agent acts as, and it is what an envelope constrains and a clearance is granted
on. This chapter is the role in full: what it holds, what its job description
actually _does_, what its authority level does and does not gate, and why an empty
one is an ordinary state rather than a gap.

Three things in this chapter are commonly misread in the same direction — as
weaker than they are, or as stronger. The job description looks like documentation
and is executable intent. The authority level looks like a permission and is not
one. Vacancy looks like an outage and changes exactly one thing.

**The single idea to carry out: a role is a position the organisation holds open,
and everything the platform knows about what that position is _for_ lives in
fields on the role, not in the person occupying it.**

## The role, field by field

`api:POST /api/v1/organization-roles` creates one;
`api:PUT /api/v1/organization-roles/{id}` updates it; `sdk:aegis_sdk.modules.RolesModule`
is the typed surface. The fields divide cleanly into four groups, and the groups
behave very differently.

| field                        | what it actually does                                                          |
| ---------------------------- | ------------------------------------------------------------------------------ |
| **structure**                |                                                                                |
| `organization_unit_id`       | the unit it belongs to — structural, required, exactly one                     |
| `reports_to_role_id`         | the reporting edge; absent makes it a **chain root**                           |
| `is_primary_for_unit`        | marks the unit's head role — exactly one per unit                              |
| `address`                    | its position, derived — see [10.3](03-addressing.md)                           |
| `direct_reports_count`       | how many roles report to it                                                    |
| **intent**                   |                                                                                |
| `title`                      | the position's name — this field is `title`, not `name`                        |
| `description`                | a short human-facing summary                                                   |
| `job_description`            | **the primary content of the role agent's system prompt** — see below          |
| `responsibilities_json`      | what this position is answerable for; **carried into the prompt in full**      |
| `approval_authority_json`    | what this position may approve, and up to what limits                          |
| `required_skills_json`       | the skills the position calls for                                              |
| `required_capabilities_json` | the capabilities the position calls for                                        |
| **authority and bounds**     |                                                                                |
| `authority_level`            | 1 (Staff) … 5 (C-Suite) — **seniority, not an access gate**                    |
| `constraint_template_id`     | the constraint template this role's bounds start from                          |
| `constraint_overrides_json`  | this role's deviations from that template                                      |
| **occupancy**                |                                                                                |
| `assigned_user_id`           | the human currently in the seat                                                |
| `is_vacant`                  | whether the seat is empty — **roles are born vacant**                          |
| `vacancy_reason`             | why it is empty; a closed set of three values                                  |
| `auto_generate_agent`        | create the delegate agent with the role; defaults on, forced off when external |
| `shadow_agent_id`            | the delegate agent acting as this role — at most one                           |
| `is_external`                | a board member or advisor; governance participation only                       |
| `is_coordinator`             | a cross-team coordinator; non-primary, bridge-scoped envelope                  |
| `status`                     | `active` or `archived`                                                         |

Note what is _not_ on a role. **There is no clearance field** — a clearance is a
separate object granted on the role (`api:POST /api/v1/role-clearances`), with its
own vetting lifecycle. **There is no posture field** — posture belongs to the
agent, and the role's authority level is what determines the posture its agent is
provisioned at. Looking for either on the role and finding nothing is the
expected outcome, not a gap.

## The job description is executable

This is the field most likely to be treated as documentation, and it is the one
with the most direct runtime effect. **`job_description` becomes the primary
content of the role agent's system prompt.** Every organisational role has an
agent ([10.6](06-role-agents.md)); that agent's instructions are assembled from
the role, and the job description is the body of them.

The assembly is ordered, and the order is the priority:

```text
THE ROLE AGENT'S SYSTEM PROMPT, IN ASSEMBLY ORDER

  1. IDENTITY         who this agent is — the role's title, its authority
                      band, and the autonomy posture that band implies

  2. JOB DESCRIPTION  the role's `job_description`, carried in as the
                      PRIMARY CONTENT. This is the bulk of the prompt.

  3. RESPONSIBILITIES every entry in `responsibilities_json`, in full —
                      the list is not truncated or summarised

  4. APPROVAL         what this position may approve, derived from
     AUTHORITY        `approval_authority_json`: bare permissions, and
                      numeric limits rendered as "up to N"

  5. ESCALATION       where decisions beyond scope go — derived from
                      `reports_to_role_id`. A role with a manager
                      escalates to it; a chain root escalates only
                      critical strategic decisions upward.

  6. CONSTRAINT       the agent is told it operates inside an envelope
     AWARENESS        and that the envelope is enforced, not advisory

  Sections 2 and 4 are omitted when their fields are empty. Section 5
  changes shape depending on whether the reporting edge exists.
```

Read it as: **the fields you fill in are the agent's instructions.** A role whose
`job_description` is blank produces an agent that knows its title, its
responsibilities and its escalation path and nothing about what the job actually
is. A role whose `responsibilities_json` is an empty array produces an agent with
no statement of what it is answerable for.

Two consequences follow, and the second is the one that costs.

**Write the job description for the agent, not for a recruiter.** "Owns the
month-end close, reconciles intercompany balances, and escalates any variance
above the approval threshold to the CFO" is instructions. "Seeking a motivated
finance professional" is not, and it will be carried into the prompt verbatim.

**The failure mode is a structurally perfect organisation full of agents with
nothing to do.** Every unit has a head, every head reports correctly, every
address resolves, every envelope composes — and each agent's prompt is a title and
an escalation path, because the intent fields were left empty during provisioning
and nothing requires them. Nothing errors. The agents respond; they respond
generically. The tell is agent output that could have come from any role in the
organisation.

```python
# The intent fields are the agent's instructions. Fill them at create time.
role = await client.roles.create(
    organization_unit_id=treasury_unit_id,
    title="Treasury Analyst",
    authority_level=2,
    reports_to_role_id=head_of_treasury_id,
    job_description=(
        "Monitors daily cash position across all operating accounts. "
        "Prepares the weekly liquidity forecast. Executes approved "
        "sweeps within the standing limit and refers anything above it."
    ),
    responsibilities_json=[
        "Daily cash position reporting",
        "Weekly liquidity forecast",
        "Execution of approved account sweeps",
    ],
    approval_authority_json={"account_sweep": 250000, "counterparty_onboarding": False},
)
```

## Authority level — what it is, and what it is not

`authority_level` is an integer from 1 to 5.

| level | band     |
| ----- | -------- |
| 1     | Staff    |
| 2     | Manager  |
| 3     | Director |
| 4     | VP       |
| 5     | C-Suite  |

> ⛔ **Authority level does not gate knowledge access. Clearance does.** This is
> the single most consequential misreading of the whole model. A level-1 legal
> secretary can hold secret clearance; a level-5 sales VP may hold only
> restricted. A level-5 role with no clearance sees strictly less than a level-1
> role with one — that is the intended behaviour, not a defect to work around.
> Building a permission model on `authority_level` produces an access policy that
> is well-formed, intuitive, and enforces nothing the platform agrees with.

It is equally important that **authority level does not constrain the reporting
edge at all** — not depth, not direction. Peer reporting between two level-5 roles
is legal. A senior specialist reporting into a junior project lead is legal.
Reporting chains may be arbitrarily deep regardless of the five-value range: a
chain running Chairman → CEO → CFO → Controller → AP Manager → AP Clerk is an
ordinary six-level structure, and the bounded range says nothing about it. Matrix
and dotted-line shapes are first-class. The two real controls on the reporting
edge are cycle prevention and the escalation ceiling below, and neither reads the
parent-versus-child relationship.

What authority level genuinely drives is five things, and each is worth knowing
because each has a visible effect.

**It is a ceiling on what a caller may grant.** A caller cannot create a role, set
a role's authority, or assign a user to a role whose authority sits above the
caller's own. Additionally, a caller may not change the authority level of a role
they are themselves assigned to. Together these close the path of self-promoting
into an existing senior position that somebody else legitimately created — which
is why the rule is expressed as a ceiling on the _caller_ rather than a property
of the role.

**It determines the role agent's behavioural subtype.** Levels 1–3 provision a
`specialist`; levels 4–5 provision a `manager`. That is a statement about the part
the agent plays, not about its permissions.

**It maps one-to-one onto the autonomy posture the agent is provisioned at.**

| authority level | posture              |
| --------------- | -------------------- |
| 1               | `pseudo`             |
| 2               | `supervised`         |
| 3               | `shared_planning`    |
| 4               | `continuous_insight` |
| 5               | `delegated`          |

The mapping fails closed: anything outside 1–5 resolves to `pseudo`, the most
restrictive posture. Because there is no posture field on the role itself, this
mapping is how a provisioning choice about autonomy is expressed —
[10.6](06-role-agents.md) covers what the posture then does, and how it is changed
afterwards through the posture surface rather than by editing the level.

**It is a floor on knowledge-share policies — on the requester side.** A share
policy carries a `min_authority_level`, and a role below it is refused by that
policy. Read the direction carefully: it bounds who may _receive_ under the
policy, not who may author it.

**It tiers emergency approvals and blast-radius controls.** An emergency envelope
widening requires an approver at or above a level set by its duration — up to four
hours needs a Manager, four to twenty-four a Director, twenty-four to
seventy-two a VP. Beyond seventy-two hours it is not an emergency. Kill-switch
scopes are tiered the same way, widening from a single agent through to the whole
estate as the required level rises.

## Vacancy

Roles are **born vacant**. A unit's head role is created with the unit, before
anyone is appointed, and the platform is built to operate that way.
`vacancy_reason` is a closed set of three values, and they are not
interchangeable:

| value                    | means                                                                            |
| ------------------------ | -------------------------------------------------------------------------------- |
| `structural_placeholder` | the platform minted it — the mandatory head role of a new unit, or a coordinator |
| `pending_appointment`    | a real seat awaiting its first occupant                                          |
| `vacated`                | it was filled and the occupant was removed                                       |

The distinction is not bookkeeping. A structural placeholder has no business
holding a clearance provisioned in advance; a seat awaiting its first hire
legitimately may; and a vacated seat's prior clearance was a real decision made
about _that_ seat. Assigning a user clears the reason, because a filled seat has
no vacancy to explain.

> ⛔ **Vacancy is not a trust predicate, an execution predicate, a reachability
> predicate, or a knowledge-access predicate.** `is_vacant` means _no human
> occupies this seat_, and nothing else.

Everything that follows from that is worth stating positively, because the
intuition runs the other way:

- **Every organisational role is a role agent, and the agent is active because the
  ROLE exists** — not because someone is sitting in it. A freshly-built
  organisation is entirely vacant and entirely operational.
- **Autonomy is set by posture, composed with the constraint envelope and the
  unit's ceiling.** Occupancy is not an input to that composition.
- **A superior can task down the tree and reach every role agent beneath.** An
  empty chair in the middle of the structure does not sever the subtree below it.
- **Accountability is stamped per task at issue time.** An autonomous task on a
  vacant role is legitimate precisely _because_ the issuing human carries the
  accountability for it.

**Vacancy has exactly one consequence.** A _supervised_ task needs a human in an
inbox, and an empty seat has none — so the platform re-homes the human half of the
work to the superior. It walks the reporting edge upward, skipping external roles
(which are governance-only and never an anchor) and skipping further vacant seats,
verifying tenancy at every hop, until it reaches an occupied role. It walks up; it
never blocks.

**The failure mode that behaviour prevents is a supervised task parked in an inbox
nobody will ever open.** That is what happens if vacancy is treated as "route it
here anyway" — the task is correctly created, correctly assigned, and invisible.
The symptom is work that is neither refused nor completed, and which shows as
pending indefinitely.

Vacant roles are discoverable: `api:GET /api/v1/organization-roles` filters the
population, and `api:GET /api/v1/organization-roles/without-agents` finds the
narrower and more interesting case — roles that have no delegate agent at all,
which is a provisioning defect rather than an ordinary state.

## The bounds that attach to a role

Two independent limits attach to the same node, and designing as though they were
one is the most common modelling error on the platform.

| bound         | answers                     | created by                         | becomes effective when |
| ------------- | --------------------------- | ---------------------------------- | ---------------------- |
| **envelope**  | what may this role **do**?  | `api:POST /api/v1/role-envelopes`  | it is **activated**    |
| **clearance** | what may this role **see**? | `api:POST /api/v1/role-clearances` | it is **approved**     |

An envelope is authored by a _defining_ role for a _target_ role, and composes
along the reporting chain by **monotonic tightening** — an intersection, never a
union. The structural consequence is worth drawing out: because a target's bounds
are always a subset of its definer's, **you cannot express an escalation by adding
an envelope.** Widening is not something the model can say. If a delegate
genuinely needs to exceed its bounds, the answer is a human decision through the
emergency path, not a second envelope.

A clearance carries its own vetting lifecycle, and the approval requirements rise
with the level requested — from a single approval at the lowest vetted level,
through justification, to multiple approvals and formal vetting at the top. The
requester and the approver must be different people, and that distinctness is
enforced rather than assumed. `api:POST /api/v1/role-clearances/{id}/approve` and
`/{id}/reject` are the decision surface.

> ⛔ **Creating is not granting, in both cases, and the failure is identical.** An
> envelope defaults to draft and enforces nothing until
> `api:POST /api/v1/role-envelopes/{id}/activate`. A clearance lands pending and
> grants nothing until it is approved. A provisioning script that creates fifty of
> something and walks away has produced an organisation that lists as fully
> bounded in every view and enforces nothing. Nothing errors.
> `api:GET /api/v1/governance/envelope-coverage` and
> `api:GET /api/v1/governance/envelope-hydration-status` are the reads that tell
> you the difference between created and in force.

## The role, once

| question                                         | answer                                                                                                         |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| Is a role a person?                              | No — a **position**. The occupant is an attribute.                                                             |
| What does `job_description` do?                  | It becomes the **primary content of the role agent's system prompt**.                                          |
| Are responsibilities summarised into the prompt? | No — carried in **full**.                                                                                      |
| Does `authority_level` gate knowledge access?    | **No.** Clearance does.                                                                                        |
| Does `authority_level` constrain reporting?      | **No** — not depth, not direction, not peers.                                                                  |
| What does it gate?                               | The granting ceiling, agent subtype, provisioned posture, share-policy floor, emergency and kill-switch tiers. |
| Are new roles occupied?                          | No — **born vacant**, and fully operational that way.                                                          |
| What does vacancy change?                        | Exactly one thing: a supervised task routes to the superior.                                                   |
| Where does clearance live?                       | On a separate clearance object, not on the role.                                                               |
| Where does posture live?                         | On the agent; the role's authority level sets what it is provisioned at.                                       |
| When does an envelope start enforcing?           | On **activation**, not on creation.                                                                            |

---

_Next: [10.5 — Trust chains and delegation](05-trust-chains-and-delegation.md)_
