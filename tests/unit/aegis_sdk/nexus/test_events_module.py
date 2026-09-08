"""
Tier 1: Unit Tests for Nexus Events Module.

Tests real-time event streaming, pub/sub, SSE, WebSocket connections,
and backpressure handling.
"""

import time

import pytest

from aegis_sdk.nexus.events_module import (
    ConnectionState,
    EventBus,
    EventQueue,
    EventsModule,
    EventType,
    StreamEvent,
    StreamProtocol,
    Subscription,
    WebSocketConnection,
)


@pytest.fixture
def module():
    """Create a fresh events module for each test."""
    return EventsModule()


@pytest.fixture
def event_bus():
    """Create a fresh event bus for each test."""
    EventBus.reset_instance()
    return EventBus.get_instance()


# Reset event bus singleton after each test
@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset event bus singleton before and after each test."""
    EventBus.reset_instance()
    yield
    EventBus.reset_instance()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEventType:
    """Test EventType enum."""

    def test_event_type_values(self):
        """EventType should have expected values."""
        assert EventType.WORKFLOW_STARTED.value == "workflow.started"
        assert EventType.WORKFLOW_COMPLETED.value == "workflow.completed"
        assert EventType.NODE_EXECUTED.value == "node.executed"
        assert EventType.ERROR_OCCURRED.value == "error.occurred"

    def test_event_type_str(self):
        """EventType str should return value."""
        assert str(EventType.WORKFLOW_STARTED) == "workflow.started"

    def test_event_type_from_string(self):
        """EventType.from_string should convert strings."""
        assert EventType.from_string("workflow.started") == EventType.WORKFLOW_STARTED
        assert EventType.from_string("unknown") == EventType.CUSTOM


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestStreamProtocol:
    """Test StreamProtocol enum."""

    def test_protocol_values(self):
        """StreamProtocol should have SSE and WebSocket."""
        assert StreamProtocol.SSE is not None
        assert StreamProtocol.WEBSOCKET is not None

    def test_protocol_str(self):
        """StreamProtocol str should return lowercase name."""
        assert str(StreamProtocol.SSE) == "sse"
        assert str(StreamProtocol.WEBSOCKET) == "websocket"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestConnectionState:
    """Test ConnectionState enum."""

    def test_connection_states(self):
        """ConnectionState should have expected states."""
        assert ConnectionState.CONNECTING is not None
        assert ConnectionState.CONNECTED is not None
        assert ConnectionState.DISCONNECTING is not None
        assert ConnectionState.DISCONNECTED is not None

    def test_connection_state_str(self):
        """ConnectionState str should return lowercase name."""
        assert str(ConnectionState.CONNECTED) == "connected"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestStreamEvent:
    """Test StreamEvent dataclass."""

    def test_event_creation(self):
        """StreamEvent should be created with required fields."""
        event = StreamEvent(
            id="evt-1",
            type="workflow.started",
            data={"workflow_name": "test"},
        )
        assert event.id == "evt-1"
        assert event.type == "workflow.started"
        assert event.data["workflow_name"] == "test"

    def test_event_timestamp(self):
        """StreamEvent should have a timestamp."""
        event = StreamEvent(id="evt-1", type="test")
        assert event.timestamp > 0

    def test_event_to_sse(self):
        """StreamEvent.to_sse should format as SSE."""
        event = StreamEvent(
            id="evt-1",
            type="test.event",
            data={"key": "value"},
        )
        sse = event.to_sse()
        assert "id: evt-1" in sse
        assert "event: test.event" in sse
        assert "data:" in sse
        assert '"key"' in sse

    def test_event_to_sse_with_retry(self):
        """StreamEvent.to_sse should include retry if set."""
        event = StreamEvent(id="evt-1", type="test", retry=3000)
        sse = event.to_sse()
        assert "retry: 3000" in sse

    def test_event_to_websocket(self):
        """StreamEvent.to_websocket should format as JSON."""
        event = StreamEvent(
            id="evt-1",
            type="test.event",
            data={"key": "value"},
        )
        ws = event.to_websocket()
        assert '"id": "evt-1"' in ws
        assert '"type": "test.event"' in ws

    def test_event_to_dict(self):
        """StreamEvent.to_dict should return dictionary."""
        event = StreamEvent(
            id="evt-1",
            type="test",
            data={"key": "value"},
            source="test-source",
            workflow_name="my-workflow",
        )
        data = event.to_dict()
        assert data["id"] == "evt-1"
        assert data["type"] == "test"
        assert data["source"] == "test-source"
        assert data["workflow_name"] == "my-workflow"

    def test_event_from_dict(self):
        """StreamEvent.from_dict should create from dictionary."""
        data = {
            "id": "evt-1",
            "type": "test",
            "data": {"key": "value"},
            "source": "test-source",
        }
        event = StreamEvent.from_dict(data)
        assert event.id == "evt-1"
        assert event.type == "test"
        assert event.source == "test-source"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSubscription:
    """Test Subscription dataclass."""

    def test_subscription_creation(self):
        """Subscription should be created with required fields."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            event_types=["workflow.started"],
        )
        assert sub.id == "sub-1"
        assert sub.subscriber_id == "client-1"
        assert "workflow.started" in sub.event_types

    def test_subscription_matches_event_type(self):
        """Subscription.matches should filter by event type."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            event_types=["workflow.started"],
        )
        event_match = StreamEvent(id="evt-1", type="workflow.started")
        event_no_match = StreamEvent(id="evt-2", type="workflow.completed")

        assert sub.matches(event_match) is True
        assert sub.matches(event_no_match) is False

    def test_subscription_matches_wildcard(self):
        """Subscription.matches should support wildcards."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            event_types=["workflow.*"],
        )
        event1 = StreamEvent(id="evt-1", type="workflow.started")
        event2 = StreamEvent(id="evt-2", type="workflow.completed")
        event3 = StreamEvent(id="evt-3", type="node.executed")

        assert sub.matches(event1) is True
        assert sub.matches(event2) is True
        assert sub.matches(event3) is False

    def test_subscription_matches_workflow_name(self):
        """Subscription.matches should filter by workflow name."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            workflow_name="my-workflow",
        )
        event_match = StreamEvent(id="evt-1", type="test", workflow_name="my-workflow")
        event_no_match = StreamEvent(id="evt-2", type="test", workflow_name="other")

        assert sub.matches(event_match) is True
        assert sub.matches(event_no_match) is False

    def test_subscription_matches_session_id(self):
        """Subscription.matches should filter by session ID."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            session_id="session-1",
        )
        event_match = StreamEvent(id="evt-1", type="test", session_id="session-1")
        event_no_match = StreamEvent(id="evt-2", type="test", session_id="session-2")

        assert sub.matches(event_match) is True
        assert sub.matches(event_no_match) is False

    def test_subscription_matches_custom_filter(self):
        """Subscription.matches should use custom filter function."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            filter_fn=lambda e: e.data.get("priority", 0) > 5,
        )
        event_match = StreamEvent(id="evt-1", type="test", data={"priority": 10})
        event_no_match = StreamEvent(id="evt-2", type="test", data={"priority": 3})

        assert sub.matches(event_match) is True
        assert sub.matches(event_no_match) is False

    def test_subscription_inactive_no_match(self):
        """Inactive subscription should not match."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            active=False,
        )
        event = StreamEvent(id="evt-1", type="test")
        assert sub.matches(event) is False

    def test_subscription_to_dict(self):
        """Subscription.to_dict should return dictionary."""
        sub = Subscription(
            id="sub-1",
            subscriber_id="client-1",
            event_types=["workflow.started"],
            workflow_name="my-workflow",
        )
        data = sub.to_dict()
        assert data["id"] == "sub-1"
        assert data["subscriber_id"] == "client-1"
        assert "workflow.started" in data["event_types"]


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWebSocketConnection:
    """Test WebSocketConnection dataclass."""

    def test_connection_creation(self):
        """WebSocketConnection should be created with required fields."""
        conn = WebSocketConnection(
            id="conn-1",
            subscriber_id="client-1",
        )
        assert conn.id == "conn-1"
        assert conn.subscriber_id == "client-1"
        assert conn.state == ConnectionState.CONNECTED

    def test_connection_is_alive(self):
        """WebSocketConnection.is_alive should check connection state."""
        conn = WebSocketConnection(id="conn-1", subscriber_id="client-1")
        assert conn.is_alive is True

        conn.state = ConnectionState.DISCONNECTED
        assert conn.is_alive is False

    def test_connection_is_alive_with_ping_pong(self):
        """WebSocketConnection.is_alive should check ping/pong."""
        conn = WebSocketConnection(id="conn-1", subscriber_id="client-1")
        conn.last_ping = time.time()
        conn.last_pong = time.time() + 0.1

        assert conn.is_alive is True

        conn.last_pong = conn.last_ping - 1  # Pong before ping
        assert conn.is_alive is False

    def test_connection_latency(self):
        """WebSocketConnection.latency_ms should calculate latency."""
        conn = WebSocketConnection(id="conn-1", subscriber_id="client-1")
        conn.last_ping = time.time()
        conn.last_pong = conn.last_ping + 0.1

        latency = conn.latency_ms
        assert latency is not None
        assert 95 <= latency <= 105  # ~100ms with some tolerance

    def test_connection_to_dict(self):
        """WebSocketConnection.to_dict should return dictionary."""
        conn = WebSocketConnection(
            id="conn-1",
            subscriber_id="client-1",
            metadata={"user": "test"},
        )
        data = conn.to_dict()
        assert data["id"] == "conn-1"
        assert data["subscriber_id"] == "client-1"
        assert data["state"] == "connected"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEventQueue:
    """Test EventQueue class."""

    def test_queue_creation(self):
        """EventQueue should be created with max size."""
        queue = EventQueue(max_size=100)
        assert queue.size == 0
        assert queue.is_full is False

    def test_queue_put_get(self):
        """EventQueue should put and get events."""
        queue = EventQueue(max_size=10)
        event = StreamEvent(id="evt-1", type="test")

        result = queue.put(event)
        assert result is True
        assert queue.size == 1

        retrieved = queue.get(timeout=0.1)
        assert retrieved is not None
        assert retrieved.id == "evt-1"

    def test_queue_get_all(self):
        """EventQueue.get_all should return multiple events."""
        queue = EventQueue(max_size=10)

        for i in range(5):
            queue.put(StreamEvent(id=f"evt-{i}", type="test"))

        events = queue.get_all(max_events=10)
        assert len(events) == 5

    def test_queue_drop_oldest_overflow(self):
        """EventQueue should drop oldest on overflow with drop_oldest strategy."""
        queue = EventQueue(max_size=3, overflow_strategy="drop_oldest")

        for i in range(5):
            queue.put(StreamEvent(id=f"evt-{i}", type="test"))

        assert queue.size == 3
        events = queue.get_all()
        # Should have evt-2, evt-3, evt-4 (oldest dropped)
        ids = [e.id for e in events]
        assert "evt-0" not in ids
        assert "evt-1" not in ids
        assert "evt-4" in ids

    def test_queue_clear(self):
        """EventQueue.clear should remove all events."""
        queue = EventQueue(max_size=10)
        for i in range(5):
            queue.put(StreamEvent(id=f"evt-{i}", type="test"))

        count = queue.clear()
        assert count == 5
        assert queue.size == 0

    def test_queue_get_stats(self):
        """EventQueue.get_stats should return statistics."""
        queue = EventQueue(max_size=10, overflow_strategy="drop_oldest")
        for i in range(5):
            queue.put(StreamEvent(id=f"evt-{i}", type="test"))

        stats = queue.get_stats()
        assert stats["size"] == 5
        assert stats["max_size"] == 10
        assert stats["total_count"] == 5
        assert stats["overflow_strategy"] == "drop_oldest"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEventsModule:
    """Test EventsModule class."""

    def test_module_creation(self):
        """EventsModule should be created with defaults."""
        module = EventsModule()
        assert len(module) == 0

    def test_module_subscribe(self, module):
        """EventsModule.subscribe should create subscription."""
        sub = module.subscribe(
            subscriber_id="client-1",
            event_types=["workflow.started"],
        )

        assert sub.id is not None
        assert sub.subscriber_id == "client-1"
        assert sub.id in module

    def test_module_subscribe_with_filters(self, module):
        """EventsModule.subscribe should accept all filters."""
        sub = module.subscribe(
            subscriber_id="client-1",
            event_types=["workflow.*"],
            workflow_name="my-workflow",
            session_id="session-1",
            protocol=StreamProtocol.WEBSOCKET,
        )

        assert sub.workflow_name == "my-workflow"
        assert sub.session_id == "session-1"
        assert sub.protocol == StreamProtocol.WEBSOCKET

    def test_module_unsubscribe(self, module):
        """EventsModule.unsubscribe should remove subscription."""
        sub = module.subscribe(subscriber_id="client-1")
        result = module.unsubscribe(sub.id)

        assert result is True
        assert sub.id not in module

    def test_module_unsubscribe_returns_false_for_missing(self, module):
        """EventsModule.unsubscribe should return False for missing."""
        assert module.unsubscribe("nonexistent") is False

    def test_module_unsubscribe_all(self, module):
        """EventsModule.unsubscribe_all should remove all subscriber subscriptions."""
        module.subscribe(subscriber_id="client-1", event_types=["type1"])
        module.subscribe(subscriber_id="client-1", event_types=["type2"])
        module.subscribe(subscriber_id="client-2", event_types=["type1"])

        count = module.unsubscribe_all("client-1")
        assert count == 2
        assert len(module.list_subscriptions("client-1")) == 0
        assert len(module.list_subscriptions("client-2")) == 1

    def test_module_publish(self, module):
        """EventsModule.publish should create and return event."""
        event = module.publish(
            event_type="workflow.started",
            data={"name": "test"},
            source="test-source",
        )

        assert event.id is not None
        assert event.type == "workflow.started"
        assert event.data["name"] == "test"
        assert event.source == "test-source"

    def test_module_publish_delivers_to_subscribers(self, module):
        """EventsModule.publish should deliver to matching subscribers."""
        module.subscribe(subscriber_id="client-1", event_types=["workflow.started"])

        module.publish("workflow.started", data={"name": "test"})

        events = module.get_events("client-1", max_events=10)
        assert len(events) == 1
        assert events[0].type == "workflow.started"

    def test_module_publish_filters_by_event_type(self, module):
        """EventsModule.publish should filter by event type."""
        module.subscribe(subscriber_id="client-1", event_types=["workflow.started"])
        module.subscribe(subscriber_id="client-2", event_types=["workflow.completed"])

        module.publish("workflow.started", data={"name": "test"})

        events1 = module.get_events("client-1")
        events2 = module.get_events("client-2")

        assert len(events1) == 1
        assert len(events2) == 0

    def test_module_publish_filters_by_workflow_name(self, module):
        """EventsModule.publish should filter by workflow name."""
        module.subscribe(subscriber_id="client-1", workflow_name="workflow-a")
        module.subscribe(subscriber_id="client-2", workflow_name="workflow-b")

        module.publish("test", workflow_name="workflow-a")

        events1 = module.get_events("client-1")
        events2 = module.get_events("client-2")

        assert len(events1) == 1
        assert len(events2) == 0

    def test_module_get_events_empty(self, module):
        """EventsModule.get_events should return empty for no events."""
        module.subscribe(subscriber_id="client-1")
        events = module.get_events("client-1")
        assert events == []

    def test_module_get_events_max_limit(self, module):
        """EventsModule.get_events should respect max_events."""
        module.subscribe(subscriber_id="client-1")

        for i in range(10):
            module.publish("test", data={"i": i})

        events = module.get_events("client-1", max_events=5)
        assert len(events) == 5

    def test_module_list_subscriptions(self, module):
        """EventsModule.list_subscriptions should list all or filtered."""
        module.subscribe(subscriber_id="client-1")
        module.subscribe(subscriber_id="client-2")

        all_subs = module.list_subscriptions()
        assert len(all_subs) == 2

        client1_subs = module.list_subscriptions("client-1")
        assert len(client1_subs) == 1

    def test_module_list_subscribers(self, module):
        """EventsModule.list_subscribers should return subscriber IDs."""
        module.subscribe(subscriber_id="client-1")
        module.subscribe(subscriber_id="client-2")

        subscribers = module.list_subscribers()
        assert "client-1" in subscribers
        assert "client-2" in subscribers

    def test_module_get_subscriber_stats(self, module):
        """EventsModule.get_subscriber_stats should return stats."""
        module.subscribe(subscriber_id="client-1")
        module.publish("test")

        stats = module.get_subscriber_stats("client-1")
        assert stats is not None
        assert stats["subscriber_id"] == "client-1"
        assert "queue" in stats

    def test_module_websocket_connection(self, module):
        """EventsModule should manage WebSocket connections."""
        conn = module.add_websocket_connection("client-1", metadata={"user": "test"})

        assert conn.id is not None
        assert conn.subscriber_id == "client-1"
        assert conn.metadata["user"] == "test"

        retrieved = module.get_websocket_connection(conn.id)
        assert retrieved is not None
        assert retrieved.id == conn.id

    def test_module_remove_websocket_connection(self, module):
        """EventsModule.remove_websocket_connection should remove connection."""
        conn = module.add_websocket_connection("client-1")
        result = module.remove_websocket_connection(conn.id)

        assert result is True
        assert module.get_websocket_connection(conn.id) is None

    def test_module_ping_pong_connection(self, module):
        """EventsModule should handle ping/pong for connections."""
        conn = module.add_websocket_connection("client-1")

        assert module.ping_connection(conn.id) is True
        assert module.pong_connection(conn.id) is True

        updated = module.get_websocket_connection(conn.id)
        assert updated.last_ping is not None
        assert updated.last_pong is not None

    def test_module_list_websocket_connections(self, module):
        """EventsModule.list_websocket_connections should list connections."""
        module.add_websocket_connection("client-1")
        module.add_websocket_connection("client-2")
        module.add_websocket_connection("client-1")

        all_conns = module.list_websocket_connections()
        assert len(all_conns) == 3

        client1_conns = module.list_websocket_connections("client-1")
        assert len(client1_conns) == 2

    def test_module_cleanup_stale_connections(self, module):
        """EventsModule.cleanup_stale_connections should remove stale."""
        # Create module with short timeout
        short_module = EventsModule(connection_timeout_s=0.1)
        conn = short_module.add_websocket_connection("client-1")
        short_module.ping_connection(conn.id)

        # Wait for timeout
        time.sleep(0.2)

        count = short_module.cleanup_stale_connections()
        assert count == 1

    def test_module_hooks(self, module):
        """EventsModule hooks should be called."""
        published_events = []
        subscribed = []
        unsubscribed = []

        module.on_publish(lambda e: published_events.append(e))
        module.on_subscribe(lambda s: subscribed.append(s))
        module.on_unsubscribe(lambda s: unsubscribed.append(s))

        sub = module.subscribe(subscriber_id="client-1")
        assert len(subscribed) == 1

        module.publish("test")
        assert len(published_events) == 1

        module.unsubscribe(sub.id)
        assert len(unsubscribed) == 1

    def test_module_get_stats(self, module):
        """EventsModule.get_stats should return statistics."""
        module.subscribe(subscriber_id="client-1")
        module.publish("test")

        stats = module.get_stats()
        assert stats["total_subscriptions"] == 1
        assert stats["total_subscribers"] == 1
        assert stats["total_published"] == 1

    def test_module_clear(self, module):
        """EventsModule.clear should remove everything."""
        module.subscribe(subscriber_id="client-1")
        module.add_websocket_connection("client-1")

        result = module.clear()
        assert result["subscriptions"] == 1
        assert result["connections"] == 1
        assert len(module) == 0

    def test_module_len_and_contains(self, module):
        """EventsModule should support len and contains."""
        assert len(module) == 0
        sub = module.subscribe(subscriber_id="client-1")
        assert len(module) == 1
        assert sub.id in module
        assert "nonexistent" not in module


