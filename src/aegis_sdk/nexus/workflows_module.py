"""Workflows Module for Nexus v1.1 - Dynamic workflow registration and management.

This module provides enhanced workflow management capabilities including:
- Dynamic runtime registration/unregistration
- Semantic versioning support with multiple versions per workflow
- Automatic metadata extraction from handlers
- Schema validation for inputs/outputs
- Global registry singleton for cross-module access

Example:
    >>> from aegis_sdk.nexus import WorkflowsModule, WorkflowRegistry
    >>>
    >>> # Get global registry (singleton)
    >>> registry = WorkflowRegistry.get_instance()
    >>>
    >>> # Or create a local module
    >>> module = WorkflowsModule()
    >>>
    >>> def my_handler(inputs):
    ...     return {"result": inputs.get("value", 0) * 2}
    >>>
    >>> # Register workflow
    >>> module.register(
    ...     name="double-value",
    ...     handler=my_handler,
    ...     version="1.0.0",
    ...     description="Doubles the input value"
    ... )
    >>>
    >>> # Execute workflow
    >>> result = await module.execute("double-value", {"value": 21})
"""

from __future__ import annotations

import asyncio
import builtins
import inspect
import logging
import re
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import (
    Any,
    Union,
    get_type_hints,
)

logger = logging.getLogger(__name__)

# Type alias for workflow handlers
WorkflowHandlerType = Callable[..., Any | Awaitable[Any]]


class WorkflowModuleStatus(Enum):
    """Workflow status within the module."""

    REGISTERED = auto()
    ACTIVE = auto()
    DEPRECATED = auto()
    DISABLED = auto()

    def __str__(self) -> str:
        """Return lowercase status name."""
        return self.name.lower()


class ValidationMode(Enum):
    """Validation mode for workflow execution."""

    NONE = auto()  # No validation
    WARN = auto()  # Log warnings but continue
    STRICT = auto()  # Raise on validation errors

    def __str__(self) -> str:
        """Return lowercase mode name."""
        return self.name.lower()


