"""Comprehensive tests for Nexus REST Tier deployment module.

Tests cover:
- AuthMode enum (3 tests)
- RESTEndpoint validation (4 tests)
- RESTConfig validation (5 tests)
- WorkflowSchema (3 tests)
- RESTWorkflowRegistration (5 tests)
- ExecutionResult (3 tests)
- RESTTierDeployer (15 tests)

Total: 38 tests
"""

from datetime import datetime

import pytest

from aegis_sdk.nexus.rest_tier import (
    AuthMode,
    ExecutionResult,
    RESTConfig,
    RESTEndpoint,
    RESTTierDeployer,
    RESTWorkflowRegistration,
    WorkflowSchema,
)

# ==============================================================================
# AuthMode Tests (3 tests)
# ==============================================================================


class TestAuthMode:
    """Tests for AuthMode enum."""

    def test_auth_mode_values_exist(self):
        """Test that all expected auth mode values exist."""
        assert AuthMode.NONE is not None
        assert AuthMode.API_KEY is not None
        assert AuthMode.OAUTH2 is not None
        assert AuthMode.JWT is not None

    def test_auth_mode_from_string_valid(self):
        """Test from_string with valid values."""
        assert AuthMode.from_string("none") == AuthMode.NONE
        assert AuthMode.from_string("api_key") == AuthMode.API_KEY
        assert AuthMode.from_string("apikey") == AuthMode.API_KEY
        assert AuthMode.from_string("oauth2") == AuthMode.OAUTH2
        assert AuthMode.from_string("jwt") == AuthMode.JWT
        assert AuthMode.from_string("bearer") == AuthMode.JWT

    def test_auth_mode_from_string_invalid_raises(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid auth mode"):
            AuthMode.from_string("invalid")
        with pytest.raises(ValueError, match="Invalid auth mode"):
            AuthMode.from_string("")


# ==============================================================================
# RESTEndpoint Tests (4 tests)
# ==============================================================================


class TestRESTEndpoint:
    """Tests for RESTEndpoint dataclass."""

    def test_endpoint_defaults(self):
        """Test RESTEndpoint default values."""
        endpoint = RESTEndpoint(
            path="/test",
            method="GET",
            handler=lambda: None,
        )
        assert endpoint.auth_required is True
        assert endpoint.rate_limit is None
        assert endpoint.description == ""

    def test_endpoint_valid_config(self):
        """Test RESTEndpoint with valid configuration."""
        endpoint = RESTEndpoint(
            path="/workflows/test/execute",
            method="POST",
            handler=lambda x: x,
            auth_required=True,
            rate_limit=100,
            description="Test endpoint",
        )
        errors = endpoint.validate()
        assert errors == []

    def test_endpoint_invalid_path(self):
        """Test RESTEndpoint validation catches invalid path."""
        endpoint = RESTEndpoint(
            path="no-leading-slash",
            method="GET",
            handler=lambda: None,
        )
        errors = endpoint.validate()
        assert any("path must start with '/'" in e for e in errors)

    def test_endpoint_invalid_method(self):
        """Test RESTEndpoint validation catches invalid method."""
        endpoint = RESTEndpoint(
            path="/test",
            method="INVALID",
            handler=lambda: None,
        )
        errors = endpoint.validate()
        assert any("Invalid method" in e for e in errors)


# ==============================================================================
# RESTConfig Tests (5 tests)
# ==============================================================================


class TestRESTConfig:
    """Tests for RESTConfig dataclass."""

    def test_rest_config_defaults(self):
        """Test RESTConfig default values."""
        config = RESTConfig()
        assert config.port == 8000
        assert config.host == "0.0.0.0"
        assert config.auth_mode == AuthMode.NONE
        assert config.enable_docs is True
        assert config.timeout_s == 300

    def test_rest_config_valid(self):
        """Test RESTConfig with valid configuration."""
        config = RESTConfig(
            port=8080,
            host="127.0.0.1",
            auth_mode=AuthMode.API_KEY,
            rate_limit=200,
            timeout_s=60,
        )
        errors = config.validate()
        assert errors == []

    def test_rest_config_invalid_port(self):
        """Test RESTConfig validation catches invalid port."""
        config = RESTConfig(port=70000)
        errors = config.validate()
        assert any("port must be between 1 and 65535" in e for e in errors)

    def test_rest_config_invalid_timeout(self):
        """Test RESTConfig validation catches invalid timeout."""
        config = RESTConfig(timeout_s=0)
        errors = config.validate()
        assert any("timeout_s must be >= 1" in e for e in errors)

    def test_rest_config_invalid_prefix(self):
        """Test RESTConfig validation catches invalid prefix."""
        config = RESTConfig(prefix="no-slash")
        errors = config.validate()
        assert any("prefix must start with '/'" in e for e in errors)


# ==============================================================================
# WorkflowSchema Tests (3 tests)
# ==============================================================================


class TestWorkflowSchema:
    """Tests for WorkflowSchema dataclass."""

    def test_schema_creation(self):
        """Test WorkflowSchema creation."""
        schema = WorkflowSchema(
            name="test-workflow",
            version="1.0.0",
            description="Test workflow",
        )
        assert schema.name == "test-workflow"
        assert schema.version == "1.0.0"

    def test_schema_with_json_schemas(self):
        """Test WorkflowSchema with input/output schemas."""
        schema = WorkflowSchema(
            name="test-workflow",
            input_schema={"type": "object", "properties": {"x": {"type": "number"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "number"}}},
        )
        assert "properties" in schema.input_schema
        assert "properties" in schema.output_schema

    def test_schema_to_dict(self):
        """Test WorkflowSchema serialization."""
        schema = WorkflowSchema(
            name="test-workflow",
            version="2.0.0",
            description="Test",
        )
        data = schema.to_dict()
        assert data["name"] == "test-workflow"
        assert data["version"] == "2.0.0"
        assert data["description"] == "Test"


# ==============================================================================
# RESTWorkflowRegistration Tests (5 tests)
# ==============================================================================


class TestRESTWorkflowRegistration:
    """Tests for RESTWorkflowRegistration dataclass."""

    def test_registration_defaults(self):
        """Test RESTWorkflowRegistration default values."""
        reg = RESTWorkflowRegistration(
            name="test",
            handler=lambda x: x,
        )
        assert reg.version == "1.0.0"
        assert reg.auth_required is True
        assert reg.timeout_s is None

    def test_registration_valid(self):
        """Test valid RESTWorkflowRegistration."""
        reg = RESTWorkflowRegistration(
            name="my-workflow",
            handler=lambda x: x * 2,
            version="1.0.0",
            description="Doubles the input",
            rate_limit=50,
        )
        errors = reg.validate()
        assert errors == []

    def test_registration_invalid_name(self):
        """Test RESTWorkflowRegistration validation catches invalid name."""
        reg = RESTWorkflowRegistration(
            name="",
            handler=lambda: None,
        )
        errors = reg.validate()
        assert any("name is required" in e for e in errors)

        reg = RESTWorkflowRegistration(
            name="invalid name with spaces",
            handler=lambda: None,
        )
        errors = reg.validate()
        assert any("alphanumeric" in e for e in errors)

    def test_registration_invalid_handler(self):
        """Test RESTWorkflowRegistration validation catches non-callable handler."""
        reg = RESTWorkflowRegistration(
            name="test",
            handler="not a callable",  # type: ignore
        )
        errors = reg.validate()
        assert any("handler must be callable" in e for e in errors)

    def test_registration_get_schema(self):
        """Test RESTWorkflowRegistration.get_schema() method."""
        reg = RESTWorkflowRegistration(
            name="test",
            handler=lambda x: x,
            version="2.0.0",
            description="Test workflow",
            input_schema={"type": "object"},
        )
        schema = reg.get_schema()
        assert schema.name == "test"
        assert schema.version == "2.0.0"
        assert schema.description == "Test workflow"


# ==============================================================================
# ExecutionResult Tests (3 tests)
# ==============================================================================


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_result_creation(self):
        """Test ExecutionResult creation."""
        result = ExecutionResult(
            success=True,
            workflow_name="test",
            result={"value": 42},
        )
        assert result.success is True
        assert result.result["value"] == 42

    def test_result_duration_calculation(self):
        """Test ExecutionResult duration calculation."""
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 1, 500000)  # 1.5 seconds later

        result = ExecutionResult(
            success=True,
            workflow_name="test",
            started_at=start,
            completed_at=end,
        )
        assert result.duration_ms == 1500.0

    def test_result_to_dict(self):
        """Test ExecutionResult serialization."""
        result = ExecutionResult(
            success=False,
            workflow_name="test",
            error="Something went wrong",
            execution_id="exec-123",
        )
        data = result.to_dict()
        assert data["success"] is False
        assert data["workflow_name"] == "test"
        assert data["error"] == "Something went wrong"
        assert data["execution_id"] == "exec-123"


