# 04.2 — Every failure this client can raise

There are **four** kinds of bad outcome, and telling them apart is the whole job:

| | what happened | what you have measured |
| --- | --- | --- |
| **not reached** | the deployment never answered | **nothing** — not permissions, not existence, not state |
| **not known** | it answered: *I do not know who is asking, in the way this operation requires* | your authentication, and nothing about your permissions |
| **refused** | it answered: *I know who you are, and the answer is no* | a governance verdict |
| **fault** | something broke — a malformed request, a server error, a contract the client cannot model | that somebody has to fix something |

**A refusal is the product working.** [Part 02](../02-working-through-the-harness/)
makes that claim; this chapter is where it becomes actionable. A refusal is
evidence, and it belongs in your audit story rather than in your incident
channel. The other three do not.

⚠ **The distinction that costs a day is *not known* versus *refused* — `401`
versus `403`.** They read alike, they are both "denied" in casual speech, and
they have opposite remedies. A `401` says the platform could not establish who is
asking to the standard this operation demands; reissuing a credential may be the
answer, and no permission change will be. A `403` says it established exactly who
you are and declined; reissuing the credential is wasted work.

An architect who learns "denied means 403" will misread the other one, and the
misreading is expensive in both directions — see § *A refusal is not one status*
below, which is the case where a perfectly valid key gets a `401`.

The rest of this chapter is the mapping that lets you tell. For the diagnostic
ladder that uses it — which rung to work, in what order, and what not to change
until you have —
see [the refusal-diagnosis skill](../../coc/skills/diagnosing-a-refusal.md)
shipped beside this book, and
[the error-taxonomy guardrail](../../coc/guardrails/error-taxonomy.md) it rests
on.

## The status-to-exception table, measured

Every entry below was produced by driving `sdk:aegis_sdk.AgenticOSClient`'s
transport against each status in turn and recording what came back. Reproduce it
on your own build; it takes under a second.

| status | what the client does | kind |
| --- | --- | --- |
| `200` `201` `202` | returns the parsed JSON body | — |
| `204` | returns `None` | — |
| `400` | `sdk:aegis_sdk.ValidationError` | fault (your request) |
| `401` | `sdk:aegis_sdk.AuthenticationError` | fault (your credential) |
| `403` | `sdk:aegis_sdk.AuthorizationError` | **refusal** |
| `404` | `sdk:aegis_sdk.NotFoundError` | either — see below |
| `422` | `sdk:aegis_sdk.ValidationError` | fault (your request) |
| `423` | `sdk:aegis_sdk.GovernanceViolationError` | **refusal** |
| `429` | `sdk:aegis_sdk.RateLimitError` | not reached, yet |
| `451` | `sdk:aegis_sdk.TrustViolationError` | **refusal** |
| `5xx` | `sdk:aegis_sdk.ServiceError` | fault (theirs) |
| **anything else** | `sdk:aegis_sdk.AgenticOSError`, message `Unexpected status code: <n>` | unclassified |

Three of those are refusals and each says something different. `403` is an
authorization decision — a principal was judged and found wanting. `423` is a
**governance** refusal: a policy, a budget, an approval requirement. `451` is a
**trust** refusal: the delegated authority for this action does not hold. If you
collapse all three into "permission denied" you lose the distinction your own
evidence export depends on, because they are answered by three different people.

`404` is the ambiguous one. It means *this client asked for something the server
does not have* — which covers a deleted record, a mistyped id, and a route that
does not exist on this deployment. The client cannot separate them, and neither
can you from the status alone.

## A refusal is not one status

At least three different mechanisms refuse a caller, and they do not all produce
a `403`. Knowing which you are looking at decides what you change next.

**1. A permission-level denial gives `403`.** The principal was identified,
judged against what the route requires, and declined. This is the case the word
"denied" makes people picture, and it is the only one of the three where looking
at roles and permissions is the right next move.

**2. Some surfaces are gated at the whole-router level, so even a *read* is
refused for an API key.** This is the open defect [04.1](01-calling-the-api.md)
documents, and it is worth restating in status terms: the refusal is a `403`
carrying a message about personas, and it is **not about the route you called**.
It is admission at the door. A read that looks harmless is refused exactly as a
write would be, because nothing route-specific was ever consulted.

