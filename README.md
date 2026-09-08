# Aegis SDK

The Python client for the Aegis platform, the architect's working material, and
the handbook — in one repository you can clone and open an AI coding CLI inside.

This is the repository a **delivery partner** clones to construct an Aegis
deployment for a client.

```bash
git clone <this-repo> && cd aegis-sdk
python -m venv .venv && . .venv/bin/activate
pip install -e .
python -m aegis_sdk.handbook.check          # verify the build has what the prose names
```

Then open your CLI in the repository root. All three are wired:

| CLI | reads | you get |
| --- | --- | --- |
| Claude Code | `CLAUDE.md`, `.claude/agents/`, `.claude/skills/` | 2 agents, 13 skills |
| Codex | `AGENTS.md`, `.codex/prompts/`, `.codex/skills/` | 2 personas via `/prompts:specialist-<name>`, 13 skills |
| Gemini CLI | `GEMINI.md`, `.gemini/agents/`, `.gemini/skills/` | 2 agents, 13 skills |

All three are **projections of one neutral source**, `src/aegis_sdk/coc/`. Edit
there and re-run `node scripts/project_coc.mjs`; `--check` reds on drift.

## What this is

| | |
| --- | --- |
| `src/aegis_sdk/` | the client — 152 Python modules, version 1.0.0 |
| `src/aegis_sdk/handbook/` | how the platform **behaves** — 27 chapters in 5 parts, screenshots included |
| `src/aegis_sdk/coc/` | what to **do** about it — 2 agent briefs, 6 task skills, 7 guardrails, one probe |
| `src/aegis_sdk/docs/` | reference: quickstart, authentication, configuration, errors, streaming |
| `src/aegis_sdk/examples/` | five runnable examples |

## What this is NOT

**It is not the platform, and the platform's source is not here.** You were given
a client, a credential, and the URL of a running deployment. You cannot boot
Aegis from this repository, read its route table, or run its tests. That is
deliberate: the platform is protected IP.

Everything in this repository is written for that position. Where a claim could
not be settled from inside this package, the text says **UNVERIFIED** rather
than guessing — and `python -m aegis_sdk.coc.probe` is how you settle several of
them against your own deployment instead.

## Distribution name

The distribution is published as **`agentic-os-sdk`**, and that name is
**PROVISIONAL**.

⛔ **Do not `pip install aegis-sdk`.** That name on PyPI belongs to an unrelated
third-party package ("on-premise PII detection and masking for AI
applications"), published by a different company. Installing it gets you the
wrong software under a right-sounding name. Confirm availability on the target
index before any publish.

## Verify this material against your own build

Every count, field name and method name in the prose was true of one build. Two
commands re-derive the ground truth in seconds, and they are the right response
to any sentence here you are about to rely on:

```bash
python -m aegis_sdk.handbook.check
python -c "from aegis_sdk.handbook.check import declared_operations as d; print(len(d()))"
```

## Repository checks

```bash
python -m aegis_sdk.handbook.check          # handbook + coc anchors resolve in this build
node scripts/project_coc.mjs --check        # CLI overlays match their neutral source
python -m aegis_sdk.coc.probe --transports-only   # which client paths are real (offline)
```

## Accountability

The organisation deploying an agent keeps the accountability for what that agent
does. It cannot be delegated, and no amount of autonomy transfers it. What this
platform provides is the proof — the bounded mandate, the tamper-evident audit
trail, the fail-closed gate, the attestable lineage — that lets that organisation
show an auditor how it discharged the accountability it already had.

You keep the accountability. This gives you the evidence.

---

Aegis is Integrum's commercial implementation of four open standards — CARE,
PACT, EATP and CO — published by the Terrene Foundation under CC BY 4.0. Aegis
implements them; it does not own them.

Assembled 2026-09-08 · see `docs/UNRESOLVED.md` for what is not settled.
