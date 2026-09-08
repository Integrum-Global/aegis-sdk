"""Session management for Nexus multi-channel platform.

This module provides session tracking and management across API, CLI, and MCP
channels, enabling stateful interactions and cross-channel continuity.

Example:
    >>> from aegis_sdk.nexus import SessionManager, Session
    >>> manager = SessionManager()
    >>>
    >>> # Create a session for API channel
    >>> session = manager.create("api")
    >>> print(session.id)  # UUID for the session
    >>>
    >>> # Store data in session
    >>> manager.update(session.id, {"user_id": 123, "preferences": {...}})
    >>>
    >>> # Retrieve session
    >>> session = manager.get(session.id)
    >>> print(session.data)  # {"user_id": 123, "preferences": {...}}
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""

    ACTIVE = auto()
    IDLE = auto()
    EXPIRED = auto()
    TERMINATED = auto()

    def __str__(self) -> str:
        """Return lowercase state name."""
        return self.name.lower()


@dataclass
class SessionMetrics:
    """Session usage metrics.

    Attributes:
        request_count: Number of requests in this session.
        error_count: Number of errors in this session.
        total_latency_ms: Total request latency in milliseconds.
        last_request_at: Timestamp of last request.
    """

    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    last_request_at: float | None = None

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency per request."""
        if self.request_count == 0:
            return 0.0
        return self.total_latency_ms / self.request_count

    def record_request(self, latency_ms: float, error: bool = False) -> None:
        """Record a request in metrics.

        Args:
            latency_ms: Request latency in milliseconds.
            error: Whether the request resulted in an error.
        """
        self.request_count += 1
        self.total_latency_ms += latency_ms
        self.last_request_at = time.time()
        if error:
            self.error_count += 1


@dataclass
class Session:
    """Represents a user session in the Nexus platform.

    Sessions track state and data across requests within a channel,
    and can optionally span multiple channels for unified experiences.

    Attributes:
        id: Unique session identifier (UUID).
        channel: Channel where session was created ('api', 'cli', 'mcp').
        created_at: Session creation timestamp (Unix time).
        last_activity: Last activity timestamp (Unix time).
        data: Session data store.
        state: Current session state.
        user_id: Optional associated user identifier.
        metadata: Additional session metadata.
        metrics: Session usage metrics.
        ttl_s: Session time-to-live in seconds (0 = no expiry).
        cross_channel: Whether session can be accessed from other channels.
    """

    id: str
    channel: str
    created_at: float
    last_activity: float
    data: dict[str, Any] = field(default_factory=dict)
    state: SessionState = SessionState.ACTIVE
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    ttl_s: int = 3600  # 1 hour default
    cross_channel: bool = False

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
        if self.state == SessionState.IDLE:
            self.state = SessionState.ACTIVE

    def is_expired(self) -> bool:
        """Check if session has expired.

        Returns:
            True if session is expired based on TTL.
        """
        if self.ttl_s == 0:
            return False
        return (time.time() - self.last_activity) > self.ttl_s

    def is_active(self) -> bool:
        """Check if session is active and not expired.

        Returns:
            True if session is active.
        """
        return self.state == SessionState.ACTIVE and not self.is_expired()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from session data.

        Args:
            key: Data key to retrieve.
            default: Default value if key not found.

        Returns:
            Value from session data or default.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in session data.

        Args:
            key: Data key to set.
            value: Value to store.
        """
        self.data[key] = value
        self.touch()

    def delete(self, key: str) -> bool:
        """Delete a value from session data.

        Args:
            key: Data key to delete.

        Returns:
            True if key was deleted, False if not found.
        """
        if key in self.data:
            del self.data[key]
            self.touch()
            return True
        return False

    def clear_data(self) -> None:
        """Clear all session data."""
        self.data.clear()
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary representation.

        Returns:
            Dictionary representation of the session.
        """
        return {
            "id": self.id,
            "channel": self.channel,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "data": self.data,
            "state": str(self.state),
            "user_id": self.user_id,
            "metadata": self.metadata,
            "metrics": {
                "request_count": self.metrics.request_count,
                "error_count": self.metrics.error_count,
                "avg_latency_ms": self.metrics.avg_latency_ms,
            },
            "ttl_s": self.ttl_s,
            "cross_channel": self.cross_channel,
            "is_expired": self.is_expired(),
            "is_active": self.is_active(),
        }