# ==============================================================================
# RESTTierDeployer Tests (15 tests)
# ==============================================================================


class TestRESTTierDeployer:
    """Tests for RESTTierDeployer class."""

    @pytest.fixture
    def deployer(self):
        """Create a basic deployer for testing."""
        return RESTTierDeployer(
            config=RESTConfig(port=8000),
            name="test-deployer",
        )

    def test_deployer_creation(self, deployer):
        """Test deployer creation with default config."""
        assert deployer.name == "test-deployer"
        assert deployer.config.port == 8000
        assert deployer.is_running is False

    def test_deployer_register_workflow(self, deployer):
        """Test workflow registration."""
        reg = deployer.register_workflow(
            name="my-workflow",
            handler=lambda x: x,
            version="1.0.0",
        )
        assert reg.name == "my-workflow"
        assert "my-workflow" in deployer
        assert len(deployer) == 1

    def test_deployer_register_duplicate_raises(self, deployer):
        """Test registering duplicate workflow raises ValueError."""
        deployer.register_workflow(name="test", handler=lambda: None)
        with pytest.raises(ValueError, match="already registered"):
            deployer.register_workflow(name="test", handler=lambda: None)

    def test_deployer_unregister_workflow(self, deployer):
        """Test workflow unregistration."""
        deployer.register_workflow(name="test", handler=lambda: None)
        assert deployer.unregister_workflow("test") is True
        assert "test" not in deployer
        assert deployer.unregister_workflow("nonexistent") is False

    def test_deployer_get_workflow(self, deployer):
        """Test getting workflow registration."""
        deployer.register_workflow(name="test", handler=lambda: None)
        reg = deployer.get_workflow("test")
        assert reg is not None
        assert reg.name == "test"
        assert deployer.get_workflow("nonexistent") is None

    def test_deployer_list_workflows(self, deployer):
        """Test listing all workflows."""
        deployer.register_workflow(name="workflow1", handler=lambda: None)
        deployer.register_workflow(name="workflow2", handler=lambda: None)
        workflows = deployer.list_workflows()
        assert len(workflows) == 2
        names = [w.name for w in workflows]
        assert "workflow1" in names
        assert "workflow2" in names

    def test_deployer_api_key_management(self, deployer):
        """Test API key management."""
        deployer.add_api_key("test-key-1")
        deployer.add_api_key("test-key-2")
        # When auth_mode is NONE, all validation passes (no auth required)
        assert deployer.validate_api_key("test-key-1") is True
        assert deployer.validate_api_key("any-key") is True  # Any key works with NONE

        # Change to API key auth
        deployer._config.auth_mode = AuthMode.API_KEY
        assert deployer.validate_api_key("test-key-1") is True
        assert deployer.validate_api_key("invalid") is False

        assert deployer.remove_api_key("test-key-1") is True
        assert deployer.validate_api_key("test-key-1") is False

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_success(self, deployer):
        """Test successful workflow execution."""
        deployer.register_workflow(
            name="double",
            handler=lambda x: {"result": x.get("value", 0) * 2},
        )

        result = await deployer.execute_workflow("double", {"value": 21})
        assert result.success is True
        assert result.result["result"] == 42
        assert result.execution_id is not None

    @pytest.mark.asyncio
    async def test_deployer_execute_workflow_not_found(self, deployer):
        """Test execution of non-existent workflow."""
        result = await deployer.execute_workflow("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_deployer_execute_async_handler(self, deployer):
        """Test execution with async handler."""

        async def async_handler(inputs):
            return {"doubled": inputs.get("value", 0) * 2}

        deployer.register_workflow(name="async-workflow", handler=async_handler)

        result = await deployer.execute_workflow("async-workflow", {"value": 10})
        assert result.success is True
        assert result.result["doubled"] == 20

    def test_deployer_get_workflow_schema(self, deployer):
        """Test getting workflow schema."""
        deployer.register_workflow(
            name="test",
            handler=lambda: None,
            input_schema={"type": "object"},
        )
        schema = deployer.get_workflow_schema("test")
        assert schema is not None
        assert schema.name == "test"
        assert deployer.get_workflow_schema("nonexistent") is None

    @pytest.mark.asyncio
    async def test_deployer_start_and_stop(self, deployer):
        """Test deployer start and stop."""
        await deployer.start()
        assert deployer.is_running is True
        assert deployer.uptime_s is not None

        await deployer.stop()
        assert deployer.is_running is False

    @pytest.mark.asyncio
    async def test_deployer_start_with_invalid_config_raises(self):
        """Test start with invalid config raises ValueError."""
        deployer = RESTTierDeployer(config=RESTConfig(port=99999))
        with pytest.raises(ValueError, match="Invalid configuration"):
            await deployer.start()

    def test_deployer_health_check(self, deployer):
        """Test health check."""
        health = deployer.health_check()
        assert health["status"] == "stopped"
        assert health["name"] == "test-deployer"

    def test_deployer_get_stats(self, deployer):
        """Test getting deployer statistics."""
        deployer.register_workflow(name="test", handler=lambda: None)
        stats = deployer.get_stats()
        assert stats["name"] == "test-deployer"
        assert stats["workflows_count"] == 1
        assert "metrics" in stats

    def test_deployer_get_openapi_spec(self, deployer):
        """Test OpenAPI spec generation."""
        deployer.register_workflow(
            name="test-workflow",
            handler=lambda: None,
            description="Test workflow",
        )
        spec = deployer.get_openapi_spec()
        assert spec["openapi"] == "3.0.0"
        assert "paths" in spec
        assert "/workflows/test-workflow/execute" in spec["paths"]
        assert "/health" in spec["paths"]


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestRESTTierIntegration:
    """Integration tests for REST tier."""

    @pytest.mark.asyncio
    async def test_full_rest_tier_lifecycle(self):
        """Test complete REST tier lifecycle."""
        # Create deployer
        deployer = RESTTierDeployer(
            config=RESTConfig(port=8080, auth_mode=AuthMode.API_KEY),
            name="integration-test",
        )

        # Add API key
        deployer.add_api_key("test-key")

        # Register workflows
        deployer.register_workflow(
            name="add",
            handler=lambda x: {"sum": x.get("a", 0) + x.get("b", 0)},
            description="Add two numbers",
        )

        deployer.register_workflow(
            name="multiply",
            handler=lambda x: {"product": x.get("a", 0) * x.get("b", 0)},
            description="Multiply two numbers",
        )

        # Start
        await deployer.start()
        assert deployer.is_running

        # Execute workflows
        add_result = await deployer.execute_workflow("add", {"a": 5, "b": 3})
        assert add_result.success
        assert add_result.result["sum"] == 8

        mult_result = await deployer.execute_workflow("multiply", {"a": 4, "b": 7})
        assert mult_result.success
        assert mult_result.result["product"] == 28

        # Check stats
        stats = deployer.get_stats()
        assert stats["metrics"]["successful_requests"] == 2

        # Stop
        await deployer.stop()
        assert not deployer.is_running

    def test_multiple_deployers(self):
        """Test multiple deployers can coexist."""
        deployer1 = RESTTierDeployer(
            config=RESTConfig(port=8001),
            name="deployer-1",
        )
        deployer2 = RESTTierDeployer(
            config=RESTConfig(port=8002),
            name="deployer-2",
        )

        deployer1.register_workflow(name="wf1", handler=lambda: {"from": "deployer1"})
        deployer2.register_workflow(name="wf2", handler=lambda: {"from": "deployer2"})

        assert len(deployer1) == 1
        assert len(deployer2) == 1
        assert "wf1" in deployer1
        assert "wf2" in deployer2
        assert "wf1" not in deployer2
        assert "wf2" not in deployer1
