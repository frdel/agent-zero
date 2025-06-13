import json

from python.helpers.tool import Tool, Response
from python.helpers.tasklist import (
    Task,
    TaskStatus,
    TaskLog,
    TaskList
)


class TaskListErrorResponse(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class TaskListTool(Tool):

    async def execute(self, **kwargs):
        valid_methods = [
            "add_task",  # name. description
            "add_task_before",  # uid. name. description
            "add_task_after",  # uid. name. description
            "delete_task",  # uid
            "update_task",  # uid. name. description. status
            "swap_tasks",  # uid1. uid2
            "set_task_pending",  # uid
            "set_task_in_progress",  # uid
            "set_task_done",  # uid. message
            "set_task_failed",  # uid
            "set_task_skipped",  # uid
            "get_task_logs",  # uid
            "log_task_progress",  # uid. message
            "get_task_in_progress",
            "get_task",  # uid
            "get_tasks",  # status
            "clear",
            "display",
        ]

        if self.method not in valid_methods:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tool_call.invalid_method.md",
                    tool_name=self.name,
                    tool_method=self.method,
                    valid_methods=json.dumps(valid_methods, indent=4),
                ),
                break_loop=False,
            )

        return await getattr(self, self.method)()

    async def add_task(self):
        try:
            name = self._task_param("name", self.args)
            description = self._task_param("description", self.args, default=name)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        task = Task(name=name, description=description)
        tasklist = TaskList.get_instance(self.agent.context.id)
        tasklist.add_task(task)
        message = self.agent.parse_prompt(
            "fw.tasklist.add_task.md",
            uid=task.uid,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def add_task_before(self):
        try:
            uid = self._task_param("uid", self.args)
            name = self._task_param("name", self.args)
            description = self._task_param("description", self.args, default=name)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        task = Task(name=name, description=description)
        tasklist.add_task_before(task, uid)
        message = self.agent.parse_prompt(
            "fw.tasklist.add_task_before.md",
            uid=task.uid,
            before_uid=uid,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def add_task_after(self):
        try:
            uid = self._task_param("uid", self.args)
            name = self._task_param("name", self.args)
            description = self._task_param("description", self.args, default=name)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        task = Task(name=name, description=description)
        tasklist.add_task_after(task, uid)
        message = self.agent.parse_prompt(
            "fw.tasklist.add_task_after.md",
            uid=task.uid,
            after_uid=uid,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def delete_task(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        task = tasklist.get_task(uid=uid)
        if task is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )
        tasklist.remove_task(uid)
        message = self.agent.parse_prompt(
            "fw.tasklist.delete_task.md",
            uid=uid,
            task_name=task.name,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def update_task(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        task = tasklist.get_task(uid=uid)
        if task is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        try:
            name = self._task_param("name", self.args, default=task.name)
            description = self._task_param("description", self.args, default=task.description)
            status = self._task_param("status", self.args, default=task.status.value)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist.update_task(uid=uid, name=name, description=description, status=TaskStatus(status))
        message = self.agent.parse_prompt(
            "fw.tasklist.update_task.md",
            uid=uid,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def swap_tasks(self):
        try:
            uid1 = self._task_param("uid1", self.args)
            uid2 = self._task_param("uid2", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid1) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid1,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )
        if tasklist.get_task(uid=uid2) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid2,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        tasklist.swap_tasks(uid1, uid2)
        message = self.agent.parse_prompt(
            "fw.tasklist.swap_tasks.md",
            uid1=uid1,
            uid2=uid2,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def set_task_pending(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        tasklist.set_task_status(uid, TaskStatus.PENDING)
        message = self.agent.parse_prompt(
            "fw.tasklist.set_task_status.md",
            uid=uid,
            status=TaskStatus.PENDING.value,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def set_task_in_progress(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        tasklist.set_task_status(uid, TaskStatus.IN_PROGRESS)
        message = self.agent.parse_prompt(
            "fw.tasklist.set_task_status.md",
            uid=uid,
            status=TaskStatus.IN_PROGRESS.value,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def set_task_done(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        tasklist.set_task_status(uid, TaskStatus.DONE)
        message = self.agent.parse_prompt(
            "fw.tasklist.set_task_status.md",
            uid=uid,
            status=TaskStatus.DONE.value,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def set_task_failed(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        tasklist.set_task_status(uid, TaskStatus.FAILED)
        message = self.agent.parse_prompt(
            "fw.tasklist.set_task_status.md",
            uid=uid,
            status=TaskStatus.FAILED.value,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def set_task_skipped(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        tasklist.set_task_status(uid, TaskStatus.SKIPPED)
        message = self.agent.parse_prompt(
            "fw.tasklist.set_task_status.md",
            uid=uid,
            status=TaskStatus.SKIPPED.value,
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def get_task_logs(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        if tasklist.get_task(uid=uid) is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )

        message = self.agent.parse_prompt(
            "fw.tasklist.get_task_logs.md",
            uid=uid,
            all_logs=json.dumps(tasklist.get_task_logs_for_rendering(uid), indent=4),
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def log_task_progress(self):
        try:
            uid = self._task_param("uid", self.args)
            log_message = self._task_param("message", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        task = tasklist.get_task(uid=uid)
        if task is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )
        task.add_log(TaskLog(message=log_message))
        message = self.agent.parse_prompt(
            "fw.tasklist.log_task_progress.md",
            uid=uid,
            log_message=log_message,
            all_logs=json.dumps(task.get_logs_for_rendering(), indent=4),
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def get_task_in_progress(self):
        tasklist = TaskList.get_instance(self.agent.context.id)
        task = tasklist.get_task_in_progress()
        if task is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.no_task_in_progress.md",
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )
        message = self.agent.parse_prompt(
            "fw.tasklist.get_task_in_progress.md",
            uid=task.uid,
            task=task.model_dump_json(indent=4),
        )
        return Response(message=message, break_loop=False)

    async def get_task(self):
        try:
            uid = self._task_param("uid", self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        task = tasklist.get_task(uid=uid)
        if task is None:
            return Response(
                message=self.agent.read_prompt(
                    "fw.tasklist.task_not_found.md",
                    uid=uid,
                    all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
                ),
                break_loop=False,
            )
        message = self.agent.parse_prompt(
            "fw.tasklist.get_task.md",
            uid=task.uid,
            task=task.model_dump_json(indent=4),
        )
        return Response(message=message, break_loop=False)

    async def get_tasks(self):
        try:
            status_filter = self._task_status_filter(self.args)
        except TaskListErrorResponse as e:
            return Response(message=str(e), break_loop=False)

        tasklist = TaskList.get_instance(self.agent.context.id)
        tasks_json = json.dumps(tasklist.get_tasks_for_rendering(status_filter), indent=4)
        message = self.agent.parse_prompt(
            "fw.tasklist.get_tasks.md",
            status_filter=json.dumps([s.value for s in status_filter], indent=4),
            tasks=tasks_json,
        )
        return Response(message=message, break_loop=False)

    async def clear(self):
        tasklist = TaskList.get_instance(self.agent.context.id)
        tasklist.clear()
        message = self.agent.parse_prompt(
            "fw.tasklist.clear.md",
            all_tasks=json.dumps(tasklist.get_tasks_for_rendering(), indent=4),
        )
        return Response(message=message, break_loop=False)

    async def display(self):
        tasklist = TaskList.get_instance(self.agent.context.id)
        tasks_json = json.dumps(tasklist.get_tasks_for_rendering(), indent=4)
        message = self.agent.parse_prompt(
            "fw.tasklist.display.md",
            all_tasks=tasks_json,
        )
        return Response(message=message, break_loop=False)

    def _task_param(self, param: str, args: dict[str, str], default: str | None = None) -> str:
        if param not in args or not args[param]:
            if default is not None:
                return default
            message = self.agent.read_prompt(
                "fw.tool_call.missing_tool_arg.md",
                tool_name=self.name,
                missing_arg=param,
                tool_args=json.dumps(args, indent=4),
            )
            raise TaskListErrorResponse(message)
        return args[param]

    def _task_status_filter(self, args: dict[str, str]) -> list[TaskStatus]:
        status = self._task_param("status", args, default=None)
        if status is None:
            return [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED]

        status_filter: list[TaskStatus] = []
        if isinstance(status, str):
            status_filter = [TaskStatus(status)]
        elif isinstance(status, list):
            status_filter = [TaskStatus(s) for s in list(status)]
        else:
            message = self.agent.read_prompt(
                "fw.tool_call.invalid_tool_arg.md",
                tool_name=self.name,
                invalid_arg="status",
                invalid_arg_value=args["status"],
                valid_args=json.dumps(TaskStatus.__members__.keys(), indent=4),
                tool_args=json.dumps(args, indent=4),
            )
            raise TaskListErrorResponse(message)
        return status_filter
