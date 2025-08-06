import json
from python.helpers.tool import Tool, Response
from python.helpers.tasklist import TaskList, Task, TaskLog, TaskStatus
from python.helpers import files, runtime


class TaskListErrorResponse(Exception):
    def __init__(self, message: str):
        self.message = message


class TaskListTool(Tool):

    async def execute(self, **kwargs):
        """Execute tasklist operations based on method"""
        method = self.method or "display"

        # Route to specific method handlers
        if method == "add_task":
            return await self.add_task(**kwargs)
        elif method == "add_task_before":
            return await self.add_task_before(**kwargs)
        elif method == "add_task_after":
            return await self.add_task_after(**kwargs)
        elif method == "delete_task":
            return await self.delete_task(**kwargs)
        elif method == "update_task":
            return await self.update_task(**kwargs)
        elif method == "swap_tasks":
            return await self.swap_tasks(**kwargs)
        elif method == "set_task_pending":
            return await self.set_task_pending(**kwargs)
        elif method == "set_task_in_progress":
            return await self.set_task_in_progress(**kwargs)
        elif method == "set_task_done":
            return await self.set_task_done(**kwargs)
        elif method == "set_task_failed":
            return await self.set_task_failed(**kwargs)
        elif method == "set_task_skipped":
            return await self.set_task_skipped(**kwargs)
        elif method == "log_task_progress":
            return await self.log_task_progress(**kwargs)
        elif method == "get_task_logs":
            return await self.get_task_logs(**kwargs)
        elif method == "get_task_in_progress":
            return await self.get_task_in_progress(**kwargs)
        elif method == "get_task":
            return await self.get_task(**kwargs)
        elif method == "get_tasks":
            return await self.get_tasks(**kwargs)
        elif method == "clear":
            return await self.clear(**kwargs)
        elif method == "display":
            return await self.display(**kwargs)
        else:
            return Response(message=f"Unknown method '{self.name}:{method}'", break_loop=False)

    async def _get_tasklist(self) -> TaskList:
        """Get the TaskList instance for the current agent context, loading from storage if needed"""
        context_id = self.agent.context.id

        # Try to get from memory first
        tasklist = TaskList.get_instance(context_id)

        # Try to load from storage
        file_path = f"tmp/tasklists/{context_id}.json"
        if await runtime.call_development_function(files.exists, file_path):
            try:
                content = await runtime.call_development_function(files.read_file, file_path)
                loaded_tasklist = TaskList.model_validate_json(content)
                TaskList.set_instance(context_id, loaded_tasklist)
                return loaded_tasklist
            except Exception:
                # If loading fails, use the in-memory instance
                pass

        return tasklist

    async def _save_tasklist(self, tasklist: TaskList):
        """Save the TaskList to storage using RFC calls"""
        file_path = f"tmp/tasklists/{tasklist.uid}.json"
        content = tasklist.model_dump_json(indent=2)

        # Use relative path - write_file handles directory creation
        await runtime.call_development_function(files.write_file, file_path, content)

    def _validate_required_param(self, param_name: str, kwargs: dict) -> str:
        """Validate that a required parameter exists and return it"""
        value = kwargs.get(param_name)
        if not value:
            raise TaskListErrorResponse(f"Parameter '{param_name}' is required")
        return str(value)

    def _format_task_response(self, template_name: str, all_tasks: list[dict], **kwargs) -> str:
        """Format a simple response without reading the prompt file"""
        if template_name == "display":
            if all_tasks:
                return json.dumps(all_tasks, indent=2)
            else:
                return "Tasklist is empty."
        elif template_name == "add_task":
            return f"Task added: {kwargs.get('task_name', 'Unknown')}"
        elif template_name == "delete_task":
            return f"Task deleted: {kwargs.get('task_uid', 'Unknown')}"
        elif template_name == "clear":
            return "Tasklist cleared successfully."
        else:
            # For all other operations, return the tasklist
            if all_tasks:
                return json.dumps(all_tasks, indent=2)
            else:
                return "Operation completed. Tasklist is empty."

    async def add_task(self, **kwargs) -> Response:
        """Add a new task to the end of the tasklist"""
        try:
            name = self._validate_required_param("name", kwargs)
            description = kwargs.get("description", "")

            tasklist = await self._get_tasklist()
            task = Task(name=name, description=description)
            tasklist.add_task(task)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "add_task",
                tasklist.get_tasks_for_rendering(),
                task_name=name
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def add_task_before(self, **kwargs) -> Response:
        """Insert a new task before an existing task"""
        try:
            name = self._validate_required_param("name", kwargs)
            uid = self._validate_required_param("uid", kwargs)
            description = kwargs.get("description", "")

            tasklist = await self._get_tasklist()
            if tasklist.get_task(uid=uid) is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            task = Task(name=name, description=description)
            tasklist.add_task_before(task, uid)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "add_task_before",
                tasklist.get_tasks_for_rendering(),
                task_name=name,
                before_uid=uid
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def add_task_after(self, **kwargs) -> Response:
        """Insert a new task after an existing task"""
        try:
            name = self._validate_required_param("name", kwargs)
            uid = self._validate_required_param("uid", kwargs)
            description = kwargs.get("description", "")

            tasklist = await self._get_tasklist()
            if tasklist.get_task(uid=uid) is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            task = Task(name=name, description=description)
            tasklist.add_task_after(task, uid)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "add_task_after",
                tasklist.get_tasks_for_rendering(),
                task_name=name,
                after_uid=uid
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def delete_task(self, **kwargs) -> Response:
        """Delete a task from the tasklist"""
        try:
            uid = self._validate_required_param("uid", kwargs)

            tasklist = await self._get_tasklist()
            task = tasklist.get_task(uid=uid)
            if task is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            task_name = task.name
            tasklist.remove_task(uid)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "delete_task",
                tasklist.get_tasks_for_rendering(),
                task_name=task_name,
                uid=uid
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def update_task(self, **kwargs) -> Response:
        """Update a task's properties"""
        try:
            uid = self._validate_required_param("uid", kwargs)

            tasklist = await self._get_tasklist()
            task = tasklist.get_task(uid=uid)
            if task is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            name = kwargs.get("name", task.name)
            description = kwargs.get("description", task.description)
            status_str = kwargs.get("status", task.status.value)
            status = TaskStatus(status_str)

            tasklist.update_task(uid=uid, name=name, description=description, status=status)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "update_task",
                tasklist.get_tasks_for_rendering(),
                uid=uid
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def swap_tasks(self, **kwargs) -> Response:
        """Swap the positions of two tasks"""
        try:
            uid1 = self._validate_required_param("uid1", kwargs)
            uid2 = self._validate_required_param("uid2", kwargs)

            tasklist = await self._get_tasklist()
            if tasklist.get_task(uid=uid1) is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid1
                )
                return Response(message=response, break_loop=False)

            if tasklist.get_task(uid=uid2) is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid2
                )
                return Response(message=response, break_loop=False)

            tasklist.swap_tasks(uid1, uid2)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "swap_tasks",
                tasklist.get_tasks_for_rendering(),
                uid1=uid1,
                uid2=uid2
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def set_task_pending(self, **kwargs) -> Response:
        """Set a task status to pending"""
        return await self._set_task_status(TaskStatus.PENDING, **kwargs)

    async def set_task_in_progress(self, **kwargs) -> Response:
        """Set a task status to in progress"""
        return await self._set_task_status(TaskStatus.IN_PROGRESS, **kwargs)

    async def set_task_done(self, **kwargs) -> Response:
        """Set a task status to done"""
        return await self._set_task_status(TaskStatus.DONE, **kwargs)

    async def set_task_failed(self, **kwargs) -> Response:
        """Set a task status to failed"""
        return await self._set_task_status(TaskStatus.FAILED, **kwargs)

    async def set_task_skipped(self, **kwargs) -> Response:
        """Set a task status to skipped"""
        return await self._set_task_status(TaskStatus.SKIPPED, **kwargs)

    async def _set_task_status(self, status: TaskStatus, **kwargs) -> Response:
        """Helper method to set task status"""
        try:
            uid = self._validate_required_param("uid", kwargs)

            tasklist = await self._get_tasklist()
            if tasklist.get_task(uid=uid) is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            tasklist.set_task_status(uid, status)
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "set_task_status",
                tasklist.get_tasks_for_rendering(),
                uid=uid,
                status=status.value
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def log_task_progress(self, **kwargs) -> Response:
        """Add a log entry to a task"""
        try:
            uid = self._validate_required_param("uid", kwargs)
            message = self._validate_required_param("message", kwargs)

            tasklist = await self._get_tasklist()
            task = tasklist.get_task(uid=uid)
            if task is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            log = TaskLog(message=message)
            task.add_log(log)
            tasklist.update_timestamp()
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "log_task_progress",
                tasklist.get_tasks_for_rendering(),
                uid=uid,
                log_message=message
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def get_task_logs(self, **kwargs) -> Response:
        """Get all logs for a specific task"""
        try:
            uid = self._validate_required_param("uid", kwargs)

            tasklist = await self._get_tasklist()
            task = tasklist.get_task(uid=uid)
            if task is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            response = self._format_task_response(
                "get_task_logs",
                tasklist.get_tasks_for_rendering(),
                uid=uid,
                all_logs=json.dumps(task.get_logs_for_rendering(), indent=4)
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def get_task_in_progress(self, **kwargs) -> Response:
        """Get the task currently in progress"""
        try:
            tasklist = await self._get_tasklist()
            task = tasklist.get_task_in_progress()

            if task is None:
                response = self._format_task_response(
                    "no_task_in_progress",
                    tasklist.get_tasks_for_rendering()
                )
                return Response(message=response, break_loop=False)

            response = self._format_task_response(
                "get_task_in_progress",
                tasklist.get_tasks_for_rendering(),
                task=json.dumps(task.model_dump(mode="json"), indent=4)
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def get_task(self, **kwargs) -> Response:
        """Get a specific task by UID"""
        try:
            uid = self._validate_required_param("uid", kwargs)

            tasklist = await self._get_tasklist()
            task = tasklist.get_task(uid=uid)
            if task is None:
                response = self._format_task_response(
                    "task_not_found",
                    tasklist.get_tasks_for_rendering(),
                    uid=uid
                )
                return Response(message=response, break_loop=False)

            response = self._format_task_response(
                "get_task",
                tasklist.get_tasks_for_rendering(),
                task=json.dumps(task.model_dump(mode="json"), indent=4)
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def get_tasks(self, **kwargs) -> Response:
        """Get tasks filtered by status"""
        try:
            status_filter = kwargs.get("status")
            status_list = None

            if status_filter:
                if isinstance(status_filter, str):
                    status_list = [TaskStatus(status_filter)]
                elif isinstance(status_filter, list):
                    status_list = [TaskStatus(s) for s in status_filter]

            tasklist = await self._get_tasklist()
            filtered_tasks = tasklist.get_tasks_for_rendering(status_list)

            response = self._format_task_response(
                "get_tasks",
                tasklist.get_tasks_for_rendering(),
                tasks=json.dumps(filtered_tasks, indent=4),
                status_filter=status_filter or "all"
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def clear(self, **kwargs) -> Response:
        """Clear all tasks from the tasklist"""
        try:
            tasklist = await self._get_tasklist()
            tasklist.clear_all_tasks()
            await self._save_tasklist(tasklist)

            response = self._format_task_response(
                "clear",
                tasklist.get_tasks_for_rendering()
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)

    async def display(self, **kwargs) -> Response:
        """Display the entire tasklist"""
        try:
            tasklist = await self._get_tasklist()

            response = self._format_task_response(
                "display",
                tasklist.get_tasks_for_rendering()
            )
            return Response(message=response, break_loop=False)

        except TaskListErrorResponse as e:
            return Response(message=e.message, break_loop=False)
