from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import TaskScheduler, TaskState


class SchedulerTaskRun(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        """
        Manually run a task from the scheduler by ID
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
            return {"error": f"Task with ID '{task_id}' not found"}

        # Check if task is already running
        if task.state != TaskState.IDLE:
            # Return task details along with error for better frontend handling
            serialized_task = scheduler.serialize_task(task_id)
            return {
                "error": f"Task '{task_id}' is in state '{task.state}' and cannot be run",
                "task": serialized_task
            }

        # Run the task, which now includes atomic state checks and updates
        try:
            await scheduler.run_task_by_uuid(task_id)
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
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Failed to run task '{task_id}': {str(e)}"}
