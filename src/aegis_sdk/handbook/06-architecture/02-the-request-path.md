# 06.2 — The request path

[06.1](01-what-core-and-the-sdk-are.md) drew the boundary and named the two
planes. This chapter walks a call across it — every layer it passes through, the
point at which each kind of decision is actually taken, and what happens to the
request when one of them says no.

The point of the walk is prediction. A refusal does not tell you which layer
produced it, and the layers have different remedies: one is answered by a
different credential, one by a different permission, one by a different design,
and one is not about you at all. Knowing the order is what lets you tell them
apart from the outside.

## The layers, in order

```text
one call, and the layers it passes through
│
├── in your process ───────────────────────────────────────────────────────────
│     1  the module        builds the path, percent-encoding every identifier
│     2  the transport     one credential header · SDK + API version · Content-Type
│                          retries transport failures only — never an HTTP status
│
├───── THE BOUNDARY · everything below is the deployment's ────────────────────
│
└── in the deployment
      │
      3  ADMISSION ──────── ENFORCED, before any route is consulted
      │                     the credential is resolved, the organisation is resolved
      │                     router-level gates run here — so a refusal here is a
      │                     statement about the DOOR, not about the route you called
      │                     → 401 (no usable credential) · 400 (no organisation context)
      │                     → 403 (refused at the door)
      │
      4  AUTHORIZATION ──── ENFORCED, per route
      │                     the permission the route names, against the caller's role
      │                     attribute rules may also deny, and a deny beats a role allow
      │                     → 403
      │
      5  THE TRUST PLANE ── ENFORCED, for an AGENT's action — not for your API call
      │                     chain · posture · envelope → one verdict on THIS action
      │                     → 403 / 423 / 451 · and the decision is written down
      │
      6  THE HANDLER ────── the work happens
      │                     or the request is refused as malformed
      │                     → 400 / 422
      │
      7  THE RESPONSE ───── back across the boundary
                            JSON · raw bytes · none (204) · or a typed exception
```

Eight claims are compressed into that picture, and each of the rest of this
chapter's sections is one of them, derived.

> ⚠ **Where that ordering comes from, stated so you know what you are relying
> on.** Layers 1 and 2 are this package's own behaviour, and every claim about
> them here is measured against the build in your hands. Layers 3 to 5 are on
> the deployment's side, and **no SDK can measure the order in which a server
> runs its own checks.** That half of the picture is derived from two things:
> what the client's own documentation reports about admission and authorization,
> and the observable *consequences* — which status a refusal carries, which
> fields the error envelope does or does not populate, and what a caller
> receives when the same call is retried with the other credential type. The
> layer order is the reading that makes those consequences consistent, and it
> matches what [04.1](../04-the-api-surface/01-calling-the-api.md) and
> [04.2](../04-the-api-surface/02-errors-and-refusals.md) describe. Treat it as
> a well-supported model, not as something you can open and read.

> ⛔ **Layers 3 and 4 decide about *your call*. Layer 5 decides about an
> *agent's action*.** They are the two enforcement points on this path and they
> are easy to conflate because they produce overlapping statuses. The sentence
> to keep: **admission and authorization are access control on the caller; the
> Trust Plane is governance on the governed.** A `403` can come from either,
> and the request body will not say which — which is why the rest of this
> chapter teaches the shape of the evidence rather than the shape of the
> response.

## Construction: the client will not guess where core is

`sdk:aegis_sdk.AgenticOSClient` requires a base URL. There is no default host,
and the omission is deliberate enough that it raises
`sdk:aegis_sdk.ConfigurationError` before anything else happens.

Construction comes down to two decisions — **which deployment** you are pointing
at, and **which credential** you present — and you supply them in one of three
ways: directly, as a whole `sdk:aegis_sdk.ClientConfig`, or by letting
`AgenticOSClient.from_env()` read them from the environment. The third is the
one with architectural weight, because it is the only path where a *deployment*
configures the client rather than a developer typing it into a script — which is
what makes the same code promotable between environments. The mechanics, the
credential vocabulary and the provisioning patterns belong to
[04.3](../04-the-api-surface/03-credentials-and-keys.md); what belongs here is
what the choice decides.

