# 01.2 — The mental model

## Aegis is not a proxy

When a governed agent writes to an external system — creates a Jira ticket, pushes
a commit, sends a message — the request does **not** travel to Aegis for Aegis to
forward. Aegis never takes possession of the call. There is no generic egress
gateway, no outbound request broker, no forwarding layer.

This is the thing people get wrong, and they get it wrong in a specific way: they
assume that because the platform can _stop_ an action, it must be _carrying_ the
action. It is not. It is standing beside it.

Here is the actual shape **on the `claude_agent_sdk` runtime**, which is the one
this model describes. Runtimes differ in what sits on the call path, so
establish which one your deployment runs before designing against these steps:

1. The agent decides to call a tool.
2. Before that call executes, a **`PreToolUse` hook fires on the agent's own call
   path**, inside the agent's own process.
3. The hook consults Aegis and gets back a verdict.
4. On a permitting verdict, the **original call proceeds and the tool itself does
   the work**. Aegis is no longer involved.
5. Afterwards a **`PostToolUse` hook** records what happened.

The verdict happens _in line_, not _in between_.

### Two wrong models, and why each fails

**Wrong model 1: "ask permission, then act."** The agent asks Aegis whether it
may do something, receives a yes, and then does it. This is wrong because it is
_advisory_ — an agent that skips the asking step proceeds unimpeded. Governance
that depends on the governed party choosing to participate is not governance.
Hooking the call path is what makes the check something that happens _to_ the
agent rather than something the agent invokes.

> ⛔ **The enforcement point is a property of the runtime, so establish which
> runtime your deployment runs before you design against a hook.**
>
> The hook model described here is the **`claude_agent_sdk`** runtime. The
> **default** runtime is `kaizen_native`, which places no pre-execution hook on
> the call path. The platform declares this rather than leaving you to infer it:
> it emits a `default_has_no_pre_execution_gate` notice at boot naming the
> runtime and the enforcement point, and it will _refuse to start_ — not warn —
> when the deployment has set the environment variable requiring a
> pre-execution gate. A deployment that must have one says so in configuration
> and the platform holds it to that, fail-closed.
>
> **The property that holds on every runtime is custody, not interception: the
> agent does not hold the keys.** Credentials for the systems your tools write
> to are not the agent's to present. That is true whatever runtime is
> configured, and it is the one to reason from.

**Wrong model 2: "intercept and forward."** The agent's request goes to Aegis,
Aegis evaluates it and then performs the write on the agent's behalf. This is
wrong because there is nothing here that does it. There is no generic forwarding
component — no egress proxy, no outbound gateway, no request broker. You can
confirm this from your own side: no operation in this client accepts an outbound
request and returns a foreign system's response, and none names a forwarding
endpoint. If your design has Aegis making the outbound call, you are designing a
component that does not exist and will have to be built.

The distinction is not academic. Under the correct model, Aegis needs no
credentials for the external system, never sees the response body, and cannot
become a bottleneck or a single point of failure for the agent's actual work. All
three of those follow directly from _not_ being in the data path.

## The reference implementation, and what its shape tells you

The reference implementation is the Claude Code wrapper. It registers **four
hooks** with the agent runtime's hook system — two before a tool call and two
after:

| when          | hook               | what it does                               |
| ------------- | ------------------ | ------------------------------------------ |
| `PreToolUse`  | trust verification | asks the trust plane for a verdict         |
| `PreToolUse`  | budget enforcement | refuses if the spend envelope is exhausted |
| `PostToolUse` | audit logging      | records what happened                      |
| `PostToolUse` | cost recording     | attributes the spend                       |

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

That return type — `dict` in, `dict` out — _is_ the proof that this is
interception rather than proxying. A forwarding layer would return the external
system's response. This returns the arguments.

