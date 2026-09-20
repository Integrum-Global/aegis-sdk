# Part 04 — The API surface

**Audience: you are calling Aegis over HTTP directly, or you are debugging a call
that failed.** Most of the time the SDK is the better path — it is typed, it
handles path encoding, and parts 02 and 03 are written against it. This part is
for when you need the layer underneath: another language, a webhook receiver, a
proxy, an authorization failure you cannot explain, or any question about what
the client does under load.

> ⚠ **Be precise about what the SDK retries, because the scope is narrower than
> the word usually implies.** It retries a request that got **no answer** — a
> connection failure, a timeout — and it retries **no HTTP status at all**,
> including `429` and `503`. Counts and the arithmetic are in
> [04.5](05-concurrency-and-streams.md). If your integration needs status-level
> retry, that layer is yours to write.

| #    | Chapter                                                            | Read it when                                                            |
| ---- | ------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| 04.1 | [Calling the API](01-calling-the-api.md)                           | You are calling it directly, or a 403 is not making sense               |
| 04.2 | [Errors and refusals](02-errors-and-refusals.md)                   | Something raised and you need to know whether to retry, fix, or file it |
| 04.3 | [Credentials, and what a key is not](03-credentials-and-keys.md)   | You are issuing, rotating or auditing API keys                          |
| 04.4 | [Lists, filters and pagination](04-lists-and-pagination.md)        | You are reading an organisation big enough to have a second page        |
| 04.5 | [Concurrency, timeouts and streams](05-concurrency-and-streams.md) | You are running calls in parallel, or consuming an agent's output live  |
| 04.6 | [Reading a response honestly](06-reading-a-response-honestly.md)   | A field is `None` and you are about to conclude something from it       |

**Read 04.2 first if something has already gone wrong.** It carries the
status-to-exception table, the seven statuses with no branch at all, the five
failures that are not in this client's exception hierarchy, and the four-way
split — not reached, not known, refused, fault — that decides what you change
next. A `try/except` written from the documentation alone lets all five past, and
treats a `401` a fresh credential cannot clear as a credential problem.

## Start here if you have a 403

Aegis has **two credential models**: personas belong to user sessions, scopes
belong to API keys. A route gated on personas wants a session, and a wider scope
will not substitute for one. Chapter 04.1 gives you a one-minute test that tells
you which model a route follows.

Run it before you re-issue keys, widen scopes, or conclude your permission model
is wrong — a 403 names the permission, not the layer that decided.

## What the route anchors in this book mean

Every operation named in this handbook is written as an **api anchor** — the
method and path in backticks behind an `api:` prefix, as in
`api:GET /api/v1/agents` — and every one is checked by
`python -m aegis_sdk.handbook.check` against the calls this package actually
makes. A resolving anchor tells you the operation exists in the surface you were
given. Where this book says something is _enforced_, that claim rests on
observed behaviour, not on the anchor.

**Run the check, and look routes up rather than deriving them.** The quota
**read** is `api:GET /api/v1/features/limits`, while the quota **write** is
`api:POST /api/v1/billing/quotas/adjust` — **the read and the write of the same
noun do not share a prefix**, and nothing in the module name predicts it.

**Do not infer a route from a noun.** Sibling operations on the same concept are
not reliably siblings in the path. When you need the read for something whose
write you know, look it up. Build the same habit into your own code: a
plausible-looking route string is easy to write and considerably more expensive
to discover later.

---

_Next: [04.1 — Calling the API](01-calling-the-api.md)_