The supported environment names are `AEGIS_`-prefixed; the older `AGENTIC_OS_`
names are still read and emit a one-time deprecation warning, and when both are
set the `AEGIS_` value wins.

The configuration surface is small, and it is the whole of what you control
about the connection:

| setting | default | note |
| --- | --- | --- |
| `timeout` | `30.0` | applied to connect, write, read **and** pool waits alike |
| `max_retries` | `3` | attempts, not retries-after-the-first |
| `retry_backoff` | `1.5` | base of an exponent, not seconds |
| `verify_ssl` | `True` | leave it |
| `debug` | `False` | logs requests, with bodies scrubbed |

`sdk:aegis_sdk.ClientConfig.with_base_url` and `ClientConfig.with_api_key` build
a variant without repeating the rest — useful when one job needs a longer
timeout than everything else.

> ⛔ **`max_retries=0` does not mean "do not retry". It means "do not make the
> request."** The retry loop *is* the send loop, so zero iterations send nothing
> and every call raises `sdk:aegis_sdk.ServiceError` with the message
> `Unknown error after retries` — including calls that would have returned
> `200`. Use `1` for a single attempt. The constructor happens to substitute the
> default for a literal `0`, so this bites through the environment variable and
> through the config object, which are the two paths a deployment configures
> rather than the one a developer types.

## Layer 1 — the module builds a request

A module namespace is stateless. It holds the transport and a set of path
templates, and that is all: `sdk:aegis_sdk.core.AgentsModule` has no agents in
it.

Every interpolated identifier is percent-encoded **at the call site**, before it
is spliced into the path, so a value containing `/` or `..` cannot shift which
route you address. Measured through the transport:

```text
get("abc-123")      ->  /api/v1/agents/abc-123
get("a/b")          ->  /api/v1/agents/a%2Fb
get("../../admin")  ->  /api/v1/agents/..%2F..%2Fadmin
```

The last line is the point. An id is a *segment*, and a slash inside one never
becomes a route separator.

> ⚠ **Encoding is applied to the raw value, so an already-escaped id gets
> double-escaped.** `%2F` in an id becomes `%252F` on the wire, because the `%`
> itself is encoded. If you are storing ids in escaped form, unescape before you
> pass them. Nothing errors — you simply address a different resource, or get a
> `404` that looks like a missing record.

Not every call site in the package is a request. Some methods raise
`sdk:aegis_sdk.UnsupportedOperationError` unconditionally, because the operation
they target does not exist. Those never reach the wire, so **no layer above is
consulted** and retrying is meaningless. This is an **open defect** enumerated in
[04.2](../04-the-api-surface/02-errors-and-refusals.md), and it is the purest
case of the rule that gives this whole chapter its value: **when a call fails,
establish that a request was made before you investigate the deployment at all.**

## Layer 2 — the transport types and signs it

This is the layer that touches the network, and it is shared by every module —
which is why the behaviour below is uniform no matter whose method you called.

Measured on the wire, a `GET` from a client holding an API key carries:

| header | value |
| --- | --- |
| `X-API-Key` | the key, verbatim |
| `X-SDK-Version` | the package version |
| `X-API-Version` | `v1` |
| `User-Agent` | `AgenticOS-SDK/<version>` |
| `Accept` | `application/json` |
| `Content-Type` | `application/json` — set per request, including on bodyless `GET`s |

**The credential is routed by its shape, not by what you intended.** A value
beginning `sk_live_` goes into `X-API-Key`; anything else goes into
`Authorization: Bearer`. Both are accepted by core, and the client picks the
canonical channel for each kind. Measured both ways.

