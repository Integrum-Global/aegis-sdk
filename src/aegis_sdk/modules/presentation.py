"""
Agentic OS SDK Presentation Module.

Presentations are decks rendered from a validated spec and persisted as an
``AgenticArtifact`` -- served under ``/api/v1/presentations``:

======  ====================================  ==============================
verb    route                                 method
======  ====================================  ==============================
POST    ``/api/v1/presentations``             :meth:`PresentationModule.create`
GET     ``/api/v1/presentations/{id}``        :meth:`PresentationModule.get`
======  ====================================  ==============================

A presentation IS an artifact -- upload, list, version history, download and
delete are already covered by :class:`~aegis_sdk.execution.artifacts.ArtifactsModule`
(``client.artifacts``). This module is only the render-from-spec surface a
plain file upload cannot express: give it a validated spec and a format, get
back a rendered, persisted deck.

Every read is clearance-checked server-side, same as artifacts: another
organization's presentation is reported as not found (404), never as
forbidden, so a refusal does not confirm that it exists.
"""

from __future__ import annotations

from typing import Any

from .._http import encode_path_param

#: The formats the server can render a presentation spec into. Mirrors
#: ``aegis.services.presentation_render.SUPPORTED_PRESENTATION_FORMATS`` --
#: not imported from it (this package ships independently of ``aegis``;
#: see the SDK boundary convention), so if the server ever adds a third
#: format this constant is the one place to update on the client side.
SUPPORTED_PRESENTATION_FORMATS: frozenset[str] = frozenset({"html", "pptx"})


