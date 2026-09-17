# 06.4 — Trust and the audit spine

[02.4](../02-working-through-the-harness/04-trust-chains-and-postures.md) showed
you how to establish a chain, move a posture and revoke one.
This chapter is about the shape underneath those calls: what trust *is* as an
object here, how a decision to permit or refuse is actually reached, how standing
can be withdrawn, and what survives an action so that somebody who was not there
can reconstruct it later.

The single most useful thing to carry into your design is this: **trust here is
not a boolean the platform computes about an agent. It is a set of first-class
objects you can read, compose and argue with** — a lineage that names where
authority came from, a standing that moves and can be explained, and a decision
that can be re-derived after the fact. Everything below follows from taking that
seriously.

## Four objects that people collapse into one

| object | answers | mutable? | read it at |
| --- | --- | --- | --- |
| **Authority** | who attested this agent? | created, deactivated | `sdk:aegis_sdk.trust.AuthoritiesModule` |
| **Chain** | where did its authority come from? | established, revoked | `sdk:aegis_sdk.trust.ChainsModule` |
| **Posture** | how much may it do unaided, now? | moves both ways | `sdk:aegis_sdk.trust.PosturesModule` |
| **Decision** | was *this* action permitted? | — it is a record | `api:POST /api/v1/trust/verify` |

They are separable in practice, not just in principle. An agent can hold a valid
chain and a restrictive posture — that is the normal state of anything newly
provisioned. An authority can be retired while chains established under it
continue to exist. A chain can be live and a particular action still refused,
because the decision consults the envelope and the posture as well.

## The authority — the signing root

A chain is not self-originating. An **organisational authority** is the signing
root a chain is established under: agents are attested *by* an authority, and
that relationship is recorded in the chain's genesis. Enumerate them at
`api:GET /api/v1/trust/authorities`, create one with
`api:POST /api/v1/trust/authorities`, and read the agents established under one
at `api:GET /api/v1/trust/authorities/{id}/agents`.

Deactivating an authority (`api:POST /api/v1/trust/authorities/{id}/deactivate`)
is not a rename — it is a **security transition that every chain established
under it inherits**, which is why the platform requires a reason and records it
on the deactivation entry. Treat it like a revocation, not like housekeeping.

Two honest limits on the read surface. The established-agent count on the display
routes is computed by scanning trust chains, and it is **absent rather than
zero** when the platform could not compute it — an unknown count and a genuine
zero are different facts, and the model deliberately does not collapse them. And
`list_agents` itself walks a bounded page of chains, so on a large tenant it can
return a partial answer **with nothing in the response marking it as partial**.

## The chain — lineage, and its one nesting trap

Establishing is `api:POST /api/v1/trust/establish`, returning
`sdk:aegis_sdk.EstablishedTrustChain`. The body names the agent, the authority,
a list of **capability labels** and a list of **constraint labels** — both are
`list[str]`, not dictionaries; the actual bounds live in envelopes, which is
[02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md).
Expiry defaults to 365 days, and chains genuinely expire.

Two properties of this call are worth restating because they constrain what you
can build rather than merely how you call it. **Human origin is derived
server-side from the authenticated caller** and cannot be supplied — the
parameter is accepted and ignored. *Design intent, not observable:* an identity a
client can assert is an identity a client can forge, so the one fact the lineage
must not be able to lie about is taken from the session. The practical
consequence is that **the human on the record is whoever's credentials ran the
script**, which is why provisioning under a shared machine key produces a tenant
whose entire authority structure descends from a service account.

> ⛔ **Identity is NESTED one level down, and this is the trap.** On the full
> lineage document returned by `api:GET /api/v1/trust/chains/{id}`, `id`,
> `agent_id` and `authority_id` live on `genesis`, **not** at the top level.
> A reader that looks for those three names a level too high finds none of them
> — and on a permissive parser, reads three nulls beside fully-populated
> capability rows, which looks like a response problem rather than a lookup one.
> `sdk:aegis_sdk.TrustChain` is the flat summary shape and
> `sdk:aegis_sdk.EstablishedTrustChain` is the establishment shape; the lineage
> document is a third, richer shape again. For the narrow projection, when the
> lineage is more than you need, use `api:GET /api/v1/trust/chains/{id}/summary`.

