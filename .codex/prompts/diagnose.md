---
name: diagnose
description: "A call failed. Attribute it to a layer before changing anything — credential type, admission, authorization, tenancy, a governance hold, or a defect in this client."
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/commands/diagnose.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


Something was refused, raised, hung or returned a field you did not expect.

**The expensive mistake is not misdiagnosing it. It is changing something before
diagnosing it** — because the change that clears an unattributed refusal is
almost always a widening, and a widening that was not needed is permanent.

Load the **diagnosing-a-refusal** skill. It carries the ladder; this is the
order to work it in and the traps at each rung.

## Rung 0 — Capture the response, not the exception's rendering

```python
try:
    await <the call>
except AgenticOSError as exc:
    print(exc.details.get("status_code"), repr(exc.details.get("message")))
```

**The exception class does not identify the status.** The mapping from HTTP
status to subclass is partial, and the gaps include statuses an integrator meets
routinely. A `try/except` written from the class names alone lets several
failures past and mistakes others for each other.

Discriminate on the **status code**. Load the **error-taxonomy** guardrail before
you write your `except` clause.

## Rung 1 — Which credential made this call?

Before anything else. **An API-key principal carries no personas, ever**, and a
route gated on a persona compares against that empty list and refuses. No scope
configuration changes it, because scopes are not consulted on that path.

So a `403` here is frequently not a permissions problem at all, and the two have
opposite remedies: one is fixed by a different credential, the other by a grant.
Widening the grant to clear a credential-type refusal grants something nobody
needed, permanently.

Handbook chapter **Credentials, and what a key is not**. Guardrail:
**credential-reachability**.

## Rung 2 — Was it reached at all?

Four outcomes, and they are not degrees of the same thing:

| | means | what changes |
| --- | --- | --- |
| **not reached** | no answer came back | transport, host, timeout |
| **not known** | the route is not there for you | credential type, or it does not exist |
| **refused** | it was reached and said no | authorization, tenancy, or a governance hold |
| **fault** | it was reached and broke | not yours to fix; report it |

`python -m aegis_sdk.coc.probe` separates the first two for your deployment and
your credential. Its exit `3` is UNDETERMINED and is not a `0` — a probe that
could not tell you and a probe that found nothing wrong are different results.

## Rung 3 — Refused by authorization, or held by governance?

These look alike from the caller and are opposite in meaning. A governance hold
is **the product working**: an agent reached the edge of a bound someone set
deliberately, and a human is being asked. It clears when the human answers, and
it does not clear by changing a permission.

Handbook chapters **When something is held** and **Approvals, holds and
evidence**. If you cannot tell which you have, check whether anything is waiting
for a decision before you touch a single grant.

## Rung 4 — Is it this client rather than the deployment?

The client's models are hand-authored against a server that moves. When they
disagree, **the server is right and the client is silent** — a field the client
omits and a field the server did not send are indistinguishable from here.

Symptoms: a field that is always `None`; a response that validates but is thinner
than the console shows; a call that succeeds and does nothing. Handbook chapter
**Reading a response honestly**. Guardrails: **client-model-fidelity**,
**sentinels-and-defaults**.

**Also check what you asked for.** A sentinel is a value in the ordinary range
that means something outside it, and a default is a value this client sent
because you said nothing. Both fail the same way and the direction of the error
is almost always permissive.

## Rung 5 — Retries, timeouts, concurrency

Correcting the assumption most integrations start with: this client retries a
request that got **no answer** — a connection failure, a timeout. It retries **no
HTTP status at all**. If your integration needs status-level retry, you are
writing it. Handbook chapter **Concurrency, timeouts and streams**.

## Before you change anything

- [ ] the status code is captured, not inferred from the exception class
- [ ] the credential type is named
- [ ] the failure is attributed to exactly one of: not reached · not known ·
      refused · fault · this client
- [ ] if the answer is "refused", you have established authorization vs hold
- [ ] the change you are about to make addresses **that** layer and no other

⛔ **You cannot read the platform's implementation from here, and a diagnosis
that requires it is not available to you.** Say so, and say what would settle it
— a probe run, a response body, a question for whoever operates the deployment.
An inferred cause stated as an observed one is the failure this whole ladder
exists to prevent.

## Next

- `/orient` — re-establish the target and instrument if the credential changed
- `/construct` · `/extend` — resume, now that the layer is known

**Skills:** `diagnosing-a-refusal` (the ladder in full), `day-two-operations`
(if this is recurring rather than a one-off).
