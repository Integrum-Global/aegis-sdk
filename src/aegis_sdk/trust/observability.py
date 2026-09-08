"""
Aegis SDK Trust Observability Module.

Aggregate views over the trust plane: chain and verification metrics for a
time range, a compliance report for an organization, and a health snapshot of
the trust plane itself.

Operations:
- get_metrics(): chain / delegation / verification counts plus a daily timeline
- export_metrics(): the same figures, as a downloadable document
- get_compliance_report(): audited action counts and a compliance score
- get_health(): unauthenticated trust-plane health snapshot
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param


class TrustTimelinePoint(BaseModel):
    """One day of verification activity."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    date: str
    verifications: int = 0
    successful: int = 0
    failed: int = 0


class TrustMetrics(BaseModel):
    """Trust-plane metrics for a time range.

    Warning:
        The chain counts and the verification counts are each computed from a
        BOUNDED page of records, not the whole population. For an organization
        with more chains or audit entries than that page holds, every figure
        here is a sample of the most recent records rather than a total, and
        the response carries no marker distinguishing the two cases. Treat
        these as indicative, and use the compliance report -- which scans to
        exhaustion and declares when it could not -- when a figure has to be
        defensible.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    total_chains: int = 0
    active_chains: int = 0
    expired_chains: int = 0
    revoked_chains: int = 0
    total_delegations: int = 0
    total_verifications: int = 0
    successful_verifications: int = 0
    failed_verifications: int = 0
    timeline: list[TrustTimelinePoint] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    """Compliance report for an organization over a period.

    Reading this correctly turns on three fields, not on the score:

    * ``measured`` is ``False`` when the period contained no audited actions
      at all. ``compliance_score`` is then ``None``, NOT ``100.0`` -- "we
      looked and everything passed" and "we found nothing to look at" are
      different claims and this report keeps them apart.
    * ``scan_complete`` is ``False`` when the scan hit its record bound before
      exhausting the period. The score is then a sample of the period, not the
      period's figure, and ``scan_note`` says so.
    * ``violations_truncated`` is ``True`` when more violations exist than the
      ``violations`` list carries; ``violations_total`` is the real count.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    organization_id: str
    start_time: str
    end_time: str
    total_actions: int = 0
    allowed_actions: int = 0
    denied_actions: int = 0
    failed_actions: int = 0
    compliance_score: float | None = None
    violations: list[dict[str, Any]] = Field(default_factory=list)
    measured: bool = False
    measurement_reason: str | None = None
    scan_complete: bool = True
    scan_note: str | None = None
    violations_truncated: bool = False
    violations_total: int = 0
    pages_scanned: int = 0


class TrustFailure(BaseModel):
    """One active failure mode detected on the trust plane."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    failure_mode: str
    severity: str
    detected_at: str
    description: str
    impact: str


class TrustHealth(BaseModel):
    """Trust-plane health snapshot."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    healthy: bool
    active_failures: list[TrustFailure] = Field(default_factory=list)
    checked_at: str
    warnings: list[str] = Field(default_factory=list)


class TrustObservabilityModule:
    """
    Aggregate trust-plane reads.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     report = await client.trust.observability.get_compliance_report(
        ...         organization_id="org_abc123",
        ...         start_time="2026-01-01T00:00:00Z",
        ...         end_time="2026-02-01T00:00:00Z",
        ...     )
        ...     if not report.measured:
        ...         print("No audited activity in the period -- no score")
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def get_metrics(
        self,
        start: str,
        end: str,
        preset: str | None = None,
    ) -> TrustMetrics:
        """
        Get trust metrics for a time range.

        Args:
            start: ISO-8601 start of the range
            end: ISO-8601 end of the range
            preset: Named range preset, when the platform offers one

        Returns:
            Metrics, subject to the sampling caveat on :class:`TrustMetrics`.
        """
        params: dict[str, Any] = {"start": start, "end": end}
        if preset is not None:
            params["preset"] = preset

        response = await self._http.request(
            "GET",
            "/api/v1/trust/metrics",
            params=params,
        )
        return TrustMetrics(**response)

    async def export_metrics(
        self,
        start: str,
        end: str,
        preset: str | None = None,
    ) -> TrustMetrics:
        """
        Export trust metrics as a downloadable document.

        Args:
            start: ISO-8601 start of the range
            end: ISO-8601 end of the range
            preset: Named range preset, when the platform offers one

        Returns:
            The same figures :meth:`get_metrics` returns. The difference is on
            the wire, not in the data: this route sets a download disposition
            header so a browser saves the body to a file.

        Note:
            The platform accepts a ``format`` query parameter on this route and
            currently ignores it -- the body is JSON regardless. It is
            deliberately not exposed here rather than offered as a choice the
            platform will not honour.
        """
        params: dict[str, Any] = {"start": start, "end": end}
        if preset is not None:
            params["preset"] = preset

        response = await self._http.request(
            "GET",
            "/api/v1/trust/metrics/export",
            params=params,
        )
        return TrustMetrics(**response)

    async def get_compliance_report(
        self,
        organization_id: str,
        start_time: str,
        end_time: str,
    ) -> ComplianceReport:
        """
        Get the compliance report for an organization over a period.

        Args:
            organization_id: Organization to report on. Must be the caller's
                own organization; any other value is answered as not-found.
            start_time: ISO-8601 start of the period
            end_time: ISO-8601 end of the period

        Returns:
            The report. Branch on ``measured`` and ``scan_complete`` before
            reading ``compliance_score``.

        Raises:
            NotFoundError: If ``organization_id`` is not the caller's own.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/compliance/{encode_path_param(organization_id)}",
            params={"start_time": start_time, "end_time": end_time},
        )
        return ComplianceReport(**response)

    async def get_health(self) -> TrustHealth:
        """
        Get a trust-plane health snapshot.

        Returns:
            The snapshot. This route answers 200 even when degraded, so branch
            on ``healthy`` and ``active_failures`` -- a successful call is not
            a healthy verdict.

        Note:
            This route requires no authentication and is safe to poll from a
            monitoring or readiness probe. It runs every failure check with no
            context, and a check given no context reports as failing -- so a
            bare probe legitimately reports failures that reflect the absence
            of inputs rather than a degraded plane.
        """
        response = await self._http.request(
            "GET",
            "/api/v1/trust/health",
        )
        return TrustHealth(**response)
