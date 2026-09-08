"""
Unit tests for SDK connectors module.

Tests ConnectorsModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.modules.connectors import (
    Connector,
    ConnectorInstance,
    ConnectorsModule,
    ConnectorType,
    QueryResult,
)
from aegis_sdk.modules.connectors import (
    TestResult as ConnectorTestResult,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def connectors_module(mock_http):
    """Create ConnectorsModule with mock HTTP client."""
    return ConnectorsModule(mock_http)


def make_connector_response(
    connector_type="database",
    provider="postgresql",
    status="active",
):
    """Create connector response dict."""
    return {
        "id": "conn-123",
        "organizationId": "org-456",
        "name": "Production DB",
        "connectorType": connector_type,
        "provider": provider,
        "status": status,
        "lastTestedAt": "2024-01-15T10:00:00Z",
        "lastError": None,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_test_result(success=True):
    """Create test result response."""
    return {
        "success": success,
        "message": "Connection successful" if success else "Connection failed",
        "latencyMs": 25.5 if success else None,
    }


def make_query_result():
    """Create query result response."""
    return {
        "success": True,
        "query": "SELECT COUNT(*) FROM users",
        "rows": [[150]],
        "rowCount": 1,
        "executionTimeMs": 12.5,
    }


def make_connector_type():
    """Create connector type response."""
    return {
        "type": "database",
        "providers": ["postgresql", "mysql", "mongodb"],
        "description": "Database connectors",
    }


def make_connector_instance():
    """Create connector instance response."""
    return {
        "id": "inst-123",
        "connectorId": "conn-456",
        "agentId": "agent-789",
        "alias": "prod-db",
        "configOverride": {"timeout": 30},
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleCRUD:
    """Test connector CRUD operations."""

    async def test_list_connectors(self, mock_http, connectors_module):
        """list() should return connectors."""
        mock_http.request = AsyncMock(return_value={"connectors": [make_connector_response()]})

        result = await connectors_module.list()

        assert len(result) == 1
        assert isinstance(result[0], Connector)
        assert result[0].id == "conn-123"
        assert result[0].connector_type == "database"
        mock_http.request.assert_called_once()

    async def test_list_with_filters(self, mock_http, connectors_module):
        """list() should accept filters."""
        mock_http.request = AsyncMock(return_value={"connectors": []})

        await connectors_module.list(
            connector_type="database",
            provider="postgresql",
            status="active",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["connector_type"] == "database"
        assert call_args[1]["params"]["provider"] == "postgresql"
        assert call_args[1]["params"]["status"] == "active"

    async def test_create_connector(self, mock_http, connectors_module):
        """create() should create connector."""
        mock_http.request = AsyncMock(return_value=make_connector_response())

        result = await connectors_module.create(
            name="Production DB",
            connector_type="database",
            provider="postgresql",
            config={"host": "db.example.com", "port": 5432},
        )

        assert isinstance(result, Connector)
        assert result.name == "Production DB"
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json_data"]["name"] == "Production DB"
        assert call_args[1]["json_data"]["connectorType"] == "database"
        assert call_args[1]["json_data"]["provider"] == "postgresql"

    async def test_get_connector(self, mock_http, connectors_module):
        """get() should return connector details."""
        mock_http.request = AsyncMock(return_value=make_connector_response())

        result = await connectors_module.get("conn-123")

        assert isinstance(result, Connector)
        assert result.id == "conn-123"
        mock_http.request.assert_called_once_with(
            "GET",
            "/api/v1/connectors/conn-123",
        )

    async def test_update_connector(self, mock_http, connectors_module):
        """update() should update connector."""
        mock_http.request = AsyncMock(return_value=make_connector_response())

        result = await connectors_module.update(
            connector_id="conn-123",
            name="New Name",
            status="inactive",
        )

        assert isinstance(result, Connector)
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "PUT"
        assert call_args[1]["json_data"]["name"] == "New Name"
        assert call_args[1]["json_data"]["status"] == "inactive"

    async def test_delete_connector(self, mock_http, connectors_module):
        """delete() should delete connector."""
        mock_http.request = AsyncMock(return_value={})

        result = await connectors_module.delete("conn-123")

        assert result is True
        mock_http.request.assert_called_once_with(
            "DELETE",
            "/api/v1/connectors/conn-123",
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleTest:
    """Test connector testing operations."""

    async def test_test_connector_success(self, mock_http, connectors_module):
        """test() should return success result."""
        mock_http.request = AsyncMock(return_value=make_test_result(success=True))

        result = await connectors_module.test("conn-123")

        assert isinstance(result, ConnectorTestResult)
        assert result.success is True
        assert result.latency_ms == 25.5
        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/connectors/conn-123/test",
        )

    async def test_test_connector_failure(self, mock_http, connectors_module):
        """test() should return failure result."""
        mock_http.request = AsyncMock(return_value=make_test_result(success=False))

        result = await connectors_module.test("conn-123")

        assert result.success is False
        assert "failed" in result.message


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleQuery:
    """Test query execution."""

    async def test_query_success(self, mock_http, connectors_module):
        """query() should execute and return results."""
        mock_http.request = AsyncMock(return_value=make_query_result())

        result = await connectors_module.query(
            connector_id="conn-123",
            sql="SELECT COUNT(*) FROM users",
        )

        assert isinstance(result, QueryResult)
        assert result.success is True
        assert result.rows == [[150]]
        assert result.row_count == 1

    async def test_query_with_params(self, mock_http, connectors_module):
        """query() should pass parameters."""
        mock_http.request = AsyncMock(return_value=make_query_result())

        await connectors_module.query(
            connector_id="conn-123",
            sql="SELECT * FROM users WHERE id = :id",
            params={"id": 123},
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["params"] == {"id": 123}


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleTypes:
    """Test connector type operations."""

    async def test_list_types(self, mock_http, connectors_module):
        """list_types() should return available types."""
        mock_http.request = AsyncMock(return_value={"types": [make_connector_type()]})

        result = await connectors_module.list_types()

        assert len(result) == 1
        assert isinstance(result[0], ConnectorType)
        assert result[0].type == "database"
        assert "postgresql" in result[0].providers


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleSchema:
    """Test schema operations."""

    async def test_get_schema(self, mock_http, connectors_module):
        """get_schema() should return schema info."""
        mock_http.request = AsyncMock(
            return_value={"tables": [{"name": "users", "columns": ["id", "name", "email"]}]}
        )

        result = await connectors_module.get_schema("conn-123")

        assert "tables" in result
        assert len(result["tables"]) == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleValidation:
    """Test validation operations."""

    async def test_validate_connector(self, mock_http, connectors_module):
        """validate() should validate configuration."""
        mock_http.request = AsyncMock(return_value=make_test_result(success=True))

        result = await connectors_module.validate(
            connector_id="conn-123",
            config={"host": "new-host.example.com"},
        )

        assert isinstance(result, ConnectorTestResult)
        assert result.success is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleHealth:
    """Test health operations."""

    async def test_health(self, mock_http, connectors_module):
        """health() should return health status."""
        mock_http.request = AsyncMock(
            return_value={
                "status": "healthy",
                "latency_ms": 15.0,
                "uptime_percentage": 99.9,
            }
        )

        result = await connectors_module.health("conn-123")

        assert result["status"] == "healthy"


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectorsModuleAttach:
    """Test attach/detach operations."""

    async def test_attach_connector(self, mock_http, connectors_module):
        """attach() should attach connector to agent."""
        mock_http.request = AsyncMock(return_value=make_connector_instance())

        result = await connectors_module.attach(
            connector_id="conn-456",
            agent_id="agent-789",
            alias="prod-db",
        )

        assert isinstance(result, ConnectorInstance)
        assert result.alias == "prod-db"
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["agentId"] == "agent-789"

    async def test_detach_connector(self, mock_http, connectors_module):
        """detach() should detach connector."""
        mock_http.request = AsyncMock(return_value={})

        result = await connectors_module.detach("inst-123")

        assert result is True
