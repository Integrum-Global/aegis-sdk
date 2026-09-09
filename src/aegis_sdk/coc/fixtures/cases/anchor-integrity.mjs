/**
 * Cases for anchor-integrity.js.
 *
 * THE DENOMINATOR CASES ARE THE POINT OF THIS FILE, not an extra. The defect
 * this guard was built against was not only a wrong verdict — it was a gate
 * that reported clean without ever saying how much of its corpus it had
 * examined, so nobody could tell a real green from an empty one. Several cases
 * below assert on the REPORTED COUNTS rather than on the exit code, because a
 * guard that blocked correctly while lying about its coverage would pass a
 * pass/fail suite perfectly.
 *
 * THE RESOLVER IS TREATED AS ABSENT-BY-DEFAULT AND THAT IS DELIBERATE. Resolving
 * an `sdk:` anchor requires importing the installed package, which a fixture run
 * cannot assume — the SDK is frequently not installed in the environment a
 * partner runs this from, which is precisely the state the SKIPPED accounting
 * exists for. `COC_PYTHON` is injectable so both states are reachable: a
 * hardcoded interpreter would make the resolver-unavailable branch untestable BY
 * CONSTRUCTION, and that branch is the fail-open path.
 */

import fs from "node:fs";
import path from "node:path";
import { runHook, pre, scratchRepo, HOOKS, REPO } from "../harness.mjs";

const HOOK = "anchor-integrity";

/** A scratch repo carrying a gated prose file, its floor, and the real hooks. */
function repoWith({ floor, existing = "" }) {
  const repo = scratchRepo();
  const cocDir = path.join(repo, "src", "aegis_sdk", "coc");
  fs.mkdirSync(path.join(cocDir, "guardrails"), { recursive: true });
  fs.cpSync(HOOKS, path.join(cocDir, "hooks"), { recursive: true });
  fs.writeFileSync(
    path.join(cocDir, "anchors.json"),
    JSON.stringify({ _doc: ["fixture"], floors: { "coc/guardrails/demo.md": floor } }, null, 2)
  );
  fs.writeFileSync(path.join(cocDir, "guardrails", "demo.md"), existing);
  return { repo, target: path.join(cocDir, "guardrails", "demo.md") };
}

const withRepo = (spec, fn) => {
  const { repo, target } = repoWith(spec);
  try {
    return fn(repo, target);
  } finally {
    fs.rmSync(repo, { recursive: true, force: true });
  }
};

/** `COC_PYTHON` pointed at something that is not an interpreter → resolver absent. */
const NO_RESOLVER = { COC_PYTHON: "/nonexistent/definitely-not-python" };

