"""Event system for Nexus platform extensibility.

This module provides an asynchronous event emitter for decoupled communication
between Nexus components, plugins, and external integrations.

Example:
    >>> from aegis_sdk.nexus import EventEmitter, Event
    >>> emitter = EventEmitter()
    >>>
    >>> # Register event handler
    >>> def on_workflow_complete(event):
    ...     print(f"Workflow {event.data['name']} completed")
    >>>
    >>> emitter.on("workflow:complete", on_workflow_complete)
    >>>
    >>> # Emit event
    >>> emitter.emit("workflow:complete", {"name": "my-workflow", "success": True})
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[["Event"], None | Awaitable[None]]


class EventPriority(Enum):
    """Handler execution priority."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

    def __lt__(self, other: EventPriority) -> bool:
        """Compare priorities."""
        if isinstance(other, EventPriority):
            return self.value < other.value
        return NotImplemented


@dataclass
class Event:
    """Represents an event in the Nexus platform.

    Events are immutable data carriers that flow through the event system,
    enabling decoupled communication between components.

    Attributes:
        name: Event name/type (e.g., "workflow:complete").
        data: Event payload data.
        timestamp: Event creation timestamp (Unix time).
        source: Optional source identifier.
        correlation_id: Optional correlation ID for tracking.
        metadata: Additional event metadata.
    """

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure data is a dictionary."""
        if self.data is None:
            self.data = {}

    @property
    def age_ms(self) -> float:
        """Get event age in milliseconds."""
        return (time.time() - self.timestamp) * 1000

    def with_data(self, **kwargs) -> Event:
        """Create a new event with additional data.

        Args:
            **kwargs: Additional data to merge.

        Returns:
            New Event instance with merged data.
        """
        return Event(
            name=self.name,
            data={**self.data, **kwargs},
            timestamp=self.timestamp,
            source=self.source,
            correlation_id=self.correlation_id,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary representation.

        Returns:
            Dictionary representation of the event.
        """
        return {
            "name": self.name,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "age_ms": self.age_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Create event from dictionary.

        Args:
            data: Dictionary containing event data.

        Returns:
            Event instance.
        """
        return cls(
            name=data["name"],
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class HandlerRegistration:
    """Registered event handler metadata.

    Attributes:
        handler: The event handler function.
        priority: Handler execution priority.
        once: If True, handler is removed after first invocation.
        filter_fn: Optional filter function for conditional handling.
    """

    handler: EventHandler
    priority: EventPriority = EventPriority.NORMAL
    once: bool = False
    filter_fn: Callable[[Event], bool] | None = None

    def should_handle(self, event: Event) -> bool:
        """Check if this handler should handle the event.

        Args:
            event: Event to check.

        Returns:
            True if handler should process the event.
        """
        if self.filter_fn is None:
            return True
        try:
            return self.filter_fn(event)
        except Exception:
            return False


class EventEmitter:
    """Asynchronous event emitter for Nexus platform.

    Provides publish-subscribe event handling with support for
    async handlers, priorities, filters, and wildcard patterns.

    Example:
        >>> emitter = EventEmitter()
        >>> emitter.on("user:login", lambda e: print(f"User logged in: {e.data}"))
        >>> emitter.emit("user:login", {"user_id": "123"})

    Wildcard Patterns:
        - "user:*" matches any event starting with "user:"
        - "*" matches all events
    """

    def __init__(
        self,
        max_listeners: int = 100,
        async_mode: bool = False,
    ):
        """Initialize event emitter.

        Args:
            max_listeners: Maximum listeners per event type.
            async_mode: If True, all handlers run asynchronously.
        """
        self._handlers: dict[str, list[HandlerRegistration]] = defaultdict(list)
        self._max_listeners = max_listeners
        self._async_mode = async_mode
        self._lock = threading.RLock()
        self._event_history: list[Event] = []
        self._history_limit = 1000
        self._paused_events: set[str] = set()
        self._global_interceptors: list[Callable[[Event], Event | None]] = []

    def on(
        self,
        event_name: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> EventEmitter:
        """Register an event handler.

        Args:
            event_name: Event name to listen for (supports wildcards).
            handler: Handler function to invoke.
            priority: Handler execution priority.
            filter_fn: Optional filter for conditional handling.

        Returns:
            Self for chaining.

        Raises:
            ValueError: If max listeners exceeded.
        """
        with self._lock:
            if len(self._handlers[event_name]) >= self._max_listeners:
                raise ValueError(
                    f"Max listeners ({self._max_listeners}) exceeded for '{event_name}'"
                )

            registration = HandlerRegistration(
                handler=handler,
                priority=priority,
                filter_fn=filter_fn,
            )
            self._handlers[event_name].append(registration)

            # Sort by priority (highest first)
            self._handlers[event_name].sort(key=lambda r: r.priority.value, reverse=True)

            logger.debug("Registered handler for '%s'", event_name)
            return self

    def once(
        self,
        event_name: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> EventEmitter:
        """Register a one-time event handler.

        Handler is automatically removed after first invocation.

        Args:
            event_name: Event name to listen for.
            handler: Handler function to invoke once.
            priority: Handler execution priority.

        Returns:
            Self for chaining.
        """
        with self._lock:
            if len(self._handlers[event_name]) >= self._max_listeners:
                raise ValueError(
                    f"Max listeners ({self._max_listeners}) exceeded for '{event_name}'"
                )

            registration = HandlerRegistration(
                handler=handler,
                priority=priority,
                once=True,
            )
            self._handlers[event_name].append(registration)
            self._handlers[event_name].sort(key=lambda r: r.priority.value, reverse=True)

            return self

    def off(
        self,
        event_name: str,
        handler: EventHandler | None = None,
    ) -> bool:
        """Remove event handler(s).

        Args:
            event_name: Event name to remove handler from.
            handler: Specific handler to remove (None removes all).

        Returns:
            True if any handlers were removed.
        """
        with self._lock:
            if event_name not in self._handlers:
                return False

            if handler is None:
                # Remove all handlers for event
                del self._handlers[event_name]
                logger.debug("Removed all handlers for '%s'", event_name)
                return True

            # Remove specific handler
            original_count = len(self._handlers[event_name])
            self._handlers[event_name] = [
                r for r in self._handlers[event_name] if r.handler != handler
            ]
            removed = original_count - len(self._handlers[event_name])

            if removed > 0:
                logger.debug("Removed %d handler(s) for '%s'", removed, event_name)
                return True

            return False

    def emit(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        correlation_id: str | None = None,
    ) -> Event:
        """Emit an event synchronously.

        Args:
            event_name: Event name to emit.
            data: Event payload data.
            source: Event source identifier.
            correlation_id: Correlation ID for tracking.

        Returns:
            The emitted Event instance.
        """
        event = Event(
            name=event_name,
            data=data or {},
            source=source,
            correlation_id=correlation_id,
        )

        # Check if event is paused
        if event_name in self._paused_events:
            logger.debug("Event '%s' is paused, skipping", event_name)
            return event

        # Apply global interceptors
        for interceptor in self._global_interceptors:
            try:
                result = interceptor(event)
                if result is None:
                    # Interceptor stopped propagation
                    return event
                event = result
            except Exception as e:
                logger.warning("Event interceptor failed: %s", e)

        # Store in history
        self._store_event(event)

        # Get matching handlers
        handlers = self._get_matching_handlers(event_name)

        # Execute handlers
        once_handlers = []
        for registration in handlers:
            if not registration.should_handle(event):
                continue

            try:
                if asyncio.iscoroutinefunction(registration.handler):
                    # Run async handler in event loop if available
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(registration.handler(event))
                    except RuntimeError:
                        # No running loop, run synchronously via asyncio.run
                        asyncio.run(registration.handler(event))
                else:
                    registration.handler(event)

                if registration.once:
                    once_handlers.append(registration)

            except Exception as e:
                logger.error("Handler error for '%s': %s", event_name, e)

        # Remove once handlers
        for registration in once_handlers:
            self._remove_registration(event_name, registration)

        return event

    async def emit_async(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        correlation_id: str | None = None,
    ) -> Event:
        """Emit an event asynchronously.

        Args:
            event_name: Event name to emit.
            data: Event payload data.
            source: Event source identifier.
            correlation_id: Correlation ID for tracking.

        Returns:
            The emitted Event instance.
        """
        event = Event(
            name=event_name,
            data=data or {},
            source=source,
            correlation_id=correlation_id,
        )

        # Check if event is paused
        if event_name in self._paused_events:
            return event

        # Apply global interceptors
        for interceptor in self._global_interceptors:
            try:
                result = interceptor(event)
                if result is None:
                    return event
                event = result
            except Exception as e:
                logger.warning("Event interceptor failed: %s", e)

        # Store in history
        self._store_event(event)

        # Get matching handlers
        handlers = self._get_matching_handlers(event_name)

        # Execute handlers concurrently
        tasks = []
        once_handlers = []

        for registration in handlers:
            if not registration.should_handle(event):
                continue

            try:
                if asyncio.iscoroutinefunction(registration.handler):
                    tasks.append(registration.handler(event))
                else:
                    registration.handler(event)

                if registration.once:
                    once_handlers.append(registration)

            except Exception as e:
                logger.error("Handler error for '%s': %s", event_name, e)

        # Await all async handlers
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error("Async handler error: %s", result)

        # Remove once handlers
        for registration in once_handlers:
            self._remove_registration(event_name, registration)

        return event

    def _get_matching_handlers(self, event_name: str) -> list[HandlerRegistration]:
        """Get all handlers matching an event name including wildcards."""
        handlers = []

        with self._lock:
            # Exact match
            handlers.extend(self._handlers.get(event_name, []))

            # Wildcard matches
            for pattern, pattern_handlers in self._handlers.items():
                if pattern == event_name:
                    continue
                if pattern == "*":
                    handlers.extend(pattern_handlers)
                elif pattern.endswith("*"):
                    prefix = pattern[:-1]
                    if event_name.startswith(prefix):
                        handlers.extend(pattern_handlers)

        # Sort by priority
        handlers.sort(key=lambda r: r.priority.value, reverse=True)
        return handlers

    def _remove_registration(self, event_name: str, registration: HandlerRegistration) -> None:
        """Remove a specific handler registration."""
        with self._lock:
            if event_name in self._handlers:
                self._handlers[event_name] = [
                    r for r in self._handlers[event_name] if r != registration
                ]

    def _store_event(self, event: Event) -> None:
        """Store event in history."""
        self._event_history.append(event)
        if len(self._event_history) > self._history_limit:
            self._event_history = self._event_history[-self._history_limit :]

    def add_interceptor(self, interceptor: Callable[[Event], Event | None]) -> None:
        """Add a global event interceptor.

        Interceptors can modify events or stop propagation by returning None.

        Args:
            interceptor: Function that receives and returns Event (or None).
        """
        self._global_interceptors.append(interceptor)

    def remove_interceptor(self, interceptor: Callable[[Event], Event | None]) -> bool:
        """Remove a global event interceptor.

        Args:
            interceptor: Interceptor to remove.

        Returns:
            True if removed, False if not found.
        """
        try:
            self._global_interceptors.remove(interceptor)
            return True
        except ValueError:
            return False

    def pause(self, event_name: str) -> None:
        """Pause event emission for a specific event.

        Args:
            event_name: Event name to pause.
        """
        self._paused_events.add(event_name)

    def resume(self, event_name: str) -> None:
        """Resume event emission for a specific event.

        Args:
            event_name: Event name to resume.
        """
        self._paused_events.discard(event_name)

    def is_paused(self, event_name: str) -> bool:
        """Check if an event is paused.

        Args:
            event_name: Event name to check.

        Returns:
            True if event is paused.
        """
        return event_name in self._paused_events

    def listener_count(self, event_name: str) -> int:
        """Get number of listeners for an event.

        Args:
            event_name: Event name to count.

        Returns:
            Number of registered listeners.
        """
        return len(self._handlers.get(event_name, []))

    def event_names(self) -> list[str]:
        """Get all registered event names.

        Returns:
            List of event names with handlers.
        """
        return list(self._handlers.keys())

    def get_history(
        self,
        event_name: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get event history.

        Args:
            event_name: Filter by event name (None for all).
            limit: Maximum events to return.

        Returns:
            List of events in reverse chronological order.
        """
        events = self._event_history
        if event_name:
            events = [e for e in events if e.name == event_name]
        return list(reversed(events[-limit:]))

    def clear_history(self) -> int:
        """Clear event history.

        Returns:
            Number of events cleared.
        """
        count = len(self._event_history)
        self._event_history.clear()
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get emitter statistics.

        Returns:
            Dictionary with emitter statistics.
        """
        with self._lock:
            total_handlers = sum(len(h) for h in self._handlers.values())
            return {
                "event_types": len(self._handlers),
                "total_handlers": total_handlers,
                "max_listeners": self._max_listeners,
                "history_size": len(self._event_history),
                "history_limit": self._history_limit,
                "paused_events": len(self._paused_events),
                "interceptors": len(self._global_interceptors),
                "handlers_by_event": {
                    name: len(handlers) for name, handlers in self._handlers.items()
                },
            }

    def clear(self) -> None:
        """Clear all handlers and history."""
        with self._lock:
            self._handlers.clear()
            self._event_history.clear()
            self._paused_events.clear()
            self._global_interceptors.clear()
            logger.info("Cleared all event handlers and history")

    def __len__(self) -> int:
        """Get total number of handlers."""
        return sum(len(h) for h in self._handlers.values())
