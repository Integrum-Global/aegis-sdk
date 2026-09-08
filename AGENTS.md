<!-- PROJECTED FILE — do not edit here.
     Source of truth: coc-context.md (one neutral body, three CLI filenames)
     Regenerate: node scripts/project_coc.mjs -->

# Aegis SDK — working context

You are working in the **Aegis SDK** repository. This is the client, the
architect's working material, and the handbook. It is what a delivery partner
clones to construct an Aegis deployment for a client.

**You do not have the platform's source, and you will not be given it.** That is
deliberate and it is the single most important fact about this repository. Every
piece of material here is written for that position rather than adapted to it.
If a question can only be answered by reading the platform's implementation, the
honest answer is that it cannot be answered from here — say so rather than
inferring, and say what would settle it.

## What you have

| | |
| --- | --- |
| `src/aegis_sdk/` | the Python client — 114 modules, version 1.0.0 |
| `src/aegis_sdk/handbook/` | how the platform **behaves** — 27 chapters in 5 parts |
| `src/aegis_sdk/coc/` | what to **do** about it — 2 agent briefs, 6 skills, 7 guardrails |
| .codex/prompts/ · .codex/skills/ | the same material, projected for Codex |

The handbook and the working material are the SAME text you see wired into
Codex. `src/aegis_sdk/coc/` is the source of truth; the CLI overlays are
projections of it. Edit the source, then run `node scripts/project_coc.mjs`.

## Start here

```bash
python -m aegis_sdk.handbook.check                 # does this build still have what the prose names?
python -m aegis_sdk.coc.probe --transports-only    # which client paths are real? offline, no credentials
```

With a deployment URL and a credential:

```bash
export AGENTIC_OS_BASE_URL=https://<your-deployment>   # required; there is no default
python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" --api-key "$KEY" --token "$SESSION_TOKEN"
```

The probe answers, **for your deployment**, a question the handbook marks
UNVERIFIED: which routes your credential cannot reach at all. It verifies its
own credentials against a control operation first and exits `3` UNDETERMINED
rather than `0` when it cannot tell — an expired token and a healthy API produce
identical output from a probe that skips that step.

## Three habits this material exists to install

**1. Name the credential.** An answer that is true for a session and false for
an API key, given without saying which, is worse than no answer. Most of what
looks like a permissions problem here is a credential-type problem, and the two
have opposite remedies.

**2. Name what would have proved you wrong.** Before citing any check as
evidence, say what it would have printed had the claim been false. A green that
could not have been red is not a green.

**3. Separate what you observed from what you inferred.** "This client declares
the operation" and "the deployment serves the operation" are different claims,
and only the first is free.

## What is out of scope here

- **The platform's source.** Not present, not vendored, not quoted. Do not
  reconstruct it from the client, and do not cite paths into it — a path the
  reader cannot open is useless to them and discloses the shape of protected IP.
- **Booting the platform.** You work against a *deployed* Aegis over HTTP. There
  is no server to start in this repository.
- **Reading the platform's route table or tests.** The client's declared
  operations are this package's own *belief* about the API. Where it is wrong,
  it is wrong confidently and in the same direction as anything derived from it.

## Reachability is not correctness

A route you can reach may not be doing what you think. Reachability is
admission, not correctness, and not enforcement — a route that admits you when
it should not returns `200`, and nothing in this repository can see that. Read
every check here for what it says it checks, not for the reassurance it
produces.

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