**3. At least one control requires a verified interactive session and answers
`401`, not `403`.** This is the one that costs the day. Your key is valid, it is
unexpired, it was accepted everywhere else this morning — and this operation
answers `401` because it demands a kind of authentication a key cannot supply.
The client raises `sdk:aegis_sdk.AuthenticationError`, whose own documentation
says "API key is invalid or malformed / token has expired", and **both of those
readings are wrong here**. Reissuing the key produces an identical `401`.

*Design intent, not observable:* which control demands a verified session, and
what makes a session count as verified, is decided at the platform side. You
cannot query it from here and this book will not invent a way to tell you.

**What you can do from outside** is the same sibling comparison
[04.1](01-calling-the-api.md) uses, with one extra rung: if a `401` survives a
freshly-issued key, stop treating it as a credential problem and retry the
identical call with an interactive session. If the session succeeds, you have
found mechanism 3, and no key of any scope will ever pass.

```python
# The discriminator, in full. Run all three; the pattern identifies the mechanism.
#   key -> 401, fresh key -> 401, session -> 200   ... mechanism 3, use a session
#   key -> 403, session -> 200                     ... mechanism 2, use a session
#   key -> 403, session -> 403                     ... mechanism 1, look at permissions
```

## Holding the right grants is not sufficient

The most confusing refusal on this API is the one where you hold every grant the
operation names and are still refused — **with those grants never consulted**.

The mechanism is ordering. On at least one surface the identity gate runs
*before* the permission check, so a caller who fails the first gate is turned
away while the grants that would have satisfied the second sit inert. The
verdict is a `403` whose message names something to obtain, and obtaining it
changes nothing.

Your instinct on seeing that message will be to add permissions. **Adding
permissions will not help**, and you will finish holding a wider credential than
the job needs, permanently, having fixed nothing. This is the same trap
[04.1](01-calling-the-api.md) frames as *"was I refused at the door, or at the
desk?"* — and the answer is not in the response body.

The observable signature, from your side, is precisely that: **a change that
should have worked and did not.** Treat "I granted the thing it asked for and
the refusal is byte-identical" as diagnostic rather than as a reason to grant
more. Take it to whoever administers your organisation, who can see the ordering
and the rules; you cannot.

## The gaps, named — because the table above has a bottom row for a reason

**Seven statuses an integrator meets routinely have no branch at all.** They fall
to the base class carrying `Unexpected status code: <n>`, which reads like a
platform malfunction and is nothing of the sort:

| status | what it actually means | what a naive handler does |
| --- | --- | --- |
| `402` | payment required | retries |
| `405` | wrong method for this path | retries |
| `409` | conflict — the state moved under you | **retries, and re-loses** |
| `410` | gone — permanently, not temporarily | **polls forever** |
| `413` `415` `428` | too large / wrong content type / precondition required | retries |

`409` and `410` are the expensive two. A conflict means your precondition has
already failed, so re-asserting it fails again; a `410` means the id will never
come back, so a poll loop on it never terminates. Both are the shape a
retry-by-default handler gets exactly wrong.

**And the boundary is wide, not a corner case.** That the client has no branch
for either is checkable by you, in seconds, and is the fact this book anchors on.
How much of the platform can *emit* them is not checkable from here: the count
measured on the platform's own side is **90 call sites** across the two statuses.
Treat that number as reported rather than verified — you cannot reproduce it from
what you were given, which is exactly why it is written down as a magnitude
rather than left as "some". What follows from it is not a magnitude: **write the
`409` and `410` branches**, because the client will not, and the base class will
not tell you which one you have without reading the status.

⚠ **`sdk:aegis_sdk.PaymentError` exists, is exported, and is never raised.** The
transport has no `402` branch, and the whole package contains no site that
raises it. Do not write an `except PaymentError` and believe you have covered
billing failures; a `402` arrives as the base class.

**Two more gaps are easy to miss because they look like success.**

- **Any `2xx` that is not `200`, `201`, `202` or `204` is raised as an error.** A
  `203`, `205`, `206` or `207` becomes `Unexpected status code`. If a partial or
  multi-status response ever appears on a route you use, you will see it as a
  failure.
- **No redirect is followed.** The client is configured not to, so a `301`,
  `302`, `307` or `308` becomes `Unexpected status code: 307`. This is the
  single most confusing first-day failure: point the client at a base URL that
  redirects — `http` where the deployment wants `https`, a host that appends a
  trailing slash, a gateway that normalises paths — and **every call fails with
  a message that mentions nothing about redirects.** Check your base URL with a
  plain `curl -i` before you debug anything else.

