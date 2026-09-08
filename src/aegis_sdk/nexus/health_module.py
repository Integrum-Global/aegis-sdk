"""Health Module for Nexus v1.1 - Comprehensive health monitoring and aggregation.

This module provides enhanced health monitoring capabilities including:
- Standard health checks for all Nexus components
- Health check aggregation across modules
- REST endpoint support (GET /health)
- Pluggable health check registration
- Automatic status aggregation

Example:
    >>> from aegis_sdk.nexus import HealthModule, HealthAggregator
    >>>
    >>> # Create health module
    >>> module = HealthModule(version="1.0.0")
    >>>
    >>> # Add health checks
    >>> module.add_health_check("database", check_database)
    >>> module.add_health_check("cache", check_cache, critical=True)
    >>>
    >>> # Check health
    >>> status = await module.check()
    >>> print(status["status"])  # "healthy" or "unhealthy"
    >>>
    >>> # Get detailed status
    >>> details = module.get_status()
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import (
    Any,
)

logger = logging.getLogger(__name__)

# Type alias for health check functions
HealthCheckerFn = Callable[
    [], tuple[bool, dict[str, Any]] | Awaitable[tuple[bool, dict[str, Any]]] | bool
]


class ModuleHealthStatus(Enum):
    """Health status for modules."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPING = "stopping"

    def __str__(self) -> str:
        """Return status value."""
        return self.value

    @property
    def is_operational(self) -> bool:
        """Check if status indicates system is operational."""
        return self in (ModuleHealthStatus.HEALTHY, ModuleHealthStatus.DEGRADED)

    @property
    def http_status_code(self) -> int:
        """Get HTTP status code for this health status."""
        if self in (ModuleHealthStatus.HEALTHY, ModuleHealthStatus.DEGRADED):
            return 200
        return 503


class HealthCheckCategory(Enum):
    """Categories of health checks."""

    LIVENESS = auto()  # Is the service running?
    READINESS = auto()  # Is the service ready to accept requests?
    STARTUP = auto()  # Has the service started successfully?
    DEPENDENCY = auto()  # Are dependencies healthy?
    CUSTOM = auto()  # Custom health check

    def __str__(self) -> str:
        """Return lowercase category name."""
        return self.name.lower()


@dataclass
class ComponentHealth:
    """Health status of a single component.

    Attributes:
        name: Component name.
        status: Health status.
        message: Human-readable status message.
        details: Additional health details.
        latency_ms: Check execution time in milliseconds.
        last_checked: When check was last run.
        consecutive_failures: Number of consecutive failures.
        category: Health check category.
        critical: Whether this component is critical.
        error: Error message if unhealthy.
    """

    name: str
    status: ModuleHealthStatus = ModuleHealthStatus.UNKNOWN
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    last_checked: datetime | None = None
    consecutive_failures: int = 0
    category: HealthCheckCategory = HealthCheckCategory.LIVENESS
    critical: bool = False
    error: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        return self.status == ModuleHealthStatus.HEALTHY

    @property
    def is_operational(self) -> bool:
        """Check if component is operational."""
        return self.status.is_operational

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "name": self.name,
            "status": str(self.status),
            "message": self.message,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "consecutive_failures": self.consecutive_failures,
            "category": str(self.category),
            "critical": self.critical,
            "error": self.error,
            "is_healthy": self.is_healthy,
            "is_operational": self.is_operational,
        }


@dataclass
class HealthCheckRegistration:
    """Registration information for a health check.

    Attributes:
        name: Health check name.
        checker: Health check function.
        category: Health check category.
        timeout_s: Check timeout in seconds.
        critical: Whether failure should fail overall health.
        enabled: Whether check is enabled.
        failure_threshold: Failures before marking unhealthy.
        success_threshold: Successes before marking healthy.
        tags: Categorization tags.
    """

    name: str
    checker: HealthCheckerFn
    category: HealthCheckCategory = HealthCheckCategory.LIVENESS
    timeout_s: float = 10.0
    critical: bool = False
    enabled: bool = True
    failure_threshold: int = 3
    success_threshold: int = 1
    tags: list[str] = field(default_factory=list)


