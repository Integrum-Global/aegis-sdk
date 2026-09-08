"""
Surfaces Module for Agentic OS SDK — the architect-tier surface registry.

Thin HTTP-wrapper over the backend's surface-registry API
(prefix ``/api/v1/surface-registry``). A *surface* is a tenant-scoped,
data-driven domain screen: one registration contributes one navigation entry
and one reachable route, with no code edit and no deploy. This is the
capability that lets a client architect compose a domain area of the product
at runtime instead of forking the frontend.

Every route below was verified against the backend handlers and the stored
model before implementation — path, method, and response shape (all
snake_case, no camelCase aliasing) match exactly. This module is
self-contained (no imports from client.py / modules/__init__.py / types.py);
a separate registration pass exposes it on ``AgenticOSClient``.

6 methods:
- manifest()              - GET    /api/v1/surface-registry
- list_registrations()    - GET    /api/v1/surface-registry/registrations
- create_registration()   - POST   /api/v1/surface-registry/registrations
- get_registration()      - GET    /api/v1/surface-registry/registrations/{surface_key}
- update_registration()   - PATCH  /api/v1/surface-registry/registrations/{surface_key}
- delete_registration()   - DELETE /api/v1/surface-registry/registrations/{surface_key}

TWO READS, TWO DIFFERENT PROJECTIONS
====================================
:meth:`SurfacesModule.manifest` is the per-caller read every persona may
make: it returns exactly the entries THIS caller may see, already filtered
server-side by tenant, status, vocabulary, persona and each entry's own
required permission. It deliberately omits ``organization_id``, provenance
and ``required_permission`` — the gate that admitted an entry tells the
client nothing it can act on.

The ``/registrations`` methods are the AUTHORING projection and are gated
separately: they require an ``architect``, ``admin`` or ``executive``
persona AND a ``surfaces:<verb>`` permission. Holding the persona is not
sufficient. They return the full row, including ids, provenance and every
unpublished draft.

THE ROUTE PATH IS DERIVED, NEVER SUPPLIED
=========================================
There is no ``route_path`` request field. A surface mounts at
``/x/{surface_key}``, computed server-side from a key constrained to a
leading lowercase letter followed by lowercase alphanumerics and
underscores, length 3-64. Nothing a caller writes is concatenated into a
path, so path traversal, scheme injection and route shadowing are
unrepresentable rather than filtered. ``route_path`` is returned on reads;
supplying it on a write is refused.

⚠ ``classification`` IS DECLARATIVE AND GATES NOTHING TODAY
===========================================================
The field is stored, returned, and validated against a closed vocabulary —
and it is NOT consulted when deciding who sees a surface. Server-side
visibility resolves on tenant, status, vocabulary, persona and
``required_permission`` only; the caller's clearance is never compared
against this value. A surface registered ``confidential`` is shown to every
persona its registration names, exactly as a ``public`` one is. Use
``personas`` and ``required_permission`` to restrict who sees a surface.
This is recorded rather than implied because a field named
``classification`` on a governance product otherwise reads as an access
control it does not perform. Levels above ``confidential`` are refused by
the writer for the same reason: the model carries no compartment column, so
admitting them would offer a protection level with nothing behind it.

⚠ A ``record_list`` SURFACE HAS NO SUPPORTED API TO POPULATE IT YET
===================================================================
``view_kind="record_list"`` is the only shipped renderer, and the governed
object layer beneath it — the record types and the records themselves — is
schema-only today: it has no handler, no service, no route, and no client
method here or anywhere else in this package. A registered surface therefore
mounts, is navigable, and renders its configured empty state. Registering
surfaces now is still useful (the navigation entry, the permission gate and
the route are real and enforced), but this module cannot create the records
such a surface would list, and no other module can either.

FAIL-CLOSED DEFAULT
===================
``status`` defaults to ``disabled`` server-side. A registration created
without an explicit ``status`` exists, is visible to authors, contributes
nothing to any caller's manifest and mounts no route until it is enabled.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .._http import HTTPClient, encode_path_param

#: Navigation sections a surface may join. Closed server-side — an architect
#: cannot invent a section, so a registration can never create a new region of
#: the product.
NavSection = Literal["BUILD", "WORK", "GOVERN", "OBSERVE"]

#: Personas that may be named on a registration. An empty persona list means no
#: persona, which means invisible (fail-closed).
Persona = Literal["architect", "user", "admin", "executive", "operator"]

#: Shipped renderers. An architect selects one; they never supply a component
#: path, a module name, or code.
ViewKind = Literal["record_list"]

#: Writable classifications. Higher levels are refused — see the module
#: docstring for why. ``internal`` is accepted on write as an alias for
#: ``restricted`` and is canonicalised to ``restricted`` before storage.
Classification = Literal["public", "restricted", "confidential"]

#: ``disabled`` is the default and the fail-closed state.
SurfaceStatus = Literal["disabled", "enabled"]


# ============================================================================
# Response Models (local — mirror the server response shape exactly)
# ============================================================================


class SurfaceManifestEntry(BaseModel):
    """One navigation entry the calling principal may see.

    The rendering projection: exactly what a sidebar and a route need.
    ``organization_id``, provenance and ``required_permission`` are absent by
    design — the manifest is already filtered to entries this caller may see.
    """

    model_config = ConfigDict(populate_by_name=True)

    surface_key: str
    #: Derived server-side as ``/x/{surface_key}``; never stored, never supplied.
    route_path: str
    nav_section: str | None = None
    nav_label: str = ""
    nav_description: str = ""
    icon_key: str = "Layers"
    sort_order: int = 0
    view_kind: str = "record_list"
    view_config: dict[str, Any] = Field(default_factory=dict)
    personas: list[str] = Field(default_factory=list)
    #: Declarative only — see the module docstring. Does not restrict who sees
    #: this entry; the entry is already filtered to those who may see it.
    classification: str = "restricted"


class SurfaceManifest(BaseModel):
    """``GET /api/v1/surface-registry`` — this caller's composed navigation.

    An object rather than a bare array, matching the backend's list-endpoint
    convention: the envelope leaves room for further fields without a
    wire-shape break.
    """

    model_config = ConfigDict(populate_by_name=True)

    surfaces: list[SurfaceManifestEntry] = Field(default_factory=list)


class SurfaceRegistration(BaseModel):
    """The full authoring projection of one registration.

    ⚠ EVERY FIELD BUT ``surface_key`` IS OPTIONAL, AND THAT IS THE WIRE SHAPE,
    NOT DEFENSIVE TYPING. When a stored row no longer satisfies the CURRENT
    server-side vocabulary — because the key pattern was tightened or a key was
    reserved after the row was written — the authoring reads degrade to a short
    row rather than failing the whole list: ``id``, ``organization_id``,
    ``surface_key``, ``route_path`` (null, because it cannot be derived),
    ``nav_label``, ``status``, plus ``unresolvable: true`` and
    ``unresolvable_field``. The row is still shown to its owner so it can be
    repaired or deleted; it is dropped from every caller's manifest. A model
    that required ``nav_section`` would raise on exactly the rows an architect
    most needs to see.
    """

    model_config = ConfigDict(populate_by_name=True)

    surface_key: str
    id: str | None = None
    organization_id: str | None = None
    #: ``None`` on an unresolvable row — the path cannot be derived from a key
    #: today's vocabulary rejects.
    route_path: str | None = None
    nav_section: str | None = None
    nav_label: str = ""
    nav_description: str = ""
    icon_key: str = "Layers"
    sort_order: int = 0
    view_kind: str = "record_list"
    view_config: dict[str, Any] = Field(default_factory=dict)
    required_permission: str | None = None
    personas: list[str] = Field(default_factory=list)
    #: Declarative only — see the module docstring.
    classification: str = "restricted"
    status: str = "disabled"
    #: ⚠ DESCRIPTIVE LABELS, NOT GRANTABLE PERMISSIONS. Derived mechanically
    #: from the key for display in an authoring UI; nothing registers them and
    #: no gate consults them. Enforcement uses ``required_permission``.
    derived_scopes: dict[str, str] = Field(default_factory=dict)
    created_by: str | None = None
    updated_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    #: Present and ``True`` only on a row today's vocabulary rejects.
    unresolvable: bool = False
    #: Which field made the row unresolvable, when it is.
    unresolvable_field: str | None = None


class SurfaceRegistrationListResult(BaseModel):
    """``GET /registrations`` — every registration in the tenant, any status."""

    model_config = ConfigDict(populate_by_name=True)

    registrations: list[SurfaceRegistration] = Field(default_factory=list)


class SurfaceDeleteResult(BaseModel):
    """Confirmation of a soft delete. The row is retained for compliance."""

    model_config = ConfigDict(populate_by_name=True)

    deleted: bool
    surface_key: str


# ============================================================================
# Module
# ============================================================================


class SurfacesModule:
    """
    Architect-tier surface registry — compose a domain surface at runtime.

    One registration is one navigation entry plus one reachable route, scoped
    to the calling principal's organization. ``surface_key`` is unique WITHIN
    a tenant, never globally: two organizations may both register
    ``"finance_exceptions"`` and neither can see the other's.

    Examples:
        >>> # Any persona: what may I see?
        >>> nav = await client.surfaces.manifest()
        >>> for entry in nav.surfaces:
        ...     print(entry.nav_section, entry.nav_label, entry.route_path)

        >>> # Architect/admin/executive persona + surfaces:create
        >>> row = await client.surfaces.create_registration(
        ...     surface_key="finance_exceptions",
        ...     nav_section="GOVERN",
        ...     nav_label="Finance Exceptions",
        ...     personas=["architect", "executive"],
        ...     required_permission="organizations:read",
        ... )
        >>> row.status, row.route_path
        ('disabled', '/x/finance_exceptions')

        >>> # Nothing is live until it is enabled — the default is fail-closed.
        >>> await client.surfaces.update_registration(
        ...     "finance_exceptions", status="enabled"
        ... )
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """
        Initialize the surfaces module.

        Args:
            http_client: HTTPClient instance for API requests
        """
        self._http = http_client

    async def manifest(self) -> SurfaceManifest:
        """
        Get the navigation entries and routes THIS caller may see.

        GET /api/v1/surface-registry

        The per-caller read. It carries no persona restriction — every persona
        needs its own composed navigation — and the admission gate is not what
        protects the data: the server filters by organization, then by
        ``status``, then by vocabulary resolvability, then by persona
        intersection, then by each entry's own ``required_permission``
        evaluated against this caller. Entries the caller may not see are never
        returned, so this cannot be used to enumerate a tenant's surfaces.

        Disabled registrations, and registrations whose stored values no longer
        satisfy the server's vocabulary, are excluded.

        Returns:
            SurfaceManifest: surfaces — sorted by sort_order, then nav_label
        """
        response = await self._http.request("GET", "/api/v1/surface-registry")
        return SurfaceManifest(**response)

    async def list_registrations(self) -> SurfaceRegistrationListResult:
        """
        List every surface registration in the caller's organization.

        GET /api/v1/surface-registry/registrations

        The authoring projection: all statuses including drafts, with ids and
        provenance. Requires an architect/admin/executive persona AND
        ``surfaces:admin`` — holding the persona alone is refused. Scoped
        server-side to the caller's organization; no parameter can widen it.

        Rows the current vocabulary rejects are returned in the short
        ``unresolvable`` form rather than being hidden or raising — see
        :class:`SurfaceRegistration`.

        Returns:
            SurfaceRegistrationListResult: registrations
        """
        response = await self._http.request("GET", "/api/v1/surface-registry/registrations")
        return SurfaceRegistrationListResult(**response)

    async def get_registration(self, surface_key: str) -> SurfaceRegistration:
        """
        Read one surface registration by key.

        GET /api/v1/surface-registry/registrations/{surface_key}

        Requires an architect/admin/executive persona AND ``surfaces:admin``.

        A key belonging to another organization returns 404, identically to a
        key that does not exist — the response cannot be used to probe another
        tenant's key space.

        Args:
            surface_key: The registration's tenant-unique key

        Returns:
            SurfaceRegistration: The full registration row
        """
        response = await self._http.request(
            "GET",
            f"/api/v1/surface-registry/registrations/{encode_path_param(surface_key)}",
        )
        return SurfaceRegistration(**response)

    async def create_registration(
        self,
        surface_key: str,
        nav_section: NavSection,
        nav_label: str,
        nav_description: str | None = None,
        icon_key: str | None = None,
        sort_order: int | None = None,
        view_kind: ViewKind | None = None,
        view_config: dict[str, Any] | None = None,
        required_permission: str | None = None,
        personas: list[Persona] | None = None,
        classification: Classification | None = None,
        status: SurfaceStatus | None = None,
    ) -> SurfaceRegistration:
        """
        Register a new surface — one navigation entry and one route.

        POST /api/v1/surface-registry/registrations

        Requires an architect/admin/executive persona AND ``surfaces:create``.
        The organization is taken from the authenticated principal and can
        neither be supplied nor overridden. The create is audit-logged
        server-side.

        Omitting ``status`` creates the registration ``disabled``: it exists,
        authors can see it, and it contributes nothing to any manifest and
        mounts no route until it is enabled. This is the fail-closed default,
        not an oversight.

        Unknown keys are REJECTED rather than ignored, at the top level and
        inside ``view_config``, so a typo is a 422 and not a silently dropped
        field.

        Args:
            surface_key: Tenant-unique key, 3-64 chars, a leading lowercase
                letter then lowercase alphanumerics and underscores. Immutable
                once created, and the only supplied value that reaches a URL —
                the route is derived from it as ``/x/{surface_key}``.
            nav_section: Which navigation section the entry joins
            nav_label: Menu label, max 64 chars. Sanitized server-side and
                rendered as text, never as markup.
            nav_description: Tooltip / subtitle, max 200 chars, same sanitization
            icon_key: Icon NAME from the server's allowlist of already-bundled
                icons (max 32 chars) — a name, never a URL or a component path.
                Defaults server-side to ``"Layers"``. An unlisted name is a 422
                naming ``icon_key``.
            sort_order: Sort position within the section. Platform navigation
                items always sort ahead of registered surfaces.
            view_kind: Which shipped renderer the route uses. ``record_list`` is
                the only one today, and see the module docstring: the layer that
                would supply its records does not exist yet.
            view_config: Configuration for the selected ``view_kind``. For
                ``record_list``: ``{"columns": [{"key": ..., "label": ...}],
                "empty_message": ...}``. Validated per view kind; unknown keys
                are rejected, not stored.
            required_permission: The permission a caller must hold for this
                entry to appear in their manifest AND for its route to resolve.
                Must be a member of the platform's existing permission catalogue
                — selected, never minted. Defaults server-side to
                ``"organizations:read"``.
            personas: Personas that may see the entry. An empty list means the
                entry is visible to nobody (fail-closed).
            classification: Declarative label only — it does NOT restrict who
                sees the surface. See the module docstring. Defaults server-side
                to ``"restricted"``.
            status: ``"disabled"`` (default) or ``"enabled"``

        Returns:
            SurfaceRegistration: The persisted row, read back server-side after
            the write rather than echoed from the request

        Raises:
            The backend answers 422 naming the refused FIELD, 409 when the key
            already exists in this organization, and 403 when the persona or the
            permission is missing.
        """
        body: dict[str, Any] = {
            "surface_key": surface_key,
            "nav_section": nav_section,
            "nav_label": nav_label,
        }
        if nav_description is not None:
            body["nav_description"] = nav_description
        if icon_key is not None:
            body["icon_key"] = icon_key
        if sort_order is not None:
            body["sort_order"] = sort_order
        if view_kind is not None:
            body["view_kind"] = view_kind
        if view_config is not None:
            body["view_config"] = view_config
        if required_permission is not None:
            body["required_permission"] = required_permission
        if personas is not None:
            body["personas"] = personas
        if classification is not None:
            body["classification"] = classification
        if status is not None:
            body["status"] = status

        response = await self._http.request(
            "POST",
            "/api/v1/surface-registry/registrations",
            json_data=body,
        )
        return SurfaceRegistration(**response)

    async def update_registration(
        self,
        surface_key: str,
        nav_section: NavSection | None = None,
        nav_label: str | None = None,
        nav_description: str | None = None,
        icon_key: str | None = None,
        sort_order: int | None = None,
        view_kind: ViewKind | None = None,
        view_config: dict[str, Any] | None = None,
        required_permission: str | None = None,
        personas: list[Persona] | None = None,
        classification: Classification | None = None,
        status: SurfaceStatus | None = None,
    ) -> SurfaceRegistration:
        """
        Partially update a surface registration.

        PATCH /api/v1/surface-registry/registrations/{surface_key}

        Requires an architect/admin/executive persona AND ``surfaces:update``.
        Only the arguments you pass are sent; anything omitted is left
        untouched. The update is audit-logged server-side.

        ``surface_key`` addresses the row and is NOT a writable field — it is
        immutable, and an attempt to re-point a live URL is refused with a 422
        rather than silently ignored. To change a key, register a new surface
        and delete the old one.

        This is the method that publishes a surface: ``status="enabled"``.

        Args:
            surface_key: The registration to update
            nav_section: New navigation section
            nav_label: New menu label
            nav_description: New tooltip / subtitle
            icon_key: New icon name from the server's allowlist
            sort_order: New sort position
            view_kind: New renderer
            view_config: Replacement view configuration (not merged — the
                supplied object replaces the stored one)
            required_permission: New required permission, from the platform
                catalogue
            personas: Replacement persona list
            classification: New declarative classification — still gates
                nothing; see the module docstring
            status: ``"enabled"`` to publish, ``"disabled"`` to withdraw

        Returns:
            SurfaceRegistration: The updated row, read back after the write
        """
        body: dict[str, Any] = {}
        if nav_section is not None:
            body["nav_section"] = nav_section
        if nav_label is not None:
            body["nav_label"] = nav_label
        if nav_description is not None:
            body["nav_description"] = nav_description
        if icon_key is not None:
            body["icon_key"] = icon_key
        if sort_order is not None:
            body["sort_order"] = sort_order
        if view_kind is not None:
            body["view_kind"] = view_kind
        if view_config is not None:
            body["view_config"] = view_config
        if required_permission is not None:
            body["required_permission"] = required_permission
        if personas is not None:
            body["personas"] = personas
        if classification is not None:
            body["classification"] = classification
        if status is not None:
            body["status"] = status

        response = await self._http.request(
            "PATCH",
            f"/api/v1/surface-registry/registrations/{encode_path_param(surface_key)}",
            json_data=body,
        )
        return SurfaceRegistration(**response)

    async def delete_registration(self, surface_key: str) -> SurfaceDeleteResult:
        """
        Soft-delete a surface registration.

        DELETE /api/v1/surface-registry/registrations/{surface_key}

        Requires an architect/admin/executive persona AND ``surfaces:delete``.
        The row is retained for compliance and stops appearing in reads,
        manifests and routing. The delete is audit-logged server-side.

        A key belonging to another organization returns 404, identically to a
        key that does not exist.

        Args:
            surface_key: The registration to delete

        Returns:
            SurfaceDeleteResult: deleted + surface_key
        """
        response = await self._http.request(
            "DELETE",
            f"/api/v1/surface-registry/registrations/{encode_path_param(surface_key)}",
        )
        return SurfaceDeleteResult(**response)
