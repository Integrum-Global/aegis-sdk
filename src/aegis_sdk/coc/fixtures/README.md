# Fixtures for the enforcing hooks

```bash
node src/aegis_sdk/coc/fixtures/run.mjs                 # every case, then the mutation controls
node src/aegis_sdk/coc/fixtures/run.mjs --only <hook>   # one hook
node src/aegis_sdk/coc/fixtures/run.mjs --mutations     # the controls alone
```

**This repository had no fixture convention before this directory.** That is
stated rather than implied, because "there was a convention and I followed it"
and "I established one" are different claims and only the second is true. What
follows is the convention, and the reason for each part of it.

## Why a guardrail without a fixture does not count

Six guardrails shipped here as prose. One of them is named
`reading-a-measurement`, and nothing measured whether it was ever read. That is
the shape this directory exists to end: an obligation with no instrument behind
it is a suggestion, and a suggestion is what the platform repository has already
had to retire three separate times — a worktree census that had to become a
ceiling, an idle-lane guard that was advisory for three cycles before it grew
teeth, and a drain signal an orchestrator read backwards all day with the rule
loaded.

## The four properties, each with the failure it prevents

**Real scripts, real processes.** Every case spawns the actual hook file with an
actual JSON payload on stdin and reads the actual exit code. Nothing is imported
and nothing is stubbed. These guards' predicates ARE their process interactions
— an environment value, a receipt on disk, a subprocess that may not exist — so
a mocked hook would be testing the one part that cannot be wrong.

**Both polarities, always.** A guard that always blocks passes every "it caught
the bad thing" test ever written. Of the 122 cases here, the majority assert
SILENCE. Three are named in the commissioning brief as the false positives that
would make a delivery partner switch the whole set off, and they are pinned
hardest:

| must stay silent | case |
| --- | --- |
| a read-only probe | `SILENT: the probe, live, by name` · `SILENT: the probe, offline` |
| a properly-labelled inference | `SILENT: labelled as inference` · `SILENT: hedged with 'appears'` |
| an already-confirmed target | `SILENT: an already-confirmed target does not re-prompt` |

**A negative-control corpus, with its denominator printed.**
`source-absence-boundary` is run over **every shipped prose file in the package**
— 48 of them — and must be silent on all 48. That corpus is not a convenience
sample: it is prose about platform behaviour written from exactly the position
the guard polices, by an author who did not have the source, which makes it the
hardest possible silence case. The sweep prints `examined=N fired=N` and FAILS
if `examined` is zero, because a corpus sweep that found no files reports clean
identically to one that found nothing wrong.

That calibration is what forced the guard's handbook scoping. On its first run
it fired once, on the handbook legitimately describing the platform's internal
layering. The pattern was not weakened to make that go away — the SCOPE was
corrected, and the handbook's own anchor gate, which is strictly stronger, was
named as what governs it instead.

**Mutation controls, in a scratch copy, with reachability recorded.**
`--mutations` breaks each guard in a COPY of the tree and requires the suite to
red. Never in place: mutating a shared checkout is how a fleet manufactures
false findings, and this harness must not be able to leave the repository
damaged.

⛔ **A non-reddening mutation is not a verdict.** It leaves two live hypotheses —
a vacuous test, or an INERT mutation that never reached the code. The harness
therefore asserts the text it is about to change is PRESENT, and reports
`INERT (prove none)` separately from `ESCAPED`. Without that, a typo in a
mutation string produces a green run and a false vacuity verdict against a
working control, which is worse than no mutation testing at all.

## Measured state

```
cases passed        : 122
cases failed        : 0
corpus              : examined=48  fired=0
mutations declared  : 8
reached the code    : 8
INERT (prove none)  : 0
caught by fixtures  : 8
ESCAPED             : 0
```

## Two defects these fixtures found in the hooks they test

Recorded because they are the argument for the directory existing, and because
both were invisible to a reading of the code.

1. **The `setTimeout` fail-open was inert.** A timer cannot preempt synchronous
   work, and every guard here does its analysis synchronously — so the timer
   fired only after the decision it was meant to prevent. A fixture asserting
   fail-open under a tiny budget instead got a full block. Fixed with an inline
   `budget.spent()` check before each expensive step, so the path is reached by
   code rather than by a scheduler that never gets a turn.

2. **The exhausted-budget branch was untestable by construction.** No positive
   budget a fixture can name is reliably exceeded by a sub-millisecond hook, so
   `budgetMs` now accepts a non-positive value meaning ALREADY EXHAUSTED.
   Production never sets the variable and is byte-identical either way.

## What this suite does NOT establish

- **That the guards are correctly calibrated for a real partner's prose.** The
  corpus is this package's own writing. A partner writes differently, and the
  first real false positive is evidence no fixture here can supply.
- **That the Codex and Gemini overlays behave identically.** Every case runs the
  script directly. The registrations are checked by `project_coc.mjs --check`,
  which proves they are IN SYNC, not that each CLI honours them — and Codex's
  Bash-only event surface means two of these guards are structurally partial
  there, which `hooks.manifest.json` records per hook.
- **That a guard is right to fire.** `source-absence-boundary` and
  `probe-before-claim` read prose. Both are `halt-and-report` for exactly that
  reason, and both say so where a reader will meet them.
