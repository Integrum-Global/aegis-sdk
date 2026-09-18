# Aegis SDK Changelog

This SDK is versioned independently of the Aegis platform it talks to. The
version here is the SDK's own; it is not the server's.

## Unreleased

### Added — the first runnable pipeline example

`examples/build_a_pipeline.py` is the SDK's first pipeline example. The five that
shipped before it cover agents, trust, streaming and error handling; none showed
a pipeline, so the one surface where node types actually get used had no worked
code at all.

It walks the whole path in one file: ask the deployment which node types it has,
filter to the ones whose verdict says they will run, build a graph from those,
validate it, and execute it. It stops early — with the catalogue's own
`unavailable_reason` — rather than assembling a graph the deployment cannot run.

Two things it demonstrates that the surrounding docs only assert:

- **Filter to executable types BEFORE building.** A graph built from
  non-executable types passes `validate()` and refuses at execution, because
  validation and execution ask different questions. Building first is a slow way
  to learn what the catalogue already said.
- **Read `warnings` as well as `valid`.** Several real defect classes are
  warnings by deliberate severity contract, and a warning never flips `valid` to
  `False`.

The handbook's pipeline chapter gained the matching walkthrough, so the
discovery section and the construction section now connect to each other.

### Fixed — the node-type catalogue could never be read

`client.pipelines.list_node_types()` raised on every call. It asserted that
`GET /api/v1/pipelines/node-types` answers a flat list; the route answers a
category-structured object. So a caller asking which nodes their deployment
offers got a `ServiceError` — and the message named only the payload's _type_,
which was true and left the reader unable to tell which side had moved.

Nothing caught it because nothing called it. There was no caller anywhere in the
package and no test of the method. A method that always raises looks exactly
like a method nobody uses, until a customer is the first to find out.

It now returns a `NodeTypeCatalog` built from what the server actually sends,
**keeping the executability fields rather than flattening them away** — "will my
pipeline run?" is the question the catalogue exists to answer, and a plain list
of nodes discards it:

- `total_types` — the palette: what this deployment offers on its canvas.
- `node_types` — the whole pipeline vocabulary, each type carrying its own
  verdict. A type can appear here and still refuse to run, and `fabricates`
  distinguishes a loud refusal from a node that emits a diagnostic string **as
  its output** and feeds it downstream. A surface rendering those two the same
  way is how a fabricated result reaches a client.
- `executable` / `unavailable_reason` — stated once for the palette, because a
  deployment unable to run its own palette is a configuration, not a defect.

Two things to know when upgrading:

- **Return type change.** This returned `list[dict]`; it now returns
  `NodeTypeCatalog`. No caller inside the package used it, so nothing here
  breaks — code outside that read the old shape must be updated.
- **The old docstring described fields the server never sent.** It promised
  `origin`, `citation`, `binding`, and per-node `params` / `inputs` / `outputs`.
  The server sends none of them, and cannot yet — the node registry exposes no
  per-node parameter schema to Python. Do not write against those fields.

### Fixed — `workspace_id` may be `None` on six response models

Servers that removed the Workspace entity keep the `workspace_id` key on their
responses but always send it as `null`. The SDK declared it a required `str` on
`Agent`, `ToolAgent`, `Pipeline`, `Objective`, `ScopedBridge` and
`ExternalAgent`, so every response carrying one of them failed validation.

The worst symptom was `client.agents.create()`: the server created the agent,
then the SDK raised `ValidationError` reading the reply. A caller saw a failure,
retried, and left a duplicate behind each time. `agents.get()` and
`agents.list()` failed outright on every agent such a deployment held.

The field is now `str | None` on all six, and `client.objectives` no longer turns
a null into `""`. Two things to know when upgrading:

- **Type change.** Code that assumed a `str` (for example
  `agent.workspace_id.startswith(...)`) must handle `None`; a strict type checker
  will now flag it.
- **Do not use it as a filter.** List methods omit the filter when you pass
  `None`, so `agents.list(workspace_id=agent.workspace_id)` returns the whole
  organization rather than one workspace.

`agents.create()` still requires `workspace_id`, because those servers still
require it on the request.

### Added — `client.mcp`, an MCP capability surface

Reported by a partner, in their words: the installed SDK exposed no MCP verb at
all — no module, class or method name contained `mcp`. That was accurate. The
platform has carried an MCP client for some time; nothing in this package could
reach it, so the capability existed and the party who reported it could not call
it.

`client.mcp` registers MCP servers and attaches them to agents. The shape worth
knowing before you read the reference: **registration and binding are two
separate acts with two separate bodies.** Registering a server stores its
endpoint and credential and attaches it to nobody; an agent receives its tools
only when a binding references that registration. `bind` therefore takes no
`url`, `headers` or `command` — a row carrying a reference and inline connection
settings is refused, so those parameters do not exist on it. `bind_inline` is
the self-contained form.

The partner's second observation was also accurate and is unchanged by design:
an endpoint is resolved at registration time, and loopback, link-local,
cloud-metadata and private ranges are refused. The platform is what reaches the
server, so an address only you can reach is not one it can use — which does mean
an MCP server on your own machine cannot be registered. Expose it at an address
the deployment can reach.

See [modules/mcp.md](docs/modules/mcp.md).

### Fixed — the 2.0.0 note on `governance_explain` advertised a capability the module does not have

The 2.0.0 highlights below described it as _"ask why a specific action was
refused, instead of inferring it from a 403."_ It cannot do that, and the module
says so in its own docstring: it never sees the action that was refused. It
evaluates an item **you describe** — a dry run in which nothing is read from a
stored record and nothing is recorded as an access — so the verdict is only as
good as the item you pass, and its subject is a role plus a knowledge item rather
than a connector or a tool. The 2.0.0 entry is corrected in place rather than
merely superseded here: a description of a shipped capability is a claim about
the product, and a reader who skims one highlights list must not find two
answers in it.

### Added — `client.dataflow`: the data-lineage surface, restored as a real API surface

