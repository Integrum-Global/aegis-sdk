# 08.6 — Knowledge and data

This chapter enumerates **what the organisation knows** and **where that came
from**. Knowledge in Aegis is not a document store bolted onto an agent platform
— it is a governed asset with a classification, a review lifecycle, a sharing
policy, and a lineage, and every one of those is a first-class surface.

The reason it works this way is the one the rest of the catalogue keeps
returning to: an agent's clearance decides what it may read, and a knowledge item
without a classification cannot be cleared for. **Classification is what makes
knowledge reachable, not what restricts it** — an unclassified item is not
maximally available, it is unresolvable.

Four distinct things live here, and they are easy to run together:

| object             | what it is                                       |
| ------------------ | ------------------------------------------------ |
| **Knowledge item** | A governed piece of what the organisation knows  |
| **Connector**      | A live link to an external data system           |
| **Data source**    | A registered, described source of data           |
| **Workspace**      | A collaborative container for documents and work |

[02.3](../02-working-through-the-harness/03-envelopes-clearance-and-knowledge.md)
teaches the clearance model this chapter's classification surface serves.

## Knowledge items — the core lifecycle

A knowledge item moves through a review lifecycle before it is available, and
every transition is recorded.

| state                 | meaning                                            |
| --------------------- | -------------------------------------------------- |
| **Draft**             | Authored, not yet submitted                        |
| **Under review**      | Submitted; a reviewer is assigned                  |
| **Changes requested** | Returned to the author                             |
| **Approved**          | Reviewed and accepted, not yet published           |
| **Published**         | Available to anyone cleared for it                 |
| **Archived**          | Withdrawn from availability, retained for evidence |

| capability                             | what it does                                        |
| -------------------------------------- | --------------------------------------------------- |
| **Create / update / delete**           | Standard record lifecycle                           |
| **List / get / search**                | Enumerate, address and search                       |
| **Submit for review**                  | Move it into the review lifecycle                   |
| **Assign reviewer**                    | Name who decides                                    |
| **Approve / reject / request changes** | The reviewer's three verdicts                       |
| **Publish**                            | Make it available                                   |
| **Create version**                     | Snapshot the current content                        |
| **Create revision**                    | Start a new editable revision from a published item |
| **Archive / unarchive**                | Withdraw or restore availability                    |
| **Review queue**                       | Everything awaiting review                          |

Entry points: `sdk:aegis_sdk.standup.knowledge.KnowledgeModule` for the simple
create/get/publish/list path, and
`sdk:aegis_sdk.modules.knowledge_govern.KnowledgeGovernModule` for the full
governance surface.

Operations: `api:POST /api/v1/knowledge` · `api:GET /api/v1/knowledge` ·
`api:GET /api/v1/knowledge/{id}` · `api:PUT /api/v1/knowledge/{id}` ·
`api:DELETE /api/v1/knowledge/{id}` · `api:GET /api/v1/knowledge/search` ·
`api:POST /api/v1/knowledge/{id}/submit` ·
`api:POST /api/v1/knowledge/{id}/assign-reviewer` ·
`api:POST /api/v1/knowledge/{id}/approve` ·
`api:POST /api/v1/knowledge/{id}/reject` ·
`api:POST /api/v1/knowledge/{id}/request-changes` ·
`api:POST /api/v1/knowledge/{id}/publish` ·
`api:POST /api/v1/knowledge/{id}/version` ·
`api:POST /api/v1/knowledge/{id}/create-revision` ·
`api:POST /api/v1/knowledge/{id}/archive` ·
`api:POST /api/v1/knowledge/{id}/unarchive` ·
`api:GET /api/v1/knowledge-reviews`

```python
item = await client.knowledge.create(
    title="Q3 close procedure",
    content=procedure_text,
    classification="confidential",
    category_id=finance_category_id,
)
await client.knowledge_govern.submit_for_review(knowledge_id=item["id"])
await client.knowledge_govern.assign_reviewer(
    knowledge_id=item["id"],
    reviewer_id=controller_user_id,
)
await client.knowledge_govern.approve(knowledge_id=item["id"])
await client.knowledge.publish(knowledge_id=item["id"])
```

> ⛔ **Approved is not published.** Approval records a reviewer's verdict;
> publication makes the item available. An approved-but-unpublished item is
> invisible to every agent that should be able to read it, and appears correct in
> every listing — the review shows complete, the content is there, and no agent
> can reach it.

