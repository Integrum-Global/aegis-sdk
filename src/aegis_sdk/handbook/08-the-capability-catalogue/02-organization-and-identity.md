# 08.2 — Organisation and identity

This chapter enumerates everything that answers **who exists** and **who may
act**. It is the foundation of the catalogue: a trust chain anchors to a role, an
envelope scopes to a unit, an agent links to a role, and knowledge is cleared
against the clearance a role holds. Nothing above this layer means anything
without it.

Two distinct things live here and they are easy to conflate. The **organisation
model** — units, roles, teams — is a description of the business: it persists,
it is addressed positionally, and it exists whether or not anyone is employed.
The **identity model** — users, credentials, SSO, permissions — is about the
humans and machines that authenticate. A role is a seat; a user is an occupant;
the seat exists first and outlives every occupant.

**Get the organisation model right before anything else, because every control
in 08.5 attaches to it.**

## Organisations

The tenant boundary. Everything else in this catalogue exists inside exactly one
organisation, and no call crosses that line.

| capability     | what it does                                                               |
| -------------- | -------------------------------------------------------------------------- |
| **Create**     | Stand up a new tenant with its own units, roles, agents and evidence       |
| **List / get** | Enumerate organisations your principal is a member of                      |
| **Membership** | A user may belong to several; one is active per session                    |
| **Switch**     | Move the active session to another organisation you are a member of        |
| **Settings**   | Per-organisation configuration — see [08.7](07-evidence-and-operations.md) |

Entry points: `sdk:aegis_sdk.standup.organizations.OrganizationsModule` for the
create/get/list path, and
`sdk:aegis_sdk.modules.auth_users.AuthUsersModule` for membership and switching.

Operations: `api:POST /api/v1/organizations` · `api:GET /api/v1/organizations` ·
`api:GET /api/v1/organizations/{id}` ·
`api:GET /api/v1/auth/me/organizations` ·
`api:POST /api/v1/auth/me/switch-org`

```python
org = await client.organizations.create(
    name="Northwind Logistics",
    slug="northwind",
)

memberships = await client.auth_users.auth_organizations()
await client.auth_users.auth_switch_org(organization_id=org["id"])
```

> ⛔ **An organisation is the isolation boundary, not a folder.** Two
> organisations on one deployment share no knowledge, no agents, no trust chains
> and no evidence. Creating a second organisation to separate two departments
> gives you two estates that cannot cooperate — use units for that, and read
> [06.3](../06-architecture/03-the-governed-organization.md) before deciding.

## Units — the containment tree

Units are departments and teams: the containers that give the organisation its
shape. They nest, they carry posture ceilings, and they are what an isolation
domain is drawn around.

| capability                             | what it does                                                                               |
| -------------------------------------- | ------------------------------------------------------------------------------------------ |
| **Create / update / delete**           | Standard record lifecycle on a unit                                                        |
| **Tree**                               | The whole hierarchy in one call, rather than walked one parent at a time                   |
| **Roots**                              | The top-level units, for rendering or for starting a walk                                  |
| **Ancestors / children / descendants** | Relative navigation from any unit                                                          |
| **Move**                               | Re-parent a unit; the addresses of everything beneath it are recomputed                    |
| **Summary**                            | A rolled-up view of one unit — counts, roles, agents                                       |
| **Validate**                           | Check the hierarchy for structural problems before relying on it                           |
| **Posture ceiling**                    | Cap the autonomy of every agent beneath this unit — see [08.5](05-governance-and-trust.md) |
| **Isolation domains**                  | Declare which parts of the tree may not see one another                                    |

Entry point: `sdk:aegis_sdk.standup.units.OrganizationUnitsModule` for the basic
lifecycle; `sdk:aegis_sdk.modules.org_standup.OrgStandupModule` carries the tree,
navigation, move, ceiling and isolation surface.

