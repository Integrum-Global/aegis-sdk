# Part 01 — Orientation

<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->

Three chapters, read in order. They are the only part of this book that is meant
to be read straight through, and skipping them is the most expensive shortcut
available: chapter 01.2 in particular describes a model people routinely guess
wrong, and every design built on the wrong guess has to be rebuilt.

| #    | Chapter                                                        | What you get                                                                     |
| ---- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 01.1 | [What you were given](01-what-you-were-given.md)               | The shape of the thing in your hands, and what each piece is for                   |
| 01.2 | [The mental model](02-the-mental-model.md)                     | Where governance actually happens. The load-bearing chapter of the whole book      |
| 01.3 | [Your first working session](03-your-first-session.md)         | Install, point at a deployment, authenticate, and make a real call — end to end    |

## Why 01.2 is the one to read even in a hurry

The single most expensive misunderstanding on this platform is about *where*
governance happens. People assume Aegis sits between an agent and the outside
world, receiving the agent's requests and forwarding the approved ones. It does
not. Nothing here does that, and building against the wrong model produces
designs that cannot work — usually discovered late, when someone asks where the
forwarding code is and the answer is that there isn't any.

That chapter is short and it decides how you design everything afterwards.

## What this part deliberately does not do

It does not teach the four standards. Aegis implements CARE, PACT, EATP and CO;
you can operate a deployment competently without reading any of them, and this
book uses the Foundation's vocabulary where it uses it rather than inventing a
parallel one. Where a term is load-bearing — *envelope*, *posture*, *clearance*,
*verification gradient* — the chapter that first needs it defines it in place.

---

_Next: [01.1 — What you were given](01-what-you-were-given.md)_
