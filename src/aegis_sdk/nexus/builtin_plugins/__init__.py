"""Nexus Built-in Plugins Package.

Built-in plugins for extending Nexus functionality.

Available plugins:
- LoggingPlugin: Logs all requests/responses
- MetricsPlugin: Collects request metrics (latency, count, errors)
- CachingPlugin: Caches workflow execution results
"""

from .builtins import (
    CacheEntry,
    CachingPlugin,
    LoggingPlugin,
    MetricsPlugin,
    RequestMetrics,
)

__all__ = [
    "LoggingPlugin",
    "MetricsPlugin",
    "CachingPlugin",
    "RequestMetrics",
    "CacheEntry",
]
