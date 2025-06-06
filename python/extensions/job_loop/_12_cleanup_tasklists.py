from datetime import datetime, timezone, timedelta
from agent import LoopData, AgentContext, AgentContextType
from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle
from python.helpers.tasklist import TaskList


class CleanupTasklists(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        context_ids = list(TaskList.get_all().keys())
        for context_id in context_ids:
            context = AgentContext.get(context_id)
            if not context:
                PrintStyle().debug(f"Tasklist {context_id} - context not found - removing")
                TaskList.delete_instance(context_id)
                continue
