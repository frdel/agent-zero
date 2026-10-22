# scheduler_task_create.py DOX

## Purpose

- Own the `scheduler_task_create.py` API endpoint.
- This module handles scheduler task create requests.
- Keep this file-level DOX profile synchronized with `scheduler_task_create.py` because this directory is intentionally flat.

## Ownership

- `scheduler_task_create.py` owns the runtime implementation.
- `scheduler_task_create.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `SchedulerTaskCreate` (`ApiHandler`)
  - `async process(self, input: Input, request: Request) -> Output`

## Runtime Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `SchedulerTaskCreate` is an `ApiHandler`.
- `SchedulerTaskCreate` defines `process(...)`.
- An optional `state` is validated as `TaskState` and applied before persistence; it defaults to `idle`. Creating a disabled task must not briefly expose it as runnable.
- Observed side-effect areas: filesystem writes, secret handling, scheduler state.
- Imported dependency areas include: `helpers.api`, `helpers.localization`, `helpers.print_style`, `helpers.projects`, `helpers.task_scheduler`, `random`.

## Key Concepts

- Important called helpers/classes observed in the source: `PrintStyle`, `scheduler.get_task_by_uuid`, `serialize_task`, `Localization.get.set_timezone`, `scheduler.reload`, `ValueError`, `ScheduledTask.create`, `scheduler.add_task`, `requested_project_slug.strip`, `load_basic_project_data`, `random.randint`, `schedule.split`, `TaskSchedule`, `PlannedTask.create`, `AdHocTask.create`, `printer.error`, `type`, `parse_task_plan`, `parse_task_schedule`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- Run `tests/test_scheduler_editor.py` for initial-state persistence.

## Child DOX Index

No child DOX files.