## What escapes the taxonomy entirely

`except AgenticOSError` is the idiom, and it is not complete. Four failures are
not `sdk:aegis_sdk.AgenticOSError` at all, measured:

| what happens | what is raised |
| --- | --- |
| a `200`, `201` or `202` whose body is empty, truncated, or not JSON | `json.JSONDecodeError` |
| a list route that returns an envelope where this client expects a bare array | `TypeError` |
| **a client method that hands the transport a keyword it does not accept** | `TypeError`, **before anything is sent** |
| any call on a client you already closed | `RuntimeError` |
| **any transport failure during a stream** | the raw underlying HTTP-library exception |

The first is the one you will hit most often. A proxy or gateway that returns an
HTML page with a `200`, or an endpoint that accepts with `202` and an empty
body, both produce a decode error rather than anything in this book's
vocabulary. The last is covered in [04.5](05-concurrency-and-streams.md): the
streaming path has no error translation, so a read timeout mid-stream arrives
raw.

If you are writing a library on top of this one, catch `Exception` at your
boundary and re-raise something of your own. If you are writing a script, at
least know that a bare `except AgenticOSError` will let five things past.

### The middle row deserves its own warning: some methods cannot execute at all

A client method builds a request by passing keyword arguments down to the
transport. Anything the transport does not declare falls through to the
underlying HTTP library, and there it either **raises**, or — worse — is
**quietly accepted and does something else**. Neither is visible to a type
checker, because the argument disappears into a catch-all before anything can
check it.

Measured on this build: **seven call sites pass the transport a keyword it does
not declare.** Two of them make their method impossible to call at all.

```python
await client.compliance.export_audit(          # api:POST /api/v1/compliance/audit/export
    start_date="2024-01-01", end_date="2024-01-31", format="csv",
)
# TypeError: ... got an unexpected keyword argument 'raw_response'
```

`sdk:aegis_sdk.modules.ComplianceModule.export_audit` and
`sdk:aegis_sdk.modules.ComplianceModule.export_soc2_evidence` both raise that,
and — the part that matters for diagnosis — **zero requests reach the wire.**
Verified by counting requests at a mock transport that would have answered
`200`: both methods, 0 requests; a sibling on the same module that passes no
stray keyword, 1 request.

Read that as a general instruction, not as two names to avoid. **When a call
fails, establish whether a request was made before you look at the
deployment at all.** A pre-wire failure is a client defect and no amount of
credential, permission or network investigation will move it — and it is the
one failure mode where the deployment is definitively not involved.

```python
# `--transports-only` answers this offline, before any network
#   python -m aegis_sdk.coc.probe --transports-only
#
# Or discriminate a single call: if AGENTIC_OS_DEBUG=true logs no
# "SDK Request:" line for it, nothing was sent.
```

The other five sites are the quieter half: a keyword the HTTP library *does*
accept, which sends a form body or a file upload where a JSON body was intended,
or attaches query parameters to a stream. Those fail on the wire rather than
before it, so they surface as a `400` or a `422` that looks like your data is
wrong. **UNVERIFIED:** whether each of the five is a defect or deliberate — some
are on upload paths where a non-JSON body is correct. What is settled is that the
type checker could not have told you either way.

The general lesson is the one worth carrying past this release: **a method being
exported, documented and typed is not evidence that it has ever run.** Where this
book documents a method's behaviour, it documents one that was traced end to end;
where you are about to depend on one this book does not cover, call it once
against a deployment you can afford to be wrong about before you build on it.

## Two failures that happen before any request is sent

Neither is a deployment problem, and both are frequently reported as one.

**`sdk:aegis_sdk.ConfigurationError`** — no base URL. Nothing was contacted.
Covered in [01.3](../01-orientation/03-your-first-session.md).

**`sdk:aegis_sdk.UnsupportedOperationError`** — the method you called targets a
server operation that does not exist. **Six methods raise it unconditionally,
before any request is made**, and all six are on the trust surface:
`sdk:aegis_sdk.trust.ChainsModule.suspend` and
`sdk:aegis_sdk.trust.ChainsModule.reinstate`, the three delegation *read*
methods, and a single-entry audit read. Two more raise it only for an argument
the client cannot honour — asking the analytics exports for `csv` or `xlsx`,
which this transport cannot return because it always parses a response as JSON.
None of these recover, and retrying is meaningless: the operation is not
implemented, not down.