> ⛔ **There is exactly one credential on the wire at a time, and the client is
> careful about it.** `set_api_key` rewrites both headers on every call: the one
> being set is written, and the other is *removed*. That matters because the
> same slot holds either an API key or a session JWT, and a swap that left the
> old header in place would present two identities and let the deployment
> authenticate as whichever it checked first. Measured: a key swap retires
> `Authorization`; a token swap retires `X-API-Key`.

**No organisation identifier is sent.** Measured: the header set above is
complete — there is no tenant or org header on any request. This is the
transport half of layer 3, and it is the architectural reason a body field
naming an organisation is at best ignored: **the caller does not get to say who
it is.** Tenancy is derived from the credential and resolved on the deployment.
To see which organisation your credential actually resolves to, ask:
`api:GET /api/v1/auth/me`.

**`Content-Type` is applied per request, not once on the connection**, and
precedence runs caller-supplied first, then whatever type the body's own encoder
computes, then JSON. That ordering is the fix for an upload failure in which a
client-wide JSON type overrode the multipart boundary a file upload needs — the
deployment could not parse the form and answered `422` on every upload call
while the module tests, which stubbed the transport, stayed green. The rule to
carry: **if you send a body the client does not type for you, and you care how
it is labelled, set the header yourself.**

## Layer 2, continued — the loop that sends it

The transport sends, and on failure decides whether to send again. Measured at
the default `max_retries` of 3:

| what failed | attempts | added delay |
| --- | ---: | --- |
| a connect, read or pool timeout | 3 | 2.5 s |
| a network or request error | 3 | 2.5 s |
| any HTTP status — `500`, `429`, `403` alike | **1** | none |

The backoff is `retry_backoff ** attempt`, so roughly one second then one and a
half, and it is not configurable from the environment. Only `max_retries` is.

**No HTTP status is retried.** The loop covers the case where the deployment
*did not answer*; it does not cover the case where it answered `503`. That
distinction is load-bearing at this point on the path: **a retry is only sound
where nothing happened, and this client can only tell that a reply is missing —
never that a request was not applied.** If your integration needs status-level
retry, you write it, and [04.5](../04-the-api-surface/05-concurrency-and-streams.md)
has the measured arithmetic and the statuses worth retrying.

*Design intent, not observable:* the reason the client declines to retry
statuses is a reading, not a measurement — the transport sends no idempotency
header, so a retried write is simply a second write. Treat the reading as the
book's explanation of a behaviour you can measure directly in the table above.

## Layer 3 — admission, and why a refusal here lies to you

This is the first layer on the deployment's side, and it runs **before your
route is consulted**. What happens here is coarse: the credential is resolved,
the organisation is resolved, and router-level gates decide whether you are
admitted at all.

The consequences are the ones that cost people days, and they are worth stating
as a list because they all present as "I do not have permission":

- **A refusal at admission is not about the route you called.** The route's own
  permission check was never reached, so what the route documents is irrelevant
  to your refusal.
- **A read can be refused exactly as a write would be.** Where a router-level
  gate is what refused you, nothing route-specific was consulted, so the
  read/write distinction never entered the decision. This is one of the platform
  behaviours [04.2](../04-the-api-surface/02-errors-and-refusals.md) records as
  an open defect, and it is scoped: it applies to the surfaces that carry such a
  gate, not to every route.
- **The message may name something to obtain, and obtaining it changes
  nothing.** The identity gate runs before the permission check on at least one
  surface, so grants that would have satisfied the later check sit inert.

The door/desk distinction is [04.1](../04-the-api-surface/01-calling-the-api.md)'s,
including the one-minute test that settles which you have. What this chapter adds
is *where* on the path it happens: at layer 3, before anything you can see in the
route's own documentation.

**The status here is not what you expect, and that is the trap.** A caller with no
organisation context is refused with a **`400`**, not a `401` or `403`. A caller
reading only the status code classifies that as a malformed request and goes
looking at their body. It is an identity problem.

## Layer 4 — authorization, the per-route decision

If admission lets you through, the route's own requirement is checked against
what your principal holds. This is where the two registries of
[04.1](../04-the-api-surface/01-calling-the-api.md) become load-bearing — roles
for a session, scopes for a key — and where a scope check turns out to be a
no-op for a session caller, because it is an API-key mechanism.

