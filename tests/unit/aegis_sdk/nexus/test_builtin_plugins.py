"""
Tier 1: Unit Tests for Nexus Built-in Plugins.

Tests LoggingPlugin, MetricsPlugin, and CachingPlugin functionality.
"""

import asyncio
from datetime import UTC, datetime

import pytest

from aegis_sdk.nexus.builtin_plugins.builtins import (
    CacheEntry,
    CachingPlugin,
    LoggingPlugin,
    MetricsPlugin,
    RequestMetrics,
)
from aegis_sdk.nexus.plugins_module import (
    PluginPriority,
)


@pytest.fixture
def logging_plugin():
    """Create a logging plugin."""
    return LoggingPlugin()


@pytest.fixture
def metrics_plugin():
    """Create a metrics plugin."""
    return MetricsPlugin()


@pytest.fixture
def caching_plugin():
    """Create a caching plugin."""
    return CachingPlugin(ttl_s=60)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestLoggingPlugin:
    """Test LoggingPlugin class."""

    def test_plugin_info(self, logging_plugin):
        """Plugin should have correct info."""
        info = logging_plugin.info
        assert info.name == "logging-plugin"
        assert info.version == "1.0.0"
        assert info.priority == PluginPriority.FIRST
        assert "logging" in info.tags

    @pytest.mark.asyncio
    async def test_on_load(self, logging_plugin):
        """on_load should initialize plugin."""
        await logging_plugin.on_load()
        # No error should occur

    @pytest.mark.asyncio
    async def test_on_request_logs_request(self, logging_plugin, caplog):
        """on_request should log request details."""
        logging_plugin.config.set("log_level", "info")
        await logging_plugin.on_load()
        await logging_plugin.on_activate()

        result = await logging_plugin.on_request(
            request_id="req-123",
            workflow_name="test-workflow",
            inputs={"value": 42},
        )

        assert result is None  # Pass through
        # Request tracking should be recorded
        assert "req-123" in logging_plugin._request_times

    @pytest.mark.asyncio
    async def test_on_response_logs_response(self, logging_plugin, caplog):
        """on_response should log response details."""
        await logging_plugin.on_load()
        await logging_plugin.on_activate()

        # First create a request
        await logging_plugin.on_request(
            request_id="req-123",
            workflow_name="test-workflow",
            inputs={"value": 42},
        )

        result = await logging_plugin.on_response(
            request_id="req-123",
            workflow_name="test-workflow",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        assert result is None
        # Request tracking should be cleared
        assert "req-123" not in logging_plugin._request_times

    @pytest.mark.asyncio
    async def test_on_error_logs_error(self, logging_plugin, caplog):
        """on_error should log error details."""
        await logging_plugin.on_load()
        await logging_plugin.on_activate()

        # First create a request
        await logging_plugin.on_request(
            request_id="req-123",
            workflow_name="test-workflow",
            inputs={},
        )

        result = await logging_plugin.on_error(
            request_id="req-123",
            workflow_name="test-workflow",
            inputs={},
            error=ValueError("Test error"),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_config_log_inputs(self, logging_plugin):
        """log_inputs config should control input logging."""
        logging_plugin.config.set("log_inputs", False)

        result = await logging_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"sensitive": "data"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_config_max_data_length(self, logging_plugin):
        """max_data_length should truncate long data."""
        logging_plugin.config.set("max_data_length", 10)

        result = await logging_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"key": "a" * 100},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_on_deactivate_clears_state(self, logging_plugin):
        """on_deactivate should clear request times."""
        await logging_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )
        assert len(logging_plugin._request_times) > 0

        await logging_plugin.on_deactivate()
        assert len(logging_plugin._request_times) == 0


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestRequestMetrics:
    """Test RequestMetrics dataclass."""

    def test_metrics_creation(self):
        """Metrics should be created with required fields."""
        metrics = RequestMetrics(
            request_id="req-1",
            workflow_name="test",
        )
        assert metrics.request_id == "req-1"
        assert metrics.workflow_name == "test"
        assert metrics.success is True
        assert metrics.started_at is not None

    def test_metrics_to_dict(self):
        """Metrics should convert to dictionary."""
        metrics = RequestMetrics(
            request_id="req-1",
            workflow_name="test",
            latency_ms=15.5,
        )
        data = metrics.to_dict()
        assert data["request_id"] == "req-1"
        assert data["latency_ms"] == 15.5


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestMetricsPlugin:
    """Test MetricsPlugin class."""

    def test_plugin_info(self, metrics_plugin):
        """Plugin should have correct info."""
        info = metrics_plugin.info
        assert info.name == "metrics-plugin"
        assert info.version == "1.0.0"
        assert info.priority == PluginPriority.EARLY
        assert "metrics" in info.tags

    @pytest.mark.asyncio
    async def test_on_load_resets_metrics(self, metrics_plugin):
        """on_load should reset metrics."""
        await metrics_plugin.on_load()
        metrics = metrics_plugin.get_metrics()
        assert metrics["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_on_request_tracks_request(self, metrics_plugin):
        """on_request should track request start."""
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={"value": 42},
        )

        metrics = metrics_plugin.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["pending_requests"] == 1

    @pytest.mark.asyncio
    async def test_on_response_tracks_success(self, metrics_plugin):
        """on_response should track successful completion."""
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={},
        )
        await metrics_plugin.on_response(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={},
            outputs={"result": 42},
        )

        metrics = metrics_plugin.get_metrics()
        assert metrics["successful_requests"] == 1
        assert metrics["pending_requests"] == 0

    @pytest.mark.asyncio
    async def test_on_error_tracks_failure(self, metrics_plugin):
        """on_error should track failed request."""
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={},
        )
        await metrics_plugin.on_error(
            request_id="req-1",
            workflow_name="test-workflow",
            inputs={},
            error=ValueError("Test error"),
        )

        metrics = metrics_plugin.get_metrics()
        assert metrics["failed_requests"] == 1
        assert metrics["error_rate"] > 0

    @pytest.mark.asyncio
    async def test_latency_tracking(self, metrics_plugin):
        """Plugin should track latency metrics."""
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )
        await asyncio.sleep(0.01)  # Small delay
        await metrics_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={},
            outputs={},
        )

        metrics = metrics_plugin.get_metrics()
        assert metrics["avg_latency_ms"] >= 10  # At least 10ms

    @pytest.mark.asyncio
    async def test_workflow_metrics(self, metrics_plugin):
        """Plugin should track per-workflow metrics."""
        # Execute multiple workflows
        for wf_name in ["workflow-a", "workflow-b", "workflow-a"]:
            await metrics_plugin.on_request(
                request_id=f"req-{wf_name}",
                workflow_name=wf_name,
                inputs={},
            )
            await metrics_plugin.on_response(
                request_id=f"req-{wf_name}",
                workflow_name=wf_name,
                inputs={},
                outputs={},
            )

        workflow_metrics = metrics_plugin.get_workflow_metrics()
        assert "workflow-a" in workflow_metrics
        assert workflow_metrics["workflow-a"]["count"] == 2
        assert workflow_metrics["workflow-b"]["count"] == 1

    @pytest.mark.asyncio
    async def test_get_workflow_metrics_single(self, metrics_plugin):
        """get_workflow_metrics should return single workflow stats."""
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )
        await metrics_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={},
            outputs={},
        )

        workflow_metrics = metrics_plugin.get_workflow_metrics("test")
        assert "test" in workflow_metrics

    @pytest.mark.asyncio
    async def test_latency_histogram(self, metrics_plugin):
        """Plugin should track latency histogram."""
        for i in range(5):
            await metrics_plugin.on_request(
                request_id=f"req-{i}",
                workflow_name="test",
                inputs={},
            )
            await metrics_plugin.on_response(
                request_id=f"req-{i}",
                workflow_name="test",
                inputs={},
                outputs={},
            )

        histogram = metrics_plugin.get_latency_histogram()
        assert len(histogram) > 0

    @pytest.mark.asyncio
    async def test_get_recent_requests(self, metrics_plugin):
        """get_recent_requests should return completed requests."""
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )
        await metrics_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={},
            outputs={},
        )

        recent = metrics_plugin.get_recent_requests()
        assert len(recent) == 1
        assert recent[0]["request_id"] == "req-1"

    def test_reset_metrics(self, metrics_plugin):
        """reset_metrics should clear all metrics."""
        # Add some metrics first (simulate)
        metrics_plugin._total_requests = 100
        metrics_plugin._successful_requests = 90

        metrics_plugin.reset_metrics()

        metrics = metrics_plugin.get_metrics()
        assert metrics["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_max_history_config(self):
        """max_history should limit stored requests."""
        plugin = MetricsPlugin()
        plugin.config.set("max_history", 5)

        for i in range(10):
            await plugin.on_request(
                request_id=f"req-{i}",
                workflow_name="test",
                inputs={},
            )
            await plugin.on_response(
                request_id=f"req-{i}",
                workflow_name="test",
                inputs={},
                outputs={},
            )

        recent = plugin.get_recent_requests(limit=100)
        assert len(recent) == 5


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_entry_creation(self):
        """Entry should be created with required fields."""
        entry = CacheEntry(
            key="cache-key-1",
            workflow_name="test",
            inputs={"value": 42},
            outputs={"result": 84},
        )
        assert entry.key == "cache-key-1"
        assert entry.hit_count == 0
        assert entry.is_expired is False

    def test_entry_expiration(self):
        """Entry should detect expiration."""
        from datetime import timedelta

        entry = CacheEntry(
            key="cache-key-1",
            workflow_name="test",
            inputs={},
            outputs={},
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        assert entry.is_expired is True

    def test_entry_to_dict(self):
        """Entry should convert to dictionary."""
        entry = CacheEntry(
            key="cache-key-1",
            workflow_name="test",
            inputs={},
            outputs={},
        )
        data = entry.to_dict()
        assert data["key"] == "cache-key-1"
        assert data["workflow_name"] == "test"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestCachingPlugin:
    """Test CachingPlugin class."""

    def test_plugin_info(self, caching_plugin):
        """Plugin should have correct info."""
        info = caching_plugin.info
        assert info.name == "caching-plugin"
        assert info.version == "1.0.0"
        assert info.priority == PluginPriority.EARLY
        assert "caching" in info.tags

    @pytest.mark.asyncio
    async def test_on_load(self, caching_plugin):
        """on_load should initialize plugin."""
        await caching_plugin.on_load()
        # No error should occur

    @pytest.mark.asyncio
    async def test_cache_miss_on_first_request(self, caching_plugin):
        """First request should be a cache miss."""
        result = await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
        )
        assert result is None  # Cache miss returns None

    @pytest.mark.asyncio
    async def test_cache_stores_response(self, caching_plugin):
        """on_response should cache the result."""
        # First request - miss
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
        )

        # Store response
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        stats = caching_plugin.get_cache_stats()
        assert stats["entries"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_on_second_request(self, caching_plugin):
        """Second identical request should be a cache hit."""
        inputs = {"value": 42}

        # First request - miss and store
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
            outputs={"result": 84},
        )

        # Second request - hit
        result = await caching_plugin.on_request(
            request_id="req-2",
            workflow_name="test",
            inputs=inputs,
        )

        assert result is not None
        assert result["__cached__"] is True
        assert result["__cached_outputs__"]["result"] == 84

    @pytest.mark.asyncio
    async def test_cache_miss_on_different_inputs(self, caching_plugin):
        """Different inputs should be cache miss."""
        # First request
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        # Different inputs - miss
        result = await caching_plugin.on_request(
            request_id="req-2",
            workflow_name="test",
            inputs={"value": 100},  # Different input
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_excluded_workflows(self, caching_plugin):
        """Excluded workflows should not be cached."""
        caching_plugin.config.set("excluded_workflows", ["no-cache-workflow"])

        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="no-cache-workflow",
            inputs={"value": 42},
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="no-cache-workflow",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        stats = caching_plugin.get_cache_stats()
        assert stats["entries"] == 0

    @pytest.mark.asyncio
    async def test_workflow_specific_ttl(self, caching_plugin):
        """workflow_ttls should set per-workflow TTL."""
        caching_plugin.config.set("workflow_ttls", {"long-cache": 3600})

        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="long-cache",
            inputs={},
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="long-cache",
            inputs={},
            outputs={},
        )

        stats = caching_plugin.get_cache_stats()
        assert stats["entries"] == 1

    def test_get_cache_stats(self, caching_plugin):
        """get_cache_stats should return cache statistics."""
        stats = caching_plugin.get_cache_stats()
        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    @pytest.mark.asyncio
    async def test_get_cached_workflows(self, caching_plugin):
        """get_cached_workflows should return per-workflow counts."""
        # Each call needs unique inputs to generate different cache keys
        calls = [
            ("wf-a", {"unique_id": 1}),
            ("wf-b", {"unique_id": 2}),
            ("wf-a", {"unique_id": 3}),  # Second wf-a with different inputs
        ]
        for i, (wf_name, inputs) in enumerate(calls):
            await caching_plugin.on_request(
                request_id=f"req-{i}",
                workflow_name=wf_name,
                inputs=inputs,
            )
            await caching_plugin.on_response(
                request_id=f"req-{i}",
                workflow_name=wf_name,
                inputs=inputs,
                outputs={},
            )

        workflows = caching_plugin.get_cached_workflows()
        assert workflows.get("wf-a", 0) == 2
        assert workflows.get("wf-b", 0) == 1

    @pytest.mark.asyncio
    async def test_invalidate_by_workflow(self, caching_plugin):
        """invalidate should remove entries by workflow."""
        for wf_name in ["wf-a", "wf-b"]:
            await caching_plugin.on_request(
                request_id=f"req-{wf_name}",
                workflow_name=wf_name,
                inputs={},
            )
            await caching_plugin.on_response(
                request_id=f"req-{wf_name}",
                workflow_name=wf_name,
                inputs={},
                outputs={},
            )

        count = caching_plugin.invalidate(workflow_name="wf-a")
        assert count == 1

        stats = caching_plugin.get_cache_stats()
        assert stats["entries"] == 1

    def test_clear(self, caching_plugin):
        """clear should remove all cache entries."""
        # Add some entries manually
        caching_plugin._cache["key1"] = CacheEntry(
            key="key1",
            workflow_name="test",
            inputs={},
            outputs={},
        )
        caching_plugin._cache["key2"] = CacheEntry(
            key="key2",
            workflow_name="test",
            inputs={},
            outputs={},
        )

        count = caching_plugin.clear()
        assert count == 2
        assert len(caching_plugin._cache) == 0

    @pytest.mark.asyncio
    async def test_eviction_on_capacity(self):
        """Cache should evict entries when at capacity."""
        plugin = CachingPlugin(max_entries=3)

        for i in range(5):
            await plugin.on_request(
                request_id=f"req-{i}",
                workflow_name="test",
                inputs={"i": i},
            )
            await plugin.on_response(
                request_id=f"req-{i}",
                workflow_name="test",
                inputs={"i": i},
                outputs={"result": i},
            )

        stats = plugin.get_cache_stats()
        assert stats["entries"] <= 3

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, caching_plugin):
        """Hit rate should be calculated correctly."""
        inputs = {"value": 42}

        # First request - miss
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
            outputs={},
        )

        # Second request - hit
        await caching_plugin.on_request(
            request_id="req-2",
            workflow_name="test",
            inputs=inputs,
        )

        stats = caching_plugin.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_cache_key_fields_config(self, caching_plugin):
        """cache_key_fields should limit fields used in key."""
        caching_plugin.config.set("cache_key_fields", ["important_field"])

        # Two requests with same important_field but different other fields
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"important_field": "value", "ignored": "a"},
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={"important_field": "value", "ignored": "a"},
            outputs={"cached": True},
        )

        result = await caching_plugin.on_request(
            request_id="req-2",
            workflow_name="test",
            inputs={"important_field": "value", "ignored": "b"},  # Different ignored
        )

        # Should be a hit since important_field is the same
        assert result is not None
        assert result["__cached__"] is True

    @pytest.mark.asyncio
    async def test_on_error_clears_tracking(self, caching_plugin):
        """on_error should clean up tracking state."""
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )

        await caching_plugin.on_error(
            request_id="req-1",
            workflow_name="test",
            inputs={},
            error=ValueError("Test error"),
        )

        # Should not have cached the failed request
        stats = caching_plugin.get_cache_stats()
        assert stats["entries"] == 0

    @pytest.mark.asyncio
    async def test_on_unload_clears_cache(self, caching_plugin):
        """on_unload should clear all cache."""
        await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={},
        )
        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={},
            outputs={},
        )

        await caching_plugin.on_unload()

        stats = caching_plugin.get_cache_stats()
        assert stats["entries"] == 0


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestPluginIntegration:
    """Test plugins working together."""

    @pytest.mark.asyncio
    async def test_logging_and_metrics_together(self, logging_plugin, metrics_plugin):
        """Logging and metrics plugins should work together."""
        await logging_plugin.on_load()
        await metrics_plugin.on_load()
        await logging_plugin.on_activate()
        await metrics_plugin.on_activate()

        # Simulate request
        await logging_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
        )
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
        )

        # Simulate response
        await logging_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
            outputs={"result": 84},
        )
        await metrics_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs={"value": 42},
            outputs={"result": 84},
        )

        metrics = metrics_plugin.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["successful_requests"] == 1

    @pytest.mark.asyncio
    async def test_caching_and_metrics_together(self, caching_plugin, metrics_plugin):
        """Caching and metrics plugins should work together."""
        await caching_plugin.on_load()
        await metrics_plugin.on_load()
        await caching_plugin.on_activate()
        await metrics_plugin.on_activate()

        inputs = {"value": 42}

        # First request - cache miss
        await metrics_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
        )
        cache_result = await caching_plugin.on_request(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
        )
        assert cache_result is None  # Miss

        await caching_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
            outputs={"result": 84},
        )
        await metrics_plugin.on_response(
            request_id="req-1",
            workflow_name="test",
            inputs=inputs,
            outputs={"result": 84},
        )

        # Second request - cache hit
        await metrics_plugin.on_request(
            request_id="req-2",
            workflow_name="test",
            inputs=inputs,
        )
        cache_result = await caching_plugin.on_request(
            request_id="req-2",
            workflow_name="test",
            inputs=inputs,
        )
        assert cache_result is not None  # Hit
        assert cache_result["__cached__"] is True

        cache_stats = caching_plugin.get_cache_stats()
        assert cache_stats["hits"] == 1
        assert cache_stats["misses"] == 1
