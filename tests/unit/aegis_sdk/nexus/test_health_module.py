"""
Tier 1: Unit Tests for Nexus Health Module.

Tests health check registration, execution, aggregation, and monitoring.
"""

import asyncio
import time

import pytest

from aegis_sdk.nexus.health_module import (
    AggregatedHealth,
    ComponentHealth,
    HealthAggregator,
    HealthCheckCategory,
    HealthCheckRegistration,
    HealthModule,
    ModuleHealthStatus,
)


@pytest.fixture
def module():
    """Create a fresh health module for each test."""
    return HealthModule(version="1.0.0")


def healthy_check():
    """Sample healthy check."""
    return True, {"latency_ms": 5}


def unhealthy_check():
    """Sample unhealthy check."""
    return False, {"error": "Connection failed"}


def slow_check():
    """Sample slow check that times out."""
    time.sleep(2)
    return True, {}


async def async_healthy_check():
    """Sample async healthy check."""
    await asyncio.sleep(0.001)
    return True, {"async": True}


async def async_unhealthy_check():
    """Sample async unhealthy check."""
    await asyncio.sleep(0.001)
    return False, {"async": True, "error": "Async failure"}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestModuleHealthStatus:
    """Test ModuleHealthStatus enum."""

    def test_status_values(self):
        """ModuleHealthStatus should have expected values."""
        assert ModuleHealthStatus.HEALTHY.value == "healthy"
        assert ModuleHealthStatus.DEGRADED.value == "degraded"
        assert ModuleHealthStatus.UNHEALTHY.value == "unhealthy"
        assert ModuleHealthStatus.UNKNOWN.value == "unknown"

    def test_status_str(self):
        """ModuleHealthStatus str should return value."""
        assert str(ModuleHealthStatus.HEALTHY) == "healthy"

    def test_status_is_operational(self):
        """is_operational should return True for operational statuses."""
        assert ModuleHealthStatus.HEALTHY.is_operational is True
        assert ModuleHealthStatus.DEGRADED.is_operational is True
        assert ModuleHealthStatus.UNHEALTHY.is_operational is False
        assert ModuleHealthStatus.UNKNOWN.is_operational is False

    def test_status_http_code(self):
        """http_status_code should return correct codes."""
        assert ModuleHealthStatus.HEALTHY.http_status_code == 200
        assert ModuleHealthStatus.DEGRADED.http_status_code == 200
        assert ModuleHealthStatus.UNHEALTHY.http_status_code == 503


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthCheckCategory:
    """Test HealthCheckCategory enum."""

    def test_category_values(self):
        """HealthCheckCategory should have expected values."""
        assert HealthCheckCategory.LIVENESS is not None
        assert HealthCheckCategory.READINESS is not None
        assert HealthCheckCategory.STARTUP is not None
        assert HealthCheckCategory.DEPENDENCY is not None
        assert HealthCheckCategory.CUSTOM is not None

    def test_category_str(self):
        """HealthCheckCategory str should return lowercase name."""
        assert str(HealthCheckCategory.LIVENESS) == "liveness"
        assert str(HealthCheckCategory.READINESS) == "readiness"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestComponentHealth:
    """Test ComponentHealth dataclass."""

    def test_component_health_creation(self):
        """ComponentHealth should be created with required fields."""
        health = ComponentHealth(
            name="test-component",
            status=ModuleHealthStatus.HEALTHY,
            latency_ms=10.5,
        )
        assert health.name == "test-component"
        assert health.status == ModuleHealthStatus.HEALTHY
        assert health.latency_ms == 10.5

    def test_component_is_healthy(self):
        """is_healthy should check status."""
        healthy = ComponentHealth(name="test", status=ModuleHealthStatus.HEALTHY)
        unhealthy = ComponentHealth(name="test", status=ModuleHealthStatus.UNHEALTHY)

        assert healthy.is_healthy is True
        assert unhealthy.is_healthy is False

    def test_component_is_operational(self):
        """is_operational should check operational status."""
        healthy = ComponentHealth(name="test", status=ModuleHealthStatus.HEALTHY)
        degraded = ComponentHealth(name="test", status=ModuleHealthStatus.DEGRADED)
        unhealthy = ComponentHealth(name="test", status=ModuleHealthStatus.UNHEALTHY)

        assert healthy.is_operational is True
        assert degraded.is_operational is True
        assert unhealthy.is_operational is False

    def test_component_to_dict(self):
        """to_dict should return dictionary representation."""
        health = ComponentHealth(
            name="test-component",
            status=ModuleHealthStatus.HEALTHY,
            details={"key": "value"},
            latency_ms=10.5,
            critical=True,
        )
        data = health.to_dict()
        assert data["name"] == "test-component"
        assert data["status"] == "healthy"
        assert data["details"]["key"] == "value"
        assert data["latency_ms"] == 10.5
        assert data["critical"] is True
        assert data["is_healthy"] is True


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthCheckRegistration:
    """Test HealthCheckRegistration dataclass."""

    def test_registration_creation(self):
        """HealthCheckRegistration should be created with required fields."""
        reg = HealthCheckRegistration(
            name="test-check",
            checker=healthy_check,
        )
        assert reg.name == "test-check"
        assert reg.checker is healthy_check
        assert reg.category == HealthCheckCategory.LIVENESS
        assert reg.critical is False
        assert reg.enabled is True

    def test_registration_with_options(self):
        """HealthCheckRegistration should accept all options."""
        reg = HealthCheckRegistration(
            name="test-check",
            checker=healthy_check,
            category=HealthCheckCategory.READINESS,
            timeout_s=5.0,
            critical=True,
            failure_threshold=5,
            success_threshold=2,
            tags=["database"],
        )
        assert reg.category == HealthCheckCategory.READINESS
        assert reg.timeout_s == 5.0
        assert reg.critical is True
        assert reg.failure_threshold == 5
        assert reg.success_threshold == 2
        assert "database" in reg.tags


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestAggregatedHealth:
    """Test AggregatedHealth dataclass."""

    def test_aggregated_health_creation(self):
        """AggregatedHealth should be created with required fields."""
        health = AggregatedHealth(
            status=ModuleHealthStatus.HEALTHY,
            checks={},
            healthy_count=2,
        )
        assert health.status == ModuleHealthStatus.HEALTHY
        assert health.healthy_count == 2

    def test_aggregated_http_status_code(self):
        """http_status_code should return correct code."""
        healthy = AggregatedHealth(status=ModuleHealthStatus.HEALTHY, checks={})
        unhealthy = AggregatedHealth(status=ModuleHealthStatus.UNHEALTHY, checks={})

        assert healthy.http_status_code == 200
        assert unhealthy.http_status_code == 503

    def test_aggregated_to_dict(self):
        """to_dict should return dictionary representation."""
        health = AggregatedHealth(
            status=ModuleHealthStatus.HEALTHY,
            checks={},
            healthy_count=2,
            degraded_count=1,
            version="1.0.0",
        )
        data = health.to_dict()
        assert data["status"] == "healthy"
        assert data["healthy_count"] == 2
        assert data["version"] == "1.0.0"

    def test_aggregated_to_endpoint_response(self):
        """to_endpoint_response should format for HTTP endpoint."""
        component = ComponentHealth(name="test", status=ModuleHealthStatus.HEALTHY, message="OK")
        health = AggregatedHealth(
            status=ModuleHealthStatus.HEALTHY,
            checks={"test": component},
            version="1.0.0",
        )
        response = health.to_endpoint_response()
        assert response["status"] == "healthy"
        assert len(response["checks"]) == 1
        assert response["checks"][0]["name"] == "test"
        assert response["version"] == "1.0.0"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthModule:
    """Test HealthModule class."""

    def test_module_creation(self, module):
        """HealthModule should be created with defaults."""
        assert module.version == "1.0.0"
        assert len(module) == 0

    def test_module_add_health_check(self, module):
        """add_health_check should register check."""
        module.add_health_check("test", healthy_check)
        assert "test" in module
        assert len(module) == 1

    def test_module_add_health_check_with_options(self, module):
        """add_health_check should accept all options."""
        module.add_health_check(
            name="test",
            checker=healthy_check,
            category=HealthCheckCategory.READINESS,
            timeout_s=5.0,
            critical=True,
            failure_threshold=5,
            tags=["database"],
        )
        config = module.get_check_config("test")
        assert config.category == HealthCheckCategory.READINESS
        assert config.timeout_s == 5.0
        assert config.critical is True
        assert "database" in config.tags

    def test_module_remove_health_check(self, module):
        """remove_health_check should unregister check."""
        module.add_health_check("test", healthy_check)
        result = module.remove_health_check("test")
        assert result is True
        assert "test" not in module

    def test_module_remove_health_check_returns_false_for_missing(self, module):
        """remove_health_check should return False for missing."""
        assert module.remove_health_check("nonexistent") is False

    def test_module_enable_disable_check(self, module):
        """enable_check and disable_check should toggle enabled state."""
        module.add_health_check("test", healthy_check)

        assert module.disable_check("test") is True
        config = module.get_check_config("test")
        assert config.enabled is False

        assert module.enable_check("test") is True
        config = module.get_check_config("test")
        assert config.enabled is True

    @pytest.mark.asyncio
    async def test_module_check_healthy(self, module):
        """check should return healthy status for passing check."""
        module.add_health_check("test", healthy_check)
        result = await module.check()

        assert result.status == ModuleHealthStatus.HEALTHY
        assert result.healthy_count == 1
        assert "test" in result.checks
        assert result.checks["test"].is_healthy is True

    @pytest.mark.asyncio
    async def test_module_check_unhealthy(self, module):
        """check should return unhealthy status for failing check."""
        module.add_health_check("test", unhealthy_check, failure_threshold=1)
        result = await module.check()

        assert result.checks["test"].status == ModuleHealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_module_check_async_handler(self, module):
        """check should handle async health check functions."""
        module.add_health_check("async-test", async_healthy_check)
        result = await module.check()

        assert result.status == ModuleHealthStatus.HEALTHY
        assert result.checks["async-test"].is_healthy is True
        assert result.checks["async-test"].details.get("async") is True

    @pytest.mark.asyncio
    async def test_module_check_timeout(self, module):
        """check should timeout for slow checks."""
        module.add_health_check("slow", slow_check, timeout_s=0.1, failure_threshold=1)
        result = await module.check()

        assert result.checks["slow"].status == ModuleHealthStatus.UNHEALTHY
        assert "timed out" in result.checks["slow"].error.lower()

    @pytest.mark.asyncio
    async def test_module_check_failure_threshold(self, module):
        """check should respect failure_threshold."""
        module.add_health_check("test", unhealthy_check, failure_threshold=3)

        # First failure should be degraded
        result = await module.check(force=True)
        assert result.checks["test"].status == ModuleHealthStatus.DEGRADED

        # Second failure still degraded
        result = await module.check(force=True)
        assert result.checks["test"].status == ModuleHealthStatus.DEGRADED

        # Third failure becomes unhealthy
        result = await module.check(force=True)
        assert result.checks["test"].status == ModuleHealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_module_check_filter_by_category(self, module):
        """check should filter by category."""
        module.add_health_check("liveness", healthy_check, category=HealthCheckCategory.LIVENESS)
        module.add_health_check("readiness", healthy_check, category=HealthCheckCategory.READINESS)

        result = await module.check(category=HealthCheckCategory.LIVENESS)
        assert len(result.checks) == 1
        assert "liveness" in result.checks

    @pytest.mark.asyncio
    async def test_module_check_filter_by_tags(self, module):
        """check should filter by tags."""
        module.add_health_check("db", healthy_check, tags=["database"])
        module.add_health_check("cache", healthy_check, tags=["cache"])

        result = await module.check(tags=["database"])
        assert len(result.checks) == 1
        assert "db" in result.checks

    @pytest.mark.asyncio
    async def test_module_check_critical_failure(self, module):
        """check should be unhealthy on critical failure."""
        module.add_health_check("healthy", healthy_check)
        module.add_health_check("critical", unhealthy_check, critical=True, failure_threshold=1)

        result = await module.check()
        assert result.status == ModuleHealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_module_check_caching(self, module):
        """check should use cache when enabled."""
        module.add_health_check("test", healthy_check)

        # First check
        result1 = await module.check()
        # Second check should return cached
        result2 = await module.check()

        # Timestamps should be the same (cached)
        assert result1.timestamp == result2.timestamp

        # Force should bypass cache
        result3 = await module.check(force=True)
        assert result3.timestamp != result1.timestamp

    def test_module_check_sync(self, module):
        """check_sync should run checks synchronously."""
        module.add_health_check("test", healthy_check)
        result = module.check_sync()
        assert result.status == ModuleHealthStatus.HEALTHY

    def test_module_get_status(self, module):
        """get_status should return cached results."""
        module.add_health_check("test", healthy_check)
        # No checks run yet
        status = module.get_status()
        assert len(status) == 0

    def test_module_get_component(self, module):
        """get_component should return specific component health."""
        module.add_health_check("test", healthy_check)
        assert module.get_component("test") is None  # No check run yet

    @pytest.mark.asyncio
    async def test_module_is_healthy(self, module):
        """is_healthy should check critical components."""
        module.add_health_check("critical", healthy_check, critical=True)
        await module.check()
        assert module.is_healthy() is True

    def test_module_list_checks(self, module):
        """list_checks should return check names."""
        module.add_health_check("check1", healthy_check)
        module.add_health_check("check2", healthy_check)

        names = module.list_checks()
        assert "check1" in names
        assert "check2" in names

    def test_module_get_check_config(self, module):
        """get_check_config should return configuration."""
        module.add_health_check("test", healthy_check, timeout_s=5.0)
        config = module.get_check_config("test")
        assert config.timeout_s == 5.0

    @pytest.mark.asyncio
    async def test_module_on_healthy_hook(self, module):
        """on_healthy hook should be called on recovery."""
        events = []
        module.on_healthy(lambda name, result: events.append(("healthy", name)))

        # Create a check that alternates
        call_count = {"count": 0}

        def alternating_check():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return False, {}
            return True, {}

        module.add_health_check("test", alternating_check, failure_threshold=1, success_threshold=1)
        await module.check(force=True)  # Unhealthy
        await module.check(force=True)  # Healthy - triggers hook

        assert any(e[0] == "healthy" for e in events)

    @pytest.mark.asyncio
    async def test_module_on_unhealthy_hook(self, module):
        """on_unhealthy hook should be called on failure."""
        events = []
        module.on_unhealthy(lambda name, result: events.append(("unhealthy", name)))

        call_count = {"count": 0}

        def alternating_check():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return True, {}
            return False, {}

        module.add_health_check("test", alternating_check, failure_threshold=1, success_threshold=1)
        await module.check(force=True)  # Healthy
        await module.check(force=True)  # Unhealthy - triggers hook

        assert any(e[0] == "unhealthy" for e in events)

    @pytest.mark.asyncio
    async def test_module_on_degraded_hook(self, module):
        """on_degraded hook should be called on degradation."""
        events = []
        module.on_degraded(lambda name, result: events.append(("degraded", name)))

        # Create a check that goes from healthy to degraded
        call_count = {"count": 0}

        def degrading_check():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return True, {}  # First call: healthy
            return False, {}  # Subsequent calls: failing

        # Use failure_threshold > 1 to get degraded state
        module.add_health_check("test", degrading_check, failure_threshold=3, success_threshold=1)
        await module.check(force=True)  # First check: healthy
        await module.check(force=True)  # Second check: first failure -> degraded

        assert any(e[0] == "degraded" for e in events)

    def test_module_register_standard_checks(self, module):
        """register_standard_checks should register basic checks."""
        module.register_standard_checks()
        assert "liveness" in module

    def test_module_register_standard_checks_with_components(self, module):
        """register_standard_checks should register component checks."""

        class MockWorkflowRegistry:
            def __len__(self):
                return 5

        class MockSessionManager:
            def get_stats(self):
                return {"total": 10}

        module.register_standard_checks(
            workflow_registry=MockWorkflowRegistry(),
            session_manager=MockSessionManager(),
        )
        assert "workflow_registry" in module
        assert "session_manager" in module

    def test_module_uptime(self, module):
        """uptime_s should return module uptime."""
        assert module.uptime_s >= 0

    def test_module_get_stats(self, module):
        """get_stats should return statistics."""
        module.add_health_check("check1", healthy_check, critical=True)
        module.add_health_check("check2", healthy_check)

        stats = module.get_stats()
        assert stats["registered_checks"] == 2
        assert stats["version"] == "1.0.0"
        assert stats["critical_checks"] == 1

    def test_module_clear(self, module):
        """clear should remove all checks."""
        module.add_health_check("check1", healthy_check)
        module.add_health_check("check2", healthy_check)

        module.clear()
        assert len(module) == 0

    def test_module_len_and_contains(self, module):
        """HealthModule should support len and contains."""
        assert len(module) == 0
        module.add_health_check("test", healthy_check)
        assert len(module) == 1
        assert "test" in module
        assert "missing" not in module


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthAggregator:
    """Test HealthAggregator class."""

    def test_aggregator_creation(self):
        """HealthAggregator should be created with version."""
        aggregator = HealthAggregator(version="1.0.0")
        assert len(aggregator) == 0

    def test_aggregator_add_module(self):
        """add_module should register health module."""
        aggregator = HealthAggregator()
        module = HealthModule()
        aggregator.add_module("api", module)

        assert "api" in aggregator
        assert len(aggregator) == 1

    def test_aggregator_remove_module(self):
        """remove_module should unregister health module."""
        aggregator = HealthAggregator()
        aggregator.add_module("api", HealthModule())
        result = aggregator.remove_module("api")

        assert result is True
        assert "api" not in aggregator

    def test_aggregator_remove_module_returns_false_for_missing(self):
        """remove_module should return False for missing module."""
        aggregator = HealthAggregator()
        assert aggregator.remove_module("nonexistent") is False

    @pytest.mark.asyncio
    async def test_aggregator_check_all(self):
        """check_all should check all modules."""
        aggregator = HealthAggregator()

        module1 = HealthModule()
        module1.add_health_check("check1", healthy_check)
        aggregator.add_module("api", module1)

        module2 = HealthModule()
        module2.add_health_check("check2", healthy_check)
        aggregator.add_module("worker", module2)

        results = await aggregator.check_all()
        assert "api" in results
        assert "worker" in results

    @pytest.mark.asyncio
    async def test_aggregator_get_aggregate_status(self):
        """get_aggregate_status should combine all module health."""
        aggregator = HealthAggregator(version="1.0.0")

        module1 = HealthModule()
        module1.add_health_check("check1", healthy_check)
        aggregator.add_module("api", module1)

        module2 = HealthModule()
        module2.add_health_check("check2", healthy_check)
        aggregator.add_module("worker", module2)

        status = await aggregator.get_aggregate_status()
        assert status.status == ModuleHealthStatus.HEALTHY
        assert status.healthy_count == 2
        assert "api.check1" in status.checks
        assert "worker.check2" in status.checks

    @pytest.mark.asyncio
    async def test_aggregator_get_aggregate_status_with_failures(self):
        """get_aggregate_status should report failures."""
        aggregator = HealthAggregator()

        module1 = HealthModule()
        module1.add_health_check("healthy", healthy_check)
        aggregator.add_module("api", module1)

        module2 = HealthModule()
        module2.add_health_check("unhealthy", unhealthy_check, failure_threshold=1)
        aggregator.add_module("worker", module2)

        status = await aggregator.get_aggregate_status()
        assert status.unhealthy_count == 1
        assert status.status == ModuleHealthStatus.DEGRADED

    def test_aggregator_list_modules(self):
        """list_modules should return module names."""
        aggregator = HealthAggregator()
        aggregator.add_module("api", HealthModule())
        aggregator.add_module("worker", HealthModule())

        modules = aggregator.list_modules()
        assert "api" in modules
        assert "worker" in modules

    def test_aggregator_uptime(self):
        """uptime_s should return aggregator uptime."""
        aggregator = HealthAggregator()
        assert aggregator.uptime_s >= 0

    def test_aggregator_get_stats(self):
        """get_stats should return statistics."""
        aggregator = HealthAggregator(version="1.0.0")
        aggregator.add_module("api", HealthModule())

        stats = aggregator.get_stats()
        assert stats["module_count"] == 1
        assert "api" in stats["modules"]
        assert stats["version"] == "1.0.0"

    def test_aggregator_clear(self):
        """clear should remove all modules."""
        aggregator = HealthAggregator()
        aggregator.add_module("api", HealthModule())
        aggregator.add_module("worker", HealthModule())

        count = aggregator.clear()
        assert count == 2
        assert len(aggregator) == 0

    def test_aggregator_len_and_contains(self):
        """HealthAggregator should support len and contains."""
        aggregator = HealthAggregator()
        assert len(aggregator) == 0
        aggregator.add_module("api", HealthModule())
        assert len(aggregator) == 1
        assert "api" in aggregator
        assert "missing" not in aggregator
