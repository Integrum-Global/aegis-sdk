#!/usr/bin/env node
"use strict";
/**
 * deployment-blast-radius.js — a mutating call against a client's live
 * deployment is refused until the target has been named out loud.
 *
 * @hook-event PreToolUse:Bash
 * @severity   block  (grounded in process state — argued below)
 * @enforces   src/aegis_sdk/coc/skills/working-against-a-deployment.md
 *             src/aegis_sdk/coc/guardrails/credential-reachability.md
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE THING BEING DEFENDED
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * `AGENTIC_OS_BASE_URL` plus a credential is the entire distance between a
 * session in this repository and a client's production data. There is no server
 * to start here and no staging by default — `coc-context.md` says it plainly:
 * "You work against a *deployed* Aegis over HTTP."
 *
 * The platform repository has no equivalent guard and does not need one: a core
 * developer's blast radius is a branch. The architect's is somebody else's
 * business. That asymmetry is why this guard exists here and not there.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS ONE MAY CARRY `block` WHEN THE SOURCE-ABSENCE GUARD MAY NOT
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The hook-severity rule forbids `block` on a LEXICAL match,
 * because shell expansion is invisible before execution. This guard does not
 * decide on the lexical match. The match only selects WHICH QUESTION TO ASK;
 * every input to the ANSWER is process state:
 *
 *   · the resolved target host                (parsed URL, or `process.env`)
 *   · whether that host is a real deployment  (not loopback, not RFC-2606)
 *   · whether an unexpired receipt names it   (a file on disk)
 *
 * And the refusal is reachable only in a state that is independently bad: a
 * mutating verb, aimed at a genuine remote deployment, with nothing on record
 * saying which deployment the operator believes they are aimed at. A command
 * that merely MENTIONS `curl -X POST` inside a string cannot trip it, because
 * the segment must LEAD with the transport verb — the same leading-token
 * discrimination the platform's WIP ceiling uses to justify its own teeth.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT IS ALWAYS ALLOWED, AND THIS IS THE HALF PINNED HARDEST
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   · every read — GET, HEAD, OPTIONS, and any curl with no method and no body
 *   · `python -m aegis_sdk.coc.probe`, by name. The probe is read-only BY
 *     CONSTRUCTION — it keeps only parameter-free GETs, because "a probe that
 *     mutates the deployment it is measuring is not a probe". A guard that made
 *     the diagnostic instrument expensive to run would push the architect
 *     toward guessing, which is the failure everything else here fences.
 *   · localhost, 127.0.0.1, ::1, *.local, and the RFC-2606 example domains
 *   · anything whose target cannot be resolved AND no deployment is configured
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE THIRD STATE, WHICH IS NOT SILENCE AND IS NOT A BLOCK
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * A mutating command whose host is `$SOME_VAR` this process cannot expand is
 * genuinely undecidable at hook time — MUST-3 says the skip is structural and
 * that in-hook expansion is a confused-deputy hole, so it is not attempted.
 *
 * But "I cannot tell" is not "nothing is happening". If `AGENTIC_OS_BASE_URL`
 * IS set in this session, a deployment is configured and a mutating call is in
 * flight toward an address this guard cannot read. Collapsing that into silence
 * would be the exact move `probe.py` refuses when it exits 3 rather than 0. So
 * it emits `halt-and-report`: not a refusal it cannot ground, not a silence it
 * has not earned.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE RECEIPT, AND WHY IT IS WRITTEN BY THIS FILE RATHER THAN A SIBLING TOOL
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *     node <this file> --confirm https://acme.aegis.example --reason "<why>"
 *
 * PRODUCER AND READER ARE THE SAME PROCESS, sharing one constant for the
 * directory and one function for the match. That is not tidiness; it is the fix
 * for a measured failure. In the platform repository the WIP ceiling's
 * documented escape was written to one location and read from another, so the
 * tool printed AUTHORIZED and the guard produced a byte-identical refusal — and
 * before that, the same escape was an environment variable a hook in a separate
 * process could never see. Both failures were a producer and a reader that
 * disagreed. Two callers of one function cannot disagree.
 *
 * Properties, each load-bearing and none of them free:
 *   TARGET-SCOPED  a receipt names ONE host. Confirming staging does not
 *                  authorise production; that substitution is the accident.
 *   TIME-BOXED     `expires_at` is required, defaulted to 60 minutes and capped
 *                  at 4 hours. A receipt with no expiry is a standing exemption.
 *   NOT SINGLE-USE and this is a deliberate DIFFERENCE from the WIP ceiling.
 *                  Constructing a deployment is dozens of mutating calls in one
 *                  sitting; a per-call ceremony would be re-typed
 *                  mechanically within ten minutes and would stop being read.
 *                  The window is what bounds it.
 *
 * ⛔ WHAT A RECEIPT DOES NOT ESTABLISH: that the mutation is correct, that the
 * operator was authorised by the client, or who ran the tool. It establishes
 * that the target was named, deliberately, recently, with a reason, and that
 * the naming is greppable afterwards. Read it as a discipline receipt, never as
 * proof.
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
  readReceipts,
  writeReceipt,
  splitSegments,
  hasUnexpandedVar,
  AUTHZ_DIR,
} = require("./lib/coc-hook.js");

const GUARDRAIL = "skills/working-against-a-deployment.md — name the target before you mutate it";
const RECEIPT_KIND = "deployment-target";
const DEFAULT_TTL_MIN = 60;
const MAX_TTL_MIN = 240;
const BUDGET = budgetMs("COC_BLAST_RADIUS_BUDGET_MS", 4000);

/** Transport verbs whose FIRST token starts a network call. */
const TRANSPORT = /^(?:curl|wget|http|https|xh)\b/;
const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Hosts that are not a client's deployment. Loopback plus RFC-2606/6761. */
function isLocalOrReserved(host) {
  const h = host.toLowerCase().replace(/:\d+$/, "");
  if (["localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"].includes(h)) return true;
  if (/^127\./.test(h)) return true;
  if (/\.(?:local|localhost|test|invalid|internal)$/.test(h)) return true;
  if (/^(?:.*\.)?example\.(?:com|org|net)$/.test(h)) return true;
  return false;
}

