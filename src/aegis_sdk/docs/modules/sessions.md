# Sessions Module

The `SessionsModule` (`client.sessions`) manages work sessions -- execution contexts where agents perform work on requests. Sessions track messages, artifacts, and spawned subagents.

## Access

```python
from aegis_sdk import AgenticOSClient

async with AgenticOSClient.from_env() as client:
    sessions_module = client.sessions
```

## Session Model

The `Session` model represents a work session:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Session ID |
| `request_id` | `str` | Associated request ID |
| `agent_id` | `str` | Agent performing work |
| `status` | `SessionStatus` | `"active"`, `"paused"`, `"completed"`, `"terminated"` |
| `start_time` | `datetime` | Session start time |
| `end_time` | `Optional[datetime]` | Session end time |
| `pause_time` | `Optional[datetime]` | When session was paused |
| `message_count` | `int` | Total messages in session |
| `artifact_count` | `int` | Total artifacts produced |
| `metadata` | `Dict[str, Any]` | Custom metadata |

## Session Lifecycle

### Start a Session

```python
from aegis_sdk import Session

session: Session = await client.sessions.start(
    request_id="req_abc123",
    agent_id="agent_xyz",
    metadata={"context": "research", "priority": "high"},
)

print(f"Session started: {session.id}")
print(f"Status: {session.status}")
```

### Get Session

```python
from aegis_sdk import Session, NotFoundError

try:
    session: Session = await client.sessions.get("ses_abc123")
    print(f"Status: {session.status}")
    print(f"Messages: {session.message_count}")
    print(f"Artifacts: {session.artifact_count}")
except NotFoundError:
    print("Session not found")
```

### Pause Session

```python
from aegis_sdk import Session

session: Session = await client.sessions.pause(
    "ses_abc123",
    reason="Waiting for human approval on data access",
)

print(f"Paused at: {session.pause_time}")
```

### Resume Session

```python
from aegis_sdk import Session

session: Session = await client.sessions.resume("ses_abc123")
print(f"Resumed, status: {session.status}")
```

### End Session

```python
from aegis_sdk import Session

session: Session = await client.sessions.end(
    "ses_abc123",
    summary="Analysis complete with 5 key findings and 3 recommendations.",
    metadata={"findings_count": 5, "recommendation_count": 3},
)

print(f"Ended, status: {session.status}")
```

## Messages

### Send a Message

```python
from aegis_sdk import SessionMessage

message: SessionMessage = await client.sessions.send_message(
    "ses_abc123",
    role="assistant",           # "user", "assistant", "system", "tool"
    content="I've completed the initial data analysis. Here are the key findings...",
    metadata={"step": "analysis", "confidence": 0.95},
)

print(f"Message sent: {message.id}")
```

### Get Messages

```python
from aegis_sdk import SessionMessage
from typing import List

messages: List[SessionMessage] = await client.sessions.get_messages(
    "ses_abc123",
    role="assistant",    # Optional: filter by role
    limit=50,            # Max messages to return (default 100)
    offset=0,            # Offset for pagination
)

for msg in messages:
    print(f"[{msg.role}] {msg.content[:80]}...")
    print(f"  Sent at: {msg.created_at}")
```

### SessionMessage Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Message ID |
| `session_id` | `str` | Parent session ID |
| `role` | `str` | `"user"`, `"assistant"`, `"system"`, `"tool"` |
| `content` | `str` | Message content |
| `metadata` | `Dict[str, Any]` | Custom metadata |
| `created_at` | `datetime` | Creation timestamp |

## Artifacts

### Add an Artifact

```python
from aegis_sdk import SessionArtifact

artifact: SessionArtifact = await client.sessions.add_artifact(
    "ses_abc123",
    artifact_type="json",                # "file", "code", "image", "json"
    name="analysis_results",
    data={
        "findings": [
            {"title": "Revenue growth", "trend": "up", "percentage": 15.3},
            {"title": "Cost reduction", "trend": "down", "percentage": 8.2},
        ],
        "overall_score": 85,
    },
)

print(f"Artifact created: {artifact.id}")
```

### Get Artifacts

```python
from aegis_sdk import SessionArtifact
from typing import List

artifacts: List[SessionArtifact] = await client.sessions.get_artifacts("ses_abc123")
for a in artifacts:
    print(f"  {a.name} ({a.artifact_type})")
    print(f"  Data keys: {list(a.data.keys())}")
```

