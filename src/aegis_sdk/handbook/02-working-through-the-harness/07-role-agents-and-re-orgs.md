# 02.7 — Role agents, and surviving a re-org

The sequences that work, in the order the platform requires them, with the traps
named where they bite. Everything here was derived by working a real deployment
and then checking each finding against the platform source, because several
things that *appeared* to be defects turned out to be old builds, and several
things that appeared to work were doing something other than advertised.

**Read 02.2 first** for the org-provisioning order and 02.4 for what a trust chain
is. This chapter is the step between them: the delegate agent that stands in for a
human in a role, and what happens to it when the org chart moves.

## The one idea that makes the rest make sense

**A delegate agent belongs to the ROLE, not to the person sitting in it.**

Once that is in view, most of the surprising behaviour stops being surprising.
The agent survives an occupant leaving. It survives a new occupant arriving — its
trust lineage is re-minted for the new seat. It does *not* survive the role being
deleted, because the role is the thing it belonged to.

And the corollary, which is the single most expensive misconception here:

> **A role with no human in it is the ordinary case, not an error state.**

Seats are routinely created before anybody is appointed. A deployment can
legitimately run with every lead role vacant. If your build refuses to create,
trust or activate an agent on a vacant role, see § "If your deployment refuses a
vacant role" at the end — that is an old build, not a rule you must design around.

## 1. A team, and the role you did not ask for

```python
unit = await client.units.create(
    name="Treasury",
    unit_type="department",
    default_classification="confidential",
)
```

Two traps, both silent.

**`default_classification` must be one of five exact values** — `public`,
`restricted`, `confidential`, `secret`, `top_secret`. Plausible synonyms are
rejected with a 422; `internal` is the one people reach for and it is not a value.

**Creating a unit auto-creates its primary role, and that role arrives
UNPARENTED** — `reports_to_role_id` is null, so it is a root of the reporting
tree rather than a child of anything. Nothing warns you. Parent it explicitly:

```python
await client.role_admin.update(primary_role_id, reports_to_role_id=parent_role_id)
```

An unparented lead role is not cosmetic. Trust chains follow the reporting
structure (02.4), so a role that reports to nothing anchors its own chain instead
of inheriting one.

## 2. A role, and its occupant — two calls, never one

`roles.create()` takes no `assigned_user_id`. Creating the seat and seating
somebody in it are separate operations, in that order:

```python
role = await client.roles.create(
    organization_unit_id=unit_id,
    title="Head of Treasury",
    authority_level=3,
)
await client.role_admin.assign_user(role["id"], user_id=user_id)
```

⚠ **Two role surfaces, and this chapter uses both.** `client.roles` carries
`create`, `get` and `list` on `/api/v1/organization-roles` and returns untyped
dicts — which is why `role["id"]` works above and would not if you reached for
the typed client instead. Everything that *administers* a role that already
exists — updating it, seating or vacating its occupant, linking or unlinking its
agent — is on `client.role_admin`, the full `/api/v1/roles` surface, and returns
typed models. A call written against the wrong one fails with `AttributeError`
before it reaches the server.

You may legitimately stop after the first call. A seat with nobody in it is a
valid, workable state — see § "Standing up a lead seat nobody occupies yet".

## 3. A role agent — one call, and be explicit about the model

```python
result = await client.agents.create_delegate_agent(
    role_id=role_id,
    provider=os.environ["AEGIS_LLM_PROVIDER"],
    model_id=os.environ["AEGIS_LLM_MODEL"],
)
agent = result.agent
```

`api:POST /api/v1/delegate-agents`. **Prefer this over hand-rolling an agent with
`is_shadow_agent=True`** (03.2 shows the hand-rolled form and why not): this call
creates the agent, establishes the trust chain, and links the role in one
operation. The hand-rolled version leaves you to remember the chain, and an agent
without one cannot be activated.

**Pass `provider` and `model_id` explicitly.** They are optional in the signature
and the server-side defaults are not guaranteed to be a runnable pair — on some
deployments the default combination fails at provisioning time rather than at call
time, which surfaces much later and much less clearly. Read both from your own
configuration; never hardcode a model string.

**Check whether the role already has one.** `roles.create()` defaults to
`auto_generate_agent=True`, so the seat may already be occupied by an agent. A
role carries at most one delegate agent, and this call will not stop you from
trying.

## 4. Promoting an agent — two principals, and not the endpoint you would guess

```python
await client.trust_posture.update_trust_posture(
    agent_id, posture="supervised", reason="routine upgrade"
)
# ... then, as a DIFFERENT principal:
await client.trust_posture.approve_posture_transition(agent_id)
```

