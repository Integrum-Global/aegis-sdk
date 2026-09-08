# Sentinels and defaults — a value that cannot be distinguished from an intention

**Scope:** every field you read that might be a sentinel, and every argument you
give a default.

Two failures, one shape. A **sentinel** is a value in the ordinary range that
means something outside it — `-1` for *unlimited*, `null` for *unknown*. A
**default** is a value the client sends when you said nothing. Both go wrong the
same way: **the receiver cannot tell the special case from the ordinary one**,
and the direction of the error is almost always permissive.

## MUST 1 — Never compare a sentinel numerically

⚠ **The quota READ and the quota WRITE do not live under the same prefix**, and
guessing costs a `404`. `sdk:aegis_sdk.revenue.quotas.QuotasModule` reads
`api:GET /api/v1/features/limits` and writes to a `billing/quotas` path. Nothing
about the module name predicts that; re-derive it for your build rather than
inferring the read path from the write path.

```python
# DO — ask the boolean the model computes for you
if quota.unlimited:
    ...
elif quota.remaining < threshold:
    warn()

# DO NOT — arithmetic on a sentinel
if quota.remaining < threshold:      # remaining is -1 when unlimited
    warn()                            # so an UNLIMITED quota is the loudest alarm
```

**Why:** `-1` is smaller than every threshold you will ever set, so a numeric
comparison inverts precisely on the case that should be silent. `remaining` is
set to `-1` for an unlimited quota, and `limit == -1` means unlimited too.

## MUST 2 — Read the derivation, not the field name, before trusting `unlimited`

This is the one to actually check in your build rather than assume, because in
the build this was written against the derivation is **wider than its name**:

```python
unlimited = limit <= 0 or limit == -1
```

**A limit of `0` is reported as UNLIMITED.** Zero allowance and no limit are
opposite conditions and they arrive as the same boolean. `remaining` for that
same quota computes to `0` — so the object carries `unlimited=True` and
`remaining=0` simultaneously, which is not a state anything downstream is
prepared for.

The client's own quota check is permissive in the same direction, and says so:

```python
if quota is None:
    # If quota not found, assume allowed (unknown resource type)
    return QuotaCheck(..., allowed=True, ...)
```

**So a client-side quota check answers `allowed=True` for a resource it has never
heard of, and for a resource whose allowance is zero.**

```
# DO      treat a client-side quota check as a hint; let the SERVER refuse
# DO NOT  gate a spend, a provisioning step, or a customer-visible promise on it
```

**Why:** a quota check that fails open is not a quota check. It is a latency
optimisation that happens to return a boolean, and reading it as authority means
the first thing that stops an over-allocation is the invoice.

## MUST 3 — A default MUST NOT be indistinguishable from an intentional value

If a server distinguishes *"the caller did not mention this field"* from *"the
caller explicitly set it to null"*, then a client parameter defaulting to `None`
**erases that distinction on every call**.

```python
# DO — a sentinel object that cannot be confused with a real value
_UNSET = object()

async def set_ceiling(unit_id: str, ceiling=_UNSET) -> None:
    body = {} if ceiling is _UNSET else {"ceiling": ceiling}
    ...

# DO NOT — None as the default when None is also a meaningful value
async def set_ceiling(unit_id: str, ceiling: str | None = None) -> None:
    body = {"ceiling": ceiling}     # sends null every time you did not pass one
```

**Why, and this is the reason the guardrail exists rather than a style note:**
where clearing a field WIDENS an authority — a posture ceiling, a clearance, a
spend cap — the permissive default does not merely lose information. Every call
made for an unrelated reason silently removes the bound. The caller who wrote
`set_ceiling(unit_id)` to touch something else has just raised what that unit may
do, and nothing in the call, the response or the audit trail reads as an
authority change.

Two conditions and the danger needs both: the server distinguishes absent from
null, **and** null is the widening direction. When you meet a setter on any
governance surface, establish both before you call it once.

## MUST 4 — Where the special case is not expressible, say so rather than encoding it

If a field can be *unknown* and the type has no room for unknown, the honest
move is to surface the ambiguity, not to pick a side.

```
# DO      "limit is 0 — this is either no allowance or no limit; the client
#          cannot tell, confirm against the plan"
# DO NOT  "limit: unlimited"     (the client's own guess, promoted to a fact)
```

**Why:** the reader cannot audit a guess they cannot see, and a permissive guess
presented as a reading is how an over-allocation gets signed off.

## MUST NOT — Assume a value in range is ordinary

**Why:** sentinels are drawn from the ordinary range by construction — that is
what makes them cheap on the wire and dangerous in a comparison. `-1`, `0`, `""`
and `null` are all live special cases somewhere in this client, and none of them
announces itself at the call site.

## What this does not cover

Which fields in *your* build are sentinels. That is a property of the build and
it moves. Read the derivation of any boolean you are about to trust — it is
usually one line and it is usually wider than its name.
