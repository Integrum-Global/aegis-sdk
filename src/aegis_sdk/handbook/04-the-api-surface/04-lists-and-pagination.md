# 04.4 — Lists, filters and pagination

An organisation of any size makes this the first thing you hit and the easiest
thing to get quietly wrong. A list call that returns fifty rows out of four
hundred does not fail. It succeeds, returns a plausible answer, and your
create-if-missing script re-creates everything past the first page.

This chapter is about the four ways this client asks for a page, the many ways
the API answers, and which of the fields you get back you may actually trust.

## There is no one pagination convention. There are four

Measured across the client: **83 of its 841 asynchronous methods take a paging
parameter**, in four distinct caller-facing shapes.

| the parameters the method takes | methods | example |
| --- | ---: | --- |
| `limit` + `offset` | 45 | `sdk:aegis_sdk.core.SkillsModule.list` |
| `page` + `page_size` | 18 | `sdk:aegis_sdk.core.AgentsModule.list` |
| `limit` only — no way to advance | 18 | several memory and lookup reads |
| `page_size` only — no way to advance | 2 | `sdk:aegis_sdk.execution.ObjectivesModule.list` |

**The third and fourth rows are the ones to notice.** Twenty methods let you ask
for *more* and give you no way to ask for the *next*. On those, the only page you
can ever read is the first one, and the only lever you have is to raise the
limit. If the collection is larger than your limit, the remainder is not
reachable through that method at all.

⚠ **Do not assume the parameter names are the wire names.** `agents.list` takes
`page` and `page_size` and sends `limit` and `offset`, because that is what the
route reads; sending `page` would be silently ignored and every call would
return the same first page. The translation is the client doing you a service,
and it means you cannot infer the HTTP contract from the Python signature. Where
this book names a paging parameter, it is naming the **Python** one.

## The default page is small, and it varies

Every paging method has a literal default. Across the 83:

```
 38 x  limit = 50          15 x  limit = 100         4 x  page_size = 20
 14 x  page_size = 50       4 x  limit = 10          3 x  limit = 20
                            2 x  page_size = 10      1 x  limit = 12
                            1 x  limit = 200         1 x  limit = 1000
```

So the modal default is **50** — a bit over sixty per cent of the paging surface —
and the range runs from 10 to 1000. **Never rely on the default.** Pass the page
size explicitly at every call site, so that the number is in your code where a
reviewer can see it rather than in a signature they will not read.

Servers cap it too, and the cap is not uniform: `skills.list` documents a maximum
of 100, `objectives.list` a maximum of 200. Asking for more than the cap does not
error; you get the cap.

## What comes back is not uniform either

There is no single list envelope. **This client reads the collection out of the
response under 27 distinct key names**, of which `records` is the plurality (18
sites) and `items` a distant second (7). `agents`, `data`, `skills`, `policies`,
`history`, `events`, `invoices`, `plans`, `members`, `nodes`, `permissions` and
fifteen others each appear on their own routes. A handful of routes — API keys
among them — return a **bare JSON array** with no envelope at all.

You do not usually have to care, because the typed methods unwrap it for you.
You have to care in exactly two situations:

- **You are calling the raw transport**, in which case the key is yours to find.
  Print the response before you write the accessor. Do not guess it from the
  noun; [the part README](README.md) has the worked case of a read and a write on
  the same noun that share no path prefix, and envelope keys are no more
  predictable.
- **Your deployment returns a different envelope than this client expects.** A
  route that hands back `{"records": [...]}` where the client wants a bare array
  produces a raw `TypeError`, outside the exception taxonomy — see
  [04.2](02-errors-and-refusals.md).

## `PaginatedResponse` is a client construction, not a server one

Several methods return `sdk:aegis_sdk.PaginatedResponse`, which has five fields:

```
items  total  page  page_size  has_next
```

**Only `items` and `total` are required. `page`, `page_size` and `has_next` are
optional with defaults of `1`, `50` and `False`.** And — this is the part that
decides whether your paging loop is correct — **the client computes all of them
itself, differently per module, from whatever the route actually returned.**

Three measured examples, all returning the same type:

| method | `total` means | `has_next` is computed as |
| --- | --- | --- |
| `sdk:aegis_sdk.core.AgentsModule.list` | the organisation-wide count | `offset + len(page) < total` |
| `sdk:aegis_sdk.core.SkillsModule.list` | the organisation-wide count | `offset + len(page) < total` |
| `sdk:aegis_sdk.execution.ObjectivesModule.list` | **the length of this page** | `len(page) >= page_size` — a heuristic |

