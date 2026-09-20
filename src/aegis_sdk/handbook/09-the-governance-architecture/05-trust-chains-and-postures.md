# 09.5 — Trust chains and postures

Every decision in the three preceding chapters rests on a question those
chapters take for granted: _on whose authority is this agent acting, and how
much may it do unaided?_ Those are two separate objects with two separate
lifecycles, and this chapter is both of them end to end — established, verified,
moved, suspended, withdrawn, and evidenced.

[02.4](../02-working-through-the-harness/04-trust-chains-and-postures.md) shows
you the calls. [06.4](../06-architecture/04-trust-and-the-audit-spine.md) covers
the object shapes and the decision path. This chapter is the _governance_
argument: what standing means, how it is earned rather than assigned, what
withdrawing it actually removes, and what an auditor can be shown.

The idea to carry out: **trust here is not a boolean the platform computes about
an agent — it is a set of first-class objects you can read, compose and argue
with.** A lineage that names where authority came from, a standing that moves
and can be explained, and a decision that can be re-derived after the fact.

## Four objects that people collapse into one

| object        | answers                            | mutable?             | read at                                 |
| ------------- | ---------------------------------- | -------------------- | --------------------------------------- |
| **Authority** | who attested this agent?           | created, deactivated | `sdk:aegis_sdk.trust.AuthoritiesModule` |
| **Chain**     | where did its authority come from? | established, revoked | `sdk:aegis_sdk.trust.ChainsModule`      |
| **Posture**   | how much may it do unaided, now?   | moves both ways      | `sdk:aegis_sdk.trust.PosturesModule`    |
| **Decision**  | was _this_ action permitted?       | — it is a record     | `api:POST /api/v1/trust/verify`         |

They are separable in practice, not merely in principle, and every combination
occurs. An agent can hold a valid chain and a restrictive posture — the normal
state of anything newly provisioned. An authority can be retired while chains
established under it continue to exist. A chain can be live and a particular
action still refused, because the decision consults the envelope and the posture
as well as the chain.

## The authority — the signing root

A chain is not self-originating. An **organisational authority** is the signing
root a chain is established under: agents are attested _by_ an authority, and
that relationship is recorded in the chain's genesis.

```python
authority = await client.trust.authorities.create(
    name="Treasury Operations Authority",
    description="Attests agents operating inside the Treasury desk.",
)
agents = await client.trust.authorities.list_agents(authority["id"])
```

Enumerate them at `api:GET /api/v1/trust/authorities`, create one with
`api:POST /api/v1/trust/authorities`, amend with
`api:PATCH /api/v1/trust/authorities/{id}`, and read the agents established under
one at `api:GET /api/v1/trust/authorities/{id}/agents`.

> ⛔ **Deactivating an authority is a security transition that every chain
> established under it inherits.** `api:POST /api/v1/trust/authorities/{id}/deactivate`
> is not a rename and not housekeeping — which is why the platform requires a
> reason and records it on the deactivation entry. Treat it like a revocation:
> decide the blast radius first, using
> `api:GET /api/v1/trust/authorities/{id}/agents`, and expect every agent in that
> list to be affected.

**How many authorities should a tenant have?** One per accountability boundary,
not one per department and not one overall. The test is whether you would ever
want to retire one of them independently — if two groups of agents would always
be retired together, they share an authority; if retiring one group should leave
the other standing, they do not.

## The chain — lineage from a human root

Establishing is `api:POST /api/v1/trust/establish`, returning
`sdk:aegis_sdk.EstablishedTrustChain`.

```python
chain = await client.trust.chains.establish(
    agent_id=agent_id,
    authority_id=authority["id"],
    capabilities=["read_positions", "draft_settlement"],
    constraints=["treasury_desk_only"],
)
```

The body names the agent, the authority, a list of **capability labels** and a
list of **constraint labels**. Both are lists of strings, not dictionaries — the
actual bounds live in envelopes ([09.2](02-envelopes-and-constraints.md)), and
these labels are how the chain describes what it was established _for_. Expiry
defaults to 365 days, and chains genuinely expire.

Two properties constrain what you can build rather than merely how you call it:

