"""Workflow registration and management for Nexus multi-channel platform.

This module provides a robust workflow registry system for registering,
discovering, and managing workflows across API, CLI, and MCP channels.

Example:
    >>> from aegis_sdk.nexus import WorkflowRegistry, WorkflowRegistration
    >>> registry = WorkflowRegistry()
    >>>
    >>> def my_handler(inputs):
    ...     return {"result": inputs.get("value", 0) * 2}
    >>>
    >>> reg = registry.register(
    ...     name="double-value",
    ...     handler=my_handler,
    ...     version="1.0.0",
    ...     channels=["api", "cli"],
    ...     description="Doubles the input value"
    ... )
    >>>
    >>> workflow = registry.get("double-value")
    >>> result = workflow.handler({"value": 21})
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow registration status."""

    REGISTERED = auto()
    ACTIVE = auto()
    DEPRECATED = auto()
    DISABLED = auto()

    def __str__(self) -> str:
        """Return lowercase status name."""
        return self.name.lower()


class WorkflowPriority(Enum):
    """Workflow execution priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

    def __lt__(self, other: WorkflowPriority) -> bool:
        """Compare priority levels."""
        if isinstance(other, WorkflowPriority):
            return self.value < other.value
        return NotImplemented


@dataclass
class WorkflowMetadata:
    """Additional metadata for workflow registration.

    Attributes:
        author: Workflow author or team.
        created_at: When the workflow was registered.
        updated_at: When the workflow was last modified.
        timeout_s: Maximum execution time in seconds.
        retry_count: Number of retries on failure.
        cache_ttl_s: Cache time-to-live in seconds (0 = no cache).
        rate_limit: Maximum executions per minute (None = unlimited).
    """

    author: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    timeout_s: int = 300
    retry_count: int = 0
    cache_ttl_s: int = 0
    rate_limit: int | None = None


@dataclass
class WorkflowRegistration:
    """Registered workflow metadata and configuration.

    Represents a workflow registered with the Nexus platform,
    including its handler, channel configuration, and metadata.

    Attributes:
        name: Unique workflow identifier.
        version: Semantic version string.
        channels: List of enabled channels ('api', 'cli', 'mcp').
        handler: Callable that executes the workflow.
        description: Human-readable workflow description.
        tags: Categorization tags for discovery.
        status: Current workflow status.
        priority: Execution priority level.
        metadata: Additional workflow metadata.
        input_schema: JSON schema for input validation.
        output_schema: JSON schema for output validation.
    """

    name: str
    version: str
    channels: list[str]
    handler: Callable
    description: str = ""
    tags: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.ACTIVE
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    metadata: WorkflowMetadata = field(default_factory=WorkflowMetadata)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    def __post_init__(self):
        """Validate and normalize registration data."""
        # Normalize channel names
        self.channels = [ch.lower() for ch in self.channels]
        # Normalize tags
        self.tags = [tag.lower().strip() for tag in self.tags]

    def validate(self) -> list[str]:
        """Validate workflow registration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        # Name validation
        if not self.name:
            errors.append("name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("name must be alphanumeric with hyphens/underscores")
        elif len(self.name) > 128:
            errors.append("name must be <= 128 characters")

        # Version validation
        if not self.version:
            errors.append("version is required")

        # Channel validation
        valid_channels = {"api", "cli", "mcp"}
        for channel in self.channels:
            if channel not in valid_channels:
                errors.append(f"Invalid channel: '{channel}'. Valid: {valid_channels}")

        if not self.channels:
            errors.append("At least one channel must be specified")

        # Handler validation
        if not callable(self.handler):
            errors.append("handler must be callable")

        return errors

    def is_channel_enabled(self, channel: str) -> bool:
        """Check if a channel is enabled for this workflow.

        Args:
            channel: Channel name to check.

        Returns:
            True if channel is enabled.
        """
        return channel.lower() in self.channels

    def enable_channel(self, channel: str) -> None:
        """Enable a channel for this workflow.

        Args:
            channel: Channel name to enable.
        """
        channel = channel.lower()
        if channel not in self.channels:
            self.channels.append(channel)
            self.metadata.updated_at = datetime.now(UTC)

    def disable_channel(self, channel: str) -> None:
        """Disable a channel for this workflow.

        Args:
            channel: Channel name to disable.
        """
        channel = channel.lower()
        if channel in self.channels:
            self.channels.remove(channel)
            self.metadata.updated_at = datetime.now(UTC)

    def add_tag(self, tag: str) -> None:
        """Add a tag to the workflow.

        Args:
            tag: Tag to add.
        """
        tag = tag.lower().strip()
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.metadata.updated_at = datetime.now(UTC)

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the workflow.

        Args:
            tag: Tag to remove.

        Returns:
            True if tag was removed, False if not found.
        """
        tag = tag.lower().strip()
        if tag in self.tags:
            self.tags.remove(tag)
            self.metadata.updated_at = datetime.now(UTC)
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert registration to dictionary representation.

        Returns:
            Dictionary representation of the registration.
        """
        return {
            "name": self.name,
            "version": self.version,
            "channels": self.channels,
            "description": self.description,
            "tags": self.tags,
            "status": str(self.status),
            "priority": self.priority.name.lower(),
            "metadata": {
                "author": self.metadata.author,
                "created_at": self.metadata.created_at.isoformat(),
                "updated_at": self.metadata.updated_at.isoformat(),
                "timeout_s": self.metadata.timeout_s,
                "retry_count": self.metadata.retry_count,
                "cache_ttl_s": self.metadata.cache_ttl_s,
                "rate_limit": self.metadata.rate_limit,
            },
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class WorkflowRegistry:
    """Central registry for workflow management.

    Manages workflow registrations, provides discovery and lookup,
    and maintains workflow lifecycle across channels.

    Example:
        >>> registry = WorkflowRegistry()
        >>> registry.register("my-workflow", lambda x: x, version="1.0.0")
        >>> workflow = registry.get("my-workflow")
        >>> all_workflows = registry.list_all()
    """

    def __init__(self):
        """Initialize the workflow registry."""
        self._workflows: dict[str, WorkflowRegistration] = {}
        self._version_history: dict[str, list[str]] = {}
        self._tag_index: dict[str, set[str]] = {}
        self._channel_index: dict[str, set[str]] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        version: str = "1.0.0",
        channels: list[str] | None = None,
        description: str = "",
        tags: list[str] | None = None,
        priority: WorkflowPriority = WorkflowPriority.NORMAL,
        metadata: WorkflowMetadata | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> WorkflowRegistration:
        """Register a workflow with the registry.

        Args:
            name: Unique workflow identifier.
            handler: Callable that executes the workflow.
            version: Semantic version string.
            channels: List of enabled channels (default: all).
            description: Human-readable description.
            tags: Categorization tags.
            priority: Execution priority level.
            metadata: Additional metadata.
            input_schema: JSON schema for input validation.
            output_schema: JSON schema for output validation.

        Returns:
            WorkflowRegistration instance.

        Raises:
            ValueError: If registration validation fails.
        """
        if channels is None:
            channels = ["api", "cli", "mcp"]
        if tags is None:
            tags = []
        if metadata is None:
            metadata = WorkflowMetadata()

        registration = WorkflowRegistration(
            name=name,
            version=version,
            channels=channels,
            handler=handler,
            description=description,
            tags=tags,
            priority=priority,
            metadata=metadata,
            input_schema=input_schema,
            output_schema=output_schema,
        )

        errors = registration.validate()
        if errors:
            raise ValueError(f"Invalid workflow registration: {'; '.join(errors)}")

        # Track version history
        if name in self._version_history:
            if version not in self._version_history[name]:
                self._version_history[name].append(version)
        else:
            self._version_history[name] = [version]

        # Update indexes
        self._update_indexes(registration)

        # Store registration
        self._workflows[name] = registration
        logger.info("Registered workflow: %s v%s", name, version)

        return registration

    def _update_indexes(self, registration: WorkflowRegistration) -> None:
        """Update tag and channel indexes for a registration."""
        name = registration.name

        # Clear old index entries if updating
        for tag_set in self._tag_index.values():
            tag_set.discard(name)
        for channel_set in self._channel_index.values():
            channel_set.discard(name)

        # Add to tag index
        for tag in registration.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(name)

        # Add to channel index
        for channel in registration.channels:
            if channel not in self._channel_index:
                self._channel_index[channel] = set()
            self._channel_index[channel].add(name)

    def unregister(self, name: str) -> bool:
        """Remove a workflow from the registry.

        Args:
            name: Workflow name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self._workflows:
            # Remove from indexes
            for tag_set in self._tag_index.values():
                tag_set.discard(name)
            for channel_set in self._channel_index.values():
                channel_set.discard(name)

            del self._workflows[name]
            logger.info("Unregistered workflow: %s", name)
            return True
        return False

    def get(self, name: str) -> WorkflowRegistration | None:
        """Get a workflow registration by name.

        Args:
            name: Workflow name to retrieve.

        Returns:
            WorkflowRegistration if found, None otherwise.
        """
        return self._workflows.get(name)

    def get_or_raise(self, name: str) -> WorkflowRegistration:
        """Get a workflow registration or raise if not found.

        Args:
            name: Workflow name to retrieve.

        Returns:
            WorkflowRegistration instance.

        Raises:
            KeyError: If workflow not found.
        """
        if name not in self._workflows:
            raise KeyError(f"Workflow not found: {name}")
        return self._workflows[name]

    def list_all(self) -> list[WorkflowRegistration]:
        """Get all registered workflows.

        Returns:
            List of all workflow registrations.
        """
        return list(self._workflows.values())

    def list_by_channel(self, channel: str) -> list[WorkflowRegistration]:
        """Get workflows enabled for a specific channel.

        Args:
            channel: Channel name to filter by.

        Returns:
            List of workflows enabled for the channel.
        """
        channel = channel.lower()
        names = self._channel_index.get(channel, set())
        return [self._workflows[name] for name in names if name in self._workflows]

    def list_by_tag(self, tag: str) -> list[WorkflowRegistration]:
        """Get workflows with a specific tag.

        Args:
            tag: Tag to filter by.

        Returns:
            List of workflows with the tag.
        """
        tag = tag.lower().strip()
        names = self._tag_index.get(tag, set())
        return [self._workflows[name] for name in names if name in self._workflows]

    def list_by_status(self, status: WorkflowStatus) -> list[WorkflowRegistration]:
        """Get workflows with a specific status.

        Args:
            status: Status to filter by.

        Returns:
            List of workflows with the status.
        """
        return [w for w in self._workflows.values() if w.status == status]

    def search(
        self,
        query: str | None = None,
        channels: list[str] | None = None,
        tags: list[str] | None = None,
        status: WorkflowStatus | None = None,
    ) -> list[WorkflowRegistration]:
        """Search workflows with multiple criteria.

        Args:
            query: Text to search in name and description.
            channels: Filter by enabled channels (AND).
            tags: Filter by tags (OR).
            status: Filter by status.

        Returns:
            List of matching workflows.
        """
        results = list(self._workflows.values())

        # Filter by query
        if query:
            query = query.lower()
            results = [
                w for w in results if query in w.name.lower() or query in w.description.lower()
            ]

        # Filter by channels (must have all specified channels)
        if channels:
            channels = [ch.lower() for ch in channels]
            results = [w for w in results if all(ch in w.channels for ch in channels)]

        # Filter by tags (must have at least one specified tag)
        if tags:
            tags = [tag.lower().strip() for tag in tags]
            results = [w for w in results if any(tag in w.tags for tag in tags)]

        # Filter by status
        if status:
            results = [w for w in results if w.status == status]

        return results

    def update_status(self, name: str, status: WorkflowStatus) -> bool:
        """Update workflow status.

        Args:
            name: Workflow name.
            status: New status.

        Returns:
            True if updated, False if not found.
        """
        if name in self._workflows:
            self._workflows[name].status = status
            self._workflows[name].metadata.updated_at = datetime.now(UTC)
            logger.info("Updated workflow %s status to %s", name, status)
            return True
        return False

    def get_version_history(self, name: str) -> list[str]:
        """Get version history for a workflow.

        Args:
            name: Workflow name.

        Returns:
            List of version strings in registration order.
        """
        return list(self._version_history.get(name, []))

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dictionary with registry statistics.
        """
        workflows = list(self._workflows.values())
        return {
            "total_workflows": len(workflows),
            "by_status": {
                str(status): len([w for w in workflows if w.status == status])
                for status in WorkflowStatus
            },
            "by_channel": {channel: len(names) for channel, names in self._channel_index.items()},
            "total_tags": len(self._tag_index),
            "active_workflows": len([w for w in workflows if w.status == WorkflowStatus.ACTIVE]),
        }

    def clear(self) -> int:
        """Clear all workflows from the registry.

        Returns:
            Number of workflows removed.
        """
        count = len(self._workflows)
        self._workflows.clear()
        self._version_history.clear()
        self._tag_index.clear()
        self._channel_index.clear()
        logger.info("Cleared %d workflows from registry", count)
        return count

    def __len__(self) -> int:
        """Get number of registered workflows."""
        return len(self._workflows)

    def __contains__(self, name: str) -> bool:
        """Check if workflow is registered."""
        return name in self._workflows

    def __iter__(self):
        """Iterate over workflow registrations."""
        return iter(self._workflows.values())
