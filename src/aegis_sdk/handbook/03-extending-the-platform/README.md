# Part 03 — Extending the platform

<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->

**Audience: you are adding a capability.** Part 02 was about describing and
running a governed organisation with what is already there. This part is about
giving it something new to do — a tool an agent can call, an agent configured for
a job, a skill, a pipeline — and about everything that comes after "it works":
who may call it, what happens when it fails, and how you take it out of service.

This is still harness work. There is no console path for authoring a tool.

| #    | Chapter                                                                                  | Read it when                                      |
| ---- | ---------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 03.1 | [Writing a tool an agent can call](01-writing-a-tool.md)                                 | You are adding a capability an agent will use     |
| 03.2 | [Agents, skills and pipelines](02-agents-skills-and-pipelines.md)                        | You are configuring who does the work             |
| 03.3 | [The tool-agent lifecycle](03-the-tool-agent-lifecycle.md)                               | You are registering a shared capability           |
| 03.4 | [Who may call your tool](04-applications-grants-and-policy.md)                           | You are deciding which consumers may invoke it    |
| 03.5 | [Testing an extension](05-testing-an-extension.md)                                       | Before it touches a real organisation             |
| 03.6 | [Choosing between a tool, a skill, an agent and a pipeline](06-choosing-between-them.md) | You are deciding what to build in the first place |

**Read 03.6 first if you have not decided what you are building.** It is the
shortest path from "I need to add X" to knowing which of six shapes X is, and the
wrong choice is cheap to make and expensive to unwind.

## The one distinction that runs through this whole part

**"Tool" names two different objects here.**

An **in-process tool** is a function inside the agent's runtime. It has no id, no
status and no record of its own. Governance reaches it at the moment of the call,
through a hook. Nothing needs to be registered, and that is the whole design.

A **registered tool agent** is a first-class platform object with an id, a lifecycle
status, an accountable role, components, consumers, a derived envelope and an
invocation history. Every step of its life is a governance event.

Choosing the first while describing the second to your stakeholders is the most
common expensive mistake in this part: an in-process tool has no consumers list, no
impact analysis and no invocation history, so none of the questions an auditor asks
about it have mechanical answers. 03.1 opens with the full comparison.

## The working artifacts this part hands off to

The chapters here are the explanation. The **working** half ships beside them,
under `aegis_sdk/coc/`, and three of those artifacts are this part's subject:

| artifact                                                                                       | use it when                                                                  |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [`coc/skills/registering-a-tool-or-agent.md`](../../coc/skills/registering-a-tool-or-agent.md) | you are actually registering something — the order of operations, condensed  |
| [`coc/agents/aegis-sdk-specialist.md`](../../coc/agents/aegis-sdk-specialist.md)               | you are building against the client and want its brief rather than its prose |
| [`coc/skills/diagnosing-a-refusal.md`](../../coc/skills/diagnosing-a-refusal.md)               | your extension was refused and you need to know which kind of refusal it was |

Have the skill open while you work and this part open when you want to know _why_.
[Chapter 01.1](../01-orientation/01-what-you-were-given.md) carries the full linked
corpus, including the guardrails 03.4, 03.5 and 03.6 point at.

**A chapter here and its companion skill are the same claim at two
resolutions.** If they ever disagree, report it rather than choosing between
them.

## Read 01.2 first if you have not

The most expensive misunderstanding on this platform is about _where_ governance
happens, and it decides how you write a tool. People assume Aegis sits between an
agent and the outside world, receiving the agent's requests and forwarding the
approved ones. It does not.

The practical consequence for this part: **your tool holds the credentials and
does the work.** Aegis is not in the data path. If your design has Aegis making
the outbound call, you are designing a component that does not exist.

[Chapter 01.2](../01-orientation/02-the-mental-model.md) is short and it is the
load-bearing one.

## Two things about authorization to settle before you register anything

Both are covered in full in [chapter 04.1](../04-the-api-surface/01-calling-the-api.md).
Named here because registration is a _write_, and the write surface is where
they matter most.

- **Personas belong to sessions; scopes belong to keys.** A route gated on
  personas wants a user session, and a wider scope will not substitute for one.
  If you are debugging API-key authorization and your scopes look right, they
  probably are — 04.1 gives you a one-minute test that tells you which model a
  route follows.
- **A permission your role holds can still be refused.** Denials reach you as
  HTTP refusals on the routes you call, and the response names the permission
  and not what evaluated it — so re-granting the role is not the diagnosis and
  will not clear it. 04.1 gives you the order to work through instead.

## Three defaults in this part that are not what you would guess

Each is documented where it lives; collected here because a default nobody chose is
still a default you own.

- **A task agent's `posture_ceiling` defaults to `delegated`** — the _most_
  autonomous posture. Nearly every other default in this book is restrictive. 03.6.
- **An external agent's four budget and rate limits default to `-1`, meaning
  unlimited** — and `-1` compares as smaller than every threshold, so a naive
  numeric check fires loudest on the agent that has no limit at all. 03.6.
- **An application's `default_posture_ceiling` defaults to `pseudo`** — the most
  restrictive, which is right, and which surprises people whose grants then cannot
  exceed it. 03.4.

## How this part is anchored

Claims name **surfaces you can reach** — an HTTP operation this client performs,
a symbol this package exports — rather than coordinates in a source tree you were
not given. Verify them against your own installed package:

```
python -m aegis_sdk.handbook.check
```

A resolving anchor tells you the operation exists in the surface you were given.
Where a claim is about what the server **enforces**, this part says so
explicitly — and chapter 03.2 shows you how to confirm a route end to end rather
than inferring it from the client alone.

## What this part is careful about

Aegis is Integrum's commercial implementation of four open standards — CARE,
PACT, EATP and CO — published by Terrene Foundation under CC BY 4.0. Aegis
implements them; it does not own them. Where this part uses standard
terminology, it is using the Foundation's vocabulary deliberately.

A note on liability, because the distinction matters to how you build: the
organisation deploying an agent keeps the accountability for what that agent
does. It cannot be delegated, and no amount of autonomy transfers it. What this
platform provides is the _proof_ — the bounded mandate, the tamper-evident audit
trail, the fail-closed gate, the attestable lineage — that lets that organisation
show an auditor how it discharged the accountability it already had. Build
accordingly: the artifacts you produce are evidence, and evidence that cannot be
shown to a third party is not doing its job.

---

_Next: [03.1 — Writing a tool an agent can call](01-writing-a-tool.md)_
