# mcp_server.py DOX

## Purpose

- Own the `mcp_server.py` helper module.
- This module serves Agent Zero chats through a dynamic MCP proxy.
- Keep this file-level DOX profile synchronized with `mcp_server.py` because this directory is intentionally flat.

## Ownership

- `mcp_server.py` owns the runtime implementation.
- `mcp_server.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ToolResponse` (`BaseModel`)
- `ToolError` (`BaseModel`)
- `DynamicMcpProxy` (no explicit base class)
  - `get_instance()`
  - `reconfigure(self, token: str)`
- `PureAsgiMcpMiddleware` (no explicit base class)
  - `__init__(self, app: ASGIApp)`
  - `__call__(self, scope: Scope, receive: Receive, send: Send) -> None`
- Top-level functions:
- `async send_message(message: Annotated[str, Field(description='The message to send to the remote Agent Zero Instance', title='message')], attachments: Annotated[list[str], Field(description='Optional: A list of attachments (file paths or web urls) to send to the remote Agent Zero Instance with the message. Default: Empty list', title='attachments')] | None=..., chat_id: Annotated[str, Field(description='Optional: ID of the chat. Used to continue a chat. This value is returned in response to sending previous message. Default: Empty string', title='chat_id')] | None=..., persistent_chat: Annotated[bool, Field(description='Optional: Whether to use a persistent chat. If true, the chat will be saved and can be continued later. Default: False.', title='persistent_chat')] | None=...) -> Annotated[Union[ToolResponse, ToolError], Field(description='The response from the remote Agent Zero Instance', title='response')]`
- `async finish_chat(chat_id: Annotated[str, Field(description='ID of the chat to be finished. This value is returned in response to sending previous message.', title='chat_id')]) -> Annotated[Union[ToolResponse, ToolError], Field(description='The response from the remote Agent Zero Instance', title='response')]`
- `async _run_chat(context: AgentContext, message: str, attachments: list[str] | None=...)`
- Notable constants/configuration names: `_PRINTER`, `SEND_MESSAGE_DESCRIPTION`, `FINISH_CHAT_DESCRIPTION`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, network calls, settings/state persistence, secret handling, scheduler state.
- Imported dependency areas include: `agent`, `asyncio`, `contextvars`, `fastmcp`, `fastmcp.server.http`, `helpers`, `helpers.persist_chat`, `helpers.print_style`, `initialize`, `openai`, `os`, `pydantic`, `starlette.exceptions`, `starlette.middleware`, `starlette.responses`, `starlette.types`.

## Key Concepts

- Important called helpers/classes observed in the source: `PrintStyle`, `contextvars.ContextVar`, `FastMCP`, `mcp_server.tool`, `Field`, `settings.get_settings`, `initialize_agent`, `AgentContext`, `ToolError`, `ToolResponse`, `context.reset`, `AgentContext.remove`, `remove_chat`, `context.communicate`, `threading.RLock`, `self.reconfigure`, `StreamableHTTPSessionManager`, `mcp_server._get_additional_http_routes`, `create_base_app`, `PrintStyle.error`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_default_prompt_budget.py`
  - `tests/test_fasta2a_client.py`
  - `tests/test_ws_security.py`

## Child DOX Index

No child DOX files.
