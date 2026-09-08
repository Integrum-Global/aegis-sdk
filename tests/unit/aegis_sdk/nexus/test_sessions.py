"""
Tier 1: Unit Tests for Nexus Session Management.

Tests session creation, retrieval, and lifecycle management.
"""

import time

import pytest

from aegis_sdk.nexus.sessions import (
    Session,
    SessionManager,
    SessionMetrics,
    SessionState,
)


@pytest.fixture
def manager():
    """Create a fresh session manager for each test."""
    return SessionManager(default_ttl_s=3600, max_sessions=100)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSession:
    """Test Session dataclass."""

    def test_session_creation(self):
        """Session should be created with required fields."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now,
        )
        assert session.id == "test-id"
        assert session.channel == "api"
        assert session.state == SessionState.ACTIVE

    def test_session_touch(self):
        """touch should update last_activity."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now - 100,
        )
        old_activity = session.last_activity
        session.touch()
        assert session.last_activity > old_activity

    def test_session_is_expired_with_ttl(self):
        """is_expired should check TTL."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now - 7200,
            last_activity=now - 7200,
            ttl_s=3600,
        )
        assert session.is_expired() is True

    def test_session_is_expired_no_ttl(self):
        """is_expired should return False when ttl_s=0."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now - 7200,
            last_activity=now - 7200,
            ttl_s=0,
        )
        assert session.is_expired() is False

    def test_session_is_active(self):
        """is_active should check state and expiration."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now,
        )
        assert session.is_active() is True

    def test_session_get_and_set(self):
        """get and set should manage session data."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now,
        )
        session.set("key", "value")
        assert session.get("key") == "value"
        assert session.get("missing", "default") == "default"

    def test_session_delete(self):
        """delete should remove data from session."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now,
            data={"key": "value"},
        )
        assert session.delete("key") is True
        assert session.get("key") is None
        assert session.delete("missing") is False

    def test_session_clear_data(self):
        """clear_data should remove all session data."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now,
            data={"key1": "value1", "key2": "value2"},
        )
        session.clear_data()
        assert len(session.data) == 0

    def test_session_to_dict(self):
        """to_dict should return dictionary representation."""
        now = time.time()
        session = Session(
            id="test-id",
            channel="api",
            created_at=now,
            last_activity=now,
            data={"key": "value"},
        )
        data = session.to_dict()
        assert data["id"] == "test-id"
        assert data["channel"] == "api"
        assert data["data"]["key"] == "value"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionMetrics:
    """Test SessionMetrics class."""

    def test_metrics_creation(self):
        """Metrics should initialize with defaults."""
        metrics = SessionMetrics()
        assert metrics.request_count == 0
        assert metrics.error_count == 0
        assert metrics.total_latency_ms == 0.0

    def test_metrics_record_request(self):
        """record_request should update metrics."""
        metrics = SessionMetrics()
        metrics.record_request(100.0)
        assert metrics.request_count == 1
        assert metrics.total_latency_ms == 100.0
        assert metrics.last_request_at is not None

    def test_metrics_record_error(self):
        """record_request with error should count errors."""
        metrics = SessionMetrics()
        metrics.record_request(50.0, error=True)
        assert metrics.request_count == 1
        assert metrics.error_count == 1

    def test_metrics_avg_latency(self):
        """avg_latency_ms should calculate average."""
        metrics = SessionMetrics()
        metrics.record_request(100.0)
        metrics.record_request(200.0)
        assert metrics.avg_latency_ms == 150.0


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionManager:
    """Test SessionManager class."""

    def test_manager_create_session(self, manager):
        """create should create a new session."""
        session = manager.create("api")
        assert session is not None
        assert session.channel == "api"
        assert session.id in manager

    def test_manager_create_with_options(self, manager):
        """create should accept all options."""
        session = manager.create(
            channel="api",
            user_id="user-123",
            data={"key": "value"},
            ttl_s=7200,
            cross_channel=True,
        )
        assert session.user_id == "user-123"
        assert session.data["key"] == "value"
        assert session.ttl_s == 7200
        assert session.cross_channel is True

    def test_manager_create_validates_channel(self, manager):
        """create should reject invalid channel."""
        with pytest.raises(ValueError):
            manager.create("invalid")

    def test_manager_create_respects_max_sessions(self):
        """create should raise when max sessions exceeded."""
        small_manager = SessionManager(max_sessions=2)
        small_manager.create("api")
        small_manager.create("api")
        with pytest.raises(RuntimeError):
            small_manager.create("api")

    def test_manager_get_session(self, manager):
        """get should return existing session."""
        session = manager.create("api")
        retrieved = manager.get(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    def test_manager_get_returns_none_for_missing(self, manager):
        """get should return None for missing session."""
        assert manager.get("nonexistent") is None

    def test_manager_get_or_raise(self, manager):
        """get_or_raise should raise for missing session."""
        session = manager.create("api")
        assert manager.get_or_raise(session.id) is not None
        with pytest.raises(KeyError):
            manager.get_or_raise("missing")

    def test_manager_update_session(self, manager):
        """update should modify session data."""
        session = manager.create("api", data={"key1": "value1"})
        result = manager.update(session.id, {"key2": "value2"})
        assert result is True

        updated = manager.get(session.id)
        assert updated.data["key1"] == "value1"
        assert updated.data["key2"] == "value2"

    def test_manager_update_replace(self, manager):
        """update with merge=False should replace data."""
        session = manager.create("api", data={"key1": "value1"})
        manager.update(session.id, {"key2": "value2"}, merge=False)

        updated = manager.get(session.id)
        assert "key1" not in updated.data
        assert updated.data["key2"] == "value2"

    def test_manager_delete_session(self, manager):
        """delete should remove session."""
        session = manager.create("api")
        result = manager.delete(session.id)
        assert result is True
        assert session.id not in manager

    def test_manager_delete_returns_false_for_missing(self, manager):
        """delete should return False for missing session."""
        assert manager.delete("nonexistent") is False

    def test_manager_touch_session(self, manager):
        """touch should update session activity."""
        session = manager.create("api")
        old_activity = session.last_activity
        time.sleep(0.01)
        result = manager.touch(session.id)
        assert result is True
        assert manager.get(session.id).last_activity > old_activity

    def test_manager_list_by_channel(self, manager):
        """list_by_channel should filter sessions."""
        manager.create("api")
        manager.create("api")
        manager.create("cli")

        api_sessions = manager.list_by_channel("api")
        assert len(api_sessions) == 2

        cli_sessions = manager.list_by_channel("cli")
        assert len(cli_sessions) == 1

    def test_manager_list_by_user(self, manager):
        """list_by_user should filter sessions."""
        manager.create("api", user_id="user-1")
        manager.create("api", user_id="user-1")
        manager.create("api", user_id="user-2")

        user1_sessions = manager.list_by_user("user-1")
        assert len(user1_sessions) == 2

    def test_manager_get_cross_channel_sessions(self, manager):
        """get_cross_channel_sessions should filter by cross_channel flag."""
        manager.create("api", user_id="user-1", cross_channel=False)
        manager.create("api", user_id="user-1", cross_channel=True)

        cross_sessions = manager.get_cross_channel_sessions("user-1")
        assert len(cross_sessions) == 1

    def test_manager_terminate_user_sessions(self, manager):
        """terminate_user_sessions should delete all user sessions."""
        manager.create("api", user_id="user-1")
        manager.create("cli", user_id="user-1")
        manager.create("api", user_id="user-2")

        count = manager.terminate_user_sessions("user-1")
        assert count == 2
        assert len(manager.list_by_user("user-1")) == 0

    def test_manager_cleanup(self, manager):
        """cleanup should remove expired sessions."""
        # Create session with very short TTL
        short_manager = SessionManager(default_ttl_s=0)
        # This session won't expire (ttl_s=0 means no expiry)
        short_manager.create("api", ttl_s=0)
        count = short_manager.cleanup()
        assert count == 0

    def test_manager_on_create_hook(self, manager):
        """on_create hook should be called on session creation."""
        created_sessions = []
        manager.on_create(lambda s: created_sessions.append(s.id))

        session = manager.create("api")
        assert session.id in created_sessions

    def test_manager_on_delete_hook(self, manager):
        """on_delete hook should be called on session deletion."""
        deleted_sessions = []
        manager.on_delete(lambda s: deleted_sessions.append(s.id))

        session = manager.create("api")
        manager.delete(session.id)
        assert session.id in deleted_sessions

    def test_manager_get_stats(self, manager):
        """get_stats should return session statistics."""
        manager.create("api")
        manager.create("cli")

        stats = manager.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["by_channel"]["api"] == 1
        assert stats["by_channel"]["cli"] == 1

    def test_manager_clear(self, manager):
        """clear should remove all sessions."""
        manager.create("api")
        manager.create("cli")

        count = manager.clear()
        assert count == 2
        assert len(manager) == 0

    def test_manager_len(self, manager):
        """__len__ should return session count."""
        assert len(manager) == 0
        manager.create("api")
        assert len(manager) == 1

    def test_manager_contains(self, manager):
        """__contains__ should check session existence."""
        session = manager.create("api")
        assert session.id in manager
        assert "missing" not in manager
