#!/usr/bin/env node
"use strict";
/**
 * source-absence-boundary.js — you do not have the platform's source, so a
 * claim that could only have come from it is a claim you did not make honestly.
 *
 * @hook-event PreToolUse:Write|Edit|Bash
 * @severity   halt-and-report  (NOT block — argued below, and the argument is
 *             the point of the file rather than a caveat on it)
 * @enforces   coc-context.md § "You do not have the platform's source"
 *             src/aegis_sdk/coc/guardrails/client-model-fidelity.md
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS DEFENDS, AND WHY NOTHING ELSE DOES
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * `coc-context.md` states the constraint this repository is built around:
 *
 *   > You do not have the platform's source, and you will not be given it.
 *   > That is deliberate and it is the single most important fact about this
 *   > repository. … If a question can only be answered by reading the
 *   > platform's implementation, the honest answer is that it cannot be
 *   > answered from here — say so rather than inferring, and say what would
 *   > settle it.
 *
 * The platform's evidence-first guidance governs the GRAMMAR of a
 * claim: quote your evidence, label inference as inference. It is a good rule
 * and it is not this one. It assumes the source is READABLE — that a diagnostic
 * claim can, in principle, be settled by opening the file. Here it cannot.
 * The architect's position is epistemically narrower than a core developer's,
 * and the narrower position needs the STRONGER guard, not a copy of the wider
 * one.
 *
 * Until this file, that constraint was defended by one paragraph of prose.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY `halt-and-report` AND NOT `block` — SAID PLAINLY, NOT BURIED
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The hook-severity rule reserves `block` for a finding grounded in
 * process state — an env var, an exit code, a file's existence, an AST shape —
 * because a lexical match cannot see what it is matching. THIS PREDICATE IS
 * JUDGMENT-BEARING. Whether a sentence ASSERTS a platform mechanism or MENTIONS
 * one, quotes one, forbids one, or hedges one is a question about what its
 * author meant, and no regex answers it.
 *
 * ⛔ SO IT DOES NOT CARRY TEETH, AND THE TEMPTATION TO GIVE IT SOME BY DRESSING
 * A REGEX UP AS PROCESS STATE IS REFUSED HERE EXPLICITLY. ARM 1 below does
 * consult the filesystem — but it consults it to CONFIRM a lexical hit, not to
 * produce one, and a confirmation of a judgment call is still a judgment call.
 * Manufacturing a process-state veneer to justify a block would be exactly the
 * move this ecosystem's own guardrail on reading a measurement forbids.
 *
 * Its value is not that it refuses. Its value is THAT IT FIRES AT ALL: today,
 * on the SDK's signature constraint, nothing does.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY WRITE-TIME, RATHER THAN AT THE END OF THE TURN
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * A claim that stays in a session's scrollback is corrected by the next turn. A
 * claim written into a file, a commit message or an issue body OUTLIVES the
 * session, is read by someone who was not there, and carries the authority of
 * having been written down. That is where the harm is, so that is where the
 * guard sits.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE TWO ARMS, AND WHY THEY ARE SEPARATE
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ARM 1 — PLATFORM COORDINATE. A path or dotted symbol that points INTO the
 *   platform: `src/aegis/services/…`, `aegis.services.TrustChainService`,
 *   `apps/web/…`. Two conditions, and the second is what makes it precise:
 *   the coordinate names the platform (not `aegis_sdk`), AND it does not
 *   resolve in this repository. `coc-context.md` bans these by name: "do not
 *   cite paths into it — a path the reader cannot open is useless to them and
 *   discloses the shape of protected IP." Near-zero false-positive rate,
 *   because the coordinate either exists here or it does not.
 *
 * ARM 2 — IMPLEMENTATION LOCUTION. Prose that names an implementation detail
 *   nobody in this position can see: "under the hood", "internally", "the
 *   handler", "the middleware", "the SQL it runs", "is implemented as". The
 *   deliberate NARROWNESS here is a design decision, not an oversight. An
 *   earlier draft matched generic mechanism verbs ("the server validates…",
 *   "the route enforces…") and fired on the SHIPPED GUARDRAILS THEMSELVES —
 *   `credential-reachability.md` legitimately states a mechanism it sources
 *   from the handbook. A guard that reds the corpus it ships beside is not
 *   strict, it is broken, and it would be switched off in a day.
 *
 *   The discriminator is therefore not "does this describe behaviour" — the
 *   handbook describes behaviour, and that is its job — but "does this describe
 *   behaviour in the vocabulary of someone who read the code".
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * CALIBRATION, MEASURED RATHER THAN ASSERTED
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The 15 shipped artifacts under `src/aegis_sdk/coc/` are this guard's NEGATIVE
 * CONTROL CORPUS. They are prose about platform behaviour, written from exactly
 * this position, by an author who did not have the source — i.e. they are the
 * hardest possible silence case. `fixtures/source-absence-boundary/` runs the
 * guard over every one of them and FAILS if any fires. A firing there is not a
 * finding about the corpus; it is a finding about this file.
 *
 * ⚠ WHAT THAT CALIBRATION DOES NOT ESTABLISH: that the guard CATCHES anything.
 * A predicate that never fires passes a corpus test perfectly. The positive
 * fixtures and the mutation control are the other half, and neither is optional.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS STRUCTURALLY CANNOT CATCH — stated, because a guard that oversells
 * its reach is worse than no guard
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   * A false claim in ORDINARY vocabulary. "Budgets are checked before
 *     dispatch" is a source-derived claim in plain English and is invisible
 *     here. ARM 2 catches the TELL, not the claim.
 *   * A claim the agent only SAYS. Nothing routes assistant prose through a
 *     tool call, so a claim that never lands in a file is out of reach.
 *   * Whether the claim is TRUE. This guard has no more access to the platform
 *     than its reader does. It asks how a claim was obtained, never whether it
 *     is correct — and a correct claim obtained by inventing an implementation
 *     is still the failure being fenced.
 */

