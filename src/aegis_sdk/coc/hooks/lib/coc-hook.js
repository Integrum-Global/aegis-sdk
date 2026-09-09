"use strict";
/**
 * coc-hook.js — the minimal hook runtime the Aegis SDK's guards share.
 *
 * WHY THIS EXISTS AT ALL, WHEN THE PLATFORM REPOSITORY ALREADY HAS ONE.
 *
 * The platform repository's hooks import `.claude/hooks/lib/runtime.js` and
 * `.claude/hooks/lib/instruct-and-wait.js`. Neither ships to a delivery
 * partner. This repository is what a partner CLONES — it carries the client,
 * the handbook and the working material, and nothing else. A hook here that
 * `require`d the platform's library would throw `MODULE_NOT_FOUND` in every
 * session it was written for: a guard that does not exist, wearing the file
 * name of one.
 *
 * So this is self-contained ON PURPOSE. It is deliberately SMALLER than the
 * platform's library rather than a copy of it — it carries the emit shape and
 * the payload normalisation, and nothing that would have to be kept in
 * agreement with a file the partner does not have.
 *
 * THE EMIT SHAPE IS NOT DECORATION.
 *
 * A bare `process.exit(2)` shows the operator "Execution stopped by hook" and
 * shows the agent nothing. The fields below convert a silent flow-stop into a
 * handoff both of them can act on. Every halting branch in every guard here
 * goes through `emit()`; there is exactly one legitimate raw exit — the timeout
 * fallback — and `failOpen()` owns it.
 *
 * THREE SEVERITIES, AND THE MIDDLE ONE IS NOT A CONSOLATION PRIZE.
 *
 *   block             the guard read PROCESS STATE — an environment value, a
 *                     file's existence, a derived symbol table, an exit code —
 *                     and the state is unambiguous. The agent cannot argue with
 *                     it, because it is not an opinion.
 *   halt-and-report   the guard matched TEXT. Text is judgment-bearing: shell
 *                     expansion is invisible before execution, and prose means
 *                     what its author meant. The turn stops and the agent
 *                     reports; the work is not refused.
 *   advisory          surfaced; nothing stops.
 *
 * A guard that reaches for `block` on a lexical match is the failure this
 * distinction exists to prevent. A guard that defaults to `advisory` because it
 * is easier is the failure the epic that commissioned these exists to prevent.
 * Both are wrong, and they are wrong in opposite directions.
 */

const fs = require("node:fs");
const path = require("node:path");

/** The one directory these guards read and write receipts in. */
const AUTHZ_DIR = ".coc-authz";

/**
 * Read the whole of stdin, synchronously, tolerating an empty pipe.
 *
 * Synchronous on purpose: a hook has a hard timeout above it, and an async read
 * that never resolves is indistinguishable from a hook that decided to allow.
 */
