#!/usr/bin/env node
/**
 * Project the neutral COC working material into per-CLI overlays.
 *
 * ONE SOURCE, THREE OVERLAYS
 * --------------------------
 * `src/aegis_sdk/coc/` is the SINGLE source of truth for the architect-facing
 * working material: agent briefs, task skills and guardrails. It ships inside
 * the installed package, so it travels with the client whether or not anyone
 * clones this repository.
 *
 * No count is written here on purpose. This file SHIPS, and a hand-typed total
 * in a shipped comment goes stale against the directory it describes with
 * nothing to catch it — this line said "six guardrails" while the tree carried
 * seven, disagreeing with the derived counts in the same repository's README.
 * The run prints the live figures; read those.
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
const sources = new Map(); // repo-relative dest -> repo-relative source

function put(rel, content, source) {
  files.set(rel, content);
  if (source) sources.set(rel, source);
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

// ───────────────────────────── hooks ─────────────────────────────────────────
//
// THE HOOKS ARE PROJECTED DIFFERENTLY FROM THE PROSE, AND THE DIFFERENCE IS
// DELIBERATE. A skill is projected as THREE COPIES because each CLI reads its
// own tree and the content is what matters. A hook is EXECUTABLE: three copies
// of a script is three programs that can diverge in behaviour, and a behavioural
// divergence between CLI overlays is not a drift a diff makes obvious. So the
// scripts land ONCE, under `.claude/hooks/`, and all three CLIs invoke that same
// path. What is projected three times is only the REGISTRATION.
//
// `hooks.manifest.json` is the single source for all three registrations.
// Hand-maintaining `.claude/settings.json`, `.codex/hooks.json` and
// `.gemini/settings.json` was never going to hold: each looks authoritative, and
// a hook missing from one of them does not fail — it simply never fires, which
// is indistinguishable from a hook that found nothing.

const HOOKS_DIR = path.join(COC, "hooks");
const MANIFEST = path.join(HOOKS_DIR, "hooks.manifest.json");

/** CC event name -> Gemini event name. Gemini renames events, not tools. */
const CC_TO_GEMINI_EVENT = {
  PreToolUse: "BeforeTool",
  PostToolUse: "AfterTool",
  SessionStart: "SessionStart",
  Stop: "SessionEnd",
};

let hookEntries = [];
let hookScripts = [];