Two properties decide what you can predict from outside:

**There is more than one guard, and they do not agree by construction.** One
consults roles only; the other consults roles *and* attribute rules. Which one
guards a given route is not visible in any response. So **a permission granted to
your role and still refused is not necessarily a misconfigured role** — an
attribute rule may be denying you, and a deny overrides a role allow, so adding
the role again will not clear it.

**Two routes requiring what looks like the same permission can decide
differently for the same caller**, because one consults the attribute rules and
one does not. That is a real distinction, not a flake, and retrying is not a
remedy for it.

## Layer 5 — the Trust Plane, where a governed action is decided

This is the enforcement point the rest of this book exists to describe, and it
is the one most often mistaken for access control. The distinction is the
subject, not the mechanism:

| | layers 3 and 4 | layer 5 |
| --- | --- | --- |
| decides about | **the caller** — you, holding a credential | **an agent's action** — the delegate, mid-run |
| the question | may this principal call this route? | may *this agent* do *this thing*, given its authority? |
| what it consults | roles, scopes, attribute rules | the chain, the posture, the envelope |
| the artifact | — | **a decision, written down** |

The Trust Plane's answer is not a boolean the platform computes and discards. It
resolves into CARE's four-zone verification gradient — four values and exactly
four, delivered as the verdict's `level`:

```text
auto_approved      proceed, and record it
flagged            proceed, and surface it for attention
held               stop, and wait for a human
blocked            refuse
```

Three things about that output govern what you can build on it.

**`held` is not a soft `blocked`.** Under an enforced-execution path a held
action **ends the run** rather than queueing politely. Plan for a held action to
terminate the work, not to pause it — [the mental model](../01-orientation/02-the-mental-model.md)
has the incident where that mattered, and [06.5](05-the-execution-model.md) is
where you design for it.

**Thoroughness can upgrade a verdict.** A stricter setting promotes
`auto_approved` to `flagged`, so raising it produces more *signal*, not merely
more refusals. If your flagged count rises after you tighten something, that is
the feature.

**The verdict is reachable as a call, and as a record.** `api:POST /api/v1/trust/verify`
is the decision on demand; `api:GET /api/v1/trust/audit` is what it left behind.
That second one is unusual and worth designing around: most systems treat a
permission check as a step, and this one treats it as an object you can go back
and read.

### Where the refusal statuses come from

**There is no status that uniquely means "the Trust Plane refused you", and
`403` is not the authorization-only status it looks like.** Three statuses map
to three distinct exceptions, and the first of them is shared:

| status | exception | what it means |
| --- | --- | --- |
| `403` | `sdk:aegis_sdk.AuthorizationError` | an authorization decision at layers 3 or 4 — **or** a governance verdict that arrived with no structured half |
| `423` | `sdk:aegis_sdk.GovernanceViolationError` | a governance refusal: a policy, a budget, an approval requirement |
| `451` | `sdk:aegis_sdk.TrustViolationError` | a trust refusal: the delegated authority for this action does not hold |

⚠ **That first row is the sharpest trap on this page, so read it twice.** A
refusal on a governed action can arrive as a bare `403` carrying
`error_code: "FORBIDDEN"` and nothing else — byte-for-byte the shape of an
authorization refusal from layer 3 or 4 — and **nothing in the response says
which one you have.** So collapsing governance into "denied" is worse than
lossy: on those paths there is nothing to collapse, and the two are answered by
different changes made by different people.

> ⛔ **And the two causes *inside* that `403` are also indistinguishable.** A
> refusal caused by the governance apparatus being unreachable and one caused by
> the agent's own declared restriction arrive identically — same status, same
> code, both with an empty structured half — and the only thing that differs is
> the wording of a message you should not parse. This is the fail-closed
> property from [06.1](01-what-core-and-the-sdk-are.md) wearing a refusal's
> clothes: the platform could not evaluate, so it declined. **Retrying is the
> correct response to the first and the wrong response to the second.** Until
> the structured discriminator reaches you, the honest handling is to treat a
> refusal on a governed action as a refusal, and quote the request id to whoever
> operates the deployment when you need to know which kind it was. Full
> treatment in [04.2](../04-the-api-surface/02-errors-and-refusals.md).

