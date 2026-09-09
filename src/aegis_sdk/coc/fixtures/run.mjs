#!/usr/bin/env node
/**
 * run.mjs — the fixture harness for the enforcing hooks.
 *
 *     node src/aegis_sdk/coc/fixtures/run.mjs             # every case
 *     node src/aegis_sdk/coc/fixtures/run.mjs --only <hook>
 *     node src/aegis_sdk/coc/fixtures/run.mjs --mutations # the controls only
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THIS REPOSITORY HAD NO FIXTURE CONVENTION. THIS ESTABLISHES ONE.
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * Stated rather than assumed, because "there is a convention and I followed it"
 * and "I invented one" are different claims and only one of them is true here.
 * The shape is deliberately the one the platform repository arrived at after
 * paying for the alternatives:
 *
 *   REAL SCRIPTS, REAL PROCESSES.  Each case spawns the actual hook file with
 *     an actual JSON payload on stdin and reads the actual exit code. Nothing
 *     is imported and nothing is stubbed. A mocked hook tests the mock — and
 *     these guards' predicates ARE their process interactions (an environment
 *     value, a file on disk, a subprocess that may not exist), so a mock would
 *     be testing the one part that cannot be wrong.
 *
 *   BOTH POLARITIES, ALWAYS.  A guard that always blocks passes every "it
 *     caught the bad thing" test ever written. The SILENCE cases are pinned as
 *     hard as the firing ones, and for these guards they are pinned HARDER:
 *     three of them are named in the brief as the false positives that would
 *     make a partner switch the whole set off.
 *
 *   MUTATION CONTROLS, IN A SCRATCH COPY.  `--mutations` breaks each guard in a
 *     COPY of the tree and requires the suite to RED. Never in place: mutating
 *     a shared checkout is how a fleet manufactures false findings, and this
 *     harness must not be able to leave the repository damaged.
 *
 *   ⛔ AND A NON-REDDENING MUTATION IS NOT A VERDICT. If a mutation does not
 *     red the suite, that leaves TWO live hypotheses — a vacuous test, or an
 *     INERT mutation that never reached the code under test. This harness
 *     therefore records `reached` for every mutation: whether the mutated text
 *     was actually present to be changed. A mutation that changed nothing is
 *     reported as INERT, never as "proven vacuous".
 *
 * EXIT CODES ASSERTED: 0 allow · 2 PreToolUse refusal (block or halt-and-report).
 * `severity` is asserted separately from the emitted JSON, because block and
 * halt-and-report share an exit code and the distinction is the whole of
 * the hook-severity rule: `block` is reserved for process state.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { HOOKS } from "./harness.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

const argv = process.argv.slice(2);
const ONLY = argv.includes("--only") ? argv[argv.indexOf("--only") + 1] : null;
const MUTATIONS_ONLY = argv.includes("--mutations");

// ───────────────────────────── the runner ────────────────────────────────────

const CASE_FILES = fs
  .readdirSync(path.join(HERE, "cases"))
  .filter((f) => f.endsWith(".mjs"))
  .sort();

async function runAll(hooksDir, only = ONLY) {
  let pass = 0;
  const failures = [];
  for (const f of CASE_FILES) {
    const hook = f.replace(/\.mjs$/, "");
    if (only && only !== hook) continue;
    const mod = await import(path.join(HERE, "cases", f));
    for (const c of mod.cases) {
      let got;
      try {
        got = c.run({ hooksDir });
      } catch (e) {
        failures.push(`${hook} / ${c.name}: THREW ${e.message}`);
        continue;
      }
      const wantCode = c.expect.code;
      const okCode = got.code === wantCode;
      const okSeverity = c.expect.severity === undefined || got.severity === c.expect.severity;
      if (okCode && okSeverity) {
        pass++;
      } else {
        failures.push(
          `${hook} / ${c.name}: want code=${wantCode}` +
            (c.expect.severity !== undefined ? ` severity=${c.expect.severity}` : "") +
            ` — got code=${got.code} severity=${got.severity}`
        );
      }
    }
  }
  return { pass, failures };
}

// ───────────────────────────── mutation controls ─────────────────────────────

/**
 * Break one guard in a COPY of the hooks tree and require the suite to red.
 *
 * `find` is asserted PRESENT before the replacement, and that assertion is what
 * separates the two hypotheses a green mutation leaves open. Without it, a typo
 * in `find` produces a mutation that changes nothing, the suite stays green,
 * and the harness reports the guard vacuous — a false verdict against a working
 * control, which is worse than no mutation testing at all.
 */
