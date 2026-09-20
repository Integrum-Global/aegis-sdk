# 08.8 — Commercial and extensibility

This chapter closes the catalogue with the two surfaces that surround everything
else: **what the platform costs** and **what attaches to it from outside**.

They sit together because they share a property the rest of the catalogue does
not. Every other chapter describes things inside the governed organisation —
roles, agents, work, knowledge. These describe the boundary: metering, which
measures what crossed it; and integration, which is the crossing itself. An
external agent, a gateway, a registered surface and a third-party application are
all ways something outside becomes something the organisation can govern.

**Everything that attaches from outside is governed on the way in.** An external
agent is bounded by an envelope like any other; an application holds explicit,
revocable grants; a tool agent publishes a capability under a policy. There is no
side door.

[03.4](../03-extending-the-platform/04-applications-grants-and-policy.md) teaches
the grant model this chapter inventories.

## What the commercial surface is actually selling

Worth stating plainly before the metering tables, because it is the thing most
often misread at a procurement review.

**You keep the accountability. Aegis gives you the proof.** Your organisation is
accountable for what its agents do, and that accountability cannot be delegated
to a platform, a vendor, or a model — "the AI did it" is not a defence anywhere
that matters. What this platform provides is the **evidence** that your
governance was real: bounded mandates, tamper-evident audit, fail-closed
permissions, and attestable lineage, against an external open standard.

So the artifact the commercial surface produces is a **proof artifact** — a
signed, exportable record of conformance, audit chain and human gates that a
CISO can put in front of an auditor, or an insurer can underwrite against. It
makes your residual risk documentable. It does not move your risk onto someone
else, and no offering here should be read as doing so.

The practical consequence for an evaluator: the question to ask of this chapter
is _"can we evidence our governance to a third party?"_ and not _"who is on the
hook?"_ The second question has the same answer it had before Aegis — you are —
and [08.7](07-evidence-and-operations.md) is where the answer to the first one is
produced.

## Billing and metering

What the organisation is consuming, what it will cost, and the payment surface.

| capability                         | what it does                                   |
| ---------------------------------- | ---------------------------------------------- |
| **Usage / usage details**          | What has been consumed, summarised or itemised |
| **Quotas**                         | The consumption ceilings in force              |
| **Update / adjust quota**          | Change a ceiling                               |
| **Periods / current period / get** | Billing periods                                |
| **Close period**                   | Finalise a period                              |
| **Estimate cost**                  | Price a hypothetical before committing to it   |
| **Pricing**                        | The rate card                                  |
| **Plans**                          | Available plans                                |
| **Summary**                        | The billing position at a glance               |
| **Setup / remove payment method**  | Manage payment instruments                     |
| **Set default payment method**     | Choose which one is used                       |
| **Billing contact**                | Who receives billing correspondence            |
| **Usage alerts**                   | Thresholds that warn before a ceiling is hit   |
| **Metered items / reconcile**      | Attach and reconcile metered usage             |

Entry point: `sdk:aegis_sdk.revenue.billing.BillingModule`.

Operations: `api:GET /api/v1/billing/usage` ·
`api:GET /api/v1/billing/usage/details` · `api:GET /api/v1/billing/quotas` ·
`api:PUT /api/v1/billing/quotas/{id}` ·
`api:POST /api/v1/billing/quotas/adjust` · `api:GET /api/v1/billing/periods` ·
`api:GET /api/v1/billing/periods/current` ·
`api:GET /api/v1/billing/periods/{id}` ·
`api:POST /api/v1/billing/periods/{id}/close` ·
`api:POST /api/v1/billing/estimate` · `api:GET /api/v1/billing/pricing` ·
`api:GET /api/v1/billing/plans` · `api:GET /api/v1/billing/summary` ·
`api:POST /api/v1/billing/setup-payment-method` ·
`api:DELETE /api/v1/billing/payment-methods/{id}` ·
`api:POST /api/v1/billing/payment-methods/{id}/default` ·
`api:GET /api/v1/billing/contact` · `api:PUT /api/v1/billing/contact` ·
`api:GET /api/v1/billing/alerts` · `api:PUT /api/v1/billing/alerts` ·
`api:POST /api/v1/billing/metered-items` ·
`api:POST /api/v1/billing/metered-reconcile`

