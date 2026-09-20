# 11.8 — Verifying the deployment

A deployment that is up is not the same as a deployment that is correct, and the
gap between them is where most of the expensive surprises live. This chapter is
how you close it: prove the cluster matches the repository, prove the running
version is the one you meant, prove a partner can actually reach what you built,
and prove the documentation you ship resolves.

Each check below answers one question and **only** that question. The
temptation — and it is the failure mode this whole chapter exists to block — is
to run the cheapest one and let it stand for the others.

**The one idea to carry out: name what each check would say if the answer were
NO, before you cite it as evidence that the answer is yes.**

## The four checks, and what each is blind to

| Check                  | Answers                                           | Does not answer                 |
| ---------------------- | ------------------------------------------------- | ------------------------------- |
| **Drift**              | Does the live cluster match the repository?       | Whether the repository is right |
| **Policy enforcement** | Is NetworkPolicy actually enforced?               | Whether the policies are right  |
| **Version surfaces**   | Is the running code the commit you deployed?      | Whether that commit behaves     |
| **Reachability**       | Can a partner call what you built?                | Whether the answers are correct |
| **Anchor check**       | Does every claim in the shipped handbook resolve? | Whether the prose is true       |

Read the right-hand column as the reason you run all five. **A green drift check
on a wrong manifest is a correctly-applied mistake**, and it is
indistinguishable from a correctly-applied intent by every instrument in this
chapter — so each check's answer is worth exactly the question it was asked.

## Drift verification

Drift is the live cluster diverging from the repository — a hand-applied fix, a
scaled replica count nobody committed, an image reference edited in place during
an incident. It accumulates silently and surfaces at the next deploy, when
something that had been working is overwritten by the declared state.

The verifier runs on a daily schedule and on demand, and it has **three**
outcomes, not two:

| Outcome          | Meaning                                                             |
| ---------------- | ------------------------------------------------------------------- |
| **MATCHES**      | Live state equals the repository                                    |
| **DRIFTED**      | A named difference exists                                           |
| **UNDETERMINED** | The check could not reach the cluster, or could not resolve a value |

> ⛔ **UNDETERMINED is a failure, not a pass.** It means the check did not look —
> and "could not look" and "looked and found nothing" produce the same silence
> from anything that treats the outcome as a boolean. The scheduled run fails on
> DRIFTED **and** on UNDETERMINED, deliberately. A verifier that reports clean
> when it could not reach the cluster is worse than no verifier, because it
> retires the question.

The check runs against the live cluster on its own schedule, never on the
pull-request path. That placement is deliberate: **production staleness is not a
property of the change under review**, and a gate that reds unrelated proposals
is muted within a week.

```bash
# Orientation: the difference between declared and live, per workload
kubectl -n <app-namespace> get deploy -o wide          # image references in force
kubectl -n <app-namespace> get deploy/<backend> -o jsonpath='{.spec.replicas}{"\n"}'
```

## Policy enforcement — prove the engine is live

[11.2](02-provisioning-the-substrate.md) requires the cluster to be provisioned
with a network-policy engine. This is the check that proves it, and it is the
only one that can: every other signal — the policy objects, the listing, the
manifest review — reads identically with and without an engine.

The deploy operation runs this as a preflight and **refuses to apply policies to
a cluster that has no engine to enforce them**, so a deploy that reaches the
apply step has already answered this. Run it independently when you want the
answer without a deploy:

```bash
# Orientation: is an enforcing engine present on this cluster?
kubectl get nodes -o jsonpath='{.items[0].metadata.labels}' | tr ',' '\n' | grep -i policy
kubectl -n kube-system get pods            # the engine runs here when one is installed
```

Three outcomes, and the third is not a pass:

| Outcome           | Meaning                                           |
| ----------------- | ------------------------------------------------- |
| **ENFORCING**     | An engine is present; the policies bind           |
| **NOT ENFORCING** | Policies are admitted and inert — fix the cluster |
| **INDETERMINATE** | The check could not read the cluster              |

An engine can also be installed on a **running** cluster with the provider's
update command, so NOT ENFORCING is a remediation rather than a rebuild.

## Version surfaces

Two surfaces report what is running: a **version operation on the backend**, and
a **static version file the web image serves**. Both derive from the stamp
generated inside each build ([11.6](06-releasing-and-rolling-back.md)).

Three states, and the third is the one worth looking for:

| Reading                                         | Means                                                              |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| Both name the commit you deployed               | Correct                                                            |
| Either names something else                     | The deploy did not land what you believe it landed                 |
| **They name DIFFERENT commits from each other** | **A split release — front end and back end from different builds** |

**The split is the dangerous one** because nothing about it is unhealthy. Both
pods are Ready, both surfaces answer, the deployment reports green — and the
contract between the two halves is whatever the older one assumed. It surfaces
later as an intermittent field mismatch that reads like a code defect.

