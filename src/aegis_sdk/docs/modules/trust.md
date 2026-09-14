# Trust Module

The trust module (`client.trust`) provides management for the Enterprise Agent Trust Protocol (EATP). It is organized into four sub-modules:

| Sub-Module  | Access                     | Description                                                     |
| ----------- | -------------------------- | --------------------------------------------------------------- |
| Chains      | `client.trust.chains`      | Trust chain establish, verify, revoke (cascade), analyze impact |
| Delegations | `client.trust.delegations` | Delegation create, revoke, query                                |
| Postures    | `client.trust.postures`    | Posture get, progression, override                              |
| Audit       | `client.trust.audit`       | Audit log query, chain history                                  |

## Trust Concepts

**Trust Chains** establish the foundation of trust from a human origin to an agent. Every agent action must be traceable back to a human authorization.

**Delegations** allow agents to grant subsets of their capabilities to other agents, creating a delegation tree that preserves traceability.

**Postures** define progressive levels of agent autonomy (pseudo, supervised, shared_planning, continuous_insight, delegated), based on track record.

**Audit Logs** record every trust operation for compliance and forensic analysis.

---

## Chains (`client.trust.chains`)

### Establish a Trust Chain

```python
from aegis_sdk import EstablishedTrustChain

chain: EstablishedTrustChain = await client.trust.chains.establish(
    agent_id="agent_abc123",
    authority_id="authority_xyz",
    capabilities=["read:data", "write:reports", "execute:workflows"],
    constraints=["max_cost:1000", "allowed_regions:us-west-2"],
    expires_in_days=365,
)

print(f"Chain established for: {chain.agent_id}")
print(f"Status: {chain.status}")
print(f"Capabilities: {chain.genesis.capabilities}")
```

The server derives `human_origin` from the authenticated caller
(`POST /trust/establish`) — it is never
client-supplied.

### EstablishedTrustChain Model

Returned by `establish()`. Mirrors the server's `TrustChain` response model.

| Field          | Type                             | Description                                                   |
| -------------- | -------------------------------- | ------------------------------------------------------------- |
| `agent_id`     | `str`                            | Agent this chain authorizes                                   |
| `genesis`      | `TrustGenesisRecord`             | agent_id, authority_id, capabilities, constraints, timestamps |
| `delegations`  | `List[TrustDelegationRecord]`    | Delegations made under this chain                             |
| `status`       | `str`                            | `"active"`, `"suspended"`, `"revoked"`                        |
| `human_origin` | `Optional[TrustHumanOriginInfo]` | Human who authorized the chain (server-derived)               |

### TrustChain Model

⛔ **This table used to describe a shape the server has never emitted, on any
trust-chain route.** `chains.list()` and `chains.get()` raised a Pydantic
`ValidationError` on every call under the old model (`id`,
`human_origin_id`, `human_origin_data`, a dict `constraints`, `delegation_depth`,
datetime `created_at`/`revoked_at` — none of it real). Corrected below. This
is the confirmed root cause behind the partner-reported symptom *"trust chain
read returns `id`, `agent_id` and `authority_id` as null while the capability
rows carry the data"* — a reader who trusted the old table would reach for
exactly the fields it invented.

Returned by `list()`, per item (see the next section for `get()`, which
returns a **different, richer** shape — the two are not interchangeable):

| Field          | Type                              | Description                                                                                       |
| -------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------- |
| `agent_id`     | `str`                               | Agent this chain authorizes                                                                          |
| `genesis`      | `TrustGenesisRecord`                | `agent_id`, `authority_id`, `capabilities`, `constraints` (a `list[str]`, not a dict), timestamps    |
| `delegations`  | `List[TrustDelegationRecord]`       | Delegations made under this chain                                                                     |
| `status`       | `str`                                | `"active"`, `"suspended"`, `"revoked"`                                                                |
| `human_origin` | `Optional[TrustHumanOriginInfo]`    | Human who authorized the chain (server-derived)                                                      |

