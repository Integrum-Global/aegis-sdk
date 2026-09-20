---
name: extend
description: "Add a capability to a governed organisation — decide what shape it is, build it, decide who may call it, test it off a real tenant, and know how to take it out of service."
---
<!-- PROJECTED FILE — do not edit here.
     Source of truth: src/aegis_sdk/coc/commands/extend.md
     Regenerate: node scripts/project_coc.mjs   ·   Verify: node scripts/project_coc.mjs --check -->


<!-- anchor-floor: exempt (procedure; routes to handbook chapters and skills by name) -->

You are giving a running organisation something new to do. This is harness work
throughout — there is no console path for authoring a capability.

**Precondition:** `/orient` has run and you hold a named deployment and a probe
verdict of `0`. If the organisation itself does not exist yet, you want
`/construct` first.

## 0 — Decide what shape it is, before you build anything

Handbook chapter **Choosing between a tool, a skill, an agent and a pipeline**.
Read it first if you have not decided. The wrong choice is cheap to make and
expensive to unwind, and the shortest path from "I need to add X" to knowing
which of six shapes X is runs through that chapter.

### The distinction that decides most of it

**"Tool" names two different objects here, and they do not overlap.**

| | **in-process tool** | **registered tool agent** |
| --- | --- | --- |
| is | a function inside the agent's runtime | a first-class platform object |
| has | no id, no status, no record of its own | id, status, accountable role, components, consumers, derived envelope, invocation history |
| governed | at the moment of the call, through a hook | at every step of its life, as governance events |
| register | nothing to register — that is the design | everything |

Pick deliberately. Building the second when you needed the first buys you a
lifecycle you now have to operate; building the first when you needed the second
leaves a capability with no accountable role and no invocation record.

## 1 — Build it

Handbook chapters **Writing a tool an agent can call** and **Agents, skills and
pipelines**. Load the **registering-a-tool-or-agent** skill — it carries the
order of operations and the tool-agent / task-agent split, which is a second
pair of things sharing one word.

A tool agent is a capability something else invokes. A task agent is a unit of
work with a prompt. Their surfaces do not overlap; establish which you are
building before the first call.

## 2 — Give it an accountable role and check its envelope

A registered capability derives its envelope from the role accountable for it.
Check what it actually resolved to rather than what you intended — the derived
envelope is the composition, and a composition can be narrower than every input
you gave it.

If it resolved wider than you expected, stop. A capability whose bound is wider
than its author believed is the failure this platform exists to prevent, and it
will not announce itself.

## 3 — Decide who may call it

Handbook chapter **Who may call your tool: applications, grants and policy**.
Registering a capability does not publish it. Consumers are granted explicitly,
and the grant is the thing an auditor will ask about.

If you are registering a **surface** — one row that is simultaneously a
navigation entry and a reachable route — load the **domain-surfaces** guardrail.
That composition happens at runtime with no deploy, against a semi-trusted
principal, and the assumption people make about who can see it is usually wrong.

## 4 — Test it before it touches a real organisation

Handbook chapter **Testing an extension before it touches a real organisation**.
The chapter title is the instruction. A capability tested first on a client's
tenant has been tested in production.

**Prove it is actually callable**, and be exact about what the proof covers:
invoking it once establishes that it was admitted and returned. It does not
establish that the grant is correct for every consumer, and it does not
establish that a refusal you did not trigger would fire. Reachability is
admission, not enforcement.

## 5 — Know how it comes out again

Handbook chapter **The tool-agent lifecycle, definition to retirement**. Status
changes are governance events. Decide now what retiring it looks like, while you
still remember what depends on it — a capability with live consumers and no
retirement path is a capability nobody can safely remove.

## Before you call it done

- [ ] the shape was chosen from the chapter, not from familiarity
- [ ] the accountable role is set and the **derived** envelope was read, not assumed
- [ ] consumers are granted explicitly, and you can name them
- [ ] it was exercised somewhere that is not a client's live organisation
- [ ] the retirement path exists and you have said what it is
- [ ] anything you could not verify from here is written down as unverified

## Next

- `/diagnose` — the capability was refused, or a consumer cannot reach it
- `/construct` — the organisation around it needs more work

**Skills:** `registering-a-tool-or-agent` (the order of operations),
`reading-trust-and-governance` (reading the derived envelope honestly).
**Guardrails:** `domain-surfaces`, `client-model-fidelity`.
