# 09.7 — Containment and explainable refusal

The six preceding chapters govern _decisions_. This one governs _places_ — the
containers that classified material sits in, what a container is allowed to
hold, and what happens when material tries to leave one. It closes with the
other half of the same discipline: a refusal that names the rule that refused it,
because a control the operator cannot diagnose is a control the operator routes
around.

This is the newest and most consequential part of the governance model, and it
is where the classification axis from [09.3](03-clearance-and-classification.md)
stops being a property of individual items and becomes a property of the places
they live.

The idea to carry out: **a workspace is a clearance-bearing container, not a
label.** It carries a mark, that mark is the high-water of everything inside it,
and admission to the container is a floor test against that mark. Designs that
treat a workspace as a filing convention — a string you match on — produce a
system where the container advertises a ceiling it does not hold.

## Two quantities, two algebras

This is the architectural point of the whole chapter, and getting it wrong
inverts the control rather than weakening it.

| quantity        | question                         | algebra                     | direction                            |
| --------------- | -------------------------------- | --------------------------- | ------------------------------------ |
| **containment** | what does this container hold?   | `max()` — a high-water mark | monotonically non-decreasing         |
| **admission**   | may this principal be inside it? | a floor test, `>=`          | binds at every mark above the bottom |

A container's mark is raised by `max()` on every attach and is **never lowered by
a detach**. Admission compares the principal's effective clearance against that
mark and admits when the clearance reaches it — `>=`, not `>`, so an
exact-match clearance is admitted, which is the common case.

> ⛔ **Intersection is the right algebra for envelopes and the wrong one for
> classification.** [09.2](02-envelopes-and-constraints.md) composes bounds by
> intersection because a delegate must never exceed its supervisor. Applying the
> same instinct here — taking `min()` over member clearances to decide a
> container's mark — is **declassification by invite**: a workspace holding
> `confidential` documents would relabel itself downward the moment a
> `public`-cleared member joined. The two quantities look similar enough that one
> function gets reused for both, and the symptom is a container whose mark falls
> as its membership grows.

The identity matters too. `max()` over the empty set is `public` — the bottom of
the lattice — because an empty container holds nothing to protect. At that mark
the floor test is a tautology: every clearance reaches `public`, so an empty
workspace refuses nobody. That is correct, and it is why the mark rising is what
makes the container start enforcing.

## The artifact mark

An artifact carries a `classification` drawn from the same five-level EATP ladder
as everything else in [09.3](03-clearance-and-classification.md): `public`,
`restricted`, `confidential`, `secret`, `top_secret`.

```python
artifact = await client.artifacts.create(
    request_id=request_id,
    name="settlement-reconciliation.xlsx",
    content=content,
    classification="confidential",
)
```

`api:POST /api/v1/artifacts` creates one, `api:GET /api/v1/artifacts` lists,
`api:GET /api/v1/artifacts/{id}` reads the metadata,
`api:GET /api/v1/artifacts/{id}/download` retrieves the bytes, and
`api:DELETE /api/v1/artifacts/{id}` removes one. Objective- and session-scoped
listings are `api:GET /api/v1/objectives/{id}/artifacts` and
`api:GET /api/v1/sessions/{id}/artifacts`, with
`api:POST /api/v1/sessions/{id}/artifacts` for the session write path.

> ⛔ **An unmarked artifact is UNKNOWN, and unknown denies at egress. It is not
> `public`.** This is the opposite of the intuitive default and it is the one
> that makes the model sound. "We do not know what this is" must never resolve to
> "the least sensitive thing there is", because the population of unmarked
> material is exactly the population nobody has looked at. The mark is nullable
> precisely so that unknown is representable — folding it to `public` would mint
> a capability rather than record an absence.

There is a third state worth knowing about, because the two failure modes have
different remedies. A mark can be **absent** — the artifact carries nothing — or
**present but unmappable**, where a value is stored that no level recognises. Both
deny, and they deny with distinct reasons, because the operator fix differs: mark
the artifact, versus correct the value. A report that collapses them sends
somebody to the wrong remedy.

## Lineage is not versioning

Artifacts carry two different edges to other artifacts, and they answer two
different questions. Confusing them is the single most consequential modelling
error in this chapter.