**Human origin is derived server-side from the authenticated caller** and cannot
be supplied. An identity a client can assert is an identity a client can forge,
and the one fact a lineage must not be able to lie about is where the human
authority came from. The practical consequence is that **the human on the record
is whoever's credentials ran the script** — so provisioning an entire
organisation under a shared machine key produces a tenant whose whole authority
structure descends from a service account, which is exactly the finding an
auditor is looking for. Provision under a named principal.

**Chains are keyed by agent.** What looks like a chain id in the chain routes is
an agent id, and an agent with no chain returns an _empty path_ rather than an
error. `None` there means "no chain", never "failed to load".

| read                       | route                                               | shape                                |
| -------------------------- | --------------------------------------------------- | ------------------------------------ |
| all chains                 | `api:GET /api/v1/trust/chains`                      | `sdk:aegis_sdk.TrustChain` summaries |
| the full lineage document  | `api:GET /api/v1/trust/chains/{id}`                 | genesis, delegations, capabilities   |
| the narrow projection      | `api:GET /api/v1/trust/chains/{id}/summary`         | the clearance-gated summary          |
| the walk to the human root | `api:GET /api/v1/trust/chains/{id}/delegation-path` | `sdk:aegis_sdk.DelegationPath`       |
| a delegate agent's chain   | `api:GET /api/v1/delegate-agents/{id}/trust-chain`  | the chain for one delegate           |

> ⚠ **Identity is nested one level down on the full lineage document.** On the
> document returned by `api:GET /api/v1/trust/chains/{id}`, `id`, `agent_id` and
> `authority_id` live on `genesis`, not at the top level. A reader that looks a
> level too high finds none of them — and on a permissive parser reads three
> nulls beside fully-populated capability rows, which presents as a response
> problem rather than as a lookup one. `sdk:aegis_sdk.TrustChain` is the flat
> summary shape, `sdk:aegis_sdk.EstablishedTrustChain` is the establishment
> shape, and the lineage document is a third, richer shape again.

The summary projection is **clearance-gated under selective disclosure**: some
fields may be _absent_ rather than null when your clearance does not reach them,
while `id`, `status` and `created_at` are always visible. A null on a gated field
is therefore ambiguous between "not disclosed to you" and "genuinely absent", and
the response cannot tell you which. Do not build a security decision on reading
absence.

Delegation between agents is `api:POST /api/v1/trust/delegate`, returning
`sdk:aegis_sdk.TrustDelegationRecord`; a single delegation edge is removed with
`api:POST /api/v1/trust/revoke-delegation`. Bulk chain generation during org
standup is `api:POST /api/v1/organization-builder/generate-trust-chains`.

## The posture — standing, and how it moves

A posture is not a property of the chain. It is the current answer to _how much
may this agent do without a human in the loop_, and it moves in both directions.

| posture                  | what it means                                         | clearance ceiling         |
| ------------------------ | ----------------------------------------------------- | ------------------------- |
| **`pseudo`**             | deterministic behaviour only; no autonomous judgement | `public`                  |
| **`supervised`**         | acts, with a human approving the consequential paths  | `restricted`              |
| **`shared_planning`**    | plans with a human, executes within the agreed plan   | `confidential`            |
| **`continuous_insight`** | acts autonomously, with continuous human visibility   | `secret`                  |
| **`delegated`**          | acts on delegated authority within its envelope       | the role's full clearance |

Read it at `api:GET /api/v1/agents/{id}/trust-posture`, which returns
`sdk:aegis_sdk.TrustPostureInfo`. Two fields in that response are load-bearing
and are routinely confused:

- **`posture` is the EFFECTIVE posture.** If an override is active, this is the
  override's value, not the agent's own.
- **`base_posture` is what the agent reverts to** when the override lapses.

So _what posture is this agent at_ has two correct answers depending on whether
you mean **now** or **by default**, and an emergency restriction implemented as
an override is precisely the case where they differ.
`sdk:aegis_sdk.PostureOverride` models the override row itself — who initiated
it, why, and when it expires.

The unit posture ceiling from [09.2](02-envelopes-and-constraints.md) composes
here: an agent's effective posture is the lowest of its own posture, its unit's
effective ceiling, and any posture selected for the particular piece of work. A
child unit cannot raise its ceiling above its parent's, so the organisational
brake cascades the same way envelopes do.

## Changing a posture — one endpoint, two outcomes

