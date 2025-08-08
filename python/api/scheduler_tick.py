from datetime import datetime

from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.print_style import PrintStyle
from python.helpers.task_scheduler import TaskScheduler
from python.helpers.localization import Localization
from python.helpers.user_management import get_user_manager


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

        # Run scheduler for each user by switching central username
        um = get_user_manager()
        original_user = None
        try:
            try:
                original_user = um.get_current_username_safe()
            except Exception:
                original_user = None

            results = []
            for user in um.list_users():
                username = user.username
                try:
                    um.set_central_current_username(username)
                except Exception:
                    pass

                scheduler = TaskScheduler.get()
                await scheduler.reload()

                tasks = scheduler.get_tasks()
                tasks_count = len(tasks)

                printer.print(f"[{username}] Scheduler has {tasks_count} task(s)")
                # Run the scheduler tick for this user's task list
                await scheduler.tick()

                # Collect updated tasks after tick for this user
                serialized_tasks = scheduler.serialize_all_tasks()
                results.append({
                    "user": username,
                    "tasks_count": tasks_count,
                    "tasks": serialized_tasks
                })

            return {
                "scheduler": "tick_all_users",
                "timestamp": timestamp,
                "results": results
            }
        finally:
            # Restore original central username
            try:
                um.set_central_current_username(original_user)
            except Exception:
                pass
