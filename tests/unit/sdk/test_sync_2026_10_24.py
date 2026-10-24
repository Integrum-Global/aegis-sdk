"""Behavioral contracts for the public client reconciliation.

Wrong execution routes, dropped response fields or hidden nulls fail these
assertions even when the transport itself returns successfully.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ConfigDict, ValidationError

from aegis_sdk import AgenticOSClient, ServiceError
from aegis_sdk._tolerant import TolerantModel, tolerant_null
from aegis_sdk.core.agents import AgentsModule
from aegis_sdk.core.pipelines import PipelinesModule
from aegis_sdk.modules.compliance import AuditVerificationResult
from aegis_sdk.modules.governance_explain import AccessExplanation
from aegis_sdk.modules.objective_workspaces import ObjectiveWorkspacesModule
from aegis_sdk.modules.work_objectives import WorkObjectivesModule
from aegis_sdk.types import ExecutionStatus


@pytest.fixture
def http():
    transport = MagicMock()
    transport.request = AsyncMock()
    return transport


def run(execution_id="run-1", pipeline_id="pipe-1", status="completed"):
    return {
        "id": execution_id,
        "pipelineId": pipeline_id,
        "status": status,
        "inputs": {"topic": "audit"},
        "outputs": {"answer": "recorded"},
        "nodeExecutions": [{"nodeId": "node-1", "status": status}],
    }


def workspace():
    return {
        "id": "ws-1", "name": "Review", "objective_id": "obj-1",
        "organization_id": "org-1", "workspace_type": "objective",
        "classification": "internal", "contains_classification": "internal",
        "environment_type": "production", "is_objective_workspace": True,
        "is_archived": False, "inherit_constraints_from_parent": True,
        "inherit_knowledge_from_parent": True,
        "created_at": "2026-10-24T00:00:00Z", "updated_at": "2026-10-24T00:00:00Z",
    }


async def test_objective_workspace_is_an_additional_client_surface():
    async with AgenticOSClient(base_url="https://example.invalid", api_key="key") as client:
        assert isinstance(client.objective_workspaces, ObjectiveWorkspacesModule)
        # Client wiring must add the surface without losing standalone features.
        assert client.mcp is not None
        assert client.artifacts is not None
        assert client.presentation is not None


async def test_workspace_create_uses_collection_slash_and_cannot_supply_actor(http):
    http.request.return_value = workspace()
    result = await ObjectiveWorkspacesModule(http).create("obj-1", name="Review")
    http.request.assert_awaited_once_with(
        "POST", "/api/v1/objective-workspaces/",
        json_data={"objective_id": "obj-1", "name": "Review"},
    )
    assert result.id == "ws-1"
    assert result.objective_id == "obj-1"
    with pytest.raises(TypeError):
        await ObjectiveWorkspacesModule(http).create("obj-1", user_id="another-user")


async def test_workspace_objective_identifier_is_encoded(http):
    http.request.return_value = workspace()
    result = await ObjectiveWorkspacesModule(http).get_by_objective("objective/other")
    assert result.id == "ws-1"
    assert http.request.call_args.args[1].endswith("/by-objective/objective%2Fother")


async def test_pipeline_default_reads_camel_case_run_from_public_route(http):
    http.request.side_effect = [{"executionId": "run-1"}, run()]
    result = await PipelinesModule(http).execute("pipe-1")
    assert result.status == ExecutionStatus.COMPLETED
    assert result.outputs == {"answer": "recorded"}
    assert result.node_results[0]["node_id"] == "node-1"
    assert http.request.await_args_list[1].args == ("GET", "/api/v1/executions/run-1")


async def test_pipeline_no_read_reports_unknown_without_fabricated_status(http):
    http.request.return_value = {"executionId": "run-1"}
    result = await PipelinesModule(http).execute("pipe-1", wait=False)
    assert result.status == ExecutionStatus.UNKNOWN
    assert result.id == "run-1"
    assert http.request.await_count == 1


@pytest.mark.parametrize("payload", [{}, [], {"executionId": ""}])
async def test_start_without_execution_id_is_an_explicit_error(http, payload):
    http.request.return_value = payload
    with pytest.raises(ServiceError, match="executionId"):
        await PipelinesModule(http).execute("pipe-1")


@pytest.mark.parametrize("payload", [run(pipeline_id="another"), run(execution_id="another")])
async def test_get_refuses_a_mismatched_run_pair(http, payload):
    http.request.return_value = payload
    with pytest.raises(ValueError, match="pipeline/id"):
        await PipelinesModule(http).get_execution("pipe-1", "run-1")


async def test_cancel_verifies_pair_before_stop(http):
    http.request.side_effect = [run(status="running"), None]
    await PipelinesModule(http).cancel_execution("pipe-1", "run-1")
    assert [c.args for c in http.request.await_args_list] == [
        ("GET", "/api/v1/executions/run-1"),
        ("POST", "/api/v1/executions/run-1/stop"),
    ]


async def test_cancel_never_stops_a_mismatched_pipeline(http):
    http.request.return_value = run(pipeline_id="another")
    with pytest.raises(ValueError):
        await PipelinesModule(http).cancel_execution("pipe-1", "run-1")
    assert http.request.await_count == 1


async def test_history_retains_total_and_reports_unfiltered_next_page(http):
    http.request.return_value = {"executions": [run()], "total": 3, "page": 1, "page_size": 1}
    result = await PipelinesModule(http).list_executions("pipe-1", page_size=1)
    assert [item.id for item in result.items] == ["run-1"]
    assert result.total == 3
    assert result.has_next is True
    assert http.request.call_args.args[1] == "/api/v1/executions/history/pipe-1"


async def test_status_filter_scans_all_pages_before_paging_the_matches(http):
    http.request.side_effect = [
        {"executions": [run(status="failed")], "total": 101, "page": 1},
        {"executions": [run("run-2"), run("run-3")], "total": 101, "page": 2},
    ]
    result = await PipelinesModule(http).list_executions(
        "pipe-1", status="completed", page=2, page_size=1,
    )
    assert result.total == 2
    assert [item.id for item in result.items] == ["run-3"]
    assert result.has_next is False
    assert http.request.await_count == 2
    assert all("status" not in c.kwargs["params"] for c in http.request.await_args_list)


async def test_unknown_get_state_is_not_reported_pending(http):
    payload = run()
    del payload["status"]
    http.request.return_value = payload
    result = await PipelinesModule(http).get_execution("pipe-1", "run-1")
    assert result.status == ExecutionStatus.UNKNOWN


async def test_deprecated_session_filter_warns_but_preserves_wire_compatibility(http):
    http.request.return_value = {"records": [], "total": 0, "page": 1, "page_size": 50}
    with pytest.warns(DeprecationWarning, match="HAS NO EFFECT"):
        await WorkObjectivesModule(http).list_sessions(workspace_id="ws-1")
    assert http.request.call_args.kwargs["params"]["workspace_id"] == "ws-1"


def test_marked_object_null_is_preserved():
    class Reply(TolerantModel):
        payload: object = tolerant_null(default_factory=dict)
    assert Reply(payload=None).payload is None


def test_python_name_without_name_population_is_not_silently_dropped():
    class Reply(TolerantModel):
        model_config = ConfigDict(extra="forbid", populate_by_name=False)
        allowed: bool = tolerant_null(True, alias="wire_allowed")
    with pytest.raises(ValidationError):
        Reply.model_validate({"allowed": None})
    # A declared input alias still receives its explicitly opted-in default.
    assert Reply.model_validate({"wire_allowed": None}).allowed is True


def test_governance_explanation_retains_unchecked_gates():
    explanation = AccessExplanation(allowed=True, gates_not_evaluated=["approval"])
    assert explanation.gates_not_evaluated == ["approval"]


def test_hash_only_audit_verdict_is_not_lost_behind_valid_boolean():
    result = AuditVerificationResult(
        valid=True, entriesChecked=2, status="hash-consistent, not signature-verified",
        verificationRan=True, signaturesVerified=0,
    )
    assert result.valid is True
    assert result.status == "hash-consistent, not signature-verified"
    assert result.verification_ran is True
    assert result.signatures_verified == 0


@pytest.mark.parametrize("response", [{"error": {"message": "refused"}}, {"error": "refused"}, {}])
async def test_successful_http_reply_without_an_agent_answer_reports_failure(http, response):
    http.request.return_value = response
    result = await AgentsModule(http).execute("agent-1", "summarize")
    assert result.status == ExecutionStatus.FAILED
    assert result.error
