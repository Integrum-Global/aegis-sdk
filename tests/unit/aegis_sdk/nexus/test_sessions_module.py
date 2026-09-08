"""
Tier 1: Unit Tests for Nexus Sessions Module.

Tests unified session management, storage backends, and cross-channel access.
"""

import asyncio
import time

import pytest

from aegis_sdk.nexus.sessions_module import (
    AffinityMode,
    DatabaseStorage,
    InMemoryStorage,
    SessionChannel,
    SessionContext,
    SessionManagerFactory,
    SessionMessage,
    SessionModuleState,
    UnifiedSession,
    UnifiedSessionsModule,
    WorkflowExecution,
)


@pytest.fixture
def module():
    """Create a fresh sessions module for each test."""
    return UnifiedSessionsModule(default_ttl_s=3600, max_sessions=100)


@pytest.fixture
def storage():
    """Create a fresh in-memory storage for each test."""
    return InMemoryStorage()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionChannel:
    """Test SessionChannel enum."""

    def test_channel_from_string(self):
        """from_string should convert strings to channels."""
        assert SessionChannel.from_string("api") == SessionChannel.API
        assert SessionChannel.from_string("API") == SessionChannel.API
        assert SessionChannel.from_string("cli") == SessionChannel.CLI
        assert SessionChannel.from_string("mcp") == SessionChannel.MCP

    def test_channel_from_string_aliases(self):
        """from_string should support aliases."""
        assert SessionChannel.from_string("rest") == SessionChannel.API
        assert SessionChannel.from_string("http") == SessionChannel.API
        assert SessionChannel.from_string("command") == SessionChannel.CLI
        assert SessionChannel.from_string("tool") == SessionChannel.MCP

    def test_channel_from_string_invalid(self):
        """from_string should raise on invalid channel."""
        with pytest.raises(ValueError):
            SessionChannel.from_string("invalid")

    def test_channel_str(self):
        """__str__ should return lowercase name."""
        assert str(SessionChannel.API) == "api"
        assert str(SessionChannel.CLI) == "cli"
        assert str(SessionChannel.MCP) == "mcp"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionMessage:
    """Test SessionMessage class."""

    def test_message_creation(self):
        """Message should be created with required fields."""
        msg = SessionMessage(
            id="msg-1",
            role="user",
            content="Hello!",
        )
        assert msg.id == "msg-1"
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.timestamp > 0

    def test_message_to_dict(self):
        """to_dict should return dictionary representation."""
        msg = SessionMessage(
            id="msg-1",
            role="user",
            content="Hello!",
            metadata={"key": "value"},
        )
        data = msg.to_dict()
        assert data["id"] == "msg-1"
        assert data["role"] == "user"
        assert data["metadata"]["key"] == "value"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowExecution:
    """Test WorkflowExecution class."""

    def test_execution_creation(self):
        """Execution should be created with required fields."""
        exec_record = WorkflowExecution(
            workflow_name="test-workflow",
            execution_id="exec-1",
            inputs={"value": 42},
        )
        assert exec_record.workflow_name == "test-workflow"
        assert exec_record.execution_id == "exec-1"
        assert exec_record.success is True

    def test_execution_duration_ms(self):
        """duration_ms should calculate duration."""
        now = time.time()
        exec_record = WorkflowExecution(
            workflow_name="test-workflow",
            execution_id="exec-1",
            started_at=now,
            completed_at=now + 1,  # 1 second later
        )
        assert exec_record.duration_ms == 1000.0

    def test_execution_to_dict(self):
        """to_dict should return dictionary representation."""
        exec_record = WorkflowExecution(
            workflow_name="test-workflow",
            execution_id="exec-1",
            inputs={"value": 42},
            outputs={"result": 84},
            success=True,
        )
        data = exec_record.to_dict()
        assert data["workflow_name"] == "test-workflow"
        assert data["inputs"]["value"] == 42
        assert data["success"] is True


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionContext:
    """Test SessionContext class."""

    def test_context_creation(self):
        """Context should be created with defaults."""
        ctx = SessionContext()
        assert ctx.user_id is None
        assert ctx.channel is None
        assert ctx.custom_data == {}

    def test_context_get_set(self):
        """get and set should manage custom data."""
        ctx = SessionContext()
        ctx.set("key", "value")
        assert ctx.get("key") == "value"
        assert ctx.get("missing", "default") == "default"

    def test_context_variables(self):
        """get_variable and set_variable should manage variables."""
        ctx = SessionContext()
        ctx.set_variable("count", 42)
        assert ctx.get_variable("count") == 42

    def test_context_to_dict(self):
        """to_dict should return dictionary representation."""
        ctx = SessionContext(
            user_id="user-123",
            channel=SessionChannel.API,
            custom_data={"key": "value"},
        )
        data = ctx.to_dict()
        assert data["user_id"] == "user-123"
        assert data["channel"] == "api"
        assert data["custom_data"]["key"] == "value"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestUnifiedSession:
    """Test UnifiedSession class."""

    def test_session_creation(self):
        """Session should be created with required fields."""
        session = UnifiedSession(
            id="session-1",
            user_id="user-123",
            channel=SessionChannel.API,
        )
        assert session.id == "session-1"
        assert session.user_id == "user-123"
        assert session.channel == SessionChannel.API
        assert session.state == SessionModuleState.ACTIVE

    def test_session_touch(self):
        """touch should update last_activity."""
        session = UnifiedSession(id="session-1")
        old_activity = session.last_activity
        time.sleep(0.01)
        session.touch()
        assert session.last_activity > old_activity

    def test_session_touch_with_channel(self):
        """touch should track active channels."""
        session = UnifiedSession(id="session-1")
        session.touch(SessionChannel.CLI)
        assert SessionChannel.CLI in session.active_channels

    def test_session_is_expired_with_ttl(self):
        """is_expired should check TTL."""
        session = UnifiedSession(
            id="session-1",
            last_activity=time.time() - 7200,
            ttl_s=3600,
        )
        assert session.is_expired() is True

    def test_session_is_expired_no_ttl(self):
        """is_expired should return False when ttl_s=0."""
        session = UnifiedSession(
            id="session-1",
            last_activity=time.time() - 7200,
            ttl_s=0,
        )
        assert session.is_expired() is False

    def test_session_is_active(self):
        """is_active should check state and expiration."""
        session = UnifiedSession(id="session-1")
        assert session.is_active() is True

    def test_session_get_set(self):
        """get and set should manage session data."""
        session = UnifiedSession(id="session-1")
        session.set("key", "value")
        assert session.get("key") == "value"
        assert session.get("missing", "default") == "default"

    def test_session_delete(self):
        """delete should remove data from session."""
        session = UnifiedSession(
            id="session-1",
            data={"key": "value"},
        )
        assert session.delete("key") is True
        assert session.get("key") is None
        assert session.delete("missing") is False

    def test_session_add_message(self):
        """add_message should add to message history."""
        session = UnifiedSession(id="session-1")
        msg = session.add_message("user", "Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert len(session.messages) == 1

    def test_session_add_workflow_execution(self):
        """add_workflow_execution should add to history."""
        session = UnifiedSession(id="session-1")
        exec_record = WorkflowExecution(
            workflow_name="test",
            execution_id="exec-1",
        )
        session.add_workflow_execution(exec_record)
        assert len(session.context.workflow_history) == 1

    def test_session_get_recent_messages(self):
        """get_recent_messages should return limited messages."""
        session = UnifiedSession(id="session-1")
        for i in range(20):
            session.add_message("user", f"Message {i}")

        recent = session.get_recent_messages(limit=10)
        assert len(recent) == 10
        assert recent[0].content == "Message 10"

    def test_session_clear_messages(self):
        """clear_messages should remove all messages."""
        session = UnifiedSession(id="session-1")
        session.add_message("user", "Hello!")
        session.add_message("assistant", "Hi!")

        count = session.clear_messages()
        assert count == 2
        assert len(session.messages) == 0

    def test_session_to_dict(self):
        """to_dict should return dictionary representation."""
        session = UnifiedSession(
            id="session-1",
            user_id="user-123",
            channel=SessionChannel.API,
            data={"key": "value"},
        )
        data = session.to_dict()
        assert data["id"] == "session-1"
        assert data["user_id"] == "user-123"
        assert data["channel"] == "api"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestInMemoryStorage:
    """Test InMemoryStorage class."""

    async def test_storage_save_and_load(self, storage):
        """save and load should work correctly."""
        session = UnifiedSession(id="session-1")
        await storage.save(session)

        loaded = await storage.load("session-1")
        assert loaded is not None
        assert loaded.id == "session-1"

    async def test_storage_load_missing(self, storage):
        """load should return None for missing session."""
        assert await storage.load("nonexistent") is None

    async def test_storage_delete(self, storage):
        """delete should remove session."""
        session = UnifiedSession(id="session-1")
        await storage.save(session)

        assert await storage.delete("session-1") is True
        assert await storage.load("session-1") is None

    async def test_storage_delete_missing(self, storage):
        """delete should return False for missing session."""
        assert await storage.delete("nonexistent") is False

    async def test_storage_list_all(self, storage):
        """list_all should return all session IDs."""
        await storage.save(UnifiedSession(id="session-1"))
        await storage.save(UnifiedSession(id="session-2"))

        ids = await storage.list_all()
        assert "session-1" in ids
        assert "session-2" in ids

    async def test_storage_clear(self, storage):
        """clear should remove all sessions."""
        await storage.save(UnifiedSession(id="session-1"))
        await storage.save(UnifiedSession(id="session-2"))

        count = await storage.clear()
        assert count == 2
        assert len(storage) == 0


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestDatabaseStorage:
    """Test DatabaseStorage class — async SQLAlchemy engine, real sqlite.

    Uses an in-memory `sqlite+aiosqlite://` database (StaticPool-backed so
    the whole test shares one connection) rather than a mock — this is the
    behavioral round-trip governance requires: the async engine actually
    opens, creates the table, and persists/reads a real row.
    """

    @pytest.fixture
    async def db_storage(self):
        """Create a fresh async DatabaseStorage backed by in-memory sqlite."""
        storage = DatabaseStorage(database_url="sqlite:///:memory:")
        yield storage
        await storage.aclose()

    async def test_bare_sqlite_url_translated_to_aiosqlite(self):
        """A bare `sqlite://` URL is translated to the async `+aiosqlite` driver."""
        storage = DatabaseStorage(database_url="sqlite:///:memory:")
        assert storage._database_url == "sqlite+aiosqlite:///:memory:"
        await storage.aclose()

    async def test_bare_postgresql_url_translated_to_asyncpg(self):
        """A bare `postgresql://` URL is translated to the async `+asyncpg` driver."""
        storage = DatabaseStorage(database_url="postgresql://user:pass@host/db")
        assert storage._database_url == "postgresql+asyncpg://user:pass@host/db"

    async def test_create_get_round_trip_through_async_engine(self, db_storage):
        """A session saved through the async engine is readable back by ID."""
        session = UnifiedSession(id="session-db-1", user_id="user-123")
        await db_storage.save(session)

        loaded = await db_storage.load("session-db-1")
        assert loaded is not None
        assert loaded.id == "session-db-1"
        assert loaded.user_id == "user-123"

    async def test_load_missing_returns_none(self, db_storage):
        """load() returns None for a session ID never saved."""
        assert await db_storage.load("nonexistent") is None

    async def test_save_update_persists_change(self, db_storage):
        """Saving an already-persisted session id updates the existing row."""
        session = UnifiedSession(id="session-db-2", user_id="user-a")
        await db_storage.save(session)

        session.user_id = "user-b"
        await db_storage.save(session)

        loaded = await db_storage.load("session-db-2")
        assert loaded.user_id == "user-b"

    async def test_delete_removes_row(self, db_storage):
        """delete() removes the row; a second load() returns None."""
        session = UnifiedSession(id="session-db-3")
        await db_storage.save(session)

        assert await db_storage.delete("session-db-3") is True
        assert await db_storage.load("session-db-3") is None

    async def test_delete_missing_returns_false(self, db_storage):
        """delete() on a never-saved id returns False."""
        assert await db_storage.delete("nonexistent") is False

    async def test_list_all_returns_saved_ids(self, db_storage):
        """list_all() enumerates every saved session id."""
        await db_storage.save(UnifiedSession(id="session-db-4"))
        await db_storage.save(UnifiedSession(id="session-db-5"))

        ids = await db_storage.list_all()
        assert "session-db-4" in ids
        assert "session-db-5" in ids

    async def test_clear_removes_all_rows(self, db_storage):
        """clear() deletes every row and reports the count removed."""
        await db_storage.save(UnifiedSession(id="session-db-6"))
        await db_storage.save(UnifiedSession(id="session-db-7"))

        count = await db_storage.clear()
        assert count == 2
        assert await db_storage.list_all() == []

    async def test_unified_sessions_module_round_trip_through_database_storage(self):
        """UnifiedSessionsModule create->get round-trips through the async DB engine."""
        storage = DatabaseStorage(database_url="sqlite:///:memory:")
        module = UnifiedSessionsModule(storage=storage)
        try:
            session = await module.create(user_id="user-123", channel="api")
            retrieved = await module.get(session.id)
            assert retrieved is not None
            assert retrieved.id == session.id
            assert retrieved.user_id == "user-123"
        finally:
            await storage.aclose()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestUnifiedSessionsModule:
    """Test UnifiedSessionsModule class."""

    async def test_module_create_session(self, module):
        """create should create a new session."""
        session = await module.create(channel="api")
        assert session is not None
        assert session.channel == SessionChannel.API
        assert await module.contains(session.id)

    async def test_module_create_with_options(self, module):
        """create should accept all options."""
        session = await module.create(
            user_id="user-123",
            channel="api",
            data={"key": "value"},
            ttl_s=7200,
            metadata={"source": "test"},
            affinity_key="sticky-1",
        )
        assert session.user_id == "user-123"
        assert session.data["key"] == "value"
        assert session.ttl_s == 7200
        assert session.affinity_key == "sticky-1"

    async def test_module_create_validates_channel(self, module):
        """create should reject invalid channel."""
        with pytest.raises(ValueError):
            await module.create(channel="invalid")

    async def test_module_create_respects_max_sessions(self):
        """create should raise when max sessions exceeded."""
        small_module = UnifiedSessionsModule(max_sessions=2)
        await small_module.create(channel="api")
        await small_module.create(channel="api")
        with pytest.raises(RuntimeError):
            await small_module.create(channel="api")

    async def test_module_get_session(self, module):
        """get should return existing session."""
        session = await module.create(channel="api")
        retrieved = await module.get(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    async def test_module_get_returns_none_for_missing(self, module):
        """get should return None for missing session."""
        assert await module.get("nonexistent") is None

    async def test_module_get_or_create_existing(self, module):
        """get_or_create should return existing session."""
        session = await module.create(channel="api")
        retrieved = await module.get_or_create(session_id=session.id)
        assert retrieved.id == session.id

    async def test_module_get_or_create_new(self, module):
        """get_or_create should create new session if not found."""
        session = await module.get_or_create(user_id="user-123", channel="api")
        assert session is not None
        assert session.user_id == "user-123"

    async def test_module_list_all(self, module):
        """list should return all sessions."""
        await module.create(channel="api")
        await module.create(channel="cli")

        sessions = await module.list()
        assert len(sessions) == 2

    async def test_module_list_by_user(self, module):
        """list should filter by user."""
        await module.create(user_id="user-1", channel="api")
        await module.create(user_id="user-1", channel="cli")
        await module.create(user_id="user-2", channel="api")

        user1_sessions = await module.list(user_id="user-1")
        assert len(user1_sessions) == 2

    async def test_module_list_by_channel(self, module):
        """list should filter by channel."""
        await module.create(channel="api")
        await module.create(channel="api")
        await module.create(channel="cli")

        api_sessions = await module.list(channel="api")
        assert len(api_sessions) == 2

    async def test_module_update_session(self, module):
        """update should modify session data."""
        session = await module.create(channel="api", data={"key1": "value1"})
        result = await module.update(session.id, {"key2": "value2"})
        assert result is True

        updated = await module.get(session.id)
        assert updated.data["key1"] == "value1"
        assert updated.data["key2"] == "value2"

    async def test_module_update_replace(self, module):
        """update with merge=False should replace data."""
        session = await module.create(channel="api", data={"key1": "value1"})
        await module.update(session.id, {"key2": "value2"}, merge=False)

        updated = await module.get(session.id)
        assert "key1" not in updated.data
        assert updated.data["key2"] == "value2"

    async def test_module_delete_session(self, module):
        """delete should remove session."""
        session = await module.create(channel="api")
        result = await module.delete(session.id)
        assert result is True
        assert not await module.contains(session.id)

    async def test_module_delete_returns_false_for_missing(self, module):
        """delete should return False for missing session."""
        assert await module.delete("nonexistent") is False

    async def test_module_add_message(self, module):
        """add_message should add to session history."""
        session = await module.create(channel="api")
        msg = await module.add_message(session.id, "user", "Hello!")

        assert msg is not None
        assert msg.role == "user"
        assert msg.content == "Hello!"

    async def test_module_add_message_missing_session(self, module):
        """add_message should return None for missing session."""
        result = await module.add_message("nonexistent", "user", "Hello!")
        assert result is None

    async def test_module_add_workflow_execution(self, module):
        """add_workflow_execution should add to session history."""
        session = await module.create(channel="api")
        result = await module.add_workflow_execution(
            session.id,
            workflow_name="test-workflow",
            execution_id="exec-1",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        assert result is True
        updated = await module.get(session.id)
        assert len(updated.context.workflow_history) == 1

    async def test_module_get_by_affinity(self, module):
        """get_by_affinity should find session by affinity key."""
        session = await module.create(channel="api", affinity_key="sticky-1")
        found = await module.get_by_affinity("sticky-1")
        assert found is not None
        assert found.id == session.id

    async def test_module_create_reaps_expired_session_without_deadlock(self):
        """Regression: create() -> _cleanup_expired_unlocked() -> _delete_unlocked()
        must not re-acquire self._lock. asyncio.Lock is NOT reentrant (unlike the
        threading.RLock this replaced) — if a nested call path acquired the lock
        twice on the same task, this test hangs forever instead of failing fast.
        cleanup_interval_s=0 forces the reap-on-create path to actually run.
        """
        module = UnifiedSessionsModule(default_ttl_s=1, cleanup_interval_s=0)
        expiring = await module.create(channel="api")
        await asyncio.sleep(1.1)

        # A hard timeout converts a reentrancy deadlock into a fast failure
        # instead of hanging the whole CI job.
        created = await asyncio.wait_for(module.create(channel="api"), timeout=5)

        assert created is not None
        assert not await module.contains(expiring.id), "expired session should be reaped"
        assert await module.contains(created.id)

    async def test_module_touch(self, module):
        """touch should update session activity."""
        session = await module.create(channel="api")
        old_activity = session.last_activity
        time.sleep(0.01)
        result = await module.touch(session.id)
        assert result is True
        updated = await module.get(session.id)
        assert updated.last_activity > old_activity

    async def test_module_on_create_hook(self, module):
        """on_create hook should be called on session creation."""
        created_sessions = []
        module.on_create(lambda s: created_sessions.append(s.id))

        session = await module.create(channel="api")
        assert session.id in created_sessions

    async def test_module_on_delete_hook(self, module):
        """on_delete hook should be called on session deletion."""
        deleted_sessions = []
        module.on_delete(lambda s: deleted_sessions.append(s.id))

        session = await module.create(channel="api")
        await module.delete(session.id)
        assert session.id in deleted_sessions

    async def test_module_get_stats(self, module):
        """get_stats should return session statistics."""
        await module.create(channel="api")
        await module.create(channel="cli")

        stats = await module.get_stats()
        assert stats["total_sessions"] == 2

    async def test_module_clear(self, module):
        """clear should remove all sessions."""
        await module.create(channel="api")
        await module.create(channel="cli")

        count = await module.clear()
        assert count == 2
        assert await module.size() == 0

    async def test_module_size(self, module):
        """size() should return session count (async replacement for __len__)."""
        assert await module.size() == 0
        await module.create(channel="api")
        assert await module.size() == 1

    async def test_module_contains(self, module):
        """contains() should check session existence (async replacement for __contains__)."""
        session = await module.create(channel="api")
        assert await module.contains(session.id)
        assert not await module.contains("missing")


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionManagerFactory:
    """Test SessionManagerFactory class."""

    def test_factory_create_memory(self):
        """create should create InMemory backend."""
        module = SessionManagerFactory.create("memory")
        assert module is not None
        assert isinstance(module, UnifiedSessionsModule)

    def test_factory_create_inmemory(self):
        """create should support 'inmemory' alias."""
        module = SessionManagerFactory.create("inmemory")
        assert module is not None

    async def test_factory_create_with_options(self):
        """create should pass options to module."""
        module = SessionManagerFactory.create(
            "memory",
            default_ttl_s=7200,
            max_sessions=500,
        )
        stats = await module.get_stats()
        assert stats["default_ttl_s"] == 7200
        assert stats["max_sessions"] == 500

    def test_factory_create_invalid_backend(self):
        """create should raise on invalid backend."""
        with pytest.raises(ValueError):
            SessionManagerFactory.create("invalid")


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestAffinityMode:
    """Test AffinityMode enum."""

    def test_affinity_modes_exist(self):
        """All affinity modes should exist."""
        assert AffinityMode.NONE is not None
        assert AffinityMode.CHANNEL is not None
        assert AffinityMode.USER is not None
        assert AffinityMode.STICKY is not None

    def test_affinity_str(self):
        """__str__ should return lowercase name."""
        assert str(AffinityMode.NONE) == "none"
        assert str(AffinityMode.STICKY) == "sticky"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionModuleState:
    """Test SessionModuleState enum."""

    def test_states_exist(self):
        """All session states should exist."""
        assert SessionModuleState.ACTIVE is not None
        assert SessionModuleState.IDLE is not None
        assert SessionModuleState.EXPIRED is not None
        assert SessionModuleState.TERMINATED is not None

    def test_state_str(self):
        """__str__ should return lowercase name."""
        assert str(SessionModuleState.ACTIVE) == "active"
        assert str(SessionModuleState.EXPIRED) == "expired"
