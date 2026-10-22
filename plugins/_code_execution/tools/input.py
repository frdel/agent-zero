from helpers.tool import Tool, Response
from plugins._code_execution.tools.code_execution_tool import CodeExecution


class Input(Tool):

    async def execute(self, keyboard="", **kwargs):
        # normalize keyboard input
        keyboard = keyboard.rstrip()
        # keyboard += "\n" # no need to, code_exec does that
        
        # terminal session number
        session = int(self.args.get("session", 0))

        # forward keyboard input to code execution tool
        args = {"runtime": "terminal", "code": keyboard, "session": session, "allow_running": True}
        cet = CodeExecution(self.agent, "code_execution_tool", "", args, self.message, self.loop_data)
        cet.log = self.log
        return await cet.execute(**args)

    def get_log_object(self):
        import uuid
        return self.agent.context.log.log(type="code_exe", heading=f"icon://keyboard Using tool '{self.name}'", content="", kvps=self.args, id=str(uuid.uuid4()))

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message, id=self.log.id if self.log else "", **(response.additional or {}))