Read the third row twice. On `objectives.list`, `total` is *not* an
organisation-wide count and `page` is hard-coded to `1`, because the route does
not paginate. A loop that reads `result.total` as "how many objectives exist"
gets "how many objectives came back", which is a different number wearing the
same name, and the two agree exactly when the answer does not matter.

⛔ **The failure mode that will actually bite you.** Where a route omits `total`,
the client falls back to the length of the page it received. `has_next` then
evaluates `offset + len(page) < len(page)`, which is **false on the first
page** — so a paging loop terminates after one page and reports success. Nothing
errors, nothing warns, and the result looks exactly like a small collection.

That is not hypothetical arithmetic; it is the shape behind the
create-if-missing hazard in
[02.2](../02-working-through-the-harness/02-standing-up-an-organization.md),
where a re-runnable provisioning script that reads only the first page re-creates
everything it could not see.

## A paging loop that does not lie to you

Two rules make it robust against every variation above: **advance by what you
received**, and **stop when a page comes back short**, rather than trusting
`total` or `has_next`.

```python
async def all_of(fetch, page_size: int = 200):
    """Every row from a limit/offset method, without trusting `total`.

    `fetch` takes (limit, offset) and returns a PaginatedResponse.
    """
    out, offset = [], 0
    while True:
        page = await fetch(page_size, offset)
        out.extend(page.items)
        if len(page.items) < page_size:       # short page = last page
            return out
        offset += len(page.items)             # advance by RECEIVED, not by requested
        if offset > 100_000:                  # a bound, so a server bug cannot loop forever
            raise RuntimeError(f"paging did not terminate at offset {offset}")


skills = await all_of(lambda limit, offset: client.skills.list(limit=limit, offset=offset))
```

Three things that loop does deliberately:

- **It advances by `len(page.items)`, not by `page_size`.** If the server caps
  your requested size, advancing by the requested amount skips rows. Advancing by
  what arrived cannot.
- **It stops on a short page, not on `has_next`.** A short page is a fact about
  the response; `has_next` is an inference the client made from fields that may
  not have been sent.
- **It has an upper bound.** A route that ignores `offset` returns the same page
  forever and the loop never ends. The bound converts a hang into an error you
  can read.

For a `page`/`page_size` method the same shape applies with `page += 1`. For the
twenty methods with no offset at all, there is no loop to write: raise the limit
to the cap, and **if you get exactly the cap back, treat the result as truncated
rather than complete** — because you cannot tell the difference from here.

## Filters, and the ones that do nothing

Filtering is per-method and the parameters are not uniform either. `skills.list`
takes `category`, `is_public` and `search`; `agents.list` takes `workspace_id`,
`status` and `agent_type`; `objectives.list` takes **`status` and nothing else** —
no `agent_id`, no `workspace_id`, and no page cursor.

⚠ **A parameter a route does not read is silently ignored.** It is not an error
and there is no warning: the server matches the parameters it declares and drops
the rest, so an unsupported filter returns the *unfiltered* first page. That is
the more dangerous direction — you get more than you asked for while believing
you were narrowed — and it is how a "list the objectives for this agent" call
becomes "list the organisation's objectives" without saying so.

Two habits that catch it:

```python
# 1. Assert the filter actually held, rather than assuming it.
page = await client.agents.list(status="active", page_size=200)
assert all(a.status == "active" for a in page.items), "the status filter did not apply"

# 2. Read the method's own docstring for the supported set before you rely on it.
help(client.objectives.list)
```

The first is worth writing into any sweep whose conclusion depends on the filter.
A filter that silently no-ops turns a narrow question into a broad answer, and
the broad answer is usually still plausible.

## Two return shapes, and the one that fails at the point of use

[01.1](../01-orientation/01-what-you-were-given.md) names this and it is worth
the reminder in a chapter about reading collections: some modules return typed
models with attribute access, and the vertical-standup modules return raw
dictionaries with subscript access. Within a single provisioning script you will
handle both — typically a `dict` from the create and a model from the list, for
the *same* noun.

```python
created = await client.units.create(name="Treasury", unit_type="department")
unit_id = created["id"]                       # dict -> subscript

page = await client.org_standup.list_units(limit=200, offset=0)
names = [u.name for u in page.records]        # model -> attribute
```

Note that `list_units` returns `.records`, not `.items` — it is not a
`PaginatedResponse`. When in doubt, `print(type(result))` once and stop guessing;
the failure otherwise surfaces as a `TypeError` or `AttributeError` at the point
of *use*, several lines from the call that decided it.

---

*Next: [04.5 — Concurrency, timeouts and streams](05-concurrency-and-streams.md)*