The delegation path is `api:GET /api/v1/trust/chains/{id}/delegation-path`,
returning `sdk:aegis_sdk.DelegationPath` — the ordered walk from the human root
down to this agent, its depth, and the ceiling in force. Note the two addressings
in play: **chains are keyed by agent**, so what looks like a chain id in these
routes is an agent id, and an agent with no chain returns an *empty path rather
than an error*. `None` there means "no chain", never "failed to load".

One more read worth knowing about before you depend on it: the summary projection
is **clearance-gated under selective disclosure**. Some fields — the two parties
and the bridge origin — may be *absent* rather than null when your clearance does
not reach them, while `id`, `status` and `created_at` are always visible. That
means a null on a gated field is ambiguous between "not disclosed to you" and
"genuinely absent", and the response cannot tell you which. Do not build a
security decision on reading absence.

## Standing — posture as a moving object

A posture is not a property of the chain; it is the current answer to *how much
may this agent do without a human in the loop*, and it moves. Read it at
`api:GET /api/v1/agents/{id}/trust-posture`. The five levels are CARE-aligned and
lowercase — `sdk:aegis_sdk.TrustPosture` — and
[02.4](../02-working-through-the-harness/04-trust-chains-and-postures.md) has the
table.

The read returns more structure than people expect, and two fields in it are
load-bearing:

- **`posture` is the EFFECTIVE posture.** If an override is active, this is the
  override's value, not the agent's own.
- **`base_posture` is what the agent reverts to** when the override lapses.

So "what posture is this agent at" has two correct answers depending on whether
you mean *now* or *by default*, and an emergency restriction implemented as an
override is precisely the case where they differ. `sdk:aegis_sdk.PostureOverride`
models the override row itself, including who initiated it, why, and when it
expires.

### Changing it: one endpoint, two outcomes

Both the governed progression request and the administrative override go through
the *same* call — `api:PUT /api/v1/agents/{id}/trust-posture` — which decides
internally whether the change applies immediately or is held for a human. There
is no separate override endpoint, and the two are gated on the same permission.

The return shape exists because the two outcomes demand **opposite next actions**,
and inferring them is what goes wrong:

```text
   PUT trust-posture
         │
         ▼
   ┌───────────────┐  downward, or     ┌──────────────────┐
   │   Requested   │  at/below         │     Applied      │── posture is ──▶ [*]
   └───────┬───────┘  supervised       └──────────────────┘   the NEW value
           │                                   ▲
           │  upward, above supervised         │
           ▼                                   │
   ┌───────────────┐                           │
   │    Pending    │── POST .../approve ───────┘
   └──┬─────────┬──┘
      │         │
      │         └── POST .../reject ──▶ ┌───────────────┐
      │                                 │   Rejected    │── posture never ──▶ [*]
      │                                 └───────────────┘   changed
      │
      └── approval window lapses ─────▶ ┌───────────────┐
                                        │    Expired    │── posture never ──▶ [*]
                                        └───────────────┘   changed

   While a change is Pending the agent is STILL RUNNING at the old posture, and
   result.posture reports the OLD value. Do not re-issue the same transition to
   "make it take" — it records nothing new and comes back flagged.
```

Branch on `approval_pending`. When it is `True`, `result.posture` is the posture
the agent is **still running at** — reporting it as the new one is the single
most common integration defect in this area, and it is a reporting defect that
compounds: a caller that retries after a timeout files a *second* pending
request, because the endpoint has no idempotency key. Re-issuing the same
transition while one is pending records nothing new and comes back flagged —
check `api:GET /api/v1/agents/{id}/trust-posture/pending` before every request,
and treat a non-null answer as *already asked* rather than as an obstacle.

A pending change is decided at `api:POST /api/v1/agents/{id}/trust-posture/approve`
or the matching `.../reject`. Both accept an explicit approval id, and past one
pending request the server
**refuses rather than picking one** — which is the right behaviour, and means
your code should never let a second request accumulate in the first place.

### Where the evidence lives

There is a whole read surface for *why* an agent's standing is what it is, and it
is worth more to an auditor than the posture value itself. The eligibility
verdict is `api:GET /api/v1/agents/{id}/trust-posture/evaluate`, and it is the
**only** call that answers "may this agent progress" — no posture read and no
change response carries an eligibility verdict. The behavioural rates it is
computed from are at `.../trust-posture/metrics`; the basis is at
`.../trust-posture/evidence`; and the trail of how the agent got here is at
`.../trust-posture/history`. `sdk:aegis_sdk.TrustPostureModule` holds the
per-agent reads.

