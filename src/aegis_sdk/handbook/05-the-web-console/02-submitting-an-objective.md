# 05.2 — Submitting an objective

## Ask for an outcome, not for a task

The box on your home screen is headed **"What would you like to accomplish?"**
and the prompt underneath asks you to state it in natural language. That is
meant literally. You are describing a result you want, in a sentence or two, the
way you would to a capable colleague.

You do not need to break the work down. The system does that, shows you its plan,
and waits for you to approve it before doing anything.

## Writing it

The box behaves like a message field:

- **Enter** submits. **Shift+Enter** starts a new line.
- **Cmd/Ctrl+K** jumps your cursor into it from anywhere on the page.
- It grows as you type, up to **2,000 characters**. A counter appears once you
  are past a hundred or so, and warns you as you approach the limit.
- There is a microphone control if you would rather speak it.

Once you have typed a few characters it will start offering completions based on
what you are writing. These are genuine suggestions drawn from the system,
unlike the four fixed examples shown on an empty box.

## The two controls underneath, which are the important part

Directly below the box are two collapsed controls. Most people ignore them.
They are the only place you set the terms of the work *before* it starts, and
they are worth thirty seconds.

### Trust — how much you want to be asked

A row reading **Trust:** followed by a badge and a plain-English phrase. Four
choices, and the phrasing on screen is the clearest summary anyone has written:

| Setting | What it means for you |
|---|---|
| **Supervised** | *"I approve each action"* |
| **Shared Planning** | *"I review the plan"* |
| **Continuous Insight** | *"I monitor progress"* |
| **Delegated** | *"Full autonomy"* |

Expanding the control draws a spectrum from **more control** to **more
autonomy**. Pick by how much you want to be interrupted, and how reversible the
work is. Drafting a document is a different risk from sending it.

**You may not be offered all four.** Your organisation sets a ceiling, and
anything above it is not shown. If **Delegated** is missing, that is a decision
someone made for your organisation or your role — not a fault, and not something
this screen can override.

### Advanced — spending cap and restrictions

A collapsible section reading **"Advanced — spending cap & restrictions"**, which
shows **"(set)"** when you have put something in it. Two fields:

- **Spending cap for this objective (USD)** — blank means no per-objective limit.
- **Blocked actions** — specific things this piece of work must not do.

Setting a cap here binds *this* objective. It is the cheapest way to be
comfortable letting something run with less supervision: rather than approving
each step, you bound what the whole thing may cost.

## What happens when you press Enter

1. Your objective is saved, and you get a confirmation reading **"Objective
   created"** with a **View objective** link.
2. A short **initialisation** window appears, showing the trust chain being
   established, any sub-agents involved, and the constraints in force. This is
   the system writing down what it is allowed to do before it does anything.
3. You are taken into the work session, and the conversation starts.

> **[SCREENSHOT]** id: `work-home-objective-compose` · route: `/work/home` ·
> state: `northwind.objective.compose` · persona: `design_lead`
> *Must show:* the objective box with text entered, the Trust control expanded,
> and the Advanced section open with a spending cap set.

**One message worth recognising:** if your objective saves but the session fails
to open, you will see **"Objective saved — could not open a work session"** and,
importantly, *"You do not need to submit it again."* Take that at its word.
Re-submitting produces a duplicate. Use **View objective** to find it.

## It will ask you questions back

This surprises people, so: **being asked questions is the normal path, not an
error.** Shortly after you submit, the agent posts something like *"I've received
your objective… Let me analyze this and prepare some questions"*, and then a short
numbered list of things it wants to understand.

Underneath the questions is the instruction that matters:

> *"Feel free to address these in your own words — you don't need to answer each
> one separately."*

**There is no form and no Skip button.** You reply in the ordinary message box,
in prose, the way you would to a colleague who asked three things in one email.
Answer all of it, some of it, or say "use your judgement and proceed" — the work
moves on either way. If your reply cannot be processed you will be told, and
nothing is lost; you simply reply again.

Occasionally the questions are generic — *"What format should the deliverable
take?"* and similar. When that happens the system says so, prefacing them with a
note that it could not generate specific questions. That admission is honest;
treat those questions as a checklist rather than as evidence it understood you.

## Then it shows you the plan

Next comes a plan: a set of tasks, drawn as a graph, with a summary of **Tasks**,
**Estimated time**, **Estimated cost** and **Agents**. Below it, a confirmation
block headed **"Review & Approve Plan"**.

If a number is not available it will read **"Estimating…"** or **"Assigning…"**
rather than showing zero. Those placeholders sometimes stay. **An unfilled cost
estimate is not an estimate of nothing** — if the cost matters to you, set a
spending cap rather than relying on the figure.

Approving raises a final check — **"Approve Execution Plan?"** — which spells out
that the agent will delegate to specialist agents and consume resources, and
repeats the estimated cost. Two buttons: **Review Plan Again** and **Approve &
Start Execution**.

**You can push back.** Declining does not cancel anything. You are asked to
describe the changes you want, the plan is revised, and there is an **Approve
Original Plan** escape hatch if you change your mind.

## Watching it run

Inside the session you will see status wording as things progress —
**Initializing**, **Active**, **Paused**, **Completing**, **Completed**,
**Failed**, **Cancelled** — with controls to pause, resume or end the work.

Elsewhere in the interface the same work is labelled by **what it needs from
you**, which is more useful:

| Label | Meaning |
|---|---|
| **Needs Your Input** | it is waiting on you |
| **Review Plan** | a plan is ready for approval |
| **Decision Needed** | something requires you to decide |
| **Running** | in progress, nothing needed |
| **Completed** / **Failed** / **Paused** / **Cancelled** | as they read |

The first three pulse gently. Those are the ones to act on.

> **[SCREENSHOT]** id: `work-session-in-flight` · route: `/work/sessions/:id` ·
> state: `northwind.session.in_flight` · persona: `design_lead`
> *Must show:* the conversation with the clarification questions answered, the
> approved plan graph, and the session status chip.

**On connection messages:** you may see *"Reconnecting to stream…"* or a red
banner offering **Reconnect**. Read the small print, because it is accurate —
*"Your session continues on the server."* Your work is not lost when your
connection drops. Messages you type while disconnected may not arrive, so
re-send those.

## When work stops and waits

If the agent reaches the edge of what it may do, the work stops and waits for a
person. That is chapter 4, and it is the chapter most people need.

---

*Next: [05.3 — Your inbox](03-your-inbox.md)*
