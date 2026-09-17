# 03.1 — Writing a tool an agent can call

## "Tool" names two different objects here, and the difference decides your design

Settle this before you write anything, because the two have almost nothing in
common and choosing wrong is not a refactor — it is a rewrite.

**An in-process tool** is a function inside the agent's own runtime. The agent
calls it directly. It has no id, no status, no record of its own, and it never
appears in any listing. Governance reaches it at the moment of the call, through
the hook described in [chapter 01.2](../01-orientation/02-the-mental-model.md).
This chapter is about that one.

**A registered tool agent** is a first-class object on the platform —
`sdk:aegis_sdk.modules.tool_agents.ToolAgent`. It has an id, a lifecycle status,
an accountable role, components, consumers, a derived envelope and an invocation
history. It is created, granted, invoked and retired over the API, and every one
of those steps is a governance event.
[Chapter 03.3](03-the-tool-agent-lifecycle.md) is its lifecycle end to end.

|                 | in-process tool                     | registered tool agent                                         |
| --------------- | ----------------------------------- | ------------------------------------------------------------- |
| **is**          | a function in the agent's runtime   | a platform object with an id                                  |
| **governed at** | the tool call, by a hook            | the invoke call, by the platform                              |
| **you declare** | nothing                             | name, accountable role, capabilities                          |
| **it returns**  | whatever its caller expects         | `sdk:aegis_sdk.modules.tool_agents.ToolAgentInvocationResult` |
| **failure is**  | an exception in the agent's process | a status on a recorded invocation                             |
| **retired by**  | deleting the code                   | `api:PATCH /api/v1/tool-agents/{id}/status`                   |
| **callable by** | whoever runs the agent              | an application holding a grant (03.4)                         |

The mistake to avoid is building the first while describing the second to your
stakeholders. An in-process tool has no consumers list, no impact analysis and no
invocation history, so none of the questions an auditor asks about it have
mechanical answers. If the capability is shared, is called by more than one thing,
or has to be evidenced, it wants to be a registered tool agent.
[Chapter 03.6](06-choosing-between-them.md) is the fuller decision.

## The short version, for an in-process tool

It needs **no Aegis-specific contract**. You write the tool. That is the whole
obligation.

This surprises people who expect a governance platform to demand a policy
declaration, an identity assertion, a capability manifest and a registration
ceremony before it will let a tool run. Aegis asks for none of that, and the
reason is structural rather than generous: the two things the gate needs, it
already has without asking you.

## Why the gate does not need your help

**The tool's name comes from the call.** The pre-hook receives the tool name and
the tool input as arguments, from the invocation itself. Nothing needs to be
declared anywhere for the gate to know which tool is being invoked — the
invocation carries it.

That is worth pausing on, because it is also the security property: **the gate
does not ask your tool what it is.** A tool cannot misreport its own name to
obtain a softer verdict, because it is never consulted.

**The identity is server-derived.** It comes from the authenticated session — the
organisation and user are read from the wrapper's own configuration and passed
into the verification context, **never from anything the tool says about
itself**. A tool cannot assert a different identity to widen its own envelope,
because its assertion is not an input.

That second point is a security property, not an implementation convenience. If a
tool could declare who it was acting as, the declaration would be forgeable by
whatever is running the tool — which is precisely the party being governed. A
managed party that self-reports its own identity has not been identified. So the
platform does not accept identity from tools, and consequently there is no field
for you to fill in.

The same reasoning is enforced on the HTTP side, where the identity of an
approver is derived server-side from the session and never taken from a request
body. Chapter 04.1 covers that surface.

## What your tool receives

Two things, and only two: **the tool's name** and **the tool's input**.

That is the entire evidence base the verdict is made on, and it has three
consequences worth designing around rather than discovering.

**The verdict is about an intent, not an outcome.** No response exists when the
decision is made, because the call has not happened. A rule of the form "block
this if the result contains customer data" is not expressible at this point in the
path — there is nothing yet to inspect. Rules here are about _what you are about
to do_, phrased over the tool name and the arguments.

