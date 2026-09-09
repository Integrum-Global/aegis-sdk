#!/usr/bin/env node
/**
 * lifecycle.mjs — DERIVE the architect's lifecycle, and the command surface
 * that discharges it, from the material this repository already ships.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS EXISTS AS A DERIVATION AND NOT AS A LIST
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * A hand-written "these are the commands" list is right on the day it is typed
 * and silently wrong afterwards. It cannot tell you that a lifecycle stage
 * arrived with nothing to drive it, and it cannot tell you that a command is
 * addressing a stage that no longer exists. Both failures read as a clean set.
 *
 * So the stage set is not written down anywhere. It is READ OFF THE HANDBOOK,
 * and the commands declare which stage they serve. The gate compares the two
 * and reds when they disagree — in EITHER direction.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE DERIVATION, AND WHAT EACH STEP IS ENTITLED TO CONCLUDE
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * STAGES.  Each `handbook/NN-<slug>/` directory is one stage of the architect's
 * engagement with a deployment, in the order the number gives. This is a
 * FILESYSTEM fact, not a reading of prose: a part exists or it does not, and a
 * new part cannot arrive without this derivation seeing it.
 *
 * WARRANTED.  A stage warrants a command when the architect can actually DRIVE
 * it from a session — measured, not assumed, as the conjunction of two counts
 * over the stage's own chapters:
 *
 *     python_blocks    ```python fences        an executable path exists
 *     client_surfaces  `client.<name>` tokens  it goes through this client
 *
 * Both are required, and the conjunction is what makes the predicate honest: a
 * chapter can name a client surface while only describing it, and a chapter can
 * carry a code fence that configures rather than drives. Neither alone
 * establishes that a session can do the work.
 *
 * This predicate is DISCRIMINATING on the tree it was written against, which is
 * the only reason it is allowed to be the gate: four parts measure 5, 29, 35 and
 * 25 python blocks against 15, 16, 10 and 9 client surfaces; the console part
 * measures ZERO of both, because it is written entirely from the running
 * application and there is no harness path in it to drive. A predicate that
 * returned the same answer for every part would be decorative.
 *
 * COMMANDS.  Every command declares its stage in its own frontmatter. The
 * mapping lives BESIDE THE ARTIFACT, never in a table inside this file — a
 * table here would be the hand-written list this derivation exists to replace,
 * one indirection further away.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHAT THIS CANNOT DO — carried openly rather than discovered later
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * It cannot tell you a stage is MISSING from the handbook. The handbook is the
 * denominator here, so work the architect genuinely does that no part describes
 * is invisible to this derivation and will be reported as complete. Two such
 * gaps were found by hand while writing it and are recorded in the audit output
 * as `unreachable_surfaces`, derived by subtracting the surfaces the handbook
 * names from the surfaces the client actually exposes — which is the one part
 * of that blind spot a measurement can reach.
 *
 * It also cannot tell you a command is GOOD. It establishes that a command
 * exists for every drivable stage and that each command reaches every CLI
 * overlay. Whether the body is worth reading is not a property any derivation
 * recovers.
 *
 *     node src/aegis_sdk/coc/lifecycle.mjs            # the derivation, as a table
 *     node src/aegis_sdk/coc/lifecycle.mjs --json     # the same, machine-readable
 *     node src/aegis_sdk/coc/lifecycle.mjs --check    # exit 1 on any disagreement
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** `client.<surface>` as it appears in prose and in code fences alike. */
const CLIENT_SURFACE = /\bclient\.([a-z_][a-z_0-9]*)/g;
const PYTHON_FENCE = /```python/g;
const PART_DIR = /^(\d\d)-(.+)$/;

const read = (p) => fs.readFileSync(p, "utf8");
const listMd = (dir) =>
  fs.existsSync(dir)
    ? fs
        .readdirSync(dir)
        .filter((f) => f.endsWith(".md") && f !== "README.md")
        .sort()
    : [];

/**
 * The overlay paths one command name must reach, for all three CLIs.
 *
 * CODEX TAKES A PROMPT, NOT A COMMAND, and that asymmetry is the projector's
 * existing precedent for agents rather than a new invention here: Codex has no
 * command registry, so a command projects to `prompts/` exactly as a persona
 * does. Gemini takes TOML rather than Markdown. A projection that assumed one
 * layout for all three would write two files no CLI ever reads, and nothing
 * would fail — the command would simply never appear, which is indistinguishable
 * from a command that was never written.
 */
export function overlayPaths(name) {
  return {
    claude: `.claude/commands/${name}.md`,
    codex: `.codex/prompts/${name}.md`,
    gemini: `.gemini/commands/${name}.toml`,
  };
}

/** Minimal frontmatter reader: `key: value` pairs in a leading `---` block. */
export function frontmatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { fm: null, body: text };
  const fm = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^([A-Za-z_-]+):\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].replace(/^"(.*)"$/, "$1").trim();
  }
  return { fm, body: text.slice(m[0].length) };
}

/**
 * The lifecycle stages, derived from the handbook's part directories.
 *
 * Ordered by the part number, which is the handbook's own statement of
 * sequence. Nothing here is keyed on a part's TITLE: titles are prose and get
 * rewritten, and a derivation that broke when a heading was reworded would be
 * abandoned the first time it did so.
 */
export function deriveStages(root) {
  const hb = path.join(root, "src", "aegis_sdk", "handbook");
  if (!fs.existsSync(hb)) return [];
  const stages = [];
  for (const dir of fs.readdirSync(hb).sort()) {
    const m = dir.match(PART_DIR);
    if (!m || !fs.statSync(path.join(hb, dir)).isDirectory()) continue;
    const chapters = listMd(path.join(hb, dir));
    let python = 0;
    const surfaces = new Set();
    for (const f of chapters) {
      const raw = read(path.join(hb, dir, f));
      python += (raw.match(PYTHON_FENCE) || []).length;
      for (const s of raw.matchAll(CLIENT_SURFACE)) surfaces.add(s[1]);
    }
    const warranted = python > 0 && surfaces.size > 0;
    stages.push({
      id: dir,
      index: m[1],
      slug: m[2],
      chapters: chapters.length,
      python_blocks: python,
      client_surfaces: [...surfaces].sort(),
      warranted,
      // The reason is DERIVED from the same counts the verdict is, so it can
      // never disagree with it. A hand-written reason beside a computed verdict
      // is the pair that goes stale first.
      reason: warranted
        ? `drivable: ${python} python example(s) over ${surfaces.size} client surface(s)`
        : `NOT drivable from a session: ${python} python example(s), ${surfaces.size} client surface(s)` +
          ` — nothing here is driven through this client, so there is no session work for a command to order`,
    });
  }
  return stages;
}

/** Every command in the neutral source, with the stage it claims. */
export function readCommands(root) {
  const dir = path.join(root, "src", "aegis_sdk", "coc", "commands");
  const out = [];
  for (const f of listMd(dir)) {
    const raw = read(path.join(dir, f));
    const { fm, body } = frontmatter(raw);
    out.push({
      file: `src/aegis_sdk/coc/commands/${f}`,
      name: fm?.name ?? f.replace(/\.md$/, ""),
      declared_name: fm?.name ?? null,
      description: fm?.description ?? null,
      stage: fm?.stage ?? null,
      body,
      lines: body.split("\n").length,
    });
  }
  return out;
}

/** The client surfaces this package exposes but the handbook never names. */
function unreachableSurfaces(root, stages) {
  const clientPy = path.join(root, "src", "aegis_sdk", "client.py");
  if (!fs.existsSync(clientPy)) return null;
  // TOP-LEVEL client attributes only, identified by the transport they are
  // handed: the client's own surfaces take `self._http`, while the nested
  // groups (reached as `client.<group>.<surface>`) take a passed-in
  // `http_client`. Measured on this tree: 55 and 19.
  //
  // TWO NARROWER INSTRUMENTS WERE TRIED AND BOTH REFUTED, by the size of the
  // answer they gave rather than by inspection. Comparing module FILENAMES to
  // attribute names reported 27 of 37 unreachable, because `client.units` lives
  // in `organization_units.py`. Taking EVERY `self.x =` in the file reported 49,
  // because it counted nested surfaces the handbook names through their group.
  // A number that large is the tell; both were replaced rather than tuned.
  const exposed = new Set(
    [...read(clientPy).matchAll(/^\s+self\.([a-z_][a-z_0-9]*)\s*=\s*[A-Za-z_]+\(\s*self\._http/gm)]
      .map((m) => m[1])
      .filter((n) => !n.startsWith("_"))
  );
  const named = new Set(stages.flatMap((s) => s.client_surfaces));
  return [...exposed].filter((s) => !named.has(s)).sort();
}

/**
 * The gate. Every problem is a DISAGREEMENT between two independently derived
 * sets, never a violation of a rule written here.
 *
 * `overlays` is off by default because the neutral source is checkable on its
 * own, before anything has been projected; the projector turns it on after it
 * writes, where "did this command actually reach all three CLIs" is a question
 * with an answer.
 */
export function auditLifecycle(root, { overlays = false, maxBodyLines = 150 } = {}) {
  const stages = deriveStages(root);
  const commands = readCommands(root);
  const problems = [];

  if (!stages.length) problems.push("no handbook parts found — the lifecycle cannot be derived from this tree");

  const byStage = new Map();
  for (const c of commands) {
    if (!c.declared_name) {
      problems.push(`${c.file}: no 'name' in frontmatter`);
    } else if (c.declared_name !== path.basename(c.file, ".md")) {
      problems.push(`${c.file}: frontmatter name '${c.declared_name}' does not match the filename`);
    }
    if (!c.description) problems.push(`${c.file}: no 'description' in frontmatter`);
    if (!c.stage) {
      // The one thing a command may not do is decline to say what it is for.
      // Without the declaration this gate has nothing to join on, and a command
      // nothing joins to is exactly the artifact that survives its own stage.
      problems.push(`${c.file}: no 'stage' in frontmatter — the gate has nothing to join it to`);
    } else {
      const stage = stages.find((s) => s.id === c.stage);
      if (!stage) {
        problems.push(`${c.file}: declares stage '${c.stage}', which is not a handbook part`);
      } else if (!stage.warranted) {
        problems.push(
          `${c.file}: declares stage '${c.stage}', which the derivation found NOT drivable (${stage.reason})`
        );
      } else {
        if (!byStage.has(stage.id)) byStage.set(stage.id, []);
        byStage.get(stage.id).push(c);
      }
    }
    if (c.lines > maxBodyLines) {
      problems.push(`${c.file}: body is ${c.lines} lines, over the ${maxBodyLines}-line ceiling — put the depth in a skill`);
    }
  }

  for (const s of stages) {
    if (s.warranted && !byStage.has(s.id)) {
      problems.push(`stage '${s.id}' is drivable (${s.reason}) but no command declares it`);
    }
  }

  // A command whose name collides with a projected persona would overwrite it
  // in `.codex/prompts/`, where both land. Personas are written there as
  // `specialist-<name>`, so the collision is narrow and worth naming exactly.
  const agentDir = path.join(root, "src", "aegis_sdk", "coc", "agents");
  for (const a of listMd(agentDir)) {
    const persona = `specialist-${a.replace(/\.md$/, "")}`;
    for (const c of commands) {
      if (c.name === persona) problems.push(`${c.file}: name collides with the projected persona prompt '${persona}.md'`);
    }
  }

  if (overlays) {
    for (const c of commands) {
      for (const [cli, rel] of Object.entries(overlayPaths(c.name))) {
        if (!fs.existsSync(path.join(root, rel))) {
          problems.push(`${c.file}: not projected for ${cli} — ${rel} is missing`);
        }
      }
    }
  }

  return {
    stages,
    commands: commands.map(({ body, ...rest }) => rest),
    coverage: stages.map((s) => ({
      stage: s.id,
      warranted: s.warranted,
      commands: (byStage.get(s.id) || []).map((c) => c.name),
      reason: s.warranted ? undefined : s.reason,
    })),
    unreachable_surfaces: unreachableSurfaces(root, stages),
    problems,
  };
}

// ───────────────────────────── CLI ───────────────────────────────────────────

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
  const audit = auditLifecycle(root, { overlays: process.argv.includes("--overlays") });
  if (process.argv.includes("--json")) {
    console.log(JSON.stringify(audit, null, 2));
  } else {
    console.log("LIFECYCLE STAGES — derived from src/aegis_sdk/handbook/\n");
    console.log("  stage                             ch   py  surf  command(s)");
    for (const s of audit.stages) {
      const cmds = audit.coverage.find((c) => c.stage === s.id)?.commands ?? [];
      console.log(
        "  " + s.id.padEnd(34) +
          String(s.chapters).padStart(2) + String(s.python_blocks).padStart(5) +
          String(s.client_surfaces.length).padStart(6) + "  " +
          (s.warranted ? cmds.join(", ") || "(none)" : "— no command: " + s.reason.split(" — ")[1])
      );
    }
    if (audit.unreachable_surfaces?.length) {
      console.log(
        `\n  client surfaces the handbook never names (${audit.unreachable_surfaces.length}): ` +
          audit.unreachable_surfaces.join(", ") +
          "\n  Not a defect in the command set — a stage this derivation cannot see."
      );
    }
    console.log(
      `\n  ${audit.stages.filter((s) => s.warranted).length} drivable stage(s) · ` +
        `${audit.commands.length} command(s) · ${audit.problems.length} problem(s)`
    );
  }
  for (const p of audit.problems) console.error("  PROBLEM  " + p);
  if (process.argv.includes("--check")) process.exit(audit.problems.length ? 1 : 0);
}
