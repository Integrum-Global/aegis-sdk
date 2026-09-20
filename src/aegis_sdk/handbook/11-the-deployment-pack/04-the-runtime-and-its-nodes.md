# 11.4 — The runtime and its nodes

Aegis executes work as **workflows**, and a workflow is a graph of **nodes**.
Every node is a typed unit the runtime knows how to run: call an endpoint, query
a database, invoke a model, branch, merge, encrypt, alert. The set of node types
the runtime recognises is the deployment's capability surface — it is the honest
answer to "what can this actually do?", and it is the reach the rest of this
part exists to keep running.

The runtime arrives as a **published package**, not as source. There is nothing
to clone and nothing to build: you install a version, the version determines the
catalogue, and the catalogue is introspectable from the package itself. That
last property is the important one, because it means you never have to trust a
list — including this one.

**The one idea to carry out: the node catalogue is DERIVED from your own
install, and the derivation is two lines.**

## The runtime package and its version constraint

| Fact                   | Value                                                       |
| ---------------------- | ----------------------------------------------------------- |
| **Package**            | `kailash-enterprise`                                        |
| **Version constraint** | `>=4.47.0,<4.48.0`                                          |
| **Import name**        | `kailash`                                                   |
| **Distribution shape** | A single compiled extension, `abi3` from Python 3.10        |
| **Interpreters**       | Wheels for CPython 3.10 through 3.14                        |
| **Typing**             | Ships `py.typed` with stub files, so a type checker sees it |

Pin to a minor range rather than a floating latest. **A runtime version change
is a capability change**, and it is the one dependency in this pack whose
upgrade can alter what an existing workflow does rather than merely what it can
do — which is why the upper bound is part of the pin and not decoration.

The package carries sub-namespaces for the surfaces built on it. Fifteen import
with the base install — `dataflow`, `nexus`, `kaizen`, `mcp`, `a2a`, `pact`,
`enterprise`, `events`, `infra`, `delegate`, `trust_plane`, `nodes`, `workflow`,
`runtime` and `distill`. The node catalogue below is reached from the top level.

**One does not: `ml` requires the `ml` extra.** Install it only if you need that
surface:

```bash
pip install 'kailash-enterprise[ml]'
```

Without the extra, importing `kailash.ml` raises rather than resolving, and the
error names the install command — so treat it as a dependency you choose, not as
a namespace that is missing.

## Derive the catalogue yourself — the method

Everything in this chapter came from this, and you should re-run it against your
own install rather than reading the table below as standing fact:

```bash
# The total, and the full list, from the installed distribution
python -c "from kailash import NodeRegistry; t=sorted(NodeRegistry().list_types()); print(len(t)); print('\n'.join(t))"
```

It needs no database, no configuration and no network. `NodeRegistry()`
constructs a registry populated with every built-in type; `list_types()` returns
their names exactly as you write them in a workflow.

```bash
# Does this install recognise a specific type? (the check to run before you rely on one)
python -c "from kailash import NodeRegistry; print(NodeRegistry().has_type('HTTPRequestNode'))"
```

**The registry exposes exactly three public methods** — `pkg:kailash.NodeRegistry.list_types`,
`pkg:kailash.NodeRegistry.has_type` and `pkg:kailash.NodeRegistry.register_callback`. There is no metadata accessor: you can
enumerate node-type **strings** from the package, and you cannot introspect
descriptions, categories or parameter schemas from it.

That is why the catalogue below is worth having — **it supplies what the
registry cannot.** The counts and the names are yours to re-derive; the grouping
and the descriptions are the part the package does not carry.

**Derived on version 4.47: 138 built-in node types.** That number is the
denominator for everything below, and the categories that follow sum to exactly
it. If your install reports a different total, your install is the authority.

## The catalogue, by category

Twenty categories, disjoint, summing to 138.