**Anything the gate can reason about must be visible in the arguments.** A tool
whose input is an opaque handle — a job id, a session token, a pre-built request
object — hands the gate an argument list it cannot read. It is still governed by
name, but no argument-level rule can apply to it, because the distinguishing
detail sits on the other side of the handle. If you want the amount in a payment
tool to be governable, the amount has to be an argument.

**Whatever is not an argument is invisible.** Configuration read from the
environment at call time, a value cached from a previous call, a default buried in
the tool's own module — none of it reaches the gate. Two calls that will do wildly
different things can present identically.

```python
# DO — the governable facts are arguments, so a rule can see them
async def transfer_funds(amount_usd: float, destination_account: str) -> dict:
    ...

# DO NOT — the amount is inside an opaque handle the gate cannot read
async def transfer_funds(request_handle: str) -> dict:
    ...
```

_Design intent, not observable:_ that the argument-visibility property is
deliberate rather than incidental. What is observable from your side is the
hook's shape — name and input in, input out — and the consequence follows from it.

## What your tool must return

**For an in-process tool, Aegis imposes no return shape at all.** Your tool
returns whatever its own caller — the agent runtime — expects. There is no Aegis
envelope to wrap, no status field to populate, no receipt to emit. If you find
yourself designing a return type "so Aegis can understand it", stop: nothing here
reads it.

**For a registered tool agent the return shape is fixed**, and it is worth
studying even if you are building the in-process kind, because it is the clearest
statement the platform makes about what it considers an invocation to consist of.
`sdk:aegis_sdk.modules.tool_agents.ToolAgentInvocationResult` carries nine fields:

| field               | what it is                                      |
| ------------------- | ----------------------------------------------- |
| `content`           | the output                                      |
| `model`             | which model produced it                         |
| `dispatch_path`     | `llm`, or `builtin_tool` when no model was used |
| `usage`             | token accounting                                |
| `cost`              | what it cost                                    |
| `trust_chain_id`    | the chain the invocation ran under              |
| `constraint_status` | how the constraints resolved                    |
| `verification_zone` | `auto_approved`, `flagged`, `held` or `blocked` |
| `audit_anchor_id`   | the anchor the record is bound to               |

Note the ratio. **One field is the answer; eight are the provenance of the
answer.** That is the platform's shape in miniature — the result is not the
product, the evidenced result is. `verification_zone` is CARE's four-zone
gradient, the same four values chapter 01.2 describes, arriving on a return type
you can read from your own code.

## When your tool fails

The in-process case and the registered case fail in genuinely different places,
and conflating them produces a monitoring plan pointed at the wrong surface.

**An in-process tool fails inside the agent's process.** It raises; the agent's
runtime sees the exception. Aegis is not in that path and does not learn what
happened from the failure itself. Your tool's own logging and your own error
handling are the primary record. Do not assume a failed tool call appears in a
platform listing — nothing reachable from here promises that.

**A refusal is not a failure, and the difference matters.** If the pre-hook
verdict denies the call, the tool never runs. Your tool sees nothing at all — not
an error, not an invocation. From inside the tool, a refused call and a call that
was never attempted are identical. So a tool that counts its own invocations is
counting _permitted_ invocations, and the gap between that number and what the
agent attempted is not visible from where you are standing.

**A registered tool agent fails against the API**, where the failure is typed.
Invoking one can raise:

- `sdk:aegis_sdk.GovernanceViolationError` — governance denied it. A budget was
  exhausted, an approval was required, a constraint refused. Retrying is wrong.
- `sdk:aegis_sdk.ServiceError` — including the fail-closed case where the
  governance service itself is unreachable. **The platform refuses rather than
  proceeding ungoverned**, which means an outage in the governance path presents
  as your tool being unavailable rather than as your tool running unchecked. That
  is the correct trade and it will still page someone at 3am.
- `sdk:aegis_sdk.NotFoundError`, `sdk:aegis_sdk.ValidationError` and
  `sdk:aegis_sdk.AuthorizationError` — the ordinary shapes.

Every one of these carries the HTTP status in `details["status_code"]`, and the
status is the discriminator rather than the class — two statuses in common use map
to no subclass at all and land on the base
`sdk:aegis_sdk.AgenticOSError`.
[`coc/guardrails/error-taxonomy.md`](../../coc/guardrails/error-taxonomy.md) has
the full table; read it before you write an `except` clause.

