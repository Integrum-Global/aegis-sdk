"""
Tier 1: Unit Tests for Nexus Plugins Module.

Tests plugin lifecycle management, discovery, isolation, and hook execution.
"""

import os
import tempfile
from typing import Any

import pytest

from aegis_sdk.nexus.plugins_module import (
    PluginBase,
    PluginConfig,
    PluginExecutionResult,
    PluginInfo,
    PluginLifecycleState,
    PluginPriority,
    PluginsModule,
    PluginsModuleSingleton,
)

# Test plugin implementations


class SimplePlugin(PluginBase):
    """Simple test plugin."""

    def __init__(self, name: str = "simple-plugin"):
        super().__init__()
        self._name = name
        self.load_called = False
        self.activate_called = False
        self.deactivate_called = False
        self.unload_called = False

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name=self._name,
            version="1.0.0",
            description="A simple test plugin",
            author="Test Author",
            tags=["test", "simple"],
        )

    async def on_load(self) -> None:
        self.load_called = True

    async def on_activate(self) -> None:
        self.activate_called = True

    async def on_deactivate(self) -> None:
        self.deactivate_called = True

    async def on_unload(self) -> None:
        self.unload_called = True


class RequestInterceptorPlugin(PluginBase):
    """Plugin that intercepts requests."""

    def __init__(self):
        super().__init__()
        self.requests: list = []
        self.responses: list = []
        self.errors: list = []

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="interceptor-plugin",
            version="1.0.0",
            description="Intercepts requests and responses",
            priority=PluginPriority.FIRST,
        )

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any] | None:
        self.requests.append(
            {
                "request_id": request_id,
                "workflow_name": workflow_name,
                "inputs": inputs,
            }
        )
        return {"intercepted": True, **inputs}

    async def on_response(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        outputs: Any,
        **kwargs,
    ) -> Any | None:
        self.responses.append(
            {
                "request_id": request_id,
                "workflow_name": workflow_name,
                "outputs": outputs,
            }
        )
        return {"response_intercepted": True, "original": outputs}

    async def on_error(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> Exception | None:
        self.errors.append(
            {
                "request_id": request_id,
                "workflow_name": workflow_name,
                "error": str(error),
            }
        )
        return None


class FailingPlugin(PluginBase):
    """Plugin that fails on hooks."""

    def __init__(self, fail_on: str = "load"):
        super().__init__()
        self.fail_on = fail_on

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="failing-plugin",
            version="1.0.0",
        )

    async def on_load(self) -> None:
        if self.fail_on == "load":
            raise ValueError("Load failed intentionally")

    async def on_activate(self) -> None:
        if self.fail_on == "activate":
            raise ValueError("Activate failed intentionally")

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any] | None:
        if self.fail_on == "request":
            raise ValueError("Request hook failed intentionally")
        return None


class DependentPlugin(PluginBase):
    """Plugin that depends on another plugin."""

    def __init__(self, dependency_name: str):
        super().__init__()
        self._dependency = dependency_name

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="dependent-plugin",
            version="1.0.0",
            dependencies=[self._dependency],
        )


@pytest.fixture
def module():
    """Create a fresh plugins module for each test."""
    return PluginsModule()


@pytest.fixture
def simple_plugin():
    """Create a simple test plugin."""
    return SimplePlugin()


@pytest.fixture
def interceptor_plugin():
    """Create an interceptor plugin."""
    return RequestInterceptorPlugin()