**Archive rather than delete when an item was superseded.** Deleting removes the
record that the organisation ever held that knowledge, which is exactly the
question an audit asks. Archiving withdraws availability and keeps the evidence.

## Knowledge categories

The taxonomy items are filed under. Categories are how knowledge is scoped to
parts of the organisation.

| capability                   | what it does         |
| ---------------------------- | -------------------- |
| **Create / update / delete** | Manage the taxonomy  |
| **List**                     | Enumerate categories |

Entry point: `sdk:aegis_sdk.modules.knowledge_govern.KnowledgeGovernModule`.

Operations: `api:GET /api/v1/knowledge-categories` ·
`api:POST /api/v1/knowledge-categories` ·
`api:PUT /api/v1/knowledge-categories/{id}` ·
`api:DELETE /api/v1/knowledge-categories/{id}`

## Knowledge share policies

Who may see what, expressed as a policy rather than per-item permissions. Share
policies carry their own review cadence.

| capability                   | what it does                         |
| ---------------------------- | ------------------------------------ |
| **Create / update / delete** | Author a sharing policy              |
| **List / get**               | Enumerate them                       |
| **Due for review**           | Policies whose review has come round |
| **Suspend / reactivate**     | Take a policy out of force and back  |

Entry point: `sdk:aegis_sdk.modules.knowledge_govern.KnowledgeGovernModule`.

Operations: `api:GET /api/v1/knowledge-share-policies` ·
`api:POST /api/v1/knowledge-share-policies` ·
`api:GET /api/v1/knowledge-share-policies/{id}` ·
`api:PUT /api/v1/knowledge-share-policies/{id}` ·
`api:DELETE /api/v1/knowledge-share-policies/{id}` ·
`api:GET /api/v1/knowledge-share-policies/due-for-review` ·
`api:POST /api/v1/knowledge-share-policies/{id}/suspend` ·
`api:POST /api/v1/knowledge-share-policies/{id}/reactivate`

```python
due = await client.knowledge_govern.list_share_policies_due_for_review()
```

**`due-for-review` is the query that keeps sharing honest.** A share policy
written for a project that ended two years ago is still granting access, and
nothing surfaces that except this call.

## Content reviews and templates

A general review workflow over content, distinct from the knowledge lifecycle
above — and templates to author consistently against.

| capability                | reviews | templates |
| ------------------------- | ------- | --------- |
| Create / list / get       | yes     | yes       |
| Update / delete           | delete  | yes       |
| Submit                    | yes     | —         |
| Approve / reject / reopen | yes     | —         |

Entry point: `sdk:aegis_sdk.modules.knowledge_govern.KnowledgeGovernModule`.

Operations: `api:GET /api/v1/content-reviews` ·
`api:POST /api/v1/content-reviews` · `api:GET /api/v1/content-reviews/{id}` ·
`api:DELETE /api/v1/content-reviews/{id}` ·
`api:POST /api/v1/content-reviews/{id}/submit` ·
`api:POST /api/v1/content-reviews/{id}/approve` ·
`api:POST /api/v1/content-reviews/{id}/reject` ·
`api:POST /api/v1/content-reviews/{id}/reopen` ·
`api:GET /api/v1/content-templates` ·
`api:POST /api/v1/content-templates` ·
`api:GET /api/v1/content-templates/{id}` ·
`api:PUT /api/v1/content-templates/{id}` ·
`api:DELETE /api/v1/content-templates/{id}`

## Connectors — live links to external systems

A connector is a configured, testable link to a system outside Aegis. Agents
query through connectors rather than holding credentials themselves.

| capability                   | what it does                                       |
| ---------------------------- | -------------------------------------------------- |
| **Create / update / delete** | Manage a connector                                 |
| **List / get / types**       | Enumerate connectors and the kinds available       |
| **Test**                     | Confirm it connects, before anything depends on it |
| **Validate**                 | Check the configuration is well-formed             |
| **Health**                   | Whether it is working now                          |
| **Schema**                   | What the far side exposes                          |
| **Metadata**                 | Descriptive information about the source           |
| **Query**                    | Read through it                                    |
| **Attach / detach**          | Wire it to an agent, or unwire it                  |
| **Instances**                | Per-use configured instances of a connector        |

