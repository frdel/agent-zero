import asyncio
from datetime import datetime
import json
import random
import re
from typing import Any
import pytz
from helpers.tool import Tool, Response
from helpers.task_scheduler import (
    TaskScheduler, ScheduledTask, AdHocTask, PlannedTask,
    serialize_task, TaskState, TaskSchedule, TaskPlan, parse_datetime,
    parse_task_plan, serialize_datetime
)
from agent import AgentContext
from helpers import persist_chat
from helpers.localization import Localization
from helpers.projects import get_context_project_name, load_basic_project_data

DEFAULT_WAIT_TIMEOUT = 300
LOCAL_TIMEZONE_ALIASES = {"local", "user", "default", "current", "current_timezone"}


def _current_action(tool: Tool, kwargs: dict) -> str:
    return (
        str(
            kwargs.get("action")
            or tool.args.get("action")
            or ""
        )
        .strip()
        .lower()
        .replace("-", "_")
    )


def _normalize_timezone(value: Any) -> str | None:
    if value is None:
        return None
    timezone_name = str(value).strip()
    if not timezone_name:
        return None
    if timezone_name.lower() in LOCAL_TIMEZONE_ALIASES:
        return Localization.get().get_timezone()
    try:
        pytz.timezone(timezone_name)
    except pytz.exceptions.UnknownTimeZoneError as exc:
        raise ValueError(
            f"Invalid timezone: {timezone_name}. Use an IANA timezone name such as Europe/Rome, "
            "or omit timezone to use the current user timezone."
        ) from exc
    return timezone_name


def _schedule_timezone(kwargs: dict) -> str | None:
    schedule = kwargs.get("schedule")
    if isinstance(schedule, dict) and schedule.get("timezone"):
        return _normalize_timezone(schedule["timezone"])
    if kwargs.get("timezone"):
        return _normalize_timezone(kwargs["timezone"])
    return None


def _task_schedule_from_input(schedule: Any, timezone: str | None = None) -> TaskSchedule:
    if isinstance(schedule, str):
        parts = schedule.split()
        schedule_data: dict[str, Any] = {
            "minute": parts[0] if len(parts) > 0 else "*",
            "hour": parts[1] if len(parts) > 1 else "*",
            "day": parts[2] if len(parts) > 2 else "*",
            "month": parts[3] if len(parts) > 3 else "*",
            "weekday": parts[4] if len(parts) > 4 else "*",
        }
    elif isinstance(schedule, dict):
        schedule_data = dict(schedule)
    else:
        schedule_data = {}

    task_schedule_kwargs = {
        "minute": str(schedule_data.get("minute", "*")),
        "hour": str(schedule_data.get("hour", "*")),
        "day": str(schedule_data.get("day", "*")),
        "month": str(schedule_data.get("month", "*")),
        "weekday": str(schedule_data.get("weekday", "*")),
    }
    normalized_timezone = _normalize_timezone(timezone if timezone is not None else schedule_data.get("timezone"))
    if normalized_timezone:
        task_schedule_kwargs["timezone"] = normalized_timezone

    return TaskSchedule(**task_schedule_kwargs)


def _validate_task_schedule(task_schedule: TaskSchedule) -> str:
    # Validate cron expression, agent might hallucinate
    cron_regex = r"^((((\d+,)+\d+|(\d+(\/|-|#)\d+)|\d+L?|\*(\/\d+)?|L(-\d+)?|\?|[A-Z]{3}(-[A-Z]{3})?) ?){5,7})$"
    crontab = task_schedule.to_crontab()
    return "" if re.match(cron_regex, crontab) else f"Invalid cron expression: {crontab}"


def _task_plan_from_input(plan: Any) -> tuple[TaskPlan | None, str]:
    if isinstance(plan, dict):
        try:
            return parse_task_plan(plan), ""
        except Exception as exc:
            return None, f"Invalid plan: {exc}"

    if not isinstance(plan, list):
        return None, "Plan must be an array of ISO datetimes."

    todo: list[datetime] = []
    for item in plan:
        dt = parse_datetime(str(item))
        if dt is None:
            return None, f"Invalid datetime: {item}"
        todo.append(dt)

    return TaskPlan.create(todo=todo, in_progress=None, done=[]), ""


