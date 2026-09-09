#!/usr/bin/env node
// PROJECTED FILE — do not edit here.
// Source of truth: src/aegis_sdk/coc/hooks/probe-before-claim.js
// Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check
"use strict";
/**
 * probe-before-claim.js — you have an instrument for this question. Use it
 * before you answer it in writing.
 *
 * @hook-event PostToolUse:Bash  (record what the probe answered)
 *             PreToolUse:Write|Edit|Bash  (check before a durable claim)
 * @severity   halt-and-report  (the claim half is textual — argued below)
 * @enforces   src/aegis_sdk/coc/guardrails/reading-a-measurement.md
 *             src/aegis_sdk/coc/guardrails/client-model-fidelity.md
 *             coc-context.md § habit 3 — separate observed from inferred
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THE SDK CAN ENFORCE THIS AND THE PLATFORM CANNOT
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The platform's verify-before-claiming guidance says: cite the
 * endpoint, not the documentation. Good advice, and advice is all it can be —
 * there is no single artifact it can point at and say "run THAT first".
 *
 * This repository ships one. `python -m aegis_sdk.coc.probe` asks a specific
 * deployment, with specific credentials, which of this client's declared routes
 * they can actually reach — and it is built to refuse a misleading zero: it
 * authenticates against a control operation before printing any count and exits
 * `3` UNDETERMINED rather than `0` when it cannot tell, because "an expired
 * token and a perfectly reachable API produce the same output from a naive
 * version of this".
 *
 * An obligation with a named instrument behind it is enforceable. That is the
 * whole of the exceed here: not a better rule, a rule that has something to
 * bind to.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE TWO HALVES, AND WHY THE RECORDING HALF IS AN OBSERVATION
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * RECORD (PostToolUse). When a probe invocation completes, its OWN OUTPUT is
 *   read and a receipt is written: which deployment, and what it answered. This
 *   is not the agent asserting it ran a probe — it is the harness observing
 *   that one ran and reading the verdict the probe itself printed. The agent
 *   cannot write this receipt by saying so.
 *
 * CHECK (PreToolUse). A durable claim about what a deployment SUPPORTS or what
 *   a credential CAN REACH, with no answering receipt, is surfaced.
 *
 * ⛔ AN UNDETERMINED RUN DOES NOT SATISFY THE OBLIGATION, AND THIS IS THE CLAUSE
 * MOST WORTH GUARDING. The probe's exit `3` exists precisely so that "I could
 * not tell" is never spelled `0`. A receipt that recorded UNDETERMINED and then
 * cleared the requirement would take the one distinction the instrument was
 * built to preserve and discard it at the last step — and it would do so
 * silently, which is worse than not checking at all. So an UNDETERMINED receipt
 * produces a DIFFERENT and sharper message than a missing one: you ran it, and
 * it told you it could not answer.
 *
 * Silence is reachable by exactly two routes — a receipt that answered, or a
 * claim written honestly (hedged, or attributed to something the reader holds).
 * It is not reachable by omission.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY `halt-and-report` AND NOT `block`
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * Half of this IS process state — the receipt exists or it does not, and its
 * verdict was printed by the instrument rather than claimed by the agent. But
 * the other half asks whether a sentence IS a reachability claim, and that is a
 * question about what its author meant. The hook-severity rule is
 * unambiguous that a decision resting on a text match does not carry teeth, and
 * dressing the receipt half up as though it settled the whole thing would be
 * the same false-grounding move the source-absence guard refuses beside it.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS STRUCTURALLY CANNOT CATCH
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   · a reachability claim in ordinary words ("that endpoint works fine")
 *   · a claim about a DIFFERENT deployment than the one probed — the receipt is
 *     host-scoped for that reason, but a claim naming no host cannot be matched
 *     to one, and is checked against any answering receipt at all
 *   · whether the claim is TRUE. A probe that ran does not make the sentence
 *     right; it makes it answerable. Reachability is admission, not correctness
 *     — the probe's own header says so, and no receipt changes that.
 */

const {
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
} = require("./lib/coc-hook.js");

const GUARDRAIL = "guardrails/reading-a-measurement.md — you have an instrument; run it before you answer in writing";
const RECEIPT_KIND = "probe";
const BUDGET = budgetMs("COC_PROBE_CLAIM_BUDGET_MS", 4000);

/** A reachability answer is stable for hours, not minutes; it is not permanent. */
const RECEIPT_TTL_MS = 4 * 60 * 60 * 1000;

