# Unresolved — what this repository does not settle

Assembled 2026-09-17. Each entry names what is open, who decides, and what
would close it. Nothing here is a placeholder for work that was skipped; each is
a decision that was deliberately not taken by the assembly.

---

## 1. Domain surfaces — CONTRACT STATED, CLIENT SUPPORT ABSENT

The architect-tier requirement is settled and is documented: see the
**`domain-surfaces` guardrail** (`src/aegis_sdk/coc/guardrails/domain-surfaces.md`,
projected into all three CLI overlays). It carries the five non-negotiable
invariants verbatim, the closed-vocabulary and derived-path design, and the tier
split that puts domain composition in the architect layer rather than the
developer layer.

What remains open is **not** the contract. It is three absences the guardrail
names and this repository cannot close:

**(a) This client cannot register a surface.** The package exposes no surfaces
module and declares no surface-registration operation. Measured:

```bash
python -c "import aegis_sdk, pkgutil; print([m.name for m in pkgutil.iter_modules(aegis_sdk.modules.__path__) if 'surf' in m.name])"   # []
python -c "from aegis_sdk.handbook.check import declared_operations as d; print([o for o in d() if 'surface' in str(o).lower()])"       # []
```

Both empty, with a `tool_agent` control returning `['tool_agents']` and `13`
respectively — so the emptiness is a measurement, not a command that could not
speak. Surface composition is therefore an **out-of-band step** today: the
console and the platform API, not this SDK.

**Closes when:** the client gains a surfaces module. The two commands above are
how a reader will know it has.

**(b) The classification field gates nothing.** It is declarative; visibility
resolves on tenant, status, vocabulary, persona and permission and never against
caller clearance. Pinned as a named absence in the platform's own security tests.

**Closes when:** clearance enters the visibility resolution. Until then the
guardrail's warning stands, and a partner must not treat classification as a
control.

**(c) The governed-object layer beneath a surface is schema-only.** The domain
object *type* and the governed object *record* ship with no handler, no service,
no route and no frontend. A surface can be registered; it cannot yet be populated
with governed domain records through a supported API.

**Closes when:** those two models gain a reachable surface of their own.

⚠ The owning programme is **open and self-reports as not converged** — multiple
adversarial review rounds, none clean, open critical findings — even though the
registration model has shipped and is live. That is recorded here because a
partner is better served knowing it than discovering it.

---

## 2. Distribution name — PROVISIONAL

The distribution is `agentic-os-sdk`. This is a product decision, not a packaging
one, and it was carried forward rather than chosen.

`aegis-sdk` on PyPI belongs to an unrelated third-party package. The current name
matches the platform's own distribution family and the `AGENTIC_OS_*` environment
prefix the client actually reads.

**Closes when:** availability is confirmed on the target index and the name is
ratified. Change it in `pyproject.toml` only — the version is read from
`src/aegis_sdk/_version.py` and is never restated.

---

## 3. LICENSE and NOTICE — PRESENT, UNAPPROVED

Both files now exist and travel. **Neither has been reviewed by counsel**, and
each carries a `⛔ DRAFT` block at the top saying so. Read that block before
relying on either.

Nothing about the license was CHOSEN here. `pyproject.toml` already declared
`license = { text = "LicenseRef-Proprietary" }`; what was missing was a file
delivering it, so a recipient held software under a declared-but-undelivered
license. The files materialise that declaration and nothing more: no grant, no
warranty, no liability and no indemnity terms are stated, because those belong
to the written agreement between the parties and not to a file in a repository.

Two facts in them were carried rather than settled, and both are flagged in
`LICENSE` itself: the **legal entity name** (the packaging descriptor says
`Integrum`; internal drafting notes elsewhere say `Agentic OS, Inc.`) and the
**copyright years**. Only counsel can settle either.

**Closes when:** counsel reviews both, the entity name and years are confirmed,
and the `⛔ DRAFT` blocks are removed as part of that sign-off — not as tidying.

---

## 3b. The type ratchet is green — but it is a budget, not a zero

`python packaging/aegis-sdk/harness.py all` is green on all four steps. This
section stays because the green is a *budget* being met, and a reader who takes
it for "no type errors" would be wrong by 262.

It was red when this tree was first assembled. Measured 2026-09-08: **320 errors
across 58 files against a banked budget of 269 across 52**, which split three
ways rather than the two first reported:

- **7 files were never in the baseline at all** (34 errors) — they landed after
  it was banked and nothing forced it forward. A ratchet nobody ran, not code
  that got worse.
- **3 files genuinely regressed** (+18): `modules/compliance.py` 3 → 17,
  `modules/work_objectives.py` 27 → 29, `modules/knowledge_govern.py` 10 → 12.
- **1 file had quietly improved** (−1), which is why 269 + 34 + 18 came to 321
  against a measured 320.

`--update-baseline` would have greened all of it in one command, and that was
refused: it banks the regressions with the omissions and you would inherit a
budget nobody chose. Instead the 3 regressions were FIXED — to zero, not to
their old budgets — and only then were the 7 omissions banked at their true
counts. The 3 regressions were: a local variable shadowing its own method's
public parameter; a public method named `list` shadowing the builtin in every
signature in its class; and `Returning Any` at sites whose declared return type
was never asserted onto the local.

Current state: **262 errors across 55 files against a 262 budget.** Every entry
is inherited debt with a number on it, and the ratchet only goes down — a file
may improve and may never regress.

**Not closed.** `py.typed` promises consumers these annotations are meaningful,
and that promise is backed by a budget rather than by zero. The largest holdings
are `nexus/plugins_module.py` (33), `nexus/sessions_module.py` (27),
`nexus/workflows_module.py` (17), `core/agents.py` (13) and `modules/promotions.py`
(11). Most are the same `Returning Any` shape the three fixed files carried, and
the same remedy applies.

---

## 3c. `project.urls.Documentation` — CLOSED

The `Documentation` URL no longer names a host at all. It previously pointed
into the private platform repository, which was neither resolvable from outside
nor a name that belonged in a partner-facing descriptor; it was then repointed
at a second repository that is ALSO private, and the entry was marked closed
here on that basis — a closure that did not hold, because a partner cannot read
a private repository either.

⚠ THIS REPOSITORY IS PUBLISHED PER DEPLOYMENT. The address a partner clones from
belongs to the deployment, not to this file, and canon does not know it. Any
absolute URL written here is therefore wrong for every reader except one, which
is why the field is now absent rather than repointed a third time.
Kept here as a closed entry rather than deleted, so the next reader does not
re-open a decision that has been taken. The documentation itself ships in this
tree under `src/aegis_sdk/docs/`.

**Still open, and separate:** the distribution NAME (§ 2) and the publishing
path (§ 4). A published home is not a published package.

---

## 4. Publishing — no index, no credential, no release job

Building is proven; shipping is not. There is no package index configured, no
publishing credential, and no release workflow in this repository.

**Closes when:** an index and a release path are chosen. Note that the target
audience clones this repository rather than installing from an index, so this is
not on the critical path for partner enablement.

---

## 5. Git history — squashed to a clean root, deliberately

This repository is assembled with **no inherited history**.

That is not tidiness. Measured on the platform repository: of 183 commits
touching the exported surface, **73 carry an internal reference in the commit
body** — issue numbers, private source paths, internal governance rule filenames,
internal programme names. Commit bodies are required there to explain *why*,
which makes them the densest internal-reference surface in that repository, and
every carry-history option ships all 73.

**Closes when:** nothing. The decision is made; it is recorded here so the next
person does not "restore" the history as a favour.