const fs = require("node:fs");
const path = require("node:path");
const {
  readStdin,
  parsePayload,
  allow,
  failOpen,
  startBudget,
  budgetMs,
  emit,
  repoRoot,
  splitSegments,
} = require("./lib/coc-hook.js");

const GUARDRAIL = "coc-context.md § the platform's source is not here";
const BUDGET = budgetMs("COC_SOURCE_ABSENCE_BUDGET_MS", 4000);

/**
 * A coordinate INTO the platform. `aegis_sdk` is deliberately excluded by the
 * negative lookahead rather than by a later filter: `aegis_sdk/modules/auth.py`
 * is a path in THIS repository and citing it is the correct thing to do.
 */
const PLATFORM_PATH = /(?:^|[\s(`'"[])((?:src\/)?aegis(?!_sdk)\/[\w./-]+\.(?:py|ts|tsx|rs|sql|json))/g;
const PLATFORM_SYMBOL = /(?:^|[\s(`'"[])(aegis(?!_sdk)\.[a-z_][\w.]*\.[A-Za-z_]\w*)/g;
const PLATFORM_TREE = /(?:^|[\s(`'"[])(apps\/web\/[\w./-]+\.(?:ts|tsx|js|jsx))/g;

/**
 * The vocabulary of someone who read the code. Each entry names a thing that is
 * only visible from inside an implementation — not a behaviour a handbook could
 * legitimately describe from the outside.
 */
const LOCUTIONS = [
  /\bunder the hood\b/i,
  /\bbehind the scenes\b/i,
  /\binternally,? (?:it|the|they|aegis)\b/i,
  /\bthe (?:implementation|codebase|source code|server code|backend code)\b/i,
  /\bin the (?:platform|server|backend)(?:'s)? (?:code|source|implementation)\b/i,
  /\bthe (?:request )?(?:handler|middleware|interceptor|seriali[sz]er|ORM|migration)\b/i,
  /\bthe (?:SQL|query) (?:it|the (?:server|platform|route|endpoint)) (?:runs|issues|executes)\b/i,
  /\bis implemented (?:as|by|in|using|with)\b/i,
  /\b(?:it|the (?:server|platform|route|endpoint|API)) (?:delegates|dispatches) to\b/i,
  /\bthe (?:service|repository|controller|model) (?:layer|class)\b/i,
  /\breading the (?:platform|server|backend)(?:'s)? (?:source|implementation|code)\b/i,
];

/**
 * Markers that make a sentence honest about where it came from. Any one of them
 * SILENCES arm 2 for that sentence.
 *
 * Three families, and all three are load-bearing:
 *   hedges       — the claim is labelled as inference, which is what
 *                  `coc-context.md` habit 3 asks for.
 *   attribution  — the claim is sourced to something the reader HAS: the
 *                  handbook, the client, the probe, an observed response.
 *   prohibition  — the text is forbidding or quoting the locution rather than
 *                  using it. Without this family, every guardrail that teaches
 *                  the distinction trips the guard that enforces it.
 */
const HONEST = [
  // hedges
  /\b(?:appears?|seems?|suggests?|presumably|probably|likely|perhaps|may|might)\b/i,
  /\b(?:I )?(?:infer|inferred|inference|hypothesi[sz]e|hypothesis|assume|assuming)\b/i,
  /\bunverified\b/i,
  /\bcannot be (?:answered|determined|established|settled|verified)\b/i,
  /\bwould settle\b/i,
  /\bnot (?:visible|knowable|observable) from here\b/i,
  // attribution to something the reader holds
  /\bthe handbook\b/i,
  /\bthe (?:client|SDK|package|probe|checker|guard|projector)\b/i,
  /\bthis (?:package|client|repository|repo)\b/i,
  /\baccording to\b/i,
  /\bobserved\b/i,
  /\bthe (?:deployment|response|route) returned\b/i,
  // prohibition / quotation — DIRECTIVE forms only.
  //
  // An earlier draft had `never` and `refus\w+` here and both were REMOVED
  // after a fixture caught what they cost: they are BEHAVIOURAL verbs, not
  // prohibition markers, so "the middleware refuses the request before RBAC"
  // and "the handler never caches" — the exact invented-implementation claims
  // this arm exists to catch — silenced themselves. A marker set that admits a
  // verb the subject can perform is not a marker set.
  /\b(?:do not|don't|must not|shall not)\b/i,
  /\bnever (?:claim|assert|state|write|say|cite|infer|guess)\b/i,
  /\b(?:forbidden|banned|prohibit\w*)\b/i,
  /\b(?:BLOCKED|DO NOT|MUST NOT)\b/,
];

/** Text that reaches a durable destination, or null when there is none. */
function durableText(payload) {
  const t = payload.toolName;
  const i = payload.toolInput;
  if (t === "Write") return { text: String(i.content || ""), dest: String(i.file_path || "") };
  if (t === "Edit") return { text: String(i.new_string || ""), dest: String(i.file_path || "") };
  if (t === "NotebookEdit") return { text: String(i.new_source || ""), dest: String(i.notebook_path || "") };
  if (t !== "Bash") return null;

  // A commit message, an issue comment, a PR body: durable, and authored in a
  // shell string. Only the QUOTED payload is read — the surrounding flags are
  // not prose and matching them would be matching our own tooling.
  const command = String(i.command || "");
  const segments = splitSegments(command);
  const bodies = [];
  for (const seg of segments) {
    if (!/^(?:git|gh)\b/.test(seg)) continue;
    if (!/\b(?:commit|comment|create|edit|close|reopen)\b/.test(seg)) continue;
    for (const m of seg.matchAll(/(?:-m|--body|--body-text|--message)[\s=]+("(?:[^"\\]|\\.)*"|'[^']*')/g)) {
      bodies.push(m[1].slice(1, -1));
    }
  }
  return bodies.length ? { text: bodies.join("\n\n"), dest: "<git/gh message>" } : null;
}

/**
 * Strip fenced code blocks.
 *
 * A `# DO NOT` example inside a fence is TEACHING the failure, and firing on it
 * would mean the guard reds every file that documents what it forbids. The
 * fences are removed rather than skipped-over so that character offsets do not
 * have to be tracked; nothing downstream needs them.
 */
function stripFences(text) {
  return text.replace(/```[\s\S]*?```/g, " ").replace(/^ {4,}\S.*$/gm, " ");
}

/** Sentences, whitespace-normalised first because prose here wraps at ~80 cols. */
function sentences(text) {
  return stripFences(text)
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?:])\s+(?=[A-Z`*_-]|$)/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** ARM 1: coordinates that name the platform and do not resolve here. */
function platformCoordinates(text, root) {
  const hits = new Map();
  const stripped = stripFences(text);
  for (const re of [PLATFORM_PATH, PLATFORM_TREE]) {
    re.lastIndex = 0;
    for (const m of stripped.matchAll(re)) {
      const coord = m[1];
      // The confirming half. A coordinate that RESOLVES here is a citation into
      // this repository, however platform-shaped it looks — say nothing.
      if (fs.existsSync(path.join(root, coord))) continue;
      hits.set(coord, "path");
    }
  }
  PLATFORM_SYMBOL.lastIndex = 0;
  for (const m of stripped.matchAll(PLATFORM_SYMBOL)) hits.set(m[1], "symbol");
  return [...hits.entries()].map(([coord, kind]) => ({ coord, kind }));
}

/** ARM 2: implementation locutions in sentences that never say where they came from. */
function unhedgedLocutions(text) {
  const out = [];
  for (const s of sentences(text)) {
    if (HONEST.some((re) => re.test(s))) continue;
    for (const re of LOCUTIONS) {
      const m = s.match(re);
      if (m) {
        out.push({ phrase: m[0], sentence: s.length > 180 ? s.slice(0, 177) + "…" : s });
        break;
      }
    }
  }
  return out;
}

function main() {
  const budget = startBudget(BUDGET);
  const payload = parsePayload(readStdin());
  if (!payload || payload.event !== "PreToolUse") return allow();

  if (budget.spent()) return failOpen();

  const target = durableText(payload);
  if (!target || !target.text.trim()) return allow();

  const root = repoRoot(payload.projectDir);

  // NAMING-TO-PROHIBIT CARVE-OUT, and it is exactly one directory wide.
  //
  // This file, and the fixtures that prove it fires, MUST contain the
  // vocabulary they detect. Nothing else is exempt — in particular the
  // guardrails are NOT, because a guardrail asserting an invented platform
  // mechanism is precisely the failure being fenced, and exempting the prose
  // most likely to make that claim would hollow the guard out.
  const rel = path.relative(root, path.resolve(root, target.dest));
  if (rel.startsWith(path.join("src", "aegis_sdk", "coc", "hooks"))) return allow();
  if (rel.startsWith(path.join("src", "aegis_sdk", "coc", "fixtures"))) return allow();

  // THE HANDBOOK IS A SOURCE, NOT AN OUTPUT — arm 2 does not apply to it, and
  // this scoping was FORCED BY MEASUREMENT rather than anticipated.
  //
  // Run over the 48 shipped prose files, this guard fired once: on
  // `handbook/04-the-api-surface/01-calling-the-api.md`, at "**The service
  // layer** — a tenant guard applied per call". That sentence is the handbook
  // doing its job. The handbook is the sanctioned record of how the platform
  // BEHAVES, written by someone who had the access this repository's reader
  // does not, and describing internal layering is exactly what the architect
  // clones it for.
  //
  // It is also already governed, and governed HARDER: every claim there must
  // carry an `api:` or `sdk:` anchor that resolves against this package, under
  // a per-chapter floor that only rises (`anchors.json`, and the sibling guard
  // `anchor-integrity.js`). Layering a text heuristic on top of a resolving
  // gate adds no coverage and subtracts credibility — a guard that reds the
  // corpus it ships beside gets switched off, and then it is not defending the
  // architect's output either.
  //
  // ⛔ ARM 1 IS NOT SCOPED OUT, and the asymmetry is deliberate. The handbook's
  // whole anchoring design moved OFF source coordinates and onto observable
  // surface precisely because a coordinate into the platform is unopenable by
  // its reader. A `src/aegis/…` path in a handbook chapter is a defect there
  // for the same reason it is one anywhere else.
  const inHandbook = rel.startsWith(path.join("src", "aegis_sdk", "handbook"));

  const coords = platformCoordinates(target.text, root);
  const locutions = inHandbook ? [] : unhedgedLocutions(target.text);
  budget.clear();

  // THE DENOMINATOR IS REPORTED WHETHER OR NOT ANYTHING FIRED, and `arm_2`
  // names its own state rather than reporting a zero. "0 locutions" and "arm 2
  // did not run against this destination" are the same number and opposite
  // facts, and collapsing them is the defect this ecosystem measured in its own
  // citation gate — blind to a quarter of its corpus while reporting clean.
  const denominator = {
    sentences: sentences(target.text).length,
    coordinates_flagged: coords.length,
    arm_2: inHandbook ? "SKIPPED (handbook — anchor-gated instead)" : `${locutions.length} flagged`,
  };

  if (!coords.length && !locutions.length) return allow();

  const report = [];
  if (coords.length) {
    report.push(
      `Quote each platform coordinate and say how it was obtained: ${coords
        .map((c) => `${c.coord} (${c.kind})`)
        .join(", ")}`
    );
    report.push(
      "Remove it, or replace it with something the reader can open — a handbook chapter by title, an `api:`/`sdk:` anchor, or a probe result"
    );
  }
  if (locutions.length) {
    for (const l of locutions.slice(0, 4)) {
      report.push(`Implementation locution "${l.phrase}" in: ${l.sentence}`);
    }
    report.push(
      "For each: state what you actually observed, and what would settle it — or say it cannot be answered from here"
    );
  }
  report.push(
    "If the claim is sourced from the shipped handbook or a probe run, say so in the sentence; that is what makes it checkable by the reader"
  );

  emit({
    hookEvent: "PreToolUse",
    severity: "halt-and-report",
    guardrail: GUARDRAIL,
    what_happened:
      `A durable write to ${target.dest || "a file"} carries ` +
      `${coords.length} platform coordinate(s) and ${locutions.length} unhedged implementation locution(s).`,
    why:
      "This repository does not contain the platform's source. A claim that could only have been " +
      "obtained by reading it was not obtained — and a coordinate the reader cannot open is useless " +
      "to them and discloses the shape of protected IP (coc-context.md § What is out of scope here).",
    agent_must_report: report,
    agent_must_wait:
      "Rewrite the claim, or state that it cannot be answered from here and what would settle it. This guard reads text and can be wrong — if it is, say why and proceed.",
    user_summary: "source-absence boundary — a claim reaching for the platform's implementation",
    denominator,
  });
}

try {
  main();
} catch {
  // Every unanticipated failure is an envelope failure, and an envelope failure
  // must not wedge a partner's session. Silence here means UNMEASURED, never
  // clean — which is why this catch does nothing except get out of the way.
  failOpen();
}
