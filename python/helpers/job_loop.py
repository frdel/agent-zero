import asyncio
from datetime import datetime
import time
from typing import Any
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from agent import Agent, LoopData
from initialize import initialize
from python.helpers import extract_tools
from python.helpers import runtime

SLEEP_TIME = 60

keep_running = True
pause_time = 0


async def run_loop():
    global pause_time, keep_running
    config = initialize()
    agent = Agent(0, config)
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
            await call_extensions(agent, "job_loop", loop_data=LoopData())
        await asyncio.sleep(SLEEP_TIME)  # TODO! - if we lower it under 1min, it can run a 5min job multiple times in it's target minute


async def call_extensions(agent: Agent, folder: str, **kwargs) -> Any:
    from python.helpers.extension import Extension
    classes = extract_tools.load_classes_from_folder(
        "python/extensions/" + folder, "*", Extension
    )
    for cls in classes:
        try:
            await cls(agent=agent).execute(**kwargs)
        except Exception as e:
            PrintStyle().error("Error calling job_loop extension: " + errors.format_error(e))


def pause_loop():
    global keep_running, pause_time
    keep_running = False
    pause_time = time.time()


def resume_loop():
    global keep_running, pause_time
    keep_running = True
    pause_time = 0
