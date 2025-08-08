from python.helpers.extension import Extension
from agent import LoopData, AgentContextType
from python.helpers import persist_chat


class SaveChat(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Skip saving BACKGROUND contexts as they should be ephemeral
        if self.agent.context.type == AgentContextType.BACKGROUND:
            return

        persist_chat.save_tmp_chat(self.agent.context)
