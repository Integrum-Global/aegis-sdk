"""
Build A Pipeline Example

Demonstrates: discovering which node types YOUR deployment actually has, reading
their executability verdicts, building a graph out of the ones that will run,
validating it, and executing it.

This example exists because the catalogue and the construction surface were
documented apart from each other. A reader could learn how to list node types,
and separately how to build a pipeline, and had nothing joining the two -- so
"which nodes do I have?" and "how do I build with them?" stayed two questions.

Prerequisites:
    # NOT on PyPI -- `pip install aegis-sdk` installs an unrelated
    # third-party package. Install from source (see docs/quickstart.md):
    pip install -e .
    export AGENTIC_OS_BASE_URL=https://your-deployment.example.com   # REQUIRED, no default
    export AGENTIC_OS_API_KEY=sk_live_your_key_here
    export AGENTIC_OS_MODEL=<your model id>                          # examples never hardcode one
    export AGENTIC_OS_WORKSPACE_ID=<your workspace id>               # agents.create() requires it

Credentials needed: reading the catalogue takes `agents:read`; creating and
running take write authority on agents. An API key scoped to read-only will get
as far as the verdict report and then stop.
"""

import asyncio
import os
from typing import Any

from aegis_sdk import (
    Agent,
    AgenticOSClient,
    AgenticOSError,
    AuthenticationError,
    AuthorizationError,
    NodeTypeCatalog,
    Pipeline,
    PipelineExecution,
    ValidationError,
)


def _report(catalog: NodeTypeCatalog) -> tuple[list[str], list[str]]:
    """Print what this deployment has, and return (executable, fabricating).

    The two lists are the point of the whole example. A node type appearing in
    the catalogue means it is RECOGNISED -- not that it will run. On a
    deployment whose palette is connector-shaped, every entry in the palette
    can be non-executable, and `unavailable_reason` says so once.
    """
    print(f"\nThis deployment's palette: {catalog.total_types} node type(s)")
    for category in catalog.categories:
        print(f"  {category.label}:")
        for node in category.nodes:
            print(f"    - {node.type}")

    print(f"\nWhole pipeline vocabulary: {len(catalog.node_types)} type(s)")
    for name in sorted(catalog.node_types):
        verdict = catalog.node_types[name]
        if verdict.executable:
            mark = "runs"
        elif verdict.fabricates:
            # The dangerous arm: it does not refuse, it emits a diagnostic
            # string AS ITS OUTPUT and feeds that downstream.
            mark = "DOES NOT RUN -- and fails SILENTLY"
        else:
            mark = "does not run"
        print(f"  {name:<14} {mark}")

    if not catalog.executable:
        print(f"\n⚠ Palette unavailable here: {catalog.unavailable_reason}")

    executable = sorted(n for n, v in catalog.node_types.items() if v.executable)
    fabricating = sorted(n for n, v in catalog.node_types.items() if v.fabricates)

    if fabricating:
        print(
            f"\n⚠ {len(fabricating)} type(s) fail SILENTLY rather than refusing: "
            f"{', '.join(fabricating)}. A pipeline built on one of these "
            "completes carrying an error message as its result. Never wire one."
        )

    return executable, fabricating