## Layer 6 — the handler, and what a refusal leaves behind

If nothing refused you, the work happens. This is where a malformed body is
caught (`400`, `422`) — after admission and authorization, which is why a `422`
tells you your *request* was wrong and says nothing about your standing.

**What happens to the refused request is: nothing.** There is no partial
application to compensate for and no queue it sits in. The layers above run
before the handler, so a refusal at any of them means the handler was never
entered, and the request is gone. The response you get back is the canonical
error envelope, and the two fields that matter are the machine-readable code and
the request id — the correlation handle that lets somebody who was not there
find the same event on their side.

That is a stronger guarantee than it sounds, and it is worth naming as one. The
common alternative is a request that half-applied and returned an error, which
is where compensation logic gets invented. Here, a refusal is clean: either the
handler ran or it did not.

*Design intent, not observable:* that ordering is a design choice, not something
you can measure from the response. What you can measure is its consequence — a
refused call leaves no work product — and that is the part your design may rely
on.

## Layer 7 — the response, and its three success shapes

A `2xx` does not always give you back a dictionary. Measured:

| status | body | you receive |
| --- | --- | --- |
| `200` `201` `202` | JSON | the parsed value — a `dict` or a `list` |
| `200` `201` `202` | not JSON (an HTML error page, a PDF, a CSV) | **`bytes`**, the raw body |
| `202` with an empty body | — | **`b""`**, not `None` |
| `204` | — | `None` |

The bytes row is the one that catches people. A gateway or proxy answering `200`
with an HTML page gives you `bytes`; so does an endpoint that emits a file, and
so does a success whose body is empty. The client decides by *whether the body
parses*, never by the `Content-Type` header — a JSON body served under a wrong
type still parses, and the client will not change behaviour on a path that
currently works.

If you get `bytes` where you expected a mapping, you are looking at an unparsed
body, and the next move is to check your base URL for a redirect before you check
anything else. That trap, and the one-minute test that identifies it, are
[04.2](../04-the-api-surface/02-errors-and-refusals.md)'s.

### How the error becomes a typed exception

Every error the deployment returns is re-wrapped into one envelope before it
leaves:

```text
{"error": {"code": "FORBIDDEN",
           "message": "Constraint violation: ...",
           "details": {...},
           "request_id": "..."}}
```

The transport recognises an `error` key whose value is an object as that
envelope and reads the fields one level in. Anything else — including an `error`
key holding a plain string, which some servers use as the message — takes the
flat `{"detail": ...}` path unchanged, so a gateway or a non-Aegis server
answering in a different shape still parses as it always did.

Then it maps the status to a class and projects the envelope onto it. Measured
on a `403` carrying the envelope above:

| attribute | value |
| --- | --- |
| the exception's class | `sdk:aegis_sdk.AuthorizationError` |
| `exc.message` | the envelope's message — a string, not a dict |
| `exc.error_code` | `"FORBIDDEN"` |
| `exc.server_details` | `{"unverifiable_scope": "apparatus"}` — the structured fields |
| `exc.request_id` | the server's correlation id |
| `exc.status_code` | `403` |

Branch on those attributes; never on the message text. `sdk:aegis_sdk.AgenticOSError`
is the base every one of them inherits from, and its own documentation is
explicit that a **missing** key in `server_details` means the server sent
nothing under that name — never that the underlying condition is absent.

The transport-level failures are typed too, so `except AgenticOSError` covers
them: `sdk:aegis_sdk.TimeoutError` and `sdk:aegis_sdk.ConnectionError` for the
two ways the deployment can fail to answer, and `sdk:aegis_sdk.RateLimitError`
for a `429`, which carries a `retry_after` read from the response header. **The
client does not act on that number** — it is there for you.

