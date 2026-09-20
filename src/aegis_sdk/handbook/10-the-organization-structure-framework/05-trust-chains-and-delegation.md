# 10.5 — Trust chains and delegation

A trust chain is the record of where an agent's authority came from. The property
it exists to guarantee is EATP's: **every action an agent takes traces back,
through an unbroken and tamper-evident chain, to a human who authorised it.** No
agent holds authority intrinsically. It holds delegated authority, and the chain
is the delegation.

This chapter is the chain as a structural object — what it is derived from, what
it carries, how it is generated from the organisation, how it is verified, and
what happens when it is withdrawn. [06.4](../06-architecture/04-trust-and-the-audit-spine.md)
covers the decision the chain participates in at request time; this chapter covers
where the chain came from and what shape the graph of them has.

**The single idea to carry out: chains are derived from the reporting relation and
nothing else, so the reporting edges you set in
[10.4](04-roles-authority-and-intent.md) are the delegation graph — you do not
author it separately, and you cannot correct it separately.**

## Derived from reporting, never from containment

The generation rule is one sentence: **for each role that has a reporting parent,
delegate from the parent role's agent to this role's agent.** Roles with no
reporting parent are chain roots and are left as roots — that is correct, not a
gap, and the platform does not fill it in from containment.

```text
THE DELEGATION GRAPH IS THE REPORTING GRAPH

   human authoriser
         │  establishes
         ▼
   CEO role agent ─────────────┐  chain ROOT — no reports_to_role_id
         │ delegates           │
         ▼                     ▼
   CFO role agent        Staff Officer role agent
         │ delegates
         ▼
   Treasury Analyst role agent

   Each arrow is one TrustChain row: trustor_agent_id -> trustee_agent_id.
   Each arrow exists because a reporting edge exists. Containment
   contributes NOTHING to this graph — a role contained in one unit and
   reporting into another delegates along the REPORTING line.
```

Read it as: containment says where a role lives; reporting says whose authority
it acts under. The chain follows the second. A role contained in Engineering but
reporting to the General Counsel receives its delegation from the General
Counsel's agent, and that is the intended behaviour of a deliberately drawn matrix
edge.

Two details of the generation are worth knowing because they are visible in the
chains you read back.

**The constraint envelope attached to a delegation comes from the CHILD role**,
not the parent. The delegation carries the bounds of the position being delegated
to. This is consistent with monotonic tightening — the child's envelope is already
a subset of the parent's, so attaching the child's is attaching the narrower one.

**The delegation's scope is derived from the child's authority band.** A child at
authority 3 or above receives a `full` delegation; at 1 or 2 it receives a
`partial` one. The chain also records a maximum cascade depth derived from the
child's band, which bounds how far authority may be re-delegated beneath it.

Generation is a call you can run:
`api:POST /api/v1/organization-builder/generate-trust-chains` derives the graph
for the organisation. `api:POST /api/v1/trust/establish` creates a chain from an
authority, and `api:POST /api/v1/trust/delegate` creates a single delegation
directly when you need one outside the derived set.

## What a chain carries

`sdk:aegis_sdk.TrustChain` is the typed shape. The fields divide into the parties,
the lifecycle, the bounds, and the tamper evidence.

| field                                             | what it holds                                                            |
| ------------------------------------------------- | ------------------------------------------------------------------------ |
| **the parties**                                   |                                                                          |
| `trustor_agent_id`                                | the **delegator** — the agent granting authority                         |
| `trustee_agent_id`                                | the **delegatee** — the agent receiving it                               |
| `human_origin_data`                               | the human the lineage terminates at, and how they authenticated          |
| `organization_id`                                 | the tenant                                                               |
| `organization_unit_id`                            | the unit context the delegation sits in                                  |
| **lifecycle**                                     |                                                                          |
| `status`                                          | `active` · `completed` · `expired` · `revoked` · `suspended`             |
| `expires_at`                                      | when the delegation lapses                                               |
| `revoked_at` / `revoked_by` / `revocation_reason` | the withdrawal record                                                    |
| **scope and bounds**                              |                                                                          |
| `delegation_type`                                 | `full` · `partial` · `conditional` — **scope, never origin**             |
| `constraint_envelope_id`                          | the envelope bounding what the trustee may do                            |
| `constraint_envelope_data`                        | the computed envelope carried with the chain                             |
| `derived_from_org_structure`                      | whether this chain was generated from the reporting tree                 |
| `source_bridge_id`                                | set when the delegation originated at a **bridge**, not a reporting edge |
| **tamper evidence**                               |                                                                          |
| `genesis_signature`                               | the signature over the chain's immutable content                         |
| `integrity_hash`                                  | the hash binding that content and signature together                     |
| `previous_chain_hash`                             | links this chain to its predecessor                                      |
| `signing_key_id`                                  | which key signed it                                                      |

⚠ **`trustor` and `trustee`, not `delegator` and `delegate`.** The two
vocabularies are both natural and only one is the field name. Code written against
`delegator_agent_id` reads nothing and fails silently against a `None`.

