# watchdog.py DOX

## Purpose

- Own the `watchdog.py` helper module.
- This module registers filesystem watchdogs with debouncing, path filtering, batched registration, and 9p/WSL mount detection.
- Keep this file-level DOX profile synchronized with `watchdog.py` because this directory is intentionally flat.

## Ownership

- `watchdog.py` owns the runtime implementation.
- `watchdog.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `_DispatchHandler(FileSystemEventHandler)`
  - `dispatch(self, event: Any)`
- `_Watch` (no explicit base class)
- `_PendingBatch` (no explicit base class)
- `_WatchRegistry` (no explicit base class)
  - `add(self, id: str, roots: list[str], patterns: list[str] | None, ignore_patterns: list[str] | None, events: WatchEvents, debounce: float, handler: WatchHandler) -> None`
  - `remove(self, id: str) -> bool`
  - `clear(self) -> None`
  - `start(self) -> None`
  - `stop(self) -> None`
  - `dispatch(self, scheduled_root: str, event: Any) -> None`
  - `_refresh_observer(self) -> None` — recomputes covering roots, creates/stops observer, schedules watches; all state under `self._lock`, observer I/O outside lock, `_scheduled_roots` published after scheduling (publish-after-commit)
  - `_stop_observer(self) -> None` — snapshots observer under lock, stops/joins outside lock
  - `batch(self)` — contextmanager that defers observer refresh until exit; sets `_batching=True` under lock, yields, resets under lock, then calls `_refresh_observer()`
- Top-level functions:
- `_normalize_root(root: str) -> str`
- `_normalize_roots(roots: list[str]) -> list[str]`
- `_normalize_patterns(patterns: list[str] | None, default: list[str] | None=...) -> list[str]`
- `_normalize_events(events: WatchEvents) -> frozenset[WatchEvent]`
- `_map_event_type(event_type: str) -> WatchEvent | None`
- `_normalize_debounce(debounce: float) -> float`
- `_is_9p_mount(path: str) -> bool` — reads /proc/mounts, finds 9p filesystem mounts, returns True if path resides on deepest matching 9p mount (longest prefix). Emits one-time `PrintStyle.warning` via `_9p_warned` flag. Catches `OSError`, returns `False` if /proc/mounts unreadable. Related: https://github.com/microsoft/WSL/issues/4739
- `_covering_roots(roots: Iterable[str]) -> set[str]`
- `_is_same_or_nested(path: str, root: str) -> bool`
- `_is_under_watch(path: str, watch: _Watch) -> bool`
- `_compile_matcher(root: str, patterns: list[str], ignore_patterns: list[str]) -> PatternMatcher`
- `_compile_single_matcher(root: str, patterns: list[str]) -> PatternMatcher`
- `add_watchdog(id: str, roots: list[str], patterns: list[str] | None=..., ignore_patterns: list[str] | None=..., events: WatchEvents=..., debounce: float=..., handler: WatchHandler | None=...) -> None`
- `remove_watchdog(id: str) -> bool`
- `clear_watchdogs() -> None`
- `start_watchdog_daemon() -> None`
- `stop_watchdog_daemon() -> None`
- `batch_watchdogs()` — returns `_registry.batch()` contextmanager for grouping registrations
- Notable constants/configuration names: `_DEFAULT_PATTERNS`, `_DEFAULT_IGNORE_FOLDERS`, `_DEFAULT_IGNORE_PATTERNS`, `_VALID_EVENTS`, `_EVENT_ALIASES`, `_9p_warned`.
- Pattern handling: `add()` calls `_normalize_patterns(ignore_patterns, default=[])` to avoid the catch-all `**/*` short-circuit. `_DEFAULT_IGNORE_PATTERNS` and folder-derived globs are always appended. `_normalize_patterns` checks `if default is None` (not `or`) so `default=[]` returns an empty list.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion.
- Imported dependency areas include: `__future__`, `collections.abc`, `contextlib`, `dataclasses`, `fnmatch`, `os`, `pathspec`, `threading`, `typing`, `watchdog.events`, `watchdog.observers`, `helpers.print_style`.

## Key Concepts
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.
- Important called helpers/classes observed in the source: `frozenset`, `dataclass`, `_WatchRegistry`, `_registry.start`, `os.path.abspath`, `_compile_single_matcher`, `_compile_matcher`, `_registry.add`, `_registry.remove`, `_registry.clear`, `_registry.stop`, `self.registry.dispatch`, `threading.RLock`, `_is_9p_mount`, `_normalize_roots`, `_normalize_patterns`, `_normalize_events`, `_normalize_debounce`, `self._refresh_observer`, `_map_event_type`, `_covering_roots`, `PathSpec.from_lines`, `fnmatch.fnmatch`, `PrintStyle.warning`.
- Pattern matching approach: path-bearing patterns (anything containing `/`) use `pathspec.PathSpec(gitwildmatch)` which correctly treats `**` as recursive globstar. Name-only patterns (e.g. `*.pyc`) use `fnmatch.fnmatch` against the basename. This aligns with `helpers/file_tree.py`, `helpers/backup.py`, and `_promptinclude/.../scanner.py` which all use `pathspec.PathSpec(gitwildmatch)` for recursive directory exclusion.

### 9p/WSL Mount Detection

- `_is_9p_mount(path)` reads `/proc/mounts` to find 9p filesystem entries.
- Returns True if the path resides on the deepest matching 9p mount (longest prefix match ensures specificity for nested mounts).
- Emits a one-time `PrintStyle.warning` via the `_9p_warned` module flag when a 9p mount is first detected.
- Catches `OSError` and returns `False` if `/proc/mounts` is unreadable (non-Linux environments).
- Used in `add()` to filter out roots that cannot be reliably watched. Related WSL issue: https://github.com/microsoft/WSL/issues/4739

### Concurrency Model

- `_WatchRegistry` uses `threading.RLock` for all mutable state access.
- `_refresh_observer()`: snapshots `_watches`, `_observer`, `_scheduled_roots` under lock; performs observer I/O (`unschedule_all`, `schedule`, `stop`, `join`) outside lock on local references to prevent deadlock.
- Observer creation + `start()` inside lock: prevents duplicate observer race where two threads could each create and start their own Observer.
- `_scheduled_roots` published AFTER scheduling completes (publish-after-commit): if two threads interleave and one wipes the other's schedules, the next `_refresh_observer()` detects mismatch (`target != scheduled`) and reschedules correctly.
- `batch()`: `_batching` flag set/cleared under lock.
- `_batching` read without lock in `add()`, `remove()`, `clear()` (TOCTOU): benign — worst case is an extra `_refresh_observer()` call during batching.

### Defense-in-Depth Filtering

- `_DEFAULT_IGNORE_FOLDERS` enforced in three independent layers:
  1. **Root filter** (`add()`): roots whose basename is in `_DEFAULT_IGNORE_FOLDERS` are excluded before watch registration.
  2. **Dispatch filter** (`dispatch()`): events whose path contains any `_DEFAULT_IGNORE_FOLDERS` component are dropped before handler invocation.
  3. **Pattern matcher**: `**/{folder}/**` globs appended to ignore patterns for every watcher.
- If all roots are filtered out, `add()` silently registers nothing — this is intended behavior.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_model_config_api_keys.py`
  - `tests/test_model_config_project_presets.py`
  - `tests/test_time_travel.py`

## Child DOX Index

No child DOX files.
