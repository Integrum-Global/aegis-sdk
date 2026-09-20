# 11.3 — Configuration reference

This is the chapter you will come back to. A deployment that will not boot, or
boots and refuses everything, or boots and serves a blank page, is a
configuration question far more often than it is a code, network or cluster
question — and the three symptoms above map to three different missing keys.

Configuration arrives in two surfaces. **Non-secret settings** live in a config
map: readable by anyone who can read the namespace, versioned with the
manifests, safe in a diff. **Secrets** live in a secret set: mounted into the
container at start, never baked into an image, never committed. The split is not
cosmetic — anything in the first surface is visible to every workload in the
namespace and to anyone reading a manifest.

**The one idea to carry out: every key below has a failure mode, and almost none
of them is an error message with the key's name in it.**

## Non-secret settings

These are the config-map keys. Values shown are the reference defaults; the
ones marked **set per environment** have no sensible default and must be
supplied.

| Key                                  | Reference default          | What it actually does                                                                                                |
| ------------------------------------ | -------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `ENVIRONMENT`                        | `production`               | Names the environment. Read by logging and by behaviour that differs outside production.                             |
| `DEBUG`                              | `false`                    | Verbose error surfaces. **Never `true` outside a throwaway environment** — it widens what an error response reveals. |
| `LOG_LEVEL`                          | `info`                     | Emitted log verbosity. `debug` on a busy deployment is a cost decision, not just a noise one.                        |
| `JWT_ALGORITHM`                      | `HS256`                    | Symmetric by default; `RS256` switches to the asymmetric key pair below.                                             |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`    | `15`                       | Access-token lifetime. Shorter means more refreshes, not less access.                                                |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`      | `7`                        | Refresh-token lifetime. This is how long a stolen refresh token is useful.                                           |
| `POSTGRES_DB`                        | `kaizen_studio`            | Database name. Must match what the connection string in the secret points at.                                        |
| `POSTGRES_PORT`                      | `5432`                     | Database port.                                                                                                       |
| `REDIS_PORT`                         | `6379`                     | Cache port.                                                                                                          |
| `AEGIS_DB_USE_APP_ROLE`              | `false`                    | Turns on connecting as a restricted application role rather than the owner.                                          |
| `AEGIS_DB_APP_ROLE`                  | `application_role`         | The role name used when the switch above is on. Inert while it is off.                                               |
| `AEGIS_ARTIFACT_STORAGE_PATH`        | `/var/lib/aegis/artifacts` | Where artifacts are written. Must be a writable mount, not the image's root filesystem.                              |
| `CORS_ORIGINS`                       | **set per environment**    | Origins the browser is allowed to call from. Must include your front-end's exact scheme, host and port.              |
| `FRONTEND_URL`                       | **set per environment**    | The front-end's own address, used where the backend needs to construct a link back.                                  |
| `AZURE_TENANT_ID`                    | `common`                   | Directory tenant for single sign-on. `common` accepts any directory; name yours to restrict it.                      |
| `AEGIS_ALLOW_SELF_SERVE_ORG_ADMIN`   | `false`                    | Whether a new organisation may self-provision an administrator.                                                      |
| `AEGIS_BOOTSTRAP_ADMIN_EMAILS`       | _(empty)_                  | Addresses granted administrator on first boot. Empty means nobody is bootstrapped.                                   |
| `AEGIS_GENESIS_SUPER_ADMIN_ENABLED`  | `false`                    | The first-boot super-administrator path. Off after the deployment is established.                                    |
| `AEGIS_ENTITLEMENT_ENFORCEMENT_MODE` | `off`                      | Whether licence entitlements are enforced, observed, or ignored.                                                     |

### The three keys that produce the three classic symptoms

| Symptom                                              | The key                                                     |
| ---------------------------------------------------- | ----------------------------------------------------------- |
| Front-end loads, every API call fails in the browser | `CORS_ORIGINS` does not exactly match the front-end origin  |
| Deployment healthy, nobody can log in                | `AEGIS_BOOTSTRAP_ADMIN_EMAILS` empty on a fresh database    |
| Everything works, then stops after fifteen minutes   | Refresh path misconfigured; the access token simply expired |

**`CORS_ORIGINS` is the one that wastes the most time**, because the failure is
entirely browser-side. The backend logs a successful request. The front-end
shows a network error with no status. Nothing in either log names the origin
check, and the scheme and port are part of the match — `https://host` and
`https://host:443` are different origins to a browser.

## Secrets

Mounted from the secret set, never baked into an image, never committed. Every
one of these is required unless the row says otherwise.

