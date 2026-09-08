# Error taxonomy — the exception class does not identify the status

**Scope:** every `except` clause you write against this client.

Every failure raised by this client is an `sdk:aegis_sdk.AgenticOSError` or a
subclass of one. The mapping from HTTP status to subclass is **partial**, and
the gaps are not at the edges — they include two statuses an integrator meets
routinely.

## MUST 1 — Discriminate on the status code, not on the subclass alone

The status is carried in `details["status_code"]` on every raised error. Read it
there.

```python
# DO
except AgenticOSError as exc:
    status = exc.details.get("status_code")
    if status == 409:
        ...      # conflict — retry is wrong, the state moved
    elif status == 410:
        ...      # gone — stop polling this id

# DO NOT
except AgenticOSError:
    ...          # 409, 410, 418 and a JSON decode failure all land here
```

**Why:** **no subclass is mapped to 409 or 410.** Both fall through to the base
class with the message `"Unexpected status code: <n>"`. A handler that branches
on subclass treats a conflict and a permanent deletion identically, and the most
common default — retry — is wrong for both.

The same fall-through catches any 2xx that is not 200, 201, 202 or 204. A 206 or
a 207 is **raised as an error**, not returned.

## MUST 2 — Never render the exception message as the explanation

```python
# DO
detail = exc.details.get("message") or f"HTTP {exc.details.get('status_code')}"

# DO NOT
log.error("call failed: %s", exc)     # can print exactly: call failed: None
```

**Why:** the detail extractor builds `message` from the first of the body's
`detail`, `message`, `error` keys that is present. When a JSON error body
carries none of them the key is set to `None` — and `details.get("message",
"Insufficient permissions")` then returns `None`, not the default, because the
key **exists**. `str(exc)` is the string `"None"`.

Verified directly:

```python
>>> {"message": None}.get("message", "Insufficient permissions")
None
```

This lands hardest exactly where you need the message most: a 403 whose body is
a bare object gives you an `AuthorizationError` reading `None`, and the
[the credential guardrail](credential-reachability.md)'s diagnosis is the one you now have to do by hand.

## MUST 3 — Treat a transport error and a refusal as different outcomes

`sdk:aegis_sdk.ConnectionError` and `sdk:aegis_sdk.TimeoutError` mean the
deployment did not answer. They are **not** evidence about permissions,
existence, or state.

**Why:** a timeout that is recorded as a denial, or as an empty result, is a
wrong answer wearing the grammar of a measurement — and it is the shape that
makes a whole sweep read clean for the wrong reason.

## MUST 4 — Retry on the statuses that mean "later", never on the ones that mean "no"

| retry | `sdk:aegis_sdk.RateLimitError` (429 — honour `retry_after`), `sdk:aegis_sdk.ServiceError` (5xx), transport errors |
| never | 400, 401, 403, 404, 409, 410, 422, 423, 451 |

**Why:** retrying a 403 produces a slower 403 and a rate limit. Retrying a 409
re-asserts a precondition that has already failed.

## MUST NOT — Read `sdk:aegis_sdk.UnsupportedOperationError` as an outage

It means the method targets a server operation that does not exist and is not
planned. It is a deprecation shim kept for one minor cycle. It will not recover,
and no amount of waiting or retrying changes it — which is precisely what
distinguishes it from `sdk:aegis_sdk.ServiceUnavailableError`, where the
capability exists and the infrastructure is down.

## What this does not tell you

Which status a given route returns. That is a property of the deployment, and
the only way to know it is to call the route and read
`details["status_code"]`. This file governs what you do with the answer, not
what the answer will be.
