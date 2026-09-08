"""Unified Sessions Module for Nexus v1.1 - Cross-channel session management.

This module provides enhanced session management capabilities including:
- Unified sessions across API/CLI/MCP channels
- Pluggable storage backends (InMemory, Redis, Database)
- Session affinity (sticky sessions)
- Automatic session lifecycle management
- Workflow execution history tracking

Example:
    >>> from aegis_sdk.nexus import UnifiedSessionsModule, SessionManager
    >>>
    >>> # Create module with InMemory backend (default)
    >>> module = UnifiedSessionsModule()
    >>>
    >>> # Or use the factory to get a specific backend
    >>> manager = SessionManager.create("redis", redis_url="redis://localhost")
    >>>
    >>> # Create a session (all storage-backed operations are async-first)
    >>> session = await module.create(user_id="user-123", channel="api")
    >>>
    >>> # Add message to session
    >>> await module.add_message(session.id, role="user", content="Hello!")
"""

from __future__ import annotations

import abc
import asyncio
import builtins
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class SessionModuleState(Enum):
    """Session lifecycle states."""

    ACTIVE = auto()
    IDLE = auto()
    EXPIRED = auto()
    TERMINATED = auto()

    def __str__(self) -> str:
        """Return lowercase state name."""
        return self.name.lower()


class SessionChannel(Enum):
    """Session channel types."""

    API = auto()
    CLI = auto()
    MCP = auto()

    def __str__(self) -> str:
        """Return lowercase channel name."""
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> SessionChannel:
        """Convert string to SessionChannel.

        Args:
            value: String representation (case-insensitive).

        Returns:
            Corresponding SessionChannel enum value.

        Raises:
            ValueError: If the string does not match any channel.
        """
        mapping = {
            "api": cls.API,
            "rest": cls.API,
            "http": cls.API,
            "cli": cls.CLI,
            "command": cls.CLI,
            "terminal": cls.CLI,
            "mcp": cls.MCP,
            "model": cls.MCP,
            "tool": cls.MCP,
        }
        normalized = value.lower().strip()
        if normalized not in mapping:
            valid = ", ".join(sorted({"api", "cli", "mcp"}))
            raise ValueError(f"Invalid channel: '{value}'. Valid values: {valid}")
        return mapping[normalized]


class AffinityMode(Enum):
    """Session affinity modes."""

    NONE = auto()  # No affinity - sessions are independent
    CHANNEL = auto()  # Affinity per channel
    USER = auto()  # Affinity per user (across channels)
    STICKY = auto()  # Sticky sessions to specific server/instance

    def __str__(self) -> str:
        """Return lowercase affinity name."""
        return self.name.lower()


@dataclass
class SessionMessage:
    """Message in session history.

    Attributes:
        id: Unique message identifier.
        role: Message role (user, assistant, system).
        content: Message content.
        timestamp: Message timestamp.
        metadata: Additional message metadata.
    """

    id: str
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowExecution:
    """Record of a workflow execution in session.

    Attributes:
        workflow_name: Name of executed workflow.
        execution_id: Unique execution identifier.
        inputs: Workflow inputs.
        outputs: Workflow outputs.
        started_at: Execution start time.
        completed_at: Execution completion time.
        success: Whether execution succeeded.
        error: Error message if failed.
    """

    workflow_name: str
    execution_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: Any = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    success: bool = True
    error: str | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get execution duration in milliseconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert execution to dictionary."""
        return {
            "workflow_name": self.workflow_name,
            "execution_id": self.execution_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class SessionContext:
    """Context data accessible in workflow handlers.

    Attributes:
        user_id: User identifier.
        channel: Session channel.
        workflow_history: List of workflow executions.
        custom_data: Custom session data.
        variables: Session variables.
    """

    user_id: str | None = None
    channel: SessionChannel | None = None
    workflow_history: list[WorkflowExecution] = field(default_factory=list)
    custom_data: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom data value."""
        return self.custom_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a custom data value."""
        self.custom_data[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a session variable."""
        return self.variables.get(key, default)

    def set_variable(self, key: str, value: Any) -> None:
        """Set a session variable."""
        self.variables[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "user_id": self.user_id,
            "channel": str(self.channel) if self.channel else None,
            "workflow_history": [w.to_dict() for w in self.workflow_history],
            "custom_data": self.custom_data,
            "variables": self.variables,
        }


