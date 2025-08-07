from python.helpers.extension import Extension
from python.helpers.task_scheduler import TaskScheduler
from agent import LoopData


class ExecuteSchedulerTick(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Execute the main scheduler tick - runs scheduled tasks"""
        scheduler = TaskScheduler.get()
        await scheduler.tick()