Both a governed progression request and an administrative override go through the
_same_ call, `api:PUT /api/v1/agents/{id}/trust-posture`, which decides
internally whether the change applies immediately or is held for a human. There
is no separate override endpoint and the two are gated on the same permission.

```text
   PUT trust-posture
         │
         ▼
   ┌───────────────┐  downward, or     ┌──────────────────┐
   │   Requested   │  at/below         │     Applied      │── posture is ──▶ [*]
   └───────┬───────┘  supervised       └──────────────────┘   the NEW value
           │                                   ▲
           │  upward, above supervised         │
           ▼                                   │
   ┌───────────────┐                           │
   │    Pending    │── POST .../approve ───────┘
   └──┬─────────┬──┘
      │         │
      │         └── POST .../reject ──▶ ┌───────────────┐
      │                                 │   Rejected    │── posture never ──▶ [*]
      │                                 └───────────────┘   changed
      │
      └── approval window lapses ─────▶ ┌───────────────┐
                                        │    Expired    │── posture never ──▶ [*]
                                        └───────────────┘   changed

   While a change is Pending the agent is STILL RUNNING at the old posture, and
   the result reports the OLD value. Do not re-issue the same transition to
   "make it take" — it records nothing new and comes back flagged.
```

Read it as: **branch on `approval_pending`.** When it is `True`,
`result.posture` is the posture the agent is _still running at_. Reporting it as
the new one is the single most common integration defect in this area, and it
compounds — a caller that retries after a timeout files a _second_ pending
request, and past one pending request the server refuses rather than picking
one.

The remedy is one read before the write: check
`api:GET /api/v1/agents/{id}/trust-posture/pending` and treat a non-null answer
as _already asked_ rather than as an obstacle. The decision routes are
`api:POST /api/v1/agents/{id}/trust-posture/approve` and
`api:POST /api/v1/agents/{id}/trust-posture/reject`, both of which accept an
explicit approval id. `api:POST /api/v1/agents/{id}/trust-posture/request-upgrade`
is the agent-initiated form, and `api:GET /api/v1/posture/pending-approvals` is
the tenant-wide queue.

```python
pending = await client.trust_posture.get_pending(agent_id=agent_id)
if pending is None:
    result = await client.trust_posture.update(
        agent_id=agent_id,
        posture="continuous_insight",
        reason="Six weeks at shared_planning with zero constraint violations.",
    )
```

**Downward always applies immediately.** That asymmetry is the whole design: a
restriction must never wait on an approval, because the moment you need one is
the moment nobody is available to grant it. It is also what makes a downward
override the correct reversible brake — see § Withdrawal below.

## Progression — autonomy earned, and the evidence for it

There is a whole read surface for _why_ an agent's standing is what it is, and
to an auditor it is worth more than the posture value.

| read                | route                                                           | what it answers                     |
| ------------------- | --------------------------------------------------------------- | ----------------------------------- |
| eligibility verdict | `api:GET /api/v1/agents/{id}/trust-posture/evaluate`            | may this agent progress?            |
| upgrade eligibility | `api:GET /api/v1/agents/{id}/trust-posture/upgrade-eligibility` | to what, and what is missing        |
| behavioural rates   | `api:GET /api/v1/agents/{id}/trust-posture/metrics`             | what eligibility is computed _from_ |
| the basis           | `api:GET /api/v1/agents/{id}/trust-posture/evidence`            | the observations behind the rates   |
| how it got here     | `api:GET /api/v1/agents/{id}/trust-posture/history`             | every transition, and why           |

`api:GET /api/v1/agents/{id}/trust-posture/evaluate` is the **only** call that
answers "may this agent progress". No posture read and no change response carries
an eligibility verdict, and inferring one from the metrics is how a progression
gets made on numbers that were never compared to a threshold.

```python
verdict = await client.trust_posture.evaluate(agent_id=agent_id)
metrics = await client.trust_posture.get_metrics(agent_id=agent_id)
history = await client.trust_posture.get_history(agent_id=agent_id)
```

> ⛔ **Look at the history endpoint before you decide whether your governance is
> real.** If every entry in it is an override, the graduated progression was
> decorative: the agent was _placed_ at its autonomy level rather than having
> earned it. An agent that has never been observed under supervision has no
> evidence behind its autonomy — which is exactly the thing you would be asked
> to show, and the absence reads the same in the API as a well-earned posture
> does in the posture field alone.

