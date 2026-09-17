# 07.5 — Stateful services

Everything that survives a restart lives here. The workloads in
[07.2](02-the-cluster-and-namespaces.md) are designed to be replaced; these are
the components that must not lose anything, and they are consequently the ones
where an operator's choices matter most and are least visible from outside.

## State does not live on the cluster

The platform's own services run on the cluster. Its **state does not.** That is a
deliberate separation and worth understanding, because it explains a great deal
about how the deployment behaves.

Nodes are cattle, not pets: they are created, drained and destroyed as the pools
autoscale. Anything stored only on a node's local disk is therefore coupled to
that node's lifetime. So the stateful components are **managed services outside
the cluster** — the database, the cache, and object storage are reached
*over the network* by the services that use them, rather than running as pods
alongside them.

The practical consequences you will meet:

- **A pod being rescheduled loses nothing.** It was never holding the data.
- **The cluster can be rebuilt without the data being rebuilt**, because the data
  was never on it.
- **Database availability and cluster availability are different things.** One
  can be healthy while the other is not, and the symptoms differ — worth knowing
  before an incident rather than during one.

## The relational database

This is where the organisation's state lives: its structure, its roles and their
envelopes, its clearance model, its objectives and their history, and the record
of what was permitted. **Managed** means the platform operates it — engine
version, patching, replication, backup — and you do not. You own what is *in* it.

### Embeddings live in the database

This is the detail that most affects a design decision, so it is stated
separately.

**The database carries a vector extension, and embeddings are stored in it — not
in a separate vector service.** When an agent or a search performs a semantic
lookup, that lookup runs against the same database that holds the organisation's
records, with the same transactional and backup characteristics as everything
else.

The operation this shows up in is `api:GET /api/v1/knowledge/search`. That this
client declares it is something you can check from your own machine. *Design
intent, not observable:* which store the embeddings actually live in is a
property of the deployment, and nothing available to you establishes it.

Three consequences worth planning around:

- **One store, one backup, one recovery point.** There is no second system whose
  consistency with the first has to be reasoned about. A record and the embedding
  derived from it share a recovery point by construction.
- **The engine is constrained.** You cannot move this deployment onto an
  arbitrary relational engine or an arbitrary major version. The engine must be
  one that supports the vector extension, and a version upgrade is gated on that
  extension being available for the new version. *Design intent, not observable:*
  this constraint is real, and which engines satisfy it is a question for your
  operator rather than something inferable from here.
- **Embedding cost is storage cost.** As the corpus grows, so does the database.
  Capacity planning for knowledge is database capacity planning, not a separate
  line item.

## The cache

The cache exists to make reads fast. Its correctness property is the useful thing
to know:

**Losing the cache degrades performance, not correctness.** Nothing durable lives
in it. A cold cache means slower responses while it refills — temporarily worse
latency, the same answers.

That is the honest general statement, and it comes with an honest caveat:

**Any system has exceptions to that rule, and you should confirm which apply
here.** A cache that holds anything authoritative — a rate-limit counter, a
session that is not also persisted, a lock — is no longer merely an optimisation,
and losing it changes behaviour rather than speed. The reference shape keeps
authoritative state out of the cache, but *design intent, not observable* applies:
you cannot verify from outside what a given deployment actually stores there.

**If you are designing for failure, this is worth one direct question to your
operator:** does losing the cache lose anything that is not reconstructible? A
"no" is what the architecture intends. Anything other than a clear "no" should be
treated as a real answer.

## Object storage

Artifacts and evidence — the large, immutable, long-retained material. A few
properties that matter:

- **It is not the system of record for structure.** Roles, envelopes and history
  live in the database. Object storage holds the bulkier things: uploaded
  artifacts, captured evidence, exports.
- **It is written to be retained, not overwritten.** The reference shape treats
  stored objects as effectively immutable; the way to change one is to write a
  new one. That is what makes it evidence rather than storage.
- **Retention is a policy, not an accident.** How long evidence is kept, and who
  can delete it, are decisions the deployment makes — and if you have compliance
  obligations of your own, they are decisions you should confirm rather than
  assume.

```
┌──────────────────────────────────────────────────────────┐
│ APPLICATION SERVICES                                     │
└───────┬─────────────────┬───────────────────┬────────────┘
        │                 │                   │
        │ read/write      │ read mostly       │ artifacts
        ▼                 ▼                   ▼
┌───────────────┐   ┌────────────┐   ┌────────────────┐
│ RELATIONAL DB │   │ CACHE      │   │ OBJECT STORAGE │
│ records and   │   │ no durable │   │ artifacts and  │
│ embeddings    │   │ state      │   │ evidence       │
└───────┬───────┘   └────────────┘   └────────┬───────┘
        │ replication                         │ versioning
        ▼                                     ▼
┌──────────────────────────────────────────────────────────┐
│ BACKUP AND POINT-IN-TIME RECOVERY                        │
└──────────────────────────────────────────────────────────┘
```

The absence is the point of the diagram: the cache is the one component with no
arrow into the protected copy, because there is nothing in it that cannot be
rebuilt. The database and object storage both have one — replication and
versioning respectively.

## Backup and recovery

**The reference expectation:** automated backups, and **point-in-time recovery**
— the ability to restore to a chosen moment, not merely to last night. The
distinction is the difference between "we lost a day" and "we lost an hour",
and it is the second you want when something is deleted at 2pm.

Recovery objectives — how much loss is tolerable (the recovery point) and how
long recovery may take (the recovery time) — are **targets an operator sets**,
not guarantees a platform ships. They are choices with costs attached, and
different deployments will have made different ones. [07.7](07-operating-the-deployment.md)
covers what to ask.

**What an operator must verify rather than assume:**

- That backups are **actually running**, not merely configured. A policy that
  exists and a job that executes are different facts.
- That the retention window is what was intended, and that the oldest available
  restore point is where you think it is.
- That a restore has been **performed**, into a real environment, within recent
  memory.

**A backup nobody has restored is a hypothesis.** It is a common and
understandable one — the configuration looks right, the job reports success, the
storage has bytes in it — and none of those observations distinguishes a working
backup from an unusable one. The only instrument that settles it is a restore
that produces a usable database. Until that has happened, the correct description
of your disaster-recovery posture is *untested*, which is not the same as *bad*
but must not be reported as *good*.

*Design intent, not observable:* all of it, from your position. This is the
chapter where the gap between what a reference architecture describes and what
you can check is widest, and it is why the next section exists.

## Encryption

Encryption at rest and in transit are both expected in the reference shape:

- **In transit.** Traffic reaches the edge over TLS ([07.4](04-the-network-boundary.md)),
  and connections to the data plane are encrypted inside the private network as
  well as outside it. Encrypting only the public hop would leave the private
  network — which is not a trust boundary in the sense [07.2](02-the-cluster-and-namespaces.md)
  describes — carrying plaintext.
- **At rest.** Stored data is encrypted by the managed service that holds it.
  This is a property of the platform, not something you configure.

**Your operator's key management may extend this.** A deployment can use
customer-managed keys so that the keys protecting your data are held in your
control rather than the platform's, which changes who can read the data at the
storage layer. That is a genuine control with real operational consequences —
losing such a key is a different class of incident — and whether it is in place
is a question of policy, not something visible from your integration.

**UNVERIFIED — and marked deliberately:** the specific encryption configuration,
key custody arrangements, and recovery objectives of any particular deployment.
Every claim in this section is about construction. The reader who checks them by
asking has done the right thing; the reader who treats them as established
because they appear in a reference architecture has not.

---

*Next: [07.6 — Identity and secrets](06-identity-and-secrets.md)*
