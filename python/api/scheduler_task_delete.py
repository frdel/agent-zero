from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import TaskScheduler, TaskState
from python.helpers.localization import Localization
from agent import AgentContext
from python.helpers import persist_chat


class SchedulerTaskDelete(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        """
        Delete a task from the scheduler by ID
        """
        # Get timezone from input (do not set if not provided, we then rely on poll() to set it)
        if timezone := input.get("timezone", None):
            Localization.get().set_timezone(timezone)

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

        context = None
        if task.context_id:
            context = self.get_context(task.context_id)

        # If the task is running, update its state to IDLE first
        if task.state == TaskState.RUNNING:
            if context:
                context.reset()
            # Update the state to IDLE so any ongoing processes know to terminate
            await scheduler.update_task(task_id, state=TaskState.IDLE)
            # Force a save to ensure the state change is persisted
            await scheduler.save()

        # This is a dedicated context for the task, so we remove it
        if context and context.id == task.uuid:
            AgentContext.remove(context.id)
            persist_chat.remove_chat(context.id)

        # Remove the task
        await scheduler.remove_task_by_uuid(task_id)

        return {"success": True, "message": f"Task {task_id} deleted successfully"}
