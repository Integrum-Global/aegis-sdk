"""
Aegis SDK Trust Revocation Module.

Revocation withdraws trust from an agent, and its cascade fans out to every
chain that descends from it. A cascade that runs out of time is recorded as an
INCOMPLETE job rather than silently reported as success -- so this module also
covers discovering those jobs and resuming them.

Operations:
- revoke(): withdraw trust from a single agent
- list_incomplete_jobs(): find cascades that did not finish
- resume_job(): finish an incomplete cascade
"""

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class RevocationResult(TolerantModel):
    """Outcome of revoking trust for one agent.

    Carries a human-readable ``message`` and ``reason`` alongside the fields
    the underlying cascade produced; the exact cascade fields are not declared
    by the platform, so read them through ``model_extra``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    message: str | None = None
    reason: str | None = None


class IncompleteRevocationJob(TolerantModel):
    """A cascade revocation that did not complete.

    While a job sits in this state, some of the agents it names may STILL hold
    active trust chains. ``completed_count`` against ``total_targets`` is the
    measure of how far it got.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    target_agent_id: str
    status: str
    reason: str
    total_targets: int
    completed_count: int
    failed_count: int
    initiated_by: str
    created_at: str
    updated_at: str


class RevocationJobResumeResult(TolerantModel):
    """Outcome of resuming an incomplete cascade revocation.

    ``timed_out`` reports whether the RESUME itself ran out of time. A resume
    that times out again leaves the job incomplete and can be called again.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    revocation_job_id: str
    status: str
    total_targets: int
    total_revoked: int
    newly_revoked: list[str] = Field(default_factory=list)
    timed_out: bool


class RevocationModule:
    """
    Trust revocation and incomplete-cascade recovery.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     jobs = await client.trust.revocation.list_incomplete_jobs()
        ...     for job in jobs:
        ...         await client.trust.revocation.resume_job(job.id)
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def revoke(self, agent_id: str, reason: str) -> RevocationResult:
        """
        Revoke trust for an agent.

        Args:
            agent_id: Agent whose trust is withdrawn
            reason: Why -- recorded on the revocation audit trail

        Returns:
            The revocation outcome.

        Raises:
            NotFoundError: If the agent is unknown, belongs to another
                organization, or holds no ACTIVE trust chain. The last case is
                deliberate: a revocation that revoked nothing fails loudly
                rather than reporting success.

        Note:
            Despite the name, this runs the cascade machinery scoped to the one
            agent. Chains descending from it are affected. Requires a
            revocation permission, not merely trust write access.
        """
        response = await self._http.request(
            "POST",
            "/api/v1/trust/revoke",
            params={"agent_id": agent_id, "reason": reason},
        )
        return RevocationResult(**(response or {}))

    async def list_incomplete_jobs(self) -> list[IncompleteRevocationJob]:
        """
        List cascade revocations that did not complete.

        Returns:
            Every incomplete job in the caller's organization. An empty list
            means every cascade finished.

        Note:
            This is the discovery surface for a real hazard: until a job here
            is resumed, agents it named may still be trusted. Requires the
            same revocation permission as revoking, because knowing which jobs
            are incomplete reveals which agents are still trusted.
        """
        response = await self._http.request(
            "GET",
            "/api/v1/trust/revoke/jobs/incomplete",
        )
        items: list[dict[str, Any]] = (response or {}).get("items", [])
        return [IncompleteRevocationJob(**item) for item in items]

    async def resume_job(self, job_id: str) -> RevocationJobResumeResult:
        """
        Resume an incomplete cascade revocation.

        Args:
            job_id: Job ID from :meth:`list_incomplete_jobs`

        Returns:
            What the resume achieved, including whether it timed out again.

        Raises:
            NotFoundError: If the job belongs to another organization.
            ValidationError: If the job is not in a resumable state, or if the
                resume still did not achieve full coverage -- it fails rather
                than reporting a partial success as done.

        Note:
            Idempotent. Per-agent steps only touch chains that are still
            active, so resuming an already-covered job is a safe no-op.
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/trust/revoke/jobs/{encode_path_param(job_id)}/resume",
        )
        return RevocationJobResumeResult(**response)
