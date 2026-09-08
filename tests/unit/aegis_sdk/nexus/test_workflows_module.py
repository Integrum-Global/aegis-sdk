"""
Tier 1: Unit Tests for Nexus Workflows Module.

Tests dynamic workflow registration, versioning, metadata extraction,
and execution capabilities.
"""

import asyncio
from datetime import datetime

import pytest

from aegis_sdk.nexus.workflows_module import (
    MetadataExtractor,
    ModuleWorkflowRegistration,
    ValidationMode,
    WorkflowExecutionResult,
    WorkflowModuleStatus,
    WorkflowRegistrySingleton,
    WorkflowSchema,
    WorkflowsModule,
    WorkflowVersionInfo,
)


@pytest.fixture
def module():
    """Create a fresh workflows module for each test."""
    return WorkflowsModule()


@pytest.fixture
def sample_handler():
    """Sample sync workflow handler."""

    def handler(inputs):
        return {"result": inputs.get("value", 0) * 2}

    return handler


@pytest.fixture
def async_handler():
    """Sample async workflow handler."""

    async def handler(inputs):
        await asyncio.sleep(0.001)
        return {"result": inputs.get("value", 0) * 2}

    return handler


@pytest.fixture
def typed_handler():
    """Sample typed workflow handler."""

    def handler(value: int, name: str = "default") -> dict:
        """Process value and name."""
        return {"value": value, "name": name}

    return handler


