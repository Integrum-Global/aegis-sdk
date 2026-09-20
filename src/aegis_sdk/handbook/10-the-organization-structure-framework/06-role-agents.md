# 10.6 — Role agents

Every organisational role is a role agent. Not _may have_ one, not _gets one when
someone is hired_ — the agent exists and is active because the **role** exists.
This chapter is that agent: when it comes into being, what it is provisioned
with, how much autonomy it holds and who decides that, and what actually stands
between it and an action.

The framing to correct first, because it shapes everything after it: a role agent
is not a robot assigned to help an employee. **It is the position, acting.** The
CFO's role agent acts as the CFO — inside the CFO's envelope, at the CFO's
clearance, under a delegation from the CEO's agent, and with the CFO position's
job description as its instructions. Whether a human currently occupies that
position is a separate question, and it is not this one.

**The single idea to carry out: the agent's authority comes from the position,
its instructions come from the position, and its autonomy comes from posture — so
provisioning an agent is not a step after describing the organisation, it is a
consequence of it.**

## When an agent comes into being

A role's agent is created with the role. `auto_generate_agent` defaults on, and a
role created through `api:POST /api/v1/organization-roles` arrives with its agent
provisioned and bound. The same happens for the head role the platform mints when
you create a unit — so a freshly-created department has a head role, that head
role has an agent, and the agent is active, all before anyone is appointed.

Two things modify that.

**External roles get no operational agent.** A role with `is_external` set — a
board member, an advisor, outside counsel — has `auto_generate_agent` forced off.
External roles participate in governance: they approve, observe and audit. They do
not execute work, and the platform enforces that rather than relying on you to
remember it. **The failure mode that prevents is a board seat that can execute** —
which, in every listing, looks exactly like an ordinary senior role.

**Bulk provisioning has its own call.**
`api:POST /api/v1/organization-builder/generate-agents` provisions agents across a
structure, which is the path for an organisation imported or compiled in one pass
rather than built role by role.

⛔ **The agent is created ACTIVE, and a vacant role's agent is active too.**
Vacancy is not an agent-lifecycle predicate
([10.4](04-roles-authority-and-intent.md)). A role agent that waited for a hire
would mean a freshly-built organisation — which is entirely vacant by construction
— was entirely unable to act, which is the opposite of the intended behaviour.

⚠ **`active` is a lifecycle state, not a grant.** An active agent is one that
exists and is eligible to be reached; it is not one that may do anything it likes.
Everything it may actually do is decided by the envelope, the posture, the
clearance and the chain, every time it acts. Reading `status: active` as "this
agent is permitted" is the single most common overreading of this field.

## The binding

**A role holds at most one delegate agent**, which is why the link operations take
the role rather than the agent as their subject:
`api:POST /api/v1/organization-roles/{id}/link-agent` and the bodyless
`api:POST /api/v1/organization-roles/{id}/unlink-agent`. The role carries the
binding as `shadow_agent_id`.

**Linking does not widen anything.** The agent acts inside the envelope the role
already carries, so the link is a _naming_ of who acts as this position — not a
grant of anything. That is worth internalising because it inverts the usual
instinct: you do not give an agent permissions, you attach it to a position that
already has bounds.

`api:GET /api/v1/organization-roles/without-agents` is the read that finds roles
with no agent bound. On a well-provisioned organisation the result should be the
external roles and nothing else; anything else on that list is a provisioning
defect, and it presents as a position that exists, addresses correctly, has an
envelope, and never responds.

| read                                                | answers                                   |
| --------------------------------------------------- | ----------------------------------------- |
| `api:GET /api/v1/delegate-agents`                   | every delegate agent in the organisation  |
| `api:GET /api/v1/delegate-agents/for-unit/{id}`     | the agents acting for roles in one unit   |
| `api:GET /api/v1/delegate-agents/{id}/trust-chain`  | the delegation this agent is acting under |
| `api:GET /api/v1/delegate-agents/{id}/health`       | whether it is currently fit to act        |
| `api:GET /api/v1/delegate-agents/{id}/activity`     | what it has been doing                    |
| `api:GET /api/v1/delegate-agents/dashboard-summary` | the population at a glance                |

`api:POST /api/v1/delegate-agents/{id}/deactivate` and `/{id}/activate` are the
lifecycle controls, and `api:PATCH /api/v1/delegate-agents/{id}` amends one.

## What the agent is provisioned with

Four things are derived from the role at provisioning time. Three of them are
derived from `authority_level`, which is why that field matters far more than its
"informational" description suggests.

