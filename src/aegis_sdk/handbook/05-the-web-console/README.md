# Part 05 — The web console

**Audience: anyone with a login — including you.**

This part is written entirely from the running application: no code, no
configuration, no assumed knowledge of how any of it is built. What it contains
instead is a plain account of what you are looking at, screen by screen.

**Two reasons an architect or operator should read it anyway.** First, this is
where *you* answer a held decision — approvals are attributable to a named human,
and the console is where you are authenticated as yourself rather than as a
provisioning key. Second, this is what everyone else in the organisation will
ever see of the system you designed; chapter 05.5 in particular, on why things
are invisible, is the screen-side face of the clearance model you set up in 02.3,
and it is worth knowing what that model looks like from the outside.

The harness equivalent of everything here is [part 02](../02-working-through-the-harness/).
Where this part says "click", part 02 says which call it makes.

## The chapters

| # | Chapter | What it answers |
|---|---------|-----------------|
| 1 | [First login](01-first-login.md) | What you see the first time, and what to do with it |
| 2 | [Submitting an objective](02-submitting-an-objective.md) | How to ask for work, and why it asks you questions back |
| 3 | [Your inbox](03-your-inbox.md) | The things waiting for you, and which ones are urgent |
| 4 | [When something is held](04-when-something-is-held.md) | Why work stops, what "held" means, and where to look — including why the approvals queue can be empty even though something was held |
| 5 | [What you can see, and why](05-what-you-can-see.md) | Why some things are invisible to you, and why that is deliberate |
| 6 | [The rest of your workspace](06-the-rest-of-your-workspace.md) | The five remaining entries in your navigation, and whether you can change anything in them |

## Three things worth knowing before you start

**1. Aegis will stop and ask you things. That is the product working, not
failing.** Agents here operate inside bounds someone set deliberately. When an
agent reaches the edge of its bounds — it wants to spend more than its budget, or
touch data outside its remit, or take an action classed as needing a human — it
stops and waits for a person. You may be that person. Chapter 4 is about this
and is the chapter most people need first.

**2. You will not be able to see everything, and that is by design.** Aegis
treats organisational units as knowledge boundaries. Being a colleague of
someone does not grant you sight of their work. When you hit a boundary, the
system tells you that you hit one rather than pretending the thing does not
exist. Chapter 5 explains how to tell the two apart, and what to do about it.

**3. Nothing you do here is invisible.** Every action — yours and every agent's
— is recorded in a tamper-evident audit trail. This is not surveillance of you;
it is the evidence that lets your organisation stand behind what its agents did.
It also means that if something goes wrong, there is a record of what actually
happened rather than a reconstruction.

## About the screenshots

**Six of the screens in this part have a picture, and every picture was taken
from a fictional company.** That company is Northwind Manufacturing — its
people, agents, objectives and figures invented, its email addresses on a
reserved domain that cannot reach a real mailbox. Nothing in any image is any
organisation's real data, and none of it came from a live deployment. That is a
hard rule rather than a preference: blurring a real name does not remove it, and
the only safe method is to photograph data that was never real.

**Where a picture is still missing, the page says so in place.** Six screens in
this part carry a marked placeholder instead of an image, naming the exact
screen, the state it has to be in, and who has to be logged in to see it. Read
those as instructions rather than apologies — each tells you which screen the
paragraphs beside it are describing, so the text stands on its own. A mocked-up
picture of a governance product would be worse than a missing one, because you
could not tell it apart from the real screen.

**Some screens are photographed empty, and that is the honest picture.** The
demo company has an organisation, roles, agents and work; it does not have every
kind of record. Where a list is empty in an image, the caption says why. Chapter
4 makes the argument that matters here: an empty queue is not evidence that
nothing was held.

Where an image does not quite match what you see, the difference will be your
own organisation's configuration — its unit names, its clearances, what your
role is allowed to do — not a different version of the software. The shape will
be the same.
