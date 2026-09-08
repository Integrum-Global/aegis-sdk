"""Events Module for Nexus v1.1 - Real-time event streaming and pub/sub.

This module provides enhanced event streaming capabilities including:
- Server-Sent Events (SSE) streaming
- WebSocket bidirectional streaming
- Pub/sub pattern for workflow events
- Event filtering by workflow, type, and session
- Backpressure handling with configurable queues
- Connection management with heartbeats

Example:
    >>> from aegis_sdk.nexus import EventsModule, EventBus
    >>>
    >>> # Create events module
    >>> module = EventsModule()
    >>>
    >>> # Subscribe to workflow events
    >>> subscription = module.subscribe(
    ...     subscriber_id="client-1",
    ...     event_types=["workflow.started", "workflow.completed"],
    ...     workflow_name="my-workflow"
    ... )
    >>>
    >>> # Publish an event
    >>> module.publish("workflow.started", {"workflow_name": "my-workflow"})
    >>>
    >>> # Get events for subscriber (for SSE)
    >>> events = module.get_events("client-1")
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator, Callable, Generator
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
)

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Standard event types for workflow lifecycle."""

    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    NODE_EXECUTED = "node.executed"
    NODE_FAILED = "node.failed"
    ERROR_OCCURRED = "error.occurred"
    SESSION_CREATED = "session.created"
    SESSION_EXPIRED = "session.expired"
    HEALTH_CHANGED = "health.changed"
    CUSTOM = "custom"

    def __str__(self) -> str:
        """Return event type value."""
        return self.value

    @classmethod
    def from_string(cls, value: str) -> EventType:
        """Convert string to EventType.

        Args:
            value: String representation.

        Returns:
            Corresponding EventType enum value.

        Raises:
            ValueError: If the string does not match any event type.
        """
        for member in cls:
            if member.value == value:
                return member
        return cls.CUSTOM


class ConnectionState(Enum):
    """Connection lifecycle states."""

    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTING = auto()
    DISCONNECTED = auto()

    def __str__(self) -> str:
        """Return lowercase state name."""
        return self.name.lower()


class StreamProtocol(Enum):
    """Streaming protocol types."""

    SSE = auto()  # Server-Sent Events
    WEBSOCKET = auto()  # WebSocket

    def __str__(self) -> str:
        """Return lowercase protocol name."""
        return self.name.lower()


