# vision_load.py DOX

## Purpose

- Own the `vision_load.py` agent tool.
- This module routes images either into Main model-visible content or through the preset's optional Vision Model.
- Keep this file-level DOX profile synchronized with `vision_load.py` because this directory is intentionally flat.

## Ownership

- `vision_load.py` owns the runtime implementation.
- `vision_load.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `VisionLoad` (`Tool`)
  - `get_log_object(self)`
  - `get_heading(self)`
  - `async execute(self, paths, query="", **kwargs) -> Response`
  - `async after_execution(self, response: Response, **kwargs)`
- Notable constants/configuration names: `TOKENS_ESTIMATE`.

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- One call may contain multiple paths; a bare string is treated as one path. The Vision Model route sends every selected path in one request and returns one textual capsule.
- Model configuration exposes a Vision Model only when the effective preset selects that route; otherwise this tool follows Main's native vision path.
- The public tool contract is route-agnostic and accepts an optional focused `query`. A Vision Model receives both that query and the current user request through `fw.vision_load.md`; direct parallel workers inherit the request from their parent.
- Native Main vision already retains the query in its authored tool-call transcript, so native raw history remains image-only and does not repeat model-authored instructions as user content.
- Delegation completes during `execute(...)` so native Responses function output contains the real capsule before `after_execution(...)` persists it.
- Delegated history contains the text capsule only. Native history contains the tool result followed by one raw message holding all loaded image blocks.
- In a direct parallel worker, native image content is queued for the parent and promoted immediately after the outer `parallel` result; the disposable worker never owns the only copy of model-visible pixels.
- Direct parallel workers inherit the parent's model override generically. This tool uses their recorded parent context only to resolve ephemeral refs and durable chat media.
- `max_embeds` comes from the model that actually receives the images.
- Native tool-result summaries omit the skipped-images section when no images were skipped; when the limit drops inputs, the section reports the skipped paths and active maximum.
- Vision Model calls use the selected model's Advanced `kwargs`; this tool does not impose a separate timeout or output-token limit.
- An empty Vision Model response is reported as an image-analysis error instead of a successful empty capsule.
- Every call logs as the dedicated `vision_load` type with an `icon://imagesmode` headline naming the first image and the extra count; `extensions/webui/get_message_handler/` owns the `EYE` badge presentation and `get_process_step_types/` registers the type.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `VisionLoad` is a `Tool`.
- `VisionLoad` defines `execute(...)`.
- Observed side-effect areas: filesystem writes, model calls, plugin state, settings/state persistence, secret handling.
- Imported dependency areas include: `helpers`, `helpers.strings`, `helpers.tool`, `langchain_core.messages`, `mimetypes`, `uuid`, and `_model_config`.

## Key Concepts

- Important called helpers/classes observed in the source: `build_vision_model`, `get_vision_model_config`, `self._get_max_embeds`, `Response`, `self._context_id`, `chat_media.save_image_base64`, `chat_media.save_image_data_url`, `chat_media.materialize_image_ref`, `ephemeral_images.consume_image`, `images.to_data_url`, `history.RawMessage`, `super().after_execution`, `model.unified_call`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run targeted tool and prompt-contract tests for changed behavior; smoke-test agent execution when no focused test exists.
- Related tests observed by source search:
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_host_browser_connector.py`
  - `tests/test_office_desktop_state.py`
  - `tests/test_vision_load_image_refs.py`

## Child DOX Index

No child DOX files.