**Design a progression path deliberately.** The shape that works is: provision
at `supervised`, accumulate observations under a gradient weighted toward `held`
([09.4](04-the-decision-gradient.md)), evaluate on a cadence rather than on
demand, and progress one level at a time with the evidence attached to the
request's reason. The shape that does not work is provisioning at `delegated`
because the agent needs to be useful on day one — which produces an agent with
maximal standing and an empty evidence surface, and no way to narrow it later
that does not read as a punishment.

## Verification — how a permit is actually reached

`api:POST /api/v1/trust/verify` is the operation the enforcement path calls on an
agent's behalf. It takes an agent, an **action** (a string such as `write` or
`execute`), and a target addressed as a **kind plus an optional instance**:
`resource_type` says what sort of thing is being acted on, `resource_id` says
which one.

```python
decision = await client.trust.verify(
    agent_id=agent_id,
    action="write",
    resource_type="knowledge_item",
    resource_id=document_id,
)
```

The kind is required and the client refuses rather than inventing one — the
platform writes that value into its audit trail, so a fabricated placeholder
would read as one the caller had named.

The result is `sdk:aegis_sdk.TrustVerificationResult`, carrying `allowed` and
`reason`, with the richer shape carrying `capabilities_matched` and — the field
to read when a request was refused — `constraints_violated`.

> ⚠ **Read `constraints_violated`, not `constraints_applied`.** The latter is
> inherited from a base model and is always empty on this route, so reading it
> for the reason a denial happened tells you nothing and tells you so silently.
> Caller-supplied `context` is likewise accepted and ignored: the evaluation runs
> against the chain's own recorded constraints, never against anything the
> request asserts about itself.

For multi-agent work, `api:POST /api/v1/trust/pipeline/validate` pre-flights a
whole pipeline: it confirms every agent holds an active chain carrying the
capabilities its step requires. Read `all_valid` as a statement about chains and
capabilities — the envelope bounds are evaluated at the decision, not on this
route — and per-agent detail at
`api:GET /api/v1/trust/pipeline/{id}/agents/{agent_id}`.

## What is display and what is enforcement

Two read surfaces look like controls and are projections for humans.
`api:GET /api/v1/trust/agents/{id}/trust-score` returns a grade;
`api:GET /api/v1/trust/agents/{id}/care-budget` returns the five-dimension CARE
budget. Neither is consulted by the enforcement path.

That is the correct design — a score that gates an action is a score an
adversary optimises against — and the consequence for you is one rule: **never
gate your own logic on a grade.** Gate on the decision. The score is for a human
deciding whether to look more closely; the decision is for a machine deciding
whether to proceed.

The genuinely useful agent-scoped reads are
`api:GET /api/v1/trust/agents/{id}/capabilities` (what the chain established),
`api:GET /api/v1/trust/agents/{id}/constraints` (the bounds in force),
`api:GET /api/v1/trust/agents/{id}/trust-context` (`sdk:aegis_sdk.AgentTrustContext`,
the composed picture) and `api:GET /api/v1/trust/agents/{id}/trust-summary`.

## Withdrawal — the reversible brake and the permanent one

Two different operations, and choosing the wrong one is expensive in opposite
directions.

**The reversible brake is a posture, not a chain state.** There is no operation
that suspends a trust chain. If you need to stop an agent acting without
permanently ending its lineage, the honest tool is a _downward_ posture override
— `api:PUT /api/v1/agents/{id}/trust-posture` — which applies immediately rather
than waiting on approval, and which you can lift afterwards.

**Revocation is permanent and cascades.** `api:POST /api/v1/trust/revoke/{id}/cascade`
removes an agent's standing and everything that derived authority from it,
returning `sdk:aegis_sdk.CascadeRevocationResult`. The cascade is not optional:
every revocation route cascades, so there is no non-cascading revoke to reach
for.

```python
impact = await client.trust.revocation.get_impact(agent_id=agent_id)
if impact.affected_agent_count > 1:
    ...  # decide deliberately before proceeding
result = await client.trust.revocation.revoke_cascade(agent_id=agent_id)
```