Operations: `api:POST /api/v1/organization-units` ·
`api:GET /api/v1/organization-units` ·
`api:GET /api/v1/organization-units/tree` ·
`api:GET /api/v1/organization-units/roots` ·
`api:GET /api/v1/organization-units/validate` ·
`api:GET /api/v1/organization-units/{id}` ·
`api:GET /api/v1/organization-units/{id}/ancestors` ·
`api:GET /api/v1/organization-units/{id}/children` ·
`api:GET /api/v1/organization-units/{id}/descendants` ·
`api:GET /api/v1/organization-units/{id}/summary` ·
`api:POST /api/v1/organization-units/{id}/move` ·
`api:GET /api/v1/organization-units/{id}/posture-ceiling` ·
`api:PUT /api/v1/organization-units/{id}/posture-ceiling` ·
`api:GET /api/v1/organization-units/isolation-domains` ·
`api:PUT /api/v1/organization-units/isolation-domains` ·
`api:DELETE /api/v1/organization-units/{id}`

```python
tree = await client.org_standup.get_unit_tree()
issues = await client.org_standup.validate_hierarchy()

await client.org_standup.move_unit(
    unit_id=treasury_id,
    new_parent_id=finance_id,
)
```

**The failure mode is a move you do not re-validate.** Re-parenting recomputes
positional addresses beneath the moved unit, and an envelope or a trust chain
written against the old address is now attached to a path that no longer
describes the reporting line. Nothing errors — the records are still valid. Call
`validate_hierarchy` after any structural change, and read the result before
declaring the re-organisation done.

## Roles — the accountability anchors

A role is a position, not a person. It persists across occupants, it is what an
agent is linked to, and it is the anchor every trust chain terminates at.

| capability                   | what it does                                                                |
| ---------------------------- | --------------------------------------------------------------------------- |
| **Create / update / delete** | Standard record lifecycle                                                   |
| **Hierarchy**                | The reporting tree, distinct from the unit containment tree                 |
| **Reporting chain**          | Everyone above a given role, in order                                       |
| **Direct reports**           | Everyone immediately beneath it                                             |
| **Assign / unassign user**   | Seat a human in the role, or vacate it                                      |
| **Link / unlink agent**      | Bind an agent to the role's authority                                       |
| **Constraints**              | The envelope that bounds this role — see [08.5](05-governance-and-trust.md) |
| **Validate**                 | Check one role's structural integrity                                       |
| **Without agents**           | Find roles that have no agent linked — the coverage gap query               |

Entry points: `sdk:aegis_sdk.standup.roles.OrganizationRolesModule` for
create/get/list, `sdk:aegis_sdk.modules.roles.RolesModule` for the
agent/user-linking surface, and `sdk:aegis_sdk.modules.org_standup.OrgStandupModule`
for the reporting navigation.

Operations: `api:POST /api/v1/organization-roles` ·
`api:GET /api/v1/organization-roles` ·
`api:GET /api/v1/organization-roles/{id}` ·
`api:PUT /api/v1/organization-roles/{id}` ·
`api:DELETE /api/v1/organization-roles/{id}` ·
`api:GET /api/v1/organization-roles/without-agents` ·
`api:GET /api/v1/organization-roles/{id}/reporting-chain` ·
`api:GET /api/v1/organization-roles/{id}/direct-reports` ·
`api:GET /api/v1/organization-roles/{id}/constraints` ·
`api:GET /api/v1/organization-roles/{id}/validate` ·
`api:POST /api/v1/organization-roles/{id}/assign-user` ·
`api:POST /api/v1/organization-roles/{id}/unassign-user` ·
`api:POST /api/v1/organization-roles/{id}/link-agent` ·
`api:POST /api/v1/organization-roles/{id}/unlink-agent` ·
`api:GET /api/v1/roles/hierarchy` · `api:GET /api/v1/roles/{id}/agents` ·
`api:GET /api/v1/roles/{id}/users`

The `/roles` family is an alias twin of `/organization-roles` carrying the same
record through a shorter path, and it publishes its own full CRUD surface:
`api:GET /api/v1/roles` · `api:POST /api/v1/roles` ·
`api:GET /api/v1/roles/{id}` · `api:PUT /api/v1/roles/{id}` ·
`api:DELETE /api/v1/roles/{id}` · `api:POST /api/v1/roles/{id}/agents` ·
`api:DELETE /api/v1/roles/{id}/agents/{agent_id}` ·
`api:POST /api/v1/roles/{id}/users` ·
`api:DELETE /api/v1/roles/{id}/users/{user_id}`

**The two families address the same records**, so a role created through one is
visible through the other. Pick one and use it consistently — code that mixes
them works correctly and reads as though two different things are being managed.