| Category                                                          |   Count |
| ----------------------------------------------------------------- | ------: |
| [Core workflow and control flow](#core-workflow-and-control-flow) |      10 |
| [Code execution](#code-execution)                                 |       4 |
| [Data transform](#data-transform)                                 |      12 |
| [Files and documents](#files-and-documents)                       |       7 |
| [HTTP and API](#http-and-api)                                     |       7 |
| [Databases and SQL](#databases-and-sql)                           |       4 |
| [Vector and retrieval](#vector-and-retrieval)                     |       9 |
| [AI and multimodal](#ai-and-multimodal)                           |       8 |
| [Cache](#cache)                                                   |       3 |
| [Redis](#redis)                                                   |       3 |
| [Kafka and streaming](#kafka-and-streaming)                       |       6 |
| [Authentication and identity](#authentication-and-identity)       |       9 |
| [Authorization and governance](#authorization-and-governance)     |       7 |
| [Security and data protection](#security-and-data-protection)     |      13 |
| [Monitoring and diagnostics](#monitoring-and-diagnostics)         |      13 |
| [Alerts](#alerts)                                                 |       6 |
| [Distributed transactions](#distributed-transactions)             |       5 |
| [Edge and distributed placement](#edge-and-distributed-placement) |       6 |
| [Platform and infrastructure](#platform-and-infrastructure)       |       4 |
| [MCP and tool integration](#mcp-and-tool-integration)             |       2 |
| **Total**                                                         | **138** |

### Core workflow and control flow

| Type                 | What it is for                             |
| -------------------- | ------------------------------------------ |
| `ConditionalNode`    | Branch on a predicate                      |
| `SwitchNode`         | Multi-way branch on a value                |
| `MergeNode`          | Join several branches back into one        |
| `LoopNode`           | Iterate over a collection                  |
| `ParallelNode`       | Fan out independent work                   |
| `WaitNode`           | Pause for a duration or a condition        |
| `RetryNode`          | Re-attempt a failing step under a policy   |
| `ErrorHandlerNode`   | Catch and route a failure                  |
| `NoOpNode`           | Do nothing — a placeholder or a join point |
| `BatchProcessorNode` | Process a collection in bounded batches    |

### Code execution

| Type                 | What it is for                |
| -------------------- | ----------------------------- |
| `EmbeddedPythonNode` | Run inline Python             |
| `EmbeddedJSNode`     | Run inline JavaScript         |
| `SubprocessNode`     | Run an external process       |
| `CodeValidationNode` | Check code before it executes |

### Data transform

| Type                   | What it is for                            |
| ---------------------- | ----------------------------------------- |
| `DataMapperNode`       | Reshape a record between two schemas      |
| `JSONTransformNode`    | Transform JSON structurally               |
| `TextTransformNode`    | Transform free text                       |
| `StringOperationsNode` | String manipulation primitives            |
| `MathOperationsNode`   | Arithmetic and numeric primitives         |
| `ArrayOperationsNode`  | Collection manipulation primitives        |
| `FormatConverterNode`  | Convert between serialisation formats     |
| `FilterNode`           | Drop records failing a predicate          |
| `SchemaValidatorNode`  | Reject records that do not match a schema |
| `TextSplitterNode`     | Chunk text for embedding or processing    |
| `XMLParserNode`        | Parse XML into structured data            |
| `CSVProcessorNode`     | Read and write delimited data             |

### Files and documents

| Type                  | What it is for                               |
| --------------------- | -------------------------------------------- |
| `FileReaderNode`      | Read a file                                  |
| `FileWriterNode`      | Write a file                                 |
| `ExcelReaderNode`     | Read a spreadsheet                           |
| `PDFReaderNode`       | Extract content from a PDF                   |
| `DocumentLoaderNode`  | Load a document into the processing pipeline |
| `DocumentStoreNode`   | Persist a document                           |
| `DirectoryReaderNode` | Enumerate a directory                        |

### HTTP and API

| Type                 | What it is for                        |
| -------------------- | ------------------------------------- |
| `HTTPRequestNode`    | Make one HTTP request                 |
| `HTTPBatchNode`      | Make many, with concurrency control   |
| `GraphQLNode`        | Issue a GraphQL query or mutation     |
| `RateLimitedAPINode` | Call an API under a rate-limit policy |
| `WebhookNode`        | Receive or emit a webhook             |
| `WebSocketNode`      | Hold a websocket connection           |
| `WebScrapingNode`    | Fetch and extract from a web page     |

### Databases and SQL

| Type                     | What it is for                        |
| ------------------------ | ------------------------------------- |
| `SQLQueryNode`           | Execute a query                       |
| `SQLTransactionNode`     | Group statements into one transaction |
| `DatabaseConnectionNode` | Establish and hold a connection       |
| `GraphDatabaseNode`      | Query a graph store                   |

### Vector and retrieval

| Type                   | What it is for                         |
| ---------------------- | -------------------------------------- |
| `VectorSearchNode`     | Similarity search                      |
| `VectorQueryNode`      | Query a vector collection              |
| `VectorUpsertNode`     | Insert or update vectors               |
| `VectorDeleteNode`     | Remove vectors                         |
| `EmbeddingNode`        | Produce embeddings                     |
| `EmbeddingStoreNode`   | Persist embeddings                     |
| `RerankNode`           | Re-order candidates by relevance       |
| `RAGPipelineNode`      | Retrieve-then-generate, as one step    |
| `ContextAssemblerNode` | Assemble retrieved context for a model |

### AI and multimodal

| Type                  | What it is for        |
| --------------------- | --------------------- |
| `LLMNode`             | Call a language model |
| `SummarizationNode`   | Summarise text        |
| `SentimentNode`       | Score sentiment       |
| `ClassificationNode`  | Classify into labels  |
| `VisionNode`          | Interpret an image    |
| `AudioNode`           | Process audio         |
| `TextToSpeechNode`    | Synthesise speech     |
| `ImageGenerationNode` | Generate an image     |

### Cache

| Type                  | What it is for              |
| --------------------- | --------------------------- |
| `CacheGetNode`        | Read from cache             |
| `CacheSetNode`        | Write to cache              |
| `CacheInvalidateNode` | Evict an entry or a pattern |

### Redis

| Type               | What it is for               |
| ------------------ | ---------------------------- |
| `RedisCommandNode` | Issue a Redis command        |
| `RedisPubSubNode`  | Publish or subscribe         |
| `RedisStreamNode`  | Read or write a Redis stream |

### Kafka and streaming

| Type                  | What it is for                |
| --------------------- | ----------------------------- |
| `KafkaProducerNode`   | Produce to a topic            |
| `KafkaConsumerNode`   | Consume from a topic          |
| `KafkaStreamNode`     | Stream-process a topic        |
| `StreamProducerNode`  | Produce to a generic stream   |
| `StreamConsumerNode`  | Consume from a generic stream |
| `StreamTransformNode` | Transform a stream in flight  |

> ⚠ **`TokenGenerationNode` resolves to the authentication implementation.** Two
> distinct implementations carry that name and the registry is first-wins, so
> the auth one is what a workflow gets. Read it as the auth node wherever it
> appears, and name the category you mean when you write about it.

### Authentication and identity

| Type                       | What it is for                           |
| -------------------------- | ---------------------------------------- |
| `JWTAuthNode`              | Issue or verify a JWT                    |
| `OAuth2Node`               | Drive an OAuth2 exchange                 |
| `APIKeyAuthNode`           | Authenticate by API key                  |
| `SSONode`                  | Single sign-on integration               |
| `MFANode`                  | Second-factor challenge                  |
| `AuthFlowNode`             | Compose a multi-step authentication flow |
| `SessionManagerNode`       | Create, read and end sessions            |
| `TokenGenerationNode`      | Mint a token                             |
| `DirectoryIntegrationNode` | Read from a directory service            |

### Authorization and governance

| Type                          | What it is for                  |
| ----------------------------- | ------------------------------- |
| `ABACPermissionEvaluatorNode` | Evaluate attribute-based access |
| `UserManagementNode`          | Create and modify users         |
| `TenantAssignmentNode`        | Place a principal in a tenant   |
| `ComplianceCheckNode`         | Assert a compliance control     |
| `GDPRComplianceNode`          | Data-subject rights operations  |
| `DataRetentionPolicyNode`     | Apply a retention rule          |
| `DataLineageNode`             | Record where data came from     |

### Security and data protection

| Type                        | What it is for                          |
| --------------------------- | --------------------------------------- |
| `EncryptionNode`            | Encrypt or decrypt                      |
| `HashingNode`               | Hash a value                            |
| `CertificateNode`           | Handle a certificate                    |
| `SignatureVerificationNode` | Verify a signature                      |
| `CredentialValidatorNode`   | Validate a credential's shape and state |
| `SecretRotationNode`        | Rotate a secret                         |
| `DataMaskingNode`           | Mask sensitive fields                   |
| `InputSanitizationNode`     | Sanitise untrusted input                |
| `OutputEncodingNode`        | Encode output for a sink                |
| `ThreatDetectionNode`       | Detect a known threat pattern           |
| `SecurityEventNode`         | Emit a security event                   |
| `BehaviorAnalysisNode`      | Score behaviour against a baseline      |
| `EnterpriseAuditLoggerNode` | Write an audit record                   |

### Monitoring and diagnostics

| Type                        | What it is for               |
| --------------------------- | ---------------------------- |
| `HealthCheckNode`           | Probe a dependency           |
| `MetricsCollectorNode`      | Gather metrics               |
| `LogNode`                   | Emit a log line              |
| `LogProcessorNode`          | Process logs in a pipeline   |
| `PerformanceAnomalyNode`    | Detect a performance outlier |
| `PerformanceBenchmarkNode`  | Measure a benchmark          |
| `DeadlockDetectorNode`      | Detect a lock cycle          |
| `RaceConditionDetectorNode` | Detect a concurrency hazard  |
| `TransactionMonitorNode`    | Watch transaction behaviour  |
| `ConnectionDashboardNode`   | Report connection-pool state |
| `ResourceAnalyzerNode`      | Analyse resource consumption |
| `ResourceOptimizerNode`     | Recommend a resource change  |
| `ResourceScalerNode`        | Apply a scaling decision     |

### Alerts

| Type                 | What it is for            |
| -------------------- | ------------------------- |
| `AlertNode`          | Emit a generic alert      |
| `EmailAlertNode`     | Alert by email            |
| `SlackAlertNode`     | Alert to Slack            |
| `TeamsAlertNode`     | Alert to Teams            |
| `DiscordAlertNode`   | Alert to Discord          |
| `PagerDutyAlertNode` | Page an on-call responder |

### Distributed transactions

| Type                                | What it is for                                      |
| ----------------------------------- | --------------------------------------------------- |
| `DistributedTransactionManagerNode` | Choose and drive a distributed-transaction strategy |
| `TwoPhaseCommitCoordinatorNode`     | Two-phase commit, for strong consistency            |
| `SagaCoordinatorNode`               | Saga orchestration, for availability                |
| `SagaStepNode`                      | One saga step and its compensation                  |
| `TransactionContextNode`            | Carry transaction context across steps              |

### Edge and distributed placement

| Type                   | What it is for                    |
| ---------------------- | --------------------------------- |
| `EdgeDataNode`         | Read or write at an edge location |
| `EdgeStateMachineNode` | Run a state machine at the edge   |
| `EdgeCoordinationNode` | Coordinate across edge locations  |
| `EdgeMigrationNode`    | Move work between locations       |
| `EdgeMonitoringNode`   | Observe an edge location          |
| `EdgeWarmingNode`      | Pre-warm an edge location         |

### Platform and infrastructure

| Type             | What it is for                    |
| ---------------- | --------------------------------- |
| `KubernetesNode` | Interact with a cluster           |
| `DockerNode`     | Interact with a container runtime |
| `CloudNode`      | Call a cloud provider surface     |
| `PlatformNode`   | Platform-level operations         |

### MCP and tool integration

| Type                        | What it is for                         |
| --------------------------- | -------------------------------------- |
| `MCPServiceDiscoveryNode`   | Discover available tool servers        |
| `EnterpriseMCPExecutorNode` | Execute a tool through a governed path |

## Model-generated nodes — eleven per registered model

The 138 above are built in. **Registering a data model generates eleven more,
for that model alone**, so the live registry is larger than the built-in
catalogue and grows with your schema.

The naming rule is `<Verb><ModelName>` — verb first, model name exactly as
registered. Derived by registering one model named `Invoice` against a clean
registry and diffing the type list:

| Verb         | Generated type      | Operation                      |
| ------------ | ------------------- | ------------------------------ |
| `Create`     | `CreateInvoice`     | Insert one row                 |
| `Read`       | `ReadInvoice`       | Fetch one row by key           |
| `Update`     | `UpdateInvoice`     | Modify one row                 |
| `Delete`     | `DeleteInvoice`     | Remove one row                 |
| `List`       | `ListInvoice`       | Fetch many, filtered and paged |
| `Count`      | `CountInvoice`      | Count matching rows            |
| `Upsert`     | `UpsertInvoice`     | Insert or update one row       |
| `BulkCreate` | `BulkCreateInvoice` | Insert many                    |
| `BulkUpdate` | `BulkUpdateInvoice` | Modify many                    |
| `BulkDelete` | `BulkDeleteInvoice` | Remove many                    |
| `BulkUpsert` | `BulkUpsertInvoice` | Insert or update many          |

Derive it for your own models the same way — register, then diff:

```bash
# Before-and-after around your own registration; the difference is the generated set
python -c "from kailash import NodeRegistry; print(len(NodeRegistry().list_types()))"
```

> ⛔ **The verb comes FIRST, and there is no `Node` suffix.** A workflow naming
> `InvoiceReadNode` or `ReadInvoiceNode` fails at build time with an
> unknown-node-type error, not at run time — which is the good outcome, but the
> message names the type you asked for rather than the type you meant, so it
> reads as a missing capability rather than a spelling.

**Registration is all-or-nothing, and pre-checked.** The eleven names are
validated against the registry before any of them installs, so a collision with
an existing type leaves the registry **byte-unchanged** rather than half-wired.

That is the property to design around: a model whose name collides gives you a
clean refusal and a registry you can still reason about, instead of a partial
set where six verbs work and five do not. **A half-registered model would be the
expensive failure** — the workflows naming the installed verbs would run, and
the ones naming the rest would fail at build, from what looks like the same
change.

## The execution contract

Four objects, in this order. Verified against the installed distribution.

| Step | Object                     | Call                                                                              |
| ---- | -------------------------- | --------------------------------------------------------------------------------- |
| 1    | `pkg:kailash.NodeRegistry` | `NodeRegistry()` — populated with every built-in type                             |
| 2    | `WorkflowBuilder`          | `add_node(type_name, node_id, config)`, then `connect(src, src_out, tgt, tgt_in)` |
| 3    | build                      | `builder.build(registry)` → a `Workflow`                                          |
| 4    | `pkg:kailash.Runtime`      | `Runtime(registry, config)`, then `execute(workflow, inputs)`                     |

`execute` returns a dict with three keys — `results`, `run_id` and `metadata` —
and `execute_async` is the awaitable form of the same call. `RuntimeConfig`
carries the tuning: `debug`, `max_concurrent_nodes`, `enable_cycles`,
`node_timeout`, `workflow_timeout` and `conditional_execution`.

All four resolve at the **top level** of `kailash`, and that import line is the
whole published entry point:

```python
from kailash import WorkflowBuilder, NodeRegistry, Runtime, RuntimeConfig
```

> ⛔ **There is no registry factory and no runtime factory in the package.** You
> construct `NodeRegistry()` and `Runtime(...)` directly, or wrap them in a
> factory of your own. An import of a helper that is not in the line above
> raises `ImportError` at import time — which is the good outcome, but it names
> the symbol you asked for rather than the one you needed, so it reads as a
> missing feature rather than as the wrong entry point.

```python
registry = NodeRegistry()
builder = WorkflowBuilder()
builder.add_node("HTTPRequestNode", "fetch", {"url": endpoint, "method": "GET"})
builder.add_node("SchemaValidatorNode", "check", {"schema": invoice_schema})
builder.connect("fetch", "body", "check", "record")
workflow = builder.build(registry)

runtime = Runtime(registry, RuntimeConfig(max_concurrent_nodes=4))
outcome = await runtime.execute_async(workflow, inputs={"tenant": tenant_id})
```

**`build()` is where an unknown node type is caught**, and it is the earliest
point at which a typo in a type name becomes visible. A workflow assembled but
never built carries the error silently — so build eagerly, at assembly time,
rather than at the point of first execution.

### Custom types are registered before any Runtime shares the registry

`register_callback` adds a type of your own. **Register every custom type BEFORE
constructing a Runtime against that registry.**

> ⛔ **Registering late fails at USE, not at registration.** The registration
> call itself succeeds whenever you make it, and a Runtime that already holds
> the registry does not see the addition — so every workflow naming your custom
> type fails with `unknown node type`, and the registration that would explain
> it reported success. Register at start-up, in one place, before anything is
> constructed against the registry.

### Registered is not runnable — each category has its own preconditions

`list_types()` reports that a node type is **registered**. It does not report
that the node can run: most categories reach something outside the process, and
that dependency is configured separately.

| Category                            | Needs configured before the node runs                     |
| ----------------------------------- | --------------------------------------------------------- |
| AI/multimodal, vector and retrieval | A model provider credential and endpoint                  |
| Kafka and streaming                 | A broker address and topic permissions                    |
| Redis, Cache                        | A cache URL and credential                                |
| Databases and SQL, Vector           | A connection string and a reachable database              |
| HTTP/API, alerts                    | A reachable destination, and egress permitted             |
| Platform and infrastructure         | Credentials for the platform being addressed              |
| Auth, authorization, security       | The relevant keys — [11.3](03-configuration-reference.md) |
| Control flow, transform, code       | Nothing beyond the workflow itself                        |

**The last row is the only one that is self-contained**, and it is why a
workflow of pure control flow and transforms runs in an environment where
everything else fails. A green run over that subset is not evidence the rest of
the catalogue is reachable.

## What a deployment change does to the catalogue

| Change                       | Effect on the catalogue                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------------------- |
| Runtime version upgrade      | Types may be added; behaviour of existing types may change                                   |
| Registering a new data model | Eleven new types appear, for that model                                                      |
| Renaming a data model        | Eleven types disappear and eleven appear — every workflow naming the old set breaks at build |
| Configuration change         | None. The catalogue is a property of the package and the registered models                   |

**The rename row is the one to plan around.** It is a build-time break across
every workflow that referenced the model, it surfaces all at once, and the
remedy is a coordinated edit rather than a compatibility shim — the generated
types are derived from the name and there is no alias.

---

_Next: [11.5 — Data stores and migrations](05-data-stores-and-migrations.md)_