```python
current = await client.revenue.billing.get_current_period()
usage = await client.revenue.billing.get_usage()

estimate = await client.revenue.billing.estimate_cost(
    workload={"agent_executions": 50_000, "knowledge_items": 2_000},
)

await client.revenue.billing.update_usage_alerts(
    thresholds=[{"resource": "agent_executions", "percent": 80}],
)
```

> ⚠ **Set usage alerts before you need them.** A quota reached mid-objective
> stops work, and the refusal arrives attributed to the agent that happened to be
> running — not to the quota. The alert at 80% is what turns an outage into a
> conversation.

**Estimate before a large workload, not after.** `estimate` prices a hypothetical
against the live rate card, which is the only way to answer "what will this
campaign cost" without running it.

## Subscriptions

The plan the organisation is on, and the self-service surface for changing it.

| capability              | what it does                     |
| ----------------------- | -------------------------------- |
| **Current**             | The active subscription          |
| **Plans**               | What is available                |
| **Subscribe**           | Take a plan                      |
| **Upgrade**             | Move to a higher plan            |
| **Cancel / reactivate** | End a subscription, or resume it |
| **Usage**               | Consumption against the plan     |
| **Invoices**            | Billing documents                |
| **Portal**              | A hosted self-service session    |

Entry points: `sdk:aegis_sdk.revenue.subscriptions.SubscriptionsModule`,
`sdk:aegis_sdk.revenue.plans.PlansModule` and
`sdk:aegis_sdk.revenue.invoices.InvoicesModule`.

Operations: `api:GET /api/v1/subscriptions/current` ·
`api:GET /api/v1/subscriptions/plans` ·
`api:POST /api/v1/subscriptions/subscribe` ·
`api:PUT /api/v1/subscriptions/upgrade` ·
`api:POST /api/v1/subscriptions/cancel` ·
`api:POST /api/v1/subscriptions/reactivate` ·
`api:GET /api/v1/subscriptions/usage` ·
`api:GET /api/v1/subscriptions/invoices` ·
`api:POST /api/v1/subscriptions/portal`

```python
sub = await client.revenue.subscriptions.get()
comparison = await client.revenue.plans.compare_tiers()
```

**Cancellation is not immediate termination.** A cancelled subscription runs to
the end of its period and `reactivate` reverses it within that window. Treating
cancel as a kill switch leaves the organisation running and billing until the
period closes.

## Licences

Where the deployment is licensed rather than subscribed — generation, validation,
and revocation.

| capability   | what it does                     |
| ------------ | -------------------------------- |
| **Generate** | Issue a licence                  |
| **Validate** | Check one is genuine and current |
| **Revoke**   | Withdraw it                      |
| **Status**   | The licence position             |
| **Usage**    | Consumption against one licence  |
| **Editions** | The licence editions available   |

Entry point: `sdk:aegis_sdk.revenue.licenses.LicensesModule`.

Operations: `api:POST /api/v1/licenses/generate` ·
`api:POST /api/v1/licenses/validate` ·
`api:POST /api/v1/licenses/{id}/revoke` ·
`api:GET /api/v1/licenses/status` · `api:GET /api/v1/licenses/{id}/usage` ·
`api:GET /api/v1/licenses/editions`

> ⛔ **A licence governs the deployment, not this SDK.** The harness you are
> reading is obtained by cloning it and working inside the directory — there is
> no package index entry for it, no version to pin, and nothing to install. What
> a licence covers is the platform your client points at.
>
> The distinction matters because one nearby thing genuinely is an installed
> package: **`kailash-enterprise`** is the runtime Aegis is _built on_, and it is
> a dependency of the platform rather than something an architect adds to their
> own project. Two different artifacts, one of which is installed and one of
> which is cloned — reaching for a package manager to obtain this SDK is the
> error the distinction exists to prevent.

