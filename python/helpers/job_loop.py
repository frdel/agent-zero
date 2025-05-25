import asyncio
from typing import Any
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from agent import Agent, LoopData
from initialize import initialize
from python.helpers import extract_tools


async def run_loop():
    config = initialize()
    agent = Agent(0, config)
    while True:
        await call_extensions(agent, "job_loop", loop_data=LoopData())
        await asyncio.sleep(60)  # TODO! - if we lower it under 1min, it can run a 5min job multiple times in it's target minute


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
