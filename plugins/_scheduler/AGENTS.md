# Scheduler Plugin DOX

## Purpose

- Own the `scheduler` agent tool and the Tasks UI for managing saved tasks and schedules.

## Ownership

- `tools/scheduler.py` owns action dispatch, timezone normalization, cron/plan validation, and agent-facing task CRUD.
- The tool logs its message as type `scheduler` with an `icon://calendar_month Schedule: <action>` headline; `extensions/webui/get_message_handler/` owns the `SCH` badge presentation and `extensions/webui/get_process_step_types/` registers the type.
- `prompts/` owns the tool prompt and the framework repair messages.
- `api/` owns the scheduler CRUD HTTP endpoints (`scheduler_task_create`, `scheduler_task_delete`, `scheduler_task_run`, `scheduler_task_update`, `scheduler_tasks_list`); core `api/scheduler_tick.py` stays with the scheduling engine.
- `webui/scheduler/` owns the Tasks modal (store, modal, detail, editor, list) and `webui/css/` owns the scheduler styles loaded through the plugin `page-head` extension.
- `webui/sidebar/` owns the sidebar tasks list and its store, injected through the `sidebar-extensions` extension point.
- `extensions/webui/sidebar-extensions/` owns the plugin contribution to that extension point.
- `extensions/webui/sidebar-quick-actions-dropdown-start/` owns the Tasks dropdown button, moved after the Files item via `x-move-after`.
- `extensions/webui/welcome-actions-start/` owns the Tasks card on the welcome screen, contributed through the `welcome-actions-start` point.
- `extensions/webui/page-head/` owns the scheduler and datepicker asset loading; core `webui/index.html` owns the shared flatpickr preload.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- The tool and API endpoints delegate to the shared `helpers.task_scheduler` engine, which stays in core and is also used by `api/scheduler_tick.py`, `helpers/job_loop.py`, chat lifecycle endpoints, and `_chat_naming`.
- The plugin declares `always_enabled: true`: the core scheduling engine keeps running tasks it created even when plugin code is absent, so the plugin must not be disableable into a state where tasks run without any way to manage them.
- Plugin API routes resolve as `/api/plugins/_scheduler/<handler>` via the standard plugin API resolution in `helpers/api.py`.
- Core consumers of the tasks store (`webui/index.js`, `chats-store.js`) read it through a soft `getStore("tasks")` accessor so the plugin can be disabled without breaking the sidebar.
- Timezone aliases (local/user/default/current/current_timezone) resolve via `helpers.localization`; cron validation rejects malformed expressions before task creation.
- `wait_for_task` polls task state until completion, failure, or idempotent runs.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with the tool prompt and the shared task scheduler engine.
- Respect intervention flow for long waits and user-visible task operations.

## Verification

- Import the tool and API endpoints in the framework runtime and run the scheduler tool, timezone, tool contract, and webui extension surface tests after changes.
- For scheduler editing, run `pytest tests/test_scheduler_editor.py` and check prompt expansion, draft retention, and save/reopen on desktop and mobile.

## Child DOX Index

Direct child DOX files:

| Child | Scope |
| --- | --- |
| [extensions/webui/sidebar-extensions/AGENTS.md](extensions/webui/sidebar-extensions/AGENTS.md) | Sidebar tasks section extension contribution. |