## Features and quotas

Feature gating — whether a capability is available on this plan — and the quota
surface that bounds consumption of it.

| capability             | what it does                                    |
| ---------------------- | ----------------------------------------------- |
| **Check**              | Is this feature available to this organisation? |
| **Limits**             | The limits this plan imposes                    |
| **Tiers**              | What each tier includes                         |
| **Get / update quota** | Read and change a quota                         |
| **Check limit**        | Whether a specific limit has been reached       |

Entry points: `sdk:aegis_sdk.revenue.features.FeaturesModule`,
`sdk:aegis_sdk.revenue.quotas.QuotasModule` and
`sdk:aegis_sdk.revenue.usage.UsageModule`.

Operations: `api:GET /api/v1/features/check` ·
`api:GET /api/v1/features/limits` · `api:GET /api/v1/features/tiers`

```python
available = await client.revenue.features.check(feature="advanced_lineage")
if not available["enabled"]:
    fall_back_to_basic_lineage()
```

**Check the feature before building the path that depends on it.** A feature
check that runs only in the error handler means the first time you learn a
capability is unavailable is when a user hits it.

## Applications, grants and policy

An application is a third party the organisation has admitted: it holds explicit
grants over named tool agents, operates under an invocation policy, and every
call it makes is attributable to it.

| capability                   | what it does                                       |
| ---------------------------- | -------------------------------------------------- |
| **Create / update / delete** | Manage an application                              |
| **List / get / summary**     | Enumerate and inspect                              |
| **Change status**            | Move it between states                             |
| **Archive**                  | Retire it                                          |
| **Freeze status**            | Whether it is frozen, and why                      |
| **Grants**                   | List, grant and revoke access to named tool agents |
| **Policy**                   | Read and set the invocation policy                 |
| **Delegation matrix**        | Which of its operators may invoke what             |
| **Operators**                | List, add and remove the humans behind it          |
| **Invocations**              | What it has called                                 |
| **Audit events**             | Its governed act history                           |
| **Notifications**            | What it has been told                              |

Entry point: `sdk:aegis_sdk.modules.applications.ApplicationsModule`.

Operations: `api:POST /api/v1/applications` · `api:GET /api/v1/applications` ·
`api:GET /api/v1/applications/{id}` · `api:PUT /api/v1/applications/{id}` ·
`api:DELETE /api/v1/applications/{id}` ·
`api:GET /api/v1/applications/{id}/summary` ·
`api:PATCH /api/v1/applications/{id}/status` ·
`api:GET /api/v1/applications/{id}/freeze-status` ·
`api:GET /api/v1/applications/{id}/grants` ·
`api:POST /api/v1/applications/{id}/grants` ·
`api:DELETE /api/v1/applications/{id}/grants/{grant_id}` ·
`api:GET /api/v1/applications/{id}/policy/{policy_id}` ·
`api:PUT /api/v1/applications/{id}/policy/{policy_id}` ·
`api:GET /api/v1/applications/{id}/delegation-matrix` ·
`api:PUT /api/v1/applications/{id}/delegation-matrix` ·
`api:GET /api/v1/applications/{id}/operators` ·
`api:POST /api/v1/applications/{id}/operators` ·
`api:DELETE /api/v1/applications/{id}/operators/{operator_id}` ·
`api:GET /api/v1/applications/{id}/invocations` ·
`api:GET /api/v1/applications/{id}/notifications` ·
`api:GET /api/v1/applications/{id}/audit-events`

```python
app = await client.applications.create(
    name="treasury-dashboard",
    description="Read-only liquidity view for the treasury team.",
)
await client.applications.grant_tool_agent(
    application_id=app["id"],
    tool_agent_id=liquidity_reader_id,
)
matrix = await client.applications.get_delegation_matrix(application_id=app["id"])
```

