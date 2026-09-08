# Client-model fidelity — what the client omits, you never see

**Scope:** every response you read through a typed model, and every endpoint you
are tempted to wrap because it exists.

The client's models are hand-authored against a server that moves. When they
disagree, **the server is right and the client is silent** — which is the worst
combination, because a missing field and a field the server did not send are
indistinguishable from where you sit.

## MUST 1 — A `None` from a typed model is two claims, and you must separate them

```
the server did not send it   vs   the client does not declare it
```

Both surface as `None` or as an absent attribute. Only the first is information.
The principal model `sdk:aegis_sdk.User` is the one you will test this on first,
read from `api:GET /api/v1/auth/me`.

```python
# DO — when a field you expect reads empty, look at the raw body once
raw = await client._http.request("GET", "/api/v1/…")
print(sorted(raw))          # what the server ACTUALLY sent

# DO NOT — conclude the platform does not populate it
```

**Why:** this has happened, in this client, to fields that matter. Two
organisation models were each missing exactly one field the server declares, and
every consumer reading them got nothing back with no error and no warning. The
symptom is a feature that looks unimplemented and is merely unmodelled — and the
architect reports a platform gap that does not exist.

Reaching past the model is the right move **for this diagnosis and no other**. If
the raw body carries the field, the defect is client-side and the fix is a model
change, not a workaround at your call site.

## MUST 2 — Verify a claim about the surface against your own build, not against prose

Including this file. Every count, field name and method name in the shipped
material was true of one build.

```bash
# DO — settle it against the package you installed
python -m aegis_sdk.handbook.check     # every named surface still exists?
python -c "from aegis_sdk.handbook.check import declared_operations as d; \
print(len(d()))"                        # how many operations this client declares
```

**Why:** a claim you cannot re-derive is an assertion with a decoration on it. The
two commands above are the whole re-derivation and they take seconds.

## MUST 3 — Some endpoints exist and must not be called from here

Three authentication paths — an SSO callback, its public variant, and a SAML
assertion consumer — are deliberately **not** wrapped by this client, and their
absence is a decision rather than an omission:

- the callbacks answer `307` and set **HTTP-only, host-only session cookies**
  that an SDK call cannot hold;
- the assertion consumer takes a SAML assertion signed by the identity provider,
  which a client cannot construct **and should not be able to**.

```
# DO      route the human to a browser; collect the resulting session token
# DO NOT  wrap the callback, or hand-build an assertion to POST at it
```

**Why:** a method wrapping either is a method nobody can correctly call. More
usefully, the instinct generalises: **some endpoints are browser targets or
identity-provider targets, and reaching for one from the SDK means you have
misread the flow rather than found a gap.** If wrapping an endpoint requires you
to forge something a third party is supposed to sign, stop — the thing you are
about to build is an attack, not an integration.

## MUST 4 — A missing wrapper is not evidence of a missing capability, and vice versa

Four states, and they need different actions:

| client | server | what it is |
| ------ | ------ | ---------- |
| wraps  | serves | ordinary |
| wraps  | absent | a client defect — the method 404s for everyone |
| absent | serves | unwrapped; call it through the raw request path |
| absent | absent | genuinely not a capability |

**Why:** rows two and three are the expensive ones and they look alike from a
distance. Row two sends an architect to the platform team about a client bug; row
three sends them away believing a capability is missing when it is one raw call
away. [the credential guardrail](credential-reachability.md)'s two-credential retry and the operation
derivation above are what separate them.

## MUST NOT — Add a field to a local model to make a value appear

**Why:** the model is a description, not a request. Declaring a field the server
does not send produces `None` with more steps, and now the client asserts a
contract nobody honours — which the next reader will believe.

## What this does not cover

Whether a field the server sends means what its name suggests. Fidelity is about
the field arriving; the measurement guardrail is about what a value means once it
has.