**Look at the history endpoint before you decide whether your governance is
real.** If every entry in it is an override, the graduated progression was
decorative: the agent was placed at its autonomy level rather than having earned
it, and an agent that has never been observed under supervision has no evidence
behind its autonomy — which is exactly the thing you would need to show.

## The decision path — how a permit is reached

`api:POST /api/v1/trust/verify` is the operation the enforcement path calls on an
agent's behalf. It takes an agent, an **action** (a string like `write` or
`execute`), and a target addressed as a **kind plus an optional instance**:
`resource_type` says what sort of thing is being acted on, `resource_id` says
which one. The kind is required, and the client will refuse rather than invent
one — *design intent, not observable:* the platform writes that value into its
audit trail, so a fabricated placeholder would read as one the caller had named.

The result is a decision plus the platform's reasoning:
`sdk:aegis_sdk.TrustVerificationResult` carries `allowed` and `reason`, and the
richer shape carries `capabilities_matched` and — the one to read when a request
was refused — `constraints_violated`. Two traps in the shape: `chain_id` and
`constraints_applied` are inherited from a base model and are **always empty on
this route**, so reading `constraints_applied` for the reason a denial happened
tells you nothing. Read `constraints_violated`. And caller-supplied `context` is
accepted and ignored: the evaluation runs against the chain's own recorded
constraints, never against anything the request asserts about itself.

### Asking why, without doing the thing

`api:POST /api/v1/governance/explain-access` — on
`sdk:aegis_sdk.modules.GovernanceExplainModule` — returns the same decision as a
trace rather than a verdict: whether it was allowed, the reason, **the step the
evaluation reached**, and the access path taken. That step name is the useful
field on a refusal, because it tells you *where* the chain stopped.

Read its two subject modes carefully, because they are not the same kind of
answer. A **knowledge item** subject is a dry run: nothing is accessed, nothing
is recorded, and the verdict is only as good as the item description you passed
— it is not evidence that a real access would be permitted. A **tool** subject is
the opposite: it reads the refusals that were actually persisted for that tool's
work unit, so the step and reason are that gate's own words rather than a
recomputation. And a tool subject with no refusal on record reports the *absence
of a record*, which is not the same as a determination that the tool is
permitted. That distinction is stated in the response itself; believe it.

### One question worth asking on a schedule

`api:GET /api/v1/governance/envelope-coverage` answers not *"do envelopes
exist"* but *"would they stop anything"*. It is the closest thing here to a
readiness check on the governance layer, and it is honest in a way that makes it
usable: an envelope that resolves to allow-all is counted in its own bucket
rather than as coverage, and the report carries a **completeness flag** —
when the measurement did not fully happen, the counts are a floor and the report
says which part was missed. Check completeness first, or you will quote a
partial number as a total.

The same honesty appears one level down in the hydration status
(`api:GET /api/v1/governance/envelope-hydration-status`): the envelopes a
hydration pass **skipped** are surfaced rather than silently dropped, and a
skipped envelope means the engine fell back to a restrictive bootstrap default.
A skip is fail-closed, not a hole — but it is also invisible everywhere else,
which is why it has its own read.

## Where enforcement actually attaches

Two questions, and both have a precise answer that is shorter than people expect.

**To which object?** **To two, and the division is the important part.** The
bounds split by *whose* they are:

| attached to | what it carries | why there |
| --- | --- | --- |
| the **role** | envelope, clearance | they describe the *seat*, so they survive whoever occupies it |
| the **agent** | trust chain, posture | they describe the *occupant* — its lineage, and how far it may go unaided |

Both are consulted at the same decision (Gate 2 below), and the split is what
makes the two facts independent: **swapping the agent in a role changes the
agent's standing and leaves the role's bounds untouched**, which is exactly what
makes a seat reusable and a re-org survivable. It is also why linking an agent
to a role grants nothing — the role's bounds were already there and the agent
brings only its own. The organisation and the unit sit above both and contribute
*ceilings* that propagate down; neither carries a value that is consulted
directly.

**At which moment?** **At the decision — not at the declaration.** Every
authority object has a declared state and a consulted state, and they are not
the same moment and are frequently not the same value. An envelope that exists in
`draft` is *declared* in every listing you will read and is *consulted* by
nothing. A clearance awaiting vetting is declared and is not consulted. That gap
is the single most common way a governance design ends up looking complete and
enforcing nothing, and the diagram below is the whole of it.