**What the platform does with a failing tool agent:** it records the invocation
and carries on. There is no automatic circuit breaker, no automatic
deactivation, and nothing that quarantines a tool that has failed _n_ times. If
you want a failing tool taken out of service, that is your operational decision,
expressed as `api:PATCH /api/v1/tool-agents/{id}/status` moving it to `suspended`.
Chapter 03.3 covers the status machine and the one-way edges in it.

## Versioning the contract, not just the code

An in-process tool's version is whatever you deployed. There is no platform
registry to disagree with you, which sounds simple and is exactly why the hazard
is easy to miss: **the governance around a tool is keyed on its name.**

So renaming a tool silently detaches it from every rule written about it. Nothing
errors. Nothing warns. The rules still exist, still parse, and now describe a tool
that no longer exists — while the renamed tool is governed by whatever the default
for an unrecognised name happens to be.

```
# DO      keep the name stable and version the behaviour behind it, OR
#         land the new name and the rules referencing it in one change
# DO NOT  rename a governed tool and treat the rules as someone else's problem
```

The same reasoning applies with more force to a widened _signature_. Adding an
argument that expands what the tool can do — a `force` flag, a destination that
was previously fixed — changes the tool's reach without changing its name, so
every rule keyed on that name now covers strictly more than it was written for.
Treat a widening signature change as a governance change and re-read the rules.

For a registered tool agent the versioning surface is explicit and is covered in
03.3; for an agent's own configuration it is
`api:POST /api/v1/agents/{id}/versions`, covered in 03.2.

## When you _do_ need to declare something

Finer-grained governance — rules about _categories_ of action rather than about
named tools — needs the platform to know what kind of effect a tool has. Reading a
file and deleting a database row are both "a tool call"; a policy that treats them
identically is not much of a policy.

Two vocabularies exist for that purpose, and they are the subject of the
cautionary tale below:

- **The tool registry** — keyed by tool id, and its ids are **snake_case**:
  `read_file`. This is the catalogue of tools the platform knows about.
- **The posture permission set** — which names tools the way the agent runtime
  does, in **PascalCase**: `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash`,
  `NotebookEdit`. This is what actually appears in a materialised allow/deny
  list.

**The two are not the same vocabulary, and nothing translates between them for
you.** A tool id that looks correct in one is simply absent from the other.

If you are adding a tool that needs category-level governance, work out which
vocabulary the consuming gate speaks _before_ you write the declaration, and check
that a producer actually emits in that vocabulary. That sentence is doing a lot of
work, and the next section is why.

## The cautionary tale: a vocabulary mismatch that disabled a gate

**Status: fixed.** What follows is a historical incident, not current behaviour.
It is here because it is the most instructive failure this subsystem has
produced, and because the shape of it is easy to recreate in your own code.

A fail-closed action-declaration gate resolved each tool's declared effect from
the **snake_case** tool registry. The runtime, meanwhile, emits **PascalCase**
names verbatim — the adapter passes the block's name straight
through, and it arrives at the gate unchanged as `tool_name`.

**There was no bridge between the two vocabularies.** Measured at the time across
the adapter layer:

```
snake_case tool id  ('read_file')   -> 0 occurrences
the runtime's own name field        -> 2 occurrences   <- positive control
alias / normalise tables anywhere   -> 0 occurrences
```

Note the positive control in the middle line. Without it, the zero on the first
line would be indistinguishable from a search that was simply looking in the
wrong place — a check that cannot produce a different answer when the
proposition is false is not evidence. That is a habit worth copying into your
own checks, and this book uses it throughout. The measured effect of merging the
gate unchanged:

```
Read -> HELD    Write -> HELD    Edit -> HELD
NotebookEdit / WebSearch / WebFetch / Task / TodoWrite -> HELD
Glob -> READ    Grep -> READ    Bash -> WRITE
```

`Read` is the most common call in the product, and under `delegated` posture the
enforced-execution path **returns** on a constraint violation rather than parking
the work — so an auto-claimed agent would die on its first file read.

Three things about this are worth carrying with you:

