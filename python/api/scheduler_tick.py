from datetime import datetime

from python.helpers.api import ApiHandler, Input, Output, Request
from python.helpers.print_style import PrintStyle
from python.helpers.task_scheduler import TaskScheduler


class SchedulerTick(ApiHandler):
    @classmethod
    def requires_loopback(cls):
        return True

    async def process(self, input: Input, request: Request) -> Output:
        # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # PrintStyle().print(f"Scheduler tick - API: {timestamp}")
        await TaskScheduler.get().tick()
        return {"scheduler": "tick"}
