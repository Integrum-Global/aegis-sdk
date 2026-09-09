#!/usr/bin/env node
// PROJECTED FILE — do not edit here.
// Source of truth: src/aegis_sdk/coc/hooks/client-credential-containment.js
// Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check
"use strict";
/**
 * client-credential-containment.js — the credential in this session belongs to
 * a client. It goes to their deployment, and nowhere else.
 *
 * @hook-event PreToolUse:Bash|Write|Edit|NotebookEdit
 * @severity   block  (grounded in process state — argued below)
 * @enforces   src/aegis_sdk/coc/guardrails/credential-reachability.md
 *             src/aegis_sdk/coc/skills/working-against-a-deployment.md
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * HOW THIS DIFFERS FROM ORDINARY SECRET SCANNING, WHICH IS THE WHOLE POINT
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * A secret scanner asks "does this text LOOK like a credential?" — a regex for
 * `sk-[A-Za-z0-9]{32}`, a high-entropy string, a `password =` assignment. It is
 * pattern-matching on shape, it is about THIS repository's own secrets, and it
 * is wrong in both directions: it misses a credential that does not match its
 * shapes, and it fires on a hex digest that is not one.
 *
 * This asks a different and strictly answerable question: **is this the exact
 * byte sequence that is sitting in this session's environment right now?** The
 * comparison is against a VALUE READ FROM `process.env`, not against a pattern.
 *
 * That is what earns `block` under the hook-severity rule. There is
 * no lexical judgment in the decision — a literal string equality against a
 * live environment value is process state in the most direct sense available to
 * a hook, and it is not something the agent can rationalise away.
 *
 * And the credential is someone else's. The platform repository's secret rules
 * protect the platform. Here, the operator is holding a client's API key
 * against a client's production deployment. A key that reaches a log, a commit,
 * a scratch file or a third-party host is a disclosure the client suffers and
 * the operator may never learn about.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE ONE PERMITTED DESTINATION
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The client's own deployment host, over the transport that reaches it. That is
 * what the credential is FOR. `curl -H "X-API-Key: <literal>" https://<their
 * deployment>/…` is the intended use and is allowed; the same literal in a
 * commit message, a redirect into a file, a `gh issue` body, or a request to
 * any other host is not.
 *
 * Conventional secret stores — `.env`, `.envrc`, `.env.local` — are allowed as
 * write destinations. Blocking those would mean the guard forbids the correct
 * place to keep a credential, which is how a guard gets switched off. The
 * confirm path reports whether they are ignored rather than assuming it.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * FALSE-POSITIVE CONTROL, BECAUSE A BLOCK MUST NOT MISFIRE
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * A short or predictable environment value substring-matches innocent text. The
 * platform's redactor contract records exactly this: a subject id of 1–7
 * characters matches "alice" inside "malice", so it enforces a length floor and
 * fails closed with a typed error. The same reasoning, and the same remedy:
 *
 *   · a value shorter than {MIN_SECRET_LEN} characters is NOT treated as a
 *     credential — it cannot be compared safely, and saying so is honest
 *   · placeholder values (`changeme`, `test`, `xxx`, `<your-key>`, `unset`, a
 *     run of one repeated character) are excluded by name
 *   · a value with no non-alphanumeric variety AND a dictionary-plain shape is
 *     excluded — `production` is not a secret however it got into the env
 *
 * ⛔ THE VALUE IS NEVER PRINTED. Every message names the VARIABLE and a short
 * digest. A guard that quotes the credential into the transcript in order to
 * complain about the credential reaching a transcript has performed the leak it
 * is reporting.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS STRUCTURALLY CANNOT CATCH
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   · a credential that is NOT in this process's environment — read from a file
 *     by the command itself, or pasted from elsewhere. The comparison has
 *     nothing to compare against.
 *   · `$AEGIS_API_KEY` written unexpanded. That is the CORRECT form and is
 *     allowed by design; where it ends up is the shell's business, not this
 *     guard's, and it is invisible here either way.
 *   · a transformation — base64, a slice, a rot13. Equality is equality.
 *
 * It catches the literal, which is the form a credential takes when it is
 * pasted into a message, echoed into a note, or committed by accident.
 */

const crypto = require("node:crypto");
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
  splitSegments,
} = require("./lib/coc-hook.js");

const GUARDRAIL = "guardrails/credential-reachability.md — the client's credential reaches the client's deployment, and nothing else";
const BUDGET = budgetMs("COC_CREDENTIAL_BUDGET_MS", 4000);

/** Below this, a value substring-matches ordinary prose. See the header. */
const MIN_SECRET_LEN = 16;

const SECRET_NAME =
  /(?:^|_)(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE_?KEY|ACCESS_?KEY|SESSION_?TOKEN|BEARER)(?:_|$)/i;

/**
 * Variables whose names match but which are never credentials. Named
 * explicitly rather than heuristically: an unnamed exclusion is invisible to
 * the next reader and becomes a hole nobody can audit.
 */
const NOT_SECRET = new Set([
  "TOKENIZERS_PARALLELISM",
  "HF_TOKEN_PATH",
  "SECRETS_DIR",
  "API_KEY_FILE",
  "CREDENTIALS_FILE",
  "GOOGLE_APPLICATION_CREDENTIALS",
]);

const PLACEHOLDER =
  /^(?:<.*>|\{\{.*\}\}|changeme|change_me|placeholder|example|test|testing|dummy|fake|none|null|unset|todo|xxx+|your[-_].*|sk-test.*|redacted)$/i;

