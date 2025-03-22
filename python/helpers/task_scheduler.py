import uuid
import random
import os
from datetime import datetime, timezone
import threading
import asyncio
import nest_asyncio
nest_asyncio.apply()

from typing import Union, Literal, Optional

from crontab import CronTab
from pydantic import BaseModel, Field, PrivateAttr
from python.helpers.files import get_abs_path, exists, write_file, read_file, make_dirs
from agent import Agent, AgentContext, UserMessage
from initialize import initialize
from python.helpers.persist_chat import export_json_chat, load_json_chats, load_tmp_chats, save_tmp_chat
from python.helpers.print_style import PrintStyle
from python.helpers.defer import DeferredTask
from python.helpers.persist_chat import CHATS_FOLDER, TASKS_FOLDER
from python.helpers import errors

SCHEDULER_FOLDER = "memory/scheduler"


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
    state: Literal["idle", "running", "disabled"] = Field(default="idle")
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
        self._lock = threading.Lock()

    def update(self,
               name: str | None = None,
               state: Literal["idle", "running", "disabled"] | None = None,
               system_prompt: str | None = None,
               prompt: str | None = None,
               attachments: list[str] | None = None,
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
            if last_run is not None:
                self.last_run = last_run
                self.updated_at = datetime.now(timezone.utc)
            if last_result is not None:
                self.last_result = last_result
                self.updated_at = datetime.now(timezone.utc)

    def check_schedule(self) -> bool:
        with self._lock:
            return False


class ScheduledTask(BaseModel):
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: Literal["idle", "running", "disabled"] = Field(default="idle")
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
        self._lock = threading.Lock()

    def update(self,
               name: str | None = None,
               state: Literal["idle", "running", "disabled"] | None = None,
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
            next_run: float | None = crontab.next(now=datetime.now(timezone.utc), return_datetime=False)
            if next_run is None:
                return False
            return next_run < frequency_seconds

    def run(self):
        pass


class SchedulerTaskList(BaseModel):
    tasks: list[Union[ScheduledTask, AdHocTask]]

    # lock: threading.Lock = Field(exclude=True, default=threading.Lock())

    @classmethod
    def get(cls) -> "SchedulerTaskList":
        path = get_abs_path(SCHEDULER_FOLDER, "tasks.json")
        if not exists(path):
            make_dirs(path)
            instance = asyncio.run(cls(tasks=[]).save())
        else:
            instance = cls.model_validate_json(read_file(path))
        return instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()

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

    @classmethod
    def get(cls) -> "TaskScheduler":
        return cls()

    def __init__(self):
        self._tasks = SchedulerTaskList.get()
        self._printer = PrintStyle(italic=True, font_color="green", padding=False)

    async def tick(self):
        for task in self._tasks.get_due_tasks():
            await self._run_task(task)

    async def run_task_by_uuid(self, task_uuid: str):
        task = self._tasks.get_task_by_uuid(task_uuid)
        if task is None:
            raise ValueError(f"Task with UUID {task_uuid} not found")
        await self._run_task(task)

    async def run_task_by_name(self, name: str):
        task = self._tasks.get_task_by_name(name)
        if task is None:
            raise ValueError(f"Task with name {name} not found")
        await self._run_task(task)

    async def __new_context(self, task: Union[ScheduledTask, AdHocTask]) -> AgentContext:
        config = initialize()
        context: AgentContext = AgentContext(config)
        context.id = task.uuid
        # chat_json = export_json_chat(context)
        # chat_file = get_abs_path(TASKS_FOLDER, task.uuid, "chat.json")
        # make_dirs(chat_file)
        # write_file(chat_file, chat_json)
        save_tmp_chat(context, TASKS_FOLDER)
        return context

    async def _get_chat_context(self, task: Union[ScheduledTask, AdHocTask]) -> AgentContext:
        ctxids = load_tmp_chats(TASKS_FOLDER)
        # chat_file = get_abs_path(TASKS_FOLDER, task.uuid, "chat.json")
        # if exists(chat_file):
        if task.uuid in ctxids:
            # chat = read_file(chat_file)
            context = AgentContext.get(task.uuid)
            if isinstance(context, AgentContext):
                self._printer.print(
                    f"Scheduler Task {task.name} loaded from task {task.uuid}, context ok"
                )
                context.id = task.uuid
                save_tmp_chat(context, TASKS_FOLDER)
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
        # chat_json = export_json_chat(context)
        # chat_file = get_abs_path(TASKS_FOLDER, task.uuid, "chat.json")
        # make_dirs(chat_file)
        # write_file(chat_file, chat_json)
        context.id = task.uuid
        save_tmp_chat(context, TASKS_FOLDER)

    async def _run_task(self, task: Union[ScheduledTask, AdHocTask]):

        async def _run_task_wrapper(task: Union[ScheduledTask, AdHocTask]):
            if task.state != "idle":
                self._printer.print(f"Scheduler Task {task.name} state is '{task.state}', skipping")
                return

            if task.state == "running":
                self._printer.print(f"Scheduler Task {task.name} already running, skipping")
                return

            try:
                self._printer.print(f"Scheduler Task {task.name} started")

                task.update(state="running")
                await self._tasks.save()

                context = await self._get_chat_context(task)
                agent = Agent(0, context.config, context)

                # Prepare attachment filenames for logging
                attachment_filenames = []
                if task.attachments:
                    for attachment in task.attachments:
                        if os.path.exists(attachment):
                            attachment_filenames.append(os.path.basename(attachment))

                self._printer.print("User message:")
                self._printer.print(f"> {task.prompt}")
                if attachment_filenames:
                    self._printer.print("Attachments:")
                    for filename in attachment_filenames:
                        self._printer.print(f"- {filename}")

                # Log the message with message_id and attachments
                context.log.log(
                    type="user",
                    heading="User message",
                    content=task.prompt,
                    kvps={"attachments": attachment_filenames},
                    id=str(uuid.uuid4()),
                )

                agent.hist_add_user_message(
                    UserMessage(
                        message=task.prompt,
                        attachments=[]))

                await self._persist_chat(task, context)

                result = await agent.monologue()
                task.update(last_result="SUCCESS: " + result)

                self._printer.print(f"Scheduler Task '{task.name}' completed: {result}")

                await self._persist_chat(task, context)

            except Exception as e:
                self._printer.print(f"Scheduler Task {task.name} failed: {e}")
                task.update(last_result=f"ERROR: {str(e)}")
                if agent:
                    agent.handle_critical_exception(e)

            finally:
                try:
                    task.update(
                        state="idle",
                        last_run=datetime.now(timezone.utc)
                    )
                    await self._tasks.save()
                except Exception as e:
                    self._printer.print(f"Scheduler Task {task.name} failed to save: {e}")

        deferred_task = DeferredTask(thread_name=self.__class__.__name__)
        deferred_task.start_task(_run_task_wrapper, task)