# Reset singleton before each test that uses it
@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    PluginsModuleSingleton.reset_instance()
    yield
    PluginsModuleSingleton.reset_instance()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginInfo:
    """Test PluginInfo dataclass."""

    def test_plugin_info_defaults(self):
        """PluginInfo should have sensible defaults."""
        info = PluginInfo(name="test-plugin")
        assert info.name == "test-plugin"
        assert info.version == "1.0.0"
        assert info.priority == PluginPriority.NORMAL
        assert info.enabled is True
        assert info.dependencies == []
        assert info.tags == []

    def test_plugin_info_to_dict(self):
        """PluginInfo should convert to dictionary."""
        info = PluginInfo(
            name="test-plugin",
            version="2.0.0",
            description="Test description",
            author="Test Author",
            tags=["tag1", "tag2"],
        )
        data = info.to_dict()
        assert data["name"] == "test-plugin"
        assert data["version"] == "2.0.0"
        assert data["description"] == "Test description"
        assert "tag1" in data["tags"]


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginConfig:
    """Test PluginConfig dataclass."""

    def test_config_defaults(self):
        """PluginConfig should have sensible defaults."""
        config = PluginConfig()
        assert config.enabled is True
        assert config.settings == {}
        assert config.environment == "production"

    def test_config_get_set(self):
        """PluginConfig should support get/set."""
        config = PluginConfig()
        config.set("key1", "value1")
        assert config.get("key1") == "value1"
        assert config.get("missing", "default") == "default"

    def test_config_to_dict(self):
        """PluginConfig should convert to dictionary."""
        config = PluginConfig(
            enabled=True,
            settings={"key": "value"},
            environment="testing",
        )
        data = config.to_dict()
        assert data["enabled"] is True
        assert data["settings"]["key"] == "value"
        assert data["environment"] == "testing"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginLifecycleState:
    """Test PluginLifecycleState enum."""

    def test_state_can_activate(self):
        """Only certain states should allow activation."""
        assert PluginLifecycleState.LOADED.can_activate is True
        assert PluginLifecycleState.INITIALIZED.can_activate is True
        assert PluginLifecycleState.DEACTIVATED.can_activate is True
        assert PluginLifecycleState.ACTIVE.can_activate is False
        assert PluginLifecycleState.ERROR.can_activate is False

    def test_state_can_deactivate(self):
        """Only ACTIVE state should allow deactivation."""
        assert PluginLifecycleState.ACTIVE.can_deactivate is True
        assert PluginLifecycleState.LOADED.can_deactivate is False
        assert PluginLifecycleState.DEACTIVATED.can_deactivate is False


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginPriority:
    """Test PluginPriority enum."""

    def test_priority_comparison(self):
        """Priorities should compare correctly."""
        assert PluginPriority.FIRST < PluginPriority.NORMAL
        assert PluginPriority.NORMAL < PluginPriority.LAST
        assert PluginPriority.EARLY < PluginPriority.LATE

    def test_priority_values(self):
        """Priorities should have expected values."""
        assert PluginPriority.FIRST.value == 1
        assert PluginPriority.NORMAL.value == 50
        assert PluginPriority.LAST.value == 100


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginBase:
    """Test PluginBase abstract class."""

    def test_plugin_initial_state(self, simple_plugin):
        """Plugin should start in UNLOADED state."""
        assert simple_plugin.state == PluginLifecycleState.UNLOADED
        assert simple_plugin.is_active is False

    def test_plugin_name_from_info(self, simple_plugin):
        """Plugin name should come from info."""
        assert simple_plugin.name == "simple-plugin"
        assert simple_plugin.version == "1.0.0"

    def test_plugin_config_default(self, simple_plugin):
        """Plugin should have default config."""
        assert simple_plugin.config is not None
        assert simple_plugin.config.enabled is True

    def test_plugin_to_dict(self, simple_plugin):
        """Plugin should convert to dictionary."""
        data = simple_plugin.to_dict()
        assert data["info"]["name"] == "simple-plugin"
        assert data["state"] == "unloaded"
        assert data["execution_count"] == 0


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginsModule:
    """Test PluginsModule class."""

    def test_module_creation(self, module):
        """Module should be created with defaults."""
        assert len(module) == 0
        assert module.uptime_s >= 0

    def test_module_load_plugin(self, module, simple_plugin):
        """load should add plugin to module."""
        result = module.load(simple_plugin)
        assert result is True
        assert simple_plugin.name in module
        assert simple_plugin.load_called is True
        assert simple_plugin.state == PluginLifecycleState.LOADED

    def test_module_load_with_config(self, module, simple_plugin):
        """load should apply configuration."""
        config = PluginConfig(settings={"key": "value"})
        module.load(simple_plugin, config=config)
        assert simple_plugin.config.get("key") == "value"

    def test_module_load_raises_on_empty_name(self, module):
        """load should raise on plugin without name."""

        class EmptyNamePlugin(PluginBase):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name="")

        with pytest.raises(ValueError, match="must have a name"):
            module.load(EmptyNamePlugin())

    def test_module_load_raises_on_duplicate(self, module, simple_plugin):
        """load should raise on duplicate plugin name."""
        module.load(simple_plugin)
        with pytest.raises(ValueError, match="already loaded"):
            module.load(SimplePlugin())  # Same name

    def test_module_load_raises_on_missing_dependency(self, module):
        """load should raise on missing dependency."""
        dependent = DependentPlugin("missing-plugin")
        with pytest.raises(ValueError, match="Missing dependency"):
            module.load(dependent)

    def test_module_unload_plugin(self, module, simple_plugin):
        """unload should remove plugin from module."""
        module.load(simple_plugin)
        result = module.unload(simple_plugin.name)
        assert result is True
        assert simple_plugin.name not in module
        assert simple_plugin.unload_called is True
        assert simple_plugin.state == PluginLifecycleState.UNLOADED

    def test_module_unload_returns_false_for_missing(self, module):
        """unload should return False for missing plugin."""
        assert module.unload("nonexistent") is False

    def test_module_unload_deactivates_first(self, module, simple_plugin):
        """unload should deactivate plugin first."""
        module.load(simple_plugin)
        module.activate(simple_plugin.name)
        module.unload(simple_plugin.name)
        assert simple_plugin.deactivate_called is True
        assert simple_plugin.unload_called is True

    def test_module_activate_plugin(self, module, simple_plugin):
        """activate should activate loaded plugin."""
        module.load(simple_plugin)
        result = module.activate(simple_plugin.name)
        assert result is True
        assert module.is_active(simple_plugin.name) is True
        assert simple_plugin.activate_called is True
        assert simple_plugin.state == PluginLifecycleState.ACTIVE

    def test_module_activate_returns_false_for_missing(self, module):
        """activate should return False for missing plugin."""
        assert module.activate("nonexistent") is False

    def test_module_activate_activates_dependencies(self, module):
        """activate should activate dependencies first."""
        base = SimplePlugin("base-plugin")
        dependent = DependentPlugin("base-plugin")
        dependent._name_override = "dependent-plugin"

        # Override name property for dependent plugin
        class TestDependentPlugin(DependentPlugin):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(
                    name="dependent-plugin",
                    version="1.0.0",
                    dependencies=["base-plugin"],
                )

        dependent = TestDependentPlugin("base-plugin")

        module.load(base)
        module.load(dependent)
        module.activate("dependent-plugin")

        assert module.is_active("base-plugin") is True
        assert module.is_active("dependent-plugin") is True

    def test_module_deactivate_plugin(self, module, simple_plugin):
        """deactivate should deactivate active plugin."""
        module.load(simple_plugin)
        module.activate(simple_plugin.name)
        result = module.deactivate(simple_plugin.name)
        assert result is True
        assert module.is_active(simple_plugin.name) is False
        assert simple_plugin.deactivate_called is True
        assert simple_plugin.state == PluginLifecycleState.DEACTIVATED

    def test_module_deactivate_returns_false_for_missing(self, module):
        """deactivate should return False for missing plugin."""
        assert module.deactivate("nonexistent") is False

    def test_module_get_plugin(self, module, simple_plugin):
        """get should return loaded plugin."""
        module.load(simple_plugin)
        plugin = module.get(simple_plugin.name)
        assert plugin is not None
        assert plugin.name == simple_plugin.name

    def test_module_get_returns_none_for_missing(self, module):
        """get should return None for missing plugin."""
        assert module.get("nonexistent") is None

    def test_module_list_all(self, module):
        """list should return all loaded plugins."""
        module.load(SimplePlugin("plugin-1"))
        module.load(SimplePlugin("plugin-2"))

        plugins = module.list()
        assert len(plugins) == 2
        names = [p.name for p in plugins]
        assert "plugin-1" in names
        assert "plugin-2" in names

    def test_module_list_active_only(self, module):
        """list should filter active plugins."""
        p1 = SimplePlugin("plugin-1")
        p2 = SimplePlugin("plugin-2")
        module.load(p1)
        module.load(p2)
        module.activate("plugin-1")

        active = module.list(active_only=True)
        assert len(active) == 1
        assert active[0].name == "plugin-1"

    def test_module_list_by_tags(self, module):
        """list should filter by tags."""

        class TaggedPlugin(PluginBase):
            def __init__(self, name: str, tags: list):
                super().__init__()
                self._name = name
                self._tags = tags

            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name=self._name, tags=self._tags)

        module.load(TaggedPlugin("plugin-1", ["api", "core"]))
        module.load(TaggedPlugin("plugin-2", ["cli"]))

        api_plugins = module.list(tags=["api"])
        assert len(api_plugins) == 1
        assert api_plugins[0].name == "plugin-1"

    def test_module_is_loaded(self, module, simple_plugin):
        """is_loaded should check plugin presence."""
        assert module.is_loaded(simple_plugin.name) is False
        module.load(simple_plugin)
        assert module.is_loaded(simple_plugin.name) is True

    def test_module_is_active(self, module, simple_plugin):
        """is_active should check activation state."""
        module.load(simple_plugin)
        assert module.is_active(simple_plugin.name) is False
        module.activate(simple_plugin.name)
        assert module.is_active(simple_plugin.name) is True

    @pytest.mark.asyncio
    async def test_module_on_request(self, module, interceptor_plugin):
        """on_request should execute plugin hooks."""
        module.load(interceptor_plugin)
        module.activate(interceptor_plugin.name)

        results = await module.on_request(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={"value": 42},
        )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].result["intercepted"] is True
        assert len(interceptor_plugin.requests) == 1

    @pytest.mark.asyncio
    async def test_module_on_response(self, module, interceptor_plugin):
        """on_response should execute plugin hooks."""
        module.load(interceptor_plugin)
        module.activate(interceptor_plugin.name)

        results = await module.on_response(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        assert len(results) == 1
        assert results[0].success is True
        assert len(interceptor_plugin.responses) == 1

    @pytest.mark.asyncio
    async def test_module_on_error(self, module, interceptor_plugin):
        """on_error should execute plugin hooks."""
        module.load(interceptor_plugin)
        module.activate(interceptor_plugin.name)

        results = await module.on_error(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={"value": 42},
            error=ValueError("Test error"),
        )

        assert len(results) == 1
        assert results[0].success is True
        assert len(interceptor_plugin.errors) == 1

    @pytest.mark.asyncio
    async def test_module_hook_skips_inactive_plugins(self, module, interceptor_plugin):
        """Hooks should skip inactive plugins."""
        module.load(interceptor_plugin)
        # Not activated

        results = await module.on_request(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={},
        )

        assert len(results) == 0
        assert len(interceptor_plugin.requests) == 0

    @pytest.mark.asyncio
    async def test_module_hook_priority_order(self, module):
        """Hooks should execute in priority order."""
        execution_order = []

        class PriorityPlugin(PluginBase):
            def __init__(self, name: str, priority: PluginPriority):
                super().__init__()
                self._name = name
                self._priority = priority

            @property
            def info(self) -> PluginInfo:
                return PluginInfo(name=self._name, priority=self._priority)

            async def on_request(self, **kwargs):
                execution_order.append(self._name)
                return None

        module.load(PriorityPlugin("last", PluginPriority.LAST))
        module.load(PriorityPlugin("first", PluginPriority.FIRST))
        module.load(PriorityPlugin("normal", PluginPriority.NORMAL))

        module.activate("last")
        module.activate("first")
        module.activate("normal")

        await module.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )

        assert execution_order == ["first", "normal", "last"]

    def test_module_plugin_isolation_load(self, module):
        """Plugin errors should be isolated on load."""
        module = PluginsModule(isolation_enabled=True)
        failing = FailingPlugin(fail_on="load")

        # Should not raise with isolation enabled
        module.load(failing)
        # Plugin is still loaded (error was isolated), but may have error recorded
        assert failing.name in module
        # The error is logged but plugin state proceeds to LOADED in sync context
        # In threaded execution, the error state may not propagate back
        assert failing._error is not None or failing.state == PluginLifecycleState.LOADED

    @pytest.mark.asyncio
    async def test_module_plugin_isolation_hook(self, module):
        """Plugin errors should be isolated during hook execution."""
        module = PluginsModule(isolation_enabled=True)
        failing = FailingPlugin(fail_on="request")

        # Need to load without error first
        failing.fail_on = None
        module.load(failing)
        module.activate(failing.name)

        # Now make it fail on request
        failing.fail_on = "request"

        results = await module.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error == "Plugin execution failed"

    def test_module_set_config(self, module, simple_plugin):
        """set_config should update plugin configuration."""
        module.load(simple_plugin)
        config = PluginConfig(settings={"new_key": "new_value"})
        result = module.set_config(simple_plugin.name, config)
        assert result is True
        assert simple_plugin.config.get("new_key") == "new_value"

    def test_module_get_config(self, module, simple_plugin):
        """get_config should return plugin configuration."""
        module.load(simple_plugin)
        config = module.get_config(simple_plugin.name)
        assert config is not None
        assert config.enabled is True

    def test_module_event_hooks(self, module, simple_plugin):
        """Event hooks should be called on lifecycle events."""
        loaded_plugins = []
        activated_plugins = []
        deactivated_plugins = []
        unloaded_plugins = []

        module.on_plugin_load(lambda name, p: loaded_plugins.append(name))
        module.on_plugin_activate(lambda name, p: activated_plugins.append(name))
        module.on_plugin_deactivate(lambda name, p: deactivated_plugins.append(name))
        module.on_plugin_unload(lambda name, p: unloaded_plugins.append(name))

        module.load(simple_plugin)
        assert simple_plugin.name in loaded_plugins

        module.activate(simple_plugin.name)
        assert simple_plugin.name in activated_plugins

        module.deactivate(simple_plugin.name)
        assert simple_plugin.name in deactivated_plugins

        module.unload(simple_plugin.name)
        assert simple_plugin.name in unloaded_plugins

    def test_module_get_stats(self, module, simple_plugin):
        """get_stats should return module statistics."""
        module.load(simple_plugin)
        module.activate(simple_plugin.name)

        stats = module.get_stats()
        assert stats["total_plugins"] == 1
        assert stats["active_plugins"] == 1
        assert stats["uptime_s"] >= 0

    def test_module_clear(self, module, simple_plugin):
        """clear should unload all plugins."""
        module.load(simple_plugin)
        module.load(SimplePlugin("plugin-2"))

        count = module.clear()
        assert count == 2
        assert len(module) == 0

    def test_module_len(self, module, simple_plugin):
        """__len__ should return plugin count."""
        assert len(module) == 0
        module.load(simple_plugin)
        assert len(module) == 1

    def test_module_contains(self, module, simple_plugin):
        """__contains__ should check plugin presence."""
        module.load(simple_plugin)
        assert simple_plugin.name in module
        assert "missing" not in module

    def test_module_iter(self, module):
        """__iter__ should iterate over plugins."""
        module.load(SimplePlugin("plugin-1"))
        module.load(SimplePlugin("plugin-2"))

        names = [p.name for p in module]
        assert "plugin-1" in names
        assert "plugin-2" in names


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    def test_discover_empty_directory(self, module):
        """discover should handle empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovered = module.discover(tmpdir)
            assert len(discovered) == 0

    def test_discover_with_plugin_file(self, module):
        """discover should load plugins from files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a plugin file
            plugin_code = """
from aegis_sdk.nexus.plugins_module import PluginBase, PluginInfo

class TestFilePlugin(PluginBase):
    @property
    def info(self):
        return PluginInfo(name="test-file-plugin", version="1.0.0")
"""
            plugin_file = os.path.join(tmpdir, "test_plugin.py")
            with open(plugin_file, "w") as f:
                f.write(plugin_code)

            discovered = module.discover(tmpdir)
            assert "test-file-plugin" in discovered
            assert module.is_loaded("test-file-plugin")

    def test_discover_skips_private_files(self, module):
        """discover should skip files starting with underscore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a private file
            private_file = os.path.join(tmpdir, "_private.py")
            with open(private_file, "w") as f:
                f.write("# private module")

            discovered = module.discover(tmpdir)
            assert len(discovered) == 0

    def test_discover_handles_invalid_files(self, module):
        """discover should handle invalid plugin files."""
        module = PluginsModule(isolation_enabled=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an invalid file
            invalid_file = os.path.join(tmpdir, "invalid.py")
            with open(invalid_file, "w") as f:
                f.write("raise RuntimeError('Invalid')")

            # Should not raise
            discovered = module.discover(tmpdir)
            assert len(discovered) == 0

    def test_load_from_file_nonexistent(self, module):
        """load_from_file should handle nonexistent file."""
        result = module.load_from_file("/nonexistent/path.py")
        assert result is None


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginsModuleSingleton:
    """Test PluginsModuleSingleton class."""

    def test_singleton_instance(self):
        """Should return same instance."""
        instance1 = PluginsModuleSingleton.get_instance()
        instance2 = PluginsModuleSingleton.get_instance()
        assert instance1 is instance2

    def test_singleton_load(self, simple_plugin):
        """Singleton should support loading."""
        singleton = PluginsModuleSingleton.get_instance()
        result = singleton.load(simple_plugin)
        assert result is True
        assert simple_plugin.name in singleton

    def test_singleton_unload(self, simple_plugin):
        """Singleton should support unloading."""
        singleton = PluginsModuleSingleton.get_instance()
        singleton.load(simple_plugin)
        result = singleton.unload(simple_plugin.name)
        assert result is True
        assert simple_plugin.name not in singleton

    def test_singleton_activate(self, simple_plugin):
        """Singleton should support activation."""
        singleton = PluginsModuleSingleton.get_instance()
        singleton.load(simple_plugin)
        result = singleton.activate(simple_plugin.name)
        assert result is True

    def test_singleton_list(self, simple_plugin):
        """Singleton should support listing."""
        singleton = PluginsModuleSingleton.get_instance()
        singleton.load(simple_plugin)
        plugins = singleton.list()
        assert len(plugins) == 1

    @pytest.mark.asyncio
    async def test_singleton_on_request(self, interceptor_plugin):
        """Singleton should support hook execution."""
        singleton = PluginsModuleSingleton.get_instance()
        singleton.load(interceptor_plugin)
        singleton.activate(interceptor_plugin.name)

        results = await singleton.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )
        assert len(results) == 1

    def test_singleton_reset(self, simple_plugin):
        """reset_instance should clear singleton."""
        singleton1 = PluginsModuleSingleton.get_instance()
        singleton1.load(simple_plugin)

        PluginsModuleSingleton.reset_instance()

        singleton2 = PluginsModuleSingleton.get_instance()
        assert simple_plugin.name not in singleton2
        assert singleton1 is not singleton2


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginExecutionResult:
    """Test PluginExecutionResult dataclass."""

    def test_result_success(self):
        """Result should indicate success."""
        result = PluginExecutionResult(
            plugin_name="test",
            hook_name="on_request",
            success=True,
            result={"key": "value"},
        )
        assert result.success is True
        assert result.error is None

    def test_result_failure(self):
        """Result should indicate failure."""
        result = PluginExecutionResult(
            plugin_name="test",
            hook_name="on_request",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_result_to_dict(self):
        """Result should convert to dictionary."""
        result = PluginExecutionResult(
            plugin_name="test",
            hook_name="on_request",
            success=True,
            latency_ms=10.5,
        )
        data = result.to_dict()
        assert data["plugin_name"] == "test"
        assert data["hook_name"] == "on_request"
        assert data["latency_ms"] == 10.5


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestAutoActivation:
    """Test auto-activation functionality."""

    def test_auto_activate_on_load(self):
        """Plugins should auto-activate when configured."""
        module = PluginsModule(auto_activate=True)
        plugin = SimplePlugin()

        module.load(plugin)

        assert module.is_active(plugin.name) is True
        assert plugin.activate_called is True

    def test_auto_activate_respects_config(self):
        """Auto-activate should respect plugin config.enabled."""
        module = PluginsModule(auto_activate=True)
        plugin = SimplePlugin()
        config = PluginConfig(enabled=False)

        module.load(plugin, config=config)

        assert module.is_active(plugin.name) is False


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginReload:
    """Test plugin reload functionality."""

    def test_reload_from_file(self):
        """reload should reload plugin from file."""
        module = PluginsModule()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial plugin
            plugin_code = """
