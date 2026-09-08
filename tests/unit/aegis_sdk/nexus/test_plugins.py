"""
Tier 1: Unit Tests for Nexus Plugin System.

Tests plugin registration, lifecycle management, and hook execution.
"""

import pytest

from aegis_sdk.nexus.plugins import (
    HookPriority,
    HookResult,
    Plugin,
    PluginManager,
    PluginMetadata,
    PluginState,
)


@pytest.fixture
def manager():
    """Create a fresh plugin manager for each test."""
    return PluginManager()


@pytest.fixture
def sample_plugin():
    """Sample plugin for testing."""
    return Plugin(
        name="test-plugin",
        version="1.0.0",
        hooks={
            "request:before": lambda **kwargs: {"modified": True},
            "request:after": lambda **kwargs: None,
        },
    )


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPlugin:
    """Test Plugin dataclass."""

    def test_plugin_creation(self):
        """Plugin should be created with required fields."""
        plugin = Plugin(name="test-plugin", version="1.0.0")
        assert plugin.name == "test-plugin"
        assert plugin.version == "1.0.0"
        assert plugin.enabled is True
        assert plugin.state == PluginState.REGISTERED

    def test_plugin_with_hooks(self):
        """Plugin should store hooks."""
        hooks = {
            "event:before": lambda: None,
            "event:after": lambda: None,
        }
        plugin = Plugin(name="test", version="1.0.0", hooks=hooks)
        assert len(plugin.hooks) == 2

    def test_plugin_validation_passes(self):
        """Valid plugin should pass validation."""
        plugin = Plugin(name="test-plugin", version="1.0.0")
        errors = plugin.validate()
        assert len(errors) == 0

    def test_plugin_validation_fails_empty_name(self):
        """Empty name should fail validation."""
        plugin = Plugin(name="", version="1.0.0")
        errors = plugin.validate()
        assert any("name" in e for e in errors)

    def test_plugin_validation_fails_empty_version(self):
        """Empty version should fail validation."""
        plugin = Plugin(name="test", version="")
        errors = plugin.validate()
        assert any("version" in e for e in errors)

    def test_plugin_validation_fails_invalid_name(self):
        """Invalid name characters should fail validation."""
        plugin = Plugin(name="test plugin!", version="1.0.0")
        errors = plugin.validate()
        assert any("name" in e.lower() for e in errors)

    def test_plugin_validation_fails_non_callable_hook(self):
        """Non-callable hook should fail validation."""
        plugin = Plugin(
            name="test",
            version="1.0.0",
            hooks={"event": "not_callable"},
        )
        errors = plugin.validate()
        assert any("callable" in e for e in errors)

    def test_plugin_get_hook(self):
        """get_hook should return hook handler."""

        def hook():
            return None

        plugin = Plugin(name="test", version="1.0.0", hooks={"event": hook})
        assert plugin.get_hook("event") is hook
        assert plugin.get_hook("missing") is None

    def test_plugin_has_hook(self):
        """has_hook should check hook existence."""
        plugin = Plugin(
            name="test",
            version="1.0.0",
            hooks={"event": lambda: None},
        )
        assert plugin.has_hook("event") is True
        assert plugin.has_hook("missing") is False

    def test_plugin_to_dict(self):
        """to_dict should return dictionary representation."""
        plugin = Plugin(
            name="test-plugin",
            version="1.0.0",
            hooks={"event": lambda: None},
            metadata=PluginMetadata(author="Test Author"),
        )
        data = plugin.to_dict()
        assert data["name"] == "test-plugin"
        assert data["version"] == "1.0.0"
        assert "event" in data["hooks"]
        assert data["metadata"]["author"] == "Test Author"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginManager:
    """Test PluginManager class."""

    def test_manager_register_plugin(self, manager, sample_plugin):
        """register should add plugin to manager."""
        manager.register(sample_plugin)
        assert sample_plugin.name in manager
        assert len(manager) == 1

    def test_manager_register_raises_on_invalid(self, manager):
        """register should raise on invalid plugin."""
        plugin = Plugin(name="", version="1.0.0")
        with pytest.raises(ValueError):
            manager.register(plugin)

    def test_manager_register_raises_on_duplicate(self, manager, sample_plugin):
        """register should raise on duplicate plugin name."""
        manager.register(sample_plugin)
        with pytest.raises(ValueError):
            manager.register(sample_plugin)

    def test_manager_register_checks_dependencies(self, manager):
        """register should check dependencies exist."""
        plugin = Plugin(
            name="dependent",
            version="1.0.0",
            dependencies=["missing-dependency"],
        )
        with pytest.raises(ValueError):
            manager.register(plugin)

    def test_manager_register_auto_enables(self, manager):
        """register should auto-enable if plugin.enabled is True."""
        plugin = Plugin(name="test", version="1.0.0", enabled=True)
        manager.register(plugin)
        assert manager.is_enabled("test") is True

    def test_manager_unregister_plugin(self, manager, sample_plugin):
        """unregister should remove plugin."""
        manager.register(sample_plugin)
        result = manager.unregister(sample_plugin.name)
        assert result is True
        assert sample_plugin.name not in manager

    def test_manager_unregister_returns_false_for_missing(self, manager):
        """unregister should return False for missing plugin."""
        assert manager.unregister("nonexistent") is False

    def test_manager_unregister_prevents_if_dependency(self, manager):
        """unregister should prevent removal if other plugins depend on it."""
        base = Plugin(name="base", version="1.0.0")
        dependent = Plugin(name="dependent", version="1.0.0", dependencies=["base"])

        manager.register(base)
        manager.register(dependent)

        with pytest.raises(ValueError):
            manager.unregister("base")

    def test_manager_enable_plugin(self, manager):
        """enable should enable a plugin."""
        plugin = Plugin(name="test", version="1.0.0", enabled=False)
        manager.register(plugin)
        result = manager.enable("test")
        assert result is True
        assert manager.is_enabled("test") is True

    def test_manager_enable_returns_false_for_missing(self, manager):
        """enable should return False for missing plugin."""
        assert manager.enable("nonexistent") is False

    def test_manager_enable_enables_dependencies(self, manager):
        """enable should enable dependencies first."""
        base = Plugin(name="base", version="1.0.0", enabled=False)
        dependent = Plugin(name="dependent", version="1.0.0", dependencies=["base"], enabled=False)

        manager.register(base)
        manager.register(dependent)

        # Base not enabled yet
        manager.enable("dependent")

        assert manager.is_enabled("base") is True
        assert manager.is_enabled("dependent") is True

    def test_manager_disable_plugin(self, manager, sample_plugin):
        """disable should disable a plugin."""
        manager.register(sample_plugin)
        result = manager.disable(sample_plugin.name)
        assert result is True
        assert manager.is_enabled(sample_plugin.name) is False

    def test_manager_disable_returns_false_for_missing(self, manager):
        """disable should return False for missing plugin."""
        assert manager.disable("nonexistent") is False

    def test_manager_disable_prevents_if_dependent(self, manager):
        """disable should prevent if other enabled plugins depend on it."""
        base = Plugin(name="base", version="1.0.0")
        dependent = Plugin(name="dependent", version="1.0.0", dependencies=["base"])

        manager.register(base)
        manager.register(dependent)

        with pytest.raises(ValueError):
            manager.disable("base")

    def test_manager_get_plugin(self, manager, sample_plugin):
        """get should return plugin."""
        manager.register(sample_plugin)
        plugin = manager.get(sample_plugin.name)
        assert plugin is not None
        assert plugin.name == sample_plugin.name

    def test_manager_get_returns_none_for_missing(self, manager):
        """get should return None for missing plugin."""
        assert manager.get("nonexistent") is None

    def test_manager_is_enabled(self, manager, sample_plugin):
        """is_enabled should check plugin enabled state."""
        manager.register(sample_plugin)
        assert manager.is_enabled(sample_plugin.name) is True
        manager.disable(sample_plugin.name)
        assert manager.is_enabled(sample_plugin.name) is False

    def test_manager_list_all(self, manager):
        """list_all should return all plugins."""
        manager.register(Plugin(name="plugin1", version="1.0.0"))
        manager.register(Plugin(name="plugin2", version="1.0.0"))

        plugins = manager.list_all()
        assert len(plugins) == 2

    def test_manager_list_enabled(self, manager):
        """list_enabled should return only enabled plugins."""
        manager.register(Plugin(name="enabled", version="1.0.0", enabled=True))
        manager.register(Plugin(name="disabled", version="1.0.0", enabled=False))

        enabled = manager.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    def test_manager_list_hooks(self, manager, sample_plugin):
        """list_hooks should return all registered hook names."""
        manager.register(sample_plugin)

        hooks = manager.list_hooks()
        assert "request:before" in hooks
        assert "request:after" in hooks

    def test_manager_has_hook(self, manager, sample_plugin):
        """has_hook should check if hook has handlers."""
        manager.register(sample_plugin)
        assert manager.has_hook("request:before") is True
        assert manager.has_hook("nonexistent") is False

    @pytest.mark.asyncio
    async def test_manager_execute_hook(self, manager, sample_plugin):
        """execute_hook should invoke hook handlers."""
        manager.register(sample_plugin)

        results = await manager.execute_hook("request:before")
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].result == {"modified": True}

    @pytest.mark.asyncio
    async def test_manager_execute_hook_async_handler(self, manager):
        """execute_hook should handle async handlers."""

        async def async_handler(**kwargs):
            return {"async": True}

        plugin = Plugin(
            name="async-plugin",
            version="1.0.0",
            hooks={"event": async_handler},
        )
        manager.register(plugin)

        results = await manager.execute_hook("event")
        assert len(results) == 1
        assert results[0].result == {"async": True}

    @pytest.mark.asyncio
    async def test_manager_execute_hook_skips_disabled(self, manager, sample_plugin):
        """execute_hook should skip disabled plugins."""
        manager.register(sample_plugin)
        manager.disable(sample_plugin.name)

        results = await manager.execute_hook("request:before")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_manager_execute_hook_with_args(self, manager):
        """execute_hook should pass args to handlers."""
        received = {}

        def handler(**kwargs):
            received.update(kwargs)
            return None

        plugin = Plugin(name="test", version="1.0.0", hooks={"event": handler})
        manager.register(plugin)

        await manager.execute_hook("event", key="value")
        assert received["key"] == "value"

    @pytest.mark.asyncio
    async def test_manager_execute_hook_error_handling(self, manager):
        """execute_hook should handle errors gracefully."""

        def failing_handler(**kwargs):
            raise ValueError("Test error")

        plugin = Plugin(
            name="failing",
            version="1.0.0",
            hooks={"event": failing_handler},
        )
        manager.register(plugin)

        results = await manager.execute_hook("event")
        assert len(results) == 1
        assert results[0].success is False
        assert "Test error" in results[0].error

    @pytest.mark.asyncio
    async def test_manager_execute_hook_stop_on_error(self, manager):
        """execute_hook with stop_on_error should stop on first error."""
        calls = []

        def first(**kwargs):
            calls.append(1)
            raise ValueError("Error")

        def second(**kwargs):
            calls.append(2)
            return None

        plugin1 = Plugin(
            name="first",
            version="1.0.0",
            hooks={"event": first},
            priority=HookPriority.FIRST,
        )
        plugin2 = Plugin(
            name="second",
            version="1.0.0",
            hooks={"event": second},
            priority=HookPriority.LAST,
        )
        manager.register(plugin1)
        manager.register(plugin2)

        results = await manager.execute_hook("event", stop_on_error=True)
        assert len(results) == 1
        assert len(calls) == 1

    def test_manager_on_enable_hook(self, manager):
        """on_enable hook should be called when plugin is enabled."""
        enabled_plugins = []
        manager.on_enable(lambda p: enabled_plugins.append(p.name))

        plugin = Plugin(name="test", version="1.0.0", enabled=False)
        manager.register(plugin)
        manager.enable("test")

        assert "test" in enabled_plugins

    def test_manager_on_disable_hook(self, manager, sample_plugin):
        """on_disable hook should be called when plugin is disabled."""
        disabled_plugins = []
        manager.on_disable(lambda p: disabled_plugins.append(p.name))

        manager.register(sample_plugin)
        manager.disable(sample_plugin.name)

        assert sample_plugin.name in disabled_plugins

    def test_manager_get_stats(self, manager, sample_plugin):
        """get_stats should return manager statistics."""
        manager.register(sample_plugin)

        stats = manager.get_stats()
        assert stats["total_plugins"] == 1
        assert stats["enabled_plugins"] == 1
        assert stats["total_hooks"] == 2

    def test_manager_clear(self, manager, sample_plugin):
        """clear should remove all plugins."""
        manager.register(sample_plugin)

        count = manager.clear()
        assert count == 1
        assert len(manager) == 0

    def test_manager_len(self, manager, sample_plugin):
        """__len__ should return plugin count."""
        assert len(manager) == 0
        manager.register(sample_plugin)
        assert len(manager) == 1

    def test_manager_contains(self, manager, sample_plugin):
        """__contains__ should check plugin existence."""
        manager.register(sample_plugin)
        assert sample_plugin.name in manager
        assert "missing" not in manager

    def test_manager_iter(self, manager):
        """__iter__ should iterate over plugins."""
        manager.register(Plugin(name="plugin1", version="1.0.0"))
        manager.register(Plugin(name="plugin2", version="1.0.0"))

        names = [p.name for p in manager]
        assert "plugin1" in names
        assert "plugin2" in names


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHookResult:
    """Test HookResult dataclass."""

    def test_hook_result_success(self):
        """HookResult should indicate success."""
        result = HookResult(
            hook_name="event",
            plugin_name="test",
            result={"key": "value"},
        )
        assert result.success is True
        assert result.result == {"key": "value"}

    def test_hook_result_failure(self):
        """HookResult should indicate failure."""
        result = HookResult(
            hook_name="event",
            plugin_name="test",
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"