```python
uncovered = await client.org_standup.get_roles_without_agents()

chain = await client.org_standup.get_reporting_chain(role_id=controller_id)
reports = await client.org_standup.get_direct_reports(role_id=cfo_id)

await client.org_standup.assign_user_to_role(
    role_id=controller_id,
    user_id=user["id"],
)
```

> ⚠ **The containment tree and the reporting tree are different trees.** A role
> lives inside a unit (containment) and reports to another role (reporting), and
> the two do not have to agree — a matrixed specialist sits in one department and
> reports into another. Authority and trust follow the **reporting** chain. Code
> that walks the unit tree to compute authority produces a plausible answer that
> is wrong for every matrixed role in the organisation.

## Teams

A lighter-weight grouping than a unit: a working group with members, used where
you need collaboration structure without a new node in the containment tree.

| capability              | what it does              |
| ----------------------- | ------------------------- |
| **Create / get / list** | Standard record surface   |
| **Add member**          | Attach a user to the team |

Entry point: `sdk:aegis_sdk.standup.teams.TeamsModule`.

Operations: `api:POST /api/v1/teams` · `api:GET /api/v1/teams` ·
`api:GET /api/v1/teams/{id}` · `api:POST /api/v1/teams/{id}/members`

## Users

The humans. A user authenticates, holds permissions, occupies zero or more roles,
and belongs to one or more organisations.

| capability                   | what it does                                           |
| ---------------------------- | ------------------------------------------------------ |
| **Create / update / delete** | Standard record lifecycle                              |
| **List / get**               | Enumerate the directory                                |
| **Me**                       | The authenticated principal, as the deployment sees it |
| **Reset password**           | Administrative credential reset                        |
| **Permissions**              | What this principal may do — see RBAC below            |

Entry point: `sdk:aegis_sdk.modules.auth_users.AuthUsersModule`.

Operations: `api:POST /api/v1/users` · `api:GET /api/v1/users` ·
`api:GET /api/v1/users/{id}` · `api:PUT /api/v1/users/{id}` ·
`api:DELETE /api/v1/users/{id}` · `api:GET /api/v1/users/me` ·
`api:POST /api/v1/users/{id}/reset-password`

```python
me = await client.auth_users.users_me()
directory = await client.auth_users.users_list(limit=100)
```

## Authentication and sessions

How a principal proves who it is. Two credential kinds, and they are not
interchangeable — [04.3](../04-the-api-surface/03-credentials-and-keys.md) owns
the distinction in full.

| capability         | what it does                                                   |
| ------------------ | -------------------------------------------------------------- |
| **Login / logout** | Exchange credentials for a session bearer token                |
| **Refresh**        | Extend a session without re-presenting the password            |
| **Register**       | Self-service account creation, where the deployment permits it |
| **Me**             | Which principal the presented credential resolves to           |
| **Verify email**   | Complete the email-confirmation step                           |
| **Start trial**    | Onboarding entry point for a new tenant                        |

Entry point: `sdk:aegis_sdk.auth.client.AuthModule`.

Operations: `api:POST /api/v1/auth/login` · `api:POST /api/v1/auth/logout` ·
`api:POST /api/v1/auth/refresh` · `api:POST /api/v1/auth/register` ·
`api:GET /api/v1/auth/me` · `api:GET /api/v1/auth/verify-email/{token}` ·
`api:POST /api/v1/onboarding/start-trial`

```python
token = await client.auth.login(email="ops@example.com", password="<secret>")
principal = await client.auth.get_current_user()
```

**`api:GET /api/v1/auth/me` is the first call to make when anything looks
wrong.** A deployment pointed at the wrong environment, and a credential
resolving to a principal you did not expect, both look exactly like a correct
setup until you ask. Establish which principal you are before debugging anything
downstream.

## API keys

Machine credentials, for integrations and unattended work.

| capability          | what it does                                           |
| ------------------- | ------------------------------------------------------ |
| **Create**          | Mint a key; the secret is returned once and not again  |
| **List / get**      | Enumerate keys and their metadata, never their secrets |
| **Update**          | Change a key's description or scope set                |
| **Regenerate**      | Rotate the secret, keeping the key record              |
| **Revoke / delete** | Withdraw a key immediately                             |

Entry point: `sdk:aegis_sdk.auth.client.AuthModule` — the key surface lives
alongside login.

