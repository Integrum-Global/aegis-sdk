# 04.5 — Concurrency, timeouts and streams

Everything in this client is asynchronous, and the shape of that matters once you
are provisioning two hundred roles rather than one. This chapter is what the
client does under load, what it does _not_ do for you, and the one place —
streaming — where its error handling stops.

## One client, many calls

The client holds a connection pool and is meant to be shared. Create it once, use
it concurrently, close it once.

```python
import asyncio
from aegis_sdk import AgenticOSClient


async def main() -> None:
    async with AgenticOSClient.from_env() as client:          # one pool
        agents = await asyncio.gather(*[
            client.agents.get(agent_id) for agent_id in ids   # concurrently
        ])
```

The pool allows **100 simultaneous connections with 20 kept alive** between
calls. Sixty concurrent requests through one client all go in flight together —
the client applies **no concurrency limit of its own** below the pool ceiling.

**A client per call is the anti-pattern.** Each one builds its own pool and TLS
session, so a loop that constructs and discards clients pays a handshake per
request and holds none of the connection reuse the pool exists for. Two hundred
roles is one client and a `gather`, not two hundred clients.

**Closing matters.** `sdk:aegis_sdk.AgenticOSClient.close` releases the pool; the
`async with` form calls it for you. A call on a client you already closed raises
a plain `RuntimeError`, not anything in this book's exception vocabulary — see
[04.2](02-errors-and-refusals.md).

## The timeout is one number, and it applies four times over

`AGENTIC_OS_TIMEOUT` (default **30.0** seconds) becomes the timeout for
connecting, writing, reading and waiting for a pool slot — the same value for
all four. There is no separate connect timeout and no separate read timeout.

That matters when you raise it. Setting `timeout=300` for one slow report also
gives you a five-minute _connect_ timeout, so a deployment that is simply
unreachable now takes five minutes to say so, three times over. Prefer a second
client for the slow work:

```python
fast = AgenticOSClient.from_env()
slow = AgenticOSClient(base_url=fast.base_url, api_key=KEY, timeout=300.0)
```

`sdk:aegis_sdk.ClientConfig.with_base_url` and
`sdk:aegis_sdk.ClientConfig.with_api_key` build a variant config if you would
rather not repeat the settings.

## What is retried — and it is less than you think

Counting HTTP attempts against each failure in turn, at the default
`max_retries` of 3:

| what fails                | attempts made | total added delay |
| ------------------------- | ------------: | ----------------- |
| a connection error        |         **3** | 2.5 s             |
| a read or connect timeout |         **3** | 2.5 s             |
| a pool timeout            |         **3** | 2.5 s             |
| a `500` or `503`          |         **1** | none              |
| a `429` rate limit        |         **1** | none              |
| a `403` refusal           |         **1** | none              |

⚠ **No HTTP status is ever retried. Only transport failures are.** This is the
single most commonly mis-stated property of the client — including, until this
edition, by parts of this book that described it as handling retries without
saying which ones. It retries the case where the deployment _did not answer_. It
does not retry the case where the deployment answered _`503`_.

**`sdk:aegis_sdk.RateLimitError` carries a `retry_after` parsed from the
response header, and nothing acts on it.** The value is there for you to use;
the client will not sleep on your behalf. If your integration needs status-level
retry, you write it, and the table in [04.2](02-errors-and-refusals.md) says
which statuses may have it.

The backoff between transport attempts is fixed — roughly one second, then one
and a half — and it is **not configurable from the environment**. Only
`AGENTIC_OS_MAX_RETRIES` is. So the worst case for one unreachable call is
`max_retries × timeout` plus the backoff: at the defaults, **about 92 seconds
before a single call gives up.** For a `gather` of two hundred against a
deployment that is down, that is a script which appears to hang for a minute and
a half and then produces two hundred identical errors. Lower the timeout for
anything you would rather have fail fast.

> ⛔ **Do not set `max_retries` to 0 to disable retries.** With
> `AGENTIC_OS_MAX_RETRIES=0` the retry loop never executes, **no request is made
> at all**, and every call raises `sdk:aegis_sdk.ServiceError` with the message
> `Unknown error after retries` — including calls that would have returned `200`.
> The failure looks like a broken deployment and is entirely local.
>
> Use `1` for a single attempt with no retry. The constructor argument path
> happens to fall back to the default when given `0`, so this bites specifically
> through the environment variable and through
> `sdk:aegis_sdk.ClientConfig` — which is to say, through the two paths a
> deployment configures rather than the one a developer types.

## What the client does not do for you

Stated plainly, because each of these is something integrators assume is handled:

- **No rate limiting.** Nothing throttles you below the pool's 100. A `gather`
  over a large collection will hit the deployment as hard as your event loop can
  manage, and the `429` you get back will not be retried.