```text
FROM THE ROLE, TO THE AGENT

  title + authority band ──────▶ IDENTITY        "You are the {title} agent,
                                                  operating {authority band}."

  job_description ─────────────▶ INSTRUCTIONS    the bulk of the system prompt
  responsibilities_json ───────▶ (in full)
  approval_authority_json ─────▶ what it may approve
  reports_to_role_id ──────────▶ where it escalates

  authority_level ─────────────▶ SUBTYPE         1-3 specialist · 4-5 manager
                   └───────────▶ POSTURE         the autonomy it starts at
                   └───────────▶ CEILINGS        emergency + blast-radius tiers

  constraint_template_id ──────▶ ENVELOPE        what it may do
  the role's clearance ────────▶ VISIBILITY      what it may see
  the reporting edge ──────────▶ TRUST CHAIN     whose authority it acts under
```

Read it as: nothing here is configured on the agent. Every one of these is read
from the position. An agent whose behaviour is wrong is almost always a role whose
fields are wrong, and editing the agent is treating the symptom.

[10.4](04-roles-authority-and-intent.md) covers the prompt assembly in detail —
the short version is that `job_description` is the primary content and
`responsibilities_json` is carried in whole.

## Type, subtype and status

Three enums describe an agent and they answer genuinely different questions.

**Type** (`sdk:aegis_sdk.AgentType`) is what the agent _is_ from a lifecycle
standpoint, and the vocabulary is wider than the create surface — which matters,
because you will see values in listings you cannot create:

| creatable through the API            | minted by the platform itself     |
| ------------------------------------ | --------------------------------- |
| `chat`, `task`, `pipeline`, `custom` | `shadow`, `pseudo`, `tool`, `esa` |

Presence in the right-hand column is not something you provision; those agents
come into existence because some _other_ object did. A tool agent is created by
registering a tool. A role's delegate agent is created by the role. **Finding an
agent in a listing you never made is normal**, and it does not mean someone
provisioned it behind your back.

**Subtype** (`sdk:aegis_sdk.AgentSubtype`) is behavioural — the part the agent
plays. Role agents are provisioned as `specialist` at authority levels 1–3 and
`manager` at 4–5; the wider enum also carries `esa`, `pseudo` and `governance`.

**Status** (`sdk:aegis_sdk.AgentStatus`) is the lifecycle: `draft`, `active`,
`archived`, `deprecated`, `suspended`, `revoked`. Treat `suspended` and `revoked`
as reachable rather than exotic — an agent is transitioned to `suspended` by the
platform when something goes wrong, which is precisely the moment your code is
running and reading it.

## Posture — the autonomy dial

Posture is how much of its delegated authority an agent may exercise unaided. The
five values are CARE-aligned and lowercase:

| posture              | what it means for the agent            | provisioned at authority |
| -------------------- | -------------------------------------- | ------------------------ |
| `pseudo`             | acts only as a proxy for a human       | 1                        |
| `supervised`         | acts, with a human in the loop         | 2                        |
| `shared_planning`    | plans jointly, executes agreed work    | 3                        |
| `continuous_insight` | acts, with continuous human visibility | 4                        |
| `delegated`          | acts within its envelope, unaided      | 5                        |

**The mapping from authority to posture is one-to-one, and it fails closed.**
Anything outside 1–5 resolves to `pseudo`, the most restrictive value. Because
there is no posture field on the role itself, this mapping is how a provisioning
decision about autonomy gets expressed: the authority band you set is the posture
the agent starts at.

Posture is then managed on the agent, through its own surface:

| call                                                             | purpose                                     |
| ---------------------------------------------------------------- | ------------------------------------------- |
| `api:GET /api/v1/agents/{id}/trust-posture`                      | what posture is this agent at?              |
| `api:PUT /api/v1/agents/{id}/trust-posture`                      | set it                                      |
| `api:GET /api/v1/agents/{id}/trust-posture/evaluate`             | what does the platform assess it should be? |
| `api:GET /api/v1/agents/{id}/trust-posture/evidence`             | on what evidence                            |
| `api:GET /api/v1/agents/{id}/trust-posture/history`              | how it has moved                            |
| `api:GET /api/v1/agents/{id}/trust-posture/upgrade-eligibility`  | may it move up yet?                         |
| `api:POST /api/v1/agents/{id}/trust-posture/request-upgrade`     | ask                                         |
| `api:POST /api/v1/agents/{id}/trust-posture/approve` / `/reject` | a human decides                             |
| `api:GET /api/v1/posture/pending-approvals`                      | everything currently awaiting a decision    |

`sdk:aegis_sdk.TrustPostureModule` wraps these and `sdk:aegis_sdk.TrustPosture` is
the typed value. **Posture progression is a human decision with evidence behind
it** — the evaluate and evidence reads exist so the decision is made against a
record rather than a feeling, and the upgrade path is a request plus an approval
rather than a write.