Check them together, never one alone.

## Reachability — can a partner actually call this?

An operator's verification and an integrator's experience are different
measurements, and the operator's is the one that passes while the partner is
blocked. The cheapest partner-shaped probe is the SDK itself, pointed at the
deployment from outside the cluster.

```python
client = AgenticOSClient(ClientConfig(base_url=base_url, api_key=api_key))
me = await client.auth.get_me()
orgs = await client.auth.list_my_organizations()
```

`api:GET /api/v1/auth/me` confirms the deployment and the principal;
`api:GET /api/v1/auth/me/organizations` confirms the organisations that
credential resolves to — **and no others**, which is the half people skip.
`sdk:aegis_sdk.__version__` reports the client's own version, which is what you
quote when asking whether a partner's client is compatible.

Four probes, in increasing depth:

| Probe                                      | Establishes                                            |
| ------------------------------------------ | ------------------------------------------------------ |
| `api:GET /api/v1/auth/me`                  | The edge answers, and the credential resolves          |
| `api:GET /api/v1/auth/me/organizations`    | The credential's scope is what you intended            |
| `api:GET /api/v1/knowledge/search`         | The database and its vector extension are both working |
| One operation you expect to be **REFUSED** | Governance is enforcing, not merely present            |

> ⛔ **The fourth is the only one that tests the product's actual job.** A
> permission model tested only in the permissive direction is untested — every
> call succeeding is exactly what a deployment with governance switched off also
> produces. Attempt something your credential should not be allowed to do, and
> confirm the refusal.

## Governance integrity

Two operations verify the governance record itself rather than the services
that write it:

```python
integrity = await client.compliance.get_chain_integrity()
verified = await client.compliance.verify_audit()
```

`api:GET /api/v1/compliance/chain/integrity` checks the audit chain's internal
consistency; `api:GET /api/v1/compliance/audit/verify` verifies the entries.
Together they are what an auditor is shown, and they answer a question no health
check touches: **not "is the service up" but "is the record intact".**

`api:GET /api/v1/compliance/dashboard` is the posture roll-up, and
`api:GET /api/v1/trust/metrics` reports the trust surface's own numbers.

## The handbook anchor check

The handbook you ship makes claims about operations and symbols. The anchor
check resolves every one of them against the derived operation set and the
installed package, and it has exactly two outcomes — `OK`, or `FAIL` with a
count.

```bash
# Capture, then read. Never pipe into a filter and read the filter's status
python -m aegis_sdk.handbook.check > /tmp/anchors.txt 2>&1; EXIT=$?
cat /tmp/anchors.txt; echo "EXIT=$EXIT"
```

**Capturing before reading is not fussiness.** A pipeline's exit status is its
last stage's, so `... | tail` reports `tail`'s success and a failing check reads
as a pass. That trap costs a release rather than a minute, because the green is
banked and nobody re-runs it.

## The verification sequence

Run these in order. Each one's failure makes the next one's result meaningless.

- [ ] **Drift** reports MATCHES — and UNDETERMINED was treated as a failure.
- [ ] **Policy enforcement** reports ENFORCING, from the cluster rather than
      from the policy objects.
- [ ] **Both version surfaces** name the commit you deployed, and name the same
      one as each other.
- [ ] **Reachability**: the edge answers, the principal is right, the
      organisation list is exactly what you expect.
- [ ] **A refusal** was observed for an operation that should be refused.
- [ ] **Governance integrity** and audit verification both pass.
- [ ] **The backup record** shows a dump within the last hour, and a restore has
      been performed within recent memory —
      [11.5](05-data-stores-and-migrations.md).
- [ ] **The anchor check** exits `OK`, read from a captured file.

## What to establish before you depend on a deployment

Three things this chapter cannot measure, which you settle by asking rather than
by probing — and each has a right answer and a recognisable wrong one.

| Question                                                         | A good answer names                       |
| ---------------------------------------------------------------- | ----------------------------------------- |
| When was a restore last **performed**, and how long did it take? | A date and a duration                     |
| What is the retention policy for audit evidence?                 | A period, and who can delete within it    |
| Who is on call, and by what route are they reached?              | A rota and an escalation path, in writing |

**One item that is easy to skip and should not be:** confirm the person
answering is able to answer. "I will find out" is a fine answer. A confident
answer about a deployment the respondent has not inspected is not — and this
part has named enough silent failure modes that the difference between the two
is worth the extra question.

---

_This is the last chapter of part 11, and the end of the handbook. For what the
platform can do once it is running, go to
[Part 08 — The capability catalogue](../08-the-capability-catalogue/README.md);
for the governance model your deployment now enforces, go to
[Part 09 — The governance architecture](../09-the-governance-architecture/README.md)._