@dataclass
class AggregatedHealth:
    """Aggregated health status from all checks.

    Attributes:
        status: Overall health status.
        checks: Individual component health statuses.
        healthy_count: Number of healthy components.
        degraded_count: Number of degraded components.
        unhealthy_count: Number of unhealthy components.
        total_latency_ms: Total check execution time.
        timestamp: When aggregation was performed.
        version: Application version.
        uptime_s: System uptime in seconds.
    """

    status: ModuleHealthStatus
    checks: dict[str, ComponentHealth] = field(default_factory=dict)
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    total_latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: str = ""
    uptime_s: float = 0.0

    @property
    def http_status_code(self) -> int:
        """Get HTTP status code for this health."""
        return self.status.http_status_code

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "status": str(self.status),
            "checks": {name: check.to_dict() for name, check in self.checks.items()},
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unhealthy_count": self.unhealthy_count,
            "total_latency_ms": self.total_latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "uptime_s": self.uptime_s,
        }

    def to_endpoint_response(self) -> dict[str, Any]:
        """Format for HTTP endpoint response.

        Returns:
            Simplified response for /health endpoint.
        """
        return {
            "status": str(self.status),
            "checks": [
                {
                    "name": name,
                    "status": str(check.status),
                    "message": check.message,
                }
                for name, check in self.checks.items()
            ],
            "version": self.version,
            "uptime_s": self.uptime_s,
        }


