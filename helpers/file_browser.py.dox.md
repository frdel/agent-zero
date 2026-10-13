# file_browser.py DOX

## Purpose

- Own the `file_browser.py` helper module.
- This module builds safe file-browser views over allowed filesystem roots.
- Keep this file-level DOX profile synchronized with `file_browser.py` because this directory is intentionally flat.

## Ownership

- `file_browser.py` owns the runtime implementation.
- `file_browser.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `FileBrowser` (no explicit base class)
  - `save_file_b64(self, current_path: str, filename: str, base64_content: str)`
  - `save_files(self, files: List, current_path: str=...) -> Tuple[List[str], List[str]]`
  - `delete_file(self, file_path: str) -> bool`
  - `rename_item(self, file_path: str, new_name: str) -> bool`
  - `move_items(self, file_paths: List[str], destination_path: str) -> List[str]`
  - `create_folder(self, parent_path: str, folder_name: str) -> bool`
  - `save_text_file(self, file_path: str, content: str) -> bool`
  - `get_files(self, current_path: str=...) -> Dict`
  - `get_full_path(self, file_path: str, allow_dir: bool=...) -> str`

## Runtime Contracts

- The text limit is read dynamically from `file_browser_max_text_size_mb` (10 MiB default, configurable 1–100); the transfer limit remains separate. Consumers call `max_text_bytes()` rather than retaining a startup snapshot.

- `FileBrowser` owns file-transfer and text-editing limits. `limits()` exposes them to Files/Editor UI; `text_bytes` and `decode_text` validate byte length, binary content, and UTF-8 for both local and remote Editor sessions. Consumers must not maintain independent Editor size constants.
- `max_file_bytes()` reads the configurable transfer limit (100 MiB by default, positive integer MiB with no ceiling). Local and remote uploads stream through shared bounded writers; local publication is atomic. Editing uses its separate limit.

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, subprocess/runtime control, settings/state persistence.
- Imported dependency areas include: `base64`, `datetime`, `helpers`, `helpers.localization`, `helpers.print_style`, `helpers.security`, `os`, `pathlib`, `shutil`, `subprocess`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `Path`, `files.get_abs_path`, `self._get_file_extension`, `file.seek`, `file.tell`, `resolve`, `os.makedirs`, `os.path.exists`, `full_path.with_name`, `new_path.exists`, `os.rename`, `target_dir.exists`, `filename.rsplit.lower`, `subprocess.run`, `result.stdout.strip.split`, `self._get_files_via_ls`, `files.exists`, `ValueError`, `str.startswith`, `file.write`.
- Multi-item moves validate every source and target before renaming, reject collisions and directory self-nesting, preserve symlink objects, and best-effort roll back earlier renames if a later rename fails.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_download_toast_regressions.py`
  - `tests/test_office_document_store.py`
  - `tests/test_file_browser_navigation.py`

## Child DOX Index

No child DOX files.

`read_text` owns bounded local Editor reads. `encode_upload` bounds the development RFC adapter. `prepare_files_download` owns Files routing and policy; a single selected directory downloads as `<folder>.zip` while true multi-selections keep the timestamped `agent-zero-selected-<count>-<stamp>.zip` archive name. `register_files_download` rechecks remote permission at delivery. API handlers do not select byte limits. Generic attachment/Connector downloads remain separate.

Destructive entry operations resolve parent directories while preserving the final symlink. Delete/Rename operate on the link itself; empty/root targets are rejected in the shared helper. Local Files downloads stage a bounded snapshot and reject in-place source changes during preparation. Cancelled preparation closes late responses and their temporary descriptors.

Uploads pass their binary streams and Editor saves pass `BytesIO` directly to `file_transfers.write_stream_atomic`; no upload-shaped wrapper is required.
