"""
Unit tests for the trust-plane SDK modules added alongside chains/delegations.

Two things are asserted throughout, and the first matters more than it looks:

1. The exact METHOD and PATH each call issues. A client method that addresses
   the wrong path is indistinguishable from a correct one at the type level,
   and the whole point of these modules is that they reach real routes.
2. That the models parse the shape the platform actually returns -- including
   the empty-state and absent-field cases, which are where a wrong model does
   its damage quietly.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.trust.agent_trust import AgentTrustModule
from aegis_sdk.trust.audit import AuditModule
from aegis_sdk.trust.authorities import AuthoritiesModule
from aegis_sdk.trust.chains import ChainsModule
from aegis_sdk.trust.esa import ESAModule
from aegis_sdk.trust.observability import TrustObservabilityModule
from aegis_sdk.trust.pipeline import PipelineTrustModule
from aegis_sdk.trust.registry import TrustRegistryModule
from aegis_sdk.trust.revocation import RevocationModule


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
# Authorities
# ---------------------------------------------------------------------------

AUTHORITY = {
    "id": "auth-1",
    "name": "Platform Engineering",
    "organization_id": "org-1",
    "public_key": None,
    "status": "active",
    "created_at": "2026-01-01T00:00:00Z",
}


@pytest.mark.asyncio
async def test_authorities_list_addresses_the_collection(http):
    http.request.return_value = [AUTHORITY]
    result = await AuthoritiesModule(http).list()
    assert called(http) == ("GET", "/api/v1/trust/authorities")
    assert result[0].name == "Platform Engineering"


@pytest.mark.asyncio
async def test_authorities_create_sends_type_alias_not_authority_type(http):
    http.request.return_value = AUTHORITY
    await AuthoritiesModule(http).create(name="X", description="d", authority_type="regulatory")
    body = http.request.await_args.kwargs["json_data"]
    # The platform accepts BOTH spellings; the SDK sends the one the frontend
    # shape uses. Pinning it stops a silent switch to the other.
    assert body["type"] == "regulatory"
    assert body["name"] == "X"


@pytest.mark.asyncio
async def test_authorities_update_omits_unset_fields(http):
    http.request.return_value = AUTHORITY
    await AuthoritiesModule(http).update("auth-1", name="renamed")
    assert http.request.await_args.kwargs["json_data"] == {"name": "renamed"}


@pytest.mark.asyncio
async def test_authorities_deactivate_requires_reason_in_body(http):
    http.request.return_value = AUTHORITY
    await AuthoritiesModule(http).deactivate("auth-1", reason="key rotated")
    assert called(http) == ("POST", "/api/v1/trust/authorities/auth-1/deactivate")
    assert http.request.await_args.kwargs["json_data"] == {"reason": "key rotated"}


@pytest.mark.asyncio
async def test_authorities_display_variant_tolerates_absent_agent_count(http):
    http.request.return_value = [AUTHORITY]
    result = await AuthoritiesModule(http).list_for_display()
    assert called(http) == ("GET", "/api/v1/trust/authorities/ui")
    # An absent count must stay None. Defaulting it to 0 would render
    # "no agents" for an authority whose count was simply not computed.
    assert result[0].agent_count is None


@pytest.mark.asyncio
async def test_authorities_display_variant_reads_the_merged_count(http):
    http.request.return_value = [{**AUTHORITY, "agentCount": 7}]
    result = await AuthoritiesModule(http).list_for_display()
    assert result[0].agent_count == 7


# ---------------------------------------------------------------------------
# Per-agent trust reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_capabilities_empty_for_agent_without_chain(http):
    http.request.return_value = []
    result = await AgentTrustModule(http).get_capabilities("agent-1")
    assert called(http) == ("GET", "/api/v1/trust/agents/agent-1/capabilities")
    assert result == []


@pytest.mark.asyncio
async def test_agent_summary_parses_the_no_trust_empty_state(http):
    http.request.return_value = {
        "agent_id": "agent-1",
        "has_trust": False,
        "status": "none",
        "capabilities_count": 0,
        "delegations_count": 0,
        "last_verified": None,
        "human_origin": None,
    }
    summary = await AgentTrustModule(http).get_summary("agent-1")
    assert summary.has_trust is False
    assert summary.status == "none"


@pytest.mark.asyncio
async def test_agent_with_trust_keeps_protocols_and_endpoints_empty(http):
    http.request.return_value = {
        "id": "agent-1",
        "name": "Reporter",
        "trust_status": "valid",
        "trust_chain_id": "chain-1",
        "capabilities": ["read:data"],
        "constraints": [],
        "protocols": [],
        "endpoints": [],
        "established_by": "Jo",
        "expires_at": None,
    }
    result = await AgentTrustModule(http).get_with_trust("agent-1")
    assert result.protocols == []
    assert result.endpoints == []


@pytest.mark.asyncio
async def test_trust_score_parses_camelcase_wire_shape(http):
    http.request.return_value = {
        "agentId": "agent-1",
        "organizationId": "org-1",
        "compositeScore": 72.5,
        "grade": "C",
        "currentPosture": "supervised",
        "calculatedAt": "2026-01-01T00:00:00Z",
        "dimensions": [
            {
                "name": "reliability",
                "label": "Reliability",
                "careDimension": "Operational",
                "score": 80.0,
                "weight": 0.25,
                "evidenceSummary": "42 runs",
            }
        ],
    }
    score = await AgentTrustModule(http).get_trust_score("agent-1")
    assert called(http) == ("GET", "/api/v1/trust/agents/agent-1/trust-score")
    assert score.composite_score == 72.5
    assert score.dimensions[0].care_dimension == "Operational"


@pytest.mark.asyncio
async def test_care_budget_keeps_unmeasured_dimension_as_none_not_zero(http):
    http.request.return_value = {
        "agentId": "agent-1",
        "organizationId": "org-1",
        "dimensions": [
            {
                "name": "communication",
                "label": "Communication",
                "careDimension": "Communication",
                "unit": None,
                "used": None,
                "limit": None,
                "available": False,
                "detail": None,
                "binding": None,
            }
        ],
    }
    budget = await AgentTrustModule(http).get_care_budget("agent-1")
    dimension = budget.dimensions[0]
    # used=None means "no counter exists", which is NOT zero consumption.
    assert dimension.used is None
    assert dimension.available is False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_register_sends_identity_as_query_and_rest_as_body(http):
    http.request.return_value = {
        "id": "agent-1",
        "agent_id": "agent-1",
        "name": "Reporter",
        "capabilities": ["read:data"],
        "tags": [],
        "status": "active",
        "registered_at": "2026-01-01T00:00:00Z",
        "last_heartbeat": "2026-01-01T00:00:00Z",
    }
    await TrustRegistryModule(http).register(
        agent_id="agent-1", name="Reporter", capabilities=["read:data"]
    )
    assert called(http) == ("POST", "/api/v1/trust/registry/agents")
    kwargs = http.request.await_args.kwargs
    assert kwargs["params"] == {"agent_id": "agent-1", "name": "Reporter"}
    assert kwargs["json_data"] == {"capabilities": ["read:data"]}


@pytest.mark.asyncio
async def test_registry_discover_splits_status_query_from_body_filters(http):
    http.request.return_value = []
    await TrustRegistryModule(http).discover(capabilities=["read:data"], status="active")
    kwargs = http.request.await_args.kwargs
    assert kwargs["params"] == {"status": "active"}
    assert kwargs["json_data"] == {"capabilities": ["read:data"]}


@pytest.mark.asyncio
async def test_registry_heartbeat_addresses_the_agent_scoped_route(http):
    http.request.return_value = {"success": True, "timestamp": "2026-01-01T00:00:00Z"}
    result = await TrustRegistryModule(http).heartbeat("agent-1")
    assert called(http) == ("POST", "/api/v1/trust/registry/agents/agent-1/heartbeat")
    assert result.success is True


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_validate_sends_pipeline_id_as_query_agents_as_body(http):
    http.request.return_value = {
        "pipeline_id": "pipe-1",
        "all_valid": False,
        "agent_statuses": [
            {
                "agent_id": "agent-1",
                "has_trust": False,
                "missing_capabilities": ["read:data"],
                "violated_constraints": [],
            }
        ],
    }
    result = await PipelineTrustModule(http).validate(
        pipeline_id="pipe-1",
        agent_ids=["agent-1"],
        required_capabilities={"agent-1": ["read:data"]},
    )
    assert called(http) == ("POST", "/api/v1/trust/pipeline/validate")
    kwargs = http.request.await_args.kwargs
    assert kwargs["params"] == {"pipeline_id": "pipe-1"}
    assert kwargs["json_data"]["agent_ids"] == ["agent-1"]
    assert result.all_valid is False
    # Empty here means NOT CHECKED, per the model's own warning. Pinned so a
    # future reader does not start treating it as a verdict.
    assert result.agent_statuses[0].violated_constraints == []


@pytest.mark.asyncio
async def test_pipeline_agent_status_encodes_both_path_params(http):
    http.request.return_value = {
        "agent_id": "a/1",
        "pipeline_id": "p/1",
        "has_trust": False,
        "capabilities": [],
        "constraints": [],
        "status": "none",
        "human_origin": None,
    }
    await PipelineTrustModule(http).get_agent_status("p/1", "a/1")
    _method, path = called(http)
    assert "p/1" not in path and "a/1" not in path
    assert path.startswith("/api/v1/trust/pipeline/")
    assert path.endswith("/agents/a%2F1")


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_sends_agent_and_reason_as_query_params(http):
    http.request.return_value = {"message": "Trust revoked", "reason": "compromised"}
    await RevocationModule(http).revoke("agent-1", reason="compromised")
    assert called(http) == ("POST", "/api/v1/trust/revoke")
    assert http.request.await_args.kwargs["params"] == {
        "agent_id": "agent-1",
        "reason": "compromised",
    }


@pytest.mark.asyncio
async def test_incomplete_jobs_unwraps_the_items_envelope(http):
    http.request.return_value = {
        "items": [
            {
                "id": "job-1",
                "target_agent_id": "agent-1",
                "status": "incomplete",
                "reason": "compromised",
                "total_targets": 10,
                "completed_count": 4,
                "failed_count": 0,
                "initiated_by": "jo@example.com",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:05:00Z",
            }
        ],
        "total": 1,
    }
    jobs = await RevocationModule(http).list_incomplete_jobs()
    assert called(http) == ("GET", "/api/v1/trust/revoke/jobs/incomplete")
    assert jobs[0].completed_count == 4
    assert jobs[0].total_targets == 10


@pytest.mark.asyncio
async def test_resume_job_reports_whether_the_resume_itself_timed_out(http):
    http.request.return_value = {
        "revocation_job_id": "job-1",
        "status": "incomplete",
        "total_targets": 10,
        "total_revoked": 8,
        "newly_revoked": ["agent-5", "agent-6"],
        "timed_out": True,
    }
    result = await RevocationModule(http).resume_job("job-1")
    assert called(http) == ("POST", "/api/v1/trust/revoke/jobs/job-1/resume")
    assert result.timed_out is True
    assert result.total_revoked < result.total_targets


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_report_keeps_score_none_when_nothing_was_measured(http):
    http.request.return_value = {
        "organization_id": "org-1",
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-02-01T00:00:00Z",
        "total_actions": 0,
        "allowed_actions": 0,
        "denied_actions": 0,
        "failed_actions": 0,
        "compliance_score": None,
        "violations": [],
        "measured": False,
        "measurement_reason": "No audit activity recorded",
        "scan_complete": True,
        "scan_note": None,
        "violations_truncated": False,
        "violations_total": 0,
        "pages_scanned": 1,
    }
    report = await TrustObservabilityModule(http).get_compliance_report(
        "org-1", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"
    )
    assert called(http) == ("GET", "/api/v1/trust/compliance/org-1")
    # An unmeasured period must NOT read as 100% compliant.
    assert report.measured is False
    assert report.compliance_score is None


@pytest.mark.asyncio
async def test_compliance_report_surfaces_an_incomplete_scan(http):
    http.request.return_value = {
        "organization_id": "org-1",
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-02-01T00:00:00Z",
        "total_actions": 20000,
        "allowed_actions": 19000,
        "denied_actions": 900,
        "failed_actions": 100,
        "compliance_score": 95.0,
        "violations": [],
        "measured": True,
        "measurement_reason": None,
        "scan_complete": False,
        "scan_note": "Scan stopped at the bound",
        "violations_truncated": True,
        "violations_total": 1000,
        "pages_scanned": 40,
    }
    report = await TrustObservabilityModule(http).get_compliance_report(
        "org-1", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"
    )
    # A score with scan_complete False is a sample, not the period figure.
    assert report.scan_complete is False
    assert report.violations_truncated is True


@pytest.mark.asyncio
async def test_metrics_export_does_not_send_a_format_the_platform_ignores(http):
    http.request.return_value = {"total_chains": 0, "timeline": []}
    await TrustObservabilityModule(http).export_metrics("s", "e")
    assert called(http) == ("GET", "/api/v1/trust/metrics/export")
    assert http.request.await_args.kwargs["params"] == {"start": "s", "end": "e"}


@pytest.mark.asyncio
async def test_health_parses_a_degraded_snapshot(http):
    http.request.return_value = {
        "healthy": False,
        "active_failures": [
            {
                "failure_mode": "missing_evidence",
                "severity": "high",
                "detected_at": "2026-01-01T00:00:00Z",
                "description": "No evidence",
                "impact": "Scoring unavailable",
            }
        ],
        "checked_at": "2026-01-01T00:00:00Z",
        "warnings": ["probe ran without context"],
    }
    health = await TrustObservabilityModule(http).get_health()
    # The route answers 200 while degraded, so a successful call is not a
    # healthy verdict -- this is the branch a caller must actually take.
    assert health.healthy is False
    assert health.active_failures[0].severity == "high"


# ---------------------------------------------------------------------------
# ESA
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_esa_get_config_surfaces_the_masked_key_verbatim(http):
    http.request.return_value = {
        "enabled": True,
        "url": "https://esa.example.com",
        "api_key": "abc****wxyz",
        "sync_interval_minutes": 30,
    }
    config = await ESAModule(http).get_config()
    # The SDK must NOT try to be clever and blank a masked key: the caller has
    # to be able to see that what came back is a mask.
    assert config.api_key == "abc****wxyz"


@pytest.mark.asyncio
async def test_esa_update_config_sends_every_field_because_it_replaces(http):
    http.request.return_value = {
        "enabled": True,
        "url": "https://esa.example.com",
        "api_key": "real-key",
        "sync_interval_minutes": 60,
    }
    await ESAModule(http).update_config(enabled=True, url="https://esa.example.com")
    body = http.request.await_args.kwargs["json_data"]
    assert set(body) == {"enabled", "url", "api_key", "sync_interval_minutes"}


@pytest.mark.asyncio
async def test_esa_test_connection_reports_failure_in_the_body_not_by_raising(http):
    http.request.return_value = {"success": False, "message": "ESA not enabled"}
    result = await ESAModule(http).test_connection()
    assert called(http) == ("POST", "/api/v1/trust/esa/test-connection")
    assert result.success is False


# ---------------------------------------------------------------------------
# Chain summary and audit trace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_summary_accepts_fields_being_absent_under_redaction(http):
    # Under selective disclosure the gated fields are ABSENT, not null.
    http.request.return_value = {
        "id": "chain-1",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "delegation_type": "direct",
    }
    summary = await ChainsModule(http).get_summary("agent-1")
    assert called(http) == ("GET", "/api/v1/trust/chains/agent-1/summary")
    assert summary.trustor_agent_id is None
    assert summary.source_bridge_id is None


@pytest.mark.asyncio
async def test_chain_summary_reads_bridge_origin_from_source_bridge_id(http):
    http.request.return_value = {
        "id": "chain-1",
        "status": "suspended",
        "created_at": "2026-01-01T00:00:00Z",
        "delegation_type": "direct",
        "trustor_agent_id": "a",
        "trustee_agent_id": "b",
        "source_bridge_id": "bridge-9",
    }
    summary = await ChainsModule(http).get_summary("agent-1")
    # Bridge origin is source_bridge_id, NOT delegation_type == "bridge".
    assert summary.source_bridge_id == "bridge-9"
    assert summary.delegation_type == "direct"


@pytest.mark.asyncio
async def test_audit_trace_addresses_the_trace_route(http):
    http.request.return_value = {
        "root_user_id": "user-1",
        "delegation_chain": [{"from": "user-1", "to": "agent-1"}],
        "delegation_depth": 1,
        "verified": True,
    }
    chain = await AuditModule(http).trace("entry-1")
    assert called(http) == ("GET", "/api/v1/trust/audit/trace/entry-1")
    assert chain.delegation_depth == 1