| Secret key                        | Environment name                                  | Purpose                                                                       |
| --------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------- |
| `database-url`                    | `DATABASE_URL`                                    | The connection string the backend uses.                                       |
| `app-database-url`                | `AEGIS_APP_DATABASE_URL`                          | The restricted-role connection string. Needed when the app-role switch is on. |
| `postgres-user`                   | —                                                 | The database role the in-cluster Postgres is created with.                    |
| `postgres-password`               | —                                                 | Its password. Also consumed by the backup job.                                |
| `postgres-db`                     | —                                                 | The database created at first start.                                          |
| `redis-url`                       | `REDIS_URL`                                       | Cache connection string, including credentials.                               |
| `redis-password`                  | —                                                 | The cache's own password.                                                     |
| `jwt-secret`                      | `JWT_SECRET_KEY`                                  | Symmetric signing key. Used when the algorithm is `HS256`.                    |
| —                                 | `JWT_SECRET_KEY_PREVIOUS`                         | The outgoing symmetric key during a rotation. Optional.                       |
| —                                 | `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY`              | The asymmetric pair. Required when the algorithm is `RS256`.                  |
| —                                 | `JWT_PUBLIC_KEY_PREVIOUS`                         | The outgoing public key during an asymmetric rotation. Optional.              |
| `encryption-key`                  | `AEGIS_ENCRYPTION_KEY`                            | Application-level field encryption.                                           |
| `encryption-master-key`           | `ENCRYPTION_MASTER_KEY`                           | The master key the above derives from.                                        |
| `credential-encryption-key`       | `CREDENTIAL_ENCRYPTION_KEY`                       | Protects stored third-party credentials.                                      |
| `cursor-encryption-key`           | `CURSOR_ENCRYPTION_KEY`                           | Protects opaque pagination cursors against tampering.                         |
| `hash-pepper`                     | `HASH_PEPPER`                                     | Pepper for password hashing.                                                  |
| `pii-hash-salt`                   | `AEGIS_PII_HASH_SALT`                             | Salt for pseudonymising personal data in derived records.                     |
| `azure-client-id` / `-secret`     | `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`         | Workload credentials for cloud resources.                                     |
| `azure-sso-client-id` / `-secret` | `AZURE_SSO_CLIENT_ID` / `AZURE_SSO_CLIENT_SECRET` | Single sign-on application registration.                                      |
| `license-json`                    | via `LICENSE_FILE_PATH`                           | The signed licence, mounted as a file. Never baked into an image.             |

### Generate the real values before the first apply

**The secret template ships placeholders, and you generate the real values with
the provided generator before first apply.** The generator produces every key in
the table above with the right shape and writes the secret in one step:

```bash
# The one command that populates every generated key
bash <deployment-pack>/scripts/generate-secrets.sh
```

It requires `openssl`. Run it once, before the first apply.

**The recipes, if you are generating a single key by hand.** They are not
interchangeable — three keys need a Fernet-shaped value and the rest are plain
hex, and a hex string handed to a Fernet consumer is rejected at first use.

| Key                                                                          | Recipe                                                    |
| ---------------------------------------------------------------------------- | --------------------------------------------------------- |
| `AEGIS_ENCRYPTION_KEY`, `CREDENTIAL_ENCRYPTION_KEY`, `CURSOR_ENCRYPTION_KEY` | **Fernet** — 32 url-safe base64 bytes, a 44-character key |
| `ENCRYPTION_MASTER_KEY`, `HASH_PEPPER`, `AEGIS_PII_HASH_SALT`                | `openssl rand -hex 32`                                    |
| `JWT_SECRET_KEY`                                                             | `openssl rand -hex 32` — at least 32 characters           |
| `postgres-password`, `redis-password`                                        | `openssl rand -hex 32`                                    |
| `postgres-user`                                                              | A name plus a random suffix                               |
| The single sign-on client secret                                             | Supplied by your identity provider, not generated         |

> ⛔ **A Fernet key is not `openssl rand -hex 32`.** The consumer requires 32
> url-safe base64-encoded bytes and rejects anything else by length. Generate it
> as base64 and translate `+/` to `-_`, or let the generator do it — a hex value
> in one of those three slots fails at first use, not at apply.

### Two one-way doors — decide them at provisioning

Two keys cannot be changed later, so they are provisioning decisions rather than
operational ones.

- **The PII hash salt is set at genesis or never.** It pseudonymises personal
  data in derived records, and there is no re-encryption path — changing it
  later leaves every existing derived record unmatchable against every new one.
  Set it when you provision, and back it up with the deployment.
- **The master key is generated, never left at its template value.** It is the
  root the other derived keys hang from. Generate it at provisioning and treat
  it as the deployment's most valuable secret.

