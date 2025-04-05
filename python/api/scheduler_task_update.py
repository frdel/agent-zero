from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import (
    TaskScheduler, ScheduledTask, AdHocTask, TaskState,
    serialize_task, parse_task_schedule
)


class SchedulerTaskUpdate(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        """
        Update an existing task in the scheduler
        """
        scheduler = TaskScheduler.get()
        await scheduler.reload()

        # Get task ID from input
        task_id: str = input.get("task_id", "")

        if not task_id:
            return {"error": "Missing required field: task_id"}

        # Get the task to update
        task = scheduler.get_task_by_uuid(task_id)

        if not task:
            return {"error": f"Task with ID {task_id} not found"}

        # Update fields if provided using the task's update method
        update_params = {}

        if "name" in input:
            update_params["name"] = input.get("name", "")

        if "state" in input:
            update_params["state"] = TaskState(input.get("state", TaskState.IDLE))

        if "system_prompt" in input:
            update_params["system_prompt"] = input.get("system_prompt", "")

        if "prompt" in input:
            update_params["prompt"] = input.get("prompt", "")

        if "attachments" in input:
            update_params["attachments"] = input.get("attachments", [])

        # Update schedule if this is a scheduled task and schedule is provided
        if isinstance(task, ScheduledTask) and "schedule" in input:
            schedule_data = input.get("schedule", {})
            try:
                update_params["schedule"] = parse_task_schedule(schedule_data)
            except ValueError as e:
                return {"error": f"Invalid schedule format: {str(e)}"}
        elif isinstance(task, AdHocTask) and "token" in input:
            update_params["token"] = input.get("token", "")

        # Use atomic update method to apply changes
        updated_task = await scheduler.update_task(task_id, **update_params)

        if not updated_task:
            return {"error": f"Task with ID {task_id} not found or could not be updated"}

        # Return the updated task using our standardized serialization function
        task_dict = serialize_task(updated_task)

        return {
            "task": task_dict
        }