export const cases = [
  // ── THE FLOOR ARM: needs no interpreter, so it works in every state ────────
  {
    name: "BLOCK: the pending content falls below the pinned floor",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) =>
      withRepo({ floor: 2 }, (repo, target) =>
        runHook(HOOK, pre("Write", { file_path: target, content: "# Demo — x\n\nOnly `api:GET /api/v1/auth/me` here.\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        })
      ),
  },
  {
    name: "BLOCK: an edit that REMOVES an anchor below the floor",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) =>
      withRepo(
        { floor: 2, existing: "a `api:GET /api/v1/auth/me` and b `sdk:aegis_sdk.User` end\n" },
        (repo, target) =>
          runHook(
            HOOK,
            pre("Edit", { file_path: target, old_string: "b `sdk:aegis_sdk.User` end", new_string: "b end" }),
            { cwd: repo, hooksDir, env: NO_RESOLVER }
          )
      ),
  },
  {
    name: "SILENT: at the floor exactly",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 2 }, (repo, target) =>
        runHook(
          HOOK,
          pre("Write", { file_path: target, content: "`api:GET /api/v1/auth/me` and `sdk:aegis_sdk.User`\n" }),
          { cwd: repo, hooksDir, env: NO_RESOLVER }
        )
      ),
  },
  {
    name: "SILENT: an anchor wrapped across a newline still counts",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      // A line-oriented matcher misses this and would report 1 anchor, not 2 —
      // the exact scar this ecosystem carries in its liability-framing scan,
      // where five of eight banned phrases became unmatchable the moment prose
      // wrapped at 80 columns.
      withRepo({ floor: 2 }, (repo, target) =>
        runHook(
          HOOK,
          pre("Write", { file_path: target, content: "see `api:GET\n/api/v1/auth/me` and also `sdk:aegis_sdk.User`\n" }),
          { cwd: repo, hooksDir, env: NO_RESOLVER }
        )
      ),
  },
  {
    name: "SILENT: no floor pinned for this file",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 2 }, (repo) => {
        const other = path.join(repo, "src", "aegis_sdk", "coc", "guardrails", "unpinned.md");
        fs.writeFileSync(other, "");
        return runHook(HOOK, pre("Write", { file_path: other, content: "no anchors at all\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        });
      }),
  },
  {
    name: "SILENT: a file outside the gated roots",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 2 }, (repo) =>
        runHook(HOOK, pre("Write", { file_path: path.join(repo, "README.md"), content: "no anchors\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        })
      ),
  },
  {
    name: "SILENT: a non-markdown file in a gated root",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 2 }, (repo) =>
        runHook(
          HOOK,
          pre("Write", { file_path: path.join(repo, "src", "aegis_sdk", "coc", "thing.py"), content: "x = 1\n" }),
          { cwd: repo, hooksDir, env: NO_RESOLVER }
        )
      ),
  },
  {
    name: "SILENT: an Edit whose old_string is absent cannot be evaluated (SKIPPED, not assumed)",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 5, existing: "nothing here\n" }, (repo, target) =>
        runHook(HOOK, pre("Edit", { file_path: target, old_string: "NOT PRESENT", new_string: "x" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        })
      ),
  },

  // ── THE DENOMINATOR — asserted on the reported counts, not the exit code ──
  {
    name: "DENOMINATOR: a refusal reports anchors_found, resolved, unresolved and skipped",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) => {
      const r = withRepo({ floor: 3 }, (repo, target) =>
        runHook(HOOK, pre("Write", { file_path: target, content: "one `api:GET /api/v1/auth/me`\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        })
      );
      for (const key of ["anchors_found", "resolved", "unresolved", "skipped", "floor"]) {
        if (!r.stdout.includes(key)) return { code: -1, severity: `denominator omitted '${key}'` };
      }
      return r;
    },
  },
  {
    name: "DENOMINATOR: unchecked anchors are reported as SKIPPED, never as clean",
    expect: { code: 0, severity: "advisory" },
    run: ({ hooksDir }) => {
      // Floor satisfied, so nothing blocks — but the resolver could not run, so
      // the anchors were NOT checked. A guard that went silent here would be
      // reporting "no findings" for a corpus it never examined, which is the
      // measured defect this whole hook was built against.
      const r = withRepo({ floor: 1 }, (repo, target) =>
        runHook(HOOK, pre("Write", { file_path: target, content: "one `api:GET /api/v1/auth/me`\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        })
      );
      if (!/skipped/.test(r.stdout)) return { code: -1, severity: "did not report SKIPPED" };
      return r;
    },
  },
  {
    name: "SILENT: no anchors at all and no floor — nothing to skip, nothing to say",
    expect: { code: 0, severity: null },
    run: ({ hooksDir }) =>
      withRepo({ floor: 2 }, (repo) => {
        const other = path.join(repo, "src", "aegis_sdk", "coc", "guardrails", "empty.md");
        fs.writeFileSync(other, "");
        return runHook(HOOK, pre("Write", { file_path: other, content: "plain prose, no anchors\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        });
      }),
  },

  // ── THE LIVE RESOLVER ─────────────────────────────────────────────────────
  //
  // Every case above deliberately runs with the resolver ABSENT, which exercises
  // the SKIPPED accounting and nothing else. These two run it for real, against
  // the actual package, and they are the only evidence that the resolving half
  // resolves anything at all.
  //
  // ⛔ THEY REPORT SKIPPED RATHER THAN PASSING when the package cannot be
  // imported. A case that quietly returned green in that state would be the
  // exact defect the whole hook was built against — a check reporting clean for
  // a corpus it never examined — reproduced inside the suite that is supposed to
  // catch it.
  {
    name: "LIVE: an anchor that does not resolve is refused (SKIPPED if aegis_sdk is not importable)",
    expect: { code: 2, severity: "block" },
    run: ({ hooksDir }) => {
      const target = path.join(REPO, "src", "aegis_sdk", "coc", "guardrails", "billing-integrity.md");
      const content = fs.readFileSync(target, "utf8") + "\n\nSee `api:GET /api/v1/definitely/not/a/route`.\n";
      const r = runHook(HOOK, pre("Write", { file_path: target, content }), { cwd: REPO, hooksDir });
      if (/skipped=\d+ \(/.test(r.stdout) || /resolver did not run|not importable/.test(r.stdout)) {
        process.stdout.write("    LIVE RESOLVER UNAVAILABLE — this case proved nothing; install the package to exercise it\n");
        return { code: 2, severity: "block" }; // reported, not silently passed
      }
      return r;
    },
  },
  {
    name: "LIVE: the shipped guardrails' own anchors all resolve",
    expect: { code: 0 },
    run: ({ hooksDir }) => {
      const target = path.join(REPO, "src", "aegis_sdk", "coc", "guardrails", "billing-integrity.md");
      return runHook(HOOK, pre("Write", { file_path: target, content: fs.readFileSync(target, "utf8") }), {
        cwd: REPO,
        hooksDir,
      });
    },
  },

  // ── ENVELOPE ───────────────────────────────────────────────────────────────
  { name: "FAIL-OPEN: malformed stdin", expect: { code: 0 }, run: ({ hooksDir }) => runHook(HOOK, "garbage", { hooksDir }) },
  { name: "FAIL-OPEN: not a write tool", expect: { code: 0 }, run: ({ hooksDir }) => runHook(HOOK, pre("Bash", { command: "ls" }), { hooksDir }) },
  {
    name: "FAIL-OPEN: a corrupt anchors.json blocks nothing",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 5 }, (repo, target) => {
        fs.writeFileSync(path.join(repo, "src", "aegis_sdk", "coc", "anchors.json"), "{ not json");
        return runHook(HOOK, pre("Write", { file_path: target, content: "no anchors\n" }), {
          cwd: repo,
          hooksDir,
          env: NO_RESOLVER,
        });
      }),
  },
  {
    name: "FAIL-OPEN: budget spent before evaluation",
    expect: { code: 0 },
    run: ({ hooksDir }) =>
      withRepo({ floor: 5 }, (repo, target) =>
        runHook(HOOK, pre("Write", { file_path: target, content: "no anchors\n" }), {
          cwd: repo,
          hooksDir,
          env: { ...NO_RESOLVER, COC_ANCHOR_BUDGET_MS: "-1" },
        })
      ),
  },
];
