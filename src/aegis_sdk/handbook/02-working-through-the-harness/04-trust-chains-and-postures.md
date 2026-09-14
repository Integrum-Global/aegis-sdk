# 02.4 — Trust chains and postures

Two more things people collapse into one, and again they answer different
questions:

- **A trust chain** answers *where did this agent's authority come from?* It is
  lineage — a genesis rooted in a human, and delegations down from there.
- **A posture** answers *how much of that authority may it use without a human
  in the loop right now?* It is a level, and it moves.

An agent can hold a valid chain and a restrictive posture. That is the normal
state of a new agent and it is the state to design for.

## Establishing a chain

```python
chain = await client.trust.chains.establish(
    agent_id=agent.id,
    authority_id=head_role_id,
    capabilities=["cash_forecasting", "reporting"],
    expires_in_days=365,
)
```

`api:POST /api/v1/trust/establish`, returning
`sdk:aegis_sdk.EstablishedTrustChain`.

Four things about this call:

- **`authority_id` is required and has no default.** It names the organisational
  authority the delegation comes from.
- **Human origin is derived server-side from the authenticated caller and cannot
  be supplied by the client.** The `human_origin_data` parameter is accepted and
  ignored. This is not an oversight — *design intent, not observable*: an
  identity a client can assert is an identity a client can forge, so the one
  thing the audit trail must not be able to lie about is taken from the session
  instead of the body. Practically: **the human on the record is whoever's
  credentials ran the script.** Provision under a real, attributable identity,
  not a shared machine key, or your lineage records a service account as the
  origin of every delegation in the tenant.
- **`constraints` is a list of strings**, not a dictionary. It carries constraint
  *labels*; the actual bounds live in envelopes (02.3).
- **`expires_in_days` defaults to 365.** Chains expire. Put the renewal on a
  calendar at provisioning time, because the failure mode a year out is agents
  quietly losing authority.

Read chains with `api:GET /api/v1/trust/chains` and
`api:GET /api/v1/trust/chains/{id}`; the delegation path for one is at
`api:GET /api/v1/trust/chains/{id}/delegation-path`, and an agent's assembled
trust context at `api:GET /api/v1/trust/agents/{id}/trust-context`.

**Chains follow the reporting chain, not the unit tree.** A role with no
`reports_to_role_id` is a chain root. If your reporting lines are wrong (02.2),
your lineage is wrong, and it will be wrong in the audit export rather than in
anything that fails loudly.

## Verifying

```python
result = await client.trust.chains.verify(...)
```

`api:POST /api/v1/trust/verify`. This is the operation the enforcement path calls
on the agent's behalf; you will mostly use it to answer "would this be allowed?"
without doing the thing.

## Postures — the five levels

Aegis uses the CARE-aligned vocabulary, lowercase:

| level | posture | what it means |
| --- | --- | --- |
| 1 | `pseudo` | no autonomous action; a human does everything |
| 2 | `supervised` | may read; every write is a human's |
| 3 | `shared_planning` | plans with a human, acts within the plan |
| 4 | `continuous_insight` | acts, with continuous human visibility |
| 5 | `delegated` | acts within its envelope without per-action review |

An agent's effective autonomy is `min(agent posture, ceiling, selected)` — the
lowest of what it holds, what its unit permits, and what was chosen for this
piece of work. Raising one of the three does not raise the result; you have to
find the binding one. `max_trust_posture` on a unit is the ceiling, and it
cascades: a child cannot exceed its parent.

Read the current posture:

```python
posture = await client.trust.postures.get(agent_id)
```

`api:GET /api/v1/agents/{id}/trust-posture`.

## Moving a posture — three different operations, and they are not interchangeable

This is where the harness earns its place, because the three paths have different
governance and the console blurs them into one button.

**1. Request a progression** — the governed path. The agent (or you on its
behalf) asks to move up; a human approves.

```python
result = await client.trust.postures.request_progression(...)
```

⛔ There is **no dedicated `/request-upgrade` endpoint** — this and
`postures.override()` below both go through the SAME
`api:PUT /api/v1/agents/{id}/trust-posture`, which decides internally whether
the change applies at once or is held for a human. A resolution comes back
through `api:POST /api/v1/agents/{id}/trust-posture/approve` or
`.../reject`. Pending requests across the tenant are at
`api:GET /api/v1/posture/pending-approvals`; one agent's pending request is at
`api:GET /api/v1/agents/{id}/trust-posture/pending`.

**The change is not always applied when this returns.** Raising an agent
above `supervised` is held for approval — branch on `result.approval_pending`
before reporting the agent progressed; while it is `True`, `result.posture`
is the posture the agent is **still running at**, not the one you asked for.
This is the confirmed root cause of a partner-reported symptom: code that
assumed the return always carried the new posture could not parse the
approval-pending reply and raised *after the server had already accepted the
request* — and a caller that then retries files a **second** pending request
against the same agent, because the endpoint has no idempotency key.
**Before retrying after an ambiguous failure** (a timeout, a dropped
connection), call `get_pending_approval(agent_id)` to find out whether the
first attempt already landed — `None` means it did not.