Entry point: `sdk:aegis_sdk.modules.connectors.ConnectorsModule`.

Operations: `api:POST /api/v1/connectors` · `api:GET /api/v1/connectors` ·
`api:GET /api/v1/connectors/{id}` · `api:PUT /api/v1/connectors/{id}` ·
`api:DELETE /api/v1/connectors/{id}` · `api:GET /api/v1/connectors/types` ·
`api:POST /api/v1/connectors/{id}/test` ·
`api:POST /api/v1/connectors/{id}/validate` ·
`api:GET /api/v1/connectors/{id}/health` ·
`api:GET /api/v1/connectors/{id}/schema` ·
`api:GET /api/v1/connectors/{id}/metadata` ·
`api:POST /api/v1/connectors/{id}/query` ·
`api:POST /api/v1/connectors/{id}/attach` ·
`api:DELETE /api/v1/connectors/instances/{id}`

```python
connector = await client.connectors.create(
    name="general-ledger",
    connector_type="postgres",
    config={"host": "ledger.internal", "database": "gl"},
    credential_id=stored_credential_id,
)
check = await client.connectors.test(connector_id=connector["id"])
await client.connectors.attach(connector_id=connector["id"], agent_id=agent["id"])
```

> ⚠ **`validate` and `test` answer different questions.** Validation checks the
> configuration is well-formed without touching the far side; test actually
> connects. A connector that validates and does not test is misconfigured in a
> way that only shows up when an agent queries it mid-objective — and the failure
> surfaces there, attributed to the agent rather than to the connector.

**Credentials belong in the credential store, not in connector config.**
[08.8](08-commercial-and-extensibility.md) catalogues that surface; referencing a
stored credential by id keeps it rotatable without touching every connector that
uses it.

## Data source registry

Registered, described sources — the catalogue of where data comes from, distinct
from the live connectors that read it.

| capability                   | what it does                 |
| ---------------------------- | ---------------------------- |
| **Create / update / delete** | Manage a registration        |
| **List / get**               | Enumerate registered sources |

Entry point: `sdk:aegis_sdk.modules.knowledge_govern.KnowledgeGovernModule`.

Operations: `api:GET /api/v1/data-source-registry` ·
`api:POST /api/v1/data-source-registry` ·
`api:GET /api/v1/data-source-registry/{id}` ·
`api:PUT /api/v1/data-source-registry/{id}` ·
`api:DELETE /api/v1/data-source-registry/{id}`

## Data governance — classification, policy, consent

The controls over data as data, independent of the knowledge items that carry it.

### Classifications

The levels data is labelled with, and what handling each requires.

| capability                   | what it does                               |
| ---------------------------- | ------------------------------------------ |
| **Create / update / delete** | Define a classification                    |
| **List / get**               | Enumerate them, with handling requirements |

Operations: `api:GET /api/v1/data-governance/classifications` ·
`api:POST /api/v1/data-governance/classifications` ·
`api:GET /api/v1/data-governance/classifications/{id}` ·
`api:PUT /api/v1/data-governance/classifications/{id}` ·
`api:DELETE /api/v1/data-governance/classifications/{id}`

### Data policies

| capability                   | what it does                                  |
| ---------------------------- | --------------------------------------------- |
| **Create / update / delete** | Author a data policy                          |
| **List / get**               | Enumerate them                                |
| **Evaluate**                 | Ask what the policy set decides for an access |

Operations: `api:GET /api/v1/data-governance/policies` ·
`api:POST /api/v1/data-governance/policies` ·
`api:GET /api/v1/data-governance/policies/{id}` ·
`api:PUT /api/v1/data-governance/policies/{id}` ·
`api:DELETE /api/v1/data-governance/policies/{id}` ·
`api:POST /api/v1/data-governance/policies/evaluate`

### Consent

Where data subjects have a say, consent is a tracked record with a withdrawal
path — the GDPR-shaped surface.

| capability     | what it does                           |
| -------------- | -------------------------------------- |
| **Record**     | Capture a consent                      |
| **List / get** | Enumerate consents                     |
| **Check**      | Ask whether consent covers a given use |
| **Withdraw**   | Revoke a consent                       |

Operations: `api:GET /api/v1/data-governance/consents` ·
`api:POST /api/v1/data-governance/consents` ·
`api:GET /api/v1/data-governance/consents/{id}` ·
`api:POST /api/v1/data-governance/consents/check` ·
`api:POST /api/v1/data-governance/consents/{id}/withdraw`

