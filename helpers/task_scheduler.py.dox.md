# task_scheduler.py DOX

## Purpose

- Own the `task_scheduler.py` helper module.
- This module models, serializes, schedules, runs, and persists scheduled tasks.
- Keep this file-level DOX profile synchronized with `task_scheduler.py` because this directory is intentionally flat.

## Ownership

- `task_scheduler.py` owns the runtime implementation.
- `task_scheduler.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `TaskState` (`str`, `Enum`)
- `TaskType` (`str`, `Enum`)
- `TaskSchedule` (`BaseModel`)
  - `to_crontab(self) -> str`
- `TaskPlan` (`BaseModel`)
  - `create(cls, todo: list[datetime] | None=..., in_progress: datetime | None=..., done: list[datetime] | None=...)`
  - `add_todo(self, launch_time: datetime)`
  - `set_in_progress(self, launch_time: datetime)`
  - `set_done(self, launch_time: datetime)`
  - `get_next_launch_time(self) -> datetime | None`
  - `should_launch(self) -> datetime | None`
- `BaseTask` (`BaseModel`)
  - `update(self, name: str | None=..., state: TaskState | None=..., system_prompt: str | None=..., prompt: str | None=..., attachments: list[str] | None=..., last_run: datetime | None=..., last_result: str | None=..., context_id: str | None=..., **kwargs)`
  - `check_schedule(self, frequency_seconds: float=...) -> bool`
  - `get_next_run(self) -> datetime | None`
  - `is_dedicated(self) -> bool`
  - `get_next_run_minutes(self) -> int | None`
  - `async on_run(self)`
  - `async on_finish(self)`
  - `async on_error(self, error: str)`
- `AdHocTask` (`BaseTask`)
  - `create(cls, name: str, system_prompt: str, prompt: str, token: str, attachments: list[str] | None=..., context_id: str | None=..., project_name: str | None=..., project_color: str | None=...)`
  - `update(self, name: str | None=..., state: TaskState | None=..., system_prompt: str | None=..., prompt: str | None=..., attachments: list[str] | None=..., last_run: datetime | None=..., last_result: str | None=..., context_id: str | None=..., token: str | None=..., **kwargs)`
- `ScheduledTask` (`BaseTask`)
  - `create(cls, name: str, system_prompt: str, prompt: str, schedule: TaskSchedule, attachments: list[str] | None=..., context_id: str | None=..., timezone: str | None=..., project_name: str | None=..., project_color: str | None=...)`
  - `update(self, name: str | None=..., state: TaskState | None=..., system_prompt: str | None=..., prompt: str | None=..., attachments: list[str] | None=..., last_run: datetime | None=..., last_result: str | None=..., context_id: str | None=..., schedule: TaskSchedule | None=..., **kwargs)`
  - `check_schedule(self, frequency_seconds: float=...) -> bool`
  - `get_next_run(self) -> datetime | None`
- `PlannedTask` (`BaseTask`)
  - `create(cls, name: str, system_prompt: str, prompt: str, plan: TaskPlan, attachments: list[str] | None=..., context_id: str | None=..., project_name: str | None=..., project_color: str | None=...)`
  - `update(self, name: str | None=..., state: TaskState | None=..., system_prompt: str | None=..., prompt: str | None=..., attachments: list[str] | None=..., last_run: datetime | None=..., last_result: str | None=..., context_id: str | None=..., plan: TaskPlan | None=..., **kwargs)`
  - `check_schedule(self, frequency_seconds: float=...) -> bool`
  - `get_next_run(self) -> datetime | None`
  - `async on_run(self)`
  - `async on_finish(self)`
  - `async on_success(self, result: str)`
  - `async on_error(self, error: str)`
- `SchedulerTaskList` (`BaseModel`)
  - `get(cls) -> 'SchedulerTaskList'`
  - `async reload(self) -> 'SchedulerTaskList'`
  - `async add_task(self, task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> 'SchedulerTaskList'`
  - `async save(self) -> 'SchedulerTaskList'`
  - `async update_task_by_uuid(self, task_uuid: str, updater_func: Callable[[Union[ScheduledTask, AdHocTask, PlannedTask]], None], verify_func: Callable[[Union[ScheduledTask, AdHocTask, PlannedTask]], bool]=...) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None`
  - `get_tasks(self) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]`
  - `get_tasks_by_context_id(self, context_id: str, only_running: bool=...) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]`
  - `async get_due_tasks(self) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]`
- `TaskScheduler` (no explicit base class)
  - `get(cls) -> 'TaskScheduler'`
  - `cancel_running_task(self, task_uuid: str, terminate_thread: bool=...) -> bool`
  - `cancel_tasks_by_context(self, context_id: str, terminate_thread: bool=...) -> bool`
  - `async reload(self)`
  - `get_tasks(self) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]`
  - `get_tasks_by_context_id(self, context_id: str, only_running: bool=...) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]`
  - `async add_task(self, task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> 'TaskScheduler'`
  - `async remove_task_by_uuid(self, task_uuid: str) -> 'TaskScheduler'`
- Top-level functions:
- `normalize_schedule_timezone(timezone_name: str | None) -> str`
- `_now() -> datetime`
- `_localize_task_datetime(dt: datetime) -> datetime`
- `serialize_datetime(dt: Optional[datetime]) -> Optional[str]`: Serialize a datetime object to ISO format string in the user's timezone.
- `parse_datetime(dt_str: Optional[str]) -> Optional[datetime]`: Parse ISO format datetime string with timezone awareness.
- `serialize_task_schedule(schedule: TaskSchedule) -> Dict[str, str]`: Convert TaskSchedule to a standardized dictionary format.
- `parse_task_schedule(schedule_data: Dict[str, str]) -> TaskSchedule`: Parse dictionary into TaskSchedule with validation.
- `serialize_task_plan(plan: TaskPlan) -> Dict[str, Any]`: Convert TaskPlan to a standardized dictionary format.
- `parse_task_plan(plan_data: Dict[str, Any]) -> TaskPlan`: Parse dictionary into TaskPlan with validation.
- `serialize_task(task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> Dict[str, Any]`: Standardized serialization for task objects with proper handling of all complex types.
- `serialize_tasks(tasks: list[Union[ScheduledTask, AdHocTask, PlannedTask]]) -> list[Dict[str, Any]]`: Serialize a list of tasks to a list of dictionaries.
- `deserialize_task(task_data: Dict[str, Any], task_class: Optional[Type[T]]=...) -> T`: Deserialize dictionary into appropriate task object with validation.
- Notable constants/configuration names: `SCHEDULER_FOLDER`, `LOCAL_TIMEZONE_ALIASES`, `T`.

## Runtime Contracts

- Durable scheduler cancellation fences the owned workflow before cancelling its handle and never terminates the shared AgentContext event loop. Legacy scheduler handles retain their explicit thread-termination option. When called inside an API event loop, the checked cancellation projection runs on one helper thread so planned occurrences are consumed without nesting asyncio loops.
- Durable registration callbacks bind the concrete future and input identity; completion of an earlier occurrence cannot unregister a newer invocation that reuses the same DeferredTask object.

- `SchedulerTaskList` keeps `usr/scheduler/tasks.json` as its default and prefers it when both formats exist. An existing `tasks.yaml` is supported when no JSON file exists; saves use the same selection and format. Loading never migrates, renames, or creates a second file.
- JSON retains its existing Pydantic parser and path selection. Optional YAML uses `helpers.yaml` with the same task models. Saves use an owner-only same-directory temporary file, file fsync, atomic replacement, and directory fsync on POSIX. Reject symlinks in the projection path; failed publication retains the previous file. Invalid data raises before replacing the in-memory task list; YAML comments and formatting are regenerated on save.
- Scheduler runs persist their owning task UUID in chat context data as `scheduler_task_uuid`. The `Agent.monologue/end` extension uses this association to atomically change an errored task to idle and persist its recovered result after a successful main-agent chat continuation. Legacy dedicated chats use their context ID as the task UUID; shared chats need the explicit association to avoid updating unrelated tasks. Failed continuations, subordinate results, and tasks no longer in error are ignored. Normal scheduler runs retain their existing callbacks and plan progression.
- With local durability enabled, `helpers.durable.scheduler` admits the input and stable occurrence before any RUNNING/plan mutation or model call. Due cron/planned windows use stable launch identities; explicit manual runs use fresh occurrence IDs. The coordinator's context gate rejects competing/held runs. An off backend with an existing active durable owner cannot enter the legacy path.
- The local scheduler adapter supports exact built-in task classes and pinned callback implementations. It projects the built-in success/error/finish semantics with persisted private `durable_*` occurrence/run/status receipts instead of rerunning callbacks. Planned launch progression and the receipt publish together; journal reconciliation may repeat the projection without progressing a second launch. Custom callbacks require an explicit adapter. Ordinary public task serialization omits these private receipts.
- Durable scheduler cancellation records the owning input's context cancellation before killing its task. Stale handles cannot cancel a newer input sharing the same context; stale done callbacks cannot unregister a newer task handle. Removed, reassigned, or disabled scheduler records retain the user's decision when an old durable run finishes.
- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, network calls, settings/state persistence, secret handling, scheduler state.
- Imported dependency areas include: `agent`, `asyncio`, `crontab`, `datetime`, `enum`, `helpers`, `helpers.defer`, `helpers.files`, `helpers.localization`, `helpers.persist_chat`, `helpers.print_style`, `initialize`, `nest_asyncio`, `os`, `os.path`, `pydantic`.

## Key Concepts

- Important called helpers/classes observed in the source: `nest_asyncio.apply`, `TypeVar`, `str.strip`, `callable`, `datetime.now`, `tzinfo.localize`, `Field`, `PrivateAttr`, `Localization.get.serialize_datetime`, `normalize_schedule_timezone`, `Localization.get.get_timezone`, `pytz.timezone`, `now`, `localize`, `cls`, `_localize_task_datetime`, `self.todo.remove`, `self.get_next_launch_time`, `super.__init__`, `threading.RLock`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_task_scheduler_timezone.py`
  - `tests/test_task_scheduler_recovery.py`
  - `tests/test_durable_scheduler.py` (admission, restart between projection and receipt, plan ownership, controls, custom callback holds, JSON/YAML atomic publication)
  - `tests/test_scheduler_editor.py`
  - `tests/test_timezone_regressions.py`
  - `tests/test_tool_action_contracts.py`

## Child DOX Index

No child DOX files.
