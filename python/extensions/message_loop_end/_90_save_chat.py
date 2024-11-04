from python.helpers.extension import Extension
from agent import LoopData, Agent
from python.helpers import persist_chat


class SaveChat(Extension):
    async def execute(self, agent: Agent):
        persist_chat.save_tmp_chat(agent.context)
