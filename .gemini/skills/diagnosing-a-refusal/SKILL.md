---
name: diagnosing-a-refusal
description: A call was refused. Attribute it to a layer before changing anything — credential type, admission layer, authorization, tenancy, governance hold, or a client-side defect.
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/skills/diagnosing-a-refusal.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


# Diagnosing a refusal

The expensive mistake is not misdiagnosing a refusal. It is **changing something
before diagnosing it** — because the change that clears a refusal you have not
attributed is usually a widening, and a widening that was not needed is
permanent.

Work the ladder in order. Each rung is cheap and each one eliminates a class.

## Rung 0 — Capture the actual response, not the exception's rendering

```python
try:
    await <the call>
except AgenticOSError as exc:
    print(exc.details.get("status_code"), repr(exc.details.get("message")))
```

Every failure here is an `sdk:aegis_sdk.AgenticOSError` or a subclass.

Two reasons this is rung zero. The exception **subclass does not identify the
status** — 409 and 410 both arrive as the bare base class. And the rendered
message can be the literal string `"None"` when the error body carries none of
the keys the extractor looks for. Read `details`, not `str(exc)`.
[The error taxonomy guardrail](../guardrails/error-taxonomy.md) has both
mechanisms.

## Rung 1 — Is it a refusal at all?

A transport error is not a refusal. `sdk:aegis_sdk.ConnectionError` and
`sdk:aegis_sdk.TimeoutError` mean the deployment did not answer, and they are
evidence about nothing else.

```
# DO      retry once, then treat persistent transport failure as an outage
# DO NOT  record a timeout as a denial, or as an empty result
```

## Rung 2 — Which credential type? (the highest-yield rung)

Retry the identical call with the other credential.

| key | session | verdict |
| --- | ------- | ------- |
| 403 | 200 | **credential-type reachability.** No scope change helps. Use a session. |
| 403 | 403 | a real authorization decision. Continue to rung 3. |
| 403 | 401 | your session is invalid. You have measured nothing. Fix that first. |

If you have not yet mapped this for your deployment, do it once, for the whole
read surface:

```bash
python -m aegis_sdk.coc.probe --base-url "$URL" --api-key "$KEY" --token "$TOK"
```

**Read its exit code.** `3` means UNDETERMINED — a credential failed the control
call, so everything was refused and a count of zero would have meant nothing.

## Rung 3 — Which layer refused you?

Admission is layered: a router-level gate runs **before** any per-route gate. A
route can carry a perfectly correct per-route permission check that is never
reached, and the error body does not say which layer spoke.

Confirm what your credential resolves to at `api:GET /api/v1/auth/me` before
reasoning about layers.

The useful signal is a **sibling comparison**. Find a route on the same resource
that your credential does reach. If one works and its sibling does not with no
difference in the permissions either documents, you were refused at the door, not
at the desk — and the two are not fixed the same way.

⚠ A shared URL prefix is a naming convention, not an admission boundary. Two
paths under one prefix can be served by different routers with opposite postures.

## Rung 4 — Is it tenancy rather than permission?

A tenancy failure surfaces as a **400**, a **403**, or an **empty result set**,
depending on which of three independent layers caught it. Those look like three
bugs and are one.

The `400` is the one that misleads: its detail says the caller has no
organisation context. A caller reading only the status classifies it as a
malformed request and goes looking at their body. **It is an identity problem.**

```
# DO      confirm the organisation your credential resolves to, then compare it
#          to the organisation that owns the resource
# DO NOT  send an organisation id in the body expecting it to be honoured
```

## Rung 5 — Is it governance rather than authorization?

A held item is not a refusal to be cleared. It is a decision awaiting a human,
and the correct response is the approval path, not a credential change. See the
handbook chapter *When something is held*.

```
# DO NOT  widen a credential to escape a hold
```

That move fails in both branches: if it is a hold, widening is not the remedy; if
it is the rung-2 reachability case, widening changes nothing because scopes are
not consulted on that path. You end the day with a more powerful credential and
the same refusal.

**`client.governance_explain` explains the decision instead of leaving you to
infer it.** `explain_access()` walks the access chain and returns where it
stopped:

```python
why = await client.governance_explain.explain_access(
    role_id=...,                    # the role the refused call ran as
    knowledge_item={                # the item the refused call was about
        "id": ..., "classification": ..., "unit_address": ...,
    },
    posture=...,                    # that role's trust posture
)
print(why.allowed, why.step_reached, why.reason)
```

Read `step_reached`, not `allowed`. When the verdict is `False` it names the step
the chain stopped at, which is the attribution this rung exists to produce.

⚠ **It is a dry run, and it is not a record of your refusal.** It evaluates the
item *you describe*: nothing is read from a stored record, nothing is accessed,
nothing is recorded as an access, and a wrong or missing field changes the
verdict. Reconstruct the item the refused call was about and re-run the chain —
it cannot tell you what happened during a past call. It answers about a role plus
a knowledge item, not about a connector or a tool.

The same module carries the state readouts, which are the other half of "is this
governance?": `explain_envelope()` for a role's effective envelope through its
ancestor chain, and `envelope_hydration_status()` / `envelope_coverage()` — a
hydration pass that **skipped** a role leaves it on a fail-closed bootstrap
default (deny, never unlimited), so a skip reads exactly like a governance
refusal and is silent everywhere else.

## Rung 6 — Is the client the problem?

A `404` from a client method reads as *"the platform does not support this"* and
is sometimes a method pointing at a route the server does not serve.

```bash
python -c "from aegis_sdk.handbook.check import declared_operations as d; \
print(sorted(p for m,p in d() if '<fragment>' in p))"
```

Compare what the client declares against what your deployment serves.
[Client-model fidelity](../guardrails/client-model-fidelity.md) has the
four-state table for this.

## Before you report it

State, in this order: the call, the credential type, the status code, the raw
detail, and the rung at which you stopped. A refusal reported without its
credential is not reproducible, and a refusal reported without the rung invites
the next person to start again from zero.

**If you did change something and the refusal cleared, say which change and what
else it widened.** A remedy that clears a symptom does not confirm the mechanism
you blamed.
