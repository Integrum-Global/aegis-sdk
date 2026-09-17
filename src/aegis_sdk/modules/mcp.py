"""
MCP (Model Context Protocol) SDK module.

MCP is how an agent is given tools that live on a server somewhere else. The
platform models that in two SEPARATE things, and keeping them separate is the
whole point of this module:

* a **registration** — the endpoint and its credential, stored ONCE. On the
  wire it is an ordinary agent-tool row with ``tool_type="mcp"`` whose config
  holds the connection settings and NO ``mcpServerId``. Its natural home is a
  DISABLED row on a holder agent, so the holder does not itself receive the
  server's tools (see :meth:`McpModule.register_server`).
* a **binding** — that server attached to ONE agent. A binding by REFERENCE
  carries ``config["mcpServerId"]`` naming a registration and inherits only
  the connection keys from it; a binding INLINE carries its own copy of the
  connection settings and no reference.

Why the split is worth the extra verb: N agents bound to one server keep ONE
copy of that server's endpoint and credential between them, so rotating the
credential on the registration reaches every agent that references it with no
per-agent edit. A binding that copies the connection settings re-creates the
duplication invisibly — rotating the registration silently would NOT reach it.

⛔ THE TWO ARE MUTUALLY EXCLUSIVE ON THE WIRE, AND THE SERVER ENFORCES IT.
A row carrying ``mcpServerId`` alongside its own ``url`` / ``headers`` /
``command`` is refused with **422** (``_reject_inline_connection_on_reference``).
That is why :meth:`McpModule.bind` offers no way to pass connection settings
and :meth:`McpModule.bind_inline` offers no way to pass a reference: the two
legal bodies are named, and neither can drift into the other.

AUTH: the routes here are gated on ``agents:read`` for the reads and
``agents:update`` for every write, on the agent the row hangs off. An API-key
principal therefore needs the agent permissions, not just a valid key.

Contract note: registration rows are agent-tool rows, and the platform emits
their ``config`` as a JSON STRING with credentials redacted (a read needs less
privilege than a write, so a credential never round-trips out). Both models
below carry that string verbatim and expose a parsed view through
``config_dict``, so a caller can read the SHAPE of a stored config without
being handed a secret that would not have been readable anyway.
"""

from __future__ import annotations

import builtins
import json
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict

from .._http import encode_path_param
from .._tolerant import TolerantModel
from ..exceptions import NotFoundError

if TYPE_CHECKING:
    from .._http import HTTPClient


#: Config key naming a shared server registration a binding references
#: (``aegis.services.mcp_tool_binding.MCP_SERVER_REF_KEY``). Its presence, and
#: nothing else, is what makes a row a REFERENCE rather than an inline binding
#: or a registration. Mirrored rather than imported: ``aegis_sdk`` is a
#: standalone package and must not depend on the platform's source.
MCP_SERVER_REF_KEY = "mcpServerId"

#: The keys a reference inherits from its registration, mirroring
#: ``aegis.services.mcp_tool_binding.MCP_CONNECTION_KEYS``. Deliberately
#: CONNECTION-ONLY: the per-tool grant (``allowed_tools`` / ``allow_all_tools``)
#: is not inheritable, so a reference can never widen its own authorization by
#: pointing at a permissively-granted registration. A binding's grant is its
#: own, which is why :meth:`McpModule.bind` takes one.
MCP_CONNECTION_KEYS = ("url", "transport", "type", "headers", "command")

#: Connection keys that are also DESTINATIONS. A config has to name one of
#: these or there is nothing to connect to.
_DESTINATION_KEYS = ("url", "command")

#: The fields ``AgentToolResponse`` emits for every agent-tool row, in its own
#: order. Both models below carry exactly these, which a paired test derives
#: from the server's response model rather than trusting this comment.
_AGENT_TOOL_FIELDS = (
    "id",
    "agent_id",
    "tool_type",
    "name",
    "description",
    "config",
    "is_enabled",
    "created_at",
)


