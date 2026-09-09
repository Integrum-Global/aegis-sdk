/**
 * command-lifecycle-derivation — fixtures for the derivation that produces the
 * command set.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT IS UNDER TEST, AND WHY THE POLARITIES ARE NOT SYMMETRIC IN VALUE
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * The gate answers two questions that fail in opposite directions:
 *
 *   FORWARD   a stage the architect can drive, with no command to drive it
 *   BACKWARD  a command that reaches no CLI, or names a stage that is not there
 *
 * A gate that only asked the forward question would pass a command set that
 * exists in the source and appears in no CLI — which is exactly how an artifact
 * ships inert. Both are pinned here.
 *
 * ⛔ THE SILENCE CASES ARE THE ONES THAT MATTER MOST, and one of them carries
 * the whole design: a stage the derivation found NOT drivable must produce
 * SILENCE, not a demand for a command. Get that wrong and the gate insists on a
 * command for a part of the book that has no session work in it — after which
 * somebody writes one to clear the red, and the gate has manufactured the
 * artifact it was supposed to audit.
 *
 * Every case builds a THROWAWAY tree. Nothing reads the real one except the
 * final case, which asserts the shipped tree is green — and that case is the
 * one that would catch a stage arriving with nothing to drive it.
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, "..");
const COC = path.resolve(FIXTURES, "..");
const REPO = path.resolve(COC, "..", "..", "..");
const LIFECYCLE = path.join(COC, "lifecycle.mjs");
const DRIVER = path.join(FIXTURES, "lifecycle-driver.mjs");

/** Run a derivation against `root`, in a real process. */
function drive(root, { lifecycle = LIFECYCLE, overlays = false } = {}) {
  try {
    execFileSync("node", [DRIVER, lifecycle, root, overlays ? "1" : "0"], { encoding: "utf8", timeout: 30000 });
    return { code: 0, stderr: "" };
  } catch (e) {
    return { code: typeof e.status === "number" ? e.status : -1, stderr: String(e.stderr || "") };
  }
}

// ───────────────────────────── tree builder ──────────────────────────────────

const write = (root, rel, body) => {
  const abs = path.join(root, rel);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, body);
};

/** A chapter that is drivable: one python fence and one client surface. */
const DRIVABLE_CHAPTER = "# 01.1 — A chapter\n\nUse `client.units` for this.\n\n```python\nawait client.units.list()\n```\n";
/** A chapter that is not: prose only, exactly like the console part. */
const PROSE_CHAPTER = "# 05.1 — A screen\n\nClick the thing in the corner. There is no code here.\n";

const command = (name, stage, extra = "") =>
  `---\nname: ${name}\ndescription: "does a thing"\n${stage === null ? "" : `stage: ${stage}\n`}---\n\nBody.\n${extra}`;

/**
 * A tree that MUST be green: two drivable stages each with a command, one
 * non-drivable stage with none, and every command projected to all three CLIs.
 */
function healthyTree({ overlays = true } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "coc-lifecycle-"));
  write(root, "src/aegis_sdk/handbook/01-orientation/01-a.md", DRIVABLE_CHAPTER);
  write(root, "src/aegis_sdk/handbook/02-harness/01-a.md", DRIVABLE_CHAPTER);
  write(root, "src/aegis_sdk/handbook/05-console/01-a.md", PROSE_CHAPTER);
  // Not a part: no NN- prefix. A derivation that counted this would find a
  // stage in the asset directory.
  write(root, "src/aegis_sdk/handbook/assets/note.md", DRIVABLE_CHAPTER);
  write(root, "src/aegis_sdk/coc/agents/an-agent.md", "---\nname: an-agent\ndescription: x\n---\n");
  for (const [name, stage] of [["orient", "01-orientation"], ["construct", "02-harness"]]) {
    write(root, `src/aegis_sdk/coc/commands/${name}.md`, command(name, stage));
    if (overlays) {
      write(root, `.claude/commands/${name}.md`, "projected");
      write(root, `.codex/prompts/${name}.md`, "projected");
      write(root, `.gemini/commands/${name}.toml`, "projected");
    }
  }
  return root;
}

