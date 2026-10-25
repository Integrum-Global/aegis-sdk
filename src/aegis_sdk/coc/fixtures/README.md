# Fixtures for the enforcing hooks

<!-- anchor-floor: ungrammatical (no anchor kind exists for a shipped .js guard or fixture case) -->

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

| must stay silent              | case                                                              |
| ----------------------------- | ----------------------------------------------------------------- |
| a read-only probe             | `SILENT: the probe, live, by name` · `SILENT: the probe, offline` |
| a properly-labelled inference | `SILENT: labelled as inference` · `SILENT: hedged with 'appears'` |
| an already-confirmed target   | `SILENT: an already-confirmed target does not re-prompt`          |

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

## Two design properties these fixtures pin

Both are invisible to a reading of the code, which is why they are pinned here
rather than left to a comment.

1. **The budget check is inline, not a timer.** A `setTimeout` cannot preempt
   synchronous work, and every guard here does its analysis synchronously — a
   timer would fire only after the decision it exists to bound. Each guard calls
   `budget.spent()` before every expensive step, so the fail-open path is reached
   by code rather than by a scheduler that never gets a turn.

2. **`budgetMs` accepts a non-positive value meaning ALREADY EXHAUSTED.** No
   positive budget a fixture can name is reliably exceeded by a sub-millisecond
   hook, so this is how the exhausted branch is driven. Production never sets the
   variable and is byte-identical either way.

## What this suite covers, and where its edges are

- **The corpus is this package's own writing.** It is the hardest silence case
  available here, and it is not a substitute for your own prose. As you write
  against your deployment, add your own cases to the corpus — that is the
  intended way to calibrate these guards for how your team writes.
- **Every case runs the script directly.** The Codex and Gemini registrations are
  checked by `project_coc.mjs --check`, which proves they are IN SYNC; Codex's
  Bash-only event surface makes two of these guards structurally partial there,
  and `hooks.manifest.json` records which per hook.
- **Whether a guard is right to fire is a judgment, by design.**
  `source-absence-boundary` and `probe-before-claim` read prose, which is exactly
  why both are `halt-and-report` rather than `block`, and both say so where a
  reader will meet them.
