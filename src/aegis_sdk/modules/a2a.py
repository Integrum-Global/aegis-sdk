"""
Agent-to-Agent (A2A) SDK Module.

Provides programmatic access to A2A orchestration operations:
- discover(): Discover A2A-enabled agents
- get_model_card(): Get A2A model card for agent
- get_workers(): Get workers for manager agent
- route(): Find best agent for task
- invoke(): Invoke A2A-enabled agent
- orchestrate(): Execute multi-agent orchestration
"""

from typing import Any

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class AgentCapability(TolerantModel):
    """Agent capability model."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)


class A2AModelCard(TolerantModel):
    """A2A model card for agent."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    name: str
    description: str | None = None
    unit_type: str | None = Field(None, alias="unitType")
    agent_subtype: str | None = Field(None, alias="agentSubtype")
    capabilities: list[AgentCapability] = Field(default_factory=list)
    a2a_enabled: bool = Field(alias="a2aEnabled")
    provider: str | None = None
    model_id: str | None = Field(None, alias="modelId")


class DiscoveredAgent(TolerantModel):
    """Discovered A2A agent."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    name: str
    description: str | None = None
    capabilities: list[AgentCapability] = Field(default_factory=list)
    a2a_enabled: bool = Field(alias="a2aEnabled")
    match_score: float | None = Field(None, alias="matchScore")


class RouteResult(TolerantModel):
    """Result of task routing."""

    model_config = ConfigDict(populate_by_name=True)

    matched: bool
    agent: DiscoveredAgent | None = None
    match_score: float | None = Field(None, alias="matchScore")
    reasoning: str | None = None


class InvokeResult(TolerantModel):
    """
    Result of agent invocation.

    Note:
        ``result`` is a backend-shaped ``dict[str, Any]`` (e.g.
        ``{"response": "..."}``) per ``InvokeAgentResponse`` in — not a plain string.
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    result: dict[str, Any] | None = None
    error: str | None = None


