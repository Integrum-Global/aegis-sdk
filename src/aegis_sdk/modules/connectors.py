"""
Connectors Module for Agentic OS SDK.

Provides connector management for databases, APIs, and messaging systems.

12 methods:
- list() - List connectors
- create() - Create connector
- get() - Get connector details
- update() - Update connector
- delete() - Delete connector
- test() - Test connector connection
- query() - Execute query on connector
- list_types() - List available connector types
- get_schema() - Get connector schema
- validate() - Validate connector config
- health() - Get connector health
- get_metadata() - Get connector metadata
"""

import builtins
from typing import Any, Literal

from pydantic import ConfigDict, Field

from .._http import encode_path_param
from .._tolerant import TolerantModel


class ConnectorConfig(TolerantModel):
    """Connector configuration."""

    model_config = ConfigDict(populate_by_name=True)

    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    url: str | None = None
    api_key: str | None = Field(None, alias="apiKey")
    extra: dict[str, Any] | None = None


class Connector(TolerantModel):
    """Connector model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    connector_type: str = Field(alias="connectorType")
    provider: str
    status: str
    last_tested_at: str | None = Field(None, alias="lastTestedAt")
    last_error: str | None = Field(None, alias="lastError")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ConnectorInstance(TolerantModel):
    """Connector instance attached to agent."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    connector_id: str = Field(alias="connectorId")
    agent_id: str = Field(alias="agentId")
    alias: str | None = None
    config_override: dict[str, Any] | None = Field(None, alias="configOverride")


class TestResult(TolerantModel):
    """Connection test result."""

    success: bool
    message: str
    latency_ms: float | None = Field(None, alias="latencyMs")


