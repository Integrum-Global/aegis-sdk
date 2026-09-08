#!/usr/bin/env node
/**
 * Project the neutral COC working material into per-CLI overlays.
 *
 * ONE SOURCE, THREE OVERLAYS
 * --------------------------
 * `src/aegis_sdk/coc/` is the SINGLE source of truth for the architect-facing
 * working material: two agent briefs, six task skills, six guardrails. It ships
 * inside the installed package, so it travels with the client whether or not
 * anyone clones this repository.
 *
 * Three CLIs read three different layouts, and none of them reads that one.
 * This script projects the neutral source into all three:
 *
 *     src/aegis_sdk/coc/agents/<name>.md      ->  .claude/agents/<name>.md
 *                                             ->  .codex/prompts/specialist-<name>.md
 *                                             ->  .gemini/agents/<name>.md
 *     src/aegis_sdk/coc/skills/<name>.md      ->  .claude/skills/<name>/SKILL.md
 *                                             ->  .codex/skills/<name>/SKILL.md
 *                                             ->  .gemini/skills/<name>/SKILL.md
 *     src/aegis_sdk/coc/guardrails/<name>.md  ->  the same three skill paths,
 *                                                 with DERIVED frontmatter
 *     coc-context.md                          ->  CLAUDE.md / AGENTS.md / GEMINI.md
 *
 * WHY A PROJECTOR RATHER THAN THREE HAND-MAINTAINED COPIES
 * --------------------------------------------------------
 * Three copies of one obligation drift, and the drift is silent: each copy
 * looks authoritative, and the reader has no way to tell which one is current.
 * `--check` makes drift a RED rather than a discovery, so the copies can only
 * be wrong on purpose.
 *
 * WHY THE SOURCE IS ALREADY NEUTRAL, MEASURED RATHER THAN ASSUMED
 * ---------------------------------------------------------------
 * A projector cannot make CLI-specific prose neutral; it can only place it.
 * The source was checked for CLI-specific vocabulary (tool names, dispatch
 * syntax, per-CLI directory paths) and carries none — so the projection is a
 * placement problem and not a rewriting problem. Re-check before adding a file:
 *
 *     grep -rniE 'claude code|\.claude/|subagent_type|/prompts:' src/aegis_sdk/coc/
 *
 * A zero there is only evidence if the same command finds the string when you
 * plant it; plant one and remove it before trusting the zero.
 *
 * USAGE
 * -----
 *     node scripts/project_coc.mjs            # write the overlays
 *     node scripts/project_coc.mjs --check    # exit 1 if any overlay has drifted
 *
 * Exit: 0 in sync / written, 1 drift or malformed source, 2 usage.
 */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const COC = path.join(ROOT, "src", "aegis_sdk", "coc");
const CONTEXT = path.join(ROOT, "coc-context.md");
const LEDGER = path.join(ROOT, "coc-projection.json");

const CHECK = process.argv.includes("--check");
if (process.argv.slice(2).some((a) => a !== "--check")) {
  console.error("usage: project_coc.mjs [--check]");
  process.exit(2);
}

const problems = [];
const sha = (b) => createHash("sha256").update(b).digest("hex").slice(0, 16);

/**
 * CC tool identifier -> Gemini tool identifier.
 *
 * Mirrors the table the platform repository's emitter uses, so a `tools:` field
 * added upstream translates the same way here. `Task` is deliberately absent:
 * a subagent cannot recurse, so the entry is dropped rather than mapped.
 *
 * No file under `src/aegis_sdk/coc/` declares `tools:` today. The table is
 * carried anyway because the first file that does would otherwise be projected
 * with CC identifiers into a Gemini overlay that cannot resolve them, silently.
 */
const CC_TO_GEMINI_TOOLS = {
  Read: "read_file",
  Write: "write_file",
  Edit: "replace",
  Bash: "run_shell_command",
  Grep: "grep_search",
  Glob: "glob",
};

// ───────────────────────────── frontmatter ───────────────────────────────────

function splitFrontmatter(text, rel) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { fm: null, body: text };
  const fm = {};
  let key = null;
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^([A-Za-z_-]+):\s*(.*)$/);
    if (kv) {
      key = kv[1];
      fm[key] = kv[2];
      if (kv[2] === "") fm[key] = [];
      continue;
    }
    const item = line.match(/^\s+-\s+(.*)$/);
    if (item && Array.isArray(fm[key])) fm[key].push(item[1]);
  }
  return { fm, body: text.slice(m[0].length) };
}

function renderFrontmatter(fields) {
  const lines = ["---"];
  for (const [k, v] of Object.entries(fields)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      lines.push(`${k}:`);
      for (const item of v) lines.push(`  - ${item}`);
    } else {
      lines.push(`${k}: ${v}`);
    }
  }
  lines.push("---", "");
  return lines.join("\n");
}

// ───────────────────────────── read the neutral source ───────────────────────