| field                       | question                                  | used for                                |
| --------------------------- | ----------------------------------------- | --------------------------------------- |
| `supersedes_artifact_id`    | which row did this replace?               | **versioning** — the chain of revisions |
| `derivation_input_ids_json` | which classified material went into this? | **lineage** — the basis for the mark    |

`derivation_input_ids_json` is a JSON array of `{"kind": ..., "id": ...}` objects,
where `kind` is `artifact` or `knowledge`:

```python
derived = await client.artifacts.create(
    request_id=request_id,
    name="counterparty-summary.md",
    content=content,
    derivation_inputs=[
        {"kind": "knowledge", "id": policy_id},
        {"kind": "artifact", "id": position_extract_id},
    ],
)
```

**Only lineage makes a derived mark defensible.** A summary of a `secret` input
is `secret` — and without the lineage edge there is nothing that makes that true
except somebody remembering to say so. The versioning edge cannot stand in for
it: a new version of an artifact is not a statement about what went into the
artifact, and reading it as one produces a derived document whose mark reflects
its predecessor and not its sources.

Version history is `api:GET /api/v1/artifacts/{id}/versions`, and a new version
is created with `api:POST /api/v1/artifacts/{id}/supersede`.

## The high-water rule

A derived artifact's classification is the **maximum rank** over three sets:

```text
THE HIGH-WATER RULE

  classification = max( rank ) over

      { the declared level, if one was declared }
    ∪ { the predecessor's mark, if this supersedes something }
    ∪ { the resolved level of EVERY derivation input }

  ─────────────────────────────────────────────────────────────────────────

  WORKED:  a `secret` position extract  +  a `public` published policy
           declared as `restricted`

           max( restricted(1), secret(3), public(0) )  =  secret(3)

           The artifact is `secret`. The declaration did not lower it;
           declarations only ever contribute a candidate.

  ─────────────────────────────────────────────────────────────────────────

  THE PREDECESSOR IS A FLOOR.  A new version cannot fall below the mark of
  the version it replaces — a revision that dropped its predecessor's mark
  would be the laundry via the version chain: publish once at `secret`,
  supersede at `public`, and the content has been declassified by an edit.
```

Read it as: **every path that could produce a lower mark is closed.** Mixing a
`secret` input with a `public` one yields `secret`. Declaring a lower level than
the inputs justify yields the inputs' level. Superseding a marked artifact yields
at least its predecessor's mark. There is no ordering of operations that produces
a downgrade.

Two refusals fall out of the rule and both are deliberate:

**An unresolvable input refuses the write.** If a named derivation input cannot
be resolved to a classification, the artifact is not written. The alternative —
failing closed to `top_secret` — silently produces an artifact nobody can ever
read, which presents as data loss rather than as a refusal. A loud error naming
the input is the honest failure.

**An unrecognised input kind refuses rather than being skipped.** A skipped input
contributes nothing to the maximum, which is a downgrade wearing the appearance
of tolerance.

## Egress — three steps, in order

A read of an artifact from outside its origin workspace is an **egress**, and the
decision has three steps that must run in this order.

```text
ARTIFACT EGRESS — three steps, and the order is the design

  a consumer asks for artifact X
        │
        ▼
  ┌─ STEP 1 · TENANT BOUNDARY ─────────────────────────────────────────────┐
  │  is X in the caller's organisation?                                     │
  │  NO  →  404 NOT FOUND.  Never 403.                                      │
  │         A permission error would confirm the artifact EXISTS, which     │
  │         leaks across a tenant boundary. Not-found leaks nothing.        │
  └────────────────────────────┬───────────────────────────────────────────┘
                               │ same tenant
                               ▼
  ┌─ STEP 2 · ORIGIN WORKSPACE ────────────────────────────────────────────┐
  │  is the caller's workspace the artifact's ORIGIN workspace?             │
  │  YES →  served directly. This is not an egress at all.                  │
  │                                                                         │
  │  ⛔ A caller whose workspace is UNKNOWN is treated as EGRESS,           │
  │     never as a match. Absent is not equal.                              │
  └────────────────────────────┬───────────────────────────────────────────┘
                               │ different, or unknown, workspace
                               ▼
  ┌─ STEP 3 · CLEARANCE RANK ──────────────────────────────────────────────┐
  │  rank(consumer effective clearance)  >=  rank(artifact classification)? │
  │  NO  →  403, naming clearance as the reason.                            │
  │  artifact mark UNKNOWN  →  403. Unknown denies.                         │
  │  consumer clearance unresolvable  →  403, with its OWN reason.          │
  └─────────────────────────────────────────────────────────────────────────┘

  Step 2 is a SHORTCUT, not the gate. Step 3 is the gate.
```