Operations: `api:POST /api/v1/api-keys` · `api:GET /api/v1/api-keys` ·
`api:GET /api/v1/api-keys/{id}` · `api:PATCH /api/v1/api-keys/{id}` ·
`api:DELETE /api/v1/api-keys/{id}` ·
`api:POST /api/v1/api-keys/{id}/regenerate`

```python
created = await client.auth.create_api_key(
    name="nightly-reconciliation",
    scopes=["objectives:read", "artifacts:read"],
)
# created carries the secret exactly once — store it now
```

> ⛔ **An API key cannot reach a persona-gated route, and no scope configuration
> changes that.** Some surfaces require a human session because the decision they
> record is a human's. Widening a key's scopes to clear a refusal on one of those
> is the wrong fix — the probe in [08.1](01-how-to-read-this-catalogue.md) is how
> you tell the two refusal kinds apart on your own deployment.

## Single sign-on

Federated identity, where the organisation's own provider is the source of truth
for who may log in.

| capability                              | what it does                                            |
| --------------------------------------- | ------------------------------------------------------- |
| **List providers**                      | Which SSO provider types this deployment supports       |
| **Create / update / delete connection** | Configure a provider for this organisation              |
| **Initiate**                            | Begin an OIDC-style sign-in flow                        |
| **SAML initiate**                       | Begin a SAML sign-in flow                               |
| **Link account**                        | Bind an existing local user to a federated identity     |
| **Identities**                          | Enumerate the federated identities bound to a principal |

Entry point: `sdk:aegis_sdk.modules.auth_users.AuthUsersModule`.

Operations: `api:GET /api/v1/sso/providers` ·
`api:GET /api/v1/sso/connections` ·
`api:POST /api/v1/sso/connections` ·
`api:GET /api/v1/sso/connections/{id}` ·
`api:PUT /api/v1/sso/connections/{id}` ·
`api:DELETE /api/v1/sso/connections/{id}` ·
`api:GET /api/v1/sso/initiate/{provider}` ·
`api:GET /api/v1/sso/saml/initiate/{provider}` ·
`api:GET /api/v1/sso/auth/{provider}` · `api:POST /api/v1/sso/link` ·
`api:GET /api/v1/sso/identities`

## Invitations

Bringing a new human into an existing organisation.

| capability | what it does                                                  |
| ---------- | ------------------------------------------------------------- |
| **Create** | Issue an invitation, returning a token to deliver out of band |
| **List**   | Outstanding invitations and their states                      |
| **Accept** | Redeem an invitation and join the organisation                |

Operations: `api:POST /api/v1/invitations` · `api:GET /api/v1/invitations` ·
`api:POST /api/v1/invitations/{id}/accept`

## RBAC — permissions and platform roles

Distinct from organisation roles, and the distinction matters. An **organisation
role** is a seat in the business with authority and an envelope. An **RBAC role**
is a bundle of permissions that decides which API operations a principal may
call. A user has both, and they answer different questions.

| capability                  | what it does                                            |
| --------------------------- | ------------------------------------------------------- |
| **List permissions**        | Every permission the platform defines                   |
| **List / get roles**        | The permission bundles available                        |
| **Add / remove permission** | Change what a bundle grants                             |
| **Delete role**             | Retire a bundle                                         |
| **Get user permissions**    | The effective permission set for one principal          |
| **Check permission**        | Ask directly whether a principal may perform one action |

Entry point: `sdk:aegis_sdk.modules.governance.GovernanceModule`.

Operations: `api:GET /api/v1/rbac/permissions` · `api:GET /api/v1/rbac/roles` ·
`api:GET /api/v1/rbac/roles/{id}` · `api:POST /api/v1/rbac/roles/{id}` ·
`api:DELETE /api/v1/rbac/roles/{id}` ·
`api:DELETE /api/v1/rbac/roles/{id}/{permission}` ·
`api:GET /api/v1/rbac/users/{id}` ·
`api:POST /api/v1/rbac/check-permission` · `api:GET /api/v1/auth/permissions`

```python
allowed = await client.governance.check_permission(
    user_id=user["id"],
    permission="objectives:create",
)
effective = await client.governance.get_user_permissions(user_id=user["id"])
```

**The failure mode is assuming one gate.** A call can be refused because RBAC
does not grant the permission, _or_ because the envelope bounds the action, _or_
because clearance does not reach the data. Three independent controls, three
different fixes. `check_permission` answers only the first — a `True` from it is
not a prediction that the call will succeed.