> ⛔ **Revoking a grant is what stops an application; deleting the application is
> not.** A deleted application's outstanding grants are the thing to check — and
> `api:GET /api/v1/applications/{id}/invocations` is how you establish what it
> actually did before you retire it. Retire in that order: read the invocations,
> revoke the grants, then delete.

**The delegation matrix is where over-broad access hides.** Grants say which tool
agents the application may reach; the matrix says which of its operators may
invoke them. An application with narrow grants and a permissive matrix gives
every operator the full grant set, which is rarely what was intended.

## Tool agents — publishing a governed capability

A tool agent is a capability other agents and applications invoke, wrapped in
governance. It is the primary extension point of the platform.

| capability                   | what it does                                    |
| ---------------------------- | ----------------------------------------------- |
| **Create / update / delete** | Manage a tool agent                             |
| **List / get**               | Enumerate them                                  |
| **Change status**            | Move it through its lifecycle                   |
| **Invoke**                   | Call it                                         |
| **Envelope summary**         | The bounds it operates within                   |
| **Consumers**                | Who is using it                                 |
| **Invocations**              | What it has been asked to do                    |
| **Components**               | List, add and remove the parts it is built from |
| **Impact**                   | What would be affected by changing it           |

Entry point: `sdk:aegis_sdk.modules.tool_agents.ToolAgentsModule`.

Operations: `api:POST /api/v1/tool-agents` · `api:GET /api/v1/tool-agents` ·
`api:GET /api/v1/tool-agents/{id}` · `api:PUT /api/v1/tool-agents/{id}` ·
`api:PATCH /api/v1/tool-agents/{id}/status` ·
`api:POST /api/v1/tool-agents/{id}/invoke` ·
`api:GET /api/v1/tool-agents/{id}/envelope-summary` ·
`api:GET /api/v1/tool-agents/{id}/consumers` ·
`api:GET /api/v1/tool-agents/{id}/invocations` ·
`api:GET /api/v1/tool-agents/{id}/components` ·
`api:POST /api/v1/tool-agents/{id}/components` ·
`api:DELETE /api/v1/tool-agents/{id}/components/{component_id}` ·
`api:GET /api/v1/tool-agents/{id}/impact`

```python
impact = await client.tool_agents.get_impact(tool_agent_id=ta_id)
consumers = await client.tool_agents.list_consumers(tool_agent_id=ta_id)
```

**Check `impact` and `consumers` before changing a published tool agent.** It is
a shared capability by design, so a change to its behaviour propagates to every
consumer silently — they are not notified, and their next invocation gets the new
behaviour. [03.3](../03-extending-the-platform/03-the-tool-agent-lifecycle.md)
owns the lifecycle discipline.

## External agents

Agents that live outside this deployment and are invoked across the boundary.
They are registered, governed and metered like anything else.

| capability                   | what it does                             |
| ---------------------------- | ---------------------------------------- |
| **Create / update / delete** | Register and manage one                  |
| **List / get**               | Enumerate them                           |
| **Invoke**                   | Call across the boundary                 |
| **Invocations**              | What has been called, and what came back |

Entry point: `sdk:aegis_sdk.modules.integrations.IntegrationsModule`.

Operations: `api:POST /api/v1/external-agents` ·
`api:GET /api/v1/external-agents` · `api:GET /api/v1/external-agents/{id}` ·
`api:PATCH /api/v1/external-agents/{id}` ·
`api:DELETE /api/v1/external-agents/{id}` ·
`api:POST /api/v1/external-agents/{id}/invoke` ·
`api:GET /api/v1/external-agents/{id}/invocations`

```python
ext = await client.integrations.create_external_agent(
    name="partner-risk-scorer",
    endpoint_url="https://partner.example.com/score",
    auth_type="api_key",
    credential_id=partner_credential_id,
)
result = await client.integrations.invoke_external_agent(
    external_agent_id=ext["id"],
    payload={"counterparty_id": cp_id},
)
```

> ⛔ **An external agent's governance fields are separate permissions on
> purpose.** Its budget, rate limits and credentials are not ordinary update
> fields — changing them is a governance act, and the platform gates them
> accordingly. If an update is refused where the general update succeeded, that
> is the gate working, not a bug.

