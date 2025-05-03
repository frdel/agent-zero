from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.task_scheduler import (
    TaskScheduler, ScheduledTask, AdHocTask, PlannedTask, TaskSchedule,
    serialize_task, parse_task_schedule, parse_task_plan, TaskType
)
from python.helpers.localization import Localization
from python.helpers.print_style import PrintStyle
import random


class SchedulerTaskCreate(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        """
        Create a new task in the scheduler
        """
        printer = PrintStyle(italic=True, font_color="blue", padding=False)

        # Get timezone from input (do not set if not provided, we then rely on poll() to set it)
        if timezone := input.get("timezone", None):
            Localization.get().set_timezone(timezone)

        scheduler = TaskScheduler.get()
        await scheduler.reload()

        # Get common fields from input
        name = input.get("name")
        system_prompt = input.get("system_prompt", "")
        prompt = input.get("prompt")
        attachments = input.get("attachments", [])
        context_id = input.get("context_id", None)

        # Check if schedule is provided (for ScheduledTask)
        schedule = input.get("schedule", {})
        token: str = input.get("token", "")

        # Debug log the token value
        printer.print(f"Token received from frontend: '{token}' (type: {type(token)}, length: {len(token) if token else 0})")

        # Generate a random token if empty or not provided
        if not token:
            token = str(random.randint(1000000000000000000, 9999999999999999999))
            printer.print(f"Generated new token: '{token}'")

        plan = input.get("plan", {})

        # Validate required fields
        if not name or not prompt:
            # return {"error": "Missing required fields: name, system_prompt, prompt"}
            raise ValueError("Missing required fields: name, system_prompt, prompt")

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
                    raise ValueError(str(e))
            else:
                raise ValueError("Invalid schedule format. Must be string or object.")

            task = ScheduledTask.create(
                name=name,
                system_prompt=system_prompt,
                prompt=prompt,
                schedule=task_schedule,
                attachments=attachments,
                context_id=context_id,
                timezone=timezone
            )
        elif plan:
            # Create a planned task
            try:
                # Use our standardized parsing function
                task_plan = parse_task_plan(plan)
            except ValueError as e:
                return {"error": str(e)}

            task = PlannedTask.create(
                name=name,
                system_prompt=system_prompt,
                prompt=prompt,
                plan=task_plan,
                attachments=attachments,
                context_id=context_id
            )
        else:
            # Create an ad-hoc task
            printer.print(f"Creating AdHocTask with token: '{token}'")
            task = AdHocTask.create(
                name=name,
                system_prompt=system_prompt,
                prompt=prompt,
                token=token,
                attachments=attachments,
                context_id=context_id
            )
            # Verify token after creation
            if isinstance(task, AdHocTask):
                printer.print(f"AdHocTask created with token: '{task.token}'")

        # Add the task to the scheduler
        await scheduler.add_task(task)

        # Verify the task was added correctly - retrieve by UUID to check persistence
        saved_task = scheduler.get_task_by_uuid(task.uuid)
        if saved_task:
            if saved_task.type == TaskType.AD_HOC and isinstance(saved_task, AdHocTask):
                printer.print(f"Task verified after save, token: '{saved_task.token}'")
            else:
                printer.print("Task verified after save, not an adhoc task")
        else:
            printer.print("WARNING: Task not found after save!")

        # Return the created task using our standardized serialization function
        task_dict = serialize_task(task)

        # Debug log the serialized task
        if task_dict and task_dict.get('type') == 'adhoc':
            printer.print(f"Serialized adhoc task, token in response: '{task_dict.get('token')}'")

        return {
            "task": task_dict
        }
