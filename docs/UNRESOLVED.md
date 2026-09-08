# Unresolved — what this repository does not settle

Assembled 2026-09-08. Each entry names what is open, who decides, and what
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