### SessionArtifact Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Artifact ID |
| `session_id` | `str` | Parent session ID |
| `artifact_type` | `str` | `"file"`, `"code"`, `"image"`, `"json"` |
| `name` | `str` | Artifact name |
| `data` | `Dict[str, Any]` | Artifact data |
| `created_at` | `datetime` | Creation timestamp |

## Context

### Get Session Context

```python
from aegis_sdk import SessionContext

context: SessionContext = await client.sessions.get_context("ses_abc123")
print(f"Active tools: {context.active_tools}")
print(f"Agent context: {context.agent_context}")
print(f"Memory context: {context.memory_context}")
```

### Get Memory Context

```python
from typing import Any, Dict

memory: Dict[str, Any] = await client.sessions.get_memory_context(
    "ses_abc123",
    memory_type="short_term",    # "short_term", "long_term", "episodic"
)

print(f"Memory: {memory}")
```

## Subagents

### Spawn a Subagent

Delegate work to a subagent within the session:

```python
from aegis_sdk import Subagent

subagent: Subagent = await client.sessions.spawn_subagent(
    "ses_abc123",
    subagent_id="agent_researcher",
    task="Research quantum error correction techniques published in 2024",
    metadata={"max_sources": 10},
)

print(f"Subagent spawned: {subagent.id}")
print(f"Status: {subagent.status}")
```

### List Subagents

```python
from aegis_sdk import Subagent
from typing import List

subagents: List[Subagent] = await client.sessions.list_subagents("ses_abc123")
for sa in subagents:
    print(f"  Agent {sa.subagent_id}: {sa.task}")
    print(f"    Status: {sa.status}")
    if sa.completed_at:
        print(f"    Completed: {sa.completed_at}")
```

### Subagent Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Subagent instance ID |
| `session_id` | `str` | Parent session ID |
| `subagent_id` | `str` | Agent ID that was spawned |
| `task` | `str` | Task description |
| `status` | `str` | `"running"`, `"completed"`, `"failed"` |
| `created_at` | `datetime` | Spawn timestamp |
| `completed_at` | `Optional[datetime]` | Completion timestamp |

## Streaming

### Stream Messages (SSE)

Stream messages in real time as they are produced:

```python
from aegis_sdk import SessionMessage

async for message in client.sessions.stream_messages(
    "ses_abc123",
    from_message_id=None,   # Resume from after this message
):
    msg: SessionMessage = message
    print(f"[{msg.role}] {msg.content}")
    if msg.metadata.get("final"):
        break
```

### Stream All Events (SSE)

Stream messages, artifacts, status changes, and subagent events:

```python
from typing import Any, Dict

async for event in client.sessions.stream_events(
    "ses_abc123",
    event_types=["message", "artifact", "status", "subagent"],
):
    event_type: str = event.get("type", "unknown")
    data: Dict[str, Any] = event.get("data", {})

    if event_type == "message":
        print(f"Message [{data.get('role')}]: {data.get('content')}")
    elif event_type == "artifact":
        print(f"Artifact: {data.get('name')}")
    elif event_type == "status":
        print(f"Status: {data.get('status')}")
    elif event_type == "subagent":
        print(f"Subagent {data.get('subagent_id')}: {data.get('status')}")
```

## Full Workflow

```python
import asyncio
from aegis_sdk import AgenticOSClient, Session, SessionMessage

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        # Start session
        session: Session = await client.sessions.start(
            request_id="req_abc123",
            agent_id="agent_analyst",
        )

        # Send initial context
        await client.sessions.send_message(
            session.id,
            role="system",
            content="Analyze the Q4 sales data and produce a summary report.",
        )

        # Monitor via streaming
        async for message in client.sessions.stream_messages(session.id):
            print(f"[{message.role}] {message.content[:100]}")
            if message.metadata.get("final"):
                break

        # Collect artifacts
        artifacts = await client.sessions.get_artifacts(session.id)
        print(f"\nProduced {len(artifacts)} artifacts")

        # End session
        await client.sessions.end(session.id, summary="Analysis complete")

asyncio.run(main())
```

## Related

- [Objectives Module](objectives.md) -- Top-level work units
- [Agents Module](agents.md) -- Agent management
- [Streaming Guide](../streaming.md) -- SSE streaming patterns