@dataclass
class UnifiedSession:
    """Unified session across API/CLI/MCP channels.

    Attributes:
        id: Unique session identifier.
        user_id: Associated user identifier.
        channel: Primary channel where session was created.
        created_at: Session creation timestamp.
        last_activity: Last activity timestamp.
        state: Current session state.
        ttl_s: Session time-to-live in seconds (0 = no expiry).
        data: General session data.
        context: Session context for workflow handlers.
        messages: Message history.
        active_channels: Channels that have accessed this session.
        metadata: Additional session metadata.
        affinity_key: Key for sticky session routing.
    """

    id: str
    user_id: str | None = None
    channel: SessionChannel | None = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    state: SessionModuleState = SessionModuleState.ACTIVE
    ttl_s: int = 1800  # 30 minutes default
    data: dict[str, Any] = field(default_factory=dict)
    context: SessionContext = field(default_factory=SessionContext)
    messages: list[SessionMessage] = field(default_factory=list)
    active_channels: builtins.set[SessionChannel] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    affinity_key: str | None = None

    def __post_init__(self):
        """Initialize session context."""
        if self.channel:
            self.active_channels.add(self.channel)
            self.context.channel = self.channel
        if self.user_id:
            self.context.user_id = self.user_id

    def touch(self, channel: SessionChannel | None = None) -> None:
        """Update last activity timestamp.

        Args:
            channel: Channel that triggered activity.
        """
        self.last_activity = time.time()
        if self.state == SessionModuleState.IDLE:
            self.state = SessionModuleState.ACTIVE
        if channel:
            self.active_channels.add(channel)

    def is_expired(self) -> bool:
        """Check if session has expired.

        Returns:
            True if session is expired based on TTL.
        """
        if self.ttl_s == 0:
            return False
        return (time.time() - self.last_activity) > self.ttl_s

    def is_active(self) -> bool:
        """Check if session is active.

        Returns:
            True if session is active and not expired.
        """
        return self.state == SessionModuleState.ACTIVE and not self.is_expired()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from session data.

        Args:
            key: Data key.
            default: Default value if key not found.

        Returns:
            Value or default.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in session data.

        Args:
            key: Data key.
            value: Value to store.
        """
        self.data[key] = value
        self.touch()

    def delete(self, key: str) -> bool:
        """Delete a value from session data.

        Args:
            key: Data key.

        Returns:
            True if key was deleted.
        """
        if key in self.data:
            del self.data[key]
            self.touch()
            return True
        return False

    def add_message(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionMessage:
        """Add a message to session history.

        Args:
            role: Message role.
            content: Message content.
            metadata: Additional metadata.

        Returns:
            Created SessionMessage.
        """
        message = SessionMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(message)
        self.touch()
        return message

    def add_workflow_execution(self, execution: WorkflowExecution) -> None:
        """Add a workflow execution to history.

        Args:
            execution: WorkflowExecution to add.
        """
        self.context.workflow_history.append(execution)
        self.touch()

    def get_recent_messages(self, limit: int = 10) -> list[SessionMessage]:
        """Get recent messages.

        Args:
            limit: Maximum number of messages.

        Returns:
            List of recent messages.
        """
        return self.messages[-limit:]

    def clear_messages(self) -> int:
        """Clear message history.

        Returns:
            Number of messages cleared.
        """
        count = len(self.messages)
        self.messages.clear()
        self.touch()
        return count

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel": str(self.channel) if self.channel else None,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "state": str(self.state),
            "ttl_s": self.ttl_s,
            "data": self.data,
            "context": self.context.to_dict(),
            "messages_count": len(self.messages),
            "active_channels": [str(c) for c in self.active_channels],
            "metadata": self.metadata,
            "affinity_key": self.affinity_key,
            "is_expired": self.is_expired(),
            "is_active": self.is_active(),
        }


class SessionStorageBackend(abc.ABC):
    """Abstract base class for session storage backends.

    All methods are async-first — every backend (in-memory, Redis, database)
    implements the same async surface so `UnifiedSessionsModule` can await
    any backend polymorphically without a sync-blocking shim.
    """

    @abc.abstractmethod
    async def save(self, session: UnifiedSession) -> None:
        """Save a session.

        Args:
            session: Session to save.
        """
        pass

    @abc.abstractmethod
    async def load(self, session_id: str) -> UnifiedSession | None:
        """Load a session.

        Args:
            session_id: Session ID.

        Returns:
            UnifiedSession or None.
        """
        pass

    @abc.abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID.

        Returns:
            True if deleted.
        """
        pass

    @abc.abstractmethod
    async def list_all(self) -> list[str]:
        """List all session IDs.

        Returns:
            List of session IDs.
        """
        pass

    @abc.abstractmethod
    async def clear(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared.
        """
        pass


class InMemoryStorage(SessionStorageBackend):
    """In-memory session storage for development/testing.

    Thread-safe storage using a dictionary. Methods are `async def` to
    satisfy the `SessionStorageBackend` async contract, but the bodies are
    pure in-process dict operations with no `await` inside the critical
    section — so holding the (sync) `threading.RLock` here never blocks
    the event loop.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._sessions: dict[str, UnifiedSession] = {}
        self._lock = threading.RLock()

    async def save(self, session: UnifiedSession) -> None:
        """Save a session."""
        with self._lock:
            self._sessions[session.id] = session

    async def load(self, session_id: str) -> UnifiedSession | None:
        """Load a session."""
        with self._lock:
            return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def list_all(self) -> list[str]:
        """List all session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    async def clear(self) -> int:
        """Clear all sessions."""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def __len__(self) -> int:
        """Get number of sessions (sync — pure in-process dict length)."""
        return len(self._sessions)


class RedisStorage(SessionStorageBackend):
    """Redis-based session storage for production.

    Requires redis-py package. Uses `redis.asyncio` — the client is
    non-blocking so `UnifiedSessionsModule` never blocks the event loop
    waiting on a Redis round-trip.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "nexus:session:",
        ttl_s: int = 3600,
    ):
        """Initialize Redis storage.

        Args:
            redis_url: Redis connection URL.
            prefix: Key prefix for sessions.
            ttl_s: Default TTL for keys.
        """
        self._redis_url = redis_url
        self._prefix = prefix
        self._ttl_s = ttl_s
        self._client = None

    def _get_client(self):
        """Get or create the async Redis client.

        Constructing `redis.asyncio.Redis.from_url(...)` does not itself
        perform any I/O — the connection pool connects lazily on first
        command — so this helper stays a plain (non-async) method.
        """
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(self._redis_url)
            except ImportError:
                raise ImportError("redis package required for RedisStorage")
        return self._client

    def _serialize(self, session: UnifiedSession) -> str:
        """Serialize session to JSON."""
        import json

        data = session.to_dict()
        # Store full session data for reconstruction
        data["_messages"] = [m.to_dict() for m in session.messages]
        data["_workflow_history"] = [w.to_dict() for w in session.context.workflow_history]
        return json.dumps(data)

    def _deserialize(self, data: str) -> UnifiedSession:
        """Deserialize session from JSON."""
        import json

        d = json.loads(data)

        # Reconstruct messages
        messages = []
        for m in d.get("_messages", []):
            messages.append(
                SessionMessage(
                    id=m["id"],
                    role=m["role"],
                    content=m["content"],
                    timestamp=m["timestamp"],
                    metadata=m.get("metadata", {}),
                )
            )

        # Reconstruct workflow history
        workflow_history = []
        for w in d.get("_workflow_history", []):
            workflow_history.append(
                WorkflowExecution(
                    workflow_name=w["workflow_name"],
                    execution_id=w["execution_id"],
                    inputs=w.get("inputs", {}),
                    outputs=w.get("outputs"),
                    started_at=w.get("started_at", time.time()),
                    completed_at=w.get("completed_at"),
                    success=w.get("success", True),
                    error=w.get("error"),
                )
            )

        # Reconstruct context
        ctx = d.get("context", {})
        context = SessionContext(
            user_id=ctx.get("user_id"),
            channel=SessionChannel.from_string(ctx["channel"]) if ctx.get("channel") else None,
            workflow_history=workflow_history,
            custom_data=ctx.get("custom_data", {}),
            variables=ctx.get("variables", {}),
        )

        # Reconstruct session
        channel = None
        if d.get("channel"):
            channel = SessionChannel.from_string(d["channel"])

        active_channels = set()
        for c in d.get("active_channels", []):
            try:
                active_channels.add(SessionChannel.from_string(c))
            except ValueError:
                pass

        return UnifiedSession(
            id=d["id"],
            user_id=d.get("user_id"),
            channel=channel,
            created_at=d.get("created_at", time.time()),
            last_activity=d.get("last_activity", time.time()),
            state=SessionModuleState[d.get("state", "active").upper()],
            ttl_s=d.get("ttl_s", 1800),
            data=d.get("data", {}),
            context=context,
            messages=messages,
            active_channels=active_channels,
            metadata=d.get("metadata", {}),
            affinity_key=d.get("affinity_key"),
        )

    async def save(self, session: UnifiedSession) -> None:
        """Save a session to Redis."""
        client = self._get_client()
        key = f"{self._prefix}{session.id}"
        data = self._serialize(session)
        ttl = session.ttl_s if session.ttl_s > 0 else self._ttl_s
        await client.setex(key, ttl, data)

    async def load(self, session_id: str) -> UnifiedSession | None:
        """Load a session from Redis."""
        client = self._get_client()
        key = f"{self._prefix}{session_id}"
        data = await client.get(key)
        if data:
            return self._deserialize(data.decode("utf-8"))
        return None

    async def delete(self, session_id: str) -> bool:
        """Delete a session from Redis."""
        client = self._get_client()
        key = f"{self._prefix}{session_id}"
        return await client.delete(key) > 0

    async def list_all(self) -> list[str]:
        """List all session IDs in Redis."""
        client = self._get_client()
        keys = await client.keys(f"{self._prefix}*")
        return [k.decode("utf-8").replace(self._prefix, "") for k in keys]

    async def clear(self) -> int:
        """Clear all sessions from Redis."""
        client = self._get_client()
        keys = await client.keys(f"{self._prefix}*")
        if keys:
            return await client.delete(*keys)
        return 0