/** Build the healthy tree, then break it, and return the broken root. */
function broken(mutate, opts) {
  const root = healthyTree(opts);
  mutate(root);
  return root;
}

const rm = (root) => fs.rmSync(root, { recursive: true, force: true });

/** A case that drives a tree and reports the derivation's verdict as an exit code. */
const treeCase = (name, build, expectCode, opts = {}) => ({
  name,
  expect: { code: expectCode },
  run() {
    const root = build();
    try {
      return drive(root, opts);
    } finally {
      rm(root);
    }
  },
});

// ───────────────────────────── mutation controls ─────────────────────────────

/**
 * Break ONE line of the derivation in a copy, and require that a tree the real
 * derivation REDS goes GREEN under the mutation.
 *
 * The `reached` assertion is the half that makes this a control rather than a
 * ritual. Without it, a typo in `find` mutates nothing, the mutated copy behaves
 * exactly like the original, and the case reports the line load-bearing on the
 * strength of a change that never happened. A mutation that changed nothing is
 * INERT and proves neither vacuity nor coverage.
 */
const mutationControl = (name, { find, replace, build, overlays = false }) => ({
  name: `mutation control — ${name}`,
  expect: { code: 0 },
  run() {
    const src = fs.readFileSync(LIFECYCLE, "utf8");
    if (!src.includes(find)) {
      process.stderr.write(`INERT: the text to mutate was not found — this proves NOTHING\n  ${find}\n`);
      return { code: 2, severity: null };
    }
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "coc-lifecycle-mut-"));
    const mutated = path.join(tmp, "lifecycle.mjs");
    fs.writeFileSync(mutated, src.split(find).join(replace));
    const root = build();
    try {
      const real = drive(root, { overlays });
      const broke = drive(root, { lifecycle: mutated, overlays });
      // The control is satisfied only when the real derivation objected and the
      // mutated one did not. Either half alone is consistent with a check that
      // never ran.
      if (real.code !== 2) {
        process.stderr.write(`the unmutated derivation did NOT object to this tree — the case is not testing what it claims\n`);
        return { code: 2, severity: null };
      }
      if (broke.code === 2) {
        process.stderr.write(`the mutation reached the code and the derivation still objected — that line is not what enforces this\n`);
        return { code: 2, severity: null };
      }
      return { code: 0, severity: null };
    } finally {
      rm(root);
      rm(tmp);
    }
  },
});

// ───────────────────────────── the cases ─────────────────────────────────────

