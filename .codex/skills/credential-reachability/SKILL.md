---
name: credential-reachability
description: "Credential reachability — a 403 is not always a permissions problem. Scope: every call you make against a deployed Aegis platform."
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/guardrails/credential-reachability.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->

# Credential reachability — a 403 is not always a permissions problem

**Scope:** every call you make against a deployed Aegis platform.

The mechanism is documented in the shipped handbook chapter _The API surface_
(cited by title — the handbook is being renumbered, and a number printed here
would resolve today and mislead next month), and is not restated here. In one
line: **an API-key principal carries no personas, ever, and a persona-gated
route compares against that empty list and refuses.** No scope configuration
changes it, because scopes are not consulted on that path.

This file is the part the handbook does not carry: what you must do about it.

## MUST 1 — Establish which credential you hold before diagnosing any refusal

One call, `api:GET /api/v1/auth/me`, before you look at scopes, roles or route
documentation. An empty persona list is the whole diagnosis for a large class of
403s and it takes seconds to read.

```python
# DO — read the principal, then reason
me = await client.auth.get_current_user()
if not me.personas:
    ...  # you hold a key; persona-gated routes are closed regardless of scopes

# DO NOT — open the scope list first
# The scopes are almost always fine. That is what makes this cost a day.
```

**Why:** the denial names the personas the route wants. That reads as an
actionable remedy — obtain one of these — and for an API key **the remedy named
does not exist**, because a key cannot hold a persona at all. The error is not
merely uninformative; it points at a door that is not there.

### ⚠ This call may raise instead of answering, and the shape says which

`sdk:aegis_sdk.User` declares `role` as a **required `str`**, while a key
principal is documented as carrying no role. Three plausible wire shapes, tested
against the model this client declares:

| the response carries | result                            |
| -------------------- | --------------------------------- |
| `role` omitted       | `ValidationError` — _missing_     |
| `role: null`         | `ValidationError` — _string_type_ |
| `role: ""`           | parses, `role == ''`              |

**`role` is not the only required field, and that widens the exposure.** Measured
by omitting each in turn against a control with all present: **six** are required
— `id`, `email`, `name`, `organization_id`, `organization_name`, `role`. A
principal thin on any one of them hits the same wall for the same reason.

⚠ **When you reproduce this, vary ONE field and supply every other.** Otherwise
all three rows above come back _missing_, the shapes look indistinguishable when
they are not, and the table you build from it is wrong in a way that reads as
confirmation.

That generalises well past this model, and it is the sentence to carry out of
this file if you carry only one:

> **A result identical across the branches of your question is not evidence about
> that question, however cleanly it prints.**

It is why every check in this package states what it would have shown had the
claim been false, and why the probe exits `3` rather than `0` when it cannot
tell.

**A `ValidationError` here means the request was ANSWERED, not refused.** The
deployment replied; the client could not model the reply. That is a different
finding from a 401 or a 403 and points at a different owner. Nothing downstream
depends on this call succeeding — it is a diagnostic, so a failure to parse it
does not block your work, it only removes a convenience.

**UNVERIFIED from this side: which of the three your deployment sends.** It
cannot be settled without calling one, and this package is the wrong place to
guess. What is settled is that two of the three make the _diagnostic call itself_
fail for the credential it exists to diagnose.

So: if `get_current_user()` raises a validation error naming `role`, **do not
read that as a broken deployment or a bad key.** It is consistent with a
correctly-issued API key. Fall back to the raw call and read the body yourself:

```python
raw = await client._http.request("GET", "/api/v1/auth/me")   # api:GET /api/v1/auth/me
print(raw)   # personas, role, organization_id — unparsed, and therefore readable
```

That reaches past the model deliberately. It is the right move for exactly this
diagnosis and the wrong move everywhere else.

## MUST 2 — Attribute a 403 to a layer before changing anything

Retry the identical call with the other credential type. The difference between
the two results carries more information than the status code does.

| key | session | what it is                                                           |
| --- | ------- | -------------------------------------------------------------------- |
| 403 | 200     | credential-type reachability. No scope change helps. Use a session.  |
| 403 | 403     | an actual authorization decision. Now look at roles and permissions. |
| 403 | 401     | your session is not valid. You have measured nothing yet.            |

```bash
# DO — measure the whole surface once, with both credentials
python -m aegis_sdk.coc.probe --base-url "$URL" --api-key "$KEY" --token "$TOK"

# DO NOT — infer reachability from a scope list
# Scopes and permissions are different registries that share a spelling.
```

**Why:** the two causes are indistinguishable in the response and have opposite
remedies. Guessing picks the wrong one about half the time, and one of the wrong
answers leaves you holding a wider credential.

## MUST 3 — Assume nothing carries from one route to a sibling

Two routes can share a URL prefix, be served by different routers, and have
**opposite** postures towards the same credential. A prefix is a naming
convention, not an admission boundary.

**Why:** admission is layered — a router-level gate runs before any per-route
gate — so a route can carry a perfectly correct per-route check that is never
reached. Two routes on the same resource can therefore differ with no difference
in anything either route documents.

## MUST NOT — Widen a credential to clear a refusal you have not attributed

```
# DO NOT
"The 403 mentions permissions, so I will add scopes until it passes."
```

**Why:** in the reachability branch, added scopes change nothing — they are not
read on that path — and you finish holding a more powerful credential than the
job needs, permanently, for no benefit. In the authorization branch you have
granted access without deciding that it should be granted. Neither branch is
improved by widening; only one of them is even affected by it.

## MUST NOT — Report reachability from a probe that could not have said otherwise

A run of the probe with an expired token refuses everything and finds nothing to
report. That output is byte-identical to a healthy deployment with no trapped
routes. The probe therefore verifies both credentials against a control
operation first and exits `3` UNDETERMINED rather than `0` when it cannot.

**Why:** before citing any check as evidence, name what it would have printed
had the claim been false. If nothing it could have printed would have falsified
you, it was not evidence — whatever it printed.

## What none of this establishes

That a route you _can_ reach is doing what you think. Reachability is admission,
not correctness, and not enforcement. A route that admits you when it should not
returns `200`, and no probe in this package can see that.
