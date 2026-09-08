# Aegis SDK

A Python SDK for programmatic access to the Agentic OS platform. Provides async-first APIs for managing agents, objectives, sessions, trust chains, and billing.

**Version**: 1.0.0

## Installation

**Not on PyPI.** `pip install aegis-sdk` installs an unrelated third-party
package (a different company's on-premise PII detection tool), not this SDK.
This SDK ships as part of `agentic-os` (`pyproject.toml`), which is not yet
published to PyPI either. Install from source:

```bash
# From a local checkout of this repo
pip install -e .

# Or directly from git (requires repo access)
pip install "git+https://github.com/esperie-enterprise/aegis-sdk.git"
```

The SDK requires Python 3.10+ and depends on `httpx` and `pydantic`.

## Quick Start

```python
import asyncio
import os
from aegis_sdk import AgenticOSClient

async def main() -> None:
    # base_url has no hardcoded default -- set AGENTIC_OS_BASE_URL or pass
    # base_url=... explicitly.
    async with AgenticOSClient(
        base_url=os.environ["AGENTIC_OS_BASE_URL"],
        api_key="sk_live_your_key_here",
    ) as client:
        # List agents
        result = await client.agents.list(status="active")
        for agent in result.items:
            print(f"Agent: {agent.name} ({agent.status})")

        # Create an agent
        agent = await client.agents.create(
            name="Research Assistant",
            agent_type="chat",  # one of: chat, task, pipeline, custom
            model_id=os.environ["AGENTIC_OS_MODEL"],  # never hardcode a model name
            capabilities=["research", "summarization"],
        )

        # Execute the agent
        execution = await client.agents.execute(
            agent.id,
            objective="Research quantum computing and summarize findings",
        )
        print(f"Status: {execution.status}")
        print(f"Result: {execution.result}")

asyncio.run(main())
```

## Authentication

The SDK supports two authentication methods:

1. **API Key** (recommended for programmatic access):
   ```python
   client = AgenticOSClient(api_key="sk_live_your_key_here")
   ```

2. **Email/Password** (for interactive use):
   ```python
   client = AgenticOSClient(base_url="https://aegis.example.com")
   token = await client.auth.login("user@example.com", "password")
   client.set_auth_token(token.access_token)
   ```

3. **Environment Variables**:
   ```bash
   export AGENTIC_OS_API_KEY=sk_live_your_key_here
   export AGENTIC_OS_BASE_URL=https://aegis.example.com
   ```
   ```python
   client = AgenticOSClient.from_env()
   ```

See [authentication.md](authentication.md) for full details.

## SDK Modules

The client provides access to the following module groups:

### Core

| Module | Access | Description |
|--------|--------|-------------|
| `client.auth` | [AuthModule](modules/agents.md) | Login, logout, API key management |
| `client.agents` | [AgentsModule](modules/agents.md) | Agent CRUD, execution, versions, contexts, tools |
| `client.skills` | SkillsModule | Skill CRUD |
| `client.pipelines` | PipelinesModule | Pipeline CRUD and execution |

### Execution

| Module | Access | Description |
|--------|--------|-------------|
| `client.objectives` | [ObjectivesModule](modules/objectives.md) | Objective CRUD, progress, requests |
| `client.requests` | RequestsModule | Request claim, complete, escalate |
| `client.sessions` | [SessionsModule](modules/sessions.md) | Session lifecycle, messages, streaming |

### Trust (EATP)

| Module | Access | Description |
|--------|--------|-------------|
| `client.trust.chains` | [ChainsModule](modules/trust.md) | Trust chain establish, verify, revoke |
| `client.trust.delegations` | [DelegationsModule](modules/trust.md) | Delegation create, revoke |
| `client.trust.postures` | [PosturesModule](modules/trust.md) | Posture get, progression, override |
| `client.trust.audit` | [AuditModule](modules/trust.md) | Audit log queries |

### Revenue

| Module | Access | Description |
|--------|--------|-------------|
| `client.revenue.subscriptions` | [SubscriptionsModule](modules/billing.md) | Subscribe, upgrade, cancel |
| `client.revenue.plans` | [PlansModule](modules/billing.md) | List plans, compare tiers |
| `client.revenue.licenses` | [LicensesModule](modules/billing.md) | License generation, validation |
| `client.revenue.usage` | [UsageModule](modules/billing.md) | Usage tracking |
| `client.revenue.quotas` | [QuotasModule](modules/billing.md) | Quota management |
| `client.revenue.invoices` | [InvoicesModule](modules/billing.md) | Invoice history |

### Advanced

| Module | Access | Description |
|--------|--------|-------------|
| `client.a2a` | A2AModule | Agent-to-agent communication |
| `client.analytics` | AnalyticsModule | Analytics queries |
| `client.connectors` | ConnectorsModule | External connectors |
| `client.notifications` | NotificationsModule | Notification management |
| `client.webhooks` | WebhooksModule | Webhook configuration |
| `client.governance` | GovernanceModule | Governance policies |
| `client.compliance` | ComplianceModule | Compliance checks |
| `client.pools` | PoolsModule | Agent pool management |

## Guides

- [Quick Start](quickstart.md) -- 5-minute getting started guide
- [Authentication](authentication.md) -- API keys, OAuth2, token refresh
- [Streaming](streaming.md) -- SSE streaming for real-time events
- [Error Handling](error-handling.md) -- Exception hierarchy and retry strategies
- [Configuration](configuration.md) -- ClientConfig, environment variables, timeouts

## Code Examples

- [Basic Agent Workflow](../examples/basic_agent_workflow.py) -- Create, execute, monitor agents
- [Streaming Progress](../examples/streaming_progress.py) -- Real-time SSE streaming
- [Trust Chain Management](../examples/trust_chain_management.py) -- EATP trust operations
- [Error Handling Patterns](../examples/error_handling.py) -- Retry, rate limiting, error recovery

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTIC_OS_BASE_URL` | (required, no default) | API base URL |
| `AGENTIC_OS_API_KEY` | -- | API key for authentication |
| `AGENTIC_OS_TIMEOUT` | `30` | Request timeout in seconds |
| `AGENTIC_OS_MAX_RETRIES` | `3` | Maximum retry attempts |
| `AGENTIC_OS_VERIFY_SSL` | `true` | SSL certificate verification |
| `AGENTIC_OS_DEBUG` | `false` | Enable debug logging |
