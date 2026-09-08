# 01.3 — Your first working session

End to end, from nothing to a call that proves your credentials, your network
path and your permissions all work. Fifteen minutes, and it is worth doing before
you write anything real: almost every "the SDK is broken" report resolves to one
of the three things this chapter separates.

## Install

```
pip install -e .
```

> ⚠ **Install from source, not from the public index.** The name `aegis-sdk` on
> PyPI belongs to an unrelated third-party package. `pip install aegis-sdk` will
> succeed, install something else entirely, and then fail in ways that look like
> your code is wrong.

Confirm you have the right thing:

```python
import aegis_sdk
print(aegis_sdk.__version__)
```

## Point it at your deployment

There is **no default base URL, deliberately, and it will refuse to start
without one.**

```bash
export AGENTIC_OS_BASE_URL="https://aegis.your-company.example"   # your deployment
export AGENTIC_OS_API_KEY="sk_live_..."                           # your key
```

If you omit the base URL, `sdk:aegis_sdk.ClientConfig` raises
`sdk:aegis_sdk.ConfigurationError` with a message naming the variable. That
refusal is the design working — *design intent, not observable*: a client that
fell back to a built-in host would send production traffic to a placeholder
endpoint and report success, so the failure is made loud and early instead.

Other variables the client reads, all optional: `AGENTIC_OS_TIMEOUT` (default
30.0 seconds), `AGENTIC_OS_MAX_RETRIES` (3), `AGENTIC_OS_VERIFY_SSL` (true),
`AGENTIC_OS_DEBUG` (false). Set `AGENTIC_OS_DEBUG=true` while you are getting
started; it is the difference between "something went wrong" and a request you
can read.

## Before the first call: two checks that need no credentials

Both run offline and both answer a question you would otherwise guess at:

```
python -m aegis_sdk.handbook.check              # does this build still have what this book names?
python -m aegis_sdk.coc.probe --transports-only # which client paths are real, before any network
```

The first is this handbook's own verifier. The second reports which transports
the client genuinely has, without contacting anything — so a later failure can be
attributed to the deployment rather than to the package.

Then point the probe at your deployment once you have the variables below:

```
python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" --api-key "$KEY"
```

That measures **reachability** — what your credential can actually get to. Run it
before you conclude anything about permissions; 04.1 explains why reachability
and permission are different questions that produce the same 403.

## The first call

```python
import asyncio
from aegis_sdk import AgenticOSClient


async def main() -> None:
    client = AgenticOSClient.from_env()
    me = await client.auth.get_current_user()
    print(me)


asyncio.run(main())
```

`sdk:aegis_sdk.AgenticOSClient.from_env` reads the environment above.
`client.auth.get_current_user()` calls `api:GET /api/v1/auth/me` and returns a
`sdk:aegis_sdk.User`.

This one call is a better smoke test than a health check, because it exercises
the whole chain rather than only reachability. Read the failure by *kind*:

| what you see | what it means | where to go |
| --- | --- | --- |
| `ConfigurationError` | the client never made a request — no base URL | set `AGENTIC_OS_BASE_URL` |
| `ConnectionError` / `NetworkError` | DNS, TLS or routing — the deployment was not reached | your network, VPN, or the URL itself |
| `AuthenticationError` | reached it; the key is absent, malformed or revoked | reissue the key |
| `AuthorizationError` | reached it, key is valid, this principal may not do this | 04.1 — and read the warning below first |
| a `ValidationError` on `role` | the call **succeeded**; the client could not parse the reply | see immediately below |
| a `User` printed | everything works | continue |

> ⚠ **This diagnostic can fail for the very credential it exists to diagnose, and
> the failure does not look like an auth problem.** `sdk:aegis_sdk.User` declares
> `role` as a **required** `str`, and an API-key principal is documented as
> carrying no role. Measured against the installed model, with every other
> required field supplied:
>
> | what the server sends | what the client does |
> | --- | --- |
> | `role` omitted | raises `ValidationError` — `role: missing` |
> | `role: null` | raises `ValidationError` — `role: string_type` |
> | `role: ""` | parses |
>
> Two of the three plausible shapes raise. **UNVERIFIED:** which one a real
> deployment sends — settling it needs a live call against a deployment, which
> this edition could not make.
>
> **`role` is not alone.** Measured by omitting each field in turn against a
> control with all of them present, `sdk:aegis_sdk.User` requires **six**: `id`,
> `email`, `name`, `organization_id`, `organization_name`, `role`. Each reports
> `missing` on its own; the control parses. A principal thin on any one of them
> hits the same wall.
>
> ⚠ **A note on how to measure this, because the obvious way gives a confident
> wrong answer.** Vary **one** field and supply every other. The first attempt at
> the table above omitted several at once, and then all three shapes reported
> `missing` — the rows became indistinguishable, and the table read as
> confirmation while being wrong. A result that is identical across the branches
> of your question is not evidence about that question, however cleanly it
> prints. This applies well beyond this one model, and it is the reason the
> control row exists.
>
> **If you hit it, do not conclude your key is broken.** A `ValidationError` here
> means the request was authenticated and answered — the reply simply did not fit
> the model. Drop to the raw call to see what actually came back, and continue:
> nothing else in this book depends on `get_current_user()` succeeding.

**If you are using a token rather than an API key**, this call is the
straightforward one and the caveat above is unlikely to bite. It is worth doing
both if you hold both, because the two credential types do not reach the same
surface — see 04.1.

> ⛔ **Do not spend a day tuning scopes on an `AuthorizationError` before reading
> chapter 04.1.** There is an **open defect** in which a large number of routes
> are unreachable by *every* API key regardless of the scopes attached to it, and
> the denial is a generic 403 that is indistinguishable from a genuine scope
> problem. 04.1 gives you a one-minute test that settles which one you have. If
> your scopes look right, they probably are.

## Now do something that changes state

Creating an organisation is the smallest end-to-end write, and it is the root
every other noun hangs off.

```python
org = await client.organizations.create(
    name="Northwind Manufacturing",
    slug="northwind",
    plan_tier="pro",
)
print(org["id"])          # note: a dict, not a model — see 01.1
```

That is `api:POST /api/v1/organizations`. Read it back with
`api:GET /api/v1/organizations/{id}`, and list what you can see with
`api:GET /api/v1/auth/me/organizations`.

**In the console**, the same object is what you land in after signing in; there
is no separate "create organisation" screen for most deployments, because this is
provisioning rather than daily work. That asymmetry is the pattern for the whole
book: the harness does the building, the console does the working.

## Where to go next

You now have a client that authenticates and a tenant root to hang things off.
[Part 02](../02-working-through-the-harness/) is the working spine — units,
roles, envelopes, trust, work, evidence — and it assumes exactly the state this
chapter left you in.

---

*Next: [Part 02 — Working through the harness](../02-working-through-the-harness/)*