@pytest.mark.unit
@pytest.mark.timeout(5)
@pytest.mark.asyncio
class TestEventsModuleAsync:
    """Test EventsModule async functionality."""

    async def test_get_events_async(self):
        """get_events_async should return events asynchronously."""
        module = EventsModule()
        module.subscribe(subscriber_id="client-1")
        module.publish("test", data={"value": 42})

        events = await module.get_events_async("client-1")
        assert len(events) == 1
        assert events[0].data["value"] == 42

    async def test_stream_sse_async(self):
        """stream_sse_async should yield SSE events."""
        module = EventsModule()
        module.subscribe(subscriber_id="client-1")
        module.publish("test", data={"value": 1})
        module.publish("test", data={"value": 2})

        events_received = []
        async for sse in module.stream_sse_async("client-1", timeout=0.1):
            if "heartbeat" not in sse:
                events_received.append(sse)
            if len(events_received) >= 2:
                break

        assert len(events_received) == 2


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEventBus:
    """Test EventBus singleton."""

    def test_event_bus_singleton(self):
        """EventBus should be a singleton."""
        bus1 = EventBus.get_instance()
        bus2 = EventBus.get_instance()
        assert bus1 is bus2

    def test_event_bus_reset(self):
        """EventBus.reset_instance should reset singleton."""
        bus1 = EventBus.get_instance()
        EventBus.reset_instance()
        bus2 = EventBus.get_instance()
        assert bus1 is not bus2

    def test_event_bus_publish(self, event_bus):
        """EventBus.publish should publish events."""
        event = event_bus.publish("test", data={"key": "value"})
        assert event.type == "test"

    def test_event_bus_subscribe(self, event_bus):
        """EventBus.subscribe should create subscription."""
        sub = event_bus.subscribe("client-1", event_types=["test"])
        assert sub.subscriber_id == "client-1"

    def test_event_bus_unsubscribe(self, event_bus):
        """EventBus.unsubscribe should remove subscription."""
        sub = event_bus.subscribe("client-1")
        result = event_bus.unsubscribe(sub.id)
        assert result is True

    def test_event_bus_get_events(self, event_bus):
        """EventBus.get_events should return events."""
        event_bus.subscribe("client-1")
        event_bus.publish("test", data={"value": 42})

        events = event_bus.get_events("client-1")
        assert len(events) == 1

    def test_event_bus_get_stats(self, event_bus):
        """EventBus.get_stats should return statistics."""
        stats = event_bus.get_stats()
        assert "total_subscriptions" in stats

    def test_event_bus_module_access(self, event_bus):
        """EventBus.module should provide access to underlying module."""
        assert event_bus.module is not None
        assert isinstance(event_bus.module, EventsModule)

    def test_event_bus_len(self, event_bus):
        """EventBus should support len."""
        assert len(event_bus) == 0
        event_bus.subscribe("client-1")
        assert len(event_bus) == 1