const MUTATIONS = [
  {
    hook: "source-absence-boundary",
    what: "remove the platform-path arm",
    find: "for (const re of [PLATFORM_PATH, PLATFORM_TREE]) {",
    with: "for (const re of []) {",
  },
  {
    hook: "source-absence-boundary",
    what: "make every sentence look honest, so arm 2 never fires",
    find: "if (HONEST.some((re) => re.test(s))) continue;",
    with: "if (true) continue;",
  },
  {
    hook: "deployment-blast-radius",
    what: "treat every host as local, so no mutation is ever gated",
    find: "if (isLocalOrReserved(target.host)) continue;",
    with: "if (true) continue;",
  },
  {
    hook: "deployment-blast-radius",
    what: "accept any receipt regardless of host",
    find: ".filter((r) => r.host === host)",
    with: ".filter(() => true)",
  },
  {
    hook: "client-credential-containment",
    what: "drop the length floor, so short values match prose",
    find: "if (v.length < MIN_SECRET_LEN) continue;",
    with: "if (false) continue;",
  },
  {
    hook: "client-credential-containment",
    what: "permit every destination",
    find: "if (!leak) return allow();",
    with: "if (true) return allow();",
  },
  {
    hook: "probe-before-claim",
    what: "let an UNDETERMINED run satisfy the obligation",
    find: 'const answering = receipts.filter((r) => r.verdict === "answered" || r.verdict === "answered-untargeted");',
    with: "const answering = receipts;",
  },
  {
    hook: "anchor-integrity",
    what: "stop enforcing the floor",
    find: "const belowFloor = typeof floor === \"number\" && anchors.length < floor;",
    with: "const belowFloor = false;",
  },
];

function mutate() {
  let inert = 0;
  let caught = 0;
  const escaped = [];
  const results = [];

  for (const m of MUTATIONS) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "coc-mutate-"));
    fs.cpSync(HOOKS, path.join(tmp, "hooks"), { recursive: true });
    const target = path.join(tmp, "hooks", `${m.hook}.js`);
    const before = fs.readFileSync(target, "utf8");

    // REACHED? The mutation must have something to change. This is the check
    // that stops an inert mutation being read as a vacuity verdict.
    const reached = before.includes(m.find);
    if (!reached) {
      inert++;
      results.push({ ...m, reached: false, verdict: "INERT — the text to mutate was not found; this proves NOTHING" });
      fs.rmSync(tmp, { recursive: true, force: true });
      continue;
    }
    fs.writeFileSync(target, before.split(m.find).join(m.with));
    results.push({ ...m, reached: true, tmp, target });
  }
  return { results, inert, caught, escaped };
}

async function runMutations() {
  const { results, inert } = mutate();
  let caught = 0;
  const escaped = [];
  for (const r of results) {
    if (!r.reached) continue;
    // SCOPED TO THE MUTATED HOOK'S OWN CASES, and that is evidence rather than
    // speed. Run against the whole suite, a mutation counts as "caught" when
    // ANY case reds — including one belonging to a different guard, which would
    // establish nothing about the mutation. The scope makes the verdict mean
    // what it says: THIS guard's fixtures noticed THIS guard being broken.
    const { failures } = await runAll(path.join(r.tmp, "hooks"), r.hook);
    if (failures.length) {
      caught++;
      r.verdict = `CAUGHT — ${failures.length} case(s) red`;
    } else {
      escaped.push(r);
      r.verdict = "ESCAPED — mutation reached the code and the suite stayed green";
    }
    fs.rmSync(r.tmp, { recursive: true, force: true });
  }
  console.log("\nMUTATION CONTROLS");
  for (const r of results) console.log(`  ${r.hook}: ${r.what}\n    ${r.verdict}`);
  console.log(
    `\n  mutations declared : ${MUTATIONS.length}\n` +
      `  reached the code   : ${MUTATIONS.length - inert}\n` +
      `  INERT (prove none) : ${inert}\n` +
      `  caught by fixtures : ${caught}\n` +
      `  ESCAPED            : ${escaped.length}`
  );
  return inert === 0 && escaped.length === 0;
}

// ───────────────────────────── main ──────────────────────────────────────────

const { pass, failures } = MUTATIONS_ONLY ? { pass: 0, failures: [] } : await runAll(HOOKS);
if (!MUTATIONS_ONLY) {
  console.log(`\nFIXTURES\n  cases passed : ${pass}\n  cases failed : ${failures.length}`);
  for (const f of failures) console.log(`    FAIL  ${f}`);
}

let mutationsOk = true;
if (MUTATIONS_ONLY || (!ONLY && !failures.length)) mutationsOk = await runMutations();

process.exit(failures.length === 0 && mutationsOk ? 0 : 1);
