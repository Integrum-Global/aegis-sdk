# 01.2 — The mental model

## Aegis is not a proxy

When a governed agent writes to an external system — creates a Jira ticket, pushes
a commit, sends a message — the request does **not** travel to Aegis for Aegis to
forward. Aegis never takes possession of the call. There is no generic egress
gateway, no outbound request broker, no forwarding layer.

This is the thing people get wrong, and they get it wrong in a specific way: they
assume that because the platform can *stop* an action, it must be *carrying* the
action. It is not. It is standing beside it.

Here is the actual shape **on the `claude_agent_sdk` runtime**, which is the one
this model describes. It is not the default — see the runtime qualifier below,
and check which runtime you are on before designing against these steps:

1. The agent decides to call a tool.
2. Before that call executes, a **`PreToolUse` hook fires on the agent's own call
   path**, inside the agent's own process.
3. The hook consults Aegis and gets back a verdict.
4. On a permitting verdict, the **original call proceeds and the tool itself does
   the work**. Aegis is no longer involved.
5. Afterwards a **`PostToolUse` hook** records what happened.

The verdict happens *in line*, not *in between*.

### Two wrong models, and why each fails

**Wrong model 1: "ask permission, then act."** The agent asks Aegis whether it
may do something, receives a yes, and then does it. This is wrong because it is
*advisory* — an agent that skips the asking step proceeds unimpeded. Governance
that depends on the governed party choosing to participate is not governance.
Hooking the call path is what makes the check something that happens *to* the
agent rather than something the agent invokes.

> ⛔ **Do not upgrade that into "the agent cannot get around the hook."** This
> chapter said exactly that in an earlier revision, and it is false on the
> shipped default.
>
> The hook model described here is the **`claude_agent_sdk`** runtime. The
> **default** agent runtime is `kaizen_native`, which has **no pre-execution
> hook at all** — there is nothing to route around, because there is nothing in
> the path. The product knows this and says so out loud: it emits a
> `default_has_no_pre_execution_gate` warning at boot naming the runtime and the
> missing gate, and it will *refuse* to start rather than warn if the deployment
> has set the environment variable requiring a pre-execution gate.
>
> **The claim that is true on every runtime is about custody, not interception:
> the agent does not hold the keys.** Credentials for the systems your tools
> write to are not the agent's to present. That property does not depend on
> which runtime is configured, and it is the one to reason from.
>
> Which runtime you are on decides what else is true. Check it before designing
> against a hook.

**Wrong model 2: "intercept and forward."** The agent's request goes to Aegis,
Aegis evaluates it and then performs the write on the agent's behalf. This is
wrong because there is nothing here that does it. There is no generic forwarding
component — no egress proxy, no outbound gateway, no request broker. You can
settle this from your own side without the platform source: nothing in this
client's surface accepts an outbound request and returns a foreign system's
response, and no operation in it names a forwarding endpoint. If your design has
Aegis making the outbound call, you are designing a component that does not exist
and will have to be built.

The distinction is not academic. Under the correct model, Aegis needs no
credentials for the external system, never sees the response body, and cannot
become a bottleneck or a single point of failure for the agent's actual work. All
three of those follow directly from *not* being in the data path.

## The reference implementation, and what its shape tells you

The reference implementation is the Claude Code wrapper. It registers **four
hooks** with the agent runtime's hook system — two before a tool call and two
after:

| when | hook | what it does |
| --- | --- | --- |
| `PreToolUse` | trust verification | asks the trust plane for a verdict |
| `PreToolUse` | budget enforcement | refuses if the spend envelope is exhausted |
| `PostToolUse` | audit logging | records what happened |
| `PostToolUse` | cost recording | attributes the spend |

**Note the fallback structure, because it tells you the posture of the design.**
The wrapper prefers to register with the runtime's own hook manager; if that
registration raises, it falls back to an internal registry rather than
proceeding ungoverned. Failing to register is not treated as permission to run
unhooked.

The pre-hook's shape tells you everything about the model:

```python
async def pre_tool_hook(
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    ...
```

It receives the tool's **name** and its **input**, and it returns the tool input,
possibly modified. It does not return a response, because it never made a
request. On failure it raises — a trust-verification error, or a
constraint-violation error from the constraint enforcer — and the tool call never
happens. On success the call continues with the input the hook handed back.

That return type — `dict` in, `dict` out — *is* the proof that this is
interception rather than proxying. A forwarding layer would return the external
system's response. This returns the arguments.

Trust verification itself is a call *out* to the trust plane, keyed on the agent id and an
action string built as `f"tool:{tool_name}"`, with the organisation and user
carried in the context — **never taken from anything the tool says about
itself**.

## The verdicts

