# 01.1 — What you were given

Three things, and it is worth being precise about each, because the boundaries
between them explain most of what this book can and cannot tell you.

## 1. A deployed Aegis

A running instance, reachable over HTTPS at a base URL someone gave you. It holds
your organisation's state: units, roles, agents, envelopes, trust chains,
knowledge, objectives, and the audit trail of everything that has happened to
them.

You do not administer the process. You administer what is *inside* it.

## 2. This SDK — `aegis_sdk`

A Python client for that deployment. It is not a thin HTTP wrapper: it is
organised into typed modules that mirror the governed nouns, so the code you
write reads like the organisation you are describing.

```python
client.organizations   # the tenant root
client.units           # organisational units — the knowledge boundaries
client.roles           # roles within units, and their authority level
client.teams           # working groups
client.role_envelopes  # what a role's delegate may do
client.knowledge       # governing documents, with a review lifecycle
client.ontology        # the vocabulary a vertical speaks
client.agents          # the agents themselves
client.trust.chains    # who delegated authority to whom
client.trust.postures  # how much autonomy an agent currently holds
client.trust.audit     # the trust-decision record
client.objectives      # work you ask for
client.requests        # work items that need a human
client.sessions        # an agent's actual run
client.approvals       # the queue of things waiting on a person
client.compliance      # evidence export and audit verification
```

The full client exposes considerably more than this — revenue and licensing,
analytics, connectors, webhooks, notifications, pools, applications, specialist
configuration, LLM provider settings. The list above is the set an architect or
operator touches on a normal day.

Two facts about the client that shape how you use it:

- **It is asynchronous.** Every call is `await`ed. If you are writing a
  provisioning script, it runs inside `asyncio.run(...)`.
- **Its return shapes are not uniform, and this catches people.** Some modules
  return typed models with attribute access (`agent.id`); the vertical-standup
  modules return raw dictionaries with subscript access (`unit["id"]`). Mixing
  them up produces a `TypeError` or an `AttributeError` at the point of use
  rather than at the call. When in doubt, `print(type(result))` once.

## 3. This handbook, and the working artifacts beside it

The handbook ships *inside* the package, at `aegis_sdk/handbook/`, which is why
the verification command in the introduction works on your machine and not only
on someone else's. That is deliberate: a handbook whose honesty can only be
checked by its authors is asking you to take its word.

Beside it, at `aegis_sdk/coc/`, is a set of **working artifacts** — the same
working mode this book describes, in a form your tooling can load rather than a
form you read:

Every path below is a link, and the gate that checks this book resolves all of
them. A table of coordinates nothing verifies is the failure this whole edition
is built to avoid, so the rows arrived in the same change that made them
checkable.

**Two agent briefs** — a specialist's responsibilities, written so a question can
be answered without inventing server behaviour:

| brief | for |
| --- | --- |
| [`coc/agents/aegis-sdk-specialist.md`](../../coc/agents/aegis-sdk-specialist.md) | building against the client — what it exposes, what it refuses to assume |
| [`coc/agents/aegis-operator.md`](../../coc/agents/aegis-operator.md) | running an organisation day to day, across both surfaces |

**Six skills** — the order of operations for a task, not an explanation of it:

| skill | when |
| --- | --- |
| [`coc/skills/working-against-a-deployment.md`](../../coc/skills/working-against-a-deployment.md) | connecting, establishing what you hold, measuring reachability |
| [`coc/skills/running-an-objective.md`](../../coc/skills/running-an-objective.md) | submitting work and following it to a result |
| [`coc/skills/registering-a-tool-or-agent.md`](../../coc/skills/registering-a-tool-or-agent.md) | extending the platform with something of your own |
| [`coc/skills/reading-trust-and-governance.md`](../../coc/skills/reading-trust-and-governance.md) | answering "why was this allowed" or "why was it not" |
| [`coc/skills/diagnosing-a-refusal.md`](../../coc/skills/diagnosing-a-refusal.md) | a call came back denied and you need to know which kind |
| [`coc/skills/day-two-operations.md`](../../coc/skills/day-two-operations.md) | the work that starts after the organisation exists |

**Six guardrails** — obligations carried with their reasons, so they can be
argued with rather than only obeyed:

| guardrail | the obligation |
| --- | --- |
| [`coc/guardrails/credential-reachability.md`](../../coc/guardrails/credential-reachability.md) | establish what your credential can reach before concluding anything from a refusal |
| [`coc/guardrails/error-taxonomy.md`](../../coc/guardrails/error-taxonomy.md) | tell a refusal from a fault from an unauthenticated call; they are three things |
| [`coc/guardrails/reading-a-measurement.md`](../../coc/guardrails/reading-a-measurement.md) | name what would have proved you wrong before citing what you measured |
| [`coc/guardrails/client-model-fidelity.md`](../../coc/guardrails/client-model-fidelity.md) | the client will not invent a contract the platform does not make |
| [`coc/guardrails/sentinels-and-defaults.md`](../../coc/guardrails/sentinels-and-defaults.md) | a default is a claim; an absent value and a zero are not the same |
| [`coc/guardrails/billing-integrity.md`](../../coc/guardrails/billing-integrity.md) | what a spend control does and does not establish |

**And one runnable check** — [`coc/probe.py`](../../coc/probe.py), invoked as
`python -m aegis_sdk.coc.probe`: a reachability and transport-honesty probe you
run rather than read. [`coc/README.md`](../../coc/README.md) is the door into all
of it.

⚠ **"Agent brief", not "agent".** This platform's own word *agent* means the thing
under governance — the delegate that does work inside an envelope. An agent brief
is a document describing a specialist's responsibilities. The two are unrelated
and readers conflate them instantly, so this book keeps bare "agent" for the
platform's sense throughout and says "agent brief" for the other.

Those artifacts are the **primary** working mode; this book is the explanation
behind them. Where they disagree with a chapter here, they are newer — check the
probe's output against what you read.

## What you were NOT given, and why that shows

You do not have the platform's own source. This is a reachability boundary rather
than a secrecy one, and the practical consequence is visible in how this book is
written: it never cites a file path or a line number, because a coordinate into a
tree you cannot open is simultaneously useless to you and a disclosure.

What it cites instead is **surface you can reach** — an HTTP operation this
client performs, written `api:POST /api/v1/trust/establish`, or a symbol this
package exports, written `sdk:aegis_sdk.TrustChain`. Both resolve on your machine
under `python -m aegis_sdk.handbook.check`.

Be clear-eyed about the trade. A source citation can point at the line that
*enforces* a rule. An existence anchor cannot: it proves the operation is
declared, never that the server enforces anything on it. Where this book asserts
that something is enforced, that assertion rests on observed behaviour or is
labelled, not on the anchor.

## The two surfaces, stated once so the rest of the book can be terse

| | **The harness** | **The console** |
| --- | --- | --- |
| what it is | this SDK, driven from your own code | the web application at your deployment's base URL |
| who uses it | architects, operators | anyone with a login, including you |
| good at | building, bounding, provisioning, promoting between environments, evidencing | answering a held decision, inspecting current state, day-to-day work |
| bad at | being read by someone who does not code | being reviewed, diffed, repeated, or promoted |
| leaves behind | code someone can review before it runs | an audit entry, and no reviewable intent |

Both surfaces hit the same API and are governed identically. Choosing the console
does not get you a lighter check, and choosing the harness does not get you a
heavier one — *design intent, not observable*: the enforcement sits behind the
API rather than in either client, which is why the same call from either side
lands on the same verdict.

---

*Next: [01.2 — The mental model](02-the-mental-model.md)*
