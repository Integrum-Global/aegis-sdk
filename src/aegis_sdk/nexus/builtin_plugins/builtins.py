"""Built-in plugins for Nexus v1.1.

Provides essential plugins for logging, metrics collection, and caching.

Example:
    >>> from aegis_sdk.nexus import PluginsModule
    >>> from aegis_sdk.nexus.plugins import LoggingPlugin, MetricsPlugin, CachingPlugin
    >>>
    >>> module = PluginsModule()
    >>>
    >>> # Add logging
    >>> module.load(LoggingPlugin())
    >>> module.activate("logging-plugin")
    >>>
    >>> # Add metrics
    >>> metrics = MetricsPlugin()
    >>> module.load(metrics)
    >>> module.activate("metrics-plugin")
    >>>
    >>> # Add caching
    >>> cache = CachingPlugin(ttl_s=300)
    >>> module.load(cache)
    >>> module.activate("caching-plugin")
    >>>
    >>> # Execute workflows - plugins intercept automatically
    >>> results = await module.on_request("req-1", "my-workflow", {"value": 42})
    >>>
    >>> # Get metrics
    >>> print(metrics.get_metrics())
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.nexus.plugins_module import (
    PluginBase,
    PluginInfo,
    PluginPriority,
)

logger = logging.getLogger(__name__)


class LoggingPlugin(PluginBase):
    """Plugin that logs all requests and responses.

    Provides detailed logging of workflow execution for
    debugging, auditing, and observability.

    Configuration options (via config.settings):
        - log_level: Logging level ("debug", "info", "warning", "error")
        - log_inputs: Whether to log input data (default: True)
        - log_outputs: Whether to log output data (default: True)
        - log_errors: Whether to log errors (default: True)
        - max_data_length: Maximum length of logged data (default: 1000)
        - include_timestamp: Include timestamp in logs (default: True)
        - include_latency: Include latency in response logs (default: True)

    Example:
        >>> plugin = LoggingPlugin()
        >>> plugin.config.set("log_level", "debug")
        >>> plugin.config.set("max_data_length", 500)
    """

    @property
    def info(self) -> PluginInfo:
        """Get plugin info."""
        return PluginInfo(
            name="logging-plugin",
            version="1.0.0",
            description="Logs all workflow requests and responses",
            author="Nexus Team",
            priority=PluginPriority.FIRST,  # Log before other plugins
            tags=["logging", "observability", "debugging"],
        )

    def __init__(self, log_level: str = "info"):
        """Initialize logging plugin.

        Args:
            log_level: Default log level.
        """
        super().__init__()
        self._log_level = log_level
        self._request_times: dict[str, float] = {}
        self._lock = threading.Lock()

    async def on_load(self) -> None:
        """Initialize plugin."""
        log_level = self.config.get("log_level", self._log_level)
        logger.info("LoggingPlugin loaded with level: %s", log_level)

    async def on_activate(self) -> None:
        """Activate plugin."""
        logger.info("LoggingPlugin activated")

    async def on_deactivate(self) -> None:
        """Deactivate plugin."""
        with self._lock:
            self._request_times.clear()
        logger.info("LoggingPlugin deactivated")

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any] | None:
        """Log incoming request.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Workflow inputs.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        with self._lock:
            self._request_times[request_id] = time.time()

        log_inputs = self.config.get("log_inputs", True)
        max_length = self.config.get("max_data_length", 1000)
        include_timestamp = self.config.get("include_timestamp", True)

        # Build log message
        parts = [f"[REQUEST] {request_id} -> {workflow_name}"]

        if include_timestamp:
            parts.append(f"timestamp={datetime.now(UTC).isoformat()}")

        if log_inputs and inputs:
            inputs_str = str(inputs)
            if len(inputs_str) > max_length:
                inputs_str = inputs_str[:max_length] + "..."
            parts.append(f"inputs={inputs_str}")

        # Add kwargs (session_id, channel, etc.)
        for key, value in kwargs.items():
            if value is not None:
                parts.append(f"{key}={value}")

        log_message = " | ".join(parts)
        self._log(log_message)

        return None

    async def on_response(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        outputs: Any,
        **kwargs,
    ) -> Any | None:
        """Log response.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original inputs.
            outputs: Workflow outputs.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        latency_ms = None
        with self._lock:
            if request_id in self._request_times:
                latency_ms = (time.time() - self._request_times[request_id]) * 1000
                del self._request_times[request_id]

        log_outputs = self.config.get("log_outputs", True)
        max_length = self.config.get("max_data_length", 1000)
        include_latency = self.config.get("include_latency", True)
        include_timestamp = self.config.get("include_timestamp", True)

        # Build log message
        parts = [f"[RESPONSE] {request_id} <- {workflow_name}"]

        if include_timestamp:
            parts.append(f"timestamp={datetime.now(UTC).isoformat()}")

        if include_latency and latency_ms is not None:
            parts.append(f"latency_ms={latency_ms:.2f}")

        if log_outputs and outputs is not None:
            outputs_str = str(outputs)
            if len(outputs_str) > max_length:
                outputs_str = outputs_str[:max_length] + "..."
            parts.append(f"outputs={outputs_str}")

        log_message = " | ".join(parts)
        self._log(log_message)

        return None

    async def on_error(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> Exception | None:
        """Log error.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original inputs.
            error: The exception.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        log_errors = self.config.get("log_errors", True)
        if not log_errors:
            return None

        latency_ms = None
        with self._lock:
            if request_id in self._request_times:
                latency_ms = (time.time() - self._request_times[request_id]) * 1000
                del self._request_times[request_id]

        include_timestamp = self.config.get("include_timestamp", True)

        # Build log message
        parts = [f"[ERROR] {request_id} <- {workflow_name}"]

        if include_timestamp:
            parts.append(f"timestamp={datetime.now(UTC).isoformat()}")

        if latency_ms is not None:
            parts.append(f"latency_ms={latency_ms:.2f}")

        parts.append(f"error={type(error).__name__}: {str(error)}")

        log_message = " | ".join(parts)
        self._log(log_message, level="error")

        return None

    def _log(self, message: str, level: str | None = None) -> None:
        """Log a message at the configured level.

        Args:
            message: Log message.
            level: Override level.
        """
        log_level = level or self.config.get("log_level", self._log_level)

        if log_level == "debug":
            logger.debug(message)
        elif log_level == "warning":
            logger.warning(message)
        elif log_level == "error":
            logger.error(message)
        else:
            logger.info(message)