@dataclass
class WorkflowSchema:
    """JSON Schema for workflow inputs/outputs.

    Attributes:
        type: Schema type (usually 'object').
        properties: Property definitions.
        required: List of required property names.
        description: Schema description.
        additional_properties: Whether additional properties are allowed.
    """

    type: str = "object"
    properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    description: str = ""
    additional_properties: bool = True

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate data against the schema.

        Args:
            data: Data to validate.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []

        if not isinstance(data, dict):
            errors.append(f"Expected object, got {type(data).__name__}")
            return False, errors

        # Check required fields
        for req in self.required:
            if req not in data:
                errors.append(f"Missing required field: '{req}'")

        # Check property types if specified
        for prop_name, prop_def in self.properties.items():
            if prop_name in data:
                expected_type = prop_def.get("type")
                if expected_type:
                    value = data[prop_name]
                    if not self._check_type(value, expected_type):
                        errors.append(
                            f"Field '{prop_name}' should be {expected_type}, "
                            f"got {type(value).__name__}"
                        )

        # Check for additional properties
        if not self.additional_properties:
            extra = set(data.keys()) - set(self.properties.keys())
            if extra:
                errors.append(f"Unexpected properties: {extra}")

        return len(errors) == 0, errors

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON Schema type."""
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        expected = type_mapping.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow
        return isinstance(value, expected)

    def to_dict(self) -> dict[str, Any]:
        """Convert schema to dictionary."""
        result = {
            "type": self.type,
            "properties": self.properties,
        }
        if self.required:
            result["required"] = self.required
        if self.description:
            result["description"] = self.description
        if not self.additional_properties:
            result["additionalProperties"] = False
        return result


@dataclass
class WorkflowVersionInfo:
    """Information about a specific workflow version.

    Attributes:
        version: Semantic version string.
        handler: Workflow handler for this version.
        created_at: When this version was registered.
        deprecated: Whether this version is deprecated.
        deprecation_message: Message explaining deprecation.
    """

    version: str
    handler: WorkflowHandlerType
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deprecated: bool = False
    deprecation_message: str = ""

    def __post_init__(self):
        """Parse and validate version."""
        self._parsed = self._parse_version(self.version)

    @staticmethod
    def _parse_version(version: str) -> tuple[int, int, int]:
        """Parse semantic version string.

        Args:
            version: Version string (e.g., "1.2.3").

        Returns:
            Tuple of (major, minor, patch).
        """
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (0, 0, 0)

    def __lt__(self, other: WorkflowVersionInfo) -> bool:
        """Compare versions for sorting."""
        return self._parsed < other._parsed

    def __eq__(self, other: object) -> bool:
        """Check version equality."""
        if isinstance(other, WorkflowVersionInfo):
            return self.version == other.version
        return False


@dataclass
class WorkflowMetadataInfo:
    """Extracted metadata from workflow handler.

    Attributes:
        name: Workflow name.
        description: Workflow description (from docstring).
        author: Workflow author.
        created_at: Registration timestamp.
        updated_at: Last update timestamp.
        timeout_s: Execution timeout in seconds.
        retry_count: Number of retries on failure.
        tags: Workflow tags for categorization.
        input_schema: JSON Schema for inputs.
        output_schema: JSON Schema for outputs.
        is_async: Whether handler is async.
        parameter_names: List of parameter names.
    """

    name: str
    description: str = ""
    author: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    timeout_s: int = 300
    retry_count: int = 0
    tags: list[str] = field(default_factory=list)
    input_schema: WorkflowSchema | None = None
    output_schema: WorkflowSchema | None = None
    is_async: bool = False
    parameter_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "timeout_s": self.timeout_s,
            "retry_count": self.retry_count,
            "tags": self.tags,
            "input_schema": self.input_schema.to_dict() if self.input_schema else None,
            "output_schema": self.output_schema.to_dict() if self.output_schema else None,
            "is_async": self.is_async,
            "parameter_names": self.parameter_names,
        }


@dataclass
class ModuleWorkflowRegistration:
    """Complete workflow registration in the module.

    Attributes:
        name: Unique workflow identifier.
        metadata: Extracted workflow metadata.
        versions: Dictionary mapping version string to version info.
        latest_version: Current latest version string.
        status: Current workflow status.
        execution_count: Total execution count.
        last_executed: Last execution timestamp.
        channels: Enabled channels for this workflow.
    """

    name: str
    metadata: WorkflowMetadataInfo
    versions: dict[str, WorkflowVersionInfo] = field(default_factory=dict)
    latest_version: str = "1.0.0"
    status: WorkflowModuleStatus = WorkflowModuleStatus.ACTIVE
    execution_count: int = 0
    last_executed: datetime | None = None
    channels: set[str] = field(default_factory=lambda: {"api", "cli", "mcp"})

    def get_handler(self, version: str | None = None) -> WorkflowHandlerType:
        """Get handler for a specific version.

        Args:
            version: Version string (None for latest).

        Returns:
            Workflow handler function.

        Raises:
            KeyError: If version not found.
        """
        target_version = version or self.latest_version
        if target_version not in self.versions:
            raise KeyError(f"Version not found: {target_version}")
        return self.versions[target_version].handler

    def get_latest_handler(self) -> WorkflowHandlerType:
        """Get the latest version handler."""
        return self.get_handler(self.latest_version)

    def list_versions(self) -> list[str]:
        """Get sorted list of available versions (newest first)."""
        sorted_versions = sorted(self.versions.values(), reverse=True)
        return [v.version for v in sorted_versions]

    def validate(self) -> list[str]:
        """Validate the registration.

        Returns:
            List of validation error messages.
        """
        errors = []

        if not self.name:
            errors.append("name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("name must be alphanumeric with hyphens/underscores")
        elif len(self.name) > 128:
            errors.append("name must be <= 128 characters")

        if not self.versions:
            errors.append("at least one version must be registered")

        valid_channels = {"api", "cli", "mcp"}
        for channel in self.channels:
            if channel not in valid_channels:
                errors.append(f"Invalid channel: '{channel}'")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert registration to dictionary."""
        return {
            "name": self.name,
            "metadata": self.metadata.to_dict(),
            "versions": self.list_versions(),
            "latest_version": self.latest_version,
            "status": str(self.status),
            "execution_count": self.execution_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "channels": list(self.channels),
        }


