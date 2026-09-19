# tool.py DOX

## Purpose

- Own the `tool.py` helper module.
- This module defines the base agent tool class and response contract.
- Keep this file-level DOX profile synchronized with `tool.py` because this directory is intentionally flat.

## Ownership

- `tool.py` owns the runtime implementation.
- `tool.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `coerce_bool(value: Any, default: bool) -> bool` (module-level function shared by tools and plugins)
- `Response` (no explicit base class)
- `Tool` (no explicit base class)
  - `async execute(self, **kwargs) -> Response`
  - `async set_progress(self, content: str | None)`
  - `add_progress(self, content: str | None)`
  - `async before_execution(self, **kwargs)`
  - `async after_execution(self, response: Response, **kwargs)`
  - `get_log_object(self)`
  - `nice_key(self, key: str)`

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- `Tool` defines `execute(...)`.
- Observed side-effect areas: settings/state persistence.
- Imported dependency areas include: `abc`, `agent`, `dataclasses`, `helpers.extension`, `helpers.print_style`, `helpers.strings`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `self.get_log_object`, `sanitize_string`, `self.agent.hist_add_tool_result`, `self.agent.context.log.log`, `key.split`, `join`, `call_extensions_async`, `response.message.strip`, `uuid.uuid4`, `PrintStyle`, `PrintStyle.stream`, `words.capitalize`, `word.lower`, `self.nice_key`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_a0_connector_prompt_gating.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_default_prompt_budget.py`
  - `tests/test_dirty_json.py`
  - `tests/test_document_query_plugin.py`
  - `tests/test_fastmcp_openapi_security.py`
  - `tests/test_host_browser_connector.py`
  - `tests/test_mcp_handler_multimodal.py`

## Child DOX Index

No child DOX files.
