# Part 04 — The API surface

**Audience: you are calling Aegis over HTTP directly, or you are debugging a call
that failed.** Most of the time the SDK is the better path — it is typed, it
handles path encoding, and parts 02 and 03 are written against it. This part is
for when you need the layer underneath: another language, a webhook receiver, a
proxy, an authorization failure you cannot explain, or any question about what
the client does under load.

> ⚠ **One correction to make up front, because this README used to make it.**
> The SDK does not "handle retries" in the sense most readers take. It retries a
> request that got **no answer** — a connection failure, a timeout — and it
> retries **no HTTP status at all**, including `429` and `503`. Measured counts
> and the arithmetic are in [04.5](05-concurrency-and-streams.md). If your
> integration needs status-level retry, you are writing it.

| #    | Chapter                                                                     | Read it when                                                              |
| ---- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 04.1 | [Calling the API](01-calling-the-api.md)                                     | You are calling it directly, or a 403 is not making sense                  |
| 04.2 | [Errors and refusals](02-errors-and-refusals.md)                             | Something raised and you need to know whether to retry, fix, or file it    |
| 04.3 | [Credentials, and what a key is not](03-credentials-and-keys.md)             | You are issuing, rotating or auditing API keys                             |
| 04.4 | [Lists, filters and pagination](04-lists-and-pagination.md)                  | You are reading an organisation big enough to have a second page           |
| 04.5 | [Concurrency, timeouts and streams](05-concurrency-and-streams.md)           | You are running calls in parallel, or consuming an agent's output live     |
| 04.6 | [Reading a response honestly](06-reading-a-response-honestly.md)             | A field is `None` and you are about to conclude something from it          |

**Read 04.2 first if something has already gone wrong.** It carries the measured
status-to-exception table, the seven statuses with no branch at all, the five
failures that are not in this client's exception hierarchy, and the four-way
split — not reached, not known, refused, fault — that decides what you change
next. A `try/except` written from the documentation alone lets all five past, and
treats a `401` a fresh credential cannot clear as a credential problem.

## Start here if you have a 403

There is an **open defect** in which a large number of routes are unreachable by
*every* API key regardless of the scopes attached to it, and the denial is a
generic 403 indistinguishable from a genuine scope problem. Chapter 04.1 gives
you a one-minute test that settles which one you have.

Do this before you re-issue keys, widen scopes, or conclude your permission model
is wrong. It is the single most common wasted day on this platform.

## What the route anchors in this book mean, and what they do not

Every operation named in this handbook is written as an **api anchor** — the
method and path in backticks behind an `api:` prefix, as in
`api:GET /api/v1/agents` — and every one is checked by
`python -m aegis_sdk.handbook.check`. Be precise about the guarantee:

- **It proves this client declares the operation.** The route table is extracted
  from the calls this package actually makes.
- **It does not prove the server enforces anything on it**, returns the status
  the prose claims, or checks a permission.
- **It is the client's belief about the API, not the API.** If the client is
  wrong about a path, the anchor is wrong in the same direction and nothing
  notices. A document emitted by the server would be a stronger anchor; it is not
  available offline, which is the whole constraint.

So treat a resolving anchor as "this operation exists in the surface you were
given" and nothing more. Where this book claims something is *enforced*, that
claim rests on observed behaviour or is labelled — never on the anchor alone.

**What it does catch is worth one concrete example, because it is not
hypothetical.** An author writing the companion artifacts asserted
`GET /api/v1/billing/quotas` for reading a quota. The check rejected it: this
client declares no such operation. The quota **read** is
`api:GET /api/v1/features/limits`, while the quota **write** is
`api:POST /api/v1/billing/quotas/adjust` — **the read and the write of the same
noun do not share a prefix**, and nothing in the module name predicts it.

Two things follow, and the second is the one to carry with you:

1. **Do not infer a route from a noun.** Sibling operations on the same concept
   are not reliably siblings in the path. When you need the read for something
   whose write you know, look it up rather than deriving it.
2. **The claim was wrong, plausible, and written by someone who knew the
   system.** It was stopped by a mechanical check rather than by care. That is
   the whole argument for running `python -m aegis_sdk.handbook.check` yourself
   rather than trusting that the prose was written carefully — and for building
   the same habit into your own code, where a plausible-looking route string is
   equally easy to write and considerably more expensive to discover.
