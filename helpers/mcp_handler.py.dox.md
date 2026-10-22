# mcp_handler.py DOX

## Purpose

- Own the `mcp_handler.py` helper module.
- This module loads global and project-scoped MCP server configuration and exposes MCP tools to agents.
- Keep this file-level DOX profile synchronized with `mcp_handler.py` because this directory is intentionally flat.

## Ownership

- `mcp_handler.py` owns the runtime implementation.
- `mcp_handler.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `MCPTool` (`Tool`)
  - `get_log_object(self) -> LogItem`
  - `async execute(self, **kwargs)`
  - `async before_execution(self, **kwargs)`
  - `async after_execution(self, response: Response, **kwargs)`
- `MCPServerRemote` (`BaseModel`)
  - `get_error(self) -> str`
  - `get_log(self) -> str`
  - `get_tools(self) -> List[dict[str, Any]]`
  - `get_all_tools(self) -> List[dict[str, Any]]`
  - `has_tool(self, tool_name: str) -> bool`
  - `async call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult`
  - `update(self, config: dict[str, Any]) -> 'MCPServerRemote'`
  - `async initialize(self) -> 'MCPServerRemote'`
- `MCPServerLocal` (`BaseModel`)
  - `get_error(self) -> str`
  - `get_log(self) -> str`
  - `get_tools(self) -> List[dict[str, Any]]`
  - `get_all_tools(self) -> List[dict[str, Any]]`
  - `has_tool(self, tool_name: str) -> bool`
  - `async call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult`
  - `update(self, config: dict[str, Any]) -> 'MCPServerLocal'`
  - `async initialize(self) -> 'MCPServerLocal'`
- `MCPConfig` (`BaseModel`)
  - `get_instance(cls) -> 'MCPConfig'`
  - `clear_project_instances(cls)`
  - `parse_config_string(cls, config_str: str) -> List[Dict[str, Any]]`
  - `merge_config_strings(cls, global_config: str, project_config: str) -> tuple[List[Dict[str, Any]], str]`
  - `get_project_instance(cls, project_name: str | None, *, force: bool = False) -> 'MCPConfig'`
  - `refresh_project(cls, project_name: str) -> 'MCPConfig'`
  - `get_for_agent(cls, agent: Any) -> 'MCPConfig'`
  - `wait_for_lock(cls)`
  - `update(cls, config_str: str) -> Any`
  - `normalize_config(cls, servers: Any)`
  - `get_server_log(self, server_name: str) -> str`
  - `get_servers_status(self) -> list[dict[str, Any]]`
  - `get_server_detail(self, server_name: str) -> dict[str, Any]`
  - `is_initialized(self) -> bool`
- `MCPClientBase` (`ABC`)
  - `async update_tools(self) -> 'MCPClientBase'`
  - `has_tool(self, tool_name: str) -> bool`
  - `get_tools(self) -> List[dict[str, Any]]`
  - `async call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> CallToolResult`
  - `get_log(self)`
- `MCPClientLocal` (`MCPClientBase`)
- `CustomHTTPClientFactory` (`ABC`)
- `MCPClientRemote` (`MCPClientBase`)
  - `get_session_id(self) -> Optional[str]`
- Top-level functions:
- `_mcp_get(item: Any, key: str, default: Any=...) -> Any`
- `normalize_name(name: str) -> str`
- `_determine_server_type(config_dict: dict) -> str`: Determine the server type based on configuration, with backward compatibility.
- `_is_streaming_http_type(server_type: str) -> bool`: Check if the server type is a streaming HTTP variant.
- `_split_qualified_tool_name(tool_name: str) -> tuple[str, str]`: Split `server.tool` names while preserving dots inside MCP tool names.
- `_normalize_disabled_tools(value: Any) -> list[str]`: Normalize the optional per-server disabled tool list.
- `_split_stdio_command(command: Any) -> tuple[str, list[str]]`: Split shell-style local MCP command lines into an executable plus leading arguments.
- `_split_stdio_arg_fragment(arg: str) -> list[str]`: Split collapsed option/value argument fragments while preserving obvious single values with spaces.
- `_normalize_stdio_args(value: Any) -> list[str]`: Normalize local MCP argument lists after manager/raw JSON parsing.
- `initialize_mcp(mcp_servers_config: str)`
- Notable constants/configuration names: `DEFAULT_MCP_SERVERS_CONFIG`, `MCP_MEDIA_TOKENS_ESTIMATE`, `MAX_MCP_RESOURCE_TEXT_CHARS`, `MCP_SESSION_CLEANUP_TIMEOUT_SECONDS`, `MCP_OPERATION_TIMEOUT_GRACE_SECONDS`, `T`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- `MCPTool` is a `Tool`.
- `MCPTool` defines `execute(...)`.
- Global MCP configuration remains backed by settings; project MCP configuration is loaded through `helpers.projects` and merged with global config when an active agent context has `context.project`.
- Project-scoped MCP servers overlay global servers by normalized name. The resulting `MCPConfig` cache key is derived from both config strings so project instances refresh when either scope changes.
- Server status and detail responses include `scope`, and MCP tools resolve through `MCPConfig.get_for_agent(agent)` before execution.
- MCP tool names are qualified as `server_name.tool_name`; server names are normalized without dots, and the tool portion may contain dots.
- Agent-facing MCP prompt descriptions filter through the central profile tool
  policy, and `MCPTool.execute()` rechecks the same policy with the explicit MCP
  canonical ID before invocation. Prompt construction uses one fresh policy
  snapshot and omits server sections when none of their tools are allowed.
  `get_tools_prompt(include_tools=False)` returns policy-filtered server context without tool details or an outer protocol wrapper. Responses owns its own framing; blocked-only servers remain absent.
  Server headings are explicitly non-callable groups; each tool heading exposes
  the exact qualified name that Chat Completions must call. Prompt guidance
  treats each allowed-operation description as exhaustive and rejects inferring
  capabilities from names or schemas when no operation matches. Static MCP
  framing is rendered from `prompts/agent.system.mcp_tools.md`,
  `prompts/agent.system.mcp_server.md`, and
  `prompts/agent.system.mcp_tool.md`; this helper supplies the policy-filtered
  server names, exact qualified tool names, descriptions, and schemas.
- `MCPConfig.get_tool()` tries the supplied qualified name first, then restores an advertised Responses alias from the calling agent's name map; names that still do not identify an MCP tool return `None` unchanged for downstream local-tool resolution.
- Servers may define `disabled_tools` as a list of MCP tool names. Disabled tools are omitted from agent-facing prompts, status counts, `has_tool`, and calls, while detail views can still retrieve them through `get_all_tools()` with a `disabled` flag so users can re-enable them.
- Server-specific `init_timeout` and `tool_timeout` override global MCP client timeout settings for list-tools and call-tool operations.
- Local stdio server configs accept either strict MCP JSON (`command: "uvx", args: [...]`) or manager-style command lines (`command: "uvx package"`) and normalize them before spawning the process.
- MCP image and image-resource content is materialized to scoped artifact files and returned both as model-visible image attachments and as path metadata (`attachments`/`media_paths`) for downstream delivery.
- MCP config locks must not be held across awaited server initialization or tool-call operations. Slow or wedged MCP servers must not block status reads, prompt construction, unrelated MCP servers, or later tool calls through the shared config lock.
- MCP client session work runs inside disposable isolated `DeferredTask` workers with an outer timeout. Normal `AsyncExitStack` cleanup is also bounded; if cleanup or transport shutdown does not finish, the operation reports failure or warning while Agent Zero keeps control of the agent loop.
- Server status marks initialized server objects with cached initialization errors as disconnected, even if the config object exists.
- Durable calls pass the actual initialized connection through the session adapter before invoking a tool. Its encrypted descriptor binds the locally configured server fingerprint, InitializeResult identity/capabilities and current advertised tool schemas; recheck ownership after the handshake before dispatch. Credentials remain locally configured and are never exported in descriptors. Legacy callers do not receive the optional durable keyword arguments.
- Shared PostgreSQL tools dispatch through `durable/mcp_broker.py`: an independent actor consumes a fenced one-use send grant, validates the actual server initialize/schema identity, invokes the original MCP call once and retains its real `CallToolResult` in encrypted chunks. Framework-worker loss reuses that receipt; unresolved actor/host loss holds. The database stores only opaque operation/config fingerprints and result refs. Resolved remote headers and local server env exist only in a Fernet-encrypted owner-only local spool, removed after completion; a successor can reconstruct a still-submitted operation only with matching locally configured server custody, using its encrypted shared operation/token descriptor. A running intent never relaunches. Stdio children never receive any `A0_DURABILITY_*` variables, including explicitly configured ones. Legacy direct calls preserve their transport behavior except this credential isolation.
- `validate_durable_session(tool)` reconnects and validates without calling the original tool. Trusted local `sessions.register_reconciler(server, tool, async_callable)` adapters may query a documented server status API and return an actual completed `CallToolResult` or `None`; their source identity is pinned in the descriptor. No reconciler is installed by default. Server annotations/read-only hints never authorize replay. Changed identity/schema/config, unknown effects, transport timeouts and lost outcomes hold.
- A private exception sentinel carries recovery holds through the disposable worker boundary, then restores `RecoveryHeld` on the owning loop. Session cleanup still runs on validation failure; the tool wrapper must not turn an unknown durable outcome into a completed retryable error.
- Observed side-effect areas: filesystem writes, network calls, WebSocket state, settings/state persistence, secret handling.
- Imported dependency areas include: `abc`, `anyio.streams.memory`, `asyncio`, `contextlib`, `datetime`, `helpers`, `helpers.defer`, `helpers.log`, `helpers.print_style`, `helpers.tool`, `httpx`, `json`, `mcp`, `mcp.client.sse`, `mcp.client.stdio`, `mcp.client.streamable_http`, `mcp.shared.message`, `shlex`.

## Key Concepts

- Important called helpers/classes observed in the source: `TypeVar`, `name.strip.lower`, `re.sub`, `Field`, `PrivateAttr`, `threading.Lock`, `DeferredTask`, `_split_qualified_tool_name`, `config_dict.lower`, `server_type.lower`, `MCPConfig.get_instance.is_initialized`, `MCPConfig.get_for_agent`, `projects.validate_project_name`, `projects.load_project_mcp_servers`, `settings.get_settings`, `self.agent.context.log.log`, `str.strip`, `media_artifacts.guess_extension`, `callable`, `self._content_item_dump`, `join`, `Response`, `self.get_log_object`, `self._raw_tool_response`, `additional.pop`, `self._coerce_media_token_estimate`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.
- Keep MCP timeout and cleanup changes covered by deterministic tests that do not require real MCP servers or network credentials.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_mcp_handler_multimodal.py`
  - `tests/test_durable_sessions.py` (real local stdio MCP process; no external server, provider or credentials)
  - `tests/test_tool_policy.py`

## Child DOX Index

No child DOX files.