# Reset singleton before each test that uses it
@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    WorkflowRegistrySingleton.reset_instance()
    yield
    WorkflowRegistrySingleton.reset_instance()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowSchema:
    """Test WorkflowSchema class."""

    def test_schema_creation_defaults(self):
        """Schema should have sensible defaults."""
        schema = WorkflowSchema()
        assert schema.type == "object"
        assert schema.properties == {}
        assert schema.required == []
        assert schema.additional_properties is True

    def test_schema_validate_valid_data(self):
        """Schema should validate valid data."""
        schema = WorkflowSchema(
            properties={"value": {"type": "integer"}},
            required=["value"],
        )
        is_valid, errors = schema.validate({"value": 42})
        assert is_valid is True
        assert len(errors) == 0

    def test_schema_validate_missing_required(self):
        """Schema should detect missing required fields."""
        schema = WorkflowSchema(
            properties={"value": {"type": "integer"}},
            required=["value"],
        )
        is_valid, errors = schema.validate({})
        assert is_valid is False
        assert any("value" in e for e in errors)

    def test_schema_validate_wrong_type(self):
        """Schema should detect wrong types."""
        schema = WorkflowSchema(
            properties={"value": {"type": "integer"}},
        )
        is_valid, errors = schema.validate({"value": "not an int"})
        assert is_valid is False
        assert any("integer" in e for e in errors)

    def test_schema_validate_additional_properties(self):
        """Schema should detect unexpected properties when disabled."""
        schema = WorkflowSchema(
            properties={"value": {"type": "integer"}},
            additional_properties=False,
        )
        is_valid, errors = schema.validate({"value": 42, "extra": "field"})
        assert is_valid is False
        assert any("extra" in str(e) for e in errors)

    def test_schema_to_dict(self):
        """Schema should convert to dictionary."""
        schema = WorkflowSchema(
            type="object",
            properties={"value": {"type": "integer"}},
            required=["value"],
            description="Test schema",
        )
        data = schema.to_dict()
        assert data["type"] == "object"
        assert "value" in data["properties"]
        assert "value" in data["required"]


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowVersionInfo:
    """Test WorkflowVersionInfo class."""

    def test_version_info_creation(self, sample_handler):
        """VersionInfo should be created with handler."""
        version = WorkflowVersionInfo(
            version="1.0.0",
            handler=sample_handler,
        )
        assert version.version == "1.0.0"
        assert callable(version.handler)
        assert version.deprecated is False

    def test_version_comparison(self, sample_handler):
        """Versions should compare correctly."""
        v1 = WorkflowVersionInfo(version="1.0.0", handler=sample_handler)
        v2 = WorkflowVersionInfo(version="1.1.0", handler=sample_handler)
        v3 = WorkflowVersionInfo(version="2.0.0", handler=sample_handler)

        assert v1 < v2
        assert v2 < v3
        assert v1 < v3

    def test_version_equality(self, sample_handler):
        """Same version strings should be equal."""
        v1 = WorkflowVersionInfo(version="1.0.0", handler=sample_handler)
        v2 = WorkflowVersionInfo(version="1.0.0", handler=sample_handler)

        assert v1 == v2


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestMetadataExtractor:
    """Test MetadataExtractor class."""

    def test_extract_basic_metadata(self, sample_handler):
        """Extractor should extract basic metadata."""
        metadata = MetadataExtractor.extract(
            handler=sample_handler,
            name="test-workflow",
        )
        assert metadata.name == "test-workflow"
        assert metadata.is_async is False

    def test_extract_async_handler(self, async_handler):
        """Extractor should detect async handlers."""
        metadata = MetadataExtractor.extract(
            handler=async_handler,
            name="async-workflow",
        )
        assert metadata.is_async is True

    def test_extract_description_from_docstring(self, typed_handler):
        """Extractor should extract description from docstring."""
        metadata = MetadataExtractor.extract(
            handler=typed_handler,
            name="typed-workflow",
        )
        assert "Process value" in metadata.description

    def test_extract_parameter_names(self, typed_handler):
        """Extractor should extract parameter names."""
        metadata = MetadataExtractor.extract(
            handler=typed_handler,
            name="typed-workflow",
        )
        assert "value" in metadata.parameter_names
        assert "name" in metadata.parameter_names

    def test_extract_with_override_description(self, sample_handler):
        """Extractor should use override description."""
        metadata = MetadataExtractor.extract(
            handler=sample_handler,
            name="test-workflow",
            description="Custom description",
        )
        assert metadata.description == "Custom description"

    def test_extract_with_input_schema(self, sample_handler):
        """Extractor should use provided input schema."""
        metadata = MetadataExtractor.extract(
            handler=sample_handler,
            name="test-workflow",
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        )
        assert metadata.input_schema is not None
        assert "value" in metadata.input_schema.properties


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestModuleWorkflowRegistration:
    """Test ModuleWorkflowRegistration class."""

    def test_registration_creation(self, sample_handler):
        """Registration should be created with required fields."""
        metadata = MetadataExtractor.extract(sample_handler, "test")
        reg = ModuleWorkflowRegistration(
            name="test-workflow",
            metadata=metadata,
            versions={"1.0.0": WorkflowVersionInfo("1.0.0", sample_handler)},
        )
        assert reg.name == "test-workflow"
        assert reg.status == WorkflowModuleStatus.ACTIVE

    def test_registration_get_handler(self, sample_handler):
        """get_handler should return handler for version."""
        metadata = MetadataExtractor.extract(sample_handler, "test")
        reg = ModuleWorkflowRegistration(
            name="test-workflow",
            metadata=metadata,
            versions={
                "1.0.0": WorkflowVersionInfo("1.0.0", sample_handler),
                "1.1.0": WorkflowVersionInfo("1.1.0", sample_handler),
            },
            latest_version="1.1.0",
        )

        handler = reg.get_handler("1.0.0")
        assert callable(handler)

        handler = reg.get_handler()  # Latest
        assert callable(handler)

    def test_registration_list_versions(self, sample_handler):
        """list_versions should return sorted versions."""
        metadata = MetadataExtractor.extract(sample_handler, "test")
        reg = ModuleWorkflowRegistration(
            name="test-workflow",
            metadata=metadata,
            versions={
                "1.0.0": WorkflowVersionInfo("1.0.0", sample_handler),
                "2.0.0": WorkflowVersionInfo("2.0.0", sample_handler),
                "1.5.0": WorkflowVersionInfo("1.5.0", sample_handler),
            },
            latest_version="2.0.0",
        )

        versions = reg.list_versions()
        assert versions[0] == "2.0.0"  # Newest first
        assert versions[-1] == "1.0.0"  # Oldest last

    def test_registration_validate_valid(self, sample_handler):
        """Valid registration should pass validation."""
        metadata = MetadataExtractor.extract(sample_handler, "test")
        reg = ModuleWorkflowRegistration(
            name="test-workflow",
            metadata=metadata,
            versions={"1.0.0": WorkflowVersionInfo("1.0.0", sample_handler)},
        )
        errors = reg.validate()
        assert len(errors) == 0

    def test_registration_validate_empty_name(self, sample_handler):
        """Empty name should fail validation."""
        metadata = MetadataExtractor.extract(sample_handler, "")
        reg = ModuleWorkflowRegistration(
            name="",
            metadata=metadata,
            versions={"1.0.0": WorkflowVersionInfo("1.0.0", sample_handler)},
        )
        errors = reg.validate()
        assert any("name" in e for e in errors)

    def test_registration_to_dict(self, sample_handler):
        """to_dict should return dictionary representation."""
        metadata = MetadataExtractor.extract(sample_handler, "test")
        reg = ModuleWorkflowRegistration(
            name="test-workflow",
            metadata=metadata,
            versions={"1.0.0": WorkflowVersionInfo("1.0.0", sample_handler)},
        )
        data = reg.to_dict()
        assert data["name"] == "test-workflow"
        assert "1.0.0" in data["versions"]


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowsModule:
    """Test WorkflowsModule class."""

    def test_module_register_workflow(self, module, sample_handler):
        """register should add workflow to module."""
        reg = module.register("test-workflow", sample_handler)
        assert reg.name == "test-workflow"
        assert "test-workflow" in module

    def test_module_register_with_options(self, module, sample_handler):
        """register should accept all options."""
        reg = module.register(
            name="test-workflow",
            handler=sample_handler,
            version="2.0.0",
            description="Test workflow",
            author="Test Author",
            tags=["test", "example"],
            channels=["api", "cli"],
        )
        assert reg.metadata.description == "Test workflow"
        assert reg.metadata.author == "Test Author"
        assert "test" in reg.metadata.tags
        assert "api" in reg.channels

    def test_module_register_raises_on_invalid_handler(self, module):
        """register should raise on non-callable handler."""
        with pytest.raises(ValueError):
            module.register("test", "not a callable")

    def test_module_register_multiple_versions(self, module, sample_handler):
        """register should support multiple versions."""
        module.register("test-workflow", sample_handler, version="1.0.0")
        module.register("test-workflow", sample_handler, version="1.1.0")
        module.register("test-workflow", sample_handler, version="2.0.0")

        reg = module.get("test-workflow")
        versions = reg.list_versions()
        assert len(versions) == 3
        assert reg.latest_version == "2.0.0"

    def test_module_unregister_workflow(self, module, sample_handler):
        """unregister should remove workflow."""
        module.register("test-workflow", sample_handler)
        assert module.unregister("test-workflow") is True
        assert "test-workflow" not in module

    def test_module_unregister_specific_version(self, module, sample_handler):
        """unregister should remove specific version."""
        module.register("test-workflow", sample_handler, version="1.0.0")
        module.register("test-workflow", sample_handler, version="1.1.0")

        assert module.unregister("test-workflow", version="1.0.0") is True
        reg = module.get("test-workflow")
        assert "1.0.0" not in reg.list_versions()
        assert "1.1.0" in reg.list_versions()

    def test_module_list_all(self, module, sample_handler):
        """list should return all workflows."""
        module.register("workflow-1", sample_handler)
        module.register("workflow-2", sample_handler)

        workflows = module.list()
        assert len(workflows) == 2

    def test_module_list_by_channel(self, module, sample_handler):
        """list should filter by channel."""
        module.register("api-only", sample_handler, channels=["api"])
        module.register("all-channels", sample_handler, channels=["api", "cli", "mcp"])

        api_workflows = module.list(channel="api")
        assert len(api_workflows) == 2

        mcp_workflows = module.list(channel="mcp")
        assert len(mcp_workflows) == 1

    def test_module_list_by_tags(self, module, sample_handler):
        """list should filter by tags."""
        module.register("data-workflow", sample_handler, tags=["data", "processing"])
        module.register("api-workflow", sample_handler, tags=["api"])

        data_workflows = module.list(tags=["data"])
        assert len(data_workflows) == 1
        assert data_workflows[0].name == "data-workflow"

    def test_module_get_workflow(self, module, sample_handler):
        """get should return registered workflow."""
        module.register("test-workflow", sample_handler)
        reg = module.get("test-workflow")
        assert reg is not None
        assert reg.name == "test-workflow"

    def test_module_get_returns_none_for_missing(self, module):
        """get should return None for missing workflow."""
        assert module.get("nonexistent") is None

    def test_module_get_handler(self, module, sample_handler):
        """get_handler should return handler for version."""
        module.register("test-workflow", sample_handler, version="1.0.0")
        handler = module.get_handler("test-workflow", version="1.0.0")
        assert callable(handler)

    def test_module_get_versions(self, module, sample_handler):
        """get_versions should return available versions."""
        module.register("test-workflow", sample_handler, version="1.0.0")
        module.register("test-workflow", sample_handler, version="1.1.0")

        versions = module.get_versions("test-workflow")
        assert "1.0.0" in versions
        assert "1.1.0" in versions

    @pytest.mark.asyncio
    async def test_module_execute_sync_handler(self, module, sample_handler):
        """execute should run sync handler."""
        module.register("test-workflow", sample_handler)
        result = await module.execute("test-workflow", {"value": 21})

        assert result.success is True
        assert result.result["result"] == 42

    @pytest.mark.asyncio
    async def test_module_execute_async_handler(self, module, async_handler):
        """execute should run async handler."""
        module.register("async-workflow", async_handler)
        result = await module.execute("async-workflow", {"value": 21})

        assert result.success is True
        assert result.result["result"] == 42

    @pytest.mark.asyncio
    async def test_module_execute_specific_version(self, module, sample_handler):
        """execute should run specific version."""

        def v1_handler(inputs):
            return {"version": "1.0.0", "value": inputs.get("value", 0)}

        def v2_handler(inputs):
            return {"version": "2.0.0", "value": inputs.get("value", 0) * 2}

        module.register("test-workflow", v1_handler, version="1.0.0")
        module.register("test-workflow", v2_handler, version="2.0.0")

        # Execute v1
        result = await module.execute("test-workflow", {"value": 10}, version="1.0.0")
        assert result.result["version"] == "1.0.0"
        assert result.result["value"] == 10

        # Execute latest (v2)
        result = await module.execute("test-workflow", {"value": 10})
        assert result.result["version"] == "2.0.0"
        assert result.result["value"] == 20

    @pytest.mark.asyncio
    async def test_module_execute_missing_workflow(self, module):
        """execute should return error for missing workflow."""
        result = await module.execute("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_module_execute_disabled_workflow(self, module, sample_handler):
        """execute should return error for disabled workflow."""
        module.register("test-workflow", sample_handler)
        module.set_status("test-workflow", WorkflowModuleStatus.DISABLED)

        result = await module.execute("test-workflow", {})
        assert result.success is False
        assert "disabled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_module_execute_with_validation_strict(self, sample_handler):
        """execute should fail on invalid inputs in strict mode."""
        module = WorkflowsModule(validation_mode=ValidationMode.STRICT)
        module.register(
            "test-workflow",
            sample_handler,
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        )

        result = await module.execute("test-workflow", {})  # Missing required
        assert result.success is False
        assert "validation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_module_execute_updates_stats(self, module, sample_handler):
        """execute should update execution statistics."""
        module.register("test-workflow", sample_handler)

        await module.execute("test-workflow", {"value": 1})
        await module.execute("test-workflow", {"value": 2})

        reg = module.get("test-workflow")
        assert reg.execution_count == 2
        assert reg.last_executed is not None

    def test_module_deprecate_version(self, module, sample_handler):
        """deprecate_version should mark version as deprecated."""
        module.register("test-workflow", sample_handler, version="1.0.0")
        result = module.deprecate_version("test-workflow", "1.0.0", "Use v2")

        assert result is True
        reg = module.get("test-workflow")
        assert reg.versions["1.0.0"].deprecated is True
        assert "Use v2" in reg.versions["1.0.0"].deprecation_message

    def test_module_set_status(self, module, sample_handler):
        """set_status should update workflow status."""
        module.register("test-workflow", sample_handler)
        module.set_status("test-workflow", WorkflowModuleStatus.DEPRECATED)

        reg = module.get("test-workflow")
        assert reg.status == WorkflowModuleStatus.DEPRECATED

    def test_module_get_stats(self, module, sample_handler):
        """get_stats should return module statistics."""
        module.register("workflow-1", sample_handler)
        module.register("workflow-2", sample_handler)

        stats = module.get_stats()
        assert stats["total_workflows"] == 2
        assert stats["by_status"]["active"] == 2

    def test_module_clear(self, module, sample_handler):
        """clear should remove all workflows."""
        module.register("workflow-1", sample_handler)
        module.register("workflow-2", sample_handler)

        count = module.clear()
        assert count == 2
        assert len(module) == 0

    def test_module_len(self, module, sample_handler):
        """__len__ should return workflow count."""
        assert len(module) == 0
        module.register("workflow-1", sample_handler)
        assert len(module) == 1

    def test_module_contains(self, module, sample_handler):
        """__contains__ should check workflow existence."""
        module.register("test-workflow", sample_handler)
        assert "test-workflow" in module
        assert "missing" not in module

    def test_module_iter(self, module, sample_handler):
        """__iter__ should iterate over workflows."""
        module.register("workflow-1", sample_handler)
        module.register("workflow-2", sample_handler)

        names = [w.name for w in module]
        assert "workflow-1" in names
        assert "workflow-2" in names


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowRegistrySingleton:
    """Test WorkflowRegistrySingleton class."""

    def test_singleton_instance(self):
        """Should return same instance."""
        instance1 = WorkflowRegistrySingleton.get_instance()
        instance2 = WorkflowRegistrySingleton.get_instance()
        assert instance1 is instance2

    def test_singleton_register(self, sample_handler):
        """Singleton should support registration."""
        registry = WorkflowRegistrySingleton.get_instance()
        reg = registry.register("test-workflow", sample_handler)
        assert reg.name == "test-workflow"
        assert "test-workflow" in registry

    def test_singleton_unregister(self, sample_handler):
        """Singleton should support unregistration."""
        registry = WorkflowRegistrySingleton.get_instance()
        registry.register("test-workflow", sample_handler)
        assert registry.unregister("test-workflow") is True
        assert "test-workflow" not in registry

    def test_singleton_list(self, sample_handler):
        """Singleton should support listing."""
        registry = WorkflowRegistrySingleton.get_instance()
        registry.register("workflow-1", sample_handler)
        registry.register("workflow-2", sample_handler)

        workflows = registry.list()
        assert len(workflows) == 2

    def test_singleton_get(self, sample_handler):
        """Singleton should support getting."""
        registry = WorkflowRegistrySingleton.get_instance()
        registry.register("test-workflow", sample_handler)

        reg = registry.get("test-workflow")
        assert reg is not None

    @pytest.mark.asyncio
    async def test_singleton_execute(self, sample_handler):
        """Singleton should support execution."""
        registry = WorkflowRegistrySingleton.get_instance()
        registry.register("test-workflow", sample_handler)

        result = await registry.execute("test-workflow", {"value": 21})
        assert result.success is True
        assert result.result["result"] == 42

    def test_singleton_reset(self, sample_handler):
        """reset_instance should clear singleton."""
        registry1 = WorkflowRegistrySingleton.get_instance()
        registry1.register("test-workflow", sample_handler)

        WorkflowRegistrySingleton.reset_instance()

        registry2 = WorkflowRegistrySingleton.get_instance()
        assert "test-workflow" not in registry2
        assert registry1 is not registry2


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestWorkflowExecutionResult:
    """Test WorkflowExecutionResult class."""

    def test_result_creation(self):
        """Result should be created with required fields."""
        result = WorkflowExecutionResult(
            success=True,
            workflow_name="test-workflow",
            version="1.0.0",
            result={"value": 42},
        )
        assert result.success is True
        assert result.workflow_name == "test-workflow"
        assert result.result["value"] == 42

    def test_result_duration_ms(self):
        """duration_ms should calculate duration."""
        started = datetime(2024, 1, 1, 12, 0, 0)
        completed = datetime(2024, 1, 1, 12, 0, 1)  # 1 second later

        result = WorkflowExecutionResult(
            success=True,
            workflow_name="test",
            version="1.0.0",
            started_at=started,
            completed_at=completed,
        )
        assert result.duration_ms == 1000.0

    def test_result_to_dict(self):
        """to_dict should return dictionary representation."""
        result = WorkflowExecutionResult(
            success=True,
            workflow_name="test-workflow",
            version="1.0.0",
            result={"value": 42},
            execution_id="exec-123",
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["workflow_name"] == "test-workflow"
        assert data["execution_id"] == "exec-123"
