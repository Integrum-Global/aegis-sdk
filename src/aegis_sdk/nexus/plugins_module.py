"""Plugins Module for Nexus v1.1 - Dynamic plugin loading and lifecycle management.

This module provides enhanced plugin management capabilities including:
- Dynamic plugin loading/unloading at runtime
- Plugin lifecycle: load -> initialize -> activate -> deactivate -> unload
- Plugin discovery from directory
- Plugin isolation (errors don't crash Nexus)
- Plugin configuration management
- Global plugin registry singleton

Example:
    >>> from aegis_sdk.nexus import PluginsModule, PluginBase
    >>>
    >>> # Create plugins module
    >>> module = PluginsModule(plugins_dir="/path/to/plugins")
    >>>
    >>> # Create a custom plugin
    >>> class MyPlugin(PluginBase):
    ...     async def on_request(self, request_id, workflow_name, inputs, **kwargs):
    ...         return {"modified": True}
    >>>
    >>> # Load and activate
    >>> module.load(MyPlugin())
    >>> module.activate("my-plugin")
    >>>
    >>> # Execute lifecycle hooks
    >>> results = await module.on_request("req-1", "my-workflow", {"value": 42})
"""

from __future__ import annotations

import asyncio
import builtins
import importlib.util
import inspect
import logging
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
)

logger = logging.getLogger(__name__)


class PluginLifecycleState(Enum):
    """Plugin lifecycle states."""

    UNLOADED = auto()
    LOADED = auto()
    INITIALIZED = auto()
    ACTIVE = auto()
    DEACTIVATED = auto()
    ERROR = auto()

    def __str__(self) -> str:
        """Return lowercase state name."""
        return self.name.lower()

    @property
    def can_activate(self) -> bool:
        """Check if plugin can be activated from this state."""
        return self in (
            PluginLifecycleState.LOADED,
            PluginLifecycleState.INITIALIZED,
            PluginLifecycleState.DEACTIVATED,
        )

    @property
    def can_deactivate(self) -> bool:
        """Check if plugin can be deactivated from this state."""
        return self == PluginLifecycleState.ACTIVE


class PluginPriority(Enum):
    """Plugin execution priority levels."""

    FIRST = 1
    EARLY = 25
    NORMAL = 50
    LATE = 75
    LAST = 100

    def __lt__(self, other: PluginPriority) -> bool:
        """Compare priorities for sorting."""
        if isinstance(other, PluginPriority):
            return self.value < other.value
        return NotImplemented


