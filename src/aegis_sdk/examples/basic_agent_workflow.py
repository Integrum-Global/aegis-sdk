"""
Basic Agent Workflow Example

Demonstrates: creating an agent, submitting an objective, monitoring progress,
and collecting results using the Agentic OS SDK.

Prerequisites:
    # NOT on PyPI -- `pip install aegis-sdk` installs an unrelated
    # third-party package. Install from source (see docs/quickstart.md):
    pip install -e .
    export AGENTIC_OS_BASE_URL=https://your-deployment.example.com   # REQUIRED, no default
    export AGENTIC_OS_API_KEY=sk_live_your_key_here
    export AGENTIC_OS_MODEL=<your model id>                          # examples never hardcode one
    export AGENTIC_OS_WORKSPACE_ID=<your workspace id>               # agents.create() requires it
"""

import asyncio
import os
from typing import Any

from aegis_sdk import (
    Agent,
    AgentExecution,
    AgenticOSClient,
    AgenticOSError,
    AuthenticationError,
    NotFoundError,
    Objective,
    PaginatedResponse,
    ValidationError,
)


async def main() -> None:
    """Run the basic agent workflow."""
    async with AgenticOSClient.from_env() as client:
        # ----------------------------------------------------------------
        # Step 1: Verify authentication
        # ----------------------------------------------------------------
        # NOT client.auth.get_current_user() -- it resolves a real User
        # database row and raises AuthenticationError ("User not found")
        # for an API-key principal (this example authenticates via
        # AGENTIC_OS_API_KEY, per the prerequisites above), which has no
        # user row. agents:read works for both a JWT session and a
        # scoped API key.
        try:
            agents = await client.agents.list(page_size=1)
            print(f"Authenticated. Organization has {agents.total} agent(s).")
        except AuthenticationError as e:
            print(f"Authentication failed: {e.message}")
            return

        # ----------------------------------------------------------------
        # Step 2: Create an agent
        # ----------------------------------------------------------------
        try:
            # `workspace_id` is REQUIRED: agents.create() pre-flights it and
            # raises ValidationError before any request goes out, because the
            # server's CreateAgentRequest requires it.
            agent: Agent = await client.agents.create(
                name="Research Assistant",
                agent_type="chat",
                workspace_id=os.environ["AGENTIC_OS_WORKSPACE_ID"],
                model_id=os.environ["AGENTIC_OS_MODEL"],
                system_prompt=(
                    "You are a research assistant that finds, analyzes, "
                    "and summarizes information on technical topics."
                ),
                capabilities=["research", "summarization", "analysis"],
                description="AI assistant for research and analysis tasks",
            )
            print(f"\nAgent created: {agent.name}")
            print(f"  ID: {agent.id}")
            print(f"  Type: {agent.agent_type}")
            print(f"  Status: {agent.status}")
        except ValidationError as e:
            print(f"Failed to create agent: {e.message}")
            return

        # ----------------------------------------------------------------
        # Step 3: List existing agents
        # ----------------------------------------------------------------
        result: PaginatedResponse[Agent] = await client.agents.list(
            status="active",
            page_size=10,
        )
        print(f"\nActive agents ({result.total} total):")
        for a in result.items:
            print(f"  - {a.name} ({a.id})")

        # ----------------------------------------------------------------
        # Step 4: Submit an objective
        # ----------------------------------------------------------------
        objective: Objective = await client.objectives.create(
            title="Quantum Computing Research",
            description=(
                "Research the latest advances in quantum error correction. "
                "Summarize the top 5 findings with citations."
            ),
            agent_id=agent.id,
            priority=5,
        )
        print(f"\nObjective submitted: {objective.id}")
        print(f"  Title: {objective.title}")
        print(f"  Status: {objective.status}")

        # ----------------------------------------------------------------
        # Step 5: Execute the agent directly (alternative to objectives)
        # ----------------------------------------------------------------
        # `execute` is a synchronous chat-completion call: the body key is
        # `message` (not `objective`) and there is no `wait` -- the call either
        # completes or raises. See AgentsModule.execute.
        execution: AgentExecution = await client.agents.execute(
            agent.id,
            message="Summarize the current state of quantum error correction in 3 paragraphs",
            context={"format": "markdown", "max_length": 500},
        )
        print("\nExecution result:")
        print(f"  Status: {execution.status}")
        print(f"  Duration: {execution.duration_ms}ms")
        if execution.result:
            print(f"  Result: {execution.result}")
        if execution.error:
            print(f"  Error: {execution.error}")

        # ----------------------------------------------------------------
        # Step 6: Monitor objective progress
        # ----------------------------------------------------------------
        print(f"\nMonitoring objective: {objective.id}")
        terminal_states = {"completed", "failed", "cancelled"}

        while objective.status not in terminal_states:
            await asyncio.sleep(5)
            try:
                objective = await client.objectives.get(objective.id)
                print(f"  Status: {objective.status}")
            except NotFoundError:
                print("  Objective not found!")
                break

        # ----------------------------------------------------------------
        # Step 7: Collect results
        # ----------------------------------------------------------------
        if objective.status == "completed":
            print("\nObjective completed successfully!")

            # Get requests (sub-tasks)
            requests = await client.objectives.get_requests(objective.id)
            print(f"  Requests: {len(requests)}")
            for req in requests:
                print(f"    [{req.status}] {req.title}")

            # Get artifacts
            artifacts: list[dict[str, Any]] = await client.objectives.get_artifacts(objective.id)
            print(f"  Artifacts: {len(artifacts)}")
            for art in artifacts:
                print(f"    {art.get('name', 'unnamed')} ({art.get('type', 'unknown')})")

            # Get decisions
            decisions: list[dict[str, Any]] = await client.objectives.get_decisions(objective.id)
            print(f"  Decisions: {len(decisions)}")
        else:
            print(f"\nObjective ended with status: {objective.status}")

        # ----------------------------------------------------------------
        # Step 8: Check execution history
        # ----------------------------------------------------------------
        executions: PaginatedResponse[AgentExecution] = await client.agents.list_executions(
            agent.id,
            page_size=5,
        )
        print(f"\nExecution history ({executions.total} total):")
        for ex in executions.items:
            print(f"  {ex.id}: {ex.status} ({ex.duration_ms}ms)")

        # ----------------------------------------------------------------
        # Step 9: Clean up (optional)
        # ----------------------------------------------------------------
        # await client.agents.delete(agent.id)
        # print(f"\nAgent deleted: {agent.id}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AgenticOSError as e:
        print(f"SDK error: {e.message}")
        if e.details:
            print(f"Details: {e.details}")
    except KeyboardInterrupt:
        print("\nInterrupted")
