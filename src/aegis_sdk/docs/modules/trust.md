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

Returned by `get()` and `list()` (unchanged by this reconciliation).

| Field               | Type                 | Description                            |
| ------------------- | -------------------- | -------------------------------------- |
| `id`                | `str`                | Chain ID                               |
| `agent_id`          | `str`                | Agent this chain authorizes            |
| `human_origin_id`   | `str`                | Human who originated the trust         |
| `human_origin_data` | `Dict[str, Any]`     | Data about the human origin            |
| `capabilities`      | `List[str]`          | Granted capabilities                   |
| `constraints`       | `Dict[str, Any]`     | Constraints on the chain               |
| `status`            | `TrustChainStatus`   | `"active"`, `"suspended"`, `"revoked"` |
| `delegation_depth`  | `int`                | Current delegation depth               |
| `created_at`        | `datetime`           | Creation timestamp                     |
| `revoked_at`        | `Optional[datetime]` | Revocation timestamp                   |

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
    print(f"  Chain {chain.id}: {chain.status} (depth: {chain.delegation_depth})")
```

### Get Trust Chain

```python
from aegis_sdk import TrustChain

chain: TrustChain = await client.trust.chains.get("chain_abc123")
print(f"Agent: {chain.agent_id}")
print(f"Capabilities: {chain.capabilities}")
print(f"Constraints: {chain.constraints}")
```

### Verify an Action

Check if an agent is authorized to perform an action:

```python
from aegis_sdk import TrustVerificationResult

result: TrustVerificationResult = await client.trust.chains.verify(
    agent_id="agent_abc123",
    action="write",
    resource="report_q4_2024",
    context={"cost": 50, "region": "us-west-2"},
)

if result.allowed:
    print(f"Authorized via chain: {result.chain_id}")
    print(f"Constraints applied: {result.constraints_applied}")
else:
    print(f"Denied: {result.reason}")
```

### TrustVerificationResult Model

| Field                 | Type            | Description                        |
| --------------------- | --------------- | ---------------------------------- |
| `allowed`             | `bool`          | Whether the action is authorized   |
| `chain_id`            | `Optional[str]` | Chain that authorized (if allowed) |
| `reason`              | `Optional[str]` | Denial reason (if denied)          |
| `constraints_applied` | `List[str]`     | Constraints that were evaluated    |

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

Trace the delegation path from human origin to the current agent:

```python
from aegis_sdk import DelegationPath

path: DelegationPath = await client.trust.chains.get_delegation_path("chain_abc123")
print(f"Depth: {path.depth}")
for step in path.path:
    print(f"  {step.get('from')} -> {step.get('to')}: {step.get('capabilities')}")
```

### Get Agent Trust Context

Get the current trust context for an agent:

```python
from aegis_sdk import AgentTrustContext

context: AgentTrustContext = await client.trust.chains.get_agent_context("agent_abc123")
print(f"Posture: {context.posture}")
print(f"Capabilities: {context.capabilities}")
print(f"Constraints: {context.constraints}")
print(f"Delegation depth: {context.delegation_depth}")
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

```python
from aegis_sdk import TrustDelegation
from typing import List

delegations: List[TrustDelegation] = await client.trust.delegations.get_for_agent(
    "agent_abc123",
    include_granted=True,     # Delegations this agent granted
    include_received=True,    # Delegations this agent received
)

for d in delegations:
    if d.delegator_id == "agent_abc123":
        print(f"  Granted to {d.delegatee_id}: {d.capabilities}")
    else:
        print(f"  Received from {d.delegator_id}: {d.capabilities}")
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

### Get Current Posture

```python
from aegis_sdk import TrustPostureInfo

info: TrustPostureInfo = await client.trust.postures.get("agent_abc123")
print(f"Current posture: {info.posture}")
print(f"Eligible for progression: {info.progression_eligible}")
print(f"Last assessment: {info.last_assessment}")
```

### Request Progression

```python
from aegis_sdk import TrustPostureInfo

