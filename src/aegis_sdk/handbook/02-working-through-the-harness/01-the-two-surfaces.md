# 02.1 — The two surfaces

Aegis has one API and two clients over it: **this SDK**, which you drive from
your own code, and **the web console**, which people use in a browser. This
chapter is about choosing between them, because the choice is not a matter of
taste and getting it wrong is expensive in a way that shows up months later.

## They are the same system

Both surfaces speak to the same HTTP API and are governed by the same checks. The
console has no privileged back channel, and the SDK has no bypass. A call that is
refused for you in one is refused in the other, for the same reason, and produces
the same audit entry.

*Design intent, not observable:* the enforcement lives behind the API rather than
in either client, which is why parity holds without anyone maintaining it. You
can act on that — a control you verified through the SDK does not need
re-verifying through the console — but you cannot observe it from here, so it is
labelled rather than asserted.

## Why the harness is the primary surface

Not because it is more powerful. Because of what it leaves behind.

| | harness | console |
| --- | --- | --- |
| **reviewable before it runs** | yes — it is code, in a branch, in a diff | no — the action *is* the record |
| **repeatable** | yes — run it against staging, then production | no — someone repeats it by hand, differently |
| **diffable when it drifts** | yes — re-run and compare | only by reading screens |
| **rebuildable after an incident** | yes | from memory |
| **legible to a non-programmer** | no | yes |
| **good for a decision that needs a person** | no | yes |

The asymmetry is the point. An organisation's *structure* — who reports to whom,
what each role's delegate may spend, which units can see which knowledge — is
configuration that outlives the person who set it and must be defensible to an
auditor. Configuration like that belongs in code.

An organisation's *operation* — approving a held payment, reading why an
objective stopped, checking an inbox — is human judgment happening now. That
belongs on a screen.

**A rule of thumb that holds up:** if the action would be identical next quarter
in a fresh environment, write it in the harness. If the action is a person
deciding something about a specific case, do it in the console.

## What only the console can do

Be honest about this, because "harness-first" is sometimes read as
"harness-only", and that produces operators who cannot do their jobs.

- **Answer a held decision as yourself.** Approvals are attributable to a human,
  and the console is where a human is authenticated as themselves rather than as
  a provisioning key.
- **Read state you have not scripted a view for.** Dashboards, activity feeds,
  drift alerts and the inbox are assembled views. You can reach the same data
  through the SDK, but you would be rebuilding a screen that already exists.
- **Be used by people who do not write Python.** Most of an organisation's users
  are only ever going to see the console. Part 05 is written for them, and it is
  worth reading if you are designing what they will meet.

## What only the harness can do

- **Provision.** Creating an organisation, its units, its roles and their
  envelopes as one reviewable transaction.
- **Promote.** The same script, a different `AGENTIC_OS_BASE_URL`.
- **Assert.** You can write checks about your own organisation — "no envelope
  permits an external wire transfer", "every unit has a head role" — and run them
  on a schedule. Nothing in the console does this, and nothing in Aegis does it
  for you.
- **Bulk anything.** Two hundred roles is a loop. It is not two hundred forms.

## The pattern every chapter in this part follows

```python
# HARNESS — what you write
unit = await client.units.create(name="Treasury", unit_type="department")
```

> **In the console:** *Organisation → Units → New unit.* Same result, same audit
> entry, no reviewable artifact.

When a chapter names a console screen, it is telling you where a human will meet
the thing you just built — not suggesting you build it there.

## One caution about mixing them

If you provision with a script and then let people edit the result in the
console, your script stops describing reality and starts describing an intention.
That is fine as long as everyone knows which one is authoritative. Decide early,
write it down, and prefer making the script re-runnable (create-or-update) over
forbidding console edits, which nobody will honour under pressure.

---

*Next: [02.2 — Standing up an organisation](02-standing-up-an-organization.md)*
