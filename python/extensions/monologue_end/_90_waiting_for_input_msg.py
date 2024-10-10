from python.helpers.extension import Extension
from agent import LoopData

class WaitingForInputMsg(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # show temp info message
        if self.agent.number == 0:
            self.agent.context.log.log(
                type="util", heading="Waiting for input", temp=True
            )

