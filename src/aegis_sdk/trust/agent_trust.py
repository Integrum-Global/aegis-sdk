"""
Aegis SDK Agent Trust Module.

Per-agent projections of the trust plane: what an agent is permitted to do,
what constrains it, how the platform scores it, and how much of its CARE
budget it has consumed.

Operations:
- get_capabilities() / get_constraints(): the agent's genesis grants
- get_summary(): compact trust card for an agent
- get_with_trust(): agent identity composed with its trust chain
- get_capability_summary(): per-capability rows with source and status
- get_trust_score(): display-only A-F grade with a 5-dimension radar
- get_care_budget(): display-only 5-dimension CARE budget

Every route here is a READ. None of them makes a governance decision, and the
scoring and budget projections are explicitly display-only: the platform's
enforcement path does not consult them.
"""

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class AgentTrustSummary(TolerantModel):
    """Compact trust summary for an agent.

    When the agent has no trust chain the platform returns ``has_trust=False``
    with zeroed counts and a ``status`` of ``"none"`` -- an explicit empty
    state, not an error.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str
    has_trust: bool
    status: str
    capabilities_count: int = 0
    delegations_count: int = 0
    last_verified: str | None = None
    human_origin: dict[str, Any] | None = None


class AgentWithTrust(TolerantModel):
    """An agent composed with its trust chain.

    Note:
        ``protocols`` and ``endpoints`` are always emitted as empty lists. The
        platform has no backing data source for either field today and returns
        real empty arrays rather than fabricated values -- treat a non-empty
        list as a future capability, never assume one is populated.

        ``trust_status`` is a projection of the chain state onto a smaller
        vocabulary (``valid`` / ``pending`` / ``invalid`` / ``revoked`` /
        ``expired``). A SUSPENDED chain projects to ``invalid``, so this field
        alone cannot distinguish a suspended chain from other unusable states;
        read the chain itself when that distinction matters.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    name: str = ""
    trust_status: str
    trust_chain_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    established_by: str | None = None
    expires_at: str | None = None


class CapabilitySummaryEntry(TolerantModel):
    """One capability with its provenance."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    capability: str
    source: str
    status: str


class TrustScoreDimension(TolerantModel):
    """One dimension of the display-only trust radar."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str
    label: str
    care_dimension: str = Field(alias="careDimension")
    score: float
    weight: float
    evidence_summary: str | None = Field(None, alias="evidenceSummary")


class AgentTrustScore(TolerantModel):
    """Display-only trust grade and 5-dimension radar for an agent.

    DISPLAY ONLY. This is computed from recorded evidence for presentation and
    is not consulted by any authorization decision. A missing evidence
    dimension scores zero rather than full marks, so a brand-new agent grades
    at the bottom of the scale -- that is the intended fail-closed reading, not
    a defect.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str = Field(alias="agentId")
    organization_id: str = Field(alias="organizationId")
    composite_score: float = Field(alias="compositeScore")
    grade: str
    current_posture: str | None = Field(None, alias="currentPosture")
    calculated_at: str = Field(alias="calculatedAt")
    dimensions: list[TrustScoreDimension] = Field(default_factory=list)


class CareBudgetDimension(TolerantModel):
    """One CARE constraint dimension with its limit and consumption.

    ``used`` is ``None`` and ``available`` is ``False`` for any dimension with
    no durable consumption counter behind it. That is an explicit empty state:
    do not read ``used is None`` as zero consumption.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str
    label: str
    care_dimension: str = Field(alias="careDimension")
    unit: str | None = None
    used: float | None = None
    limit: float | None = None
    available: bool = False
    detail: str | None = None
    binding: str | None = None


class AgentCareBudget(TolerantModel):
    """Display-only 5-dimension CARE budget for an agent.

    DISPLAY ONLY -- no enforcement decision reads this projection.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    agent_id: str = Field(alias="agentId")
    organization_id: str = Field(alias="organizationId")
    dimensions: list[CareBudgetDimension] = Field(default_factory=list)


class AgentTrustModule:
    """
    Per-agent trust-plane reads.

    Example:
        >>> async with AgenticOSClient(api_key="sk_live_...") as client:
        ...     summary = await client.trust.agents.get_summary("agent_abc123")
        ...     if not summary.has_trust:
        ...         print("Agent has no trust chain")
    """

    def __init__(self, http_client: Any) -> None:
        """Initialize with HTTP client."""
        self._http = http_client

    async def get_capabilities(self, agent_id: str) -> list[str]:
        """
        Get the capabilities granted at the agent's trust chain genesis.

        Args:
            agent_id: Agent ID

        Returns:
            Capability names. An agent with no trust chain returns an empty
            list rather than raising -- an empty list therefore means either
            "no chain" or "a chain granting nothing"; call
            :meth:`get_summary` when the distinction matters.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/capabilities",
        )
        return list(response or [])

    async def get_constraints(self, agent_id: str) -> list[str]:
        """
        Get the constraints recorded at the agent's trust chain genesis.

        Args:
            agent_id: Agent ID

        Returns:
            Constraint names. As with :meth:`get_capabilities`, an agent with
            no chain returns an empty list.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/constraints",
        )
        return list(response or [])

    async def get_summary(self, agent_id: str) -> AgentTrustSummary:
        """
        Get a compact trust summary for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            The summary, including ``has_trust=False`` when no chain exists.

        Note:
            ``last_verified`` is always ``None`` today -- the platform does not
            yet track a last-verification timestamp on this surface.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/trust-summary",
        )
        return AgentTrustSummary(**response)

    async def get_with_trust(self, agent_id: str) -> AgentWithTrust:
        """
        Get an agent composed with its trust chain.

        Args:
            agent_id: Agent ID

        Returns:
            Agent identity plus chain-derived capabilities, constraints and
            status.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/with-trust",
        )
        return AgentWithTrust(**response)

    async def get_capability_summary(self, agent_id: str) -> list[CapabilitySummaryEntry]:
        """
        Get per-capability rows with their provenance.

        Args:
            agent_id: Agent ID

        Returns:
            One row per genesis capability. Every row currently reports
            ``source="genesis"`` and ``status="active"``: the platform derives
            them from the genesis grant alone, so these two fields do not yet
            discriminate between capability sources.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/capability-summary",
        )
        return [CapabilitySummaryEntry(**item) for item in response or []]

    async def get_trust_score(self, agent_id: str) -> AgentTrustScore:
        """
        Get the display-only trust grade and radar for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            The computed score.

        Raises:
            NotFoundError: If the agent does not exist, belongs to another
                organization, or has no recorded evidence yet. All three are
                answered as not-found; a fresh agent with no evidence is
                therefore indistinguishable from a missing one on this route.
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/trust-score",
        )
        return AgentTrustScore(**response)

    async def get_care_budget(self, agent_id: str) -> AgentCareBudget:
        """
        Get the display-only 5-dimension CARE budget for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Per-dimension limit and consumption. Dimensions with no durable
            counter report ``used=None`` / ``available=False``.

        Example:
            >>> budget = await client.trust.agents.get_care_budget("agent_abc123")
            >>> for dimension in budget.dimensions:
            ...     if dimension.available:
            ...         print(dimension.label, dimension.used, dimension.limit)
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/trust/agents/{encode_path_param(agent_id)}/care-budget",
        )
        return AgentCareBudget(**response)
