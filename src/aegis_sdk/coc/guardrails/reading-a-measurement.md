# Reading a measurement — three states, two of which render as zero

**Scope:** every number you take off an analytics, compliance or audit surface
and put in front of a human.

These surfaces answer honestly and are read carelessly. The failure is never a
wrong number; it is a correct number answering a question nobody asked.

## MUST 1 — Branch on the null before you branch on the flag

Several rate fields are `float | None` beside a `measured: bool`. The two
together are **three-valued**: measured with a value, measured with nothing to
score, and not stated at all. The SLA surface — `api:GET /api/v1/analytics/sla`,
modelled by `sdk:aegis_sdk.modules.analytics.SLAMetrics` — is the one you will
meet first.

```python
# DO — the null is the discriminator; the flag is the explanation
sla = await client.analytics.sla()            # api:GET /api/v1/analytics/sla
if sla.compliance_rate is None:
    render("no data for this period")          # NOT 0%
else:
    render(f"{sla.compliance_rate:.0%}")

# DO NOT — branch on the flag, or coerce the null
rate = sla.compliance_rate or 0.0              # turns "unknown" into "total failure"
```

**Why:** `measured` **defaults to `True`**. A response that omits the field but
sends a null rate arrives as *"we measured it, and the answer is nothing"* —
which is not a state the field was designed to express, and not one a reader
branching on `measured` alone will handle. The null is present in every one of
those cases; the flag is not.

And the direction of the coercion error is the worst available one: `or 0.0`
turns "we do not know" into "everything failed", on a compliance figure, in
front of the person least able to tell the difference.

## MUST 2 — An empty result is an absence of records, never an absence of events

```python
entries = await client.compliance.list_audit_entries()
# api:GET /api/v1/compliance/audit/entries
```

That reads `api:GET /api/v1/compliance/audit/entries`. An empty list means
**nothing was recorded that this credential can see**. Three
different worlds produce it: nothing happened; something happened and was not
recorded; something was recorded and your credential cannot read it.

```
# DO      "no audit entries are visible to this credential for this period"
# DO NOT  "no policy violations occurred"
```

**Why:** the second sentence is a claim about the world, made from an instrument
that reports on a store. If you cannot say what the query would have returned had
something happened, you have not measured whether anything did.

Establish the difference before reporting: confirm your credential can read the
surface at all (see [the credential guardrail](credential-reachability.md)), and confirm the period contains at
least one event you already know about. A query that has never returned a row
has not been shown to be capable of returning one.

## MUST 3 — Never report a result obtained through a simulated transport

Part of this package fabricates responses without performing a request. A call
into one returns a populated object with a success status, having touched no
network, and nothing at the call site says so.

```bash
# DO — before trusting any client-side result, ask which paths are real
python -m aegis_sdk.coc.probe --transports-only
```

At the time of writing that scan reports **one** such method, reached through a
publicly exported A2A client whose batch invocation returns `"completed"` with a
placeholder result for every request. Re-run the scan against your own build
rather than trusting this paragraph — the count is a property of your build, not
of this sentence.

**Read its denominator, not only its finding count.** It prints `files parsed`
and `eligible` beside the result, and exits `3` UNDETERMINED rather than `0` when
either is zero — because a scan that examined nothing prints the same reassuring
zero as a scan that examined everything and found nothing. That is this file's
own MUST applied to the instrument this file tells you to run.

**Why:** a fabricated success is the most expensive possible reading, because it
is indistinguishable from the real one at every layer above it, and it fails in
the direction of reassurance. This is the same class the platform's own packaging
notes record as the reason another subpackage was withdrawn from shipping.

## MUST 4 — Say which credential and which build produced a number

```
# DO      "12 chains from `api:GET /api/v1/trust/chains`, read with a session
#          token, at 14:02 UTC"
# DO NOT  "there are 12 trust chains"
```

**Why:** every read here is tenant-scoped and credential-scoped. Two honest
readings of the same deployment, taken with different credentials, legitimately
disagree — and a number with no credential attached invites the reader to treat
a scoped view as a total.

## MUST NOT — Present a derived percentage without its denominator

**Why:** a rate over a denominator of one is arithmetically correct and
evidentially worthless, and the shape hides it: `100%` reads the same at n=1 and
n=10,000.

## What this does not cover

Whether the platform *enforces* anything it reports. These surfaces are read
paths; nothing here observes an execution being stopped. A clean compliance
dashboard is evidence about records, and evidence about records is not evidence
about conduct — which is exactly why the accountability for the conduct stays
with the organisation deploying the agent, and why what this platform offers is
the proof rather than the liability.