**Look before you cut.** `api:GET /api/v1/trust/revoke/{id}/impact` returns
`sdk:aegis_sdk.RevocationImpact` — how many agents are affected, and whether
active workloads are at risk. That preview is the difference between removing one
agent and silently removing a department's, and it costs one call.

`api:POST /api/v1/trust/revoke/by-human/{id}` revokes everything originating from
a particular person, which is what you want when someone leaves.
`api:POST /api/v1/trust/revoke` is the general form.

> ⛔ **A cascade can fail to complete, and that is a real, discoverable state.**
> `api:GET /api/v1/trust/revoke/jobs/incomplete` lists cascade revocations that
> did not finish — and **until a job there is resumed, agents it named may still
> hold active trust.** `api:POST /api/v1/trust/revoke/jobs/{id}/resume` retries
> it idempotently and reports whether the resume itself timed out again. Read the
> two counts on a job — completed against total — rather than its status string
> alone, because the status does not tell you how far it got. **Put this listing
> on a schedule.** A revocation you believe landed and which did not is the most
> expensive possible version of this system's failure modes: the agent is gone
> from every dashboard and still holds standing.

## Discovery, health and the tenant-wide view

| read               | route                                                   | what it answers               |
| ------------------ | ------------------------------------------------------- | ----------------------------- |
| registry discovery | `api:POST /api/v1/trust/registry/discover`              | which agents are discoverable |
| one registry entry | `api:GET /api/v1/trust/registry/agents/{id}`            | its registration              |
| liveness           | `api:POST /api/v1/trust/registry/agents/{id}/heartbeat` | the agent is still there      |
| plane health       | `api:GET /api/v1/trust/health`                          | is the trust plane serving    |
| tenant metrics     | `api:GET /api/v1/trust/metrics`                         | chain and verification counts |
| exportable metrics | `api:GET /api/v1/trust/metrics/export`                  | the same, portable            |
| compliance report  | `api:GET /api/v1/trust/compliance/{id}`                 | the defensible scan           |

Two notes on reading these honestly. **The discovery surface reads chains, not
agents** — an agent with no chain is invisible to discovery even if it exists and
is running, so an empty discovery result is not evidence that no such agent
exists. And **`api:GET /api/v1/trust/metrics` computes from a bounded window** of
recent records, which makes it the right surface for a dashboard and the wrong
one for a figure that has to be defensible; the compliance report scans further
and declares when it could not, which is why it is the one to reach for when a
number is going into a document.

> **In the console:** the trust area shows authorities, chains and postures on
> separate surfaces, and the posture surface is where progression requests
> appear for approval. An agent showing an effective posture different from its
> base posture renders the override explicitly, with its expiry — which is the
> fastest way to answer "why can it not do that today".

## Summary

| you need                            | the object         | the call                                             |
| ----------------------------------- | ------------------ | ---------------------------------------------------- |
| a signing root                      | authority          | `api:POST /api/v1/trust/authorities`                 |
| give an agent standing              | chain              | `api:POST /api/v1/trust/establish`                   |
| see where its authority came from   | delegation path    | `api:GET /api/v1/trust/chains/{id}/delegation-path`  |
| know how autonomous it is now       | posture            | `api:GET /api/v1/agents/{id}/trust-posture`          |
| move it, up or down                 | posture change     | `api:PUT /api/v1/agents/{id}/trust-posture`          |
| know whether a move is earned       | eligibility        | `api:GET /api/v1/agents/{id}/trust-posture/evaluate` |
| show that it was earned             | history + evidence | `api:GET /api/v1/agents/{id}/trust-posture/history`  |
| ask whether an action is permitted  | verification       | `api:POST /api/v1/trust/verify`                      |
| stop it reversibly                  | downward override  | `api:PUT /api/v1/agents/{id}/trust-posture`          |
| see what a revocation would cost    | impact preview     | `api:GET /api/v1/trust/revoke/{id}/impact`           |
| end it permanently                  | cascade revocation | `api:POST /api/v1/trust/revoke/{id}/cascade`         |
| catch a cascade that did not finish | incomplete jobs    | `api:GET /api/v1/trust/revoke/jobs/incomplete`       |

---

_Next: [09.6 — The audit spine and evidence](06-the-audit-spine-and-evidence.md)_
