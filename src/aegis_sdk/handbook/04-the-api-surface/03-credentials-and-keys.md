# 04.3 — Credentials, and what a key is not

[04.1](01-calling-the-api.md) explains what the two credential types *are* and
why a persona-gated route refuses a key. This chapter is the operational half:
what a key can hold, what happens to it over its life, and what a permission
failure looks like from where you are sitting.

## One header, two credentials

Whatever you hold, this client sends it the same way:

```
Authorization: Bearer <the credential>
```

That is the whole mechanism. The client sends **no `X-API-Key` header** — the
deployment may well accept one from a hand-rolled caller, but this package never
produces it, so a rule you write against that header will not see SDK traffic.

The consequence for your code is convenient and slightly alarming: one client
object can hold either kind, and swap between them mid-run.

```python
client = AgenticOSClient.from_env()        # holding the provisioning key

token = await client.auth.login(email, password)     # api:POST /api/v1/auth/login
client.set_auth_token(token.access_token)            # now holding a session
```

`sdk:aegis_sdk.AgenticOSClient.set_auth_token` and
`sdk:aegis_sdk.AgenticOSClient.set_api_key` are the **same method under two
names** — the "token" one is an alias. There is no separate token slot, no
precedence rule, and nothing warns you that you have just replaced a
long-lived provisioning credential with a session that will expire. If you need
both, hold two clients:

```python
provisioner = AgenticOSClient(base_url=URL, api_key=KEY)
operator    = AgenticOSClient(base_url=URL)
operator.set_auth_token((await provisioner.auth.login(e, p)).access_token)
```

`sdk:aegis_sdk.ClientConfig.with_api_key` builds a second config from the first
if you would rather not repeat the settings.

**Neither the repr nor the masked property will leak the credential.** Printing
the client shows a truncated form, and `sdk:aegis_sdk.AuthToken` hides both
`access_token` and `refresh_token` from its own repr. That is a real protection
and it is also a trap in the other direction: `print(token)` will not show you
the token, so a debugging session that prints the object and sees nothing has
not necessarily got nothing.

## A key is a provisioning credential, not a person

This is the sentence to carry out of the chapter.

An API-key principal has an id of the form `api_key:<key id>`, no role and no
personas — see the table in [04.1](01-calling-the-api.md). That is not a defect
of your particular key. **It is what a key is.** Three consequences follow, and
each of them is somebody's wasted afternoon:

1. **A key cannot approve anything.** Approvals are attributable to a human, and
   the approver identity is derived from the authenticated session and pinned
   when the record is created. A key has no human behind it to attribute to.
2. **A key cannot reach a persona-gated route, at any scope.** The one-minute
   test is in [04.1](01-calling-the-api.md); run it before you touch scopes.
3. **A key's `organization_id` is fixed at issue.** It is the key's
   organisation, not a claim you can vary. `api:POST /api/v1/auth/me/switch-org`
   exists for a session; a key has nothing to switch.

Read your own credential before reasoning about any refusal:

```python
me = await client.auth.get_current_user()   # api:GET /api/v1/auth/me
if not me.personas:
    ...  # you are holding a key. Persona-gated routes are closed. Scopes will not help.
```

> ⚠ **That call can raise for exactly the credential it exists to diagnose.**
> `sdk:aegis_sdk.User` requires six fields — `id`, `email`, `name`,
> `organization_id`, `organization_name`, `role` — and a key principal is
> documented as carrying no role. Two of the three plausible wire shapes for a
> missing role raise a validation error; only `role: ""` parses.
>
> **A validation error here means the request was ANSWERED, not refused.** It is
> a different finding from a `401` or a `403` and it points at a different owner.
> **UNVERIFIED:** which shape a real deployment sends. Settling it needs a live
> call, and this edition could not make one, so do not read either answer out of
> this book — make the call and read the body:
>
> ```python
> raw = await client._http.request("GET", "/api/v1/auth/me")   # api:GET /api/v1/auth/me
> print(raw)          # personas, role, organization_id — unparsed, therefore readable
> ```
>
> That deliberately reaches past the model. It is right for this one diagnosis
> and wrong everywhere else.
>
> Nothing in this book depends on `get_current_user()` succeeding. It is a
> convenience, not a gate.

## Creating a key, and the secret you will lose

```python
key = await client.auth.create_api_key(          # api:POST /api/v1/api-keys
    name="nightly-provisioning",
    scopes=["organizations:write", "agents:read"],
    expires_in_days=90,
)
print(key.key_prefix)     # 'sk_live_' — an identifier, not a credential
```

⛔ **The returned `sdk:aegis_sdk.APIKey` has no field for the key itself.** Its
fields are `id`, `name`, `key_prefix`, `scopes`, `created_at`, `expires_at`,
`last_used_at` — and nothing else. A server response carrying the full secret is
parsed into that model, the secret matches no declared field, and it is
**silently discarded**. There is no error and no warning; you are left holding a
prefix and an id, and the secret is not retrievable afterwards by design.

Measured against the model with a response body carrying both `key` and
`api_key`: neither attribute exists on the result, while the same body read
before parsing contains both.

**If you are provisioning keys from a script, take the raw body:**

```python
raw = await client._http.request(
    "POST", "/api/v1/api-keys",                  # api:POST /api/v1/api-keys
    json_data={"name": "nightly-provisioning", "scopes": ["agents:read"]},
)
secret = raw.get("key") or raw.get("api_key")    # whichever your deployment emits
```

**UNVERIFIED:** which field name a real deployment uses for the secret, or
whether it returns one at all — that is a property of the deployment and cannot
be settled from this package. What *is* settled is that the typed method cannot
give it to you whatever it is called.