def _to_async_driver_url(database_url: str) -> str:
    """Translate a bare sync DB URL scheme to its async-driver equivalent.

    DataFlow/async-first eradication: callers may pass the conventional bare `postgresql://` /
    `sqlite://` scheme; this helper rewrites it to the async-capable
    driver this module actually uses (`asyncpg` / `aiosqlite`, both
    already declared dependencies of this project) so `create_async_engine`
    never receives a scheme it cannot drive. URLs that already name an
    async (or any other) driver are returned unchanged.

    Args:
        database_url: The raw database URL as supplied by the caller.

    Returns:
        A URL guaranteed to use an async-capable driver for the
        postgres/sqlite families; any other scheme passes through as-is.
    """
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url[len("postgresql://") :]
    if database_url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + database_url[len("sqlite://") :]
    return database_url


class DatabaseStorage(SessionStorageBackend):
    """Database-based session storage using async SQLAlchemy.

    Requires the `sqlalchemy[asyncio]` package (plus the async DBAPI driver
    for the target dialect — `asyncpg` for PostgreSQL, `aiosqlite` for
    SQLite; both are already project dependencies). Async-first per / zero-tolerance Rule 4 — this backend never opens a
    sync SQLAlchemy engine or session, and never blocks the event loop.
    """

    def __init__(
        self,
        database_url: str = "sqlite+aiosqlite:///sessions.db",
        table_name: str = "nexus_sessions",
    ):
        """Initialize database storage.

        Args:
            database_url: SQLAlchemy database URL. Bare `postgresql://` /
                `sqlite://` schemes are translated to their async-driver
                equivalent (`+asyncpg` / `+aiosqlite`) automatically.
            table_name: Table name for sessions.
        """
        self._database_url = _to_async_driver_url(database_url)
        self._table_name = table_name
        self._engine = None
        self._session_factory = None
        self._SessionModel = None
        self._initialized = False
        # Guards the lazy _init_db() critical section — two concurrent
        # coroutines racing the first CRUD call must not each build a
        # separate engine/table-create.
        self._init_lock = asyncio.Lock()

    async def _init_db(self) -> None:
        """Initialize database tables (idempotent, concurrency-safe)."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            try:
                from sqlalchemy import (
                    Column,
                    Float,
                    Integer,
                    String,
                    Text,
                )
                from sqlalchemy.ext.asyncio import (
                    async_sessionmaker,
                    create_async_engine,
                )
                from sqlalchemy.orm import declarative_base
            except ImportError:
                raise ImportError("sqlalchemy[asyncio] package required for DatabaseStorage")

            engine_kwargs: dict[str, Any] = {}
            if "sqlite" in self._database_url and ":memory:" in self._database_url:
                # In-memory SQLite: each new connection gets an isolated
                # database unless pinned to a single shared connection.
                from sqlalchemy.pool import StaticPool

                engine_kwargs["poolclass"] = StaticPool
                engine_kwargs["connect_args"] = {"check_same_thread": False}

            self._engine = create_async_engine(self._database_url, **engine_kwargs)
            Base = declarative_base()

            class SessionModel(Base):
                __tablename__ = self._table_name

                id = Column(String(36), primary_key=True)
                user_id = Column(String(128), nullable=True, index=True)
                channel = Column(String(16), nullable=True)
                created_at = Column(Float, nullable=False)
                last_activity = Column(Float, nullable=False)
                state = Column(String(16), nullable=False)
                ttl_s = Column(Integer, nullable=False)
                data = Column(Text, nullable=False)  # JSON

            self._SessionModel = SessionModel
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # expire_on_commit=False: rows returned by CRUD methods below
            # stay readable after the session closes without triggering a
            # lazy (sync-only) refresh load.
            self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
            self._initialized = True

    async def aclose(self) -> None:
        """Dispose the async engine and its connection pool.

        Per, the engine is an application-level
        singleton — callers MUST dispose it on shutdown/teardown rather
        than letting connections leak until GC.
        """
        if self._engine is not None:
            await self._engine.dispose()

    def _serialize(self, session: UnifiedSession) -> str:
        """Serialize session to JSON."""
        import json

        data = session.to_dict()
        data["_messages"] = [m.to_dict() for m in session.messages]
        data["_workflow_history"] = [w.to_dict() for w in session.context.workflow_history]
        return json.dumps(data)

    def _deserialize(self, data: str, model) -> UnifiedSession:
        """Deserialize session from database model."""
        import json

        d = json.loads(data)

        # Reconstruct messages
        messages = []
        for m in d.get("_messages", []):
            messages.append(
                SessionMessage(
                    id=m["id"],
                    role=m["role"],
                    content=m["content"],
                    timestamp=m["timestamp"],
                    metadata=m.get("metadata", {}),
                )
            )

        # Reconstruct workflow history
        workflow_history = []
        for w in d.get("_workflow_history", []):
            workflow_history.append(
                WorkflowExecution(
                    workflow_name=w["workflow_name"],
                    execution_id=w["execution_id"],
                    inputs=w.get("inputs", {}),
                    outputs=w.get("outputs"),
                    started_at=w.get("started_at", time.time()),
                    completed_at=w.get("completed_at"),
                    success=w.get("success", True),
                    error=w.get("error"),
                )
            )

        # Reconstruct context
        ctx = d.get("context", {})
        context = SessionContext(
            user_id=ctx.get("user_id"),
            channel=SessionChannel.from_string(ctx["channel"]) if ctx.get("channel") else None,
            workflow_history=workflow_history,
            custom_data=ctx.get("custom_data", {}),
            variables=ctx.get("variables", {}),
        )

        channel = None
        if model.channel:
            channel = SessionChannel.from_string(model.channel)

        active_channels = set()
        for c in d.get("active_channels", []):
            try:
                active_channels.add(SessionChannel.from_string(c))
            except ValueError:
                pass

        return UnifiedSession(
            id=model.id,
            user_id=model.user_id,
            channel=channel,
            created_at=model.created_at,
            last_activity=model.last_activity,
            state=SessionModuleState[model.state.upper()],
            ttl_s=model.ttl_s,
            data=d.get("data", {}),
            context=context,
            messages=messages,
            active_channels=active_channels,
            metadata=d.get("metadata", {}),
            affinity_key=d.get("affinity_key"),
        )

    async def save(self, session: UnifiedSession) -> None:
        """Save a session to database."""
        from sqlalchemy import select

        await self._init_db()
        async with self._session_factory() as db:
            existing = (
                await db.execute(select(self._SessionModel).filter_by(id=session.id))
            ).scalar_one_or_none()
            if existing:
                existing.user_id = session.user_id
                existing.channel = str(session.channel) if session.channel else None
                existing.last_activity = session.last_activity
                existing.state = str(session.state)
                existing.ttl_s = session.ttl_s
                existing.data = self._serialize(session)
            else:
                model = self._SessionModel(
                    id=session.id,
                    user_id=session.user_id,
                    channel=str(session.channel) if session.channel else None,
                    created_at=session.created_at,
                    last_activity=session.last_activity,
                    state=str(session.state),
                    ttl_s=session.ttl_s,
                    data=self._serialize(session),
                )
                db.add(model)
            await db.commit()

    async def load(self, session_id: str) -> UnifiedSession | None:
        """Load a session from database."""
        from sqlalchemy import select

        await self._init_db()
        async with self._session_factory() as db:
            model = (
                await db.execute(select(self._SessionModel).filter_by(id=session_id))
            ).scalar_one_or_none()
            if model:
                return self._deserialize(model.data, model)
            return None

    async def delete(self, session_id: str) -> bool:
        """Delete a session from database."""
        from sqlalchemy import delete as sa_delete

        await self._init_db()
        async with self._session_factory() as db:
            result = await db.execute(sa_delete(self._SessionModel).filter_by(id=session_id))
            await db.commit()
            return result.rowcount > 0

    async def list_all(self) -> list[str]:
        """List all session IDs in database."""
        from sqlalchemy import select

        await self._init_db()
        async with self._session_factory() as db:
            results = await db.execute(select(self._SessionModel.id))
            return [r[0] for r in results.all()]

    async def clear(self) -> int:
        """Clear all sessions from database."""
        from sqlalchemy import delete as sa_delete

        await self._init_db()
        async with self._session_factory() as db:
            result = await db.execute(sa_delete(self._SessionModel))
            await db.commit()
            return result.rowcount


class UnifiedSessionsModule:
    """Unified sessions module for cross-channel session management.

    Provides session creation, retrieval, updates, and lifecycle management
    with pluggable storage backends.

    Example:
        >>> module = UnifiedSessionsModule()
        >>> session = await module.create(user_id="user-123", channel="api")
        >>> await module.update(session.id, {"key": "value"})
        >>> await module.add_message(session.id, role="user", content="Hello!")

    Note:
        Every storage-backed method here is `async def` — `size()` and
        `contains()` replace the old `__len__`/`__contains__` dunders
        because Python's `len()`/`in` protocols require a synchronous
        return, which an async-first storage backend cannot provide
        without blocking the event loop.
    """

    def __init__(
        self,
        storage: SessionStorageBackend | None = None,
        default_ttl_s: int = 1800,
        max_sessions: int = 10000,
        affinity_mode: AffinityMode = AffinityMode.USER,
        cleanup_interval_s: int = 300,
    ):
        """Initialize sessions module.

        Args:
            storage: Storage backend (default: InMemoryStorage).
            default_ttl_s: Default session TTL (30 minutes).
            max_sessions: Maximum number of sessions.
            affinity_mode: Session affinity mode.
            cleanup_interval_s: Cleanup interval in seconds.
        """
        self._storage = storage if storage is not None else InMemoryStorage()
        self._default_ttl_s = default_ttl_s
        self._max_sessions = max_sessions
        self._affinity_mode = affinity_mode
        self._cleanup_interval_s = cleanup_interval_s
        # asyncio.Lock (not threading.RLock): every method below holds this
        # lock across `await` points, and a threading lock held across an
        # `await` can deadlock the whole event loop (the suspended holder
        # never gets to run again because the loop is blocked waiting on
        # a lock acquire that isn't itself awaitable). NOTE: asyncio.Lock is
        # NOT reentrant — internal calls made while the lock is already
        # held MUST use the `_unlocked` helper variants below, never the
        # public locking method, or the second acquire deadlocks.
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()

        # Indexes for fast lookup
        self._user_sessions: dict[str, set[str]] = {}
        self._channel_sessions: dict[SessionChannel, set[str]] = {}
        self._affinity_sessions: dict[str, str] = {}

        # Hooks
        self._on_create_hooks: list[Callable[[UnifiedSession], None]] = []
        self._on_delete_hooks: list[Callable[[UnifiedSession], None]] = []
        self._on_expire_hooks: list[Callable[[UnifiedSession], None]] = []

    async def create(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        data: dict[str, Any] | None = None,
        ttl_s: int | None = None,
        metadata: dict[str, Any] | None = None,
        affinity_key: str | None = None,
    ) -> UnifiedSession:
        """Create a new session.

        Args:
            user_id: User identifier.
            channel: Channel name (api, cli, mcp).
            data: Initial session data.
            ttl_s: Session TTL (None uses default).
            metadata: Additional metadata.
            affinity_key: Key for sticky sessions.

        Returns:
            Created UnifiedSession.

        Raises:
            RuntimeError: If max sessions exceeded.
            ValueError: If channel is invalid.
        """
        async with self._lock:
            await self._cleanup_expired_unlocked()

            # Check session limit
            session_ids = await self._storage.list_all()
            if len(session_ids) >= self._max_sessions:
                raise RuntimeError(f"Maximum sessions ({self._max_sessions}) exceeded")

            # Parse channel
            session_channel = None
            if channel:
                session_channel = SessionChannel.from_string(channel)

            # Create session
            session = UnifiedSession(
                id=str(uuid.uuid4()),
                user_id=user_id,
                channel=session_channel,
                data=data or {},
                ttl_s=ttl_s if ttl_s is not None else self._default_ttl_s,
                metadata=metadata or {},
                affinity_key=affinity_key,
            )

            # Save to storage
            await self._storage.save(session)

            # Update indexes
            if user_id:
                if user_id not in self._user_sessions:
                    self._user_sessions[user_id] = set()
                self._user_sessions[user_id].add(session.id)

            if session_channel:
                if session_channel not in self._channel_sessions:
                    self._channel_sessions[session_channel] = set()
                self._channel_sessions[session_channel].add(session.id)

            if affinity_key:
                self._affinity_sessions[affinity_key] = session.id

            # Invoke hooks
            for hook in self._on_create_hooks:
                try:
                    hook(session)
                except Exception as e:
                    logger.warning("Session create hook failed: %s", e)

            logger.debug("Created session %s", session.id)
            return session

    async def get(self, session_id: str) -> UnifiedSession | None:
        """Get a session by ID.

        Args:
            session_id: Session ID.

        Returns:
            UnifiedSession if found and not expired, None otherwise.
        """
        session = await self._storage.load(session_id)
        if session is None:
            return None

        if session.is_expired():
            session.state = SessionModuleState.EXPIRED
            await self._storage.save(session)
            for hook in self._on_expire_hooks:
                try:
                    hook(session)
                except Exception as e:
                    logger.warning("Session expire hook failed: %s", e)
            return None

        return session

    async def get_or_create(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        channel: str | None = None,
        **kwargs,
    ) -> UnifiedSession:
        """Get an existing session or create a new one.

        Args:
            session_id: Optional existing session ID.
            user_id: Optional user identifier.
            channel: Optional channel name.
            **kwargs: Additional arguments for create.

        Returns:
            UnifiedSession instance.
        """
        if session_id:
            session = await self.get(session_id)
            if session:
                if channel:
                    session.touch(SessionChannel.from_string(channel))
                    await self._storage.save(session)
                return session

        return await self.create(user_id=user_id, channel=channel, **kwargs)

    async def list(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        state: SessionModuleState | None = None,
        limit: int = 100,
    ) -> builtins.list[UnifiedSession]:
        """List sessions with optional filtering.

        Args:
            user_id: Filter by user.
            channel: Filter by channel.
            state: Filter by state.
            limit: Maximum number of sessions to return.

        Returns:
            List of matching sessions.
        """
        async with self._lock:
            session_ids = set(await self._storage.list_all())

            # Filter by user
            if user_id:
                user_ids = self._user_sessions.get(user_id, set())
                session_ids = session_ids.intersection(user_ids)

            # Filter by channel
            if channel:
                session_channel = SessionChannel.from_string(channel)
                channel_ids = self._channel_sessions.get(session_channel, set())
                session_ids = session_ids.intersection(channel_ids)

            # Load and filter sessions
            results = []
            for sid in list(session_ids)[: limit * 2]:  # Load extra for filtering
                session = await self.get(sid)
                if session:
                    if state is None or session.state == state:
                        results.append(session)
                        if len(results) >= limit:
                            break

            return results

    async def update(
        self,
        session_id: str,
        data: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update session data.

        Args:
            session_id: Session ID.
            data: Data to update.
            merge: If True, merge with existing; if False, replace.

        Returns:
            True if updated, False if not found.
        """
        session = await self.get(session_id)
        if session is None:
            return False

        if merge:
            session.data.update(data)
        else:
            session.data = data

        session.touch()
        await self._storage.save(session)
        return True

    async def _delete_unlocked(self, session_id: str) -> bool:
        """Delete a session — assumes `self._lock` is already held.

        Shared by `delete()` (acquires the lock) and
        `_cleanup_expired_unlocked()` (invoked from within `create()`/
        `cleanup()`, which already hold the lock). `asyncio.Lock` is NOT
        reentrant, so this body MUST NOT itself acquire `self._lock`.
        """
        session = await self._storage.load(session_id)
        if session is None:
            return False

        # Remove from indexes
        if session.user_id and session.user_id in self._user_sessions:
            self._user_sessions[session.user_id].discard(session_id)

        if session.channel and session.channel in self._channel_sessions:
            self._channel_sessions[session.channel].discard(session_id)

        if session.affinity_key and session.affinity_key in self._affinity_sessions:
            del self._affinity_sessions[session.affinity_key]

        # Update state
        session.state = SessionModuleState.TERMINATED

        # Delete from storage
        result = await self._storage.delete(session_id)

        # Invoke hooks
        for hook in self._on_delete_hooks:
            try:
                hook(session)
            except Exception as e:
                logger.warning("Session delete hook failed: %s", e)

        logger.debug("Deleted session %s", session_id)
        return result

    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID.

        Returns:
            True if deleted, False if not found.
        """
        async with self._lock:
            return await self._delete_unlocked(session_id)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionMessage | None:
        """Add a message to session history.

        Args:
            session_id: Session ID.
            role: Message role.
            content: Message content.
            metadata: Additional metadata.

        Returns:
            Created SessionMessage or None if session not found.
        """
        session = await self.get(session_id)
        if session is None:
            return None

        message = session.add_message(role, content, metadata)
        await self._storage.save(session)
        return message

    async def add_workflow_execution(
        self,
        session_id: str,
        workflow_name: str,
        execution_id: str,
        inputs: dict[str, Any] | None = None,
        outputs: Any = None,
        success: bool = True,
        error: str | None = None,
    ) -> bool:
        """Add a workflow execution to session history.

        Args:
            session_id: Session ID.
            workflow_name: Name of executed workflow.
            execution_id: Execution identifier.
            inputs: Workflow inputs.
            outputs: Workflow outputs.
            success: Whether execution succeeded.
            error: Error message if failed.

        Returns:
            True if added, False if session not found.
        """
        session = await self.get(session_id)
        if session is None:
            return False

        execution = WorkflowExecution(
            workflow_name=workflow_name,
            execution_id=execution_id,
            inputs=inputs or {},
            outputs=outputs,
            completed_at=time.time(),
            success=success,
            error=error,
        )

        session.add_workflow_execution(execution)
        await self._storage.save(session)
        return True

    async def get_by_affinity(self, affinity_key: str) -> UnifiedSession | None:
        """Get session by affinity key.

        Args:
            affinity_key: Affinity key.

        Returns:
            UnifiedSession or None.
        """
        session_id = self._affinity_sessions.get(affinity_key)
        if session_id:
            return await self.get(session_id)
        return None

    async def touch(self, session_id: str, channel: str | None = None) -> bool:
        """Update session activity timestamp.

        Args:
            session_id: Session ID.
            channel: Channel that triggered activity.

        Returns:
            True if updated, False if not found.
        """
        session = await self.get(session_id)
        if session is None:
            return False

        if channel:
            session.touch(SessionChannel.from_string(channel))
        else:
            session.touch()

        await self._storage.save(session)
        return True

    async def _cleanup_expired_unlocked(self) -> int:
        """Clean up expired sessions — assumes `self._lock` is already held.

        Only called from `create()` and `cleanup()`, both of which acquire
        `self._lock` before calling this. Must not itself acquire the lock
        (non-reentrant `asyncio.Lock`) or re-enter through the public
        `delete()` (same reason) — it calls `_delete_unlocked()` directly.
        """
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval_s:
            return 0

        self._last_cleanup = now
        count = 0

        for session_id in await self._storage.list_all():
            session = await self._storage.load(session_id)
            if session and session.is_expired():
                await self._delete_unlocked(session_id)
                count += 1

        if count > 0:
            logger.debug("Cleaned up %d expired sessions", count)

        return count

    async def cleanup(self) -> int:
        """Force cleanup of expired sessions.

        Returns:
            Number of sessions cleaned up.
        """
        async with self._lock:
            self._last_cleanup = 0
            return await self._cleanup_expired_unlocked()

    def on_create(self, callback: Callable[[UnifiedSession], None]) -> None:
        """Register session creation hook.

        Args:
            callback: Callback function.
        """
        self._on_create_hooks.append(callback)

    def on_delete(self, callback: Callable[[UnifiedSession], None]) -> None:
        """Register session deletion hook.

        Args:
            callback: Callback function.
        """
        self._on_delete_hooks.append(callback)

    def on_expire(self, callback: Callable[[UnifiedSession], None]) -> None:
        """Register session expiration hook.

        Args:
            callback: Callback function.
        """
        self._on_expire_hooks.append(callback)

    async def get_stats(self) -> dict[str, Any]:
        """Get module statistics.

        Returns:
            Dictionary with statistics.
        """
        async with self._lock:
            session_ids = await self._storage.list_all()
            active_count = 0
            expired_count = 0

            for sid in session_ids:
                session = await self._storage.load(sid)
                if session:
                    if session.is_expired():
                        expired_count += 1
                    elif session.is_active():
                        active_count += 1

            return {
                "total_sessions": len(session_ids),
                "active_sessions": active_count,
                "expired_sessions": expired_count,
                "by_channel": {str(ch): len(ids) for ch, ids in self._channel_sessions.items()},
                "unique_users": len(self._user_sessions),
                "affinity_mode": str(self._affinity_mode),
                "default_ttl_s": self._default_ttl_s,
                "max_sessions": self._max_sessions,
            }

    async def clear(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared.
        """
        async with self._lock:
            count = await self._storage.clear()
            self._user_sessions.clear()
            self._channel_sessions.clear()
            self._affinity_sessions.clear()
            logger.info("Cleared %d sessions", count)
            return count

    async def size(self) -> int:
        """Get number of sessions.

        Replaces the old `__len__` dunder — `len()` requires a synchronous
        return, which an async-first storage backend cannot provide.
        """
        return len(await self._storage.list_all())

    async def contains(self, session_id: str) -> bool:
        """Check if a session exists.

        Replaces the old `__contains__` dunder — the `in` operator
        requires a synchronous return, which an async-first storage
        backend cannot provide.
        """
        return await self._storage.load(session_id) is not None