**The gate was correct and the effect was catastrophic.** The mechanism did
exactly what a fail-closed gate should do. It held actions it could not resolve.
Everything that went wrong went wrong upstream of it, in the fact that nothing
produced declarations in the vocabulary the gate consumed.

**A spot-check would have passed.** Glob, Grep and Bash resolved correctly — but
only because their lowercased spellings coincidentally equal a registry id. Three
tools working is exactly the sample that makes a developer stop checking.

**Fail-closed converted a benign bug into a total outage.** The mismatch had
existed all along and had been harmless, because everything fell through to an
`else "read"` default. Tightening the gate turned a latent vocabulary
disagreement into a shutdown. This is the general hazard of fail-closed design:
it does not create the disagreement, it _reveals_ it, all at once, in production.

The remedy was deliberately not improvised alongside the fix. Which vocabulary
is canonical is a design decision on a path that fails closed, and it was
settled separately rather than guessed at under time pressure. Declining to invent an answer under those conditions was the right
call.

## Practical guidance

**For an ordinary in-process tool.** Write it. Do not add Aegis-specific
plumbing, do not accept an identity argument, do not try to pre-declare
permissions. The hook will see the call.

**Make the governable facts arguments.** Anything a rule might need to reason
about has to be visible in the input, because that is the whole of what the gate
receives.

**If your tool spawns a subprocess.** Understand that it leaves the reach of every
in-process control at the moment it spawns — see chapter 01.2 on the egress
guard's stated coverage boundary. The pre-hook still fires on the tool call
itself, so the _decision to spawn_ is governed; anything the child process
subsequently does on its own is not.

**If your tool holds credentials, it holds them alone.** Aegis has no credential
for the system you are writing to and never sees the response. Rotation, scoping
and least privilege on that credential are yours, and they are not covered by
anything on this platform.

**If you need category-level governance.** Establish, with a command whose output
you can quote, that a producer emits declarations in the vocabulary your consumer
reads. "The registry has an entry for it" is **not** that check — in the incident
above the registry was fully populated and correct throughout. The registry was
never the broken part; the join to it was.

**If you are tightening a gate.** Enumerate what the change will now hold, and
measure it, before merging. In the incident above that table existed, which is
why the outage was caught in review rather than in production — the enumeration
is what caught it, not the intent behind the change.

## Before you hand a tool to an agent

1. **Which kind is it?** In-process, or a registered tool agent? If it is shared,
   invoked by more than one consumer, or has to be evidenced, it is the second and
   03.3 is your chapter.
2. **Are the governable facts arguments?** If the amount, the destination or the
   scope is inside an opaque handle, no argument-level rule can reach it.
3. **Does it spawn?** If so, govern the decision to spawn, because nothing here
   governs what happens afterwards.
4. **What does it do on failure?** Whose log receives the exception, and who reads
   that log?
5. **Is the name stable?** Every rule about this tool is keyed on the name you are
   about to freeze.
6. **Has it been exercised against something other than your production
   organisation?** [Chapter 03.5](05-testing-an-extension.md) covers how, and
   what each testing surface does and does not prove.

## What is not settled

The posture→permission mapping and the action-category vocabulary are two
different things and this chapter has been careful not to merge them. The posture
permission set is a materialized allow/deny list written into an agent's own
settings file (chapter 01.2); the tool registry is a catalogue of tool definitions
with declared effects. They overlap in the tools they name and they disagree in
how they spell them.

**UNVERIFIED:** whether a single canonical vocabulary has since been chosen and a
bridge landed between the two. The PascalCase posture permission set is present
and unchanged, and the fix — whatever form it took — is not annotated in a way
this edition could trace. Do not infer from this chapter that the two
vocabularies have been reconciled. Check before you rely on either.

**UNVERIFIED:** whether a _refused_ in-process tool call is recorded anywhere an
architect can read. The pre-hook has the information; whether it is durably
written and retrievable is not settled from what is reachable here. If your
compliance story depends on evidencing attempts that were blocked, establish this
against your own deployment before you promise it.

---

_Next: [03.2 — Agents, skills and pipelines](02-agents-skills-and-pipelines.md)_
