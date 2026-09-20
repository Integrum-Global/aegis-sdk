# Part 11 — The deployment pack

<!-- anchor-floor: exempt (part navigation; chapters carry the anchors) -->

**Audience: the operator who runs an Aegis deployment.** Not the integrator
attaching to one — that is part 07 — but the person who provisions the
substrate, sets the configuration, applies the release, watches it, and answers
for it at three in the morning. You hold the cluster credentials. You decide the
maintenance window. You are the one the auditor asks.

Part 07 describes the SHAPE of a deployment: what the components are, who owns
what, where the boundaries fall. **This part is the working pack** — the
substrate to provision, the configuration keys to set, the runtime and its node
catalogue, the stores and their migrations, the release and rollback operation,
the day-to-day watch, and the checks that prove the whole thing is correct.

The two parts are deliberately disjoint. Where this part needs a shape, it links
to part 07 rather than restating it. **Read part 07 first if you have not; read
this one with a terminal open.**

## The chapters

| #    | Chapter                                                        | You leave able to                                                                                              |
| ---- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 11.1 | [What is in the pack](01-what-is-in-the-pack.md)               | Name every artefact you were given, say what each is for, and route a question to the right chapter            |
| 11.2 | [Provisioning the substrate](02-provisioning-the-substrate.md) | Stand up the cluster, namespace, quotas, storage, ingress and certificates a deployment needs before it boots  |
| 11.3 | [Configuration reference](03-configuration-reference.md)       | Set every required key, know which are secrets, and recognise what a missing one looks like at runtime         |
| 11.4 | [The runtime and its nodes](04-the-runtime-and-its-nodes.md)   | Name the runtime package, reach every one of its node types, and derive the catalogue against your own install |
| 11.5 | [Data stores and migrations](05-data-stores-and-migrations.md) | Size and tune the database and cache, apply schema changes in order, and take a backup you have restored       |
| 11.6 | [Releasing and rolling back](06-releasing-and-rolling-back.md) | Build and stamp an image, run the deploy operation with its preflights, and reverse it                         |
| 11.7 | [Operating day to day](07-operating-day-to-day.md)             | Read health, watch the right numbers, respect the capacity ceilings, and work the incident playbooks           |
| 11.8 | [Verifying the deployment](08-verifying-the-deployment.md)     | Prove the running deployment matches the repository, and that a partner can reach it                           |

## How the eight chapters relate

They are one deployment, described in the order you actually meet it: what you
were given, what you build it on, what you tell it, what it runs, what it
stores, how you change it, how you watch it, and how you prove it.

```
┌─ the pack, in working order ──────────────────────────────────────────────────
│
│  11.1  What is in the pack              the inventory, and the routing
│   │
│   ├─► 11.2  Provisioning the substrate  what must exist before anything boots
│   │    │
│   │    └─► 11.3  Configuration          what you tell it — the required keys
│   │         │
│   │         ├─► 11.4  Runtime and nodes what it can actually do
│   │         │
│   │         └─► 11.5  Stores            what it keeps, and how schema moves
│   │              │
│   │              └─► 11.6  Release      how the running version changes
│   │                   │
│   │                   └─► 11.7  Operate the steady state, and the incidents
│   │                        │
│   │                        └─► 11.8  Verify   proof, for you and the auditor
│   │
└───────────────────────────────────────────────────────────────────────────────
```

Read it as: each arrow is a **precondition**, not a call path. You cannot
usefully set configuration before the namespace exists, and you cannot verify a
release you have not applied. Four things follow from the shape:

- **11.1 is the map.** Every later chapter is one row of its inventory expanded.
- **11.3 is the chapter you will return to most.** A deployment that will not
  boot, or boots and refuses everything, is a configuration question far more
  often than it is anything else.
- **11.4 stands slightly apart.** It is the capability surface rather than the
  infrastructure, and it is what you hand a builder who asks "what can this
  actually do?"
- **11.8 assumes all of them.** A verification is only meaningful once you know
  what was supposed to be there.

## Where this part sits relative to the others

Part 02 is how work runs through a governed organisation. Part 04 is the API
surface an integration calls. Part 06 is the platform's architecture. Part 07 is
the deployment's shape and the ownership line.

This part is the deployment's **operation**. Part 07 tells you a managed
database holds the state and that backups are the operator's responsibility;
this part tells you how to size it, how to migrate it, and how to prove the
restore works.

The practical test is the question you are asking. _"What does a rollout do to
in-flight requests?"_ is part 07 — it is the shape. _"Which configuration key
turns on asymmetric JWT, and what happens if I set only half the pair?"_ is
[11.3](03-configuration-reference.md). _"Which node type do I use to call a
webhook from a workflow?"_ is [11.4](04-the-runtime-and-its-nodes.md).

Every cluster name, registry, namespace, storage account and hostname in this
part is a placeholder — `<cluster-name>`, `<registry>`, `<app-namespace>`,
`<your-deployment>` — because those belong to your deployment, not to the pack.

---

_Next: [11.1 — What is in the pack](01-what-is-in-the-pack.md)_
