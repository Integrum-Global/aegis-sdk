"""
Tier 1: Unit Tests for Nexus Event System.

Tests event emission, handling, and subscription patterns.
"""

import asyncio

import pytest

from aegis_sdk.nexus.events import (
    Event,
    EventEmitter,
    EventPriority,
)


@pytest.fixture
def emitter():
    """Create a fresh event emitter for each test."""
    return EventEmitter()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEvent:
    """Test Event dataclass."""

    def test_event_creation(self):
        """Event should be created with required fields."""
        event = Event(name="test:event", data={"key": "value"})
        assert event.name == "test:event"
        assert event.data["key"] == "value"

    def test_event_timestamp(self):
        """Event should have a timestamp."""
        event = Event(name="test:event")
        assert event.timestamp > 0

    def test_event_age_ms(self):
        """age_ms should return event age."""
        event = Event(name="test:event")
        assert event.age_ms >= 0

    def test_event_with_data(self):
        """with_data should create new event with merged data."""
        event = Event(name="test:event", data={"key1": "value1"})
        new_event = event.with_data(key2="value2")

        assert new_event.data["key1"] == "value1"
        assert new_event.data["key2"] == "value2"
        assert "key2" not in event.data  # Original unchanged

    def test_event_to_dict(self):
        """to_dict should return dictionary representation."""
        event = Event(
            name="test:event",
            data={"key": "value"},
            source="test",
            correlation_id="123",
        )
        data = event.to_dict()
        assert data["name"] == "test:event"
        assert data["data"]["key"] == "value"
        assert data["source"] == "test"
        assert data["correlation_id"] == "123"

    def test_event_from_dict(self):
        """from_dict should create event from dictionary."""
        data = {
            "name": "test:event",
            "data": {"key": "value"},
            "source": "test",
        }
        event = Event.from_dict(data)
        assert event.name == "test:event"
        assert event.data["key"] == "value"
        assert event.source == "test"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEventEmitter:
    """Test EventEmitter class."""

    def test_emitter_on_registers_handler(self, emitter):
        """on should register event handler."""

        def handler(e):
            return None

        emitter.on("test:event", handler)
        assert emitter.listener_count("test:event") == 1

    def test_emitter_on_chaining(self, emitter):
        """on should return self for chaining."""
        result = emitter.on("event1", lambda e: None).on("event2", lambda e: None)
        assert result is emitter

    def test_emitter_on_with_priority(self, emitter):
        """on should accept priority."""
        emitter.on("test:event", lambda e: None, priority=EventPriority.HIGH)
        assert emitter.listener_count("test:event") == 1

    def test_emitter_on_respects_max_listeners(self):
        """on should raise when max listeners exceeded."""
        small_emitter = EventEmitter(max_listeners=2)
        small_emitter.on("test", lambda e: None)
        small_emitter.on("test", lambda e: None)
        with pytest.raises(ValueError):
            small_emitter.on("test", lambda e: None)

    def test_emitter_once_registers_one_time_handler(self, emitter):
        """once should register handler that fires once."""
        results = []
        emitter.once("test:event", lambda e: results.append(1))

        emitter.emit("test:event")
        emitter.emit("test:event")

        assert len(results) == 1

    def test_emitter_off_removes_handler(self, emitter):
        """off should remove handler."""

        def handler(e):
            return None

        emitter.on("test:event", handler)
        result = emitter.off("test:event", handler)
        assert result is True
        assert emitter.listener_count("test:event") == 0

    def test_emitter_off_removes_all_handlers(self, emitter):
        """off without handler should remove all handlers."""
        emitter.on("test:event", lambda e: None)
        emitter.on("test:event", lambda e: None)
        result = emitter.off("test:event")
        assert result is True
        assert emitter.listener_count("test:event") == 0

    def test_emitter_off_returns_false_for_missing(self, emitter):
        """off should return False for missing event."""
        assert emitter.off("nonexistent") is False

    def test_emitter_emit_invokes_handlers(self, emitter):
        """emit should invoke registered handlers."""
        results = []
        emitter.on("test:event", lambda e: results.append(e.data["value"]))

        emitter.emit("test:event", {"value": 42})
        assert results == [42]

    def test_emitter_emit_returns_event(self, emitter):
        """emit should return the emitted event."""
        event = emitter.emit("test:event", {"key": "value"})
        assert event.name == "test:event"
        assert event.data["key"] == "value"

    def test_emitter_emit_with_source_and_correlation(self, emitter):
        """emit should accept source and correlation_id."""
        event = emitter.emit(
            "test:event",
            data={"key": "value"},
            source="test",
            correlation_id="123",
        )
        assert event.source == "test"
        assert event.correlation_id == "123"

    def test_emitter_emit_handler_priority(self, emitter):
        """emit should invoke handlers in priority order."""
        results = []
        emitter.on("test", lambda e: results.append("low"), priority=EventPriority.LOW)
        emitter.on("test", lambda e: results.append("high"), priority=EventPriority.HIGH)
        emitter.on("test", lambda e: results.append("normal"), priority=EventPriority.NORMAL)

        emitter.emit("test")
        assert results == ["high", "normal", "low"]

    def test_emitter_wildcard_star(self, emitter):
        """* wildcard should match all events."""
        results = []
        emitter.on("*", lambda e: results.append(e.name))

        emitter.emit("event1")
        emitter.emit("event2")

        assert results == ["event1", "event2"]

    def test_emitter_wildcard_prefix(self, emitter):
        """Prefix wildcard should match events with prefix."""
        results = []
        emitter.on("user:*", lambda e: results.append(e.name))

        emitter.emit("user:login")
        emitter.emit("user:logout")
        emitter.emit("order:created")

        assert results == ["user:login", "user:logout"]

    def test_emitter_filter_function(self, emitter):
        """Filter function should conditionally handle events."""
        results = []
        emitter.on(
            "test",
            lambda e: results.append(e.data["value"]),
            filter_fn=lambda e: e.data.get("value", 0) > 10,
        )

        emitter.emit("test", {"value": 5})
        emitter.emit("test", {"value": 15})

        assert results == [15]

    def test_emitter_pause_and_resume(self, emitter):
        """pause and resume should control event emission."""
        results = []
        emitter.on("test", lambda e: results.append(1))

        emitter.pause("test")
        emitter.emit("test")
        assert len(results) == 0

        emitter.resume("test")
        emitter.emit("test")
        assert len(results) == 1

    def test_emitter_is_paused(self, emitter):
        """is_paused should check pause status."""
        assert emitter.is_paused("test") is False
        emitter.pause("test")
        assert emitter.is_paused("test") is True

    def test_emitter_add_interceptor(self, emitter):
        """Interceptor should modify events."""

        def add_timestamp(event):
            return event.with_data(modified=True)

        emitter.add_interceptor(add_timestamp)
        results = []
        emitter.on("test", lambda e: results.append(e.data.get("modified")))

        emitter.emit("test")
        assert results == [True]

    def test_emitter_interceptor_stops_propagation(self, emitter):
        """Interceptor returning None should stop propagation."""
        emitter.add_interceptor(lambda e: None)
        results = []
        emitter.on("test", lambda e: results.append(1))

        emitter.emit("test")
        assert len(results) == 0

    def test_emitter_remove_interceptor(self, emitter):
        """remove_interceptor should remove interceptor."""

        def interceptor(e):
            return e

        emitter.add_interceptor(interceptor)
        assert emitter.remove_interceptor(interceptor) is True
        assert emitter.remove_interceptor(interceptor) is False

    def test_emitter_listener_count(self, emitter):
        """listener_count should return handler count."""
        assert emitter.listener_count("test") == 0
        emitter.on("test", lambda e: None)
        assert emitter.listener_count("test") == 1

    def test_emitter_event_names(self, emitter):
        """event_names should return registered event names."""
        emitter.on("event1", lambda e: None)
        emitter.on("event2", lambda e: None)

        names = emitter.event_names()
        assert "event1" in names
        assert "event2" in names

    def test_emitter_get_history(self, emitter):
        """get_history should return event history."""
        emitter.emit("event1")
        emitter.emit("event2")

        history = emitter.get_history()
        assert len(history) == 2
        assert history[0].name == "event2"  # Most recent first

    def test_emitter_get_history_filtered(self, emitter):
        """get_history should filter by event name."""
        emitter.emit("event1")
        emitter.emit("event2")
        emitter.emit("event1")

        history = emitter.get_history(event_name="event1")
        assert len(history) == 2

    def test_emitter_clear_history(self, emitter):
        """clear_history should remove event history."""
        emitter.emit("test")
        emitter.emit("test")

        count = emitter.clear_history()
        assert count == 2
        assert len(emitter.get_history()) == 0

    def test_emitter_get_stats(self, emitter):
        """get_stats should return emitter statistics."""
        emitter.on("event1", lambda e: None)
        emitter.on("event2", lambda e: None)
        emitter.emit("event1")

        stats = emitter.get_stats()
        assert stats["event_types"] == 2
        assert stats["total_handlers"] == 2
        assert stats["history_size"] == 1

    def test_emitter_clear(self, emitter):
        """clear should remove all handlers and history."""
        emitter.on("test", lambda e: None)
        emitter.emit("test")

        emitter.clear()
        assert len(emitter) == 0
        assert len(emitter.get_history()) == 0

    def test_emitter_len(self, emitter):
        """__len__ should return total handler count."""
        assert len(emitter) == 0
        emitter.on("event1", lambda e: None)
        emitter.on("event2", lambda e: None)
        assert len(emitter) == 2


@pytest.mark.unit
@pytest.mark.timeout(5)
@pytest.mark.asyncio
class TestEventEmitterAsync:
    """Test EventEmitter async functionality."""

    async def test_emit_async_invokes_handlers(self):
        """emit_async should invoke async handlers."""
        emitter = EventEmitter()
        results = []

        async def async_handler(event):
            results.append(event.data["value"])

        emitter.on("test", async_handler)
        await emitter.emit_async("test", {"value": 42})

        assert results == [42]

    async def test_emit_async_concurrent_handlers(self):
        """emit_async should run handlers concurrently."""
        emitter = EventEmitter()
        results = []

        async def slow_handler(event):
            await asyncio.sleep(0.01)
            results.append(event.data["value"])

        emitter.on("test", slow_handler)
        emitter.on("test", slow_handler)

        await emitter.emit_async("test", {"value": 1})
        assert len(results) == 2
