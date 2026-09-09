#!/usr/bin/env node
// PROJECTED FILE — do not edit here.
// Source of truth: src/aegis_sdk/coc/hooks/anchor-integrity.js
// Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check
"use strict";
/**
 * anchor-integrity.js — a claim in the shipped prose keeps its grounding, and
 * this guard says how much of the corpus it actually looked at.
 *
 * @hook-event PreToolUse:Write|Edit|NotebookEdit
 * @severity   block  (grounded in a derived operation set + a real import)
 * @enforces   src/aegis_sdk/coc/anchors.json + src/aegis_sdk/handbook/anchors.json
 *             (the ratchet), and the anchoring contract in handbook/check.py
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT AN ANCHOR IS, AND WHY THE GATE EXISTS AT ALL
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The prose here makes claims about a platform its reader cannot open. So the
 * anchoring moved off source coordinates — a path nobody can follow — and onto
 * observable surface, in two kinds, both checkable from inside this package:
 *
 *     `api:POST /api/v1/trust/establish`   an operation this client performs
 *     `sdk:aegis_sdk.TrustChain`           a symbol this package exports
 *
 * `anchors.json` pins a per-chapter MINIMUM. It only rises. The failure mode
 * being fenced is deleting a claim to make a gate pass, so removal is the
 * expensive direction.
 *
 * `python -m aegis_sdk.handbook.check` already enforces all of this. What did
 * not exist is anything that fires AT THE MOMENT THE PROSE IS WRITTEN, so a
 * broken anchor lived until somebody remembered to run the checker.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * BUILT AGAINST A MEASURED DEFECT IN THE PLATFORM'S EQUIVALENT
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The platform repository's citation gate was measured on 2026-09-08 and found
 * **blind to 25% of its corpus and silent about its denominator**: a drifted
 * citation passed on a SUBSTRING MATCH, and the gate reported clean without
 * ever saying how much it had examined. Two defects, and the second is what
 * made the first survive — "0 findings" and "examined nothing" print
 * identically, so nobody could tell which one they were reading.
 *
 * Neither is ported here. Both fixes are structural, not resolutions to be
 * careful:
 *
 *   1. NO SUBSTRING MATCHING. An `api:` anchor resolves by EXACT membership of
 *      `(METHOD, normalised path)` in the set derived by AST walk from this
 *      package's own call sites. An `sdk:` anchor resolves by actually
 *      importing the module and walking the attribute chain. There is no
 *      "contains" anywhere in the decision.
 *
 *   2. THE DENOMINATOR IS ALWAYS REPORTED, AND ALWAYS INCLUDES `skipped`.
 *      Every emission carries `anchors_found`, `resolved`, `unresolved`,
 *      `skipped`, `declared_ops` and the floor state. An anchor this guard
 *      could not adjudicate is counted as SKIPPED — never as resolved, and
 *      never silently dropped. `skipped > 0` with `unresolved == 0` is NOT a
 *      clean result and does not print as one.
 *
 * ⚠ And the honest consequence, stated rather than elided: when the resolver
 * cannot run at all — no interpreter, package not installed, budget spent —
 * every anchor is SKIPPED, and this guard ALLOWS. That is the fail-open
 * non-negotiable, and it means a green from this guard is only as strong as its
 * `skipped` count. Read the count, not the absence of a message. The FLOOR arm
 * below needs no interpreter and still runs in that state, which is why the two
 * arms are separate.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY `block` IS GROUNDED HERE
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The lexical part of this guard finds the anchors, and the anchor grammar is
 * unambiguous — a backticked `api:` or `sdk:` prefix, a form nothing else in
 * this prose uses. It does not DECIDE anything. The decision comes from an AST
 * walk over the package's call sites and from a real `import`, which is process
 * state in the sense the hook-severity rule requires, and the floor
 * comparison is arithmetic against a committed file.
 *
 * A false positive is therefore not "the regex misread the prose"; it would
 * have to be "the client does not declare an operation the prose says it does",
 * which is the finding.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS STRUCTURALLY CANNOT CATCH — inherited from the anchor design itself
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   · AN ANCHOR PROVES THE CLIENT DECLARES THE OPERATION. It does not prove the
 *     deployment serves it, and it says nothing about whether the surrounding
 *     sentence is true. That gap is `probe-before-claim.js`'s question.
 *   · THE FLOOR COUNTS ANCHORS, NOT CLAIMS. A chapter can satisfy its floor and
 *     still contain an unanchored assertion. The floor stops wholesale removal;
 *     it cannot see a single ungrounded sentence.
 *   · IF THE CLIENT IS WRONG ABOUT A PATH, the anchor is wrong in exactly the
 *     same direction and resolves cleanly. The derivation is this package's
 *     BELIEF about the API, and nothing here can step outside it.
 */

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const {
  readStdin,
  parsePayload,
  allow,
  failOpen,
  startBudget,
  budgetMs,
  emit,
  repoRoot,
} = require("./lib/coc-hook.js");

