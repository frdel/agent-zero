from python.helpers.tool import Tool, Response

# example of a tool redefinition
# the original response tool is in python/tools/response.py
# for the example agent this version will be used instead

class ResponseTool(Tool):

    async def execute(self, **kwargs):
        print("Redefined response tool executed")
        return Response(message=self.args["text"] if "text" in self.args else self.args["message"], break_loop=True)

    async def before_execution(self, **kwargs):
        # self.log = self.agent.context.log.log(type="response", heading=f"{self.agent.agent_name}: Responding", content=self.args.get("text", ""))
        # don't log here anymore, we have the live_response extension now
        pass

    async def after_execution(self, response, **kwargs):
        # do not add anything to the history or output

        if self.loop_data and "log_item_response" in self.loop_data.params_temporary:
            log = self.loop_data.params_temporary["log_item_response"]
            log.update(finished=True) # mark the message as finished