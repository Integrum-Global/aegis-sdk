---
name: working-against-a-deployment
description: Connect to a running Aegis, authenticate, submit an objective, read the inbox, handle a held item — and know which of those your credential can actually do.
---

# Working against a deployed Aegis

You have a URL, a credential, and this repository, cloned and open. You do not
have the platform source and you cannot boot it. This is the path from that
starting point to a completed piece of work.

**The prose for each step is in the shipped handbook and is not repeated here.**
Duplicating it would produce two copies that drift, and the handbook's copy is
the one that is anchor-checked. This skill is the _order of operations_ and the
decisions between the steps.

Chapters are named by **title**, not by number. The shipped handbook is being
renumbered, and a number printed here would be a reference that resolves today
and misleads next month.

| Step                | Handbook chapter          |
| ------------------- | ------------------------- |
| First login         | _First login_             |
| Submit an objective | _Submitting an objective_ |
| Your inbox          | _Your inbox_              |
| Something is held   | _When something is held_  |
| What you can see    | _What you can see_        |
| Calling the API     | _The API surface_         |

## Step 0 — Establish what you are holding, before anything else

Do this first, every time, including when you are confident. It costs one call.

```python
import asyncio
from aegis_sdk import AgenticOSClient, ClientConfig

async def main() -> None:
    client = AgenticOSClient(config=ClientConfig(base_url=BASE_URL, api_key=KEY))
    me = await client.auth.get_current_user()   # api:GET /api/v1/auth/me
    print(me)

asyncio.run(main())
```

**If that raises a validation error naming `role`, you have not found a broken
deployment.** `sdk:aegis_sdk.User` requires `role` to be a string and a key
principal is documented as having none — read the fallback in the credential
guardrail before concluding anything.

Read two things in the result and nothing else matters yet:

- **the organisation** your credential resolves to — everything you see later is
  scoped to it, and a body field naming a different one is ignored;
- **the personas list.** If it is empty you are holding an API key, and a large
  part of the API is closed to you no matter how the key is scoped. That is the
  single most expensive surprise on this platform. Read [the credential guardrail](../guardrails/credential-reachability.md)
  beside this file before you debug anything as a permissions problem.

## Step 1 — Find out what your credential can reach, by measuring it

Do not derive this from documentation and do not derive it from scopes. Ask your
deployment:

```
python -m aegis_sdk.coc.probe --base-url https://<your-deployment> \
    --api-key "$KEY" --token "$SESSION_TOKEN"
```

It prints the parameter-free read operations your key is refused and your
session is served. Those are the calls where a session is the answer and no
scope change will help.

**The two-credential form is the one that answers the question.** With one
credential a 403 cannot be attributed — "your credential type cannot reach
this" and "you lack a permission" produce the identical response. The probe
says so and exits differently rather than pretending otherwise.

**Read its exit code, not its silence.** `0` clean, `1` findings, `3`
UNDETERMINED — which is what you get when a credential could not authenticate,
because at that point everything is refused and a count of zero findings would
mean nothing.

## Step 2 — Submit an objective, then stop assuming

Submission is covered in the handbook's chapter on objectives and the work
loop. The part worth adding here is what to do
immediately afterwards: **poll the objective rather than trusting the submit
response**. Acceptance of a request is not execution of it, and the platform is
explicitly a governance layer — an objective can be admitted and then held.

## Step 3 — Work the inbox

The handbook's chapter on approvals and evidence covers this. One thing that is
not there and that you need: an empty inbox and
an inbox you are not permitted to read are the same shape from the client side —
a successful call returning no records. Confirm with step 0 that your credential
carries the personas that surface implies before you conclude there is no work.

## Step 4 — When something is held

The handbook covers what a hold is and how to release it. The decision this
skill adds:

**Never resolve a hold by widening the credential that hit it.** If a hold is a
governance decision, widening is not the remedy. If a refusal is the credential
trap in step 1, widening does nothing at all, because scopes are not consulted
on that path — you end the day holding a more powerful credential and the same 403. Widening a credential to clear an undiagnosed refusal is the wrong move in
both branches, which is what makes it worth a rule.

## Step 5 — Before you report anything as working

- Say which credential the result was obtained with.
- Say whether you called the deployment or read the client. A symbol in this
  package is not the server implementing it.
- If a number came out of a compliance or analytics surface, read the
  measurement guardrail first. Several of those fields are three-valued and two
  of the three states render as zero.

## What this skill deliberately does not cover

Adding a route, changing a gate, or altering platform behaviour. That needs the
platform source, which is not part of what you were given, and no amount of
client-side work substitutes for it. When the answer is "this needs a platform
change", the useful output is a precise report of the observed behaviour — the
call, the credential, the status, the body — not a workaround.
