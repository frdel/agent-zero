from datetime import datetime

from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.print_style import PrintStyle
from python.helpers.task_scheduler import TaskScheduler
from python.helpers.localization import Localization


class SchedulerTick(ApiHandler):
    @classmethod
    def requires_loopback(cls) -> bool:
        return True

    @classmethod
    def requires_auth(cls) -> bool:
        return False

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    async def process(self, input: Input, request: Request) -> Output:
        # Get timezone from input (do not set if not provided, we then rely on poll() to set it)
        if timezone := input.get("timezone", None):
            Localization.get().set_timezone(timezone)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        printer = PrintStyle(font_color="green", padding=False)
        printer.print(f"Scheduler tick - API: {timestamp}")

        # Get the task scheduler instance and print detailed debug info
        scheduler = TaskScheduler.get()
        await scheduler.reload()

        tasks = scheduler.get_tasks()
        tasks_count = len(tasks)

        # Log information about the tasks
        printer.print(f"Scheduler has {tasks_count} task(s)")
        if tasks_count > 0:
            for task in tasks:
                printer.print(f"Task: {task.name} (UUID: {task.uuid}, State: {task.state})")

        # Run the scheduler tick
        await scheduler.tick()

        # Get updated tasks after tick
        serialized_tasks = scheduler.serialize_all_tasks()

        return {
            "scheduler": "tick",
            "timestamp": timestamp,
            "tasks_count": tasks_count,
            "tasks": serialized_tasks
        }