@dataclass
class PluginInfo:
    """Plugin metadata and configuration information.

    Attributes:
        name: Unique plugin identifier.
        version: Semantic version string.
        description: Plugin description.
        author: Plugin author.
        homepage: Plugin homepage URL.
        license: Plugin license.
        priority: Execution priority.
        enabled: Whether plugin is enabled.
        dependencies: Required plugin names.
        tags: Categorization tags.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = ""
    priority: PluginPriority = PluginPriority.NORMAL
    enabled: bool = True
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert info to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "license": self.license,
            "priority": self.priority.name.lower(),
            "enabled": self.enabled,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


@dataclass
class PluginConfig:
    """Plugin-specific configuration.

    Attributes:
        enabled: Whether plugin is enabled.
        settings: Plugin-specific settings dictionary.
        environment: Environment-specific overrides.
    """

    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)
    environment: str = "production"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            Setting value or default.
        """
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value.

        Args:
            key: Setting key.
            value: Setting value.
        """
        self.settings[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "settings": self.settings,
            "environment": self.environment,
        }


@dataclass
class PluginExecutionResult:
    """Result of plugin hook execution.

    Attributes:
        plugin_name: Name of the plugin.
        hook_name: Name of the hook.
        success: Whether execution succeeded.
        result: Hook return value.
        error: Error message if failed.
        latency_ms: Execution time in milliseconds.
        timestamp: When hook was executed.
    """

    plugin_name: str
    hook_name: str
    success: bool = True
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "plugin_name": self.plugin_name,
            "hook_name": self.hook_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class PluginBase(ABC):
    """Abstract base class for Nexus plugins.

    Plugins must inherit from this class and implement lifecycle hooks.
    All hooks are optional except for the info property.

    Example:
        >>> class MyPlugin(PluginBase):
        ...     @property
        ...     def info(self) -> PluginInfo:
        ...         return PluginInfo(
        ...             name="my-plugin",
        ...             version="1.0.0",
        ...             description="My custom plugin"
        ...         )
        ...
        ...     async def on_load(self) -> None:
        ...         print("Plugin loaded")
        ...
        ...     async def on_request(self, request_id, workflow_name, inputs, **kwargs):
        ...         return {"intercepted": True}
    """

    def __init__(self):
        """Initialize plugin base."""
        self._state = PluginLifecycleState.UNLOADED
        self._config = PluginConfig()
        self._load_time: datetime | None = None
        self._error: str | None = None
        self._execution_count = 0
        self._error_count = 0

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Get plugin metadata information.

        Returns:
            PluginInfo instance.
        """
        pass

    @property
    def name(self) -> str:
        """Get plugin name."""
        return self.info.name

    @property
    def version(self) -> str:
        """Get plugin version."""
        return self.info.version

    @property
    def state(self) -> PluginLifecycleState:
        """Get current plugin state."""
        return self._state

    @state.setter
    def state(self, value: PluginLifecycleState) -> None:
        """Set plugin state."""
        self._state = value

    @property
    def config(self) -> PluginConfig:
        """Get plugin configuration."""
        return self._config

    @config.setter
    def config(self, value: PluginConfig) -> None:
        """Set plugin configuration."""
        self._config = value

    @property
    def is_active(self) -> bool:
        """Check if plugin is active."""
        return self._state == PluginLifecycleState.ACTIVE

    # Lifecycle hooks — optional no-op defaults; subclasses override
    # selectively. Intentionally NOT @abstractmethod (would force every
    # plugin to implement all four). noqa B027 is the correct disposition.

    async def on_load(self) -> None:  # noqa: B027
        """Called when plugin is loaded.

        Initialize resources, validate configuration, etc.
        """
        pass

    async def on_activate(self) -> None:  # noqa: B027
        """Called when plugin is activated.

        Start processing, register handlers, etc.
        """
        pass

    async def on_deactivate(self) -> None:  # noqa: B027
        """Called when plugin is deactivated.

        Stop processing, unregister handlers, etc.
        """
        pass

    async def on_unload(self) -> None:  # noqa: B027
        """Called when plugin is unloaded.

        Clean up resources, close connections, etc.
        """
        pass

    # Request/Response hooks

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any] | None:
        """Called before workflow execution.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow to execute.
            inputs: Workflow input parameters.
            **kwargs: Additional context (session_id, channel, etc.).

        Returns:
            Optional modified inputs or None to pass through unchanged.
        """
        return None

    async def on_response(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        outputs: Any,
        **kwargs,
    ) -> Any | None:
        """Called after workflow execution.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the executed workflow.
            inputs: Original workflow inputs.
            outputs: Workflow outputs.
            **kwargs: Additional context.

        Returns:
            Optional modified outputs or None to pass through unchanged.
        """
        return None

    async def on_error(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> Exception | None:
        """Called when workflow execution fails.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the failed workflow.
            inputs: Original workflow inputs.
            error: The exception that occurred.
            **kwargs: Additional context.

        Returns:
            Optional modified exception or None to pass through unchanged.
        """
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert plugin to dictionary representation."""
        return {
            "info": self.info.to_dict(),
            "state": str(self._state),
            "config": self._config.to_dict(),
            "load_time": self._load_time.isoformat() if self._load_time else None,
            "error": self._error,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
        }


@dataclass
class PluginRegistration:
    """Internal registration for a loaded plugin.

    Attributes:
        plugin: The plugin instance.
        loaded_at: When plugin was loaded.
        activated_at: When plugin was activated.
        source_path: Path to plugin file (if loaded from directory).
        namespace: Isolated namespace for plugin.
    """

    plugin: PluginBase
    loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    activated_at: datetime | None = None
    source_path: str | None = None
    namespace: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Get plugin name."""
        return self.plugin.name

    @property
    def state(self) -> PluginLifecycleState:
        """Get plugin state."""
        return self.plugin.state

    @property
    def is_active(self) -> bool:
        """Check if plugin is active."""
        return self.plugin.is_active


class PluginsModule:
    """Enhanced plugin management module for Nexus v1.1.

    Provides dynamic plugin loading, lifecycle management, and
    isolated execution for platform extensibility.

    Example:
        >>> module = PluginsModule()
        >>> module.load(MyPlugin())
        >>> module.activate("my-plugin")
        >>> results = await module.on_request("req-1", "workflow", {"value": 42})
    """

    def __init__(
        self,
        plugins_dir: str | None = None,
        auto_discover: bool = False,
        auto_activate: bool = False,
        isolation_enabled: bool = True,
        default_timeout_s: float = 30.0,
    ):
        """Initialize plugins module.

        Args:
            plugins_dir: Directory to scan for plugins.
            auto_discover: Whether to auto-discover plugins on init.
            auto_activate: Whether to auto-activate discovered plugins.
            isolation_enabled: Whether to isolate plugin errors.
            default_timeout_s: Default timeout for plugin operations.
        """
        self._plugins_dir = plugins_dir
        self._auto_discover = auto_discover
        self._auto_activate = auto_activate
        self._isolation_enabled = isolation_enabled
        self._default_timeout_s = default_timeout_s

        self._registrations: dict[str, PluginRegistration] = {}
        self._active_plugins: set[str] = set()
        self._lock = threading.RLock()
        self._start_time = time.time()

        # Configuration management
        self._configs: dict[str, PluginConfig] = {}

        # Event hooks
        self._on_load_hooks: list[Callable[[str, PluginBase], None]] = []
        self._on_activate_hooks: list[Callable[[str, PluginBase], None]] = []
        self._on_deactivate_hooks: list[Callable[[str, PluginBase], None]] = []
        self._on_unload_hooks: list[Callable[[str, PluginBase], None]] = []
        self._on_error_hooks: list[Callable[[str, str, Exception], None]] = []

        # Statistics
        self._total_executions = 0
        self._successful_executions = 0
        self._failed_executions = 0

        # Auto-discover if enabled
        if self._auto_discover and self._plugins_dir:
            self.discover()

    @property
    def uptime_s(self) -> float:
        """Get module uptime in seconds."""
        return time.time() - self._start_time

    # Plugin Loading

    def load(
        self,
        plugin: PluginBase,
        config: PluginConfig | None = None,
        source_path: str | None = None,
    ) -> bool:
        """Load a plugin into the module.

        Args:
            plugin: Plugin instance to load.
            config: Optional plugin configuration.
            source_path: Optional source file path.

        Returns:
            True if loaded successfully, False otherwise.

        Raises:
            ValueError: If plugin validation fails.
        """
        with self._lock:
            name = plugin.name

            # Validate
            if not name:
                raise ValueError("Plugin must have a name")
            if name in self._registrations:
                raise ValueError(f"Plugin already loaded: {name}")

            # Check dependencies - must be loaded (not necessarily active yet)
            for dep in plugin.info.dependencies:
                if dep not in self._registrations:
                    raise ValueError(f"Missing dependency: {dep}")

            # Apply configuration
            if config:
                plugin.config = config
            elif name in self._configs:
                plugin.config = self._configs[name]

            # Create registration
            registration = PluginRegistration(
                plugin=plugin,
                source_path=source_path,
            )

            # Execute load hook with isolation
            self._run_lifecycle_hook_sync(plugin, "on_load")

            # Update state
            plugin.state = PluginLifecycleState.LOADED
            plugin._load_time = datetime.now(UTC)
            self._registrations[name] = registration

            # Invoke hooks
            for hook in self._on_load_hooks:
                try:
                    hook(name, plugin)
                except Exception as e:
                    logger.warning("Load hook failed for %s: %s", name, e)

            logger.info("Loaded plugin: %s v%s", name, plugin.version)

            # Auto-activate if configured
            if self._auto_activate and plugin.config.enabled:
                self.activate(name)

            return True

    def unload(self, name: str) -> bool:
        """Unload a plugin from the module.

        Args:
            name: Plugin name to unload.

        Returns:
            True if unloaded, False if not found.
        """
        with self._lock:
            if name not in self._registrations:
                return False

            registration = self._registrations[name]
            plugin = registration.plugin

            # Check if other plugins depend on this one
            for other_name, other_reg in self._registrations.items():
                if other_name != name and name in other_reg.plugin.info.dependencies:
                    if other_reg.is_active:
                        raise ValueError(
                            f"Cannot unload {name}: required by active plugin {other_name}"
                        )

            # Deactivate first if active
            if name in self._active_plugins:
                self.deactivate(name)

            # Execute unload hook
            self._run_lifecycle_hook_sync(plugin, "on_unload")

            # Update state
            plugin.state = PluginLifecycleState.UNLOADED

            # Invoke hooks
            for hook in self._on_unload_hooks:
                try:
                    hook(name, plugin)
                except Exception as e:
                    logger.warning("Unload hook failed for %s: %s", name, e)

            # Remove registration
            del self._registrations[name]
            logger.info("Unloaded plugin: %s", name)
            return True

    def reload(self, name: str) -> bool:
        """Reload a plugin (unload then load again).

        Useful for development and hot-reloading.

        Args:
            name: Plugin name to reload.

        Returns:
            True if reloaded, False if not found.
        """
        with self._lock:
            if name not in self._registrations:
                return False

            registration = self._registrations[name]
            plugin = registration.plugin
            was_active = name in self._active_plugins
            source_path = registration.source_path
            config = plugin.config

            # Unload
            self.unload(name)

            # Reload from source if available
            if source_path:
                loaded = self.load_from_file(source_path, config)
                if loaded and was_active:
                    self.activate(name)
                return loaded
            else:
                # Can't reload instance-based plugin
                logger.warning("Cannot reload plugin %s: no source path", name)
                return False

    # Plugin Activation

    def activate(self, name: str) -> bool:
        """Activate a loaded plugin.

        Args:
            name: Plugin name to activate.

        Returns:
            True if activated, False otherwise.
        """
        with self._lock:
            if name not in self._registrations:
                return False

            registration = self._registrations[name]
            plugin = registration.plugin

            if not plugin.state.can_activate:
                logger.warning("Cannot activate plugin %s in state %s", name, plugin.state)
                return False

            # Activate dependencies first
            for dep in plugin.info.dependencies:
                if dep not in self._active_plugins:
                    if not self.activate(dep):
                        return False

            # Execute activate hook
            self._run_lifecycle_hook_sync(plugin, "on_activate")

            # Update state
            plugin.state = PluginLifecycleState.ACTIVE
            registration.activated_at = datetime.now(UTC)
            self._active_plugins.add(name)

            # Invoke hooks
            for hook in self._on_activate_hooks:
                try:
                    hook(name, plugin)
                except Exception as e:
                    logger.warning("Activate hook failed for %s: %s", name, e)

            logger.info("Activated plugin: %s", name)
            return True

    def deactivate(self, name: str) -> bool:
        """Deactivate an active plugin.

        Args:
            name: Plugin name to deactivate.

        Returns:
            True if deactivated, False otherwise.
        """
        with self._lock:
            if name not in self._registrations:
                return False

            registration = self._registrations[name]
            plugin = registration.plugin

            if not plugin.state.can_deactivate:
                logger.warning("Cannot deactivate plugin %s in state %s", name, plugin.state)
                return False

            # Check if other active plugins depend on this one
            for other_name, other_reg in self._registrations.items():
                if other_name != name and name in other_reg.plugin.info.dependencies:
                    if other_reg.is_active:
                        raise ValueError(
                            f"Cannot deactivate {name}: required by active plugin {other_name}"
                        )

            # Execute deactivate hook
            self._run_lifecycle_hook_sync(plugin, "on_deactivate")

            # Update state
            plugin.state = PluginLifecycleState.DEACTIVATED
            self._active_plugins.discard(name)

            # Invoke hooks
            for hook in self._on_deactivate_hooks:
                try:
                    hook(name, plugin)
                except Exception as e:
                    logger.warning("Deactivate hook failed for %s: %s", name, e)

            logger.info("Deactivated plugin: %s", name)
            return True

    def _run_lifecycle_hook_sync(self, plugin: PluginBase, hook_name: str) -> None:
        """Run a lifecycle hook synchronously, handling async hooks properly.

        Args:
            plugin: Plugin instance.
            hook_name: Name of the lifecycle hook.
        """
        hook = getattr(plugin, hook_name, None)
        if hook is None:
            return

        try:
            if asyncio.iscoroutinefunction(hook):
                # Check if we're in an async context
                try:
                    asyncio.get_running_loop()
                    # We're in an async context, schedule the hook
                    # Create a new task and let it run
                    import threading

                    # Run in a separate thread to avoid blocking
                    def run_hook():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            new_loop.run_until_complete(
                                asyncio.wait_for(hook(), timeout=self._default_timeout_s)
                            )
                        finally:
                            new_loop.close()

                    thread = threading.Thread(target=run_hook)
                    thread.start()
                    thread.join(timeout=self._default_timeout_s)

                except RuntimeError:
                    # No running loop, we can create one
                    asyncio.run(asyncio.wait_for(hook(), timeout=self._default_timeout_s))
            else:
                hook()
        except TimeoutError:
            error_msg = f"Plugin {plugin.name} {hook_name} timed out"
            plugin._error = error_msg
            plugin.state = PluginLifecycleState.ERROR
            if not self._isolation_enabled:
                raise TimeoutError(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Plugin {plugin.name} {hook_name} failed: {e}"
            plugin._error = str(e)
            plugin.state = PluginLifecycleState.ERROR
            if not self._isolation_enabled:
                raise
            logger.error(error_msg)
            for hook_fn in self._on_error_hooks:
                try:
                    hook_fn(plugin.name, hook_name, e)
                except Exception as hook_error:
                    logger.warning("Error hook failed: %s", hook_error)

    async def _execute_lifecycle_hook(
        self,
        plugin: PluginBase,
        hook_name: str,
    ) -> None:
        """Execute a plugin lifecycle hook with isolation.

        Args:
            plugin: Plugin instance.
            hook_name: Name of the lifecycle hook.
        """
        hook = getattr(plugin, hook_name, None)
        if hook is None:
            return

        try:
            if asyncio.iscoroutinefunction(hook):
                await asyncio.wait_for(
                    hook(),
                    timeout=self._default_timeout_s,
                )
            else:
                hook()
        except TimeoutError:
            error_msg = f"Plugin {plugin.name} {hook_name} timed out"
            plugin._error = error_msg
            plugin.state = PluginLifecycleState.ERROR
            if not self._isolation_enabled:
                raise TimeoutError(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Plugin {plugin.name} {hook_name} failed: {e}"
            plugin._error = str(e)
            plugin.state = PluginLifecycleState.ERROR
            if not self._isolation_enabled:
                raise
            logger.error(error_msg)
            for hook_fn in self._on_error_hooks:
                try:
                    hook_fn(plugin.name, hook_name, e)
                except Exception as hook_error:
                    logger.warning("Error hook failed: %s", hook_error)

    # Plugin Discovery

    def discover(self, plugins_dir: str | None = None) -> builtins.list[str]:
        """Discover and load plugins from a directory.

        Args:
            plugins_dir: Directory to scan (uses module default if None).

        Returns:
            List of discovered plugin names.
        """
        target_dir = plugins_dir or self._plugins_dir
        if not target_dir:
            return []

        discovered = []
        plugins_path = Path(target_dir)

        if not plugins_path.exists() or not plugins_path.is_dir():
            logger.warning("Plugins directory not found: %s", target_dir)
            return []

        # Scan for Python files
        for py_file in plugins_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                loaded_name = self.load_from_file(str(py_file))
                if loaded_name:
                    discovered.append(loaded_name)
            except Exception as e:
                logger.error("Failed to load plugin from %s: %s", py_file, e)

        logger.info("Discovered %s plugins from %s", len(discovered), target_dir)
        return discovered

    def load_from_file(
        self,
        file_path: str,
        config: PluginConfig | None = None,
    ) -> str | None:
        """Load a plugin from a Python file.

        Args:
            file_path: Path to the plugin file.
            config: Optional plugin configuration.

        Returns:
            Plugin name if loaded, None otherwise.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("Plugin file not found: %s", file_path)
            return None

        # Generate unique module name
        module_name = f"nexus_plugin_{path.stem}_{id(path)}"

        try:
            # Load module with isolation
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.error("Cannot load plugin spec from %s", file_path)
                return None

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules temporarily for imports to work
            old_module = sys.modules.get(module_name)
            sys.modules[module_name] = module

            try:
                spec.loader.exec_module(module)
            finally:
                if old_module is not None:
                    sys.modules[module_name] = old_module
                else:
                    sys.modules.pop(module_name, None)

            # Find plugin class
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    plugin_class = attr
                    break

            if plugin_class is None:
                logger.warning("No PluginBase subclass found in %s", file_path)
                return None

            # Instantiate and load
            plugin = plugin_class()
            self.load(plugin, config=config, source_path=file_path)
            return plugin.name

        except Exception as e:
            logger.error("Failed to load plugin from %s: %s", file_path, e)
            if not self._isolation_enabled:
                raise
            return None

    # Plugin Access

    def get(self, name: str) -> PluginBase | None:
        """Get a loaded plugin by name.

        Args:
            name: Plugin name.

        Returns:
            Plugin instance or None.
        """
        registration = self._registrations.get(name)
        return registration.plugin if registration else None

    def list(
        self,
        active_only: bool = False,
        tags: builtins.list[str] | None = None,
    ) -> builtins.list[PluginBase]:
        """List loaded plugins with optional filtering.

        Args:
            active_only: Only return active plugins.
            tags: Filter by tags.

        Returns:
            List of plugin instances.
        """
        with self._lock:
            plugins = [reg.plugin for reg in self._registrations.values()]

            if active_only:
                plugins = [p for p in plugins if p.is_active]

            if tags:
                tags_lower = [t.lower() for t in tags]
                plugins = [p for p in plugins if any(t.lower() in tags_lower for t in p.info.tags)]

            return plugins

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded.

        Args:
            name: Plugin name.

        Returns:
            True if loaded.
        """
        return name in self._registrations

    def is_active(self, name: str) -> bool:
        """Check if a plugin is active.

        Args:
            name: Plugin name.

        Returns:
            True if active.
        """
        return name in self._active_plugins

    # Request/Response Hooks Execution

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> builtins.list[PluginExecutionResult]:
        """Execute on_request hooks for all active plugins.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Workflow inputs.
            **kwargs: Additional context.

        Returns:
            List of execution results.
        """
        return await self._execute_hook(
            "on_request",
            request_id=request_id,
            workflow_name=workflow_name,
            inputs=inputs,
            **kwargs,
        )

    async def on_response(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        outputs: Any,
        **kwargs,
    ) -> builtins.list[PluginExecutionResult]:
        """Execute on_response hooks for all active plugins.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original workflow inputs.
            outputs: Workflow outputs.
            **kwargs: Additional context.

        Returns:
            List of execution results.
        """
        return await self._execute_hook(
            "on_response",
            request_id=request_id,
            workflow_name=workflow_name,
            inputs=inputs,
            outputs=outputs,
            **kwargs,
        )

    async def on_error(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> builtins.list[PluginExecutionResult]:
        """Execute on_error hooks for all active plugins.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original workflow inputs.
            error: The exception that occurred.
            **kwargs: Additional context.

        Returns:
            List of execution results.
        """
        return await self._execute_hook(
            "on_error",
            request_id=request_id,
            workflow_name=workflow_name,
            inputs=inputs,
            error=error,
            **kwargs,
        )

    async def _execute_hook(
        self,
        hook_name: str,
        **kwargs,
    ) -> builtins.list[PluginExecutionResult]:
        """Execute a hook across all active plugins.

        Args:
            hook_name: Name of the hook to execute.
            **kwargs: Hook arguments.

        Returns:
            List of execution results.
        """
        results = []

        # Get active plugins sorted by priority
        with self._lock:
            active_plugins = [
                self._registrations[name].plugin
                for name in self._active_plugins
                if name in self._registrations
            ]

        active_plugins.sort(key=lambda p: p.info.priority.value)

        for plugin in active_plugins:
            hook = getattr(plugin, hook_name, None)
            if hook is None:
                continue

            start_time = time.time()
            self._total_executions += 1
            plugin._execution_count += 1

            try:
                if asyncio.iscoroutinefunction(hook):
                    result = await asyncio.wait_for(
                        hook(**kwargs),
                        timeout=self._default_timeout_s,
                    )
                else:
                    result = hook(**kwargs)

                latency_ms = (time.time() - start_time) * 1000
                self._successful_executions += 1

                results.append(
                    PluginExecutionResult(
                        plugin_name=plugin.name,
                        hook_name=hook_name,
                        success=True,
                        result=result,
                        latency_ms=latency_ms,
                    )
                )

            except TimeoutError:
                latency_ms = (time.time() - start_time) * 1000
                self._failed_executions += 1
                plugin._error_count += 1

                error_msg = f"Plugin {plugin.name} {hook_name} timed out"
                logger.error(error_msg)

                results.append(
                    PluginExecutionResult(
                        plugin_name=plugin.name,
                        hook_name=hook_name,
                        success=False,
                        error=error_msg,
                        latency_ms=latency_ms,
                    )
                )

                if not self._isolation_enabled:
                    raise

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                self._failed_executions += 1
                plugin._error_count += 1

                logger.error("Plugin %s %s failed: %s", plugin.name, hook_name, e, exc_info=True)

                results.append(
                    PluginExecutionResult(
                        plugin_name=plugin.name,
                        hook_name=hook_name,
                        success=False,
                        error="Plugin execution failed",
                        latency_ms=latency_ms,
                    )
                )

                # Invoke error hooks
                for error_hook in self._on_error_hooks:
                    try:
                        error_hook(plugin.name, hook_name, e)
                    except Exception as hook_error:
                        logger.warning("Error hook failed: %s", hook_error)

                if not self._isolation_enabled:
                    raise

        return results

    # Configuration Management

    def set_config(self, name: str, config: PluginConfig) -> bool:
        """Set configuration for a plugin.

        Args:
            name: Plugin name.
            config: Plugin configuration.

        Returns:
            True if set, False if plugin not found.
        """
        with self._lock:
            self._configs[name] = config

            if name in self._registrations:
                self._registrations[name].plugin.config = config
                return True
            return False

    def get_config(self, name: str) -> PluginConfig | None:
        """Get configuration for a plugin.

        Args:
            name: Plugin name.

        Returns:
            PluginConfig or None.
        """
        if name in self._registrations:
            return self._registrations[name].plugin.config
        return self._configs.get(name)

    # Event Hooks

    def on_plugin_load(self, callback: Callable[[str, PluginBase], None]) -> None:
        """Register callback for plugin load events."""
        self._on_load_hooks.append(callback)

    def on_plugin_activate(self, callback: Callable[[str, PluginBase], None]) -> None:
        """Register callback for plugin activate events."""
        self._on_activate_hooks.append(callback)

    def on_plugin_deactivate(self, callback: Callable[[str, PluginBase], None]) -> None:
        """Register callback for plugin deactivate events."""
        self._on_deactivate_hooks.append(callback)

    def on_plugin_unload(self, callback: Callable[[str, PluginBase], None]) -> None:
        """Register callback for plugin unload events."""
        self._on_unload_hooks.append(callback)

    def on_plugin_error(self, callback: Callable[[str, str, Exception], None]) -> None:
        """Register callback for plugin error events."""
        self._on_error_hooks.append(callback)

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """Get module statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._lock:
            plugins = list(self._registrations.values())
            return {
                "total_plugins": len(plugins),
                "active_plugins": len(self._active_plugins),
                "plugins_by_state": {
                    str(state): len([p for p in plugins if p.state == state])
                    for state in PluginLifecycleState
                },
                "total_executions": self._total_executions,
                "successful_executions": self._successful_executions,
                "failed_executions": self._failed_executions,
                "uptime_s": self.uptime_s,
                "isolation_enabled": self._isolation_enabled,
                "auto_discover": self._auto_discover,
                "plugins_dir": self._plugins_dir,
            }

    def clear(self) -> int:
        """Unload all plugins.

        Returns:
            Number of plugins unloaded.
        """
        with self._lock:
            count = len(self._registrations)
            names = list(self._registrations.keys())

            # Unload in reverse dependency order
            for name in reversed(names):
                try:
                    self.unload(name)
                except Exception as e:
                    logger.error("Failed to unload %s: %s", name, e)

            self._registrations.clear()
            self._active_plugins.clear()
            logger.info("Cleared %d plugins", count)
            return count

    def __len__(self) -> int:
        """Get number of loaded plugins."""
        return len(self._registrations)

    def __contains__(self, name: str) -> bool:
        """Check if plugin is loaded."""
        return name in self._registrations

    def __iter__(self):
        """Iterate over loaded plugins."""
        return iter(reg.plugin for reg in self._registrations.values())


class PluginsModuleSingleton:
    """Singleton plugins module for global access.

    Provides a single point of access for plugin management
    across the entire application.

    Example:
        >>> registry = PluginsModuleSingleton.get_instance()
        >>> registry.load(MyPlugin())
        >>> registry.activate("my-plugin")
    """

    _instance: PluginsModuleSingleton | None = None
    _lock = threading.Lock()

    def __new__(cls) -> PluginsModuleSingleton:
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
        self._module = PluginsModule()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> PluginsModuleSingleton:
        """Get the singleton instance.

        Returns:
            PluginsModuleSingleton instance.
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing)."""
        with cls._lock:
            if cls._instance is not None and cls._instance._initialized:
                cls._instance._module.clear()
            cls._instance = None

    # Delegation methods

    def load(
        self,
        plugin: PluginBase,
        config: PluginConfig | None = None,
    ) -> bool:
        """Load a plugin (delegates to module)."""
        return self._module.load(plugin, config)

    def unload(self, name: str) -> bool:
        """Unload a plugin (delegates to module)."""
        return self._module.unload(name)

    def reload(self, name: str) -> bool:
        """Reload a plugin (delegates to module)."""
        return self._module.reload(name)

    def activate(self, name: str) -> bool:
        """Activate a plugin (delegates to module)."""
        return self._module.activate(name)

    def deactivate(self, name: str) -> bool:
        """Deactivate a plugin (delegates to module)."""
        return self._module.deactivate(name)

    def discover(self, plugins_dir: str | None = None) -> builtins.list[str]:
        """Discover plugins (delegates to module)."""
        return self._module.discover(plugins_dir)

    def get(self, name: str) -> PluginBase | None:
        """Get a plugin (delegates to module)."""
        return self._module.get(name)

    def list(self, **kwargs) -> builtins.list[PluginBase]:
        """List plugins (delegates to module)."""
        return self._module.list(**kwargs)

    async def on_request(self, *args, **kwargs) -> builtins.list[PluginExecutionResult]:
        """Execute on_request (delegates to module)."""
        return await self._module.on_request(*args, **kwargs)

    async def on_response(self, *args, **kwargs) -> builtins.list[PluginExecutionResult]:
        """Execute on_response (delegates to module)."""
        return await self._module.on_response(*args, **kwargs)

    async def on_error(self, *args, **kwargs) -> builtins.list[PluginExecutionResult]:
        """Execute on_error (delegates to module)."""
        return await self._module.on_error(*args, **kwargs)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics (delegates to module)."""
        return self._module.get_stats()

    def clear(self) -> int:
        """Clear plugins (delegates to module)."""
        return self._module.clear()

    @property
    def module(self) -> PluginsModule:
        """Get the underlying module."""
        return self._module

    def __len__(self) -> int:
        """Get number of loaded plugins."""
        return len(self._module)

    def __contains__(self, name: str) -> bool:
        """Check if plugin is loaded."""
        return name in self._module
