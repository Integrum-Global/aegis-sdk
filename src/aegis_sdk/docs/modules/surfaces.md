# Surfaces Module

The surfaces module (`client.surfaces`) is the architect-tier surface registry. A **surface** is a tenant-scoped, data-driven domain screen: one registration contributes one navigation entry and one reachable route, at runtime, with no code edit and no deploy.

This is the capability that lets an architect compose a domain area of the product for their own organization instead of forking the frontend.

| Method                   | Route                                                     | Who                                     |
| ------------------------ | --------------------------------------------------------- | --------------------------------------- |
| `manifest()`             | `GET /api/v1/surface-registry`                            | Every persona — the per-caller read     |
| `list_registrations()`   | `GET /api/v1/surface-registry/registrations`              | Authoring persona + `surfaces:admin`    |
| `get_registration()`     | `GET /api/v1/surface-registry/registrations/{key}`        | Authoring persona + `surfaces:admin`    |
| `create_registration()`  | `POST /api/v1/surface-registry/registrations`             | Authoring persona + `surfaces:create`   |
| `update_registration()`  | `PATCH /api/v1/surface-registry/registrations/{key}`      | Authoring persona + `surfaces:update`   |
| `delete_registration()`  | `DELETE /api/v1/surface-registry/registrations/{key}`     | Authoring persona + `surfaces:delete`   |

"Authoring persona" means `architect`, `admin` or `executive`. The persona alone is not sufficient — every authoring route also requires the matching `surfaces:<verb>` permission, and holding one without the other is refused with 403.

---

## Read Before You Build

### `classification` is a clearance gate

The caller's clearance is compared against `classification`. An entry the caller is not cleared for is omitted from their manifest and its route refuses to resolve.

It is one of **three independent per-entry gates**. `personas`, `required_permission` and `classification` are conjunctive: an entry is served only when the caller satisfies all three, so widening one does not relax the others.

The ladder is `public` < `restricted` < `confidential` < `secret` < `top_secret`. Reaching a level admits everything at or below it. `internal` is an accepted spelling of `restricted`.

The caller's clearance is resolved server-side from their active, vetted role clearances. It is not a token claim, and no request field sets it — a caller cannot raise their own. **A clearance the server cannot resolve denies every entry**, including `public` ones, rather than falling back to the bottom of the ladder.

⚠ **This changed.** An earlier revision of this guide said the field was declarative and gated nothing. That was true when written and is now wrong — a surface classified above its readers' clearance will disappear for them, which the earlier text said would not happen.

Writes are still capped at `confidential`: the stored record carries no compartment, so admitting a higher level would advertise a protection tier with nothing behind it. That cap is on what may be **registered** — a caller cleared to `secret` or `top_secret` reads normally.

Entries above your clearance are **absent** from the response rather than reported as forbidden, so the manifest cannot be used to detect that a more sensitive surface exists.

### A `record_list` surface has no supported API to populate it yet

`record_list` is the only shipped renderer, and the governed object layer beneath it — the record types and the records themselves — is schema-only today. It has no route and no client method, here or anywhere else in this package.

So a registered surface mounts, appears in navigation for the personas you name, enforces its permission and its classification, resolves its route, and renders its configured empty state. What it cannot yet do is list records, because nothing can create them.

Registering surfaces now is still real work — the navigation entry, the permission and clearance gates, and the route are live and enforced — but do not plan a data-bearing screen around it in this release.

---

## The Per-Caller Read

```python
nav = await client.surfaces.manifest()

for entry in nav.surfaces:
    print(entry.nav_section, entry.nav_label, entry.route_path)
```

`manifest()` takes no arguments, and that is deliberate: there is no parameter that could widen it. The server returns exactly the entries this caller may see, having filtered by organization, then `status`, then vocabulary resolvability, then persona intersection, then each entry's own `required_permission` evaluated against this caller. Entries you may not see are never returned, so the route cannot be used to enumerate an organization's surfaces.

Disabled registrations are excluded. So are registrations whose stored values no longer satisfy the server's current vocabulary.

### `SurfaceManifestEntry`

