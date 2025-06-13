import asyncio
from datetime import datetime, timezone, timedelta
import os
import random
import threading
from urllib.parse import urlparse
import uuid
from enum import Enum
from os.path import exists
from typing import Any, Callable, Dict, Literal, Optional, Type, TypeVar, Union, cast, ClassVar

import nest_asyncio
nest_asyncio.apply()

from crontab import CronTab
from pydantic import BaseModel, Field, PrivateAttr

from agent import Agent, AgentContext, UserMessage
from initialize import initialize_agent
from python.helpers.persist_chat import save_tmp_chat
from python.helpers.print_style import PrintStyle
from python.helpers.defer import DeferredTask
from python.helpers.files import get_abs_path, make_dirs, read_file, write_file
from python.helpers.localization import Localization
import pytz
from typing import Annotated

SCHEDULER_FOLDER = "tmp/scheduler"

# ----------------------
# Task Models
# ----------------------


class TaskState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DISABLED = "disabled"
    ERROR = "error"


class TaskType(str, Enum):
    AD_HOC = "adhoc"
    SCHEDULED = "scheduled"
    PLANNED = "planned"


class TaskSchedule(BaseModel):
    minute: str
    hour: str
    day: str
    month: str
    weekday: str
    timezone: str = Field(default_factory=lambda: Localization.get().get_timezone())

    def to_crontab(self) -> str:
        return f"{self.minute} {self.hour} {self.day} {self.month} {self.weekday}"


class TaskPlan(BaseModel):
    todo: list[datetime] = Field(default_factory=list)
    in_progress: datetime | None = None
    done: list[datetime] = Field(default_factory=list)

    @classmethod
    def create(cls, todo: list[datetime] = list(), in_progress: datetime | None = None, done: list[datetime] = list()):
        if todo:
            for idx, dt in enumerate(todo):
                if dt.tzinfo is None:
                    todo[idx] = pytz.timezone("UTC").localize(dt)
        if in_progress:
            if in_progress.tzinfo is None:
                in_progress = pytz.timezone("UTC").localize(in_progress)
        if done:
            for idx, dt in enumerate(done):
                if dt.tzinfo is None:
                    done[idx] = pytz.timezone("UTC").localize(dt)
        return cls(todo=todo, in_progress=in_progress, done=done)

    def add_todo(self, launch_time: datetime):
        if launch_time.tzinfo is None:
            launch_time = pytz.timezone("UTC").localize(launch_time)
        self.todo.append(launch_time)
        self.todo = sorted(self.todo)

    def set_in_progress(self, launch_time: datetime):
        if launch_time.tzinfo is None:
            launch_time = pytz.timezone("UTC").localize(launch_time)
        if launch_time not in self.todo:
            raise ValueError(f"Launch time {launch_time} not in todo list")
        self.todo.remove(launch_time)
        self.todo = sorted(self.todo)
        self.in_progress = launch_time

    def set_done(self, launch_time: datetime):
        if launch_time.tzinfo is None:
            launch_time = pytz.timezone("UTC").localize(launch_time)
        if launch_time != self.in_progress:
            raise ValueError(f"Launch time {launch_time} is not the same as in progress time {self.in_progress}")
        if launch_time in self.done:
            raise ValueError(f"Launch time {launch_time} already in done list")
        self.in_progress = None
        self.done.append(launch_time)
        self.done = sorted(self.done)

    def get_next_launch_time(self) -> datetime | None:
        return self.todo[0] if self.todo else None

    def should_launch(self) -> datetime | None:
        next_launch_time = self.get_next_launch_time()
        if next_launch_time is None:
            return None
        # return next launch time if current datetime utc is later than next launch time
        if datetime.now(timezone.utc) > next_launch_time:
            return next_launch_time
        return None


