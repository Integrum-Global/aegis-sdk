# Domain surfaces — the architect tier composes at runtime, against a semi-trusted principal

**Scope:** every domain surface you register, and every assumption you make about
who can see it.

A **surface registration** is one row that is simultaneously one navigation entry
and one reachable route. Registering it is composition **at runtime, with no
deploy** — and that is the whole point of the architect tier.

## The three tiers, and which one you are in

| Tier | Who | What they change |
| --- | --- | --- |
| Primitives and engines | a developer, through the Kailash SDK | nodes, data models, HTTP, agents, governance primitives |
| The platform | a developer, in platform code | the governed object model and its enforcement |
| **Architect** | **you, at runtime, no deploy** | **org composition and domain surfaces** |

Domain needs belong in the architect layer rather than the developer layer. If
you find yourself asking for a code change to add a domain view, you are in the
wrong tier — that is what surface registration exists to make unnecessary.

## The one sentence that changes how you must read everything below

**The architect tier is self-service for client architects.** Every "an
architect cannot mint X" guarantee is load-bearing against a **semi-untrusted
principal** — it is not an internal consistency property.

You are that principal. So is every architect at every other tenant on the
deployment you are working against. Nothing below is a style rule; each is a
security boundary, and the constraints exist because *your* input is the
untrusted input.

## MUST — the five invariants

These are the platform's own words, and they are reproduced rather than
summarised because a paraphrase of a security boundary is a weaker boundary.

1. **Tenant isolation is a read-layer invariant, not a route convention** — an
   entry authored by tenant A is unreachable and invisible to tenant B, tested in
   both directions.
2. ⛔ **Architect-supplied input MUST NOT reach any module-level mutable.**
3. **Fail closed** — an unresolvable, malformed or unauthorized entry renders
   nothing and denies.
4. **Route paths and nav labels are user-controlled strings reaching the DOM and
   the router.**
5. **Framework-first**: DataFlow for persistence, Nexus for HTTP, PACT for
   authorization.

Invariant 4 is the one architects misread most often. It is not a warning that
you might make a typo. It says the values you supply arrive at a renderer and a
router as **attacker-controlled strings**, because from the platform's side that
is exactly what they are.

## What you SELECT, and what you may never MINT

Every architect-supplied value comes from a **closed vocabulary**. You choose
from a list; you do not invent a member of it.

| field | you choose from |
| --- | --- |
| navigation section | the four fixed sections: BUILD, WORK, GOVERN, OBSERVE |
| personas | the five known personas: architect, user, admin, executive, operator |
| view kind | the enumerated kinds; today, a record list |
| icon | the bundled icon allowlist |
| required permission | the existing permission catalogue |

**There is no route-path field, deliberately.** You supply a surface *key*; the
path is **derived** from it. The key is constrained to lowercase letters, digits
and underscores, must begin with a letter, and is between three and sixty-four
characters.

Read that as a design property rather than as validation: path traversal, a
`javascript:` scheme, a protocol-relative `//host` and a key that shadows an
existing route are not *filtered out* — they are **unrepresentable**. A filter can
be bypassed by an input its author did not imagine. A value that cannot be
expressed in the field's grammar has nothing to bypass.

One parametric route serves every registered surface. Registering a surface does
not add a route to the application; it adds a row the existing route resolves.

## MUST — do not treat registration as activation

A registration's status defaults to **disabled**. That is fail-closed
(invariant 3), and it is not an inconvenience to work around: a surface that
appears the moment it is written is a surface that appears before anyone has
checked who can see it.

Authoring is gated on holding an architect, admin or executive persona **and** the
relevant surface permission. A `developer` persona deliberately does **not** hold
surface permissions. If you are surprised by that, re-read the tier table — it is
the tier split, working.

## ⛔ Two things that are NOT true, however they read

**1. Setting a classification does not restrict who sees the surface.**

The classification field is **declarative and gates nothing today**. Surface
visibility resolves on tenant, status, vocabulary, persona and permission — and
never compares the value against the caller's clearance. The platform pins this
as a named absence in its own security tests rather than leaving it to be
discovered.

So: do **not** put a sensitive surface behind a classification value and treat it
as protected. Use the persona and permission gates, which are the ones that
actually resolve. Read the field as documentation of intent, not as a control.

**2. The governed-object layer beneath a surface is not reachable yet.**

Two sibling models — the domain object *type* (the shape) and the governed object
*record* (its rows) — ship as **schema only**. No handler, no service, no route,
no frontend. Their own definitions carry explicit named-absence notices.

The consequence for you is concrete: **you can register a surface today; you
cannot yet populate it with governed domain records through a supported API.**
Plan for a surface as a composition primitive that is arriving in stages, and do
not design a client delivery on the assumption that the record layer is there.

## ⛔ This client cannot register a surface

Measured against this package: it exposes **no surfaces module**, and it declares
no surface-registration operation. Confirm it yourself rather than taking this
sentence's word for it —

```bash
python -c "import aegis_sdk, pkgutil; print([m.name for m in pkgutil.iter_modules(aegis_sdk.modules.__path__) if 'surf' in m.name])"
python -c "from aegis_sdk.handbook.check import declared_operations as d; print([o for o in d() if 'surface' in str(o).lower()])"
```

Both print an empty list. **Now pair them with a control**, because an empty
result from a command that cannot speak is not evidence of absence — re-run each
with a term this client demonstrably does have:

```bash
python -c "import aegis_sdk, pkgutil; print([m.name for m in pkgutil.iter_modules(aegis_sdk.modules.__path__) if 'tool_agent' in m.name])"
python -c "from aegis_sdk.handbook.check import declared_operations as d; print(len([o for o in d() if 'tool-agent' in str(o).lower()]))"
```

Those return `['tool_agents']` and a non-zero count. Only with that pair in hand
is the first pair's emptiness a measurement.

Note `declared_operations()` yields `(method, path)` **tuples**, not strings —
hence `str(o)`. A version of this check written against strings raises
`AttributeError` rather than printing a misleading empty list, which is the
better failure of the two, but is still not the check you wanted to run.

So a surface is composed through the console and the platform's own API, not
through this client, and any workflow you build on this SDK must treat surface
registration as an out-of-band step. If a later release of this package adds the
module, the commands above are how you will know.

## The honest status of this capability

The programme that owns surface registration is **open and self-reports as not
converged**: multiple adversarial review rounds, none clean, with open critical
findings outstanding — even though the registration model itself has shipped and
is live.

That is a fact about *this documentation*, and you are better served knowing it
than discovering it. Compose surfaces; do not build a client commitment on the
parts marked absent above until the absences are closed.

## What none of this establishes

That a surface you can see is a surface you should be able to see. Visibility
resolves on tenant, status, vocabulary, persona and permission — and a
misconfiguration in any of those renders a surface without any error. Reading a
surface list tells you what resolved, never what was *intended* to resolve.