| Field             | Type             | Description                                                     |
| ----------------- | ---------------- | ---------------------------------------------------------------- |
| `surface_key`     | `str`            | Tenant-unique key                                                |
| `route_path`      | `str`            | Derived server-side as `/x/{surface_key}`                        |
| `nav_section`     | `str \| None`    | `BUILD`, `WORK`, `GOVERN` or `OBSERVE`                           |
| `nav_label`       | `str`            | Menu label                                                       |
| `nav_description` | `str`            | Tooltip / subtitle                                               |
| `icon_key`        | `str`            | Icon name from the server's allowlist                            |
| `sort_order`      | `int`            | Position within the section                                      |
| `view_kind`       | `str`            | `record_list`                                                    |
| `view_config`     | `dict`           | Configuration for the renderer                                   |
| `personas`        | `list[str]`      | Personas the entry is offered to                                 |
| `classification`  | `str`            | Clearance required to see the entry — see above                  |

`organization_id`, provenance and `required_permission` are deliberately absent. The manifest is already filtered to entries this caller may see, so echoing the gate that admitted them tells the client nothing it can act on.

---

## Registering a Surface

```python
row = await client.surfaces.create_registration(
    surface_key="finance_exceptions",
    nav_section="GOVERN",
    nav_label="Finance Exceptions",
    nav_description="Exceptions awaiting review",
    icon_key="Shield",
    sort_order=10,
    view_config={
        "columns": [
            {"key": "reference", "label": "Reference"},
            {"key": "raised_at", "label": "Raised"},
        ],
        "empty_message": "No exceptions outstanding.",
    },
    required_permission="organizations:read",
    personas=["architect", "executive"],
)

print(row.route_path)   # /x/finance_exceptions
print(row.status)       # disabled
```

**The default is fail-closed.** A registration created without an explicit `status` is `disabled`: it exists, authors can see it, and it contributes nothing to any caller's manifest and mounts no route. Publishing is a separate, deliberate act:

```python
await client.surfaces.update_registration("finance_exceptions", status="enabled")
```

The returned row is read back from storage after the write, not echoed from your request — so what you get is what persisted.

### The route path is derived, never supplied

There is no `route_path` request field, and sending one is refused. A surface mounts at `/x/{surface_key}`, computed server-side from the key.

This is a security design, not a convenience. Because nothing a caller writes is ever concatenated into a path, path traversal, scheme injection and route shadowing are unrepresentable rather than filtered — there is no denylist that has to stay ahead of an adversary.

`surface_key` must match: a leading lowercase letter, then lowercase letters, digits and underscores, length 3 to 64. It is unique **within** your organization, never globally — two organizations may both register `finance_exceptions` and neither can see the other's.

It is also **immutable**. `update_registration()` addresses a row by key and never sends the key in the body; an attempt to re-point a live URL is refused with 422 rather than silently ignored. To change a key, register a new surface and delete the old one.

### Closed vocabularies

| Argument         | Accepted values                                                    |
| ---------------- | ------------------------------------------------------------------ |
| `nav_section`    | `BUILD`, `WORK`, `GOVERN`, `OBSERVE`                               |
| `personas`       | `architect`, `user`, `admin`, `executive`, `operator`              |
| `view_kind`      | `record_list`                                                      |
| `classification` | `public`, `restricted`, `confidential`                             |
| `status`         | `disabled`, `enabled`                                              |

An empty `personas` list means the entry is visible to nobody. That is a valid, fail-closed request, and the client sends it rather than dropping it.

`internal` is accepted on write as an alias for `restricted` and is stored canonicalised as `restricted`.

`required_permission` must be a member of the platform's existing permission catalogue — it is **selected, never minted**. Nothing about registering a surface creates a new permission. It defaults server-side to `organizations:read`.

`icon_key` is a **name** from an allowlist of already-bundled icons, never a URL and never a component path, so nothing you write can cause an arbitrary asset to be fetched or rendered. The server owns the list and is authoritative; as of this release it accepts:

`Activity`, `AlertTriangle`, `BarChart`, `BookOpen`, `Boxes`, `Building2`, `ClipboardCheck`, `DollarSign`, `FileText`, `FolderKanban`, `Gauge`, `Inbox`, `Layers`, `ListChecks`, `ScrollText`, `Shield`, `Users`, `Workflow`

An unlisted name is a 422 naming `icon_key`. The default is `Layers`.

### `view_config` for `record_list`

Two keys, and only two — unknown keys are **rejected, not ignored**, so a typo is a 422 rather than a field that silently disappears.

