"""REST tier deployment for Nexus platform.

This module provides lightweight REST-only deployment of workflows as HTTP APIs,
without the overhead of CLI or MCP channels.

Example:
    >>> from aegis_sdk.nexus import RESTTierDeployer, TierConfig
    >>> deployer = RESTTierDeployer()
    >>>
    >>> # Register workflow handlers
    >>> deployer.register_workflow("process-data", handler=process_data)
    >>>
    >>> # Start REST server
    >>> await deployer.start()
    >>>
    >>> # Access via HTTP:
    >>> # POST /workflows/process-data/execute
    >>> # GET /workflows
    >>> # GET /workflows/process-data/schema
    >>> # GET /health
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for workflow handlers
WorkflowHandler = Callable[..., Any | Awaitable[Any]]


class AuthMode(Enum):
    """Authentication modes for REST tier."""

    NONE = auto()
    API_KEY = auto()
    OAUTH2 = auto()
    JWT = auto()

    def __str__(self) -> str:
        """Return lowercase mode name."""
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> AuthMode:
        """Convert string to AuthMode.

        Args:
            value: String representation (case-insensitive).

        Returns:
            Corresponding AuthMode enum value.

        Raises:
            ValueError: If the string does not match any mode.
        """
        mapping = {
            "none": cls.NONE,
            "api_key": cls.API_KEY,
            "apikey": cls.API_KEY,
            "oauth2": cls.OAUTH2,
            "oauth": cls.OAUTH2,
            "jwt": cls.JWT,
            "bearer": cls.JWT,
        }
        normalized = value.lower().strip().replace("-", "_")
        if normalized not in mapping:
            valid = ", ".join(sorted(set(mapping.keys())))
            raise ValueError(f"Invalid auth mode: '{value}'. Valid values: {valid}")
        return mapping[normalized]


@dataclass
class RESTEndpoint:
    """Configuration for a REST endpoint.

    Attributes:
        path: URL path for the endpoint.
        method: HTTP method (GET, POST, etc.).
        handler: Handler function for the endpoint.
        auth_required: Whether authentication is required.
        rate_limit: Requests per minute limit (None = unlimited).
        description: Endpoint description for OpenAPI docs.
        tags: Tags for OpenAPI categorization.
    """

    path: str
    method: str
    handler: WorkflowHandler
    auth_required: bool = True
    rate_limit: int | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Validate endpoint configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if not self.path:
            errors.append("path is required")
        elif not self.path.startswith("/"):
            errors.append("path must start with '/'")

        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
        if self.method.upper() not in valid_methods:
            errors.append(f"Invalid method: {self.method}. Valid: {valid_methods}")

        if not callable(self.handler):
            errors.append("handler must be callable")

        if self.rate_limit is not None and self.rate_limit < 1:
            errors.append("rate_limit must be >= 1")

        return errors


@dataclass
class RESTConfig:
    """Configuration for REST tier deployment.

    Attributes:
        port: Port to listen on.
        host: Host to bind to.
        auth_mode: Authentication mode.
        api_key_header: Header name for API key authentication.
        cors_origins: Allowed CORS origins.
        rate_limit: Global rate limit (requests per minute).
        enable_docs: Enable OpenAPI documentation.
        docs_path: Path for OpenAPI docs.
        prefix: URL prefix for all endpoints.
        timeout_s: Request timeout in seconds.
        max_request_size_mb: Maximum request body size.
    """

    port: int = 8000
    host: str = "0.0.0.0"
    auth_mode: AuthMode = AuthMode.NONE
    api_key_header: str = "X-API-Key"
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    rate_limit: int | None = None
    enable_docs: bool = True
    docs_path: str = "/docs"
    prefix: str = ""
    timeout_s: int = 300
    max_request_size_mb: int = 10

    def validate(self) -> list[str]:
        """Validate REST configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if self.port < 1 or self.port > 65535:
            errors.append("port must be between 1 and 65535")

        if self.timeout_s < 1:
            errors.append("timeout_s must be >= 1")

        if self.max_request_size_mb < 1:
            errors.append("max_request_size_mb must be >= 1")

        if self.rate_limit is not None and self.rate_limit < 1:
            errors.append("rate_limit must be >= 1")

        if self.prefix and not self.prefix.startswith("/"):
            errors.append("prefix must start with '/'")

        return errors


@dataclass
class WorkflowSchema:
    """JSON Schema for workflow input/output.

    Attributes:
        name: Workflow name.
        version: Schema version.
        input_schema: JSON schema for inputs.
        output_schema: JSON schema for outputs.
        description: Workflow description.
    """

    name: str
    version: str = "1.0.0"
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert schema to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "name": self.name,
            "version": self.version,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "description": self.description,
        }