class BaseTask(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: Optional[str] = Field(default=None)
    state: TaskState = Field(default=TaskState.IDLE)
    name: str = Field()
    system_prompt: str
    prompt: str
    attachments: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_run: datetime | None = None
    last_result: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.context_id:
            self.context_id = self.uuid
        self._lock = threading.RLock()

    def update(self,
               name: str | None = None,
               state: TaskState | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
               last_run: datetime | None = None,
               last_result: str | None = None,
               context_id: str | None = None,
               **kwargs):
        with self._lock:
            if name is not None:
                self.name = name
                self.updated_at = datetime.now(timezone.utc)
            if state is not None:
                self.state = state
                self.updated_at = datetime.now(timezone.utc)
            if system_prompt is not None:
                self.system_prompt = system_prompt
                self.updated_at = datetime.now(timezone.utc)
            if prompt is not None:
                self.prompt = prompt
                self.updated_at = datetime.now(timezone.utc)
            if attachments is not None:
                self.attachments = attachments
                self.updated_at = datetime.now(timezone.utc)
            if last_run is not None:
                self.last_run = last_run
                self.updated_at = datetime.now(timezone.utc)
            if last_result is not None:
                self.last_result = last_result
                self.updated_at = datetime.now(timezone.utc)
            if context_id is not None:
                self.context_id = context_id
                self.updated_at = datetime.now(timezone.utc)
            for key, value in kwargs.items():
                if value is not None:
                    setattr(self, key, value)
                    self.updated_at = datetime.now(timezone.utc)

    def check_schedule(self, frequency_seconds: float = 60.0) -> bool:
        return False

    def get_next_run(self) -> datetime | None:
        return None

    def get_next_run_minutes(self) -> int | None:
        next_run = self.get_next_run()
        if next_run is None:
            return None
        return int((next_run - datetime.now(timezone.utc)).total_seconds() / 60)

    async def on_run(self):
        pass

    async def on_finish(self):
        # Ensure that updated_at is refreshed to reflect completion time
        # This helps track when the task actually finished, regardless of success/error
        await TaskScheduler.get().update_task(
            self.uuid,
            updated_at=datetime.now(timezone.utc)
        )

    async def on_error(self, error: str):
        # Update task state to ERROR and set last result
        scheduler = TaskScheduler.get()
        await scheduler.reload()  # Ensure we have the latest state
        updated_task = await scheduler.update_task(
            self.uuid,
            state=TaskState.ERROR,
            last_run=datetime.now(timezone.utc),
            last_result=f"ERROR: {error}"
        )
        if not updated_task:
            PrintStyle(italic=True, font_color="red", padding=False).print(
                f"Failed to update task {self.uuid} state to ERROR after error: {error}"
            )
        await scheduler.save()  # Force save after update

    async def on_success(self, result: str):
        # Update task state to IDLE and set last result
        scheduler = TaskScheduler.get()
        await scheduler.reload()  # Ensure we have the latest state
        updated_task = await scheduler.update_task(
            self.uuid,
            state=TaskState.IDLE,
            last_run=datetime.now(timezone.utc),
            last_result=result
        )
        if not updated_task:
            PrintStyle(italic=True, font_color="red", padding=False).print(
                f"Failed to update task {self.uuid} state to IDLE after success"
            )
        await scheduler.save()  # Force save after update


class AdHocTask(BaseTask):
    type: Literal[TaskType.AD_HOC] = TaskType.AD_HOC
    token: str = Field(default_factory=lambda: str(random.randint(1000000000000000000, 9999999999999999999)))

    @classmethod
    def create(
        cls,
        name: str,
        system_prompt: str,
        prompt: str,
        token: str,
        attachments: list[str] = list(),
        context_id: str | None = None
    ):
        return cls(name=name,
                   system_prompt=system_prompt,
                   prompt=prompt,
                   attachments=attachments,
                   token=token,
                   context_id=context_id)

    def update(self,
               name: str | None = None,
               state: TaskState | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
               last_run: datetime | None = None,
               last_result: str | None = None,
               context_id: str | None = None,
               token: str | None = None,
               **kwargs):
        super().update(name=name,
                       state=state,
                       system_prompt=system_prompt,
                       prompt=prompt,
                       attachments=attachments,
                       last_run=last_run,
                       last_result=last_result,
                       context_id=context_id,
                       token=token,
                       **kwargs)


class ScheduledTask(BaseTask):
    type: Literal[TaskType.SCHEDULED] = TaskType.SCHEDULED
    schedule: TaskSchedule

    @classmethod
    def create(
        cls,
        name: str,
        system_prompt: str,
        prompt: str,
        schedule: TaskSchedule,
        attachments: list[str] = list(),
        context_id: str | None = None,
        timezone: str | None = None
    ):
        # Set timezone in schedule if provided
        if timezone is not None:
            schedule.timezone = timezone
        else:
            schedule.timezone = Localization.get().get_timezone()

        return cls(name=name,
                   system_prompt=system_prompt,
                   prompt=prompt,
                   attachments=attachments,
                   schedule=schedule,
                   context_id=context_id)

    def update(self,
               name: str | None = None,
               state: TaskState | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
               last_run: datetime | None = None,
               last_result: str | None = None,
               context_id: str | None = None,
               schedule: TaskSchedule | None = None,
               **kwargs):
        super().update(name=name,
                       state=state,
                       system_prompt=system_prompt,
                       prompt=prompt,
                       attachments=attachments,
                       last_run=last_run,
                       last_result=last_result,
                       context_id=context_id,
                       schedule=schedule,
                       **kwargs)

    def check_schedule(self, frequency_seconds: float = 60.0) -> bool:
        with self._lock:
            crontab = CronTab(crontab=self.schedule.to_crontab())  # type: ignore

            # Get the timezone from the schedule or use UTC as fallback
            task_timezone = pytz.timezone(self.schedule.timezone or Localization.get().get_timezone())

            # Get reference time in task's timezone (by default now - frequency_seconds)
            reference_time = datetime.now(timezone.utc) - timedelta(seconds=frequency_seconds)
            reference_time = reference_time.astimezone(task_timezone)

            # Get next run time as seconds until next execution
            next_run_seconds: Optional[float] = crontab.next(  # type: ignore
                now=reference_time,
                return_datetime=False
            )  # type: ignore

            if next_run_seconds is None:
                return False

            return next_run_seconds < frequency_seconds

    def get_next_run(self) -> datetime | None:
        with self._lock:
            crontab = CronTab(crontab=self.schedule.to_crontab())  # type: ignore
            return crontab.next(now=datetime.now(timezone.utc), return_datetime=True)  # type: ignore


class PlannedTask(BaseTask):
    type: Literal[TaskType.PLANNED] = TaskType.PLANNED
    plan: TaskPlan

    @classmethod
    def create(
        cls,
        name: str,
        system_prompt: str,
        prompt: str,
        plan: TaskPlan,
        attachments: list[str] = list(),
        context_id: str | None = None
    ):
        return cls(name=name,
                   system_prompt=system_prompt,
                   prompt=prompt,
                   plan=plan,
                   attachments=attachments,
                   context_id=context_id)

    def update(self,
               name: str | None = None,
               state: TaskState | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
               last_run: datetime | None = None,
               last_result: str | None = None,
               context_id: str | None = None,
               plan: TaskPlan | None = None,
               **kwargs):
        super().update(name=name,
                       state=state,
                       system_prompt=system_prompt,
                       prompt=prompt,
                       attachments=attachments,
                       last_run=last_run,
                       last_result=last_result,
                       context_id=context_id,
                       plan=plan,
                       **kwargs)

    def check_schedule(self, frequency_seconds: float = 60.0) -> bool:
        with self._lock:
            return self.plan.should_launch() is not None

    def get_next_run(self) -> datetime | None:
        with self._lock:
            return self.plan.get_next_launch_time()

    async def on_run(self):
        with self._lock:
            # Get the next launch time and set it as in_progress
            next_launch_time = self.plan.should_launch()
            if next_launch_time is not None:
                self.plan.set_in_progress(next_launch_time)
        await super().on_run()

    async def on_finish(self):
        # Handle plan item progression regardless of success or error
        plan_updated = False

        with self._lock:
            # If there's an in_progress time, mark it as done
            if self.plan.in_progress is not None:
                self.plan.set_done(self.plan.in_progress)
                plan_updated = True

        # If we updated the plan, make sure to persist it
        if plan_updated:
            scheduler = TaskScheduler.get()
            await scheduler.reload()
            await scheduler.update_task(self.uuid, plan=self.plan)
            await scheduler.save()  # Force save

        # Call the parent implementation for any additional cleanup
        await super().on_finish()

    async def on_success(self, result: str):
        # Call parent implementation to update state, etc.
        await super().on_success(result)

    async def on_error(self, error: str):
        # Call parent implementation to update state, etc.
        await super().on_error(error)


class SchedulerTaskList(BaseModel):
    tasks: list[Annotated[Union[ScheduledTask, AdHocTask, PlannedTask], Field(discriminator="type")]] = Field(default_factory=list)
    # Singleton instance
    __instance: ClassVar[Optional["SchedulerTaskList"]] = PrivateAttr(default=None)

    # lock: threading.Lock = Field(exclude=True, default=threading.Lock())

    @classmethod
    def get(cls) -> "SchedulerTaskList":
        path = get_abs_path(SCHEDULER_FOLDER, "tasks.json")
        if cls.__instance is None:
            if not exists(path):
                make_dirs(path)
                cls.__instance = asyncio.run(cls(tasks=[]).save())
            else:
                cls.__instance = cls.model_validate_json(read_file(path))
        else:
            asyncio.run(cls.__instance.reload())
        return cls.__instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    async def reload(self) -> "SchedulerTaskList":
        path = get_abs_path(SCHEDULER_FOLDER, "tasks.json")
        if exists(path):
            with self._lock:
                data = self.__class__.model_validate_json(read_file(path))
                self.tasks.clear()
                self.tasks.extend(data.tasks)
        return self

    async def add_task(self, task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> "SchedulerTaskList":
        with self._lock:
            self.tasks.append(task)
            await self.save()
        return self

    async def save(self) -> "SchedulerTaskList":
        with self._lock:
            # Debug: check for AdHocTasks with null tokens before saving
            for task in self.tasks:
                if isinstance(task, AdHocTask):
                    if task.token is None or task.token == "":
                        PrintStyle(italic=True, font_color="red", padding=False).print(
                            f"WARNING: AdHocTask {task.name} ({task.uuid}) has a null or empty token before saving: '{task.token}'"
                        )
                        # Generate a new token to prevent errors
                        task.token = str(random.randint(1000000000000000000, 9999999999999999999))
                        PrintStyle(italic=True, font_color="red", padding=False).print(
                            f"Fixed: Generated new token '{task.token}' for task {task.name}"
                        )

            path = get_abs_path(SCHEDULER_FOLDER, "tasks.json")
            if not exists(path):
                make_dirs(path)

            # Get the JSON string before writing
            json_data = self.model_dump_json()

            # Debug: check if 'null' appears as token value in JSON
            if '"type": "adhoc"' in json_data and '"token": null' in json_data:
                PrintStyle(italic=True, font_color="red", padding=False).print(
                    "ERROR: Found null token in JSON output for an adhoc task"
                )

            write_file(path, json_data)

            # Debug: Verify after saving
            if exists(path):
                loaded_json = read_file(path)
                if '"type": "adhoc"' in loaded_json and '"token": null' in loaded_json:
                    PrintStyle(italic=True, font_color="red", padding=False).print(
                        "ERROR: Null token persisted in JSON file for an adhoc task"
                    )

        return self

    async def update_task_by_uuid(
        self,
        task_uuid: str,
        updater_func: Callable[[Union[ScheduledTask, AdHocTask, PlannedTask]], None],
        verify_func: Callable[[Union[ScheduledTask, AdHocTask, PlannedTask]], bool] = lambda task: True
    ) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        """
        Atomically update a task by UUID using the provided updater function.

        The updater_func should take the task as an argument and perform any necessary updates.
        This method ensures that the task is updated and saved atomically, preventing race conditions.

        Returns the updated task or None if not found.
        """
        with self._lock:
            # Reload to ensure we have the latest state
            await self.reload()

            # Find the task
            task = next((task for task in self.tasks if task.uuid == task_uuid and verify_func(task)), None)
            if task is None:
                return None

            # Apply the updates via the provided function
            updater_func(task)

            # Save the changes
            await self.save()

            return task

    def get_tasks(self) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        with self._lock:
            return self.tasks

    def get_tasks_by_context_id(self, context_id: str, only_running: bool = False) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        with self._lock:
            return [
                task for task in self.tasks
                if task.context_id == context_id
                and (not only_running or task.state == TaskState.RUNNING)
            ]

    async def get_due_tasks(self) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        with self._lock:
            await self.reload()
            return [
                task for task in self.tasks
                if task.check_schedule() and task.state == TaskState.IDLE
            ]

    def get_task_by_uuid(self, task_uuid: str) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        with self._lock:
            return next((task for task in self.tasks if task.uuid == task_uuid), None)

    def get_task_by_name(self, name: str) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        with self._lock:
            return next((task for task in self.tasks if task.name == name), None)

    def find_task_by_name(self, name: str) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        with self._lock:
            return [task for task in self.tasks if name.lower() in task.name.lower()]

    async def remove_task_by_uuid(self, task_uuid: str) -> "SchedulerTaskList":
        with self._lock:
            self.tasks = [task for task in self.tasks if task.uuid != task_uuid]
            await self.save()
        return self

    async def remove_task_by_name(self, name: str) -> "SchedulerTaskList":
        with self._lock:
            self.tasks = [task for task in self.tasks if task.name != name]
            await self.save()
        return self


class TaskScheduler:

    _tasks: SchedulerTaskList
    _printer: PrintStyle
    _instance = None

    @classmethod
    def get(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Only initialize if this is a new instance
        if not hasattr(self, '_initialized'):
            self._tasks = SchedulerTaskList.get()
            self._printer = PrintStyle(italic=True, font_color="green", padding=False)
            self._initialized = True

    async def reload(self):
        await self._tasks.reload()

    def get_tasks(self) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        return self._tasks.get_tasks()

    def get_tasks_by_context_id(self, context_id: str, only_running: bool = False) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        return self._tasks.get_tasks_by_context_id(context_id, only_running)

    async def add_task(self, task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> "TaskScheduler":
        await self._tasks.add_task(task)
        ctx = await self._get_chat_context(task)  # invoke context creation
        return self

    async def remove_task_by_uuid(self, task_uuid: str) -> "TaskScheduler":
        await self._tasks.remove_task_by_uuid(task_uuid)
        return self

    async def remove_task_by_name(self, name: str) -> "TaskScheduler":
        await self._tasks.remove_task_by_name(name)
        return self

    def get_task_by_uuid(self, task_uuid: str) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        return self._tasks.get_task_by_uuid(task_uuid)

    def get_task_by_name(self, name: str) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        return self._tasks.get_task_by_name(name)

    def find_task_by_name(self, name: str) -> list[Union[ScheduledTask, AdHocTask, PlannedTask]]:
        return self._tasks.find_task_by_name(name)

    async def tick(self):
        for task in await self._tasks.get_due_tasks():
            await self._run_task(task)

    async def run_task_by_uuid(self, task_uuid: str, task_context: str | None = None):
        # First reload tasks to ensure we have the latest state
        await self._tasks.reload()

        # Get the task to run
        task = self.get_task_by_uuid(task_uuid)
        if not task:
            raise ValueError(f"Task with UUID '{task_uuid}' not found")

        # If the task is already running, raise an error
        if task.state == TaskState.RUNNING:
            raise ValueError(f"Task '{task.name}' is already running")

        # If the task is disabled, raise an error
        if task.state == TaskState.DISABLED:
            raise ValueError(f"Task '{task.name}' is disabled")

        # If the task is in error state, reset it to IDLE first
        if task.state == TaskState.ERROR:
            self._printer.print(f"Resetting task '{task.name}' from ERROR to IDLE state before running")
            await self.update_task(task_uuid, state=TaskState.IDLE)
            # Force a reload to ensure we have the updated state
            await self._tasks.reload()
            task = self.get_task_by_uuid(task_uuid)
            if not task:
                raise ValueError(f"Task with UUID '{task_uuid}' not found after state reset")

        # Run the task
        await self._run_task(task, task_context)

    async def run_task_by_name(self, name: str, task_context: str | None = None):
        task = self._tasks.get_task_by_name(name)
        if task is None:
            raise ValueError(f"Task with name {name} not found")
        await self._run_task(task, task_context)

    async def save(self):
        await self._tasks.save()

    async def update_task_checked(
        self,
        task_uuid: str,
        verify_func: Callable[[Union[ScheduledTask, AdHocTask, PlannedTask]], bool] = lambda task: True,
        **update_params
    ) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        """
        Atomically update a task by UUID with the provided parameters.
        This prevents race conditions when multiple processes update tasks concurrently.

        Returns the updated task or None if not found.
        """
        def _update_task(task):
            task.update(**update_params)

        return await self._tasks.update_task_by_uuid(task_uuid, _update_task, verify_func)

    async def update_task(self, task_uuid: str, **update_params) -> Union[ScheduledTask, AdHocTask, PlannedTask] | None:
        return await self.update_task_checked(task_uuid, lambda task: True, **update_params)

    async def __new_context(self, task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> AgentContext:
        if not task.context_id:
            raise ValueError(f"Task {task.name} has no context ID")

        config = initialize_agent()
        context: AgentContext = AgentContext(config, id=task.context_id, name=task.name)
        # context.id = task.context_id
        # initial name before renaming is same as task name
        # context.name = task.name

        # Save the context
        save_tmp_chat(context)
        return context

    async def _get_chat_context(self, task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> AgentContext:
        context = AgentContext.get(task.context_id) if task.context_id else None

        if context:
            assert isinstance(context, AgentContext)
            self._printer.print(
                f"Scheduler Task {task.name} loaded from task {task.uuid}, context ok"
            )
            save_tmp_chat(context)
            return context
        else:
            self._printer.print(
                f"Scheduler Task {task.name} loaded from task {task.uuid} but context not found"
            )
            return await self.__new_context(task)

    async def _persist_chat(self, task: Union[ScheduledTask, AdHocTask, PlannedTask], context: AgentContext):
        if context.id != task.context_id:
            raise ValueError(f"Context ID mismatch for task {task.name}: context {context.id} != task {task.context_id}")
        save_tmp_chat(context)

    async def _run_task(self, task: Union[ScheduledTask, AdHocTask, PlannedTask], task_context: str | None = None):

        async def _run_task_wrapper(task_uuid: str, task_context: str | None = None):

            # preflight checks with a snapshot of the task
            task_snapshot: Union[ScheduledTask, AdHocTask, PlannedTask] | None = self.get_task_by_uuid(task_uuid)
            if task_snapshot is None:
                self._printer.print(f"Scheduler Task with UUID '{task_uuid}' not found")
                return
            if task_snapshot.state == TaskState.RUNNING:
                self._printer.print(f"Scheduler Task '{task_snapshot.name}' already running, skipping")
                return

            # Atomically fetch and check the task's current state
            current_task = await self.update_task_checked(task_uuid, lambda task: task.state != TaskState.RUNNING, state=TaskState.RUNNING)
            if not current_task:
                self._printer.print(f"Scheduler Task with UUID '{task_uuid}' not found or updated by another process")
                return
            if current_task.state != TaskState.RUNNING:
                # This means the update failed due to state conflict
                self._printer.print(f"Scheduler Task '{current_task.name}' state is '{current_task.state}', skipping")
                return

            await current_task.on_run()

            # the agent instance - init in try block
            agent = None

            try:
                self._printer.print(f"Scheduler Task '{current_task.name}' started")

                context = await self._get_chat_context(current_task)

                # Ensure the context is properly registered in the AgentContext._contexts
                # This is critical for the polling mechanism to find and stream logs
                # Dict operations are atomic
                # AgentContext._contexts[context.id] = context
                agent = context.streaming_agent or context.agent0

                # Prepare attachment filenames for logging
                attachment_filenames = []
                if current_task.attachments:
                    for attachment in current_task.attachments:
                        if os.path.exists(attachment):
                            attachment_filenames.append(attachment)
                        else:
                            try:
                                url = urlparse(attachment)
                                if url.scheme in ["http", "https", "ftp", "ftps", "sftp"]:
                                    attachment_filenames.append(attachment)
                                else:
                                    self._printer.print(f"Skipping attachment: [{attachment}]")
                            except Exception:
                                self._printer.print(f"Skipping attachment: [{attachment}]")

                self._printer.print("User message:")
                self._printer.print(f"> {current_task.prompt}")
                if attachment_filenames:
                    self._printer.print("Attachments:")
                    for filename in attachment_filenames:
                        self._printer.print(f"- {filename}")

                task_prompt = f"# Starting scheduler task '{current_task.name}' ({current_task.uuid})"
                if task_context:
                    task_prompt = f"## Context:\n{task_context}\n\n## Task:\n{current_task.prompt}"
                else:
                    task_prompt = f"## Task:\n{current_task.prompt}"

                # Log the message with message_id and attachments
                context.log.log(
                    type="user",
                    heading="User message",
                    content=task_prompt,
                    kvps={"attachments": attachment_filenames},
                    id=str(uuid.uuid4()),
                )

                agent.hist_add_user_message(
                    UserMessage(
                        message=task_prompt,
                        system_message=[current_task.system_prompt],
                        attachments=attachment_filenames))

                # Persist after setting up the context but before running the agent
                # This ensures the task context is saved and can be found by polling
                await self._persist_chat(current_task, context)

                result = await agent.monologue()

                # Success
                self._printer.print(f"Scheduler Task '{current_task.name}' completed: {result}")
                await self._persist_chat(current_task, context)
                await current_task.on_success(result)

                # Explicitly verify task was updated in storage after success
                await self._tasks.reload()
                updated_task = self.get_task_by_uuid(task_uuid)
                if updated_task and updated_task.state != TaskState.IDLE:
                    self._printer.print(f"Fixing task state consistency: '{current_task.name}' state is not IDLE after success")
                    await self.update_task(task_uuid, state=TaskState.IDLE)

            except Exception as e:
                # Error
                self._printer.print(f"Scheduler Task '{current_task.name}' failed: {e}")
                await current_task.on_error(str(e))

                # Explicitly verify task was updated in storage after error
                await self._tasks.reload()
                updated_task = self.get_task_by_uuid(task_uuid)
                if updated_task and updated_task.state != TaskState.ERROR:
                    self._printer.print(f"Fixing task state consistency: '{current_task.name}' state is not ERROR after failure")
                    await self.update_task(task_uuid, state=TaskState.ERROR)

                if agent:
                    agent.handle_critical_exception(e)
            finally:
                # Call on_finish for task-specific cleanup
                await current_task.on_finish()

                # Make one final save to ensure all states are persisted
                await self._tasks.save()

        deferred_task = DeferredTask(thread_name=self.__class__.__name__)
        deferred_task.start_task(_run_task_wrapper, task.uuid, task_context)

        # Ensure background execution doesn't exit immediately on async await, especially in script contexts
        # This helps prevent premature exits when running from non-event-loop contexts
        asyncio.create_task(asyncio.sleep(0.1))

    def serialize_all_tasks(self) -> list[Dict[str, Any]]:
        """
        Serialize all tasks in the scheduler to a list of dictionaries.
        """
        return serialize_tasks(self.get_tasks())

    def serialize_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Serialize a specific task in the scheduler by UUID.
        Returns None if task is not found.
        """
        # Get task without locking, as get_task_by_uuid() is already thread-safe
        task = self.get_task_by_uuid(task_id)
        if task:
            return serialize_task(task)
        return None


# ----------------------
# Task Serialization Helpers
# ----------------------

def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Serialize a datetime object to ISO format string in the user's timezone.

    This uses the Localization singleton to convert the datetime to the user's timezone
    before serializing it to an ISO format string for frontend display.

    Returns None if the input is None.
    """
    # Use the Localization singleton for timezone conversion and serialization
    return Localization.get().serialize_datetime(dt)


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO format datetime string with timezone awareness.

    This converts from the localized ISO format returned by serialize_datetime
    back to a datetime object with proper timezone handling.

    Returns None if dt_str is None.
    """
    if not dt_str:
        return None

    try:
        # Use the Localization singleton for consistent timezone handling
        return Localization.get().localtime_str_to_utc_dt(dt_str)
    except ValueError as e:
        raise ValueError(f"Invalid datetime format: {dt_str}. Expected ISO format. Error: {e}")


def serialize_task_schedule(schedule: TaskSchedule) -> Dict[str, str]:
    """Convert TaskSchedule to a standardized dictionary format."""
    return {
        'minute': schedule.minute,
        'hour': schedule.hour,
        'day': schedule.day,
        'month': schedule.month,
        'weekday': schedule.weekday,
        'timezone': schedule.timezone
    }


def parse_task_schedule(schedule_data: Dict[str, str]) -> TaskSchedule:
    """Parse dictionary into TaskSchedule with validation."""
    try:
        return TaskSchedule(
            minute=schedule_data.get('minute', '*'),
            hour=schedule_data.get('hour', '*'),
            day=schedule_data.get('day', '*'),
            month=schedule_data.get('month', '*'),
            weekday=schedule_data.get('weekday', '*'),
            timezone=schedule_data.get('timezone', Localization.get().get_timezone())
        )
    except Exception as e:
        raise ValueError(f"Invalid schedule format: {e}") from e


def serialize_task_plan(plan: TaskPlan) -> Dict[str, Any]:
    """Convert TaskPlan to a standardized dictionary format."""
    return {
        'todo': [serialize_datetime(dt) for dt in plan.todo],
        'in_progress': serialize_datetime(plan.in_progress) if plan.in_progress else None,
        'done': [serialize_datetime(dt) for dt in plan.done]
    }


def parse_task_plan(plan_data: Dict[str, Any]) -> TaskPlan:
    """Parse dictionary into TaskPlan with validation."""
    try:
        # Handle case where plan_data might be None or empty
        if not plan_data:
            return TaskPlan(todo=[], in_progress=None, done=[])

        # Parse todo items with careful validation
        todo_dates = []
        for dt_str in plan_data.get('todo', []):
            if dt_str:
                parsed_dt = parse_datetime(dt_str)
                if parsed_dt:
                    # Ensure datetime is timezone-aware (use UTC if not specified)
                    if parsed_dt.tzinfo is None:
                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                    todo_dates.append(parsed_dt)

        # Parse in_progress with validation
        in_progress = None
        if plan_data.get('in_progress'):
            in_progress = parse_datetime(plan_data.get('in_progress'))
            # Ensure datetime is timezone-aware
            if in_progress and in_progress.tzinfo is None:
                in_progress = in_progress.replace(tzinfo=timezone.utc)

        # Parse done items with validation
        done_dates = []
        for dt_str in plan_data.get('done', []):
            if dt_str:
                parsed_dt = parse_datetime(dt_str)
                if parsed_dt:
                    # Ensure datetime is timezone-aware
                    if parsed_dt.tzinfo is None:
                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                    done_dates.append(parsed_dt)

        # Sort dates for better usability
        todo_dates.sort()
        done_dates.sort(reverse=True)  # Most recent first for done items

        # Cast to ensure type safety
        todo_dates_cast: list[datetime] = cast(list[datetime], todo_dates)
        done_dates_cast: list[datetime] = cast(list[datetime], done_dates)

        return TaskPlan.create(
            todo=todo_dates_cast,
            in_progress=in_progress,
            done=done_dates_cast
        )
    except Exception as e:
        PrintStyle(italic=True, font_color="red", padding=False).print(
            f"Error parsing task plan: {e}"
        )
        # Return empty plan instead of failing
        return TaskPlan(todo=[], in_progress=None, done=[])


T = TypeVar('T', bound=Union[ScheduledTask, AdHocTask, PlannedTask])


def serialize_task(task: Union[ScheduledTask, AdHocTask, PlannedTask]) -> Dict[str, Any]:
    """
    Standardized serialization for task objects with proper handling of all complex types.
    """
    # Start with a basic dictionary
    task_dict = {
        "uuid": task.uuid,
        "name": task.name,
        "state": task.state,
        "system_prompt": task.system_prompt,
        "prompt": task.prompt,
        "attachments": task.attachments,
        "created_at": serialize_datetime(task.created_at),
        "updated_at": serialize_datetime(task.updated_at),
        "last_run": serialize_datetime(task.last_run),
        "next_run": serialize_datetime(task.get_next_run()),
        "last_result": task.last_result,
        "context_id": task.context_id
    }

    # Add type-specific fields
    if isinstance(task, ScheduledTask):
        task_dict['type'] = 'scheduled'
        task_dict['schedule'] = serialize_task_schedule(task.schedule)  # type: ignore
    elif isinstance(task, AdHocTask):
        task_dict['type'] = 'adhoc'
        adhoc_task = cast(AdHocTask, task)
        task_dict['token'] = adhoc_task.token
    else:
        task_dict['type'] = 'planned'
        planned_task = cast(PlannedTask, task)
        task_dict['plan'] = serialize_task_plan(planned_task.plan)  # type: ignore

    return task_dict


def serialize_tasks(tasks: list[Union[ScheduledTask, AdHocTask, PlannedTask]]) -> list[Dict[str, Any]]:
    """
    Serialize a list of tasks to a list of dictionaries.
    """
    return [serialize_task(task) for task in tasks]


def deserialize_task(task_data: Dict[str, Any], task_class: Optional[Type[T]] = None) -> T:
    """
    Deserialize dictionary into appropriate task object with validation.
    If task_class is provided, uses that type. Otherwise determines type from data.
    """
    task_type_str = task_data.get('type', '')
    determined_class = None

    if not task_class:
        # Determine task class from data
        if task_type_str == 'scheduled':
            determined_class = cast(Type[T], ScheduledTask)
        elif task_type_str == 'adhoc':
            determined_class = cast(Type[T], AdHocTask)
            # Ensure token is a valid non-empty string
            if not task_data.get('token'):
                task_data['token'] = str(random.randint(1000000000000000000, 9999999999999999999))
        elif task_type_str == 'planned':
            determined_class = cast(Type[T], PlannedTask)
        else:
            raise ValueError(f"Unknown task type: {task_type_str}")
    else:
        determined_class = task_class
        # If this is an AdHocTask, ensure token is valid
        if determined_class == AdHocTask and not task_data.get('token'):  # type: ignore
            task_data['token'] = str(random.randint(1000000000000000000, 9999999999999999999))

    common_args = {
        "uuid": task_data.get("uuid"),
        "name": task_data.get("name"),
        "state": TaskState(task_data.get("state", TaskState.IDLE)),
        "system_prompt": task_data.get("system_prompt", ""),
        "prompt": task_data.get("prompt", ""),
        "attachments": task_data.get("attachments", []),
        "created_at": parse_datetime(task_data.get("created_at")),
        "updated_at": parse_datetime(task_data.get("updated_at")),
        "last_run": parse_datetime(task_data.get("last_run")),
        "last_result": task_data.get("last_result"),
        "context_id": task_data.get("context_id")
    }

    # Add type-specific fields
    if determined_class == ScheduledTask:  # type: ignore
        schedule_data = task_data.get("schedule", {})
        common_args["schedule"] = parse_task_schedule(schedule_data)
        return ScheduledTask(**common_args)  # type: ignore
    elif determined_class == AdHocTask:  # type: ignore
        common_args["token"] = task_data.get("token", "")
        return AdHocTask(**common_args)  # type: ignore
    else:
        plan_data = task_data.get("plan", {})
        common_args["plan"] = parse_task_plan(plan_data)
        return PlannedTask(**common_args)  # type: ignore