@dataclass
class WorkflowExecutionResult:
    """Result of workflow execution.

    Attributes:
        success: Whether execution succeeded.
        workflow_name: Name of executed workflow.
        version: Version that was executed.
        result: Execution result data.
        error: Error message if failed.
        execution_id: Unique execution identifier.
        started_at: Execution start time.
        completed_at: Execution completion time.
        duration_ms: Execution duration in milliseconds.
    """

    success: bool
    workflow_name: str
    version: str
    result: Any = None
    error: str | None = None
    execution_id: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "workflow_name": self.workflow_name,
            "version": self.version,
            "result": self.result,
            "error": self.error,
            "execution_id": self.execution_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class MetadataExtractor:
    """Extracts metadata from workflow handlers automatically."""

    @staticmethod
    def extract(
        handler: WorkflowHandlerType,
        name: str,
        description: str | None = None,
        author: str | None = None,
        timeout_s: int = 300,
        retry_count: int = 0,
        tags: list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> WorkflowMetadataInfo:
        """Extract metadata from a workflow handler.

        Args:
            handler: Workflow handler function.
            name: Workflow name.
            description: Override for description.
            author: Override for author.
            timeout_s: Execution timeout.
            retry_count: Retry count.
            tags: Workflow tags.
            input_schema: Override for input schema.
            output_schema: Override for output schema.

        Returns:
            Extracted WorkflowMetadataInfo.
        """
        # Extract description from docstring if not provided
        extracted_desc = description
        if not extracted_desc and handler.__doc__:
            extracted_desc = handler.__doc__.strip().split("\n")[0]

        # Check if handler is async
        is_async = asyncio.iscoroutinefunction(handler)

        # Get parameter names from signature
        parameter_names = []
        try:
            sig = inspect.signature(handler)
            parameter_names = [
                p.name for p in sig.parameters.values() if p.name not in ("self", "cls")
            ]
        except (ValueError, TypeError):
            pass

        # Build input schema if not provided
        built_input_schema = None
        if input_schema:
            built_input_schema = WorkflowSchema(
                type=input_schema.get("type", "object"),
                properties=input_schema.get("properties", {}),
                required=input_schema.get("required", []),
                description=input_schema.get("description", ""),
                additional_properties=input_schema.get("additionalProperties", True),
            )
        elif parameter_names:
            # Auto-generate basic schema from parameters
            properties = {}
            try:
                hints = get_type_hints(handler)
                for param in parameter_names:
                    if param in hints:
                        hint = hints[param]
                        properties[param] = {"type": MetadataExtractor._python_type_to_json(hint)}
                    else:
                        properties[param] = {"type": "any"}
            except Exception:
                for param in parameter_names:
                    properties[param] = {"type": "any"}

            if properties:
                built_input_schema = WorkflowSchema(
                    type="object",
                    properties=properties,
                    description=f"Input parameters for {name}",
                )

        # Build output schema if provided
        built_output_schema = None
        if output_schema:
            built_output_schema = WorkflowSchema(
                type=output_schema.get("type", "object"),
                properties=output_schema.get("properties", {}),
                required=output_schema.get("required", []),
                description=output_schema.get("description", ""),
                additional_properties=output_schema.get("additionalProperties", True),
            )

        return WorkflowMetadataInfo(
            name=name,
            description=extracted_desc or "",
            author=author,
            timeout_s=timeout_s,
            retry_count=retry_count,
            tags=tags or [],
            input_schema=built_input_schema,
            output_schema=built_output_schema,
            is_async=is_async,
            parameter_names=parameter_names,
        )

    @staticmethod
    def _python_type_to_json(python_type: type) -> str:
        """Convert Python type hint to JSON Schema type."""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null",
        }
        # Handle Optional and other generics
        origin = getattr(python_type, "__origin__", None)
        if origin is Union:
            args = getattr(python_type, "__args__", ())
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return MetadataExtractor._python_type_to_json(non_none[0])

        return type_mapping.get(python_type, "any")


