from agent import Agent
from tools.helpers.tool import Tool, Response
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

class TaskDone(Tool):

    def execute(self):
        self.agent.set_data("timeout",0) # wait for user, no timeout
        return Response(message=self.content, stop_tool_processing=True, break_loop=True)