### The typed model, and the exception that is not one

Most methods end by constructing a model from the parsed body. That construction
is strict, and it is the last thing that can fail — in a way the taxonomy above
does not cover.

Measured: driving `client.agents.get()` with a body missing required fields, or
carrying an unexpected enum value, raises `pydantic.ValidationError` — which is
a `ValueError`, and is **not** an `sdk:aegis_sdk.AgenticOSError`. An
`except AgenticOSError` block lets it straight through.

That is worth internalising rather than working around. It means a wire-shape
change on core surfaces to you as a validation error naming the fields that
moved, and it means the typed models are a real contract rather than a
decorative annotation. `sdk:aegis_sdk.Agent` and `sdk:aegis_sdk.User` are both
strict about required fields and about enumerated values — `unit_type` accepts
exactly two strings, `status` an exact set.

> ⚠ **The models you send are strict in the other direction too: they carry
> fields you did not set.** Measured: a create call given four arguments put
> **eight** fields in the request body, filling in `unit_type`, `agent_subtype`,
> `a2a_enabled` and `is_shadow_agent` from the client's own defaults. A body you
> assume equals the arguments you passed is not the body that goes out. When a
> create behaves unexpectedly, read the request body — the debug log prints it,
> scrubbed.

### The envelope the deployment sends, and who unwraps it

Many endpoints wrap their payload as `{"data": ...}`, sometimes beside a
pagination sibling like `{"total": 12}`. A client that reads fields straight off
the outer object finds none of them, and the failure is quiet: a list reads as
empty and a single object reads as missing.

**The transport never unwraps.** Doing it there would change the return shape of
every method at once, including the many that are correct today and the
endpoints that answer with a bare list or with a payload that legitimately owns
a `data` field of its own.

Unwrapping is therefore opt-in per call site, and it is guarded: a response is
treated as an envelope only when its `data` key is accompanied by nothing
outside a known set of pagination siblings. Measured — `{"data": [...], "total":
12}` unwraps; `{"version": 1, "data": ...}` does not, because `data` there is one
field of the answer rather than a wrapper around it.

Measured across the whole package: **exactly one module opts in —
`sdk:aegis_sdk.core.PipelinesModule`.** Everything else hands you the
deployment's body as it arrived.

That single fact explains a class of confusion worth naming: **two methods on
different modules can return the same conceptual noun in different shapes**, one
unwrapped and one not. Before you subscript a result, know which module it came
from. The shape hazard itself — and the habit of checking the type once at any
call site you are unsure about — belongs to
[the orientation chapter](../01-orientation/01-what-you-were-given.md); what a
*field* of a returned model does and does not guarantee is
[04.6](../04-the-api-surface/06-reading-a-response-honestly.md)'s.

## Authentication is a request like any other

There is no bypass path. `api:POST /api/v1/auth/login` returns a nested envelope
— a `user` object and a `tokens` object — and the module flattens `tokens` onto
the returned `sdk:aegis_sdk.AuthToken` while attaching the parsed
`sdk:aegis_sdk.User` beside it, so you do not need a second round trip. If the
body is not that shape, the module raises `sdk:aegis_sdk.AgenticOSError` naming
the keys it expected and the keys it received, rather than a bare `KeyError`.

> ⛔ **Logging in does not authenticate the client. The install step is yours.**
>
> `client.auth.login()` returns a token; it does not adopt it. The client's
> configuration already holds either an API key or a session JWT, never both, and
> it changes only when you tell it to. Measured: after a `login()` on a client
> constructed with an API key, the next request still carried the key. Skipping
> the install step is the difference between a session and a key — presented as
> whichever you had before, and resolved at layer 3. The call itself, and the two
> ways to install what it returns, are
> [04.3](../04-the-api-surface/03-credentials-and-keys.md)'s.

