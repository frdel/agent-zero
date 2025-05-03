from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
from python.tools.code_execution_tool import CodeExecution


class Input(Tool):

    async def execute(self, keyboard="", **kwargs):
        # normalize keyboard input
        keyboard = keyboard.rstrip()
        keyboard += "\n"

        # forward keyboard input to code execution tool
        args = {"runtime": "terminal", "code": keyboard}
        cot = CodeExecution(self.agent, "code_execution_tool", "", args, self.message)
        cot.log = self.log
        return await cot.execute(**args)

    def get_log_object(self):
        return self.agent.context.log.log(type="code_exe", heading=f"{self.agent.agent_name}: Using tool '{self.name}'", content="", kvps=self.args)

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message)