@dataclass
class RequestMetrics:
    """Metrics for a single request.

    Attributes:
        request_id: Unique request identifier.
        workflow_name: Name of the workflow.
        started_at: When request started.
        completed_at: When request completed.
        latency_ms: Request latency in milliseconds.
        success: Whether request succeeded.
        error: Error message if failed.
    """

    request_id: str
    workflow_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    latency_ms: float | None = None
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "workflow_name": self.workflow_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error,
        }


class MetricsPlugin(PluginBase):
    """Plugin that collects request metrics.

    Tracks request counts, latency distributions, error rates,
    and workflow-level statistics for monitoring and analytics.

    Configuration options (via config.settings):
        - max_history: Maximum number of requests to track (default: 10000)
        - track_latency_histogram: Track latency distribution (default: True)
        - histogram_buckets: Latency histogram buckets in ms (default: [10, 50, 100, 250, 500, 1000, 5000])

    Example:
        >>> plugin = MetricsPlugin()
        >>> module.load(plugin)
        >>> module.activate("metrics-plugin")
        >>>
        >>> # After some requests...
        >>> metrics = plugin.get_metrics()
        >>> print(f"Total requests: {metrics['total_requests']}")
        >>> print(f"Error rate: {metrics['error_rate']:.2%}")
    """

    @property
    def info(self) -> PluginInfo:
        """Get plugin info."""
        return PluginInfo(
            name="metrics-plugin",
            version="1.0.0",
            description="Collects request metrics and statistics",
            author="Nexus Team",
            priority=PluginPriority.EARLY,  # Collect before most plugins
            tags=["metrics", "monitoring", "analytics"],
        )

    def __init__(self):
        """Initialize metrics plugin."""
        super().__init__()
        self._lock = threading.Lock()
        self._reset_metrics()

    def _reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        self._pending_requests: dict[str, RequestMetrics] = {}
        self._completed_requests: list[RequestMetrics] = []
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_latency_ms = 0.0
        self._workflow_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "success": 0,
                "failure": 0,
                "total_latency_ms": 0.0,
                "min_latency_ms": float("inf"),
                "max_latency_ms": 0.0,
            }
        )
        self._latency_histogram: dict[int, int] = defaultdict(int)
        self._start_time = time.time()

    async def on_load(self) -> None:
        """Initialize plugin."""
        self._reset_metrics()
        logger.info("MetricsPlugin loaded")

    async def on_activate(self) -> None:
        """Activate plugin."""
        logger.info("MetricsPlugin activated")

    async def on_deactivate(self) -> None:
        """Deactivate plugin."""
        logger.info("MetricsPlugin deactivated")

    async def on_unload(self) -> None:
        """Unload plugin."""
        with self._lock:
            self._reset_metrics()
        logger.info("MetricsPlugin unloaded")

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any] | None:
        """Track request start.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Workflow inputs.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        with self._lock:
            self._total_requests += 1
            metrics = RequestMetrics(
                request_id=request_id,
                workflow_name=workflow_name,
            )
            self._pending_requests[request_id] = metrics

            # Update workflow stats
            self._workflow_stats[workflow_name]["count"] += 1

        return None

    async def on_response(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        outputs: Any,
        **kwargs,
    ) -> Any | None:
        """Track successful response.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original inputs.
            outputs: Workflow outputs.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        with self._lock:
            self._successful_requests += 1

            metrics = self._pending_requests.pop(request_id, None)
            if metrics:
                metrics.completed_at = datetime.now(UTC)
                metrics.latency_ms = (
                    metrics.completed_at - metrics.started_at
                ).total_seconds() * 1000
                metrics.success = True

                self._record_completed(metrics)

        return None

    async def on_error(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> Exception | None:
        """Track error.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original inputs.
            error: The exception.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        with self._lock:
            self._failed_requests += 1

            metrics = self._pending_requests.pop(request_id, None)
            if metrics:
                metrics.completed_at = datetime.now(UTC)
                metrics.latency_ms = (
                    metrics.completed_at - metrics.started_at
                ).total_seconds() * 1000
                metrics.success = False
                metrics.error = str(error)

                self._record_completed(metrics)

        return None

    def _record_completed(self, metrics: RequestMetrics) -> None:
        """Record completed request metrics.

        Args:
            metrics: Request metrics to record.
        """
        max_history = self.config.get("max_history", 10000)

        # Add to completed list
        self._completed_requests.append(metrics)

        # Trim if necessary
        if len(self._completed_requests) > max_history:
            self._completed_requests = self._completed_requests[-max_history:]

        # Update totals
        if metrics.latency_ms is not None:
            self._total_latency_ms += metrics.latency_ms

            # Update workflow stats
            stats = self._workflow_stats[metrics.workflow_name]
            if metrics.success:
                stats["success"] += 1
            else:
                stats["failure"] += 1
            stats["total_latency_ms"] += metrics.latency_ms
            stats["min_latency_ms"] = min(stats["min_latency_ms"], metrics.latency_ms)
            stats["max_latency_ms"] = max(stats["max_latency_ms"], metrics.latency_ms)

            # Update histogram
            if self.config.get("track_latency_histogram", True):
                buckets = self.config.get("histogram_buckets", [10, 50, 100, 250, 500, 1000, 5000])
                bucket = self._get_histogram_bucket(metrics.latency_ms, buckets)
                self._latency_histogram[bucket] += 1

    def _get_histogram_bucket(self, latency_ms: float, buckets: list[int]) -> int:
        """Get the histogram bucket for a latency value.

        Args:
            latency_ms: Latency in milliseconds.
            buckets: Bucket boundaries.

        Returns:
            Bucket value.
        """
        for bucket in sorted(buckets):
            if latency_ms <= bucket:
                return bucket
        return buckets[-1] + 1  # Overflow bucket

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics summary.

        Returns:
            Dictionary with metrics.
        """
        with self._lock:
            completed = self._successful_requests + self._failed_requests
            avg_latency = self._total_latency_ms / completed if completed > 0 else 0.0
            error_rate = (
                self._failed_requests / self._total_requests if self._total_requests > 0 else 0.0
            )

            # Calculate percentiles from recent history
            recent_latencies = [
                m.latency_ms for m in self._completed_requests[-1000:] if m.latency_ms is not None
            ]
            p50, p90, p99 = self._calculate_percentiles(recent_latencies)

            return {
                "total_requests": self._total_requests,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "pending_requests": len(self._pending_requests),
                "error_rate": error_rate,
                "avg_latency_ms": avg_latency,
                "p50_latency_ms": p50,
                "p90_latency_ms": p90,
                "p99_latency_ms": p99,
                "uptime_s": time.time() - self._start_time,
                "requests_per_second": (
                    self._total_requests / (time.time() - self._start_time)
                    if time.time() > self._start_time
                    else 0.0
                ),
            }

    def get_workflow_metrics(self, workflow_name: str | None = None) -> dict[str, Any]:
        """Get workflow-level metrics.

        Args:
            workflow_name: Specific workflow (None for all).

        Returns:
            Dictionary with workflow metrics.
        """
        with self._lock:
            if workflow_name:
                stats = dict(self._workflow_stats.get(workflow_name, {}))
                if stats.get("count", 0) > 0:
                    stats["avg_latency_ms"] = stats["total_latency_ms"] / stats["count"]
                    stats["error_rate"] = stats["failure"] / stats["count"]
                return {workflow_name: stats}
            else:
                result = {}
                for name, stats in self._workflow_stats.items():
                    workflow_stats = dict(stats)
                    if workflow_stats.get("count", 0) > 0:
                        workflow_stats["avg_latency_ms"] = (
                            workflow_stats["total_latency_ms"] / workflow_stats["count"]
                        )
                        workflow_stats["error_rate"] = (
                            workflow_stats["failure"] / workflow_stats["count"]
                        )
                    result[name] = workflow_stats
                return result

    def get_latency_histogram(self) -> dict[str, int]:
        """Get latency histogram.

        Returns:
            Dictionary mapping bucket names to counts.
        """
        with self._lock:
            buckets = self.config.get("histogram_buckets", [10, 50, 100, 250, 500, 1000, 5000])
            result = {}
            for bucket in sorted(buckets):
                result[f"<={bucket}ms"] = self._latency_histogram.get(bucket, 0)
            overflow = buckets[-1] + 1
            result[f">{buckets[-1]}ms"] = self._latency_histogram.get(overflow, 0)
            return result

    def get_recent_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent completed requests.

        Args:
            limit: Maximum number of requests.

        Returns:
            List of request metrics.
        """
        with self._lock:
            return [m.to_dict() for m in self._completed_requests[-limit:]]

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._reset_metrics()
        logger.info("MetricsPlugin metrics reset")

    def _calculate_percentiles(
        self, values: list[float]
    ) -> tuple[float | None, float | None, float | None]:
        """Calculate p50, p90, p99 percentiles.

        Args:
            values: List of values.

        Returns:
            Tuple of (p50, p90, p99).
        """
        if not values:
            return None, None, None

        sorted_values = sorted(values)
        n = len(sorted_values)

        def percentile(p: int) -> float:
            idx = (p / 100) * (n - 1)
            lower = int(idx)
            upper = min(lower + 1, n - 1)
            weight = idx - lower
            return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

        return percentile(50), percentile(90), percentile(99)


@dataclass
class CacheEntry:
    """Cache entry for workflow results.

    Attributes:
        key: Cache key.
        workflow_name: Name of the workflow.
        inputs: Original inputs.
        outputs: Cached outputs.
        created_at: When entry was created.
        expires_at: When entry expires.
        hit_count: Number of cache hits.
    """

    key: str
    workflow_name: str
    inputs: dict[str, Any]
    outputs: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "workflow_name": self.workflow_name,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "hit_count": self.hit_count,
            "is_expired": self.is_expired,
        }


class CachingPlugin(PluginBase):
    """Plugin that caches workflow execution results.

    Provides in-memory caching of workflow outputs to improve
    performance for repeated identical requests.

    Configuration options (via config.settings):
        - ttl_s: Default cache TTL in seconds (default: 300)
        - max_entries: Maximum cache entries (default: 10000)
        - workflow_ttls: Workflow-specific TTLs (dict)
        - excluded_workflows: Workflows to never cache (list)
        - cache_key_fields: Fields to include in cache key (None = all)

    Example:
        >>> plugin = CachingPlugin(ttl_s=600)  # 10 minute TTL
        >>> plugin.config.set("excluded_workflows", ["random-workflow"])
        >>> plugin.config.set("workflow_ttls", {"heavy-workflow": 3600})
    """

    @property
    def info(self) -> PluginInfo:
        """Get plugin info."""
        return PluginInfo(
            name="caching-plugin",
            version="1.0.0",
            description="Caches workflow execution results",
            author="Nexus Team",
            priority=PluginPriority.EARLY,  # Check cache before execution
            tags=["caching", "performance", "optimization"],
        )

    def __init__(self, ttl_s: int = 300, max_entries: int = 10000):
        """Initialize caching plugin.

        Args:
            ttl_s: Default cache TTL in seconds.
            max_entries: Maximum cache entries.
        """
        super().__init__()
        self._default_ttl_s = ttl_s
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._cache: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        # Track requests that had cache hits
        self._cached_requests: set[str] = set()

    async def on_load(self) -> None:
        """Initialize plugin."""
        logger.info(
            "CachingPlugin loaded with TTL=%ss, max=%s", self._default_ttl_s, self._max_entries
        )

    async def on_activate(self) -> None:
        """Activate plugin."""
        logger.info("CachingPlugin activated")

    async def on_deactivate(self) -> None:
        """Deactivate plugin."""
        logger.info("CachingPlugin deactivated")

    async def on_unload(self) -> None:
        """Unload plugin."""
        self.clear()
        logger.info("CachingPlugin unloaded")

    async def on_request(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any] | None:
        """Check cache for existing result.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Workflow inputs.
            **kwargs: Additional context.

        Returns:
            Cached result if found, None otherwise.
        """
        # Check exclusions
        excluded = self.config.get("excluded_workflows", [])
        if workflow_name in excluded:
            return None

        # Generate cache key
        cache_key = self._generate_cache_key(workflow_name, inputs)

        with self._lock:
            entry = self._cache.get(cache_key)

            if entry and not entry.is_expired:
                self._hits += 1
                entry.hit_count += 1
                # Mark this request as served from cache
                self._cached_requests.add(request_id)
                logger.debug("Cache hit for %s: %s", workflow_name, cache_key)
                # Return cached outputs - this signals to skip workflow execution
                # Note: The calling code needs to handle this appropriately
                return {"__cached__": True, "__cached_outputs__": entry.outputs}
            elif entry:
                # Expired entry - remove it
                del self._cache[cache_key]

            self._misses += 1
            logger.debug("Cache miss for %s: %s", workflow_name, cache_key)

        return None

    async def on_response(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        outputs: Any,
        **kwargs,
    ) -> Any | None:
        """Cache successful response.

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original inputs.
            outputs: Workflow outputs.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        # Don't cache if this was a cache hit (already cached)
        if request_id in self._cached_requests:
            self._cached_requests.discard(request_id)
            return None

        # Check exclusions
        excluded = self.config.get("excluded_workflows", [])
        if workflow_name in excluded:
            return None

        # Get TTL
        workflow_ttls = self.config.get("workflow_ttls", {})
        ttl_s = workflow_ttls.get(workflow_name, self._default_ttl_s)
        ttl_s = self.config.get("ttl_s", ttl_s)

        # Generate cache key
        cache_key = self._generate_cache_key(workflow_name, inputs)

        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_entries:
                self._evict_oldest()

            # Create entry
            from datetime import timedelta

            entry = CacheEntry(
                key=cache_key,
                workflow_name=workflow_name,
                inputs=inputs,
                outputs=outputs,
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_s),
            )
            self._cache[cache_key] = entry
            logger.debug("Cached result for %s: %s", workflow_name, cache_key)

        return None

    async def on_error(
        self,
        request_id: str,
        workflow_name: str,
        inputs: dict[str, Any],
        error: Exception,
        **kwargs,
    ) -> Exception | None:
        """Handle error (don't cache errors by default).

        Args:
            request_id: Unique request identifier.
            workflow_name: Name of the workflow.
            inputs: Original inputs.
            error: The exception.
            **kwargs: Additional context.

        Returns:
            None (pass through).
        """
        # Clean up any pending cache tracking
        self._cached_requests.discard(request_id)
        return None

    def _generate_cache_key(
        self,
        workflow_name: str,
        inputs: dict[str, Any],
    ) -> str:
        """Generate cache key from workflow name and inputs.

        Args:
            workflow_name: Name of the workflow.
            inputs: Workflow inputs.

        Returns:
            Cache key string.
        """
        cache_key_fields = self.config.get("cache_key_fields")

        if cache_key_fields:
            # Only include specified fields
            key_inputs = {k: inputs.get(k) for k in cache_key_fields if k in inputs}
        else:
            key_inputs = inputs

        # Create deterministic string representation
        try:
            key_str = json.dumps(
                {"workflow": workflow_name, "inputs": key_inputs},
                sort_keys=True,
                default=str,
            )
        except (TypeError, ValueError):
            # Fall back to string representation
            key_str = f"{workflow_name}:{str(key_inputs)}"

        # Hash for consistent key length
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def _evict_oldest(self) -> None:
        """Evict oldest cache entries."""
        if not self._cache:
            return

        # Remove expired first
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]
            self._evictions += 1

        # If still at capacity, remove oldest
        if len(self._cache) >= self._max_entries:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at,
            )
            del self._cache[oldest_key]
            self._evictions += 1

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "default_ttl_s": self._default_ttl_s,
            }

    def get_cached_workflows(self) -> dict[str, int]:
        """Get count of cached entries per workflow.

        Returns:
            Dictionary mapping workflow names to entry counts.
        """
        with self._lock:
            counts: dict[str, int] = defaultdict(int)
            for entry in self._cache.values():
                counts[entry.workflow_name] += 1
            return dict(counts)

    def invalidate(
        self,
        workflow_name: str | None = None,
        cache_key: str | None = None,
    ) -> int:
        """Invalidate cache entries.

        Args:
            workflow_name: Invalidate all entries for workflow.
            cache_key: Invalidate specific entry.

        Returns:
            Number of entries invalidated.
        """
        with self._lock:
            if cache_key:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    return 1
                return 0

            if workflow_name:
                keys_to_remove = [
                    k for k, v in self._cache.items() if v.workflow_name == workflow_name
                ]
                for key in keys_to_remove:
                    del self._cache[key]
                return len(keys_to_remove)

            return 0

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._cached_requests.clear()
            logger.info("CachingPlugin cache cleared: %d entries", count)
            return count
