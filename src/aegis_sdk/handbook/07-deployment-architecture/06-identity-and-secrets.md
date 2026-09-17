# 07.6 — Identity and secrets

Most of a deployment's actual security posture reduces to one question: **which
identities exist, and which of them are holding a password.** This chapter is
about the answer the reference architecture gives, and about a contrast you can
draw for yourself before you finish reading it.

## Two identities, and they are different

Keep these apart, because they are conflated constantly and the conflation leads
to bad reasoning about who can do what.

| | Operator identity | Workload identity |
| --- | --- | --- |
| **Whose is it?** | A person's | A workload's |
| **What is it for?** | Administering the deployment | A service reaching a resource |
| **How does it authenticate?** | Interactively, through the identity provider | With a short-lived token issued to the pod |
| **Lifetime** | As long as the person's access is valid | Minutes, refreshed automatically |
| **Can it be shared?** | It should not be, and it is attributable | It is not a thing anyone shares |
| **Blast radius if misused** | Whatever that person's roles allow | Whatever that one workload is permitted |

Neither is privileged over the other in principle. They are simply **different
kinds of principal**, and an architecture that keeps them separate can answer
"who did this?" unambiguously. One that merges them — where a workload
authenticates as a person, or a person's credential is baked into a service —
cannot, and that is the failure this separation exists to prevent.

## A pod holds no long-lived secret

**This is the single most important sentence in this chapter:**

**A pod authenticates to cloud resources as a federated managed identity, which
means there is no long-lived credential stored inside the container.**

Say the negative form too, because it is what the architecture is actually built
to avoid: **a stored credential in a container is the thing this design exists to
prevent.** A password in an environment variable, a key in a mounted file, a
token in an image layer — each is a secret with a long life, many places to leak
from, and no automatic end. Anything that can read the container's environment or
filesystem reads it; anything that can read the image layer reads it forever.

**Workload identity federation** replaces that with a token the pod requests and
receives at runtime, issued because the platform can attest *which workload is
asking*. The credential is short-lived, scoped to the resource being reached, and
never written anywhere durable.

```
┌──────────────────────────────────────────────────────────┐
│ IDENTITIES                                               │
│   operator identity  — a person, attributed              │
│   workload identity  — issued to the pod, minutes long   │
└─────────────────────────────┬────────────────────────────┘
                              │  federated token — one hop, no stored secret
                              ▼
┌──────────────────────────────────────────────────────────┐
│ RESOURCES                                                │
│   container registry · database · secret store · API     │
└──────────────────────────────────────────────────────────┘

┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┆   ✗  STATIC STORED CREDENTIAL — NOT PRESENT              ┆
┆      a credential stored in a container is what this     ┆
┆      design exists to avoid. This box stays empty.       ┆
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
```

The dashed box at the bottom is the one that is *absent*, and it is drawn
deliberately: the contrast between a federated hop and a stored credential is
the entire argument of this section. If you take one thing from this part, take
that this box must stay empty.

*Design intent, not observable:* that no workload in a given deployment holds a
stored credential. This is exactly the kind of claim that is true by construction
in the reference shape and unverifiable from your integration — you cannot see
inside a container. It is also, for that reason, one of the most valuable
questions to put to your operator directly.

## The secret store, and what lives in it

A secret store still exists, and that is not a contradiction — federation removes
the *need* for stored credentials, it does not remove every secret. What actually
lives there:

- **The platform's own credentials** for the resources that genuinely cannot
  issue short-lived tokens — third-party services that only accept a static key,
  for instance.
- **Provider keys**, where a model provider requires an API key rather than
  accepting a federated identity. This is a common and unavoidable case, and it
  is precisely why the store exists.
- **Configuration that is sensitive but not a credential** — endpoints and
  parameters whose disclosure would be a problem.

**The rule that governs all of them: a secret is referenced at runtime, never
baked in.** It is read when the workload needs it, from the store, rather than
being written into an image or a deployment manifest. The distinction is not
stylistic — a secret in an image is in every copy of that image and survives
every rotation of the original, while a referenced secret is one thing in one
place, replaceable without rebuilding anything.

*Design intent, not observable:* what your deployment's store actually contains,
and whether anything in it should have been federated instead. There is no
outside vantage point for this, and the honest position is that it is a
construction property you are told about rather than one you check.

## Rotation, and what it costs a running workload

Rotation is where the two designs above diverge in a way you will feel
operationally, so it is worth stating as a comparison rather than a list.

| What rotates | Trigger | Effect on a running workload |
| --- | --- | --- |
| **Workload identity tokens** | Automatic, continuously | None. The pod asks for the next one. This is the common case. |
| **Federated identities' trust configuration** | Platform change | A pod restart, at a time the platform chooses. |
| **Third-party provider keys** | On a schedule, or on suspicion | A restart or a reload, depending on how the workload reads it. |
| **Your application credential** | You decide | None, if you issue the new one before revoking the old. |

The first row is the payoff of the whole design: **the credential that is used
most often is the one that never needs a maintenance window**, because it was
never stored and its rotation is invisible.

The last row is the one you control, and it is covered next.

## Your credential, and what you can verify about it

Your integration holds an application credential, presented by the client —
`sdk:aegis_sdk.AgenticOSClient` is where that happens, and it is the only
credential your code handles.

Three properties to understand about it:

- **Issued to your organisation, scoped by roles.** What it can do is the union
  of what the roles granted to it permit. Nothing about the credential itself
  confers authority; the scoping is enforced server-side, on every request.
- **Attributable.** Actions taken with it are recorded as having been taken by
  that principal. That is what makes the audit trail mean anything — an entry
  naming a credential that ten systems share is not evidence of much.
- **Revocable.** Revocation is immediate, and it is the reason a leaked
  credential is recoverable rather than terminal.

**You can settle which principal you are, at any time, with
`api:GET /api/v1/auth/me`.** This is more useful than it sounds during an
incident: when a call is refused and the reason is not obvious, the first
question is whether you are who you think you are, and that operation answers it
directly rather than by inference.

**What you can verify from outside, and what you cannot:**

| Claim | Verifiable by you? |
| --- | --- |
| Which principal your credential authenticates as | **Yes** — `api:GET /api/v1/auth/me` |
| What your credential is permitted to do | **Yes, by trying** — refusals are the evidence |
| Who else holds a credential for your organisation | **Partly** — ask; it is your organisation's, not the platform's |
| That no pod holds a stored secret | **No** — take it on trust, and ask |
| How rotation is performed, and when it last happened | **No** — ask your operator |

*Design intent, not observable:* the third row rests on the ownership split in
[07.1](01-what-a-deployment-is.md)'s table, and that table is itself construction.
Whether your organisation or your operator keeps the credential records is a
question to put to them, not an answer this book can give you.

The bottom two rows are the ones to notice. They are the claims this architecture
most wants you to believe and the ones you are least able to check, which is
exactly why they are listed rather than left implicit.

**UNVERIFIED:** every construction claim in this chapter, for any specific
deployment. The reference shape is described; the estate you were handed may
differ, and no part of this document can see into it. Asking is not a workaround
here — for these particular questions, it is the only instrument there is.

---

*Next: [07.7 — Operating the deployment](07-operating-the-deployment.md)*
