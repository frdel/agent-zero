# Scheduler Plugin DOX

## Purpose

- Own the `scheduler` agent tool and the Tasks UI for managing saved tasks and schedules.

## Ownership

- `tools/scheduler.py` owns action dispatch, timezone normalization, cron/plan validation, and agent-facing task CRUD.
- `prompts/` owns the tool prompt.
- `api/` owns the scheduler CRUD HTTP endpoints (`scheduler_task_create`, `scheduler_task_delete`, `scheduler_task_run`, `scheduler_task_update`, `scheduler_tasks_list`); core `api/scheduler_tick.py` stays with the scheduling engine.
- `webui/scheduler/` owns the Tasks modal (store, modal, detail, editor, list) and `webui/css/` owns the scheduler styles loaded through the plugin `page-head` extension.
- `webui/sidebar/` owns the sidebar tasks list and its store, injected through the `sidebar-tasks-list` extension point.
- `extensions/webui/sidebar-tasks-list/` owns the plugin contribution to that extension point.
- `extensions/webui/sidebar-quick-actions-dropdown-start/` owns the Tasks dropdown button, moved after the Files item via `x-move-after`.
- `extensions/webui/welcome-actions-middle/` owns the Tasks card on the welcome screen, contributed through the `welcome-actions-middle` point between the Memory and Files cards.
- `extensions/webui/page-head/` owns the scheduler, datepicker, and flatpickr asset loading.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- The tool and API endpoints delegate to the shared `helpers.task_scheduler` engine, which stays in core and is also used by `api/scheduler_tick.py`, `helpers/job_loop.py`, chat lifecycle endpoints, and `_chat_naming`.
- The plugin declares `always_enabled: true`: the core scheduling engine keeps running tasks it created even when plugin code is absent, so the plugin must not be disableable into a state where tasks run without any way to manage them.
- Plugin API routes resolve as `/api/plugins/_scheduler/<handler>` via the standard plugin API resolution in `helpers/api.py`.
- Core consumers of the tasks store (`webui/index.js`, `chats-store.js`) read it through a soft `getStore("tasks")` accessor so the plugin can be disabled without breaking the sidebar.
- Timezone aliases (local/user/default/current/current_timezone) resolve via `helpers.localization`; cron validation rejects malformed expressions before task creation.
- `wait_for_task` polls task state until completion, failure, or idempotent runs.

## Verification

- Import the tool and API endpoints in the framework runtime and run the scheduler tool, timezone, tool contract, and webui extension surface tests after changes.

## Child DOX Index

No child DOX files.