Read it as: **equality is the shortcut; rank is the gate.** In-workspace reads
are fast because they skip the comparison, not because the comparison would have
passed. That has a direct consequence for how much the container's mark matters,
and it is the reason the rest of this chapter exists: since an in-workspace read
is not clearance-checked, the thing standing between a `public`-cleared member
and a `confidential` artifact is **whether they were admitted to the workspace at
all**.

The two unresolved cases deny with _distinct_ reasons — the artifact is unmarked
versus the consumer's clearance could not be established — because the operator
remedies are different and collapsing them into one "denied" makes the fix
unguessable.

> ⚠ **A cross-tenant read returns not-found, and that is not an error message
> to improve.** The temptation when an integration hits a 404 it believes should
> be a 403 is to make the platform more helpful. Do not: the 404 is the control.
> A permission error on a cross-tenant read confirms the row exists, which is
> information the caller is not entitled to and which no amount of body redaction
> puts back.

## The container mark, and what raises it

A workspace carries `contains_classification` — the high-water mark of every
document and artifact attached to it.

| operation                              | effect on the mark                                   |
| -------------------------------------- | ---------------------------------------------------- |
| attach a document or write an artifact | raised to `max(current, attached)`                   |
| attach something lower-classified      | unchanged                                            |
| detach anything                        | **unchanged** — a detach never lowers                |
| re-derive, deliberately                | recomputed, with an actor, a reason and an audit row |

**Raising is cheap; lowering is deliberate.** Raising happens as a side effect of
ordinary work and requires nothing of the caller. Lowering has exactly one path,
it demands a named actor and a non-blank reason, and it writes an audit row. That
asymmetry is the whole safety property: a declassification is an act somebody
performs and answers for, not a consequence of a detach.

```python
await client.workspaces.attach_document(
    workspace_id=workspace_id,
    knowledge_id=document_id,
)
documents = await client.workspaces.list_documents(workspace_id=workspace_id)
await client.workspaces.detach_document(
    workspace_id=workspace_id,
    knowledge_id=document_id,
)
```

Document attach, list and detach operate on the workspaces router:
`api:POST /api/v1/workspaces/{id}/documents`,
`api:GET /api/v1/workspaces/{id}/documents` and
`api:DELETE /api/v1/workspaces/{id}/documents/{document_id}`.

> ⛔ **The listing is filtered by the CALLER's own clearance, because workspace
> membership is not a read grant.** Being inside a container tells you the
> container's mark; it does not entitle you to every item in it. A member cleared
> to `restricted` in a workspace marked `confidential` sees the subset they are
> cleared for, and the absent rows are absent rather than redacted. The symptom
> of expecting otherwise is two members comparing screens and concluding the
> platform lost a document.

## Admission — the floor test

Adding a member to a workspace is an admission decision, and it runs the floor
test:

```
effective_clearance(principal)  >=  workspace.contains_classification
```

```python
await client.workspaces.add_member(
    workspace_id=workspace_id,
    user_id=user_id,
    role="contributor",
)
```

`api:POST /api/v1/workspaces/{id}/members` adds one,
`api:PATCH /api/v1/workspaces/{id}/members/{member_id}` amends the membership, and
`api:DELETE /api/v1/workspaces/{id}/members/{member_id}` removes it.

Three properties of the test are worth stating precisely:

**`>=`, not `>`.** A `confidential`-cleared principal may join a workspace
holding `confidential` content. Using `>` would deny the exact-match case, which
is the common one, and would produce a model where a clearance can only ever
admit you to material strictly below it.

**Both principal kinds route through the same resolver.** An agent's clearance is
posture-capped ([09.3](03-clearance-and-classification.md)); a human's is not,
because humans have no posture and evaluating one through the agent formula
collapses their ceiling. The admission surface takes the principal _kind_ rather
than a pre-resolved clearance, so the resolver owns that difference and three
call sites cannot each get it slightly wrong.

