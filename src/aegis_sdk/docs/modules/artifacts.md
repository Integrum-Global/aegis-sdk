# Artifacts Module

The `ArtifactsModule` (`client.artifacts`) manages artifacts -- the files produced against a request, by an agent or by a user -- and their version chains.

## Access

```python
from aegis_sdk import AgenticOSClient

async with AgenticOSClient.from_env() as client:
    artifacts_module = client.artifacts
```

## Routes

| Method | Route | Returns |
|--------|-------|---------|
| `create(request_id, file_content, filename, ...)` | `POST /api/v1/artifacts` | `{"success", "artifact", "error"}` |
| `list(request_id=None, workspace_id=None, limit=None)` | `GET /api/v1/artifacts` | `list[dict]` |
| `get(artifact_id)` | `GET /api/v1/artifacts/{artifact_id}` | `dict` |
| `get_versions(artifact_id)` | `GET /api/v1/artifacts/{artifact_id}/versions` | `{"success", "versions", "total", "error"}` |
| `supersede(artifact_id, file_content, change_description, ...)` | `POST /api/v1/artifacts/{artifact_id}/supersede` | `{"success", "artifact", "error"}` |
| `download(artifact_id)` | `GET /api/v1/artifacts/{artifact_id}/download` | `bytes` |
| `delete(artifact_id)` | `DELETE /api/v1/artifacts/{artifact_id}` | `{"success", "deleted", "error"}` |

Responses are returned as the server emits them, as plain dictionaries.

## The Artifact Record

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Artifact ID |
| `name` | `str` | Artifact name |
| `artifact_type` | `str` | Type (`csv`, `xlsx`, `md`, ...) |
| `mime_type` | `str` | MIME type |
| `size_bytes` | `int` | Size of the content |
| `artifact_version` | `int` | Version number within the chain |
| `supersedes_artifact_id` | `str \| None` | The version this one replaced |
| `change_description` | `str` | What changed in this version |
| `created_by_id` | `str` | Creator (agent or user) |
| `created_by_type` | `str` | `"agent"` or `"user"` |
| `request_id` | `str` | The request it is attached to |
| `organization_id` | `str` | Owning organization |
| `workspace_id` | `str` | Owning workspace |
| `classification` | `str \| None` | EATP classification; `None` for an artifact that predates classification |
| `created_at` | `str` | Creation timestamp |

## Upload an Artifact

```python
created = await client.artifacts.create(
    "req_abc123",
    b"region,revenue\nemea,42\n",
    "revenue.csv",
    content_type="text/csv",
    metadata={"source": "weekly-review"},
)
artifact = created["artifact"]
```

The upload is `multipart/form-data`. `name` defaults to the filename and `artifact_type` to the filename's extension.

**There is no `workspace_id` argument.** The workspace an artifact belongs to is derived by the server from the request it is attached to. A caller-named workspace would let the caller choose whose classification mark an upload raises, so the platform does not accept one.

| Outcome | Status | SDK exception |
|---------|--------|---------------|
| Created | `201` | -- |
| Request not in your organization | `404` | `NotFoundError` |
| Request has no workspace | `409` | `AgenticOSError`, `status_code == 409` |
| Invalid upload, or a classification the workspace cannot hold | `400` | `ValidationError` |
| A backing store (file storage or database) was unreachable | `500` | `ServiceError`, `error_code == "ARTIFACT_STORAGE_UNAVAILABLE"` |
| Any other handled failure | `500` | `ServiceError`, `error_code == "ARTIFACT_CREATE_FAILED"` |
| Platform defect | `500` | `ServiceError`, `error_code == "INTERNAL_ERROR"` |

## List Artifacts

```python
# Everything attached to one request
for a in await client.artifacts.list(request_id="req_abc123"):
    print(a["name"], a["artifact_version"])

# Your organization's artifacts in one workspace
recent = await client.artifacts.list(workspace_id="ws_abc", limit=20)
```

Passing both `request_id` and `workspace_id` is refused (`400`): a request already belongs to exactly one workspace.

## Versions and Supersede

```python
history = await client.artifacts.get_versions(artifact["id"])
for v in history["versions"]:
    print(v["artifact_version"], v["change_description"])

updated = await client.artifacts.supersede(
    artifact["id"],
    b"region,revenue\nemea,43\n",
    "Corrected EMEA revenue",
)
```

Each version is clearance-checked individually, so a version you may not see is left out. Version numbers are not renumbered: a gap such as `1, 2, 4` is expected when a version was withheld.

## Download and Delete

```python
content: bytes = await client.artifacts.download(artifact["id"])
await client.artifacts.delete(artifact["id"])
```

`download` always returns raw bytes, including for JSON artifacts. `delete` is a soft delete.

## Access Control

Reads are checked against your clearance. An artifact your clearance does not reach raises `AuthorizationError` (`403`). An artifact in another organization raises `NotFoundError` (`404`), so a refusal never confirms that it exists.