`api:POST /api/v1/agents/{agent_id}/trust-posture/approve`. Note that
`update_trust_posture` returns a **union** — a completed transition when no
approval was required, or an approval-pending envelope when it was. Branch on
which you got; do not assume the write landed.

⛔ **Keep `reason` short and plain — this field is a live trap.** It is required,
it is free text, and a descriptive sentence in it can be rejected by a web
application firewall sitting in front of the deployment. What comes back is **raw
HTML with a 403 and no JSON body**, which is indistinguishable at a glance from an
authorization denial — so the natural conclusion is that you lack permission to
promote, when in fact the gateway never forwarded the request. `"routine upgrade"`
passes. **Before believing any 403 on this call, check whether the body is HTML.**

⛔ **Do not reach for `request-upgrade`.** It is gated on execution evidence, and
a newly created agent has none — it cannot produce evidence until it is promoted,
and cannot be promoted without evidence. For a new agent that gate is circular.
The update-then-approve path is the one that works: it records the request, routes
it for human approval, and returns a `202` on the deferred branch.

**The approval must come from a second principal.** The server derives both
identities itself and refuses a self-approval, fail-closed, with a `400` naming
the collision. This is a correct control — do not try to route around it by
re-authenticating as the same person.

**What "promoted" costs you, stated once:** a posture change resets the agent's
accumulated execution evidence. Two agents with identical configuration can sit in
different evidence states purely because one was promoted more recently.

## 5. Moving a person between teams — move the ROLE

⛔ **Do not un-assign the person and re-assign them elsewhere.** Re-point the
role, or move the role between units. `reports_to_role_id` is the safest field in
this whole surface to change:

```python
await client.role_admin.update(role_id, reports_to_role_id=new_manager_role_id)
```

The write is confined to the field you named. It does legitimately propagate —
direct-report counts on both the old and new manager, access-cache invalidation,
and a rewiring of the trust delegations between manager and subordinate agents.
That propagation is correct and required; the reporting column and the trust edge
have to agree.

⚠ **The trust rewiring is fire-and-forget.** If it fails, the call still returns
`200` and the only signal is an `X-Warning` response header saying trust chains
may need manual regeneration. **Read that header.** It is the one place this
operation can half-succeed.

### The safe recipe: UNLINK THE AGENT FIRST, THEN UNASSIGN THE USER

If you must separate a person from a seat, do it in this order:

```python
await client.role_admin.unlink_agent(role_id, agent_id)      # 1. break the role -> agent pointer
await client.role_admin.unassign_user(role_id, user_id)      # 2. now vacate the seat
```

**Unlinking first leaves the vacate step nothing to act on.** Every cascade in
this area is reached through the role's `shadow_agent_id` pointer; clear that
pointer and the cascade has no agent to find.

Measured on a live deployment: two re-orgs done in the other order each needed a
full repair sequence afterwards; the same move done unlink-first needed **zero**.
It is the single most useful ordering in this chapter.

⚠ **This matters most on a build that predates the vacancy retraction**, where
vacating actually did suspend the agent and its chain. On a current build the
vacate step is far gentler (below) and the ordering costs you nothing. **Do it
this way regardless** — it is correct on both, and you frequently do not know
which build you are talking to.

⛔ **The one-way door this avoids, on a pre-retraction build.** Once a role has
been vacated there, the two halves of the repair are **not** equally available:

| repair | on a pre-retraction build |
| --- | --- |
| restore the agent's `status` | succeeds (200) |
| re-establish the trust chain | **refused (422) — the role is vacant** |

So the agent comes back and its authority does not, and the only way to restore
the chain is to seat a human first. That asymmetry is what makes an un-repaired
cascade on a vacated role irreversible in practice, and it is why the ordering
above is worth more than the repair sequence below.

### If you must un-assign anyway

Un-assigning clears the occupant from the role and unbinds the agent from the
departed person — and that is *all* it does on a current build. The agent stays
active. Its trust chain stays live. The role keeps pointing at the agent, which is
correct: the agent belonged to the seat, not to the leaver.

Assigning the next person then re-binds automatically: the stale chain is
suspended and a fresh one minted for the new seat.

⚠ **That re-bind is best-effort and never raises.** A transient failure inside it
is logged and swallowed, and the assignment still returns `200` — leaving the
agent bound to the person who left. **Verify after every assignment** (§ 7). If
the binding did not move, repeat the assignment; it is idempotent in the
direction you want.

## 6. Un-linking an agent — know what it leaves behind

```python
await client.role_admin.unlink_agent(role_id, agent_id)
```

This clears the role's pointer to the agent. **It does not touch the agent** — the
agent remains `active`, and **its trust chain remains live while belonging to no
role at all.**

That asymmetry is worth stating plainly, because the neighbouring operation
disagrees with it: deleting a role *refuses* with a `409` rather than leave a live
trust chain orphaned. Un-linking reaches the same state with no refusal and no
warning. If you un-link deliberately, revoke the chain yourself or re-link the
agent promptly.