**That is not the whole of the dead surface.** Separately, **eighteen methods
carry a warning in their own docstring that the route they call currently
returns `404`** — a known-dead path rather than a missing record. They are
spread across agent executions, skills, objectives, sessions, analytics and
audit-log reads. When a `NotFoundError` looks impossible against data you know
exists, read the method's docstring before you doubt your data:

```python
help(client.objectives.submit)   # the warning is in the docstring, not the type
```

Contrast `sdk:aegis_sdk.ServiceUnavailableError`, which means the capability
exists and the infrastructure is down. It is exported, and — like
`PaymentError` — **no site in this package raises it.**

## Reading the message, and why you should not

The exception's string is built from the first of the body's `detail`, `message`
or `error` keys that is present. When an error body carries none of them, that
value is `None` — and because the key **exists** and holds `None`, a
`details.get("message", "some default")` returns `None` rather than your default.
Measured, on a `403`:

| the error body | `str(exc)` |
| --- | --- |
| `{"detail": "real detail"}` | `'real detail'` |
| `{}` or `{"foo": "bar"}` | `'None'` |
| no body at all | `'Unknown error'` |
| `<html>…</html>` from a proxy | the raw HTML, to 500 characters |

So `log.error("call failed: %s", exc)` can log, literally, `call failed: None` —
at exactly the moment you most need the message. Build your own line from the
status:

```python
from aegis_sdk import AgenticOSError

try:
    await client.agents.list()
except AgenticOSError as exc:
    status = exc.details.get("status_code")
    detail = exc.details.get("message") or f"HTTP {status}"
    log.error("agents.list failed: %s (%s)", detail, status)
```

**The status code is on every raised error**, at `exc.details["status_code"]`,
including the unclassified ones. That is the field to branch on — not the
subclass, which cannot distinguish `409` from `410` from `418`.

> ⚠ **A `422` puts a *list* where you expect a string.** A field-validation
> failure carries a list of per-field objects, and that list is what lands in the
> message. `str(exc)` becomes the printed repr of a list of dicts, each with the
> field path and the reason. It is genuinely the most useful error body the API
> produces and the least readable thing to print. Iterate it rather than logging
> it:
>
> ```python
> except ValidationError as exc:
>     problems = exc.details.get("message")
>     if isinstance(problems, list):
>         for p in problems:
>             log.error("  %s: %s", ".".join(str(x) for x in p.get("loc", [])), p.get("msg"))
> ```

## What to retry, and what never to

| | |
| --- | --- |
| **retry** | `sdk:aegis_sdk.RateLimitError` (honour its `retry_after`), `sdk:aegis_sdk.ServiceError`, `sdk:aegis_sdk.ConnectionError`, `sdk:aegis_sdk.TimeoutError` |
| **never** | `400` `401` `403` `404` `409` `410` `422` `423` `451`, and every `sdk:aegis_sdk.UnsupportedOperationError` |

Retrying a refusal produces a slower refusal and, eventually, a rate limit.
Retrying a `409` re-asserts a precondition that has already failed.

⚠ **The client does not do this for you, and [04.5](05-concurrency-and-streams.md)
is blunt about the gap.** It retries *transport* failures only — no HTTP status
is ever retried, including `429` and `503`. `RateLimitError` carries a
`retry_after` parsed from the response header, and nothing acts on it. If your
integration needs status-level retry, you write it.

## The one distinction to keep hold of

A `sdk:aegis_sdk.ConnectionError` or a `sdk:aegis_sdk.TimeoutError` is not
evidence about permissions, about existence, or about state. It is the absence of
an answer.

This matters most in a sweep. If you are walking a hundred routes to establish
what your credential can reach, a timeout recorded as a denial — or worse, as an
empty result — produces a report that looks clean for the wrong reason. Record
"not reached" as its own outcome, distinct from both "allowed" and "refused",
and count it. A sweep with unexplained gaps is a sweep with an unknown answer,
and saying so is the whole of the discipline.

---

*Next: [04.3 — Credentials, and what a key is not](03-credentials-and-keys.md)*
