"""Stand Up a Vertical Example.

Demonstrates the full P0 "stand up a vertical" flow using ONLY typed SDK
methods — no raw ``client._http.request`` calls:

    organization -> unit -> head role -> shadow (delegate) agent
      -> role envelope -> knowledge (create + publish) -> ontology preset
      -> approvals (list + approve)

Every call maps to a verified server route (cited in each module's docstrings).

Prerequisites:
    # NOT on PyPI -- `pip install aegis-sdk` installs an unrelated
    # third-party package. Install from source (see docs/quickstart.md):
    pip install -e .
    export AGENTIC_OS_BASE_URL=https://your-deployment.example.com   # REQUIRED, no default
    export AGENTIC_OS_API_KEY=sk_live_your_key_here
    export AGENTIC_OS_MODEL=<your model id>                          # examples never hardcode one

Session vs API-key callers — read before adapting this file:
    This example authenticates with an API KEY, and creating an organization
    therefore needs no extra step: the server does not rotate a key's
    credentials, and a key's organization is fixed, so every call below runs in
    the organization created on the first line.

    A SESSION (JWT / bearer) caller is different. For one of those, creating an
    organization also switches that session into it and ROTATES the pair: the
    access token the request authenticated with, and the refresh token minted
    alongside it, are revoked immediately — not at their expiry. The SDK does
    NOT adopt the returned token for you. If you lift this example onto a
    session, call ``client.set_auth_token(resp["access_token"])`` with the value
    from ``client.organizations.create(...)`` before sending the next request,
    or that request is rejected with 401.
"""

import asyncio
import os
from typing import Any

from aegis_sdk import AgenticOSClient


async def stand_up_vertical(client: AgenticOSClient) -> dict[str, Any]:
    """Provision a minimal, governed vertical end-to-end.

    Returns a dict of the created resource IDs for inspection.
    """
    # 1. Organization — the tenant root.
    org = await client.organizations.create(
        name="Acme Robotics",
        slug="acme-robotics",
        plan_tier="pro",
    )
    org_id = org["id"]

    # 2. Root unit (department) + its mandatory head role.
    unit = await client.units.create(
        name="Treasury",
        unit_type="department",
        description="Cash and liquidity management",
        default_classification="confidential",
    )
    unit_id = unit["id"]

    head_role = await client.roles.create(
        organization_unit_id=unit_id,
        title="Head of Treasury",
        authority_level=4,
        is_primary_for_unit=True,
    )
    head_role_id = head_role["id"]

    # A working team under the same unit.
    team = await client.teams.create(name="Cash Ops", description="Daily cash desk")

    # 3. A shadow (delegate) agent for the head role — uses the new
    #    is_shadow_agent / shadow_for_user_id / human_role_id /
    #    organization_unit_id fields (bug B fix) and the corrected agent_type
    #    domain (bug A fix).
    agent = await client.agents.create(
        name="Treasury Assistant",
        agent_type="chat",
        workspace_id=org_id,
        model_id=os.environ["AGENTIC_OS_MODEL"],
        system_prompt="You assist the Head of Treasury within policy.",
        capabilities=["cash_forecasting", "reporting"],
        is_shadow_agent=True,
        shadow_for_user_id="user_head_treasury",
        human_role_id=head_role_id,
        organization_unit_id=unit_id,
    )

    # 4. A standing operating envelope defining what the delegate role may do.
    envelope = await client.role_envelopes.create(
        defining_role_id=head_role_id,
        target_role_id=head_role_id,
        constraint_config={
            "financial": {"max_amount": 100_000, "currency": "USD"},
            "operational": {"blocked_actions": ["wire_transfer_external"]},
        },
        status="active",
    )

    # 5. Governing knowledge — create then publish.
    policy = await client.knowledge.create(
        title="Treasury Approval Policy",
        content_markdown="# Approval Policy\nAll wires >$50k require sign-off.",
        knowledge_type="policy",
        path="/treasury/policies/approvals",
        classification="restricted",
    )
    await client.knowledge.publish(policy["id"])

    # 6. Apply a vocabulary preset so the vertical speaks its domain language.
    await client.ontology.apply_preset(org_id, preset_id="finance")

    # 7. Human-on-the-loop: review the pending approval queue and act on it.
    #    NOTE: agents.create returns a typed Agent model (attribute access),
    #    while the standup modules return raw dicts (subscript access).
    pending = await client.approvals.list_pending(agent_id=agent.id, limit=25)
    approved_ids: list[str] = []
    for record in pending.get("records", []):
        await client.approvals.approve(
            record["id"],
            reviewed_by="user_head_treasury",
            reason="Within envelope; policy satisfied.",
        )
        approved_ids.append(record["id"])

    return {
        "organization_id": org_id,
        "unit_id": unit_id,
        "head_role_id": head_role_id,
        "team_id": team["id"],
        "agent_id": agent.id,
        "envelope_id": envelope["id"],
        "knowledge_id": policy["id"],
        "approved_ids": approved_ids,
    }


async def main() -> None:
    async with AgenticOSClient.from_env() as client:
        result = await stand_up_vertical(client)
        print("Vertical provisioned:", result)


if __name__ == "__main__":
    asyncio.run(main())
