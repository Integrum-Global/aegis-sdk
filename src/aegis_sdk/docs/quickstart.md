# Quick Start Guide

Get up and running with the Aegis SDK in 5 minutes.

## 1. Install the SDK

**Not on PyPI, and do NOT `pip install aegis-sdk`.** That name on PyPI belongs
to an **unrelated third-party package** ("on-premise PII detection and masking
for AI applications", published by a different company). Installing it gets you
the wrong software under a right-sounding name.

Install from your checkout of the **SDK repository** — the one you cloned to
get here. Either form gives you `aegis_sdk` and **nothing else** — neither
carries the platform:

```bash
# editable, for working in the repo
pip install -e .

# or a wheel, if you want the artifact
pip install build hatchling
python -m build --wheel .
pip install dist/agentic_os_sdk-*.whl     # the distribution is `agentic-os-sdk`
```

Both read the `pyproject.toml` at the ROOT of the SDK repository. If you have
seen an older instruction naming a path under `packaging/`, it does not apply
there: in the SDK repository that directory ships the test harness and its type
baseline, not a build descriptor, and the command would fail on a fresh clone.

Verify what you installed:

```bash
python -c "import aegis_sdk; print(aegis_sdk.__version__)"
```

> The base install is the whole install: `httpx` and `pydantic`. The
> orchestration subpackage that used to drag a web-server stack in behind
> `import aegis_sdk` is no longer part of this distribution, so there is no
> extra to add and no first-import `ImportError` to work around.

<details>
<summary>Installing the whole platform instead (maintainers only)</summary>

⛔ This applies **only** inside the private platform repository, which is a
different repository and is not the one you cloned; if you do not have it, this
paragraph is not about you. There, `pip install -e .` from the repo root
installs the umbrella distribution, which ships the SDK **and the full server
codebase**. That is the right thing when you are developing the platform and the
wrong thing when you want a client.

</details>

## 2. Authenticate

The SDK talks to the server over JWT (email/password) or an API key.
**Start with JWT** -- it is the only path a brand-new developer has, and it
is what the rest of this guide uses.

```python
import asyncio
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient(base_url="https://aegis.example.com") as client:
        # New account: client.auth.register(email, password, name, organization_name)
        # Existing account:
        token = await client.auth.login("you@example.com", "your_password")
        client.set_auth_token(token.access_token)

        # Verify the client is authenticated. Do NOT use
        # client.auth.get_current_user() for this -- see the warning below.
        agents = await client.agents.list(page_size=1)
        print(f"Authenticated. Organization has {agents.total} agent(s).")

asyncio.run(main())
```

> **The `get_current_user()` pitfall.** `client.auth.get_current_user()` (the
> server's `GET /auth/me`) resolves a real `User` database row by id. It
> works for a JWT-authenticated session, but it is NOT a general
> "is my client set up correctly?" check -- for an API-key principal (§3
> below) there is no user row (the identity is a synthetic
> `api_key:<id>`), so it raises `AuthenticationError: {'code':
> 'UNAUTHORIZED', 'message': 'User not found'}` even with a perfectly valid
> key. `client.agents.list()` (above) works for both a JWT session AND a
> scoped API key, so it is the one verification call that always tells you
> whether you're authenticated -- not whether you happen to be a JWT user.

A brand-new self-service account (`client.auth.register(...)`) is created
with role `developer` (personas `["architect", "user"]`) -- enough to
authenticate, read, create agents, and create objectives (§4-§5), but NOT
enough to mint an API key (§3, which needs `admin`/`executive` persona).
See "A note on access" below.

Also required before §4/§5 will succeed: a **verified email address**.
Registration does not auto-verify one, and this SDK does not yet expose a
verification-flow method -- check with whoever operates your deployment for
how verification is completed there.

Recommended environment-variable setup:

```bash
export AGENTIC_OS_BASE_URL=https://aegis.example.com
```

## 3. Get an API Key (optional -- for machine-to-machine use)

An API key is for scripts and services, not for a human's first login (use
§2 for that). **Minting one requires `admin` or `executive` persona**
(`dependencies=[Depends(require_persona("admin",
"executive"))]`) -- a self-service `developer` account (§2) does NOT have
this (`developer` resolves to `["architect", "user"]`) and gets a 403 on
both `GET /api-keys/scopes` and `POST /api-keys`. There is currently no
self-service path to a key; an operator must first grant you (or the
account) elevated access:

```bash
# Promote an EXISTING user to org owner (org_owner => admin/executive personas)
aegis admin grant-owner --org-id <ORG_ID> --email you@example.com

# Or, bootstrapping a brand-new deployment with no owner yet
aegis admin create-owner --org-id <ORG_ID> --email you@example.com --name "Your Name"
```

Once your account (or the account you're scripting as) holds `admin`/
`executive`, create a key with scopes that actually exist -- the full list is
`GET /api-keys/scopes` (21 scopes). There is no `objectives:*` scope.

```python
import asyncio
from aegis_sdk import AgenticOSClient

async def create_key() -> None:
    async with AgenticOSClient(base_url="https://aegis.example.com") as client:
        token = await client.auth.login("you@example.com", "your_password")
        client.set_auth_token(token.access_token)

        key = await client.auth.create_api_key(
            name="My SDK Key",
            scopes=["agents:read", "agents:write"],
        )
        print(f"API Key created: {key.key_prefix}...")
        # The full key (key.key) is shown ONLY in this response -- store it now.

asyncio.run(create_key())
```

Set it as an environment variable (real keys are prefixed `sk_live_`, never
`aos_`):

```bash
export AGENTIC_OS_API_KEY=sk_live_your_key_here
```

```python
import asyncio
from aegis_sdk import AgenticOSClient

async def main() -> None:
    # Option A: Pass API key directly
    client = AgenticOSClient(api_key="sk_live_your_key_here")

    # Option B: Load from environment variables
    client = AgenticOSClient.from_env()

    # Always close when done, or use async context manager
    await client.close()

asyncio.run(main())
```

**Note:** `client.objectives.*` (§5-§7) currently returns 403 for EVERY API
key, regardless of scope -- those routes gate on persona `"user"`, and an
API-key principal always resolves to `personas: []`. Use
a JWT session (§2), not an API key, for the objectives sections below.

## 4. Create an Agent

Requires (a) a verified email address (`require_verified_email`; not required for an API-key principal, only a
JWT one) and (b) the `agents:create` permission -- the self-service
`developer` role (§2) has it, along with `user`/`operator`/`manager`/
`org_admin`/`org_owner`; `viewer` does
not.

```python
import asyncio
import os
from aegis_sdk import AgenticOSClient, Agent

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        agent: Agent = await client.agents.create(
            name="Research Assistant",
            agent_type="chat",  # one of: chat, task, pipeline, custom
            workspace_id="ws_abc123",  # required by the server — use your workspace's ID
            model_id=os.environ["AGENTIC_OS_MODEL"],  # never hardcode a model name
            system_prompt="You are a research assistant that finds and summarizes information.",
            capabilities=["research", "summarization"],
            description="AI assistant for research tasks",
        )
        print(f"Created agent: {agent.name} (ID: {agent.id})")
        print(f"Status: {agent.status}")
        print(f"Type: {agent.agent_type}")

asyncio.run(main())
```

## 5. Submit an Objective

Objectives are top-level work units that agents work toward. **Use a JWT
session (§2), not an API key** -- see the note in §3.

If `agent_id` is omitted, the server auto-assigns your delegate agent. A
freshly-created custom agent from §4 needs two more steps first: activation
(it starts in `draft` status) and an explicit access grant -- creating an
agent does not by itself grant its creator access to submit objectives
against it. Both are beyond this guide's scope; omit `agent_id` if you just
want something that works.

```python
import asyncio
from aegis_sdk import AgenticOSClient, Objective

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        objective: Objective = await client.objectives.create(
            title="Research quantum computing",
            description="Analyze recent advances in quantum error correction and summarize the top 5 findings.",
            agent_id="agent_abc123",  # Use your agent's ID from step 4
            priority=5,
        )
        print(f"Objective created: {objective.id}")
        print(f"Status: {objective.status}")

asyncio.run(main())
```

## 6. Check Progress

Poll the objective status or stream events in real time:

```python
import asyncio
from aegis_sdk import AgenticOSClient

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        # Poll status
        objective = await client.objectives.get("obj_abc123")
        print(f"Status: {objective.status}")

        # Task-graph-derived progress (NOT client.objectives.get_requests() --
        # that method's own docstring documents it as a KNOWN GAP: no
        # matching backend route exists, and it will 404. get_progress() IS
        # the real, verified route.)
        progress = await client.objectives.get_progress("obj_abc123")
        print(f"  Progress: {progress['overall_progress']}%")

        # Get artifacts produced
        artifacts = await client.objectives.get_artifacts("obj_abc123")
        for artifact in artifacts:
            print(f"  Artifact: {artifact['name']} ({artifact['type']})")

asyncio.run(main())
```

For real-time streaming, see [streaming.md](streaming.md).

## 7. Full Workflow Example

Here is a complete workflow that creates an agent, submits an objective, and monitors progress:

```python
import asyncio
import os
from aegis_sdk import AgenticOSClient, AgenticOSError, NotFoundError

async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        # Verify authentication (agents:read works for both a JWT session
        # and a scoped API key -- see the warning in §2 about
        # get_current_user() for why this call, not that one)
        agents = await client.agents.list(page_size=1)
        print(f"Authenticated. Organization has {agents.total} agent(s).")

        # Create agent
        agent = await client.agents.create(
            name="Data Analyst",
            agent_type="chat",  # one of: chat, task, pipeline, custom
            workspace_id="ws_abc123",  # required by the server — use your workspace's ID
            model_id=os.environ["AGENTIC_OS_MODEL"],  # never hardcode a model name
            capabilities=["analysis", "visualization"],
        )
        print(f"Agent created: {agent.id}")

        # Submit objective
        objective = await client.objectives.create(
            title="Analyze Q4 Sales Data",
            description="Process the Q4 sales data, identify trends, and generate a summary report.",
            agent_id=agent.id,
            priority=5,
            metadata={"department": "sales", "quarter": "Q4"},
        )
        print(f"Objective submitted: {objective.id}")

        # Monitor until complete
        while objective.status not in ("completed", "failed", "cancelled"):
            await asyncio.sleep(5)
            try:
                objective = await client.objectives.get(objective.id)
                print(f"  Status: {objective.status}")
            except NotFoundError:
                print("Objective not found")
                break

        if objective.status == "completed":
            print("Objective completed successfully!")
            artifacts = await client.objectives.get_artifacts(objective.id)
            print(f"Produced {len(artifacts)} artifacts")
        else:
            print(f"Objective ended with status: {objective.status}")

asyncio.run(main())
```

## A note on access

Everything above assumes your account can reach it. A stock deployment's
self-service registration (`client.auth.register(...)`) gives you role
`developer` (personas `["architect", "user"]`) -- deliberately NOT
`org_owner` by default (`allow_self_serve_org_admin=False`,; an operator provisions the first owner
out-of-band). This is enough for everything in §2, §4, §5, §6 and §7 EXCEPT
minting an API key (§3), which needs `admin`/`executive` persona. You will
also need a verified email before §4/§5 succeed (see the note in §2). If you
need an API key:

- Ask whoever operates your deployment to run
  `aegis admin grant-owner --org-id <ORG_ID> --email you@example.com`, or
- For local/dev deployments you control, set
  `AEGIS_ALLOW_SELF_SERVE_ORG_ADMIN=true` before registering (this grants
  `org_owner` directly, skipping `developer`).

## Next Steps

- [Authentication](authentication.md) -- API keys, OAuth2, token management
- [Streaming](streaming.md) -- Real-time SSE event streaming
- [Error Handling](error-handling.md) -- Exception types and retry patterns
- [Agents Module](modules/agents.md) -- Full agent API reference
- [Trust Module](modules/trust.md) -- EATP trust chain management
