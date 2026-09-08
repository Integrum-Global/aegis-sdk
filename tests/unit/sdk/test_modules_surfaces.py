"""
Contract tests for the SurfacesModule SDK module.

Pins route + method + request body + response shape for the architect-tier
surface registry against the real backend handlers (six routes served by the
Nexus surface-registry bridge) via a stubbed HTTPClient.

WHAT THESE ASSERT, AND WHAT THEY DELIBERATELY DO NOT
----------------------------------------------------
They assert the WIRE SHAPE: the exact method, the exact path, the exact body
keys, and that the parsed model carries the server's field set. A test that
only asserted a method exists would pass against a client addressing the wrong
path with the wrong verb, which is the defect class this module is most likely
to acquire.

They do NOT assert server behaviour — persona gating, permission gating,
tenant scoping, vocabulary rejection and the fail-closed default are enforced
server-side and are covered by the backend's own unit and security suites. A
stubbed transport cannot observe any of them, and a test that pretended to
would be reporting on the stub.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.modules.surfaces import (
    SurfaceDeleteResult,
    SurfaceManifest,
    SurfaceManifestEntry,
    SurfaceRegistration,
    SurfaceRegistrationListResult,
    SurfacesModule,
)


@pytest.fixture
def mock_http():
    """Create mock HTTP client."""
    return MagicMock()


@pytest.fixture
def surfaces_module(mock_http):
    """Create SurfacesModule with mock HTTP client."""
    return SurfacesModule(mock_http)


def make_manifest_entry(surface_key="finance_exceptions"):
    """The manifest projection — 11 keys, no ids and no provenance."""
    return {
        "surface_key": surface_key,
        "route_path": f"/x/{surface_key}",
        "nav_section": "GOVERN",
        "nav_label": "Finance Exceptions",
        "nav_description": "Exceptions awaiting review",
        "icon_key": "Shield",
        "sort_order": 10,
        "view_kind": "record_list",
        "view_config": {"columns": [{"key": "ref", "label": "Reference"}]},
        "personas": ["architect", "executive"],
        "classification": "restricted",
    }


def make_registration(surface_key="finance_exceptions", status="disabled"):
    """The full authoring projection."""
    return {
        "id": "surf-1",
        "organization_id": "org-1",
        "surface_key": surface_key,
        "route_path": f"/x/{surface_key}",
        "nav_section": "GOVERN",
        "nav_label": "Finance Exceptions",
        "nav_description": "Exceptions awaiting review",
        "icon_key": "Shield",
        "sort_order": 10,
        "view_kind": "record_list",
        "view_config": {"empty_message": "Nothing to review"},
        "required_permission": "organizations:read",
        "personas": ["architect", "executive"],
        "classification": "restricted",
        "status": status,
        "derived_scopes": {
            "read": f"surface:{surface_key}:read",
            "write": f"surface:{surface_key}:write",
            "approve": f"surface:{surface_key}:approve",
            "admin": f"surface:{surface_key}:admin",
        },
        "created_by": "user-1",
        "updated_by": "user-1",
        "created_at": "2026-09-08T12:00:00Z",
        "updated_at": "2026-09-08T12:00:00Z",
    }


@pytest.mark.unit
@pytest.mark.asyncio
class TestManifest:
    """GET /api/v1/surface-registry"""

    async def test_manifest_route_and_shape(self, mock_http, surfaces_module):
        mock_http.request = AsyncMock(return_value={"surfaces": [make_manifest_entry()]})

        result = await surfaces_module.manifest()

        mock_http.request.assert_called_once_with("GET", "/api/v1/surface-registry")
        assert isinstance(result, SurfaceManifest)
        entry = result.surfaces[0]
        assert isinstance(entry, SurfaceManifestEntry)
        assert entry.surface_key == "finance_exceptions"
        assert entry.route_path == "/x/finance_exceptions"
        assert entry.nav_section == "GOVERN"
        assert entry.personas == ["architect", "executive"]
        assert entry.view_config == {"columns": [{"key": "ref", "label": "Reference"}]}

    async def test_manifest_takes_no_parameters(self, mock_http, surfaces_module):
        """The manifest is scoped entirely server-side. No query parameter can
        widen it, so the client sends none — passing one would read as though
        the caller could choose whose manifest they receive."""
        mock_http.request = AsyncMock(return_value={"surfaces": []})

        await surfaces_module.manifest()

        _args, kwargs = mock_http.request.call_args
        assert "params" not in kwargs
        assert "json_data" not in kwargs

    async def test_empty_manifest_parses(self, mock_http, surfaces_module):
        """An empty registry is the normal state for a fresh tenant."""
        mock_http.request = AsyncMock(return_value={"surfaces": []})

        result = await surfaces_module.manifest()

        assert result.surfaces == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestListRegistrations:
    """GET /api/v1/surface-registry/registrations"""

    async def test_list_route_and_shape(self, mock_http, surfaces_module):
        mock_http.request = AsyncMock(
            return_value={"registrations": [make_registration()]}
        )

        result = await surfaces_module.list_registrations()

        mock_http.request.assert_called_once_with(
            "GET", "/api/v1/surface-registry/registrations"
        )
        assert isinstance(result, SurfaceRegistrationListResult)
        row = result.registrations[0]
        assert isinstance(row, SurfaceRegistration)
        assert row.id == "surf-1"
        assert row.organization_id == "org-1"
        assert row.required_permission == "organizations:read"
        assert row.derived_scopes["admin"] == "surface:finance_exceptions:admin"
        assert row.unresolvable is False

    async def test_unresolvable_row_parses_rather_than_raising(
        self, mock_http, surfaces_module
    ):
        """THE REGRESSION THIS FILE EXISTS FOR.

        When a stored row no longer satisfies the current server-side
        vocabulary the authoring read degrades to eight keys — no nav_section,
        no icon_key, no personas, and a NULL route_path — so the whole list does
        not fail on one bad row. A model requiring those fields would raise on
        exactly the row an architect needs to see in order to repair it.
        """
        mock_http.request = AsyncMock(
            return_value={
                "registrations": [
                    {
                        "id": "surf-2",
                        "organization_id": "org-1",
                        "surface_key": "legacy_key",
                        "route_path": None,
                        "nav_label": "Legacy",
                        "status": "disabled",
                        "unresolvable": True,
                        "unresolvable_field": "surface_key",
                    }
                ]
            }
        )

        result = await surfaces_module.list_registrations()

        row = result.registrations[0]
        assert row.unresolvable is True
        assert row.unresolvable_field == "surface_key"
        assert row.route_path is None
        assert row.nav_section is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetRegistration:
    """GET /api/v1/surface-registry/registrations/{surface_key}"""

    async def test_get_route_and_shape(self, mock_http, surfaces_module):
        mock_http.request = AsyncMock(return_value=make_registration())

        result = await surfaces_module.get_registration("finance_exceptions")

        mock_http.request.assert_called_once_with(
            "GET", "/api/v1/surface-registry/registrations/finance_exceptions"
        )
        assert isinstance(result, SurfaceRegistration)
        assert result.surface_key == "finance_exceptions"

    async def test_surface_key_is_path_encoded(self, mock_http, surfaces_module):
        """A key is interpolated into the path, so it is percent-encoded per
        segment. The server's own key pattern would refuse this value; the
        encoder is defence in depth ahead of that, so a separator smuggled into
        an identifier cannot shift which segments the request addresses."""
        mock_http.request = AsyncMock(return_value=make_registration("a"))

        await surfaces_module.get_registration("../../admin")

        called_path = mock_http.request.call_args[0][1]
        assert called_path.startswith("/api/v1/surface-registry/registrations/")
        tail = called_path.rsplit("/", 1)[-1]
        assert "/" not in tail
        assert tail == "..%2F..%2Fadmin"


@pytest.mark.unit
@pytest.mark.asyncio
class TestCreateRegistration:
    """POST /api/v1/surface-registry/registrations"""

    async def test_create_sends_only_required_keys_when_nothing_else_given(
        self, mock_http, surfaces_module
    ):
        """Omitted arguments are ABSENT from the body, not sent as null.

        The server applies its own defaults — notably status="disabled" — to
        keys the body does not carry. Sending explicit nulls would be a
        different request.
        """
        mock_http.request = AsyncMock(return_value=make_registration())

        result = await surfaces_module.create_registration(
            surface_key="finance_exceptions",
            nav_section="GOVERN",
            nav_label="Finance Exceptions",
        )

        mock_http.request.assert_called_once_with(
            "POST",
            "/api/v1/surface-registry/registrations",
            json_data={
                "surface_key": "finance_exceptions",
                "nav_section": "GOVERN",
                "nav_label": "Finance Exceptions",
            },
        )
        assert isinstance(result, SurfaceRegistration)
        assert result.status == "disabled"

    async def test_create_sends_every_optional_field_under_its_wire_name(
        self, mock_http, surfaces_module
    ):
        mock_http.request = AsyncMock(return_value=make_registration())

        await surfaces_module.create_registration(
            surface_key="finance_exceptions",
            nav_section="GOVERN",
            nav_label="Finance Exceptions",
            nav_description="Exceptions awaiting review",
            icon_key="Shield",
            sort_order=10,
            view_kind="record_list",
            view_config={"empty_message": "Nothing to review"},
            required_permission="organizations:read",
            personas=["architect", "executive"],
            classification="confidential",
            status="enabled",
        )

        body = mock_http.request.call_args[1]["json_data"]
        assert body == {
            "surface_key": "finance_exceptions",
            "nav_section": "GOVERN",
            "nav_label": "Finance Exceptions",
            "nav_description": "Exceptions awaiting review",
            "icon_key": "Shield",
            "sort_order": 10,
            "view_kind": "record_list",
            "view_config": {"empty_message": "Nothing to review"},
            "required_permission": "organizations:read",
            "personas": ["architect", "executive"],
            "classification": "confidential",
            "status": "enabled",
        }

    async def test_create_never_sends_route_path_or_organization_id(
        self, mock_http, surfaces_module
    ):
        """Neither is a request field. The route is DERIVED server-side from
        the key, and the organization comes from the authenticated principal —
        a client that sent either would be addressing a contract that does not
        exist, and the server forbids unknown keys."""
        mock_http.request = AsyncMock(return_value=make_registration())

        await surfaces_module.create_registration(
            surface_key="finance_exceptions",
            nav_section="GOVERN",
            nav_label="Finance Exceptions",
        )

        body = mock_http.request.call_args[1]["json_data"]
        assert "route_path" not in body
        assert "organization_id" not in body
        assert "derived_scopes" not in body

    async def test_sort_order_zero_is_sent_not_dropped(self, mock_http, surfaces_module):
        """0 is a meaningful sort position and is falsy. A truthiness test here
        would silently drop it and let the server default apply instead."""
        mock_http.request = AsyncMock(return_value=make_registration())

        await surfaces_module.create_registration(
            surface_key="finance_exceptions",
            nav_section="GOVERN",
            nav_label="Finance Exceptions",
            sort_order=0,
        )

        assert mock_http.request.call_args[1]["json_data"]["sort_order"] == 0

    async def test_empty_persona_list_is_sent_not_dropped(
        self, mock_http, surfaces_module
    ):
        """An empty persona list means visible to nobody — the fail-closed
        state, and a deliberate request. Dropping it as falsy would leave the
        server's default in place, which is the opposite instruction."""
        mock_http.request = AsyncMock(return_value=make_registration())

        await surfaces_module.create_registration(
            surface_key="finance_exceptions",
            nav_section="GOVERN",
            nav_label="Finance Exceptions",
            personas=[],
        )

        assert mock_http.request.call_args[1]["json_data"]["personas"] == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestUpdateRegistration:
    """PATCH /api/v1/surface-registry/registrations/{surface_key}"""

    async def test_update_is_patch_and_sends_only_supplied_fields(
        self, mock_http, surfaces_module
    ):
        mock_http.request = AsyncMock(return_value=make_registration(status="enabled"))

        result = await surfaces_module.update_registration(
            "finance_exceptions", status="enabled"
        )

        mock_http.request.assert_called_once_with(
            "PATCH",
            "/api/v1/surface-registry/registrations/finance_exceptions",
            json_data={"status": "enabled"},
        )
        assert isinstance(result, SurfaceRegistration)
        assert result.status == "enabled"

    async def test_update_never_sends_surface_key_in_the_body(
        self, mock_http, surfaces_module
    ):
        """The key addresses the row; it is immutable and is not a writable
        field. Sending it would be refused rather than ignored."""
        mock_http.request = AsyncMock(return_value=make_registration())

        await surfaces_module.update_registration(
            "finance_exceptions", nav_label="Renamed", sort_order=3
        )

        body = mock_http.request.call_args[1]["json_data"]
        assert body == {"nav_label": "Renamed", "sort_order": 3}
        assert "surface_key" not in body

    async def test_update_key_is_path_encoded(self, mock_http, surfaces_module):
        mock_http.request = AsyncMock(return_value=make_registration("a"))

        await surfaces_module.update_registration("a/b", status="enabled")

        called_path = mock_http.request.call_args[0][1]
        assert called_path == "/api/v1/surface-registry/registrations/a%2Fb"


