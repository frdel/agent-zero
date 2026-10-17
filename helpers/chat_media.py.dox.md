# chat_media.py DOX

## Purpose

- Own the `chat_media.py` helper module.
- This module materializes, stores, and resolves chat-scoped image/media artifacts.
- Keep this file-level DOX profile synchronized with `chat_media.py` because this directory is intentionally flat.

## Ownership

- `chat_media.py` owns the runtime implementation.
- `chat_media.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ChatImage` (no explicit base class)
- Top-level functions:
- `screenshot_dir(context_id: str, source: str) -> Path`
- `artifact_dir(context_id: str, category: ImageCategory=..., source: str=...) -> Path`
- `save_image_bytes(context_id: str, payload: bytes, mime_type: str=..., category: ImageCategory=..., source: str=..., preferred_name: str=..., max_bytes: int | None=...) -> ChatImage`
- `save_image_base64(context_id: str, data: str, mime_type: str=..., category: ImageCategory=..., source: str=..., preferred_name: str=..., max_bytes: int | None=...) -> ChatImage`
- `save_image_file(context_id: str, path: str | Path, category: ImageCategory=..., source: str=..., preferred_name: str=..., max_bytes: int | None=...) -> ChatImage`
- `save_image_data_url(context_id: str, data_url: str, category: ImageCategory=..., source: str=..., preferred_name: str=..., max_bytes: int | None=...) -> ChatImage`
- `materialize_image_ref(context_id: str, url: str, source: str=..., preferred_name: str=..., max_bytes: int | None=...) -> str`
- `is_chat_scoped_path(context_id: str, path: str | Path) -> bool`
- `infer_source(value: str=..., preferred_name: str=...) -> str`
- `category_for_source(source: str) -> ImageCategory`
- `snapshot_image_refs(text: str, context_id: str, source: str=...) -> str`: Copy live local image files referenced by `img://` or `/api/image_get?path=` onto unique chat artifacts and rewrite those refs so later filename reuse cannot overwrite earlier chat bubbles.
- `_guess_image_mime(path: Path) -> str`
- `_is_data_image_url(value: str) -> bool`
- `_split_image_data_url(data_url: str) -> tuple[str, str]`
- Notable constants/configuration names: `DEFAULT_MAX_IMAGE_BYTES`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion.
- Imported dependency areas include: `__future__`, `dataclasses`, `helpers`, `pathlib`, `re`, `time`, `typing`, `uuid`.
- Finished chat responses that embed `img://` or `/api/image_get?path=` local image refs are rewritten onto unique files under `usr/chats/<id>/images/response/`. Already chat-scoped artifacts are left in place. Missing or non-image refs are left unchanged.

## Key Concepts

- Important called helpers/classes observed in the source: `dataclass`, `artifact_dir`, `bytes`, `media_artifacts.normalize_mime`, `media_artifacts.guess_extension`, `media_artifacts.safe_filename`, `Path`, `time.strftime`, `path.parent.mkdir`, `path.write_bytes`, `ChatImage`, `media_artifacts.decode_base64_payload`, `save_image_bytes`, `image_path.read_bytes`, `_split_image_data_url`, `save_image_base64`, `str.strip`, `category_for_source`, `_is_data_image_url`, `images.resolve_ref`, `snapshot_image_refs`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_host_browser_connector.py`
  - `tests/test_tool_action_contracts.py`
  - `tests/test_vision_load_image_refs.py`
  - `tests/test_chat_media_response_snapshots.py`

## Child DOX Index

No child DOX files.
