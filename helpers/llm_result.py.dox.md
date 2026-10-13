# llm_result.py DOX

## Purpose

- Own canonical LLM result metadata shared by model transports, history, and tool-result processing.
- Preserve Responses API output items, provider response IDs, reasoning text, usage, and capability metadata in a serializable form.

## Ownership

- `llm_result.py` owns the runtime implementation.
- `llm_result.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ResponseItem`
- `ResponseFunctionCall`
- `LLMResult`
- Top-level functions include metadata conversion, function-call output item construction, object normalization, output-text extraction, reasoning extraction, and function-call argument parsing.

## Runtime Contracts

- `LLMResult.metadata()` stores durable provider state under `RESPONSE_METADATA_KEY`: response IDs, structured output items, provider/mode/state, usage, capability data, and a nonempty `history_extras` snapshot for eligible local Responses turns. Accumulated prompt inputs, raw responses, and duplicated response/reasoning text are not persisted in history. Missing or non-string extras deserialize as empty for legacy chats.
- `from_response(...)` must preserve provider `response_id`, `previous_response_id`, raw output items, usage, and capability metadata.
- `from_dict(...)` preserves explicit modes, including the empty non-LLM sentinel; only missing or null modes use the legacy `responses` default.
- `from_chat(...)` must produce an equivalent chat-completions result with `mode="chat_completions"` and `state="off"`, preserving optional function-call output items and provider usage when the chat transport supplies them.
- Function-call output items must preserve `call_id` and optional acknowledged safety checks.
- `finish_reason` carries the provider stop reason for the turn and is not persisted in history metadata; `truncated` is true for output-token-limit reasons (`length`, `max_tokens`).
- `repeat_response_text()` combines response text and canonical calls for native repeat detection, excluding provider IDs, usage and separate reasoning. Non-native replies retain their full response text. This comparison value is transient and does not replace canonical call history or provider metadata.
- Argument parsing must tolerate JSON strings, dictionaries, and malformed values without throwing.

## Work Guidance

- Keep metadata backward-compatible with existing serialized chat history.
- Treat unknown response item types as preserved built-in items unless they are local function calls, message text, or reasoning.
- Avoid provider-specific assumptions in result parsing.

## Verification

- Run `pytest tests/test_responses_architecture.py -q` after changing result metadata behavior.
- Run focused history/tool-processing tests when changing function-call serialization.

## Child DOX Index

No child DOX files.