Both of these are decided once. **Deciding them by not deciding them is the
failure mode** — the placeholder is a valid string, so a deployment that never
ran the generator starts, serves, and stores data under a value that is neither
secret nor yours.

### The rotation keys are pairs, and half a pair is worse than none

`JWT_SECRET_KEY_PREVIOUS` and `JWT_PUBLIC_KEY_PREVIOUS` exist so a signing key
can be rotated without invalidating every live session: the new key signs, the
previous key still verifies, and the overlap is drained before the old key is
removed.

> ⛔ **Removing the previous key before its tokens have expired logs everyone
> out at once**, and the symptom is a support incident rather than an error: the
> deployment is healthy, the logs are clean, and every user is simultaneously
> asked to sign in again. Drain for at least the refresh-token lifetime —
> the reference `7` days — before dropping the outgoing key.

### The encryption keys are not interchangeable, and losing one is not recoverable

Four distinct keys protect four distinct things. **They are not a group you can
rotate together casually**, and a value encrypted under a key you no longer have
is gone — there is no recovery path, because that is the property the key
exists to provide.

| Key                         | What becomes unreadable if you lose it  |
| --------------------------- | --------------------------------------- |
| `ENCRYPTION_MASTER_KEY`     | Everything derived from it              |
| `AEGIS_ENCRYPTION_KEY`      | Encrypted application fields            |
| `CREDENTIAL_ENCRYPTION_KEY` | Every stored third-party credential     |
| `CURSOR_ENCRYPTION_KEY`     | Nothing durable — cursors are ephemeral |

The last row is the only safe one to rotate without ceremony: an invalidated
cursor means a client's next page request fails and the client starts over.

## The licence is mounted, never baked

The licence is a signed file. The **public key that verifies it** is baked into
the image as a trust anchor; the **licence itself** is not, and is mounted from
a secret at `LICENSE_FILE_PATH`.

That split is what lets one image serve every deployment. **Baking a licence
into an image ties that image to one deployment silently** — it still runs
anywhere, and it reports the wrong entitlements in every environment it was not
built for, with no error at any point.

## Confirming configuration actually landed

A config map or secret is read at container **start**. Editing one does not
change a running pod, and this is the single most common false conclusion in
this chapter: the value is correct in the cluster and stale in the process.

```bash
# Orientation: what the cluster holds, and whether the pods have picked it up
kubectl -n <app-namespace> get configmap <name> -o yaml    # what is declared
kubectl -n <app-namespace> get secret <name> -o jsonpath='{.data}' | tr ',' '\n' | cut -d'"' -f2
#   ^ key NAMES only — never decode values into a terminal or a transcript
kubectl -n <app-namespace> rollout restart deployment/<backend>   # what makes it take effect
```

From the API, two operations report the configuration as the deployment
understands it, which is the reading that matters:

```python
org = await client.settings.get_organization()
posture = await client.compliance.get_dashboard()
```

`api:GET /api/v1/settings/organization` is the organisation-level view, and
`api:GET /api/v1/compliance/dashboard` reports the governance posture the
deployment is actually enforcing rather than the one the manifests declare.

> ⚠ **Never decode a secret's value into a terminal, a log or a transcript.**
> Read the key NAMES to confirm presence. A decoded value lives in scrollback,
> in shell history, and in whatever captured the session — and rotating a key
> because it was pasted into a chat is an avoidable afternoon.

## Configuration checklist

- [ ] `CORS_ORIGINS` and `FRONTEND_URL` both name your exact front-end origin,
      scheme and port included.
- [ ] `DEBUG` is `false` and `ENVIRONMENT` names the right environment.
- [ ] The generator has been run, so no key still holds its template
      placeholder. Confirm by key name, never by decoding a value.
- [ ] The three Fernet-shaped keys are Fernet-shaped, not hex.
- [ ] The PII hash salt and the master key were generated at provisioning —
      both are one-way doors.
- [ ] Every secret in the table above is present. Confirm by key name.
- [ ] If `JWT_ALGORITHM` is `RS256`, both halves of the key pair are set.
- [ ] If `AEGIS_DB_USE_APP_ROLE` is `true`, `AEGIS_APP_DATABASE_URL` is set and
      the role exists in the database.
- [ ] The licence is mounted from a secret, and no image contains one.
- [ ] `AEGIS_BOOTSTRAP_ADMIN_EMAILS` names someone, on a fresh database.
- [ ] The four encryption keys are backed up somewhere that survives the
      cluster, and you know which of them is unrecoverable.

---

_Next: [11.4 — The runtime and its nodes](04-the-runtime-and-its-nodes.md)_