/**
 * The method this segment performs, or null when it performs no request.
 *
 * `-d` / `--data` / `-F` / `--form` / `-T` imply POST or PUT in curl even with
 * no `-X`, which is exactly how a mutating call gets written by hand — reading
 * only `-X` would miss the common form and produce a guard that looks armed.
 */
function methodOf(segment) {
  const explicit = segment.match(/(?:-X|--request)[\s=]+["']?([A-Za-z]+)["']?/);
  if (explicit) return explicit[1].toUpperCase();
  const httpie = segment.match(/^(?:https?|xh)\s+(?:-\S+\s+)*([A-Z]+)\b/);
  if (httpie) return httpie[1].toUpperCase();
  const wget = segment.match(/--method[\s=]+["']?([A-Za-z]+)["']?/);
  if (wget) return wget[1].toUpperCase();
  if (/(?:^|\s)(?:-d|--data(?:-raw|-binary|-urlencode)?|-F|--form)(?:[\s=]|$)/.test(segment)) return "POST";
  if (/(?:^|\s)(?:-T|--upload-file)(?:[\s=]|$)/.test(segment)) return "PUT";
  return null;
}

/**
 * The host this segment targets: `{ host }`, `{ unresolved: true }`, or null.
 *
 * `$AGENTIC_OS_BASE_URL` IS expanded, and only that one, from this process's
 * own environment — the variable whose whole purpose is to name the deployment,
 * exported by the operator per `coc-context.md`. Any OTHER unexpanded construct
 * in the URL position is reported unresolved rather than guessed: expanding
 * arbitrary shell here would be evaluating attacker-influenced text inside the
 * guard, which is a confused-deputy hole and not a feature.
 */
function targetOf(segment) {
  const base = process.env.AGENTIC_OS_BASE_URL || "";
  const expanded = segment.replace(/\$\{?AGENTIC_OS_BASE_URL\}?/g, base || " UNSET ");

  const url = expanded.match(/\bhttps?:\/\/([^\s"'/\\]+)/);
  if (url) return { host: url[1] };

  const urlish = segment.match(/["']?\$\{?[A-Za-z_][A-Za-z0-9_]*\}?[^\s"']*\/[^\s"']*/);
  if (urlish || hasUnexpandedVar(segment)) return { unresolved: true };
  return null;
}

/** The probe, by name. Read-only by construction; never gated. */
function isProbe(segment) {
  return /\baegis_sdk\.coc\.probe\b/.test(segment);
}

function normaliseHost(u) {
  try {
    return new URL(u).host.toLowerCase();
  } catch {
    return String(u).replace(/^https?:\/\//, "").replace(/\/.*$/, "").toLowerCase();
  }
}

// ───────────────────────────── the --confirm producer ────────────────────────

function confirm(argv) {
  const target = argv[argv.indexOf("--confirm") + 1];
  const ri = argv.indexOf("--reason");
  const reason = ri >= 0 ? argv[ri + 1] : "";
  const mi = argv.indexOf("--minutes");
  const minutes = mi >= 0 ? Number(argv[mi + 1]) : DEFAULT_TTL_MIN;

  if (!target || target.startsWith("--")) {
    process.stderr.write("usage: --confirm <deployment-url> --reason <why> [--minutes N]\n");
    return 2;
  }
  if (!reason || !reason.trim() || reason.startsWith("--")) {
    process.stderr.write(
      "--reason is REQUIRED. 'I need to run this' is not a reason — that is the precondition.\n" +
        "Say which client, which construction step, and what you expect to change.\n"
    );
    return 2;
  }
  if (!Number.isFinite(minutes) || minutes <= 0 || minutes > MAX_TTL_MIN) {
    process.stderr.write(`--minutes must be 1..${MAX_TTL_MIN}\n`);
    return 2;
  }

  const root = repoRoot(process.cwd());
  const host = normaliseHost(target);
  if (!host) {
    process.stderr.write("UNDETERMINED: could not read a host out of that target.\n");
    return 3;
  }
  const file = writeReceipt(root, RECEIPT_KIND, { host, target, reason }, minutes * 60 * 1000);

  process.stdout.write(
    `CONFIRMED  mutating calls to ${host} for ${minutes} minute(s)\n` +
      `  reason:  ${reason}\n` +
      `  receipt: ${path.relative(root, file)}\n\n` +
      `  Scoped to THIS host. It does not authorise any other deployment, and it\n` +
      `  does not make the mutation correct — it records that you named the target.\n`
  );

  // A receipt names a client's deployment. If this directory is tracked, that
  // name reaches every clone of this repository, which is a disclosure the
  // operator did not intend and would not see. Surfaced rather than enforced:
  // refusing to write would leave the session with no escape at all, which is
  // the failure mode an unreachable escape hatch already demonstrated here.
  try {
    const { execFileSync } = require("node:child_process");
    execFileSync("git", ["check-ignore", "-q", path.join(root, AUTHZ_DIR)], {
      cwd: root,
      stdio: "ignore",
    });
  } catch {
    process.stderr.write(
      `\n⚠ ${AUTHZ_DIR}/ does not appear to be git-ignored. These receipts name a\n` +
        `  client's deployment; add '${AUTHZ_DIR}/' to .gitignore before committing.\n`
    );
  }
  return 0;
}

// ───────────────────────────── the guard ─────────────────────────────────────

function main() {
  const argv = process.argv.slice(2);
  if (argv.includes("--confirm")) process.exit(confirm(argv));

  const budget = startBudget(BUDGET);
  const payload = parsePayload(readStdin());
  if (!payload || payload.event !== "PreToolUse" || payload.toolName !== "Bash") return allow();

  if (budget.spent()) return failOpen();

  const command = String(payload.toolInput.command || "");
  const root = repoRoot(payload.projectDir);

  let hostToBlock = null;
  let methodToBlock = null;
  let undecidable = null;
  let segmentsExamined = 0;

  for (const segment of splitSegments(command)) {
    segmentsExamined++;
    if (isProbe(segment)) continue;
    if (!TRANSPORT.test(segment)) continue;

    const method = methodOf(segment);
    if (!method || !MUTATING.has(method)) continue; // every read, always allowed

    const target = targetOf(segment);
    if (!target) continue;
    if (target.unresolved) {
      undecidable = { segment, method };
      continue;
    }
    if (target.host.includes(" UNSET ")) {
      undecidable = { segment, method };
      continue;
    }
    if (isLocalOrReserved(target.host)) continue;

    const host = normaliseHost(target.host);
    const receipts = readReceipts(root, RECEIPT_KIND).filter((r) => r.host === host);
    if (receipts.length) continue;

    hostToBlock = host;
    methodToBlock = method;
    break;
  }
  budget.clear();

  if (hostToBlock) {
    const known = readReceipts(root, RECEIPT_KIND).map((r) => r.host);
    emit({
      hookEvent: "PreToolUse",
      severity: "block",
      guardrail: GUARDRAIL,
      what_happened: `A ${methodToBlock} is aimed at the live deployment ${hostToBlock}, and nothing on record says that is the intended target.`,
      why:
        "This is somebody else's production data. A mutating call against a deployment must be preceded by naming " +
        "the deployment — so that a target substituted by a stale environment variable is caught by the operator " +
        "rather than by the client.",
      agent_must_report: [
        `Confirm with the operator that ${hostToBlock} is the deployment they mean, and what this ${methodToBlock} will change`,
        `Then record it: node src/aegis_sdk/coc/hooks/deployment-blast-radius.js --confirm https://${hostToBlock} --reason "<which client, which construction step, what changes>"`,
        "If this is the wrong deployment, fix AGENTIC_OS_BASE_URL rather than re-running the command",
      ],
      agent_must_wait: "Do not retry the mutating call until the target is confirmed.",
      user_summary: `blast radius — unconfirmed ${methodToBlock} against ${hostToBlock}`,
      denominator: {
        segments: segmentsExamined,
        confirmed_hosts: known.length ? known.join(",") : "none",
      },
    });
  }

  if (undecidable && process.env.AGENTIC_OS_BASE_URL) {
    emit({
      hookEvent: "PreToolUse",
      severity: "halt-and-report",
      guardrail: GUARDRAIL,
      what_happened: `A ${undecidable.method} is in flight to a target this guard cannot resolve, while AGENTIC_OS_BASE_URL names a live deployment (${normaliseHost(process.env.AGENTIC_OS_BASE_URL)}).`,
      why:
        "The host is behind a shell variable this process cannot expand, and expanding shell inside a guard is a " +
        "confused-deputy hole rather than a feature. 'I cannot tell' is not 'nothing is happening' — so this is " +
        "surfaced rather than silently allowed.",
      agent_must_report: [
        "State which deployment this command actually reaches, and how you established it",
        "Prefer a literal URL over a variable for a mutating call, so the target is visible in the transcript",
      ],
      agent_must_wait: "Say what the target is before re-running.",
      user_summary: "blast radius — mutating call to an unresolvable target, deployment configured",
      denominator: { segments: segmentsExamined, resolved: "no" },
    });
  }

  return allow();
}

try {
  main();
} catch {
  failOpen();
}