The evaluation resolves into CARE's four-zone verification gradient. Four
values, and **exactly four** — you will see one of them on the wire as the
verdict's `level`:

```
auto_approved / flagged / held / blocked
```

- **`auto_approved`** — proceed, recorded.
- **`flagged`** — proceed, but surfaced for attention.
- **`held`** — stopped pending a human decision.
- **`blocked`** — refused.

Two behaviours worth knowing because they surprise people. Thoroughness can
*upgrade* a verdict: a `full` thoroughness setting promotes `auto_approved` to
`flagged`, so a stricter setting produces more **signal** rather than merely more
refusals — if you set thoroughness high and see your flagged count rise, that is
the feature, not a regression. And **`held` is not a soft `blocked`.** Under
`delegated` posture the enforced-execution path *returns* on a constraint
violation rather than parking the work, which means a held action **ends the
agent's run** instead of queuing politely. Plan for a held action to terminate
the run, not to pause it. Chapter 03.1 has the incident where that mattered.

## The permission set is materialized, not asked for

The clearest evidence that governance rides the agent's own call path is that
Aegis *writes the agent's permission file*. Trust posture is materialised into a
concrete allow/deny list before the agent runs — you can read the posture an
agent currently holds at `api:GET /api/v1/agents/{id}/trust-posture`:

| Posture | allow | deny |
|---|---|---|
| `pseudo` | — | `Bash`, `Edit`, `Write`, `NotebookEdit` |
| `supervised` | `Read`, `Glob`, `Grep` | `Bash`, `Edit`, `Write`, `NotebookEdit` |
| `shared_planning` | + `Edit`, `Write` | — |
| `continuous_insight` | + `Bash` | — |
| `delegated` | + `NotebookEdit` | — |

This is written into the agent's own `settings.json` — its native permission
mechanism — and the selection **falls back to `supervised` for an unrecognised
posture, not to the permissive end**. That default is the whole design in one
line: an unknown posture is treated as a constrained one. A
proxy would not need this file to exist. An in-line interceptor does, because the
enforcement point is inside the agent's runtime, and the runtime has to be told
what it may do.

## The one genuine egress control, and its limits

The paragraph above says Aegis is not a proxy for *tool calls*. That is exactly
true, and it would be careless to leave you with "Aegis never gates anything
outbound", because one thing is gated outbound: **LLM content**.

There is a fail-closed classification guard for outbound **LLM content**. Read
its terms precisely, because it is narrower than the name suggests:

- It ships the **mechanism** only. Guarded environments come from
  `GUARDED_ENVIRONMENTS` config; the classification **policy** is supplied by the
  deployment via a classifier the deployment installs. The canonical
  default is no guarded environments and no classifier — an inert pass-through
  with zero overhead. This is deliberate: canonical Aegis stays generic and client
  deployments adapt.
- Inside a guarded environment it is **fail-closed** — an *absent* classifier and
  a classifier that *raises* both produce DENY. A
  guarded environment with undefined policy does not let content out.
- It covers four in-process surfaces: the HTTP LLM-provider adapters, the in-process
  agentic runtime adapters, the `KaizenClient` facade, and raw
  `kailash.Agent`/`BaseAgent` `.run()` sites.

And it names its own coverage boundary, which is the part to remember: it
**cannot** classify content leaving through the
*subprocess-spawning* runtime adapters — `claude_agent_sdk`, `claude_code`,
`openai_codex`, `gemini_cli`. Each spawns an external CLI that performs its own
egress, and an in-process content guard has no way to intercept that. For a
deployment that must guarantee no external-LLM egress, classification is
insufficient for those four; they have to be **disabled**, so that constructing
one raises rather than succeeding quietly. Structural inability to construct the
adapter is the control — not a policy that inspects what it sends.

So: content leaving *your process* toward an LLM can be classified. A tool call
an agent makes is governed at the hook, not forwarded. Neither of those is a
general-purpose egress proxy, and no such thing exists here.

## What follows from all this

If you remember one sentence: **where there is a hook, the hook decides and the
tool acts** — and on the default runtime there is no pre-execution hook, so
establish which runtime you are on before you rely on that sentence.

Practical consequences for anything you build:

- Aegis holds no credentials for the systems your tools write to. Your tool does.
- A verdict is about an *intent* — a tool name and its arguments — never about a
  response body, because no response exists yet when the verdict is made.
- If governance must cover a new execution path, the question is not "how do we
  route it through Aegis" but "where on that path does the hook fire". A path with
  no hook is ungoverned no matter how much policy exists elsewhere.
- Anything that spawns a subprocess leaves the reach of every in-process control
  the moment it spawns. Govern it before the spawn, or disable it.

---

*Next: [01.3 — Your first working session](03-your-first-session.md)*