class WorkflowsModule:
    """Enhanced workflow management module with versioning support.

    Provides dynamic workflow registration, versioning, validation,
    and execution capabilities for Nexus v1.1.

    Example:
        >>> module = WorkflowsModule(validation_mode=ValidationMode.STRICT)
        >>> module.register("my-workflow", handler=my_handler, version="1.0.0")
        >>> result = await module.execute("my-workflow", {"value": 42})
    """

    def __init__(
        self,
        validation_mode: ValidationMode = ValidationMode.WARN,
        default_timeout_s: int = 300,
    ):
        """Initialize workflows module.

        Args:
            validation_mode: Validation mode for execution.
            default_timeout_s: Default execution timeout.
        """
        self._workflows: dict[str, ModuleWorkflowRegistration] = {}
        self._validation_mode = validation_mode
        self._default_timeout_s = default_timeout_s
        self._lock = threading.RLock()
        self._execution_counter = 0
        self._total_executions = 0
        self._successful_executions = 0
        self._failed_executions = 0

    def register(
        self,
        name: str,
        handler: WorkflowHandlerType,
        version: str = "1.0.0",
        description: str | None = None,
        author: str | None = None,
        timeout_s: int | None = None,
        retry_count: int = 0,
        tags: builtins.list[str] | None = None,
        channels: builtins.list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> ModuleWorkflowRegistration:
        """Register a workflow with the module.

        Args:
            name: Unique workflow identifier.
            handler: Workflow handler function.
            version: Semantic version string (e.g., "1.0.0").
            description: Workflow description.
            author: Workflow author.
            timeout_s: Execution timeout in seconds.
            retry_count: Number of retries on failure.
            tags: Workflow tags for categorization.
            channels: Enabled channels (default: all).
            input_schema: JSON Schema for inputs.
            output_schema: JSON Schema for outputs.

        Returns:
            ModuleWorkflowRegistration instance.

        Raises:
            ValueError: If validation fails.
        """
        if not callable(handler):
            raise ValueError("handler must be callable")

        with self._lock:
            # Extract metadata
            metadata = MetadataExtractor.extract(
                handler=handler,
                name=name,
                description=description,
                author=author,
                timeout_s=timeout_s or self._default_timeout_s,
                retry_count=retry_count,
                tags=tags,
                input_schema=input_schema,
                output_schema=output_schema,
            )

            # Create version info
            version_info = WorkflowVersionInfo(
                version=version,
                handler=handler,
            )

            # Check if workflow already exists
            if name in self._workflows:
                registration = self._workflows[name]
                # Add new version
                registration.versions[version] = version_info
                # Update latest if this is newer
                current_latest = registration.versions.get(registration.latest_version)
                if current_latest is None or version_info > current_latest:
                    registration.latest_version = version
                registration.metadata.updated_at = datetime.now(UTC)
                logger.info("Added version %s to workflow: %s", version, name)
            else:
                # Create new registration
                registration = ModuleWorkflowRegistration(
                    name=name,
                    metadata=metadata,
                    versions={version: version_info},
                    latest_version=version,
                    channels=set(channels) if channels else {"api", "cli", "mcp"},
                )

                # Validate
                errors = registration.validate()
                if errors:
                    raise ValueError(f"Invalid workflow registration: {'; '.join(errors)}")

                self._workflows[name] = registration
                logger.info("Registered workflow: %s v%s", name, version)

            return registration

    def unregister(self, name: str, version: str | None = None) -> bool:
        """Remove a workflow or specific version from the module.

        Args:
            name: Workflow name.
            version: Specific version to remove (None removes all).

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if name not in self._workflows:
                return False

            if version is None:
                # Remove entire workflow
                del self._workflows[name]
                logger.info("Unregistered workflow: %s", name)
                return True
            else:
                # Remove specific version
                registration = self._workflows[name]
                if version in registration.versions:
                    del registration.versions[version]

                    # If no versions left, remove workflow
                    if not registration.versions:
                        del self._workflows[name]
                        logger.info("Unregistered workflow: %s (no versions left)", name)
                    else:
                        # Update latest version
                        sorted_versions = sorted(registration.versions.values(), reverse=True)
                        registration.latest_version = sorted_versions[0].version
                        logger.info("Removed version %s from workflow: %s", version, name)
                    return True
                return False

    def list(
        self,
        channel: str | None = None,
        tags: builtins.list[str] | None = None,
        status: WorkflowModuleStatus | None = None,
    ) -> builtins.list[ModuleWorkflowRegistration]:
        """List workflows with optional filtering.

        Args:
            channel: Filter by enabled channel.
            tags: Filter by tags (OR).
            status: Filter by status.

        Returns:
            List of matching workflow registrations.
        """
        with self._lock:
            results = list(self._workflows.values())

            if channel:
                channel = channel.lower()
                results = [w for w in results if channel in w.channels]

            if tags:
                tags = [t.lower() for t in tags]
                results = [
                    w
                    for w in results
                    if any(t in [tag.lower() for tag in w.metadata.tags] for t in tags)
                ]

            if status:
                results = [w for w in results if w.status == status]

            return results

    def get(self, name: str, version: str | None = None) -> ModuleWorkflowRegistration | None:
        """Get a workflow registration.

        Args:
            name: Workflow name.
            version: Specific version (ignored, returns full registration).

        Returns:
            ModuleWorkflowRegistration or None.
        """
        return self._workflows.get(name)

    def get_handler(
        self,
        name: str,
        version: str | None = None,
    ) -> WorkflowHandlerType | None:
        """Get workflow handler for a specific version.

        Args:
            name: Workflow name.
            version: Specific version (None for latest).

        Returns:
            Workflow handler or None.
        """
        registration = self._workflows.get(name)
        if registration:
            try:
                return registration.get_handler(version)
            except KeyError:
                return None
        return None

    def get_versions(self, name: str) -> builtins.list[str]:
        """Get available versions for a workflow.

        Args:
            name: Workflow name.

        Returns:
            List of version strings (newest first).
        """
        registration = self._workflows.get(name)
        if registration:
            return registration.list_versions()
        return []

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        self._execution_counter += 1
        timestamp = int(time.time() * 1000)
        return f"wf-exec-{timestamp}-{self._execution_counter}"

    async def execute(
        self,
        name: str,
        inputs: dict[str, Any] | None = None,
        version: str | None = None,
        validate_inputs: bool = True,
    ) -> WorkflowExecutionResult:
        """Execute a workflow.

        Args:
            name: Workflow name.
            inputs: Workflow inputs.
            version: Specific version (None for latest).
            validate_inputs: Whether to validate inputs against schema.

        Returns:
            WorkflowExecutionResult with execution outcome.
        """
        started_at = datetime.now(UTC)
        execution_id = self._generate_execution_id()
        inputs = inputs or {}

        self._total_executions += 1

        # Get registration
        registration = self._workflows.get(name)
        if not registration:
            self._failed_executions += 1
            return WorkflowExecutionResult(
                success=False,
                workflow_name=name,
                version=version or "unknown",
                error=f"Workflow not found: {name}",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        # Check status
        if registration.status == WorkflowModuleStatus.DISABLED:
            self._failed_executions += 1
            return WorkflowExecutionResult(
                success=False,
                workflow_name=name,
                version=version or registration.latest_version,
                error=f"Workflow is disabled: {name}",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        # Get handler
        target_version = version or registration.latest_version
        try:
            handler = registration.get_handler(target_version)
        except KeyError:
            self._failed_executions += 1
            return WorkflowExecutionResult(
                success=False,
                workflow_name=name,
                version=target_version,
                error=f"Version not found: {target_version}",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        # Validate inputs
        if validate_inputs and registration.metadata.input_schema:
            is_valid, errors = registration.metadata.input_schema.validate(inputs)
            if not is_valid:
                if self._validation_mode == ValidationMode.STRICT:
                    self._failed_executions += 1
                    return WorkflowExecutionResult(
                        success=False,
                        workflow_name=name,
                        version=target_version,
                        error=f"Input validation failed: {'; '.join(errors)}",
                        execution_id=execution_id,
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                    )
                elif self._validation_mode == ValidationMode.WARN:
                    logger.warning("Input validation warnings for %s: %s", name, errors)

        # Check for deprecation warning
        version_info = registration.versions.get(target_version)
        if version_info and version_info.deprecated:
            logger.warning(
                "Executing deprecated version %s of workflow %s. %s",
                target_version,
                name,
                version_info.deprecation_message,
            )

        try:
            # Execute handler
            if asyncio.iscoroutinefunction(handler):
                result = await handler(inputs)
            else:
                # Run sync handler in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handler, inputs)

            # Update execution stats
            registration.execution_count += 1
            registration.last_executed = datetime.now(UTC)
            self._successful_executions += 1

            return WorkflowExecutionResult(
                success=True,
                workflow_name=name,
                version=target_version,
                result=result,
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        except Exception as e:
            self._failed_executions += 1
            logger.error("Workflow execution failed for %s: %s", name, e, exc_info=True)
            return WorkflowExecutionResult(
                success=False,
                workflow_name=name,
                version=target_version,
                error="Workflow execution failed",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

    def deprecate_version(
        self,
        name: str,
        version: str,
        message: str = "",
    ) -> bool:
        """Mark a workflow version as deprecated.

        Args:
            name: Workflow name.
            version: Version to deprecate.
            message: Deprecation message.

        Returns:
            True if deprecated, False if not found.
        """
        with self._lock:
            registration = self._workflows.get(name)
            if not registration:
                return False

            version_info = registration.versions.get(version)
            if not version_info:
                return False

            version_info.deprecated = True
            version_info.deprecation_message = message
            logger.info("Deprecated workflow %s version %s: %s", name, version, message)
            return True

    def set_status(self, name: str, status: WorkflowModuleStatus) -> bool:
        """Set workflow status.

        Args:
            name: Workflow name.
            status: New status.

        Returns:
            True if updated, False if not found.
        """
        with self._lock:
            if name in self._workflows:
                self._workflows[name].status = status
                self._workflows[name].metadata.updated_at = datetime.now(UTC)
                logger.info("Set workflow %s status to %s", name, status)
                return True
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get module statistics.

        Returns:
            Dictionary with module statistics.
        """
        with self._lock:
            workflows = list(self._workflows.values())
            return {
                "total_workflows": len(workflows),
                "by_status": {
                    str(status): len([w for w in workflows if w.status == status])
                    for status in WorkflowModuleStatus
                },
                "total_versions": sum(len(w.versions) for w in workflows),
                "total_executions": self._total_executions,
                "successful_executions": self._successful_executions,
                "failed_executions": self._failed_executions,
                "validation_mode": str(self._validation_mode),
            }

    def clear(self) -> int:
        """Clear all workflows.

        Returns:
            Number of workflows removed.
        """
        with self._lock:
            count = len(self._workflows)
            self._workflows.clear()
            logger.info("Cleared %d workflows from module", count)
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


class WorkflowRegistrySingleton:
    """Singleton workflow registry for global access.

    Provides a single point of access for workflow registration
    across the entire application.

    Example:
        >>> registry = WorkflowRegistrySingleton.get_instance()
        >>> registry.register("my-workflow", handler=my_handler)
    """

    _instance: WorkflowRegistrySingleton | None = None
    _lock = threading.Lock()

    def __new__(cls) -> WorkflowRegistrySingleton:
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry (only once)."""
        if self._initialized:
            return
        self._module = WorkflowsModule()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> WorkflowRegistrySingleton:
        """Get the singleton instance.

        Returns:
            WorkflowRegistrySingleton instance.
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing)."""
        with cls._lock:
            cls._instance = None

    def register(
        self,
        name: str,
        handler: WorkflowHandlerType,
        version: str = "1.0.0",
        **kwargs,
    ) -> ModuleWorkflowRegistration:
        """Register a workflow (delegates to module)."""
        return self._module.register(name, handler, version, **kwargs)

    def unregister(self, name: str, version: str | None = None) -> bool:
        """Unregister a workflow (delegates to module)."""
        return self._module.unregister(name, version)

    def list(self, **kwargs) -> builtins.list[ModuleWorkflowRegistration]:
        """List workflows (delegates to module)."""
        return self._module.list(**kwargs)

    def get(self, name: str, version: str | None = None) -> ModuleWorkflowRegistration | None:
        """Get a workflow (delegates to module)."""
        return self._module.get(name, version)

    async def execute(
        self,
        name: str,
        inputs: dict[str, Any] | None = None,
        version: str | None = None,
        **kwargs,
    ) -> WorkflowExecutionResult:
        """Execute a workflow (delegates to module)."""
        return await self._module.execute(name, inputs, version, **kwargs)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics (delegates to module)."""
        return self._module.get_stats()

    def clear(self) -> int:
        """Clear all workflows (delegates to module)."""
        return self._module.clear()

    @property
    def module(self) -> WorkflowsModule:
        """Get the underlying module."""
        return self._module

    def __len__(self) -> int:
        """Get number of registered workflows."""
        return len(self._module)

    def __contains__(self, name: str) -> bool:
        """Check if workflow is registered."""
        return name in self._module