## Gateways and deployments

Gateways front external traffic; deployments are the runnable units the platform
manages.

| capability   | gateways | deployments |
| ------------ | -------- | ----------- |
| Create       | yes      | yes         |
| List         | yes      | yes         |
| Get          | —        | yes         |
| Start / stop | —        | yes         |
| Redeploy     | —        | yes         |

Entry point: `sdk:aegis_sdk.modules.integrations.IntegrationsModule`.

Operations: `api:GET /api/v1/gateways` · `api:POST /api/v1/gateways` ·
`api:GET /api/v1/deployments` · `api:POST /api/v1/deployments` ·
`api:GET /api/v1/deployments/{id}` ·
`api:POST /api/v1/deployments/{id}/start` ·
`api:POST /api/v1/deployments/{id}/stop` ·
`api:POST /api/v1/deployments/{id}/redeploy`

```python
await client.integrations.redeploy_deployment(deployment_id=d_id)
metrics = await client.metrics.deployment_metrics(deployment_id=d_id)
```

Per-deployment measurement is catalogued in
[08.7](07-evidence-and-operations.md). The platform-level deployment
architecture — clusters, images, networks — is part 07, and is a different
subject from these records.

## Credentials

The secret store. Credentials are stored once, referenced by id everywhere, and
rotated without touching the things that use them.

| capability           | what it does                                     |
| -------------------- | ------------------------------------------------ |
| **Store**            | Put a secret in                                  |
| **List / get**       | Enumerate metadata — never the secret            |
| **Retrieve**         | Read a secret, as a governed act                 |
| **Rotate**           | Replace the secret, keeping the reference stable |
| **Revoke**           | Withdraw it immediately                          |
| **Delete**           | Remove the record                                |
| **Types / statuses** | The kinds available and the states one can be in |

Entry point: `sdk:aegis_sdk.modules.credentials.CredentialsModule`.

Operations: `api:POST /api/v1/credentials` · `api:GET /api/v1/credentials` ·
`api:GET /api/v1/credentials/{id}` ·
`api:POST /api/v1/credentials/{id}/retrieve` ·
`api:POST /api/v1/credentials/{id}/rotate` ·
`api:POST /api/v1/credentials/{id}/revoke` ·
`api:DELETE /api/v1/credentials/{id}` ·
`api:GET /api/v1/credentials/types` · `api:GET /api/v1/credentials/statuses`

```python
cred = await client.credentials.store(
    name="partner-api-key",
    credential_type="api_key",
    value=secret_value,
)
# Reference it by id from connectors and external agents; rotate in one place
await client.credentials.rotate(credential_id=cred["id"], value=new_secret)
```

**Rotation is the reason to reference rather than embed.** A secret pasted into a
connector configuration and an external agent's auth block must be changed in
both places and in whatever else copied it; a stored credential referenced by id
is rotated once. `retrieve` is itself a governed, audited act — if you find it
being called on a hot path, something is re-reading a secret it should hold.

## Surface registry

The catalogue of what this deployment publishes: which surfaces exist and which
are registered as available.

| capability                                | what it does              |
| ----------------------------------------- | ------------------------- |
| **Manifest**                              | The full surface manifest |
| **List / get registrations**              | What is registered        |
| **Create / update / delete registration** | Manage a registration     |

Entry point: `sdk:aegis_sdk.modules.surfaces.SurfacesModule`.

Operations: `api:GET /api/v1/surface-registry` ·
`api:GET /api/v1/surface-registry/registrations` ·
`api:GET /api/v1/surface-registry/registrations/{id}` ·
`api:POST /api/v1/surface-registry/registrations` ·
`api:PATCH /api/v1/surface-registry/registrations/{id}` ·
`api:DELETE /api/v1/surface-registry/registrations/{id}`

```python
manifest = await client.surfaces.manifest()
```

