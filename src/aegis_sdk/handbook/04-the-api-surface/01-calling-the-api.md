# 04.1 — Calling the API

This chapter documents **current behaviour**, including two open defects. Where
something is broken it says so and cites the issue. Do not read the intended
design out of the parts describing the shipped one.

## Two credentials, one door

Both JWTs and API keys enter through the same dependency, and they arrive there
already resolved: validation happens in middleware, _before_ the dependency
runs. An `X-API-Key` header, or a bearer token beginning `sk_live_`, is
validated against the API-key service, which stamps the organisation and a
synthetic user id of the form `api_key:<key id>` onto the request.

Either credential is accepted the same way by the client
(`sdk:aegis_sdk.ClientConfig`), and you can see which one you are holding at
`api:GET /api/v1/auth/me`.

The two principals differ in ways that decide everything downstream:

| field             | API key                | JWT                        |
| ----------------- | ---------------------- | -------------------------- |
| `id`              | `api_key:<key id>`     | the user id                |
| `organization_id` | the key's organisation | the token's `org_id` claim |
| `role`            | **`None`**             | the resolved role          |
| `personas`        | **`[]`**               | the resolved personas      |
| `auth_type`       | `"api_key"`            | **absent entirely**        |
| `api_key_scopes`  | the key's scopes       | —                          |

Read that table before you read anything else in this chapter. **Two of those
cells are empty on purpose and they are the source of most API-key surprises:**
an API key has no role and no personas, ever, whatever it is scoped to.

**The absence of `auth_type` on the JWT shape is the discriminator every gate
uses.** That is worth internalising, because it means gates test for
`auth_type == "api_key"` and treat "no `auth_type`" as "human session". A
principal constructed by some third path that forgets the key will be treated as a
JWT caller.

**There is more than one principal resolver, and they do not behave alike.** The
main dependency is one; the RBAC middleware derives its own principal with a
mirrored API-key branch; and a third resolver serves an alternate handler
surface, splitting the two credentials into separate paths behind a single front
door. That front door **refuses API keys unless a handler explicitly asks for
them** — fail-closed, and correct.

What this means for you as a caller: **a route's behaviour towards an API key is
not a property of the API as a whole.** Two routes that look alike from outside
can sit behind different resolvers with different defaults. If a key works on one
route and is refused on a sibling, that is not necessarily a scope problem — the
routes may not share an admission path at all.

⚠ **This chapter previously carried source coordinates, and they were wrong
often enough to be worth recording as a warning about method rather than as
history.** One section was re-derived and found to point ~32 lines short of each
target — close enough to look plausible and land a reader mid-comment. A
sentence certifying the rest of the chapter had been checked was written before
the rest was checked; a later sweep found parts off by −188 to −230 lines.

That is the failure this edition removes at the root rather than repairing.
Claims here now name **surfaces you can call** and symbols you can import, and
you can re-verify every one of them against your own installed package:

```
python -m aegis_sdk.handbook.check
```

A coordinate you cannot open is not evidence to you. An operation you can call is.

## ⛔ Known open defect: an API key cannot reach a persona-gated route

**This is open, it sits in the highest severity band, and every developer using
an API key hits it.** It is documented here rather than omitted because a chapter
that describes the intended design as if it were the shipped one is worse than no
chapter.

**The mechanism**, which is knowable entirely from the principal table above:

1. An API-key principal is constructed with **no personas**, unconditionally.
   That is deliberate fail-closed design, not an oversight.
2. A persona gate resolves the caller's personas and compares them against the
   personas the route allows.
3. An empty persona list is not a *missing* persona list, so nothing falls back
   to deriving personas from a role — and an API key has no role either, which
   would defeat such a fallback anyway.
4. The comparison asks "is any of the caller's personas allowed?". Over an empty
   list that is always false, so the deny branch always fires.

So a persona-gated route is unreachable by **every API key, regardless of
scopes**. No scope configuration can fix it, because **scopes are never consulted
on that path**.

**Why it costs a whole day, and how to recognise it in one minute.** The denial is
a `403` whose detail reads:

```
Access denied: requires one of personas admin, architect
```

That reads exactly like a permissions problem, so you go and inspect the key's
scopes — where you find nothing wrong, because nothing is wrong there.

**The one-minute diagnosis:** retry the identical request with a user session
instead of the key (`api:POST /api/v1/auth/login`, then the same call). If the
session succeeds and the key fails with that message, this is the defect and no
amount of scope editing will move it. Confirm what your key actually carries with
`api:GET /api/v1/auth/me` — an API-key principal shows an empty persona list, and
that is the whole story.