### Retention

| capability          | what it does                 |
| ------------------- | ---------------------------- |
| **Create / update** | Define how long data is kept |
| **Get**             | Read one retention rule      |

Operations: `api:POST /api/v1/data-governance/retention` ·
`api:GET /api/v1/data-governance/retention/{id}` ·
`api:PUT /api/v1/data-governance/retention/{id}`

Compliance-driven retention policies — the ones a framework requires, with an
execution surface — are catalogued in
[08.7](07-evidence-and-operations.md).

Entry point for all four: `sdk:aegis_sdk.modules.governance.GovernanceModule`.

```python
decision = await client.governance.evaluate_access(
    principal_id=agent["id"],
    resource_id=dataset_id,
    action="read",
)
covered = await client.governance.check_consent(
    subject_id=subject_id,
    purpose="analytics",
)
```

**Check consent before the use, not after the complaint.** `consents/check` is
cheap and the alternative is discovering the gap during a subject access request.

## Lineage — where data came from and what depends on it

Two lineage surfaces, serving different questions.

**Data governance lineage** is a graph of nodes and edges you build explicitly:
this dataset derived from those inputs.

| capability             | what it does                         |
| ---------------------- | ------------------------------------ |
| **Create node / edge** | Record a data asset and a derivation |
| **Graph**              | Read the whole graph                 |
| **Get node**           | One node in full                     |
| **Upstream**           | Everything this derived from         |
| **Downstream**         | Everything derived from this         |
| **Impact**             | What changing this would affect      |

Operations: `api:POST /api/v1/data-governance/lineage/nodes` ·
`api:POST /api/v1/data-governance/lineage/edges` ·
`api:GET /api/v1/data-governance/lineage/graph` ·
`api:GET /api/v1/data-governance/lineage/nodes/{id}` ·
`api:GET /api/v1/data-governance/lineage/nodes/{id}/upstream` ·
`api:GET /api/v1/data-governance/lineage/nodes/{id}/downstream` ·
`api:GET /api/v1/data-governance/lineage/nodes/{id}/impact`

Entry points: `sdk:aegis_sdk.modules.governance.GovernanceModule` and
`sdk:aegis_sdk.dataflow.graph.LineageGraphModule`.

**Invocation lineage** is recorded for you: which agent invoked what, with what
data, on whose behalf.

| capability      | what it does                                      |
| --------------- | ------------------------------------------------- |
| **List / get**  | Enumerate invocation lineage records              |
| **Graph**       | The invocation graph                              |
| **Export**      | Extract it for external analysis                  |
| **Redact user** | Remove one subject's data from the lineage record |

Entry point: `sdk:aegis_sdk.dataflow.lineage.InvocationLineageModule`.

Operations: `api:GET /api/v1/lineage` · `api:GET /api/v1/lineage/{id}` ·
`api:GET /api/v1/lineage/graph` · `api:GET /api/v1/lineage/export` ·
`api:DELETE /api/v1/lineage/user/{user_id}`

```python
upstream = await client.dataflow.graph.upstream(node_id=report_node_id)
impact = await client.governance.get_lineage_impact(node_id=source_node_id)

records = await client.dataflow.lineage.list(agent_id=agent["id"], limit=100)
await client.dataflow.lineage.redact_user(user_id=erasure_request_user_id)
```

> ⛔ **`api:DELETE /api/v1/lineage/user/{user_id}` is the erasure surface, and it
> is not reversible.** It exists to satisfy a right-to-erasure request. Running
> it removes that subject from the lineage record permanently — confirm the
> request is genuine before calling it, because there is no restore.

**Impact analysis before a schema change is the cheapest version of this
chapter.** `lineage/nodes/{id}/impact` answers what breaks, and the alternative
is finding out from the downstream consumer.

## Datasets

Named, addressable data collections — the unit agents and MCP bindings consume.

| capability                   | what it does     |
| ---------------------------- | ---------------- |
| **Create / update / delete** | Manage a dataset |
| **List / get**               | Enumerate them   |

Entry point: `sdk:aegis_sdk.modules.mcp.McpModule`.

