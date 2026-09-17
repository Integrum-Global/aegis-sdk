# 07.3 — Images and the registry

Everything the deployment runs is a container image, and every image comes from a
registry. That much is unremarkable. What is worth a chapter is **how an image is
named when it is deployed**, because the difference between the two obvious ways
of naming one is the difference between a release you can reason about and a
release you cannot.

## A tag is a label. A digest is an identity.

A registry lets you refer to an image two ways:

```text
<registry>.azurecr.io/<image>:1.4.0
<registry>.azurecr.io/<image>@sha256:<digest>
```

The first is a **tag**. The second is a **digest**. They look like variations on
the same idea. They are not.

| | tag | digest |
| --- | --- | --- |
| **What it names** | a label someone chose | the exact bytes of one image |
| **Can it change?** | yes — pushed over, silently | no — it *is* the content hash |
| **Reproducible?** | only if nobody ever retags | always |
| **Good for** | humans reading a list | deploying, auditing, rolling back |
| **Failure mode** | two different images, same name, weeks apart | none — a digest cannot drift |

**A mutable tag is not a release.** If a deployment is pinned to a tag, then the
thing running in your environment today is not provably the thing that was tested
last week, even though every artefact of the process — the manifest, the
deployment record, the change ticket — says `1.4.0`. Nothing has to go wrong for
this to be true; a rebuild and a re-push under the same tag is enough, and it
leaves no trace anyone would think to look for.

**A digest is what makes "we tested this exact thing" a true sentence.** When you
see a pod running `@sha256:…`, that string names one image and no other, and it
names the same image in every environment and every registry copy.

*Design intent, not observable:* that your deployment pins by digest rather than
by tag. You cannot read the running pod's image reference from outside, and this
is a reasonable question to put to your operator precisely because the answer is
not visible from where you sit.

## Build once, then promote

The reference pipeline builds an image **once** and then moves *that same image*
through the environments:

1. **Build** — from a specific source revision, in a pipeline, into an image.
2. **Publish** — pushed to the registry and identified by its digest.
3. **Promote** — the *same digest* is referenced in each environment in turn, as
   it passes whatever gate that environment applies.

**Why not build per environment, which is easier to wire up?** Because a rebuild
is a different image. Different base layer, possibly different dependency
resolution, different build timestamps — all invisible, all real. So
"we tested it in staging, then built for production" means you tested something
and deployed something else, and the only reason it usually works is that the two
are *usually* identical rather than *guaranteed* identical. Promoting a digest
removes the word "usually".

This is also what makes the chain auditable: build happened once, at one time,
from one revision, and everything after that is a reference to it.

```
                      source revision
                             │
                             │  built once — never rebuilt per environment
                             ▼
┌──────────────────────────────────────────────────────────┐
│ BUILD — one pipeline run                                 │
│   acts as: the publisher identity                        │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│ REGISTRY — stores by digest                              │
│   a tag is a label · a digest is an identity             │
└────────────────────────────┬─────────────────────────────┘
                             │
                             │  pulled as: workload identity
                             │  no stored credential
                             ▼
┌──────────────────────────────────────────────────────────┐
│ DEPLOYED WORKLOAD                                        │
│   references the digest — rollback re-pins it            │
└──────────────────────────────────────────────────────────┘
```

The label beside each hop is the subject of the next two sections: a different
identity acts at each one, and none of them is a password sitting in a file.

## The cluster does not hold a registry password

A cluster that must pull a private image has to authenticate to the registry to
do it. The obvious way is an **image pull secret** — a credential stored in the
cluster and handed to every node that pulls. The reference architecture does
**not** do this, and the reason is not tidiness:

**A stored pull credential is a long-lived secret with cluster-wide reach.** It
sits in the cluster, it is readable by anything that can read secrets there, it
must be rotated by hand, and when it leaks the blast radius is
the whole registry rather than one workload.

Instead, the cluster authenticates as a **managed identity** — a workload
identity federated from the platform's identity provider. There is no password to
store, because there is no password: the identity is issued to the workload at
runtime and is scoped to what that workload should be able to reach.

That mechanism is [07.6](06-identity-and-secrets.md)'s subject, and it is
deliberately the same mechanism used for every other cloud resource a pod might
need. One identity model, not one per service.

*Design intent, not observable:* the federation is the reference shape's
construction. A specific deployment may still hold a pull secret; if you are
auditing one, this is a question worth asking directly, because the two designs
have very different exposure when a credential leaks.

## Supply chain: what to require before you promote

Two properties, both about trusting an image you did not build:

- **Provenance** — evidence of *how* the image was produced: which source
  revision, which build, which pipeline. Provenance answers "where did this come
  from?" and makes the answer checkable rather than asserted.
- **Signature** — evidence of *who* produced it, verifiable against a key you
  trust. A signature answers "should I accept this?" and is what lets a policy
  say *reject anything unsigned* rather than *check the tag and hope*.

They are complementary. Provenance without a signature tells you a story you
cannot authenticate; a signature without provenance tells you who signed
something without telling you what is in it.

**What an operator should require before promoting an image into an environment
that matters:** that it is pinned by digest, that its signature verifies against
a trusted key, and that its provenance names a source revision the operator
recognises. A tag that looks right is not on that list, and the reason is the
first section of this chapter.

*Design intent, not observable:* whether your deployment enforces these, or
merely supports them. Enforcement is admission policy inside the cluster and is
not visible from the client side — another question for your operator, and one
whose answer changes how much the previous paragraph is worth.

## Rollback is re-pinning, not rebuilding

This follows directly from digests, and it is the practical payoff:

**To roll back, reference the previous digest.** The image still exists, it is
still the exact bytes that ran before, and the operation is a change of
reference — minutes, and no build.

Contrast the tag-based version of the same operation, which is where rollback
usually goes wrong: you cannot roll *back* to a tag, because the tag does not
remember. You can only redeploy the tag and hope it still points where you think
it does, or reconstruct the earlier build and deploy something that is
*approximately* what ran before.

**The corollary is worth acting on:** a rollback you have never rehearsed is a
hypothesis. Knowing the previous digest exists is not the same as having deployed
it. If the answer to "what do we do if this goes wrong" is a procedure nobody has
executed, the honest state of that control is untested — [07.7](07-operating-the-deployment.md)
returns to this in the pre-production checklist.

## Which versions you can and cannot see

These are different questions and it is easy to conflate them:

- **Your own integration's version** is entirely observable. `sdk:aegis_sdk.__version__`
  reports it from your own environment, and it is what you quote when asking
  whether your client is compatible with a deployment.
- **The deployment's running image digests** are not observable from your
  integration. You reach the platform over HTTP; you do not get to read what it
  is running.

**UNVERIFIED:** whether any deployment exposes its own version through a
supported operation. The health operations in [07.7](07-operating-the-deployment.md)
report liveness rather than build identity, and this document does not claim a
version endpoint exists. If you need the deployed version, ask your operator —
that is the reliable route, and it is not a workaround.

---

*Next: [07.4 — The network boundary](04-the-network-boundary.md)*