class SchedulerTool(Tool):

    async def execute(self, **kwargs):
        action = _current_action(self, kwargs)
        if action == "list_tasks":
            return await self.list_tasks(**kwargs)
        elif action == "find_task_by_name":
            return await self.find_task_by_name(**kwargs)
        elif action == "show_task":
            return await self.show_task(**kwargs)
        elif action == "run_task":
            return await self.run_task(**kwargs)
        elif action == "delete_task":
            return await self.delete_task(**kwargs)
        elif action == "update_task":
            return await self.update_task(**kwargs)
        elif action == "create_scheduled_task":
            return await self.create_scheduled_task(**kwargs)
        elif action == "create_adhoc_task":
            return await self.create_adhoc_task(**kwargs)
        elif action == "create_planned_task":
            return await self.create_planned_task(**kwargs)
        elif action == "wait_for_task":
            return await self.wait_for_task(**kwargs)
        else:
            return Response(
                message=(
                    f"Unknown scheduler action '{action or self.method or ''}'. "
                    "Supported actions: list_tasks, find_task_by_name, show_task, "
                    "run_task, delete_task, update_task, create_scheduled_task, "
                    "create_adhoc_task, create_planned_task, wait_for_task."
                ),
                break_loop=False,
            )

    def _resolve_project_metadata(self) -> tuple[str | None, str | None]:
        context = self.agent.context
        if not context:
            return (None, None)
        project_slug = get_context_project_name(context)
        if not project_slug:
            return (None, None)
        try:
            metadata = load_basic_project_data(project_slug)
            color = metadata.get("color") or None
        except Exception:
            color = None
        return project_slug, color

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
        name: str = kwargs.get("name", "")
        if not name:
            return Response(message="Task name is required", break_loop=False)
        tasks: list[ScheduledTask | AdHocTask | PlannedTask] = TaskScheduler.get().find_task_by_name(name)
        if not tasks:
            return Response(message=f"Task not found: {name}", break_loop=False)
        return Response(message=json.dumps([serialize_task(task) for task in tasks], indent=4), break_loop=False)

    async def show_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", "")
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)
        task: ScheduledTask | AdHocTask | PlannedTask | None = TaskScheduler.get().get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)
        return Response(message=json.dumps(serialize_task(task), indent=4), break_loop=False)

    async def run_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", "")
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
        task_uuid: str = kwargs.get("uuid", "")
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

    async def update_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", "")
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)

        scheduler = TaskScheduler.get()
        await scheduler.reload()
        task: ScheduledTask | AdHocTask | PlannedTask | None = scheduler.get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)

        update_params: dict[str, Any] = {}
        for field in ("name", "system_prompt", "prompt", "attachments"):
            if field in kwargs:
                update_params[field] = kwargs[field]

        if "state" in kwargs:
            update_params["state"] = TaskState(kwargs.get("state", TaskState.IDLE))

        if "dedicated_context" in kwargs:
            dedicated_context = bool(kwargs.get("dedicated_context"))
            update_params["context_id"] = task.uuid if dedicated_context else self.agent.context.id

        try:
            timezone = _schedule_timezone(kwargs)
            if isinstance(task, ScheduledTask) and ("schedule" in kwargs or timezone):
                task_schedule = _task_schedule_from_input(
                    kwargs.get("schedule") or serialize_task(task).get("schedule") or {},
                    timezone=timezone,
                )
                if err := _validate_task_schedule(task_schedule):
                    return Response(message=err, break_loop=False)
                update_params["schedule"] = task_schedule
        except ValueError as exc:
            return Response(message=str(exc), break_loop=False)

        if isinstance(task, ScheduledTask) and "schedule" in update_params:
            task_schedule = update_params["schedule"]
            if err := _validate_task_schedule(task_schedule):
                return Response(message=err, break_loop=False)
        elif isinstance(task, PlannedTask) and "plan" in kwargs:
            task_plan, err = _task_plan_from_input(kwargs.get("plan") or [])
            if err:
                return Response(message=err, break_loop=False)
            update_params["plan"] = task_plan

        updated_task = await scheduler.update_task(task_uuid, **update_params)
        await scheduler.save()
        if not updated_task:
            return Response(message=f"Task failed to update: {task_uuid}", break_loop=False)

        return Response(message=json.dumps(serialize_task(updated_task), indent=4), break_loop=False)

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
        name: str = kwargs.get("name", "")
        system_prompt: str = kwargs.get("system_prompt", "")
        prompt: str = kwargs.get("prompt", "")
        attachments: list[str] = kwargs.get("attachments", [])
        schedule: dict[str, str] = kwargs.get("schedule", {})
        dedicated_context: bool = kwargs.get("dedicated_context", True)

        try:
            task_schedule = _task_schedule_from_input(schedule, timezone=_schedule_timezone(kwargs))
        except ValueError as exc:
            return Response(message=str(exc), break_loop=False)

        if err := _validate_task_schedule(task_schedule):
            return Response(message=err, break_loop=False)

        project_slug, project_color = self._resolve_project_metadata()

        task = ScheduledTask.create(
            name=name,
            system_prompt=system_prompt,
            prompt=prompt,
            attachments=attachments,
            schedule=task_schedule,
            timezone=getattr(task_schedule, "timezone", None),
            context_id=None if dedicated_context else self.agent.context.id,
            project_name=project_slug,
            project_color=project_color,
        )
        await TaskScheduler.get().add_task(task)
        return Response(message=f"Scheduled task '{name}' created: {task.uuid}", break_loop=False)

    async def create_adhoc_task(self, **kwargs) -> Response:
        name: str = kwargs.get("name", "")
        system_prompt: str = kwargs.get("system_prompt", "")
        prompt: str = kwargs.get("prompt", "")
        attachments: list[str] = kwargs.get("attachments", [])
        token: str = str(random.randint(1000000000000000000, 9999999999999999999))
        dedicated_context: bool = kwargs.get("dedicated_context", True)

        project_slug, project_color = self._resolve_project_metadata()

        task = AdHocTask.create(
            name=name,
            system_prompt=system_prompt,
            prompt=prompt,
            attachments=attachments,
            token=token,
            context_id=None if dedicated_context else self.agent.context.id,
            project_name=project_slug,
            project_color=project_color,
        )
        await TaskScheduler.get().add_task(task)
        return Response(message=f"Adhoc task '{name}' created: {task.uuid}", break_loop=False)

    async def create_planned_task(self, **kwargs) -> Response:
        name: str = kwargs.get("name", "")
        system_prompt: str = kwargs.get("system_prompt", "")
        prompt: str = kwargs.get("prompt", "")
        attachments: list[str] = kwargs.get("attachments", [])
        plan: list[str] = kwargs.get("plan", [])
        dedicated_context: bool = kwargs.get("dedicated_context", True)

        # Convert plan to list of datetimes in UTC
        task_plan, err = _task_plan_from_input(plan)
        if err:
            return Response(message=err, break_loop=False)

        project_slug, project_color = self._resolve_project_metadata()

        # Create planned task with task plan
        task = PlannedTask.create(
            name=name,
            system_prompt=system_prompt,
            prompt=prompt,
            attachments=attachments,
            plan=task_plan,
            context_id=None if dedicated_context else self.agent.context.id,
            project_name=project_slug,
            project_color=project_color
        )
        await TaskScheduler.get().add_task(task)
        return Response(message=f"Planned task '{name}' created: {task.uuid}", break_loop=False)

    async def wait_for_task(self, **kwargs) -> Response:
        task_uuid: str = kwargs.get("uuid", "")
        if not task_uuid:
            return Response(message="Task UUID is required", break_loop=False)

        scheduler = TaskScheduler.get()
        task: ScheduledTask | AdHocTask | PlannedTask | None = scheduler.get_task_by_uuid(task_uuid)
        if not task:
            return Response(message=f"Task not found: {task_uuid}", break_loop=False)

        if task.context_id == self.agent.context.id:
            return Response(message="You can only wait for tasks running in their own dedicated context.", break_loop=False)

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