Identity is **not** at the top level: read `chain.genesis.agent_id` and
`chain.genesis.authority_id`. There is no top-level `id` field on this model.

### List Trust Chains

```python
from aegis_sdk import PaginatedResponse, TrustChainStatus

result: PaginatedResponse = await client.trust.chains.list(
    agent_id="agent_abc123",          # Optional
    human_origin_id="user_123",       # Optional
    status=TrustChainStatus.ACTIVE,   # Optional
    page=1,
    page_size=20,
)

for chain in result.items:
    print(f"  Agent {chain.agent_id}: {chain.status}")
    print(f"    Capabilities: {chain.genesis.capabilities}")
```

### Get Trust Chain

`get()` returns `TrustChainLineage`, a **richer, differently-shaped** document
than a `list()` item — the full signed EATP lineage, not the flat summary.
Identity is nested under `genesis` here too; `chain.agent_id` and
`chain.authority_id` are convenience *properties* that read through to it, so
they work, but there is still no top-level `id` field to read instead.

```python
from aegis_sdk.trust.chains import TrustChainLineage

chain: TrustChainLineage = await client.trust.chains.get("agent_abc123")
print(f"Agent: {chain.agent_id}")                # property -> chain.genesis.agent_id
print(f"Authority: {chain.authority_id}")         # property -> chain.genesis.authority_id
print(f"Capabilities: {[c.capability for c in chain.capabilities]}")
print(f"Chain hash: {chain.chain_hash}")
```

⚠ The one argument this method takes is spelled `chain_id` in the signature
but **is an agent id** — every chain route in this API is keyed by agent, not
by a separate chain identifier.

⚠ `chain.capabilities` here is a list of `TrustLineageCapability` objects
(`.capability`, `.attester_id`, ...) — a genuinely different type from a
`list()` item's `genesis.capabilities`, which is a plain `list[str]`. Read the
type you actually have; the same-sounding attribute name on two different
methods is not a coincidence to rely on.

### Verify an Action

Check if an agent is authorized to perform an action. The target is
addressed as a **kind** plus an optional **instance** —
`resource_type` names what sort of thing is being acted on (required),
`resource_id` names which one (omit it to ask about the kind as a whole).
The older `resource=`/`context=` keywords shown in earlier examples are
**deprecated**: `context` is accepted and silently ignored (the route
evaluates only the chain's own recorded constraints, never a caller-supplied
one), and `resource` is folded into `resource_type` for backward compatibility
but raises `DeprecationWarning` on every call. This is one confirmed root
cause behind the partner-reported symptom *"trust verify fails validation as
the client sends it"* — a caller supplying neither `resource_type` nor the
deprecated `resource` gets a `ValidationError`, by design: the SDK will not
invent a resource kind that becomes part of the platform's audit record.

```python
from aegis_sdk.trust.chains import TrustVerificationOutcome

result: TrustVerificationOutcome = await client.trust.chains.verify(
    agent_id="agent_abc123",
    action="write",
    resource_type="report",
    resource_id="report_q4_2024",
)

if result.allowed:
    print(f"Authorized. Capabilities matched: {result.capabilities_matched}")
else:
    print(f"Denied: {result.reason}")
    print(f"Constraints violated: {result.constraints_violated}")
```

### TrustVerificationOutcome Model

⛔ `chain_id` and `constraints_applied` are inherited fields on this model and
are **always `None` / empty** — the verification route emits neither. A
caller reading them (as the previous revision of this doc showed) always gets
nothing, silently. Read `constraints_violated` for what decided a denial.

| Field                    | Type            | Description                                                      |
| ------------------------ | --------------- | ------------------------------------------------------------------ |
| `allowed`                | `bool`          | Whether the action is authorized                                   |
| `reason`                 | `Optional[str]` | Denial reason (if denied)                                          |
| `capabilities_matched`   | `List[str]`     | Capabilities that matched the request                              |
| `constraints_violated`   | `List[str]`     | Constraints that caused a denial (populated only on denial)        |
| `chain_id`               | `Optional[str]` | **Always `None`.** The route does not emit it. Do not rely on it.  |
| `constraints_applied`    | `List[str]`     | **Always `[]`.** The route does not emit it. Do not rely on it.    |