`manifest` is worth calling once against any deployment you are new to — it is
the deployment's own statement of what it publishes, which is a useful
cross-check against this catalogue.

## LLM providers and models

Which models the deployment may use, what they cost, and whether they are
healthy.

| capability                          | what it does                         |
| ----------------------------------- | ------------------------------------ |
| **List / create / update provider** | Manage provider configuration        |
| **Provider health**                 | Whether a provider is reachable      |
| **Refresh provider cache**          | Re-read a provider's model list      |
| **List models / all models**        | What is available                    |
| **Validate model**                  | Check a model name is usable         |
| **Model metadata**                  | Capabilities and limits of one model |
| **Rate card / pricing**             | What each model costs                |

Entry point: `sdk:aegis_sdk.modules.llm_providers.LlmProvidersModule`.

Operations: `api:GET /api/v1/llm/providers` · `api:POST /api/v1/llm/providers` ·
`api:PUT /api/v1/llm/providers/{id}` ·
`api:GET /api/v1/llm/providers/{id}/health` ·
`api:POST /api/v1/llm/providers/{id}/refresh` ·
`api:GET /api/v1/llm/models` · `api:GET /api/v1/llm/models/all` ·
`api:POST /api/v1/llm/models/validate` ·
`api:GET /api/v1/llm/models/{provider}/{model}/metadata` ·
`api:GET /api/v1/llm/pricing`

```python
health = await client.llm_providers.check_provider_health(provider_id=p_id)
ok = await client.llm_providers.validate_model(provider="openai", model=model_name)
rates = await client.llm_providers.get_rate_card()
```

**Validate a model name before configuring an agent with it.** An agent
configured against a model the provider has retired fails at execution time, and
the error surfaces as an agent failure rather than as a configuration problem.
`refresh` re-reads the provider's list, which is what you want after a provider
deprecates something.

## Administrative surface

Cross-cutting administration: pools, agent assignments, and the access views that
answer _who can reach what_.

| capability                  | what it does                                        |
| --------------------------- | --------------------------------------------------- |
| **Pools**                   | Create, list, get, update, delete and archive pools |
| **Pool stats**              | Statistics for one pool                             |
| **Agent assignments**       | List, get, create and delete assignments            |
| **Bulk delete assignments** | Remove many at once                                 |
| **Role hierarchy**          | The administrative view of the role tree            |
| **Access tree**             | Who can reach what, as a tree                       |
| **Access matrix**           | The same, as a matrix                               |
| **Access audit**            | The access-review record                            |
| **Export access**           | Extract the access picture for review               |

Entry point: `sdk:aegis_sdk.modules.admin.AdminModule`.

Operations: `api:GET /api/v1/admin/pools` · `api:POST /api/v1/admin/pools` ·
`api:GET /api/v1/admin/pools/{id}` · `api:PUT /api/v1/admin/pools/{id}` ·
`api:DELETE /api/v1/admin/pools/{id}` ·
`api:POST /api/v1/admin/pools/{id}/archive` ·
`api:GET /api/v1/admin/pools/{id}/stats` ·
`api:GET /api/v1/admin/agent-assignments` ·
`api:POST /api/v1/admin/agent-assignments` ·
`api:GET /api/v1/admin/agent-assignments/{id}` ·
`api:DELETE /api/v1/admin/agent-assignments/{id}` ·
`api:POST /api/v1/admin/agent-assignments/bulk-delete` ·
`api:GET /api/v1/admin/roles/hierarchy` ·
`api:GET /api/v1/admin/access/tree` · `api:GET /api/v1/admin/access/matrix` ·
`api:GET /api/v1/admin/access/audit` · `api:POST /api/v1/admin/access/export`

```python
matrix = await client.admin.get_access_matrix()
export = await client.admin.export_access(format="csv")
```

**The access matrix is the artefact an access review actually needs.** It answers
"who can reach what" in one call, where reconstructing the same picture from
roles, grants, clearances and envelopes takes a working day and gets it wrong.
Export it on whatever cadence your review requires.

## Presentations

