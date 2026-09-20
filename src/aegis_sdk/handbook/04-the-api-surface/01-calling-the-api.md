# 04.1 — Calling the API

This chapter is about _who you are_ when you call Aegis, and why a call is
refused. Read it before you change a credential: most refusals here are answered
by knowing which of two credentials you hold and which layer turned you away.

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
cells are empty by design, and they decide which routes each credential
reaches:** an API key has no role and no personas, ever, whatever it is scoped
to. A key carries scopes; a session carries a role and personas.

**The absence of `auth_type` on the JWT shape is the discriminator every gate
uses.** That is worth internalising, because it means gates test for
`auth_type == "api_key"` and treat "no `auth_type`" as "human session". A
principal constructed by some third path that forgets the key will be treated as a
JWT caller.

**A route's behaviour towards an API key is not a property of the API as a
whole.** Two routes that look alike from outside can admit a key on different
terms, and some admit one only where the route asks for it explicitly — a
refusal by default, which is the right default. So if a key works on one route
and is refused on a sibling, that is not necessarily a scope problem. Treat the
two routes as two questions and test each with the credential in your hand.

Claims in this chapter name **surfaces you can call** and symbols you can
import, and you can re-verify every one of them against your own installed
package:

```
python -m aegis_sdk.handbook.check
```

An operation you can call is evidence you can act on.

## Which credential reaches which route

**Personas belong to sessions; scopes belong to keys.** That single sentence is
the credential model, and it decides admission across the whole API.

A **persona** is a property of a human identity — `admin`, `architect` and the
rest are things a _person_ is within an organisation. An API-key principal is
constructed with no personas and no role, unconditionally and by design: a
machine credential is not a person, and inventing a persona for one would be a
fail-open default in the place that can least afford it. A **scope** is the
machine equivalent — a narrow, explicit grant of `:read` or `:write` over a
named resource, attached to the key when it is issued.

So the routing is direct:

| route is gated on | reached by                                                 |
| ----------------- | ---------------------------------------------------------- |
| personas          | a user session                                             |
| API-key scopes    | an API key carrying a satisfying scope                     |
| both              | either, admitted at the router and scope-checked per route |

**Use a session for persona-gated calls and a key for scope-gated ones.** A
wider scope does not turn a key into a session: on a persona-gated path, scopes
are not the question being asked, so widening one buys you nothing and leaves
you holding a more powerful credential than the job needs.

**Routers that accept both** use a persona-**or**-API-key admission gate — the
router decides whether the caller is admitted at all, and each route beneath it
applies its own write-scope check. That is the shape to expect on mixed
surfaces, and it is being extended across the remaining persona-gated routers
[immediate roadmap].

**Telling the two apart in one minute.** When a call is refused and you are not
sure which model a route follows, retry the identical request with a user
session (`api:POST /api/v1/auth/login`, then the same call). If the session
succeeds where the key did not, the route is persona-gated and a session is the
credential it wants. Confirm what your own credential carries with
`api:GET /api/v1/auth/me` — an API-key principal shows an empty persona list,
which is the expected shape, not a misconfiguration.

**Admission is layered, and that explains an otherwise baffling result.** A
router-level gate runs _before_ any per-route gate. So a route can carry a
perfectly correct per-route permission check that is never reached, because the
router made the admission decision first.

What you observe: two routes on the same resource, one reachable with your
credential and one not, with no difference in the permissions either route
documents. The difference is which layer decided — and the error body does not
say. If a route is refused where a sibling is not, the useful question is not
"which permission am I missing?" but "was I refused at the door, or at the
desk?".

> ### ⚠ A scope check is a no-op for session callers
>
> **The scope gate returns early for anything that is not an API key.** It is an
> API-key mechanism; against a user session it checks nothing at all.
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

These are two different vocabularies that share a spelling. Keep them apart.

**The permission matrix** — RBAC. Keyed by _role_ (`tenant_admin`, `org_owner`,
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
answer different questions, and a name in one is not a name in the other.

**The bridge between them is one-directional.** A permission _resource_ expands
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

Where a gate is role-only it is so by deliberate configuration — a documented
choice, and a property of the platform's design rather than a gap.

**The guard is chosen per route at the platform side, and the choice is not
exposed on the response.** The error body names the permission, not the
mechanism that evaluated it. So a permission granted to your role and _still_
refused is not necessarily a bug in your role — an attribute rule may be denying
you, and deny wins over a role allow.

**So diagnose it from the outside, in this order.** Confirm the permission is
granted to your role. If it is and the call is still refused, treat an attribute
rule as the live hypothesis and take it to whoever administers your organisation
— they can see the rules and you cannot. The one thing not to do is widen the
role and retry, which cannot succeed against an attribute deny and leaves the
role permanently wider than it needed to be.

## Tenancy

The field is `organization_id` on the principal — the key's organisation for an
API key, the token's `org_id` claim for a session — and it is mirrored onto the
request. You can read the organisation your credential resolves to at
`api:GET /api/v1/auth/me`.

**Tenancy is checked in more than one place, and that is the fact to carry.**
One of those refusals is worth knowing exactly: a caller with no organisation
context is turned away with a **400** and the detail
`"Authenticated caller has no organization context"`. Note the status — a _400_,
not a 401 or 403. A caller who reads only the status code will classify this as a
malformed request and go looking at their body. It is an identity problem.

The consequence: **a tenancy failure can surface as a 400, a 403, or an empty
result set.** Those look like three different bugs and are one. When you meet any
of the three, read the organisation your credential resolves to before you change
anything else.

**A scope and a tenant are different questions.** Your organisation comes from
the credential itself, never from what that credential is scoped to. A scope
tells you which operations a key may attempt; it never tells you whose data the
key reaches. So widening a scope is not a way to reach another organisation's
data, and a scope that looks correct is no evidence that a tenancy refusal was
about scopes at all.

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

_Adding a route to the platform, rather than calling it, is covered by the
platform's own internal documentation._

**Where the rest of this part goes.** This chapter is about _who you are_ and
_why you were refused_. The five that follow are about everything that happens
once a call actually goes out: what each failure means and whether to retry it
([04.2](02-errors-and-refusals.md)), what a key can and cannot hold over its
life ([04.3](03-credentials-and-keys.md)), how to read a collection without
silently truncating it ([04.4](04-lists-and-pagination.md)), what the client
does under load and where its error handling stops
([04.5](05-concurrency-and-streams.md)), and which fields of a successful
response you may actually act on
([04.6](06-reading-a-response-honestly.md)).

---

_Next: [04.2 — Errors and refusals](02-errors-and-refusals.md)_
