from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import TaskScheduler, TaskState
from python.helpers.print_style import PrintStyle
from python.helpers.localization import Localization


class SchedulerTaskRun(ApiHandler):

    _printer: PrintStyle = PrintStyle(italic=True, font_color="green", padding=False)

    async def process(self, input: Input, request: Request) -> Output:
        """
        Manually run a task from the scheduler by ID
        """
        # Get timezone from input (do not set if not provided, we then rely on poll() to set it)
        if timezone := input.get("timezone", None):
            Localization.get().set_timezone(timezone)

        # Get task ID from input
        task_id: str = input.get("task_id", "")

        if not task_id:
            return {"error": "Missing required field: task_id"}

        self._printer.print(f"SchedulerTaskRun: On-Demand running task {task_id}")

        scheduler = TaskScheduler.get()
        await scheduler.reload()

        # Check if the task exists first
        task = scheduler.get_task_by_uuid(task_id)
        if not task:
            self._printer.error(f"SchedulerTaskRun: Task with ID '{task_id}' not found")
            return {"error": f"Task with ID '{task_id}' not found"}

        # Check if task is already running
        if task.state == TaskState.RUNNING:
            # Return task details along with error for better frontend handling
            serialized_task = scheduler.serialize_task(task_id)
            self._printer.error(f"SchedulerTaskRun: Task '{task_id}' is in state '{task.state}' and cannot be run")
            return {
                "error": f"Task '{task_id}' is in state '{task.state}' and cannot be run",
                "task": serialized_task
            }

        # Run the task, which now includes atomic state checks and updates
        try:
            await scheduler.run_task_by_uuid(task_id)
            self._printer.print(f"SchedulerTaskRun: Task '{task_id}' started successfully")
            # Get updated task after run starts
            serialized_task = scheduler.serialize_task(task_id)
            if serialized_task:
                return {
                    "success": True,
                    "message": f"Task '{task_id}' started successfully",
                    "task": serialized_task
                }
            else:
                return {"success": True, "message": f"Task '{task_id}' started successfully"}
        except ValueError as e:
            self._printer.error(f"SchedulerTaskRun: Task '{task_id}' failed to start: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            self._printer.error(f"SchedulerTaskRun: Task '{task_id}' failed to start: {str(e)}")
            return {"error": f"Failed to run task '{task_id}': {str(e)}"}