export const cases = [
  // ── SILENCE: the shapes that must NOT be reported ──────────────────────────
  treeCase("silence: healthy tree, every drivable stage covered and projected", () => healthyTree(), 0, { overlays: true }),

  treeCase(
    "silence: a NON-drivable stage with no command is not a finding",
    // The console stage is present in every healthy tree and has no command.
    // This is the design, not an omission, and the gate must not ask for one.
    () => healthyTree(),
    0
  ),

  treeCase(
    "silence: two commands may serve one stage",
    () =>
      broken((root) => {
        fs.writeFileSync(
          path.join(root, "src/aegis_sdk/coc/commands/orient-again.md"),
          command("orient-again", "01-orientation")
        );
        for (const p of [".claude/commands/orient-again.md", ".codex/prompts/orient-again.md", ".gemini/commands/orient-again.toml"])
          write(root, p, "projected");
      }),
    0,
    { overlays: true }
  ),

  treeCase(
    "silence: a directory without a NN- prefix is not a stage",
    // `handbook/assets/` holds a drivable-looking file in every tree above. If
    // it were counted, every tree here would demand a fifth command.
    () => healthyTree(),
    0,
    { overlays: true }
  ),

  // ── FIRING: forward direction — a stage with nothing to drive it ───────────
  treeCase(
    "fires: a drivable stage has no command",
    () => broken((root) => fs.rmSync(path.join(root, "src/aegis_sdk/coc/commands/construct.md"))),
    2
  ),

  treeCase(
    "fires: a new drivable stage arrives with nothing to drive it",
    // The case the whole derivation exists for: a part is added, and no list
    // anywhere had to be updated for the gate to notice.
    () => broken((root) => write(root, "src/aegis_sdk/handbook/03-extending/01-a.md", DRIVABLE_CHAPTER)),
    2
  ),

  // ── FIRING: backward direction — a command that does not correspond ────────
  treeCase(
    "fires: a command names a stage that is not a handbook part",
    () =>
      broken((root) =>
        fs.writeFileSync(path.join(root, "src/aegis_sdk/coc/commands/orient.md"), command("orient", "99-invented"))
      ),
    2
  ),

  treeCase(
    "fires: a command names a stage the derivation found NOT drivable",
    () =>
      broken((root) =>
        fs.writeFileSync(path.join(root, "src/aegis_sdk/coc/commands/orient.md"), command("orient", "05-console"))
      ),
    2
  ),

  treeCase(
    "fires: a command declares no stage at all",
    () => broken((root) => fs.writeFileSync(path.join(root, "src/aegis_sdk/coc/commands/orient.md"), command("orient", null))),
    2
  ),

  treeCase(
    "fires: frontmatter name disagrees with the filename",
    () =>
      broken((root) =>
        fs.writeFileSync(path.join(root, "src/aegis_sdk/coc/commands/orient.md"), command("something-else", "01-orientation"))
      ),
    2
  ),

  treeCase(
    "fires: a command body is over the line ceiling",
    () =>
      broken((root) =>
        fs.writeFileSync(
          path.join(root, "src/aegis_sdk/coc/commands/orient.md"),
          command("orient", "01-orientation", "x\n".repeat(200))
        )
      ),
    2
  ),

  treeCase(
    "fires: a command name collides with a projected persona prompt",
    () => {
      const root = healthyTree({ overlays: false });
      write(root, "src/aegis_sdk/coc/commands/specialist-an-agent.md", command("specialist-an-agent", "01-orientation"));
      return root;
    },
    2
  ),

  // ── FIRING: the projection reach, one CLI at a time ────────────────────────
  // Separately, because a check that only ever saw all three missing together
  // would pass a projector that reached two of them.
  ...["claude/commands/orient.md", "codex/prompts/orient.md", "gemini/commands/orient.toml"].map((rel) =>
    treeCase(
      `fires: a command is not projected for ${rel.split("/")[0]}`,
      () => broken((root) => fs.rmSync(path.join(root, "." + rel))),
      2,
      { overlays: true }
    )
  ),

  // ── MUTATION CONTROLS ─────────────────────────────────────────────────────
  mutationControl("the drivability predicate stops discriminating", {
    find: "const warranted = python > 0 && surfaces.size > 0;",
    replace: "const warranted = true;",
    // Under the mutation the console stage becomes drivable, so a command
    // pointing at it is no longer an error and the tree goes green.
    //
    // The command is ADDED rather than repointed, and that detail was not a
    // choice — the first version of this control moved `orient` onto the
    // console stage, which left `01-orientation` uncovered. The mutated
    // derivation then still objected, for a reason that had nothing to do with
    // the mutated line, and the control correctly refused to certify it. A
    // control whose tree has two problems cannot attribute the red to either.
    build: () =>
      broken((root) => write(root, "src/aegis_sdk/coc/commands/browse.md", command("browse", "05-console"))),
  }),

  mutationControl("the forward check stops asking for a command", {
    find: "if (s.warranted && !byStage.has(s.id)) {",
    replace: "if (false) {",
    build: () => broken((root) => fs.rmSync(path.join(root, "src/aegis_sdk/coc/commands/construct.md"))),
  }),

  mutationControl("the projection reach check stops looking", {
    find: "if (!fs.existsSync(path.join(root, rel))) {",
    replace: "if (false) {",
    build: () => broken((root) => fs.rmSync(path.join(root, ".claude/commands/orient.md"))),
    overlays: true,
  }),

  // ── THE SHIPPED TREE ──────────────────────────────────────────────────────
  {
    name: "the shipped tree derives green",
    expect: { code: 0 },
    // Overlays OFF: in this repository the neutral source is what exists, and
    // the overlays are produced by the projector into the assembled tree. The
    // projector runs the reach check itself, against the map it is about to
    // write — which is a stronger question than "does a file exist", because it
    // is answerable before anything has been written.
    run: () => drive(REPO, { overlays: false }),
  },
];
