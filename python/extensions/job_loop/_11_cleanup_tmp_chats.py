from datetime import datetime, timezone, timedelta
from agent import LoopData, AgentContext, AgentContextType
from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle


class CleanupTmpChats(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        contexts = list(AgentContext._contexts.values())
        for context in contexts:
            if context.type == AgentContextType.MCP:
                if context.last_message < datetime.now(timezone.utc) - timedelta(hours=1):
                    PrintStyle().debug(f"MCP chat {context.id} - {context.last_message} - cleaning up")
                    context.reset()
                    AgentContext.remove(context.id)