info: TrustPostureInfo = await client.trust.postures.request_progression(
    "agent_abc123",
    target_posture="shared_planning",
    justification="Completed 100 tasks with 99% success rate over 30 days",
)

print(f"New posture: {info.posture}")
```

### Override Posture (Admin)

```python
from aegis_sdk import TrustPostureInfo

info: TrustPostureInfo = await client.trust.postures.override(
    "agent_abc123",
    new_posture="pseudo",
    reason="Security review pending -- restricting to pseudo posture",
)

print(f"Overridden to: {info.posture}")
```

### Get Posture Metrics

```python
from aegis_sdk import PostureMetrics

metrics: PostureMetrics = await client.trust.postures.get_metrics("agent_abc123")
print(f"Tasks completed: {metrics.tasks_completed}")
print(f"Successful verifications: {metrics.successful_verifications}")
print(f"Failed verifications: {metrics.failed_verifications}")
print(f"Days at current posture: {metrics.time_at_current}")
print(f"Progression score: {metrics.progression_score}")

if metrics.successful_verifications + metrics.failed_verifications > 0:
    success_rate = (
        metrics.successful_verifications
        / (metrics.successful_verifications + metrics.failed_verifications)
        * 100
    )
    print(f"Success rate: {success_rate:.1f}%")
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

```python
import asyncio
from aegis_sdk import (
    AgenticOSClient,
    EstablishedTrustChain,
    TrustVerificationResult,
    TrustDelegation,
    TrustViolationError,
    RevocationImpact,
)

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        # 1. Establish trust chain (server derives human_origin from the
        #    authenticated caller; chains are keyed by agent_id, not a
        #    separate chain ID)
        chain: EstablishedTrustChain = await client.trust.chains.establish(
            agent_id="agent_coordinator",
            authority_id="authority_ceo_office",
            capabilities=["read:all", "write:reports", "execute:workflows", "delegate:sub"],
            constraints=["max_cost:10000", "max_delegation_depth:2"],
        )
        print(f"Chain established for: {chain.agent_id}")

        # 2. Verify an action
        result: TrustVerificationResult = await client.trust.chains.verify(
            agent_id="agent_coordinator",
            action="write",
            resource="quarterly_report",
        )
        assert result.allowed, f"Verification failed: {result.reason}"

        # 3. Delegate to a worker
        delegation: TrustDelegation = await client.trust.delegations.create(
            chain_id=chain.agent_id,
            delegator_id="agent_coordinator",
            delegatee_id="agent_worker",
            capabilities=["read:all", "write:reports"],
            constraints={"max_cost": 1000},
        )
        print(f"Delegated: {delegation.capabilities}")

        # 4. Check posture
        posture = await client.trust.postures.get("agent_worker")
        print(f"Worker posture: {posture.posture}")

        # 5. Verify worker action
        try:
            worker_result = await client.trust.chains.verify(
                agent_id="agent_worker",
                action="write",
                resource="analysis_report",
            )
            print(f"Worker authorized: {worker_result.allowed}")
        except TrustViolationError as e:
            print(f"Trust violation: {e.message}")

        # 6. Analyze revocation impact before revoking
        impact: RevocationImpact = await client.trust.chains.analyze_revocation_impact(
            chain.agent_id
        )
        print(f"Revocation would affect {impact.total_affected} agents")

        # 7. Revoke delegation
        await client.trust.delegations.revoke(
            delegation.id,
            reason="Task completed",
            cascade=True,
        )

        # 8. Query audit trail
        audit = await client.trust.audit.get_chain_history(chain.agent_id)
        print(f"Audit trail: {len(audit)} entries")

asyncio.run(main())
```

## Related

- [Agents Module](agents.md) -- Agent management
- [Error Handling](../error-handling.md) -- `TrustViolationError` handling
- [Code Example](../../examples/trust_chain_management.py) -- Complete trust workflow
