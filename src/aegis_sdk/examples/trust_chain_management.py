"""
Trust Chain Management Example

Demonstrates: establishing trust chains, delegating capabilities, verifying
actions, managing postures, and querying audit logs using the EATP module.

Prerequisites:
    # NOT on PyPI -- `pip install aegis-sdk` installs an unrelated
    # third-party package. Install from source (see docs/quickstart.md):
    pip install -e .
    export AGENTIC_OS_BASE_URL=https://your-deployment.example.com   # REQUIRED, no default
    export AGENTIC_OS_API_KEY=sk_live_your_key_here
"""

import asyncio
from datetime import UTC, datetime, timedelta

from aegis_sdk import (
    AgenticOSClient,
    AgenticOSError,
    AgentTrustContext,
    DelegationPath,
    EstablishedTrustChain,
    PostureMetrics,
    RevocationImpact,
    TrustDelegation,
    TrustPostureInfo,
    TrustVerificationResult,
    TrustViolationError,
)


async def establish_trust_chain(client: AgenticOSClient) -> EstablishedTrustChain:
    """Establish a trust chain from a human origin to an agent.

    Trust chains are the foundation of EATP -- they connect every agent
    action back to a human authorization. The server derives human_origin
    from the AUTHENTICATED CALLER (never client-supplied); chains in this
    API are keyed by agent_id, not a separate chain ID.
    """
    print("=== Step 1: Establish Trust Chain ===\n")

    chain: EstablishedTrustChain = await client.trust.chains.establish(
        agent_id="agent_coordinator",
        authority_id="authority_ceo_office",
        capabilities=[
            "read:all",
            "write:reports",
            "write:analysis",
            "execute:workflows",
            "delegate:sub",
        ],
        constraints=[
            "max_cost:10000",
            "max_delegation_depth:3",
            "allowed_regions:us-west-2,us-east-1",
            "require_approval_above:5000",
        ],
    )

    print(f"Chain established for agent: {chain.agent_id}")
    print(f"  Status: {chain.status}")
    print(f"  Capabilities: {chain.genesis.capabilities}")
    print(f"  Constraints: {chain.genesis.constraints}")
    print(f"  Authority: {chain.genesis.authority_id}")

    return chain


async def verify_action(client: AgenticOSClient) -> None:
    """Verify if an agent is authorized to perform a specific action.

    Verification checks the trust chain's capabilities and constraints
    against the requested action.
    """
    print("\n=== Step 2: Verify Actions ===\n")

    # Verify an allowed action
    result: TrustVerificationResult = await client.trust.chains.verify(
        agent_id="agent_coordinator",
        action="write",
        resource="quarterly_report",
        context={"cost": 50, "region": "us-west-2"},
    )

    if result.allowed:
        print(f"Action ALLOWED via chain: {result.chain_id}")
        print(f"  Constraints applied: {result.constraints_applied}")
    else:
        print(f"Action DENIED: {result.reason}")

    # Verify an action that might be denied
    try:
        result_restricted = await client.trust.chains.verify(
            agent_id="agent_coordinator",
            action="delete",
            resource="production_database",
        )
        if not result_restricted.allowed:
            print(f"\nRestricted action denied: {result_restricted.reason}")
    except TrustViolationError as e:
        print(f"\nTrust violation: {e.message}")
        print(f"  Details: {e.details}")


async def delegate_capabilities(
    client: AgenticOSClient, chain: EstablishedTrustChain
) -> TrustDelegation:
    """Delegate a subset of capabilities to a worker agent.

    Delegations must grant a subset of the delegator's capabilities.
    Constraints can only be tightened, never loosened.
    """
    print("\n=== Step 3: Delegate Capabilities ===\n")

    delegation: TrustDelegation = await client.trust.delegations.create(
        chain_id=chain.agent_id,
        delegator_id="agent_coordinator",
        delegatee_id="agent_worker",
        capabilities=["read:all", "write:reports"],  # Subset of coordinator's
        constraints={
            "max_cost": 1000,  # Tighter than coordinator's 10000
            "sandbox": True,
            "max_runtime_seconds": 3600,
        },
    )

    print(f"Delegation created: {delegation.id}")
    print(f"  From: {delegation.delegator_id}")
    print(f"  To: {delegation.delegatee_id}")
    print(f"  Capabilities: {delegation.capabilities}")
    print(f"  Constraints: {delegation.constraints}")
    print(f"  Status: {delegation.status}")

    # List all delegations for the coordinator
    delegations: list[TrustDelegation] = await client.trust.delegations.get_for_agent(
        "agent_coordinator",
        include_granted=True,
        include_received=True,
    )
    print(f"\nCoordinator's delegations: {len(delegations)}")
    for d in delegations:
        direction = "granted" if d.delegator_id == "agent_coordinator" else "received"
        other = d.delegatee_id if direction == "granted" else d.delegator_id
        print(f"  [{direction}] {other}: {d.capabilities}")

    return delegation