const GUARDRAIL = "anchors.json — a claim in shipped prose keeps its grounding, and the floor only rises";
const BUDGET = budgetMs("COC_ANCHOR_BUDGET_MS", 8000);

/**
 * Injectable, and the production default is the literal it replaces. A
 * hardcoded interpreter makes the resolver-unavailable branch untestable BY
 * CONSTRUCTION — and that branch is the fail-open path, which is the one a
 * fixture most needs to reach.
 */
const PYTHON = process.env.COC_PYTHON || "python3";

const ANCHOR = /`(api|sdk):([^`]+)`/g;

/**
 * The gated roots, mirroring `check.py::_PROSE_ROOTS` — `[relative root, floor
 * key base, floor file]`, all relative to the repository root.
 *
 * The two roots keep SEPARATE floor files and DIFFERENT key bases, and that is
 * not an inconsistency to tidy: the coc keys retain their `coc/` prefix so a
 * key still names its root if the files are ever read together. Reproducing
 * that faithfully is the difference between this guard agreeing with the
 * checker and quietly disagreeing with it.
 */
const ROOTS = [
  {
    root: path.join("src", "aegis_sdk", "handbook"),
    base: path.join("src", "aegis_sdk", "handbook"),
    floors: path.join("src", "aegis_sdk", "handbook", "anchors.json"),
  },
  {
    root: path.join("src", "aegis_sdk", "coc"),
    base: path.join("src", "aegis_sdk"),
    floors: path.join("src", "aegis_sdk", "coc", "anchors.json"),
  },
];

/** The gated root this destination belongs to, or null. */
function gatedRoot(rel) {
  if (!rel.endsWith(".md")) return null;
  for (const r of ROOTS) {
    if (rel === r.root || rel.startsWith(r.root + path.sep)) return r;
  }
  return null;
}

/**
 * The content this file will HAVE after the tool call — not the content it has
 * now.
 *
 * Checking the on-disk file would answer a question about the past. Returns
 * null when the post-edit content cannot be constructed exactly (an `Edit`
 * whose `old_string` is not found, a file that will not read), and a null is
 * SKIPPED rather than assumed clean.
 */
function pendingContent(payload, abs) {
  const i = payload.toolInput;
  if (payload.toolName === "Write") return String(i.content || "");
  if (payload.toolName === "NotebookEdit") return null; // not gated prose
  if (payload.toolName !== "Edit") return null;

  let current;
  try {
    current = fs.readFileSync(abs, "utf8");
  } catch {
    return null;
  }
  const oldStr = String(i.old_string ?? "");
  const newStr = String(i.new_string ?? "");
  if (!oldStr || !current.includes(oldStr)) return null;
  return i.replace_all ? current.split(oldStr).join(newStr) : current.replace(oldStr, newStr);
}

/**
 * Anchors in the content, whitespace-normalised FIRST.
 *
 * Prose here wraps at ~80 columns, so an anchor split across a newline is
 * invisible to a line-oriented match. This ecosystem carries that exact scar in
 * its liability-framing scan, where five of eight banned phrases became
 * unmatchable the moment they wrapped — and `check.py` normalises for the same
 * reason. A guard that disagreed with the checker about which anchors EXIST
 * would be the worst of both.
 */
function anchorsIn(text) {
  const norm = text.replace(/\s+/g, " ");
  ANCHOR.lastIndex = 0;
  return [...norm.matchAll(ANCHOR)].map((m) => ({ kind: m[1], body: m[2].trim() }));
}

/** `{ ok, results, declared_ops }` or `{ ok:false, reason }`. Never throws. */
function resolveAnchors(root, anchors, msLeft) {
  if (!anchors.length) return { ok: true, results: [], declared_ops: null };
  const helper = path.join(root, "src", "aegis_sdk", "coc", "hooks", "lib", "resolve_anchors.py");
  if (!fs.existsSync(helper)) return { ok: false, reason: "resolver helper not present" };
  try {
    const out = execFileSync(PYTHON, [helper], {
      cwd: root,
      input: JSON.stringify({ anchors }),
      encoding: "utf8",
      timeout: Math.max(500, msLeft),
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, PYTHONPATH: path.join(root, "src") },
    });
    return JSON.parse(out);
  } catch (e) {
    return { ok: false, reason: `resolver did not run: ${(e && e.code) || (e && e.message) || "unknown"}` };
  }
}

function loadFloor(root, spec, relFromBase) {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(root, spec.floors), "utf8"));
    const floors = data && data.floors;
    if (!floors || typeof floors !== "object") return null;
    return Object.prototype.hasOwnProperty.call(floors, relFromBase) ? floors[relFromBase] : null;
  } catch {
    return null;
  }
}

function main() {
  const budget = startBudget(BUDGET);
  const payload = parsePayload(readStdin());
  if (!payload || payload.event !== "PreToolUse") return allow();
  if (!["Write", "Edit", "NotebookEdit"].includes(payload.toolName)) return allow();

  if (budget.spent()) return failOpen();

  const root = repoRoot(payload.projectDir);
  const dest = String(payload.toolInput.file_path || payload.toolInput.notebook_path || "");
  if (!dest) return allow();
  const abs = path.resolve(root, dest);
  const rel = path.relative(root, abs);
  const spec = gatedRoot(rel);
  if (!spec) return allow(); // not gated prose — this guard has no opinion

  const content = pendingContent(payload, abs);
  if (content === null) return allow(); // could not construct it exactly: SKIPPED

  const anchors = anchorsIn(content);
  const relFromBase = path.relative(path.join(root, spec.base), abs).split(path.sep).join("/");

  // ── ARM 1: the floor. Pure arithmetic; needs no interpreter, so it survives
  //    every state in which the resolver cannot run.
  const floor = loadFloor(root, spec, relFromBase);
  const belowFloor = typeof floor === "number" && anchors.length < floor;

  // ── ARM 2: resolution. Skipped wholesale when the resolver cannot run.
  const res = belowFloor ? { ok: false, reason: "not attempted — floor arm already failing" } : resolveAnchors(root, anchors, budget.left() - 500);
  budget.clear();

  const unresolved = res.ok ? res.results.filter((r) => !r.resolved) : [];
  const skipped = res.ok ? 0 : anchors.length;

  const denominator = {
    file: relFromBase,
    anchors_found: anchors.length,
    resolved: res.ok ? res.results.length - unresolved.length : 0,
    unresolved: unresolved.length,
    skipped: skipped ? `${skipped} (${res.reason})` : 0,
    declared_ops: res.ok && res.declared_ops !== null ? res.declared_ops : "not derived",
    floor: floor === null ? "none pinned" : floor,
  };

  if (belowFloor) {
    emit({
      hookEvent: "PreToolUse",
      severity: "block",
      guardrail: GUARDRAIL,
      what_happened: `${relFromBase} would carry ${anchors.length} anchor(s); its floor is ${floor}. A claim lost its grounding.`,
      why:
        "The floor only rises. The failure mode it fences is deleting a claim — or its anchor — to make a gate " +
        "pass, so removal is the direction that has to be expensive. Lowering the floor to fit the edit would be " +
        "weakening the check instead of fixing what it caught.",
      agent_must_report: [
        "Re-anchor the claim you changed: `api:METHOD /path` for an operation this client performs, or `sdk:dotted.name` for a symbol it exports",
        "Do NOT lower the floor in anchors.json to make this pass",
        "If the claim was genuinely removed rather than un-anchored, say which claim and why it no longer belongs",
      ],
      agent_must_wait: "Restore the grounding before writing.",
      user_summary: `anchor floor — ${relFromBase} ${anchors.length} < ${floor}`,
      denominator,
    });
  }

  if (unresolved.length) {
    emit({
      hookEvent: "PreToolUse",
      severity: "block",
      guardrail: GUARDRAIL,
      what_happened: `${unresolved.length} anchor(s) in ${relFromBase} do not resolve against this package.`,
      why:
        "An anchor is a promise that the reader can check the claim from inside this package. One that does not " +
        "resolve is a citation to something that is not there — which is worse than no citation, because it reads " +
        "as grounded.",
      agent_must_report: unresolved
        .slice(0, 6)
        .map((u) => `\`${u.body}\` — ${u.why}`)
        .concat([
          "Correct the anchor, or remove the claim. Do not leave an anchor that points at nothing",
          "For an `api:` anchor: the operation must be one this client actually calls — the set is derived from the package's own call sites, never hand-listed",
        ]),
      agent_must_wait: "Fix the anchors before writing.",
      user_summary: `anchor integrity — ${unresolved.length} unresolved in ${relFromBase}`,
      denominator,
    });
  }

  // Nothing fired. ⛔ If `skipped` is non-zero this is NOT a clean result — it
  // is an unmeasured one, and the guard allows because fail-open is the
  // non-negotiable, not because it looked and found nothing. The count is
  // surfaced so the difference is visible rather than inferred.
  if (skipped) {
    emit({
      hookEvent: "PreToolUse",
      severity: "advisory",
      guardrail: GUARDRAIL,
      what_happened: `${skipped} anchor(s) in ${relFromBase} were NOT checked — the resolver did not run (${res.reason}).`,
      why:
        "'No findings' and 'examined nothing' print identically. The platform's equivalent gate was measured blind " +
        "to a quarter of its corpus while reporting clean, because it never said what it had looked at. This says so.",
      agent_must_report: [
        `Run the full gate before relying on this: ${PYTHON} -m aegis_sdk.handbook.check`,
        "If the package is not installed in this environment, the anchor half of this guard is inert for the whole session",
      ],
      agent_must_wait: "",
      user_summary: `anchor integrity — ${skipped} anchor(s) unchecked (resolver unavailable)`,
      denominator,
    });
  }

  return allow();
}

try {
  main();
} catch {
  failOpen();
}
