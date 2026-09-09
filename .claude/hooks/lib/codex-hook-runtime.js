#!/usr/bin/env node
// PROJECTED FILE — do not edit here.
// Source of truth: src/aegis_sdk/coc/hooks/lib/codex-hook-runtime.js
// Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check
"use strict";
/**
 * codex-hook-runtime.js — deliver the runtime contract Codex does not.
 *
 * WHAT IS MISSING AND WHY A WRAPPER RATHER THAN A PREFIX.
 *
 * The three CLIs invoke the same hook scripts, and each hook needs to know two
 * things: which runtime is calling it, and where the project root is. CC and
 * Gemini export a project-dir variable; Codex exports neither, and there is no
 * safe way to add one at the registration site:
 *
 *   · `COC_RUNTIME=codex node ./.claude/hooks/x.js` — under `execvp` the whole
 *     assignment becomes `argv[0]`, so the process is ENOENT and the hook
 *     SILENTLY DOES NOT RUN. A guard that fails this way is indistinguishable
 *     from a guard that ran and found nothing, which is the worst shape a
 *     missing guard can take.
 *   · `node $CODEX_PROJECT_DIR/.claude/hooks/x.js` — that variable does not
 *     exist, expands to empty, and produces `node /.claude/hooks/x.js` →
 *     MODULE_NOT_FOUND. Same silence, different cause.
 *
 * So the registration is plain argv — `node ./.claude/hooks/lib/codex-hook-
 * runtime.js ./.claude/hooks/<name>.js` — and this file stamps the environment
 * before handing over.
 *
 * IT DELEGATES IN-PROCESS. `require` rather than a child process: the hook must
 * inherit this process's stdin (the payload is piped there and can only be read
 * once) and its exit code (a PreToolUse refusal is exit 2, and a wrapper that
 * swallowed it would turn every block into an allow).
 */

const path = require("node:path");

const target = process.argv[2];
if (!target) {
  // No target is a REGISTRATION error, not a session's fault. Say so on stderr
  // and allow: wedging a partner's session over our own misconfiguration is the
  // one failure mode none of these guards is permitted to have.
  process.stderr.write("codex-hook-runtime: no hook script given; allowing\n");
  process.stdout.write(JSON.stringify({ continue: true }) + "\n");
  process.exit(0);
}

process.env.COC_RUNTIME = "codex";
if (!process.env.CLAUDE_PROJECT_DIR) process.env.CLAUDE_PROJECT_DIR = process.cwd();

try {
  require(path.resolve(process.cwd(), target));
} catch (e) {
  process.stderr.write(`codex-hook-runtime: ${target} did not load (${e && e.message}); allowing\n`);
  process.stdout.write(JSON.stringify({ continue: true }) + "\n");
  process.exit(0);
}
