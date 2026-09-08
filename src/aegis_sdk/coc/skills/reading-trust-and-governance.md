---
name: reading-trust-and-governance
description: Read trust posture, chains, envelopes, permissions and audit state against a deployed Aegis — and be exact about what each reading does and does not establish.
---

# Reading trust and governance state

This is the surface an architect is most often asked to summarise for someone
else, which makes it the surface where a careless reading does the most damage.
Everything here reports; **almost nothing here enforces**, and the two are easy
to conflate because they share vocabulary.

## The four things people confuse

| | reports on | answers |
| --- | --- | --- |
| **posture** (`client.trust_posture`) | how much autonomy an agent may exercise | "how far may it go?" |
| **chain** (`client.trust.chains`) | who delegated authority to whom | "where did this authority come from?" |
| **envelope** | the composed bound on what may be done | "what is actually permitted here?" |
| **permission / role** (`client.governance`) | what a principal may do | "may this caller do that?" |

An agent can hold a high posture and a narrow envelope. Those are not in
contradiction — posture is a ceiling on autonomy, the envelope is the bound on
action, and the effective answer is the *intersection*. Reporting one as though
it were the other is the most common error on this surface.

## Step 1 — Posture, and the ceiling that is not on the agent

```python
cfg = await client.trust_posture.get_trust_posture(agent_id)
```

That reads `api:GET /api/v1/agents/{id}/trust-posture`; the history is
`api:GET /api/v1/agents/{id}/trust-posture/history` and the eligibility check is
`api:GET /api/v1/agents/{id}/trust-posture/upgrade-eligibility`.

A posture is bounded by a ceiling that composes from what contains the agent. So
the value you read is not a property of the agent alone, and **it can change
without anyone touching the agent.** Re-read it after any change to the
containing structure rather than caching it.

Posture names are lowercase and CARE-aligned: `pseudo`, `supervised`,
`shared_planning`, `continuous_insight`, `delegated`. If you see uppercase or a
name outside that set, you are looking at a different vocabulary and a mapping
step is missing.

## Step 2 — A posture change is a request, not a setting

```python
await client.trust_posture.check_upgrade_eligibility(agent_id)
await client.trust_posture.request_upgrade(agent_id)
await client.trust_posture.get_pending_approval(agent_id)
```

Eligible is not approved and requested is not granted. **Confirm the transition
landed by re-reading the posture**, not by the absence of an exception on the
request.

```python
await client.trust_posture.get_posture_history(agent_id)   # what actually happened
```

## Step 3 — Chains, and the three-valued integrity question

Chains are read at `api:GET /api/v1/trust/chains`, one chain at
`api:GET /api/v1/trust/chains/{id}`, and its provenance at
`api:GET /api/v1/trust/chains/{id}/delegation-path`.

Chain integrity is **not** a boolean. A verifier that has not swept yet reports
the same shape as a chain that failed verification.

```
verified          the sweep ran and the chain held
broken            the sweep ran and it did not
unverified        the sweep has not run — you know nothing
```

```
# DO      read the last-verified timestamp BEFORE reading the verdict
# DO NOT  render a not-yet-verified chain as broken, or as fine
```

**Why this matters more than it looks:** both wrong renderings are costly in
opposite directions. "Broken" triggers an incident that is not happening.
"Fine" reports an assurance nobody has established.

Note also that a chain whose authority came through a bridge can be recorded with
a status that a naive "is this revoked?" filter admits. If you are asking whether
authority is still live, do not answer it from a status field alone.

## Step 4 — Permissions, and the two registries that share a spelling

`client.governance` answers role-based questions. It is **not** the same
vocabulary as API-key scopes, and neither is a subset of the other.

```python
await client.governance.check_permission(...)      # asks the role question
await client.governance.get_user_permissions(...)  # a self-lookup
```

A permission check answering "yes" does not mean your API key can reach the
route — the key is judged against scopes, and on persona-gated routes against
neither. [the credential guardrail](../guardrails/credential-reachability.md) owns that distinction.

## Step 5 — Audit and evidence, read as records

```python
await client.observe_audit.list_logs(...)
await client.compliance.verify_audit(...)
await client.compliance.list_audit_entries(...)
```

**An empty result is an absence of records, never an absence of events.** Three
worlds produce it: nothing happened, something happened and was not recorded, or
your credential cannot read it. Establish which before reporting.

Before you trust an audit query at all, confirm it can return a row — run it over
a period containing an event you already know about. A query that has never
returned anything has not been shown capable of returning anything.

## Step 6 — Reporting to a human

State for every figure: **the credential**, **the organisation it resolved to**,
**the time**, and **whether the value was read or derived**.

```
# DO      "3 agents at `delegated`, org <X>, read with a session at 14:02 UTC;
#          chain integrity UNVERIFIED — last sweep timestamp is null"
# DO NOT  "3 agents fully autonomous, chains broken"
```

**And be plain about what none of it establishes.** These are read paths. Nothing
here observes an execution being stopped, so a clean governance summary is
evidence about records rather than about conduct. That distinction is not
pedantry: it is why the accountability for the conduct stays with the
organisation deploying the agent, and why what this platform offers is the proof
rather than the liability.

## What this skill does not cover

Changing governance state — creating roles, editing classifications, approving
transitions. Those are mutations with real authority consequences; read first,
and treat every setter on this surface as a candidate for
[the sentinels guardrail](../guardrails/sentinels-and-defaults.md)'s MUST 3 before you call it once.
