import asyncio
from python.helpers.extension import Extension
from agent import LoopData
from python.helpers.task_scheduler import TaskScheduler


class ExecuteSchedulerTick(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        scheduler = TaskScheduler.get()
        await scheduler.tick()
