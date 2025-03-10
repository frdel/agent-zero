from python.helpers.extension import Extension
from agent import LoopData


class ResetAgentData(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        self.agent.set_data('agent_responded', False)