function isPlaceholder(v) {
  if (PLACEHOLDER.test(v.trim())) return true;
  if (/^(.)\1+$/.test(v)) return true; // a run of one character
  // Plain lowercase words with no digits and no separators are not credentials,
  // however they got into the environment.
  if (/^[a-z]+$/.test(v)) return true;
  return false;
}

/** A short, non-reversing fingerprint. Enough to correlate, useless to replay. */
function fingerprint(v) {
  return "sha256:" + crypto.createHash("sha256").update(v).digest("hex").slice(0, 8);
}

/** Credentials this session actually holds: `[{ name, value }]`. */
function sessionCredentials(env) {
  const out = [];
  for (const [name, value] of Object.entries(env)) {
    if (typeof value !== "string") continue;
    if (NOT_SECRET.has(name)) continue;
    if (!SECRET_NAME.test(name)) continue;
    const v = value.trim();
    if (v.length < MIN_SECRET_LEN) continue;
    if (isPlaceholder(v)) continue;
    out.push({ name, value: v });
  }
  return out;
}

/** Hosts a credential may legitimately reach: the configured + confirmed ones. */
function permittedHosts(root, env) {
  const hosts = new Set();
  const base = env.AGENTIC_OS_BASE_URL;
  if (base) {
    try {
      hosts.add(new URL(base).host.toLowerCase());
    } catch {
      /* an unparseable base url permits nothing, which is the safe direction */
    }
  }
  for (const r of readReceipts(root, "deployment-target")) {
    if (typeof r.host === "string") hosts.add(r.host.toLowerCase());
  }
  return hosts;
}

function hostsIn(segment) {
  return [...segment.matchAll(/\bhttps?:\/\/([^\s"'/\\]+)/g)].map((m) =>
    m[1].toLowerCase().replace(/:\d+$/, "")
  );
}

/**
 * Does this Bash segment carry the credential somewhere OTHER than the
 * deployment? Returns a reason string, or null.
 *
 * The ALLOW branch is narrow on purpose: a transport verb, and every host it
 * names is a permitted deployment. A command that reaches the deployment AND
 * somewhere else in the same segment is not allowed by the first half.
 */
function bashDestination(segment, permitted) {
  // Setting a variable is not sending it anywhere.
  if (/^(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=/.test(segment.trim())) return null;

  const isTransport = /^(?:curl|wget|http|https|xh|python3?|uv)\b/.test(segment.trim());
  const hosts = hostsIn(segment);
  if (isTransport && hosts.length && hosts.every((h) => permitted.has(h))) return null;

  if (/^(?:git|gh|jj)\b/.test(segment.trim())) return "a commit message, issue or pull-request body";
  if (/>{1,2}\s*\S/.test(segment)) return "a file, by shell redirect";
  if (/^(?:echo|printf|cat|tee|logger)\b/.test(segment.trim())) return "the transcript or a log";
  if (isTransport && hosts.length) return `a host that is not the client's deployment (${hosts.join(", ")})`;
  if (isTransport && !hosts.length) return null; // no host named — nothing established
  return "a destination that is not the client's deployment";
}

function main() {
  const budget = startBudget(BUDGET);
  const payload = parsePayload(readStdin());
  if (!payload || payload.event !== "PreToolUse") return allow();

  if (budget.spent()) return failOpen();

  const creds = sessionCredentials(process.env);
  if (!creds.length) return allow(); // nothing to leak; nothing to say

  const root = repoRoot(payload.projectDir);
  const permitted = permittedHosts(root, process.env);
  const i = payload.toolInput;
  let leak = null;

  if (payload.toolName === "Bash") {
    const command = String(i.command || "");
    for (const segment of splitSegments(command)) {
      const hit = creds.find((c) => segment.includes(c.value));
      if (!hit) continue;
      const where = bashDestination(segment, permitted);
      if (where) {
        leak = { cred: hit, where, dest: "a shell command" };
        break;
      }
    }
  } else if (["Write", "Edit", "NotebookEdit"].includes(payload.toolName)) {
    const dest = String(i.file_path || i.notebook_path || "");
    const text = String(i.content || i.new_string || i.new_source || "");
    // The conventional secret store is the correct destination for a credential.
    const isEnvFile = /(?:^|[/\\])\.env(?:\.[\w.-]+)?$|(?:^|[/\\])\.envrc$/.test(dest);
    const hit = creds.find((c) => text.includes(c.value));
    if (hit && !isEnvFile) {
      leak = { cred: hit, where: `the file ${path.basename(dest) || dest}`, dest };
    }
  }
  budget.clear();

  if (!leak) return allow();

  emit({
    hookEvent: "PreToolUse",
    severity: "block",
    guardrail: GUARDRAIL,
    what_happened:
      `The literal value of $${leak.cred.name} (${fingerprint(leak.cred.value)}) is about to reach ` +
      `${leak.where}.`,
    why:
      "That credential belongs to the client, not to this repository. Its one permitted destination is the " +
      "client's own deployment. Anywhere else — a commit, a log, a scratch file, another host — is a disclosure " +
      "the client bears and may never learn about.",
    agent_must_report: [
      `Replace the literal with the variable: $${leak.cred.name}`,
      "If the credential has already reached a durable destination in this session, say so — it needs rotating, and only the operator can start that",
      "Never quote the value back into the transcript while reporting this",
    ],
    agent_must_wait: "Do not retry with the literal value.",
    user_summary: `client credential containment — $${leak.cred.name} heading for ${leak.where}`,
    denominator: {
      credentials_in_env: creds.length,
      permitted_hosts: permitted.size ? [...permitted].join(",") : "none configured",
      min_length_floor: MIN_SECRET_LEN,
    },
  });
}

try {
  main();
} catch {
  failOpen();
}
