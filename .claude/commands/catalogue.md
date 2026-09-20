---
name: catalogue
description: "Answer whether Aegis does a thing, and how you reach it — locate the capability, name its entry point, confirm it on your own deployment, and avoid concluding absence from a surface that is merely a different size."
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/commands/catalogue.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


<!-- anchor-floor: exempt (procedure; routes to handbook chapters and skills by name) -->

Someone has asked whether Aegis can do something. A requirements list, a
security questionnaire, a build-versus-buy call, or your own design.

Two instruments answer it on YOUR deployment rather than in the abstract:
`sdk:aegis_sdk.coc.probe` for reachability and `sdk:aegis_sdk.handbook.check`
for what the book names. The module set itself is `sdk:aegis_sdk.modules`.

**The expensive mistake is concluding ABSENCE.** A capability you cannot find is
usually one of three things that are not absence: it is filed under control
rather than capability, it is served over HTTP without a client method, or it
exists and was never activated. All three read identically to a quick search.

Work the five steps below in order. Skipping to a search of the client's method
names is what produces a confident wrong "no".

## 1 — Decide whether you are asking about capability or control

Do this first, because most requirements that sound like capability are control.

_"Can an agent be prevented from spending over a limit?"_ is not an agent
question — it is an envelope question. _"Can we stop a compromised integration?"_
is revocation. _"Can access be limited by data sensitivity?"_ is clearance.

| the question sounds like | it is usually   | chapter                          |
| ------------------------ | --------------- | -------------------------------- |
| what an agent can do     | what bounds it  | **Governance and trust**         |
| who can use the system   | identity + RBAC | **Organisation and identity**    |
| what gets recorded       | evidence        | **Evidence and operations**      |
| what attaches externally | grants          | **Commercial and extensibility** |

**Five of the eighteen capability areas live in the governance chapter.** If a
requirements list separates trust chains, postures, envelopes, clearances and
bridges into five items, it is describing one apparatus from five angles — read
that chapter once rather than searching five times.

## 2 — Locate the area

The handbook chapter **How to read this catalogue** carries the eighteen-area
index and maps every area to its chapter. Use it rather than guessing, and
rather than reading chapter titles — the titles group by subject, the index
groups by the question you arrived with.

Load the **domain-surfaces** guardrail if you are unsure which vocabulary a
capability belongs to.

## 3 — Name the entry point, then read the module's own methods

Every area names its entry point as a resolvable symbol. Two shapes:

| shape      | reached as                                      |
| ---------- | ----------------------------------------------- |
| top-level  | `client.pools`, `client.agents`                 |
| namespaced | `client.trust.chains`, `client.revenue.billing` |

There are three namespaces — `trust`, `revenue`, and `dataflow` for lineage.
Everything else hangs directly off the client.

**The module's own method list is the finest-grained catalogue there is**, and it
is more current than any prose:

```python
import aegis_sdk.modules.pools as pools

print([m for m in dir(pools.PoolsModule) if not m.startswith("_")])
```

The chapters print representative operations for the largest families rather
than all of them, and they say so where they do. When you need the exhaustive
answer for one area, read the module.

## 4 — Confirm it on YOUR deployment

The catalogue is a statement about the platform. What your credential reaches on
your deployment is a different question, and you can answer it yourself:

```bash
python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" --api-key "$AGENTIC_OS_API_KEY"
python -m aegis_sdk.handbook.check    # every route and symbol the book names, resolved
```

⛔ **Exit `3` is UNDETERMINED and is not a `0`.** An expired credential and a
perfectly reachable API produce the same empty finding set, so the probe refuses
a zero it did not earn. Fix the credential and run it again.

A run with findings across a whole family usually means **unreachable by that
credential**, not absent. Load the **credential-reachability** guardrail before
concluding anything from it, and the **reading-a-measurement** guardrail before
quoting a count from it.

## 5 — Before you report that Aegis cannot do it

Three checks, each of which has produced a wrong "no":

**The client is smaller than the platform, deliberately.** The client declares
933 operations; the platform serves roughly 1,254 authored ones. A capability
with no client method is reached over HTTP — `/diagnose` and the chapter
**Calling the API** cover that path. It is a difference in surface size, not a
missing feature.

**A projection never fails.** Effective constraints, access matrices and trust
scores are computed from whatever inputs exist, so an incomplete organisation
returns a successful, authoritative-looking, permissive answer. If a governance
result surprises you, ask what it was computed from.

**Created is not active.** This is the single most repeated shape in the
platform, and it is always two calls:

| you did                  | it is not yet    | until    |
| ------------------------ | ---------------- | -------- |
| create an envelope       | in force         | activate |
| approve knowledge        | available        | publish  |
| create an objective      | running          | submit   |
| approve a change request | applied          | apply    |
| approve a promotion      | effected         | execute  |
| compile policy           | governing        | apply    |
| authorize a bridge       | carrying traffic | activate |

**Nothing errors in any of these.** The record exists, every listing shows it,
and the capability does nothing. Before reporting a capability broken or absent,
check whether the second call was made.

## Before you answer the question

- [ ] you have established whether it is a capability or a control question
- [ ] you located the area through the eighteen-area index, not by title
- [ ] you read the module's methods, not only the chapter's printed subset
- [ ] you confirmed reach on your own deployment, and read the exit code
- [ ] if you are reporting absence, you have ruled out all three of step 5

⛔ **You cannot read the platform's implementation from here.** Where the honest
answer is "this deployment would have to be asked", say that and say what would
settle it — a probe run, a manifest call, a question for whoever operates it.
An inferred absence stated as an observed one is the failure this procedure
exists to prevent.

## Next

- `/orient` — if you have not established the deployment and credential
- `/construct` · `/extend` — you found the capability and are now building
- `/diagnose` — you found it, called it, and it refused

**Skills:** `working-against-a-deployment` for the order of operations,
`reading-trust-and-governance` when the answer landed in the governance chapter.