class SessionManagerFactory:
    """Factory for creating session managers with different backends.

    Example:
        >>> manager = SessionManagerFactory.create("redis", redis_url="redis://localhost")
        >>> manager = SessionManagerFactory.create(
        ...     "database", database_url="postgresql://user:pass@host/db"
        ... )  # translated internally to postgresql+asyncpg://
        >>> manager = SessionManagerFactory.create("memory")  # Default

    Note:
        `create()` itself stays synchronous — it only constructs objects
        (no I/O happens until the first `await module.create(...)` /
        `.get(...)` / etc. call lazily opens the async engine/connection).
    """

    _backends: dict[str, type[SessionStorageBackend]] = {
        "memory": InMemoryStorage,
        "inmemory": InMemoryStorage,
        "redis": RedisStorage,
        "database": DatabaseStorage,
        "db": DatabaseStorage,
        "sql": DatabaseStorage,
    }

    @classmethod
    def create(
        cls,
        backend: str = "memory",
        **kwargs,
    ) -> UnifiedSessionsModule:
        """Create a sessions module with specified backend.

        Args:
            backend: Backend type (memory, redis, database).
            **kwargs: Backend-specific configuration.

        Returns:
            Configured UnifiedSessionsModule.

        Raises:
            ValueError: If backend is not recognized.
        """
        backend_lower = backend.lower()
        if backend_lower not in cls._backends:
            valid = ", ".join(sorted(set(cls._backends.keys())))
            raise ValueError(f"Unknown backend: '{backend}'. Valid: {valid}")

        backend_class = cls._backends[backend_lower]

        # Extract module kwargs vs backend kwargs
        module_kwargs = {}
        backend_kwargs = {}

        module_params = {"default_ttl_s", "max_sessions", "affinity_mode", "cleanup_interval_s"}
        for key, value in kwargs.items():
            if key in module_params:
                module_kwargs[key] = value
            else:
                backend_kwargs[key] = value

        # Create storage backend
        if backend_lower in ("memory", "inmemory"):
            storage = backend_class()
        elif backend_lower == "redis":
            storage = backend_class(**backend_kwargs)
        elif backend_lower in ("database", "db", "sql"):
            storage = backend_class(**backend_kwargs)
        else:
            storage = backend_class(**backend_kwargs)

        return UnifiedSessionsModule(storage=storage, **module_kwargs)

    @classmethod
    def register_backend(
        cls,
        name: str,
        backend_class: type[SessionStorageBackend],
    ) -> None:
        """Register a custom backend.

        Args:
            name: Backend name.
            backend_class: Backend class.
        """
        cls._backends[name.lower()] = backend_class


# Alias for convenience
SessionManager = SessionManagerFactory
