"""Health monitoring for Nexus platform deployments.

This module provides comprehensive health checking and monitoring for Nexus
deployments across all channels (API, CLI, MCP).

Example:
    >>> from aegis_sdk.nexus import HealthMonitor, HealthStatus
    >>> monitor = HealthMonitor()
    >>>
    >>> # Register health checks
    >>> def check_database():
    ...     # Perform database health check
    ...     return True, {"latency_ms": 5}
    >>>
    >>> monitor.register("database", check_database)
    >>>
    >>> # Run checks
    >>> results = await monitor.check_all()
    >>> print(results["database"].status)  # HealthStatus.HEALTHY
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for health check functions
HealthChecker = Callable[[], tuple[bool, dict[str, Any]] | Awaitable[tuple[bool, dict[str, Any]]]]


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return status value."""
        return self.value

    @property
    def is_ok(self) -> bool:
        """Check if status indicates system is operational."""
        return self in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


class HealthCheckType(Enum):
    """Types of health checks."""

    LIVENESS = auto()  # Is the service running?
    READINESS = auto()  # Is the service ready to accept requests?
    STARTUP = auto()  # Has the service started successfully?
    DEPENDENCY = auto()  # Are dependencies healthy?

    def __str__(self) -> str:
        """Return lowercase type name."""
        return self.name.lower()


