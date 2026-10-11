# settings.py DOX

## Purpose

- Own the `settings.py` helper module.
- This module defines settings models, defaults, validation, and serialization.
- Keep this file-level DOX profile synchronized with `settings.py` because this directory is intentionally flat.

## Ownership

- `settings.py` owns the runtime implementation.
- `settings.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `Settings` (`TypedDict`)
- `PartialSettings` (`Settings`)
- `FieldOption` (`TypedDict`)
- `SettingsField` (`TypedDict`)
- `SettingsSection` (`TypedDict`)
- `ModelProvider` (`ProvidersFO`)
- `SettingsOutputAdditional` (`TypedDict`)
- `SettingsOutput` (`TypedDict`)
- Top-level functions:
- `get_default_value(name: str, value: T) -> T`: Load setting value from .env with A0_SET_ prefix, falling back to default.
- `_ensure_option_present(options: list[OptionT] | None, current_value: str | None) -> list[OptionT]`: Ensure the currently selected value exists in a dropdown options list.
- `_is_valid_timezone(value: str) -> bool`
- `_normalize_timezone_setting(value: Any, default: str=...) -> str`
- `_normalize_time_format(value: Any, default: str=...) -> str`
- `_normalize_ui_control_visibility(value: Any) -> dict[str, dict[str, bool]]`
- `_resolve_runtime_timezone(setting_value: str, browser_timezone: str | None=...) -> str`
- `_timezone_options() -> list[FieldOption]`
- `convert_out(settings: Settings) -> SettingsOutput`
- `_get_api_key_field(settings: Settings, provider: str, title: str) -> SettingsField`
- `convert_in(settings: Settings) -> Settings`
- `get_settings() -> Settings`
- `reload_settings() -> Settings`
- `set_runtime_settings_snapshot(settings: Settings) -> None`
- `version_cache_scope(version: str | None = None)`: Reuse only the Git version within one synchronous operation, expiring inherited copies on exit.
- `set_settings(settings: Settings, apply: bool=..., browser_timezone: str | None=...)`
- `set_settings_delta(delta: dict, apply: bool=...)`
- `merge_settings(original: Settings, delta: dict) -> Settings`
- `normalize_settings(settings: Settings) -> Settings`
- `_adjust_to_version(settings: Settings, default: Settings)`
- `_load_sensitive_settings(settings: Settings)`
- `_read_settings_file() -> Settings | None`
- `_write_settings_file(settings: Settings)`
- `_remove_sensitive_settings(settings: Settings)`
- `_write_sensitive_settings(settings: Settings)`
- `get_default_settings() -> Settings`
- `_apply_timezone_setting(previous: Settings | None, browser_timezone: str | None=...) -> None`
- `_apply_settings(previous: Settings | None, browser_timezone: str | None=...)`
- `_env_to_dict(data: str)`
- `_dict_to_env(data_dict)`
- `set_root_password(password: str)`
- `get_runtime_config(set: Settings)`
- Notable constants/configuration names: `T`, `PASSWORD_PLACEHOLDER`, `API_KEY_PLACEHOLDER`, `TIMEZONE_AUTO`, `TIME_FORMAT_12H`, `TIME_FORMAT_24H`, `UI_CONTROL_VISIBILITY_DEFAULTS`, `SETTINGS_FILE`.

## Runtime Contracts

- Settings reads use `models.get_api_key_raw()` to preserve complete key lists without advancing runtime rotation or persisting keys synthesized by runtime hooks. Masking, authentication reloads, and intentional clearing retain their existing behavior.
- `ui_control_visibility` accepts dynamic `canvas:<surface-id>` entries as well as built-in controls, normalizes device values to booleans (default shown), and preserves choices for temporarily unavailable plugins.

- `file_browser_max_text_size_mb` persists the instance-wide text-editing limit, default 10 MiB and normalized to 1–100. FileBrowser reads it directly so its scoped settings API can update it without restarting or reinitializing agents.
- `file_browser_max_transfer_size_mb` independently persists the Files transfer limit, default 100 MiB, normalized to a positive integer without an upper ceiling. It does not change Backup & Restore or WebSocket limits.

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, network calls, subprocess/runtime control, model calls, WebSocket state, plugin state, settings/state persistence, secret handling, scheduler state.
- Imported dependency areas include: `base64`, `hashlib`, `helpers`, `helpers.notification`, `helpers.print_style`, `helpers.providers`, `helpers.secrets`, `json`, `models`, `os`, `pytz`, `re`, `subprocess`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `TypeVar`, `files.get_abs_path`, `dotenv.get_dotenv_value`, `opts.insert`, `str.strip`, `_is_valid_timezone`, `str.strip.lower`, `_normalize_timezone_setting`, `SettingsOutput`, `get_default_settings`, `_ensure_option_present`, `_resolve_runtime_timezone`, `get_default_secrets_manager`, `get_settings`, `get_settings_for_prompt`, `normalize_settings`, `_load_sensitive_settings`, `deepcopy`, `settings.copy`, `_write_settings_file`, `reload_settings`, `set_settings`, `initialize_agent`.
- Applying settings refreshes active context configs while preserving each subordinate agent's own profile.
- `version_cache_scope()` eagerly resolves or accepts a Git version in a task-local
  scope. Settings application and persisted-chat loading reuse it while retaining
  per-agent normalization, credential reads, and initialization hooks. Nested scopes
  restore their parent even on failure. Each scope clears its cache on exit so
  inherited task contexts cannot retain or repopulate an expired version; reads
  outside an active scope resolve the version afresh.
- Applying settings starts a deferred `MCPConfig.update(...)` with the current `mcp_servers` string when global MCP server settings change.
- `get_settings()` retains normalize-on-read behavior. Prompt-building callers
  explicitly use `get_settings_for_prompt()` to reuse one task-local snapshot
  within each `Agent.prepare_prompt()` call.
- Explicit reloads also refresh an active prompt snapshot.
- `max_consecutive_unusable_responses` defaults to `5` and controls the cost circuit breaker for malformed or repeated main-model outputs.
- `ui_control_visibility` stores validated mobile and desktop visibility flags for the project selector, clock, connection status, context-window usage indicator, and right canvas rail; missing or malformed values fall back per device.
- The Global default-profile selector lists only globally available profiles.
  A currently configured unavailable profile remains visible with an explicit
  unavailable label so settings can round-trip it truthfully, except that the
  exact `default` utility profile is never offered as a selectable option.
- Legacy settings that still name the hidden `default` utility profile normalize
  to `agent0`, so newly created chats always start with a selectable profile.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_settings_cache.py`
  - `tests/test_settings_api_keys.py`
  - `tests/test_settings_mcp.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_document_query_plugin.py`
  - `tests/test_download_toast_regressions.py`
  - `tests/test_fasta2a_client.py`
  - `tests/test_mcp_handler_multimodal.py`
  - `tests/test_model_config_api_keys.py`
  - `tests/test_model_config_project_presets.py`
  - `tests/test_oauth_static.py`
  - `tests/test_subagent_profiles.py`

## Child DOX Index

No child DOX files.

`file_browser_max_extract_size_mb` (default100 MiB) and `file_browser_max_archive_entries` (default1000) are independently configurable positive integers without upper ceilings. They govern File Browser archive operations, not Backup & Restore.
