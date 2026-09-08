"""
Tier 1: Unit Tests for SDK Package Structure and Imports.

Tests cover:
- Version accessibility
- Main exports available
- All exception classes importable
- All model classes importable
- All enum classes importable

Total: 12 tests
"""

import pytest


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSDKVersion:
    """Test SDK version accessibility."""

    def test_version_accessible(self):
        """__version__ should be accessible from main package."""
        from aegis_sdk import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert __version__ == "1.0.0"

    def test_version_info_accessible(self):
        """__version_info__ should be a tuple of integers."""
        from aegis_sdk import __version_info__

        assert __version_info__ is not None
        assert isinstance(__version_info__, tuple)
        assert all(isinstance(v, int) for v in __version_info__)
        assert __version_info__ == (1, 0, 0)


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSDKClientImports:
    """Test main client imports."""

    def test_agentic_os_client_importable(self):
        """AgenticOSClient should be importable from main package."""
        from aegis_sdk import AgenticOSClient

        assert AgenticOSClient is not None
        assert callable(AgenticOSClient)

    def test_client_alias_importable(self):
        """Client alias should be importable."""
        from aegis_sdk import Client

        assert Client is not None
        assert callable(Client)

    def test_config_classes_importable(self):
        """Configuration classes should be importable."""
        from aegis_sdk import ClientConfig, OAuthConfig

        assert ClientConfig is not None
        assert OAuthConfig is not None


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSDKExceptionImports:
    """Test exception class imports."""

    def test_base_exception_importable(self):
        """AgenticOSError base exception should be importable."""
        from aegis_sdk import AgenticOSError

        assert AgenticOSError is not None
        assert issubclass(AgenticOSError, Exception)

    def test_all_exceptions_importable(self):
        """All exception classes should be importable."""
        from aegis_sdk import (
            AgenticOSError,
            AuthenticationError,
            AuthorizationError,
            ConfigurationError,
            ConnectionError,
            GovernanceViolationError,
            NotFoundError,
            RateLimitError,
            ServiceError,
            ServiceUnavailableError,
            TimeoutError,
            TrustViolationError,
            UnsupportedOperationError,
            ValidationError,
        )

        # All should be subclasses of AgenticOSError
        assert issubclass(AuthenticationError, AgenticOSError)
        assert issubclass(AuthorizationError, AgenticOSError)
        assert issubclass(NotFoundError, AgenticOSError)
        assert issubclass(ValidationError, AgenticOSError)
        assert issubclass(RateLimitError, AgenticOSError)
        assert issubclass(ServiceError, AgenticOSError)
        assert issubclass(TrustViolationError, AgenticOSError)
        assert issubclass(GovernanceViolationError, AgenticOSError)
        assert issubclass(ServiceUnavailableError, AgenticOSError)
        assert issubclass(ConfigurationError, AgenticOSError)
        assert issubclass(ConnectionError, AgenticOSError)
        assert issubclass(TimeoutError, AgenticOSError)
        assert issubclass(UnsupportedOperationError, AgenticOSError)

    def test_exception_aliases_importable(self):
        """Exception aliases should be importable."""
        from aegis_sdk import NetworkError, RequestTimeout

        assert NetworkError is not None
        assert RequestTimeout is not None


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSDKEnumImports:
    """Test enum class imports."""

    def test_all_enums_importable(self):
        """All enum classes should be importable."""
        from aegis_sdk import (
            AgentStatus,
            AgentSubtype,
            AgentType,
            DelegationStatus,
            ExecutionStatus,
            ObjectiveStatus,
            PipelinePattern,
            RequestStatus,
            SessionStatus,
            TrustChainStatus,
            TrustPosture,
            UnitType,
        )

        # Verify enum values (agent_type domain — matches server
        # CreateAgentRequest.agent_type ^(chat|task|pipeline|custom)$)
        assert AgentType.CHAT == "chat"
        assert AgentType.TASK == "task"
        assert AgentType.PIPELINE == "pipeline"
        assert AgentType.CUSTOM == "custom"

        assert AgentStatus.DRAFT == "draft"
        assert AgentStatus.ACTIVE == "active"
        assert AgentStatus.ARCHIVED == "archived"

        assert AgentSubtype.SPECIALIST == "specialist"
        assert AgentSubtype.MANAGER == "manager"
        assert AgentSubtype.ESA == "esa"
        assert AgentSubtype.PSEUDO == "pseudo"
        assert AgentSubtype.GOVERNANCE == "governance"

        assert UnitType.ATOMIC == "atomic"
        assert UnitType.COMPOSITE == "composite"

        assert PipelinePattern.SEQUENTIAL == "sequential"
        assert PipelinePattern.PARALLEL == "parallel"

        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.COMPLETED == "completed"

        # Execution enums
        assert ObjectiveStatus.PENDING == "pending"
        assert RequestStatus.CLAIMED == "claimed"
        assert SessionStatus.ACTIVE == "active"

        # Trust enums
        assert TrustPosture.SHARED_PLANNING == "shared_planning"
        assert TrustChainStatus.ACTIVE == "active"
        assert DelegationStatus.ACTIVE == "active"


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestSDKModelImports:
    """Test model class imports."""

    def test_agent_models_importable(self):
        """Agent models should be importable."""
        from aegis_sdk import Agent, AgentCreate, AgentExecution, AgentUpdate

        assert Agent is not None
        assert AgentCreate is not None
        assert AgentUpdate is not None
        assert AgentExecution is not None

    def test_skill_models_importable(self):
        """Skill models should be importable."""
        from aegis_sdk import Skill, SkillCreate, SkillUpdate

        assert Skill is not None
        assert SkillCreate is not None
        assert SkillUpdate is not None

    def test_pipeline_models_importable(self):
        """Pipeline models should be importable."""
        from aegis_sdk import (
            Pipeline,
            PipelineConnection,
            PipelineCreate,
            PipelineExecution,
            PipelineNode,
            PipelineUpdate,
        )

        assert Pipeline is not None
        assert PipelineCreate is not None
        assert PipelineUpdate is not None
        assert PipelineNode is not None
        assert PipelineConnection is not None
        assert PipelineExecution is not None

    def test_auth_models_importable(self):
        """Auth models should be importable."""
        from aegis_sdk import APIKey, APIKeyCreate, AuthToken, User

        assert AuthToken is not None
        assert APIKey is not None
        assert APIKeyCreate is not None
        assert User is not None

    def test_common_models_importable(self):
        """Common models should be importable."""
        from aegis_sdk import PaginatedResponse

        assert PaginatedResponse is not None

    def test_execution_models_importable(self):
        """Execution models should be importable."""
        from aegis_sdk import (
            Finding,
            Objective,
            ObjectiveCreate,
            ObjectiveUpdate,
            Request,
            RequestClaim,
            RequestComplete,
            RequestEscalate,
            Session,
            SessionArtifact,
            SessionContext,
            SessionMessage,
            Subagent,
        )

        assert Objective is not None
        assert ObjectiveCreate is not None
        assert ObjectiveUpdate is not None
        assert Request is not None
        assert RequestClaim is not None
        assert RequestComplete is not None
        assert RequestEscalate is not None
        assert Finding is not None
        assert Session is not None
        assert SessionMessage is not None
        assert SessionArtifact is not None
        assert SessionContext is not None
        assert Subagent is not None

    def test_trust_models_importable(self):
        """Trust models should be importable."""
        from aegis_sdk import (
            AffectedTrustAgent,
            AgentTrustContext,
            CascadeRevocationResult,
            DelegationPath,
            EstablishedTrustChain,
            PostureMetrics,
            PostureOverride,
            PostureProgressionRequest,
            RevocationImpact,
            StreamEvent,
            TrustAuditEntry,
            TrustAuditQuery,
            TrustChain,
            TrustChainEstablish,
            TrustDelegation,
            TrustDelegationCreate,
            TrustDelegationRecord,
            TrustGenesisRecord,
            TrustHumanOriginInfo,
            TrustPostureInfo,
            TrustVerification,
            TrustVerificationResult,
        )

        assert TrustChain is not None
        assert TrustChainEstablish is not None
        assert TrustVerification is not None
        assert TrustVerificationResult is not None
        assert DelegationPath is not None
        assert AgentTrustContext is not None
        assert TrustDelegation is not None
        assert TrustDelegationCreate is not None
        assert RevocationImpact is not None
        assert AffectedTrustAgent is not None
        assert CascadeRevocationResult is not None
        assert EstablishedTrustChain is not None
        assert TrustGenesisRecord is not None
        assert TrustHumanOriginInfo is not None
        assert TrustDelegationRecord is not None
        assert TrustPostureInfo is not None
        assert PostureProgressionRequest is not None
        assert PostureOverride is not None
        assert PostureMetrics is not None
        assert TrustAuditEntry is not None
        assert TrustAuditQuery is not None
        assert StreamEvent is not None