### Revoke a Trust Chain

Trust chains in this API are keyed by `agent_id`, not by a separate chain ID.
Revocation always cascades to delegated agents — the server has no
non-cascading revoke, so the `cascade` kwarg is deprecated and ignored.

```python
from aegis_sdk import CascadeRevocationResult

result: CascadeRevocationResult = await client.trust.chains.revoke(
    "agent_abc123",
    reason="Security incident detected",
)

print(f"Revoked {result.total_revoked} agents: {result.revoked_agent_ids}")
```

### Analyze Revocation Impact

Before revoking, preview the blast radius:

```python
from aegis_sdk import RevocationImpact

impact: RevocationImpact = await client.trust.chains.analyze_revocation_impact("agent_abc123")
print(f"Would affect {impact.total_affected} agents")
print(f"Active workloads at risk: {impact.has_active_workloads}")
for agent in impact.affected_agents:
    print(f"  {agent.agent_id} (depth {agent.delegation_depth})")
```

### Suspend and Reinstate

**Not currently supported.** `suspend()` and `reinstate()` are deprecated
shims — no server route exists for directly suspending or reinstating a
trust chain (checked against the published API on 2026-07-08). The internal
trust-chain state machine supports a `SUSPENDED` lifecycle state reached
automatically during cascade revocation of bridge-sourced chains, but it is
not exposed as a directly-invokable operation. Calling either method raises
`UnsupportedOperationError` and emits a `DeprecationWarning`; both methods
will be removed in a future release. See `CHANGELOG.md` for migration notes.

### Get Delegation Path

Trace the delegation path from human origin to the current agent. The
argument is an agent id, matching every other chain route.

⛔ The keys shown here used to be `from`/`to` — the real payload has no such
keys (silently printing `None -> None` for every step, forever) — and the
return type is the richer `AgentDelegationPath`, not the base `DelegationPath`.

```python
from aegis_sdk.trust.chains import AgentDelegationPath

path: AgentDelegationPath = await client.trust.chains.get_delegation_path("agent_abc123")
print(f"Depth: {path.depth} of max {path.max_depth_allowed}")
for step in path.path:
    print(f"  {step.get('delegator_id')} -> {step.get('delegatee_id')}: {step.get('capabilities')}")
```

`path.chain_id` is `None` for an agent with no established chain — the
platform answers that case with an empty path rather than an error, so
`None` here means "no chain", not "failed to load".

### Get Agent Trust Context

⛔ This used to document an `AgentTrustContext` model with `.posture`,
`.capabilities`, `.constraints` and `.delegation_depth` fields — **none of
which exist on what this method actually returns.** This is a second
confirmed root cause behind the *"trust context ... fails validation"* class
of partner symptom: code written against the fields below raises
`AttributeError` on the first line, on every call, unconditionally.

The real return is `AgentTrustContextDetail`: the agent's chain (or `None` if
none is established yet — that is a normal 200, not an error), its position
in the delegation path, and any computed warnings. It is not a flat
capability summary.

```python
from aegis_sdk.trust.chains import AgentTrustContextDetail

context: AgentTrustContextDetail = await client.trust.chains.get_agent_context("agent_abc123")
if context.trust_chain is None:
    print("No trust chain established yet")
else:
    print(f"Chain status: {context.trust_chain.status}")
print(f"Position in chain: {context.position}")
print(f"Expires in (days): {context.expires_in_days}")
print(f"Delegation path depth: {context.delegation_path.depth} of {context.delegation_path.max_depth_allowed}")
for warning in context.warnings:
    print(f"  ! [{warning.severity}] {warning.message}")
```

---

## Delegations (`client.trust.delegations`)

### Create a Delegation

Grant a subset of capabilities to another agent:

```python
from aegis_sdk import TrustDelegation

delegation: TrustDelegation = await client.trust.delegations.create(
    chain_id="chain_abc123",
    delegator_id="agent_coordinator",
    delegatee_id="agent_worker",
    capabilities=["read:data", "execute:analysis"],   # Must be subset of delegator's
    constraints={"max_runtime": 3600, "sandbox": True},
)

print(f"Delegation created: {delegation.id}")
print(f"Delegated capabilities: {delegation.capabilities}")
```

### TrustDelegation Model

| Field          | Type                 | Description                          |
| -------------- | -------------------- | ------------------------------------ |
| `id`           | `str`                | Delegation ID                        |
| `chain_id`     | `str`                | Parent trust chain                   |
| `delegator_id` | `str`                | Agent granting delegation            |
| `delegatee_id` | `str`                | Agent receiving delegation           |
| `capabilities` | `List[str]`          | Delegated capabilities               |
| `constraints`  | `Dict[str, Any]`     | Constraints on the delegation        |
| `status`       | `DelegationStatus`   | `"active"`, `"revoked"`, `"expired"` |
| `created_at`   | `datetime`           | Creation timestamp                   |
| `revoked_at`   | `Optional[datetime]` | Revocation timestamp                 |

### List Delegations

```python
from aegis_sdk import PaginatedResponse, DelegationStatus

result: PaginatedResponse = await client.trust.delegations.list(
    chain_id="chain_abc123",           # Optional
    delegator_id="agent_coordinator",  # Optional
    delegatee_id="agent_worker",       # Optional
    status=DelegationStatus.ACTIVE,    # Optional
    page=1,
    page_size=20,
)

for d in result.items:
    print(f"  {d.delegator_id} -> {d.delegatee_id}: {d.capabilities}")
```

### Revoke a Delegation

```python
from aegis_sdk import TrustDelegation

delegation: TrustDelegation = await client.trust.delegations.revoke(
    "del_abc123",
    reason="Task completed",
    cascade=True,   # Also revoke sub-delegations
)

print(f"Revoked: {delegation.status}")
```

### Get Delegations for an Agent

⛔ **`get_for_agent()` is a deprecation shim that ALWAYS raises
`UnsupportedOperationError`** — there is no `/agents/{agent_id}/delegations`
route on the backend, in either direction, and it is kept only so a caller
gets a typed, actionable error instead of a bare 404. Calling it as shown in
earlier examples fails on the first call, every time.

There is a **partial** substitute, for delegations *received* only (nothing
is servable for delegations *granted*, because that data lives in the chains
of whichever agents this one delegated to, which are not enumerable from
here). It comes from the chain's own lineage, and the entries are raw
`dict`s, not `TrustDelegation` objects:

```python
chain = await client.trust.chains.get("agent_abc123")   # TrustChainLineage
received = [d for d in chain.delegations if d.get("delegatee_id") == "agent_abc123"]
for d in received:
    print(f"  Received from {d.get('delegator_id')}: {d.get('capabilities')}")
```

---

## Postures (`client.trust.postures`)

### Posture Levels

| Posture    | Description                                   |
| ---------- | --------------------------------------------- |
| `pseudo`             | Human approval required for all actions       |
| `supervised`         | Human approval for high-impact actions        |
| `shared_planning`    | Autonomous low-risk, approval for medium/high |
| `continuous_insight` | Autonomous medium-risk, approval for high     |
| `delegated`          | Fully autonomous (rarely granted)             |

⛔ **Every model name in this section (`TrustPostureInfo`, `PostureMetrics`)
below used to be wrong for the method it was attached to** — the types exist
in the package (so the `import` line does not fail), but they are not what
these methods return, and the field names below do not exist on the real
objects. Confirmed root cause of two partner symptoms: (1) *"`request_progression`
cannot parse the approval-pending reply and raises after the server
accepted"* — the true return type carries a governed pending/applied branch
this section did not show, so code shaped like the old example could not
tell the two outcomes apart; and (2) a caller reading `info.progression_eligible`
or `metrics.tasks_completed` gets `AttributeError` on every call, since
neither field exists.

### Get Current Posture

