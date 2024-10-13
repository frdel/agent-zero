from python.helpers.extension import Extension
from agent import LoopData
from python.helpers import persist_chat


class SaveChat(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        persist_chat.save_chat(self.agent.context)