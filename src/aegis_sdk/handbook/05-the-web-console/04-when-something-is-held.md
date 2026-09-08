# 05.4 — When something is held

## Held means the system worked

An agent reached the edge of what it was allowed to do, stopped, and asked for a
person. Nothing has failed. Nothing is broken. The bounds were set deliberately,
and this is what reaching them looks like.

This is worth saying plainly because the experience does not feel like success.
Work you asked for has stopped, and a queue is asking you to decide something.
The instinct is to treat it as an obstruction. It is the opposite: an agent that
_could not_ be stopped at this point would be the thing to worry about.

The stopping itself is real and reliable — it is one of the controls this
platform genuinely enforces rather than merely records.

> **UNVERIFIED here, and deliberately so.** This page states the behaviour it
> observed. It does not claim a verdict on how strongly the control is enforced,
> because that is not a question this edition can settle from the outside — and a
> page that guessed at it would be read as an assurance. Treat the observed
> behaviour as what you can rely on, and raise anything you need a firmer answer
> on with your platform contact.

## Where held work lives

⛔ **First, the part that will otherwise waste your morning: if you are an
ordinary user, this screen has no link in your sidebar.**

You are almost certainly _allowed_ to open it: the page itself admits both the
`admin` and the `user` persona, so typing or pasting its URL works. What you do
not get is a way to _find_ it. The navigation entry that points at it sits
inside the **GOVERN** section, which is declared administrator-only, and the
entry carries no override of its own — so the link renders for administrators
and for nobody else, and no other page links to it.

**You can confirm this yourself in ten seconds, which is the point:** open the
page by URL and it loads; then look for it in your sidebar and it is not there.
Those two observations together _are_ the finding. If the page refuses to load
for you, that is a different situation from the one described here and worth
reporting — it means the persona admission has changed since this was written.

**What to do about it, today:** go to `/govern/approvals` directly in the address
bar — it will load. If it does not, you hold neither persona and you need an
administrator, not a different URL.

This is a defect rather than a policy. The queue exists precisely because an
approver is never the person who made the request, and so arrives with no link to
follow — a standing entry in the navigation is the intended remedy, and it is
currently not reachable for the people it was added for. It is reported. Until it
is fixed, treat the URL as the route in.

**Action Approvals**, subtitled _"Held actions and plans awaiting a human
decision"_. The queue is headed **Held Queue** and refreshes itself every five
seconds — there is a badge saying so, and it is accurate. You do not need to
reload.

Empty, it reads **"No actions are currently held"**, and explains that agents
under supervision are either running freely or waiting on a decision that is not
in this queue.

> **[SCREENSHOT]** id: `approvals-held-queue-countdown` ·
> route: `/govern/approvals` · state: `northwind.approvals.pending` ·
> persona: `operations_director`
> _Must show:_ the Held Queue with one card — posture badge, request type,
> agent's reasoning, proposed action, and the countdown timer mid-way.

![Action Approvals: a Held Queue panel reading "0 actions awaiting a decision" and, below it, "No actions are currently held".](../assets/screenshots/govern-approvals-operations.png)

_The approvals queue with nothing in it — the state this chapter warns you not to
over-read. The page's own explanation is the important part: every agent in a
supervised or shared-planning posture "is either executing freely or waiting on a
decision that isn't here yet." **An empty queue is not proof that nothing was
held.** Note the "All postures" filter top-right: if you are looking for
something and not finding it, check that first._

## Reading a held item

Each card shows:

- **Which agent** stopped, and **the objective** it was working on.
- **Its posture** — **Supervised** or **Shared Planning**. This is the reason it
  stopped: an agent under supervision must ask.
- **What kind of decision** — a **Single Action** or a whole **Execution Plan**.
- **Agent's reasoning** — the agent's own account of why it wants to do this.
- **Proposed action** — the specific thing it wants to do.
- **Time left** — a live countdown.

### What the card does not tell you

Three honest limits, so you are not looking for things that are not there:

**The reason is the agent's, not a policy's.** "Agent's reasoning" is the agent
explaining itself. There is no named rule, policy or clearance citation on the
card and no link to one. The posture badge is the whole answer to "why did this
stop" — it stopped because it is supervised. If the reasoning field is empty you
will see **"No reasoning was provided."**, which is the system being honest rather
than the system malfunctioning.

**It does not say who should decide.** No name, no assignee, no "waiting on".
Anyone with access to the queue can act on any item in it. In practice this means
**a held item is nobody's job unless someone makes it theirs** — if your team
relies on this queue, decide between you who watches it.

**"Requested by" shows an account identifier, not a person's name.** You may have
to ask who that is.

## The countdown, and what running out means

