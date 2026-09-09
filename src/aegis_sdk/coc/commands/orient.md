---
name: orient
description: "Establish the target and the instrument before touching anything — name the deployment, name the credential, run the probe, and record what it could not tell you."
stage: 01-orientation
---

You are starting work against a **deployed Aegis you did not build and cannot
read the source of**. Everything downstream inherits whatever you get wrong in
the next five minutes, and the two things most often gotten wrong here are which
deployment you are pointed at and which kind of credential you are holding.

Run this before designing anything, and run it again after any change of URL,
credential or environment.

## 1 — Name the deployment, out loud, in this session

```bash
echo "$AGENTIC_OS_BASE_URL"
```

There is **no default**. If that prints nothing, stop and get one; do not guess a
host, and do not carry one over from an earlier session.

State the host in your own words before you continue: *"I am working against
`<host>`."* This is not ceremony. A guard in this repository refuses a mutating
call whose target it cannot see you name, and the reason is that a client's
production deployment and a scratch one differ by a substring.

If more than one deployment is in play — a client's and your own — say which is
which now, and never let a later step resolve the ambiguity by picking one.

## 2 — Name the credential, and say what kind it is

You are holding an **API key**, a **session token**, or both. They are not
interchangeable and most of what looks like a permissions problem is this
distinction wearing a `403`.

```bash
[ -n "$KEY" ] && echo "api key: present"
[ -n "$SESSION_TOKEN" ] && echo "session token: present"
```

An answer that is true for a session and false for a key, given without saying
which, is worse than no answer. Load the **credential-reachability** guardrail
before you interpret any refusal.

⛔ The credential is the client's, not yours. It does not go into a file, a
commit message, a log line, a scratch note, or any destination other than the
call itself. A guard here enforces that, and it compares against your live
environment values rather than against a shape, so a redaction that "looks
wrong" is usually the guard being right.

## 3 — Run the probe, and read its exit code before its output

```bash
python -m aegis_sdk.coc.probe --transports-only            # offline, no credentials
python -m aegis_sdk.coc.probe --base-url "$AGENTIC_OS_BASE_URL" \
  --api-key "$KEY" --token "$SESSION_TOKEN"
```

| exit | means | what you may conclude |
| ---- | ----- | --------------------- |
| `0` | it answered | these routes are reachable **by this credential, on this deployment, now** |
| `3` | UNDETERMINED | **nothing.** Not "clean" — it could not tell |

The probe verifies its own credentials against a control operation first, which
is the step that separates an expired token from a healthy API. Those two produce
identical output from a probe that skips it.

**A `3` is not a `0` with a warning.** If you get one, fix the credential and
re-run; do not proceed and do not report reachability. Load the
**reading-a-measurement** guardrail if you are tempted to write the number down.

## 4 — Write down what the probe could NOT tell you

This is the step people skip, and it is the one that makes the rest honest. The
probe answers *admission*. It does not answer:

- **whether a route does what you think** — a route that admits you when it
  should not returns `200`, and nothing in this repository can see that;
- **whether the client's model matches the server's** — the client's declared
  operations are this package's *belief* about the API, and where it is wrong it
  is wrong confidently;
- **anything about the platform's implementation.** If a question can only be
  answered by reading the platform's source, it cannot be answered from here.
  Say so, and say what would settle it.

Record the three separately from what you observed. "This client declares the
operation" and "the deployment serves the operation" are different claims and
only the first is free.

## 5 — Read the mental model before you design

The single most expensive misunderstanding on this platform is about *where*
governance happens, and every design built on the wrong guess has to be rebuilt.
Read the handbook chapter **The mental model** now, not later. It is short, and
it decides everything in `/construct`.

## What this leaves you holding

- a named deployment, said out loud
- a named credential type
- a probe receipt with a verdict that is `0`, not `3`
- an explicit list of what remains unverified

Carry all four into `/construct`. If any is missing, you are not oriented — you
are guessing with a URL.

## Next

- `/construct` — stand up and run the governed organisation
- `/extend` — add a capability to one that already exists
- `/diagnose` — something already failed and you need to attribute it

**Skills:** `working-against-a-deployment` is the order of operations for the
whole engagement and is worth loading now.