@pytest.mark.unit
@pytest.mark.asyncio
class TestDeleteRegistration:
    """DELETE /api/v1/surface-registry/registrations/{surface_key}"""

    async def test_delete_route_and_shape(self, mock_http, surfaces_module):
        mock_http.request = AsyncMock(
            return_value={"deleted": True, "surface_key": "finance_exceptions"}
        )

        result = await surfaces_module.delete_registration("finance_exceptions")

        mock_http.request.assert_called_once_with(
            "DELETE", "/api/v1/surface-registry/registrations/finance_exceptions"
        )
        assert isinstance(result, SurfaceDeleteResult)
        assert result.deleted is True
        assert result.surface_key == "finance_exceptions"

    async def test_delete_sends_no_body(self, mock_http, surfaces_module):
        mock_http.request = AsyncMock(
            return_value={"deleted": True, "surface_key": "finance_exceptions"}
        )

        await surfaces_module.delete_registration("finance_exceptions")

        assert "json_data" not in mock_http.request.call_args[1]


@pytest.mark.unit
class TestClientRegistration:
    """The module is reachable from the client, under a stable attribute."""

    def test_client_exposes_surfaces(self):
        from aegis_sdk.client import AgenticOSClient

        client = AgenticOSClient(base_url="http://localhost:8000", api_key="test-key")

        assert isinstance(client.surfaces, SurfacesModule)

    def test_package_exports_module_and_models(self):
        import aegis_sdk

        for name in (
            "SurfacesModule",
            "SurfaceManifest",
            "SurfaceManifestEntry",
            "SurfaceRegistration",
            "SurfaceRegistrationListResult",
            "SurfaceDeleteResult",
        ):
            assert name in aegis_sdk.__all__, f"{name} missing from aegis_sdk.__all__"
            assert getattr(aegis_sdk, name) is not None