**To clear a field on an agent, send an empty string, not null.** `PATCH` on an
agent silently drops `null` values — the request succeeds with "No fields to
update" and nothing changes. `shadow_for_user_id=""` clears; `None` is a no-op
that looks like a success.

## 7. Verifying anything — the list endpoint, and both sides

⛔ **The agent detail endpoint omits the binding fields.** `is_shadow_agent`,
`shadow_for_user_id` and `human_role_id` read as `null` from
`api:GET /api/v1/delegate-agents/{agent_id}` **whether or not they are set**. It
is a serializer gap, not a data state, and it bites hardest during verification —
precisely when you are trying to confirm a link you just made.

**Use the list endpoint. It is the reliable read.**

```python
listing = await client.agents.list_delegate_agents(status="active")
```

`api:GET /api/v1/delegate-agents`.

**After every role operation, assert all three of these — not one:**

| assert | why |
| --- | --- |
| `agent.human_role_id` points at the role | the agent's side of the link |
| `role.shadow_agent_id` points at the agent | the role's side — maintained by *different* code |
| a trust chain exists and is not suspended | a third store, with its own status |

They are three separate records maintained by disjoint code paths with no
reconciliation between them. Checking one and inferring the others is the single
most reliable way to be wrong here. Read the chain with
`api:GET /api/v1/delegate-agents/{agent_id}/trust-chain`.

**Ordering rule, because it is counter-intuitive and enforced: trust before
status.** `api:POST /api/v1/delegate-agents/{agent_id}/activate` refuses with a
`422` unless a chain already exists. Any sequence that activates first and
establishes trust second fails on its first call.

## 8. What is irreversible — read this before deleting anything

**Roles are recoverable. Agents are not.**

Deleting a role is a *soft* delete by default: the role still resolves by id, still
carries its occupant, and can be restored by setting its status back to `active`.
A genuinely orphaned role id returns `404`, so "it still resolves" is a real
signal, not a caching artifact.

⛔ **But deleting a role archives its delegate agent, and `archived` is TERMINAL.**
The server enforces it — there is no transition out, so activation returns `422`
forever. Worse, the soft-deleted role keeps its pointer to the agent, and the
uniqueness check that guards linking counts archived roles too. So the agent ends
up **both permanently dead and permanently reserved** by the tombstone role. There
is no unlink-from-archived-role path.

Recovering the capability means provisioning a **new** agent against a **new**
role. Plan role deletion accordingly.

⚠ **Two further traps in the same family:**

- **`deactivate` also archives.** Despite the name, and despite platform-side
  documentation that has directed operators to it for "temporarily suspending" an
  agent, it reaches the same terminal state as delete. **There is no supported way
  to temporarily suspend a delegate agent** — no API route in the platform puts
  one into `suspended`.
- **Re-pointing `human_role_id` does not detach the agent from its old role.** The
  role's own pointer is untouched, so deleting that old role still archives the
  agent you thought you had moved. Un-link explicitly (§ 6) before deleting.

## Standing up a lead seat nobody occupies yet

The common case, written out, because it is the one people assume is unsupported:

```python
role  = await client.roles.create(organization_unit_id=unit_id, title="Head of Treasury", authority_level=3)
res   = await client.agents.create_delegate_agent(role_id=role["id"], provider=prov, model_id=model)
await client.agents.activate_delegate_agent(res.agent["id"])
```

No occupant, at any point. The trust chain's human origin is **you** — the
authenticated principal establishing it — not the role's occupant, which is why an
empty seat removes nothing the platform needs.

When somebody is eventually appointed, `assign_user` re-binds the existing agent to
them. You do not rebuild it.

### If your deployment refuses a vacant role

A build that answers `422 "linked role is vacant"` on activation or on trust
establishment predates the retraction of that rule. On such a build the refusal is
a **one-way door**: an agent can be created on a vacant seat and never completed,
sitting `draft` with no chain, indefinitely.

**Do not work around it by seating a placeholder human** — that writes a
fictitious person into the audit trail, which is a worse problem than the one it
solves, and one you will have to unpick later. Upgrade the deployment.

## What this chapter does not tell you

- **Whether any of it is enforced the way it is described.** These are the
  sequences that work and the traps that bite, derived from a live deployment and
  checked against source. A route existing is not a control enforcing — 04.6 is
  the chapter about reading a response honestly, and it applies to every `200`
  above.
- **What your build actually does.** Several behaviours documented here changed
  recently, and the refusals you meet are evidence about your deployment's
  revision as much as about the platform. When this chapter and your deployment
  disagree, establish which revision you are on before concluding either is wrong.
