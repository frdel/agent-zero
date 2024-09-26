from agent import Agent
from python.helpers.extension import Extension

class WaitingForInputMsg(Extension):

    async def execute(self, loop_data={}, **kwargs):
        # show temp info message
        if self.agent.number == 0:
            self.agent.context.log.log(
                type="util", heading="Waiting for input", temp=True
            )

