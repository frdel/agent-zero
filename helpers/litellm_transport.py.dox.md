# litellm_transport.py DOX

## Purpose

- Own Agent Zero's LiteLLM transport adapter for Chat Completions and Responses API calls.
- Normalize Agent Zero model-call kwargs into provider-safe LiteLLM requests.
- Preserve canonical response metadata for history, provider-state continuation, and fallback decisions.

## Ownership

- `litellm_transport.py` owns the runtime implementation.
- `litellm_transport.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `TransportMode`
- `TransportRecovery`
- `TransportPolicy`
- `LiteLLMTransport`
- `ChatCompletionsTransport`
- `ResponsesTransport`
- `ResponsesEventParser`
- Top-level functions include transport cache reset, request normalization, parsing, prompt-cache preparation, and response/error classifiers.

## Runtime Contracts

- Keep provider selection and provider-specific defaults outside this helper; callers pass a resolved LiteLLM model name and kwargs.
- Strip Agent Zero internal kwargs before sending requests to LiteLLM.
- Validate internal `responses_history_context` against selected prepared local input, bind its stable-prefix digest to actual affinity/tool schemas, and project eligible groups through `responses_history`. Strip the control on every provider path and omit its digest from Chat/fallback result metadata.
- Capture only the validated current extras suffix in completed local Responses results. Historical snapshots restore the growing request prefix; Chat/fallback and provider-managed continuation never acquire these snapshots.
- Apply `responses_prompt_replacements` only to Responses input when generated A0 functions are present; preserve original Chat/fallback messages and strip this internal control before either provider call.
- Do not send orphan tool controls when no tools are present; strict OpenAI-compatible servers can reject empty `tools` arrays.
- When Agent Zero function tools are present, default Responses requests to one required native call; explicit request-level `tool_choice` and `parallel_tool_calls` values still win.
- Normalize function tool parameter schemas with an explicit object `properties` field before Responses requests so OpenAI-compatible chat backends reached through LiteLLM can validate them.
- Default to Chat Completions; use Responses only when `a0_api_mode` explicitly selects it, with fallback to Chat Completions when unsupported.
- Fall back to Chat Completions when a Responses request is rejected before any output by an endpoint-specific or shape-specific Bad Request indicating the provider cannot parse Responses payloads.
- Treat opaque type-discrimination errors such as `cannot determine type` from OpenAI-compatible Responses endpoints as shape-specific rejections.
- Fall back to Chat Completions when a Responses endpoint fails before output with an endpoint-specific server error, proxy path-unavailable error, or LiteLLM proxy-extra import error.
- Fall back to Chat Completions when LiteLLM's Responses mock streaming path tries to JSON-decode a real SSE stream before any output.
- Preserve Chat Completions tool calls from both non-streaming responses and streaming deltas as canonical `LLMResult` function-call items. Non-streaming calls stay canonical when accompanied by commentary; retain that commentary as a separate output message.
- Chat Completions `content_filter` and `refusal` finish reasons raise LiteLLM `ContentPolicyViolationError` on streaming and non-streaming paths; never treat blocked output as an empty success or dispatch partial tool calls. Verify with `tests/test_model_refusal.py`.
- Responses messages explicitly marked `phase: commentary` produce an incremental `response_preview` with public text in `thoughts`, followed by the native tool preview. Previews reuse parsed call state; multiple calls form one parallel envelope. Only native agent-turn callbacks consume the preview: legacy callbacks, response/reasoning deltas, completed output items and call IDs remain unchanged. Unmarked/final-answer text and reasoning are not reclassified as commentary.
- Preserve provider usage and LiteLLM response cost for both transports only when the response or stream actually supplies them; do not synthesize unavailable provider accounting.
- Streaming Chat Completions requests include `stream_options.include_usage` so terminal usage events reach `LLMResult.usage` for OpenAI-compatible endpoints and Messages API providers alike, unless the model configuration previously rejected the option or the request already carries it. A pre-output rejection retries once without the transport-injected `include_usage` and remembers the rejection per model configuration in a process-global cache that naturally clears when the framework process restarts; tests reset it through `clear_transport_capability_cache`. User-provided `stream_options` keys are always passed through untouched, even when the provider rejects them.
- Recover all Responses output items from stream events when a terminal completed envelope omits them, including encrypted reasoning. Merge by item/call identity in output-index order; terminal non-null fields win without duplicating calls.
- Stream named native function arguments through canonical tool envelopes for display. Buffer interleaved calls until the active envelope closes; preserve independent original call metadata. Native execution still waits for the completed model turn.
- Fail incomplete Responses generations and native-call streams that end without completion; never promote partial call previews to a Chat result.
- Serialize synthesized Responses function-call JSON with literal Unicode so streamed raw-response logs preserve tool arguments.
- Preserve provider-state metadata when Responses API calls succeed, and fall back to local replay when provider state is unsupported.
- Keep prompt-cache markers only for providers that accept them.
- Chat Completions parsing prefers `reasoning_content` and falls back to `reasoning` for both streaming deltas and complete messages, preserving response content and applying the same encrypted-reasoning filter. Verify with `test_chat_reasoning_field_fallback` in `tests/test_stream_tool_early_stop.py`.
- `a0_prompt_cache_mode` selects `auto` (existing provider detection), `prompt_cache_key`, `cache_control`, or `off` (no automatic hints). Reject invalid values before provider calls and strip the internal control from both transports. Provider defaults and model Additional parameters may set it; embeddings do not acquire chat-provider defaults.
- Cache-key mode hashes the stable leading context and tool definitions, excluding changing conversation tails. Preserve caller keys at the request level or in `extra_body`; explicit retention still passes through when automatic hints are off. Strip message markers in cache-key mode without mutating callers.
- Automatic `cache_control` marker placement follows the selected cache mode; default OpenAI/Codex Responses configuration bypasses it. An explicit `cache_control` override keeps marked requests on Chat Completions, including custom OpenAI-compatible endpoints. Skipping a marker target never removes its message, tool call, or reasoning content. Responses `phase: commentary`, encrypted reasoning, native replay, and request flags remain owned by their Responses paths.
- For supported Chat providers, mark the last leading system/developer message and the last two nonempty assistant messages. Retain the previous assistant boundary as the conversation grows; leave user/tool tails containing rebuilt extras unmarked. Before the first assistant message, cache only the leading context. Do not add markers to empty assistant content or thinking/redacted-thinking blocks. Automatic placement uses at most three message breakpoints, leaving one for tool definitions; this is not a limit on conversation messages or native tool calls. Do not mutate caller messages or stored history.

## Work Guidance

- Add provider-agnostic request cleanup here when multiple OpenAI-compatible providers can benefit.
- Treat fallback behavior as a shared transport contract, not a provider registry.
- Keep tool conversion symmetric between Chat Completions and Responses requests.

- TransportMode.from_value owns API-mode interpretation; input_from_model_messages owns model-message conversion shared with Agent and replay preparation.

- `ResponsesEventParser` owns the authoritative output-item store and final reconstruction through `finish()`. Function calls are a derived view; transport attaches request/provider metadata. Finalization must not mutate the supplied terminal envelope.

## Verification

- Run `pytest tests/test_stream_tool_early_stop.py tests/test_responses_architecture.py -q` after changing transport normalization or fallback behavior.
- Run `pytest tests/test_prompt_protocol.py -q` for cache-boundary changes; the multi-turn check covers changing extras, preserved prior boundaries, and deliberate invalidation after a protocol edit.
- Run local-provider smoke checks when changing OpenAI-compatible request cleanup.
- Run `pytest tests/test_litellm_sdk.py -q` for outgoing cache-routing bodies on Venice, Agent Zero API, and custom providers across sync/async and streaming/non-streaming calls.

## Child DOX Index

No child DOX files.

## Chat reasoning boundary

- Chat Completions `reasoning_content` is readable text only up to the provider serialization marker `__ENCRYPTED_REASONING__`. Suppress that marker and its remaining opaque payload before callbacks and result metadata, including markers split across stream chunks. Preserve ordinary reasoning and response content.
- Responses encrypted output items remain opaque native state; this Chat filter neither decodes nor promotes them into text. Existing saved logs are not rewritten.
- Verify with `pytest tests/test_chat_encrypted_reasoning.py -q`.