Generating a presentable view of platform state — for a report, a review, or a
stakeholder.

| capability | what it does            |
| ---------- | ----------------------- |
| **Create** | Generate a presentation |
| **Get**    | Retrieve one            |

Entry point: `sdk:aegis_sdk.modules.presentation.PresentationModule`.

Operations: `api:POST /api/v1/presentations` ·
`api:GET /api/v1/presentations/{id}`

```python
deck = await client.presentation.create(
    subject="quarterly-governance-review",
    period={"start": "2026-07-01", "end": "2026-09-30"},
)
rendered = await client.presentation.get(presentation_id=deck["id"])
```

## Where the boundary is drawn

```
                    OUTSIDE                    │           INSIDE
                                               │
   third party ──► application ──► grants ─────┼──► tool agent ──► envelope
                        │                      │         │
                        └──► delegation matrix │         └──► invocations (metered)
                                               │
   partner system ──► external agent ──────────┼──► envelope ──► invocations (metered)
                            │                  │
                            └──► credential ───┤
                                               │
   traffic ──► gateway ────────────────────────┼──► deployment
                                               │
                                               │    surface registry
                                               │    (what this side publishes)
```

Read it as: everything crossing the line left-to-right passes through a governed
object — a grant, an envelope, a credential reference — and everything that
crosses is metered on the way. **There is no path from the left column to the
right that skips the middle**, which is what makes an external integration
something the organisation can evidence rather than something it has to trust.

## Summary — what this chapter covered

| area                  | entry point                                                    | scale         |
| --------------------- | -------------------------------------------------------------- | ------------- |
| Billing               | `revenue.billing`                                              | 22 operations |
| Subscriptions         | `revenue.subscriptions` · `revenue.plans` · `revenue.invoices` | 9 operations  |
| Licences              | `revenue.licenses`                                             | 6 operations  |
| Features and quotas   | `revenue.features` · `revenue.quotas` · `revenue.usage`        | 3 operations  |
| Applications          | `modules.applications`                                         | 21 operations |
| Tool agents           | `modules.tool_agents`                                          | 13 operations |
| External agents       | `modules.integrations`                                         | 7 operations  |
| Gateways, deployments | `modules.integrations`                                         | 8 operations  |
| Credentials           | `modules.credentials`                                          | 9 operations  |
| Surface registry      | `modules.surfaces`                                             | 6 operations  |
| LLM providers         | `modules.llm_providers`                                        | 10 operations |
| Admin                 | `modules.admin`                                                | 17 operations |
| Presentations         | `modules.presentation`                                         | 2 operations  |

## The catalogue, closed

You have now seen the whole of the client-driven surface — all 933 operations
this SDK declares, across eighteen capability areas: identity and organisation in
[08.2](02-organization-and-identity.md), the actors in
[08.3](03-agents-and-execution.md), the work in
[08.4](04-work-and-objectives.md), the controls in
[08.5](05-governance-and-trust.md), what it knows in
[08.6](06-knowledge-and-data.md), what it recorded in
[08.7](07-evidence-and-operations.md), and what surrounds it here.

The platform itself serves more than this — roughly 1,254 authored operations
against the client's 933 — and the remainder are reached over HTTP rather than
through an SDK method, by the path
[04.1](../04-the-api-surface/01-calling-the-api.md) sets out. That is a
difference in surface size, not a missing capability, and
[08.1](01-how-to-read-this-catalogue.md) explains which denominator answers which
question.

If you arrived with a requirements list, [08.5](05-governance-and-trust.md) is
the chapter to re-read — most requirements that sound like they are about
capability turn out to be about control, and that is the chapter where Aegis
differs most from a platform that added governance afterwards. Five of the
eighteen capability areas land there.

If you arrived to build, go back to
[02.2](../02-working-through-the-harness/02-standing-up-an-organization.md) and
start there. The catalogue tells you what exists; part 02 is the order to do it
in.

---

_Next: [Part 09 — The governance architecture](../09-the-governance-architecture/README.md)_