const mdIn = (dir) =>
  fs.existsSync(dir)
    ? fs
        .readdirSync(dir)
        .filter((f) => f.endsWith(".md") && f !== "README.md")
        .sort()
    : [];

/** Agents and skills: frontmatter is authored, and must be present. */
function readAuthored(kind) {
  const dir = path.join(COC, kind);
  const out = [];
  for (const f of mdIn(dir)) {
    const rel = `src/aegis_sdk/coc/${kind}/${f}`;
    const raw = fs.readFileSync(path.join(dir, f), "utf8");
    const { fm, body } = splitFrontmatter(raw, rel);
    if (!fm?.name || !fm?.description) {
      problems.push(`${rel}: missing 'name' or 'description' frontmatter`);
      continue;
    }
    out.push({ rel, raw, fm, body, name: fm.name, description: fm.description });
  }
  return out;
}

/**
 * Guardrails: obligations, authored WITHOUT frontmatter, so no CLI can surface
 * them. The frontmatter is DERIVED from the file's own two structural lines —
 * the H1 subtitle after the em-dash, and the `**Scope:**` sentence. Nothing is
 * invented: a file missing either is refused rather than described, because a
 * description written here would be a claim about a guardrail made by the tool
 * that ships it.
 */
function readGuardrails() {
  const dir = path.join(COC, "guardrails");
  const out = [];
  for (const f of mdIn(dir)) {
    const rel = `src/aegis_sdk/coc/guardrails/${f}`;
    const raw = fs.readFileSync(path.join(dir, f), "utf8");
    if (splitFrontmatter(raw, rel).fm) {
      problems.push(`${rel}: already carries frontmatter; the derivation would double it`);
      continue;
    }
    const h1 = raw.match(/^#\s+(.+?)\s+—\s+(.+)$/m);
    const scope = raw.match(/^\*\*Scope:\*\*\s*([\s\S]*?)(?:\n\n|\n#)/m);
    if (!h1 || !scope) {
      problems.push(`${rel}: no '# Title — subtitle' H1 or '**Scope:**' line to derive a description from`);
      continue;
    }
    // Both halves of the H1: the subject and the obligation. The first draft
    // used only the half after the em-dash and produced "the errors here are
    // commercial, not cosmetic" — a description with no subject, which is the
    // one thing a CLI's skill listing cannot work with.
    const flat = (s) => s.trim().replace(/\s+/g, " ");
    const description = `${flat(h1[1])} — ${flat(h1[2])}. Scope: ${flat(scope[1]).replace(/\.$/, "")}.`;
    out.push({
      rel,
      raw,
      name: f.replace(/\.md$/, ""),
      description,
      body: raw,
      derived: true,
    });
  }
  return out;
}

const agents = readAuthored("agents");
const skills = readAuthored("skills");
const guardrails = readGuardrails();

if (!fs.existsSync(CONTEXT)) problems.push("coc-context.md is missing — the three root context files derive from it");

// ───────────────────────────── projection ────────────────────────────────────

const PROVENANCE = (rel) =>
  `<!-- PROJECTED FILE — do not edit here.\n` +
  `     Source of truth: ${rel}\n` +
  `     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->\n\n`;

const files = new Map(); // repo-relative path -> content

function put(rel, content) {
  files.set(rel, content);
}

function skillDoc(entry) {
  if (entry.derived) {
    return (
      renderFrontmatter({ name: entry.name, description: JSON.stringify(entry.description) }) +
      PROVENANCE(entry.rel) +
      entry.body
    );
  }
  return renderFrontmatter({ name: entry.name, description: entry.description }) + PROVENANCE(entry.rel) + entry.body;
}

const allSkills = [...skills, ...guardrails];

for (const cli of ["claude", "codex", "gemini"]) {
  const dir = `.${cli}`;
  for (const s of allSkills) put(`${dir}/skills/${s.name}/SKILL.md`, skillDoc(s));
}

for (const a of agents) {
  // Claude Code: an agent file, frontmatter carried as authored.
  put(`.claude/agents/${a.name}.md`, renderFrontmatter({ name: a.name, description: a.description }) + PROVENANCE(a.rel) + a.body);

  // Codex: no subagent registry. The persona is a PROMPT the operator invokes,
  // and the invocation note is the only CLI-specific prose in this projection —
  // it is generated here rather than written into the neutral source.
  put(
    `.codex/prompts/specialist-${a.name}.md`,
    renderFrontmatter({ name: `specialist-${a.name}`, description: JSON.stringify(a.description) }) +
      PROVENANCE(a.rel) +
      `You are now operating as the **${a.name}** specialist for the remainder of this turn.\n` +
      `Invoke with \`/prompts:specialist-${a.name}\`; the operating specification below becomes your context.\n\n` +
      `---\n\n` +
      a.body
  );

  // Gemini: an agent file with a translated tool set and a model pin.
  const tools = Array.isArray(a.fm?.tools) ? a.fm.tools : null;
  const geminiTools = tools
    ? tools.map((t) => CC_TO_GEMINI_TOOLS[t]).filter(Boolean)
    : null;
  put(
    `.gemini/agents/${a.name}.md`,
    renderFrontmatter({
      name: a.name,
      description: a.description,
      ...(geminiTools && geminiTools.length ? { tools: geminiTools } : {}),
    }) +
      PROVENANCE(a.rel) +
      a.body
  );
}

// The three root context files. One neutral body, three names, because each CLI
// loads a different filename and none of them reads the other two.
if (fs.existsSync(CONTEXT)) {
  const body = fs.readFileSync(CONTEXT, "utf8");
  const overlay = {
    "CLAUDE.md": [".claude/agents/", ".claude/skills/", "Claude Code"],
    "AGENTS.md": [".codex/prompts/", ".codex/skills/", "Codex"],
    "GEMINI.md": [".gemini/agents/", ".gemini/skills/", "Gemini CLI"],
  };
  for (const [name, [agentDir, skillDir, cliName]] of Object.entries(overlay)) {
    put(
      name,
      `<!-- PROJECTED FILE — do not edit here.\n` +
        `     Source of truth: coc-context.md (one neutral body, three CLI filenames)\n` +
        `     Regenerate: node scripts/project_coc.mjs -->\n\n` +
        body.replace(/\{\{CLI\}\}/g, cliName).replace(/\{\{AGENT_DIR\}\}/g, agentDir).replace(/\{\{SKILL_DIR\}\}/g, skillDir)
    );
  }
}

// ───────────────────────────── write or check ────────────────────────────────

if (problems.length) {
  console.error("SOURCE PROBLEMS:\n" + problems.map((p) => "  - " + p).join("\n"));
  process.exit(1);
}

const ledger = {
  _doc: [
    "Provenance for every projected COC artifact in this repository.",
    "",
    "THE SOURCE OF TRUTH IS src/aegis_sdk/coc/ (and coc-context.md for the three",
    "root context files). The .claude/, .codex/ and .gemini/ trees are PROJECTIONS.",
    "Edit the source and re-run `node scripts/project_coc.mjs`; editing a projection",
    "is silently reverted by the next run and is reported by `--check`.",
    "",
    "`source_sha256_16` is the digest of the SOURCE at projection time, so a source",
    "edit that was never re-projected is visible here rather than only in a diff.",
  ],
  projected_on: new Date().toISOString().slice(0, 10),
  counts: {
    agents: agents.length,
    skills: skills.length,
    guardrails: guardrails.length,
    projected_files: files.size,
  },
  projected: [...files.keys()]
    .sort()
    .map((dest) => {
      const src =
        [...agents, ...allSkills].find(
          (e) => dest.includes(`/${e.name}/`) || dest.endsWith(`/${e.name}.md`) || dest.endsWith(`specialist-${e.name}.md`)
        )?.rel ?? "coc-context.md";
      return { dest, source: src, source_sha256_16: sha(fs.readFileSync(path.join(ROOT, src), "utf8")) };
    }),
};

if (CHECK) {
  const drift = [];
  for (const [rel, content] of files) {
    const abs = path.join(ROOT, rel);
    if (!fs.existsSync(abs)) drift.push(`MISSING   ${rel}`);
    else if (fs.readFileSync(abs, "utf8") !== content) drift.push(`DRIFTED   ${rel}`);
  }
  // A projection left behind after its source was deleted is drift in the other
  // direction, and is the half a "did every source project?" check cannot see.
  for (const cli of [".claude", ".codex", ".gemini"]) {
    const walk = (d) => {
      if (!fs.existsSync(d)) return;
      for (const e of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, e.name);
        if (e.isDirectory()) walk(p);
        else {
          const rel = path.relative(ROOT, p);
          if (!files.has(rel)) drift.push(`ORPHANED  ${rel}`);
        }
      }
    };
    walk(path.join(ROOT, cli));
  }
  if (drift.length) {
    console.error(
      `COC PROJECTION DRIFT (${drift.length}):\n` +
        drift.map((d) => "  " + d).join("\n") +
        `\n\nThe source of truth is src/aegis_sdk/coc/. Re-run: node scripts/project_coc.mjs`
    );
    process.exit(1);
  }
  console.log(
    `coc projection in sync — ${files.size} file(s) across .claude/.codex/.gemini ` +
      `from ${agents.length} agent(s), ${skills.length} skill(s), ${guardrails.length} guardrail(s)`
  );
  process.exit(0);
}

for (const [rel, content] of files) {
  const abs = path.join(ROOT, rel);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, content);
}
fs.writeFileSync(LEDGER, JSON.stringify(ledger, null, 2) + "\n");

console.log(`projected ${files.size} file(s) from ${agents.length} agent(s), ${skills.length} skill(s), ${guardrails.length} guardrail(s)`);
console.log(`  .claude/  .codex/  .gemini/  +  CLAUDE.md  AGENTS.md  GEMINI.md`);