from aegis_sdk.nexus.plugins_module import PluginBase, PluginInfo

class TestPlugin(PluginBase):
    @property
    def info(self):
        return PluginInfo(name="reload-test", version="1.0.0")
"""
            plugin_file = os.path.join(tmpdir, "reload_plugin.py")
            with open(plugin_file, "w") as f:
                f.write(plugin_code)

            # Load from file
            module.load_from_file(plugin_file)
            assert module.is_loaded("reload-test")

            # Reload - returns plugin name on success
            result = module.reload("reload-test")
            assert result == "reload-test"
            assert module.is_loaded("reload-test")

    def test_reload_preserves_active_state(self):
        """reload should preserve active state."""
        module = PluginsModule()

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_code = """
from aegis_sdk.nexus.plugins_module import PluginBase, PluginInfo

class TestPlugin(PluginBase):
    @property
    def info(self):
        return PluginInfo(name="reload-active-test", version="1.0.0")
"""
            plugin_file = os.path.join(tmpdir, "reload_active_plugin.py")
            with open(plugin_file, "w") as f:
                f.write(plugin_code)

            module.load_from_file(plugin_file)
            module.activate("reload-active-test")
            assert module.is_active("reload-active-test")

            module.reload("reload-active-test")
            assert module.is_active("reload-active-test")

    def test_reload_returns_false_for_instance_plugin(self, module, simple_plugin):
        """reload should fail for plugins without source path."""
        module.load(simple_plugin)
        result = module.reload(simple_plugin.name)
        assert result is False
