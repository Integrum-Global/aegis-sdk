"""
Streaming Progress Example

Demonstrates: real-time SSE streaming for agent execution progress
and session message streaming.

Prerequisites:
    # NOT on PyPI -- `pip install aegis-sdk` installs an unrelated
    # third-party package. Install from source (see docs/quickstart.md):
    pip install -e .
    export AGENTIC_OS_BASE_URL=https://your-deployment.example.com   # REQUIRED, no default
    export AGENTIC_OS_API_KEY=sk_live_your_key_here
"""

import asyncio
from typing import Any

from aegis_sdk import (
    AgenticOSClient,
    AgenticOSError,
    ConnectionError,
    SessionMessage,
    TimeoutError,
)


async def stream_agent_execution(client: AgenticOSClient) -> None:
    """Stream real-time events from an agent execution.

    Uses `client.agents.stream()`. Each event carries its kind under the key
    `type` -- NOT `event_type` -- and the event fields are FLAT on the frame,
    with no `data` wrapper. (The session stream below is the other way round:
    `type` plus a nested `data`. The two streams do not share a shape.)

    `start` carries `model`: the resolved model this execution is running. It is
    the per-agent model the stream exposes, and it arrives before any content,
    so a live view can label the run from the first event.
    """
    print("=== Agent Execution Streaming ===\n")

    agent_id = "agent_abc123"  # Replace with your agent ID

    # `stream` mirrors `execute`: the body key is `message`, not `objective`.
    async for event in client.agents.stream(
        agent_id=agent_id,
        message="Write a comprehensive summary of recent AI safety research",
        context={"format": "markdown", "max_length": 1000},
    ):
        event_type: str = event.get("type", "unknown")

        if event_type == "start":
            # "" means the platform could not resolve a model -- treat that as
            # unknown, never as "the default model".
            model: str = event.get("model") or "model unresolved"
            print(f"[START] {model} (thread {event.get('thread_id')})")
        elif event_type == "content":
            print(event.get("content", ""), end="", flush=True)
        elif event_type == "done":
            print("\n\n[DONE]")
        elif event_type == "error":
            print(f"\n[ERROR] {event.get('error', 'Unknown error')}")
        else:
            print(f"[{event_type.upper()}] {event}")


async def stream_session_messages(client: AgenticOSClient) -> None:
    """Stream messages from an active work session.

    Uses `client.sessions.stream_messages()` which yields
    `SessionMessage` objects via SSE.
    """
    print("\n=== Session Message Streaming ===\n")

    session_id = "ses_abc123"  # Replace with your session ID

    message_count: int = 0

    # `stream_messages` takes the session id and nothing else -- it always
    # streams from the beginning. There is no server-side resume offset; see
    # the reconnect example below for how to skip what you have already seen.
    async for message in client.sessions.stream_messages(session_id=session_id):
        msg: SessionMessage = message
        message_count += 1

        # Format based on role
        role_prefix = {
            "user": "USER",
            "assistant": "AGENT",
            "system": "SYSTEM",
            "tool": "TOOL",
        }.get(msg.role, msg.role.upper())

        print(f"[{role_prefix}] {msg.content}")

        # Check for metadata flags
        if msg.metadata.get("final"):
            print(f"\n--- Final message received ({message_count} total) ---")
            break

    print(f"Total messages: {message_count}")


async def stream_session_events(client: AgenticOSClient) -> None:
    """Stream session activity, including which model each agent is running.

    Uses `client.sessions.stream_events()`. Each event is the parsed SSE frame
    with a `type` and a NESTED `data` payload -- the event-specific fields,
    including `model`, live under `data`, not on the frame.

    The filter below names the wire types that carry agent activity. This is
    worth being precise about: `event_types` filters client-side against the
    server's own vocabulary, and a name the server does not emit is dropped
    SILENTLY. A plausible-looking spelling buys an empty stream rather than an
    error, which is why the list is taken from the method's own docstring.
    """
    print("\n=== Session Event Streaming ===\n")

    session_id = "ses_abc123"  # Replace with your session ID

    async for event in client.sessions.stream_events(
        session_id=session_id,
        event_types=["progress_update", "subagent_spawned", "cost_update"],
    ):
        event_type: str = event.get("type", "unknown")
        data: dict[str, Any] = event.get("data", {})

        # `model` is the model THIS agent is running. Agents within one session
        # do not share a model, so it has to be read per event rather than
        # resolved once for the session. It is "" when the platform could not
        # resolve one: empty means UNKNOWN, never "the default model".
        model: str = data.get("model") or "model unresolved"

        if event_type == "progress_update":
            message: str = data.get("message", "")
            progress: int | None = data.get("progress")
            suffix = f" ({progress}%)" if progress else ""
            print(f"[{model}] {message}{suffix}")

        elif event_type == "subagent_spawned":
            node_name: str = data.get("nodeName", "unnamed")
            print(f"[{model}] subagent started: {node_name}")

        elif event_type == "cost_update":
            tokens: int = data.get("totalTokens", 0)
            dollars: float = data.get("costDollars", 0.0)
            print(f"[{model}] {tokens} tokens, ${dollars}")

        else:
            print(f"[{model}] [{event_type}] {data}")


async def resilient_stream(client: AgenticOSClient) -> None:
    """Stream with automatic reconnection on transient errors.

    Demonstrates handling connection drops and resuming from the
    last received message using `from_message_id`.
    """
    print("\n=== Resilient Streaming with Reconnection ===\n")

    session_id = "ses_abc123"  # Replace with your session ID
    max_reconnects: int = 3
    last_message_id: str | None = None

    for attempt in range(max_reconnects):
        try:
            # The stream has no server-side resume offset, so a reconnect
            # replays from the beginning. Skip forward client-side to the
            # message after the last one this loop already printed.
            resuming = last_message_id is not None
            async for message in client.sessions.stream_messages(
                session_id=session_id,
            ):
                if resuming:
                    # Still replaying history we have already shown.
                    if message.id == last_message_id:
                        resuming = False
                    continue
                last_message_id = message.id
                print(f"[{message.role}] {message.content[:80]}")

                if message.metadata.get("final"):
                    print("\nStream completed normally.")
                    return

            # Stream ended without final message (server closed)
            print("Stream ended by server.")
            return

        except (ConnectionError, TimeoutError) as e:
            print(f"\nConnection lost (attempt {attempt + 1}/{max_reconnects}): {e.message}")

            if attempt < max_reconnects - 1:
                wait_time: float = 2.0**attempt
                print(f"Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)
                print(f"Resuming from message: {last_message_id}")
            else:
                print("Max reconnection attempts reached. Giving up.")
                raise


async def main() -> None:
    """Run all streaming examples."""
    async with AgenticOSClient.from_env() as client:
        # Uncomment the example you want to run:

        await stream_agent_execution(client)
        # await stream_session_messages(client)
        # await stream_session_events(client)
        # await resilient_stream(client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AgenticOSError as e:
        print(f"\nSDK error: {e.message}")
    except KeyboardInterrupt:
        print("\nInterrupted")