class QueryResult(TolerantModel):
    """Query execution result."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    message: str | None = None
    error: str | None = None
    query: str
    params: dict[str, Any] | None = None
    rows: list[Any] | None = None
    row_count: int | None = Field(None, alias="rowCount")
    execution_time_ms: float | None = Field(None, alias="executionTimeMs")


class ConnectorType(TolerantModel):
    """Connector type definition."""

    type: str
    providers: list[str]
    description: str


class ConnectorsModule:
    """
    Connectors module for managing data connectors.

    Supports database, API, storage, and messaging connectors.

    Examples:
        # Create PostgreSQL connector
        >>> connector = await client.connectors.create(
        ...     name="Production DB",
        ...     connector_type="database",
        ...     provider="postgresql",
        ...     config={"host": "db.example.com", "port": 5432}
        ... )

        # Test connection
        >>> result = await client.connectors.test(connector.id)
        >>> print(f"Connected: {result.success}")
    """

    def __init__(self, http_client):
        """Initialize connectors module."""
        self._http = http_client

    async def list(
        self,
        connector_type: Literal["database", "api", "storage", "messaging"] | None = None,
        provider: str | None = None,
        status: Literal["active", "inactive", "error"] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Connector]:
        """
        List connectors.

        Args:
            connector_type: Filter by type (database, api, storage, messaging)
            provider: Filter by provider (postgresql, mysql, etc.)
            status: Filter by status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List[Connector]: List of connectors
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if connector_type:
            params["connector_type"] = connector_type
        if provider:
            params["provider"] = provider
        if status:
            params["status"] = status

        response = await self._http.request(
            "GET",
            "/api/v1/connectors",
            params=params,
        )
        return [Connector(**c) for c in response.get("connectors", [])]

    async def create(
        self,
        name: str,
        connector_type: Literal["database", "api", "storage", "messaging"],
        provider: str,
        config: dict[str, Any],
    ) -> Connector:
        """
        Create a new connector.

        Args:
            name: Connector name
            connector_type: Type (database, api, storage, messaging)
            provider: Provider (postgresql, mysql, mongodb, rest, etc.)
            config: Connection configuration

        Returns:
            Connector: Created connector

        Example:
            >>> connector = await client.connectors.create(
            ...     name="Production DB",
            ...     connector_type="database",
            ...     provider="postgresql",
            ...     config={
            ...         "host": "db.example.com",
            ...         "port": 5432,
            ...         "database": "mydb",
            ...         "username": "user",
            ...         "password": "secret"
            ...     }
            ... )
        """
        response = await self._http.request(
            "POST",
            "/api/v1/connectors",
            json_data={
                "name": name,
                "connectorType": connector_type,
                "provider": provider,
                "config": config,
            },
        )
        return Connector(**response)

    async def get(self, connector_id: str) -> Connector:
        """
        Get connector details.

        Args:
            connector_id: Connector ID

        Returns:
            Connector: Connector details
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/connectors/{encode_path_param(connector_id)}",
        )
        return Connector(**response)

    async def update(
        self,
        connector_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> Connector:
        """
        Update connector.

        Args:
            connector_id: Connector ID
            name: New name (optional)
            config: New configuration (optional)
            status: New status (optional)

        Returns:
            Connector: Updated connector
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        if config:
            data["config"] = config
        if status:
            data["status"] = status

        response = await self._http.request(
            "PUT",
            f"/api/v1/connectors/{encode_path_param(connector_id)}",
            json_data=data,
        )
        return Connector(**response)

    async def delete(self, connector_id: str) -> bool:
        """
        Delete connector.

        Args:
            connector_id: Connector ID

        Returns:
            bool: True if deleted
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/connectors/{encode_path_param(connector_id)}",
        )
        return True

    async def test(self, connector_id: str) -> TestResult:
        """
        Test connector connection.

        Args:
            connector_id: Connector ID

        Returns:
            TestResult: Connection test result

        Example:
            >>> result = await client.connectors.test("conn-123")
            >>> if result.success:
            ...     print(f"Connected in {result.latency_ms}ms")
        """
        response = await self._http.request(
            "POST",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/test",
        )
        return TestResult(**response)

    async def query(
        self,
        connector_id: str,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        """
        Execute query on connector.

        Args:
            connector_id: Connector ID
            sql: SQL query or command
            params: Query parameters (optional)

        Returns:
            QueryResult: Query execution result

        Example:
            >>> result = await client.connectors.query(
            ...     "conn-123",
            ...     "SELECT COUNT(*) FROM users WHERE status = :status",
            ...     {"status": "active"}
            ... )
            >>> print(f"Count: {result.rows[0][0]}")
        """
        data: dict[str, Any] = {"query": sql}
        if params:
            data["params"] = params

        response = await self._http.request(
            "POST",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/query",
            json_data=data,
        )
        return QueryResult(**response)

    async def list_types(self) -> builtins.list[ConnectorType]:
        """
        List available connector types.

        Returns:
            List[ConnectorType]: Available connector types and providers
        """
        response = await self._http.request(
            "GET",
            "/api/v1/connectors/types",
        )
        return [ConnectorType(**t) for t in response.get("types", [])]

    async def get_schema(self, connector_id: str) -> dict[str, Any]:
        """
        Get connector schema (for databases).

        Args:
            connector_id: Connector ID

        Returns:
            Dict with schema information (tables, columns, types)
        """
        return await self._http.request(
            "GET",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/schema",
        )

    async def validate(
        self,
        connector_id: str,
        config: dict[str, Any] | None = None,
    ) -> TestResult:
        """
        Validate connector configuration.

        Args:
            connector_id: Connector ID
            config: Configuration to validate (optional, uses current if not provided)

        Returns:
            TestResult: Validation result
        """
        data = {"config": config} if config else {}
        response = await self._http.request(
            "POST",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/validate",
            json_data=data if data else None,
        )
        return TestResult(**response)

    async def health(self, connector_id: str) -> dict[str, Any]:
        """
        Get connector health status.

        Args:
            connector_id: Connector ID

        Returns:
            Dict with health status, latency, and metrics
        """
        return await self._http.request(
            "GET",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/health",
        )

    async def get_metadata(self, connector_id: str) -> dict[str, Any]:
        """
        Get connector metadata.

        Args:
            connector_id: Connector ID

        Returns:
            Dict with connector metadata
        """
        return await self._http.request(
            "GET",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/metadata",
        )

    async def attach(
        self,
        connector_id: str,
        agent_id: str,
        alias: str | None = None,
        config_override: dict[str, Any] | None = None,
    ) -> ConnectorInstance:
        """
        Attach connector to agent.

        Args:
            connector_id: Connector ID
            agent_id: Agent ID
            alias: Optional alias for this attachment
            config_override: Optional config overrides

        Returns:
            ConnectorInstance: Created instance
        """
        data: dict[str, Any] = {"agentId": agent_id}
        if alias:
            data["alias"] = alias
        if config_override:
            data["configOverride"] = config_override

        response = await self._http.request(
            "POST",
            f"/api/v1/connectors/{encode_path_param(connector_id)}/attach",
            json_data=data,
        )
        return ConnectorInstance(**response)

    async def detach(self, instance_id: str) -> bool:
        """
        Detach connector from agent.

        Args:
            instance_id: Instance ID

        Returns:
            bool: True if detached
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/connectors/instances/{encode_path_param(instance_id)}",
        )
        return True
