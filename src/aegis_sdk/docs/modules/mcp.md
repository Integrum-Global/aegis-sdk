# MCP Module

The `McpModule` (`client.mcp`) registers MCP servers and attaches them to agents.

**Read this first, because it is the thing the method names do not tell you: registration and binding are two separate acts with two separate bodies.** Registering a server stores its endpoint and credential and attaches it to nobody. An agent receives a server's tools only when a _binding_ references that registration. This is why `register_server` defaults `is_enabled` to `False` — a registration is storage, not an attachment.

## Access

```python
from aegis_sdk import AgenticOSClient

async with AgenticOSClient.from_env() as client:
    mcp = client.mcp
```

## Routes

| Method                                                                                                                                       | Route                                                | Returns                 |
| -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ----------------------- |
| `register_server(holder_agent_id, *, name, description, url=None, transport=None, headers=None, command=None, extra=None, is_enabled=False)` | `POST /api/v1/agents/{holder_agent_id}/tools`        | `McpRegistration`       |
| `list_registrations(holder_agent_id)`                                                                                                        | `GET /api/v1/agents/{holder_agent_id}/tools`         | `list[McpRegistration]` |
| `get_registration(holder_agent_id, registration_id)`                                                                                         | `GET /api/v1/agents/{holder_agent_id}/tools`         | `McpRegistration`       |
| `update_registration(holder_agent_id, registration_id, ...)`                                                                                 | `PUT /api/v1/agents/{holder_agent_id}/tools/{id}`  | `McpRegistration`       |
| `delete_registration(holder_agent_id, registration_id)`                                                                                      | `DELETE /api/v1/agents/{holder_agent_id}/tools/{id}` | `None`                  |
| `bind(agent_id, registration_id, *, name, description, allowed_tools=None, allow_all_tools=False, is_enabled=True)`                          | `POST /api/v1/agents/{agent_id}/tools`               | `McpBinding`            |
| `bind_inline(agent_id, *, name, description, url=None, transport=None, headers=None, command=None, ...)`                                     | `POST /api/v1/agents/{agent_id}/tools`               | `McpBinding`            |
| `list_bindings(agent_id)`                                                                                                                    | `GET /api/v1/agents/{agent_id}/tools`                | `list[McpBinding]`      |
| `unbind(agent_id, binding_id)`                                                                                                               | `DELETE /api/v1/agents/{agent_id}/tools/{id}`        | `None`                  |


There is no by-id read route. `get_registration` is a **filtered list**, and it raises `NotFoundError` when no registration with that id is stored on that agent — it does not return `None`, so a truthiness check is the wrong shape for it.

## The two binding forms

`bind` attaches a stored server **by reference**. It emits `config = {"mcpServerId": registration_id, ...grant}` and nothing else.

**There is deliberately no way to pass `url`, `headers` or `command` to `bind`.** Those parameters do not exist on it. A row carrying a reference _and_ inline connection settings is refused with `422`, so offering them would be offering a body that cannot succeed. Use `bind_inline` for a self-contained server.

Prefer the reference form. Rotate the credential on the registration once and every referencing agent follows. An inline binding is a copy: rotating a registration will never reach it, because it never read one.

Both forms are bindings and both appear in `list_bindings()`. `McpBinding.is_reference` says which one you have.

```python
registration = await client.mcp.register_server(
    holder_agent_id,
    name="issue-tracker",
    description="Reads and files issues",
    url="https://mcp.example.com/sse",
    transport="sse",
)

binding = await client.mcp.bind(
    agent_id,
    registration.id,
    name="issue-tracker",
    description="Reads and files issues",
    allowed_tools=["list_issues", "create_issue"],
)
```

## Reachability of the endpoint

The endpoint you register is resolved at registration time, and loopback, link-local, cloud-metadata and private ranges are refused. This is deliberate: the platform reaches the server, so an address only _you_ can reach is not one it can use.

The practical consequence, stated plainly because it surprises people: **an MCP server running on your own machine cannot be registered.** Expose it at an address the deployment can reach.

## The grant belongs to the binding

`allowed_tools` and `allow_all_tools` are properties of the **binding**, not of the registration, and are never inherited from one. Two agents may reference the same registration with different grants.

| Grant                  | Effect                                                     |
| ---------------------- | ---------------------------------------------------------- |
| `allowed_tools=[...]`  | Only the named tools are exposed to this agent             |
| `allow_all_tools=True` | Every tool the server offers is exposed                    |
| neither                | No tool is exposed — the binding exists and grants nothing |

## McpRegistration

| Field         | Type   | Description                                                             |
| ------------- | ------ | ----------------------------------------------------------------------- |
| `id`          | `str`  | Registration id — what `bind` takes                                     |
| `agent_id`    | `str`  | The **holder** agent: where the registration is stored, not who uses it |
| `tool_type`   | `str`  | Tool type discriminator                                                 |
| `name`        | `str`  | Registration name                                                       |
| `description` | `str`  | Registration description                                                |
| `config`      | `str`  | Config as the platform emits it, **credentials redacted**               |
| `is_enabled`  | `bool` | Defaults to `False` on creation                                         |
| `created_at`  | `str`  | Creation timestamp                                                      |

| Property      | Returns       | Description                              |
| ------------- | ------------- | ---------------------------------------- |
| `config_dict` | `dict`        | Parsed view of `config`                  |
| `url`         | `str \| None` | The endpoint, if the config carries one  |
| `transport`   | `str \| None` | The transport, if the config carries one |

Nothing here implies a secret is readable — `config` arrives already redacted.

## McpBinding

| Field         | Type   | Description                                           |
| ------------- | ------ | ----------------------------------------------------- |
| `id`          | `str`  | Binding id — what `unbind` takes                      |
| `agent_id`    | `str`  | The agent this server is attached to                  |
| `tool_type`   | `str`  | Tool type discriminator                               |
| `name`        | `str`  | Binding name                                          |
| `description` | `str`  | Binding description                                   |
| `config`      | `str`  | Config as the platform emits it, credentials redacted |
| `is_enabled`  | `bool` | Defaults to `True` on binding                         |
| `created_at`  | `str`  | Creation timestamp                                    |

| Property            | Returns             | Description                                         |
| ------------------- | ------------------- | --------------------------------------------------- |
| `is_reference`      | `bool`              | `True` when this binding points at a registration   |
| `registration_id`   | `str \| None`       | The referenced registration, when there is one      |
| `allowed_tools`     | `list[str] \| None` | The named grant, if any                             |
| `allow_all_tools`   | `bool`              | Whether every tool is exposed                       |
| `config_dict`       | `dict`              | Parsed view of `config`                             |
| `url` / `transport` | `str \| None`       | Present on an inline binding; absent on a reference |
