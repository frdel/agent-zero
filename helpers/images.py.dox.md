# images.py DOX

## Purpose

- Own the `images.py` helper module.
- This module resolves, compresses, and serializes image references for model inputs.
- Keep this file-level DOX profile synchronized with `images.py` because this directory is intentionally flat.

## Ownership

- `images.py` owns the runtime implementation.
- `images.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `prepare_content(content: Any) -> Any`
- `is_local_ref(url: str) -> bool`
- `to_data_url(url: str) -> str`
- `resolve_ref(url: str) -> Path`
- `compress_image(image_data: bytes, max_pixels: int=..., quality: int=...) -> bytes`: Compress an image by scaling it down and converting to JPEG with quality settings.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, network calls, settings/state persistence.
- Imported dependency areas include: `PIL`, `base64`, `io`, `math`, `mimetypes`, `pathlib`, `typing`, `urllib.parse`.

## Key Concepts

- Important called helpers/classes observed in the source: `url.lower`, `lowered.startswith`, `resolve_ref`, `base64.b64encode.decode`, `Path.expanduser`, `raw_path.startswith`, `FileNotFoundError`, `io.BytesIO`, `img.save`, `output.getvalue`, `prepare_content`, `url.startswith`, `mimetypes.guess_type`, `ValueError`, `url.lower.startswith`, `unquote`, `seen.add`, `math.sqrt`, `img.resize`, `img.convert`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- `is_local_ref` recognizes a leading secret placeholder so fully masked paths still enter image preparation. `resolve_ref` uses restored placeholders only for filesystem lookup; unresolved paths retain their masked form in errors, and ordinary paths do not load secrets.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_image_get_security.py`
  - `tests/test_vision_load_image_refs.py`

## Child DOX Index

No child DOX files.