def _parse_config(raw: object) -> dict[str, Any]:
    """Parse an agent-tool ``config`` blob into a dict, never raising.

    The wire emits ``config`` as a JSON string (``AgentToolResponse.config`` is
    declared ``str``). A blob that will not parse is reported as EMPTY rather
    than as an error: this is a convenience view over a field the caller also
    receives verbatim, and a hard failure here would make one malformed row
    unreadable through the whole list.
    """
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return raw if isinstance(raw, dict) else {}


class McpRegistration(TolerantModel):
    """ONE stored MCP server: its endpoint and credential, kept in one place.

    A registration is STORAGE, not an attachment. Nothing is bound to an agent
    by creating one, and no agent receives this server's tools until a binding
    references it (:meth:`McpModule.bind`). Hold it on a holder agent and leave
    it disabled, which is why :meth:`McpModule.register_server` defaults
    ``is_enabled`` to ``False``.

    ``config`` is carried as the string the platform emits — credentials
    redacted — so nothing here implies a secret is readable. Use
    :attr:`config_dict` for the parsed view, :attr:`url` for the endpoint.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    agent_id: str
    """The HOLDER agent's id — where the registration is stored, not who uses it."""
    tool_type: str
    name: str
    description: str
    config: str
    is_enabled: bool
    created_at: str

    @property
    def config_dict(self) -> dict[str, Any]:
        """The stored config, parsed. Credentials inside it are redacted."""
        return _parse_config(self.config)

    @property
    def url(self) -> str | None:
        """The registered endpoint, when the registration is HTTP-transported."""
        value = self.config_dict.get("url")
        return value if isinstance(value, str) else None

    @property
    def transport(self) -> str | None:
        """The registered transport, when one was named."""
        value = self.config_dict.get("transport") or self.config_dict.get("type")
        return value if isinstance(value, str) else None


class McpBinding(TolerantModel):
    """One MCP server attached to ONE agent.

    Two forms, and :attr:`is_reference` says which:

    * **reference** (``config["mcpServerId"]`` set) — the connection settings
      live on a registration and are inherited at load time. This is the form
      to prefer; rotate the credential once and every referencing agent follows.
    * **inline** (no reference, connection settings on the row itself) — a
      self-contained binding. Legal, and the right shape for a genuine one-off,
      but it is a copy: rotating a registration will not reach it, because it
      never read one.

    Both are BINDINGS and both appear in :meth:`McpModule.list_bindings`. A row
    cannot be both at once — the platform refuses that body with 422.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    agent_id: str
    tool_type: str
    name: str
    description: str
    config: str
    is_enabled: bool
    created_at: str

    @property
    def config_dict(self) -> dict[str, Any]:
        """The binding's own config, parsed. Credentials inside it are redacted."""
        return _parse_config(self.config)

    @property
    def registration_id(self) -> str | None:
        """The registration this binding references, or ``None`` when inline."""
        value = self.config_dict.get(MCP_SERVER_REF_KEY)
        return value.strip() if isinstance(value, str) and value.strip() else None

    @property
    def is_reference(self) -> bool:
        """Whether this binding inherits its connection settings."""
        return self.registration_id is not None

    @property
    def allowed_tools(self) -> builtins.list[str] | None:
        """The per-tool grant, when the binding names one.

        This is the BINDING's grant and is never inherited from a registration,
        so a reference cannot widen its own authorization by pointing at a
        permissively-granted one. ``None`` means no allow-list was named, which
        is not the same as "all tools" — see :attr:`allow_all_tools`.
        """
        value = self.config_dict.get("allowed_tools")
        if isinstance(value, list):
            return [v for v in value if isinstance(v, str)]
        return None

    @property
    def allow_all_tools(self) -> bool:
        """Whether the binding explicitly opted in to every tool the server advertises."""
        return bool(self.config_dict.get("allow_all_tools"))