class OrchestrateResult(TolerantModel):
    """
    Result of multi-agent orchestration.

    Note:
        ``final_result`` and each ``task_history`` entry are backend-shaped
        ``dict[str, Any]`` payloads (see ``OrchestrateResponse`` /
        ``OrchestrationResult.to_dict()``) — the backend
        does not emit a typed ``TaskHistoryItem`` shape (no ``agentId`` /
        ``agentName`` / ``task`` / ``iteration`` keys). Consumers should read
        ``task_history[i]["task_id"]`` / ``["description"]`` / ``["status"]``
        / ``["assigned_agent_id"]`` / ``["result"]`` / ``["error"]`` /
        ``["created_at"]`` / ``["started_at"]`` / ``["completed_at"]`` /
        ``["subtasks"]``.
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    objective: str
    final_result: dict[str, Any] | None = Field(None, alias="finalResult")
    tasks_completed: int = Field(alias="tasksCompleted")
    tasks_failed: int = Field(alias="tasksFailed")
    iterations: int
    agents_used: list[str] = Field(alias="agentsUsed")
    execution_time_ms: int = Field(alias="executionTimeMs")
    error: str | None = None
    task_history: list[dict[str, Any]] = Field(default_factory=list, alias="taskHistory")


class A2AModule:
    """
    Agent-to-Agent (A2A) SDK module.

    Provides methods for A2A orchestration operations including agent discovery,
    task routing, agent invocation, and multi-agent orchestration.

    Methods:
        - discover(): Discover A2A-enabled agents
        - get_model_card(): Get A2A model card for agent
        - get_workers(): Get workers configured for manager agent
        - route(): Find best agent for task
        - invoke(): Invoke A2A-enabled agent
        - orchestrate(): Execute multi-agent orchestration

    Example:
        >>> from aegis_sdk import AgenticOS
        >>> client = AgenticOS(api_key="your-api-key")
        >>>
        >>> # Discover agents with capability
        >>> agents = await client.a2a.discover(
        ...     capability_keywords=["data-analysis", "python"]
        ... )
        >>>
        >>> # Orchestrate multi-agent workflow
        >>> result = await client.a2a.orchestrate(
        ...     manager_agent_id="mgr-123",
        ...     objective="Analyze Q4 sales data and generate report",
        ... )
    """

    def __init__(self, http_client):
        """Initialize A2A module with HTTP client."""
        self._http = http_client

    async def discover(
        self,
        workspace_id: str | None = None,
        capability_keywords: list[str] | None = None,
    ) -> list[DiscoveredAgent]:
        """
        Discover A2A-enabled agents.

        Args:
            workspace_id: Optional workspace to search in
            capability_keywords: Keywords to match agent capabilities

        Returns:
            List of discovered agents with match scores

        Example:
            >>> agents = await client.a2a.discover(
            ...     capability_keywords=["data-analysis", "reporting"]
            ... )
            >>> for agent in agents:
            ...     print(f"{agent.name}: {agent.match_score}")
        """
        data: dict[str, Any] = {}
        if workspace_id:
            data["workspace_id"] = workspace_id
        if capability_keywords:
            data["capability_keywords"] = capability_keywords

        response = await self._http.request(
            "POST",
            "/api/v1/a2a/discover",
            json_data=data if data else None,
        )
        agents = response.get("agents", [])
        return [DiscoveredAgent(**agent) for agent in agents]

    async def get_model_card(self, agent_id: str) -> A2AModelCard:
        """
        Get A2A model card for agent.

        Args:
            agent_id: Agent ID

        Returns:
            A2A model card with capabilities and configuration

        Example:
            >>> card = await client.a2a.get_model_card("agent-123")
            >>> print(f"Agent: {card.name}")
            >>> print(f"A2A enabled: {card.a2a_enabled}")
            >>> for cap in card.capabilities:
            ...     print(f"  - {cap.name}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/a2a/agent/{encode_path_param(agent_id)}/card",
        )
        return A2AModelCard(**response)

    async def get_workers(self, manager_id: str) -> list[DiscoveredAgent]:
        """
        Get workers configured for manager agent.

        Args:
            manager_id: Manager agent ID

        Returns:
            List of worker agents

        Example:
            >>> workers = await client.a2a.get_workers("manager-123")
            >>> for worker in workers:
            ...     print(f"Worker: {worker.name}")
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/a2a/workers/{encode_path_param(manager_id)}",
        )
        agents = response.get("agents", [])
        return [DiscoveredAgent(**agent) for agent in agents]

    async def route(
        self,
        task: str,
        keywords: list[str] | None = None,
        workspace_id: str | None = None,
    ) -> RouteResult:
        """
        Find best agent for task.

        Args:
            task: Task description
            keywords: Optional keywords for matching
            workspace_id: Optional workspace to search in

        Returns:
            Route result with matched agent and score

        Example:
            >>> result = await client.a2a.route(
            ...     task="Analyze sales data for Q4",
            ...     keywords=["data-analysis", "sales"]
            ... )
            >>> if result.matched:
            ...     print(f"Best agent: {result.agent.name}")
            ...     print(f"Score: {result.match_score}")
        """
        data: dict[str, Any] = {"task": task}
        if keywords:
            data["keywords"] = keywords
        if workspace_id:
            data["workspace_id"] = workspace_id

        response = await self._http.request(
            "POST",
            "/api/v1/a2a/route",
            json_data=data,
        )
        return RouteResult(**response)

    async def invoke(
        self,
        agent_id: str,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> InvokeResult:
        """
        Invoke A2A-enabled agent with task.

        Args:
            agent_id: Agent to invoke
            task: Task to execute
            context: Optional context data

        Returns:
            Invocation result with response or error

        Example:
            >>> result = await client.a2a.invoke(
            ...     agent_id="agent-123",
            ...     task="Generate Q4 sales report",
            ...     context={"quarter": "Q4", "year": 2024}
            ... )
            >>> if result.success:
            ...     print(result.result)
            ... else:
            ...     print(f"Error: {result.error}")
        """
        data: dict[str, Any] = {
            "agent_id": agent_id,
            "task": task,
        }
        if context:
            data["context"] = context

        response = await self._http.request(
            "POST",
            "/api/v1/a2a/invoke",
            json_data=data,
        )
        return InvokeResult(**response)

    async def orchestrate(
        self,
        manager_agent_id: str,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> OrchestrateResult:
        """
        Execute multi-agent orchestration via manager agent.

        The manager agent coordinates workers to achieve the objective.
        This is the primary A2A capability for complex workflows.

        Args:
            manager_agent_id: Manager agent to orchestrate
            objective: High-level objective to achieve
            context: Optional context data for orchestration

        Returns:
            Orchestration result with task history and final output

        Example:
            >>> result = await client.a2a.orchestrate(
            ...     manager_agent_id="mgr-123",
            ...     objective="Analyze Q4 data and generate report",
            ...     context={"data_source": "s3://sales/q4"}
            ... )
            >>> if result.success:
            ...     print(f"Completed in {result.execution_time_ms}ms")
            ...     print(f"Tasks: {result.tasks_completed} completed")
            ...     print(f"Agents used: {', '.join(result.agents_used)}")
            ...     print(f"Result: {result.final_result}")
        """
        data: dict[str, Any] = {
            "manager_agent_id": manager_agent_id,
            "objective": objective,
        }
        if context:
            data["context"] = context

        response = await self._http.request(
            "POST",
            "/api/v1/a2a/orchestrate",
            json_data=data,
        )
        return OrchestrateResult(**response)