- **No `Retry-After` compliance.** See above.
- **No idempotency keys.** The client sends no idempotency header on any request.
  A retried write is a second write, and the transport's own retry is on the
  transport layer — where a request that timed out _may still have been applied
  by the server_. For creates you care about, make the operation
  create-if-missing yourself, as
  [02.2](../02-working-through-the-harness/02-standing-up-an-organization.md)
  shows.
- **No request ordering.** `asyncio.gather` gives you results in argument order
  and says nothing about the order the server saw them in. If B depends on A,
  `await` A first; do not put them in one `gather` and hope.

A bounded worker is usually the right shape for anything above a few dozen calls:

```python
async def bounded(client, ids, *, concurrency: int = 8):
    sem = asyncio.Semaphore(concurrency)

    async def one(agent_id):
        async with sem:
            return await client.agents.get(agent_id)

    return await asyncio.gather(*(one(i) for i in ids), return_exceptions=True)
```

`return_exceptions=True` is deliberate: without it, the first failure cancels
the rest and you lose the results of every call that had already succeeded.
With it, you get a list you can partition into results and failures — and per
[04.2](02-errors-and-refusals.md), you should partition failures further into
refusals, faults, and _not reached_.

## Streaming, and where the error handling stops

Some operations stream server-sent events rather than returning a body:
`sdk:aegis_sdk.core.AgentsModule.stream` for an agent execution,
`sdk:aegis_sdk.execution.SessionsModule.stream_events` and
`sdk:aegis_sdk.execution.SessionsModule.stream_messages` for a session. Each
yields a dictionary with a `type` key.

```python
async for event in client.agents.stream(agent_id, message="..."):
    if event["type"] == "content":
        print(event["content"], end="", flush=True)
    elif event["type"] == "done":
        break
```

The streaming path is a different code path from every other call in this
client, and it behaves differently in four ways that all matter.

**1. Its errors are not translated.** A transport failure during a stream raises
the **raw underlying HTTP-library exception**, not
`sdk:aegis_sdk.TimeoutError` or `sdk:aegis_sdk.ConnectionError`. A read timeout
mid-stream comes out untranslated. `except AgenticOSError` around an
`async for` will not catch it.

Status codes _are_ translated — a `403` or `500` on the initial response raises
the same exception as anywhere else — but only for statuses at or above 400.

**2. A redirect on a stream yields nothing and raises nothing.** The status
check covers 400 and above, so a `302` falls through to the event loop, which
finds no events: an empty stream, clean exit, no error. A `204` does
the same. **An empty stream is indistinguishable from a governed agent that
produced no output**, which is exactly the wrong ambiguity to have here.

**3. It is not retried.** One attempt, then the exception. There is no
reconnection and no resumption from a last-seen event.

**4. The read timeout applies between events, not to the stream.** The client's
30-second timeout is the gap it will tolerate _between_ events. A long-running
governed session that thinks for more than thirty seconds without emitting will
time out mid-stream — and per point 1, it will do so with an untranslated
exception. For anything you expect to run long, use a client with a larger
timeout.

### Two silent losses to guard against

**Malformed event data is dropped without a word.** A `data:` line that is not
valid JSON is skipped; there is no error and no gap in the sequence you can
detect. A stream of three events with the middle one malformed yields two,
cleanly.

**A truncated stream looks exactly like a complete one.** The iteration ends
either on a terminator event or when the connection closes, and both produce the
same clean exit. There is no completion signal you can check afterwards.

The consequence is a rule: **decide completion from the events, never from the
loop ending.**

```python
done = False
async for event in client.agents.stream(agent_id, message=task):
    if event["type"] == "error":              # an error arrives as an EVENT
        raise RuntimeError(event.get("error", "the stream reported an error"))
    if event["type"] == "done":
        done = True
if not done:
    raise RuntimeError("stream ended without a completion event — treat as truncated")
```

⚠ **Note the first branch.** A failed execution is reported to you as an event
of type `error`, on a stream that otherwise looks healthy. A consumer that
filters for `content` and ignores everything else will print a partial answer
and never learn that it was partial. This is the same shape as the truncation
above and it is more likely: the error is _there_, in the data, and you dropped
it.

The same trap has a sharper edge on `stream_events`, whose `event_types`
argument filters **client-side**. Passing `event_types=["progress_update"]`
discards the `error` event before you ever see it — the server sent it, and the
filter you wrote to reduce noise removed the one event that mattered. If you
filter, always keep `error` in the list.

That argument filters on `type` values that are the server's, not the names in
this chapter's prose — and it fails **silently** when you pass one that does not
exist: nothing raises, you simply receive no such event, which is
indistinguishable from a session that emitted none. The vocabulary is on
`sdk:aegis_sdk.execution.SessionsModule.stream_events`; check it there rather
than guessing at a plausible name.

---

_Next: [04.6 — Reading a response honestly](06-reading-a-response-honestly.md)_
