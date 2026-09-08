"""Plugin system for Nexus platform extensibility.

This module provides a plugin architecture for extending Nexus functionality
through hooks, middleware, and custom behaviors.

Example:
    >>> from aegis_sdk.nexus import PluginManager, Plugin
    >>> manager = PluginManager()
    >>>
    >>> # Create a plugin
    >>> plugin = Plugin(
    ...     name="logging-plugin",
    ...     version="1.0.0",
    ...     hooks={
    ...         "request:before": log_request,
    ...         "request:after": log_response,
    ...     }
    ... )
    >>>
    >>> # Register and enable
    >>> manager.register(plugin)
    >>> manager.enable("logging-plugin")
    >>>
    >>> # Execute hooks
    >>> results = await manager.execute_hook("request:before", request=req)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for hook functions
HookFunction = Callable[..., Any | Awaitable[Any]]


class PluginState(Enum):
    """Plugin lifecycle states."""

    REGISTERED = auto()
    ENABLED = auto()
    DISABLED = auto()
    ERROR = auto()

    def __str__(self) -> str:
        """Return lowercase state name."""
        return self.name.lower()


class HookPriority(Enum):
    """Hook execution priority levels."""

    FIRST = 1
    EARLY = 25
    NORMAL = 50
    LATE = 75
    LAST = 100

    def __lt__(self, other: HookPriority) -> bool:
        """Compare priorities."""
        if isinstance(other, HookPriority):
            return self.value < other.value
        return NotImplemented


@dataclass
class PluginMetadata:
    """Plugin metadata information.

    Attributes:
        author: Plugin author name.
        description: Plugin description.
        homepage: Plugin homepage URL.
        license: Plugin license.
        created_at: When plugin was registered.
        updated_at: When plugin was last modified.
    """

    author: str = ""
    description: str = ""
    homepage: str = ""
    license: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class HookRegistration:
    """Registered hook metadata.

    Attributes:
        hook_name: Name of the hook.
        handler: Hook handler function.
        priority: Execution priority.
        plugin_name: Name of the plugin that registered this hook.
    """

    hook_name: str
    handler: HookFunction
    priority: HookPriority = HookPriority.NORMAL
    plugin_name: str = ""


@dataclass
class Plugin:
    """Plugin definition for Nexus extensibility.

    Plugins can provide hooks for various lifecycle events,
    middleware for request processing, and custom behaviors.

    Attributes:
        name: Unique plugin identifier.
        version: Semantic version string.
        hooks: Dictionary of hook name to handler function.
        enabled: Whether the plugin is enabled.
        state: Current plugin state.
        metadata: Plugin metadata.
        dependencies: List of required plugin names.
        config: Plugin configuration options.
        priority: Default hook priority for this plugin.
    """

    name: str
    version: str
    hooks: dict[str, HookFunction] = field(default_factory=dict)
    enabled: bool = True
    state: PluginState = PluginState.REGISTERED
    metadata: PluginMetadata = field(default_factory=PluginMetadata)
    dependencies: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    priority: HookPriority = HookPriority.NORMAL

    def validate(self) -> list[str]:
        """Validate plugin configuration.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []

        if not self.name:
            errors.append("name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("name must be alphanumeric with hyphens/underscores")
        elif len(self.name) > 64:
            errors.append("name must be <= 64 characters")

        if not self.version:
            errors.append("version is required")

        for hook_name, handler in self.hooks.items():
            if not callable(handler):
                errors.append(f"hook '{hook_name}' must be callable")

        return errors

    def get_hook(self, hook_name: str) -> HookFunction | None:
        """Get a hook handler by name.

        Args:
            hook_name: Hook name to retrieve.

        Returns:
            Hook handler or None.
        """
        return self.hooks.get(hook_name)

    def has_hook(self, hook_name: str) -> bool:
        """Check if plugin has a specific hook.

        Args:
            hook_name: Hook name to check.

        Returns:
            True if hook exists.
        """
        return hook_name in self.hooks

    def to_dict(self) -> dict[str, Any]:
        """Convert plugin to dictionary representation.

        Returns:
            Dictionary representation of the plugin.
        """
        return {
            "name": self.name,
            "version": self.version,
            "hooks": list(self.hooks.keys()),
            "enabled": self.enabled,
            "state": str(self.state),
            "metadata": {
                "author": self.metadata.author,
                "description": self.metadata.description,
                "homepage": self.metadata.homepage,
                "license": self.metadata.license,
                "created_at": self.metadata.created_at.isoformat(),
            },
            "dependencies": self.dependencies,
            "priority": self.priority.name.lower(),
        }


@dataclass
class HookResult:
    """Result of executing a hook.

    Attributes:
        hook_name: Name of the hook.
        plugin_name: Name of the plugin.
        result: Hook return value.
        error: Error if hook failed.
        latency_ms: Execution time in milliseconds.
    """

    hook_name: str
    plugin_name: str
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0

    @property
    def success(self) -> bool:
        """Check if hook execution succeeded."""
        return self.error is None


class PluginManager:
    """Manages plugin lifecycle and hook execution.

    Provides plugin registration, lifecycle management, dependency
    resolution, and hook execution orchestration.

    Example:
        >>> manager = PluginManager()
        >>> manager.register(my_plugin)
        >>> manager.enable("my-plugin")
        >>> results = await manager.execute_hook("event:name", data=123)
    """

    def __init__(self):
        """Initialize plugin manager."""
        self._plugins: dict[str, Plugin] = {}
        self._hook_registry: dict[str, list[HookRegistration]] = {}
        self._enabled_plugins: set[str] = set()
        self._on_enable_hooks: list[Callable[[Plugin], None]] = []
        self._on_disable_hooks: list[Callable[[Plugin], None]] = []

    def register(self, plugin: Plugin) -> None:
        """Register a plugin with the manager.

        Args:
            plugin: Plugin to register.

        Raises:
            ValueError: If plugin validation fails or name exists.
        """
        errors = plugin.validate()
        if errors:
            raise ValueError(f"Invalid plugin: {'; '.join(errors)}")

        if plugin.name in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.name}")

        # Check dependencies
        for dep in plugin.dependencies:
            if dep not in self._plugins:
                raise ValueError(f"Missing dependency: {dep}")

        # Register plugin
        self._plugins[plugin.name] = plugin
        plugin.state = PluginState.REGISTERED
        plugin.metadata.created_at = datetime.now(UTC)

        # Register hooks
        for hook_name, handler in plugin.hooks.items():
            self._register_hook(hook_name, handler, plugin.priority, plugin.name)

        # Auto-enable if plugin.enabled is True
        if plugin.enabled:
            self._enable_plugin(plugin.name)

        logger.info("Registered plugin: %s v%s", plugin.name, plugin.version)

    def _register_hook(
        self,
        hook_name: str,
        handler: HookFunction,
        priority: HookPriority,
        plugin_name: str,
    ) -> None:
        """Register a hook handler."""
        if hook_name not in self._hook_registry:
            self._hook_registry[hook_name] = []

        registration = HookRegistration(
            hook_name=hook_name,
            handler=handler,
            priority=priority,
            plugin_name=plugin_name,
        )
        self._hook_registry[hook_name].append(registration)

        # Sort by priority (lowest first = executes first)
        self._hook_registry[hook_name].sort(key=lambda r: r.priority.value)

    def unregister(self, name: str) -> bool:
        """Unregister a plugin.

        Args:
            name: Plugin name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name not in self._plugins:
            return False

        # Check if other plugins depend on this one
        for plugin in self._plugins.values():
            if name in plugin.dependencies:
                raise ValueError(f"Cannot unregister {name}: required by {plugin.name}")

        # Disable first
        if name in self._enabled_plugins:
            self.disable(name)

        # Remove hooks
        plugin = self._plugins[name]
        for hook_name in plugin.hooks:
            if hook_name in self._hook_registry:
                self._hook_registry[hook_name] = [
                    r for r in self._hook_registry[hook_name] if r.plugin_name != name
                ]

        # Remove plugin
        del self._plugins[name]
        logger.info("Unregistered plugin: %s", name)
        return True

    def enable(self, name: str) -> bool:
        """Enable a plugin.

        Args:
            name: Plugin name to enable.

        Returns:
            True if enabled, False if not found.
        """
        if name not in self._plugins:
            return False
        return self._enable_plugin(name)

    def _enable_plugin(self, name: str) -> bool:
        """Internal method to enable a plugin."""
        plugin = self._plugins[name]

        # Enable dependencies first
        for dep in plugin.dependencies:
            if dep not in self._enabled_plugins:
                self._enable_plugin(dep)

        if name in self._enabled_plugins:
            return True

        self._enabled_plugins.add(name)
        plugin.enabled = True
        plugin.state = PluginState.ENABLED
        plugin.metadata.updated_at = datetime.now(UTC)

        # Invoke hooks
        for hook in self._on_enable_hooks:
            try:
                hook(plugin)
            except Exception as e:
                logger.warning("Enable hook failed for %s: %s", name, e)

        logger.debug("Enabled plugin: %s", name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a plugin.

        Args:
            name: Plugin name to disable.

        Returns:
            True if disabled, False if not found.
        """
        if name not in self._plugins or name not in self._enabled_plugins:
            return False

        plugin = self._plugins[name]

        # Check if other enabled plugins depend on this one
        for p in self._plugins.values():
            if p.enabled and name in p.dependencies and p.name != name:
                raise ValueError(f"Cannot disable {name}: required by {p.name}")

        self._enabled_plugins.discard(name)
        plugin.enabled = False
        plugin.state = PluginState.DISABLED
        plugin.metadata.updated_at = datetime.now(UTC)

        # Invoke hooks
        for hook in self._on_disable_hooks:
            try:
                hook(plugin)
            except Exception as e:
                logger.warning("Disable hook failed for %s: %s", name, e)

        logger.debug("Disabled plugin: %s", name)
        return True

    def get(self, name: str) -> Plugin | None:
        """Get a plugin by name.

        Args:
            name: Plugin name.

        Returns:
            Plugin or None.
        """
        return self._plugins.get(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled.

        Args:
            name: Plugin name.

        Returns:
            True if enabled.
        """
        return name in self._enabled_plugins

    def list_all(self) -> list[Plugin]:
        """Get all registered plugins.

        Returns:
            List of all plugins.
        """
        return list(self._plugins.values())

    def list_enabled(self) -> list[Plugin]:
        """Get all enabled plugins.

        Returns:
            List of enabled plugins.
        """
        return [p for p in self._plugins.values() if p.name in self._enabled_plugins]

    def list_hooks(self) -> list[str]:
        """Get all registered hook names.

        Returns:
            List of hook names.
        """
        return list(self._hook_registry.keys())

    def has_hook(self, hook_name: str) -> bool:
        """Check if a hook has any handlers.

        Args:
            hook_name: Hook name to check.

        Returns:
            True if hook has handlers.
        """
        return hook_name in self._hook_registry and len(self._hook_registry[hook_name]) > 0

    async def execute_hook(
        self,
        hook_name: str,
        *args,
        stop_on_error: bool = False,
        **kwargs,
    ) -> list[HookResult]:
        """Execute all handlers for a hook.

        Args:
            hook_name: Hook name to execute.
            *args: Positional arguments for handlers.
            stop_on_error: Stop execution on first error.
            **kwargs: Keyword arguments for handlers.

        Returns:
            List of HookResult for each handler.
        """
        registrations = self._hook_registry.get(hook_name, [])
        results = []

        for registration in registrations:
            # Skip disabled plugins
            if registration.plugin_name not in self._enabled_plugins:
                continue

            import time

            start_time = time.time()
            error = None
            result = None

            try:
                if asyncio.iscoroutinefunction(registration.handler):
                    result = await registration.handler(*args, **kwargs)
                else:
                    result = registration.handler(*args, **kwargs)

            except Exception as e:
                error = str(e)
                logger.error(
                    "Hook %s failed in plugin %s: %s", hook_name, registration.plugin_name, e
                )

                if stop_on_error:
                    results.append(
                        HookResult(
                            hook_name=hook_name,
                            plugin_name=registration.plugin_name,
                            error=error,
                            latency_ms=(time.time() - start_time) * 1000,
                        )
                    )
                    break

            latency_ms = (time.time() - start_time) * 1000

            results.append(
                HookResult(
                    hook_name=hook_name,
                    plugin_name=registration.plugin_name,
                    result=result,
                    error=error,
                    latency_ms=latency_ms,
                )
            )

        return results

    def execute_hook_sync(
        self,
        hook_name: str,
        *args,
        stop_on_error: bool = False,
        **kwargs,
    ) -> list[HookResult]:
        """Execute hook synchronously.

        Args:
            hook_name: Hook name to execute.
            *args: Positional arguments for handlers.
            stop_on_error: Stop execution on first error.
            **kwargs: Keyword arguments for handlers.

        Returns:
            List of HookResult for each handler.
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError("Use async execute_hook() in async context")
        except RuntimeError:
            pass
        return asyncio.run(
            self.execute_hook(hook_name, *args, stop_on_error=stop_on_error, **kwargs)
        )

    def on_enable(self, callback: Callable[[Plugin], None]) -> None:
        """Register callback for plugin enable events.

        Args:
            callback: Function called with plugin when enabled.
        """
        self._on_enable_hooks.append(callback)

    def on_disable(self, callback: Callable[[Plugin], None]) -> None:
        """Register callback for plugin disable events.

        Args:
            callback: Function called with plugin when disabled.
        """
        self._on_disable_hooks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get plugin manager statistics.

        Returns:
            Dictionary with manager statistics.
        """
        return {
            "total_plugins": len(self._plugins),
            "enabled_plugins": len(self._enabled_plugins),
            "total_hooks": len(self._hook_registry),
            "hooks_by_plugin": {name: len(plugin.hooks) for name, plugin in self._plugins.items()},
            "plugins_by_state": {
                str(state): len([p for p in self._plugins.values() if p.state == state])
                for state in PluginState
            },
        }

    def clear(self) -> int:
        """Clear all plugins.

        Returns:
            Number of plugins removed.
        """
        count = len(self._plugins)
        self._plugins.clear()
        self._hook_registry.clear()
        self._enabled_plugins.clear()
        self._on_enable_hooks.clear()
        self._on_disable_hooks.clear()
        logger.info("Cleared %d plugins", count)
        return count

    def __len__(self) -> int:
        """Get number of registered plugins."""
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        """Check if plugin is registered."""
        return name in self._plugins

    def __iter__(self):
        """Iterate over plugins."""
        return iter(self._plugins.values())
