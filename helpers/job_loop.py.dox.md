# job_loop.py DOX

## Purpose

- Own the `job_loop.py` helper module.
- This module runs periodic scheduler and maintenance loops.
- Keep this file-level DOX profile synchronized with `job_loop.py` because this directory is intentionally flat.

## Ownership

- `job_loop.py` owns the runtime implementation.
- `job_loop.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `async run_loop()`
- `async scheduler_tick()`
- `pause_loop()`
- `resume_loop()`
- Notable constants/configuration names: `SLEEP_TIME`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- PostgreSQL workers elect one pinned `job-loop` session role before running integration pollers; disabled/failed workers do not poll. Scheduler execution has its own role/occurrence claims. This prevents simultaneous pollers in healthy sessions; plugin-specific delivery/idempotency and in-flight disconnect reconciliation still require adapters. Local/off mode retains existing extension dispatch.
- Observed side-effect areas: scheduler state and integration polling.
- Imported dependency areas include: `asyncio`, `datetime`, `helpers`, `helpers.print_style`, `helpers.task_scheduler`, `time`.

## Key Concepts

- Important called helpers/classes observed in the source: `time.time`, `runtime.is_development`, `scheduler.tick`, `call_extensions_async`, `resume_loop`, `asyncio.sleep`, `runtime.call_development_function`, `PrintStyle.error`, `scheduler_tick`, `errors.format_error`, `PrintStyle`, `errors.error_text`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_api_chat_lifetime.py`

## Child DOX Index

No child DOX files.
