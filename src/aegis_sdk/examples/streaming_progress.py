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

    Uses `client.agents.stream()` which returns SSE events as
    dictionaries with `event_type` and `data` fields.
    """
    print("=== Agent Execution Streaming ===\n")

    agent_id = "agent_abc123"  # Replace with your agent ID

    # `stream` mirrors `execute`: the body key is `message`, not `objective`.
    async for event in client.agents.stream(
        agent_id=agent_id,
        message="Write a comprehensive summary of recent AI safety research",
        context={"format": "markdown", "max_length": 1000},
    ):
        event_type: str = event.get("event_type", "unknown")
        data: dict[str, Any] = event.get("data", {})

        if event_type == "started":
            print(f"[STARTED] Execution ID: {data.get('execution_id')}")
        elif event_type == "thinking":
            step: str = data.get("description", "Processing...")
            print(f"[THINKING] {step}")
        elif event_type == "output":
            content: str = data.get("content", "")
            print(content, end="", flush=True)
        elif event_type == "completed":
            duration: int = data.get("duration_ms", 0)
            print(f"\n\n[COMPLETED] Duration: {duration}ms")
        elif event_type == "error":
            message: str = data.get("message", "Unknown error")
            print(f"\n[ERROR] {message}")
        else:
            print(f"[{event_type.upper()}] {data}")


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
    """Stream all session events (messages, artifacts, status changes, subagents).

    Uses `client.sessions.stream_events()` which yields raw event
    dictionaries with `type` and `data` fields.
    """
    print("\n=== Session Event Streaming ===\n")

    session_id = "ses_abc123"  # Replace with your session ID

    async for event in client.sessions.stream_events(
        session_id=session_id,
        event_types=["message", "artifact", "status", "subagent"],
    ):
        event_type: str = event.get("type", "unknown")
        data: dict[str, Any] = event.get("data", {})

        if event_type == "message":
            role: str = data.get("role", "unknown")
            content: str = data.get("content", "")
            print(f"[MSG:{role}] {content[:100]}")

        elif event_type == "artifact":
            name: str = data.get("name", "unnamed")
            artifact_type: str = data.get("artifact_type", "unknown")
            print(f"[ARTIFACT] {name} ({artifact_type})")

        elif event_type == "status":
            status: str = data.get("status", "unknown")
            print(f"[STATUS] Session status changed to: {status}")
            if status in ("completed", "terminated"):
                print("Session ended, stopping stream.")
                break

        elif event_type == "subagent":
            subagent_id: str = data.get("subagent_id", "unknown")
            subagent_status: str = data.get("status", "unknown")
            print(f"[SUBAGENT] {subagent_id}: {subagent_status}")

        else:
            print(f"[{event_type.upper()}] {data}")


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
