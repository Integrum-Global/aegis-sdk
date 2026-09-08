"""
Tier 1: Unit Tests for Nexus Workflow Registry.

Tests workflow registration, discovery, and management functionality.
"""

import pytest

from aegis_sdk.nexus.workflows import (
    WorkflowPriority,
    WorkflowRegistration,
    WorkflowRegistry,
    WorkflowStatus,
)


@pytest.fixture
def registry():
    """Create a fresh workflow registry for each test."""
    return WorkflowRegistry()


@pytest.fixture
def sample_handler():
    """Sample workflow handler."""

    def handler(inputs):
        return {"result": inputs.get("value", 0) * 2}

    return handler


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowRegistration:
    """Test WorkflowRegistration dataclass."""

    def test_registration_creation(self, sample_handler):
        """Registration should be created with required fields."""
        reg = WorkflowRegistration(
            name="test-workflow",
            version="1.0.0",
            channels=["api", "cli"],
            handler=sample_handler,
        )
        assert reg.name == "test-workflow"
        assert reg.version == "1.0.0"
        assert reg.channels == ["api", "cli"]
        assert callable(reg.handler)

    def test_registration_normalizes_channels(self, sample_handler):
        """Channels should be normalized to lowercase."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["API", "CLI", "MCP"],
            handler=sample_handler,
        )
        assert reg.channels == ["api", "cli", "mcp"]

    def test_registration_normalizes_tags(self, sample_handler):
        """Tags should be normalized to lowercase."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["api"],
            handler=sample_handler,
            tags=["DATA", "Processing", " TRIM "],
        )
        assert reg.tags == ["data", "processing", "trim"]

    def test_registration_validation_passes(self, sample_handler):
        """Valid registration should pass validation."""
        reg = WorkflowRegistration(
            name="valid-workflow",
            version="1.0.0",
            channels=["api"],
            handler=sample_handler,
        )
        errors = reg.validate()
        assert len(errors) == 0

    def test_registration_validation_fails_empty_name(self, sample_handler):
        """Empty name should fail validation."""
        reg = WorkflowRegistration(
            name="",
            version="1.0.0",
            channels=["api"],
            handler=sample_handler,
        )
        errors = reg.validate()
        assert any("name" in e for e in errors)

    def test_registration_validation_fails_invalid_channel(self, sample_handler):
        """Invalid channel should fail validation."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["invalid"],
            handler=sample_handler,
        )
        errors = reg.validate()
        assert any("channel" in e.lower() for e in errors)

    def test_registration_validation_fails_no_channels(self, sample_handler):
        """No channels should fail validation."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=[],
            handler=sample_handler,
        )
        errors = reg.validate()
        assert any("channel" in e.lower() for e in errors)

    def test_registration_is_channel_enabled(self, sample_handler):
        """is_channel_enabled should check channel availability."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["api", "cli"],
            handler=sample_handler,
        )
        assert reg.is_channel_enabled("api") is True
        assert reg.is_channel_enabled("API") is True  # Case insensitive
        assert reg.is_channel_enabled("mcp") is False

    def test_registration_enable_channel(self, sample_handler):
        """enable_channel should add channel."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["api"],
            handler=sample_handler,
        )
        reg.enable_channel("mcp")
        assert "mcp" in reg.channels

    def test_registration_disable_channel(self, sample_handler):
        """disable_channel should remove channel."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["api", "cli"],
            handler=sample_handler,
        )
        reg.disable_channel("cli")
        assert "cli" not in reg.channels

    def test_registration_to_dict(self, sample_handler):
        """to_dict should return dictionary representation."""
        reg = WorkflowRegistration(
            name="test",
            version="1.0.0",
            channels=["api"],
            handler=sample_handler,
            description="Test workflow",
        )
        data = reg.to_dict()
        assert data["name"] == "test"
        assert data["version"] == "1.0.0"
        assert data["channels"] == ["api"]
        assert data["description"] == "Test workflow"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowRegistry:
    """Test WorkflowRegistry class."""

    def test_registry_register_workflow(self, registry, sample_handler):
        """register should add workflow to registry."""
        reg = registry.register("test-workflow", sample_handler)
        assert reg.name == "test-workflow"
        assert "test-workflow" in registry

    def test_registry_register_with_options(self, registry, sample_handler):
        """register should accept all options."""
        reg = registry.register(
            name="test-workflow",
            handler=sample_handler,
            version="2.0.0",
            channels=["api"],
            description="A test workflow",
            tags=["test", "example"],
            priority=WorkflowPriority.HIGH,
        )
        assert reg.version == "2.0.0"
        assert reg.channels == ["api"]
        assert reg.description == "A test workflow"
        assert reg.tags == ["test", "example"]
        assert reg.priority == WorkflowPriority.HIGH

    def test_registry_register_raises_on_invalid(self, registry):
        """register should raise on invalid workflow."""
        with pytest.raises(ValueError):
            registry.register("", lambda x: x)  # Empty name

    def test_registry_get_workflow(self, registry, sample_handler):
        """get should return registered workflow."""
        registry.register("test-workflow", sample_handler)
        workflow = registry.get("test-workflow")
        assert workflow is not None
        assert workflow.name == "test-workflow"

    def test_registry_get_returns_none_for_missing(self, registry):
        """get should return None for missing workflow."""
        workflow = registry.get("nonexistent")
        assert workflow is None

    def test_registry_get_or_raise(self, registry, sample_handler):
        """get_or_raise should raise KeyError for missing."""
        registry.register("exists", sample_handler)
        assert registry.get_or_raise("exists") is not None
        with pytest.raises(KeyError):
            registry.get_or_raise("missing")

    def test_registry_unregister(self, registry, sample_handler):
        """unregister should remove workflow."""
        registry.register("test-workflow", sample_handler)
        assert registry.unregister("test-workflow") is True
        assert "test-workflow" not in registry

    def test_registry_unregister_returns_false_for_missing(self, registry):
        """unregister should return False for missing workflow."""
        assert registry.unregister("nonexistent") is False

    def test_registry_list_all(self, registry, sample_handler):
        """list_all should return all workflows."""
        registry.register("workflow-1", sample_handler)
        registry.register("workflow-2", sample_handler)
        workflows = registry.list_all()
        assert len(workflows) == 2

    def test_registry_list_by_channel(self, registry, sample_handler):
        """list_by_channel should filter by channel."""
        registry.register("api-only", sample_handler, channels=["api"])
        registry.register("all-channels", sample_handler, channels=["api", "cli", "mcp"])

        api_workflows = registry.list_by_channel("api")
        assert len(api_workflows) == 2

        mcp_workflows = registry.list_by_channel("mcp")
        assert len(mcp_workflows) == 1

    def test_registry_list_by_tag(self, registry, sample_handler):
        """list_by_tag should filter by tag."""
        registry.register("data-workflow", sample_handler, tags=["data"])
        registry.register("api-workflow", sample_handler, tags=["api"])

        data_workflows = registry.list_by_tag("data")
        assert len(data_workflows) == 1
        assert data_workflows[0].name == "data-workflow"

    def test_registry_list_by_status(self, registry, sample_handler):
        """list_by_status should filter by status."""
        registry.register("active-workflow", sample_handler)
        registry.register("deprecated-workflow", sample_handler)
        registry.update_status("deprecated-workflow", WorkflowStatus.DEPRECATED)

        active = registry.list_by_status(WorkflowStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].name == "active-workflow"

    def test_registry_search_by_query(self, registry, sample_handler):
        """search should filter by name/description."""
        registry.register("data-processor", sample_handler, description="Processes data")
        registry.register("api-handler", sample_handler, description="Handles API requests")

        results = registry.search(query="data")
        assert len(results) == 1
        assert results[0].name == "data-processor"

    def test_registry_search_by_multiple_criteria(self, registry, sample_handler):
        """search should combine multiple filters."""
        registry.register("workflow-1", sample_handler, channels=["api"], tags=["data"])
        registry.register("workflow-2", sample_handler, channels=["api", "cli"], tags=["data"])

        results = registry.search(channels=["api", "cli"], tags=["data"])
        assert len(results) == 1
        assert results[0].name == "workflow-2"

    def test_registry_update_status(self, registry, sample_handler):
        """update_status should change workflow status."""
        registry.register("test-workflow", sample_handler)
        result = registry.update_status("test-workflow", WorkflowStatus.DISABLED)
        assert result is True
        assert registry.get("test-workflow").status == WorkflowStatus.DISABLED

    def test_registry_get_version_history(self, registry, sample_handler):
        """get_version_history should track versions."""
        registry.register("test-workflow", sample_handler, version="1.0.0")
        registry.register("test-workflow", sample_handler, version="1.1.0")

        history = registry.get_version_history("test-workflow")
        assert "1.0.0" in history
        assert "1.1.0" in history

    def test_registry_get_stats(self, registry, sample_handler):
        """get_stats should return registry statistics."""
        registry.register("workflow-1", sample_handler, channels=["api"])
        registry.register("workflow-2", sample_handler, channels=["api", "cli"])

        stats = registry.get_stats()
        assert stats["total_workflows"] == 2
        assert stats["by_channel"]["api"] == 2
        assert stats["by_channel"]["cli"] == 1

    def test_registry_clear(self, registry, sample_handler):
        """clear should remove all workflows."""
        registry.register("workflow-1", sample_handler)
        registry.register("workflow-2", sample_handler)

        count = registry.clear()
        assert count == 2
        assert len(registry) == 0

    def test_registry_len(self, registry, sample_handler):
        """__len__ should return workflow count."""
        assert len(registry) == 0
        registry.register("workflow-1", sample_handler)
        assert len(registry) == 1

    def test_registry_contains(self, registry, sample_handler):
        """__contains__ should check workflow existence."""
        registry.register("test-workflow", sample_handler)
        assert "test-workflow" in registry
        assert "missing" not in registry

    def test_registry_iter(self, registry, sample_handler):
        """__iter__ should iterate over workflows."""
        registry.register("workflow-1", sample_handler)
        registry.register("workflow-2", sample_handler)

        names = [w.name for w in registry]
        assert "workflow-1" in names
        assert "workflow-2" in names