Then treat it as a secret. Everything in
[01.3](../01-orientation/03-your-first-session.md) about environment variables
applies: it belongs in your secret store, not in the provisioning log, and not
in the audit trail of the script that made it.

## What scopes are, briefly, and where the detail is

Two buckets — `:read` and `:write` — and **write implies read**, so asking for
both does not make a key narrower. A malformed scopes value denies rather than
permits. The scope vocabulary and the permission matrix are **different
registries that share a spelling**, and the full account of how they relate,
including the one-directional bridge between them, is in
[04.1](01-calling-the-api.md) § *The two registries*. Read it before you design
a key hierarchy; the two-registry confusion is the most reliably repeated
mistake on this API.

The one thing worth repeating here, because it inverts an assumption people
carry in: on routes whose only per-route gate is a scope check, **a scope-bounded
key is the more tightly bounded credential, not the looser one** — the scope gate
returns early for a session and checks nothing. Do not reach for a human session
on the assumption that it is the safer choice.

Read what a key actually carries with `api:GET /api/v1/api-keys`, or one key by
id with `api:GET /api/v1/api-keys/{id}`:

```python
for k in await client.auth.list_api_keys():
    print(f"{k.name:24} {k.key_prefix} scopes={k.scopes} expires={k.expires_at}")
```

## As a key ages

Four fields describe a key's life, and the gaps between them are the useful part.

| field | what it tells you |
| --- | --- |
| `created_at` | when it was issued — always present |
| `expires_at` | when it stops working, or `None` for **never** |
| `last_used_at` | when it was last presented, or `None` for **never used** |
| `scopes` | what it carries — an empty list is legal |

⚠ **There is no status, active or revoked field on the model at all.** You
cannot tell a live key from a revoked one by reading it. `expires_at` is the only
lifetime signal the client exposes, and `None` there means *no expiry*, not
*expired*. If your deployment revokes a key by deleting the record, absence from
`api:GET /api/v1/api-keys` is your signal; if it revokes in place, this client
gives you nothing to see it by. **UNVERIFIED:** which of those your deployment
does.

**`last_used_at` is the field to build a hygiene check on**, and it is the one
architects reliably forget they have:

```python
from datetime import UTC, datetime, timedelta

cutoff = datetime.now(UTC) - timedelta(days=90)
for k in await client.auth.list_api_keys():
    if k.last_used_at is None and k.created_at < cutoff:
        print(f"never used in 90 days: {k.name} ({k.id})")
    if k.expires_at is None:
        print(f"no expiry set: {k.name} ({k.id})")
```

That is exactly the kind of assertion [02.1](../02-working-through-the-harness/01-the-two-surfaces.md)
argues the harness is for and the console cannot do. Run it on a schedule.

**Rotation.** `api:POST /api/v1/api-keys/{id}/regenerate` exists on this
surface. **UNVERIFIED:** whether the old secret stops working immediately or
overlaps — that decides whether you can rotate without a maintenance window, and
it cannot be settled from the client. Establish it in a staging deployment
before you need it in production. Retiring a key outright is
`api:DELETE /api/v1/api-keys/{id}`; `sdk:aegis_sdk.auth.AuthModule.revoke_api_key`
is an alias for the delete, not a separate softer operation.

**Expiry is opt-in on this side.** `expires_in_days` is optional at creation,
the client supplies no default, and it is **omitted from the request body
entirely** when you do not pass it — so whether an unexpiring key results is the
deployment's decision, not the client's. **UNVERIFIED:** what yours does with the
field absent. Pass it explicitly for anything living in CI, and set the rotation
reminder in the same change; then you do not need to know.

## When a permission failure arrives

You will see one of three things, and they want three different responses.

| what you get | what it means | what to do |
| --- | --- | --- |
| `sdk:aegis_sdk.AuthenticationError` (401) | **two different things** — see immediately below | reissue **once**; if it recurs, stop and read on |
| `sdk:aegis_sdk.AuthorizationError` (403) | you were identified and refused | **attribute it before changing anything** |
| `sdk:aegis_sdk.GovernanceViolationError` (423) or `sdk:aegis_sdk.TrustViolationError` (451) | a policy or a trust constraint refused you | this is governance working — see [02.6](../02-working-through-the-harness/06-approvals-holds-and-evidence.md) |

⚠ **The `401` row is the one that wastes a day, and the exception's own
documentation points the wrong way.** `AuthenticationError` is documented as
"invalid or malformed key / expired token", and that is only one of its two
causes. The other is that **the operation requires a verified interactive
session, and a key cannot supply one at any scope** — so a perfectly valid,
unexpired, correctly-scoped key gets a `401` that looks exactly like a bad
credential.

The discriminator is cheap and definitive: **reissue once, and if the fresh key
gets the same `401`, retry with a session.** A session that succeeds where two
independent keys failed is mechanism 3 in
[04.2](02-errors-and-refusals.md#a-refusal-is-not-one-status), and no key will
ever pass that control. Stop reissuing.

For the `403`, the attribution step is one retry with the other credential type,
and the result table is in [04.1](01-calling-the-api.md). The short version: a
key refused where a session succeeds is a *reachability* problem no scope change
will fix; both refused is a real authorization decision; a session that returns
`401` means your session is bad and you have measured nothing.

⛔ **Do not widen a credential to clear a refusal you have not attributed.** In
the reachability branch the added scopes are never read, so you gain nothing and
are left holding a more powerful key permanently. In the authorization branch you
have granted access without deciding it should be granted. Neither branch is
improved by widening; only one is even affected by it.

---

*Next: [04.4 — Lists, filters and pagination](04-lists-and-pagination.md)*
