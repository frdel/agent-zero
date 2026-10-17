# Scheduler Plugin DOX

## Purpose

- Own the `scheduler` agent tool for managing saved tasks and schedules.

## Ownership

- `tools/scheduler.py` owns action dispatch, timezone normalization, cron/plan validation, and agent-facing task CRUD.
- The tool logs its message as type `scheduler` with an `icon://calendar_month Schedule: <action>` headline; `extensions/webui/get_message_handler/` owns the `SCH` badge presentation and `extensions/webui/get_process_step_types/` registers the type.
- `prompts/` owns the tool prompt and the framework repair messages.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- The tool delegates to the shared `helpers.task_scheduler` service, which stays in core and is also used by `api/` endpoints, `helpers/job_loop.py`, and `_chat_naming`.
- Timezone aliases (local/user/default/current/current_timezone) resolve via `helpers.localization`; cron validation rejects malformed expressions before task creation.
- `wait_for_task` polls task state until completion, failure, or idempotent runs.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with the tool prompt and the shared task scheduler engine.
- Respect intervention flow for long waits and user-visible task operations.

## Verification

- Import the tool in the framework runtime and run the scheduler tool and timezone tests after changes.

## Child DOX Index

No child DOX files.
