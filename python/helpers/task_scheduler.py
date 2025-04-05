import asyncio
import os
import random
import threading
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from os.path import exists
from typing import ClassVar, Literal, Optional, Union, Dict, Any, Type, TypeVar, cast

import nest_asyncio
nest_asyncio.apply()

from crontab import CronTab
from pydantic import BaseModel, Field, PrivateAttr

from agent import Agent, AgentContext, UserMessage
from initialize import initialize
from python.helpers.persist_chat import load_tmp_chats, save_tmp_chat
from python.helpers.print_style import PrintStyle
from python.helpers.defer import DeferredTask
from python.helpers.files import make_dirs, write_file, get_abs_path, read_file

SCHEDULER_FOLDER = "memory/scheduler"


# ----------------------
# Task Models
# ----------------------

class TaskState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DISABLED = "disabled"
    ERROR = "error"


class TaskSchedule(BaseModel):
    minute: str
    hour: str
    day: str
    month: str
    weekday: str

    def to_crontab(self) -> str:
        return f"{self.minute} {self.hour} {self.day} {self.month} {self.weekday}"


class AdHocTask(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = Field(default=TaskState.IDLE)
    name: str = Field()
    system_prompt: str
    prompt: str
    attachments: list[str] = Field(default_factory=list)
    token: str = Field(default_factory=lambda: str(random.randint(1000000000000000000, 9999999999999999999)))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_run: datetime | None = None
    last_result: str | None = None

    # lock: Optional[threading.Lock] = Field(exclude=True, default=threading.Lock())

    @classmethod
    def create(
        cls,
        name: str,
        system_prompt: str,
        prompt: str,
        token: str,
        attachments: list[str] = list()
    ):
        return cls(name=name,
                   system_prompt=system_prompt,
                   prompt=prompt,
                   attachments=attachments,
                   token=token)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def update(self,
               name: str | None = None,
               state: TaskState | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
               last_run: datetime | None = None,
               last_result: str | None = None,
               token: str | None = None):
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
            if token is not None:
                self.token = token
                self.updated_at = datetime.now(timezone.utc)

    def check_schedule(self) -> bool:
        with self._lock:
            return False


class ScheduledTask(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = Field(default=TaskState.IDLE)
    name: str
    schedule: TaskSchedule
    system_prompt: str
    prompt: str
    attachments: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_run: datetime | None = None
    last_result: str | None = None

    # lock: Optional[threading.Lock] = Field(exclude=True, default=threading.Lock())

    @classmethod
    def create(
        cls,
        name: str,
        system_prompt: str,
        prompt: str,
        schedule: TaskSchedule,
        attachments: list[str] = []
    ):
        return cls(name=name,
                   system_prompt=system_prompt,
                   prompt=prompt,
                   attachments=attachments,
                   schedule=schedule)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def update(self,
               name: str | None = None,
               state: TaskState | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
               schedule: TaskSchedule | None = None,
               last_run: datetime | None = None,
               last_result: str | None = None):
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
            if schedule is not None:
                self.schedule = schedule
                self.updated_at = datetime.now(timezone.utc)
            if last_run is not None:
                self.last_run = last_run
                self.updated_at = datetime.now(timezone.utc)
            if last_result is not None:
                self.last_result = last_result
                self.updated_at = datetime.now(timezone.utc)

    def check_schedule(self, frequency_seconds: float = 60.0) -> bool:
        with self._lock:
            crontab = CronTab(crontab=self.schedule.to_crontab())
            # Get next run time as seconds until next execution
            # Set reference time to now - 1 minute to avoid off-by-one
            next_run_seconds: Optional[float] = crontab.next(
                now=datetime.now(timezone.utc) - timedelta(seconds=frequency_seconds),
                return_datetime=False
            )  # type: ignore
            if next_run_seconds is None:
                return False
            return next_run_seconds < frequency_seconds

    def run(self):
        pass


class SchedulerTaskList(BaseModel):
    tasks: list[Union[ScheduledTask, AdHocTask]]

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

    async def add_task(self, task: Union[ScheduledTask, AdHocTask]) -> "SchedulerTaskList":
        with self._lock:
            self.tasks.append(task)
            await self.save()
        return self

    async def save(self) -> "SchedulerTaskList":
        with self._lock:
            path = get_abs_path(SCHEDULER_FOLDER, "tasks.json")
            if not exists(path):
                make_dirs(path)
            write_file(path, self.model_dump_json())
        return self

    async def update_task_by_uuid(self, task_uuid: str, updater_func) -> Union[ScheduledTask, AdHocTask] | None:
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
            task = next((task for task in self.tasks if task.uuid == task_uuid), None)
            if task is None:
                return None

            # Apply the updates via the provided function
            updater_func(task)

            # Save the changes
            path = get_abs_path(SCHEDULER_FOLDER, "tasks.json")
            if not exists(path):
                make_dirs(path)
            write_file(path, self.model_dump_json())

            return task

    def get_tasks(self) -> list[Union[ScheduledTask, AdHocTask]]:
        with self._lock:
            return self.tasks

    def get_due_tasks(self) -> list[Union[ScheduledTask, AdHocTask]]:
        with self._lock:
            return [task for task in self.tasks if task.check_schedule()]

    def get_task_by_uuid(self, task_uuid: str) -> Union[ScheduledTask, AdHocTask] | None:
        with self._lock:
            return next((task for task in self.tasks if task.uuid == task_uuid), None)

    def get_task_by_name(self, name: str) -> Union[ScheduledTask, AdHocTask] | None:
        with self._lock:
            return next((task for task in self.tasks if task.name == name), None)

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

    def get_tasks(self) -> list[Union[ScheduledTask, AdHocTask]]:
        return self._tasks.get_tasks()

    async def add_task(self, task: Union[ScheduledTask, AdHocTask]) -> "TaskScheduler":
        await self._tasks.add_task(task)
        return self

    async def remove_task_by_uuid(self, task_uuid: str) -> "TaskScheduler":
        await self._tasks.remove_task_by_uuid(task_uuid)
        return self

    async def remove_task_by_name(self, name: str) -> "TaskScheduler":
        await self._tasks.remove_task_by_name(name)
        return self

    def get_task_by_uuid(self, task_uuid: str) -> Union[ScheduledTask, AdHocTask] | None:
        return self._tasks.get_task_by_uuid(task_uuid)

    def get_task_by_name(self, name: str) -> Union[ScheduledTask, AdHocTask] | None:
        return self._tasks.get_task_by_name(name)

    async def tick(self):
        for task in self._tasks.get_due_tasks():
            await self._run_task(task)

    async def run_task_by_uuid(self, task_uuid: str):
        task = self._tasks.get_task_by_uuid(task_uuid)
        if task is None:
            raise ValueError(f"Task with UUID {task_uuid} not found")

        # The actual state check and running will be handled in the _run_task method
        await self._run_task(task)

    async def run_task_by_name(self, name: str):
        task = self._tasks.get_task_by_name(name)
        if task is None:
            raise ValueError(f"Task with name {name} not found")
        await self._run_task(task)

    async def save(self):
        await self._tasks.save()

    async def update_task(self, task_uuid: str, **update_params) -> Union[ScheduledTask, AdHocTask] | None:
        """
        Atomically update a task by UUID with the provided parameters.
        This prevents race conditions when multiple processes update tasks concurrently.

        Returns the updated task or None if not found.
        """
        def _update_task(task):
            task.update(**update_params)

        return await self._tasks.update_task_by_uuid(task_uuid, _update_task)

    async def __new_context(self, task: Union[ScheduledTask, AdHocTask]) -> AgentContext:
        config = initialize()
        context: AgentContext = AgentContext(config)
        context.id = task.uuid
        # Save the context
        save_tmp_chat(context)
        return context

    async def _get_chat_context(self, task: Union[ScheduledTask, AdHocTask]) -> AgentContext:
        ctxids = load_tmp_chats()

        if task.uuid in ctxids:
            context = AgentContext.get(task.uuid)
            if isinstance(context, AgentContext):
                self._printer.print(
                    f"Scheduler Task {task.name} loaded from task {task.uuid}, context ok"
                )
                context.id = task.uuid
                save_tmp_chat(context)
                return context
            else:
                self._printer.print(
                    f"Scheduler Task {task.name} loaded from task {task.uuid} but failed to load context"
                )
                return await self.__new_context(task)
        else:
            self._printer.print(
                f"Scheduler Task {task.name} loaded from task {task.uuid} but context not found"
            )
            return await self.__new_context(task)

    async def _persist_chat(self, task: Union[ScheduledTask, AdHocTask], context: AgentContext):
        context.id = task.uuid
        save_tmp_chat(context)

    async def _run_task(self, task: Union[ScheduledTask, AdHocTask]):

        async def _run_task_wrapper(task_uuid: str):

            # preflight checks with a snapshot of the task
            task_snapshot: Union[ScheduledTask, AdHocTask] | None = self.get_task_by_uuid(task_uuid)
            if task_snapshot is None:
                self._printer.print(f"Scheduler Task with UUID '{task_uuid}' not found")
                return
            if not isinstance(task_snapshot, ScheduledTask):
                self._printer.error(f"Scheduler Task '{task_snapshot.name}' is not an ScheduledTask, this should not happen, skipping")
                return
            if task_snapshot.state == TaskState.RUNNING:
                self._printer.print(f"Scheduler Task '{task_snapshot.name}' already running, skipping")
                return
            if task_snapshot.state != TaskState.IDLE:
                self._printer.print(f"Scheduler Task '{task_snapshot.name}' state is '{task_snapshot.state}', skipping")
                return

            # Atomically fetch and check the task's current state
            current_task = await self.update_task(task_uuid, state=TaskState.RUNNING)
            if not current_task:
                self._printer.print(f"Scheduler Task with UUID '{task_uuid}' not found")
                return
            if current_task.state != TaskState.RUNNING:
                # This means the update failed due to state conflict
                self._printer.print(f"Scheduler Task '{current_task.name}' state is '{current_task.state}', skipping")
                return

            try:
                self._printer.print(f"Scheduler Task '{current_task.name}' started")

                context = await self._get_chat_context(current_task)
                agent = Agent(0, context.config, context)

                # Prepare attachment filenames for logging
                attachment_filenames = []
                if current_task.attachments:
                    for attachment in current_task.attachments:
                        if os.path.exists(attachment):
                            attachment_filenames.append(os.path.basename(attachment))

                self._printer.print("User message:")
                self._printer.print(f"> {current_task.prompt}")
                if attachment_filenames:
                    self._printer.print("Attachments:")
                    for filename in attachment_filenames:
                        self._printer.print(f"- {filename}")

                # Log the message with message_id and attachments
                context.log.log(
                    type="user",
                    heading="User message",
                    content=current_task.prompt,
                    kvps={"attachments": attachment_filenames},
                    id=str(uuid.uuid4()),
                )

                agent.hist_add_user_message(
                    UserMessage(
                        message=current_task.prompt,
                        system_message=[current_task.system_prompt],
                        attachments=[]))

                await self._persist_chat(current_task, context)

                result = await agent.monologue()

                # Atomically update task state after completion
                await self.update_task(
                    task_uuid,
                    state=TaskState.IDLE,
                    last_run=datetime.now(timezone.utc),
                    last_result="SUCCESS: " + result
                )

                self._printer.print(f"Scheduler Task '{current_task.name}' completed: {result}")

                await self._persist_chat(current_task, context)

            except Exception as e:
                self._printer.print(f"Scheduler Task '{current_task.name}' failed: {e}")

                # Atomically update task state on error
                await self.update_task(
                    task_uuid,
                    state=TaskState.ERROR,
                    last_result=f"ERROR: {str(e)}"
                )

                if agent:
                    agent.handle_critical_exception(e)

        deferred_task = DeferredTask(thread_name=self.__class__.__name__)
        deferred_task.start_task(_run_task_wrapper, task.uuid)

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
    """Convert datetime to ISO format string or None if dt is None."""
    return dt.isoformat() if dt is not None else None


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO format datetime string with validation or return None if dt_str is None."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        raise ValueError(f"Invalid datetime format: {dt_str}. Expected ISO format.")


def serialize_task_schedule(schedule: TaskSchedule) -> Dict[str, str]:
    """Convert TaskSchedule to a standardized dictionary format."""
    return {
        'minute': schedule.minute,
        'hour': schedule.hour,
        'day': schedule.day,
        'month': schedule.month,
        'weekday': schedule.weekday
    }


def parse_task_schedule(schedule_data: Dict[str, str]) -> TaskSchedule:
    """Parse dictionary into TaskSchedule with validation."""
    try:
        return TaskSchedule(
            minute=schedule_data.get('minute', '*'),
            hour=schedule_data.get('hour', '*'),
            day=schedule_data.get('day', '*'),
            month=schedule_data.get('month', '*'),
            weekday=schedule_data.get('weekday', '*')
        )
    except Exception as e:
        raise ValueError(f"Invalid schedule format: {e}")


T = TypeVar('T', bound=Union[ScheduledTask, AdHocTask])


def serialize_task(task: Union[ScheduledTask, AdHocTask]) -> Dict[str, Any]:
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
        "last_result": task.last_result
    }

    # Add type-specific fields
    if isinstance(task, ScheduledTask):
        task_dict['type'] = 'scheduled'
        task_dict['schedule'] = serialize_task_schedule(task.schedule)
    else:
        task_dict['type'] = 'adhoc'
        adhoc_task = cast(AdHocTask, task)
        task_dict['token'] = adhoc_task.token

    return task_dict


def serialize_tasks(tasks: list[Union[ScheduledTask, AdHocTask]]) -> list[Dict[str, Any]]:
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
        else:
            raise ValueError(f"Unknown task type: {task_type_str}")
    else:
        determined_class = task_class

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
        "last_result": task_data.get("last_result")
    }

    # Add type-specific fields
    if determined_class == ScheduledTask:
        schedule_data = task_data.get("schedule", {})
        common_args["schedule"] = parse_task_schedule(schedule_data)
        return ScheduledTask(**common_args)  # type: ignore
    else:
        common_args["token"] = task_data.get("token", "")
        return AdHocTask(**common_args)  # type: ignore
