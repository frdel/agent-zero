# scheduler_tasks_list.py DOX

## Purpose

- Own the `scheduler_tasks_list.py` API endpoint.
- This module handles scheduler tasks list requests.
- Keep this file-level DOX profile synchronized with `scheduler_tasks_list.py` because this directory is intentionally flat.

## Ownership

- `scheduler_tasks_list.py` owns the runtime implementation.
- `scheduler_tasks_list.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `SchedulerTasksList` (`ApiHandler`)
  - `async process(self, input: Input, request: Request) -> Output`

## Runtime Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `SchedulerTasksList` is an `ApiHandler`.
- `SchedulerTasksList` defines `process(...)`.
- Observed side-effect areas: scheduler state.
- Imported dependency areas include: `helpers.api`, `helpers.localization`, `helpers.print_style`, `helpers.task_scheduler`, `traceback`.

## Key Concepts

- Important called helpers/classes observed in the source: `scheduler.serialize_all_tasks`, `Localization.get.set_timezone`, `scheduler.reload`, `PrintStyle.error`, `traceback.format_exc`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- No direct test reference was found by name search; choose the nearest behavioral test or perform a focused smoke check.

## Child DOX Index

No child DOX files.