> ⛔ **`delegation_type` describes SCOPE, never ORIGIN.** `full`, `partial` and
> `conditional` say _how much_ authority was delegated. They do not say _where the
> delegation came from_. A bridge-originated delegation is marked by
> `source_bridge_id` being set, and it still carries an ordinary scope value.
> Writing `"bridge"` into `delegation_type` conflates the two axes and makes the
> scope of that delegation unreadable — the value that told you how much authority
> crossed is now telling you which mechanism crossed it, and nothing is recording
> the first.

## Expiry is bounded, and absence is not the safe default

A delegation carries an explicit expiry, and the default window is **365 days**.
Chains derived from the organisation are minted with that bound written into them.

> ⛔ **An absent expiry means unbounded, not immediate.** This is the one place in
> the trust model where the intuitive reading is backwards. A chain with no
> expiry is not a chain that has already lapsed; it is a chain the expiry check
> never evaluates, which is to say a delegation valid forever. **Omission is the
> permissive default here**, so a delegation minted by your own code with the
> expiry left unset authorises execution indefinitely and looks, in every listing,
> exactly like one that was bounded.

Note also that `expired` is a status that describes a chain, not an event that
fires on a clock. Expiry is adjudicated from the timestamp when a chain is
evaluated — the row does not transition to `expired` by itself at the moment the
window closes. A chain listing as `active` past its expiry is not a defect and is
not usable; read the expiry, not just the status.

## Verifying a chain

Four reads answer four different questions.

| call                                                | answers                                                    |
| --------------------------------------------------- | ---------------------------------------------------------- |
| `api:GET /api/v1/trust/chains/{id}`                 | what does this chain say?                                  |
| `api:GET /api/v1/trust/chains/{id}/delegation-path` | what is the full lineage back to the human?                |
| `api:GET /api/v1/trust/chains/{id}/summary`         | the condensed view for display                             |
| `api:POST /api/v1/trust/verify`                     | is the cryptography intact — signature and integrity hash? |

`api:GET /api/v1/trust/agents/{id}/trust-context` is the aggregate for an agent:
its chain, its delegation path, its position, how long until expiry, and any
warnings. It is the right single call when you are deciding whether an agent is
currently fit to act, because a chain that exists is not the same as a chain that
is usable.

**Verification is two independent checks and both must hold.** The signature
proves the chain's immutable content was signed by the recorded key. The integrity
hash proves that content and that signature bind together, chained to the previous
chain's hash. Only immutable fields are signed — the parties, the genesis data,
the human origin, the envelope, the expiry, the scope — deliberately excluding
status and timestamps, so that revoking a chain does not invalidate the signature
attesting to how it was created. A revoked chain is still a provably authentic
record of a delegation that was made and then withdrawn, which is exactly what an
audit needs.

The signing root is a **trust authority**: `api:GET /api/v1/trust/authorities`
lists them, `api:POST /api/v1/trust/authorities` creates one, and
`api:GET /api/v1/trust/authorities/{id}/agents` shows what hangs off it. The
authority is the organisational anchor the lineage terminates at above the human.

```python
# Before relying on an agent's authority, read the context — not just the chain.
context = await client.trust.get_agent_trust_context(agent_id=analyst_agent_id)

if context["has_warnings"]:
    # expires_in_days, a suspended ancestor, a posture below what the task needs
    for warning in context["warnings"]:
        log.warning("trust context", agent=analyst_agent_id, detail=warning)
```

## Revocation, and why it cascades

Withdrawing authority from one agent has to withdraw it from everything that
derived authority from that agent, or the guarantee the chain exists to provide is
gone. Revocation therefore comes in a graded set of operations, and choosing
between them is a real decision.

| operation                                     | scope                                                    |
| --------------------------------------------- | -------------------------------------------------------- |
| `api:POST /api/v1/trust/revoke`               | an agent **and everything downstream of it**             |
| `api:POST /api/v1/trust/revoke/{id}/cascade`  | the same, named explicitly                               |
| `api:POST /api/v1/trust/revoke/by-human/{id}` | **everything tracing to one person**                     |
| `api:POST /api/v1/trust/revoke-delegation`    | one delegation **edge** — the only non-cascading removal |

> ⛔ **Every revocation route cascades. There is no non-cascading revoke.** The two
> general routes behave identically, so reaching for the first in the belief that it
> touches one chain removes the whole subtree beneath it. Only
> `api:POST /api/v1/trust/revoke-delegation` is narrow, and it removes an edge rather
> than an agent's standing. The symptom of the mistake is a revocation that "worked"
> and a department that stopped acting an hour later.

**Preview before you cascade.** `api:GET /api/v1/trust/revoke/{id}/impact` returns
the agents that would be affected, how many, and whether any of them currently
hold active workloads. It is a read, it is cheap, and a cascade is not reversible
by re-running it — a reactivation is a different operation with a different
record.