@dataclass
class HealthCheck:
    """Result of a health check execution.

    Attributes:
        name: Health check identifier.
        status: Check result status.
        details: Additional check details.
        latency_ms: Check execution time in milliseconds.
        check_type: Type of health check.
        message: Human-readable status message.
        last_checked: When the check was performed.
        consecutive_failures: Number of consecutive failures.
        error: Error message if check failed.
    """

    name: str
    status: HealthStatus
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    check_type: HealthCheckType = HealthCheckType.LIVENESS
    message: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(UTC))
    consecutive_failures: int = 0
    error: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if this health check passed."""
        return self.status == HealthStatus.HEALTHY

    @property
    def is_ok(self) -> bool:
        """Check if this health check is operational."""
        return self.status.is_ok

    def to_dict(self) -> dict[str, Any]:
        """Convert health check to dictionary representation.

        Returns:
            Dictionary representation of the health check.
        """
        return {
            "name": self.name,
            "status": str(self.status),
            "details": self.details,
            "latency_ms": self.latency_ms,
            "check_type": str(self.check_type),
            "message": self.message,
            "last_checked": self.last_checked.isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "error": self.error,
            "is_healthy": self.is_healthy,
            "is_ok": self.is_ok,
        }


@dataclass
class HealthCheckConfig:
    """Configuration for a registered health check.

    Attributes:
        name: Health check identifier.
        checker: Health check function.
        check_type: Type of health check.
        timeout_s: Timeout for check execution.
        interval_s: Interval between checks (for continuous monitoring).
        failure_threshold: Failures before marking unhealthy.
        success_threshold: Successes before marking healthy.
        critical: Whether failure should fail overall health.
        tags: Categorization tags.
    """

    name: str
    checker: HealthChecker
    check_type: HealthCheckType = HealthCheckType.LIVENESS
    timeout_s: float = 10.0
    interval_s: float = 30.0
    failure_threshold: int = 3
    success_threshold: int = 1
    critical: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class HealthSummary:
    """Summary of overall system health.

    Attributes:
        status: Overall system health status.
        checks: Individual health check results.
        healthy_count: Number of healthy checks.
        degraded_count: Number of degraded checks.
        unhealthy_count: Number of unhealthy checks.
        total_latency_ms: Total check execution time.
        timestamp: When summary was generated.
        version: Application version.
        uptime_s: System uptime in seconds.
    """

    status: HealthStatus
    checks: dict[str, HealthCheck]
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    total_latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: str = ""
    uptime_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary representation.

        Returns:
            Dictionary representation of the summary.
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


class HealthMonitor:
    """Health monitoring system for Nexus deployments.

    Provides health check registration, execution, and aggregation
    for monitoring deployment health across all channels.

    Example:
        >>> monitor = HealthMonitor(version="1.0.0")
        >>>
        >>> # Register checks
        >>> monitor.register("api", check_api, critical=True)
        >>> monitor.register("cache", check_cache)
        >>>
        >>> # Check health
        >>> summary = await monitor.check_all()
        >>> print(f"System is {summary.status}")
    """

    def __init__(
        self,
        version: str = "unknown",
        default_timeout_s: float = 10.0,
    ):
        """Initialize health monitor.

        Args:
            version: Application version string.
            default_timeout_s: Default check timeout.
        """
        self._version = version
        self._default_timeout_s = default_timeout_s
        self._checks: dict[str, HealthCheckConfig] = {}
        self._results: dict[str, HealthCheck] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._consecutive_successes: dict[str, int] = {}
        self._start_time = time.time()
        self._on_healthy_hooks: list[Callable[[str, HealthCheck], None]] = []
        self._on_unhealthy_hooks: list[Callable[[str, HealthCheck], None]] = []

    @property
    def uptime_s(self) -> float:
        """Get monitor uptime in seconds."""
        return time.time() - self._start_time

    def register(
        self,
        name: str,
        checker: HealthChecker,
        check_type: HealthCheckType = HealthCheckType.LIVENESS,
        timeout_s: float | None = None,
        interval_s: float = 30.0,
        failure_threshold: int = 3,
        success_threshold: int = 1,
        critical: bool = False,
        tags: list[str] | None = None,
    ) -> None:
        """Register a health check.

        Args:
            name: Unique check identifier.
            checker: Health check function returning (success, details).
            check_type: Type of health check.
            timeout_s: Check timeout (None uses default).
            interval_s: Check interval for continuous monitoring.
            failure_threshold: Failures before unhealthy.
            success_threshold: Successes before healthy.
            critical: Whether failure fails overall health.
            tags: Categorization tags.
        """
        config = HealthCheckConfig(
            name=name,
            checker=checker,
            check_type=check_type,
            timeout_s=timeout_s or self._default_timeout_s,
            interval_s=interval_s,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            critical=critical,
            tags=tags or [],
        )
        self._checks[name] = config
        self._consecutive_failures[name] = 0
        self._consecutive_successes[name] = 0
        logger.debug("Registered health check: %s", name)

    def unregister(self, name: str) -> bool:
        """Unregister a health check.

        Args:
            name: Check name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self._checks:
            del self._checks[name]
            self._consecutive_failures.pop(name, None)
            self._consecutive_successes.pop(name, None)
            self._results.pop(name, None)
            logger.debug("Unregistered health check: %s", name)
            return True
        return False

    async def check(self, name: str) -> HealthCheck:
        """Execute a single health check.

        Args:
            name: Check name to execute.

        Returns:
            HealthCheck result.

        Raises:
            KeyError: If check not found.
        """
        if name not in self._checks:
            raise KeyError(f"Health check not found: {name}")

        config = self._checks[name]
        start_time = time.time()
        status = HealthStatus.UNKNOWN
        details: dict[str, Any] = {}
        error: str | None = None
        message = ""

        try:
            # Execute check with timeout
            if asyncio.iscoroutinefunction(config.checker):
                result = await asyncio.wait_for(
                    config.checker(),
                    timeout=config.timeout_s,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, config.checker),
                    timeout=config.timeout_s,
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

                if self._consecutive_successes[name] >= config.success_threshold:
                    status = HealthStatus.HEALTHY
                    message = "Check passed"
                else:
                    status = HealthStatus.DEGRADED
                    message = f"Recovering ({self._consecutive_successes[name]}/{config.success_threshold})"
            else:
                self._consecutive_successes[name] = 0
                self._consecutive_failures[name] += 1

                if self._consecutive_failures[name] >= config.failure_threshold:
                    status = HealthStatus.UNHEALTHY
                    message = "Check failed"
                else:
                    status = HealthStatus.DEGRADED
                    message = (
                        f"Failing ({self._consecutive_failures[name]}/{config.failure_threshold})"
                    )

        except TimeoutError:
            self._consecutive_failures[name] += 1
            self._consecutive_successes[name] = 0
            status = HealthStatus.UNHEALTHY
            error = f"Check timed out after {config.timeout_s}s"
            message = "Timeout"

        except Exception as e:
            self._consecutive_failures[name] += 1
            self._consecutive_successes[name] = 0
            status = HealthStatus.UNHEALTHY
            error = str(e)
            message = "Exception"
            logger.error("Health check %s failed: %s", name, e)

        latency_ms = (time.time() - start_time) * 1000

        result = HealthCheck(
            name=name,
            status=status,
            details=details,
            latency_ms=latency_ms,
            check_type=config.check_type,
            message=message,
            consecutive_failures=self._consecutive_failures[name],
            error=error,
        )

        # Store result
        previous = self._results.get(name)
        self._results[name] = result

        # Invoke hooks on status change
        if previous is not None and previous.status != status:
            if status == HealthStatus.HEALTHY:
                for hook in self._on_healthy_hooks:
                    try:
                        hook(name, result)
                    except Exception as e:
                        logger.warning("Health hook failed: %s", e)
            elif status == HealthStatus.UNHEALTHY:
                for hook in self._on_unhealthy_hooks:
                    try:
                        hook(name, result)
                    except Exception as e:
                        logger.warning("Unhealthy hook failed: %s", e)

        return result

    async def check_all(
        self,
        check_types: list[HealthCheckType] | None = None,
        tags: list[str] | None = None,
    ) -> HealthSummary:
        """Execute all registered health checks.

        Args:
            check_types: Filter by check types (None for all).
            tags: Filter by tags (None for all).

        Returns:
            HealthSummary with aggregated results.
        """
        # Filter checks
        checks_to_run = self._checks.values()

        if check_types:
            checks_to_run = [c for c in checks_to_run if c.check_type in check_types]

        if tags:
            checks_to_run = [c for c in checks_to_run if any(t in c.tags for t in tags)]

        # Run checks concurrently
        tasks = [self.check(config.name) for config in checks_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        checks: dict[str, HealthCheck] = {}
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

            if result.status == HealthStatus.HEALTHY:
                healthy_count += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_count += 1
            else:
                unhealthy_count += 1
                config = self._checks.get(result.name)
                if config and config.critical:
                    has_critical_failure = True

        # Determine overall status
        if has_critical_failure or unhealthy_count > 0:
            if has_critical_failure:
                overall_status = HealthStatus.UNHEALTHY
            else:
                overall_status = HealthStatus.DEGRADED
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return HealthSummary(
            status=overall_status,
            checks=checks,
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            unhealthy_count=unhealthy_count,
            total_latency_ms=total_latency_ms,
            version=self._version,
            uptime_s=self.uptime_s,
        )

    def check_sync(self, name: str) -> HealthCheck:
        """Execute a health check synchronously.

        Args:
            name: Check name to execute.

        Returns:
            HealthCheck result.
        """
        try:
            asyncio.get_running_loop()
            # If we're in an async context, this won't work correctly
            raise RuntimeError("Use async check() in async context")
        except RuntimeError:
            pass
        return asyncio.run(self.check(name))

    def check_all_sync(
        self,
        check_types: list[HealthCheckType] | None = None,
        tags: list[str] | None = None,
    ) -> HealthSummary:
        """Execute all health checks synchronously.

        Args:
            check_types: Filter by check types.
            tags: Filter by tags.

        Returns:
            HealthSummary with aggregated results.
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError("Use async check_all() in async context")
        except RuntimeError:
            pass
        return asyncio.run(self.check_all(check_types=check_types, tags=tags))

    def get_status(self) -> dict[str, HealthCheck]:
        """Get current status of all health checks.

        Returns:
            Dictionary of check names to last results.
        """
        return dict(self._results)

    def get_check(self, name: str) -> HealthCheck | None:
        """Get last result for a specific check.

        Args:
            name: Check name.

        Returns:
            Last HealthCheck result or None.
        """
        return self._results.get(name)

    def on_healthy(self, callback: Callable[[str, HealthCheck], None]) -> None:
        """Register callback for when a check becomes healthy.

        Args:
            callback: Function called with (name, result).
        """
        self._on_healthy_hooks.append(callback)

    def on_unhealthy(self, callback: Callable[[str, HealthCheck], None]) -> None:
        """Register callback for when a check becomes unhealthy.

        Args:
            callback: Function called with (name, result).
        """
        self._on_unhealthy_hooks.append(callback)

    def list_checks(self) -> list[str]:
        """Get list of registered check names.

        Returns:
            List of check names.
        """
        return list(self._checks.keys())

    def get_check_config(self, name: str) -> HealthCheckConfig | None:
        """Get configuration for a health check.

        Args:
            name: Check name.

        Returns:
            HealthCheckConfig or None.
        """
        return self._checks.get(name)

    def is_healthy(self) -> bool:
        """Quick check if system appears healthy.

        Based on last cached results, not a fresh check.

        Returns:
            True if no unhealthy critical checks.
        """
        for name, result in self._results.items():
            config = self._checks.get(name)
            if config and config.critical and result.status == HealthStatus.UNHEALTHY:
                return False
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get health monitor statistics.

        Returns:
            Dictionary with monitor statistics.
        """
        results = list(self._results.values())
        return {
            "registered_checks": len(self._checks),
            "version": self._version,
            "uptime_s": self.uptime_s,
            "last_results": {
                "healthy": len([r for r in results if r.status == HealthStatus.HEALTHY]),
                "degraded": len([r for r in results if r.status == HealthStatus.DEGRADED]),
                "unhealthy": len([r for r in results if r.status == HealthStatus.UNHEALTHY]),
            },
            "critical_checks": len([c for c in self._checks.values() if c.critical]),
            "check_types": {
                str(t): len([c for c in self._checks.values() if c.check_type == t])
                for t in HealthCheckType
            },
        }

    def clear(self) -> None:
        """Clear all registered health checks and results."""
        self._checks.clear()
        self._results.clear()
        self._consecutive_failures.clear()
        self._consecutive_successes.clear()
        self._on_healthy_hooks.clear()
        self._on_unhealthy_hooks.clear()
        logger.info("Cleared all health checks")

    def __len__(self) -> int:
        """Get number of registered health checks."""
        return len(self._checks)

    def __contains__(self, name: str) -> bool:
        """Check if health check is registered."""
        return name in self._checks