class HealthModule:
    """Health monitoring module for Nexus v1.1.

    Provides health check registration, execution, and aggregation
    for monitoring platform health.

    Example:
        >>> module = HealthModule(version="1.0.0")
        >>> module.add_health_check("database", check_database)
        >>> status = await module.check()
    """

    def __init__(
        self,
        version: str = "unknown",
        default_timeout_s: float = 10.0,
        enable_caching: bool = True,
        cache_ttl_s: float = 5.0,
    ):
        """Initialize health module.

        Args:
            version: Application version string.
            default_timeout_s: Default check timeout.
            enable_caching: Whether to cache health results.
            cache_ttl_s: Cache time-to-live in seconds.
        """
        self._version = version
        self._default_timeout_s = default_timeout_s
        self._enable_caching = enable_caching
        self._cache_ttl_s = cache_ttl_s

        self._checks: dict[str, HealthCheckRegistration] = {}
        self._results: dict[str, ComponentHealth] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._consecutive_successes: dict[str, int] = {}
        self._start_time = time.time()
        self._last_check_time: float | None = None
        self._cached_health: AggregatedHealth | None = None

        self._lock = threading.RLock()

        # Hooks for health changes
        self._on_healthy_hooks: list[Callable[[str, ComponentHealth], None]] = []
        self._on_unhealthy_hooks: list[Callable[[str, ComponentHealth], None]] = []
        self._on_degraded_hooks: list[Callable[[str, ComponentHealth], None]] = []

        # Standard checks
        self._standard_checks_registered = False

    @property
    def uptime_s(self) -> float:
        """Get module uptime in seconds."""
        return time.time() - self._start_time

    @property
    def version(self) -> str:
        """Get application version."""
        return self._version

    def add_health_check(
        self,
        name: str,
        checker: HealthCheckerFn,
        category: HealthCheckCategory = HealthCheckCategory.LIVENESS,
        timeout_s: float | None = None,
        critical: bool = False,
        failure_threshold: int = 3,
        success_threshold: int = 1,
        tags: list[str] | None = None,
    ) -> None:
        """Add a health check.

        Args:
            name: Unique check name.
            checker: Health check function.
            category: Check category.
            timeout_s: Check timeout (None uses default).
            critical: Whether failure affects overall health.
            failure_threshold: Failures before unhealthy.
            success_threshold: Successes before healthy.
            tags: Categorization tags.
        """
        with self._lock:
            registration = HealthCheckRegistration(
                name=name,
                checker=checker,
                category=category,
                timeout_s=timeout_s or self._default_timeout_s,
                critical=critical,
                failure_threshold=failure_threshold,
                success_threshold=success_threshold,
                tags=tags or [],
            )
            self._checks[name] = registration
            self._consecutive_failures[name] = 0
            self._consecutive_successes[name] = 0
            logger.debug("Added health check: %s", name)

    def remove_health_check(self, name: str) -> bool:
        """Remove a health check.

        Args:
            name: Check name to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if name not in self._checks:
                return False

            del self._checks[name]
            self._consecutive_failures.pop(name, None)
            self._consecutive_successes.pop(name, None)
            self._results.pop(name, None)
            logger.debug("Removed health check: %s", name)
            return True

    def enable_check(self, name: str) -> bool:
        """Enable a health check.

        Args:
            name: Check name.

        Returns:
            True if enabled, False if not found.
        """
        with self._lock:
            if name not in self._checks:
                return False
            self._checks[name].enabled = True
            return True

    def disable_check(self, name: str) -> bool:
        """Disable a health check.

        Args:
            name: Check name.

        Returns:
            True if disabled, False if not found.
        """
        with self._lock:
            if name not in self._checks:
                return False
            self._checks[name].enabled = False
            return True

    async def _run_check(self, registration: HealthCheckRegistration) -> ComponentHealth:
        """Run a single health check.

        Args:
            registration: Health check registration.

        Returns:
            ComponentHealth result.
        """
        name = registration.name
        start_time = time.time()
        status = ModuleHealthStatus.UNKNOWN
        details: dict[str, Any] = {}
        error: str | None = None
        message = ""

        try:
            # Execute check with timeout
            if asyncio.iscoroutinefunction(registration.checker):
                result = await asyncio.wait_for(
                    registration.checker(),
                    timeout=registration.timeout_s,
                )
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, registration.checker),
                    timeout=registration.timeout_s,
                )

            # Parse result
            if isinstance(result, tuple) and len(result) >= 2:
                success, details = result[0], result[1]
            elif isinstance(result, bool):
                success = result
            else:
                success = bool(result)

            if success:
                self._consecutive_failures[name] = 0
                self._consecutive_successes[name] += 1

                if self._consecutive_successes[name] >= registration.success_threshold:
                    status = ModuleHealthStatus.HEALTHY
                    message = "Check passed"
                else:
                    status = ModuleHealthStatus.DEGRADED
                    message = f"Recovering ({self._consecutive_successes[name]}/{registration.success_threshold})"
            else:
                self._consecutive_successes[name] = 0
                self._consecutive_failures[name] += 1

                if self._consecutive_failures[name] >= registration.failure_threshold:
                    status = ModuleHealthStatus.UNHEALTHY
                    message = "Check failed"
                else:
                    status = ModuleHealthStatus.DEGRADED
                    message = f"Failing ({self._consecutive_failures[name]}/{registration.failure_threshold})"

        except TimeoutError:
            self._consecutive_failures[name] += 1
            self._consecutive_successes[name] = 0
            status = ModuleHealthStatus.UNHEALTHY
            error = f"Check timed out after {registration.timeout_s}s"
            message = "Timeout"

        except Exception as e:
            self._consecutive_failures[name] += 1
            self._consecutive_successes[name] = 0
            status = ModuleHealthStatus.UNHEALTHY
            error = "Health check exception"
            message = "Exception"
            logger.error("Health check %s failed: %s", name, e, exc_info=True)

        latency_ms = (time.time() - start_time) * 1000

        result = ComponentHealth(
            name=name,
            status=status,
            message=message,
            details=details,
            latency_ms=latency_ms,
            last_checked=datetime.now(UTC),
            consecutive_failures=self._consecutive_failures[name],
            category=registration.category,
            critical=registration.critical,
            error=error,
        )

        # Check for status changes and invoke hooks
        previous = self._results.get(name)
        self._results[name] = result

        if previous is not None and previous.status != status:
            if status == ModuleHealthStatus.HEALTHY:
                for hook in self._on_healthy_hooks:
                    try:
                        hook(name, result)
                    except Exception as e:
                        logger.warning("Healthy hook failed: %s", e)
            elif status == ModuleHealthStatus.UNHEALTHY:
                for hook in self._on_unhealthy_hooks:
                    try:
                        hook(name, result)
                    except Exception as e:
                        logger.warning("Unhealthy hook failed: %s", e)
            elif status == ModuleHealthStatus.DEGRADED:
                for hook in self._on_degraded_hooks:
                    try:
                        hook(name, result)
                    except Exception as e:
                        logger.warning("Degraded hook failed: %s", e)

        return result

    async def check(
        self,
        category: HealthCheckCategory | None = None,
        tags: list[str] | None = None,
        force: bool = False,
    ) -> AggregatedHealth:
        """Run all health checks and return aggregated status.

        Args:
            category: Filter by category.
            tags: Filter by tags.
            force: Force fresh check (ignore cache).

        Returns:
            AggregatedHealth with overall status.
        """
        # Check cache
        if not force and self._enable_caching and self._cached_health:
            cache_age = time.time() - (self._last_check_time or 0)
            if cache_age < self._cache_ttl_s:
                return self._cached_health

        with self._lock:
            # Filter checks
            checks_to_run = [c for c in self._checks.values() if c.enabled]

            if category:
                checks_to_run = [c for c in checks_to_run if c.category == category]

            if tags:
                checks_to_run = [c for c in checks_to_run if any(t in c.tags for t in tags)]

        # Run checks concurrently
        tasks = [self._run_check(check) for check in checks_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        checks: dict[str, ComponentHealth] = {}
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0
        total_latency_ms = 0.0
        has_critical_failure = False

        for result in results:
            if isinstance(result, Exception):
                logger.error("Health check failed: %s", result)
                continue

            checks[result.name] = result
            total_latency_ms += result.latency_ms

            if result.status == ModuleHealthStatus.HEALTHY:
                healthy_count += 1
            elif result.status == ModuleHealthStatus.DEGRADED:
                degraded_count += 1
            else:
                unhealthy_count += 1
                if result.critical:
                    has_critical_failure = True

        # Determine overall status
        if has_critical_failure:
            overall_status = ModuleHealthStatus.UNHEALTHY
        elif unhealthy_count > 0:
            overall_status = ModuleHealthStatus.DEGRADED
        elif degraded_count > 0:
            overall_status = ModuleHealthStatus.DEGRADED
        else:
            overall_status = ModuleHealthStatus.HEALTHY

        aggregated = AggregatedHealth(
            status=overall_status,
            checks=checks,
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            unhealthy_count=unhealthy_count,
            total_latency_ms=total_latency_ms,
            version=self._version,
            uptime_s=self.uptime_s,
        )

        # Update cache
        self._cached_health = aggregated
        self._last_check_time = time.time()

        return aggregated

    def check_sync(
        self,
        category: HealthCheckCategory | None = None,
        tags: list[str] | None = None,
        force: bool = False,
    ) -> AggregatedHealth:
        """Run health checks synchronously.

        Args:
            category: Filter by category.
            tags: Filter by tags.
            force: Force fresh check.

        Returns:
            AggregatedHealth with overall status.
        """
        return asyncio.run(self.check(category=category, tags=tags, force=force))

    def get_status(self) -> dict[str, ComponentHealth]:
        """Get current status of all components.

        Returns:
            Dictionary of component names to health status.
        """
        return dict(self._results)

    def get_component(self, name: str) -> ComponentHealth | None:
        """Get health status of a specific component.

        Args:
            name: Component name.

        Returns:
            ComponentHealth or None.
        """
        return self._results.get(name)

    def is_healthy(self) -> bool:
        """Quick check if system is healthy.

        Based on cached results, not a fresh check.

        Returns:
            True if no critical components are unhealthy.
        """
        for name, result in self._results.items():
            check = self._checks.get(name)
            if check and check.critical and result.status == ModuleHealthStatus.UNHEALTHY:
                return False
        return True

    def list_checks(self) -> list[str]:
        """Get list of registered check names.

        Returns:
            List of check names.
        """
        return list(self._checks.keys())

    def get_check_config(self, name: str) -> HealthCheckRegistration | None:
        """Get configuration for a health check.

        Args:
            name: Check name.

        Returns:
            HealthCheckRegistration or None.
        """
        return self._checks.get(name)

    # Hooks

    def on_healthy(self, callback: Callable[[str, ComponentHealth], None]) -> None:
        """Register callback for when a check becomes healthy.

        Args:
            callback: Callback function (name, result).
        """
        self._on_healthy_hooks.append(callback)

    def on_unhealthy(self, callback: Callable[[str, ComponentHealth], None]) -> None:
        """Register callback for when a check becomes unhealthy.

        Args:
            callback: Callback function (name, result).
        """
        self._on_unhealthy_hooks.append(callback)

    def on_degraded(self, callback: Callable[[str, ComponentHealth], None]) -> None:
        """Register callback for when a check becomes degraded.

        Args:
            callback: Callback function (name, result).
        """
        self._on_degraded_hooks.append(callback)

    # Standard Health Checks

    def register_standard_checks(
        self,
        workflow_registry: Any = None,
        session_manager: Any = None,
        events_module: Any = None,
    ) -> None:
        """Register standard health checks for Nexus components.

        Args:
            workflow_registry: Optional workflow registry instance.
            session_manager: Optional session manager instance.
            events_module: Optional events module instance.
        """
        if self._standard_checks_registered:
            return

        # Workflow registry check
        if workflow_registry is not None:

            def check_workflow_registry():
                try:
                    count = len(workflow_registry)
                    return True, {"workflow_count": count}
                except Exception as e:
                    logger.error("Workflow registry check failed: %s", e, exc_info=True)
                    return False, {"error": "Workflow registry check failed"}

            self.add_health_check(
                "workflow_registry",
                check_workflow_registry,
                category=HealthCheckCategory.READINESS,
                tags=["core"],
            )

        # Session manager check
        if session_manager is not None:

            def check_session_manager():
                try:
                    stats = (
                        session_manager.get_stats() if hasattr(session_manager, "get_stats") else {}
                    )
                    return True, stats
                except Exception as e:
                    logger.error("Session manager check failed: %s", e, exc_info=True)
                    return False, {"error": "Session manager check failed"}

            self.add_health_check(
                "session_manager",
                check_session_manager,
                category=HealthCheckCategory.READINESS,
                tags=["core"],
            )

        # Events module check
        if events_module is not None:

            def check_events_module():
                try:
                    stats = events_module.get_stats() if hasattr(events_module, "get_stats") else {}
                    return True, stats
                except Exception as e:
                    logger.error("Events module check failed: %s", e, exc_info=True)
                    return False, {"error": "Events module check failed"}

            self.add_health_check(
                "events_module",
                check_events_module,
                category=HealthCheckCategory.READINESS,
                tags=["core"],
            )

        # Basic liveness check
        def check_liveness():
            return True, {"uptime_s": self.uptime_s}

        self.add_health_check(
            "liveness",
            check_liveness,
            category=HealthCheckCategory.LIVENESS,
            tags=["basic"],
        )

        self._standard_checks_registered = True
        logger.debug("Registered standard health checks")

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """Get module statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._lock:
            results = list(self._results.values())
            return {
                "registered_checks": len(self._checks),
                "version": self._version,
                "uptime_s": self.uptime_s,
                "last_check_time": self._last_check_time,
                "cache_enabled": self._enable_caching,
                "cache_ttl_s": self._cache_ttl_s,
                "results": {
                    "healthy": len([r for r in results if r.status == ModuleHealthStatus.HEALTHY]),
                    "degraded": len(
                        [r for r in results if r.status == ModuleHealthStatus.DEGRADED]
                    ),
                    "unhealthy": len(
                        [r for r in results if r.status == ModuleHealthStatus.UNHEALTHY]
                    ),
                },
                "critical_checks": len([c for c in self._checks.values() if c.critical]),
                "by_category": {
                    str(cat): len([c for c in self._checks.values() if c.category == cat])
                    for cat in HealthCheckCategory
                },
            }

    def clear(self) -> None:
        """Clear all health checks and results."""
        with self._lock:
            self._checks.clear()
            self._results.clear()
            self._consecutive_failures.clear()
            self._consecutive_successes.clear()
            self._cached_health = None
            self._last_check_time = None
            self._standard_checks_registered = False
            logger.info("Cleared all health checks")

    def __len__(self) -> int:
        """Get number of registered health checks."""
        return len(self._checks)

    def __contains__(self, name: str) -> bool:
        """Check if health check is registered."""
        return name in self._checks


