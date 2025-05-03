import asyncio
from python.helpers.task_scheduler import TaskScheduler
from python.helpers.print_style import PrintStyle
from python.helpers import errors


async def run_loop():
    while True:
        try:
            await scheduler_tick()
        except Exception as e:
            PrintStyle().error(errors.format_error(e))
        await asyncio.sleep(15)


async def scheduler_tick():
    # Get the task scheduler instance and print detailed debug info
    scheduler = TaskScheduler.get()
    # Run the scheduler tick
    await scheduler.tick()