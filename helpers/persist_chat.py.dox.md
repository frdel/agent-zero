# persist_chat.py DOX

## Purpose

- Own the `persist_chat.py` helper module.
- This module persists and reloads chat contexts and message artifacts.
- Keep this file-level DOX profile synchronized with `persist_chat.py` because this directory is intentionally flat.

## Ownership

- `persist_chat.py` owns the runtime implementation.
- `persist_chat.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `_fallback_datetime_iso() -> str`
- `_parse_persisted_datetime(value: str | None) -> datetime`
- `get_chat_folder_path(ctxid: str)`: Get the folder path for any context (chat or task).
- `get_chat_msg_files_folder(ctxid: str)`
- `save_tmp_chat(context: AgentContext)`: Save context to the chats folder
- `save_tmp_chats()`: Save all contexts to the chats folder
- `load_tmp_chats()`: Load all contexts from the chats folder
- `_get_chat_file_path(ctxid: str)`
- `chat_file_exists(ctxid: str) -> bool`
- `_convert_v080_chats()`
- `load_json_chats(jsons: list[str])`: Load contexts from JSON strings
- `export_json_chat(context: AgentContext)`: Export context as JSON string
- `remove_chat(ctxid)`: Remove a chat or task context
- `remove_msg_files(ctxid)`: Remove all message files for a chat or task context
- `mark_chat_saved(context: AgentContext) -> None`
- `saved_chat_ids() -> set[str]`
- `_serialize_context(context: AgentContext)`
- `_serialize_agent(agent: Agent)`
- `_serialize_log(log: Log)`
- `_deserialize_context(data)`
- `_deserialize_agent_config(agent_data: dict[str, Any], fallback_config: AgentConfig) -> AgentConfig`
- `_deserialize_agents(agents: list[dict[str, Any]], config: AgentConfig, context: AgentContext) -> Agent`
- `_deserialize_log(data: dict[str, Any]) -> 'Log'`
- `_safe_json_serialize(obj, **kwargs)`
- Notable constants/configuration names: `CHATS_FOLDER`, `LOG_SIZE`, `CHAT_FILE_NAME`, `SAVED_CHAT_CONTEXT_DATA_KEY`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, settings/state persistence, scheduler state.
- Imported dependency areas include: `agent`, `collections`, `datetime`, `helpers`, `helpers.localization`, `helpers.log`, `initialize`, `json`, `typing`, `uuid`.
- Serialized chats store `agent_profile` both at the context level for the main chat and on each serialized agent so subordinate profiles survive server restart.
- Deserialization must rebuild each agent with its serialized profile when present, falling back to the context profile for older chat files.
- Chat loading skips directories that do not contain `chat.json`; malformed existing chat files still report load errors.
- `load_tmp_chats()` reuses one Git version through `settings.version_cache_scope()` for its per-file restoration loop. Each agent still receives normal settings/credential reads and initialization hooks; the scope expires after the load, including failures.
- Chat saves write and fsync a same-directory temporary file, atomically replace `chat.json`, and fsync the directory so an interrupted save cannot truncate the previous chat.
- Contexts are marked with private `SAVED_CHAT_CONTEXT_DATA_KEY` only after a successful save or load from disk so snapshot code can detect deleted chat files without hiding fresh unsaved chats.
- `chat_file_exists(ctxid)` reads the current `chat.json` path so snapshot pruning can confirm a missing file after taking an earlier directory listing.
- Chat and message-file removal reject empty or whitespace-only context IDs before provider or filesystem deletion begins.

## Key Concepts

- Important called helpers/classes observed in the source: `datetime.fromtimestamp.isoformat`, `datetime.fromisoformat`, `files.get_abs_path`, `_get_chat_file_path`, `files.make_dirs`, `_serialize_context`, `_safe_json_serialize`, `files.write_file`, `_convert_v080_chats`, `files.list_files`, `get_chat_folder_path`, `files.delete_dir`, `get_chat_msg_files_folder`, `agent.history.serialize`, `initialize_agent`, `_deserialize_log`, `AgentContext`, `_deserialize_agent_config`, `_deserialize_agents`, `Log`, `log.set_initial_progress`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_api_chat_lifetime.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_persist_chat_log_ids.py`
  - `tests/test_snapshot_parity.py`
  - `tests/test_subagent_profiles.py`
  - `tests/test_tool_action_contracts.py`

## Child DOX Index

No child DOX files.
