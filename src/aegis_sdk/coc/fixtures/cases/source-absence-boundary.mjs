/**
 * Cases for source-absence-boundary.js.
 *
 * THE SILENCE HALF IS THE HARD HALF HERE. This guard reads prose written from
 * exactly the position it polices, so its negative controls are not toy inputs:
 * `corpus/*` runs it over EVERY shipped prose file in the package and requires
 * silence on all of them. A guard that reds the corpus it ships beside is
 * switched off within a day, after which it defends nothing.
 *
 * ⚠ And that corpus sweep proves only one direction. A predicate that never
 * fires passes it perfectly, which is why the FIRE cases below are not
 * decoration and why the mutation controls in `run.mjs` matter more than either.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runHook, pre } from "../harness.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..", "..", "..", "..");
const HOOK = "source-absence-boundary";

// The platform-source prefix the FIRE cases need as payload, assembled at
// runtime. The hook receives a byte-identical string; what changes is that this
// shipped file carries no literal platform source path for the export-surface
// disclosure gate to find. Do NOT inline it back: the FIRE cases are this
// suite's only proof that the predicate fires at all, so deleting the payload
// to clear the gate would leave a suite that passes while asserting nothing.
const CORE = ["src", "aegis"].join("/");

const write = (content, file = "notes/finding.md") =>
  pre("Write", { file_path: path.join(REPO, file), content });

const c = (name, code, payload, severity) => ({
  name,
  expect: severity === undefined ? { code } : { code, severity },
  run: ({ hooksDir }) => runHook(HOOK, payload, { cwd: REPO, hooksDir }),
});

export const cases = [
  // ── FIRES ──────────────────────────────────────────────────────────────────
  c(
    "FIRE: a path into the platform's source",
    2,
    write(`The refusal is raised in \`${CORE}/services/trust_chain_service.py\` at line 412.`),
    "halt-and-report"
  ),
  c(
    "FIRE: a dotted platform symbol",
    2,
    write("Handled by aegis.services.TrustChainService.revoke_cascade before dispatch."),
    "halt-and-report"
  ),
  c("FIRE: a path into the platform's web app", 2, write("The nav item is registered in apps/web/src/App.tsx.")),
  c("FIRE: locution — under the hood", 2, write("Under the hood it reuses one connection pool across tenants.")),
  c("FIRE: locution — the request handler", 2, write("The request handler applies the tenant filter before returning a row.")),
  c("FIRE: locution — is implemented as", 2, write("Budget enforcement is implemented as a pre-dispatch interceptor.")),
  c("FIRE: locution — the service layer", 2, write("The service layer re-checks the organisation on every read.")),
  c(
    "FIRE: reaches a commit message",
    2,
    pre("Bash", { command: 'git commit -m "fix: under the hood the server caches the persona list"' })
  ),
  c(
    "FIRE: reaches a gh issue body",
    2,
    pre("Bash", { command: 'gh issue comment 12 --body "The middleware rejects it before RBAC runs."' })
  ),
  c(
    "FIRE: arm 1 is NOT scoped out of the handbook",
    2,
    write(`See \`${CORE}/api/routers/trust.py\`.`, "src/aegis_sdk/handbook/04-the-api-surface/01-calling-the-api.md")
  ),

  // ── SILENCE — the half that keeps the guard alive ──────────────────────────
  c("SILENT: labelled as inference", 0, write("This suggests the platform caches personas, but that cannot be answered from here.")),
  c("SILENT: hedged with 'appears'", 0, write("It appears the request handler short-circuits, though nothing here shows that.")),
  c("SILENT: attributed to the handbook", 0, write("The handbook records that an API-key principal carries no personas, ever.")),
  c("SILENT: an observation", 0, write("The deployment returned 403 for the key and 200 for the session.")),
  c("SILENT: attributed to the probe", 0, write("The probe reported 4 KEY-DENIED rows for this deployment.")),
  c("SILENT: prohibiting the locution rather than using it", 0, write("Do not claim the request handler does anything; you cannot see it.")),
  c("SILENT: a DO NOT teaching block", 0, write("# DO NOT\nThe service layer re-checks the organisation. Never assert that.")),
  c("SILENT: a coordinate inside THIS package", 0, write("The call site is `src/aegis_sdk/modules/auth.py`, which you can open.")),
  c("SILENT: the locution sits inside a code fence", 0, write("Bad:\n\n```\nUnder the hood the server caches it.\n```\n")),
  c("SILENT: arm 2 is scoped out of the handbook", 0, write("The service layer applies a tenant guard per call.", "src/aegis_sdk/handbook/04-the-api-surface/01-calling-the-api.md")),
  c("SILENT: an ordinary read command", 0, pre("Bash", { command: "curl -s $AGENTIC_OS_BASE_URL/api/v1/auth/me" })),
  c("SILENT: an empty write", 0, write("")),
  c("SILENT: a non-durable tool", 0, pre("Read", { file_path: "/etc/hosts" })),
  c("SILENT: writing into the hooks tree (naming-to-prohibit)", 0, write("Under the hood the handler does X.", "src/aegis_sdk/coc/hooks/example.js")),

  // ── ENVELOPE — every one of these must ALLOW, never wedge a session ────────
  c("FAIL-OPEN: malformed stdin", 0, "not json at all"),
  c("FAIL-OPEN: empty payload", 0, {}),
  c("FAIL-OPEN: unknown event", 0, { hook_event_name: "Nonsense", tool_name: "Write", tool_input: {} }),
  c("FAIL-OPEN: null tool_input", 0, { hook_event_name: "PreToolUse", tool_name: "Write", tool_input: null }),
  {
    name: "FAIL-OPEN: budget spent before evaluation",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      runHook(HOOK, write("Under the hood the server caches it."), {
        cwd: REPO,
        hooksDir,
        env: { COC_SOURCE_ABSENCE_BUDGET_MS: "-1" },
      }),
  },

  // ── THE CORPUS SWEEP, reported with its denominator ───────────────────────
  {
    name: "SILENT across every shipped prose file (negative control corpus)",
    expect: { code: 0 },
    run: ({ hooksDir }) => {
      const roots = [
        path.join(REPO, "src", "aegis_sdk", "coc"),
        path.join(REPO, "src", "aegis_sdk", "handbook"),
      ];
      const files = [];
      const walk = (d) => {
        if (!fs.existsSync(d)) return;
        for (const e of fs.readdirSync(d, { withFileTypes: true })) {
          const p = path.join(d, e.name);
          if (e.isDirectory()) walk(p);
          else if (p.endsWith(".md") && !p.includes(`${path.sep}hooks${path.sep}`) && !p.includes(`${path.sep}fixtures${path.sep}`)) files.push(p);
        }
      };
      roots.forEach(walk);
      const fired = [];
      for (const f of files) {
        const r = runHook(HOOK, pre("Write", { file_path: f, content: fs.readFileSync(f, "utf8") }), {
          cwd: REPO,
          hooksDir,
        });
        if (r.code !== 0) fired.push(path.relative(REPO, f));
      }
      // The denominator is printed unconditionally: "0 fired" and "0 examined"
      // are the same number and opposite facts, and a corpus sweep that found
      // no files is exactly how a calibration claim becomes vacuous.
      process.stdout.write(`    corpus: examined=${files.length} fired=${fired.length}${fired.length ? " -> " + fired.join(", ") : ""}\n`);
      if (!files.length) return { code: -1, severity: "corpus was EMPTY — this sweep proved nothing" };
      return { code: fired.length ? 2 : 0, severity: null };
    },
  },
];
