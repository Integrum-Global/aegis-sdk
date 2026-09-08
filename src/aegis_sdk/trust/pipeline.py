"""
Aegis SDK Pipeline Trust Module.

Pre-flight trust validation for a multi-agent pipeline: confirm every agent in
the pipeline holds an active trust chain carrying the capabilities its step
requires, before the pipeline runs.

Operations:
- validate(): check every agent in a pipeline at once
- get_agent_status(): read one agent's trust status in a pipeline context
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._http import encode_path_param


class PipelineAgentStatus(BaseModel):
    """Trust status of one agent within a pipeline validation."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str
    has_trust: bool
    status: str | None = None
    missing_capabilities: list[str] = Field(default_factory=list)
    violated_constraints: list[str] = Field(default_factory=list)
    human_origin: dict[str, Any] | None = None


class PipelineTrustValidation(BaseModel):
    """Result of validating trust across a pipeline.

    ``all_valid`` is ``False`` if ANY agent lacks a chain, is missing a
    required capability, or holds a chain that is not active.

    Warning:
        ``violated_constraints`` is always empty. The platform does not
        evaluate constraints on this route today, so an empty list here means
        "not checked", NOT "none violated". Do not read ``all_valid`` as a
        constraint verdict.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    pipeline_id: str
    all_valid: bool
    agent_statuses: list[PipelineAgentStatus] = Field(default_factory=list)


class PipelineAgentTrust(BaseModel):
    """One agent's trust status in the context of a pipeline."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str
    pipeline_id: str
    has_trust: bool
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    status: str
    human_origin: dict[str, Any] | None = None


class PipelineTrustModule:
    """
    Pipeline-scoped trust validation.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     result = await client.trust.pipeline.validate(
        ...         pipeline_id="pipe_abc123",
        ...         agent_ids=["agent_1", "agent_2"],
        ...         required_capabilities={"agent_1": ["read:data"]},
        ...     )
        ...     if not result.all_valid:
        ...         for status in result.agent_statuses:
        ...             print(status.agent_id, status.missing_capabilities)
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def validate(
        self,
        pipeline_id: str,
        agent_ids: list[str],
        required_capabilities: dict[str, list[str]] | None = None,
    ) -> PipelineTrustValidation:
        """
        Validate trust for every agent in a pipeline.

        Args:
            pipeline_id: Pipeline ID. This is echoed back and used for
                labelling only -- the platform does not look the pipeline up,
                so an unknown ID validates the agents just the same.
            agent_ids: Every agent to check. All must belong to the caller's
                organization; the call fails on the first that does not.
            required_capabilities: Map of agent ID to the capabilities that
                agent's step requires. Agents absent from the map are checked
                for chain presence and active status only.

        Returns:
            The per-agent verdicts and an overall ``all_valid``.

        Raises:
            NotFoundError: If any listed agent is missing or belongs to
                another organization.
        """
        body: dict[str, Any] = {"agent_ids": agent_ids}
        if required_capabilities is not None:
            body["required_capabilities"] = required_capabilities

        response = await self._http.request(
            "POST",
            "/api/v1/trust/pipeline/validate",
            params={"pipeline_id": pipeline_id},
            json_data=body,
        )
        return PipelineTrustValidation(**response)

    async def get_agent_status(self, pipeline_id: str, agent_id: str) -> PipelineAgentTrust:
        """
        Get one agent's trust status in a pipeline context.

        Args:
            pipeline_id: Pipeline ID, echoed back for labelling
            agent_id: Agent ID

        Returns:
            The agent's chain-derived capabilities, constraints and status. An
            agent with no chain returns ``has_trust=False`` with
            ``status="none"`` rather than raising.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/pipeline/{encode_path_param(pipeline_id)}/agents/{encode_path_param(agent_id)}",
        )
        return PipelineAgentTrust(**response)
