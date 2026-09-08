"""
Unit tests for SDK pools module.

Tests PoolsModule methods with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.modules.pools import (
    EscalationConfig,
    EscalationEvent,
    EscalationStats,
    PendingEscalation,
    Pool,
    PoolMember,
    PoolsModule,
    PoolUtilization,
    PseudoRequest,
    RequestStats,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def pools_module(mock_http):
    """Create PoolsModule with mock HTTP client."""
    return PoolsModule(mock_http)


def make_pool_response(status="active"):
    """Create pool response dict."""
    return {
        "id": "pool-123",
        "organizationId": "org-456",
        "workspaceId": "ws-789",
        "name": "Support Pool",
        "description": "Customer support team",
        "department": "Support",
        "claimTimeoutMinutes": 30,
        "poolTimeoutMinutes": 60,
        "loadBalancingStrategy": "round_robin",
        "escalationTargetType": "pool",
        "escalationTargetId": "pool-escalation",
        "status": status,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_pool_member_response():
    """Create pool member response."""
    return {
        "id": "member-123",
        "organizationId": "org-456",
        "poolId": "pool-789",
        "userId": "user-001",
        "capabilities": ["billing", "technical"],
        "poolRole": "member",
        "status": "active",
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_utilization_response():
    """Create utilization response."""
    return {
        "poolId": "pool-123",
        "poolName": "Support Pool",
        "totalTasks": 500,
        "avgWaitTimeSeconds": 45.5,
        "avgClaimTimeSeconds": 120.0,
        "escalationCount": 25,
        "escalationRate": 5.0,
    }


def make_escalation_config_response():
    """Create escalation config response."""
    return {
        "poolId": "pool-123",
        "enabled": True,
        "claimTimeoutMinutes": 15,
        "poolTimeoutMinutes": 30,
        "escalationChain": [
            {
                "targetType": "user",
                "targetId": "user-1",
                "targetName": "Lead",
                "timeoutMinutes": 15,
            },
            {
                "targetType": "team",
                "targetId": "team-1",
                "targetName": "Managers",
                "timeoutMinutes": 30,
            },
        ],
    }


def make_pending_escalation_response():
    """Create pending escalation response."""
    return {
        "taskId": "task-123",
        "taskTitle": "Urgent Support Request",
        "poolId": "pool-456",
        "poolName": "Support Pool",
        "urgency": "high",
        "priority": "critical",
        "createdAt": "2024-01-15T10:00:00Z",
        "timeoutAt": "2024-01-15T10:30:00Z",
        "currentStep": 1,
    }


def make_escalation_event_response():
    """Create escalation event response."""
    return {
        "id": "event-123",
        "taskId": "task-456",
        "eventType": "escalated",
        "fromTarget": "pool-123",
        "toTarget": "user-789",
        "reason": "Timeout reached",
        "createdAt": "2024-01-15T10:30:00Z",
        "createdBy": "system",
    }


def make_escalation_stats_response():
    """Create escalation stats response."""
    return {
        "poolId": "pool-123",
        "totalEscalations": 100,
        "pendingEscalations": 5,
        "acknowledgedEscalations": 95,
        "avgTimeToClaimSeconds": 180.0,
        "escalationRate": 5.0,
        "periodStart": "2024-01-01",
        "periodEnd": "2024-01-31",
    }


def make_pseudo_request_response(status="pending"):
    """Create pseudo request response."""
    return {
        "id": "req-123",
        "organizationId": "org-456",
        "workspaceId": "ws-789",
        "pseudoAgentId": "pa-001",
        "title": "Verify Customer Identity",
        "description": "Please verify the customer's identity",
        "priority": "high",
        "status": status,
        "assignedTo": "user-123" if status == "assigned" else None,
        "assignedAt": "2024-01-15T10:00:00Z" if status == "assigned" else None,
        "dueAt": "2024-01-15T12:00:00Z",
        "version": 1,
        "createdAt": "2024-01-15T09:00:00Z",
        "updatedAt": "2024-01-15T10:00:00Z",
    }


def make_request_stats_response():
    """Create request stats response."""
    return {
        "pending": 15,
        "assigned": 8,
        "dueWithin1Hour": 3,
        "overdue": 2,
        "myPending": 5,
        "unassigned": 7,
        "escalated": 1,
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestPoolsModuleCRUD:
    """Test pool CRUD operations."""

    async def test_list_pools(self, mock_http, pools_module):
        """list() should return pools."""
        mock_http.request = AsyncMock(return_value={"pools": [make_pool_response()]})

        result = await pools_module.list()

        assert len(result) == 1
        assert isinstance(result[0], Pool)
        assert result[0].id == "pool-123"
        assert result[0].load_balancing_strategy == "round_robin"

    async def test_list_with_filters(self, mock_http, pools_module):
        """list() should accept filters."""
        mock_http.request = AsyncMock(return_value={"pools": []})

        await pools_module.list(
            workspace_id="ws-123",
            status="active",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["workspace_id"] == "ws-123"
        assert call_args[1]["params"]["status"] == "active"

    async def test_create_pool(self, mock_http, pools_module):
        """create() should create pool."""
        mock_http.request = AsyncMock(return_value=make_pool_response())

        result = await pools_module.create(
            name="Support Pool",
            description="Customer support team",
            load_balancing_strategy="least_loaded",
        )

        assert isinstance(result, Pool)
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json_data"]["name"] == "Support Pool"
        assert call_args[1]["json_data"]["loadBalancingStrategy"] == "least_loaded"

    async def test_get_pool(self, mock_http, pools_module):
        """get() should return pool details."""
        mock_http.request = AsyncMock(return_value=make_pool_response())

        result = await pools_module.get("pool-123")

        assert isinstance(result, Pool)
        assert result.id == "pool-123"

    async def test_update_pool(self, mock_http, pools_module):
        """update() should update pool."""
        mock_http.request = AsyncMock(return_value=make_pool_response())

        result = await pools_module.update(
            pool_id="pool-123",
            name="Updated Pool",
            status="archived",
        )

        assert isinstance(result, Pool)
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "PUT"

    async def test_delete_pool(self, mock_http, pools_module):
        """delete() should delete pool."""
        mock_http.request = AsyncMock(return_value={})

        result = await pools_module.delete("pool-123")

        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestPoolsModuleMembership:
    """Test membership operations."""

    async def test_list_members(self, mock_http, pools_module):
        """list_members() should return members."""
        mock_http.request = AsyncMock(return_value={"members": [make_pool_member_response()]})

        result = await pools_module.list_members("pool-123")

        assert len(result) == 1
        assert isinstance(result[0], PoolMember)
        assert result[0].pool_role == "member"

    async def test_add_member(self, mock_http, pools_module):
        """add_member() should add member."""
        mock_http.request = AsyncMock(return_value=make_pool_member_response())

        result = await pools_module.add_member(
            pool_id="pool-123",
            user_id="user-001",
            pool_role="lead",
            capabilities=["billing"],
        )

        assert isinstance(result, PoolMember)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["userId"] == "user-001"
        assert call_args[1]["json_data"]["poolRole"] == "lead"

    async def test_remove_member(self, mock_http, pools_module):
        """remove_member() should remove member."""
        mock_http.request = AsyncMock(return_value={})

        result = await pools_module.remove_member("pool-123", "member-456")

        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestPoolsModuleUtilization:
    """Test utilization operations."""

    async def test_get_utilization(self, mock_http, pools_module):
        """get_utilization() should return metrics."""
        mock_http.request = AsyncMock(return_value=make_utilization_response())

        result = await pools_module.get_utilization("pool-123")

        assert isinstance(result, PoolUtilization)
        assert result.total_tasks == 500
        assert result.escalation_rate == 5.0

    async def test_get_utilization_with_dates(self, mock_http, pools_module):
        """get_utilization() should accept date range."""
        mock_http.request = AsyncMock(return_value=make_utilization_response())

        await pools_module.get_utilization(
            pool_id="pool-123",
            start_date="2024-01-01",
            end_date="2024-01-31",
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["startDate"] == "2024-01-01"


@pytest.mark.unit
@pytest.mark.asyncio
class TestPoolsModuleEscalation:
    """Test escalation operations."""

    async def test_get_escalation_config(self, mock_http, pools_module):
        """get_escalation_config() should return config."""
        mock_http.request = AsyncMock(return_value=make_escalation_config_response())

        result = await pools_module.get_escalation_config("pool-123")

        assert isinstance(result, EscalationConfig)
        assert result.enabled is True
        assert len(result.escalation_chain) == 2

    async def test_update_escalation_config(self, mock_http, pools_module):
        """update_escalation_config() should update config."""
        mock_http.request = AsyncMock(return_value=make_escalation_config_response())

        result = await pools_module.update_escalation_config(
            pool_id="pool-123",
            enabled=True,
            claim_timeout_minutes=15,
            escalation_chain=[{"targetType": "user", "targetId": "user-1", "timeoutMinutes": 15}],
        )

        assert isinstance(result, EscalationConfig)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["claimTimeoutMinutes"] == 15

    async def test_list_pending_escalations(self, mock_http, pools_module):
        """list_pending_escalations() should return escalations."""
        mock_http.request = AsyncMock(
            return_value={"escalations": [make_pending_escalation_response()]}
        )

        result = await pools_module.list_pending_escalations()

        assert len(result) == 1
        assert isinstance(result[0], PendingEscalation)
        assert result[0].urgency == "high"

    async def test_list_pending_escalations_with_filters(self, mock_http, pools_module):
        """list_pending_escalations() should accept filters."""
        mock_http.request = AsyncMock(return_value={"escalations": []})

        await pools_module.list_pending_escalations(
            pool_id="pool-123",
            urgency=["high", "critical"],
            priority=["critical"],
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["poolId"] == "pool-123"
        assert call_args[1]["params"]["urgency"] == "high,critical"

    async def test_escalate_task(self, mock_http, pools_module):
        """escalate_task() should escalate task."""
        mock_http.request = AsyncMock(return_value=make_pending_escalation_response())

        result = await pools_module.escalate_task(
            task_id="task-123",
            reason="Customer requested manager",
            target_type="user",
            target_id="user-manager",
        )

        assert isinstance(result, PendingEscalation)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["reason"] == "Customer requested manager"

    async def test_acknowledge_escalation(self, mock_http, pools_module):
        """acknowledge_escalation() should acknowledge."""
        mock_http.request = AsyncMock(return_value={})

        result = await pools_module.acknowledge_escalation("task-123")

        assert result is True

    async def test_get_escalation_history(self, mock_http, pools_module):
        """get_escalation_history() should return events."""
        mock_http.request = AsyncMock(return_value={"events": [make_escalation_event_response()]})

        result = await pools_module.get_escalation_history("task-123")

        assert len(result) == 1
        assert isinstance(result[0], EscalationEvent)
        assert result[0].event_type == "escalated"

    async def test_get_escalation_stats(self, mock_http, pools_module):
        """get_escalation_stats() should return stats."""
        mock_http.request = AsyncMock(return_value=make_escalation_stats_response())

        result = await pools_module.get_escalation_stats(pool_id="pool-123")

        assert isinstance(result, EscalationStats)
        assert result.total_escalations == 100
        assert result.escalation_rate == 5.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestPoolsModuleRequests:
    """Test request operations."""

    async def test_list_requests(self, mock_http, pools_module):
        """list_requests() should return requests."""
        mock_http.request = AsyncMock(return_value={"requests": [make_pseudo_request_response()]})

        result = await pools_module.list_requests()

        assert len(result) == 1
        assert isinstance(result[0], PseudoRequest)
        assert result[0].title == "Verify Customer Identity"

    async def test_list_requests_with_filters(self, mock_http, pools_module):
        """list_requests() should accept filters."""
        mock_http.request = AsyncMock(return_value={"requests": []})

        await pools_module.list_requests(
            status=["pending", "assigned"],
            assigned_to="me",
            priority=["high", "critical"],
        )

        call_args = mock_http.request.call_args
        assert call_args[1]["params"]["status"] == "pending,assigned"
        assert call_args[1]["params"]["assignedTo"] == "me"

    async def test_get_request_stats(self, mock_http, pools_module):
        """get_request_stats() should return stats."""
        mock_http.request = AsyncMock(return_value=make_request_stats_response())

        result = await pools_module.get_request_stats()

        assert isinstance(result, RequestStats)
        assert result.pending == 15
        assert result.overdue == 2

    async def test_claim_request(self, mock_http, pools_module):
        """claim_request() should claim request."""
        mock_http.request = AsyncMock(return_value=make_pseudo_request_response(status="assigned"))

        result = await pools_module.claim_request("req-123")

        assert isinstance(result, PseudoRequest)
        assert result.status == "assigned"

    async def test_claim_request_with_version(self, mock_http, pools_module):
        """claim_request() should accept version for optimistic locking."""
        mock_http.request = AsyncMock(return_value=make_pseudo_request_response(status="assigned"))

        await pools_module.claim_request("req-123", version=5)

        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["version"] == 5

    async def test_respond_request(self, mock_http, pools_module):
        """respond_request() should submit response."""
        response = make_pseudo_request_response(status="completed")
        response["response"] = {"approved": True}
        mock_http.request = AsyncMock(return_value=response)

        result = await pools_module.respond_request(
            request_id="req-123",
            response_data={"approved": True},
            comment="Identity verified",
        )

        assert isinstance(result, PseudoRequest)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["response"] == {"approved": True}
        assert call_args[1]["json_data"]["comment"] == "Identity verified"

    async def test_reassign_request(self, mock_http, pools_module):
        """reassign_request() should reassign."""
        mock_http.request = AsyncMock(return_value=make_pseudo_request_response(status="assigned"))

        result = await pools_module.reassign_request(
            request_id="req-123",
            to_user_id="user-new",
            reason="Expertise needed",
        )

        assert isinstance(result, PseudoRequest)
        call_args = mock_http.request.call_args
        assert call_args[1]["json_data"]["toUserId"] == "user-new"
