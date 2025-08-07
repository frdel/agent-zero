import asyncio
from datetime import datetime
import time
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from python.helpers import runtime
from python.helpers.extension import call_extensions
from agent import LoopData


SLEEP_TIME = 60

keep_running = True
pause_time = 0


async def run_loop():
    global pause_time, keep_running

    while True:
        if runtime.is_development():
            # Signal to container that the job loop should be paused
            # if we are runing a development instance to avoid duble-running the jobs
            try:
                await runtime.call_development_function(pause_loop)
            except Exception as e:
                PrintStyle().error("Failed to pause job loop by development instance: " + errors.error_text(e))
        if not keep_running and (time.time() - pause_time) > (SLEEP_TIME * 2):
            resume_loop()
        if keep_running:
            try:
                await call_extensions("job_loop", agent=None, loop_data=LoopData())
            except Exception as e:
                PrintStyle().error(errors.format_error(e))
        await asyncio.sleep(SLEEP_TIME)  # TODO! - if we lower it under 1min, it can run a 5min job multiple times in it's target minute


# scheduler_tick function removed - now handled by extensions


def pause_loop():
    global keep_running, pause_time
    keep_running = False
    pause_time = time.time()


def resume_loop():
    global keep_running, pause_time
    keep_running = True
    pause_time = 0