@dataclass
class StreamEvent:
    """Event in the streaming system.

    Attributes:
        id: Unique event identifier.
        type: Event type string.
        data: Event payload data.
        timestamp: Event creation timestamp.
        source: Event source identifier.
        workflow_name: Optional workflow name filter.
        session_id: Optional session ID filter.
        correlation_id: Optional correlation ID.
        retry: Retry interval for SSE (milliseconds).
    """

    id: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str | None = None
    workflow_name: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None
    retry: int | None = None

    def to_sse(self) -> str:
        """Format event as SSE message.

        Returns:
            SSE-formatted string.
        """
        lines = []
        lines.append(f"id: {self.id}")
        lines.append(f"event: {self.type}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        data_json = json.dumps(self.data)
        lines.append(f"data: {data_json}")
        lines.append("")  # Empty line to end event
        return "\n".join(lines)

    def to_websocket(self) -> str:
        """Format event as WebSocket message.

        Returns:
            JSON-formatted string.
        """
        return json.dumps(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "workflow_name": self.workflow_name,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamEvent:
        """Create event from dictionary.

        Args:
            data: Dictionary containing event data.

        Returns:
            StreamEvent instance.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data.get("type", "custom"),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source"),
            workflow_name=data.get("workflow_name"),
            session_id=data.get("session_id"),
            correlation_id=data.get("correlation_id"),
        )


@dataclass
class Subscription:
    """Subscriber registration for event filtering.

    Attributes:
        id: Unique subscription identifier.
        subscriber_id: Subscriber client identifier.
        event_types: List of event types to receive.
        workflow_name: Optional workflow name filter.
        session_id: Optional session ID filter.
        protocol: Streaming protocol.
        created_at: Subscription creation timestamp.
        active: Whether subscription is active.
        filter_fn: Optional custom filter function.
    """

    id: str
    subscriber_id: str
    event_types: list[str] = field(default_factory=list)
    workflow_name: str | None = None
    session_id: str | None = None
    protocol: StreamProtocol = StreamProtocol.SSE
    created_at: float = field(default_factory=time.time)
    active: bool = True
    filter_fn: Callable[[StreamEvent], bool] | None = None

    def matches(self, event: StreamEvent) -> bool:
        """Check if event matches subscription filters.

        Args:
            event: Event to check.

        Returns:
            True if event matches all filters.
        """
        if not self.active:
            return False

        # Check event type
        if self.event_types and event.type not in self.event_types:
            # Allow wildcard matching
            if not any(
                event.type.startswith(t.rstrip("*")) for t in self.event_types if t.endswith("*")
            ):
                return False

        # Check workflow name
        if self.workflow_name and event.workflow_name != self.workflow_name:
            return False

        # Check session ID
        if self.session_id and event.session_id != self.session_id:
            return False

        # Check custom filter
        if self.filter_fn:
            try:
                if not self.filter_fn(event):
                    return False
            except Exception:
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert subscription to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "subscriber_id": self.subscriber_id,
            "event_types": self.event_types,
            "workflow_name": self.workflow_name,
            "session_id": self.session_id,
            "protocol": str(self.protocol),
            "created_at": self.created_at,
            "active": self.active,
        }


@dataclass
class WebSocketConnection:
    """WebSocket connection state.

    Attributes:
        id: Unique connection identifier.
        subscriber_id: Associated subscriber ID.
        connected_at: Connection timestamp.
        last_ping: Last ping timestamp.
        last_pong: Last pong timestamp.
        state: Connection state.
        metadata: Connection metadata.
    """

    id: str
    subscriber_id: str
    connected_at: float = field(default_factory=time.time)
    last_ping: float | None = None
    last_pong: float | None = None
    state: ConnectionState = ConnectionState.CONNECTED
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        """Check if connection is alive based on ping/pong."""
        if self.state != ConnectionState.CONNECTED:
            return False
        if self.last_ping and self.last_pong:
            return self.last_pong >= self.last_ping
        return True

    @property
    def latency_ms(self) -> float | None:
        """Get connection latency in milliseconds."""
        if self.last_ping and self.last_pong and self.last_pong >= self.last_ping:
            return (self.last_pong - self.last_ping) * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert connection to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "subscriber_id": self.subscriber_id,
            "connected_at": self.connected_at,
            "last_ping": self.last_ping,
            "last_pong": self.last_pong,
            "state": str(self.state),
            "is_alive": self.is_alive,
            "latency_ms": self.latency_ms,
        }


class EventQueue:
    """Thread-safe event queue with backpressure handling.

    Provides bounded queue with configurable max size and
    overflow behavior (drop oldest or block).
    """

    def __init__(
        self,
        max_size: int = 1000,
        overflow_strategy: str = "drop_oldest",
    ):
        """Initialize event queue.

        Args:
            max_size: Maximum queue size.
            overflow_strategy: "drop_oldest" or "block".
        """
        self._max_size = max_size
        self._overflow_strategy = overflow_strategy
        self._queue: queue.Queue[StreamEvent] = queue.Queue(maxsize=max_size)
        self._lock = threading.Lock()
        self._dropped_count = 0
        self._total_count = 0

    def put(self, event: StreamEvent, timeout: float | None = None) -> bool:
        """Put event in queue with backpressure handling.

        Args:
            event: Event to add.
            timeout: Timeout for blocking (None = default based on strategy).

        Returns:
            True if event was added, False if dropped.
        """
        with self._lock:
            self._total_count += 1

            try:
                if self._overflow_strategy == "drop_oldest":
                    if self._queue.full():
                        try:
                            self._queue.get_nowait()
                            self._dropped_count += 1
                        except queue.Empty:
                            pass
                    self._queue.put_nowait(event)
                else:
                    # Block strategy
                    self._queue.put(event, timeout=timeout or 1.0)
                return True
            except queue.Full:
                self._dropped_count += 1
                return False

    def get(self, timeout: float | None = None) -> StreamEvent | None:
        """Get event from queue.

        Args:
            timeout: Timeout in seconds.

        Returns:
            StreamEvent or None if timeout.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_all(self, max_events: int = 100) -> list[StreamEvent]:
        """Get all available events up to max.

        Args:
            max_events: Maximum events to return.

        Returns:
            List of events.
        """
        events = []
        for _ in range(max_events):
            try:
                event = self._queue.get_nowait()
                events.append(event)
            except queue.Empty:
                break
        return events

    def clear(self) -> int:
        """Clear all events from queue.

        Returns:
            Number of events cleared.
        """
        count = 0
        while True:
            try:
                self._queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        return count

    @property
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics.
        """
        return {
            "size": self.size,
            "max_size": self._max_size,
            "total_count": self._total_count,
            "dropped_count": self._dropped_count,
            "overflow_strategy": self._overflow_strategy,
            "is_full": self.is_full,
        }


class EventsModule:
    """Real-time event streaming module for Nexus v1.1.

    Provides pub/sub event handling, SSE streaming, WebSocket
    connections, and backpressure management.

    Example:
        >>> module = EventsModule(max_queue_size=1000)
        >>>
        >>> # Subscribe to events
        >>> sub = module.subscribe("client-1", event_types=["workflow.*"])
        >>>
        >>> # Publish event
        >>> module.publish("workflow.started", {"name": "my-workflow"})
        >>>
        >>> # Get events for SSE streaming
        >>> events = module.get_events("client-1")
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        heartbeat_interval_s: float = 30.0,
        connection_timeout_s: float = 60.0,
        overflow_strategy: str = "drop_oldest",
    ):
        """Initialize events module.

        Args:
            max_queue_size: Maximum events per subscriber queue.
            heartbeat_interval_s: Interval for WebSocket heartbeats.
            connection_timeout_s: Timeout for inactive connections.
            overflow_strategy: Queue overflow strategy.
        """
        self._max_queue_size = max_queue_size
        self._heartbeat_interval_s = heartbeat_interval_s
        self._connection_timeout_s = connection_timeout_s
        self._overflow_strategy = overflow_strategy

        self._subscriptions: dict[str, Subscription] = {}  # subscription_id -> Subscription
        self._subscriber_queues: dict[str, EventQueue] = {}  # subscriber_id -> EventQueue
        self._websocket_connections: dict[str, WebSocketConnection] = (
            {}
        )  # connection_id -> Connection
        self._subscriber_subscriptions: dict[str, set[str]] = defaultdict(
            set
        )  # subscriber_id -> subscription_ids

        self._lock = threading.RLock()
        self._event_counter = 0
        self._total_published = 0
        self._total_delivered = 0

        # Global event hooks
        self._on_publish_hooks: list[Callable[[StreamEvent], None]] = []
        self._on_subscribe_hooks: list[Callable[[Subscription], None]] = []
        self._on_unsubscribe_hooks: list[Callable[[Subscription], None]] = []

    def subscribe(
        self,
        subscriber_id: str,
        event_types: list[str] | None = None,
        workflow_name: str | None = None,
        session_id: str | None = None,
        protocol: StreamProtocol = StreamProtocol.SSE,
        filter_fn: Callable[[StreamEvent], bool] | None = None,
    ) -> Subscription:
        """Subscribe to events with filtering.

        Args:
            subscriber_id: Unique subscriber identifier.
            event_types: Event types to receive (supports wildcards).
            workflow_name: Filter by workflow name.
            session_id: Filter by session ID.
            protocol: Streaming protocol.
            filter_fn: Custom filter function.

        Returns:
            Created Subscription.
        """
        with self._lock:
            subscription = Subscription(
                id=str(uuid.uuid4()),
                subscriber_id=subscriber_id,
                event_types=event_types or [],
                workflow_name=workflow_name,
                session_id=session_id,
                protocol=protocol,
                filter_fn=filter_fn,
            )

            self._subscriptions[subscription.id] = subscription
            self._subscriber_subscriptions[subscriber_id].add(subscription.id)

            # Create queue for subscriber if needed
            if subscriber_id not in self._subscriber_queues:
                self._subscriber_queues[subscriber_id] = EventQueue(
                    max_size=self._max_queue_size,
                    overflow_strategy=self._overflow_strategy,
                )

            logger.debug("Created subscription %s for %s", subscription.id, subscriber_id)

            # Invoke hooks
            for hook in self._on_subscribe_hooks:
                try:
                    hook(subscription)
                except Exception as e:
                    logger.warning("Subscribe hook failed: %s", e)

            return subscription

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription.

        Args:
            subscription_id: Subscription ID to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False

            subscription = self._subscriptions[subscription_id]
            del self._subscriptions[subscription_id]
            self._subscriber_subscriptions[subscription.subscriber_id].discard(subscription_id)

            # Invoke hooks
            for hook in self._on_unsubscribe_hooks:
                try:
                    hook(subscription)
                except Exception as e:
                    logger.warning("Unsubscribe hook failed: %s", e)

            logger.debug("Removed subscription %s", subscription_id)
            return True

    def unsubscribe_all(self, subscriber_id: str) -> int:
        """Remove all subscriptions for a subscriber.

        Args:
            subscriber_id: Subscriber identifier.

        Returns:
            Number of subscriptions removed.
        """
        with self._lock:
            subscription_ids = list(self._subscriber_subscriptions.get(subscriber_id, []))
            count = 0
            for sub_id in subscription_ids:
                if self.unsubscribe(sub_id):
                    count += 1

            # Clean up queue
            if subscriber_id in self._subscriber_queues:
                self._subscriber_queues[subscriber_id].clear()
                del self._subscriber_queues[subscriber_id]

            return count

    def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        workflow_name: str | None = None,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ) -> StreamEvent:
        """Publish an event to all matching subscribers.

        Args:
            event_type: Event type string.
            data: Event payload data.
            source: Event source identifier.
            workflow_name: Workflow name for filtering.
            session_id: Session ID for filtering.
            correlation_id: Correlation ID for tracking.

        Returns:
            Published StreamEvent.
        """
        with self._lock:
            self._event_counter += 1
            self._total_published += 1

            event = StreamEvent(
                id=f"evt-{int(time.time() * 1000)}-{self._event_counter}",
                type=event_type,
                data=data or {},
                source=source,
                workflow_name=workflow_name,
                session_id=session_id,
                correlation_id=correlation_id,
            )

            # Invoke publish hooks
            for hook in self._on_publish_hooks:
                try:
                    hook(event)
                except Exception as e:
                    logger.warning("Publish hook failed: %s", e)

            # Deliver to matching subscribers
            for subscription in self._subscriptions.values():
                if subscription.matches(event):
                    queue = self._subscriber_queues.get(subscription.subscriber_id)
                    if queue:
                        if queue.put(event):
                            self._total_delivered += 1

            return event

    def get_events(
        self,
        subscriber_id: str,
        max_events: int = 100,
        timeout: float | None = None,
    ) -> list[StreamEvent]:
        """Get pending events for a subscriber.

        Args:
            subscriber_id: Subscriber identifier.
            max_events: Maximum events to return.
            timeout: Timeout for waiting (None = no wait).

        Returns:
            List of pending events.
        """
        queue = self._subscriber_queues.get(subscriber_id)
        if not queue:
            return []

        if timeout:
            # Wait for at least one event
            event = queue.get(timeout=timeout)
            if event:
                events = [event]
                events.extend(queue.get_all(max_events - 1))
                return events
            return []
        else:
            return queue.get_all(max_events)

    async def get_events_async(
        self,
        subscriber_id: str,
        max_events: int = 100,
        timeout: float | None = None,
    ) -> list[StreamEvent]:
        """Get pending events asynchronously.

        Args:
            subscriber_id: Subscriber identifier.
            max_events: Maximum events to return.
            timeout: Timeout for waiting.

        Returns:
            List of pending events.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.get_events(subscriber_id, max_events, timeout),
        )

    def stream_sse(
        self,
        subscriber_id: str,
        timeout: float = 30.0,
    ) -> Generator[str, None, None]:
        """Generate SSE stream for subscriber.

        Args:
            subscriber_id: Subscriber identifier.
            timeout: Timeout between events.

        Yields:
            SSE-formatted event strings.
        """
        while True:
            events = self.get_events(subscriber_id, timeout=timeout)
            if events:
                for event in events:
                    yield event.to_sse()
            else:
                # Send keep-alive comment
                yield ": heartbeat\n\n"

    async def stream_sse_async(
        self,
        subscriber_id: str,
        timeout: float = 30.0,
    ) -> AsyncGenerator[str, None]:
        """Generate async SSE stream for subscriber.

        Args:
            subscriber_id: Subscriber identifier.
            timeout: Timeout between events.

        Yields:
            SSE-formatted event strings.
        """
        while True:
            events = await self.get_events_async(subscriber_id, timeout=timeout)
            if events:
                for event in events:
                    yield event.to_sse()
            else:
                # Send keep-alive comment
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.01)  # Small yield to prevent tight loop

    # WebSocket Connection Management

    def add_websocket_connection(
        self,
        subscriber_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> WebSocketConnection:
        """Register a WebSocket connection.

        Args:
            subscriber_id: Subscriber identifier.
            metadata: Connection metadata.

        Returns:
            WebSocketConnection instance.
        """
        with self._lock:
            connection = WebSocketConnection(
                id=str(uuid.uuid4()),
                subscriber_id=subscriber_id,
                metadata=metadata or {},
            )
            self._websocket_connections[connection.id] = connection
            logger.debug("Added WebSocket connection %s", connection.id)
            return connection

    def remove_websocket_connection(self, connection_id: str) -> bool:
        """Remove a WebSocket connection.

        Args:
            connection_id: Connection ID.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if connection_id not in self._websocket_connections:
                return False

            connection = self._websocket_connections[connection_id]
            connection.state = ConnectionState.DISCONNECTED
            del self._websocket_connections[connection_id]
            logger.debug("Removed WebSocket connection %s", connection_id)
            return True

    def ping_connection(self, connection_id: str) -> bool:
        """Send ping to WebSocket connection.

        Args:
            connection_id: Connection ID.

        Returns:
            True if ping sent, False if not found.
        """
        with self._lock:
            connection = self._websocket_connections.get(connection_id)
            if not connection:
                return False
            connection.last_ping = time.time()
            return True

    def pong_connection(self, connection_id: str) -> bool:
        """Record pong from WebSocket connection.

        Args:
            connection_id: Connection ID.

        Returns:
            True if pong recorded, False if not found.
        """
        with self._lock:
            connection = self._websocket_connections.get(connection_id)
            if not connection:
                return False
            connection.last_pong = time.time()
            return True

    def get_websocket_connection(self, connection_id: str) -> WebSocketConnection | None:
        """Get WebSocket connection by ID.

        Args:
            connection_id: Connection ID.

        Returns:
            WebSocketConnection or None.
        """
        return self._websocket_connections.get(connection_id)

    def list_websocket_connections(
        self, subscriber_id: str | None = None
    ) -> list[WebSocketConnection]:
        """List WebSocket connections.

        Args:
            subscriber_id: Optional filter by subscriber.

        Returns:
            List of connections.
        """
        connections = list(self._websocket_connections.values())
        if subscriber_id:
            connections = [c for c in connections if c.subscriber_id == subscriber_id]
        return connections

    def cleanup_stale_connections(self) -> int:
        """Remove stale WebSocket connections.

        Returns:
            Number of connections removed.
        """
        with self._lock:
            now = time.time()
            stale_ids = []

            for conn_id, connection in self._websocket_connections.items():
                # Check if connection has timed out
                if connection.last_ping:
                    if now - connection.last_ping > self._connection_timeout_s:
                        if not connection.last_pong or connection.last_pong < connection.last_ping:
                            stale_ids.append(conn_id)
                elif now - connection.connected_at > self._connection_timeout_s:
                    # No ping sent, check connection age
                    stale_ids.append(conn_id)

            for conn_id in stale_ids:
                self.remove_websocket_connection(conn_id)

            if stale_ids:
                logger.debug("Cleaned up %d stale connections", len(stale_ids))

            return len(stale_ids)

    # Subscription Management

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        """Get subscription by ID.

        Args:
            subscription_id: Subscription ID.

        Returns:
            Subscription or None.
        """
        return self._subscriptions.get(subscription_id)

    def list_subscriptions(self, subscriber_id: str | None = None) -> list[Subscription]:
        """List subscriptions.

        Args:
            subscriber_id: Optional filter by subscriber.

        Returns:
            List of subscriptions.
        """
        subscriptions = list(self._subscriptions.values())
        if subscriber_id:
            subscriptions = [s for s in subscriptions if s.subscriber_id == subscriber_id]
        return subscriptions

    def list_subscribers(self) -> list[str]:
        """List all subscriber IDs.

        Returns:
            List of subscriber IDs.
        """
        return list(self._subscriber_queues.keys())

    def get_subscriber_stats(self, subscriber_id: str) -> dict[str, Any] | None:
        """Get statistics for a subscriber.

        Args:
            subscriber_id: Subscriber identifier.

        Returns:
            Statistics dictionary or None.
        """
        queue = self._subscriber_queues.get(subscriber_id)
        if not queue:
            return None

        subscriptions = [
            s for s in self._subscriptions.values() if s.subscriber_id == subscriber_id
        ]
        connections = [
            c for c in self._websocket_connections.values() if c.subscriber_id == subscriber_id
        ]

        return {
            "subscriber_id": subscriber_id,
            "queue": queue.get_stats(),
            "subscription_count": len(subscriptions),
            "connection_count": len(connections),
        }

    # Hooks

    def on_publish(self, callback: Callable[[StreamEvent], None]) -> None:
        """Register callback for event publication.

        Args:
            callback: Callback function.
        """
        self._on_publish_hooks.append(callback)

    def on_subscribe(self, callback: Callable[[Subscription], None]) -> None:
        """Register callback for subscription creation.

        Args:
            callback: Callback function.
        """
        self._on_subscribe_hooks.append(callback)

    def on_unsubscribe(self, callback: Callable[[Subscription], None]) -> None:
        """Register callback for subscription removal.

        Args:
            callback: Callback function.
        """
        self._on_unsubscribe_hooks.append(callback)

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """Get module statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._lock:
            return {
                "total_subscriptions": len(self._subscriptions),
                "total_subscribers": len(self._subscriber_queues),
                "total_websocket_connections": len(self._websocket_connections),
                "total_published": self._total_published,
                "total_delivered": self._total_delivered,
                "max_queue_size": self._max_queue_size,
                "heartbeat_interval_s": self._heartbeat_interval_s,
                "connection_timeout_s": self._connection_timeout_s,
            }

    def clear(self) -> dict[str, int]:
        """Clear all subscriptions and queues.

        Returns:
            Dictionary with cleared counts.
        """
        with self._lock:
            sub_count = len(self._subscriptions)
            queue_count = len(self._subscriber_queues)
            conn_count = len(self._websocket_connections)

            self._subscriptions.clear()
            self._subscriber_queues.clear()
            self._websocket_connections.clear()
            self._subscriber_subscriptions.clear()

            logger.info(
                "Cleared %d subscriptions, %d queues, %d connections",
                sub_count,
                queue_count,
                conn_count,
            )

            return {
                "subscriptions": sub_count,
                "queues": queue_count,
                "connections": conn_count,
            }

    def __len__(self) -> int:
        """Get number of subscriptions."""
        return len(self._subscriptions)

    def __contains__(self, subscription_id: str) -> bool:
        """Check if subscription exists."""
        return subscription_id in self._subscriptions


class EventBus:
    """Centralized event bus for cross-module event publishing.

    Provides a singleton-like pattern for event distribution
    across the Nexus platform.

    Example:
        >>> bus = EventBus.get_instance()
        >>> bus.publish("workflow.started", {"name": "my-workflow"})
    """

    _instance: EventBus | None = None
    _lock = threading.Lock()

    def __new__(cls, module: EventsModule | None = None) -> EventBus:
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, module: EventsModule | None = None):
        """Initialize event bus.

        Args:
            module: Optional EventsModule to use.
        """
        if self._initialized:
            return
        self._module = module if module is not None else EventsModule()
        self._initialized = True

    @classmethod
    def get_instance(cls, module: EventsModule | None = None) -> EventBus:
        """Get the singleton instance.

        Args:
            module: Optional EventsModule to use.

        Returns:
            EventBus instance.
        """
        return cls(module)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing)."""
        with cls._lock:
            cls._instance = None

    def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        **kwargs,
    ) -> StreamEvent:
        """Publish an event (delegates to module)."""
        return self._module.publish(event_type, data, **kwargs)

    def subscribe(
        self,
        subscriber_id: str,
        event_types: list[str] | None = None,
        **kwargs,
    ) -> Subscription:
        """Subscribe to events (delegates to module)."""
        return self._module.subscribe(subscriber_id, event_types, **kwargs)

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe (delegates to module)."""
        return self._module.unsubscribe(subscription_id)

    def get_events(
        self,
        subscriber_id: str,
        max_events: int = 100,
        timeout: float | None = None,
    ) -> list[StreamEvent]:
        """Get events (delegates to module)."""
        return self._module.get_events(subscriber_id, max_events, timeout)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics (delegates to module)."""
        return self._module.get_stats()

    @property
    def module(self) -> EventsModule:
        """Get the underlying module."""
        return self._module

    def __len__(self) -> int:
        """Get number of subscriptions."""
        return len(self._module)