`aegis_sdk.dataflow` returns, in a form that answers the review that quarantined
the old package: ten live routes the SDK could not previously
address — the invocation-lineage router (`/api/v1/lineage/*`: `list`, `graph`,
`export`, `get`, `redact_user`) and the data-governance lineage graph
(`/api/v1/data-governance/lineage/*`: `create_node`, `get_node`, `upstream`,
`downstream`, `create_edge`) — derived from the server's own route
registrations, with no simulation and no standalone reimplementation. The old
10,899-line package, a fail-open simulation stub with zero kailash imports, was
deleted rather than restored (recoverable from git history). `lineage.get()`
percent-encodes its id and refuses the reserved literals `graph` and `export`
outright, so a literal route can never be silently addressed as an id. The 2.0.0
entry below said "No replacement — open an issue with your use case": this is
the replacement.

### Added — `client.organizations`: the one-time token fields the server already emits

`Organization` gains `access_token`, `refresh_token` (both `repr=False`),
`token_type` and `expires_in`. The server returns them on create and the SDK
silently dropped them, so a partner had a token it could never read back.

### Added — `client.directives`: typed `classification`

`Directive` gains `classification: str = "public"`, matching the server's
response model (a prior audit finding). Without it a RESTRICTED and a PUBLIC directive
parsed byte-identically and an operator could not verify what they had set.

### Fixed — `contexts.update()` sent a bodiless PUT and `tools.update()` could reach only one of five fields

