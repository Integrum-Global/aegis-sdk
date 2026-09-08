"""
Tier 1: Unit Tests for SDK Execution Types (Pydantic Models).

Tests cover:
- Objective models (Objective, ObjectiveCreate, ObjectiveUpdate)
- Request models (Request, RequestClaim, RequestComplete, RequestEscalate, Finding)
- Session models (Session, SessionMessage, SessionArtifact, SessionContext, Subagent)
- Status enums (ObjectiveStatus, RequestStatus, SessionStatus)

Total: 25 tests
"""

from datetime import UTC, datetime

import pytest

from aegis_sdk.types import (
    Finding,
    # Objective models
    Objective,
    ObjectiveCreate,
    # Enums
    ObjectiveStatus,
    ObjectiveUpdate,
    # Request models
    Request,
    RequestClaim,
    RequestComplete,
    RequestEscalate,
    RequestStatus,
    # Session models
    Session,
    SessionArtifact,
    SessionContext,
    SessionMessage,
    SessionStatus,
    Subagent,
)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestObjectiveStatusEnum:
    """Test ObjectiveStatus enum."""

    def test_all_objective_statuses(self):
        """ObjectiveStatus should have all expected values."""
        assert ObjectiveStatus.DRAFT == "draft"
        assert ObjectiveStatus.PENDING == "pending"
        assert ObjectiveStatus.IN_PROGRESS == "in_progress"
        assert ObjectiveStatus.COMPLETED == "completed"
        assert ObjectiveStatus.CANCELLED == "cancelled"
        assert ObjectiveStatus.FAILED == "failed"

    def test_objective_status_from_string(self):
        """ObjectiveStatus should be creatable from string."""
        status = ObjectiveStatus("pending")
        assert status == ObjectiveStatus.PENDING


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestRequestStatusEnum:
    """Test RequestStatus enum."""

    def test_all_request_statuses(self):
        """RequestStatus should have all expected values."""
        assert RequestStatus.PENDING == "pending"
        assert RequestStatus.CLAIMED == "claimed"
        assert RequestStatus.IN_PROGRESS == "in_progress"
        assert RequestStatus.COMPLETED == "completed"
        assert RequestStatus.ESCALATED == "escalated"
        assert RequestStatus.CANCELLED == "cancelled"

    def test_request_status_from_string(self):
        """RequestStatus should be creatable from string."""
        status = RequestStatus("claimed")
        assert status == RequestStatus.CLAIMED


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionStatusEnum:
    """Test SessionStatus enum."""

    def test_all_session_statuses(self):
        """SessionStatus should have all expected values."""
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.PAUSED == "paused"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.TERMINATED == "terminated"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestObjectiveModels:
    """Test Objective-related Pydantic models."""

    def test_objective_create_minimal(self):
        """ObjectiveCreate should accept minimal required fields."""
        obj = ObjectiveCreate(
            title="Research Task",
            description="Research quantum computing",
            agent_id="agent_123",
        )
        assert obj.title == "Research Task"
        assert obj.agent_id == "agent_123"
        assert obj.priority == 0  # default
        assert obj.metadata == {}  # default

    def test_objective_create_all_fields(self):
        """ObjectiveCreate should accept all optional fields."""
        obj = ObjectiveCreate(
            title="Priority Task",
            description="Critical analysis needed",
            agent_id="agent_456",
            priority=10,
            workspace_id="ws_789",
            metadata={"urgent": True, "category": "research"},
        )
        assert obj.title == "Priority Task"
        assert obj.priority == 10
        assert obj.workspace_id == "ws_789"
        assert obj.metadata["urgent"] is True

    def test_objective_update_partial(self):
        """ObjectiveUpdate should allow partial updates."""
        update = ObjectiveUpdate(title="Updated Title")
        assert update.title == "Updated Title"
        assert update.description is None
        assert update.priority is None

        data = update.model_dump(exclude_none=True)
        assert data == {"title": "Updated Title"}

    def test_objective_full_model(self):
        """Objective model should include all fields."""
        now = datetime.now(UTC)
        obj = Objective(
            id="obj_123",
            title="Full Objective",
            description="Complete objective description",
            agent_id="agent_789",
            status=ObjectiveStatus.IN_PROGRESS,
            priority=5,
            organization_id="org_abc",
            workspace_id="ws_abc",
            created_by="user_123",
            assigned_to="agent_789",
            metadata={"tags": ["important"]},
            created_at=now,
            updated_at=now,
        )
        assert obj.id == "obj_123"
        assert obj.status == ObjectiveStatus.IN_PROGRESS
        assert obj.organization_id == "org_abc"
        assert obj.created_by == "user_123"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestRequestModels:
    """Test Request-related Pydantic models."""

    def test_request_full_model(self):
        """Request model should include all fields."""
        now = datetime.now(UTC)
        req = Request(
            id="req_123",
            objective_id="obj_456",
            title="Analysis Request",
            description="Analyze data",
            request_type="action",
            status=RequestStatus.CLAIMED,
            claimed_by="agent_789",
            claimed_at=now,
            priority=5,
            metadata={},
            created_at=now,
            updated_at=now,
        )
        assert req.id == "req_123"
        assert req.status == RequestStatus.CLAIMED
        assert req.claimed_by == "agent_789"
        assert req.request_type == "action"

    def test_request_claim_model(self):
        """RequestClaim model should validate correctly."""
        claim = RequestClaim(agent_id="agent_123")
        assert claim.agent_id == "agent_123"

    def test_request_complete_minimal(self):
        """RequestComplete should accept minimal fields."""
        complete = RequestComplete(result={"status": "success"})
        assert complete.result == {"status": "success"}
        assert complete.artifacts == []

    def test_request_complete_with_artifacts(self):
        """RequestComplete should accept artifacts."""
        complete = RequestComplete(
            result={"data": "analysis result"},
            artifacts=["artifact_1", "artifact_2"],
        )
        assert len(complete.artifacts) == 2
        assert "artifact_1" in complete.artifacts

    def test_request_escalate_model(self):
        """RequestEscalate should accept reason and optional target."""
        escalate = RequestEscalate(
            reason="Budget exceeds approval limit",
            target_id="user_manager",
        )
        assert escalate.reason == "Budget exceeds approval limit"
        assert escalate.target_id == "user_manager"

    def test_finding_model(self):
        """Finding model should validate correctly."""
        now = datetime.now(UTC)
        finding = Finding(
            id="finding_123",
            request_id="req_456",
            finding_type="warning",
            content="Data quality issue detected",
            metadata={"severity": "medium"},
            created_at=now,
        )
        assert finding.id == "finding_123"
        assert finding.finding_type == "warning"
        assert finding.metadata["severity"] == "medium"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSessionModels:
    """Test Session-related Pydantic models."""

    def test_session_full_model(self):
        """Session model should include all fields."""
        now = datetime.now(UTC)
        session = Session(
            id="ses_123",
            request_id="req_456",
            agent_id="agent_789",
            status=SessionStatus.ACTIVE,
            start_time=now,
            message_count=10,
            artifact_count=2,
            metadata={"context": "research"},
        )
        assert session.id == "ses_123"
        assert session.status == SessionStatus.ACTIVE
        assert session.message_count == 10
        assert session.end_time is None

    def test_session_completed_with_end_time(self):
        """Completed session should have end_time."""
        now = datetime.now(UTC)
        session = Session(
            id="ses_123",
            request_id="req_456",
            agent_id="agent_789",
            status=SessionStatus.COMPLETED,
            start_time=now,
            end_time=now,
            message_count=50,
            artifact_count=5,
        )
        assert session.status == SessionStatus.COMPLETED
        assert session.end_time is not None

    def test_session_message_model(self):
        """SessionMessage model should validate correctly."""
        now = datetime.now(UTC)
        message = SessionMessage(
            id="msg_123",
            session_id="ses_456",
            role="assistant",
            content="I've completed the analysis.",
            metadata={"step": "final"},
            created_at=now,
        )
        assert message.id == "msg_123"
        assert message.role == "assistant"
        assert message.content == "I've completed the analysis."

    def test_session_artifact_model(self):
        """SessionArtifact model should validate correctly."""
        now = datetime.now(UTC)
        artifact = SessionArtifact(
            id="art_123",
            session_id="ses_456",
            artifact_type="json",
            name="analysis_results",
            data={"findings": [1, 2, 3], "score": 95},
            created_at=now,
        )
        assert artifact.id == "art_123"
        assert artifact.artifact_type == "json"
        assert artifact.data["score"] == 95

    def test_session_context_model(self):
        """SessionContext model should validate correctly."""
        context = SessionContext(
            session_id="ses_123",
            agent_context={"objective": "research", "step": 3},
            memory_context={"previous_findings": []},
            active_tools=["search", "analyze", "summarize"],
        )
        assert context.session_id == "ses_123"
        assert len(context.active_tools) == 3

    def test_subagent_model(self):
        """Subagent model should validate correctly."""
        now = datetime.now(UTC)
        subagent = Subagent(
            id="sub_123",
            session_id="ses_456",
            subagent_id="agent_researcher",
            task="Research quantum computing advances",
            status="running",
            created_at=now,
        )
        assert subagent.id == "sub_123"
        assert subagent.status == "running"
        assert subagent.completed_at is None

    def test_subagent_completed(self):
        """Completed subagent should have completed_at."""
        now = datetime.now(UTC)
        subagent = Subagent(
            id="sub_123",
            session_id="ses_456",
            subagent_id="agent_researcher",
            task="Research task",
            status="completed",
            created_at=now,
            completed_at=now,
        )
        assert subagent.status == "completed"
        assert subagent.completed_at is not None
