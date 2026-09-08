# Agents Module

The `AgentsModule` (`client.agents`) provides full lifecycle management for AI agents, including CRUD operations, execution, and sub-resource management.

## Access

```python
from aegis_sdk import AgenticOSClient

async with AgenticOSClient.from_env() as client:
    agents_module = client.agents
```

## Agent Model

The `Agent` model represents an AI agent:

| Field             | Type                     | Description                                                                                                                                                   |
| ----------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`              | `str`                    | Unique agent ID                                                                                                                                               |
| `name`            | `str`                    | Agent name                                                                                                                                                    |
| `agent_type`      | `AgentType`              | creatable: `"chat"`, `"task"`, `"pipeline"`, `"custom"`; server-persisted (read-only): `"shadow"`, `"pseudo"`, `"tool"`, `"esa"`; forward-compat: `"unknown"` |
| `unit_type`       | `UnitType`               | `"atomic"` or `"composite"`                                                                                                                                   |
| `agent_subtype`   | `Optional[AgentSubtype]` | `"specialist"`, `"generalist"`, `"coordinator"`, `"worker"`                                                                                                   |
| `status`          | `AgentStatus`            | `"draft"`, `"active"`, `"archived"`, `"deprecated"`, `"suspended"`, `"revoked"`                                                                                |
| `model_id`        | `Optional[str]`          | LLM model identifier                                                                                                                                          |
| `system_prompt`   | `Optional[str]`          | System prompt for the agent                                                                                                                                   |
| `organization_id` | `str`                    | Owning organization                                                                                                                                           |
| `workspace_id`    | `str`                    | Owning workspace                                                                                                                                              |
| `capabilities`    | `List[str]`              | Capability tags                                                                                                                                               |
| `a2a_enabled`     | `bool`                   | Agent-to-agent communication enabled                                                                                                                          |
| `description`     | `Optional[str]`          | Human-readable description                                                                                                                                    |
| `created_at`      | `datetime`               | Creation timestamp                                                                                                                                            |
| `updated_at`      | `datetime`               | Last update timestamp                                                                                                                                         |

## CRUD Operations

### List Agents

```python
from aegis_sdk import PaginatedResponse, Agent

result: PaginatedResponse[Agent] = await client.agents.list(
    workspace_id="ws_abc123",    # Optional: filter by workspace
    status="active",              # Optional: "draft", "active", "archived"
    agent_type="chat",            # Optional: "chat", "task", "pipeline", "custom"
    page=1,                       # Page number (1-indexed)
    page_size=20,                 # Items per page (max 100)
)

print(f"Total agents: {result.total}")
print(f"Page {result.page}, has next: {result.has_next}")
for agent in result.items:
    print(f"  {agent.name} ({agent.status})")
```

### Create Agent

```python
import os
from aegis_sdk import Agent

agent: Agent = await client.agents.create(
    name="Research Assistant",
    agent_type="chat",                      # "chat", "task", "pipeline", or "custom"
    unit_type="atomic",                     # Default: "atomic"
    agent_subtype="specialist",             # Default: "specialist"
    model_id=os.environ["AGENTIC_OS_MODEL"], # LLM model ID -- never hardcode
    system_prompt="You are a research assistant.",
    capabilities=["research", "summarization"],
    a2a_enabled=False,                      # Agent-to-agent communication
    description="AI assistant for research tasks",
    workspace_id="ws_abc123",               # Optional workspace
)

print(f"Created: {agent.id}")
```

### Get Agent

```python
from aegis_sdk import Agent, NotFoundError

try:
    agent: Agent = await client.agents.get("agent_abc123")
    print(f"Agent: {agent.name}")
    print(f"Type: {agent.agent_type}")
    print(f"Model: {agent.model_id}")
    print(f"Capabilities: {agent.capabilities}")
except NotFoundError:
    print("Agent not found")
```

### Update Agent

```python
import os
from aegis_sdk import Agent

agent: Agent = await client.agents.update(
    "agent_abc123",
    name="Updated Research Assistant",
    status="active",
    model_id=os.environ["AGENTIC_OS_MODEL"],  # never hardcode a model name
    system_prompt="You are an improved research assistant.",
    capabilities=["research", "summarization", "citation"],
    a2a_enabled=True,
    description="Enhanced research agent",
)
```

### Delete Agent

```python
await client.agents.delete("agent_abc123")
```

### Duplicate Agent

Create a copy of an existing agent with a new name:

```python
from aegis_sdk import Agent

copy: Agent = await client.agents.duplicate(
    "agent_abc123",
    name="Research Assistant (Copy)",
)
print(f"Copy created: {copy.id}")
```

## Execution

### Synchronous Execution

Execute an agent and wait for the result:

```python
from aegis_sdk import AgentExecution

result: AgentExecution = await client.agents.execute(
    agent_id="agent_abc123",
    objective="Research quantum computing and summarize the top 5 advances",
    context={"focus_area": "error correction", "max_sources": 10},
    wait=True,  # Default: wait for completion
)

print(f"Status: {result.status}")         # "completed", "failed", etc.
print(f"Duration: {result.duration_ms}ms")
print(f"Result: {result.result}")
if result.error:
    print(f"Error: {result.error}")
```

### Async (Fire-and-Forget) Execution

Submit an execution without waiting:

```python
from aegis_sdk import AgentExecution

result: AgentExecution = await client.agents.execute(
    agent_id="agent_abc123",
    objective="Long-running analysis task",
    wait=False,
)