class HealthAggregator:
    """Aggregates health from multiple HealthModule instances.

    Provides a unified view of health across multiple modules
    or services in a distributed system.

    Example:
        >>> aggregator = HealthAggregator()
        >>> aggregator.add_module("api", api_health_module)
        >>> aggregator.add_module("worker", worker_health_module)
        >>> status = await aggregator.check_all()
    """

    def __init__(self, version: str = "unknown"):
        """Initialize aggregator.

        Args:
            version: Application version.
        """
        self._version = version
        self._modules: dict[str, HealthModule] = {}
        self._lock = threading.RLock()
        self._start_time = time.time()

    @property
    def uptime_s(self) -> float:
        """Get aggregator uptime in seconds."""
        return time.time() - self._start_time

    def add_module(self, name: str, module: HealthModule) -> None:
        """Add a health module.

        Args:
            name: Module name.
            module: HealthModule instance.
        """
        with self._lock:
            self._modules[name] = module
            logger.debug("Added health module: %s", name)

    def remove_module(self, name: str) -> bool:
        """Remove a health module.

        Args:
            name: Module name.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if name not in self._modules:
                return False
            del self._modules[name]
            logger.debug("Removed health module: %s", name)
            return True

    async def check_all(self, force: bool = False) -> dict[str, AggregatedHealth]:
        """Check health of all modules.

        Args:
            force: Force fresh checks.

        Returns:
            Dictionary of module names to health status.
        """
        results = {}
        tasks = []

        with self._lock:
            modules = dict(self._modules)

        for name, module in modules.items():
            tasks.append((name, module.check(force=force)))

        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error("Health check for module %s failed: %s", name, e)
                results[name] = AggregatedHealth(
                    status=ModuleHealthStatus.UNKNOWN,
                    version=self._version,
                )

        return results

    async def get_aggregate_status(self, force: bool = False) -> AggregatedHealth:
        """Get aggregated health status across all modules.

        Args:
            force: Force fresh checks.

        Returns:
            Combined AggregatedHealth.
        """
        module_results = await self.check_all(force=force)

        all_checks: dict[str, ComponentHealth] = {}
        healthy_count = 0
        degraded_count = 0
        unhealthy_count = 0
        total_latency_ms = 0.0
        has_critical_failure = False

        for module_name, module_health in module_results.items():
            for check_name, check_health in module_health.checks.items():
                full_name = f"{module_name}.{check_name}"
                all_checks[full_name] = check_health
                total_latency_ms += check_health.latency_ms

                if check_health.status == ModuleHealthStatus.HEALTHY:
                    healthy_count += 1
                elif check_health.status == ModuleHealthStatus.DEGRADED:
                    degraded_count += 1
                else:
                    unhealthy_count += 1
                    if check_health.critical:
                        has_critical_failure = True

        # Determine overall status
        if has_critical_failure:
            overall_status = ModuleHealthStatus.UNHEALTHY
        elif unhealthy_count > 0:
            overall_status = ModuleHealthStatus.DEGRADED
        elif degraded_count > 0:
            overall_status = ModuleHealthStatus.DEGRADED
        else:
            overall_status = ModuleHealthStatus.HEALTHY

        return AggregatedHealth(
            status=overall_status,
            checks=all_checks,
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            unhealthy_count=unhealthy_count,
            total_latency_ms=total_latency_ms,
            version=self._version,
            uptime_s=self.uptime_s,
        )

    def list_modules(self) -> list[str]:
        """Get list of module names.

        Returns:
            List of module names.
        """
        return list(self._modules.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get aggregator statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._lock:
            return {
                "module_count": len(self._modules),
                "modules": list(self._modules.keys()),
                "version": self._version,
                "uptime_s": self.uptime_s,
            }

    def clear(self) -> int:
        """Clear all modules.

        Returns:
            Number of modules cleared.
        """
        with self._lock:
            count = len(self._modules)
            self._modules.clear()
            logger.info("Cleared %d health modules", count)
            return count

    def __len__(self) -> int:
        """Get number of modules."""
        return len(self._modules)

    def __contains__(self, name: str) -> bool:
        """Check if module is registered."""
        return name in self._modules
