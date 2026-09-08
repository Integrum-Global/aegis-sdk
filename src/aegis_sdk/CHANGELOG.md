# Aegis SDK Changelog

## Unreleased

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
  `AuthToken(**response)` directly against the nested envelope, so
  `access_token` was never populated. `AuthToken` gained an optional
  `.user` field (a `User`) carrying the authenticated user from the same
  response -- no second round-trip to `get_current_user()` needed.
  `_parse_auth_envelope` also raises a typed `AgenticOSError` (naming the
  missing key(s) and the actual keys present) when the response is missing
  `"tokens"` and/or `"user"`, instead of a bare `KeyError` -- e.g. an
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
  directly suspending or reinstating a trust chain — verified by grepping for a matching `/suspend` or `/reinstate`
  endpoint (none found, 2026-07-08). The trust-chain state machine supports `SUSPENDED`
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
(`aegis_sdk/types.py`, `.claude/) in commit
`3dd6cbff` (2026-07-14). At the time of
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
  for fetching one by ID, as first-class resources (searched the published API for a matching `/delegations*` route,
  2026-07-13, none found). All three now raise
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

| Old call                                                                         | New call                                                                              |
| ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `postures.request_progression(agent_id, target_posture, justification)`         | Unchanged signature — now targets the real `PUT /agents/{id}/trust-posture` route     |
| `postures.override(agent_id, new_posture, reason)`                              | Unchanged signature — targets the SAME real route as `request_progression`           |
| `delegations.create(chain_id, delegator_id, delegatee_id, capabilities, ...)`   | Unchanged signature — `chain_id` no longer sent over the wire; targets `POST /trust/delegate` |
| `delegations.revoke(delegation_id, reason, cascade)`                            | `delegation_id` MUST be the `"{delegator_id}:{delegatee_id}"` key from `create()`; cascade is always on |
| `delegations.list()` / `.get(id)` / `.get_for_agent(id)`                        | Not supported — raise `UnsupportedOperationError`; use `chains.get(agent_id)`         |
| `audit.query(human_origin_id=...)`                                              | Unchanged signature — now routes to the real `by-human` path-param endpoint          |
| `audit.get_chain_history(chain_id)`                                             | Unchanged signature — now filters the real `/trust/audit` route by `agent_id`        |
| `audit.get_entry(entry_id)`                                                     | Not supported — raises `UnsupportedOperationError`                                    |
