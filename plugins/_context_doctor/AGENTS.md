# Context Doctor Plugin DOX

## Purpose

- Repair malformed Agent Zero tool-call JSON and preserve raw output as compact thoughts JSON when repair cannot produce a tool call.

## Ownership

- `helpers/context_doctor.py` transforms output and refreshes log fields.
- `hooks.py` installs the exact root-pinned repair dependency in the framework runtime.
- `extensions/python/startup_migration/` prepares that dependency after startup and self-update.
- `extensions/python/message_loop_result/` normalizes completed model output before default processing.
- `prompts/` owns fallback warning texts (`fw.msg_thoughts_fallback.md`, `fw.msg_thoughts_fallback_response.md`).
- `webui/config.html` exposes debug and repair-strategy settings.

## Local Contracts

- Leave canonical `LLMResult.function_calls` and their accompanying text untouched in either transport. The agent dispatches those calls through the normal tool-policy gate; text repair must not suppress them or reinterpret a textual follow-up as another call.
- Repaired and fallback JSON is always minified.
- Leave results already handled by an earlier `message_loop_result` extension (`skip_default_processing`) untouched, such as output-limit truncation retries.
- Usable Responses output text stays untouched for the core response-tool dispatcher. Recognizable tool intent still enters repair; Chat Completions non-tool output becomes `{"thoughts":[raw]}` and XML-like output becomes `{}` when suppression is enabled.
- Blank-line-separated thoughts expand into separate entries after repair when the split strategy is enabled (default on). This rewrites model-authored thoughts for every repaired turn by design, not only the raw-text fallback branch.
- `_select_value` returns only repaired tool calls or model-authored partial responses; `transform_response` wraps otherwise-raw output as thoughts afterward. `looks_like_tool_call` rejects that synthesized wrapper, so it reaches the fallback branch. Repaired output is usable only with a non-empty thoughts list, headline/tool name string, or tool-args dict.
- A raw-text fallback conversion must emit a `fw.msg_thoughts_fallback.md` history warning and a separate `fw.msg_thoughts_fallback_response.md` user notice, refresh the generating log and response item with the transformed thoughts JSON, and set `skip_default_processing` so the retry advances the unusable-response counter.
- The fallback passes the repaired `llm_result` to `hist_add_ai_response`, which owns Responses-API state advancement (`_remember_llm_result_state`); do not call the state method directly. The fallback turn's `response_id` is recorded so the next turn's `previous_response_id` chain stays intact.
- The fallback warning is counted by the core stop-unusable-response loop alongside `fw.msg_misformat.md`, `fw.msg_repeat.md`, `fw.msg_empty_response.md`, and `fw.msg_reasoning_only.md`.
- Log kvps retain streamed `reasoning` only; `update_log_item` does not restore `thoughts` from current kvps. `update_log` controls only View Details content.
- A repaired `response` tool call refreshes the response log item when streaming did not create it.
- Runtime setup reads the `json_repair` pin from root `requirements.txt`; do not duplicate its version in plugin code.

## Work Guidance

- Keep repair scoped to complete tool-call JSON.
- Use framework-installed `json_repair`; apply plugin-local parser patch before repair. Do not vendor dependencies.

## Verification

- Run `pytest plugins/_context_doctor/tests`.

## Child DOX Index

No child DOX files.
