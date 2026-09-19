# wait.py DOX

## Purpose

- Own the `wait.py` helper module.
- This module formats and runs managed waits with progress updates.
- Keep this file-level DOX profile synchronized with `wait.py` because this directory is intentionally flat.

## Ownership

- `wait.py` owns the runtime implementation.
- `wait.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `format_remaining_time(total_seconds: float) -> str`
- `async managed_wait(agent, target_time, is_duration_wait, log, get_heading_callback)`

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Imported dependency areas include: `asyncio`, `helpers.localization`, `helpers.print_style`.

## Key Concepts

- Important called helpers/classes observed in the source: `divmod`, `join`, `Localization.get.now`, `total_seconds`, `agent.handle_intervention`, `asyncio.sleep`, `pause_duration.total_seconds`, `PrintStyle.info`, `get_heading_callback`, `format_remaining_time`, `Localization.get.serialize_datetime`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/email_parser_test.py`
  - `tests/rate_limiter_test.py`
  - `tests/test_api_chat_lifetime.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_chat_compaction.py`
  - `tests/test_default_prompt_budget.py`
  - `tests/test_document_query_plugin.py`
  - `tests/test_download_toast_regressions.py`

## Child DOX Index

No child DOX files.