print(f"Execution ID: {result.id}")
print(f"Status: {result.status}")  # "pending" or "running"

# Check later
execution: AgentExecution = await client.agents.get_execution(
    "agent_abc123",
    result.id,
)
print(f"Current status: {execution.status}")
```

### Streaming Execution

Stream execution events in real time via SSE:

```python
from typing import Any, Dict

async for event in client.agents.stream(
    agent_id="agent_abc123",
    objective="Write a report on AI trends",
    context={"format": "markdown"},
):
    event_type: str = event.get("event_type", "unknown")
    data: Dict[str, Any] = event.get("data", {})

    if event_type == "started":
        print("Execution started")
    elif event_type == "thinking":
        print(f"Processing: {data.get('description', '')}")
    elif event_type == "output":
        print(data.get("content", ""), end="", flush=True)
    elif event_type == "completed":
        print(f"\nCompleted in {data.get('duration_ms')}ms")
    elif event_type == "error":
        print(f"\nError: {data.get('message')}")
```

### List Executions

```python
from aegis_sdk import PaginatedResponse, AgentExecution

executions: PaginatedResponse[AgentExecution] = await client.agents.list_executions(
    agent_id="agent_abc123",
    status="completed",  # Optional filter
    page=1,
    page_size=20,
)

for ex in executions.items:
    print(f"  {ex.id}: {ex.status} ({ex.duration_ms}ms)")
```

### Cancel Execution

```python
await client.agents.cancel_execution("agent_abc123", "exec_xyz789")
```

## Sub-Modules

### Versions (`client.agents.versions`)

Manage agent version history for rollback and auditing:

```python
from typing import Any, Dict, List
from aegis_sdk import Agent

# List version history
versions: List[Dict[str, Any]] = await client.agents.versions.list("agent_abc123")
for v in versions:
    print(f"  Version {v['version']}: {v.get('changelog', 'No description')}")

# Get a specific version
version: Dict[str, Any] = await client.agents.versions.get("agent_abc123", version=2)
print(f"Version 2 config: {version}")

# Create a version snapshot
snapshot: Dict[str, Any] = await client.agents.versions.create(
    "agent_abc123",
    changelog="Updated system prompt for better accuracy",
)
print(f"Snapshot version: {snapshot.get('version')}")

# Rollback to a previous version
agent: Agent = await client.agents.versions.rollback("agent_abc123", version=2)
print(f"Rolled back to version 2, agent status: {agent.status}")
```

### Contexts (`client.agents.contexts`)

Manage execution contexts for agents:

```python
from typing import Any, Dict, List

# List contexts
contexts: List[Dict[str, Any]] = await client.agents.contexts.list("agent_abc123")

# Create a context
context: Dict[str, Any] = await client.agents.contexts.create(
    "agent_abc123",
    name="Research Context",
    config={"domain": "quantum_computing", "depth": "deep"},
)

# Get a specific context
ctx: Dict[str, Any] = await client.agents.contexts.get(
    "agent_abc123",
    context_id=context["id"],
)

# Update a context
updated: Dict[str, Any] = await client.agents.contexts.update(
    "agent_abc123",
    context_id=context["id"],
    name="Updated Research Context",
    content_type="text",
    content="Focus on quantum error correction techniques.",
    is_active=True,
)

# Delete a context
await client.agents.contexts.delete("agent_abc123", context["id"])
```

### Tools (`client.agents.tools`)

Manage tool configurations assigned to agents:

```python
from typing import Any, Dict, List

# List tools
tools: List[Dict[str, Any]] = await client.agents.tools.list("agent_abc123")

# Add a tool
tool: Dict[str, Any] = await client.agents.tools.add(
    "agent_abc123",
    tool_type="mcp",
    config={
        "server_url": "https://mcp.example.com",
        "tools": ["search", "summarize"],
    },
)

# Update a tool
updated_tool: Dict[str, Any] = await client.agents.tools.update(
    "agent_abc123",
    tool_id=tool["id"],
    config={"server_url": "https://mcp.example.com", "tools": ["search", "summarize", "cite"]},
)

# Remove a tool
await client.agents.tools.remove("agent_abc123", tool["id"])
```

## AgentExecution Model

The `AgentExecution` model represents an execution result:

| Field          | Type                       | Description                                                        |
| -------------- | -------------------------- | ------------------------------------------------------------------ |
| `id`           | `str`                      | Execution ID                                                       |
| `agent_id`     | `str`                      | Agent that executed                                                |
| `status`       | `ExecutionStatus`          | `"pending"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"` |
| `objective`    | `str`                      | The objective that was executed                                    |
| `context`      | `Dict[str, Any]`           | Execution context                                                  |
| `result`       | `Optional[Dict[str, Any]]` | Execution result (on completion)                                   |
| `error`        | `Optional[str]`            | Error message (on failure)                                         |
| `started_at`   | `Optional[datetime]`       | Start timestamp                                                    |
| `completed_at` | `Optional[datetime]`       | Completion timestamp                                               |
| `duration_ms`  | `Optional[int]`            | Total duration in milliseconds                                     |

## Related

- [Objectives Module](objectives.md) -- Top-level work units
- [Sessions Module](sessions.md) -- Work session management
- [Trust Module](trust.md) -- Trust chain authorization
- [Streaming Guide](../streaming.md) -- SSE streaming patterns