function readStdin() {
  try {
    return fs.readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

const CANONICAL_EVENT = {
  pretooluse: "PreToolUse",
  posttooluse: "PostToolUse",
  beforetool: "PreToolUse",
  aftertool: "PostToolUse",
  sessionstart: "SessionStart",
  sessionend: "Stop",
  stop: "Stop",
  userpromptsubmit: "UserPromptSubmit",
};

/**
 * Normalise a hook payload from any of the three CLIs into one shape.
 *
 * Gemini renames the events (`BeforeTool` / `AfterTool`), Codex snake-cases
 * them, CC uses PascalCase. Downstream branching compares canonical names, so
 * the translation happens once here rather than in five guards.
 *
 * Returns `null` on anything unparseable. A guard that cannot read its input
 * has not observed anything, and MUST fall through to silence — never to a
 * refusal, and never to a claim that it checked.
 */
function parsePayload(raw) {
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const rawEvent = String(
    data.hook_event_name || data.hookEventName || data.event || ""
  ).replace(/[_-]/g, "");
  const event = CANONICAL_EVENT[rawEvent.toLowerCase()] || null;
  const toolInput = data.tool_input || data.toolInput || {};
  return {
    runtime: process.env.COC_RUNTIME || "cc",
    event,
    toolName: data.tool_name || data.toolName || "",
    toolInput: toolInput && typeof toolInput === "object" ? toolInput : {},
    toolResponse: data.tool_response || data.toolResponse || null,
    cwd: data.cwd || data.workspace || "",
    projectDir:
      process.env.CLAUDE_PROJECT_DIR ||
      process.env.GEMINI_PROJECT_DIR ||
      data.cwd ||
      process.cwd(),
  };
}

/** Allow, saying nothing. The overwhelmingly common path. */
function allow() {
  process.stdout.write(JSON.stringify({ continue: true }) + "\n");
  process.exit(0);
}

/**
 * The timeout / unreadable-state exit.
 *
 * FAIL OPEN IS A NON-NEGOTIABLE HERE, AND THE REASON IS NOT POLITENESS. These
 * guards run in a delivery partner's session, on a machine nobody here can
 * reach, against a client deadline. A guard that wedges that session is
 * disabled within a day, and a disabled guard protects nothing — so every
 * envelope failure (no python, no git, malformed stdin, budget spent) lands
 * here, silently.
 *
 * ⛔ WHAT THIS MUST NOT BECOME: "the check could not run, therefore clean."
 * Silence here means UNMEASURED. Any guard that has something to say about
 * being unable to measure says it through `emit()` at `halt-and-report` BEFORE
 * falling back to this.
 */
function failOpen() {
  try {
    process.stdout.write(JSON.stringify({ continue: true }) + "\n");
  } catch {
    /* a closed stdout is still an allow */
  }
  process.exit(0);
}

/**
 * Install the timeout fallback and return a budget reader.
 *
 * PER-INVOCATION, NEVER MODULE-LOAD. A budget anchored at module load can be
 * spent before the guard's own evaluation is entered, producing a guard that
 * fails open for reasons that have nothing to do with its check — a defect this
 * ecosystem has already paid for once.
 */
function startBudget(ms) {
  const started = Date.now();
  const timer = setTimeout(failOpen, ms);
  if (typeof timer.unref === "function") timer.unref();
  const left = () => ms - (Date.now() - started);
  return {
    left,
    /**
     * ⛔ THE INLINE CHECK IS THE REAL PROTECTION. THE TIMER IS THE BACKSTOP.
     *
     * A `setTimeout` CANNOT PREEMPT SYNCHRONOUS WORK. Every guard here does its
     * analysis synchronously — that is deliberate, because an async read that
     * never resolves is indistinguishable from a hook that decided to allow —
     * and the event loop does not turn until that analysis is finished. So the
     * timer fires only AFTER the decision it was supposed to prevent.
     *
     * This was not reasoned out in advance. A fixture asserting fail-open under
     * a 1ms budget FAILED, with the guard returning a full block, and that is
     * what exposed it. The timer had been carried as though it were the
     * protection while being, for this shape of hook, inert — the exact class
     * of defect a guard that only ever ran its happy path can hide forever.
     *
     * `spent()` is therefore called explicitly before every expensive step, so
     * the fail-open path is REACHED BY CODE rather than by a scheduler that
     * never gets a turn — and so a fixture can drive it at all. The timer stays,
     * because a future async branch would need it and because it costs nothing.
     */
    spent: () => left() <= 0,
    clear: () => clearTimeout(timer),
  };
}

/**
 * An injectable budget. The production default is the literal it replaces, so
 * behaviour is byte-identical until the variable is set — and a fixture finally
 * CAN reach the timeout branch, which a hardcoded number makes untestable by
 * construction.
 */
function budgetMs(envVar, fallback) {
  const raw = process.env[envVar];
  if (raw === undefined) return fallback;
  const n = Number(raw);
  // ZERO AND NEGATIVE ARE ACCEPTED, AND THAT IS THE POINT RATHER THAN A LAPSE.
  //
  // These guards do their analysis synchronously in well under a millisecond,
  // so no positive budget a fixture can name is reliably exceeded — the first
  // attempt used 1ms and the guard finished, blocked, and failed the fixture
  // that was trying to prove it fails OPEN. A budget that cannot be exhausted
  // on demand makes the fail-open path unreachable by any test, which is the
  // same "untestable by construction" trap a hardcoded value creates.
  //
  // So a non-positive value means ALREADY EXHAUSTED. Production never sets this
  // variable and is byte-identical either way; a fixture sets it to -1 and the
  // branch executes.
  return Number.isFinite(n) ? n : fallback;
}

const SEVERITIES = new Set(["block", "halt-and-report", "advisory"]);

/**
 * The one halting output shape.
 *
 * `guardrail` is REQUIRED and is not a formality: every guard here enforces a
 * file under `src/aegis_sdk/coc/guardrails/`, and printing that pairing is what
 * lets the reader go and read the obligation rather than argue with the guard.
 * A guard that cannot name the obligation it enforces has not established that
 * it enforces one.
 *
 * `denominator` is required of every guard that COUNTED something, for the
 * reason `probe.py` states at length and the platform's citation gate learned
 * the hard way: "0 findings" and "examined nothing" print identically.
 */
function emit(finding) {
  const {
    hookEvent = "PreToolUse",
    severity,
    guardrail,
    what_happened,
    why,
    agent_must_report = [],
    agent_must_wait = "",
    user_summary,
    denominator = null,
  } = finding;

  if (!SEVERITIES.has(severity)) throw new Error(`bad severity: ${severity}`);
  if (!guardrail) throw new Error("emit() requires the guardrail it enforces");
  if (!agent_must_report.length) throw new Error("emit() requires agent_must_report");

  const body = {
    severity,
    guardrail,
    what_happened,
    why,
    agent_must_report,
    agent_must_wait,
    user_summary,
  };
  if (denominator) body.denominator = denominator;

  const lines = [
    `${severity === "advisory" ? "⚠" : "⛔"} ${severity.toUpperCase()}  ${user_summary}`,
    `   guardrail: ${guardrail}`,
    `   ${what_happened}`,
    `   why: ${why}`,
  ];
  if (denominator) {
    lines.push(
      "   examined: " +
        Object.entries(denominator)
          .map(([k, v]) => `${k}=${v}`)
          .join(" · ")
    );
  }
  for (const r of agent_must_report) lines.push(`   → ${r}`);
  if (agent_must_wait) lines.push(`   ${agent_must_wait}`);
  process.stderr.write(lines.join("\n") + "\n");

  if (severity === "advisory") {
    process.stdout.write(JSON.stringify({ continue: true, coc: body }) + "\n");
    process.exit(0);
  }

  process.stdout.write(JSON.stringify({ continue: false, coc: body }) + "\n");
  process.exit(hookEvent === "PreToolUse" ? 2 : 0);
}

/** Repo root: the nearest ancestor holding `src/aegis_sdk/`, else the start. */
function repoRoot(start) {
  let dir = path.resolve(start || process.cwd());
  for (let i = 0; i < 24; i++) {
    if (fs.existsSync(path.join(dir, "src", "aegis_sdk"))) return dir;
    const up = path.dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  return path.resolve(start || process.cwd());
}

/**
 * Unexpired receipts of one kind, newest first.
 *
 * Every rejection below is a REJECTION, never a default. A receipt with no
 * expiry is not "a receipt with a field unset"; it is a standing exemption
 * wearing a receipt's file name, and defaulting the field would hand back
 * exactly what the expiry exists to prevent.
 */
function readReceipts(root, kind) {
  const dir = path.join(root, AUTHZ_DIR, kind);
  let names;
  try {
    names = fs.readdirSync(dir);
  } catch {
    return [];
  }
  const now = Date.now();
  const out = [];
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    let rec;
    try {
      rec = JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
    } catch {
      continue;
    }
    const expires = Date.parse(rec.expires_at);
    if (!Number.isFinite(expires) || expires <= now) continue;
    if (typeof rec.reason !== "string" || !rec.reason.trim()) continue;
    out.push({ ...rec, _file: path.join(dir, name), _expires: expires });
  }
  return out.sort((a, b) => b._expires - a._expires);
}

/** Write a receipt. Returns its path. The TTL cap is the caller's decision. */
function writeReceipt(root, kind, record, ttlMs) {
  const dir = path.join(root, AUTHZ_DIR, kind);
  fs.mkdirSync(dir, { recursive: true });
  const now = Date.now();
  const file = path.join(
    dir,
    `${new Date(now).toISOString().replace(/[:.]/g, "-")}-${kind}.json`
  );
  fs.writeFileSync(
    file,
    JSON.stringify(
      {
        ...record,
        recorded_at: new Date(now).toISOString(),
        expires_at: new Date(now + ttlMs).toISOString(),
      },
      null,
      2
    ) + "\n"
  );
  return file;
}

/**
 * Split a shell command into segments a verb could lead.
 *
 * Compound-statement blindness is a MEASURED class in this ecosystem: a
 * detector that splits on `;` and `&&` alone goes silent on the same command
 * wrapped in `( … )`, `{ …; }`, `if … then … fi` or a loop body — 15 of 15
 * destructive commands were silenced that way in one measurement, and a pair of
 * parentheses defeated every destructive guard in that repository. The wrapper
 * keywords are stripped so a segment leads with its VERB rather than with
 * `then` or `do`, which was the second, less obvious half of that defect.
 *
 * Quote-aware, because a `;` inside a quoted string is not a separator.
 */
function splitSegments(command) {
  if (typeof command !== "string" || !command) return [];
  const out = [];
  let cur = "";
  let quote = null;
  for (let i = 0; i < command.length; i++) {
    const c = command[i];
    if (quote) {
      if (c === "\\" && quote === '"') {
        cur += c + (command[i + 1] || "");
        i++;
        continue;
      }
      if (c === quote) quote = null;
      cur += c;
      continue;
    }
    if (c === '"' || c === "'") {
      quote = c;
      cur += c;
      continue;
    }
    if ((c === "&" && command[i + 1] === "&") || (c === "|" && command[i + 1] === "|")) {
      out.push(cur);
      cur = "";
      i++;
      continue;
    }
    if (c === ";" || c === "\n" || c === "(" || c === ")" || c === "{" || c === "}" || c === "|" || c === "&") {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += c;
  }
  out.push(cur);
  const LEADING =
    /^\s*(?:then|do|else|elif|fi|done|if|while|until|for|!|time|sudo|nohup|command|exec)\b\s*/;
  return out
    .map((s) => {
      let t = s;
      for (let k = 0; k < 4; k++) t = t.replace(LEADING, "");
      return t.trim();
    })
    .filter(Boolean);
}

/** Does this text carry an UNEXPANDED shell construct we cannot evaluate? */
function hasUnexpandedVar(text) {
  return /\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\$\(|`/.test(String(text || ""));
}

module.exports = {
  AUTHZ_DIR,
  readStdin,
  parsePayload,
  allow,
  failOpen,
  startBudget,
  budgetMs,
  emit,
  repoRoot,
  readReceipts,
  writeReceipt,
  splitSegments,
  hasUnexpandedVar,
};
