# The working material — the harness is the primary surface

You cloned this repository, and you have a credential and the URL of a running
Aegis platform. You do not have the platform's source, and you cannot boot it, run
its tests, or read its route table. Everything here is written for that position
rather than adapted to it.

**This is how architects and operators work with Aegis: the SDK driven from your
own code — the harness — as against the web console.** Not a convenience layer
over the console. The harness is the default surface: it is scriptable,
reproducible, and it leaves a receipt. The console is the secondary surface, and
it is genuinely the better answer for some steps — where that is true, the skills say
so by name rather than pretending otherwise.

The handbook beside this directory (`aegis_sdk/handbook/`) says how the platform
**behaves**. This directory says what to **do** about it, including the several
cases where the behaviour is inconvenient and no amount of configuration changes
it.

## Agents

| File                                                               | Answers                                                                                          |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| [`agents/aegis-sdk-specialist.md`](agents/aegis-sdk-specialist.md) | _how do I call this_ — module surface, auth modes, errors, without inventing server behaviour    |
| [`agents/aegis-operator.md`](agents/aegis-operator.md)             | _what do I do about what I am seeing_ — queues, evidence, spend, and when the answer is a person |

## Skills — the working loop, end to end

| File                                                                               | The task                                                                                |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [`skills/working-against-a-deployment.md`](skills/working-against-a-deployment.md) | the spine: connect, establish what you hold, measure reachability, submit, work an item |
| [`skills/registering-a-tool-or-agent.md`](skills/registering-a-tool-or-agent.md)   | stand up a tool agent or task agent and prove it is callable                            |
| [`skills/running-an-objective.md`](skills/running-an-objective.md)                 | submit, clarify, track, act on a hold, confirm completion                               |
| [`skills/reading-trust-and-governance.md`](skills/reading-trust-and-governance.md) | posture, chains, envelopes, permissions, audit — and what each does not establish       |
| [`skills/diagnosing-a-refusal.md`](skills/diagnosing-a-refusal.md)                 | the seven-rung ladder; attribute before you change anything                             |
| [`skills/day-two-operations.md`](skills/day-two-operations.md)                     | the operator's recurring loop, including the sweeps that hide their own emptiness       |

## Guardrails — obligations, each with its Why

| File                                                                             | The obligation                                                                         |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| [`guardrails/credential-reachability.md`](guardrails/credential-reachability.md) | a 403 is often a credential-TYPE problem; never widen to clear an unattributed refusal |
| [`guardrails/error-taxonomy.md`](guardrails/error-taxonomy.md)                   | discriminate on the status code, never on the exception subclass                       |
| [`guardrails/reading-a-measurement.md`](guardrails/reading-a-measurement.md)     | three-valued fields; an empty result is absence of records, not of events              |
| [`guardrails/sentinels-and-defaults.md`](guardrails/sentinels-and-defaults.md)   | a value indistinguishable from an intention is a defect, not a convenience             |
| [`guardrails/billing-integrity.md`](guardrails/billing-integrity.md)             | the errors on this surface are commercial and surface at reconciliation                |
| [`guardrails/client-model-fidelity.md`](guardrails/client-model-fidelity.md)     | what the client omits you never see; some endpoints must not be wrapped                |

## Start here

```bash
python -m aegis_sdk.handbook.check                 # does this build still have what the prose names?
python -m aegis_sdk.coc.probe --transports-only    # which client paths are real? offline, no credentials
```

Then, with a URL and credentials:

```bash
export AGENTIC_OS_BASE_URL=https://<your-deployment>   # required; there is no default
python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" \
    --api-key "$KEY" --token "$SESSION_TOKEN"
```

That last one answers, for your deployment, a question the handbook explicitly
marks **UNVERIFIED**: which routes your API key cannot reach at all. It could not
be answered there — a route list derived from source you cannot open, checked by
a gate you cannot run, about a build that is not necessarily yours, is an
assertion with a decoration on it. Measured against your own deployment it is an
answer you hold.

## The three habits all of this exists to install

**1. Name the credential.** An answer that is true for a session and false for an
API key, given without saying which, is worse than no answer. Most of what looks
like a permissions problem here is a credential-type problem, and the two have
opposite remedies.

**2. Name what would have proved you wrong.** Before citing any check as
evidence, say what it would have printed had the claim been false. A probe run
with an expired token refuses everything and reports nothing — byte-identical to
a healthy result. That is why `probe.py` verifies its credentials against a
control operation first and exits `3` UNDETERMINED rather than `0` when it
cannot tell. A green that could not have been red is not a green.

**3. Separate what you observed from what you inferred.** "This client declares
the operation" and "the deployment serves the operation" are different claims,
and only the first is free. This package's route knowledge is _its own belief
about the API_ — where it is wrong, it is wrong confidently and in the same
direction as anything derived from it.

## Verify this material against your own build

Every count, field name and method name here was true of one build. Two commands
re-derive the ground truth in seconds, and they are the right response to any
sentence in this directory you are about to rely on:

```bash
python -m aegis_sdk.handbook.check
python -c "from aegis_sdk.handbook.check import declared_operations as d; print(len(d()))"
```

Where a claim could not be settled from inside this package, the text says
**UNVERIFIED** rather than guessing.

## What none of this establishes

That a route you can reach is doing what you think. Reachability is admission,
not correctness, and not enforcement — a route that admits you when it should not
returns `200`, and nothing here can see that. Read every gate in this package for
what it says it checks, not for the reassurance it produces.

## Accountability

The organisation deploying an agent keeps the accountability for what that agent
does. It cannot be delegated, and no amount of autonomy transfers it. What this
platform provides is the proof — the bounded mandate, the tamper-evident audit
trail, the fail-closed gate, the attestable lineage — that lets that organisation
show an auditor how it discharged the accountability it already had.

You keep the accountability. This gives you the evidence.

Aegis is Integrum's commercial implementation of four open standards — CARE,
PACT, EATP and CO — published by the Terrene Foundation under CC BY 4.0. Aegis
implements them; it does not own them.
