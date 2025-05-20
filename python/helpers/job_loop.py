import asyncio
from python.helpers.task_scheduler import TaskScheduler
from python.helpers.print_style import PrintStyle
from python.helpers import errors
from agent import AgentContext, AgentContextType
from datetime import datetime, timezone, timedelta
from python.helpers.persist_chat import remove_chat


async def run_loop():
    while True:
        # scheduler tick
        try:
            await scheduler_tick()
        except Exception as e:
            PrintStyle().error(errors.format_error(e))

        # cleanup tmp chats
        try:
            await cleanup_tmp_chats()
        except Exception as e:
            PrintStyle().error(errors.format_error(e))

        await asyncio.sleep(60)  # TODO! - if we lower it under 1min, it can run a 5min job multiple times in it's target minute


async def scheduler_tick():
    # Get the task scheduler instance and print detailed debug info
    scheduler = TaskScheduler.get()
    # Run the scheduler tick
    await scheduler.tick()


async def cleanup_tmp_chats():
    contexts = list(AgentContext._contexts.values())
    for context in contexts:
        if context.type == AgentContextType.MCP:
            if context.last_message < datetime.now(timezone.utc) - timedelta(hours=1):
                PrintStyle().debug(f"MCP chat {context.id} - {context.last_message} - cleaning up")
                context.reset()
                AgentContext.remove(context.id)
                remove_chat(context.id)