```text
WHERE A BOUND IS CONSULTED — and where it is only DECLARED

── THE DECISION PATH ── each step is a place the answer can change ───────────

   an agent forms an intent to act
     │
     │   nothing consults a bound here — an intent is not yet a request
     ▼
   ┌─ GATE 1 · ADMISSION ─────────────────────────────────────────────────────┐
   │ Is the CALL admitted?    credential · tenancy                            │
   │ Refused here, no plane is reached and no agent action was decided.       │
   └──────────────────────────────────────────────────────────────────────────┘
     │
     ▼
   ┌─ GATE 2 · THE TRUST DECISION   ★ ENFORCEMENT ATTACHES HERE ★ ────────────┐
   │                                                                          │
   │   trust chain    is there authority, and is it still valid?              │
   │   posture        how much may be used unaided, RIGHT NOW?                │
   │   envelope       does the bound permit THIS action?                      │
   │                                                                          │
   │   ⇒ ONE verdict, on THIS action:   permit  /  refuse                     │
   └──────────────────────────────────────────────────────────────────────────┘
     │
     ├── PERMIT ──▶ the action proceeds. The platform is no longer
     │              in the path; the record is written afterwards.
     │
     └── REFUSE ──▶ the action does not happen, and the reason names
                    the constraint that refused it.

══════════════════════════════════════════════════════════════════════════════
  DECLARED, BUT NOT CONSULTED AT GATE 2 — none of these changes a verdict:

    · an envelope in DRAFT           it appears in every listing and is
                                     not in force until activated
    · a clearance PENDING vetting    it exists; the role still cannot see
    · a trust SCORE or CARE budget   a projection for humans — the
                                     enforcement path does not read it
    · an envelope resolving to       counted in coverage as a FAILURE
      ALLOW-ALL                      bucket, precisely because it stops
                                     nothing
```

Two things to take from the shape. The gates are **sequential and different**: a
refusal at Gate 1 is a statement about your credential, and a refusal at Gate 2 is
a statement about the agent — they arrive with overlapping status codes and have
completely different remedies, which is [06.1](01-what-core-and-the-sdk-are.md)'s point about
plane-versus-door made concrete. And the second list is not a list of bugs. Each of those objects is in
the state it is in by design; they are simply *not* part of the decision, and a
design that treats their existence as coverage has misread which half of the
system it is looking at.

> ⚠ **Whether Gate 2 fires before the action is runtime-dependent.**
> [06.2](02-the-request-path.md) is explicit about this and it is not a detail: the hook model that puts the
> decision in front of the tool call is the `claude_agent_sdk` runtime. The
> default agent runtime has **no pre-execution gate**, and the platform warns at
> boot that it does not. The decision still exists and is still recorded — what
> changes is whether anything *stops*. Establish which runtime your deployment
> runs before you design a control that depends on a refusal happening.

## What is enforced, and what is only recorded

This is the table to design against, because treating a recording surface as an
enforcement surface is how a system ends up governed on paper only.

| surface | enforced? | what that means for you |
| --- | --- | --- |
| `verify` — the trust decision | **enforced** | the path the runtime calls; a refusal stops the action |
| envelope resolution | **enforced** | bounds what a delegate may do; fail-closed on a skip |
| posture materialisation | **enforced** | the agent's own permission set is written from it |
| clearance vs classification | **enforced** | gates reads; failure presents as "cannot see" |
| trust score / CARE budget reads | **not enforced — display only** | the enforcement path does not consult them |
| posture progression *metrics* | **inputs, not a verdict** | they are what eligibility is computed *from* |
| pipeline pre-flight validation | **partial** | constraints are not evaluated on that route today |
| audit log | **a record** | it tells you what happened; it does not prevent it |

> ⚠ **Read the middle column as what each surface is *for*, not as a measurement
> this chapter took.** Every row rests on what the surface says about itself and
> on what you can observe when a call is refused — but **no client can
> demonstrate that a control actually stops an action.** An anchor proves a
> surface exists; it cannot prove it refuses anything, and a control that
> silently stopped enforcing looks identical to one that never stopped. The four
> `enforced` rows are the platform's own account of its decision path. They are
> the rows most likely to be lifted into a design document as fact, which is why
> the caution sits here rather than below.

Three of those deserve expanding, because each is a place where the surface looks
stronger than it is.