const PROBE_INVOCATION = /\baegis_sdk\.coc\.probe\b/;

/** Sentences claiming what a deployment supports, or what a credential reaches. */
const CLAIMS = [
  /\bthe (?:deployment|platform|instance|tenant) (?:supports|serves|exposes|provides|offers|has) \b/i,
  /\b(?:route|endpoint|operation|path)s? (?:is|are) (?:reachable|unreachable|available|unavailable|served|supported)\b/i,
  /\b(?:is|are) (?:not )?reachable (?:by|with|from) (?:the |your |my )?(?:key|api key|session|token|credential)\b/i,
  /\b(?:the |your |my )?(?:key|api key|session|token) can(?:not|'t)? reach\b/i,
  /\b\d+ (?:of \d+ )?(?:routes?|endpoints?|operations?) (?:are|is|were|was) (?:reachable|denied|refused|available)\b/i,
  /\bthis deployment does(?:n't| not) (?:support|serve|expose|have)\b/i,
];

/**
 * Markers that make a reachability sentence honest without a probe run.
 *
 * `the client declares` is here deliberately and is not a loophole: it is the
 * FREE claim `coc-context.md` names — "'This client declares the operation' and
 * 'the deployment serves the operation' are different claims, and only the
 * first is free." A sentence that says which of the two it is has already done
 * what this guard exists to make it do.
 */
const HONEST = [
  /\b(?:appears?|seems?|suggests?|presumably|probably|likely|may|might|expect(?:ed)?)\b/i,
  /\b(?:unverified|unconfirmed|untested|not (?:yet )?(?:verified|probed|measured))\b/i,
  /\bcannot be (?:answered|determined|established|verified)\b/i,
  /\bthe (?:client|SDK|package) declares\b/i,
  /\baccording to the (?:probe|handbook)\b/i,
  /\bthe probe (?:reported|found|returned|printed|says)\b/i,
  /\b(?:do not|don't|must not|MUST NOT|BLOCKED)\b/,
];

function stripFences(text) {
  return text.replace(/```[\s\S]*?```/g, " ");
}

function claimSentences(text) {
  const out = [];
  const sentences = stripFences(text)
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?:])\s+(?=[A-Z`*_-]|$)/);
  for (const s of sentences) {
    if (!s.trim()) continue;
    if (HONEST.some((re) => re.test(s))) continue;
    if (CLAIMS.some((re) => re.test(s))) out.push(s.trim());
  }
  return out;
}

function durableText(payload) {
  const t = payload.toolName;
  const i = payload.toolInput;
  if (t === "Write") return { text: String(i.content || ""), dest: String(i.file_path || "") };
  if (t === "Edit") return { text: String(i.new_string || ""), dest: String(i.file_path || "") };
  if (t === "NotebookEdit") return { text: String(i.new_source || ""), dest: String(i.notebook_path || "") };
  if (t !== "Bash") return null;
  const command = String(i.command || "");
  const bodies = [];
  for (const seg of splitSegments(command)) {
    if (!/^(?:git|gh)\b/.test(seg)) continue;
    for (const m of seg.matchAll(/(?:-m|--body|--body-text|--message)[\s=]+("(?:[^"\\]|\\.)*"|'[^']*')/g)) {
      bodies.push(m[1].slice(1, -1));
    }
  }
  return bodies.length ? { text: bodies.join("\n\n"), dest: "<git/gh message>" } : null;
}

// ───────────────────────────── RECORD (PostToolUse) ──────────────────────────

/**
 * Read the probe's own output and record what IT said.
 *
 * The verdict is taken from the instrument's stdout, not from an exit code
 * alone, because the probe deliberately reports UNDETERMINED on stderr in
 * several distinct situations — a control credential that will not
 * authenticate, a scan that parsed nothing, a filter that excluded everything —
 * and each of them is a run that must NOT clear the obligation.
 */
function record(payload, root) {
  const command = String(payload.toolInput.command || "");
  if (!PROBE_INVOCATION.test(command)) return allow();

  const resp = payload.toolResponse || {};
  const text = [resp.stdout, resp.stderr, typeof resp === "string" ? resp : ""]
    .filter(Boolean)
    .join("\n");

  const undetermined = /\bUNDETERMINED\b/.test(text);
  const baseFromOutput = text.match(/^base url\s*:\s*(\S+)/m);
  const baseFromCommand = command.match(/--base-url[\s=]+["']?(\S+?)["']?(?:\s|$)/);
  const transportsOnly = /--transports-only\b/.test(command);

  let host = "";
  const raw = (baseFromOutput && baseFromOutput[1]) || (baseFromCommand && baseFromCommand[1]) || "";
  if (raw && !raw.startsWith("$")) {
    try {
      host = new URL(raw).host.toLowerCase();
    } catch {
      host = raw.toLowerCase();
    }
  }

  writeReceipt(
    root,
    RECEIPT_KIND,
    {
      host,
      // A `--transports-only` run never touches the network. It answers an
      // offline question about this package and says NOTHING about any
      // deployment's reachability, so it is recorded as its own verdict rather
      // than as an answer — otherwise the cheapest possible invocation would
      // clear an obligation about a live system it never contacted.
      verdict: undetermined
        ? "undetermined"
        : transportsOnly
          ? "transports-only"
          : host
            ? "answered"
            : "answered-untargeted",
      reason: "recorded from a probe invocation observed by the harness",
      command_excerpt: command.slice(0, 200),
    },
    RECEIPT_TTL_MS
  );
  return allow();
}

// ───────────────────────────── CHECK (PreToolUse) ────────────────────────────

function check(payload, root) {
  const target = durableText(payload);
  if (!target || !target.text.trim()) return allow();

  const claims = claimSentences(target.text);
  if (!claims.length) return allow();

  const receipts = readReceipts(root, RECEIPT_KIND);
  const answering = receipts.filter((r) => r.verdict === "answered" || r.verdict === "answered-untargeted");
  if (answering.length) return allow();

  const undetermined = receipts.filter((r) => r.verdict === "undetermined");
  const offline = receipts.filter((r) => r.verdict === "transports-only");

  const shown = claims.slice(0, 3).map((c) => (c.length > 160 ? c.slice(0, 157) + "…" : c));

  let what;
  let report;
  if (undetermined.length) {
    what =
      `A reachability claim is about to be written, and the only probe run on record reported UNDETERMINED ` +
      `(host: ${undetermined[0].host || "not stated"}).`;
    report = [
      "The probe told you it could not answer — most often a credential that will not authenticate against the control operation",
      "Fix the credential and re-run, then make the claim; or write what the probe actually reported, which is that this is unresolved",
      ...shown.map((c) => `Claim awaiting evidence: ${c}`),
    ];
  } else if (offline.length) {
    what =
      "A reachability claim is about to be written, and the only probe run on record was `--transports-only` — an offline scan that never contacted a deployment.";
    report = [
      "Run the live probe with --base-url and a credential; the offline scan answers a different question",
      ...shown.map((c) => `Claim awaiting evidence: ${c}`),
    ];
  } else {
    what = `A durable write to ${target.dest || "a file"} claims what a deployment supports or what a credential reaches, with no probe run on record.`;
    report = [
      'Run it: python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" --api-key "$KEY" --token "$SESSION_TOKEN"',
      "Then say what it printed, and name the falsifying result — for 'this family is reachable by my key', that is a KEY-DENIED row",
      "Or hedge the sentence honestly: 'the client declares this operation' is free; 'the deployment serves it' is not",
      ...shown.map((c) => `Claim awaiting evidence: ${c}`),
    ];
  }

  emit({
    hookEvent: "PreToolUse",
    severity: "halt-and-report",
    guardrail: GUARDRAIL,
    what_happened: what,
    why:
      "Reachability is a property of a deployment plus a credential, and this repository ships the instrument that " +
      "measures it. A claim about it that no run supports is an inference wearing the grammar of an observation.",
    agent_must_report: report,
    agent_must_wait: "Run the probe, or rewrite the claim as the inference it is.",
    user_summary: "probe-before-claim — reachability asserted with no answering probe run",
    denominator: {
      claim_sentences: claims.length,
      receipts_on_record: receipts.length,
      answering: answering.length,
      undetermined: undetermined.length,
      transports_only: offline.length,
    },
  });
}

function main() {
  const budget = startBudget(BUDGET);
  const payload = parsePayload(readStdin());
  if (!payload) return allow();
  if (budget.spent()) return failOpen();
  const root = repoRoot(payload.projectDir);

  if (payload.event === "PostToolUse" && payload.toolName === "Bash") {
    budget.clear();
    return record(payload, root);
  }
  if (payload.event === "PreToolUse") {
    budget.clear();
    return check(payload, root);
  }
  return allow();
}

try {
  main();
} catch {
  failOpen();
}
