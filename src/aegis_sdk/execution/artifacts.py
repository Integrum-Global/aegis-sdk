"""
Agentic OS SDK Artifacts Module.

Artifacts are the files produced against a request -- by an agent or by a user
-- together with their version chain. They are served under
``/api/v1/artifacts``:

======  ==========================================  ===========================
verb    route                                       method
======  ==========================================  ===========================
POST    ``/api/v1/artifacts``                       :meth:`ArtifactsModule.create`
GET     ``/api/v1/artifacts``                       :meth:`ArtifactsModule.list`
GET     ``/api/v1/artifacts/{artifact_id}``         :meth:`ArtifactsModule.get`
GET     ``/api/v1/artifacts/{artifact_id}/versions``  :meth:`ArtifactsModule.get_versions`
POST    ``/api/v1/artifacts/{artifact_id}/supersede`` :meth:`ArtifactsModule.supersede`
GET     ``/api/v1/artifacts/{artifact_id}/download``  :meth:`ArtifactsModule.download`
DELETE  ``/api/v1/artifacts/{artifact_id}``         :meth:`ArtifactsModule.delete`
======  ==========================================  ===========================

Every read is clearance-checked server-side. An artifact carries an EATP
classification (``public`` / ``restricted`` / ``confidential`` / ``secret`` /
``top_secret``, or ``None`` for an artifact that predates classification), and a
caller whose clearance does not reach it is refused with
:class:`~aegis_sdk.exceptions.AuthorizationError` (403). Another organization's
artifact is reported as not found (404), never as forbidden, so a refusal does
not confirm that it exists.

Responses are returned as the server emits them (plain ``dict`` / ``list``);
the artifact record keys are listed on :meth:`ArtifactsModule.get`.
"""

from __future__ import annotations

import json
from typing import Any

from .._http import encode_path_param

_DEFAULT_CONTENT_TYPE = "application/octet-stream"