**An unestablished clearance is not a low one, and it denies.** If the
principal's effective clearance cannot be established at all, the admission is
refused — with a different message from a clearance that was established and was
too low, and the same outcome. Admitting on an unestablished clearance is the one
direction a retry cannot undo.

The refusal message names the **workspace's mark** and deliberately does not name
the refused principal's clearance level. That is not terseness: echoing the level
would hand a caller a clearance-enumeration oracle over third parties — attempt
an add per user against a marked workspace and read each level out of the
refusal. The mark is a property of a row the caller can already read; the other
party's clearance is not.

## A container may only hold what it can enforce

A workspace carries a classification and no compartment. From
[09.3](03-clearance-and-classification.md), `secret` and `top_secret` require
compartment-level need-to-know, and a rank comparison is not a need-to-know
check.

So the workspace's writable vocabulary is **`{public, restricted, confidential}`**,
and material above that is **refused at the door rather than approximated by
rank**.

```text
WHY REFUSING BEATS APPROXIMATING

  Suppose a `secret` document is attached to a workspace, and the platform
  responds by raising the mark as far as the container can express —
  `confidential` — and logging the shortfall.

      Admission now requires `confidential`.
      A `confidential`-cleared principal is admitted.
      They are INSIDE the workspace, so their read is not clearance-checked
      (egress step 2).
      They read the `secret` document in place.

  The breach happens. A line appears in a file.

  The alternative — raising the mark to `secret` — is worse, not better:
  the mark would then READ as need-to-know isolation with none of the
  compartment membership behind it. A control that reads stronger than what
  runs is more dangerous than a narrower one that is honest.

  Therefore: REFUSE. 422, naming the document and the mark that cannot
  express it.
```

This is the general principle and it applies well beyond workspaces: **do not
offer a protection you cannot enforce.** The refusal is a smaller capability and
an honest one, and it makes the gap visible at the moment somebody tries to rely
on it rather than at the incident review.

## Two properties that make the gate real

**The container is never caller-chosen.** The workspace an artifact belongs to is
derived server-side from the request it was produced for — it is not a parameter
of the create call. A caller who picks the container picks whose classification
mark gets raised, which is a governance hole rather than a convenience. When the
request carries no workspace, the write is refused rather than falling back to
some other identifier; substituting a different kind of id into the workspace
slot trades a refusal for an outage two layers down.

**The gate runs before any side effect.** The container capability check happens
before the bytes reach storage and before the row is written, so a refusal leaves
nothing behind. Ordering it the other way produces the worst artefact of all: a
stored object whose row was refused, or a row whose bytes were never written —
each of which looks like corruption rather than like a control.

> ⚠ **Build your own write paths the same way.** If your integration produces
> classified material, route it through the platform's artifact write rather than
> storing it yourself and registering it afterwards. The register-afterwards shape
> has a window in which the material exists and is unmarked, and that window is
> exactly the population `unknown` was designed to deny.

## Explainable refusal

A refusal that says only "denied" is a refusal an operator will work around,
because working around it is the only action available. Every refusal in this
part names the rule that refused it, and the status code is the first half of
that answer.

| status  | what it means here                                        | remedy                                               |
| ------- | --------------------------------------------------------- | ---------------------------------------------------- |
| **403** | egress denied — clearance rank, or an unknown mark        | mark the artifact, or raise the reader's clearance   |
| **404** | tenant mismatch, or genuinely absent                      | check the tenant; the two are deliberately identical |
| **409** | the object exists but is not in a state that permits this | activate, approve, or resolve the pending change     |
| **422** | the sensitivity cannot be expressed by this container     | use a container that can hold it, or reclassify      |

The reason strings carry the second half. An egress refusal distinguishes _the
artifact is unmarked_ from _your clearance could not be established_ from _your
clearance is below the mark_, because those are three different fixes performed
by three different people.

For the broader question — _which gate would refuse, and where would the
evaluation stop_ — `api:POST /api/v1/governance/explain-access` evaluates a role
against a knowledge item and returns the decision as a trace: allowed or not, the
reason, the `step_reached`, and the access path taken.

```python
trace = await client.governance_explain.explain_access(
    agent_id=agent_id,
    knowledge_item_id=document_id,
)
```