if (fs.existsSync(MANIFEST)) {
  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(MANIFEST, "utf8"));
  } catch (e) {
    problems.push(`src/aegis_sdk/coc/hooks/hooks.manifest.json: not valid JSON (${e.message})`);
    manifest = { hooks: [] };
  }
  hookEntries = Array.isArray(manifest.hooks) ? manifest.hooks : [];

  // Every script under hooks/, including `lib/`. Walked rather than listed: a
  // hand-written file list is the defect this whole projector exists to avoid,
  // and it would drift the moment a guard grew a helper.
  const walkScripts = (dir, prefix = "") => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const p = path.join(dir, e.name);
      const relName = prefix ? `${prefix}/${e.name}` : e.name;
      if (e.isDirectory()) {
        walkScripts(p, relName);
        continue;
      }
      if (!/\.(js|cjs|mjs|py)$/.test(e.name)) continue;
      hookScripts.push({ relName, abs: p, src: `src/aegis_sdk/coc/hooks/${relName}` });
    }
  };
  walkScripts(HOOKS_DIR);

  // Every manifest entry must name a script that exists, and vice versa. Both
  // directions, because each failure is silent in its own way: a registered
  // hook with no script never runs, and a script no manifest registers is dead
  // code that reads as enforcement.
  const scriptNames = new Set(hookScripts.filter((s) => !s.relName.includes("/")).map((s) => s.relName.replace(/\.js$/, "")));
  for (const h of hookEntries) {
    if (!scriptNames.has(h.name)) {
      problems.push(`hooks.manifest.json: '${h.name}' is registered but src/aegis_sdk/coc/hooks/${h.name}.js does not exist`);
    }
    if (!h.event || !Array.isArray(h.matchers) || !h.matchers.length) {
      problems.push(`hooks.manifest.json: '${h.name}' needs an 'event' and a non-empty 'matchers'`);
    }
    if (!Array.isArray(h.enforces) || !h.enforces.length) {
      // A guard that cannot name the obligation it enforces has not
      // established that it enforces one — the same contract `emit()` applies
      // at runtime, applied here at projection time so it cannot be skipped.
      problems.push(`hooks.manifest.json: '${h.name}' must name the guardrail(s) it enforces`);
    }
  }
  for (const name of scriptNames) {
    if (!hookEntries.some((h) => h.name === name)) {
      problems.push(`src/aegis_sdk/coc/hooks/${name}.js exists but hooks.manifest.json registers no event for it — it would never fire`);
    }
  }

  const HOOK_PROVENANCE = (src) =>
    `// PROJECTED FILE — do not edit here.\n` +
    `// Source of truth: ${src}\n` +
    `// Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check\n`;

  for (const s of hookScripts) {
    const body = fs.readFileSync(s.abs, "utf8");
    if (s.relName.endsWith(".py")) {
      // A `#` comment banner would sit above the module docstring and silently
      // stop it being the docstring. Python scripts are projected verbatim.
      put(`.claude/hooks/${s.relName}`, body, s.src);
      continue;
    }
    const shebang = body.startsWith("#!") ? body.slice(0, body.indexOf("\n") + 1) : "";
    put(`.claude/hooks/${s.relName}`, shebang + HOOK_PROVENANCE(s.src) + body.slice(shebang.length), s.src);
  }

  // ── CC: `.claude/settings.json`, hooks block grouped by event then matcher.
  //
  // The `hooks` key is OWNED by this projector; every other key in an existing
  // file is preserved. A partner will have their own permissions and env in
  // there, and a projector that flattened them would be reverted by hand within
  // a day — after which nothing regenerates and the three registrations drift
  // again, which is the failure this replaces.
  const byEvent = new Map();
  for (const h of hookEntries) {
    if (!byEvent.has(h.event)) byEvent.set(h.event, []);
    byEvent.get(h.event).push(h);
  }
  const ccHooks = {};
  for (const [event, entries] of [...byEvent].sort()) {
    ccHooks[event] = entries
      .map((h) => ({
        matcher: h.matchers.join("|"),
        hooks: [
          {
            type: "command",
            command: `node "$CLAUDE_PROJECT_DIR/.claude/hooks/${h.name}.js"`,
            timeout: Math.ceil(h.timeout_ms / 1000),
          },
        ],
      }))
      .sort((a, b) => a.matcher.localeCompare(b.matcher) || JSON.stringify(a).localeCompare(JSON.stringify(b)));
  }
  let ccSettings = {};
  const ccPath = path.join(ROOT, ".claude", "settings.json");
  if (fs.existsSync(ccPath)) {
    try {
      ccSettings = JSON.parse(fs.readFileSync(ccPath, "utf8"));
    } catch {
      problems.push(".claude/settings.json exists but is not valid JSON — fix or remove it before projecting");
    }
  }
  put(".claude/settings.json", JSON.stringify({ ...ccSettings, hooks: ccHooks }, null, 2) + "\n", "src/aegis_sdk/coc/hooks/hooks.manifest.json");

  // ── Codex: `.codex/hooks.json`. Bash lane only — the manifest records that
  //    per hook in `codex_coverage`, and the note is carried into the emitted
  //    file so the gap is visible where someone would look for it rather than
  //    only in the source.
  const codexHooks = [];
  for (const h of hookEntries) {
    if (!h.matchers.includes("Bash")) continue;
    codexHooks.push({
      event: h.event,
      // The wrapper form, cwd-relative. `$CODEX_PROJECT_DIR` does not exist and
      // expands to empty, producing `node /.claude/hooks/…` and a silent
      // MODULE_NOT_FOUND — a hook that never runs and never says so.
      command: `node ./.claude/hooks/lib/codex-hook-runtime.js ./.claude/hooks/${h.name}.js`,
      timeout_ms: h.timeout_ms,
      _coverage: h.codex_coverage || "unstated",
    });
  }
  put(
    ".codex/hooks.json",
    JSON.stringify(
      {
        _doc: [
          "PROJECTED FILE — do not edit here. Source: src/aegis_sdk/coc/hooks/hooks.manifest.json",
          "Regenerate: node scripts/project_coc.mjs",
          "",
          "CODEX FIRES HOOKS ON THE BASH LANE ONLY. A guard whose surface is file",
          "writes is absent from this file BY CONSTRUCTION, not by omission — see",
          "each entry's `_coverage`, and the manifest's `codex_coverage` for the",
          "hooks that do not appear here at all.",
        ],
        hooks: codexHooks,
      },
      null,
      2
    ) + "\n",
    "src/aegis_sdk/coc/hooks/hooks.manifest.json"
  );

  // ── Gemini: `.gemini/settings.json`, with the event names translated. A
  //    `PreToolUse` key here is silently ignored and the hook never fires.
  const gemHooks = {};
  for (const h of hookEntries) {
    const ev = CC_TO_GEMINI_EVENT[h.event];
    if (!ev) {
      problems.push(`hooks.manifest.json: '${h.name}' event '${h.event}' has no Gemini equivalent`);
      continue;
    }
    if (!gemHooks[ev]) gemHooks[ev] = [];
    gemHooks[ev].push({
      matcher: h.matchers.join("|"),
      command: `node "$GEMINI_PROJECT_DIR/.claude/hooks/${h.name}.js"`,
      timeout_ms: h.timeout_ms,
    });
  }
  for (const k of Object.keys(gemHooks)) {
    gemHooks[k].sort((a, b) => a.matcher.localeCompare(b.matcher) || a.command.localeCompare(b.command));
  }
  let gemSettings = {};
  const gemPath = path.join(ROOT, ".gemini", "settings.json");
  if (fs.existsSync(gemPath)) {
    try {
      gemSettings = JSON.parse(fs.readFileSync(gemPath, "utf8"));
    } catch {
      problems.push(".gemini/settings.json exists but is not valid JSON — fix or remove it before projecting");
    }
  }
  put(".gemini/settings.json", JSON.stringify({ ...gemSettings, hooks: gemHooks }, null, 2) + "\n", "src/aegis_sdk/coc/hooks/hooks.manifest.json");
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
    hooks: hookEntries.length,
    hook_scripts: hookScripts.length,
    projected_files: files.size,
  },
  // EVERY GUARDRAIL, AND WHETHER ANYTHING ENFORCES IT.
  //
  // Derived from the manifest's `enforces` lists against the guardrail files on
  // disk — never hand-listed, so it cannot claim coverage that is not there.
  // A guardrail with no hook is not a defect by itself; a guardrail with no hook
  // that nobody NOTICED is, and this is the line that makes the difference
  // visible on every projection.
  enforcement: (() => {
    const enforced = new Set(hookEntries.flatMap((h) => h.enforces || []));
    const rows = {};
    for (const g of guardrails) {
      const names = hookEntries.filter((h) => (h.enforces || []).includes(g.rel)).map((h) => h.name);
      rows[g.rel] = names.length ? [...new Set(names)] : "PROSE ONLY — no hook enforces this";
    }
    for (const e of enforced) {
      if (!rows[e] && !fs.existsSync(path.join(ROOT, e))) {
        rows[e] = "REGISTERED BUT MISSING — a hook names a guardrail that does not exist";
      }
    }
    return rows;
  })(),
  projected: [...files.keys()]
    .sort()
    .map((dest) => {
      const src =
        sources.get(dest) ??
        [...agents, ...allSkills].find(
          (e) => dest.includes(`/${e.name}/`) || dest.endsWith(`/${e.name}.md`) || dest.endsWith(`specialist-${e.name}.md`)
        )?.rel ??
        "coc-context.md";
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
      `from ${agents.length} agent(s), ${skills.length} skill(s), ${guardrails.length} guardrail(s), ` +
      `${hookEntries.length} hook registration(s) over ${hookScripts.length} script(s)`
  );
  // Printed on every --check, green or not. A guardrail nobody enforces is the
  // finding this whole workstream started from — 15 artifacts, zero hooks — and
  // it stayed invisible because nothing ever printed the pairing.
  const unenforced = Object.entries(ledger.enforcement).filter(([, v]) => typeof v === "string");
  console.log(
    `guardrails with a hook  : ${guardrails.length - unenforced.length}/${guardrails.length}` +
      (unenforced.length ? `\nPROSE ONLY (no hook)    : ${unenforced.map(([k]) => path.basename(k)).join(", ")}` : "")
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
