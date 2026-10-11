# history.py DOX

## Purpose

- Own the `history.py` helper module.
- This module owns chat history message records and model-output conversion.
- Keep this file-level DOX profile synchronized with `history.py` because this directory is intentionally flat.

## Ownership

- `history.py` owns the runtime implementation.
- `history.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `RawMessage` (`TypedDict`)
- `OutputMessage` (`TypedDict`)
- `Record` (no explicit base class)
  - `get_tokens(self) -> int`
  - `async compress(self) -> bool`
  - `output(self) -> list[OutputMessage]`
  - `async summarize(self) -> str`
  - `to_dict(self) -> dict`
  - `from_dict(data: dict, history: 'History')`
  - `output_langchain(self)`
  - `output_text(self, human_label=..., ai_label=...)`
- `Message` (`Record`)
  - `get_tokens(self) -> int`
  - `calculate_tokens(self)`
  - `set_summary(self, summary: str)`
  - `async compress(self)`
  - `output(self)`
  - `output_langchain(self)`
  - `output_text(self, human_label=..., ai_label=...)`
  - `to_dict(self)`
- `Topic` (`Record`)
  - `get_tokens(self)`
  - `add_message(self, ai: bool, content: MessageContent, tokens: int=..., id: str=...) -> Message`
  - `output(self) -> list[OutputMessage]`
  - `async summarize(self)`
  - `compress_large_messages(self, message_ratio: float=...) -> bool`
  - `async compress(self) -> bool`
  - `async compress_attention(self, ratio: float=...) -> bool`
  - `async summarize_messages(self, messages: list[Message])`
- `Bulk` (`Record`)
  - `get_tokens(self)`
  - `output(self, human_label: str=..., ai_label: str=...) -> list[OutputMessage]`
  - `async compress(self)`
  - `async summarize(self)`
  - `to_dict(self)`
  - `from_dict(data: dict, history: 'History')`
- `History` (`Record`)
  - `get_tokens(self) -> int`
  - `is_over_limit(self)`
  - `get_bulks_tokens(self) -> int`
  - `get_topics_tokens(self) -> int`
  - `get_current_topic_tokens(self) -> int`
  - `add_message(self, ai: bool, content: MessageContent, tokens: int=..., id: str=...) -> Message`
  - `new_topic(self)`
  - `output(self) -> list[OutputMessage]`
- Top-level functions:
- `deserialize_history(json_data: str, agent) -> History`
- `_stringify_output(output: OutputMessage, ai_label=..., human_label=...)`
- `_stringify_content(content: MessageContent) -> str`
- `_output_content_langchain(content: MessageContent)`
- `group_outputs_abab(outputs: list[OutputMessage]) -> list[OutputMessage]`
- `group_messages_abab(messages: list[BaseMessage]) -> list[BaseMessage]`
- `output_langchain(messages: list[OutputMessage])`
- `output_text(messages: list[OutputMessage], ai_label=..., human_label=...)`
- `clear_responses_provider_state(agent) -> None`
- `_merge_outputs(a: MessageContent, b: MessageContent) -> MessageContent`
- `_merge_properties(a: Dict[str, MessageContent], b: Dict[str, MessageContent]) -> Dict[str, MessageContent]`
- `_is_raw_message(obj: object) -> bool`
- `_is_embedded_data(obj: object) -> bool`
- `_json_dumps(obj)`
- `_json_loads(obj)`
- Notable constants/configuration names: `BULK_MERGE_COUNT`, `TOPICS_MERGE_COUNT`, `CURRENT_TOPIC_RATIO`, `HISTORY_TOPIC_RATIO`, `HISTORY_BULK_RATIO`, `CURRENT_TOPIC_ATTENTION_COMPRESSION`, `HISTORY_TOPIC_ATTENTION_COMPRESSION`, `LARGE_MESSAGE_TO_CURRENT_TOPIC_RATIO`, `LARGE_MESSAGE_TO_HISTORY_TOPIC_RATIO`, `RAW_MESSAGE_OUTPUT_TEXT_TRIM`, `COMPRESSION_TARGET_RATIO`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- `clear_responses_provider_state(agent)` removes the active provider continuation IDs after local history rewrites while preserving stored response ID lists for later cleanup.
- `Message.from_dict()` normalizes legacy AI Responses metadata through `LLMResult.metadata()` so loaded chats shed transient payloads while unrelated metadata and non-AI tool-result inputs remain intact.
- `Message.from_dict()` passes saved token counts to the constructor to avoid recounting restored messages. It still restores the saved value after the summary, preserving zero/missing-count lazy recalculation against the summarized content.
- Topic token totals and large-message compression include retained extras snapshots when the selected model uses Responses. Chat Completions keeps text-only accounting. Summarized messages/topics no longer contribute snapshot overhead; unchanged records conservatively count it even when replay eligibility later changes.
- `output_langchain()` removes leading assistant messages after grouping so provider histories always begin with a user turn; the WebUI greeting remains persisted and displayed but is not sent as an orphaned assistant message.
- `_json_dumps()` emits compact JSON (`","`, `":"` separators) for serialized history and generated non-string user-turn content.
- Observed side-effect areas: filesystem writes, filesystem deletion, model calls, plugin state, settings/state persistence, secret handling.
- Imported dependency areas include: `abc`, `asyncio`, `collections`, `collections.abc`, `enum`, `helpers`, `json`, `langchain_core.messages`, `math`, `plugins._model_config.helpers.model_config`, `typing`, `uuid`.

## Key Concepts

- Important called helpers/classes observed in the source: `History`, `_is_raw_message`, `_json_dumps`, `group_messages_abab`, `join`, `make_list`, `cast`, `a.copy`, `json.dumps`, `json.loads`, `globals.from_dict`, `output_langchain`, `output_text`, `self.output_text`, `tokens.approximate_tokens`, `self.calculate_tokens`, `Message`, `get_chat_model_config`, `large_msgs.sort`, `self.compress_large_messages`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_chat_compaction.py`
  - `tests/test_error_retry_plugin.py`
  - `tests/test_history_compression_wait.py`
  - `tests/test_mcp_handler_multimodal.py`
  - `tests/test_memory_quality.py`
  - `tests/test_model_config_project_presets.py`
  - `tests/test_office_document_store.py`

## Child DOX Index

No child DOX files.
