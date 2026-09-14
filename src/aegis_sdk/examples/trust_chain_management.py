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
    EstablishedTrustChain,
    RevocationImpact,
    TrustDelegation,
    TrustVerificationResult,
    TrustViolationError,
)
from aegis_sdk.trust.chains import AgentDelegationPath, AgentTrustContextDetail
from aegis_sdk.trust.postures import (
    PostureChangeResult,
    PostureProgressionMetrics,
    PostureState,
    ProgressionEvaluation,
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

    # NOTE: DelegationsModule.get_for_agent() is a deprecation shim that
    # ALWAYS raises UnsupportedOperationError -- there is no
    # /agents/{agent_id}/delegations route on the backend, in either
    # direction. Calling it here would crash this example on every run.
    # The only servable substitute covers delegations RECEIVED (not
    # granted), and it comes from the chain's own lineage:
    received = [
        d
        for d in chain.delegations
        if d.get("delegatee_id") == "agent_coordinator"  # raw dicts, not TrustDelegation
    ]
    print(f"\nCoordinator's received delegations (lineage substitute): {len(received)}")
    for d in received:
        print(f"  [received] from {d.get('delegator_id')}: {d.get('capabilities')}")
    print(
        "  (There is no servable list of delegations GRANTED by this agent -- "
        "that data lives in the chains of whichever agents it delegated to.)"
    )

    return delegation


async def manage_postures(client: AgenticOSClient) -> None:
    """Check and manage agent trust postures.

    Postures progress from pseudo to delegated based on track record:
    pseudo -> supervised -> shared_planning -> continuous_insight -> delegated
    """
    print("\n=== Step 4: Manage Postures ===\n")

    # Get current posture. The posture routes report the posture IN FORCE and
    # who put it there -- they do NOT carry a progression verdict.
    state: PostureState = await client.trust.postures.get("agent_worker")
    print(f"Worker posture: {state.posture}")
    print(f"  In force since: {state.current_since}")
    print(f"  Configured by: {state.configured_by_name or state.configured_by}")
    print(f"  Override active: {state.override_active}")

    # Get progression metrics
    metrics: PostureProgressionMetrics = await client.trust.postures.get_metrics("agent_worker")
    print("\nPosture metrics:")
    print(f"  Interactions: {metrics.interaction_count}")
    print(f"  Approval rate: {metrics.approval_rate:.1%}")
    print(f"  Override rate: {metrics.override_rate:.1%}")
    print(f"  Error rate: {metrics.error_rate:.1%}")
    print(f"  Autonomous success rate: {metrics.autonomous_success_rate:.1%}")
    print(f"  Last evaluated: {metrics.last_evaluated_at}")

    # Eligibility is its own question, answered by its own route -- ask it
    # rather than inferring one from the metrics above.
    evaluation: ProgressionEvaluation = await client.trust.postures.evaluate_progression(
        "agent_worker"
    )
    print(f"\nCan progress: {evaluation.can_progress}")
    if evaluation.blockers:
        for blocker in evaluation.blockers:
            print(f"  Blocked by: {blocker}")

    # Request progression if eligible
    if evaluation.can_progress and evaluation.next_posture:
        print("\nRequesting posture progression...")
        result: PostureChangeResult = await client.trust.postures.request_progression(
            "agent_worker",
            target_posture=evaluation.next_posture,
            justification=(
                f"{metrics.interaction_count} interactions at "
                f"{metrics.autonomous_success_rate:.1%} autonomous success rate"
            ),
        )
        # A posture change may APPLY IMMEDIATELY or require manager approval.
        # Branch on it: the two outcomes demand opposite next actions, and a
        # caller that cannot tell them apart will re-issue an accepted request
        # and create a duplicate pending approval.
        if result.approval_pending:
            print(f"  Awaiting approval (approval id: {result.approval_id})")
            print(f"  Posture still in force: {result.posture}")
            print("  Do NOT re-issue this request -- poll get_pending_approval() instead.")
        else:
            print(f"  New posture applied: {result.posture}")

    # Override posture (admin action). Returns the same PostureChangeResult,
    # so it carries the same approval_pending branch as above.
    # override_result = await client.trust.postures.override(
    #     "agent_worker",
    #     new_posture="pseudo",
    #     reason="Security review pending",
    # )
    # print(f"  Override to: {override_result.posture}")


async def inspect_trust_context(client: AgenticOSClient, chain: EstablishedTrustChain) -> None:
    """Inspect an agent's trust context and delegation path."""
    print("\n=== Step 5: Inspect Trust Context ===\n")

    # Get agent trust context. This route returns the agent's POSITION in its
    # chain plus any standing warnings -- not a flat capability summary.
    context: AgentTrustContextDetail = await client.trust.chains.get_agent_context(
        "agent_coordinator"
    )
    print("Agent trust context:")
    print(f"  Position in chain: {context.position}")
    print(f"  Expires in (days): {context.expires_in_days}")
    print(f"  Has warnings: {context.has_warnings}")
    for warning in context.warnings:
        print(f"    ! {warning}")
    if context.trust_chain is not None:
        print(f"  Trust chain: {context.trust_chain}")

    # Get delegation path
    path: AgentDelegationPath = await client.trust.chains.get_delegation_path(chain.agent_id)
    print(f"\nDelegation path (depth: {path.depth} of max {path.max_depth_allowed}):")
    for step in path.path:
        delegator = step.get("delegator_id", "origin")
        delegatee = step.get("delegatee_id", "agent")
        print(
            f"  {delegator} ({step.get('delegator_type', '?')})"
            f" -> {delegatee} ({step.get('delegatee_type', '?')})"
        )
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