**Approving is addressed by AGENT, not by request.**
`postures.approve_transition(agent_id, notes=...)` takes no request
identifier — there is nowhere to send one, because the endpoint resolves
whichever request is pending for that agent. **With more than one request
pending, which one it decides is not something the caller controls.** This
is the confirmed root cause of a second partner-reported symptom — sending a
`request_id` to try to disambiguate does nothing, because the endpoint has no
such field, and the fix is upstream of the call: never let a second request
become pending while one is already outstanding. Check
`get_pending_approval(agent_id)` before every `request_progression()` call,
and treat a non-`None` result as "already asked, do not ask again" rather
than as an obstacle to route around.

**2. Override** — set it directly.

```python
await client.trust.postures.override(...)
```

`api:PUT /api/v1/agents/{id}/trust-posture` — the same endpoint as
`request_progression()` above, and it carries the same two-outcome shape: a
downward move (an emergency restriction) applies immediately, but an upward
override above `supervised` is held for approval exactly like a normal
progression request. Branch on `result.approval_pending` here too; do not
assume an override always takes effect at once. This is the one to be
careful with regardless — it is legitimate (an incident, a migration, a
deliberate decision) and it is also the operation that turns a governed
progression into an assertion. Use it knowingly and record why.

**3. Let the evidence decide.** Aegis accumulates evidence about whether an agent
has earned more autonomy, and will tell you:

- `api:GET /api/v1/agents/{id}/trust-posture/upgrade-eligibility` — is it
  eligible?
- `api:GET /api/v1/agents/{id}/trust-posture/evidence` — on what basis?
- `api:GET /api/v1/agents/{id}/trust-posture/metrics` — the underlying numbers
- `api:GET /api/v1/agents/{id}/trust-posture/evaluate` — evaluate progression now
- `api:GET /api/v1/agents/{id}/trust-posture/history` — how it got here

This is the intended workflow and it is the one most deployments never turn on,
because overriding is quicker. The history endpoint is what an auditor will ask
for; if every entry in it is an override, the gradient was decorative.

**Design for the ratchet to move slowly.** Start agents at `supervised`, let
evidence accumulate, promote deliberately. An agent provisioned at `delegated`
because it was easier has never been observed doing anything under supervision,
so there is no evidence behind its autonomy — which is precisely the thing you
would need to show.

## Revoking — and the two shapes that are easy to confuse

```python
result = await client.trust.chains.revoke(agent_id, reason="Security incident")
print(result.total_revoked)
```

`api:POST /api/v1/trust/revoke/{id}/cascade`.

⚠ **Revocation ALWAYS cascades. There is no non-cascading revoke.** The
`cascade=` parameter is deprecated and ignored, and passing it raises a
`DeprecationWarning` rather than changing anything. Revoking one agent revokes
everything that derived authority from it.

**Look before you cut.** The impact is knowable in advance:

```python
impact = await client.trust.chains.analyze_revocation_impact(agent_id)
```

`api:GET /api/v1/trust/revoke/{id}/impact`. Run this first, every time. It is the
difference between removing one agent and silently removing a department's.

`api:POST /api/v1/trust/revoke/by-human/{id}` revokes everything originating from
a particular person — the operation you want when someone leaves — and
`api:POST /api/v1/trust/revoke-delegation` removes a single delegation.

### There is no reversible pair — only revoke, which is not reversible

⛔ **`client.trust.chains.suspend(agent_id, reason)` and `.reinstate(agent_id)`
do not do this.** Both are deprecation shims that **always raise
`UnsupportedOperationError`** — there is no server route for suspending or
reinstating a trust chain directly. `SUSPENDED` exists only as a lifecycle
state a chain reaches automatically during cascade revocation of a
bridge-sourced chain (see the callout below); it is not something you can put
an agent into or take it out of on demand. If you need to stop an agent
acting without permanently ending its chain, the honest tool today is
`postures.override(agent_id, new_posture="pseudo", reason=...)`
([the posture section above](#postures--the-five-levels)) — reversible, and a
downward move applies immediately rather than waiting on approval. `revoke()`
remains the only permanent, cascading removal, and it is genuinely not
reversible.

> ⚠ **A revoked chain that originated from a bridge can read back as
> `suspended`.** If you are writing a check that asks "is this revoked?" by
> comparing a status string, that check can miss a genuinely revoked chain. Do
> not rely on a status-only comparison for a security decision; use the
> revocation impact and audit surfaces, which describe what happened rather than
> what state a row is in. **UNVERIFIED** in this edition — the behaviour is
> reported and the distinction is real, but it could not be confirmed against a
> live deployment from here. Treat it as a lead: if you have a revoked
> bridge-origin chain to hand, check what its status field actually says before
> writing a check that depends on the answer.

## The audit surface for trust decisions

```python
await client.trust.audit.query(...)
```

`api:GET /api/v1/trust/audit`, filtered by originating human at
`api:GET /api/v1/trust/audit/by-human/{id}`, and written to with
`api:POST /api/v1/trust/audit`.

This is a different record from the general audit log (02.6). It is specifically
the trust-decision trail — who delegated what to whom, and on what basis — and it
is the one that answers a governance question rather than an operational one.

> **In the console:** an agent's posture, its evidence and its history are
> visible on the agent's own page, and posture approvals join the same queue as
> other held decisions. Revocation is deliberately not a one-click action.

---

*Next: [02.5 — Objectives and the work loop](05-objectives-and-the-work-loop.md)*