**How much surface.** Enough that you should assume a persona-gated route is
affected rather than hope otherwise. The gate is applied both per-route and at
*router* level, and a router-level gate fans out to every route beneath it — so
the number of affected routes is substantially larger than the number of places
the gate is written. **UNVERIFIED:** the exact route-level total. Counting
occurrences, files and routers yields three different numbers, each correct for
its own unit, and the route-level enumeration has not been done.

### The fix shape, and what you can do today

A persona-**or**-API-key variant of the gate already exists and carries the
API-key branch the plain persona gate lacks. The durable fix is for affected
routers to adopt it: admission at the router, a write-scope gate per route.

Until that lands, use a user session rather than a key for persona-gated calls.
**Do not widen the key's scopes to try to reach one** — the scopes are not read
on that path, so a wider key buys you nothing and leaves you holding a more
powerful credential than the job needs.

**One consequence of the fix shape is worth knowing as a caller, because it
explains an otherwise baffling result.** Admission is layered: a router-level
gate runs *before* any per-route gate. So a route can carry a perfectly correct
per-route permission check that is never reached, because the router turned you
away first.

What you observe: two routes on the same resource, one reachable with your
credential and one not, with no difference in the permissions either route
documents. The difference is which layer refused you — and the error body does
not say. If a route is refused where a sibling is not, the useful question is not
"which permission am I missing?" but "was I refused at the door, or at the
desk?".

> ### ⚠ A scope check is a no-op for session callers
>
> This is not recorded in any defect report and you need it. **The scope gate
> returns early for anything that is not an API key.** It is an API-key
> mechanism; against a user session it checks nothing at all.
>
> The consequence, on routes whose only per-route gate is a scope check: the
> **sole** authority check for a human session is the router-level persona
> allowlist. There is no per-route permission check on that path.
>
> Read that in both directions, because both matter. As a caller, a session may
> reach a route you expected your scopes to bound. As an integrator deciding what
> to hand a colleague, **a scope-bounded API key is not the weaker credential you
> may assume it is** — on some routes it is the only one that is actually
> bounded.

## The two registries

These are different vocabularies and confusing them is easy — it has been done
more than once on this team, including by people writing the documentation.

**The permission matrix** — RBAC. Keyed by *role* (`tenant_admin`, `org_owner`,
`org_admin`, `developer`, `viewer`, `member`, `app_operator`, `app_admin`,
`user`, `operator`, `manager`, `architect`, `admin`), with granular actions plus
a `*` wildcard. This is what a user session is judged against.

**The API-key scope vocabulary** — scopes, and only two buckets: `:read` and
`:write`. Anything that is not a read resolves to write. This is what a key is
judged against, and you can list what a given key carries with
`api:GET /api/v1/api-keys`.

**Neither is a subset of the other**, and that is the whole difficulty. The
concrete case that catches people:

- `roles:read` and `roles:write` **are** valid API-key scopes.
- **No `roles:` entry exists anywhere in the permission matrix.** `roles`,
  `units`, `knowledge` and `clearance` are all absent from it.

So "`roles:write` is not in the permission matrix" is a true statement that tells
you nothing about whether the scope is valid. It is valid. The two registries
answer different questions and share a spelling, which is why confusing them is
so easy — it has been done more than once here, including by people writing the
documentation.

**The bridge between them is one-directional.** A permission *resource* expands
to a set of candidate scopes, and any one of them satisfies it:

```
organizations  ->  organizations, units, roles, knowledge
deployments    ->  deployments, gateways
```

So a key scoped `roles:write` satisfies the permission `organizations:update`.
**There is no reverse table**: you cannot map a scope back to a permission, so
"what can this key do?" has no mechanical answer from the scope alone. Expect to
determine it by trying the operation.

Two more rules worth knowing about scopes, both of which surprise people:

- **write implies read.** A key scoped `x:write` satisfies `x:read`. You do not
  need both, and asking for both does not make the key narrower.
- **a malformed scopes value denies.** If the scopes field is not a sequence, the
  answer is no — not "unrestricted". Fail-closed, as everywhere else here.

## The same permission can be enforced two different ways

Two different internal guards enforce permissions on this platform. One consults
**roles only**; the other consults roles **and attribute rules**. Which one
guards a given route is not visible from the outside, and there is no field in
any response that tells you.

**What that means for you as a caller**, which is the whole of what you can act
on:

- A permission that is granted to your role and still refused is **not
  necessarily a misconfigured role.** An attribute rule may be denying you.
- **An attribute deny overrides a role allow.** That is the merge strategy —
  deny wins — so adding the role again will not clear it.
- **Two routes requiring what looks like the same permission can decide
  differently for the same caller**, because one consults the attribute rules and
  one does not. If that happens to you it is a real distinction, not a flake, and
  not something to retry your way out of.

