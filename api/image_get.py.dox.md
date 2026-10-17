# image_get.py DOX

## Purpose

- Own the `image_get.py` API endpoint.
- This module serves allowed image references and fallback file-type icons.
- Keep this file-level DOX profile synchronized with `image_get.py` because this directory is intentionally flat.

## Ownership

- `image_get.py` owns the runtime implementation.
- `image_get.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ImageGet` (`ApiHandler`)
  - `get_methods(cls) -> list[str]`
  - `async process(self, input: dict, request: Request) -> dict | Response`
- Top-level functions:
- `_resolve_allowed_image_path(path: str) -> str`: Resolve a requested image path and keep it inside Agent Zero's base dir.
- `_cache_control_for_image(path: str, exists: bool) -> str`: Choose cache policy for a served image URL. Missing-file fallbacks use `no-store`; unique chat artifacts may be cached; mutable workdir files revalidate with `no-cache`.
- `_set_image_headers(response: Response, filename: str, file_ext: str, cache_control: str=...) -> None`
- `_send_file_type_icon(file_ext, filename=...)`: Return appropriate icon for file type
- `_send_fallback_icon(icon_name)`: Return fallback icon from public directory
- Notable constants/configuration names: `IMAGE_EXTENSIONS`, `SVG_EXTENSIONS`, `SVG_CONTENT_SECURITY_POLICY`.

## Runtime Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `ImageGet` is an `ApiHandler`.
- `ImageGet` defines `process(...)`.
- `ImageGet` defines `get_methods(...)`.
- Observed side-effect areas: filesystem reads, network calls, subprocess/runtime control, settings/state persistence.
- Image responses set `Cache-Control` from `_cache_control_for_image(...)`. Do not cache missing-file fallback icons under the requested image URL; that hid later writes and mixed chat replay after a UI reload.
- Imported dependency areas include: `base64`, `helpers`, `helpers.api`, `io`, `mimetypes`, `os`, `pathlib`, `urllib.parse`.

## Key Concepts

- Important called helpers/classes observed in the source: `runtime.is_development`, `Path.resolve`, `candidate.resolve`, `quote`, `_send_fallback_icon`, `files.get_abs_path`, `send_file`, `os.path.splitext.lower`, `os.path.basename`, `Path`, `candidate.is_absolute`, `resolved.relative_to`, `os.path.exists`, `ValueError`, `_set_image_headers`, `_send_file_type_icon`, `files.fix_dev_path`, `_resolve_allowed_image_path`, `files.exists`, `files.get_base_dir`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- Related tests observed by source search:
  - `tests/test_image_get_security.py`

## Child DOX Index

No child DOX files.
