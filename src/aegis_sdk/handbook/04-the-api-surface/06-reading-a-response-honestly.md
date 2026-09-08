# 04.6 — Reading a response honestly

A call succeeded. You have an object. The question this chapter answers is which
parts of it you may act on, and what a field that is *not there* is telling you.

That question is load-bearing here in a way it is not on an ordinary API. The
objects you read describe an organisation's governance — who delegated what to
whom, under what bound, and what was decided. **A field you read wrongly becomes
a claim in an evidence export**, and the difference between "the server said no"
and "the client did not model the answer" is exactly the difference between a
finding and a mistake.

## Required, optional, and the third thing

Across the 78 models this package exports there are **263 required fields and
226 optional ones** — so a bit under half of everything you can read is
optional. Seven models have no required field at all.

"Required" and "optional" here are properties of **this client's model**, not
promises by the deployment. That is the distinction the whole chapter turns on:

| you see | it means |
| --- | --- |
| a **required** field, populated | the deployment sent it — the client refuses to construct the object otherwise |
| an **optional** field, populated | the deployment sent it |
| an **optional** field, `None` | the deployment sent `null`, **or** sent nothing at all — you cannot tell which |
| a **required** field missing | you never got an object; the call raised instead |

**The third row is the one to internalise.** An optional field reading `None`
collapses three different situations — the deployment does not have this value,
the deployment does not implement this field, and this deployment version predates
it — into one indistinguishable answer. If a decision depends on the difference,
read the raw body:

```python
raw = await client._http.request("GET", f"/api/v1/agents/{agent_id}")
print("field present in the response:", "model_id" in raw)
print("field value:", raw.get("model_id"))
```

Absent and `null` are different facts and only the raw body carries the
difference. Reach for it for a diagnosis, not as a habit — the typed path is the
one that will keep working.

## What each of the models you will read most actually guarantees

| model | required | notable optional |
| --- | ---: | --- |
| `sdk:aegis_sdk.User` | 6 — `id`, `email`, `name`, `organization_id`, `organization_name`, `role` | `personas`, `status`, `mfa_enabled`, `last_login_at` |
| `sdk:aegis_sdk.Agent` | 9 — including `agent_type`, `unit_type`, `status`, `workspace_id` | `model_id`, `system_prompt`, `capabilities`, `description` |
| `sdk:aegis_sdk.Objective` | 10 — including `status`, `created_by`, `agent_id` | `priority`, `assigned_to`, `metadata`, `completed_at` |
| `sdk:aegis_sdk.TrustChain` | **2** — `agent_id`, `genesis` | `delegations`, `status`, `human_origin` |
| `sdk:aegis_sdk.APIKey` | 4 — `id`, `name`, `key_prefix`, `created_at` | `scopes`, `expires_at`, `last_used_at` |
| `sdk:aegis_sdk.AuthToken` | **1** — `access_token` | `refresh_token`, `expires_in`, `expires_at`, `user` |

Two rows deserve a second look.

**`TrustChain` requires only two fields**, and `delegations` — the thing you are
almost certainly reading it *for* — is optional and defaults to empty. An empty
delegation list therefore means either "this chain has no delegations" or "this
response did not carry them", and the model cannot distinguish them. Do not
report "no delegated authority" from an empty list without confirming the field
was sent.

**`AuthToken` requires only `access_token`.** `expires_in` **defaults to 3600**
when the deployment sends nothing — a *client-side* default, not something the
deployment told you. A refresh scheduler built on `token.expires_in` may be
scheduling against a number nobody sent. Prefer `expires_at` when it is
populated, and treat its absence as "unknown", not "one hour".

That is the general shape of the hazard: **a default is an answer the client
invented.** It is indistinguishable, at the point of use, from an answer the
deployment gave.

## Fields the deployment sends and you never see

**Unknown fields are silently dropped.** Every model ignores keys it does not
declare. Measured: constructing a `sdk:aegis_sdk.User` with an extra field the
model does not know about succeeds, and the attribute simply does not exist on
the result.

This is the right default — a client that raised on a new server field would
break on every deployment upgrade — and it has a real cost worth naming: **if
your deployment is newer than your SDK, its new fields are invisible to you and
nothing says so.** The typed path cannot show you what it does not know about.
The raw body can, and comparing the two is a five-line check worth running once
after any deployment upgrade:

```python
from aegis_sdk import User

raw = await client._http.request("GET", "/api/v1/auth/me")
print("sent but not modelled:", sorted(set(raw) - set(User.model_fields)))
```

**One field is dropped by design and costs you a credential**: the one-time
secret returned when you create an API key. That is
[04.3](03-credentials-and-keys.md), and it is the sharpest instance of this
whole class.

## Values the client rewrites on the way in

Two rewrites happen quietly and both are defensible. Know about them, because
each turns a server value into a different client value.

**An unrecognised agent type becomes `unknown`.** If a deployment introduces an
agent type this SDK release predates, `sdk:aegis_sdk.Agent` coerces it to
`sdk:aegis_sdk.AgentType`'s `unknown` member rather than failing. That keeps one
unfamiliar row from failing a whole list — the correct trade for a read model —
and it means **`agent_type == "unknown"` is not a state the platform has.** It is
this client telling you it is out of date. Treat it as a prompt to upgrade, not
as a property of the agent.

**Two fields on a streamed session message are generated locally.** In
`sdk:aegis_sdk.execution.SessionsModule.stream_messages`, the wire events carry
no message id and no timestamp, so the client synthesises both: `id` is a fresh
random identifier and `created_at` is **your machine's clock at the moment of
receipt**. Neither is a server fact. Do not correlate on that `id` — nothing on
the deployment knows it — and do not put that `created_at` in an audit narrative,
because it measures when your process read the event, not when the event
happened.

## The repr shows less than the object holds

Two fields are deliberately hidden from the printed form of their objects:
`email` on `sdk:aegis_sdk.User`, and both tokens on `sdk:aegis_sdk.AuthToken`.
They are present on the object and simply do not appear when you print it.

That protection is correct — a logged repr is how credentials and personal data
escape — and it produces one specific confusion worth pre-empting.
[01.3](../01-orientation/03-your-first-session.md) tells you to `print(me)` as
your first smoke test, and the email you are looking for will not be in the
output. It is there:

```python
me = await client.auth.get_current_user()
print(me)              # no email — hidden from the repr, by design
print(me.email)        # the value, when you have decided you want it in your logs
```

## A checklist for reading any response

1. **Ask whether the field is required or optional** before you branch on it.
   `type(obj).model_fields["x"].is_required()` answers it on your own build, and
   the answer is a property of your SDK version.
2. **Never read `None` as a fact about the deployment.** It is `null`, or absent,
   or not implemented — three different findings wearing one value.
3. **Never read a default as an answer.** `expires_in` of 3600 and `page` of 1
   are the client's inventions until you have confirmed the deployment sent them.
4. **Never read an empty collection as "none exist"** unless the field was
   required. An empty `delegations`, an empty `personas` and an empty page all
   have two possible causes, and only one of them is about your data.
5. **Drop to the raw body for a diagnosis, and only for a diagnosis.** It is the
   only place where present-versus-absent is visible, and it is the wrong
   long-term dependency, because it is the layer with no contract at all.
6. **When a reading will become evidence, record what you actually observed** —
   the operation you called, the status you got, and the field you read — rather
   than the conclusion you drew from it. That distinction is the whole of
   [02.6](../02-working-through-the-harness/06-approvals-holds-and-evidence.md)
   and it starts here, at the point where a `None` becomes a sentence in a report.

---

_This is the last chapter of part 04._
