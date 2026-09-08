"""
Unit tests for the objective, request, clarification and work-unit SDK
surface added on top of the existing execution and work-objectives modules.

As in the trust surface tests, the METHOD and PATH assertions carry most of
the weight: a client method addressing the wrong route type-checks perfectly
and fails only against a live server.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aegis_sdk._http import HTTPClient
from aegis_sdk.execution.objectives import ObjectivesModule
from aegis_sdk.execution.requests import RequestsModule
from aegis_sdk.modules.pseudo_agents import PseudoAgentsModule
from aegis_sdk.modules.work_objectives import WorkObjectivesModule


@pytest.fixture
def http():
    """Mock HTTP client whose request() returns whatever the test sets."""
    client = MagicMock()
    client.request = AsyncMock(return_value={})
    return client


def called(http):
    """(method, path) of the single request the module issued."""
    args = http.request.await_args
    return args.args[0], args.args[1]


# ---------------------------------------------------------------------------
# Objective lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_path"),
    [
        ("pause", "/api/v1/objectives/obj-1/pause"),
        ("resume", "/api/v1/objectives/obj-1/resume"),
        ("trigger_execution", "/api/v1/objectives/obj-1/trigger-execution"),
        ("check_completion", "/api/v1/objectives/obj-1/check-completion"),
    ],
)
async def test_objective_lifecycle_routes(http, method_name, expected_path):
    http.request.return_value = {"success": True}
    await getattr(ObjectivesModule(http), method_name)("obj-1")
    assert called(http) == ("POST", expected_path)


@pytest.mark.asyncio
async def test_trigger_execution_reports_already_decomposed_rather_than_raising(http):
    http.request.return_value = {
        "status": "already_decomposed",
        "message": "Objective already has tasks",
        "task_count": 4,
    }
    result = await ObjectivesModule(http).trigger_execution("obj-1")
    # Repeating the call is safe and reports which branch it took.
    assert result["status"] == "already_decomposed"
    assert result["task_count"] == 4


@pytest.mark.asyncio
async def test_implement_defaults_confirmed_false(http):
    http.request.return_value = {"success": True}
    await ObjectivesModule(http).implement("obj-1")
    body = http.request.await_args.kwargs["json_data"]
    # A client must not confirm a human review on the caller's behalf.
    assert body == {"confirmed": False}


@pytest.mark.asyncio
async def test_retry_node_addresses_both_path_segments(http):
    http.request.return_value = {"success": True}
    await ObjectivesModule(http).retry_node("obj-1", "node-9")
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/nodes/node-9/retry")


@pytest.mark.asyncio
async def test_completion_status_is_a_read_and_check_completion_is_a_write(http):
    http.request.return_value = {"success": True, "ready": False, "blockers": ["req-1"]}
    await ObjectivesModule(http).get_completion_status("obj-1")
    assert called(http) == ("GET", "/api/v1/objectives/obj-1/completion-status")

    http.request.reset_mock()
    http.request.return_value = {"objective_id": "obj-1", "action": "already_complete"}
    await ObjectivesModule(http).check_completion("obj-1")
    assert called(http)[0] == "POST"


@pytest.mark.asyncio
async def test_complete_can_report_failure_in_a_success_response(http):
    http.request.return_value = {
        "success": False,
        "objective_id": "obj-1",
        "new_status": "executing",
        "execution_summary": None,
        "final_deliverable_ids": [],
        "notification_ids": [],
        "audit_anchor_id": None,
        "error_message": "Outstanding requests remain",
    }
    result = await ObjectivesModule(http).complete("obj-1")
    assert result["success"] is False
    assert result["error_message"]


@pytest.mark.asyncio
async def test_participants_and_templates_unwrap_their_envelopes(http):
    http.request.return_value = {
        "success": True,
        "participants": [{"id": "u1", "type": "owner", "name": "Jo", "role": "submitter"}],
    }
    participants = await ObjectivesModule(http).get_participants("obj-1")
    assert participants == [
        {"id": "u1", "type": "owner", "name": "Jo", "role": "submitter"}
    ]

    http.request.reset_mock()
    http.request.return_value = {"records": [{"id": "tpl-1"}]}
    templates = await ObjectivesModule(http).get_templates(category="ops")
    assert called(http) == ("GET", "/api/v1/objectives/templates")
    assert http.request.await_args.kwargs["params"] == {"category": "ops"}
    assert templates == [{"id": "tpl-1"}]


@pytest.mark.asyncio
async def test_set_status_and_create_tasks_address_the_admin_routes(http):
    http.request.return_value = {"success": True}
    await ObjectivesModule(http).set_status("obj-1", status="blocked", reason="waiting")
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/admin-status")
    assert http.request.await_args.kwargs["json_data"] == {
        "status": "blocked",
        "reason": "waiting",
    }

    http.request.reset_mock()
    http.request.return_value = {"success": True, "tasks_created": 2}
    await ObjectivesModule(http).create_tasks("obj-1", [{"title": "a"}, {"title": "b"}])
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/admin-tasks")
    assert http.request.await_args.kwargs["json_data"] == {
        "tasks": [{"title": "a"}, {"title": "b"}]
    }


@pytest.mark.asyncio
async def test_download_artifacts_returns_raw_bytes(http):
    http.request.return_value = b"PK\x03\x04zip-bytes"
    archive = await ObjectivesModule(http).download_artifacts("obj-1")
    assert called(http) == ("GET", "/api/v1/objectives/obj-1/download")
    assert isinstance(archive, bytes)
    assert archive.startswith(b"PK")


# ---------------------------------------------------------------------------
# The HTTP layer's non-JSON body handling, which the download route needs
# ---------------------------------------------------------------------------


def test_non_json_success_body_comes_back_as_bytes_instead_of_raising():
    client = HTTPClient(base_url="https://example.invalid")
    response = httpx.Response(
        200,
        content=b"PK\x03\x04not-json-at-all",
        headers={"content-type": "application/zip"},
    )
    assert client._handle_response(response) == b"PK\x03\x04not-json-at-all"


def test_json_body_served_under_a_wrong_content_type_still_parses():
    # The predicate is the PARSE, not the header. A JSON body labelled
    # text/plain parses today and must keep parsing -- branching on the
    # content-type header would have broken exactly this case.
    client = HTTPClient(base_url="https://example.invalid")
    response = httpx.Response(
        200,
        content=json.dumps({"ok": True}).encode(),
        headers={"content-type": "text/plain"},
    )
    assert client._handle_response(response) == {"ok": True}


def test_created_and_accepted_bodies_still_parse_as_json():
    client = HTTPClient(base_url="https://example.invalid")
    for status in (201, 202):
        response = httpx.Response(
            status,
            content=json.dumps({"id": "x"}).encode(),
            headers={"content-type": "application/json"},
        )
        assert client._handle_response(response) == {"id": "x"}


def test_no_content_still_returns_none():
    client = HTTPClient(base_url="https://example.invalid")
    assert client._handle_response(httpx.Response(204)) is None


# ---------------------------------------------------------------------------
# Objective-scoped request operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_in_objective_is_not_the_flat_request_route(http):
    http.request.return_value = {
        "success": True,
        "request_id": "req-1",
        "status": "completed",
        "new_status": "completed",
        "objective_continuation": {
            "can_continue": False,
            "next_step": None,
            "blocking_requests": ["req-2"],
            "completed_requests": 1,
            "total_requests": 2,
        },
    }
    result = await RequestsModule(http).complete_in_objective("obj-1", "req-1")
    method, path = called(http)
    assert (method, path) == ("POST", "/api/v1/objectives/obj-1/requests/req-1/complete")
    # The objective-scoped route reports continuation; the flat one cannot.
    assert result["objective_continuation"]["blocking_requests"] == ["req-2"]


@pytest.mark.asyncio
async def test_decompose_addresses_the_objective_scoped_route(http):
    http.request.return_value = {"success": True, "task_graph": {}}
    await RequestsModule(http).decompose("obj-1", "req-1")
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/requests/req-1/decompose")


@pytest.mark.asyncio
async def test_submit_deliverable_does_not_confirm_sign_off_by_default(http):
    http.request.return_value = {"success": True, "request_id": "req-1"}
    await RequestsModule(http).submit_deliverable("obj-1", "req-1", deliverable_text="done")
    body = http.request.await_args.kwargs["json_data"]
    assert body["deliverable_text"] == "done"
    assert body["artifact_ids"] == []
    # Sign-off is a human assertion; the client must never default it on.
    assert body["sign_off_confirmed"] is False


# ---------------------------------------------------------------------------
# Clarification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_clarification_reports_queued_not_generated(http):
    http.request.return_value = {
        "status": "triggered",
        "message": "Clarification generation started.",
        "request_id": None,
    }
    result = await WorkObjectivesModule(http).trigger_clarification("obj-1")
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/clarify/trigger")
    assert result["status"] == "triggered"


@pytest.mark.asyncio
async def test_clarification_status_generating_has_empty_questions_for_a_reason(http):
    http.request.return_value = {
        "objective_id": "obj-1",
        "status": "generating",
        "questions": [],
        "responses": {},
        "understanding": None,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": None,
    }
    state = await WorkObjectivesModule(http).get_clarification_status("obj-1")
    assert called(http) == ("GET", "/api/v1/objectives/obj-1/clarification-status")
    # Empty questions with status "generating" means NOT READY, not "none
    # needed" -- the distinction a caller must branch on.
    assert state["status"] == "generating"
    assert state["questions"] == []


@pytest.mark.asyncio
async def test_clarification_status_failed_carries_a_message(http):
    http.request.return_value = {
        "objective_id": "obj-1",
        "status": "failed",
        "questions": [],
        "responses": {},
        "understanding": None,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:01:00Z",
        "message": "Clarification generation did not complete in time",
    }
    state = await WorkObjectivesModule(http).get_clarification_status("obj-1")
    assert state["status"] == "failed"
    assert state["message"]


@pytest.mark.asyncio
async def test_respond_to_clarification_variants_address_distinct_routes(http):
    http.request.return_value = {"objective_id": "obj-1", "status": "completed"}
    await WorkObjectivesModule(http).respond_to_clarification("obj-1", {"q1": "yes"})
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/clarify/respond")
    assert http.request.await_args.kwargs["json_data"] == {"responses": {"q1": "yes"}}

    http.request.reset_mock()
    http.request.return_value = {"success": True, "status": "completed"}
    await WorkObjectivesModule(http).respond_to_clarification_freeform("obj-1", "just do it")
    assert called(http) == ("POST", "/api/v1/objectives/obj-1/clarify/respond-freeform")
    assert http.request.await_args.kwargs["json_data"] == {"response": "just do it"}


# ---------------------------------------------------------------------------
# Pseudo agents
# ---------------------------------------------------------------------------

PSEUDO_AGENT = {
    "id": "pa-1",
    "name": "Legal sign-off",
    "description": "Routes approvals to counsel",
    "type": "atomic",
    "agentSubtype": "pseudo",
    "workspaceId": None,
    "workspaceIds": [],
    "createdBy": "user-1",
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z",
    "tags": [],
    "trustInfo": {},
    "pseudoConfig": {
        "routingChannels": [{"type": "email", "enabled": True, "primary": True, "config": {}}],
        "operators": [
            {
                "userId": "u1",
                "userName": "Counsel",
                "email": "counsel@example.com",
                "role": "primary",
            }
        ],
        "escalation": {
            "timeoutMinutes": 30,
            "escalationPath": ["u2"],
            "notifyOnEscalation": True,
            "maxEscalations": 2,
            "finalAction": "fail",
        },
        "instructions": "Approve or reject",
        "autoAssign": False,
        "requireClaim": True,
        "allowReassign": True,
    },
    "capabilities": [],
}


@pytest.mark.asyncio
async def test_create_pseudo_agent_sends_the_camelcase_config_key(http):
    http.request.return_value = PSEUDO_AGENT
    agent = await PseudoAgentsModule(http).create(
        name="Legal sign-off", description="d", config={"operators": []}
    )
    assert called(http) == ("POST", "/api/v1/work-units/pseudo")
    body = http.request.await_args.kwargs["json_data"]
    assert body["pseudoConfig"] == {"operators": []}
    # No trustSetup was passed, so none is sent -- the agent is created with
    # no trust chain, which the docstring says out loud.
    assert "trustSetup" not in body
    assert agent.pseudo_config.escalation.final_action == "fail"


@pytest.mark.asyncio
async def test_pseudo_agent_config_parses_operators_and_escalation(http):
    http.request.return_value = PSEUDO_AGENT
    agent = await PseudoAgentsModule(http).get("pa-1")
    assert called(http) == ("GET", "/api/v1/work-units/pseudo/pa-1")
    assert agent.pseudo_config.operators[0].user_name == "Counsel"
    assert agent.pseudo_config.escalation.timeout_minutes == 30
    assert agent.pseudo_config.routing_channels[0].type == "email"


@pytest.mark.asyncio
async def test_pseudo_agent_list_reads_the_page_envelope(http):
    http.request.return_value = {
        "items": [PSEUDO_AGENT],
        "total": 1,
        "page": 1,
        "pageSize": 50,
        "hasMore": False,
    }
    page = await PseudoAgentsModule(http).list(workspace_id="ws-1", limit=25)
    assert called(http) == ("GET", "/api/v1/work-units/pseudo")
    assert http.request.await_args.kwargs["params"] == {
        "limit": 25,
        "offset": 0,
        "workspace_id": "ws-1",
    }
    assert page.has_more is False
    assert page.items[0].name == "Legal sign-off"


@pytest.mark.asyncio
async def test_pseudo_agent_delete_addresses_the_agent_and_returns_none(http):
    http.request.return_value = None
    assert await PseudoAgentsModule(http).delete("pa-1") is None
    assert called(http) == ("DELETE", "/api/v1/work-units/pseudo/pa-1")


@pytest.mark.asyncio
async def test_test_channel_probes_a_candidate_not_a_saved_agent(http):
    http.request.return_value = {
        "success": True,
        "latencyMs": 120,
        "error": None,
        "details": None,
        "testedAt": "2026-01-01T00:00:00Z",
    }
    result = await PseudoAgentsModule(http).test_channel(
        "slack", config={"webhook": "https://hooks.example.com/x"}
    )
    method, path = called(http)
    # No agent id in the path: the channel under test is supplied inline.
    assert (method, path) == ("POST", "/api/v1/work-units/pseudo/test-channel")
    assert http.request.await_args.kwargs["json_data"]["type"] == "slack"
    assert result.latency_ms == 120


@pytest.mark.asyncio
async def test_route_task_creates_a_request_and_returns_it(http):
    http.request.return_value = {
        "id": "pr-1",
        "pseudoAgentId": "pa-1",
        "pseudoAgentName": "Legal sign-off",
        "workflowRunId": "run-1",
        "nodeId": "node-1",
        "title": "Approve contract",
        "workUnitId": "wu-1",
        "requestData": {"contract": "c-1"},
        "status": "pending",
        "priority": "high",
        "createdAt": "2026-01-01T00:00:00Z",
        "dueAt": "2026-01-01T01:00:00Z",
        "escalationLevel": 0,
        "context": {},
        "history": [],
    }
    request = await PseudoAgentsModule(http).route_task(
        "pa-1",
        workflow_run_id="run-1",
        node_id="node-1",
        title="Approve contract",
        request_data={"contract": "c-1"},
        priority="high",
    )
    assert called(http) == ("POST", "/api/v1/work-units/pseudo/pa-1/route")
    # It returns a PENDING request -- it did not wait for a human.
    assert request.status == "pending"
    assert request.due_at == "2026-01-01T01:00:00Z"


# ---------------------------------------------------------------------------
# Work-unit availability, runs and config versions
# ---------------------------------------------------------------------------

CONFIG_VERSION = {
    "id": "v-1",
    "workUnitId": "wu-1",
    "version": 3,
    "description": "before the model change",
    "config": {"model": "a"},
    "createdBy": "user-1",
    "createdByName": "Jo",
    "createdAt": "2026-01-01T00:00:00Z",
    "isCurrent": False,
    "tags": ["pre-change"],
}


@pytest.mark.asyncio
async def test_available_work_units_addresses_the_runnable_view(http):
    http.request.return_value = [
        {
            "id": "wu-1",
            "name": "Reporter",
            "type": "atomic",
            "trustInfo": {"hasTrust": False},
            "createdBy": "user-1",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        }
    ]
    units = await WorkObjectivesModule(http).list_available_work_units()
    assert called(http) == ("GET", "/api/v1/work-units/available")
    assert units[0].id == "wu-1"


@pytest.mark.asyncio
async def test_work_unit_runs_passes_the_limit(http):
    http.request.return_value = [
        {"id": "run-1", "status": "completed", "startedAt": "2026-01-01T00:00:00Z"}
    ]
    runs = await WorkObjectivesModule(http).list_work_unit_runs("wu-1", limit=5)
    assert called(http) == ("GET", "/api/v1/work-units/wu-1/runs")
    assert http.request.await_args.kwargs["params"] == {"limit": 5}
    assert runs[0].status == "completed"


@pytest.mark.asyncio
async def test_version_list_reports_which_version_is_current(http):
    http.request.return_value = {
        "versions": [CONFIG_VERSION],
        "total": 1,
        "currentVersion": 4,
    }
    listing = await WorkObjectivesModule(http).list_work_unit_versions("wu-1")
    assert called(http) == ("GET", "/api/v1/work-units/wu-1/versions")
    assert listing.currentVersion == 4
    assert listing.versions[0].isCurrent is False


@pytest.mark.asyncio
async def test_compare_versions_uses_the_from_and_to_query_names(http):
    http.request.return_value = {
        "fromVersion": CONFIG_VERSION,
        "toVersion": {**CONFIG_VERSION, "id": "v-2", "version": 4, "isCurrent": True},
        "changes": [
            {
                "field": "model",
                "path": ["config", "model"],
                "changeType": "modified",
                "oldValue": "a",
                "newValue": "b",
            }
        ],
    }
    comparison = await WorkObjectivesModule(http).compare_work_unit_versions("wu-1", "v-1", "v-2")
    assert called(http) == ("GET", "/api/v1/work-units/wu-1/versions/compare")
    # The query keys are literally "from" and "to" -- "from" is a Python
    # keyword, so this is exactly the kind of name that gets silently renamed.
    assert http.request.await_args.kwargs["params"] == {"from": "v-1", "to": "v-2"}
    assert comparison.changes[0].newValue == "b"


@pytest.mark.asyncio
async def test_restore_omits_create_backup_when_the_caller_did_not_choose(http):
    http.request.return_value = CONFIG_VERSION
    await WorkObjectivesModule(http).restore_work_unit_version("wu-1", "v-1")
    assert called(http) == ("POST", "/api/v1/work-units/wu-1/versions/v-1/restore")
    # Nothing is asserted about backups unless the caller asked for it.
    assert http.request.await_args.kwargs["json_data"] is None


@pytest.mark.asyncio
async def test_restore_sends_create_backup_when_asked(http):
    http.request.return_value = CONFIG_VERSION
    await WorkObjectivesModule(http).restore_work_unit_version(
        "wu-1", "v-1", create_backup=True, description="rollback"
    )
    assert http.request.await_args.kwargs["json_data"] == {
        "createBackup": True,
        "description": "rollback",
    }


@pytest.mark.asyncio
async def test_delete_version_returns_none(http):
    http.request.return_value = None
    assert await WorkObjectivesModule(http).delete_work_unit_version("wu-1", "v-1") is None
    assert called(http) == ("DELETE", "/api/v1/work-units/wu-1/versions/v-1")
