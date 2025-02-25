from python.helpers.tool import Tool, Response
import json

class ResponseTool(Tool):

    async def execute(self,**kwargs):
        return Response(message=self.args, break_loop=True)

    async def before_execution(self, **kwargs):
        self.log = self.agent.context.log.log(type="response", heading=f"{self.agent.agent_name}: Responding", content=json.dumps(self.args))

    
    async def after_execution(self, response, **kwargs):
        pass # do not add anything to the history or output