`get()` returns `PostureState`, the posture **currently in force** — it
carries no progression verdict at all (there is a dedicated call for that,
below).

```python
from aegis_sdk.trust.postures import PostureState

state: PostureState = await client.trust.postures.get("agent_abc123")
print(f"Current posture: {state.posture}")
print(f"In force since: {state.current_since}")
print(f"Configured by: {state.configured_by_name or state.configured_by}")
print(f"Override active: {state.override_active}")
```

### Request Progression

`request_progression()` returns `PostureChangeResult`, which has **two
outcomes that demand opposite next actions** — this is the part the earlier
example collapsed into one. Raising an agent above `supervised` is held for a
human approval; while it is pending, `result.posture` reports the posture the
agent is **still running at**, not the requested one. **Do not re-issue the
call to "make it take"** — the endpoint has no idempotency key, so a retry
after an ambiguous failure (timeout, dropped connection) files a *second*
pending request. Call `get_pending_approval()` first to find out whether the
original attempt already landed.

```python
from aegis_sdk.trust.postures import PostureChangeResult

result: PostureChangeResult = await client.trust.postures.request_progression(
    "agent_abc123",
    target_posture="shared_planning",
    justification="Completed 100 tasks with 99% success rate over 30 days",
)
if result.approval_pending:
    print(f"Awaiting approval: {result.approval_id}")
    print(f"Still running at: {result.posture}")   # NOT the requested posture yet
else:
    print(f"Applied: now {result.posture}")
```

### Approving a pending transition — safe only with ONE pending request

`approve_transition(agent_id, notes=None)` is addressed **by agent, not by
request** — it takes no request identifier, because the endpoint resolves the
agent's pending request itself. With more than one request pending for the
same agent, which one this call decides is **not determined by anything the
caller controls**. This is the confirmed root cause behind the
partner-reported symptom *"`approve_transition` sends no `request_id`, so
with two pending requests the server refuses"* — there is no `request_id`
parameter to send; the fix is to never let two requests be pending at once.

```python
pending = await client.trust.postures.get_pending_approval("agent_abc123")
if pending is not None:
    print(f"Pending: {pending.id} -> {pending.requested_posture}")
    result = await client.trust.postures.approve_transition(
        "agent_abc123",
        notes="Reviewed evidence, approved",
    )
    print(f"Applied: now {result.posture}")
```

`get_pending_approval()` returns **at most one** record even when several are
pending — `None` means nothing is pending; a record does *not* mean exactly
one is.

### Override Posture (Admin)

Same endpoint and same `PostureChangeResult` return as `request_progression()`
above — a downward override applies immediately, but an override that
*raises* the posture above `supervised` is held for approval exactly like a
normal progression request. Branch on `approval_pending`; do not assume an
override always takes effect at once.

```python
from aegis_sdk.trust.postures import PostureChangeResult

result: PostureChangeResult = await client.trust.postures.override(
    "agent_abc123",
    new_posture="pseudo",
    reason="Security review pending -- restricting to pseudo posture",
)
assert not result.approval_pending   # true for a downward change
print(f"Now restricted to: {result.posture}")
```

### Get Posture Metrics

`get_metrics()` returns `PostureProgressionMetrics` — behavioural rates the
progression evaluation is computed from, not task counts.

```python
from aegis_sdk.trust.postures import PostureProgressionMetrics

metrics: PostureProgressionMetrics = await client.trust.postures.get_metrics("agent_abc123")
print(f"Interactions: {metrics.interaction_count}")
print(f"Approval rate: {metrics.approval_rate:.1%}")
print(f"Override rate: {metrics.override_rate:.1%}")
print(f"Error rate: {metrics.error_rate:.1%}")
print(f"Autonomous success rate: {metrics.autonomous_success_rate}")
print(f"Last evaluated: {metrics.last_evaluated_at}")
```

Eligibility is a separate question with its own route — do not infer it from
these metrics:

