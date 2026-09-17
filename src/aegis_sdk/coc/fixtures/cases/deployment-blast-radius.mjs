/**
 * Cases for deployment-blast-radius.js.
 *
 * THE THREE SILENCE CASES NAMED IN THE BRIEF AS THE ONES TO PIN HARDEST ARE ALL
 * HERE AND ALL LOAD-BEARING:
 *
 *   · a read-only call is ALWAYS allowed — including `python -m
 *     aegis_sdk.coc.probe`, by name. The probe is the architect's diagnostic
 *     instrument; a guard that made it expensive to run would push them toward
 *     guessing, which is the failure everything else in this set fences.
 *   · an ALREADY-CONFIRMED target does not re-prompt. A ceremony that repeats
 *     for every call in a deployment construction is re-typed mechanically
 *     within ten minutes and stops being read.
 *   · localhost and the RFC-2606 example domains are not a client's production.
 *
 * The receipt cases drive the REAL producer (`--confirm`) rather than writing a
 * hand-shaped JSON file, so producer and reader are exercised against each
 * other. That is the specific failure this guard was designed around: in the
 * platform repository, a WIP-ceiling escape hatch printed AUTHORIZED while the
 * guard produced a byte-identical refusal, because the two disagreed about where
 * the receipt lived. A fixture that fabricated the receipt would have passed.
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runHook, pre, scratchRepo } from "../harness.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const HOOK = "deployment-blast-radius";

const bash = (command) => pre("Bash", { command });

/** Drive the real `--confirm` producer inside a scratch repo. */
function confirmed(hooksDir, url, minutes = 60) {
  const repo = scratchRepo();
  execFileSync("node", [path.join(hooksDir, `${HOOK}.js`), "--confirm", url, "--reason", "fixture: named target", "--minutes", String(minutes)], {
    cwd: repo,
    encoding: "utf8",
    env: { ...process.env, CLAUDE_PROJECT_DIR: repo },
    stdio: ["ignore", "pipe", "pipe"],
  });
  return repo;
}

const c = (name, code, command, severity, env = {}) => ({
  name,
  expect: severity === undefined ? { code } : { code, severity },
  run: ({ hooksDir }) => {
    const repo = scratchRepo();
    try {
      return runHook(HOOK, bash(command), { cwd: repo, hooksDir, env });
    } finally {
      fs.rmSync(repo, { recursive: true, force: true });
    }
  },
});

