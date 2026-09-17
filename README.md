# Aegis SDK

The Python client for the Aegis platform, the architect's working material, and
the handbook — in one repository you can clone and open an AI coding CLI inside.

This is the repository a **delivery partner** clones to construct an Aegis
deployment for a client.

You are already inside the repository — you cloned it to get here, and this
file is the first thing to read once you have. No clone URL is given because
this repository is published per deployment and the address belongs to whoever
handed it to you, not to this file.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
python -m aegis_sdk.handbook.check          # verify the build has what the prose names
```

## Start here — the handbook

**The handbook is at `src/aegis_sdk/handbook/` — 41 chapters in
7 parts.** It is four levels down inside a Python package because
it ships with the installed client rather than only with this clone, so you will
not stumble across it.

**Day one, read this first:**

```
src/aegis_sdk/handbook/05-the-web-console/01-first-login.md
```

That is the first thing your client will see, so it is the first thing you should.
From there the parts run in order: `01-orientation` (what the platform is and what
it refuses), `02-working-through-the-harness` (driving it from a CLI),
`03-extending-the-platform` (adding tools, agents and surfaces),
`04-the-api-surface` (the wire contract), `05-the-web-console` (what the client
touches).

**The lifecycle is driven by 4 commands.** They are derived from the handbook's own
part structure, not hand-listed, and they are wired in all three CLIs:

| command | what it does |
| --- | --- |
| `/orient` | Name the deployment and the credential, run the probe, and record what it could **not** tell you — before touching anything. |
| `/construct` | Stand up the client's organisation, roles and trust structure against a deployment you cannot read the source of. |
| `/extend` | Add tools, agents and surfaces, and check they are actually reachable rather than merely registered. |
| `/diagnose` | Work out why the platform refused something — separating a governance decision from a defect. |

`node scripts/project_coc.mjs` prints the live stage-to-command mapping; it is the
authority if this table and the tree ever disagree.

Then open your CLI in the repository root. All three are wired:

| CLI | reads | you get |
| --- | --- | --- |
| Claude Code | `CLAUDE.md`, `.claude/agents/`, `.claude/skills/`, `.claude/commands/` | 2 agents, 13 skills, 4 commands |
| Codex | `AGENTS.md`, `.codex/prompts/`, `.codex/skills/` | 2 personas via `/prompts:specialist-<name>`, 13 skills, 4 commands via `/prompts:<name>` |
| Gemini CLI | `GEMINI.md`, `.gemini/agents/`, `.gemini/skills/`, `.gemini/commands/` | 2 agents, 13 skills, 4 commands |

All three are **projections of one neutral source**, `src/aegis_sdk/coc/`. Edit
there and re-run `node scripts/project_coc.mjs`; `--check` reds on drift.

## What this is

| | |
| --- | --- |
| `src/aegis_sdk/` | the client — 169 Python modules, version 2.0.0 |
| `src/aegis_sdk/handbook/` | how the platform **behaves** — 41 chapters in 7 parts, screenshots included |
| `src/aegis_sdk/coc/` | what to **do** about it — 2 agent briefs, 6 task skills, 7 guardrails, 4 commands, one probe |
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
pip install -e ".[dev,nexus]"               # test tooling, with ruff and mypy pinned
python packaging/aegis-sdk/harness.py all   # lint + types + wheel + tests
python -m aegis_sdk.handbook.check          # handbook + coc anchors resolve in this build
node scripts/project_coc.mjs --check        # CLI overlays match their neutral source
python -m aegis_sdk.coc.probe --transports-only   # which client paths are real (offline)
```

This repository carries **47 test files**, and `harness.py tests` runs them.
They are the ones that could be published. Others exist that pin this client
against the platform's own server routes; those name internal source coordinates
in their assertions and stay behind. **So a green run means the client behaves —
it does not re-verify the wire contract against a live deployment.**
`python -m aegis_sdk.coc.probe` is how you check that against your own.

`harness.py all` is **green on arrival** — all four steps. If it is not, that is
a finding about this build and worth reporting; it is not a state you inherited.

The `typecheck` step is a per-file ratchet against a banked budget, not a
zero-error claim: the SDK carries type debt, and the budget records exactly how
much, per file, so it can only shrink. A file may improve and may never regress.
`docs/UNRESOLVED.md` § 3b has the current numbers and what remains unfixed.

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

Assembled 2026-09-17 · see `docs/UNRESOLVED.md` for what is not settled.
