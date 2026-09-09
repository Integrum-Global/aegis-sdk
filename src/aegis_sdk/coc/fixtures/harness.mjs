/**
 * harness.mjs — the primitives every case file uses.
 *
 * SEPARATE FROM `run.mjs` FOR A MECHANICAL REASON, not a stylistic one. The
 * runner discovers case files with a dynamic `import()`, and it has top-level
 * `await`. If the cases imported the RUNNER for these helpers, the module graph
 * would be circular and the top-level await would never settle — node reports
 * "Detected unsettled top-level await" and the suite hangs rather than fails,
 * which is the worst possible failure for a test harness: green is impossible
 * and red is never printed.
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const COC = path.resolve(HERE, "..");
export const REPO = path.resolve(COC, "..", "..", "..");
export const HOOKS = path.join(COC, "hooks");

/**
 * A throwaway repository root shaped like the SDK, so a guard that reads the
 * filesystem has something real to read without touching the checkout.
 */
export function scratchRepo() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "coc-fixture-"));
  fs.mkdirSync(path.join(dir, "src", "aegis_sdk", "coc"), { recursive: true });
  fs.mkdirSync(path.join(dir, "src", "aegis_sdk", "handbook"), { recursive: true });
  return dir;
}

/**
 * Run a hook as a REAL process with a REAL payload on stdin.
 *
 * `hooksDir` is injectable so a mutation control can point at a mutated COPY of
 * the tree — mutating the checkout in place is how a fleet manufactures false
 * findings, and this harness must not be able to leave the repository damaged.
 */
export function runHook(hook, payload, { env = {}, cwd = REPO, hooksDir = HOOKS } = {}) {
  const script = path.join(hooksDir, `${hook}.js`);
  const base = { ...process.env, CLAUDE_PROJECT_DIR: cwd };
  // A credential guard must see EXACTLY the variables a case declares. Whoever
  // runs this suite has an environment of their own, and it is not a test input
  // — an ambient AEGIS_API_KEY would make results depend on the operator.
  for (const k of Object.keys(base)) {
    if (/(?:API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AGENTIC_OS_BASE_URL)/i.test(k)) delete base[k];
  }
  let stdout = "";
  let stderr = "";
  let code = 0;
  try {
    stdout = execFileSync("node", [script], {
      input: typeof payload === "string" ? payload : JSON.stringify(payload),
      encoding: "utf8",
      cwd,
      env: { ...base, ...env },
      timeout: 30000,
    });
  } catch (e) {
    code = typeof e.status === "number" ? e.status : -1;
    stdout = String(e.stdout || "");
    stderr = String(e.stderr || "");
  }
  let severity = null;
  try {
    const last = stdout.trim().split("\n").filter(Boolean).pop() || "{}";
    const parsed = JSON.parse(last);
    severity = parsed.coc ? parsed.coc.severity : null;
  } catch {
    /* an unparseable stdout is itself a failure, and the case catches it on `code` */
  }
  return { code, stdout, stderr, severity };
}

export const pre = (tool, input, extra = {}) => ({
  hook_event_name: "PreToolUse",
  tool_name: tool,
  tool_input: input,
  ...extra,
});

export const post = (tool, input, response, extra = {}) => ({
  hook_event_name: "PostToolUse",
  tool_name: tool,
  tool_input: input,
  tool_response: response,
  ...extra,
});
