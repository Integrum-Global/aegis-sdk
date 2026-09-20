# Streaming

The Agentic OS SDK supports Server-Sent Events (SSE) for real-time streaming of agent execution progress, session messages, and session events.

## Agent Execution Streaming

Stream real-time events during agent execution using `client.agents.stream()`.
The event kind is on the key `type`, and the event fields sit on the FRAME
itself — this stream is flat, unlike the session stream below, which nests its
payload under `data`:

```python
import asyncio
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        async for event in client.agents.stream(
            agent_id="agent_abc123",
            message="Write a comprehensive analysis of quantum computing",
            context={"focus": "error correction"},
        ):
            event_type: str = event.get("type", "unknown")

            if event_type == "start":
                # The resolved model this agent is running. Agents do not share
                # a model, so read it per execution rather than assuming one.
                print(f"Started on {event.get('model') or 'model unresolved'}")
            elif event_type == "content":
                print(event.get("content", ""), end="", flush=True)
            elif event_type == "done":
                print("\nExecution completed!")
            elif event_type == "error":
                print(f"\nError: {event.get('error', 'Unknown error')}")

asyncio.run(main())
```

### Event Types

| Event Type | Description | Fields |
|------------|-------------|--------|
| `start` | Execution began | `thread_id`, `model`, `timestamp` |
| `content` | A streamed content chunk | `content`, `thread_id` |
| `done` | Execution finished | `thread_id`, `timestamp` |
| `error` | Execution failed | `error`, `thread_id` |

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

Stream all session events — agent activity, subagent spawns, cost updates:

```python
import asyncio
from typing import Any, Dict
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        async for event in client.sessions.stream_events(
            session_id="ses_abc123",
            event_types=["progress_update", "subagent_spawned"],
        ):
            event_type: str = event.get("type", "unknown")
            data: Dict[str, Any] = event.get("data", {})

            # `model` is the model THIS agent is running. Agents within one
            # session do not share a model, so read it per event. It is "" when
            # the platform could not resolve one — empty means unknown.
            model = data.get("model") or "model unresolved"

            if event_type == "progress_update":
                print(f"[{model}] {data.get('message')}")
            elif event_type == "subagent_spawned":
                print(f"[{model}] subagent: {data.get('nodeName')}")

asyncio.run(main())
```

### Filtering Event Types

Pass a list of event types to `event_types` to receive only specific events. The
filter is applied **client-side** against the server's own type vocabulary, and a
name the server does not emit is dropped **silently** — no error, just an empty
stream. The full vocabulary is listed on
`aegis_sdk.execution.SessionsModule.stream_events`.

```python
# Only agent activity and cost updates
async for event in client.sessions.stream_events(
    session_id="ses_abc123",
    event_types=["progress_update", "cost_update"],
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
