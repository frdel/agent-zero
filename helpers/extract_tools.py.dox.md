# extract_tools.py DOX

## Purpose

- Own the `extract_tools.py` helper module.
- This module normalizes and repairs model-emitted tool-call JSON.
- Keep this file-level DOX profile synchronized with `extract_tools.py` because this directory is intentionally flat.

## Ownership

- `extract_tools.py` owns the runtime implementation.
- `extract_tools.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `json_parse_dirty(json: str) -> dict[str, Any] | None`
- `extract_tool_request(content: str) -> dict[str, Any] | None`
- `extract_leaked_tool_request(response: str) -> tuple[str, dict[str, Any] | None]`
- `is_misformatted_tool_request(content: str) -> bool`
- `normalize_tool_request(tool_request: Any) -> tuple[str, dict]`
- `extract_json_root_string(content: str) -> str | None`
- `extract_json_root_strings(content: str) -> list[str]`
- `extract_json_object_string(content)`
- `extract_json_string(content)`
- `fix_json_string(json_string)`

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: settings/state persistence.
- Dirty parsing scans complete JSON object roots in prose and prefers the first object that normalizes as a valid tool request for permissive repair and legacy callers.
  Normalization accepts canonical `tool_name`/`tool_args`, legacy `tool`/`args`, native `type="function"` `name`/`parameters`, and a single-item `actions` wrapper; malformed or multi-action wrappers are rejected.
- `extract_tool_request` is the execution boundary: it accepts a request only when the complete trimmed content is one valid tool object. Plain text, ordinary JSON, and tool-shaped JSON embedded in prose remain final text.
- `extract_tool_request` rejects content that does not have complete object boundaries before invoking the dirty root scanner. This keeps incomplete streaming prefixes cheap without changing which complete canonical tool objects are accepted.
- `is_misformatted_tool_request` identifies a tool request wrapped in a JSON code fence, concatenated complete roots containing tool intent, or a complete Agent Zero envelope that starts with `thoughts` and whose dirty parser has absorbed `headline`, `tool_name`, and `tool_args` into that list. It routes that output to the existing repair prompt without executing it.
- Streaming tool snapshots use `extract_tool_request`; the permissive root helpers remain available for repair and legacy callers, not tool execution.
- Root extraction ignores objects nested inside an open parent object, so streamed wrapper tools such as `parallel` cannot stop early on the first nested `tool_calls` item.
- `extract_leaked_tool_request` classifies completed output as `clean`, `quoted`, `call`, `truncated`, or `rejected`; it never changes streaming/canonical acceptance. A `call` contains an intact candidate, not execution authorization. The result hook maps aliases, normalizes actions, and requires the currently offered tool name before dispatch.
- Completed recovery accepts one standalone `<tool_call>` JSON object/single-item array, `<function=...><parameter=...>` envelope (optionally wrapped), or `name` with `arguments`/`parameters`. It strictly decodes JSON and encoded arguments, rejecting duplicate keys, nonfinite numbers, conflicting fields, incomplete input, multiple calls, and surrounding prose. XML parameter text is preserved; only intact whitespace-free JSON tokens are coerced.
- Code fences and inline examples produce `quoted`, never a recovered call. Parse complete outer envelopes before masking code so argument content remains intact. The classifier has no logging, network, persistence, or tool-discovery side effects.
- Imported dependency areas include: `dirty_json`, `helpers.modules`, `re`, `regex`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `extract_json_object_string`, `content.find`, `DirtyJson`, `content.rfind`, `regex.search`, `re.sub`, `json.strip`, `ValueError`, `tool_name.split`, `parser.parse`, `match.group`, `match.group.replace`, `DirtyJson.parse_string`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_stream_tool_early_stop.py`
  - `tests/test_tool_request_normalization.py`
  - `tests/test_leaked_tool_calls.py`
  - `tests/test_leaked_tool_call_integration.py`

## Child DOX Index

No child DOX files.
