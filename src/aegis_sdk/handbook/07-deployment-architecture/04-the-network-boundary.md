# 07.4 — The network boundary

A deployment has a public surface and a private one, and almost all the
architecture's security value sits in the line between them. This chapter draws
that line, names what crosses it, and is honest about the one crossing where the
reference shape and real deployments diverge most.

## One public door

The public surface is deliberately tiny:

- **One hostname**, serving the API. This is the address your integration points
  at and the address the web console is served from.
- **TLS termination at the edge.** Certificates are presented and managed at the
  boundary, and your connection ends there. What the hops behind the edge look
  like is the deployment's construction; [07.5](05-stateful-services.md) covers
  what the reference shape expects of the data plane specifically.
- **Nothing else.** There is no public database port, no public storage
  endpoint, no administrative interface on a second hostname.

From your side the entire boundary is one string: the base URL you give
`sdk:aegis_sdk.ClientConfig`. That is the whole of what the SDK can reach, and it
is worth appreciating as a design statement rather than a convenience — there is
no second address and no code path in this client that aims at one.

The client half of this is yours to establish in seconds: the SDK has one
configured base URL and no other route out. That the hostname is the deployment's
only public entry point is the architecture your operator runs, and it is worth
having them confirm in writing when a security review asks.

## What crosses the line

```
              your integration · web console
                             │
                             │  HTTPS to one public hostname
                             ▼
┌──────────────────────────────────────────────────────────┐
│ PUBLIC ZONE                                              │
│   Edge / ingress — TLS termination, one hostname         │
│   nothing else is reachable from here                    │
└────────────────────────────┬─────────────────────────────┘
                             │  the only inbound crossing
                             ▼
┌──────────────────────────────────────────────────────────┐
│ PRIVATE ZONE                                             │
│   application services                                   │
│                                                          │
│   private data plane — no public address                 │
│     ├─ relational database                               │
│     ├─ cache                                             │
│     ├─ object storage                                    │
│     └─ secret store                                      │
└────────────────────────────┬─────────────────────────────┘
                             │  controlled egress — allowlisted, logged
                             ▼
┌──────────────────────────────────────────────────────────┐
│ OUTSIDE THE DEPLOYMENT                                   │
│   model providers and other external services            │
└──────────────────────────────────────────────────────────┘
```

Two crossings are drawn and they behave differently. **Inbound**, one edge admits
traffic and passes it to the application services. **Outbound**, a single
controlled path is the only way anything leaves. Everything else in the diagram
is inside a zone and never crosses.

## The private plane

The database, the cache, object storage and the secret store are reachable
**only over private endpoints inside the deployment's network**. They are not on
the public internet, and they do not have public addresses that merely happen to
be firewalled — the reference shape removes them from public reachability
entirely.

**Why this matters more for a governance product than for a typical web
application.** Three of these four components hold the things the product's
value depends on:

- The **database** holds the organisation's structure, its envelopes, its
  clearance model, and the record of what was permitted. It is simultaneously the
  system of record and a map of the organisation's authority structure.
- **Object storage** holds artifacts and evidence — the material an auditor would
  be shown.
- The **secret store** holds the credentials that let the platform act as itself.

A publicly reachable data plane would mean the audit evidence — the thing the
platform exists to produce — was an internet-exposed asset. The compromise that
matters is not disruption; it is that someone could alter or read the record
whose whole purpose is to be trustworthy. That is why the data plane sits behind
private endpoints rather than behind authentication alone.

The property that matters is the reachability outcome, and more than one
mechanism satisfies it. The reference shape uses private endpoints; a specific
deployment may reach the same outcome with a network-level restriction instead.

## Segmentation inside the private zone

Within the private zone, not everything can reach everything:

- **Namespace-to-namespace.** Network policy governs which pods may open
  connections to which others. The application services reach the data plane;
  the ephemeral job namespace reaches what its work requires and no more.
  Confirm your deployment's policy with your operator before you design against
  it — for the same reason [07.2](02-the-cluster-and-namespaces.md) treats a
  namespace as an operational boundary rather than a security one.
- **Workload-to-data-plane.** Reachability is paired with **identity**: being
  on the network is not the same as being authorised. A service that can open a
  TCP connection to the database still has to authenticate to it — see
  [07.6](06-identity-and-secrets.md). The network limits who may _try_; identity
  decides who _succeeds_.

Hold both, because they fail differently. A network rule that is too permissive
is a latent exposure. An identity that is too permissive is an immediate one.

## Egress is where deployments actually differ

Be direct about this, because it is the section most likely to be untrue of the
deployment in front of you.

Agents in this platform call **model providers**, and those providers are outside
the deployment. So there is real outbound traffic carrying real content, and how
that traffic is controlled is the single largest variable between deployments.

The reference posture:

- **Egress is not default-allow.** Outbound traffic leaves through a controlled
  path, and destinations are allowlisted rather than the whole internet being
  reachable.
- **It is a governed path.** What leaves is attributable. An agent's call to a
  model provider is the same class of event as any other externally-visible
  action the platform takes, and it is recorded as such rather than being
  invisible plumbing.
- **It is the crossing that carries your data outward.** Inbound traffic is
  requests from you; outbound traffic may be your organisation's content being
  sent to a third party in order to answer one of those requests. That asymmetry
  is why this crossing deserves more scrutiny than the inbound one.

**Where the reference shape and reality part company:** allowlisting egress is a
real operational burden. Provider endpoints change, regions differ, and an
over-tight policy produces outages that look like application failures. Each
deployment settles that trade-off for itself, which is why the posture is a
question to ask rather than a default to assume.

**What to ask your operator, in this order:**

1. Is egress allowlisted, or is it default-allow with logging?
2. Which destinations are on the allowlist, and who changes it?
3. Is the agent-to-provider path recorded, and where does that record go?

**Your operator sets the egress posture**, and it is one of the settings that
differs most between deployments — which is why those three questions are worth
asking before you write the answer into a security review rather than after.

## What the boundary is, and what it is not

**The boundary is not an authorization model.** It decides what can be
_reached_, not what may be _done_. A request that arrives cleanly over the
public hostname still faces every check the platform applies — see part 04.
Network position is not authority, and no part of this architecture treats it as
such. That separation is deliberate: it is what lets the same governance apply
whether a call arrives from inside the cluster or from your integration.

---

_Next: [07.5 — Stateful services](05-stateful-services.md)_