Refresh follows the same rule, with one more consequence.
`api:POST /api/v1/auth/refresh` returns a new token pair, and the refresh token
is single-use: rotation retires **both** halves of the pair it replaces, so the
previous access token is revoked immediately rather than at its expiry. Of two
concurrent refreshes presenting the same refresh token, exactly one succeeds and
the other raises `sdk:aegis_sdk.AuthenticationError`.

**The client never refreshes for you.** Nothing watches for a `401` and retries
with a fresh token. A long-running script that outlives its access token will
start failing on a clock, and the failure will arrive as
`sdk:aegis_sdk.AuthenticationError` on calls that were working a minute ago.

## The path again, as a sequence

The same seven layers, from your line of code to your exception — this form
carries the fan-out and the returns that the tree at the top of the chapter
flattens:

```text
    your code          module · transport        the deployment            Trust Plane
        │                       │                       │                          │
        │                       │                       │                          │
        │  the call             │                       │                          │
        │──────────────────────▶│                       │                          │
        │                       │                       │                          │
        │                       │ encode ids, add headers, one credential          │
        │                       │───┐                   │                          │
        │                       │◀──┘                   │                          │
        │                       │                       │                          │
        │                       │ HTTPS                 │                          │
        │                       │──────────────────────▶│                          │
        │                       │                       │                          │
        │  only transport failures are retried — backoff 1s, then 1.5s             │
        │                       │                       │                          │
        │                       │                       │ ADMISSION — credential + organisation
        │                       │                       │───┐                      │
        │                       │                       │◀──┘                      │
        │                       │                       │ AUTHORIZATION — the route's requirement
        │                       │                       │───┐                      │
        │                       │                       │◀──┘                      │
        │                       │                       │                          │
        │  ── opt: an agent's action, mid-run                                      │
        │                       │                       │                          │
        │                       │                       │ may this agent do this?  │
        │                       │                       │─────────────────────────▶│
        │                       │                       │◀─────────────────────────│
        │                       │                       │ the verdict              │
        │                       │                       │ auto_approved · flagged · held · blocked
        │                       │                       │                          │
        │  ── alt: a layer refused                                                 │
        │                       │                       │                          │
        │  403 / 423 / 451 — the handler was never entered                         │
        │◀──────────────────────┼───────────────────────│                          │
        │                       │                       │                          │
        │  ── else: permitted   │                       │                          │
        │                       │                       │                          │
        │                       │                       │ HANDLER                  │
        │                       │                       │───┐                      │
        │                       │                       │◀──┘                      │
        │                       │◀──────────────────────│                          │
        │                       │ status + body         │                          │
        │                       │                       │                          │
        │                       │ map status, project the error envelope           │
        │                       │───┐                   │                          │
        │                       │◀──┘                   │                          │
        │                       │ construct the typed model — strictly             │
        │                       │───┐                   │                          │
        │                       │◀──┘                   │                          │
        │                       │                       │                          │
        │  model · dict · bytes · or a typed exception  │                          │
        │◀──────────────────────│                       │                          │
        │                       │                       │                          │
```

## What the path does not do for you

Stated plainly, because each of these is something integrators assume is
handled. None of it is a defect; all of it is yours to build:

- **No enforcement.** Nothing on this path decides anything in your process. The
  only refusal your own code produces is the strict model construction, and that
  is a shape check, not a governance one.
- **No status retry.** See layer 2. `RateLimitError` even carries the number to
  wait, and nothing reads it.
- **No token refresh.** See above.
- **No idempotency key.** A retried write is a second write, and the transport's
  own retry covers a case where the deployment may not have received the first.
- **No rate limiting.** Nothing throttles you below the connection pool's
  ceiling.
- **No ordering guarantee.** `asyncio.gather` returns results in argument order
  and says nothing about the order the deployment saw them in.

Everything above is checkable from the build in your hands. Everything about
*what the deployment checks* — whether a permission is consulted, whether an
attribute rule denies you, whether the Trust Plane was reachable when it
answered — is not, and this book marks it where it appears rather than letting
you assume it.

---

*Next: [06.3 — The governed organisation](03-the-governed-organization.md)*