class ArtifactsModule:
    """
    Artifact upload, retrieval, versioning, download and deletion.

    Example:
        >>> async with AgenticOSClient.from_env() as client:
        ...     created = await client.artifacts.create(
        ...         "req_abc123",
        ...         b"region,revenue\\nemea,42\\n",
        ...         "revenue.csv",
        ...         content_type="text/csv",
        ...     )
        ...     artifact_id = created["artifact"]["id"]
        ...     data = await client.artifacts.download(artifact_id)
    """

    def __init__(self, http_client):
        """Initialize with HTTP client."""
        self._http = http_client

    async def create(
        self,
        request_id: str,
        file_content: bytes,
        filename: str,
        *,
        name: str | None = None,
        artifact_type: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a new artifact and attach it to a request.

        Fixed wire route: ``POST /api/v1/artifacts``, ``multipart/form-data``.
        The file travels as the ``file`` part; ``request_id``, ``name``,
        ``artifact_type``, ``session_id`` and ``metadata`` travel as form
        fields. Optional fields you do not pass are omitted from the form, so
        the server's own defaults apply.

        There is deliberately **no** ``workspace_id`` argument. The workspace
        an artifact belongs to is derived on the server from the request it is
        attached to. Letting a caller name the workspace would let them choose
        whose classification mark an upload raises, so the platform does not
        accept one on this route; sending it would be ignored.

        Args:
            request_id: The request this artifact belongs to. Must be a request
                in your organization that is attached to a workspace.
            file_content: Raw bytes of the file.
            filename: Filename of the upload. Used as the artifact ``name``
                when ``name`` is not given, and its extension as the
                ``artifact_type`` when ``artifact_type`` is not given.
            name: Optional artifact name (the server defaults to ``filename``).
            artifact_type: Optional type, e.g. ``"csv"``, ``"xlsx"``, ``"md"``
                (the server auto-detects it from the filename extension).
            session_id: Optional work-session id, recorded for tracking.
            metadata: Optional metadata. Serialized to the JSON string the
                route's ``metadata`` form field expects.
            content_type: Optional MIME type of the upload part (defaults to
                ``application/octet-stream``).

        Returns:
            ``{"success": True, "artifact": {...}, "error": None}`` -- the
            created artifact record is under ``"artifact"`` (keys as listed on
            :meth:`get`).

        Raises:
            NotFoundError: The request does not exist in your organization.
            AgenticOSError: The request is not attached to any workspace
                (``exc.status_code == 409``; the SDK has no dedicated 409
                exception, so this arrives as the base class).
            ValidationError: The upload was refused as invalid (400) --
                including a classification the request's workspace cannot hold,
                whose message says so.
            ServiceError: The server failed (5xx). ``exc.error_code`` is
                ``ARTIFACT_STORAGE_UNAVAILABLE`` when a store the upload
                depends on (file storage or the database) could not be
                reached, ``ARTIFACT_CREATE_FAILED`` for any other handled
                failure, and ``INTERNAL_ERROR`` for a platform defect.

        Example:
            >>> created = await client.artifacts.create(
            ...     "req_abc123",
            ...     b"# Findings\\n",
            ...     "findings.md",
            ...     metadata={"source": "weekly-review"},
            ... )
            >>> print(created["artifact"]["classification"])
        """
        form: dict[str, str] = {"request_id": request_id}
        if name is not None:
            form["name"] = name
        if artifact_type is not None:
            form["artifact_type"] = artifact_type
        if session_id is not None:
            form["session_id"] = session_id
        if metadata is not None:
            form["metadata"] = json.dumps(metadata)

        return await self._http.request(
            "POST",
            "/api/v1/artifacts",
            data=form,
            files={
                "file": (filename, file_content, content_type or _DEFAULT_CONTENT_TYPE)
            },
        )

    async def list(
        self,
        request_id: str | None = None,
        workspace_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List the artifacts you may see, newest first.

        Fixed wire route: ``GET /api/v1/artifacts``. Two scopes:

        * with ``request_id`` -- every artifact attached to that request;
        * without it -- your organization's artifacts, optionally narrowed to
          one ``workspace_id``.

        Artifacts your clearance does not reach are omitted from either scope.
        Only the arguments you pass are sent.

        Args:
            request_id: Restrict to one request.
            workspace_id: Restrict the organization scope to one workspace.
                The server refuses (400) ``workspace_id`` together with
                ``request_id``: a request already belongs to exactly one
                workspace.
            limit: Maximum number of artifacts. Must be at least 1.

        Returns:
            A list of artifact records (keys as listed on :meth:`get`).

        Example:
            >>> for a in await client.artifacts.list(request_id="req_abc123"):
            ...     print(a["name"], a["artifact_version"])
        """
        params: dict[str, Any] = {}
        if request_id is not None:
            params["request_id"] = request_id
        if workspace_id is not None:
            params["workspace_id"] = workspace_id
        if limit is not None:
            params["limit"] = limit

        return await self._http.request("GET", "/api/v1/artifacts", params=params or None)

    async def get(self, artifact_id: str) -> dict[str, Any]:
        """
        Get one artifact's metadata.

        Fixed wire route: ``GET /api/v1/artifacts/{artifact_id}``.

        Args:
            artifact_id: The artifact id.

        Returns:
            The artifact record: ``id``, ``name``, ``artifact_type``,
            ``mime_type``, ``size_bytes``, ``artifact_version``,
            ``supersedes_artifact_id``, ``change_description``,
            ``created_by_id``, ``created_by_type``, ``request_id``,
            ``organization_id``, ``workspace_id``, ``classification`` and
            ``created_at``.

        Raises:
            NotFoundError: No such artifact in your organization.
            AuthorizationError: Your clearance does not reach this artifact.
        """
        return await self._http.request(
            "GET", f"/api/v1/artifacts/{encode_path_param(artifact_id)}"
        )

    async def get_versions(self, artifact_id: str) -> dict[str, Any]:
        """
        Get an artifact's version history, oldest to newest.

        Fixed wire route: ``GET /api/v1/artifacts/{artifact_id}/versions``.

        Every version is clearance-checked individually, so a version you may
        not see is omitted. ``artifact_version`` values are returned as stored
        and are NOT renumbered, which means a gap (``1, 2, 4``) is expected
        when a version was withheld.

        Args:
            artifact_id: Any artifact id in the chain.

        Returns:
            ``{"success": True, "versions": [...], "total": int, "error": None}``
            -- ``total`` counts only the versions returned.

        Raises:
            NotFoundError: No such artifact in your organization.
            AuthorizationError: Your clearance does not reach this artifact.
        """
        return await self._http.request(
            "GET", f"/api/v1/artifacts/{encode_path_param(artifact_id)}/versions"
        )

    async def supersede(
        self,
        artifact_id: str,
        file_content: bytes,
        change_description: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a new version that supersedes an artifact.

        Fixed wire route: ``POST /api/v1/artifacts/{artifact_id}/supersede``,
        ``multipart/form-data`` with a ``file`` part and a
        ``change_description`` form field. The new version keeps the
        predecessor's name and type, takes the next version number, and
        inherits the predecessor's classification as a floor.

        Args:
            artifact_id: The artifact being superseded.
            file_content: Raw bytes of the new version.
            change_description: What changed in this version.
            filename: Optional filename for the upload part (defaults to the
                artifact id; the server does not use it for naming).
            content_type: Optional MIME type of the upload part.

        Returns:
            ``{"success": True, "artifact": {...}, "error": None}`` for the new
            version.

        Raises:
            NotFoundError: No such artifact.
            AuthorizationError: The artifact belongs to another organization.
            ValidationError: The new version was refused as invalid (400).
        """
        return await self._http.request(
            "POST",
            f"/api/v1/artifacts/{encode_path_param(artifact_id)}/supersede",
            data={"change_description": change_description},
            files={
                "file": (
                    filename or artifact_id,
                    file_content,
                    content_type or _DEFAULT_CONTENT_TYPE,
                )
            },
        )

    async def download(self, artifact_id: str) -> bytes:
        """
        Download an artifact's bytes.

        Fixed wire route: ``GET /api/v1/artifacts/{artifact_id}/download``.
        The body is the file itself (served as an attachment), so it is
        returned as raw ``bytes`` and never parsed -- a JSON artifact comes
        back as its bytes, not as a ``dict``.

        Args:
            artifact_id: The artifact id.

        Returns:
            The artifact's content.

        Raises:
            NotFoundError: No such artifact in your organization.
            AuthorizationError: Your clearance does not reach this artifact.
            ServiceError: The server holds the record but cannot reach its
                bytes (``exc.error_code == "ARTIFACT_BYTES_UNAVAILABLE"``).
            AgenticOSError: The artifact exceeds the download cap
                (``exc.status_code == 413``, ``exc.error_code ==
                "ARTIFACT_TOO_LARGE"``).
        """
        return await self._http.request(
            "GET",
            f"/api/v1/artifacts/{encode_path_param(artifact_id)}/download",
            raw_response=True,
        )

    async def delete(self, artifact_id: str) -> dict[str, Any]:
        """
        Soft-delete an artifact.

        Fixed wire route: ``DELETE /api/v1/artifacts/{artifact_id}``. The
        record is marked deleted, not physically removed.

        Args:
            artifact_id: The artifact id.

        Returns:
            ``{"success": True, "deleted": bool, "error": None}``.

        Raises:
            NotFoundError: No such artifact.
            AuthorizationError: The artifact belongs to another organization.
        """
        return await self._http.request(
            "DELETE", f"/api/v1/artifacts/{encode_path_param(artifact_id)}"
        )
