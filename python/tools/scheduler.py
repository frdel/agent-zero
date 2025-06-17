import asyncio
from datetime import datetime
import json
import random
import re
from python.helpers.tool import Tool, Response
from python.helpers.task_scheduler import (
    TaskScheduler, ScheduledTask, AdHocTask, PlannedTask,
    serialize_task, TaskState, TaskSchedule, TaskPlan, parse_datetime, serialize_datetime
)
from agent import AgentContext
from python.helpers import persist_chat

DEFAULT_WAIT_TIMEOUT = 300


class SchedulerTool(Tool):

    async def execute(self, **kwargs):
        if self.method == "list_tasks":
            return await self.list_tasks(**kwargs)
        elif self.method == "find_task_by_name":
            return await self.find_task_by_name(**kwargs)
        elif self.method == "show_task":
            return await self.show_task(**kwargs)
        elif self.method == "run_task":
            return await self.run_task(**kwargs)
        elif self.method == "delete_task":
            return await self.delete_task(**kwargs)
        elif self.method == "create_scheduled_task":
            return await self.create_scheduled_task(**kwargs)
        elif self.method == "create_adhoc_task":
            return await self.create_adhoc_task(**kwargs)
        elif self.method == "create_planned_task":
            return await self.create_planned_task(**kwargs)
        elif self.method == "wait_for_task":
            return await self.wait_for_task(**kwargs)
        else:
            return Response(message=f"Unknown method '{self.name}:{self.method}'", break_loop=False)

    async def list_tasks(self, **kwargs) -> Response:
        state_filter: list[str] | None = kwargs.get("state", None)
        type_filter: list[str] | None = kwargs.get("type", None)
        next_run_within_filter: int | None = kwargs.get("next_run_within", None)
        next_run_after_filter: int | None = kwargs.get("next_run_after", None)

        tasks: list[ScheduledTask | AdHocTask | PlannedTask] = TaskScheduler.get().get_tasks()
        filtered_tasks = []
        for task in tasks:
            if state_filter and task.state not in state_filter:
                continue
            if type_filter and task.type not in type_filter:
                continue
            if next_run_within_filter and task.get_next_run_minutes() is not None and task.get_next_run_minutes() > next_run_within_filter:  # type: ignore
                continue
            if next_run_after_filter and task.get_next_run_minutes() is not None and task.get_next_run_minutes() < next_run_after_filter:  # type: ignore
                continue
            filtered_tasks.append(serialize_task(task))

        return Response(message=json.dumps(filtered_tasks, indent=4), break_loop=False)

    async def find_task_by_name(self, **kwargs) -> Response:
        name: str = kwargs.get("name", None)
        if not name:
            return Response(message="Task name is required", break_loop=False)
        tasks: list[ScheduledTask | AdHocTask | PlannedTask] = TaskScheduler.get().find_task_by_name(name)
        if not tasks:
            return Response(message=f"Task not found: {name}", break_loop=False)
        return Response(message=json.dumps([serialize_task(task) for task in tasks], indent=4), break_loop=False)

    async def show_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", None)
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)
        task: ScheduledTask | AdHocTask | PlannedTask | None = TaskScheduler.get().get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)
        return Response(message=json.dumps(serialize_task(task), indent=4), break_loop=False)

    async def run_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", None)
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)
        task_context: str | None = kwargs.get("context", None)
        task: ScheduledTask | AdHocTask | PlannedTask | None = TaskScheduler.get().get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)
        await TaskScheduler.get().run_task_by_uuid(task_uuid, task_context)
        if task.context_id == self.agent.context.id:
            break_loop = True  # break loop if task is running in the same context, otherwise it would start two conversations in one window
        else:
            break_loop = False
        return Response(message=f"Task started: {task_uuid}", break_loop=break_loop)

    async def delete_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", None)
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)

        task: ScheduledTask | AdHocTask | PlannedTask | None = TaskScheduler.get().get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)

        context = None
        if task.context_id:
            context = AgentContext.get(task.context_id)

        if task.state == TaskState.RUNNING:
            if context:
                context.reset()
            await TaskScheduler.get().update_task(task_uuid, state=TaskState.IDLE)
            await TaskScheduler.get().save()

        if context and context.id == task.uuid:
            AgentContext.remove(context.id)
            persist_chat.remove_chat(context.id)

        await TaskScheduler.get().remove_task_by_uuid(task_uuid)
        if TaskScheduler.get().get_task_by_uuid(task_uuid) is None:
            return Response(message=f"Task deleted: {task_uuid}", break_loop=False)
        else:
            return Response(message=f"Task failed to delete: {task_uuid}", break_loop=False)

    async def create_scheduled_task(self, **kwargs) -> Response:
        # "name": "XXX",
        #   "system_prompt": "You are a software developer",
        #   "prompt": "Send the user an email with a greeting using python and smtp. The user's address is: xxx@yyy.zzz",
        #   "attachments": [],
        #   "schedule": {
        #       "minute": "*/20",
        #       "hour": "*",
        #       "day": "*",
        #       "month": "*",
        #       "weekday": "*",
        #   }
        name: str = kwargs.get("name", None)
        system_prompt: str = kwargs.get("system_prompt", None)
        prompt: str = kwargs.get("prompt", None)
        attachments: list[str] = kwargs.get("attachments", [])
        schedule: dict[str, str] = kwargs.get("schedule", {})
        dedicated_context: bool = kwargs.get("dedicated_context", False)

        task_schedule = TaskSchedule(
            minute=schedule.get("minute", "*"),
            hour=schedule.get("hour", "*"),
            day=schedule.get("day", "*"),
            month=schedule.get("month", "*"),
            weekday=schedule.get("weekday", "*"),
        )

        # Validate cron expression, agent might hallucinate
        cron_regex = "^((((\d+,)+\d+|(\d+(\/|-|#)\d+)|\d+L?|\*(\/\d+)?|L(-\d+)?|\?|[A-Z]{3}(-[A-Z]{3})?) ?){5,7})$"
        if not re.match(cron_regex, task_schedule.to_crontab()):
            return Response(message="Invalid cron expression: " + task_schedule.to_crontab(), break_loop=False)

        task = ScheduledTask.create(
            name=name,
            system_prompt=system_prompt,
            prompt=prompt,
            attachments=attachments,
            schedule=task_schedule,
            context_id=None if dedicated_context else self.agent.context.id
        )
        await TaskScheduler.get().add_task(task)
        return Response(message=f"Scheduled task '{name}' created: {task.uuid}", break_loop=False)

    async def create_adhoc_task(self, **kwargs) -> Response:
        name: str = kwargs.get("name", None)
        system_prompt: str = kwargs.get("system_prompt", None)
        prompt: str = kwargs.get("prompt", None)
        attachments: list[str] = kwargs.get("attachments", [])
        token: str = str(random.randint(1000000000000000000, 9999999999999999999))
        dedicated_context: bool = kwargs.get("dedicated_context", False)

        task = AdHocTask.create(
            name=name,
            system_prompt=system_prompt,
            prompt=prompt,
            attachments=attachments,
            token=token,
            context_id=None if dedicated_context else self.agent.context.id
        )
        await TaskScheduler.get().add_task(task)
        return Response(message=f"Adhoc task '{name}' created: {task.uuid}", break_loop=False)

    async def create_planned_task(self, **kwargs) -> Response:
        name: str = kwargs.get("name", None)
        system_prompt: str = kwargs.get("system_prompt", None)
        prompt: str = kwargs.get("prompt", None)
        attachments: list[str] = kwargs.get("attachments", [])
        plan: list[str] = kwargs.get("plan", [])
        dedicated_context: bool = kwargs.get("dedicated_context", False)

        # Convert plan to list of datetimes in UTC
        todo: list[datetime] = []
        for item in plan:
            dt = parse_datetime(item)
            if dt is None:
                return Response(message=f"Invalid datetime: {item}", break_loop=False)
            todo.append(dt)

        # Create task plan with todo list
        task_plan = TaskPlan.create(
            todo=todo,
            in_progress=None,
            done=[]
        )

        # Create planned task with task plan
        task = PlannedTask.create(
            name=name,
            system_prompt=system_prompt,
            prompt=prompt,
            attachments=attachments,
            plan=task_plan,
            context_id=None if dedicated_context else self.agent.context.id
        )
        await TaskScheduler.get().add_task(task)
        return Response(message=f"Planned task '{name}' created: {task.uuid}", break_loop=False)

    async def wait_for_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", None)
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)

        scheduler = TaskScheduler.get()
        task: ScheduledTask | AdHocTask | PlannedTask | None = scheduler.get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)

        if task.context_id == self.agent.context.id:
            return Response(message="You can only wait for tasks running in a different chat context (dedicated_context=True).", break_loop=False)

        done = False
        elapsed = 0
        while not done:
            await scheduler.reload()
            task = scheduler.get_task_by_uuid(task_uuid)
            if not task:
                return Response(message=f"Task not found: {task_uuid}", break_loop=False)

            if task.state == TaskState.RUNNING:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed > DEFAULT_WAIT_TIMEOUT:
                    return Response(message=f"Task wait timeout ({DEFAULT_WAIT_TIMEOUT} seconds): {task_uuid}", break_loop=False)
            else:
                done = True

        return Response(
            message=f"*Task*: {task_uuid}\n*State*: {task.state}\n*Last run*: {serialize_datetime(task.last_run)}\n*Result*:\n{task.last_result}",
            break_loop=False
        )