Each card shows **Time left**, counting down, amber under a minute and red under
thirty seconds. Expired, it reads **"Window closed"** with a blunt line: _"This
request should have timed out already — decide now or the agent will fail with a
timeout error."_

Take that literally. **A held action that is not decided does not wait forever
and does not proceed — it fails.** The work does not quietly continue without
approval, which is correct, but it also does not sit there indefinitely. Nobody
deciding is itself a decision, and it is the worst one available: the work fails
having consumed whatever it already spent.

If the timer cannot be worked out you will see **"Deadline unknown"**. Treat that
as urgent rather than as no deadline.

## Deciding

Two buttons: **Approve** and **Reject**. Afterwards you get a short
confirmation — _"Action approved / The agent has been notified and will
proceed."_ or _"Action rejected / The agent has been notified and will not
proceed."_

If it was **your** request, you also get **Withdraw request**, which cancels it.
That is the right move when you have changed your mind or realised the agent
misunderstood — better than rejecting, because it does not read as a judgement on
the agent's proposal.

> ### You may see Approve on your own request. It will not work.
>
> The buttons appear on every card, including ones you raised yourself. **You
> cannot approve your own request** — the refusal happens on the server, so you
> find out by pressing it and getting a red message reading **"Could not approve
> this action"**.
>
> This is a rough edge in the interface, not a rule you can talk your way around.
> The separation between requesting and approving is deliberate and is one of
> the things that makes the audit trail worth anything. Use **Withdraw request**
> if you want your own request gone, and find a colleague if it genuinely needs
> approving.

## Your work seems stuck. What to check.

**Start with the approvals queue — and know what its silence means.**

If your item is there, it is genuinely waiting for a person. Approve or reject it
and the _same_ action resumes from where it stopped; nothing is re-run and
nothing is lost. There is a **five-minute** window by default — past it the
request times out and the work does not proceed. If you are waiting on somebody
else, tell them. Do not assume they were notified.

⛔ **An empty queue does not mean nothing was held.** This is the one thing to
take away. Work can stop _because_ a human decision was required and there was
nobody to ask — and when that happens it never enters the queue at all.

**Be aware of what nobody can tell you.** If your work stopped that way, the
reason is **not recorded anywhere** — not in the queue, not on the session, and
not in any log an administrator can look up. Asking someone to "check the reason"
will not help, because there is nothing to check.

**And be aware of what the session view cannot tell you.** Today, a session that
is waiting, one that stopped because nobody could be asked, and one that is
genuinely stuck all look the same on that page: still active, no error, no
explanation. Do not read "it still looks like it's running" as evidence that it
is.

| Approvals queue                   | What it means                                                                                                                                          | What to do                                                                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Your item is there                | **Held and waiting** — someone must decide                                                                                                             | Approve or reject, within five minutes                                                                                     |
| Empty, session still shows active | **Either** it stopped because nobody could be asked, **or** it is genuinely stuck. Nothing available to you or to an administrator distinguishes these | Re-submit under a posture with a human in the loop. If it completes, it was held; if it stalls again, report it as a fault |
| Empty, session completed          | Nothing was held                                                                                                                                       | —                                                                                                                          |

**The one-sentence version:** _the approvals queue shows only the work that
stopped to wait for you; work that stopped because there was nobody to wait for
never reaches it and leaves no record — so an empty queue is not an all-clear._

⚠ **Why the re-submit is the right move rather than a workaround.** It is not
guesswork — it is the only action available to you that _discriminates_. A
posture with a human in the loop routes the same stop into the queue, where you
can see it. That turns an unanswerable question into an answerable one.

### Why your session cannot tell you, when the answer exists

The information is not missing everywhere — it is missing _from the page you are
looking at_. Whether an action of yours is held is recorded and is retrievable
through the approvals interface; it simply is not surfaced back onto your own
session view. So an administrator, or you on the approvals page, can answer "is
anything of mine held?" — while the session itself stays silent.

That is worth knowing because it changes who you ask and what you ask for. The
question "is my work waiting on someone?" has an answer. The question "why did it
stop, if it isn't waiting?" does not.

## What this is for

Every one of these decisions is recorded — who asked, what was proposed, who
decided, and when — in a tamper-evident trail. That record is the point.

Your organisation is accountable for what its agents do. That accountability
cannot be handed to a supplier, a platform or an agent, and "the AI did it" has
never been a defence. What Aegis provides is the **proof**: bounded mandates,
actions that stop at the boundary, and an evidence trail showing that a named
human decided the things that needed a human. You keep the accountability; the
system gives you what you need to show how you discharged it.

That is why a held action is worth the interruption. Approving something here is
not administrative friction — it is the moment the record captures a human
making a decision, which is exactly what an auditor, a regulator or an insurer
will later ask you to demonstrate.

---

_Next: [05.5 — What you can see, and why](05-what-you-can-see.md)_
