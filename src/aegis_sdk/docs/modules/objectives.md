# Objectives Module

The `ObjectivesModule` (`client.objectives`) manages objectives -- top-level work units that agents work toward. Each objective may contain one or more requests (sub-tasks).

## Access

```python
from aegis_sdk import AgenticOSClient

async with AgenticOSClient.from_env() as client:
    objectives_module = client.objectives
```

## Objective Model

The `Objective` model represents a top-level work unit:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique objective ID |
| `title` | `str` | Objective title |
| `description` | `str` | Detailed description |
| `agent_id` | `str` | Assigned agent ID |
| `status` | `ObjectiveStatus` | Current lifecycle status |
| `priority` | `int` | Priority level (higher = more urgent) |
| `organization_id` | `str` | Owning organization |
| `workspace_id` | `Optional[str]` | Owning workspace; `None` on servers that no longer have workspaces |
| `created_by` | `str` | User who created the objective |
| `assigned_to` | `Optional[str]` | Assigned user/agent |
| `metadata` | `Dict[str, Any]` | Custom metadata |
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |
| `completed_at` | `Optional[datetime]` | Completion timestamp |

### ObjectiveStatus Values

| Status | Description |
|--------|-------------|
| `draft` | Initial creation, not yet submitted |
| `pending` | Submitted, awaiting processing |
| `in_progress` | Agent is actively working |
| `completed` | Successfully completed |
| `cancelled` | Cancelled by user or system |
| `failed` | Failed during execution |

## CRUD Operations

### List Objectives

```python
from aegis_sdk import PaginatedResponse, ObjectiveStatus

result: PaginatedResponse = await client.objectives.list(
    status=ObjectiveStatus.IN_PROGRESS,   # Optional: filter by status
    agent_id="agent_abc123",               # Optional: filter by agent
    workspace_id="ws_abc123",              # Optional: filter by workspace
    page=1,
    page_size=20,
)

print(f"Total: {result.total}")
for obj in result.items:
    print(f"  [{obj.status}] {obj.title} (priority: {obj.priority})")
```

### Create Objective

```python
from aegis_sdk import Objective

objective: Objective = await client.objectives.create(
    title="Analyze Q4 Sales Data",
    description="Process Q4 sales data, identify trends, and generate a report with actionable insights.",
    agent_id="agent_abc123",
    priority=5,                    # Higher = more urgent
    workspace_id="ws_abc123",      # Optional
    metadata={
        "department": "sales",
        "quarter": "Q4",
        "deadline": "2024-12-31",
    },
)

print(f"Created: {objective.id}")
print(f"Status: {objective.status}")
```

### Get Objective

```python
from aegis_sdk import Objective, NotFoundError

try:
    objective: Objective = await client.objectives.get("obj_abc123")
    print(f"Title: {objective.title}")
    print(f"Status: {objective.status}")
    print(f"Agent: {objective.agent_id}")
    print(f"Priority: {objective.priority}")
except NotFoundError:
    print("Objective not found")
```

### Update Objective

```python
from aegis_sdk import Objective

objective: Objective = await client.objectives.update(
    "obj_abc123",
    title="Updated: Analyze Q4 Sales Data",
    priority=10,
    assigned_to="user_xyz",
    metadata={"urgent": True, "deadline": "2024-12-15"},
)

print(f"Updated: {objective.title} (priority: {objective.priority})")
```

### Cancel Objective

```python
from aegis_sdk import Objective

objective: Objective = await client.objectives.cancel(
    "obj_abc123",
    reason="Requirements changed, no longer needed",
)

print(f"Cancelled: {objective.status}")
```

### Submit Objective

Mark an objective as completed with a summary:

```python
from aegis_sdk import Objective

objective: Objective = await client.objectives.submit(
    "obj_abc123",
    summary="Analysis complete: identified 5 key trends with 3 actionable recommendations.",
    artifacts=["artifact_report_1", "artifact_chart_2"],
)

print(f"Submitted: {objective.status}")
```

## Sub-Resources

### Get Requests

Requests are sub-tasks within an objective:

```python
from aegis_sdk import Request
from typing import List

requests: List[Request] = await client.objectives.get_requests(
    "obj_abc123",
    status="in_progress",  # Optional filter
)

for req in requests:
    print(f"  [{req.status}] {req.title}")
    print(f"    Type: {req.request_type}")
    print(f"    Claimed by: {req.claimed_by}")
```

### Request Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Request ID |
| `objective_id` | `str` | Parent objective ID |
| `title` | `str` | Request title |
| `description` | `str` | Detailed description |
| `request_type` | `str` | `"approval"`, `"action"`, `"information"`, `"decision"` |
| `status` | `RequestStatus` | `"pending"`, `"claimed"`, `"in_progress"`, `"completed"`, `"escalated"`, `"cancelled"` |
| `priority` | `int` | Priority level |
| `claimed_by` | `Optional[str]` | Agent that claimed the request |
| `claimed_at` | `Optional[datetime]` | When it was claimed |
| `metadata` | `Dict[str, Any]` | Custom metadata |
| `created_at` | `datetime` | Creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |
| `completed_at` | `Optional[datetime]` | Completion timestamp |

### Get Decisions

Retrieve decisions made during objective execution:

```python
from typing import Any, Dict, List

decisions: List[Dict[str, Any]] = await client.objectives.get_decisions("obj_abc123")
for d in decisions:
    print(f"  Decision: {d.get('type')} at {d.get('timestamp')}")
    print(f"  Rationale: {d.get('rationale')}")
```

### Get Artifacts

Retrieve artifacts produced during objective execution:

```python
from typing import Any, Dict, List

artifacts: List[Dict[str, Any]] = await client.objectives.get_artifacts("obj_abc123")
for a in artifacts:
    print(f"  Artifact: {a.get('name')} ({a.get('type')})")
```

## Monitoring Pattern

Poll an objective until completion:

```python
import asyncio
from aegis_sdk import AgenticOSClient, Objective

async def monitor_objective(client: AgenticOSClient, objective_id: str) -> Objective:
    """Poll objective status until terminal state."""
    terminal_states = {"completed", "failed", "cancelled"}

    while True:
        objective: Objective = await client.objectives.get(objective_id)
        print(f"Status: {objective.status}")

        if objective.status in terminal_states:
            return objective

        await asyncio.sleep(5)
```

## Full Workflow

```python
import asyncio
from aegis_sdk import AgenticOSClient, Objective
from typing import Any, Dict, List

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        # Create objective
        objective: Objective = await client.objectives.create(
            title="Market Analysis Report",
            description="Analyze market trends for Q4 2024",
            agent_id="agent_analyst",
            priority=5,
        )

        # Monitor progress
        terminal_states = {"completed", "failed", "cancelled"}
        while objective.status not in terminal_states:
            await asyncio.sleep(5)
            objective = await client.objectives.get(objective.id)
            requests = await client.objectives.get_requests(objective.id)
            completed = sum(1 for r in requests if r.status == "completed")
            print(f"Status: {objective.status}, Requests: {completed}/{len(requests)}")

        # Collect results
        if objective.status == "completed":
            artifacts: List[Dict[str, Any]] = await client.objectives.get_artifacts(objective.id)
            decisions: List[Dict[str, Any]] = await client.objectives.get_decisions(objective.id)
            print(f"Completed with {len(artifacts)} artifacts and {len(decisions)} decisions")

asyncio.run(main())
```

## Related

- [Agents Module](agents.md) -- Agent management and execution
- [Sessions Module](sessions.md) -- Work session management
- [Streaming Guide](../streaming.md) -- Real-time progress streaming
