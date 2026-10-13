# state_snapshot.py DOX

## Purpose

- Own the `state_snapshot.py` helper module.
- This module builds and validates typed WebUI state snapshots.
- Keep this file-level DOX profile synchronized with `state_snapshot.py` because this directory is intentionally flat.

## Ownership

- `state_snapshot.py` owns the runtime implementation.
- `state_snapshot.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `SnapshotV1` (`TypedDict`)
- `StateRequestV1` (no explicit base class)
- `StateRequestValidationError` (`ValueError`)
- Top-level functions:
- `_annotation_to_isinstance_types(annotation: Any) -> tuple[type, ...]`: Convert type annotation to tuple suitable for isinstance().
- `_build_schema_from_typeddict(td: type) -> dict[str, tuple[type, ...]]`: Extract field names and isinstance-compatible types from TypedDict.
- `validate_snapshot_schema_v1(snapshot: Mapping[str, Any]) -> None`
- `_coerce_non_negative_int(value: Any, default: int=...) -> int`
- `_get_agent_profile_labels() -> dict[str, str]`
- `_apply_agent_profile_metadata(context_data: dict[str, Any], ctx: AgentContext, labels: dict[str, str]) -> None`
- `_prune_missing_saved_contexts() -> None`
- `parse_state_request_payload(payload: Mapping[str, Any]) -> StateRequestV1`
- `_coerce_state_request_inputs(context: Any, log_from: Any, notifications_from: Any, timezone: Any) -> StateRequestV1`
- `advance_state_request_after_snapshot(request: StateRequestV1, snapshot: Mapping[str, Any]) -> StateRequestV1`
- `async build_snapshot_from_request(request: StateRequestV1, include_collections: bool=...) -> SnapshotV1`: Build a poll-shaped snapshot for both /poll and state_push.
- `_notify_timezone_changed(previous_timezone: str, current_timezone: str) -> None`
- `async build_snapshot(context: str | None, log_from: int, notifications_from: int, timezone: str | None) -> SnapshotV1`
- Notable constants/configuration names: `_SNAPSHOT_V1_SCHEMA`, `SNAPSHOT_SCHEMA_V1_KEYS`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, plugin state, settings/state persistence, secret handling, scheduler state, in-memory context removal.
- Imported dependency areas include: `__future__`, `agent`, `dataclasses`, `helpers.dotenv`, `helpers.localization`, `helpers.persist_chat`, `helpers.task_scheduler`, `pytz`, `types`, `typing`.

## Key Concepts

- Important called helpers/classes observed in the source: `dataclass`, `_build_schema_from_typeddict`, `get_origin`, `timezone.strip`, `StateRequestV1`, `localization.get_timezone`, `localization.set_timezone`, `ctxid.strip`, `_coerce_non_negative_int`, `AgentContext.get_notification_manager`, `notification_manager.output`, `_get_agent_profile_labels`, `ctxs.sort`, `tasks.sort`, `validate_snapshot_schema_v1`, `_coerce_state_request_inputs`, `super.__init__`, `get_args`, `_annotation_to_isinstance_types`, `TypeError`.
- Snapshot building prunes non-running in-memory contexts that were previously saved but no longer have a `chat.json`, preventing stale sidebar rows after chat files are deleted outside `/chat_remove`. A context absent from the saved-ID listing is rechecked with `persist_chat.chat_file_exists()` before removal so a concurrent first save cannot lose its in-memory context.
- Notification payloads use the manager's matching GUID and cursor from the same atomic read, preventing a concurrent notification from being skipped by the WebUI.
- `StateRequestV1.collections_delta` is an optional, false-by-default capability. Negotiated state pushes may use `null` for both `contexts` and `tasks` when those collections are unchanged; HTTP polling and legacy WebSocket clients always receive full lists.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_multi_tab_isolation.py`
  - `tests/test_snapshot_parity.py`
  - `tests/test_snapshot_schema_v1.py`
  - `tests/test_state_monitor.py`
  - `tests/test_state_sync_handler.py`
  - `tests/test_state_sync_welcome_screen.py`

## Child DOX Index

No child DOX files.
