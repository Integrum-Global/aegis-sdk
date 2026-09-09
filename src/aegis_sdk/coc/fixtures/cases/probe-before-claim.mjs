/**
 * Cases for probe-before-claim.js.
 *
 * THE CLAUSE MOST WORTH GUARDING IS THAT AN **UNDETERMINED** RUN DOES NOT
 * SATISFY THE OBLIGATION. `probe.py` exits 3 rather than 0 precisely so that "I
 * could not tell" is never spelled the same as "nothing found"; a receipt that
 * recorded UNDETERMINED and then cleared the requirement would take the one
 * distinction the instrument was built to preserve and discard it silently at
 * the last step. Three cases below pin that, and the mutation control in
 * `run.mjs` breaks exactly it.
 *
 * The RECORD half is driven through real PostToolUse payloads carrying the
 * probe's real output shapes, so the receipt is written the way the harness
 * would write it rather than the way a fixture would like it to be.
 */

import fs from "node:fs";
import path from "node:path";
import { runHook, pre, post, scratchRepo } from "../harness.mjs";

const HOOK = "probe-before-claim";

const withRepo = (fn) => {
  const repo = scratchRepo();
  try {
    return fn(repo);
  } finally {
    fs.rmSync(repo, { recursive: true, force: true });
  }
};

/** Record a probe run by driving the REAL PostToolUse arm. */
function recordProbe(repo, hooksDir, { stdout, command }) {
  return runHook(HOOK, post("Bash", { command }, { stdout, stderr: "" }), { cwd: repo, hooksDir });
}

const ANSWERED =
  "files parsed         : 144\nbase url          : https://acme.aegis.io\ncredentials       : key, session\nprobeable GETs    : 31\ncontrol           : /api/v1/auth/me -> 200 for every credential\nKEY-DENIED, SESSION-OK: 4\n";
const UNDETERMINED =
  "files parsed         : 144\nbase url          : https://acme.aegis.io\n\nUNDETERMINED: control /api/v1/auth/me did not return 200 for: {'key': 401}\n";
const LIVE_CMD = 'python -m aegis_sdk.coc.probe --base-url https://acme.aegis.io --api-key "$KEY" --token "$TOK"';

const claim = (text, repo, hooksDir) =>
  runHook(HOOK, pre("Write", { file_path: path.join(repo, "notes/report.md"), content: text }), { cwd: repo, hooksDir });