## Compiling and deploying an organisation

The organisation you describe and the organisation that runs are two artifacts,
and compilation is what turns the first into the second. This is the surface that
generates agents, trust chains and constraints in bulk rather than one at a time.

| capability                | what it does                                               |
| ------------------------- | ---------------------------------------------------------- |
| **Validate**              | Check a described structure before committing to it        |
| **Preview**               | See what a compilation would produce, without producing it |
| **Compile**               | Turn the described organisation into its runtime form      |
| **Deploy**                | Put a compiled organisation into service                   |
| **Deployment status**     | Where a deploy has reached                                 |
| **Generate agents**       | Create the role agents the structure implies               |
| **Generate trust chains** | Create the delegation chains the reporting tree implies    |
| **Generate constraints**  | Create the envelopes the structure implies                 |
| **Templates**             | Prebuilt organisation shapes to start from                 |
| **Import YAML**           | Build an organisation from a declarative file              |
| **Rollback**              | Return to the previous deployed structure                  |
| **Verify integration**    | Confirm the deployed structure is internally consistent    |

Entry point: `sdk:aegis_sdk.modules.org_standup.OrgStandupModule`.

Operations: `api:POST /api/v1/organization-builder/validate` ·
`api:POST /api/v1/organization-builder/preview` ·
`api:POST /api/v1/organization-builder/compile` ·
`api:POST /api/v1/organization-builder/deploy` ·
`api:GET /api/v1/organization-builder/deployment-status` ·
`api:POST /api/v1/organization-builder/generate-agents` ·
`api:POST /api/v1/organization-builder/generate-trust-chains` ·
`api:POST /api/v1/organization-builder/generate-constraints` ·
`api:GET /api/v1/organization-builder/templates` ·
`api:GET /api/v1/organization-builder/templates/{id}` ·
`api:POST /api/v1/organization-builder/import-yaml` ·
`api:POST /api/v1/organization-builder/rollback/{id}` ·
`api:GET /api/v1/organization-builder/verify-integration`

```python
issues = await client.org_standup.validate_structure()
preview = await client.org_standup.preview_compilation()
result = await client.org_standup.compile_organization()
await client.org_standup.generate_trust_chains()
```

**This is the surface an architect uses most and reaches for last.** The
temptation is to create units and roles one call at a time, then wonder why no
agent has a trust chain. Generation is a deliberate step: the structure does not
produce its runtime objects until you ask it to, and a structurally perfect
organisation with no generated chains runs nothing.

## Ontology

The vocabulary layer — what this organisation calls its own concepts. A preset
adapts the platform's generic nouns to an industry's.

| capability              | what it does                         |
| ----------------------- | ------------------------------------ |
| **List presets**        | The vocabularies available           |
| **Apply preset**        | Adopt one for this organisation      |
| **Get / update config** | Read or adjust the active vocabulary |

Entry point: `sdk:aegis_sdk.standup.ontology.OntologyModule`.

Operations: `api:GET /api/v1/ontology/presets` ·
`api:POST /api/v1/ontology/preset/{id}` ·
`api:GET /api/v1/ontology/config/{id}` ·
`api:PUT /api/v1/ontology/config/{id}`

## Summary — what this chapter covered

| area               | entry point                                               | scale              |
| ------------------ | --------------------------------------------------------- | ------------------ |
| Organisations      | `standup.organizations` · `modules.auth_users`            | 3 + membership ops |
| Units              | `standup.units` · `modules.org_standup`                   | 16 operations      |
| Roles              | `standup.roles` · `modules.roles` · `modules.org_standup` | 26 operations      |
| Teams              | `standup.teams`                                           | 4 operations       |
| Users              | `modules.auth_users`                                      | 7 operations       |
| Auth and sessions  | `auth.client`                                             | 9 operations       |
| API keys           | `auth.client`                                             | 6 operations       |
| SSO                | `modules.auth_users`                                      | 11 operations      |
| Invitations        | `modules.auth_users`                                      | 3 operations       |
| RBAC               | `modules.governance`                                      | 8 operations       |
| Compile and deploy | `modules.org_standup`                                     | 13 operations      |
| Ontology           | `standup.ontology`                                        | 4 operations       |

---

_Next: [08.3 — Agents and execution](03-agents-and-execution.md)_