class McpModule:
    """
    MCP server registration and agent binding.

    The division, in one line: ``register_server`` STORES a server,
    :meth:`bind` ATTACHES it. Creating a registration gives no agent anything.

    Methods:
        - register_server(): Store an MCP server's endpoint and credential
        - list_registrations(): The stored servers on a holder agent
        - get_registration(): One stored server by id
        - update_registration(): Rename, re-enable, or replace a stored config
        - delete_registration(): Remove a stored server
        - bind(): Attach a stored server to an agent BY REFERENCE
        - bind_inline(): Attach a self-contained server to an agent
        - list_bindings(): The MCP servers attached to an agent
        - unbind(): Detach one

    Example:
        >>> from aegis_sdk import AgenticOSClient
        >>> client = AgenticOSClient(
        ...     api_key="your-api-key", base_url="https://your-aegis-instance"
        ... )
        >>>
        >>> # Store the endpoint and credential once, on a holder agent.
        >>> reg = await client.mcp.register_server(
        ...     holder_agent_id,
        ...     name="shared-filesystem",
        ...     description="Read-only filesystem access",
        ...     url="https://mcp.internal.example.com/rpc",
        ...     headers={"Authorization": "Bearer ..."},
        ... )
        >>>
        >>> # Attach it to as many agents as need it -- one copy of the secret.
        >>> await client.mcp.bind(
        ...     agent_id, reg.id, name="shared-filesystem",
        ...     description="Read-only filesystem access",
        ...     allowed_tools=["read_file"],
        ... )
    """

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize the MCP module with an HTTP client."""
        self._http = http_client

    # ------------------------------------------------------------------
    # Registrations -- "store the endpoint and credential once"
    # ------------------------------------------------------------------

    async def register_server(
        self,
        holder_agent_id: str,
        *,
        name: str,
        description: str,
        url: str | None = None,
        transport: str | None = None,
        headers: dict[str, str] | None = None,
        command: str | None = None,
        extra: dict[str, Any] | None = None,
        is_enabled: bool = False,
    ) -> McpRegistration:
        """
        Store an MCP server's endpoint and credential as a registration row.

        This creates an agent-tool row of ``tool_type="mcp"`` on
        ``holder_agent_id`` via ``POST /api/v1/agents/{holder_agent_id}/tools``.
        The row carries the connection settings and NO reference key, which is
        exactly what makes it a registration other agents can point at.

        ``is_enabled`` defaults to ``False`` DELIBERATELY. A registration is
        storage, and the natural way to hold one is a disabled row on a holder
        agent so that agent does not itself receive the server's tools.
        Defaulting to enabled would silently grant the holder agent every tool
        of every server it merely stores. Disabling a registration is NOT a
        kill-switch for the bindings referencing it — delete it, or rotate the
        credential, to cut them off.

        Args:
            holder_agent_id: The agent that HOLDS the registration. Not
                necessarily any agent that uses it.
            name: Registration name, 1-100 characters.
            description: Registration description, 1-500 characters.
            url: Endpoint of an HTTP-transported server.
            transport: Transport name, when you want one recorded explicitly.
            headers: Request headers, credentials included. Redacted on the way
                back out — this is a one-way trip.
            command: Command of a stdio-transported server.
            extra: Additional non-connection config keys to store alongside.
            is_enabled: Whether the holder agent should itself receive this
                server's tools. Default ``False``; see above.

        Returns:
            McpRegistration: the stored row, with its config redacted.

        Raises:
            ValueError: If neither ``url`` nor ``command`` is given — a
                registration with no destination resolves to nothing on every
                read, so it is refused before any request.
        """
        config: dict[str, Any] = dict(extra or {})
        if url is not None:
            config["url"] = url
        if transport is not None:
            config["transport"] = transport
        if headers is not None:
            config["headers"] = headers
        if command is not None:
            config["command"] = command

        if not any(config.get(key) for key in _DESTINATION_KEYS):
            raise ValueError(
                "register_server() requires url= (HTTP transport) or command= "
                "(stdio transport). A registration with no destination cannot "
                "be resolved when an agent binds to it, so it would be stored "
                "and then silently do nothing."
            )
        if MCP_SERVER_REF_KEY in config:
            raise ValueError(
                f"register_server() cannot store {MCP_SERVER_REF_KEY!r}. That key "
                f"is what makes a row a BINDING rather than a registration; use "
                f"bind() to attach a server to an agent."
            )

        payload = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(holder_agent_id)}/tools",
            json_data={
                "tool_type": "mcp",
                "name": name,
                "description": description,
                "config": config,
                "is_enabled": is_enabled,
            },
        )
        return McpRegistration(**payload)

    async def list_registrations(self, holder_agent_id: str) -> builtins.list[McpRegistration]:
        """
        List the MCP servers stored on ``holder_agent_id``.

        Returns the rows that are NOT references — a reference is something an
        agent is BOUND to, so it is not itself a registration another agent can
        point at. Non-MCP rows on the same agent are excluded.

        Args:
            holder_agent_id: The agent holding the registrations.

        Returns:
            The stored registrations, in the order the platform returns them.
            May be empty.
        """
        rows = await self._mcp_rows(holder_agent_id)
        return [
            McpRegistration(**row)
            for row in rows
            if McpBinding(**row).registration_id is None
        ]

    async def get_registration(
        self, holder_agent_id: str, registration_id: str
    ) -> McpRegistration:
        """
        Resolve one stored registration by id.

        There is no single-tool ``GET`` route, so this reads the holder agent's
        tools and selects — the extra round-trip is the platform's, not a
        choice made here.

        Args:
            holder_agent_id: The agent holding the registration.
            registration_id: The registration row's id, as returned by
                :meth:`register_server`.

        Returns:
            McpRegistration: the matching row.

        Raises:
            NotFoundError: No registration with that id is stored on that agent.
        """
        registrations = await self.list_registrations(holder_agent_id)
        for registration in registrations:
            if registration.id == registration_id:
                return registration
        raise NotFoundError(
            f"No MCP registration {registration_id!r} on agent "
            f"{holder_agent_id!r}. Check the holder agent — a registration lives "
            f"on the agent that STORES it, not on the agents that reference it."
        )

    async def update_registration(
        self,
        holder_agent_id: str,
        registration_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_enabled: bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> McpRegistration:
        """
        Rename, re-enable, or replace a stored registration's connection config.

        ``config`` REPLACES the stored connection settings key-wise, so it must
        be the WHOLE blob and not a fragment. That is why there are no loose
        ``url=`` / ``headers=`` keywords here: the platform merges a submitted
        config against the stored one per key and DELETES any non-secret key the
        submission omits, so a keyword that supplied only ``url`` would silently
        drop the stored ``headers`` — and a credential-carrying header is only
        restored when the destination is UNCHANGED, which changing the url is
        not. Supply the complete config, credentials included.

        Omitting ``config`` entirely leaves the stored blob untouched, so a
        rename is not a destructive round-trip.

        Args:
            holder_agent_id: The agent holding the registration.
            registration_id: The registration row's id.
            name: New name, 1-100 characters.
            description: New description, 1-500 characters.
            is_enabled: Whether the holder agent should receive this server's
                tools.
            config: The complete replacement connection config.

        Returns:
            McpRegistration: the updated row, with its config redacted.

        Raises:
            ValueError: If no field is supplied. The route's body is required and
                answers 400 for an empty one, so this is refused before any
                request.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if is_enabled is not None:
            body["is_enabled"] = is_enabled
        if config is not None:
            body["config"] = config

        if not body:
            raise ValueError(
                "update_registration() requires at least one field to change "
                "(name, description, is_enabled or config) -- the route's "
                "UpdateToolRequest body is required and an empty one answers 400."
            )

        payload = await self._http.request(
            "PUT",
            f"/api/v1/agents/{encode_path_param(holder_agent_id)}/tools/"
            f"{encode_path_param(registration_id)}",
            json_data=body,
        )
        return McpRegistration(**payload)

    async def delete_registration(
        self, holder_agent_id: str, registration_id: str
    ) -> None:
        """
        Delete a stored registration.

        This is how bindings referencing it are cut off. Disabling the
        registration does NOT do it — a registration is not required to be
        enabled for its references to resolve.

        Args:
            holder_agent_id: The agent holding the registration.
            registration_id: The registration row's id.
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/agents/{encode_path_param(holder_agent_id)}/tools/"
            f"{encode_path_param(registration_id)}",
        )

    # ------------------------------------------------------------------
    # Bindings -- "attach that stored server to THIS agent"
    # ------------------------------------------------------------------

    async def bind(
        self,
        agent_id: str,
        registration_id: str,
        *,
        name: str,
        description: str,
        allowed_tools: builtins.list[str] | None = None,
        allow_all_tools: bool = False,
        is_enabled: bool = True,
    ) -> McpBinding:
        """
        Attach a stored MCP server to an agent BY REFERENCE.

        Emits ``config = {"mcpServerId": registration_id, ...grant}`` — the
        reference form, and nothing else. There is deliberately no way to pass
        ``url`` / ``headers`` / ``command`` here: the platform refuses a row
        carrying a reference AND inline connection settings with 422, so
        offering them would be offering a body that cannot succeed. Use
        :meth:`bind_inline` for a self-contained server.

        The grant belongs to the BINDING and is never inherited from the
        registration, so pointing at a permissively-granted registration cannot
        widen this agent's authorization.

        Args:
            agent_id: The agent the server is attached to.
            registration_id: The id of the registration to reference.
            name: Binding name, 1-100 characters.
            description: Binding description, 1-500 characters.
            allowed_tools: Remote tool names this binding authorizes. Omit for
                no allow-list.
            allow_all_tools: Explicit opt-in to every tool the server
                advertises. Default ``False``. ``allowed_tools`` and this are
                both grants; a binding with neither authorizes nothing, which
                is a decision rather than an omission.
            is_enabled: Whether the binding is live. Default ``True``.

        Returns:
            McpBinding: the created binding, ``is_reference`` True.

        Raises:
            ValueError: If ``registration_id`` is empty. A binding with no
                reference and no inline connection is neither form.
        """
        reference = registration_id.strip() if isinstance(registration_id, str) else ""
        if not reference:
            raise ValueError(
                "bind() requires the registration_id of a stored MCP server. "
                "Call register_server() first, or use bind_inline() for a "
                "server whose connection settings live on the binding itself."
            )

        config: dict[str, Any] = {MCP_SERVER_REF_KEY: reference}
        config.update(self._grant(allowed_tools, allow_all_tools))

        payload = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/tools",
            json_data={
                "tool_type": "mcp",
                "name": name,
                "description": description,
                "config": config,
                "is_enabled": is_enabled,
            },
        )
        return McpBinding(**payload)

    async def bind_inline(
        self,
        agent_id: str,
        *,
        name: str,
        description: str,
        url: str | None = None,
        transport: str | None = None,
        headers: dict[str, str] | None = None,
        command: str | None = None,
        extra: dict[str, Any] | None = None,
        allowed_tools: builtins.list[str] | None = None,
        allow_all_tools: bool = False,
        is_enabled: bool = True,
    ) -> McpBinding:
        """
        Attach a SELF-CONTAINED MCP server to an agent, with no registration.

        The other legal polarity: connection settings on the binding, and NO
        reference. Correct for a genuine one-off, and the wrong default —
        nothing here is shared, so rotating a credential means editing every
        binding that carries it.

        Prefer :meth:`bind` when more than one agent will use the same server.

        Args:
            agent_id: The agent the server is attached to.
            name: Binding name, 1-100 characters.
            description: Binding description, 1-500 characters.
            url: Endpoint of an HTTP-transported server.
            transport: Transport name, when you want one recorded explicitly.
            headers: Request headers, credentials included.
            command: Command of a stdio-transported server.
            extra: Additional non-connection config keys to store alongside.
            allowed_tools: Remote tool names this binding authorizes.
            allow_all_tools: Explicit opt-in to every tool the server advertises.
            is_enabled: Whether the binding is live. Default ``True``.

        Returns:
            McpBinding: the created binding, ``is_reference`` False.

        Raises:
            ValueError: If neither ``url`` nor ``command`` is given — an inline
                binding with no destination resolves to nothing at load time.
        """
        config: dict[str, Any] = dict(extra or {})
        if url is not None:
            config["url"] = url
        if transport is not None:
            config["transport"] = transport
        if headers is not None:
            config["headers"] = headers
        if command is not None:
            config["command"] = command
        config.update(self._grant(allowed_tools, allow_all_tools))

        if not any(config.get(key) for key in _DESTINATION_KEYS):
            raise ValueError(
                "bind_inline() requires url= (HTTP transport) or command= "
                "(stdio transport). Without a destination the binding resolves "
                "to no session and the agent comes up without the tools."
            )

        payload = await self._http.request(
            "POST",
            f"/api/v1/agents/{encode_path_param(agent_id)}/tools",
            json_data={
                "tool_type": "mcp",
                "name": name,
                "description": description,
                "config": config,
                "is_enabled": is_enabled,
            },
        )
        return McpBinding(**payload)

    async def list_bindings(self, agent_id: str) -> builtins.list[McpBinding]:
        """
        List the MCP servers attached to ``agent_id``.

        Returns BOTH forms — reference and inline — each carrying
        :attr:`McpBinding.is_reference` so the caller can tell them apart
        without re-parsing the config.

        ⚠ A registration held on a HOLDER agent appears here too: it is an
        ``mcp`` row attached to that agent. That is why registrations are held
        DISABLED. Use :meth:`list_registrations` for the storage view.

        Args:
            agent_id: The agent whose bindings to list.

        Returns:
            The bindings, in the order the platform returns them. May be empty.
        """
        return [McpBinding(**row) for row in await self._mcp_rows(agent_id)]

    async def unbind(self, agent_id: str, binding_id: str) -> None:
        """
        Detach a binding from an agent.

        Removes the BINDING row only. The registration it referenced — if any —
        is untouched, so other agents keep working.

        Args:
            agent_id: The agent the binding hangs off.
            binding_id: The binding row's id.
        """
        await self._http.request(
            "DELETE",
            f"/api/v1/agents/{encode_path_param(agent_id)}/tools/"
            f"{encode_path_param(binding_id)}",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _mcp_rows(self, agent_id: str) -> builtins.list[dict[str, Any]]:
        """Every ``tool_type="mcp"`` row on an agent, and nothing else.

        The route returns every tool the agent has, functions and APIs
        included, so the filter is applied here rather than being left to the
        caller.
        """
        rows = await self._http.request(
            "GET", f"/api/v1/agents/{encode_path_param(agent_id)}/tools"
        )
        return [
            row
            for row in (rows or [])
            if isinstance(row, dict) and row.get("tool_type") == "mcp"
        ]

    @staticmethod
    def _grant(
        allowed_tools: builtins.list[str] | None, allow_all_tools: bool
    ) -> dict[str, Any]:
        """The per-tool grant keys, omitted entirely when not asked for.

        Absent rather than ``None`` on purpose: the platform reads a MISSING
        grant as "authorize nothing" (fail-closed) and a present one as the
        operator's decision, so sending ``allow_all_tools: False`` explicitly
        would state a choice this caller never made.
        """
        grant: dict[str, Any] = {}
        if allowed_tools is not None:
            grant["allowed_tools"] = list(allowed_tools)
        if allow_all_tools:
            grant["allow_all_tools"] = True
        return grant


__all__ = [
    "MCP_CONNECTION_KEYS",
    "MCP_SERVER_REF_KEY",
    "McpBinding",
    "McpModule",
    "McpRegistration",
]
