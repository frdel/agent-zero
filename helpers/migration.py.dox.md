# migration.py DOX

## Purpose

- Own the `migration.py` helper module.
- This module migrates legacy user data and runtime layout at startup.
- Keep this file-level DOX profile synchronized with `migration.py` because this directory is intentionally flat.

## Ownership

- `migration.py` owns the runtime implementation.
- `migration.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `startup_migration() -> None`
- `migrate_user_data() -> None`: Migrate user data from /tmp and other locations to /usr.
- `migrate_dotenv() -> None`: Migrate a legacy root `.env` before preparation writes configuration; preserve an existing `usr/.env` and conflicting legacy files.
- `convert_agents_json_yaml() -> None`
- `_move_dir(src: str, dst: str, overwrite: bool=...) -> None`: Move a directory from src to dst if src exists and dst does not.
- `_move_file(src: str, dst: str, overwrite: bool=...) -> None`: Move a file from src to dst if src exists and dst does not.
- `_migrate_memory(base_path: str=...) -> None`: Migrate memory subdirectories.
- `_merge_dir_contents(src_parent: str, dst_parent: str) -> None`: Moves all items from src_parent to dst_parent.
- `_cleanup_obsolete() -> None`: Remove directories that are no longer needed.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Startup cleanup removes obsolete `memory`, `knowledge/default`, and legacy `logs` directories; repeated runs are safe.
- `prepare.py` calls `migrate_dotenv()` and reloads dotenv before setting the root password, so preparation cannot create a placeholder `usr/.env` ahead of legacy migration. `migrate_user_data()` repeats this check safely.
- An existing `usr/.env` is authoritative. Preserve both paths when they alias the same file; warn without printing values when distinct legacy configuration is left in place. With legacy configuration present, an unusable destination stops migration; an unusable legacy source stops migration when no destination exists. Migration errors abort startup before preparation can create a placeholder configuration without the saved credentials.
- With no destination, regular legacy files move normally. A valid legacy symlink stays in place and `usr/.env` links to the same target, adjusting relative paths from the destination's actual directory (including a symlinked `usr/`) without resolving intermediate target symlinks. External configuration replacements remain visible. Link creation never replaces an existing destination; failures leave the legacy configuration untouched.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, settings/state persistence, secret handling, scheduler state.
- Imported dependency areas include: `helpers`, `helpers.print_style`, `json`, `os`.

## Key Concepts

- Important called helpers/classes observed in the source: `migrate_user_data`, `convert_agents_json_yaml`, `extension.call_extensions_sync`, `_move_dir`, `_move_file`, `_migrate_memory`, `_merge_dir_contents`, `_cleanup_obsolete`, `subagents.get_agents_roots`, `files.get_subdirectories`, `files.list_files`, `files.deabsolute_path`, `files.exists`, `files.move_dir`, `files.move_file`, `files.get_abs_path`, `os.path.isdir`, `os.path.join`, `files.delete_dir`, `os.path.isfile`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_migration_cleanup.py`
  - `tests/test_migration_dotenv.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_office_canvas_setup.py`
  - `tests/test_office_document_store.py`
  - `tests/test_speech_plugin_split.py`

## Child DOX Index

No child DOX files.