async def manage_postures(client: AgenticOSClient) -> None:
    """Check and manage agent trust postures.

    Postures progress from pseudo to delegated based on track record:
    pseudo -> supervised -> shared_planning -> continuous_insight -> delegated
    """
    print("\n=== Step 4: Manage Postures ===\n")

    # Get current posture
    info: TrustPostureInfo = await client.trust.postures.get("agent_worker")
    print(f"Worker posture: {info.posture}")
    print(f"  Eligible for progression: {info.progression_eligible}")
    print(f"  Last assessment: {info.last_assessment}")

    # Get progression metrics
    metrics: PostureMetrics = await client.trust.postures.get_metrics("agent_worker")
    print("\nPosture metrics:")
    print(f"  Tasks completed: {metrics.tasks_completed}")
    print(f"  Successful verifications: {metrics.successful_verifications}")
    print(f"  Failed verifications: {metrics.failed_verifications}")
    print(f"  Days at current posture: {metrics.time_at_current}")
    print(f"  Progression score: {metrics.progression_score}")

    if metrics.successful_verifications + metrics.failed_verifications > 0:
        success_rate = (
            metrics.successful_verifications
            / (metrics.successful_verifications + metrics.failed_verifications)
            * 100
        )
        print(f"  Success rate: {success_rate:.1f}%")

    # Request progression if eligible
    if info.progression_eligible:
        print("\nRequesting posture progression...")
        new_info: TrustPostureInfo = await client.trust.postures.request_progression(
            "agent_worker",
            target_posture="shared_planning",
            justification=(
                f"Completed {metrics.tasks_completed} tasks with "
                f"{metrics.progression_score:.1f} progression score"
            ),
        )
        print(f"  New posture: {new_info.posture}")

    # Override posture (admin action)
    # override_info = await client.trust.postures.override(
    #     "agent_worker",
    #     new_posture="pseudo",
    #     reason="Security review pending",
    # )
    # print(f"  Override to: {override_info.posture}")


async def inspect_trust_context(client: AgenticOSClient, chain: EstablishedTrustChain) -> None:
    """Inspect an agent's trust context and delegation path."""
    print("\n=== Step 5: Inspect Trust Context ===\n")

    # Get agent trust context
    context: AgentTrustContext = await client.trust.chains.get_agent_context("agent_coordinator")
    print("Agent trust context:")
    print(f"  Agent: {context.agent_id}")
    print(f"  Chain: {context.chain_id}")
    print(f"  Posture: {context.posture}")
    print(f"  Capabilities: {context.capabilities}")
    print(f"  Constraints: {context.constraints}")
    print(f"  Delegation depth: {context.delegation_depth}")

    # Get delegation path
    path: DelegationPath = await client.trust.chains.get_delegation_path(chain.agent_id)
    print(f"\nDelegation path (depth: {path.depth}):")
    for step in path.path:
        print(f"  {step.get('from', 'origin')} -> {step.get('to', 'agent')}")
        print(f"    Capabilities: {step.get('capabilities', [])}")


async def analyze_and_revoke(
    client: AgenticOSClient,
    chain: EstablishedTrustChain,
    delegation: TrustDelegation,
) -> None:
    """Analyze revocation impact and revoke delegation/chain.

    NOTE: suspend()/reinstate() are NOT demonstrated here — they have no
    backing server route and always raise
    UnsupportedOperationError. Use revoke() for permanent removal.
    """
    print("\n=== Step 6: Revocation ===\n")

    # Analyze impact before revoking
    impact: RevocationImpact = await client.trust.chains.analyze_revocation_impact(chain.agent_id)
    print("Revocation impact analysis:")
    print(f"  Would affect: {impact.total_affected} agents")
    print(f"  Active workloads at risk: {impact.has_active_workloads}")
    for affected in impact.affected_agents:
        print(f"    {affected.agent_id} (depth {affected.delegation_depth})")

    # Revoke the delegation first
    revoked_delegation: TrustDelegation = await client.trust.delegations.revoke(
        delegation.id,
        reason="Task completed, delegation no longer needed",
        cascade=True,
    )
    print(f"\nDelegation revoked: {revoked_delegation.status}")

    # Final revocation (permanent) -- cascades to all delegated agents
    # revoked = await client.trust.chains.revoke(
    #     chain.agent_id,
    #     reason="Project completed",
    # )
    # print(f"Chain revoked: {revoked.total_revoked} agents")


async def query_audit_logs(client: AgenticOSClient, chain: EstablishedTrustChain) -> None:
    """Query trust audit logs for compliance and forensics."""
    print("\n=== Step 7: Audit Logs ===\n")

    # Query all verification events in the last 30 days
    start_date = datetime.now(UTC) - timedelta(days=30)
    result = await client.trust.audit.query(
        agent_id="agent_coordinator",
        action_type="verify",
        start_date=start_date,
        page=1,
        page_size=10,
    )

    print(f"Verification events (last 30 days): {result.total}")
    for entry in result.items:
        print(f"  {entry.timestamp}: {entry.action_type} -> {entry.result}")
        print(f"    Agent: {entry.agent_id}")

    # Get full audit trail for the chain
    history = await client.trust.audit.get_chain_history(chain.agent_id)
    print(f"\nChain {chain.agent_id} audit trail ({len(history)} entries):")
    for entry in history:
        print(f"  {entry.timestamp}: {entry.action_type} ({entry.result})")
        if entry.action_data:
            print(f"    Data: {entry.action_data}")


async def main() -> None:
    """Run the complete trust chain management workflow."""
    async with AgenticOSClient.from_env() as client:
        # Step 1: Establish trust chain
        chain = await establish_trust_chain(client)

        # Step 2: Verify actions
        await verify_action(client)

        # Step 3: Delegate capabilities
        delegation = await delegate_capabilities(client, chain)

        # Step 4: Manage postures
        await manage_postures(client)

        # Step 5: Inspect trust context
        await inspect_trust_context(client, chain)

        # Step 6: Revocation
        await analyze_and_revoke(client, chain, delegation)

        # Step 7: Audit logs
        await query_audit_logs(client, chain)

        print("\n=== Trust chain workflow complete ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AgenticOSError as e:
        print(f"\nSDK error: {e.message}")
        if e.details:
            print(f"Details: {e.details}")
    except KeyboardInterrupt:
        print("\nInterrupted")
