# 08.5 — Governance and trust

This chapter enumerates **what bounds everything else**. It is the chapter to
read if you are evaluating Aegis against a governance requirement, because almost
every requirement that sounds like it is about agents turns out to be about the
controls on agents, and they are all here.

The controls are not one mechanism with several settings. They are **five
independent gates**, each answering a different question, and a call must pass
all of them:

| gate            | answers                                                 | catalogued in                                  |
| --------------- | ------------------------------------------------------- | ---------------------------------------------- |
| **Permission**  | May this principal call this operation?                 | [08.2](02-organization-and-identity.md) — RBAC |
| **Trust chain** | Does this agent hold delegated authority at all?        | here — trust chains                            |
| **Posture**     | How autonomously may it act?                            | here — postures                                |
| **Envelope**    | Within what financial, temporal and operational bounds? | here — envelopes                               |
| **Clearance**   | May it see this classification of data?                 | here + [08.6](06-knowledge-and-data.md)        |

**A refusal names one gate, and fixing a different one changes nothing.** That is
the single most useful thing to carry out of this chapter: when a call is
refused, establish which gate refused it before adjusting anything.
[02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
and [06.4](../06-architecture/04-trust-and-the-audit-spine.md) teach the model;
this is the surface.

## Trust chains

The spine. A trust chain records that authority was delegated from a human
origin, through roles, to an agent — and every act an agent takes is attributable
back along it. An agent with no chain has no authority to do anything.

| capability                   | what it does                                                   |
| ---------------------------- | -------------------------------------------------------------- |
| **Establish**                | Create a chain from an authority to an agent                   |
| **List / get**               | Enumerate and address chains                                   |
| **Verify**                   | Check a chain is intact and valid right now                    |
| **Delegation path**          | The full path from origin to this agent                        |
| **Summary**                  | One chain's rolled-up state                                    |
| **Agent trust context**      | Everything the platform knows about one agent's trust position |
| **Revoke**                   | Withdraw a chain                                               |
| **Revoke cascade**           | Withdraw it and everything that depends on it                  |
| **Revoke by human**          | Withdraw everything traceable to one human origin              |
| **Revocation impact**        | What a revocation would affect, before you do it               |
| **Incomplete jobs / resume** | Find and finish a revocation that did not complete             |
| **Suspend / reinstate**      | Pause a chain without destroying it                            |
| **Delegate**                 | Extend authority down the chain                                |
| **Revoke delegation**        | Withdraw one link rather than the whole chain                  |

Entry points: `sdk:aegis_sdk.trust.chains.ChainsModule`,
`sdk:aegis_sdk.trust.delegations.DelegationsModule` and
`sdk:aegis_sdk.trust.revocation.RevocationModule`.

Operations: `api:POST /api/v1/trust/establish` · `api:GET /api/v1/trust/chains` ·
`api:GET /api/v1/trust/chains/{id}` ·
`api:GET /api/v1/trust/chains/{id}/delegation-path` ·
`api:GET /api/v1/trust/chains/{id}/summary` · `api:POST /api/v1/trust/verify` ·
`api:POST /api/v1/trust/delegate` ·
`api:POST /api/v1/trust/revoke-delegation` · `api:POST /api/v1/trust/revoke` ·
`api:POST /api/v1/trust/revoke/{id}/cascade` ·
`api:POST /api/v1/trust/revoke/by-human/{human_id}` ·
`api:GET /api/v1/trust/revoke/{id}/impact` ·
`api:GET /api/v1/trust/revoke/jobs/incomplete` ·
`api:POST /api/v1/trust/revoke/jobs/{job_id}/resume` ·
`api:GET /api/v1/trust/agents/{agent_id}/trust-context`

```python
chain = await client.trust.chains.establish(
    authority_id=cfo_authority_id,
    agent_id=agent["id"],
)
verdict = await client.trust.chains.verify(chain_id=chain["id"])

# Always ask before you cascade
impact = await client.trust.chains.analyze_revocation_impact(chain_id=chain["id"])
if impact["affected_agent_count"] < 50:
    await client.trust.revocation.revoke(chain_id=chain["id"], cascade=True)
```

> ⛔ **Measure the blast radius before a cascade revocation.**
> `api:GET /api/v1/trust/revoke/{id}/impact` exists because a cascade from high
> in the tree can silently stop every agent beneath it. The symptom is not an
> error — it is an organisation where nothing executes and every agent reports
> valid configuration, because the configuration _is_ valid and the authority
> behind it is gone.

**A revocation that does not complete leaves a partial state.**
`api:GET /api/v1/trust/revoke/jobs/incomplete` is how you find it and
`api:POST /api/v1/trust/revoke/jobs/{job_id}/resume` is how you finish it. Check
this after any large cascade: a half-revoked tree has some agents stopped and
some still running on authority you intended to withdraw.

## Authorities

The origin points of trust. An authority is the organisational source a chain
descends from.

| capability          | what it does                               |
| ------------------- | ------------------------------------------ |
| **Create / update** | Define an authority                        |
| **List / get**      | Enumerate them                             |
| **Deactivate**      | Retire one                                 |
| **Agents**          | Every agent descending from this authority |
| **Display views**   | Presentation-shaped views for a console    |

Entry point: `sdk:aegis_sdk.trust.authorities.AuthoritiesModule`.

Operations: `api:POST /api/v1/trust/authorities` ·
`api:GET /api/v1/trust/authorities` ·
`api:GET /api/v1/trust/authorities/{id}` ·
`api:PATCH /api/v1/trust/authorities/{id}` ·
`api:POST /api/v1/trust/authorities/{id}/deactivate` ·
`api:GET /api/v1/trust/authorities/{id}/agents` ·
`api:GET /api/v1/trust/authorities/ui` ·
`api:GET /api/v1/trust/authorities/ui/{id}`

## Postures — how autonomously an agent may act

The CARE posture gradient. Five levels, lowercase, and each one is a statement
about how much a human stays in the loop.

| posture              | what it means                                             |
| -------------------- | --------------------------------------------------------- |
| `pseudo`             | Not an autonomous actor — a human in an agent-shaped slot |
| `supervised`         | Acts, but a human reviews before anything takes effect    |
| `shared_planning`    | Plans with a human; executes the agreed plan              |
| `continuous_insight` | Acts autonomously with continuous human visibility        |
| `delegated`          | Acts autonomously within its envelope                     |

Posture is not set once and left. It is **progressed** — an agent earns a higher
posture by accumulating evidence, and the platform evaluates whether it is
eligible.

| capability                      | what it does                                        |
| ------------------------------- | --------------------------------------------------- |
| **Get**                         | One agent's current posture                         |
| **Update**                      | Set it directly                                     |
| **History**                     | Every posture this agent has held                   |
| **Evaluate progression**        | Whether it currently qualifies for a higher posture |
| **Upgrade eligibility**         | The eligibility answer on its own                   |
| **Request upgrade**             | Ask for a promotion, raising an approval            |
| **Pending approvals**           | Posture changes awaiting a human                    |
| **Approve / reject transition** | Decide one                                          |
| **Evidence**                    | What supports the current posture                   |
| **Metrics**                     | The measures progression is evaluated against       |
| **Override**                    | Set a posture outside the normal progression        |
| **Posture ceiling**             | The cap a unit imposes on everything beneath it     |

Entry points: `sdk:aegis_sdk.trust.postures.PosturesModule` and
`sdk:aegis_sdk.modules.trust_posture.TrustPostureModule`.

Operations: `api:GET /api/v1/agents/{id}/trust-posture` ·
`api:PUT /api/v1/agents/{id}/trust-posture` ·
`api:GET /api/v1/agents/{id}/trust-posture/history` ·
`api:GET /api/v1/agents/{id}/trust-posture/evaluate` ·
`api:GET /api/v1/agents/{id}/trust-posture/upgrade-eligibility` ·
`api:GET /api/v1/agents/{id}/trust-posture/evidence` ·
`api:GET /api/v1/agents/{id}/trust-posture/metrics` ·
`api:GET /api/v1/agents/{id}/trust-posture/pending` ·
`api:POST /api/v1/agents/{id}/trust-posture/request-upgrade` ·
`api:POST /api/v1/agents/{id}/trust-posture/approve` ·
`api:POST /api/v1/agents/{id}/trust-posture/reject` ·
`api:GET /api/v1/posture/pending-approvals` ·
`api:GET /api/v1/organization-units/{id}/posture-ceiling` ·
`api:PUT /api/v1/organization-units/{id}/posture-ceiling`

```python
posture = await client.trust.postures.get(agent_id=agent["id"])
eligibility = await client.trust_posture.check_upgrade_eligibility(agent_id=agent["id"])

if eligibility["eligible"]:
    await client.trust_posture.request_upgrade(
        agent_id=agent["id"],
        target_posture="continuous_insight",
    )
```

> ⚠ **A unit's posture ceiling silently caps every agent beneath it.** An agent
> set to `delegated` inside a unit ceilinged at `supervised` operates as
> `supervised`, and its own posture field still reads `delegated`. The agent's
> record is not wrong — the effective posture is the minimum of the two, and only
> the ceiling call tells you what is actually in force.

## Envelopes and constraints — the five dimensions

An envelope bounds what an actor may do, across five dimensions:

| dimension         | bounds                                |
| ----------------- | ------------------------------------- |
| **Financial**     | Spend, commitments, transaction size  |
| **Operational**   | Which actions, how many, against what |
| **Temporal**      | When, and for how long                |
| **Data Access**   | Which data, at which classification   |
| **Communication** | Who and what it may talk to           |

Envelopes compose down the hierarchy and **tighten monotonically**: a child can
never be wider than its parent, and the effective envelope is the intersection of
every envelope from the origin down.

| capability                | what it does                                                    |
| ------------------------- | --------------------------------------------------------------- |
| **Role envelopes**        | Create, get, list, update, delete the standing bounds on a role |
| **Activate / suspend**    | Put a role envelope into or out of force                        |
| **Agent constraints**     | Read and set the bounds on one agent                            |
| **Effective constraints** | The composed result — what is actually in force                 |
| **Inherited constraints** | What this agent gets from above                                 |
| **Validate**              | Check a proposed constraint set before applying it              |
| **Organisation defaults** | The baseline every new actor starts from                        |
| **Envelope defaults**     | The platform's own default shape                                |
| **Gradient rules**        | How constraint breaches map onto the decision gradient          |

Entry points: `sdk:aegis_sdk.standup.envelopes.RoleEnvelopesModule` and
`sdk:aegis_sdk.modules.trust_posture.TrustPostureModule`.

Operations: `api:POST /api/v1/role-envelopes` ·
`api:GET /api/v1/role-envelopes` · `api:GET /api/v1/role-envelopes/{id}` ·
`api:PUT /api/v1/role-envelopes/{id}` ·
`api:DELETE /api/v1/role-envelopes/{id}` ·
`api:POST /api/v1/role-envelopes/{id}/activate` ·
`api:POST /api/v1/role-envelopes/{id}/suspend` ·
`api:GET /api/v1/constraints/agents/{agent_id}` ·
`api:PUT /api/v1/constraints/agents/{agent_id}` ·
`api:GET /api/v1/constraints/agents/{agent_id}/effective` ·
`api:GET /api/v1/constraints/agents/{agent_id}/inherited` ·
`api:POST /api/v1/constraints/agents/{agent_id}/validate` ·
`api:GET /api/v1/constraints/gradient-rules` ·
`api:GET /api/v1/constraints/organizations/{org_id}/defaults` ·
`api:PUT /api/v1/constraints/organizations/{org_id}/defaults` ·
`api:GET /api/v1/envelopes/defaults`

```python
envelope = await client.role_envelopes.create(
    organization_role_id=controller_role_id,
    financial={"max_amount_cents": 500_000, "period": "month"},
    temporal={"business_hours_only": True},
    data_access={"max_classification": "confidential"},
)
await client.trust_posture.activate_role_envelope(envelope_id=envelope["id"])

effective = await client.trust_posture.get_effective_constraints(agent_id=agent["id"])
```

> ⛔ **A created envelope is not an active envelope.** `create` records it;
> `activate` puts it in force. A provisioning script that creates envelopes and
> never activates them produces an organisation that looks fully bounded in every
> listing and enforces nothing. Nothing errors.

**Read the effective constraints, never the agent's own.** The agent-level
constraint call returns what was set _on that agent_; the effective call returns
the intersection of everything above it. They differ whenever any ancestor
carries a tighter bound, which is the normal case in a real hierarchy — and the
difference is exactly the part that will refuse a call you expected to succeed.

## Clearances — what an actor may see

Clearance is the Data Access dimension made explicit, and it is independent of
authority. A junior role can hold a high clearance; a senior one can hold a low
one.

| capability                   | what it does                     |
| ---------------------------- | -------------------------------- |
| **Create / update / delete** | Manage a role's clearance record |
| **List / get**               | Enumerate clearances             |
| **Approve / reject**         | Decide a requested clearance     |

Entry point: `sdk:aegis_sdk.modules.trust_posture.TrustPostureModule`.

Operations: `api:POST /api/v1/role-clearances` ·
`api:GET /api/v1/role-clearances` · `api:GET /api/v1/role-clearances/{id}` ·
`api:PUT /api/v1/role-clearances/{id}` ·
`api:DELETE /api/v1/role-clearances/{id}` ·
`api:POST /api/v1/role-clearances/{id}/approve` ·
`api:POST /api/v1/role-clearances/{id}/reject`

```python
clearance = await client.trust_posture.create_role_clearance(
    organization_role_id=analyst_role_id,
    max_classification="secret",
    compartments=["treasury"],
)
await client.trust_posture.approve_role_clearance(clearance_id=clearance["id"])
```

**Posture caps clearance.** An agent at `supervised` does not reach `secret` data
however cleared its role is — the effective clearance is the minimum of the
role's clearance and the posture's ceiling. Raising the clearance on a
low-posture agent changes nothing, and it is the most common wasted fix in this
area.

## Access policy

Attribute-based policy over resources, separate from RBAC's operation-level
permissions.

| capability                   | what it does                                      |
| ---------------------------- | ------------------------------------------------- |
| **Create / update / delete** | Author a policy                                   |
| **List / get**               | Enumerate policies                                |
| **Evaluate**                 | Ask what a policy set decides for a given request |
| **Assign / unassign**        | Attach a policy to a principal                    |
| **User policies**            | Which policies apply to one user                  |
| **References**               | What a policy refers to                           |
| **Validate conditions**      | Check a policy's conditions are well-formed       |
| **Validate conflicts**       | Find policies that contradict one another         |
| **Resolve conflict**         | Decide between conflicting policies               |

Entry point: `sdk:aegis_sdk.modules.knowledge_govern.KnowledgeGovernModule`.

Operations: `api:POST /api/v1/policies` · `api:GET /api/v1/policies` ·
`api:GET /api/v1/policies/{id}` · `api:PUT /api/v1/policies/{id}` ·
`api:DELETE /api/v1/policies/{id}` · `api:POST /api/v1/policies/evaluate` ·
`api:POST /api/v1/policies/{id}/assign` ·
`api:DELETE /api/v1/policies/assignments/{id}` ·
`api:GET /api/v1/policies/user/{user_id}` ·
`api:GET /api/v1/policies/{id}/references` ·
`api:POST /api/v1/policies/validate-conditions` ·
`api:POST /api/v1/policies/validate-conflicts` ·
`api:POST /api/v1/policies/resolve-conflict`

**Run `validate-conflicts` after adding a policy, not when something breaks.**
Two policies that contradict resolve deterministically but not necessarily the
way either author intended, and the symptom is an access decision nobody can
explain from reading either policy alone.

## Policy clauses and compilation

The declarative layer above policy: clauses are authored, compiled into a
coherent policy set, previewed, and applied as a unit.

| capability               | what it does                                      |
| ------------------------ | ------------------------------------------------- |
| **List / create clause** | Author policy clauses                             |
| **Retract clause**       | Withdraw one                                      |
| **Compile**              | Turn the clause set into an applicable policy set |
| **List / get runs**      | The compilation history                           |
| **Apply run**            | Put a compiled run into force                     |

Entry point: `sdk:aegis_sdk.modules.governance.GovernanceModule`.

Operations: `api:GET /api/v1/policy-clauses` ·
`api:POST /api/v1/policy-clauses` ·
`api:POST /api/v1/policy-clauses/{id}/retract` ·
`api:POST /api/v1/compilation-runs` · `api:GET /api/v1/compilation-runs` ·
`api:GET /api/v1/compilation-runs/{id}` ·
`api:POST /api/v1/compilation-runs/{id}/apply`

```python
run = await client.governance.compile_policy_clauses()
detail = await client.governance.get_compilation_run(run_id=run["id"])
await client.governance.apply_compilation_run(run_id=run["id"])
```

**Compile and apply are separate, as everywhere else in the platform.** A
compilation run that is never applied is a policy set that exists and governs
nothing.

## Governance explanation

The surface that answers _why_ — indispensable when a refusal is not obvious, and
the thing to reach for before changing any control.

| capability                    | what it does                                          |
| ----------------------------- | ----------------------------------------------------- |
| **Explain access**            | Why a principal can or cannot reach a resource        |
| **Explain envelope**          | How an effective envelope was composed, and from what |
| **Describe address**          | What a positional address refers to                   |
| **Envelope coverage**         | Which roles have envelopes and which do not           |
| **Envelope hydration status** | Whether the envelope data is fully loaded             |
| **Probe corrupted roles**     | Find roles whose governance data is inconsistent      |

Entry point: `sdk:aegis_sdk.modules.governance_explain.GovernanceExplainModule`.

Operations: `api:POST /api/v1/governance/explain-access` ·
`api:POST /api/v1/governance/explain-envelope` ·
`api:POST /api/v1/governance/describe-address` ·
`api:GET /api/v1/governance/envelope-coverage` ·
`api:GET /api/v1/governance/envelope-hydration-status` ·
`api:GET /api/v1/governance/probe-corrupted-roles`

```python
why = await client.governance_explain.explain_access(
    principal_id=agent["id"],
    resource_id=knowledge_item_id,
    action="read",
)
# why names the gate that decided, not just the verdict

coverage = await client.governance_explain.envelope_coverage()
```

**`envelope_coverage` is the query to run after standing an organisation up.** It
reports which roles carry no envelope — and a role with no envelope is not a role
with no bounds, it is a role whose composition has a gap, which fails closed and
produces refusals that look arbitrary.

## Bridges — authorised cross-boundary interaction

Isolation domains stop units seeing one another. A bridge is the governed
exception: an explicit, envelope-bounded channel between two roles. Three kinds,
by how long they last and how they are approved.

| kind                | lasts                              | approved by                       |
| ------------------- | ---------------------------------- | --------------------------------- |
| **Standing bridge** | Indefinitely, with periodic review | Authorisation, then activation    |
| **Scoped bridge**   | For one workspace or objective     | Approval, with expiry and renewal |
| **Ad-hoc bridge**   | One interaction                    | Approval per instance             |

**A bridge's envelope is the intersection of both sides — the most restrictive
wins.** Two roles bridged together do not gain each other's reach; each is
bounded by whichever side is tighter.

### Standing bridges

| capability                   | what it does                                    |
| ---------------------------- | ----------------------------------------------- |
| **Create / update / delete** | Standard lifecycle                              |
| **List / get / for unit**    | Enumerate, including per unit                   |
| **Authorize**                | Approve the bridge's existence                  |
| **Activate**                 | Put it into force                               |
| **Suspend / revoke**         | Pause or end it                                 |
| **Check interaction**        | Ask whether a specific interaction is permitted |
| **Submit review**            | Record the periodic review                      |
| **Overdue**                  | Bridges whose review has lapsed                 |

Entry point: `sdk:aegis_sdk.modules.bridges.StandingBridgesModule`.

Operations: `api:POST /api/v1/standing-bridges` ·
`api:GET /api/v1/standing-bridges` ·
`api:GET /api/v1/standing-bridges/{id}` ·
`api:PUT /api/v1/standing-bridges/{id}` ·
`api:DELETE /api/v1/standing-bridges/{id}` ·
`api:GET /api/v1/standing-bridges/for-unit/{unit_id}` ·
`api:GET /api/v1/standing-bridges/overdue` ·
`api:POST /api/v1/standing-bridges/{id}/authorize` ·
`api:POST /api/v1/standing-bridges/{id}/activate` ·
`api:POST /api/v1/standing-bridges/{id}/suspend` ·
`api:POST /api/v1/standing-bridges/{id}/revoke` ·
`api:POST /api/v1/standing-bridges/{id}/check-interaction` ·
`api:POST /api/v1/standing-bridges/{id}/review`

### Scoped bridges

| capability                        | what it does                   |
| --------------------------------- | ------------------------------ |
| **Create / update / delete**      | Standard lifecycle             |
| **List / get**                    | Enumerate                      |
| **For workspace / for objective** | Bridges scoped to one context  |
| **Approve / reject**              | Decide it                      |
| **Add / remove unit**             | Change which units participate |
| **Participants**                  | Who is in it                   |
| **Extend / renew**                | Push out the expiry            |
| **Complete / cancel / expire**    | End it                         |

Entry point: `sdk:aegis_sdk.modules.bridges.ScopedBridgesModule`.

Operations: `api:POST /api/v1/scoped-bridges` ·
`api:GET /api/v1/scoped-bridges` · `api:GET /api/v1/scoped-bridges/{id}` ·
`api:PUT /api/v1/scoped-bridges/{id}` ·
`api:DELETE /api/v1/scoped-bridges/{id}` ·
`api:GET /api/v1/scoped-bridges/for-workspace/{workspace_id}` ·
`api:GET /api/v1/scoped-bridges/for-objective/{objective_id}` ·
`api:GET /api/v1/scoped-bridges/{id}/participants` ·
`api:POST /api/v1/scoped-bridges/{id}/approve` ·
`api:POST /api/v1/scoped-bridges/{id}/reject` ·
`api:POST /api/v1/scoped-bridges/{id}/add-unit` ·
`api:DELETE /api/v1/scoped-bridges/{id}/participants/{participant_id}` ·
`api:POST /api/v1/scoped-bridges/{id}/extend` ·
`api:POST /api/v1/scoped-bridges/{id}/renew` ·
`api:POST /api/v1/scoped-bridges/{id}/complete` ·
`api:POST /api/v1/scoped-bridges/{id}/cancel` ·
`api:POST /api/v1/scoped-bridges/{id}/expire`

### Ad-hoc bridges

| capability           | what it does                      |
| -------------------- | --------------------------------- |
| **For unit**         | Ad-hoc bridges touching one unit  |
| **Pending for**      | Awaiting one principal's decision |
| **Approve / reject** | Decide it                         |
| **Activate**         | Put it into force                 |

Entry point: `sdk:aegis_sdk.modules.bridges.AdHocBridgesModule`.

Operations: `api:GET /api/v1/ad-hoc-bridges/for-unit/{unit_id}` ·
`api:GET /api/v1/ad-hoc-bridges/pending-for/{principal_id}` ·
`api:POST /api/v1/ad-hoc-bridges/{id}/approve` ·
`api:POST /api/v1/ad-hoc-bridges/{id}/reject` ·
`api:POST /api/v1/ad-hoc-bridges/{id}/activate`

```python
bridge = await client.bridges.standing.create(
    role_a_id=treasury_lead_id,
    role_b_id=risk_lead_id,
    purpose="Daily liquidity position exchange",
)
await client.bridges.standing.authorize(bridge_id=bridge["id"])
await client.bridges.standing.activate(bridge_id=bridge["id"])

overdue = await client.bridges.standing.overdue()
```

**Authorise and activate are two steps for standing bridges**, and an authorised
but inactive bridge passes every existence check while carrying no traffic.
`api:GET /api/v1/standing-bridges/overdue` is the other one to watch: a bridge
whose review has lapsed is still carrying traffic, and the lapse is visible
nowhere else.

## Emergency bypass

The governed way to exceed an envelope when circumstances demand it. Every bypass
is time-bounded, approved, and auditable — it is not a switch that turns
governance off.

| capability             | what it does                                 |
| ---------------------- | -------------------------------------------- |
| **Create**             | Request a bypass, stating scope and duration |
| **Approve / reject**   | Decide it                                    |
| **Revoke**             | End it early                                 |
| **List / list active** | Every bypass, or only those in force         |
| **Get**                | One bypass in full                           |

Entry point: `sdk:aegis_sdk.modules.emergency.EmergencyBypassModule`.

Operations: `api:POST /api/v1/emergency-bypass/create` ·
`api:GET /api/v1/emergency-bypass` ·
`api:GET /api/v1/emergency-bypass/active` ·
`api:GET /api/v1/emergency-bypass/{id}` ·
`api:POST /api/v1/emergency-bypass/{id}/approve` ·
`api:POST /api/v1/emergency-bypass/{id}/reject` ·
`api:POST /api/v1/emergency-bypass/{id}/revoke`

```python
bypass = await client.emergency_bypass.create(
    agent_id=agent["id"],
    reason="Settlement window closes in 40 minutes; ceiling blocks the transfer.",
    duration_hours=4,
    scope={"financial": {"max_amount_cents": 2_000_000}},
)
await client.emergency_bypass.approve(bypass_id=bypass["id"])

still_open = await client.emergency_bypass.list_active()
```

> ⛔ **Bypasses expire; check `active` rather than assuming they have.** A bypass
> that was approved for an incident and never revoked keeps its widened bounds
> until its clock runs out, and nothing announces that it is still in force.
> `api:GET /api/v1/emergency-bypass/active` belongs in whatever you review daily.

## Kill switch

The blunt instrument. Where a bypass widens bounds, the kill switch stops
activity outright.

| capability    | what it does                        |
| ------------- | ----------------------------------- |
| **Activate**  | Stop the scoped activity            |
| **List open** | Every active kill-switch activation |
| **Get**       | One activation in full              |
| **Clear**     | Lift it                             |

Entry point: `sdk:aegis_sdk.modules.emergency.KillSwitchModule`.

Operations: `api:POST /api/v1/kill-switch/activate` ·
`api:GET /api/v1/kill-switch/open` · `api:GET /api/v1/kill-switch/{id}` ·
`api:POST /api/v1/kill-switch/{id}/clear`

**An uncleared kill switch is the explanation for an organisation that has gone
quiet.** It leaves no error anywhere — agents simply do not act. Check
`api:GET /api/v1/kill-switch/open` early when nothing is happening and nothing is
failing.

## Trust observability

The measurement surface over everything above.

| capability                     | what it does                                             |
| ------------------------------ | -------------------------------------------------------- |
| **Health**                     | Whether the trust fabric is sound                        |
| **Metrics / export**           | Trust measures, readable or exportable                   |
| **Compliance report**          | The trust position formatted for a reviewer              |
| **Agent trust score**          | One agent's composite trust measure                      |
| **CARE budget**                | What the agent has left across the gradient dimensions   |
| **Capabilities**               | What this agent is actually able to do                   |
| **Capability summary**         | The rolled-up version                                    |
| **Trust summary / with-trust** | Agent records enriched with their trust position         |
| **Registry**                   | Register, discover, heartbeat and read agent metadata    |
| **Pipeline trust**             | Validate a pipeline's agents before running it           |
| **ESA config**                 | External trust-service configuration and connection test |

Entry points: `sdk:aegis_sdk.trust.observability.TrustObservabilityModule`,
`sdk:aegis_sdk.trust.agent_trust.AgentTrustModule`,
`sdk:aegis_sdk.trust.registry.TrustRegistryModule`,
`sdk:aegis_sdk.trust.pipeline.PipelineTrustModule` and
`sdk:aegis_sdk.trust.esa.ESAModule`.

Operations: `api:GET /api/v1/trust/health` · `api:GET /api/v1/trust/metrics` ·
`api:GET /api/v1/trust/metrics/export` ·
`api:GET /api/v1/trust/compliance/{id}` ·
`api:GET /api/v1/trust/agents/{agent_id}/trust-score` ·
`api:GET /api/v1/trust/agents/{agent_id}/care-budget` ·
`api:GET /api/v1/trust/agents/{agent_id}/capabilities` ·
`api:GET /api/v1/trust/agents/{agent_id}/capability-summary` ·
`api:GET /api/v1/trust/agents/{agent_id}/constraints` ·
`api:GET /api/v1/trust/agents/{agent_id}/trust-summary` ·
`api:GET /api/v1/trust/agents/{agent_id}/with-trust` ·
`api:POST /api/v1/trust/registry/agents` ·
`api:GET /api/v1/trust/registry/agents/{agent_id}` ·
`api:POST /api/v1/trust/registry/agents/{agent_id}/heartbeat` ·
`api:POST /api/v1/trust/registry/discover` ·
`api:POST /api/v1/trust/pipeline/validate` ·
`api:GET /api/v1/trust/pipeline/{pipeline_id}/agents/{agent_id}` ·
`api:GET /api/v1/trust/esa/config` · `api:PUT /api/v1/trust/esa/config` ·
`api:POST /api/v1/trust/esa/test-connection`

```python
health = await client.trust.observability.get_health()
budget = await client.trust.agents.get_care_budget(agent_id=agent["id"])
await client.trust.pipeline.validate(pipeline_id=p_id)
```

## Trust audit

The append-only record of every trust event. The audit spine proper is in
[08.7](07-evidence-and-operations.md); this is its trust-specific face.

| capability   | what it does                             |
| ------------ | ---------------------------------------- |
| **Query**    | Search trust events                      |
| **Record**   | Append an entry                          |
| **By human** | Everything traceable to one human origin |
| **Trace**    | Follow one act back along its chain      |

Entry point: `sdk:aegis_sdk.trust.audit.AuditModule`.

Operations: `api:GET /api/v1/trust/audit` · `api:POST /api/v1/trust/audit` ·
`api:GET /api/v1/trust/audit/by-human/{human_id}` ·
`api:GET /api/v1/trust/audit/trace/{event_id}`

```python
trail = await client.trust.audit.trace(event_id=suspicious_event_id)
by_person = await client.trust.audit.query(human_id=departing_user_id)
```

**`by-human` is the query a leaver process needs.** It returns everything
traceable to one human origin, which is both the audit answer and the input to
`api:POST /api/v1/trust/revoke/by-human/{human_id}`.

## The five gates, as a checklist

When a call is refused, work down this list rather than adjusting the first thing
that looks relevant:

| ask                                        | with                                                           |
| ------------------------------------------ | -------------------------------------------------------------- |
| 1. Does the principal hold the permission? | `api:POST /api/v1/rbac/check-permission`                       |
| 2. Does the agent have a valid chain?      | `api:POST /api/v1/trust/verify`                                |
| 3. Is its effective posture high enough?   | `api:GET /api/v1/agents/{id}/trust-posture` + the unit ceiling |
| 4. Do the effective constraints permit it? | `api:GET /api/v1/constraints/agents/{agent_id}/effective`      |
| 5. Does clearance reach the data?          | `api:POST /api/v1/governance/explain-access`                   |

Or ask the platform directly: `explain_access` names the gate that decided, which
turns a five-step diagnosis into one call.

---

_Next: [08.6 — Knowledge and data](06-knowledge-and-data.md)_