@dataclass
class RESTWorkflowRegistration:
    """Registered workflow for REST tier.

    Attributes:
        name: Workflow name.
        handler: Workflow handler function.
        version: Workflow version.
        description: Workflow description.
        input_schema: JSON schema for inputs.
        output_schema: JSON schema for outputs.
        auth_required: Whether authentication is required.
        rate_limit: Workflow-specific rate limit.
        timeout_s: Workflow-specific timeout.
        tags: Tags for categorization.
    """

    name: str
    handler: WorkflowHandler
    version: str = "1.0.0"
    description: str = ""
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    auth_required: bool = True
    rate_limit: int | None = None
    timeout_s: int | None = None
    tags: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Validate workflow registration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if not self.name:
            errors.append("name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("name must be alphanumeric with hyphens/underscores")

        if not callable(self.handler):
            errors.append("handler must be callable")

        if self.rate_limit is not None and self.rate_limit < 1:
            errors.append("rate_limit must be >= 1")

        if self.timeout_s is not None and self.timeout_s < 1:
            errors.append("timeout_s must be >= 1")

        return errors

    def get_schema(self) -> WorkflowSchema:
        """Get workflow schema.

        Returns:
            WorkflowSchema instance.
        """
        return WorkflowSchema(
            name=self.name,
            version=self.version,
            input_schema=self.input_schema or {},
            output_schema=self.output_schema or {},
            description=self.description,
        )


@dataclass
class ExecutionResult:
    """Result of workflow execution.

    Attributes:
        success: Whether execution succeeded.
        workflow_name: Name of the executed workflow.
        result: Execution result data.
        error: Error message if failed.
        execution_id: Unique execution identifier.
        started_at: Execution start time.
        completed_at: Execution completion time.
    """

    success: bool
    workflow_name: str
    result: Any = None
    error: str | None = None
    execution_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "success": self.success,
            "workflow_name": self.workflow_name,
            "result": self.result,
            "error": self.error,
            "execution_id": self.execution_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class RESTTierDeployer:
    """Deploys workflows as REST API only.

    Provides a lightweight HTTP API for workflow execution without
    the overhead of CLI or MCP channels.

    Example:
        >>> deployer = RESTTierDeployer(config=RESTConfig(port=8080))
        >>> deployer.register_workflow("my-workflow", handler=my_handler)
        >>> await deployer.start()

    Endpoints:
        - POST /workflows/{name}/execute - Execute a workflow
        - GET /workflows - List all workflows
        - GET /workflows/{name}/schema - Get workflow schema
        - GET /health - Health check
    """

    def __init__(
        self,
        config: RESTConfig | None = None,
        name: str = "nexus-rest",
    ):
        """Initialize REST tier deployer.

        Args:
            config: REST configuration.
            name: Deployer name for identification.
        """
        self._config = config or RESTConfig()
        self._name = name
        self._workflows: dict[str, RESTWorkflowRegistration] = {}
        self._custom_endpoints: list[RESTEndpoint] = []
        self._running = False
        self._start_time: float | None = None
        self._execution_counter = 0
        self._api_keys: set[str] = set()
        self._metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0.0,
        }
        self._on_request_hooks: list[Callable[[str, dict], None]] = []
        self._on_response_hooks: list[Callable[[str, ExecutionResult], None]] = []

    @property
    def name(self) -> str:
        """Get deployer name."""
        return self._name

    @property
    def config(self) -> RESTConfig:
        """Get REST configuration."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Check if deployer is running."""
        return self._running

    @property
    def uptime_s(self) -> float | None:
        """Get uptime in seconds."""
        if self._start_time:
            return time.time() - self._start_time
        return None

    def register_workflow(
        self,
        name: str,
        handler: WorkflowHandler,
        version: str = "1.0.0",
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        auth_required: bool = True,
        rate_limit: int | None = None,
        timeout_s: int | None = None,
        tags: list[str] | None = None,
    ) -> RESTWorkflowRegistration:
        """Register a workflow for REST deployment.

        Args:
            name: Unique workflow name.
            handler: Workflow handler function.
            version: Workflow version.
            description: Workflow description.
            input_schema: JSON schema for inputs.
            output_schema: JSON schema for outputs.
            auth_required: Whether authentication is required.
            rate_limit: Workflow-specific rate limit.
            timeout_s: Workflow-specific timeout.
            tags: Tags for categorization.

        Returns:
            RESTWorkflowRegistration instance.

        Raises:
            ValueError: If validation fails or name already exists.
        """
        if name in self._workflows:
            raise ValueError(f"Workflow already registered: {name}")

        registration = RESTWorkflowRegistration(
            name=name,
            handler=handler,
            version=version,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            auth_required=auth_required,
            rate_limit=rate_limit,
            timeout_s=timeout_s,
            tags=tags or [],
        )

        errors = registration.validate()
        if errors:
            raise ValueError(f"Invalid workflow registration: {'; '.join(errors)}")

        self._workflows[name] = registration
        logger.info("Registered REST workflow: %s", name)
        return registration

    def unregister_workflow(self, name: str) -> bool:
        """Unregister a workflow.

        Args:
            name: Workflow name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self._workflows:
            del self._workflows[name]
            logger.info("Unregistered REST workflow: %s", name)
            return True
        return False

    def get_workflow(self, name: str) -> RESTWorkflowRegistration | None:
        """Get a workflow registration.

        Args:
            name: Workflow name.

        Returns:
            RESTWorkflowRegistration or None.
        """
        return self._workflows.get(name)

    def list_workflows(self) -> list[RESTWorkflowRegistration]:
        """Get all registered workflows.

        Returns:
            List of workflow registrations.
        """
        return list(self._workflows.values())

    def add_endpoint(self, endpoint: RESTEndpoint) -> None:
        """Add a custom REST endpoint.

        Args:
            endpoint: Endpoint configuration.

        Raises:
            ValueError: If endpoint validation fails.
        """
        errors = endpoint.validate()
        if errors:
            raise ValueError(f"Invalid endpoint: {'; '.join(errors)}")

        self._custom_endpoints.append(endpoint)
        logger.debug("Added custom endpoint: %s %s", endpoint.method, endpoint.path)

    def add_api_key(self, key: str) -> None:
        """Add an API key for authentication.

        Args:
            key: API key to add.
        """
        self._api_keys.add(key)

    def remove_api_key(self, key: str) -> bool:
        """Remove an API key.

        Args:
            key: API key to remove.

        Returns:
            True if removed, False if not found.
        """
        if key in self._api_keys:
            self._api_keys.discard(key)
            return True
        return False

    def validate_api_key(self, key: str) -> bool:
        """Validate an API key.

        Args:
            key: API key to validate.

        Returns:
            True if valid.
        """
        if self._config.auth_mode == AuthMode.NONE:
            return True
        if self._config.auth_mode == AuthMode.API_KEY:
            return key in self._api_keys
        # For OAuth2/JWT, would need external validation
        return False

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID."""
        self._execution_counter += 1
        timestamp = int(time.time() * 1000)
        return f"exec-{timestamp}-{self._execution_counter}"

    async def execute_workflow(
        self,
        name: str,
        inputs: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute a registered workflow.

        Args:
            name: Workflow name to execute.
            inputs: Workflow inputs.

        Returns:
            ExecutionResult with execution outcome.
        """
        started_at = datetime.now(UTC)
        execution_id = self._generate_execution_id()
        self._metrics["total_requests"] += 1

        # Invoke request hooks
        for hook in self._on_request_hooks:
            try:
                hook(name, inputs or {})
            except Exception as e:
                logger.warning("Request hook failed: %s", e)

        if name not in self._workflows:
            result = ExecutionResult(
                success=False,
                workflow_name=name,
                error=f"Workflow not found: {name}",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_requests"] += 1
            return result

        registration = self._workflows[name]
        timeout = registration.timeout_s or self._config.timeout_s

        try:
            # Execute handler with timeout
            if asyncio.iscoroutinefunction(registration.handler):
                handler_result = await asyncio.wait_for(
                    registration.handler(inputs or {}),
                    timeout=timeout,
                )
            else:
                handler_result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        registration.handler,
                        inputs or {},
                    ),
                    timeout=timeout,
                )

            result = ExecutionResult(
                success=True,
                workflow_name=name,
                result=handler_result,
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["successful_requests"] += 1

        except TimeoutError:
            result = ExecutionResult(
                success=False,
                workflow_name=name,
                error=f"Execution timed out after {timeout}s",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_requests"] += 1

        except Exception as e:
            result = ExecutionResult(
                success=False,
                workflow_name=name,
                error="Workflow execution failed",
                execution_id=execution_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._metrics["failed_requests"] += 1
            logger.error("Workflow execution failed for %s: %s", name, e, exc_info=True)

        # Track latency
        if result.duration_ms:
            self._metrics["total_latency_ms"] += result.duration_ms

        # Invoke response hooks
        for hook in self._on_response_hooks:
            try:
                hook(name, result)
            except Exception as e:
                logger.warning("Response hook failed: %s", e)

        return result

    def get_workflow_schema(self, name: str) -> WorkflowSchema | None:
        """Get schema for a workflow.

        Args:
            name: Workflow name.

        Returns:
            WorkflowSchema or None.
        """
        registration = self._workflows.get(name)
        if registration:
            return registration.get_schema()
        return None

    def health_check(self) -> dict[str, Any]:
        """Perform health check.

        Returns:
            Health check result.
        """
        return {
            "status": "healthy" if self._running else "stopped",
            "name": self._name,
            "workflows_count": len(self._workflows),
            "uptime_s": self.uptime_s,
            "config": {
                "port": self._config.port,
                "auth_mode": str(self._config.auth_mode),
            },
        }

    async def start(self) -> None:
        """Start the REST tier.

        In a real implementation, this would start an HTTP server.
        Here we simulate the startup.
        """
        if self._running:
            logger.warning("REST tier already running")
            return

        # Validate configuration
        errors = self._config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {'; '.join(errors)}")

        self._running = True
        self._start_time = time.time()
        logger.info(
            "REST tier '%s' started on %s:%d", self._name, self._config.host, self._config.port
        )

    async def stop(self) -> None:
        """Stop the REST tier."""
        if not self._running:
            logger.warning("REST tier not running")
            return

        self._running = False
        logger.info("REST tier '%s' stopped", self._name)

    def on_request(self, callback: Callable[[str, dict], None]) -> None:
        """Register request hook.

        Args:
            callback: Function called with (workflow_name, inputs).
        """
        self._on_request_hooks.append(callback)

    def on_response(self, callback: Callable[[str, ExecutionResult], None]) -> None:
        """Register response hook.

        Args:
            callback: Function called with (workflow_name, result).
        """
        self._on_response_hooks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get deployer statistics.

        Returns:
            Dictionary with statistics.
        """
        avg_latency = 0.0
        if self._metrics["total_requests"] > 0:
            avg_latency = self._metrics["total_latency_ms"] / self._metrics["total_requests"]

        return {
            "name": self._name,
            "is_running": self._running,
            "uptime_s": self.uptime_s,
            "workflows_count": len(self._workflows),
            "custom_endpoints_count": len(self._custom_endpoints),
            "api_keys_count": len(self._api_keys),
            "metrics": {
                **self._metrics,
                "avg_latency_ms": avg_latency,
            },
        }

    def get_openapi_spec(self) -> dict[str, Any]:
        """Generate OpenAPI specification.

        Returns:
            OpenAPI 3.0 specification dictionary.
        """
        paths = {}
        prefix = self._config.prefix or ""

        # Workflow execution endpoints
        for name, registration in self._workflows.items():
            path = f"{prefix}/workflows/{name}/execute"
            paths[path] = {
                "post": {
                    "summary": f"Execute {name} workflow",
                    "description": registration.description or f"Execute the {name} workflow",
                    "tags": registration.tags or ["workflows"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": registration.input_schema or {"type": "object"},
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful execution",
                            "content": {
                                "application/json": {
                                    "schema": registration.output_schema or {"type": "object"},
                                }
                            },
                        },
                        "400": {"description": "Invalid input"},
                        "401": {"description": "Unauthorized"},
                        "500": {"description": "Execution failed"},
                    },
                }
            }

            # Schema endpoint
            schema_path = f"{prefix}/workflows/{name}/schema"
            paths[schema_path] = {
                "get": {
                    "summary": f"Get {name} schema",
                    "description": f"Get the input/output schema for {name}",
                    "tags": ["schemas"],
                    "responses": {
                        "200": {
                            "description": "Schema retrieved",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        },
                        "404": {"description": "Workflow not found"},
                    },
                }
            }

        # List workflows
        paths[f"{prefix}/workflows"] = {
            "get": {
                "summary": "List all workflows",
                "description": "Get a list of all registered workflows",
                "tags": ["workflows"],
                "responses": {
                    "200": {
                        "description": "Workflows list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                }
                            }
                        },
                    }
                },
            }
        }

        # Health endpoint
        paths[f"{prefix}/health"] = {
            "get": {
                "summary": "Health check",
                "description": "Check the health status of the REST tier",
                "tags": ["health"],
                "responses": {
                    "200": {
                        "description": "Healthy",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }

        return {
            "openapi": "3.0.0",
            "info": {
                "title": self._name,
                "version": "1.0.0",
                "description": "Nexus REST Tier API",
            },
            "servers": [{"url": f"http://{self._config.host}:{self._config.port}"}],
            "paths": paths,
        }

    def __len__(self) -> int:
        """Get number of registered workflows."""
        return len(self._workflows)

    def __contains__(self, name: str) -> bool:
        """Check if workflow is registered."""
        return name in self._workflows
