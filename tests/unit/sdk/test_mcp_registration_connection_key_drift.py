"""The SDK's connection-key set is ONE definition, not a literal that drifts.

``aegis_sdk/modules/mcp.py`` carries ``MCP_CONNECTION_KEYS`` (the SDK's own
mirror of the server's set — mirrored rather than imported, because
``aegis_sdk`` is a standalone package that must not depend on the platform's
source). ``update_registration`` did not use it: it tested a HAND-WRITTEN
``("url", "headers", "command")``, which had already lost ``transport`` and
``type``.

That drift is not cosmetic here, because the guard it feeds is the client-side
pre-flight for a mix the server refuses: a config naming ``mcpServerId`` while
also carrying inline connection settings. With the literal, a config whose ONLY
inline key was ``transport`` or ``type`` read as "reference only" and was sent,
so the caller got a server 422 instead of the local refusal that names the
mistake. Two definitions of "connection key" is the defect; the module's own
constant, consumed here, is the fix.

The set is pinned BEHAVIOURALLY rather than by reading the source, so a future
literal that re-drops a key reds this file instead of passing it.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


def _mcp() -> Any:
    """Import the MCP surface, failing THIS test when it is absent."""
    try:
        from aegis_sdk.modules import mcp
    except ImportError as exc:  # pragma: no cover - the RED state
        pytest.fail(f"the installed SDK has no MCP surface: {exc}")
    return mcp


HOLDER = "holder-agent-1"
REG_ID = "reg-1"

REGISTRATION_ROW: dict[str, Any] = {
    "id": REG_ID,
    "agent_id": HOLDER,
    "tool_type": "mcp",
    "name": "shared-filesystem",
    "description": "Shared filesystem MCP server",
    "config": "{}",
    "is_enabled": False,
    "created_at": "2026-09-17T00:00:00Z",
}


@pytest.fixture
def http() -> MagicMock:
    return MagicMock()


def module(http_client: MagicMock) -> Any:
    return _mcp().McpModule(http_client)


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectionKeySetIsSingleDefinition:
    async def test_every_connection_key_is_seen_by_the_both_forms_guard(self, http):
        """FALSIFYING RESULT: with a drifted literal this does NOT raise.

        ``transport`` and ``type`` are connection settings the resolver lets a
        binding's own value win with (``resolve_mcp_server_references``), so a
        config carrying one BESIDE ``mcpServerId`` is the mixed form the server
        refuses. Asserted per key rather than over the whole set at once: a
        single failing key must name itself, and a sum over the set would pass
        while one key was missing.
        """
        for key, value in (("transport", "sse"), ("type", "http")):
            http.request = AsyncMock(return_value=REGISTRATION_ROW)

            with pytest.raises(ValueError, match="mcpServerId"):
                await module(http).update_registration(
                    HOLDER, REG_ID, config={"mcpServerId": REG_ID, key: value}
                )

            assert not http.request.called, (
                f"{key!r} was not read as a connection key: the drifted literal "
                f"let the mixed config reach the server, which refuses it — so "
                f"the caller gets a 422 instead of this local refusal."
            )

    async def test_the_module_constant_is_the_one_consumed(self, http):
        """The set the guard reads IS the module's declared set, not a copy.

        Pinned by effect: every key the module DECLARES must be one the guard
        reacts to. A literal that omits a declared key reds here naming it,
        which is the drift this file exists to catch.
        """
        declared = _mcp().MCP_CONNECTION_KEYS
        assert declared, "the module declares no connection keys at all"

        for key in declared:
            http.request = AsyncMock(return_value=REGISTRATION_ROW)

            with pytest.raises(ValueError, match="mcpServerId"):
                await module(http).update_registration(
                    HOLDER, REG_ID, config={"mcpServerId": REG_ID, key: "placeholder"}
                )

            assert not http.request.called, f"declared key {key!r} reached the wire"

    async def test_a_non_connection_key_beside_a_reference_is_still_allowed(self, http):
        """The control — the guard must not be a blanket refusal on any key.

        ``allowed_tools`` is a per-tool GRANT, deliberately not inheritable and
        deliberately not a connection key. A reference config carrying one is the
        ordinary reference form and must keep going through, so an over-broadened
        set (the failure direction opposite to the drift) is caught here.
        """
        http.request = AsyncMock(return_value=REGISTRATION_ROW)

        await module(http).update_registration(
            HOLDER, REG_ID, config={"mcpServerId": REG_ID, "allowed_tools": ["echo"]}
        )

        assert http.request.called