```python
from aegis_sdk.trust.postures import ProgressionEvaluation

evaluation: ProgressionEvaluation = await client.trust.postures.evaluate_progression("agent_abc123")
print(f"Can progress: {evaluation.can_progress}")
if evaluation.blockers:
    for blocker in evaluation.blockers:
        print(f"  Blocked by: {blocker}")
```

---

## Audit (`client.trust.audit`)

### Query Audit Logs

```python
from datetime import datetime
from aegis_sdk import PaginatedResponse

result: PaginatedResponse = await client.trust.audit.query(
    agent_id="agent_abc123",          # Optional
    human_origin_id="user_123",       # Optional
    action_type="verify",             # "establish", "delegate", "verify", "revoke", "override"
    start_date=datetime(2024, 1, 1),  # Optional
    end_date=datetime(2024, 12, 31),  # Optional
    page=1,
    page_size=50,
)

print(f"Found {result.total} audit entries")
for entry in result.items:
    print(f"  {entry.timestamp}: {entry.action_type} -> {entry.result}")
    print(f"    Agent: {entry.agent_id}")
    print(f"    Data: {entry.action_data}")
```

### TrustAuditEntry Model

| Field             | Type             | Description                                                       |
| ----------------- | ---------------- | ----------------------------------------------------------------- |
| `id`              | `str`            | Entry ID                                                          |
| `timestamp`       | `datetime`       | When the action occurred                                          |
| `agent_id`        | `str`            | Agent involved                                                    |
| `human_origin_id` | `str`            | Human origin                                                      |
| `action_type`     | `str`            | `"establish"`, `"delegate"`, `"verify"`, `"revoke"`, `"override"` |
| `action_data`     | `Dict[str, Any]` | Action details                                                    |
| `result`          | `str`            | `"success"`, `"failure"`, `"blocked"`                             |
| `chain_id`        | `Optional[str]`  | Associated chain ID                                               |

### Get Specific Entry

```python
from aegis_sdk import TrustAuditEntry

entry: TrustAuditEntry = await client.trust.audit.get_entry("audit_abc123")
print(f"Action: {entry.action_type}")
print(f"Result: {entry.result}")
print(f"Data: {entry.action_data}")
```

### Get Chain History

Get the complete audit trail for a specific trust chain:

```python
from aegis_sdk import TrustAuditEntry
from typing import List

history: List[TrustAuditEntry] = await client.trust.audit.get_chain_history("chain_abc123")
for entry in history:
    print(f"  {entry.timestamp}: {entry.action_type} ({entry.result})")
```

---

## Full Trust Workflow Example

⛔ This section used to carry its own independent copy of a workflow that
already exists as a shipped, signature-pinned example
(`examples/trust_chain_management.py` — CI fails if any call in it stops
binding against the real SDK, per
`tests/deployment/test_sdk_examples_bind_real_signatures.py`). That
independence is exactly how it drifted: the embedded copy kept the
deprecated `verify(resource=...)` call and a bare `TrustVerificationResult`
type hint long after the real example (and the SDK itself) moved on. Rather
than re-introduce a second copy for the next release to drift again, this
section now points at the one that is checked:

**[`examples/trust_chain_management.py`](../../examples/trust_chain_management.py)**
— establish, verify, delegate, manage postures (including the
approval-pending branch), inspect trust context, analyze and revoke, and
query the audit trail, all against the real, current signatures.

A short, verified fragment for the two calls this page corrects above:

```python
from aegis_sdk import AgenticOSClient

async with AgenticOSClient.from_env() as client:
    chain = await client.trust.chains.establish(
        agent_id="agent_coordinator",
        authority_id="authority_ceo_office",
        capabilities=["read:all", "write:reports"],
        constraints=["max_cost:10000"],
    )
    result = await client.trust.chains.verify(
        agent_id="agent_coordinator",
        action="write",
        resource_type="report",
        resource_id="quarterly_report",
    )
    assert result.allowed, f"Verification failed: {result.reason}"
```

## Related

- [Agents Module](agents.md) -- Agent management
- [Error Handling](../error-handling.md) -- `TrustViolationError` handling
- [Code Example](../../examples/trust_chain_management.py) -- Complete trust workflow