Operations: `api:GET /api/v1/datasets` · `api:POST /api/v1/datasets` ·
`api:GET /api/v1/datasets/{id}` · `api:PUT /api/v1/datasets/{id}` ·
`api:DELETE /api/v1/datasets/{id}`

## Workspaces

Collaborative containers: members, work units, documents and messages in one
governed scope. A workspace is also a bridge scope — see
[08.5](05-governance-and-trust.md).

| capability                          | what it does                             |
| ----------------------------------- | ---------------------------------------- |
| **Create / update / delete**        | Standard lifecycle                       |
| **List / get**                      | Enumerate and address workspaces         |
| **Archive / restore**               | Withdraw from active use, and bring back |
| **Add / update / remove member**    | Manage membership and roles within it    |
| **Add / remove work unit**          | Attach executable work to the workspace  |
| **Attach / list / detach document** | Manage its documents                     |

Entry point: `sdk:aegis_sdk.modules.workspaces.WorkspacesModule`.

Operations: `api:POST /api/v1/workspaces` · `api:GET /api/v1/workspaces` ·
`api:GET /api/v1/workspaces/{id}` · `api:PATCH /api/v1/workspaces/{id}` ·
`api:DELETE /api/v1/workspaces/{id}` ·
`api:POST /api/v1/workspaces/{id}/archive` ·
`api:POST /api/v1/workspaces/{id}/restore` ·
`api:POST /api/v1/workspaces/{id}/members` ·
`api:PATCH /api/v1/workspaces/{id}/members/{member_id}` ·
`api:DELETE /api/v1/workspaces/{id}/members/{member_id}` ·
`api:POST /api/v1/workspaces/{id}/work-units` ·
`api:DELETE /api/v1/workspaces/{id}/work-units/{work_unit_id}` ·
`api:POST /api/v1/workspaces/{id}/documents` ·
`api:GET /api/v1/workspaces/{id}/documents` ·
`api:DELETE /api/v1/workspaces/{id}/documents/{document_id}`

```python
ws = await client.workspaces.create(
    name="Q3 close",
    description="Working space for the Q3 close objective.",
)
await client.workspaces.add_member(workspace_id=ws["id"], user_id=controller_id)
await client.workspaces.add_work_unit(workspace_id=ws["id"], work_unit_id=unit["id"])
```

**Archiving a workspace does not end its bridges.** A scoped bridge created for a
workspace outlives the workspace's archival unless it is completed or expired —
check `api:GET /api/v1/scoped-bridges/for-workspace/{workspace_id}` as part of
closing one down, or the channel stays open after the reason for it is gone.

## How the pieces connect

```
  connector ──► data source registry ──► dataset
      │                                     │
      │                                     ▼
      │                              agent reads
      ▼                                     │
  lineage node ◄────── derivation ──────────┘
      │
      ▼
  impact / upstream / downstream          ← "what breaks if I change this?"

  knowledge item ──► classification ──► clearance check ──► agent may read
        │
        └──► review lifecycle ──► published ──► share policy ──► who else sees it
```

Read it as: the top half is **data in motion** — where it comes from, what
consumes it, what derives from what. The bottom half is **knowledge at rest** —
what the organisation has written down, and who may read it. They meet at the
clearance check, which is the one gate both paths pass through, and which is
catalogued in [08.5](05-governance-and-trust.md).

## Summary — what this chapter covered

| area                 | entry point                                                  | scale         |
| -------------------- | ------------------------------------------------------------ | ------------- |
| Knowledge items      | `standup.knowledge` · `modules.knowledge_govern`             | 17 operations |
| Knowledge categories | `modules.knowledge_govern`                                   | 4 operations  |
| Share policies       | `modules.knowledge_govern`                                   | 8 operations  |
| Content reviews      | `modules.knowledge_govern`                                   | 8 operations  |
| Content templates    | `modules.knowledge_govern`                                   | 5 operations  |
| Connectors           | `modules.connectors`                                         | 14 operations |
| Data source registry | `modules.knowledge_govern`                                   | 5 operations  |
| Data governance      | `modules.governance`                                         | 26 operations |
| Lineage              | `dataflow.lineage` · `dataflow.graph` · `modules.governance` | 12 operations |
| Datasets             | `modules.mcp`                                                | 5 operations  |
| Workspaces           | `modules.workspaces`                                         | 15 operations |

---

_Next: [08.7 — Evidence and operations](07-evidence-and-operations.md)_
