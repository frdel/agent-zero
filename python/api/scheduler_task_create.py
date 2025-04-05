from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import (
    TaskScheduler, ScheduledTask, AdHocTask, TaskSchedule,
    serialize_task, parse_task_schedule
)


class SchedulerTaskCreate(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        """
        Create a new task in the scheduler
        """
        scheduler = TaskScheduler.get()
        await scheduler.reload()

        # Get common fields from input
        name = input.get("name")
        system_prompt = input.get("system_prompt")
        prompt = input.get("prompt")
        attachments = input.get("attachments", [])

        # Check if schedule is provided (for ScheduledTask)
        schedule = input.get("schedule", {})
        token: str = input.get("token", "")

        # Validate required fields
        if not name or not system_prompt or not prompt:
            return {"error": "Missing required fields: name, system_prompt, prompt"}

        task = None
        if schedule:
            # Create a scheduled task
            # Handle different schedule formats (string or object)
            if isinstance(schedule, str):
                # Parse the string schedule
                parts = schedule.split(' ')
                task_schedule = TaskSchedule(
                    minute=parts[0] if len(parts) > 0 else "*",
                    hour=parts[1] if len(parts) > 1 else "*",
                    day=parts[2] if len(parts) > 2 else "*",
                    month=parts[3] if len(parts) > 3 else "*",
                    weekday=parts[4] if len(parts) > 4 else "*"
                )
            elif isinstance(schedule, dict):
                # Use our standardized parsing function
                try:
                    task_schedule = parse_task_schedule(schedule)
                except ValueError as e:
                    return {"error": str(e)}
            else:
                return {"error": "Invalid schedule format. Must be string or object."}

            task = ScheduledTask.create(
                name=name,
                system_prompt=system_prompt,
                prompt=prompt,
                schedule=task_schedule,
                attachments=attachments
            )
        else:
            # Create an ad-hoc task
            task = AdHocTask.create(
                name=name,
                system_prompt=system_prompt,
                prompt=prompt,
                token=token,
                attachments=attachments
            )

        # Add the task to the scheduler
        await scheduler.add_task(task)

        # Return the created task using our standardized serialization function
        task_dict = serialize_task(task)

        return {
            "task": task_dict
        }