Trust verification itself is a call _out_ to the trust plane, keyed on the agent id and an
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
_upgrade_ a verdict: a `full` thoroughness setting promotes `auto_approved` to
`flagged`, so a stricter setting produces more **signal** rather than merely more
refusals — if you set thoroughness high and see your flagged count rise, that is
the feature, not a regression. And **`held` is not a soft `blocked`.** Under
`delegated` posture the enforced-execution path _returns_ on a constraint
violation rather than parking the work, which means a held action **ends the
agent's run** instead of queuing politely. Plan for a held action to terminate
the run, not to pause it. Chapter 03.1 has the incident where that mattered.

## The permission set is materialized, not asked for

The clearest evidence that governance rides the agent's own call path is that
Aegis _writes the agent's permission file_. Trust posture is materialised into a
concrete allow/deny list before the agent runs — you can read the posture an
agent currently holds at `api:GET /api/v1/agents/{id}/trust-posture`:

| Posture              | allow                  | deny                                    |
| -------------------- | ---------------------- | --------------------------------------- |
| `pseudo`             | —                      | `Bash`, `Edit`, `Write`, `NotebookEdit` |
| `supervised`         | `Read`, `Glob`, `Grep` | `Bash`, `Edit`, `Write`, `NotebookEdit` |
| `shared_planning`    | + `Edit`, `Write`      | —                                       |
| `continuous_insight` | + `Bash`               | —                                       |
| `delegated`          | + `NotebookEdit`       | —                                       |

This is written into the agent's own `settings.json` — its native permission
mechanism — and the selection **falls back to `supervised` for an unrecognised
posture, not to the permissive end**. That default is the whole design in one
line: an unknown posture is treated as a constrained one. A
proxy would not need this file to exist. An in-line interceptor does, because the
enforcement point is inside the agent's runtime, and the runtime has to be told
what it may do.

## The one egress control, and what it covers

Aegis is not a proxy for _tool calls_. One thing is gated outbound, and it is
worth naming precisely: **LLM content**.

A fail-closed classification guard governs outbound **LLM content**. Its terms:

- It ships the **mechanism** only. Which environments are guarded is
  configuration the deployment sets, and the classification **policy** is
  supplied by the deployment, through a classifier it installs. The canonical
  default is no guarded environment and no classifier — an inert pass-through
  with zero overhead. This is deliberate: canonical Aegis stays generic and client
  deployments adapt.
- Inside a guarded environment it is **fail-closed** — an _absent_ classifier and
  a classifier that _raises_ both produce DENY. A
  guarded environment with undefined policy does not let content out.
- It covers the LLM calls your own process makes, and only those.

**A runtime that spawns a subprocess leaves that coverage the moment it spawns.**
Four do — `claude_agent_sdk`, `claude_code`, `openai_codex` and `gemini_cli` —
and each launches an external CLI that performs its own egress, outside any
in-process content guard, whatever the classifier would have said. Those four
carry a **structural** control instead of a classifying one: a deployment that
must guarantee no external-LLM egress disables them, and constructing one then
raises rather than succeeding quietly. Structural inability to construct it is
the control, and it is stronger than a policy that inspects what is sent. If that
guarantee is one you have to make, establish which of the four your deployment
has enabled before you promise it.

So: content leaving _your process_ toward an LLM can be classified. A tool call
an agent makes is governed at the hook, not forwarded. Neither of those is a
general-purpose egress proxy, and no such thing exists here.

## What follows from all this

If you remember one sentence: **where there is a hook, the hook decides and the
tool acts** — and the enforcement point is a property of the runtime, so
establish which runtime your deployment runs before you design against it.

Practical consequences for anything you build:

- Aegis holds no credentials for the systems your tools write to. Your tool does.
- A verdict is about an _intent_ — a tool name and its arguments — never about a
  response body, because no response exists yet when the verdict is made.
- If governance must cover a new execution path, the question is not "how do we
  route it through Aegis" but "where on that path does the hook fire". A path with
  no hook is ungoverned no matter how much policy exists elsewhere.
- Anything that spawns a subprocess leaves the reach of every in-process control
  the moment it spawns. Govern it before the spawn, or disable it.

---

_Next: [01.3 — Your first working session](03-your-first-session.md)_
