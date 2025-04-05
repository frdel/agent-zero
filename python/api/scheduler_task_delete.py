from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import TaskScheduler


class SchedulerTaskDelete(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        """
        Delete a task from the scheduler by ID
        """
        scheduler = TaskScheduler.get()
        await scheduler.reload()

        # Get task ID from input
        task_id: str = input.get("task_id", "")

        if not task_id:
            return {"error": "Missing required field: task_id"}

        # Check if the task exists first
        task = scheduler.get_task_by_uuid(task_id)
        if not task:
            return {"error": f"Task with ID {task_id} not found"}

        # Remove the task
        await scheduler.remove_task_by_uuid(task_id)

        return {"success": True, "message": f"Task {task_id} deleted successfully"}
