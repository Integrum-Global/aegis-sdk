# Streaming

The Agentic OS SDK supports Server-Sent Events (SSE) for real-time streaming of agent execution progress, session messages, and session events.

## Agent Execution Streaming

Stream real-time events during agent execution using `client.agents.stream()`:

```python
import asyncio
from typing import Any, Dict
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        async for event in client.agents.stream(
            agent_id="agent_abc123",
            objective="Write a comprehensive analysis of quantum computing",
            context={"focus": "error correction"},
        ):
            event_type: str = event.get("event_type", "unknown")

            if event_type == "started":
                print("Execution started...")
            elif event_type == "thinking":
                print("Agent is processing...")
            elif event_type == "output":
                content: str = event.get("data", {}).get("content", "")
                print(content, end="", flush=True)
            elif event_type == "completed":
                print("\nExecution completed!")
                result: Dict[str, Any] = event.get("data", {})
                print(f"Result: {result}")
            elif event_type == "error":
                error_msg: str = event.get("data", {}).get("message", "Unknown error")
                print(f"\nError: {error_msg}")

asyncio.run(main())
```

### Event Types

| Event Type | Description | Data Fields |
|------------|-------------|-------------|
| `started` | Execution began | `agent_id`, `execution_id` |
| `thinking` | Agent is processing | `step`, `description` |
| `output` | Intermediate output | `content`, `type` |
| `completed` | Execution finished | `result`, `duration_ms` |
| `error` | Execution failed | `message`, `code` |

## Session Message Streaming

Stream messages from an active work session:

```python
import asyncio
from aegis_sdk import AgenticOSClient, SessionMessage

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        async for message in client.sessions.stream_messages(
            session_id="ses_abc123",
        ):
            msg: SessionMessage = message
            print(f"[{msg.role}] {msg.content}")

            # Stop streaming on final message
            if msg.metadata.get("final"):
                break

asyncio.run(main())
```

### Resume from a Specific Message

Pass `from_message_id` to resume streaming from after a specific message (useful for reconnection):

```python
async for message in client.sessions.stream_messages(
    session_id="ses_abc123",
    from_message_id="msg_last_seen",
):
    print(f"[{message.role}] {message.content}")
```

## Session Event Streaming

Stream all session events (messages, artifacts, status changes, subagent activity):

```python
import asyncio
from typing import Any, Dict
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        async for event in client.sessions.stream_events(
            session_id="ses_abc123",
            event_types=["message", "artifact", "status", "subagent"],
        ):
            event_type: str = event.get("type", "unknown")
            data: Dict[str, Any] = event.get("data", {})

            if event_type == "message":
                print(f"Message [{data.get('role')}]: {data.get('content')}")
            elif event_type == "artifact":
                print(f"Artifact: {data.get('name')} ({data.get('artifact_type')})")
            elif event_type == "status":
                print(f"Status changed to: {data.get('status')}")
            elif event_type == "subagent":
                print(f"Subagent {data.get('subagent_id')}: {data.get('status')}")

asyncio.run(main())
```

### Filtering Event Types

Pass a list of event types to `event_types` to receive only specific events:

```python
# Only messages and status changes
async for event in client.sessions.stream_events(
    session_id="ses_abc123",
    event_types=["message", "status"],
):
    print(event)
```

## SSE Protocol Details

The SDK uses the standard SSE format over HTTP:

- Events are delivered as `data: {json}\n\n` lines
- The stream ends with `data: [DONE]\n\n`
- Malformed JSON lines are silently skipped (logged in debug mode)
- Connection errors are raised as `ConnectionError` or `TimeoutError`

## Error Handling During Streaming

Wrap streaming calls in try/except to handle connection issues:

```python
import asyncio
from aegis_sdk import (
    AgenticOSClient,
    ConnectionError,
    TimeoutError,
    AuthenticationError,
)

async def resilient_stream() -> None:
    async with AgenticOSClient.from_env() as client:
        max_reconnects: int = 3
        last_message_id: str | None = None

        for attempt in range(max_reconnects):
            try:
                async for message in client.sessions.stream_messages(
                    session_id="ses_abc123",
                    from_message_id=last_message_id,
                ):
                    last_message_id = message.id
                    print(f"[{message.role}] {message.content}")

                # Stream ended normally
                break

            except (ConnectionError, TimeoutError) as e:
                print(f"Connection lost (attempt {attempt + 1}): {e.message}")
                if attempt < max_reconnects - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    print("Reconnecting...")
                else:
                    print("Max reconnection attempts reached")
                    raise

            except AuthenticationError:
                print("Authentication expired during streaming")
                raise

asyncio.run(resilient_stream())
```

## Combining Streaming with Polling

For maximum reliability, combine SSE streaming with periodic polling as a fallback:

```python
import asyncio
from aegis_sdk import AgenticOSClient, ConnectionError

async def monitor_objective(client: AgenticOSClient, objective_id: str) -> None:
    """Monitor objective with streaming + polling fallback."""

    # First, try to get a session for real-time streaming
    requests = await client.objectives.get_requests(objective_id)
    if not requests:
        print("No requests yet, falling back to polling")
    else:
        # Try SSE streaming on the session
        for req in requests:
            try:
                session = await client.sessions.get(req.id)
                async for event in client.sessions.stream_events(session.id):
                    print(f"Event: {event}")
                return
            except (ConnectionError, Exception):
                pass

    # Polling fallback
    while True:
        objective = await client.objectives.get(objective_id)
        print(f"Status: {objective.status}")
        if objective.status in ("completed", "failed", "cancelled"):
            break
        await asyncio.sleep(5)
```

## Related

- [Error Handling](error-handling.md) -- Exception types for stream errors
- [Sessions Module](modules/sessions.md) -- Full session API reference
- [Agents Module](modules/agents.md) -- Agent execution and streaming