| Key             | Type              | Constraint                                                          |
| --------------- | ----------------- | -------------------------------------------------------------------- |
| `columns`       | `list[dict]`      | At most 24. Each entry accepts only `key` and `label`.               |
| `empty_message` | `str`             | Max 200 characters                                                   |

A column's `key` follows the same charset rule as a surface key. `label` is optional and defaults to the key; it is sanitized on write and rendered as text, never as markup. The whole `view_config` must serialize to at most 4096 bytes.

---

## Listing and Reading Registrations

```python
result = await client.surfaces.list_registrations()

for row in result.registrations:
    print(row.surface_key, row.status, row.required_permission)

one = await client.surfaces.get_registration("finance_exceptions")
```

These are the authoring projection: every registration in your organization, any status, including unpublished drafts, with ids and provenance. Scoped server-side to your organization — no argument can widen it.

A key belonging to another organization returns 404, identically to a key that does not exist, so the response cannot be used to probe another organization's key space.

### `SurfaceRegistration`

| Field                 | Type              | Description                                                        |
| --------------------- | ----------------- | ------------------------------------------------------------------- |
| `surface_key`         | `str`             | Tenant-unique key                                                   |
| `id`                  | `str \| None`     | Row id                                                              |
| `organization_id`     | `str \| None`     | Owning organization                                                 |
| `route_path`          | `str \| None`     | `/x/{surface_key}`, or `None` on an unresolvable row                |
| `nav_section`         | `str \| None`     | Navigation section                                                  |
| `nav_label`           | `str`             | Menu label                                                          |
| `nav_description`     | `str`             | Tooltip / subtitle                                                  |
| `icon_key`            | `str`             | Icon name                                                           |
| `sort_order`          | `int`             | Position within the section                                         |
| `view_kind`           | `str`             | Renderer                                                            |
| `view_config`         | `dict`            | Renderer configuration                                              |
| `required_permission` | `str \| None`     | Permission a caller must hold to see the entry and resolve its route |
| `personas`            | `list[str]`       | Personas the entry is offered to                                    |
| `classification`      | `str`             | Clearance required to see the entry and resolve its route           |
| `status`              | `str`             | `disabled` or `enabled`                                             |
| `derived_scopes`      | `dict[str, str]`  | Descriptive labels only — see below                                 |
| `created_by`          | `str \| None`     | Author                                                              |
| `updated_by`          | `str \| None`     | Last editor                                                         |
| `created_at`          | `str \| None`     | ISO 8601                                                            |
| `updated_at`          | `str \| None`     | ISO 8601                                                            |
| `unresolvable`        | `bool`            | `True` only on a row the current vocabulary rejects                 |
| `unresolvable_field`  | `str \| None`     | Which field made it unresolvable                                    |

`derived_scopes` carries four names of the form `surface:{key}:{read|write|approve|admin}`. They are **descriptive labels for display, not grantable permissions** — nothing registers them and no gate consults them. Enforcement uses `required_permission`.

### Unresolvable rows

Every field but `surface_key` is optional on this model, and that reflects the wire shape rather than defensive typing.

If a stored row no longer satisfies the server's *current* vocabulary — because the key pattern was tightened or a key was reserved after the row was written — the authoring reads degrade to a short row rather than failing the whole list:

```python
row = (await client.surfaces.list_registrations()).registrations[0]

if row.unresolvable:
    print(f"{row.surface_key} needs attention: {row.unresolvable_field}")
    # route_path is None — it cannot be derived from a key today's rules reject
```

Such a row is still shown to its owner so it can be repaired or deleted, and it is dropped from every caller's manifest.

---

## Deleting

```python
result = await client.surfaces.delete_registration("finance_exceptions")
print(result.deleted, result.surface_key)   # True finance_exceptions
```

The delete is a **soft delete**: the row is retained for compliance and stops appearing in reads, manifests and routing.

---

## Errors

| Status | Meaning                                                                                 |
| ------ | ---------------------------------------------------------------------------------------- |
| 403    | Missing the authoring persona, or missing the `surfaces:<verb>` permission                |
| 404    | No such key in your organization — including a key that exists in another organization    |
| 409    | A registration with that key already exists in your organization                          |
| 422    | A field was refused; the response names the offending `field`                             |

The 422 body names the specific field rather than answering only "invalid" — a self-service authoring surface that refuses eleven fields anonymously is unusable. Create, update and delete are each audit-logged server-side.