`contexts.update()` with no fields sent `json=None` against a REQUIRED
`UpdateContextRequest` body and was refused with 422 before the handler for
every input; it now raises `ValueError` naming the usable fields (an EMPTY
object is the server's own 400, a different and correct refusal). `tools.update()`
accepted only `config`, leaving four of `UpdateToolRequest`'s five fields
unreachable; it now accepts `tool_type`, `name`, `description` and `is_enabled`
as optional keyword arguments, `config` still first and positional.

### Fixed — every file upload was sent as JSON and refused by the server

`HTTPClient` installed `Content-Type: application/json` as a client-wide default
header, and httpx keeps an existing Content-Type instead of the
`multipart/form-data; boundary=…` it computes for `files=`. Every upload therefore
went out labelled as JSON with no boundary, and the server answered 422
`body.file Field required` on every call. Affected: `client.artifacts.create`,
`client.artifacts.supersede`, `client.settings.preview_import`,
`client.settings.import_settings` and `client.agents.register_from_manifest_upload`.
The JSON default is now applied per request, only when httpx does not type the
body itself; JSON, raw-content and bodyless requests are unchanged, and a
Content-Type you pass explicitly still wins.

### Added — `client.artifacts`: the artifacts surface was unreachable from the SDK

The platform's `/api/v1/artifacts` routes had no SDK method at all, so a partner
could list a session's or an objective's artifacts but could not upload one
against a request, read its version history, supersede it, download it or delete
it. `ArtifactsModule` covers all seven routes:

| method                                                                                                   | route                                            |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `create(request_id, file_content, filename, *, name, artifact_type, session_id, metadata, content_type)` | `POST /api/v1/artifacts`                         |
| `list(request_id=None, workspace_id=None, limit=None)`                                                   | `GET /api/v1/artifacts`                          |
| `get(artifact_id)`                                                                                       | `GET /api/v1/artifacts/{artifact_id}`            |
| `get_versions(artifact_id)`                                                                              | `GET /api/v1/artifacts/{artifact_id}/versions`   |
| `supersede(artifact_id, file_content, change_description, *, filename, content_type)`                    | `POST /api/v1/artifacts/{artifact_id}/supersede` |
| `download(artifact_id)` → `bytes`                                                                        | `GET /api/v1/artifacts/{artifact_id}/download`   |
| `delete(artifact_id)`                                                                                    | `DELETE /api/v1/artifacts/{artifact_id}`         |

`create` has **no `workspace_id` argument, on purpose.** The workspace is derived
on the server from the request the artifact is attached to; a caller-named
workspace would let the caller choose whose classification mark an upload raises.

Server-side changes that arrived with it, visible through this module:

- **Uploading an artifact works.** `POST /api/v1/artifacts` previously failed
  with a 500 on every call. It now answers **201**; a request that has no
  workspace answers 409, and one that is not in your organization answers 404.
- **Upload failures are distinguishable.** An unreachable backing store (file
  storage or database) carries
  `exc.error_code == "ARTIFACT_STORAGE_UNAVAILABLE"`, any other handled failure
  `ARTIFACT_CREATE_FAILED`, and a platform defect the generic `INTERNAL_ERROR`.
  All three were previously the same 500 with the same message.

### Added — permanent delete, and two resources that had no delete at all

The server has always offered `?hard=true` on seven routers. The SDK reached
four of them. These three close the gap:

- **`auth.delete_api_key(key_id, hard=False)`** now takes `hard`. The server's
  `DELETE /api/v1/api-keys/{id}` declares `hard: bool = Query(False)` and this
  method had no parameter to express it, so a partner holding this SDK could not
  permanently delete an API key by any means.
- **`org_standup.delete_unit(unit_id, hard=False)`** — NEW. There was previously
  no way to delete an organization unit from this SDK at all.
- **`org_standup.delete_role(role_id, hard=False)`** — NEW. Likewise for an
  organization role. Note this is the ORG-CHART role at
  `/api/v1/organization-roles`, not `role_admin.delete()`'s RBAC role at
  `/api/v1/roles`; the two routers are distinct and an id from one does not
  resolve on the other.

The last two are why a rehearsal tenant could be built and never reset: the
structure could be created and not removed.

`hard=True` is IRREVERSIBLE and takes the audit history with it; the default is
unchanged (soft delete / archive) on all three. `revoke_api_key()` deliberately
does NOT forward `hard` — "revoke" names the soft operation, and a
`revoke_api_key(..., hard=True)` would be a permanent delete wearing the
vocabulary of a reversible one.

`delete_unit` additionally fails closed with `409` when a delegate agent in the
unit holds unsettled trust; on that response the unit is left completely
untouched, so the call is safe to retry.

### Fixed — five calls that could never succeed against a canon server

Each of these reached a route or a body shape the server does not serve, so
the call failed on every invocation. Each is now checked against the server's
real router and request models.

- **`pipelines.execute()` returned 404 on every call.** It POSTed
  `/api/v1/pipelines/{id}/execute`, which no router declares. It now starts the
  run at `POST /api/v1/executions/start` and reads the finished record back from
  `GET /api/v1/pipelines/{id}/executions/{execution_id}`; the return type is
  unchanged (`PipelineExecution`).
- **`pipelines.list_executions(status=...)` returned 400 on every call.** The
  route refuses a `status` parameter. The SDK now filters client-side across
  every page, so `total` and `has_next` describe the filtered set. An unknown
  status raises `ValueError` before any request.
- **`agents.contexts.create()` and `agents.tools.add()` returned 422 on every
  call.** The server requires `content_type` + `content` for a context and
  `name` + `description` for a tool; the SDK sent neither.
- **`agents.versions.create()` without a changelog returned 422.** It sent no
  body; the route requires a JSON object even when every field is optional.
- **`tool_agents.invoke()` could not reach built-in tool dispatch.** It now
  accepts `tool_name`, `tool_arguments` and `action_type`, and
  `ToolAgentInvocationResult.dispatch_path` (`"llm"` or `"builtin_tool"`) is
  retained instead of being dropped.

### Deprecated — migration

- `agents.contexts.create(agent_id, name, config)`: `config` was never a field
  the server reads. Passing it emits `DeprecationWarning`; pass
  `content_type=` and `content=` instead. It will be removed in the next minor
  release.
- `pipelines.execute(..., wait=...)`: the server has no asynchronous start, so
  `wait` changed nothing. Passing it emits `DeprecationWarning`; omit it. It will
  be removed in the next minor release.

### Fixed — every server error was parsed against a wire shape the platform never sends

The client read errors in FastAPI's flat `{"detail": ...}` shape. Aegis
registers a global exception handler, so **every** error it returns is re-wrapped
into a canonical envelope before it leaves the server:

```json
{"error": {"code": "FORBIDDEN", "message": "...", "details": {...}, "request_id": "..."}}
```

Read flat, that envelope produced three wrong answers at once, none of them
loud:

- **`str(exc)` rendered a Python dict repr**, not the message. `exc.message`
  was the whole inner dict rather than a string, so a log line or a user-facing
  error printed `{'code': 'FORBIDDEN', 'message': ...}`.
- **`exc.details["code"]` was `None` on every error the platform raises**, even
  though the server sends a code on all of them.
- **Every structured field the server attached was discarded** —
  `exc.details["details"]` was `None` even when the server populated it. This is
  the load-bearing one: it is the channel a caller branches on, and it was dead,
  which left string-matching an English sentence as the only way to tell two
  refusals apart.

Both shapes are now supported. The envelope is recognised by an `error` key
holding a **dict**; anything else takes the flat path unchanged, so a gateway,
proxy or non-Aegis server answering in FastAPI's default shape parses exactly as
before. An `error` key holding a plain _string_ is not an envelope and is read as
the message.

Two behaviours changed as a consequence, both deliberate:

- An error body carrying no message at all (`{}`, or a body with unrecognised
  keys) now raises with the per-status default — `'Insufficient permissions'` for
  a `403` — instead of the literal string `'None'`.
- `exc.details["message"]` is passed through **verbatim** and is not coerced to
  `str`. A `422` carries a _list_ of per-field validation objects there, which
  callers iterate; stringifying it would have destroyed the most useful error
  body the API produces while looking like a tidy-up.

### Added — `error_code`, `server_details`, `request_id` and `status_code` on every SDK error

`AgenticOSError` (and therefore every SDK exception) now exposes the server's
structured refusal data as attributes, so a caller can branch on a denial
instead of parsing its prose:

| attribute        | what it holds                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| `error_code`     | the server's code (`'FORBIDDEN'`, `'DEPENDENCY_UNAVAILABLE'`, …), or `None` for an error raised locally |
| `server_details` | the structured fields sent beside the message; `{}` when none                                           |
| `request_id`     | the server's correlation id, when supplied                                                              |
| `status_code`    | the HTTP status, or `None` for a local failure                                                          |

```python
except AgenticOSError as exc:
    if exc.error_code == "DEPENDENCY_UNAVAILABLE":
        dependency = exc.server_details.get("dependency")   # retryable; not about your agent
```

These are projections of `exc.details`, which is unchanged — `exc.details["status_code"]`
and every other existing spelling keeps working. They are plain attributes rather
than properties so that `ServiceUnavailableError`, which takes an explicit
`error_code`, can keep overwriting the projection after calling `super()`.

**A missing key in `server_details` is UNDETERMINED, not the negative case.**
Several platform refusal paths still serialise only a prose sentence, so their
structured half arrives empty. An absent key means the server did not attach one
— never that the answer is "no".

The first discriminator to ride this channel is on agent execution, landed in the
same change as the parsing fix above. A governance refusal on the temporal
dimension now carries `server_details['unverifiable_scope']`:

| value           | what it means                                                                               | what to do                           |
| --------------- | ------------------------------------------------------------------------------------------- | ------------------------------------ |
| `'apparatus'`   | the constraint store could not be queried at all; **no restriction of yours was evaluated** | escalate as a platform outage; retry |
| `'subject'`     | your agent's own stored restriction could not be read                                       | fix the agent's configuration        |
| `'unspecified'` | the server denied but attached no kind                                                      | UNDETERMINED — treat as either       |

Both kinds are still a **refusal**, and that is deliberate: an unverifiable
restriction is not a safe restriction, so neither value is an allow. What changed
is that a partner can tell an outage from a restriction without string-matching
an English sentence. See
`handbook/04-the-api-surface/02-errors-and-refusals.md`.

## [2.0.0] — 2026-09-14

The first cut of this SDK under a version number. Everything below is the
difference between `2.0.0` and the `1.0.0` that `aegis_sdk.__version__` has
reported until now.

**Read the Breaking Changes first.** Two public subpackages are gone with no
compatibility shim, several trust methods changed their first parameter, and a
handful of methods that used to return a value now raise. If you have code
running against `1.0.0`, it will not all keep working.

**Why a major bump.** We cannot establish that no consumer is pinned at
`1.0.0` — the SDK sends its own version on every request (`X-SDK-Version`), so
one may exist. Removals without a shim and signature changes are breaking under
semantic versioning whether or not anyone is currently affected. `2.0.0` costs
nothing if nobody is, and is the only honest number if somebody is.

### Breaking Changes

**Two subpackages were removed outright.**

- **`aegis_sdk.kaizen`** is gone. It shipped an agent-signature/journey/memory
  toolkit that duplicated capability the platform now exposes over HTTP. The
  name also left the top-level `__all__`, so `from aegis_sdk import kaizen`
  fails at import.
- **`aegis_sdk.dataflow`** is gone, for the same reason. It was never exported
  from the top-level `__all__`, so only direct
  `import aegis_sdk.dataflow` callers are affected.

Neither removal ships a `DeprecationWarning` shim. If you depend on either,
stay on `1.0.0` and open an issue describing what you used it for — we would
rather re-expose the capability over the API than have you vendor a copy.

**Trust chains are addressed by agent, not by a separate chain id.** Every
method that took a `chain_id` first now takes `agent_id`. This is a rename of
the first positional parameter, so positional calls keep compiling and silently
change meaning if you were passing something that was not an agent id — check
your call sites rather than trusting a clean import.

**`chains.establish()` requires `authority_id`.** It has no default; the server
has never had one. `human_origin_data` is still accepted but ignored — the
server derives human origin from the authenticated caller.

**Two trust return types changed.**
`chains.establish()` now returns `EstablishedTrustChain` (fields: `agent_id`,
`genesis`, `delegations`, `status`, `human_origin`) and `chains.revoke()`
returns `CascadeRevocationResult` (`revoked_agent_ids`, `total_revoked`,
`reason`, `initiated_by`, `completed_at`). Both previously returned
`TrustChain`, whose shape matched neither response.

**Six methods now raise `UnsupportedOperationError` instead of returning.**
There is no server route behind any of them. They are kept as named, throwing
stubs — rather than deleted — so you get a message naming the gap instead of an
`AttributeError`: `chains.suspend()`, `chains.reinstate()`,
`delegations.list()`, `delegations.get()`, `delegations.get_for_agent()`,
`audit.get_entry()`.

**`User.full_name` is now a read-only deprecated property, not a field.** The
server has never emitted `full_name`; the real field is `name`. Reading
`user.full_name` still works. Constructing a `User(full_name=...)`, or relying
on `full_name` appearing in `model_dump()`, does not. `register()` still
accepts `full_name=` as a deprecated alias for `name=`, but passing **both**
with different values now raises `ValueError` naming the conflict instead of
silently picking one.

**`bridges.scoped.participants()` returns `list[Participant]`, not `list[dict]`.**
The route now declares a schema, so the method wraps it. Only `unit_id` is
required — it is the sole field the server guarantees; `roles`, `constraints`
and `added_at` are optional, because a participant supplied at bridge-creation
time is persisted as written. Unknown keys are preserved, not dropped.

**A missing base URL raises instead of defaulting.** `ClientConfig.from_env()`
and `AgenticOSClient(...)` no longer fall back to a dead placeholder host. With
no base URL resolvable from an argument or the environment, both raise
`ConfigurationError` naming `AEGIS_BASE_URL`. If you were relying on the
default, you were pointing at a host that does not answer.

#### Migration

| You called                                               | Call this instead                                                                        |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `import aegis_sdk.kaizen`                                | No replacement — open an issue with your use case                                        |
| `import aegis_sdk.dataflow`                              | No replacement — open an issue with your use case                                        |
| `chains.establish(agent_id, human_origin_data=..., ...)` | `chains.establish(agent_id, authority_id, ...)` — `authority_id` is required             |
| `chains.revoke(chain_id, reason, cascade=...)`           | `chains.revoke(agent_id, reason)` — revocation always cascades                           |
| `chains.analyze_revocation_impact(chain_id)`             | `chains.analyze_revocation_impact(agent_id)`                                             |
| `chains.suspend(...)` / `chains.reinstate(...)`          | Unsupported — raises `UnsupportedOperationError`                                         |
| `delegations.list()` / `.get(id)` / `.get_for_agent(id)` | `chains.get(agent_id)` and read its `delegations` field                                  |
| `delegations.revoke(delegation_id, ...)`                 | `delegation_id` must be the `"{delegator_id}:{delegatee_id}"` key returned by `create()` |
| `audit.get_entry(entry_id)`                              | Unsupported — raises `UnsupportedOperationError`                                         |
| `user.full_name` on a constructed `User`                 | `user.name` — `full_name` survives as a read-only property                               |
| `participants()[0]["unit_id"]`                           | `participants()[0].unit_id` — or `.model_dump()` for the old shape                       |
| relying on a default `base_url`                          | set `AEGIS_BASE_URL`, or pass `base_url=` explicitly                                     |
| `AGENTIC_OS_*` environment variables                     | `AEGIS_*` — the old names still work and warn once                                       |

### Added

**Thirty-nine new resource surfaces on the client**, and none removed. If you
have been reaching for `httpx` because the SDK had no method for something, look
again before you do. The new attributes are:

`admin` · `agent_pools` · `agentic_dashboard` · `applications` · `approvals` ·
`auth_users` · `bridges` · `credentials` · `decisions` · `emergency_bypass` ·
`governance_explain` · `integrations` · `kill_switch` · `knowledge` ·
`knowledge_govern` · `llm_providers` · `metrics` · `observe_audit` · `ontology` ·
`org_standup` · `organizations` · `positions` · `promotions` · `pseudo_agents` ·
`review_decisions` · `role_admin` · `role_envelopes` · `roles` · `settings` ·
`specialist_system` · `surfaces` · `task_agents` · `teams` · `tool_agents` ·
`tools` · `trust_posture` · `units` · `work_objectives` · `workspaces`

Highlights, for the ones whose names do not explain themselves:

- **`surfaces`** — the domain surface registry, where a declared classification
  is a real clearance gate rather than a label.
- **`bridges`** — ad-hoc, scoped and standing bridges, with typed
  `Participant` records.
- **`emergency_bypass`** and **`kill_switch`** — break-glass controls.
- **`governance_explain`** — dry-run an access decision through the chain and
  read back the step it stopped at. It evaluates an item _you describe_ (a role,
  a knowledge item, a posture) and reads no stored record, so it explains a
  hypothetical rather than a past refusal.
- **`promotions`** — environment promotion and the rules that gate it.
- **`credentials`** — encrypted credential storage and rotation.
- **`decisions`** / **`review_decisions`** — the human decision and review
  queues.
- **`work_objectives`** — human-in-the-loop work objectives and config
  versioning.

**Attaching documents to a workspace.** `workspaces` gained the document
transport, with two new models (`WorkspaceDocument`,
`WorkspaceDocumentAttachment`):

- `attach_document(workspace_id, knowledge_id) -> WorkspaceDocumentAttachment`
- `list_documents(workspace_id, limit=50, offset=0) -> list[WorkspaceDocument]`
- `detach_document(workspace_id, knowledge_id) -> WorkspaceMessage`

**Posture transitions can be approved and rejected.** Two real server routes
that the SDK never exposed: `postures.approve_transition(agent_id, notes=None)`
and `postures.reject_transition(agent_id, notes)`.

**`AEGIS_*` environment variables.** `AEGIS_BASE_URL`, `AEGIS_API_KEY` and
friends are now the primary names. The `AGENTIC_OS_*` names are still read, emit
a one-time `DeprecationWarning`, and lose to `AEGIS_*` when both are set.

**New exception types.** `UnsupportedOperationError` for an SDK method with no
backing server capability — deliberately distinct from `ServiceUnavailableError`,
which means a transient outage and is worth retrying. `ConfigurationError` for a
client that cannot be constructed.

**New models.** `EstablishedTrustChain`, `TrustGenesisRecord`,
`TrustHumanOriginInfo`, `TrustDelegationRecord`, `CascadeRevocationResult`,
`AffectedTrustAgent`, `Participant`, `WorkspaceDocument`,
`WorkspaceDocumentAttachment`.

**Five runnable examples** under `aegis_sdk/examples/` —
`basic_agent_workflow.py`, `error_handling.py`, `stand_up_a_vertical.py`,
`streaming_progress.py`, `trust_chain_management.py`. Each runs against a live
server rather than illustrating an API in prose.

**A five-part operator and architect handbook** in `aegis_sdk/handbook/` —
orientation, working through the harness, extending the platform, the API
surface, and the web console.

**A coding-agent harness** in `aegis_sdk/coc/` — agent briefs, commands, skills,
guardrails and hooks. Open this clone in your coding CLI and it arrives already
knowing the SDK's shape, so you can architect against Aegis from inside the
agent rather than pasting docs into it.

### Fixed

- **`client.agents.list()` always returned an empty page**, no matter how many
  agents existed. It sent `page`/`page_size` query parameters the server ignores
  and read `items`/`page`/`has_next` keys from a response that carries
  `records`/`total`. The result was an empty list, indistinguishable from an
  empty account. It now sends `limit`/`offset` and reads `records`/`total`. Your
  call signature is unchanged — `page_size=` still works and is translated.
- **`client.pipelines` returned an empty list and raised on reads**, the same
  wire-shape drift in a second place.
- **`Agent.capabilities` was always `[]`.** The server only ever emits
  `capabilities_json` (a JSON-encoded string), never a bare `capabilities`
  list, so the field never populated. It now derives from the raw field.
- **`auth.login()` and `auth.register()` never populated `access_token`.** Both
  passed the server's nested `{"user": ..., "tokens": ...}` envelope straight
  into `AuthToken(**response)`. They now parse the envelope, and `AuthToken`
  carries the authenticated `user` from the same response — no second
  round-trip. A malformed envelope now raises a typed error naming the missing
  and present keys, instead of a bare `KeyError`.
- **Trust posture calls raised on every successful reply**, and four trust-chain
  calls could not succeed at all, because they targeted routes that do not
  exist. Posture progression and override both now target the real
  `PUT /agents/{agent_id}/trust-posture`; there is no separate override endpoint
  on the server, and the single route decides internally whether a transition
  applies immediately or needs manager approval. Delegation create and revoke,
  audit query and chain history were reconciled the same way.
- **`audit.query()` could not filter by human origin at all**, and sent three
  parameter names the server does not recognise (`action_type`, `start_date`,
  `end_date`; the real names are `action`, `start_time`, `end_time`).
- **Bearer tokens and email addresses appeared in `repr()` and logs.**
  `AuthToken.access_token`, `AuthToken.refresh_token`, `User.email`, API-key
  secrets and one-time invite tokens are now excluded from the default
  `repr()`/`str()`, so a `print(token)` or an uncaught traceback no longer emits
  the credential in cleartext.

  ⛔ **Read the bound precisely — this masks RENDERING, not SERIALIZATION.**
  `model_dump()` and `model_dump_json()` still return the credential in full
  (measured, not assumed). So `logger.info(token.model_dump())` — a very common
  structured-logging idiom — emits the bearer token in cleartext, and so does
  `logger.info("%s", token.access_token)`. The attributes remain fully readable
  by design; only the default rendering is masked. Scrub these fields
  explicitly before any structured log or error report.

### Changed

- **Trust postures use the platform's vocabulary.** The SDK's `TrustPosture`
  enum shipped `minimal`/`basic`/`standard`/`elevated`/`full`, which matched no
  server value. It is now `pseudo`/`supervised`/`shared_planning`/
  `continuous_insight`/`delegated`.
- **Delegation constraints are `list[str]` on the wire.** The server's field is
  a list of strings, not a mapping; a dict you pass is serialized to
  `"key=value"` entries.
- **`delegations.create()` synthesizes a stable delegation id.** This backend
  has no first-class delegation entity, so the response has no `id`. The SDK
  composes `"{delegator_id}:{delegatee_id}"` so `revoke()` can address the
  delegation later. `chain_id` is no longer sent — the server has no field for
  it — but is retained on the returned object for your reference.
- **`delegations.revoke()` verifies before it acts.** It fetches the delegatee's
  trust chain first, raising `NotFoundError` if the delegation does not exist,
  and recovers the real creation timestamp and capabilities rather than
  fabricating them.
- **Documentation and docstrings now use valid values.** Every example used
  `agent_type="atomic"`, which is a 422 every time — the server accepts
  `chat`, `task`, `pipeline`, `custom`. Hardcoded `model_id="gpt-4"` strings
  were replaced by reads from your own environment.

### Removed

- `aegis_sdk.kaizen` (see Breaking Changes).
- `aegis_sdk.dataflow` (see Breaking Changes).
- `"kaizen"` from the top-level `__all__`.
- The placeholder `base_url` default. There is no fallback host.
- The fictional fields on `RevocationImpact` — `chain_id`,
  `affected_delegations` and `cascading_revocations` matched no server response.
  `affected_agents` is now `list[AffectedTrustAgent]` rather than `list[str]`,
  alongside `target_agent_id`, `target_agent_name`, `total_affected`,
  `has_active_workloads` and `warnings`.

---

## Pre-2.0.0 working notes

The entries below were written while the changes above were being made, before
this SDK had a released version. They are kept for detail; the `2.0.0` section
is the authoritative summary.

### Changed — `bridges.scoped.participants()` returns a typed model

`participants()` previously returned raw `dict`s. That was deliberate: the
server annotated `GET /scoped-bridges/{id}/participants` as an untyped list, so
there was no declared schema to wrap, and a model here would have been the
client's invention rather than the API's contract.

The route now declares one, so the method returns `list[Participant]`.

- **`Participant`** is a new model in `aegis_sdk.modules.bridges`. Only
  `unit_id` is required — it is the sole field the server guarantees. `roles`,
  `constraints` and `added_at` are optional, because a participant supplied at
  bridge-creation time is persisted exactly as the caller wrote it and may
  carry none of them. Unknown keys are preserved rather than dropped.
- **Migration:** attribute access replaces subscripting — `p.unit_id` instead
  of `p["unit_id"]`. Callers that need the previous shape can use
  `p.model_dump()`.

### Fixed — Auth model drift; SDK unusable end-to-end

The SDK's Pydantic models had diverged from the live API, so the docs-exact
`login → me → agents.list → agents.create` flow could not complete against
a real server.

- **`auth.login()` / `auth.register()`** now parse the server's nested
  `{"user": UserResponse, "tokens": TokenResponse}` envelope
  (:LoginResponse`/`RegisterResponse`) via
`AuthModule._parse_auth_envelope`. Previously both called
`AuthToken(**response)`directly against the nested envelope, so`access_token`was never populated.`AuthToken`gained an optional`.user`field (a`User`) carrying the authenticated user from the same
response -- no second round-trip to `get_current_user()`needed.`_parse_auth_envelope`also raises a typed`AgenticOSError`(naming the
missing key(s) and the actual keys present) when the response is missing`"tokens"`and/or`"user"`, instead of a bare `KeyError` -- e.g. an
  error-shaped body, a proxy/gateway error page, or a future server contract
  change.
- **`User`** now mirrors the server's `UserResponse` exactly (`name`,
  `organization_id`, `organization_name`, `role`, `personas`, `status`,
  `mfa_enabled`, `last_login_at`, `created_at`, `email_verified`) instead of
  declaring a required `full_name` field the server has never emitted. `full_name` is kept as a deprecated read-only property (backward
  compatibility) and will be removed in a
  future release once the shim has lived through one minor cycle.
  `register()`'s `full_name=` parameter is similarly a deprecated
  keyword-only alias for the new `name=` parameter -- passing BOTH `name`
  and `full_name` with DIFFERING values now raises `ValueError` naming the
  conflict, rather than silently preferring one (a caller passing two
  different names is a bug, not a preference to resolve silently).
- **`AuthToken.access_token` / `AuthToken.refresh_token`** and
  `User.email` are now marked `Field(repr=False)` -- a `print(token)`,
  logger call, or uncaught-traceback capturing the object no longer emits
  the bearer token or the user's email in cleartext. `.access_token` /
  `.refresh_token` / `.email` remain fully readable as attributes; only the
  default `repr()`/`str()` output is masked (mirrors the existing
  `_http.py::_scrub_sensitive` / `AgenticOSClient.__repr__` masking
  elsewhere in the SDK).
- **`ClientConfig.from_env()` / `AgenticOSClient.__init__`** no longer
  default `base_url` to the dead placeholder `https://api.agentic-os.com`. Both now raise `ConfigurationError` with an actionable message
  naming `AGENTIC_OS_BASE_URL` when no base URL is resolvable from an
  explicit argument or the environment.
- **Docs, docstrings, and examples** (`quickstart.md`, `README.md`,
  `authentication.md`, `configuration.md`, `error-handling.md`,
  `docs/modules/agents.md`, `docs/modules/billing.md`, `examples/*.py`,
  `core/agents.py`, `__init__.py`) corrected `agent_type="atomic"` (a 422
  every time -- the server pattern is `chat|task|pipeline|custom`) to
  `agent_type="chat"`, and every hardcoded `model_id="gpt-4"` to read from
  the caller's own environment (never a hardcoded model name, per). Also corrected the wrong `AEGIS_BASE_URL`
  env-var name in `README.md` / `authentication.md` / `configuration.md`'s
  tables and `.env` samples -- the real variable is `AGENTIC_OS_BASE_URL`.
- **`AgentsModule.list()`** (sibling fix, found while building the E2E
  regression test below, same wire-shape-drift class as the auth cluster)
  sent `page`/`page_size` query params the server ignores (it declares
  `limit`/`offset`) and read `items`/`page`/`page_size`/`has_next` keys from
  a response shaped `{"records": [...], "total": N}` -- so
  `client.agents.list()` silently ALWAYS returned an empty page regardless
  of how many agents existed. Fixed to send `limit`/`offset` and parse
  `records`/`total`.
- **`Agent.capabilities`** now derives from the server's raw
  `capabilities_json` string field via a `model_validator` -- the server only ever emits
  `capabilities_json` (a JSON-encoded string), never a bare `capabilities`
  list, so `.capabilities` previously stayed `[]` for every agent returned
  by the server.

### Added — Test coverage for the auth cluster

- A Tier-2+ regression test
  driving the DOCS-EXACT `login → me → agents.list → agents.create` flow
  through the real `AgenticOSClient`/`HTTPClient` with `respx` mocking the
  transport using the EXACT backend envelope shapes (not an invented
  contract).
- The Tier-1
  wire-shape lock (an automated envelope-shape check on the
  platform side) pinning the envelope
  parse independent of HTTP, including the typed-error-on-malformed-envelope
  guard and the `register(name=, full_name=)` conflict-detection path.

### Fixed — Trust module route/body reconciliation

Several `client.trust.chains` methods targeted server routes that do not
exist, or sent request/response shapes that do not match the real server
contract. verified against the deployed API and reconciled:

- **`chains.establish(agent_id, ...)`** now targets `POST /trust/establish`
  (was `POST /trust/chains`, a route that does not exist). `authority_id` is
  now a **required** parameter (the server requires it — there is no
  default). `human_origin_data` is **deprecated and ignored**: the server
  derives human origin from the authenticated caller, never from
  client-supplied data. Returns a new `EstablishedTrustChain` model
  (`agent_id`, `genesis`, `delegations`, `status`, `human_origin`) matching
  the server's real `TrustChain` response — the legacy `TrustChain` model
  (`id`, `human_origin_id`, `capabilities`, ...) never matched this route.

- **`chains.revoke(agent_id, reason)`** now targets
  `POST /trust/revoke/{agent_id}/cascade` (was
  `POST /trust/chains/{chain_id}/revoke`, a route that does not exist).
  The first positional parameter is renamed `chain_id` → `agent_id` — trust
  chains in this API are keyed by agent, not a separate chain identifier.
  The `cascade` kwarg is **deprecated and ignored**: the server always
  cascades revocation regardless of route; there is no non-cascading
  revoke. Returns a new `CascadeRevocationResult` model
  (`revoked_agent_ids`, `total_revoked`, `reason`, `initiated_by`,
  `completed_at`) matching the server's real response — the method
  previously (incorrectly) returned `TrustChain`.

- **`chains.analyze_revocation_impact(agent_id)`** now targets
  `GET /trust/revoke/{agent_id}/impact` (was
  `GET /trust/chains/{chain_id}/revocation-impact`, a route that does not
  exist). Parameter renamed `chain_id` → `agent_id`. The `RevocationImpact`
  model's fields are corrected to match the server's real
  `RevocationImpactPreview` shape: `target_agent_id`, `target_agent_name`,
  `affected_agents: list[AffectedTrustAgent]` (was `list[str]`),
  `total_affected`, `has_active_workloads`, `warnings` (removed the
  fictional `chain_id`, `affected_delegations`, `cascading_revocations`
  fields, which matched no real server response).

- **`chains.suspend(agent_id, reason)`** and **`chains.reinstate(agent_id)`**
  are **deprecated and non-functional**. No server route exists for
  directly suspending or reinstating a trust chain — the API declares no
  matching `/suspend` or `/reinstate`
  endpoint. The trust-chain state machine supports `SUSPENDED`
  as an internal lifecycle state reached automatically during cascade
  revocation of bridge-sourced chains, but it is not exposed as a
  directly-invokable operation. Both methods now raise
  `UnsupportedOperationError` and emit a `DeprecationWarning`. They will be
  **removed in a future minor release** once this shim has shipped for one
  full cycle. If you need this capability, please open an issue.

### Added

- `EstablishedTrustChain`, `TrustGenesisRecord`, `TrustHumanOriginInfo`,
  `TrustDelegationRecord` — new models matching the real
  `POST /trust/establish` response shape.
- `CascadeRevocationResult` — new model matching the real
  `POST /trust/revoke/{agent_id}/cascade` response shape.
- `AffectedTrustAgent` — new model for entries in `RevocationImpact.affected_agents`.
- `UnsupportedOperationError` — new exception raised by SDK methods with no
  backing server capability (distinct from `ServiceUnavailableError`, which
  is for transient infra outages).

### Migration

| Old call                                                                   | New call                                                                               |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `chains.establish(agent_id, human_origin_data, capabilities, constraints)` | `chains.establish(agent_id, authority_id, capabilities, constraints, expires_in_days)` |
| `chains.revoke(chain_id, reason, cascade)`                                 | `chains.revoke(agent_id, reason)` — cascade is always on                               |
| `chains.analyze_revocation_impact(chain_id)`                               | `chains.analyze_revocation_impact(agent_id)`                                           |
| `chains.suspend(chain_id, reason)` / `chains.reinstate(chain_id)`          | Not supported — raises `UnsupportedOperationError`                                     |

**Deferred at this wave, since reconciled:** the SDK's `TrustPosture` enum
originally shipped a legacy vocabulary — `minimal`/`basic`/`standard`/`elevated`/`full` —
that matched no server posture value. It was realigned to the server's
CARE-aligned posture names —
`pseudo`/`supervised`/`shared_planning`/`continuous_insight`/`delegated`
(`aegis_sdk/types.py`). At the time of
THIS wave the realignment was out of scope; the response-shape mismatches
noted below (SDK Pydantic field names vs. the server's actual JSON keys) were
likewise untouched in this wave — routes and request bodies are corrected;
response deserialization is best-effort where a typed model exists, and
returns the raw dict where none does.

### Fixed — Trust posture/delegation/audit route reconciliation

Continuing the reconciliation into `PosturesModule`, `DelegationsModule`,
and `AuditModule`, verified against the deployed API:

- **`postures.request_progression(agent_id, target_posture, justification)`**
  and **`postures.override(agent_id, new_posture, reason)`** now both target
  `PUT /agents/{agent_id}/trust-posture` (was
  `POST /trust/agents/{agent_id}/posture/progression` and
  `POST /trust/agents/{agent_id}/posture/override` — neither route exists).
  There is no separate override endpoint on the real backend; both SDK
  methods hit the SAME `PUT`, which internally decides whether the
  transition applies immediately or requires manager approval.
- **`postures.approve_transition(agent_id, notes=None)`** and
  **`postures.reject_transition(agent_id, notes)`** are NEW methods —
  `POST /agents/{agent_id}/trust-posture/approve` and
  `POST /agents/{agent_id}/trust-posture/reject` were real, unexposed
  server routes. `reject_transition` returns the raw server response dict
  (no typed model exists yet for the approval-record shape).
- **`delegations.create(chain_id, delegator_id, delegatee_id, capabilities, constraints)`**
  now targets `POST /trust/delegate` (was
  `POST /trust/chains/{chain_id}/delegations`, a route that does not
  exist). The real `DelegateTrustRequest.constraints` field is
  `list[str]`, not a dict — dict constraints are serialized to
  `"key=value"` wire strings. The real `DelegationRecord` response has no
  `id`/`status` fields (this backend has no first-class delegation
  entity); a stable composite id (`"{delegator_id}:{delegatee_id}"`) is
  synthesized so `revoke()` can address the delegation later. `chain_id`
  is no longer sent over the wire (the server has no field for it) — it
  is retained on the returned `TrustDelegation` for caller reference.
- **`delegations.revoke(delegation_id, reason, cascade=True)`** now targets
  `POST /trust/revoke-delegation` (was
  `POST /trust/delegations/{delegation_id}/revoke`, a route that does not
  exist) with query params `delegatee_id`/`delegator_id`/`reason` — NOT a
  JSON body. `delegation_id` MUST now be the composite key returned by
  `create()`. `cascade=False` is deprecated and ignored: the server
  always cascades revocation. Fetches the delegatee's trust chain first
  to verify the delegation exists (raising `NotFoundError` otherwise) and
  to recover its real creation timestamp/capabilities, rather than
  fabricating them.
- **`delegations.list()`**, **`delegations.get(delegation_id)`**, and
  **`delegations.get_for_agent(agent_id, ...)`** are **deprecated and
  non-functional** — no server route exists for listing delegations, or
  for fetching one by ID, as first-class resources — the published API declares
  no matching `/delegations*` route. All three now raise
  `UnsupportedOperationError` and emit a `DeprecationWarning`. Callers
  needing an agent's received delegations can use
  `client.trust.chains.get(agent_id)` and read its `delegations` field.
- **`audit.query(...)`** now dual-routes on `human_origin_id`:
  `GET /trust/audit/by-human/{human_id}` (path param) when supplied,
  `GET /trust/audit` (query-filtered) otherwise — the prior single-route
  implementation always hit `/trust/audit` with wrong param names
  (`action_type`/`start_date`/`end_date` — the real names are
  `action`/`start_time`/`end_time`) and had no way to filter by human
  origin at all.
- **`audit.get_chain_history(chain_id)`** now targets `GET /trust/audit`
  filtered by `agent_id` (was `GET /trust/chains/{chain_id}/audit`, a
  route that does not exist) — trust chains are addressed by agent_id in
  this backend.
- **`audit.get_entry(entry_id)`** is **deprecated and non-functional** —
  no server route exists for fetching a single flat audit entry by ID.
  The closest real route, `GET /audit/trace/{entry_id}`, is a DIFFERENT
  capability (a root-source lineage trace, not an entry record) and was
  deliberately NOT repurposed under this method's name. Raises
  `UnsupportedOperationError` and emits a `DeprecationWarning`.

#### Added

- `PosturesModule.approve_transition(agent_id, notes=None)` and
  `PosturesModule.reject_transition(agent_id, notes)` — new methods
  targeting real, previously-unexposed server routes.

#### Migration

| Old call                                                                      | New call                                                                                                |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `postures.request_progression(agent_id, target_posture, justification)`       | Unchanged signature — now targets the real `PUT /agents/{id}/trust-posture` route                       |
| `postures.override(agent_id, new_posture, reason)`                            | Unchanged signature — targets the SAME real route as `request_progression`                              |
| `delegations.create(chain_id, delegator_id, delegatee_id, capabilities, ...)` | Unchanged signature — `chain_id` no longer sent over the wire; targets `POST /trust/delegate`           |
| `delegations.revoke(delegation_id, reason, cascade)`                          | `delegation_id` MUST be the `"{delegator_id}:{delegatee_id}"` key from `create()`; cascade is always on |
| `delegations.list()` / `.get(id)` / `.get_for_agent(id)`                      | Not supported — raise `UnsupportedOperationError`; use `chains.get(agent_id)`                           |
| `audit.query(human_origin_id=...)`                                            | Unchanged signature — now routes to the real `by-human` path-param endpoint                             |
| `audit.get_chain_history(chain_id)`                                           | Unchanged signature — now filters the real `/trust/audit` route by `agent_id`                           |
| `audit.get_entry(entry_id)`                                                   | Not supported — raises `UnsupportedOperationError`                                                      |