**The scoring reads are display-only, and the module says so.** The A–F grade and
the five-dimension CARE budget (`api:GET /api/v1/trust/agents/{id}/trust-score`,
`/care-budget`) are projections for humans. The platform's enforcement path does
not consult them. **design intent, not observable:** a score that gates an action
is a score an attacker optimises against, so it is kept out of the decision path.
Design accordingly — never gate your own logic on a grade.

**Pipeline validation checks less than its name suggests.** Pre-flight validation
across a multi-agent pipeline (`api:POST /api/v1/trust/pipeline/validate`,
`sdk:aegis_sdk.trust.PipelineTrustModule`) confirms every agent holds an active
chain carrying the capabilities its step requires. Its `violated_constraints`
field is **always empty because constraints are not evaluated on that route** —
so an empty list there means *not checked*, not *none violated*. Read
`all_valid` as a statement about chains and capabilities only.

**Trust metrics are a sample on a large tenant.**
`api:GET /api/v1/trust/metrics` computes its chain and verification counts from
a bounded page of records, and the response carries **no marker distinguishing a
sample from a total**. For an organisation with more chains than that page holds,
every figure is the most recent slice rather than the population. The compliance
report (`api:GET /api/v1/trust/compliance/{id}`) scans further and *declares when
it could not* — so when a number has to be defensible, that is the surface to
reach for, and the honest move is to say which one you used.

## Withdrawal — revocation, and the shapes that confuse people

`api:POST /api/v1/trust/revoke/{id}/cascade` is the permanent, cascading removal.
`sdk:aegis_sdk.CascadeRevocationResult` reports what it revoked. The cascade is
not optional: **every revocation route cascades**, so there is no non-cascading
revoke to reach for, and revoking one agent revokes everything that derived
authority from it.

Look before you cut. `api:GET /api/v1/trust/revoke/{id}/impact` returns the
`sdk:aegis_sdk.RevocationImpact` preview — how many agents are affected, and
whether active workloads are at risk. That preview is the difference between
removing one agent and silently removing a department's, and it costs one call.
`api:POST /api/v1/trust/revoke/by-human/{id}` revokes everything originating from
a particular person, which is what you want when someone leaves;
`api:POST /api/v1/trust/revoke-delegation` removes a single delegation edge.

> ⚠ **A cascade can fail to complete, and that is a real, discoverable state.**
> `api:GET /api/v1/trust/revoke/jobs/incomplete` lists cascade revocations that
> did not finish — and **until a job here is resumed, agents it named may still
> hold active trust.** `api:POST /api/v1/trust/revoke/jobs/{id}/resume` retries
> it, idempotently, and reports whether the resume itself timed out again. Read
> the two counts on a job — completed against total — rather than its status
> string alone, because the status does not tell you how far it got. **Put this
> listing on a schedule.** A revocation you believe landed and which did not is
> the most expensive possible version of this system's failure modes.

**The reversible brake is a posture, not a chain state.** There is no operation
that suspends a trust chain; the methods that appear to be one exist only as
deprecation shims and always raise. If you need to stop an agent acting without
permanently ending its lineage, the honest tool is a *downward* posture override
— `api:PUT /api/v1/agents/{id}/trust-posture` — which applies immediately rather
than waiting on approval, and which you can lift afterwards. Use revocation for
the decision you mean to be permanent.

## The audit spine — two logs, and they answer different questions

There are two distinct audit surfaces, they are written by different subsystems,
and conflating them is how an evidence request gets answered with the wrong
document.

| | platform audit | trust audit |
| --- | --- | --- |
| read at | `api:GET /api/v1/audit/logs` | `api:GET /api/v1/trust/audit` |
| records | user actions, resource changes | trust decisions — who delegated what, on what basis |
| module | `sdk:aegis_sdk.modules.ObserveAuditModule` | `sdk:aegis_sdk.trust.AuditModule` |
| answers | "who changed this?" | "why was this agent allowed?" |

Both are queryable and exportable — `api:GET /api/v1/audit/export` for the
platform log, and per-human filtering on the trust side at
`api:GET /api/v1/trust/audit/by-human/{id}`.

### Walking a decision back to the human who authorized it

The trust audit's most valuable operation is `api:GET /api/v1/trust/audit/trace/{id}`,
which takes a single audit entry and walks its lineage **backwards to the root
human source** — the delegation chain, its depth, and the person at the top.
This is the operation that discharges the accountability claim: an
organisation can point at an action and name the human whose authority it
descended from.