export const cases = [
  // ── BLOCKS ─────────────────────────────────────────────────────────────────
  c("BLOCK: POST to a live deployment, unconfirmed", 2, 'curl -X POST https://acme.aegis.io/api/v1/objectives -d "{}"', "block"),
  c("BLOCK: DELETE to a live deployment", 2, "curl -X DELETE https://acme.aegis.io/api/v1/agents/7", "block"),
  c("BLOCK: PATCH via --request", 2, "curl --request PATCH https://acme.aegis.io/api/v1/units/3", "block"),
  c("BLOCK: implied POST from -d with no -X", 2, 'curl -d \'{"a":1}\' https://acme.aegis.io/api/v1/tools', "block"),
  c("BLOCK: implied PUT from --upload-file", 2, "curl -T ./spec.json https://acme.aegis.io/api/v1/spec", "block"),
  c("BLOCK: httpie form", 2, "http POST https://acme.aegis.io/api/v1/objectives name=x", "block"),
  c("BLOCK: hidden inside a subshell", 2, "(curl -X POST https://acme.aegis.io/api/v1/x)", "block"),
  c("BLOCK: hidden inside an if/then", 2, "if true; then curl -X POST https://acme.aegis.io/api/v1/x; fi", "block"),
  c("BLOCK: hidden inside a for-do loop", 2, "for i in 1 2; do curl -X POST https://acme.aegis.io/api/v1/x; done", "block"),
  c(
    "BLOCK: target arrives via AGENTIC_OS_BASE_URL",
    2,
    'curl -X POST "$AGENTIC_OS_BASE_URL/api/v1/objectives"',
    "block",
    { AGENTIC_OS_BASE_URL: "https://acme.aegis.io" }
  ),

  // The MIGRATED operator. This guard expanded only the LEGACY name, so
  // an architect who did exactly what the env-prefix remediation instructs got
  // NO output at all on a mutating call written with the variable: measured
  // exit 0 {"continue":true} where the legacy spelling blocked. Fail-OPEN, in
  // the harness partners receive — a fail-open introduced BY the remediation.
  //
  // The pair is load-bearing: the case above pins the legacy spelling and this
  // one the current spelling, so dropping EITHER from the resolver reds one of
  // them. A single case on one name is what allowed the other to go silent.
  c(
    "BLOCK: target arrives via AEGIS_BASE_URL (the migrated operator)",
    2,
    'curl -X POST "$AEGIS_BASE_URL/api/v1/objectives"',
    "block",
    { AEGIS_BASE_URL: "https://acme.aegis.io" }
  ),
  c(
    "BLOCK: AEGIS_BASE_URL wins when BOTH are set",
    2,
    'curl -X DELETE "$AEGIS_BASE_URL/api/v1/agents/7"',
    "block",
    { AEGIS_BASE_URL: "https://acme.aegis.io", AGENTIC_OS_BASE_URL: "https://stale.aegis.io" }
  ),

  // ── THE THIRD STATE: unresolvable target, deployment configured ────────────
  c(
    "HALT: unresolvable host while a deployment is configured",
    2,
    'curl -X POST "$SOME_OTHER_URL/api/v1/x"',
    "halt-and-report",
    { AGENTIC_OS_BASE_URL: "https://acme.aegis.io" }
  ),
  c("SILENT: unresolvable host and NO deployment configured", 0, 'curl -X POST "$SOME_OTHER_URL/api/v1/x"'),

  // ── SILENCE — pinned hardest ───────────────────────────────────────────────
  c("SILENT: a GET", 0, "curl https://acme.aegis.io/api/v1/auth/me"),
  c("SILENT: an explicit -X GET", 0, "curl -X GET https://acme.aegis.io/api/v1/objectives"),
  c("SILENT: a HEAD", 0, "curl -X HEAD https://acme.aegis.io/api/v1/health"),
  c("SILENT: the probe, live, by name", 0, 'python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" --api-key "$KEY"', undefined, {
    AGENTIC_OS_BASE_URL: "https://acme.aegis.io",
  }),
  c("SILENT: the probe, offline", 0, "python -m aegis_sdk.coc.probe --transports-only"),
  c("SILENT: localhost", 0, "curl -X POST http://localhost:8000/api/v1/objectives"),
  c("SILENT: 127.0.0.1", 0, "curl -X DELETE http://127.0.0.1:8000/api/v1/x"),
  c("SILENT: an RFC-2606 example domain", 0, "curl -X POST https://aegis.example.com/api/v1/x"),
  c("SILENT: a .local host", 0, "curl -X POST https://dev.local/api/v1/x"),
  c("SILENT: the verb only MENTIONED, not led", 0, 'echo "run curl -X POST https://acme.aegis.io/api/v1/x when ready"'),
  c("SILENT: a command that is not a transport at all", 0, "git status --porcelain"),
  c("SILENT: no URL anywhere", 0, "curl -X POST"),

  // ── THE RECEIPT: real producer, real reader ───────────────────────────────
  {
    name: "SILENT: an already-confirmed target does not re-prompt",
    expect: { code: 0 },
    run: ({ hooksDir }) => {
      const repo = confirmed(hooksDir, "https://acme.aegis.io");
      try {
        return runHook(HOOK, bash("curl -X POST https://acme.aegis.io/api/v1/objectives"), { cwd: repo, hooksDir });
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },
  {
    name: "BLOCK: a receipt for staging does NOT authorise production",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) => {
      const repo = confirmed(hooksDir, "https://staging.acme.aegis.io");
      try {
        return runHook(HOOK, bash("curl -X POST https://acme.aegis.io/api/v1/objectives"), { cwd: repo, hooksDir });
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },
  {
    name: "BLOCK: an EXPIRED receipt authorises nothing",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) => {
      const repo = confirmed(hooksDir, "https://acme.aegis.io");
      const dir = path.join(repo, ".coc-authz", "deployment-target");
      for (const f of fs.readdirSync(dir)) {
        const p = path.join(dir, f);
        const rec = JSON.parse(fs.readFileSync(p, "utf8"));
        rec.expires_at = new Date(Date.now() - 1000).toISOString();
        fs.writeFileSync(p, JSON.stringify(rec));
      }
      try {
        return runHook(HOOK, bash("curl -X POST https://acme.aegis.io/api/v1/objectives"), { cwd: repo, hooksDir });
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },
  {
    name: "BLOCK: a receipt with no reason is not a receipt",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) => {
      const repo = confirmed(hooksDir, "https://acme.aegis.io");
      const dir = path.join(repo, ".coc-authz", "deployment-target");
      for (const f of fs.readdirSync(dir)) {
        const p = path.join(dir, f);
        const rec = JSON.parse(fs.readFileSync(p, "utf8"));
        delete rec.reason;
        fs.writeFileSync(p, JSON.stringify(rec));
      }
      try {
        return runHook(HOOK, bash("curl -X POST https://acme.aegis.io/api/v1/objectives"), { cwd: repo, hooksDir });
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },
  {
    name: "PRODUCER: --confirm refuses without a reason",
    expect: { code: 2 },
    run: ({ hooksDir }) => {
      const repo = scratchRepo();
      try {
        execFileSync("node", [path.join(hooksDir, `${HOOK}.js`), "--confirm", "https://acme.aegis.io"], {
          cwd: repo,
          encoding: "utf8",
          stdio: ["ignore", "pipe", "pipe"],
        });
        return { code: 0, severity: null };
      } catch (e) {
        return { code: e.status, severity: null };
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },
  {
    name: "PRODUCER: --confirm refuses a window beyond the cap",
    expect: { code: 2 },
    run: ({ hooksDir }) => {
      const repo = scratchRepo();
      try {
        execFileSync(
          "node",
          [path.join(hooksDir, `${HOOK}.js`), "--confirm", "https://acme.aegis.io", "--reason", "x", "--minutes", "9999"],
          { cwd: repo, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }
        );
        return { code: 0, severity: null };
      } catch (e) {
        return { code: e.status, severity: null };
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },

  // ── ENVELOPE ───────────────────────────────────────────────────────────────
  { name: "FAIL-OPEN: malformed stdin", expect: { code: 0 }, run: ({ hooksDir }) => runHook(HOOK, "garbage", { hooksDir }) },
  { name: "FAIL-OPEN: not a Bash call", expect: { code: 0 }, run: ({ hooksDir }) => runHook(HOOK, pre("Read", { file_path: "/x" }), { hooksDir }) },
  {
    name: "FAIL-OPEN: budget spent before evaluation",
    expect: { code: 0 },
    run: ({ hooksDir }) => {
      const repo = scratchRepo();
      try {
        return runHook(HOOK, bash("curl -X POST https://acme.aegis.io/api/v1/x"), {
          cwd: repo,
          hooksDir,
          env: { COC_BLAST_RADIUS_BUDGET_MS: "-1" },
        });
      } finally {
        fs.rmSync(repo, { recursive: true, force: true });
      }
    },
  },
];