async def main() -> None:
    """Discover the node catalogue, build with it, validate, and run."""
    async with AgenticOSClient.from_env() as client:
        # ----------------------------------------------------------------
        # Step 1: Verify authentication
        # ----------------------------------------------------------------
        try:
            agents = await client.agents.list(page_size=1)
            print(f"Authenticated. Organization has {agents.total} agent(s).")
        except AuthenticationError as exc:
            print(f"Authentication failed: {exc.message}")
            return

        # ----------------------------------------------------------------
        # Step 2: Ask the deployment which node types it has
        # ----------------------------------------------------------------
        # No list of node types is hardcoded here, and that is deliberate: the
        # catalogue is this deployment's built-ins PLUS whatever its packs
        # added. A list baked into this file would be wrong on the next
        # deployment and stale on this one.
        catalog: NodeTypeCatalog = await client.pipelines.list_node_types()
        executable, _ = _report(catalog)

        # ----------------------------------------------------------------
        # Step 3: Decide whether this deployment can run anything at all
        # ----------------------------------------------------------------
        # Checked BEFORE building, not after. A graph assembled out of
        # non-executable types passes validation and then refuses at run time,
        # which is a slow way to learn something the catalogue already said.
        needed = {"input", "output", "agent"}
        missing = sorted(t for t in needed if t not in executable)
        if missing:
            print(
                f"\nThis deployment cannot run {', '.join(missing)}, so the "
                "example stops here rather than building a graph that would "
                "fail. The verdicts above name what it CAN run."
            )
            return

        # ----------------------------------------------------------------
        # Step 4: Get an agent for the agent node to bind to
        # ----------------------------------------------------------------
        # An `agent` node is only half a node without an agent_id -- the graph
        # is valid without one, and the run then resolves to no agent. See
        # handbook 03.2 for that refusal class.
        if agents.items:
            agent: Agent = agents.items[0]
            print(f"\nReusing agent: {agent.name} ({agent.id})")
        else:
            try:
                agent = await client.agents.create(
                    name="Pipeline Worker",
                    agent_type="chat",
                    workspace_id=os.environ["AGENTIC_OS_WORKSPACE_ID"],
                    model_id=os.environ["AGENTIC_OS_MODEL"],
                    system_prompt="You carry out one step of a pipeline.",
                )
                print(f"\nCreated agent: {agent.name} ({agent.id})")
            except ValidationError as exc:
                print(f"Could not create an agent: {exc.message}")
                return

        # ----------------------------------------------------------------
        # Step 5: Build the graph
        # ----------------------------------------------------------------
        # `create()` takes PipelineNode: `id`, `name` and `node_type` are
        # required. The editor's save path takes a DIFFERENT shape -- `label`
        # instead of `name`, `id` optional. Build one way and stay with it;
        # a dict that works in one is rejected by the other.
        nodes: list[dict[str, Any]] = [
            {"id": "n_input", "name": "Topic", "node_type": "input"},
            {
                "id": "n_agent",
                "name": "Draft",
                "node_type": "agent",
                "agent_id": agent.id,
            },
            {"id": "n_output", "name": "Result", "node_type": "output"},
        ]
        connections: list[dict[str, Any]] = [
            {"source_node_id": "n_input", "target_node_id": "n_agent"},
            {"source_node_id": "n_agent", "target_node_id": "n_output"},
        ]

        try:
            pipeline: Pipeline = await client.pipelines.create(
                name="Example Pipeline",
                pattern="sequential",
                description="Built from node types this deployment reports as executable.",
                nodes=nodes,
                connections=connections,
            )
        except AuthorizationError as exc:
            print(f"\nNot permitted to create pipelines: {exc.message}")
            return
        except ValidationError as exc:
            print(f"\nPipeline rejected: {exc.message}")
            return

        print(f"\nPipeline created: {pipeline.id}")

        # ----------------------------------------------------------------
        # Step 6: Validate before running
        # ----------------------------------------------------------------
        # The cheapest check in this part, and it must be run before every
        # execution of an edited graph.
        report: dict[str, Any] = await client.pipelines.validate(pipeline.id)
        print(f"\nValid: {report.get('valid')}")
        for err in report.get("errors", []):
            print(f"  error:   {err}")

        # READ THE WARNINGS TOO. By deliberate severity contract several real
        # defect classes are warnings, and a warning never flips `valid` to
        # False -- a node bound to an agent with no trust posture, an approval
        # gate with no outbound edges, an agent node with no outbound edge. A
        # pipeline that validates clean can still refuse, or hold forever.
        warnings = report.get("warnings", [])
        print(f"Warnings: {len(warnings)}")
        for warn in warnings:
            print(f"  warning: {warn}")

        if not report.get("valid"):
            print("\nNot executing a graph that did not validate.")
            return

        # ----------------------------------------------------------------
        # Step 7: Execute
        # ----------------------------------------------------------------
        # `execute` answers only once the run has finished. There is no
        # asynchronous mode: `wait` is deprecated and changes nothing.
        try:
            execution: PipelineExecution = await client.pipelines.execute(
                pipeline.id,
                inputs={"topic": "the current state of quantum error correction"},
            )
        except AuthorizationError as exc:
            print(f"\nNot permitted to execute pipelines: {exc.message}")
            return

        print(f"\nRun {execution.status} in {execution.duration_ms}ms")

        # `node_results` is per-node, so it says WHERE a run stopped rather
        # than only that it did. It is declared as a LIST here — do not reach
        # for `.items()`, which raises on the shape the model declares.
        for node_result in execution.node_results or []:
            print(f"  {node_result}")

        if execution.error:
            print(f"  error: {execution.error}")
        if execution.outputs:
            print(f"\nOutputs: {execution.outputs}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AgenticOSError as exc:
        print(f"SDK error: {exc.message}")
        if exc.details:
            print(f"Details: {exc.details}")
    except KeyboardInterrupt:
        print("\nInterrupted")
