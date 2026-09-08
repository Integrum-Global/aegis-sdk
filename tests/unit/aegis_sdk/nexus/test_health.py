"""
Tier 1: Unit Tests for Nexus Health Monitoring.

Tests health check registration, execution, and aggregation.
"""

import pytest

from aegis_sdk.nexus.health import (
    HealthCheck,
    HealthCheckType,
    HealthMonitor,
    HealthStatus,
    HealthSummary,
)


@pytest.fixture
def monitor():
    """Create a fresh health monitor for each test."""
    return HealthMonitor(version="1.0.0")


def healthy_check():
    """Sample healthy check."""
    return True, {"latency_ms": 5}


def unhealthy_check():
    """Sample unhealthy check."""
    return False, {"error": "Connection failed"}


def slow_check():
    """Sample slow check that times out."""
    import time

    time.sleep(2)
    return True, {}


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_status_values(self):
        """HealthStatus should have expected values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_status_is_ok(self):
        """is_ok should return True for operational statuses."""
        assert HealthStatus.HEALTHY.is_ok is True
        assert HealthStatus.DEGRADED.is_ok is True
        assert HealthStatus.UNHEALTHY.is_ok is False


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthCheck:
    """Test HealthCheck dataclass."""

    def test_health_check_creation(self):
        """HealthCheck should be created with required fields."""
        check = HealthCheck(
            name="test-check",
            status=HealthStatus.HEALTHY,
            latency_ms=10.5,
        )
        assert check.name == "test-check"
        assert check.status == HealthStatus.HEALTHY
        assert check.latency_ms == 10.5

    def test_health_check_is_healthy(self):
        """is_healthy should check status."""
        healthy = HealthCheck(name="test", status=HealthStatus.HEALTHY)
        unhealthy = HealthCheck(name="test", status=HealthStatus.UNHEALTHY)

        assert healthy.is_healthy is True
        assert unhealthy.is_healthy is False

    def test_health_check_is_ok(self):
        """is_ok should check operational status."""
        healthy = HealthCheck(name="test", status=HealthStatus.HEALTHY)
        degraded = HealthCheck(name="test", status=HealthStatus.DEGRADED)
        unhealthy = HealthCheck(name="test", status=HealthStatus.UNHEALTHY)

        assert healthy.is_ok is True
        assert degraded.is_ok is True
        assert unhealthy.is_ok is False

    def test_health_check_to_dict(self):
        """to_dict should return dictionary representation."""
        check = HealthCheck(
            name="test-check",
            status=HealthStatus.HEALTHY,
            details={"key": "value"},
            latency_ms=10.5,
        )
        data = check.to_dict()
        assert data["name"] == "test-check"
        assert data["status"] == "healthy"
        assert data["details"]["key"] == "value"
        assert data["latency_ms"] == 10.5


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthMonitor:
    """Test HealthMonitor class."""

    def test_monitor_register_check(self, monitor):
        """register should add health check."""
        monitor.register("test-check", healthy_check)
        assert "test-check" in monitor
        assert len(monitor) == 1

    def test_monitor_register_with_options(self, monitor):
        """register should accept all options."""
        monitor.register(
            name="test-check",
            checker=healthy_check,
            check_type=HealthCheckType.READINESS,
            timeout_s=5.0,
            critical=True,
            tags=["database"],
        )
        config = monitor.get_check_config("test-check")
        assert config.check_type == HealthCheckType.READINESS
        assert config.timeout_s == 5.0
        assert config.critical is True
        assert "database" in config.tags

    def test_monitor_unregister_check(self, monitor):
        """unregister should remove health check."""
        monitor.register("test-check", healthy_check)
        result = monitor.unregister("test-check")
        assert result is True
        assert "test-check" not in monitor

    def test_monitor_unregister_returns_false_for_missing(self, monitor):
        """unregister should return False for missing check."""
        assert monitor.unregister("nonexistent") is False

    @pytest.mark.asyncio
    async def test_monitor_check_healthy(self, monitor):
        """check should return healthy status for passing check."""
        monitor.register("test", healthy_check)
        result = await monitor.check("test")
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_monitor_check_unhealthy(self, monitor):
        """check should return unhealthy status for failing check."""
        monitor.register("test", unhealthy_check, failure_threshold=1)
        result = await monitor.check("test")
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_monitor_check_raises_for_missing(self, monitor):
        """check should raise KeyError for missing check."""
        with pytest.raises(KeyError):
            await monitor.check("nonexistent")

    @pytest.mark.asyncio
    async def test_monitor_check_timeout(self, monitor):
        """check should timeout for slow checks."""
        monitor.register("slow", slow_check, timeout_s=0.1)
        result = await monitor.check("slow")
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_monitor_check_failure_threshold(self, monitor):
        """check should respect failure_threshold."""
        monitor.register("test", unhealthy_check, failure_threshold=3)

        # First failure should be degraded
        result = await monitor.check("test")
        assert result.status == HealthStatus.DEGRADED

        # Second failure still degraded
        result = await monitor.check("test")
        assert result.status == HealthStatus.DEGRADED

        # Third failure becomes unhealthy
        result = await monitor.check("test")
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_monitor_check_all(self, monitor):
        """check_all should check all registered checks."""
        monitor.register("check1", healthy_check)
        monitor.register("check2", healthy_check)

        summary = await monitor.check_all()
        assert summary.status == HealthStatus.HEALTHY
        assert summary.healthy_count == 2
        assert len(summary.checks) == 2

    @pytest.mark.asyncio
    async def test_monitor_check_all_with_failure(self, monitor):
        """check_all should report failures."""
        monitor.register("healthy", healthy_check)
        monitor.register("unhealthy", unhealthy_check, failure_threshold=1)

        summary = await monitor.check_all()
        assert summary.status == HealthStatus.DEGRADED
        assert summary.healthy_count == 1
        assert summary.unhealthy_count == 1

    @pytest.mark.asyncio
    async def test_monitor_check_all_critical_failure(self, monitor):
        """check_all should be unhealthy on critical failure."""
        monitor.register("healthy", healthy_check)
        monitor.register("critical", unhealthy_check, critical=True, failure_threshold=1)

        summary = await monitor.check_all()
        assert summary.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_monitor_check_all_filter_by_type(self, monitor):
        """check_all should filter by check type."""
        monitor.register("liveness", healthy_check, check_type=HealthCheckType.LIVENESS)
        monitor.register("readiness", healthy_check, check_type=HealthCheckType.READINESS)

        summary = await monitor.check_all(check_types=[HealthCheckType.LIVENESS])
        assert len(summary.checks) == 1
        assert "liveness" in summary.checks

    @pytest.mark.asyncio
    async def test_monitor_check_all_filter_by_tags(self, monitor):
        """check_all should filter by tags."""
        monitor.register("db", healthy_check, tags=["database"])
        monitor.register("cache", healthy_check, tags=["cache"])

        summary = await monitor.check_all(tags=["database"])
        assert len(summary.checks) == 1
        assert "db" in summary.checks

    def test_monitor_get_status(self, monitor):
        """get_status should return cached results."""
        monitor.register("test", healthy_check)
        # No checks run yet
        status = monitor.get_status()
        assert len(status) == 0

    def test_monitor_get_check(self, monitor):
        """get_check should return last result."""
        monitor.register("test", healthy_check)
        assert monitor.get_check("test") is None  # No check run yet

    @pytest.mark.asyncio
    async def test_monitor_on_healthy_hook(self, monitor):
        """on_healthy hook should be called on recovery."""
        events = []
        monitor.on_healthy(lambda name, result: events.append(("healthy", name)))

        # Create a check that alternates between healthy/unhealthy
        call_count = {"count": 0}

        def alternating_check():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return False, {}  # First call: unhealthy
            return True, {}  # Subsequent calls: healthy

        monitor.register("test", alternating_check, failure_threshold=1, success_threshold=1)
        await monitor.check("test")  # Becomes unhealthy
        await monitor.check("test")  # Becomes healthy - should trigger hook

        # The hook fires on status change to healthy
        assert any(e[0] == "healthy" for e in events)

    @pytest.mark.asyncio
    async def test_monitor_on_unhealthy_hook(self, monitor):
        """on_unhealthy hook should be called on failure."""
        events = []
        monitor.on_unhealthy(lambda name, result: events.append(("unhealthy", name)))

        # Create a check that alternates between healthy/unhealthy
        call_count = {"count": 0}

        def alternating_check():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return True, {}  # First call: healthy
            return False, {}  # Subsequent calls: unhealthy

        monitor.register("test", alternating_check, failure_threshold=1, success_threshold=1)
        await monitor.check("test")  # Initial healthy
        await monitor.check("test")  # Becomes unhealthy - should trigger hook

        # The hook fires on status change to unhealthy
        assert any(e[0] == "unhealthy" for e in events)

    def test_monitor_list_checks(self, monitor):
        """list_checks should return check names."""
        monitor.register("check1", healthy_check)
        monitor.register("check2", healthy_check)

        names = monitor.list_checks()
        assert "check1" in names
        assert "check2" in names

    def test_monitor_get_check_config(self, monitor):
        """get_check_config should return check configuration."""
        monitor.register("test", healthy_check, timeout_s=5.0)
        config = monitor.get_check_config("test")
        assert config.timeout_s == 5.0

    @pytest.mark.asyncio
    async def test_monitor_is_healthy(self, monitor):
        """is_healthy should check critical check status."""
        monitor.register("critical", healthy_check, critical=True)
        await monitor.check("critical")
        assert monitor.is_healthy() is True

    def test_monitor_uptime(self, monitor):
        """uptime_s should return monitor uptime."""
        assert monitor.uptime_s >= 0

    def test_monitor_get_stats(self, monitor):
        """get_stats should return monitor statistics."""
        monitor.register("check1", healthy_check, critical=True)
        monitor.register("check2", healthy_check)

        stats = monitor.get_stats()
        assert stats["registered_checks"] == 2
        assert stats["critical_checks"] == 1
        assert stats["version"] == "1.0.0"

    def test_monitor_clear(self, monitor):
        """clear should remove all checks."""
        monitor.register("check1", healthy_check)
        monitor.register("check2", healthy_check)

        monitor.clear()
        assert len(monitor) == 0

    def test_monitor_len(self, monitor):
        """__len__ should return check count."""
        assert len(monitor) == 0
        monitor.register("test", healthy_check)
        assert len(monitor) == 1

    def test_monitor_contains(self, monitor):
        """__contains__ should check if check exists."""
        monitor.register("test", healthy_check)
        assert "test" in monitor
        assert "missing" not in monitor


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestHealthSummary:
    """Test HealthSummary dataclass."""

    def test_summary_creation(self):
        """HealthSummary should be created with required fields."""
        summary = HealthSummary(
            status=HealthStatus.HEALTHY,
            checks={},
            healthy_count=2,
        )
        assert summary.status == HealthStatus.HEALTHY
        assert summary.healthy_count == 2

    def test_summary_to_dict(self):
        """to_dict should return dictionary representation."""
        summary = HealthSummary(
            status=HealthStatus.HEALTHY,
            checks={},
            healthy_count=2,
            degraded_count=1,
            total_latency_ms=150.5,
            version="1.0.0",
        )
        data = summary.to_dict()
        assert data["status"] == "healthy"
        assert data["healthy_count"] == 2
        assert data["version"] == "1.0.0"