export const cases = [
  // ── FIRES: a reachability claim with nothing on record ────────────────────
  {
    name: "FIRE: 'the deployment supports' with no probe run",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) => withRepo((repo) => claim("The deployment supports scoped tool registration.", repo, hooksDir)),
  },
  {
    name: "FIRE: 'these routes are reachable' with no probe run",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) => withRepo((repo) => claim("Those endpoints are reachable for the customer's key.", repo, hooksDir)),
  },
  {
    name: "FIRE: 'the key can reach' with no probe run",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) => withRepo((repo) => claim("The api key can reach every analytics route.", repo, hooksDir)),
  },
  {
    name: "FIRE: a counted claim with no probe run",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) => withRepo((repo) => claim("12 of 31 routes are denied for this credential.", repo, hooksDir)),
  },
  {
    name: "FIRE: the claim reaches a commit message",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) =>
      withRepo((repo) =>
        runHook(HOOK, pre("Bash", { command: 'git commit -m "docs: the deployment supports persona routing"' }), { cwd: repo, hooksDir })
      ),
  },

  // ── THE UNDETERMINED CLAUSE ───────────────────────────────────────────────
  {
    name: "FIRE: an UNDETERMINED run does NOT satisfy the obligation",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) =>
      withRepo((repo) => {
        recordProbe(repo, hooksDir, { stdout: UNDETERMINED, command: LIVE_CMD });
        return claim("The deployment supports scoped tool registration.", repo, hooksDir);
      }),
  },
  {
    name: "FIRE: a --transports-only run answers a different question",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) =>
      withRepo((repo) => {
        recordProbe(repo, hooksDir, {
          stdout: "files parsed         : 144\neligible (no HTTP lib): 130\nSIMULATED TRANSPORTS : 0\n",
          command: "python -m aegis_sdk.coc.probe --transports-only",
        });
        return claim("The deployment supports scoped tool registration.", repo, hooksDir);
      }),
  },

  // ── SILENCE ────────────────────────────────────────────────────────────────
  {
    name: "SILENT: an answering probe run clears it",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo((repo) => {
        recordProbe(repo, hooksDir, { stdout: ANSWERED, command: LIVE_CMD });
        return claim("The deployment supports scoped tool registration.", repo, hooksDir);
      }),
  },
  {
    name: "SILENT: the claim is hedged",
    expect: { code: 0 },
    run: ({ hooksDir }) => withRepo((repo) => claim("The deployment probably supports this, but it is unverified.", repo, hooksDir)),
  },
  {
    name: "SILENT: the free claim, said as the free claim",
    expect: { code: 0 },
    run: ({ hooksDir }) => withRepo((repo) => claim("The client declares this operation; whether the deployment serves it is unverified.", repo, hooksDir)),
  },
  {
    name: "SILENT: attributed to the probe",
    expect: { code: 0 },
    run: ({ hooksDir }) => withRepo((repo) => claim("The probe reported that 4 routes are reachable by the session only.", repo, hooksDir)),
  },
  {
    name: "SILENT: prose with no reachability claim in it",
    expect: { code: 0 },
    run: ({ hooksDir }) => withRepo((repo) => claim("We agreed the unit hierarchy should mirror their org chart.", repo, hooksDir)),
  },
  {
    name: "SILENT: inside a code fence",
    expect: { code: 0 },
    run: ({ hooksDir }) => withRepo((repo) => claim("Bad example:\n\n```\nThe deployment supports everything.\n```\n", repo, hooksDir)),
  },
  {
    name: "SILENT: an expired receipt is not a receipt (and re-fires)",
    expect: { code: 2, severity: "halt-and-report" },
    run: ({ hooksDir }) =>
      withRepo((repo) => {
        recordProbe(repo, hooksDir, { stdout: ANSWERED, command: LIVE_CMD });
        const dir = path.join(repo, ".coc-authz", "probe");
        for (const f of fs.readdirSync(dir)) {
          const p = path.join(dir, f);
          const rec = JSON.parse(fs.readFileSync(p, "utf8"));
          rec.expires_at = new Date(Date.now() - 1000).toISOString();
          fs.writeFileSync(p, JSON.stringify(rec));
        }
        return claim("The deployment supports scoped tool registration.", repo, hooksDir);
      }),
  },

  // ── THE RECORD ARM ITSELF ─────────────────────────────────────────────────
  {
    name: "RECORD: a probe run writes a receipt with the verdict the probe printed",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo((repo) => {
        recordProbe(repo, hooksDir, { stdout: UNDETERMINED, command: LIVE_CMD });
        const dir = path.join(repo, ".coc-authz", "probe");
        const files = fs.existsSync(dir) ? fs.readdirSync(dir) : [];
        if (files.length !== 1) return { code: -1, severity: `expected 1 receipt, found ${files.length}` };
        const rec = JSON.parse(fs.readFileSync(path.join(dir, files[0]), "utf8"));
        if (rec.verdict !== "undetermined") return { code: -1, severity: `verdict was '${rec.verdict}', not 'undetermined'` };
        if (rec.host !== "acme.aegis.io") return { code: -1, severity: `host was '${rec.host}'` };
        return { code: 0, severity: null };
      }),
  },
  {
    name: "RECORD: a non-probe command writes nothing",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo((repo) => {
        runHook(HOOK, post("Bash", { command: "pytest -q" }, { stdout: "ok" }), { cwd: repo, hooksDir });
        const dir = path.join(repo, ".coc-authz", "probe");
        return fs.existsSync(dir) ? { code: -1, severity: "wrote a receipt for a non-probe command" } : { code: 0, severity: null };
      }),
  },

  // ── ENVELOPE ───────────────────────────────────────────────────────────────
  { name: "FAIL-OPEN: malformed stdin", expect: { code: 0 }, run: ({ hooksDir }) => runHook(HOOK, "garbage", { hooksDir }) },
  { name: "FAIL-OPEN: unknown event", expect: { code: 0 }, run: ({ hooksDir }) => runHook(HOOK, { hook_event_name: "Nope", tool_name: "Write", tool_input: {} }, { hooksDir }) },
  {
    name: "FAIL-OPEN: budget spent before evaluation",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo((repo) =>
        runHook(HOOK, pre("Write", { file_path: path.join(repo, "n.md"), content: "The deployment supports it." }), {
          cwd: repo,
          hooksDir,
          env: { COC_PROBE_CLAIM_BUDGET_MS: "-1" },
        })
      ),
  },
];
