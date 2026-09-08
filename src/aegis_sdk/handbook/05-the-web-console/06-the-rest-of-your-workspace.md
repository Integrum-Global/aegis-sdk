# 05.6 — The rest of your workspace

Chapters 1 to 5 cover the things you will do most days: sign in, ask for work,
work your inbox, deal with something that stopped, and understand why parts of
the system are invisible to you.

Your navigation has five more entries. None of them is hidden from you, and none
of them is covered above, so this chapter walks each one briefly — what it is
for, what you will see, and whether you can change anything there.

**Read this as a tour, not a manual.** Most people use one or two of these
regularly and never open the rest. Skim it once so nothing in your sidebar is a
mystery, then come back when you need one.

## My Sessions

**A session is one continuous piece of work an agent did for you.** When you
submit an objective and an agent starts working, that run is a session. This
page lists yours.

You can filter the list four ways, and the counts beside each filter tell you how
many fall into it:

- **All** — everything, however old.
- **Active** — running right now. This also counts sessions that are still
  starting up, so a brand-new session appears here immediately rather than
  seeming to vanish for a few seconds.
- **Paused** — stopped part-way and able to resume. A session waiting on your
  approval is the usual reason (chapter 4).
- **Completed** — finished, whether it succeeded or not.

If the list is empty you get **"No sessions found"**. As chapter 5 explains, an
empty list means *nothing you are entitled to see*, which is not always the same
as *nothing happened*.

You can delete a session from here. It asks you to confirm first. Deleting
removes the session from your list — it does **not** erase the audit record of
what the agent did, which is kept independently and is not yours to remove. That
distinction is the point of the audit trail, not a limitation of this screen.

> **[SCREENSHOT]** id: `work-sessions-mixed` · route: `/work/sessions` · state:
> `northwind.sessions.mixed_status` · persona: `field_service_lead`
> *Must show:* the four filters with non-zero counts, including at least one
> paused session, so the filter row is legible as a summary.

## My Applications

**An application here is a piece of software your organisation runs that agents
can act on your behalf within.** If your organisation has not set any up, or has
not assigned you to one, this page will be empty and you can ignore it.

If you have been assigned some, this page is where you see them and, where you
are permitted, request changes to them. It carries a second section, **My Pending
Change Requests**, listing changes you have asked for that have not yet been
decided. A request sitting here is waiting on a person, not lost.

## EATP Tasks

**EATP is the Enterprise Agent Trust Protocol** — one of the open standards Aegis
implements, published by the Terrene Foundation. You do not need to know anything
about the standard to use this page. What matters to you is that it gives tasks a
consistent shape across every system that speaks it, so a task means the same
thing here as it does in another tool your organisation runs.

The page opens with four counts, which is usually all you need:

- **Total Pending** — everything outstanding, across everyone.
- **My Tasks** — the subset assigned to you. This is the number to act on.
- **Overdue** — shown in red. Past its due date.
- **Completed** — shown in green.

Below the counts is the task list itself. If your organisation does not use the
EATP task surface, expect these to sit at zero permanently; that is a
configuration choice, not a fault.

> **[SCREENSHOT]** id: `work-eatp-tasks-with-overdue` · route: `/work/eatp/tasks`
> · state: `northwind.eatp.tasks_one_overdue` · persona: `field_service_lead`
> *Must show:* the four count tiles with a non-zero red Overdue tile, so the
> colour coding is legible.

## EATP Processes

A process is a longer-running piece of work made of several tasks. This page
shows the ones you own or take part in, with a search box, a list of the active
ones, and a button to start a new one where you are permitted to.

**One thing here will look different for you than it does in this handbook.**
The labels on this page come from your organisation's own vocabulary rather than
being fixed in the software. If your organisation calls these things
*workflows*, or *cases*, or *engagements*, that is the word you will see — on the
heading, on the search box, on the button, and in the empty state. The page works
identically whatever it is called. So if your sidebar does not say "Processes",
you are still in the right place.

## Teams

**Read-only, for most people.** This page shows the teams in your organisation:
who is grouped with whom. Ordinary members can read it — you can see your
organisation's team structure without being an administrator.

What you will not have is the ability to change it. The controls that create,
rename or re-staff a team are reserved for administrators, so you may see buttons
that are unavailable to you. That is the expected state, not a permissions
problem to report.

Teams appears twice in the navigation config — once under **WORK** and once
under **GOVERN** — and both point at the same page. Which of them *you* see
depends on your persona: the WORK entry is the one ordinary users get, the GOVERN
one is administrators'. If a colleague describes reaching Teams by a route you do
not have, that is why, and you have not found two different screens.

⚠ **A general note for this whole part, learned the hard way in chapter 4.**
Being *allowed* to open a page and being *shown a link to it* are separate
things, decided in different files. Where this handbook says "you will find X in
the sidebar", it has been checked against the navigation entry for an ordinary
user — not merely against whether the page would let you in. If you are following
an instruction from anywhere else and the menu item is not there, check that
distinction before concluding you lack permission.

## If something in your sidebar is not in this handbook

Your navigation is filtered by what you are allowed to use, so two people in the
same organisation see different sidebars. If you have an entry this handbook does
not describe, the likeliest explanation is that you hold a role with
administrative reach — in which case the screen you are looking at changes how
the system behaves rather than how you work inside it, and the corresponding
harness path is in [part 02](../02-working-through-the-harness/) rather than
here.
