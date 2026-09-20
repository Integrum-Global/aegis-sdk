# 05.5 — What you can see, and why

<!-- anchor-floor: ungrammatical (no anchor kind exists for a front-end route) -->

## Being a colleague does not make you an audience

Most systems assume that if you work somewhere, you can see what happens there,
and they restrict the exceptions. Aegis assumes closer to the opposite: your
organisation is made of units, units are boundaries, and what happens inside one
does not automatically flow to another.

This is not a security posture bolted onto a collaboration tool. It is how the
structure works. Someone sitting beside you, on the same floor, at the same
grade, may legitimately be unable to see the work you are doing — and you theirs.

The practical consequence is that **"I cannot see it" and "it does not exist" are
different sentences**. This chapter is mostly about telling which one you are in.

## The four ways a boundary shows up

You will meet these in roughly descending order of frequency.

### 1. It simply is not in your sidebar

By far the most common, and the least alarming: the section is not there. You do
not get an error because you never reach a page to be refused from. Whole areas
of the product are invisible to you.

**Check the "Show more" control in each section before concluding anything.** A
surprising amount of what people report as "I don't have access" is one click
under a collapsed list.

### 2. A page tells you the area is restricted

If you follow a link into somewhere you are not entitled to be, you get a card
headed **"Access Restricted"** which names what the area requires and what you
currently have, and suggests contacting your administrator. There is a **Go
Back** button.

This message uses internal vocabulary — it will say something like _"This area
requires admin persona. Your current persona is user."_ Do not be put off by the
wording. It is telling you the area needs a different role from yours, and it is
naming both so that a request to your administrator can be specific. Quote it
verbatim when you ask; it is precisely the information they need.

### 3. A thing you followed a link to will not load

Open a link to something specific — a session, a task, an escalation — that you
are not entitled to see, and you get a load-failure screen with a line about not
having permission, and a **Retry** button.

**The Retry button will not help.** It offers to try again, but permission is not
a transient condition. If the message mentions permission, retrying it forever
changes nothing; ask for access instead.

### 4. A list is simply shorter

The quiet one. Lists show what you are entitled to see and say nothing about the
rest. There is **no "3 items hidden" notice anywhere in the product**.

An empty inbox and an inbox emptied by your permissions are the same screen.

## The question this chapter exists to answer

> A colleague says they sent me something. I cannot see it. Is it broken?

Work through it in this order:

1. **Is the section collapsed?** Expand "Show more" in the relevant sidebar
   section.
2. **Do you have a filter or tab set?** Task Inbox in particular defaults to
   views that hide things — check All Tasks, and clear any status or priority
   filter.
3. **Did you follow a link and land somewhere unexpected with no error?**
   Mistyped or stale links do not produce a "page not found" screen; they quietly
   return you to your home page. That silent bounce means the link was bad, not
   that you lack access.
4. **Ask your colleague what they can see.** If they see it and you do not, and
   steps 1–3 are clear, you are almost certainly on the other side of a
   boundary — a different unit, a different clearance, or work that was never
   shared across.
5. **Then ask your administrator**, quoting anything the screen said verbatim.

The order matters because the first three are things you can fix in under a
minute, and the last two involve other people's time.

## One place the system does tell you

On your home screen, next to your agent information, there is a small **"N agents
visible"** indicator you can click. It opens a **Visibility Breakdown** — a short
explanation that what you see is scoped to your role and reporting line, and that
it includes your direct reports, people below them, and any cross-unit bridges
that apply to you.

It is the only place in the product that proactively tells an ordinary user their
view is narrowed rather than complete. **It covers agents only** — not tasks, not
sessions, not knowledge. But it is worth clicking once, because it makes the
principle concrete: you are seeing a scoped view, and the scope has a shape you
can ask about.

## Why it is built this way

Three reasons, and the third is the one that matters to you personally.

**It is structural, not administrative.** Knowledge boundaries follow the
organisation's real shape, so access does not have to be granted and revoked by
hand every time someone moves. There is no long list of exceptions for someone to
forget to update.

**It bounds agents, not just people.** The same boundaries constrain what an
agent can reach. An agent working for another unit cannot pull your unit's
material into its context, which is what stops a capable agent becoming a general
purpose leak. The boundary that occasionally inconveniences you is the same one
doing that job.

**It makes the record meaningful.** Because access is bounded and every crossing
is recorded, your organisation can show precisely who and what could reach a
given piece of information. That is only worth something if the boundaries are
real — a system where everyone can see everything has nothing to attest to.

That last point is the honest answer to "why is this making my life harder". Your
organisation remains accountable for what its people and agents do with
information, and that accountability cannot be delegated to a platform. What the
system provides is the evidence — a defensible account of who could see what, and
who actually did. The boundaries are what make that account true.

## What to do when a boundary is wrong

Sometimes it genuinely is. You have changed roles, or you have been brought into
a piece of work and nobody adjusted anything.

Access is granted by whoever administers Aegis for your organisation rather than
from these screens. Go to them, and give them:

- **what you were trying to reach** — the page, or the link you followed;
- **exactly what the screen said**, including any role or permission it named;
- **what you need to do**, in terms of the work rather than the system.

That last one matters most. Access here is granted in terms of roles, units and
clearances — not page by page — so "I need to see the Q3 supplier objectives our
team is running" gets you a correct answer, and "please give me admin" usually
gets you either too much or nothing.

---

_Next: [05.6 — The rest of your workspace](06-the-rest-of-your-workspace.md). If
something has stopped and you are not sure why, 05.4 is the one to re-read — most confusion about this product resolves into either a
held action nobody has decided, or a boundary nobody explained._