> ⛔ **Read the `verified` flag on a trace with its own warning in hand.** That
> field reports signature verification but **defaults to true for an entry that
> carries no signature at all**. It therefore means *"no signature check
> failed"*, not *"this entry is cryptographically verified"* — an unsigned entry
> and a validly signed one are indistinguishable on that field alone. Check
> whether the record carries a signature before treating the flag as evidence,
> and do not report a trace as cryptographically verified on the strength of it.

### Is the log itself intact?

The audit log is presented as tamper-evident, and there are two different reads
for that claim. `api:GET /api/v1/compliance/audit/verify` performs the
verification walk — a cryptographic hash-chain check with optional start and end
bounds — and returns whether it was valid, how many entries were checked, and
the id of the first invalid entry if tampering was found. That is an
**on-demand** check you run.

`api:GET /api/v1/compliance/chain/integrity` is the *other* half: it reads the
result of the platform's own periodic verification sweep. It does not trigger a
sweep. And it has a cold-start trap worth knowing — **check the last-verified
timestamp before reading the ok flag**, because a deployment that has not yet run
a sweep reports *not ok*, which is a "nothing has been checked yet" finding and
not a "something is broken" one. Those two produce the same boolean and opposite
alarms.

## Reconstructing an action, end to end

The decision diagram earlier answered *where a bound is consulted*. This one
answers a different question — *what happens when* — and the gap between the two
halves of it is the whole reason an audit spine exists.

```text
    Agent runtime          Trust plane               Audit spine
            │                       │                       │
            │                       │                       │
            │ verify — action, resource kind and instance   │
            │──────────────────────▶│                       │
            │                       │                       │
            │                       │ resolve chain, envelope, posture
            │                       │───┐                   │
            │                       │◀──┘                   │
            │                       │                       │
            │  ── permitted         │                       │
            │                       │                       │
            │◀──────────────────────│                       │
            │ allowed, capabilities matched                 │
            │ the action proceeds   │                       │
            │───┐                   │                       │
            │◀──┘                   │                       │
            │ the action is recorded│                       │
            │───────────────────────┼──────────────────────▶│
            │                       │                       │
            │  ── refused           │                       │
            │                       │                       │
            │◀──────────────────────│                       │
            │ not allowed, constraints violated, reason     │
            │ the action does not happen                    │
            │                       │                       │
            │  ── later — by someone│who was not there      │
            │                       │                       │
            │                       │                       │ query entries, filter by agent or human
            │                       │                       │───┐
            │                       │                       │◀──┘
            │                       │                       │ trace one entry back to its root human
            │                       │                       │───┐
            │                       │                       │◀──┘
            │                       │                       │ verify the chain has not been altered
            │                       │                       │───┐
            │                       │                       │◀──┘
            │                       │                       │
```

The shape to notice is that the decision and the record are **different
witnesses**. The decision is about an intent — a tool name and its arguments, or
an action and a resource kind — made before anything happened. The record is
written after. Neither substitutes for the other, and a system that can produce
one and not the other cannot answer the question an auditor will actually ask,
which is not "was something enforced" but "show me that it was".

## What this spine does not establish

Stated as plainly as the rest, because these are the places a design goes wrong
by assuming more than is there.

- **A permitted decision is a decision about an intent, not a guarantee about an
  outcome.** No response body exists when the verdict is made.
- **A green governance check is not a statement about your configuration being
  correct.** Coverage reports readiness; they do not know what you meant.
- **The audit log records; it does not prevent.** Tamper-*evidence* is a property
  of the hash chain, not a claim that nothing can be changed before it is
  verified.
- **The trust registry's discovery surface reads chains, not agents** — see
  `sdk:aegis_sdk.trust.TrustRegistryModule` and
  `api:POST /api/v1/trust/registry/discover`. An agent with no chain is
  **invisible to discovery** even if it exists and is running, so an empty
  discovery result is not evidence that no such agent exists.
- **A signed lineage is not a trusted one.** Signature verification tells you the
  record was not altered; it says nothing about whether the authority that signed
  it should have.

**UNVERIFIED** in this edition: the precise conditions under which the platform
runs its periodic chain-verification sweep — interval, trigger and whether an
operator can schedule one — could not be settled from what is reachable here.
`api:GET /api/v1/compliance/chain/integrity` reports the *result* of a sweep; it
does not describe the schedule. If the freshness of that verification matters to
your controls, read `last_verified_at` on a schedule of your own and alarm on
staleness, rather than assuming a cadence.

---

*Next: [06.5 — The execution model](05-the-execution-model.md)*