class SessionManager:
    """Manages session lifecycle across Nexus channels.

    Provides creation, retrieval, update, and deletion of sessions
    with support for TTL-based expiration and cross-channel access.

    Example:
        >>> manager = SessionManager(default_ttl_s=7200)
        >>> session = manager.create("api", user_id="user-123")
        >>> manager.update(session.id, {"cart": ["item1", "item2"]})
        >>> session = manager.get(session.id)
        >>> manager.delete(session.id)
    """

    def __init__(
        self,
        default_ttl_s: int = 3600,
        max_sessions: int = 10000,
        cleanup_interval_s: int = 300,
    ):
        """Initialize session manager.

        Args:
            default_ttl_s: Default session TTL in seconds.
            max_sessions: Maximum number of active sessions.
            cleanup_interval_s: Interval for cleanup task in seconds.
        """
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, set[str]] = {}
        self._channel_sessions: dict[str, set[str]] = {}
        self._default_ttl_s = default_ttl_s
        self._max_sessions = max_sessions
        self._cleanup_interval_s = cleanup_interval_s
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._on_create_hooks: list[Callable[[Session], None]] = []
        self._on_delete_hooks: list[Callable[[Session], None]] = []

    def create(
        self,
        channel: str,
        user_id: str | None = None,
        data: dict[str, Any] | None = None,
        ttl_s: int | None = None,
        cross_channel: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            channel: Channel where session is created.
            user_id: Optional user identifier.
            data: Initial session data.
            ttl_s: Session TTL (None uses default).
            cross_channel: Enable cross-channel access.
            metadata: Additional metadata.

        Returns:
            Created Session instance.

        Raises:
            ValueError: If channel is invalid.
            RuntimeError: If maximum sessions exceeded.
        """
        # Validate channel
        valid_channels = {"api", "cli", "mcp"}
        channel = channel.lower()
        if channel not in valid_channels:
            raise ValueError(f"Invalid channel: '{channel}'. Valid: {valid_channels}")

        # Check session limit
        with self._lock:
            self._cleanup_expired()
            if len(self._sessions) >= self._max_sessions:
                raise RuntimeError(f"Maximum sessions ({self._max_sessions}) exceeded")

            # Create session
            now = time.time()
            session = Session(
                id=str(uuid.uuid4()),
                channel=channel,
                created_at=now,
                last_activity=now,
                data=data or {},
                user_id=user_id,
                metadata=metadata or {},
                ttl_s=ttl_s if ttl_s is not None else self._default_ttl_s,
                cross_channel=cross_channel,
            )

            # Store session
            self._sessions[session.id] = session

            # Update channel index
            if channel not in self._channel_sessions:
                self._channel_sessions[channel] = set()
            self._channel_sessions[channel].add(session.id)

            # Update user index
            if user_id:
                if user_id not in self._user_sessions:
                    self._user_sessions[user_id] = set()
                self._user_sessions[user_id].add(session.id)

            # Invoke hooks
            for hook in self._on_create_hooks:
                try:
                    hook(session)
                except Exception as e:
                    logger.warning("Session create hook failed: %s", e)

            logger.debug("Created session %s for channel %s", session.id, channel)
            return session

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session ID to retrieve.

        Returns:
            Session if found and not expired, None otherwise.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            # Check expiration
            if session.is_expired():
                session.state = SessionState.EXPIRED
                return None

            return session

    def get_or_raise(self, session_id: str) -> Session:
        """Get a session or raise if not found/expired.

        Args:
            session_id: Session ID to retrieve.

        Returns:
            Session instance.

        Raises:
            KeyError: If session not found or expired.
        """
        session = self.get(session_id)
        if session is None:
            raise KeyError(f"Session not found or expired: {session_id}")
        return session

    def update(
        self,
        session_id: str,
        data: dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """Update session data.

        Args:
            session_id: Session ID to update.
            data: Data to update/merge.
            merge: If True, merge with existing data; if False, replace.

        Returns:
            True if updated, False if session not found.
        """
        with self._lock:
            session = self.get(session_id)
            if session is None:
                return False

            if merge:
                session.data.update(data)
            else:
                session.data = data

            session.touch()
            return True

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False

            # Remove from indexes
            if session.channel in self._channel_sessions:
                self._channel_sessions[session.channel].discard(session_id)
            if session.user_id and session.user_id in self._user_sessions:
                self._user_sessions[session.user_id].discard(session_id)

            # Update state and remove
            session.state = SessionState.TERMINATED
            del self._sessions[session_id]

            # Invoke hooks
            for hook in self._on_delete_hooks:
                try:
                    hook(session)
                except Exception as e:
                    logger.warning("Session delete hook failed: %s", e)

            logger.debug("Deleted session %s", session_id)
            return True

    def touch(self, session_id: str) -> bool:
        """Update session last activity timestamp.

        Args:
            session_id: Session ID to touch.

        Returns:
            True if updated, False if not found.
        """
        session = self.get(session_id)
        if session:
            session.touch()
            return True
        return False

    def list_by_channel(self, channel: str) -> list[Session]:
        """Get all sessions for a channel.

        Args:
            channel: Channel name.

        Returns:
            List of active sessions for the channel.
        """
        channel = channel.lower()
        session_ids = self._channel_sessions.get(channel, set())
        sessions = []
        for sid in list(session_ids):
            session = self.get(sid)
            if session:
                sessions.append(session)
        return sessions

    def list_by_user(self, user_id: str) -> list[Session]:
        """Get all sessions for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of active sessions for the user.
        """
        session_ids = self._user_sessions.get(user_id, set())
        sessions = []
        for sid in list(session_ids):
            session = self.get(sid)
            if session:
                sessions.append(session)
        return sessions

    def get_cross_channel_sessions(self, user_id: str) -> list[Session]:
        """Get cross-channel enabled sessions for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of cross-channel sessions.
        """
        return [s for s in self.list_by_user(user_id) if s.cross_channel]

    def terminate_user_sessions(self, user_id: str) -> int:
        """Terminate all sessions for a user.

        Args:
            user_id: User identifier.

        Returns:
            Number of sessions terminated.
        """
        session_ids = list(self._user_sessions.get(user_id, set()))
        count = 0
        for sid in session_ids:
            if self.delete(sid):
                count += 1
        return count

    def _cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions cleaned up.
        """
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval_s:
            return 0

        self._last_cleanup = now
        expired = [sid for sid, session in self._sessions.items() if session.is_expired()]

        for sid in expired:
            self.delete(sid)

        if expired:
            logger.debug("Cleaned up %d expired sessions", len(expired))

        return len(expired)

    def cleanup(self) -> int:
        """Force cleanup of expired sessions.

        Returns:
            Number of sessions cleaned up.
        """
        with self._lock:
            self._last_cleanup = 0
            return self._cleanup_expired()

    def on_create(self, callback: Callable[[Session], None]) -> None:
        """Register a session creation hook.

        Args:
            callback: Function called when session is created.
        """
        self._on_create_hooks.append(callback)

    def on_delete(self, callback: Callable[[Session], None]) -> None:
        """Register a session deletion hook.

        Args:
            callback: Function called when session is deleted.
        """
        self._on_delete_hooks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get session manager statistics.

        Returns:
            Dictionary with session statistics.
        """
        with self._lock:
            sessions = list(self._sessions.values())
            active = [s for s in sessions if s.is_active()]
            expired = [s for s in sessions if s.is_expired()]

            return {
                "total_sessions": len(sessions),
                "active_sessions": len(active),
                "expired_sessions": len(expired),
                "by_channel": {
                    channel: len(ids) for channel, ids in self._channel_sessions.items()
                },
                "by_state": {
                    str(state): len([s for s in sessions if s.state == state])
                    for state in SessionState
                },
                "unique_users": len(self._user_sessions),
                "max_sessions": self._max_sessions,
                "default_ttl_s": self._default_ttl_s,
            }

    def clear(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared.
        """
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            self._user_sessions.clear()
            self._channel_sessions.clear()
            logger.info("Cleared %d sessions", count)
            return count

    def __len__(self) -> int:
        """Get number of sessions."""
        return len(self._sessions)

    def __contains__(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self._sessions