Where a route checks roles only, that is a deliberate configuration rather than
an omission — so the asymmetry is a property of the platform's design and not a
gap you have found.

Where a gate is role-only it is so by deliberate configuration rather than by
omission — a documented choice, not a gap someone forgot to close.

⛔ **A correction worth keeping, for its method rather than its content.** An
earlier revision of this chapter filed one of these guards on the wrong side of
the role-only/role-and-attribute line, and the evidence offered was a quoted
count: *"a search for the attribute-check term returns zero matches in that
file"*. Re-run against the same file, the same search returns **35**, and the
guard's own documentation says it enforces both.

The failure is not a stale coordinate. **A count was quoted as evidence and the
count was wrong**, so a false claim arrived wearing the strongest-looking proof
on the page. Re-run a quoted number before you trust it — including any in this
book, which is the whole reason the verification command exists and is yours to
run.

**What survives, and what you can act on from outside:** you cannot tell from
the response which of the two guards refused you, and the error body does not
say. So a permission granted to your role and *still* refused is not necessarily
a bug in your role — an attribute rule may be denying you, and deny wins over a
role allow.

*Design intent, not observable:* the guard is chosen per route at the platform
side. You cannot query which one applies, and this book will not invent a way to
tell you, because a method that appeared to work and did not would be worse than
the honest limit.

**So diagnose it from the outside, in this order.** Confirm the permission is
granted to your role. If it is and the call is still refused, treat an attribute
rule as the live hypothesis and take it to whoever administers your organisation
— they can see the rules and you cannot. The one thing not to do is widen the
role and retry, which cannot succeed against an attribute deny and leaves the
role permanently wider than it needed to be.

## Tenancy

The field is `organization_id` on the principal — the key's organisation for an
API key, the token's `org_id` claim for a session — and it is mirrored onto the
request. The alternate handler surface guards it fail-closed. You can read the
organisation your credential resolves to at `api:GET /api/v1/auth/me`.

**It is not enforced by a single middleware, and that is the fact to carry.**
Three layers check it independently, each explicit at its own call site:

1. **The HTTP boundary** — refuses a caller with no organisation context, with a
   **400** and the detail `"Authenticated caller has no organization context"`.
   Note the status: a *400*, not a 401 or 403. A caller who reads only the status
   code will classify this as a malformed request and go looking at their body.
   It is an identity problem.
2. **The service layer** — a tenant guard applied per call, plus a row-level
   check that a returned row belongs to the caller's organisation.
3. **RBAC/ABAC** — the permission check takes the caller's organisation
   explicitly. A *permission lookup* deliberately opts out of tenant scoping,
   because asking "what may I do?" is a self-lookup; the **attribute** evaluation
   does scope by tenant.

The consequence of three independent layers rather than one: **a tenancy failure
can surface as a 400, a 403, or an empty result set, depending on which layer
caught it.** Those look like three different bugs and are one.

**Scopes are not tenant-qualified.** `has_scope` and `scope_covers_permission`
take only `(scopes, permission)` — no org argument. Tenancy is an orthogonal check
applied by the route or the service, never by the scope gate. A valid scope says
nothing about which tenant's data you may touch.

## Checklist for calling this API

1. **Know which credential you hold**, and what it lacks. Check with
   `api:GET /api/v1/auth/me`. An API key has no role and no personas — ever.
2. **If a call is refused, establish which layer refused it** before changing
   anything. Retry with the other credential type; the difference tells you more
   than the status code does.
3. **Do not widen a credential to solve a refusal you have not diagnosed.** On
   several paths a wider scope changes nothing, and you are left holding a more
   powerful key for no benefit.
4. **Never send an organisation id in a request body** expecting it to be
   honoured. Tenancy is derived from your credential, and a body-supplied value
   is at best ignored.
5. **Expect the same for any approver or decider identity.** It is derived from
   the authenticated session and pinned when the record is created — a body field
   naming an approver is not how approval works here, and this is deliberate.

*Adding a route to the platform rather than calling it is covered in the
platform's own internal documentation, which is not part of this edition.*

**Where the rest of this part goes.** This chapter is about *who you are* and
*why you were refused*. The five that follow are about everything that happens
once a call actually goes out: what each failure means and whether to retry it
([04.2](02-errors-and-refusals.md)), what a key can and cannot hold over its
life ([04.3](03-credentials-and-keys.md)), how to read a collection without
silently truncating it ([04.4](04-lists-and-pagination.md)), what the client
does under load and where its error handling stops
([04.5](05-concurrency-and-streams.md)), and which fields of a successful
response you may actually act on
([04.6](06-reading-a-response-honestly.md)).

---

*Next: [04.2 — Errors and refusals](02-errors-and-refusals.md)*