⛔ **It is a DIAGNOSTIC YOU RUN, never a lookup of what happened.** The call is a
dry run over the subject you describe: nothing is read from any stored refusal,
nothing is accessed, nothing is recorded, and a wrong or missing field in the
description changes the verdict. It answers _what would the model decide about
this role and this item_ — not _why was this request refused_. For what actually
happened, the audit spine ([09.6](06-the-audit-spine-and-evidence.md)) is the
surface, and reading a dry run as a record of a past refusal is the mistake that
sends a remediation after a cause the live request never hit.

**Read `step_reached`, not `allowed`.** `allowed` restates the outcome; the step
name is the phase the evaluation stopped at, and it is the only field that
narrows a refusal to a gate. Its companion
`api:POST /api/v1/governance/describe-address` resolves a
positional address in the organisation tree to the objects that govern it, which
is the read to reach for when the refusal named an ancestor you cannot place.

> ⛔ **A refusal that cannot be diagnosed is a refusal that gets disabled.** This
> is the operational argument for everything in this section, and it is not a
> nicety. The sequence is always the same: the control refuses, nobody can
> establish why, the work is urgent, somebody widens the bound that seems most
> likely — and now the control is gone _and_ the original cause is still there.
> Name the rule in the refusal and the sequence does not start.

## Designing with containment

Four pieces of guidance, in the order they matter.

**Partition by sensitivity, not by project.** A workspace's mark is the
high-water of its contents, so a workspace mixing `public` onboarding material
with one `confidential` analysis is marked `confidential` and every future member
needs that clearance. The remedy is not to lower the mark; it is to have put the
analysis somewhere else.

**Expect the mark to ratchet, and design the membership for where it will end
up.** Marks rise as work proceeds and never fall on their own. A workspace
provisioned with members cleared exactly to its current mark will start refusing
additions the first time something more sensitive lands. Provision membership
against the mark you expect, not the mark you have.

**Declare lineage at the moment of creation.** The derivation inputs are what
make a derived mark defensible, and they are available at the moment the derived
artifact is produced and reconstructible only with effort afterwards. An
integration that creates artifacts without declaring inputs is producing material
whose sensitivity has to be re-established by hand.

**Re-derive deliberately, and rarely.** The re-derivation path exists because a
container's mark can legitimately become wrong — the document that raised it was
detached and nothing else in the container justifies the level. Use it with a
real reason written for somebody reading the audit row in a year, and treat a
deployment that re-derives on a schedule as a deployment that has turned the one
audited declassification path into an unattended one.

> **In the console:** a workspace's mark appears on the workspace rather than on
> its documents, and a member add that the floor test refuses surfaces as a
> refusal with the mark named. The document list inside a workspace is the
> clearance-filtered one, so two members legitimately see different lists — which
> is worth saying out loud to operators, because the first report is invariably
> "documents are missing".

## Summary

| you need                              | the mechanism            | the call                                                     |
| ------------------------------------- | ------------------------ | ------------------------------------------------------------ |
| mark an artifact                      | classification at create | `api:POST /api/v1/artifacts`                                 |
| make a derived mark defensible        | derivation inputs        | `derivation_inputs=[...]` at create                          |
| a new version that cannot declassify  | supersede                | `api:POST /api/v1/artifacts/{id}/supersede`                  |
| read the revision chain               | versions                 | `api:GET /api/v1/artifacts/{id}/versions`                    |
| retrieve the bytes, clearance-checked | download                 | `api:GET /api/v1/artifacts/{id}/download`                    |
| put a document in a container         | attach                   | `api:POST /api/v1/workspaces/{id}/documents`                 |
| see what is in a container, filtered  | list documents           | `api:GET /api/v1/workspaces/{id}/documents`                  |
| take one out without declassifying    | detach                   | `api:DELETE /api/v1/workspaces/{id}/documents/{document_id}` |
| admit a principal to a container      | member add, floor-tested | `api:POST /api/v1/workspaces/{id}/members`                   |
| find out which gate would refuse      | access dry run           | `api:POST /api/v1/governance/explain-access`                 |
| place an address in the tree          | address description      | `api:POST /api/v1/governance/describe-address`               |

---

_Next: [Part 10 — The organisation structure framework](../10-the-organization-structure-framework/README.md)_