The human-origin cascade deserves its own mention because it is the operation
that makes the EATP guarantee operationally real. When a person leaves, or their
access is withdrawn, **every delegation anywhere in the organisation that traces
to them is revoked in one action.** That is only expressible because every chain
records its human origin; in a model where agents held intrinsic authority, the
same question would have no answer.

**Cascades are durable and resumable.** A cascade runs as a recorded job with its
targets written down before any step executes and its completions appended as it
goes, so an interrupted cascade is resumable rather than restartable.
`api:GET /api/v1/trust/revoke/jobs/incomplete` lists jobs that did not finish;
`api:POST /api/v1/trust/revoke/jobs/{id}/resume` continues one. Per-agent steps
are idempotent, so resuming over already-revoked agents is a no-op.

> ⛔ **Check for incomplete revocation jobs after any cascade over a large
> subtree.** An interrupted cascade leaves part of the tree revoked and part of it
> still holding authority — and the part still holding it looks entirely normal,
> because a chain that was never reached is an ordinary active chain. The symptom
> is an agent that continues working after you believed its authority was
> withdrawn, which reads as a revocation bug rather than as an unfinished job.
> The incomplete-jobs list is the read that distinguishes them.

**The reversible brake is a posture, not a chain state.** Where revocation is
terminal, a leave of absence, an investigation or a temporary stand-down needs
something you can lift afterwards — and that is a _downward_ posture override
(`api:PUT /api/v1/agents/{id}/trust-posture`), which applies immediately rather than
waiting on an approval. [09.5](../09-the-governance-architecture/05-trust-chains-and-postures.md)
carries the posture surface in full.

> ⛔ **There is no operation that suspends a trust chain.** `suspended` appears in the
> status list above because the platform reaches it on its own, when a cascade revokes
> a bridge-sourced chain — it is a state the chain can be found in, never a button you
> press. Reaching for a suspend call because the status exists is the trap: the state is
> real, the operation is not, and what looks like the reversible option is a lifecycle
> outcome you cannot invoke. Use the downward posture override instead.

## The audit trail

Chains are one half of the record; the audit entries are the other.
`sdk:aegis_sdk.TrustAuditEntry` is the shape.

| call                                        | answers                                    |
| ------------------------------------------- | ------------------------------------------ |
| `api:GET /api/v1/trust/audit`               | what has happened across the trust surface |
| `api:GET /api/v1/trust/audit/by-human/{id}` | everything attributable to one person      |
| `api:GET /api/v1/trust/audit/trace/{id}`    | the full trace for one action              |

The by-human read is the counterpart of the by-human revocation, and the pair is
the practical shape of the accountability claim: for any person, you can answer
both _what was done under their authority_ and _withdraw all of it_. Those two
questions being answerable from the platform is what makes the governance
provable rather than asserted.

## Six ways a chain graph goes wrong

Each of these produces a structure that is internally consistent and wrong, which
is why they are worth having as a checklist rather than as intuitions.

| defect                                         | what it looks like                                      | the read that finds it                                                        |
| ---------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **unattached head roles**                      | subtrees that are separate authority islands            | `api:GET /api/v1/organization-roles/{id}/reporting-chain` returning one entry |
| **delegation minted without an expiry**        | authority valid forever, indistinguishable from bounded | read `expires_at`, not `status`                                               |
| **`delegation_type` used to record origin**    | scope unreadable; bridge chains miscounted              | `source_bridge_id` is the origin marker                                       |
| **interrupted cascade**                        | part of a subtree still authorised                      | `api:GET /api/v1/trust/revoke/jobs/incomplete`                                |
| **containment walked for authority**           | a plausible answer about the wrong relation             | compare against `/{id}/reporting-chain`                                       |
| **revocation used for a temporary stand-down** | an irreversible record of a reversible intent           | the withdrawal record; there is no undo — a posture override was the tool     |

## Trust chains, once

| question                                      | answer                                                                 |
| --------------------------------------------- | ---------------------------------------------------------------------- |
| What is a chain derived from?                 | The **reporting** relation. Containment contributes nothing.           |
| Who are the parties?                          | `trustor_agent_id` (delegator) → `trustee_agent_id` (delegatee).       |
| Whose envelope does a delegation carry?       | The **child** role's.                                                  |
| What does `delegation_type` mean?             | **Scope** — `full` · `partial` · `conditional`. Never origin.          |
| How is a bridge-originated chain marked?      | `source_bridge_id`, not the type field.                                |
| What is the default expiry?                   | 365 days, written explicitly at mint.                                  |
| What does an absent expiry mean?              | **Unbounded** — not immediate.                                         |
| What does verification check?                 | Signature **and** integrity hash; both must hold.                      |
| Why isn't `status` signed?                    | So revoking a chain does not invalidate the record of how it was made. |
| What precedes a cascade?                      | The impact preview.                                                    |
| What makes a person's authority withdrawable? | Every chain records its human origin.                                  |
| Which operation is reversible?                | A **downward posture override**. Revocation is terminal and cascades.  |

---

_Next: [10.6 — Role agents](06-role-agents.md)_