class PresentationModule:
    """
    Render a validated deck spec into a persisted presentation.

    Example:
        >>> async with AgenticOSClient.from_env() as client:
        ...     created = await client.presentation.create(
        ...         "req_abc123",
        ...         format="pptx",
        ...         spec={
        ...             "title": "Q3 Review",
        ...             "slides": [{"title": "Highlights", "bullets": ["Up 12%"]}],
        ...         },
        ...     )
        ...     presentation_id = created["presentation"]["id"]
        ...     fetched = await client.presentation.get(presentation_id)
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def create(
        self,
        request_id: str,
        *,
        format: str,
        spec: dict[str, Any],
        name: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Render ``spec`` for ``format`` and persist it as a presentation.

        Fixed wire route: ``POST /api/v1/presentations``, JSON body.

        There is deliberately **no** ``workspace_id`` argument -- same
        reasoning as :meth:`ArtifactsModule.create`: the workspace is derived
        server-side from ``request_id``, so a caller cannot choose whose
        classification mark a write raises.

        Args:
            request_id: The request this presentation belongs to. Must be a
                request in your organization that is attached to a workspace.
            format: One of :data:`SUPPORTED_PRESENTATION_FORMATS`.
            spec: The deck spec -- ``title``/``subtitle``/``slides``, each
                slide a ``layout``/``title``/``subtitle``/``bullets``/
                ``paragraphs``/``notes`` dict. An unrecognised key anywhere in
                the spec is refused by the server (400), never dropped.
            name: Optional presentation name (the server defaults to a
                generated one).
            session_id: Optional work-session id, recorded for tracking.
            metadata: Optional metadata attached to the artifact record.

        Returns:
            ``{"success": True, "presentation": {...}, "error": None}`` --
            the created record is under ``"presentation"`` (keys as listed on
            :meth:`get`).

        Raises:
            ValidationError: Four DISTINCT, caller-actionable conditions,
                distinguishable by ``exc.error_code`` -- do not branch on
                :attr:`~aegis_sdk.exceptions.AgenticOSError.message`, which
                is prose and may be reworded without notice:

                * The spec is malformed (400, ``exc.error_code`` unset --
                    server-side validation, not this route's own typed
                    refusal).
                * ``format`` names no renderer (400).
                * The spec is well-formed but uses a layout/field ``format``
                    cannot express (422, ``exc.error_code ==
                    "PRESENTATION_SLIDE_FIELD_UNSUPPORTED"``) -- e.g. a
                    ``"title"``-layout slide entry with ``format="pptx"``
                    (only the top-level ``title``/``subtitle`` can make a
                    pptx title slide). CALLER-CORRECTABLE and format-specific:
                    the SAME spec may render successfully under a different
                    ``format``. ``exc.server_details`` carries ``"format"``,
                    ``"index"`` (the 0-based slide position) and ``"field"``
                    -- read those rather than parsing ``exc.message``.
            AuthorizationError: 403 — you are authenticated but not permitted
                to create a presentation. THREE causes, and the response does
                not separate them: your role does not hold the execute
                permission on the agent family; your tenant's access policy
                denies it; or the policy evaluation itself errored, which
                refuses rather than admits. All three are decided BEFORE any
                of your input is looked at, so none is fixed by editing the
                spec, and none is retryable. Note the permission is the
                EXECUTE verb, not create: rendering a deck is modelled as
                running work, not as creating an agent.
            NotFoundError: The request does not exist in your organization.
            AgenticOSError: The request is not attached to any workspace
                (``exc.status_code == 409`` -- the SDK has no dedicated 409
                exception, so this arrives as the base class, same as
                :meth:`ArtifactsModule.create`'s identical case).
            ServiceError: The server failed (5xx) -- a condition the CALLER
                cannot fix by editing the spec, unlike the 422 above.
                ``exc.error_code`` is ``PRESENTATION_RENDERER_UNAVAILABLE``
                when the optional runtime a format needs is not installed,
                ``PRESENTATION_RENDER_UNDETERMINED`` when the renderer
                produced no bytes for a well-formed spec, or
                ``PRESENTATION_CREATE_FAILED`` for any other handled failure.

        Example:
            >>> created = await client.presentation.create(
            ...     "req_abc123",
            ...     format="html",
            ...     spec={"slides": [{"title": "Hello", "bullets": ["World"]}]},
            ... )
        """
        body: dict[str, Any] = {
            "request_id": request_id,
            "format": format,
            "spec": spec,
        }
        if name is not None:
            body["name"] = name
        if session_id is not None:
            body["session_id"] = session_id
        if metadata is not None:
            body["metadata"] = metadata

        return await self._http.request("POST", "/api/v1/presentations", json_data=body)

    async def get(self, presentation_id: str) -> dict[str, Any]:
        """
        Get one presentation's metadata.

        Fixed wire route: ``GET /api/v1/presentations/{presentation_id}``.

        Args:
            presentation_id: The presentation (artifact) id.

        Returns:
            The presentation record: ``id``, ``name``, ``artifact_type``
            (the rendered format), ``mime_type``, ``size_bytes``,
            ``request_id``, ``organization_id``, ``workspace_id``,
            ``classification`` and ``created_at``.

        Raises:
            NotFoundError: No such presentation in your organization -- also
                returned for an id that names an artifact of a different
                (non-presentation) type, so this route cannot be used to
                probe for artifacts outside the presentation surface.
            AuthorizationError: 403, with FOUR causes the response does not
                separate. Three are decided before the artifact is even read:
                your role does not hold the read permission on the agent
                family, your tenant's access policy denies it, or the policy
                evaluation errored and therefore refused. The fourth is the
                original one — the presentation is in your tenant, but your
                clearance does not reach its classification.

                ⚠ This entry read "your clearance does not reach this
                presentation" until the route was gated, and that is now only
                one cause in four. Do not diagnose a 403 here as a clearance
                problem before confirming the caller holds the permission:
                the older reading sends you to the clearance axis to find
                nothing wrong with your clearance.
        """
        return await self._http.request(
            "GET", f"/api/v1/presentations/{encode_path_param(presentation_id)}"
        )


__all__ = ["PresentationModule", "SUPPORTED_PRESENTATION_FORMATS"]
