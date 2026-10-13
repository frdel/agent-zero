# Message Loop Result Extensions DOX

## Purpose

- Own normalization and policy handling after a model turn completes, before default assistant-history and tool-dispatch processing.

## Ownership

- Extensions receive mutable `result_data` with `llm_result` and may set `skip_default_processing` after fully handling the turn.
- `_05_truncated_response.py` retries turns the provider cut off at the output token limit (`LLMResult.truncated`) that carry no complete tool request: add an agent-facing `fw.msg_output_limit.md` history warning with a separate `fw.msg_output_limit_response.md` user notice naming the finish reason, instead of the generic misformat warning, and count them through the stop-unusable-response-loop extension. Native calls are complete only when every raw argument value is a JSON object; a synthesized envelope around malformed arguments does not qualify.
- `_20_empty_response.py` retries fully empty turns (no response and no reasoning): count them toward the unusable-response limit without adding a warning to model history, and use `fw.msg_empty_response.md` for agent-prefixed UI warning text only.
- `_20_empty_response.py` retries reasoning-only turns: add an agent-facing `fw.msg_reasoning_only.md` history warning with a separate `fw.msg_reasoning_only_response.md` user notice, and count them through the stop-unusable-response-loop extension.
- `_30_repeat_response.py` compares `LLMResult.repeat_response_text()` for native calls (public text plus all calls), otherwise full response text. It retries content that exactly matches `loop_data.last_response`, regardless of separate reasoning or provider IDs, using `fw.msg_repeat.md` for history and `fw.msg_repeat_response.md` for the agent-prefixed UI warning text. State advancement is owned by `hist_add_ai_response`; do not call `_remember_llm_result_state` manually.
- `_40_native_thoughts.py` folds public commentary accompanying native function calls into the existing completed-generation log `thoughts` array. It preserves provider output items, canonical history, repeat comparison and dispatch. It respects handled results and excludes reasoning/encrypted items and explicit final-answer messages. Normal log masking applies.

## Local Contracts

- Files run in deterministic filename order.
- A handler that sets `skip_default_processing` owns needed history and UI side effects for that turn.
- Handlers that should not add side effects after an earlier extension has handled the result must return when `skip_default_processing` is set.
- Do not use this point to mutate streamed partial content.

## Work Guidance

- Normalize a completed result before policy extensions compare or persist it.
- Keep loop-control policy independent from optional plugins.

## Verification

- Run message-loop and unusable-response regression tests.

## Child DOX Index

No child DOX files.