⚠ **Raising `authority_level` to raise an agent's autonomy is the wrong lever.**
Authority level sets what the agent was _provisioned_ at; the posture surface is
what moves it afterwards. Editing the band to move autonomy also moves the
granting ceiling, the subtype, the emergency-approval tier and the kill-switch
scope — four unrelated changes to make one, and every one of them permanent until
someone notices.

## The ceiling cascades, and the effective value is a minimum

An agent's posture is not the whole story, because the unit it sits in carries a
ceiling and that ceiling cascades down the containment tree.

```text
EFFECTIVE POSTURE = min( the agent's posture,
                         the unit's EFFECTIVE ceiling,
                         the posture selected for this task )

   where the unit's effective ceiling is itself
      min( this unit's declared ceiling, its parent's effective ceiling )
```

Read it as: **a child unit can never exceed its parent's ceiling, whatever its own
value reads.** Setting a permissive ceiling on a leaf beneath a restrictive branch
changes nothing, and nothing tells you that.

`api:GET /api/v1/organization-units/{id}/posture-ceiling` returns both the
declared value and the effective one. **Read the effective one.** The declared
value is half the picture and it is the half that looks authoritative.

⛔ **The setter, `api:PUT /api/v1/organization-units/{id}/posture-ceiling`, has an
asymmetry worth carrying into your code: omitting the argument leaves the ceiling
unchanged, while passing an explicit null clears it — and a cleared ceiling
widens what the unit may do.** Those two are one keyword apart at the call site
and opposite in effect. The symptom of getting it wrong is agents in a subtree
operating at a higher autonomy than anyone granted, with no event marking when it
changed.

## What actually stands between an agent and an action

An active agent with a valid chain is still checked, every time. Six conditions
hold, and the list is worth having explicitly because "the agent is active" covers
none of them.

| condition                          | what it means                                                     |
| ---------------------------------- | ----------------------------------------------------------------- |
| **the organisation is active**     | the tenant itself is not suspended                                |
| **a trust chain exists**           | the agent holds a delegation at all                               |
| **that chain is usable**           | active, unexpired, not revoked or suspended                       |
| **the role resolves, same-tenant** | the position the agent acts as is real and belongs to this tenant |
| **the posture permits it**         | the effective posture is not one that denies this action          |
| **the budget is not exhausted**    | the financial dimension of the envelope still has room            |

And over all of it, the **constraint envelope** bounds what the action may be at
all — across the five constraint dimensions: financial, operational, temporal,
data access and communication.

`api:GET /api/v1/delegate-agents/{id}/health` is the aggregate read, and
`api:GET /api/v1/trust/agents/{id}/trust-context` carries the chain-side half with
its warnings ([10.5](05-trust-chains-and-delegation.md)).

```python
# "Is this agent fit to act?" is not a status read.
health = await client.delegate_agents.get_health(agent_id=analyst_agent_id)
context = await client.trust.get_agent_trust_context(agent_id=analyst_agent_id)

fit = (
    health["status"] == "healthy"
    and not context["has_warnings"]
)
```

## Five ways a role agent disappoints you

Each looks like a different problem and each is the same class: something read
from the position was wrong or absent.

| symptom                                                 | actual cause                                                         |
| ------------------------------------------------------- | -------------------------------------------------------------------- |
| the agent responds generically, like any other role     | `job_description` and `responsibilities_json` were left empty        |
| the agent refuses work it clearly should do             | the envelope was created but never **activated**                     |
| the agent sees less than expected                       | the clearance was created but never **approved**                     |
| the agent is more autonomous than intended in a subtree | a unit ceiling was **cleared** rather than left unchanged            |
| the position exists but never responds at all           | no agent bound — `api:GET /api/v1/organization-roles/without-agents` |

**None of these produces an error.** That is the shape of the whole chapter: the
role agent is derived from the position, so a position described incompletely
yields an agent that behaves incompletely, correctly, and without complaint.

## Role agents, once

| question                                 | answer                                                       |
| ---------------------------------------- | ------------------------------------------------------------ |
| Which roles have agents?                 | All of them, except `is_external` roles.                     |
| When is the agent created?               | With the role — and it is created **active**.                |
| Does a vacant role have an active agent? | Yes. Vacancy is not an agent predicate.                      |
| How many agents per role?                | At most one.                                                 |
| Does linking an agent grant anything?    | No — it names who acts as the position.                      |
| Where do its instructions come from?     | The role's `job_description` and `responsibilities_json`.    |
| What sets its starting posture?          | `authority_level`, one-to-one, failing closed to `pseudo`.   |
| How is posture changed afterwards?       | The posture surface — request, evidence, human approval.     |
| What does the unit contribute?           | A ceiling that cascades; effective posture is a **minimum**. |
| Does `status: active` mean permitted?    | No. It means eligible to be reached.                         |

---

_Next: [10.7 — Re-orgs, bridges and workspaces](07-re-orgs-bridges-and-workspaces.md)_
