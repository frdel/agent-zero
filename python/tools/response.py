from python.helpers.tool import Tool, Response
import time


class ResponseTool(Tool):

    async def execute(self,**kwargs):
        return Response(message=self.args["text"], break_loop=True)

    async def before_execution(self, **kwargs):
        monolog_duration = time.strftime("%H:%M:%S", time.gmtime(time.time() - int(self.agent.get_data('monolog_start'))))
        self.log = self.agent.context.log.log(
            type="response",
            heading=f"{self.agent.agent_name}: Responding (Duration: {monolog_duration})",
            content=self.args.get("text", ""),
        )

    async def after_execution(self, response, **kwargs):
        pass # do not add anything to the history or output
