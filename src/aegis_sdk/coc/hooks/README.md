# Enforcing hooks

Five guards. They run in the delivery partner's CLI session, on the tool call,
before it happens. They are the half of this working material that does not
depend on being read.

```bash
node src/aegis_sdk/coc/fixtures/run.mjs      # 122 cases + 8 mutation controls
node scripts/project_coc.mjs --check         # registrations in sync across three CLIs
```

## The set

| hook | event | severity | what it refuses |
| --- | --- | --- | --- |
| `deployment-blast-radius` | PreToolUse:Bash | **block** | a mutating call to a live client deployment whose target has not been named |
| `client-credential-containment` | PreToolUse:Bash·Write·Edit | **block** | a client credential's literal value reaching anywhere but that client's deployment |
| `source-absence-boundary` | PreToolUse:Write·Edit·Bash | halt-and-report | a durable claim that could only have come from platform source this repo does not contain |
| `probe-before-claim` | PreToolUse + PostToolUse | halt-and-report | a reachability claim with no answering probe run on record |
| `anchor-integrity` | PreToolUse:Write·Edit | **block** | prose whose anchors do not resolve, or that falls below its pinned floor |

## Guardrail ↔ hook, and the gap

Derived on every projection from each hook's `enforces` list, never hand-written.
`project_coc.mjs --check` prints it whether it is green or not, because the
finding that started this work — fifteen artifacts, zero hooks — survived
precisely by nobody ever printing the pairing.

| guardrail | enforced by |
| --- | --- |
| `credential-reachability.md` | `deployment-blast-radius`, `client-credential-containment` |
| `client-model-fidelity.md` | `source-absence-boundary` |
| `reading-a-measurement.md` | `probe-before-claim` |
| `billing-integrity.md` | **PROSE ONLY** |
| `error-taxonomy.md` | **PROSE ONLY** |
| `sentinels-and-defaults.md` | **PROSE ONLY** |
| `coc-context.md` § source absence | `source-absence-boundary` |
| `anchors.json` (both roots) | `anchor-integrity` |

**Three of six guardrails still have no hook.** Stated here rather than left to
be discovered: those three are billing arithmetic, error-taxonomy discipline and
sentinel/default handling — all properties of code a partner writes, not of a
tool call, so they need a different instrument than a PreToolUse guard.

## Three rules that are not negotiable

**Severity is earned, not chosen.** `block` requires process state — an
environment value, a file on disk, a derived operation set, a real import. A
regex over prose gets `halt-and-report`. Two of these guards read text and say so
in their own headers rather than dressing a lexical match up as evidence.

**Fail open on every error.** No python, no git, malformed stdin, budget spent:
allow, silently. A guard that wedges a partner's session is disabled within a
day, and a disabled guard protects nothing. ⛔ But silence means UNMEASURED, not
clean — `anchor-integrity` emits an advisory naming its SKIPPED count rather than
letting an unrun check read as a green one.

**Report the denominator.** Every emission carries what was examined. "0
findings" and "examined nothing" print identically, and that is not a
hypothetical: the platform's own citation gate was measured blind to 25% of its
corpus while reporting clean.

## One source, three CLIs

Hook SCRIPTS land once, at `.claude/hooks/`, and all three CLIs invoke that path.
Only the REGISTRATION is projected three times, from `hooks.manifest.json`.

Three copies of a *document* can drift and a diff shows it. Three copies of a
*program* can drift in behaviour, which no diff shows.

⚠ **Codex fires hooks on the Bash lane only.** `anchor-integrity` therefore does
not fire there at all, and two others are partial. Recorded per hook in
`hooks.manifest.json::codex_coverage` and carried into the emitted
`.codex/hooks.json` — a gap named where someone would look for it, rather than
found when a guard turns out never to have run.
